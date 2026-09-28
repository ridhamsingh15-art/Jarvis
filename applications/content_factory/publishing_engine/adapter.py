"""
Adapter mapping Project Bundle to n8n payloads.
"""
from core.integrations.n8n.workflow_runner import N8nWorkflowRunner
from applications.content_factory.project.models import ProjectBundle
from .models import PublishRequest

class PublishingAdapter:
    """Adapter to trigger n8n workflows for publishing."""
    
    def __init__(self, runner: N8nWorkflowRunner) -> None:
        self._n8n_runner = runner
        
    def publish(self, bundle: ProjectBundle, request: PublishRequest) -> bool:
        # Mock mapping of bundle to n8n payload
        payload = {
            "project_id": bundle.metadata.project_id,
            "mode": request.mode,
            "platforms": request.platforms,
            "seo_metadata": bundle.metadata.seo_metadata
        }
        
        # We would run this via n8n:
        # result = self._n8n_runner.run_workflow("youtube_publish_workflow", payload)
        # return result.success
        
        return True
