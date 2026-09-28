"""
Data models for the Autonomous Business Operating System.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Optional


class BusinessType(StrEnum):
    CONTENT = "content"
    SAAS = "saas"
    AGENCY = "agency"
    DIGITAL_PRODUCT = "digital_product"
    ECOMMERCE = "ecommerce"
    CONSULTING = "consulting"


@dataclass(frozen=True, kw_only=True)
class BusinessGoal:
    """A high-level business objective."""
    description: str
    target_date: Optional[str] = None
    target_revenue: Optional[float] = None


@dataclass(frozen=True, kw_only=True)
class MarketAnalysis:
    """Output from the strategy module."""
    target_audience: str
    competitors: list[str]
    unique_value_proposition: str
    market_size: str


@dataclass(frozen=True, kw_only=True)
class MarketingStrategy:
    """Output from the marketing module."""
    channels: list[str]
    content_themes: list[str]
    budget_allocation: dict[str, float]


@dataclass(frozen=True, kw_only=True)
class BusinessPlan:
    """A comprehensive business plan."""
    business_id: str = field(default_factory=lambda: f"biz_{uuid.uuid4().hex[:8]}")
    type: BusinessType
    goal: BusinessGoal
    market_analysis: MarketAnalysis
    marketing_strategy: MarketingStrategy
    required_missions: list[str] = field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class KPI:
    """Key Performance Indicator."""
    name: str
    value: float
    target: float
    unit: str


@dataclass(frozen=True, kw_only=True)
class FinancialReport:
    """Output from the finance module."""
    revenue: float
    expenses: float
    profit: float
    burn_rate: float
    kpis: list[KPI] = field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class BusinessReport:
    """Final output aggregating performance."""
    business_id: str
    financials: FinancialReport
    marketing_metrics: dict[str, float]
    recommendations: list[str]
