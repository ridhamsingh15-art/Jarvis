"""
Planner Agent for BusinessOS.

Translates broad user objectives into structured BusinessPlans.
"""
import logging
from typing import Any
from .models import BusinessGoal, BusinessPlan, BusinessType, MarketingStrategy
from .strategy import StrategyAgent
from .exceptions import PlanningError

logger = logging.getLogger(__name__)

class BusinessPlanner:
    """Agent that generates the overarching business plan."""

    def __init__(self, llm_client: Any):
        self._llm_client = llm_client
        self._strategy_agent = StrategyAgent(llm_client)

    def _determine_business_type(self, goal: BusinessGoal) -> BusinessType:
        """Use heuristics to determine business type."""
        desc = goal.description.lower()
        if "youtube" in desc or "blog" in desc or "content" in desc:
            return BusinessType.CONTENT
        if "saas" in desc or "software" in desc or "app" in desc:
            return BusinessType.SAAS
        if "agency" in desc or "service" in desc:
            return BusinessType.AGENCY
        if "product" in desc or "ecommerce" in desc:
            return BusinessType.ECOMMERCE
        
        # Default fallback
        return BusinessType.CONSULTING

    def create_plan(self, goal: BusinessGoal) -> BusinessPlan:
        """
        Generate a full BusinessPlan.
        """
        logger.info("Creating business plan...")
        
        try:
            biz_type = self._determine_business_type(goal)
            
            # Delegate to strategy agent for market analysis
            market_analysis = self._strategy_agent.analyze_market(goal, biz_type)
            
            # Stub marketing strategy
            marketing_strategy = MarketingStrategy(
                channels=["Twitter", "LinkedIn"],
                content_themes=["Automation", "AI"],
                budget_allocation={"Ads": 0.0, "Content": 1000.0}
            )
            
            # Determine required missions
            required_missions = []
            if biz_type == BusinessType.CONTENT:
                required_missions.append("content_factory_generate_scripts")
            elif biz_type == BusinessType.SAAS:
                required_missions.append("software_engineer_build_mvp")
            else:
                required_missions.append("custom_mission_setup")
                
            return BusinessPlan(
                type=biz_type,
                goal=goal,
                market_analysis=market_analysis,
                marketing_strategy=marketing_strategy,
                required_missions=required_missions
            )
        except Exception as e:
            raise PlanningError(f"Failed to create business plan: {e}") from e
