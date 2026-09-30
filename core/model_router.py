"""
Core implementation of the Model Router subsystem.
"""

import logging
import time

from config.model_config import ModelRouterConfig
from core.model_gateway import ModelGateway
from providers.capabilities import Capability
from providers.fallback_manager import FallbackManager
from providers.health_monitor import HealthMonitor
from providers.provider_models import (
    AllProvidersExhaustedError,
    EmbeddingResponse,
    InferenceRequirements,
    ModelResponse,
    NoCapableProviderError,
    ProviderExecutionError,
)
from providers.provider_registry import ProviderRegistry
from providers.selection_policy import SelectionPolicy

logger = logging.getLogger(__name__)


class ModelRouter(ModelGateway):
    """Orchestrates AI inference routing across multiple providers."""

    def __init__(
        self,
        config: ModelRouterConfig,
        registry: ProviderRegistry,
        selection_policy: SelectionPolicy,
        fallback_manager: FallbackManager,
        health_monitor: HealthMonitor,
    ) -> None:
        """Initialize the ModelRouter.
        
        Args:
            config: Router configuration defaults.
            registry: Source of truth for available providers.
            selection_policy: Strategy for ranking candidate providers.
            fallback_manager: Handles fallback iteration logic.
            health_monitor: Tracks success/failure of providers.
        """
        self._config = config
        self._registry = registry
        self._selection_policy = selection_policy
        self._fallback_manager = fallback_manager
        self._health_monitor = health_monitor

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        requirements: InferenceRequirements | None = None,
    ) -> ModelResponse:
        """Execute text generation with optimal provider routing."""
        
        # 1. Prepare requirements
        reqs = self._merge_requirements(requirements, default_capability=Capability.CHAT)
        
        # 2. Filter candidates
        candidates = self._get_capable_candidates(reqs.capabilities)
        if not candidates:
            raise NoCapableProviderError(
                f"No registered, healthy providers support capabilities: {reqs.capabilities}"
            )
            
        # 3. Rank candidates
        ranked_candidates = self._selection_policy.rank_providers(candidates, reqs)
        
        # 4. Create fallback chain
        chain = self._fallback_manager.create_chain(ranked_candidates)
        
        # 5. Execute with fallback
        last_error: tuple[str, Exception] | None = None
        while True:
            try:
                provider = chain.get_next()
            except AllProvidersExhaustedError as e:
                # Chain is exhausted. Raise with details of the last failure.
                msg = f"All {len(ranked_candidates)} capable providers failed."
                if last_error:
                    msg += f" Last error from {last_error[0]}: {last_error[1]}"
                logger.error(msg)
                raise AllProvidersExhaustedError(msg) from e

            start_llm = time.time()
            try:
                logger.info("Routing request to provider: %s", provider.provider_id)
                response = provider.generate(system_prompt, user_prompt, reqs)
                end_llm = time.time()
                
                # Success
                self._health_monitor.mark_success(provider.provider_id)

                try:
                    from core.runtime_trace import get_current_trace
                    from core.context_budget import estimate_tokens
                    trace = get_current_trace()
                    if trace is not None:
                        in_tok = (
                            response.token_usage.get("prompt_tokens")
                            if response.token_usage and isinstance(response.token_usage, dict)
                            else estimate_tokens(system_prompt + " " + user_prompt)
                        )
                        out_tok = (
                            response.token_usage.get("completion_tokens")
                            if response.token_usage and isinstance(response.token_usage, dict)
                            else estimate_tokens(response.text)
                        )
                        trace.record_llm_call(
                            model=response.model_id or getattr(reqs, "prefer_model", "default") or "default",
                            provider=response.provider_id or getattr(provider, "provider_id", "unknown"),
                            role=getattr(reqs, "role", "assistant") or "assistant",
                            stage=getattr(reqs, "stage", "router") if hasattr(reqs, "stage") else "router",
                            start_time=start_llm,
                            end_time=end_llm,
                            estimated_input_tokens=in_tok,
                            estimated_output_tokens=out_tok,
                            context_budget=trace.context_budget,
                            truncated=bool(trace.context_budget.get("truncated")) if trace.context_budget else False,
                            success=True,
                        )
                except Exception:
                    pass
                
                # Inject fallback count into response envelope
                # Create a new instance because ModelResponse is frozen
                return ModelResponse(
                    text=response.text,
                    provider_id=response.provider_id,
                    model_id=response.model_id,
                    latency_ms=response.latency_ms,
                    fallback_count=chain.fallback_count,
                    token_usage=response.token_usage,
                    cost=response.cost,
                )
                
            except ProviderExecutionError as exc:
                # Failure
                end_llm = time.time()
                try:
                    from core.runtime_trace import get_current_trace
                    from core.context_budget import estimate_tokens
                    trace = get_current_trace()
                    if trace is not None:
                        trace.record_llm_call(
                            model=getattr(reqs, "prefer_model", "default") or "default",
                            provider=getattr(provider, "provider_id", "unknown"),
                            role=getattr(reqs, "role", "assistant") or "assistant",
                            stage="router",
                            start_time=start_llm,
                            end_time=end_llm,
                            estimated_input_tokens=estimate_tokens(system_prompt + " " + user_prompt),
                            context_budget=trace.context_budget,
                            success=False,
                            error_category=type(exc).__name__,
                            error_message=str(exc),
                        )
                except Exception:
                    pass
                logger.warning(
                    "Provider %s failed: %s. Initiating fallback...",
                    provider.provider_id,
                    exc,
                )
                self._health_monitor.mark_failure(provider.provider_id)
                last_error = (provider.provider_id, exc)
            except Exception as exc:  # noqa: BLE001
                # Unexpected failure, but we still fallback
                logger.warning(
                    "Provider %s failed unexpectedly: %s. Initiating fallback...",
                    provider.provider_id,
                    exc,
                )
                self._health_monitor.mark_failure(provider.provider_id)
                last_error = (provider.provider_id, exc)

    def embed(
        self,
        text: str,
        requirements: InferenceRequirements | None = None,
    ) -> EmbeddingResponse:
        """Execute text embedding with optimal provider routing."""
        
        reqs = self._merge_requirements(requirements, default_capability=Capability.EMBEDDINGS)
        
        candidates = self._get_capable_candidates(reqs.capabilities)
        if not candidates:
            raise NoCapableProviderError(
                f"No registered, healthy providers support capabilities: {reqs.capabilities}"
            )
            
        ranked_candidates = self._selection_policy.rank_providers(candidates, reqs)
        chain = self._fallback_manager.create_chain(ranked_candidates)
        
        last_error: tuple[str, Exception] | None = None
        while True:
            try:
                provider = chain.get_next()
            except AllProvidersExhaustedError as e:
                msg = f"All {len(ranked_candidates)} capable providers failed."
                if last_error:
                    msg += f" Last error from {last_error[0]}: {last_error[1]}"
                logger.error(msg)
                raise AllProvidersExhaustedError(msg) from e

            try:
                logger.info("Routing embed request to provider: %s", provider.provider_id)
                response = provider.embed(text, reqs)
                self._health_monitor.mark_success(provider.provider_id)
                return response
                
            except ProviderExecutionError as exc:
                logger.warning("Provider %s embed failed: %s", provider.provider_id, exc)
                self._health_monitor.mark_failure(provider.provider_id)
                last_error = (provider.provider_id, exc)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Provider %s embed failed unexpectedly: %s", provider.provider_id, exc)
                self._health_monitor.mark_failure(provider.provider_id)
                last_error = (provider.provider_id, exc)

    def _merge_requirements(
        self, 
        reqs: InferenceRequirements | None, 
        default_capability: Capability
    ) -> InferenceRequirements:
        """Merge user requirements with defaults from config."""
        if not reqs:
            caps = frozenset([default_capability])
            return InferenceRequirements(
                capabilities=caps,
                prefer_local=self._config.prefer_local,
            )
            
        # If requirements exist, ensure the default capability is included
        # if the user didn't specify any capabilities.
        caps = reqs.capabilities if reqs.capabilities else frozenset([default_capability])
        
        return InferenceRequirements(
            capabilities=caps,
            max_latency_ms=reqs.max_latency_ms,
            max_cost_per_request=reqs.max_cost_per_request,
            min_context_length=reqs.min_context_length,
            prefer_local=reqs.prefer_local,
            prefer_provider=reqs.prefer_provider,
            task_complexity=reqs.task_complexity,
            prefer_model=reqs.prefer_model,
            role=reqs.role,
        )

    def _get_capable_candidates(self, required_capabilities: frozenset[Capability]) -> list:
        """Get all healthy providers that support all required capabilities."""
        healthy_providers = self._registry.list_healthy_providers()
        
        candidates = []
        for provider in healthy_providers:
            if all(provider.supports(cap) for cap in required_capabilities):
                candidates.append(provider)
                
        return candidates
