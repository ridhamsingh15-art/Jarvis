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
        capable_count = len(candidates)
        candidates = self._apply_request_constraints(
            candidates, reqs, system_prompt + "\n" + user_prompt
        )
        if not candidates:
            raise NoCapableProviderError(
                "No capable provider meets the requested latency/cost constraints. "
                f"Providers before constraints: {capable_count}."
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
                self._health_monitor.record_latency(provider.provider_id, response.latency_ms)

                try:
                    from core.context_budget import estimate_tokens
                    from core.runtime_trace import get_current_trace
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
                except Exception as exc:  # noqa: BLE001 - tracing is best-effort
                    logger.debug("Could not record successful LLM trace (%s)", type(exc).__name__)
                
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
                    from core.context_budget import estimate_tokens
                    from core.runtime_trace import get_current_trace
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
                except Exception as trace_exc:  # noqa: BLE001 - tracing must not mask provider failures
                    logger.debug("Could not record failed LLM trace (%s)", type(trace_exc).__name__)
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
        capable_count = len(candidates)
        candidates = self._apply_request_constraints(
            candidates, reqs, text, embedding=True
        )
        if not candidates:
            raise NoCapableProviderError(
                "No capable provider meets the requested latency/cost constraints "
                f"for embeddings. Providers before constraints: {capable_count}."
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
                self._health_monitor.record_latency(provider.provider_id, response.latency_ms)
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
        default_capability: Capability,
    ) -> InferenceRequirements:
        """Merge request constraints with the configured provider strategy.

        An explicit request preference wins. Otherwise prefer the provider assigned
        to the semantic role, while still filtering candidates by actual capability.
        """
        if reqs is None:
            caps = frozenset([default_capability])
            role = None
            merged = InferenceRequirements(
                capabilities=caps,
                prefer_local=self._config.prefer_local,
            )
        else:
            caps = reqs.capabilities if reqs.capabilities else frozenset([default_capability])
            merged = InferenceRequirements(
                capabilities=caps,
                max_latency_ms=reqs.max_latency_ms,
                max_cost_per_request=reqs.max_cost_per_request,
                max_output_tokens=reqs.max_output_tokens,
                min_context_length=reqs.min_context_length,
                prefer_local=reqs.prefer_local,
                prefer_provider=reqs.prefer_provider,
                task_complexity=reqs.task_complexity,
                prefer_model=reqs.prefer_model,
                role=reqs.role,
            )
            role = (reqs.role or "").strip().lower()

        configured = None
        if role in {"reasoning", "research"} or Capability.REASONING in caps:
            configured = self._config.default_reasoning_provider
        elif role == "coding" or Capability.CODING in caps:
            configured = self._config.default_coding_provider
        elif role == "vision" or Capability.VISION in caps:
            configured = self._config.default_vision_provider
        elif role == "fast" or Capability.TOOL_USE in caps:
            configured = self._config.default_fast_provider
        else:
            configured = self._config.default_chat_provider

        preferred = merged.prefer_provider or configured
        if preferred == merged.prefer_provider:
            return merged
        return InferenceRequirements(
            capabilities=merged.capabilities,
            max_latency_ms=merged.max_latency_ms,
            max_cost_per_request=merged.max_cost_per_request,
            max_output_tokens=merged.max_output_tokens,
            min_context_length=merged.min_context_length,
            prefer_local=merged.prefer_local,
            prefer_provider=preferred,
            task_complexity=merged.task_complexity,
            prefer_model=merged.prefer_model,
            role=merged.role,
        )

    def _apply_request_constraints(
        self,
        candidates: list,
        requirements: InferenceRequirements,
        prompt_text: str,
        *,
        embedding: bool = False,
    ) -> list:
        """Filter providers that cannot meet known latency and cost constraints.

        Cold-start latency is unknown and therefore remains eligible, but providers
        with a measured latency above the caller's ceiling are not selected. Cost
        ceilings are conservative estimates, not billing guarantees: cloud routing
        requires an output-token cap and a provider/model with a known estimator.
        """
        eligible = list(candidates)
        if requirements.min_context_length is not None:
            context_eligible = []
            for provider in eligible:
                try:
                    context_window = provider.context_window_tokens(requirements)
                except Exception as exc:  # noqa: BLE001 - capability metadata must not abort routing
                    logger.warning(
                        "Context-window metadata unavailable for provider %s (%s)",
                        provider.provider_id,
                        type(exc).__name__,
                    )
                    context_window = None
                if context_window is None or context_window >= requirements.min_context_length:
                    context_eligible.append(provider)
            eligible = context_eligible

        if requirements.max_latency_ms is not None:
            unknown_latency = []
            within_latency = []
            for provider in eligible:
                observed = self._health_monitor.average_latency_ms(provider.provider_id)
                if observed is None:
                    unknown_latency.append(provider)
                elif observed <= requirements.max_latency_ms:
                    within_latency.append(provider)
            # An unseen provider is retained until measured; if all observations
            # violate the ceiling, we fail closed instead of knowingly exceeding it.
            eligible = within_latency + unknown_latency

        if requirements.max_cost_per_request is not None:
            from math import ceil

            from core.context_budget import estimate_tokens

            estimated_input_tokens = max(1, ceil(estimate_tokens(prompt_text) * 1.15))
            bounded = []
            for provider in eligible:
                try:
                    if embedding:
                        model_id = getattr(provider, "_default_embed_model", None)
                        estimated_cost = provider.estimate_embedding_cost(
                            estimated_input_tokens, model_id
                        )
                    elif provider.is_local:
                        # Local inference does not incur provider token charges.
                        estimated_cost = provider.estimate_cost(
                            estimated_input_tokens,
                            requirements.max_output_tokens or 0,
                            provider.resolve_model_id(requirements),
                        )
                    elif requirements.max_output_tokens is None:
                        # Without an output ceiling, a monetary upper bound cannot be
                        # estimated safely; do not silently treat a cloud request as free.
                        continue
                    else:
                        model_id = provider.resolve_model_id(requirements)
                        estimated_cost = provider.estimate_cost(
                            estimated_input_tokens, requirements.max_output_tokens, model_id
                        )
                except Exception as exc:  # noqa: BLE001 - unknown pricing must fail closed
                    logger.warning(
                        "Cost estimate unavailable for provider %s (%s)",
                        provider.provider_id,
                        type(exc).__name__,
                    )
                    continue
                if estimated_cost is not None and estimated_cost <= requirements.max_cost_per_request:
                    bounded.append(provider)
            eligible = bounded
        return eligible

    def _get_capable_candidates(self, required_capabilities: frozenset[Capability]) -> list:
        """Get all healthy providers that support all required capabilities."""
        healthy_providers = self._registry.list_healthy_providers()
        
        candidates = []
        for provider in healthy_providers:
            if all(provider.supports(cap) for cap in required_capabilities):
                candidates.append(provider)
                
        return candidates
