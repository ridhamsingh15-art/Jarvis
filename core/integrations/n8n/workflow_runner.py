"""
Workflow Runner linking n8n execution with Mission Control.
"""

import logging
import threading
import time
from typing import Any

from core.mission.enums import MissionStatus
from core.mission.manager import MissionManager
from core.mission.models import Mission
from core.models import Metadata

from .client import N8nClient
from .exceptions import N8nConnectionError, N8nExecutionError
from .models import N8nWorkflow
from .telemetry import N8nTelemetry

logger = logging.getLogger(__name__)


class N8nWorkflowRunner:
    """Executes n8n workflows and maps them to Mission Control."""

    def __init__(
        self,
        client: N8nClient,
        mission_manager: MissionManager,
        telemetry: N8nTelemetry,
    ) -> None:
        self._client = client
        self._mission_manager = mission_manager
        self._telemetry = telemetry

    def execute_async(self, workflow: N8nWorkflow, payload: dict[str, Any]) -> str:
        """Starts a workflow and monitors it in the background via Mission Control.
        
        Returns the Mission ID.
        """
        # Create a Mission
        mission = Mission(
            title=f"n8n Workflow: {workflow.name}",
            description=workflow.description,
            metadata=Metadata(annotations={"workflow_id": workflow.id, "payload": payload})
        )
        mission = self._mission_manager.create(mission)
        self._mission_manager.queue(mission.mission_id.value)

        # Launch background thread to execute and monitor
        thread = threading.Thread(
            target=self._run_and_monitor,
            args=(mission.mission_id.value, workflow, payload),
            daemon=True
        )
        thread.start()
        
        return mission.mission_id.value

    def _run_and_monitor(self, mission_id: str, workflow: N8nWorkflow, payload: dict[str, Any]) -> None:
        try:
            self._mission_manager.ready(mission_id)
            self._mission_manager.resume(mission_id)
            
            # Start execution
            start_time = time.time()
            execution_id = self._client.execute_workflow(workflow.id, payload)
            
            self._telemetry.emit_workflow_started(workflow.name, execution_id)
            
            # Save the n8n execution ID into the mission metadata
            mission = self._mission_manager.get(mission_id)
            meta_data = dict(mission.metadata.annotations)
            meta_data["n8n_execution_id"] = execution_id
            mission = self._mission_manager.update(mission_id, metadata=Metadata(annotations=meta_data))
            
            # Poll status
            is_finished = False
            status_data = None
            
            # Note: n8n execution endpoints can take some time.
            # We poll every 2 seconds.
            while not is_finished:
                # Check if mission was cancelled by JARVIS
                current_mission = self._mission_manager.get(mission_id)
                if current_mission.status == MissionStatus.CANCELLED:
                    logger.info("Mission %s was cancelled, stopping n8n execution %s", mission_id, execution_id)
                    self._client.stop_execution(execution_id)
                    break

                status_data = self._client.get_execution_status(execution_id)
                is_finished = status_data.get("finished", False)
                if not is_finished:
                    time.sleep(2.0)
                    
            if current_mission.status == MissionStatus.CANCELLED:
                return
                
            duration = time.time() - start_time
            
            # Resolve final state
            # "status" inside n8n response could be "success", "error", "canceled", etc.
            # However, "finished" being true typically means it stopped running.
            
            n8n_status = "success"  # Placeholder, should parse from status_data if available
            
            if status_data and status_data.get("data", {}).get("resultData", {}).get("error"):
                n8n_status = "error"
                
            if n8n_status == "error":
                error_msg = "Unknown n8n error"
                if status_data:
                    error_msg = str(status_data.get("data", {}).get("resultData", {}).get("error", "Unknown error"))
                self._mission_manager.fail(mission_id)
                self._telemetry.emit_workflow_failed(workflow.name, execution_id, error_msg)
            else:
                self._mission_manager.complete(mission_id)
                output_data = status_data.get("data", {}) if status_data else {}
                self._telemetry.emit_workflow_output(workflow.name, execution_id, output_data)
                self._telemetry.emit_workflow_finished(workflow.name, execution_id, duration)
                
        except (N8nConnectionError, N8nExecutionError) as e:
            logger.error("Workflow run failed for mission %s: %s", mission_id, e)
            try:
                self._mission_manager.fail(mission_id)
            except Exception as inner_e:
                logger.error("Failed to mark mission as failed: %s", inner_e)
        except Exception:
            logger.exception("Unexpected error in workflow runner")
            try:
                self._mission_manager.fail(mission_id)
            except Exception:
                pass
