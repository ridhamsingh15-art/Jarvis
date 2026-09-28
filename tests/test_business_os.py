"""
Tests for the Autonomous Business Operating System.
"""
import pytest
from unittest.mock import Mock

from applications.business_os.models import BusinessGoal, BusinessType
from applications.business_os.manager import BusinessOSManager
from applications.business_os.planner import BusinessPlanner
from applications.business_os.finance import FinanceAgent
from applications.business_os.exceptions import FinancialConstraintError

class TestBusinessPlanner:
    def test_determine_business_type(self):
        planner = BusinessPlanner(llm_client=Mock())
        
        goal_content = BusinessGoal(description="Launch a new YouTube channel about AI.")
        assert planner._determine_business_type(goal_content) == BusinessType.CONTENT
        
        goal_saas = BusinessGoal(description="Build a B2B SaaS application.")
        assert planner._determine_business_type(goal_saas) == BusinessType.SAAS
        
    def test_create_plan(self):
        planner = BusinessPlanner(llm_client=Mock())
        goal = BusinessGoal(description="Launch a new YouTube channel about AI.")
        plan = planner.create_plan(goal)
        
        assert plan.type == BusinessType.CONTENT
        assert "content_factory_generate_scripts" in plan.required_missions

class TestFinanceAgent:
    def test_execute_transaction_is_blocked(self):
        finance = FinanceAgent()
        with pytest.raises(FinancialConstraintError):
            finance.execute_transaction(100.0, "vendor")

class TestBusinessOSManager:
    def test_launch_business(self):
        mock_runtime = Mock()
        manager = BusinessOSManager(llm_client=Mock(), ai_runtime=mock_runtime)
        
        report = manager.launch_business("Build a B2B SaaS application.")
        
        assert report.business_id.startswith("biz_")
        assert report.financials.revenue == 1000.0
        assert len(report.recommendations) > 0
