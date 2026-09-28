"""
BusinessOS Manager.

Facade for the Autonomous Business Operating System.
"""
import logging
from typing import Any

from .models import BusinessGoal, BusinessReport, BusinessPlan
from .planner import BusinessPlanner
from .execution import ExecutionManager
from .finance import FinanceAgent
from .analytics import AnalyticsAgent
from .marketing import MarketingAgent
from .forecasting import ForecastingAgent
from .exceptions import BusinessOSError

logger = logging.getLogger(__name__)

class BusinessOSManager:
    """Central facade for the Business Operating System."""

    def __init__(self, llm_client: Any, ai_runtime: Any):
        self._llm_client = llm_client
        
        self._planner = BusinessPlanner(llm_client)
        self._execution = ExecutionManager(ai_runtime)
        self._finance = FinanceAgent()
        self._analytics = AnalyticsAgent(llm_client)
        self._marketing = MarketingAgent(llm_client)
        self._forecasting = ForecastingAgent(llm_client)

    def launch_business(self, goal_description: str) -> BusinessReport:
        """
        Plan and launch a new business based on a goal.
        """
        logger.info(f"Launching business for goal: {goal_description}")
        
        goal = BusinessGoal(description=goal_description)
        
        try:
            # 1. Plan
            plan = self._planner.create_plan(goal)
            
            # 2. Execute
            self._execution.execute_plan(plan)
            
            # 3. Analyze & Report
            financials = self._finance.generate_report()
            kpis = self._analytics.analyze_metrics()
            forecast = self._forecasting.forecast_growth()
            
            return BusinessReport(
                business_id=plan.business_id,
                financials=financials,
                marketing_metrics={},
                recommendations=[forecast]
            )
            
        except Exception as e:
            raise BusinessOSError(f"BusinessOS failed to launch business: {e}") from e
