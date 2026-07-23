# Model Router — Subsystem Design Document

**Author**: Lead Software Engineer, Jarvis Core Team
**Status**: DRAFT — Pending Architectural Review
**Version**: 1.0.0
**Date**: 2026-07-23
**Target Release**: v0.9+
**Lifetime Expectation**: 10+ years

---

## Table of Contents

1. [Purpose](#1-purpose)
2. [Responsibilities](#2-responsibilities)
3. [Non-Responsibilities](#3-non-responsibilities)
4. [Public Interfaces](#4-public-interfaces)
5. [Internal Components](#5-internal-components)
6. [Provider Lifecycle](#6-provider-lifecycle)
7. [Capability System](#7-capability-system)
8. [Routing Strategy](#8-routing-strategy)
9. [Fallback Strategy](#9-fallback-strategy)
10. [Error Handling](#10-error-handling)
11. [Logging Strategy](#11-logging-strategy)
12. [Configuration](#12-configuration)
13. [Future Expansion](#13-future-expansion)
14. [UML Diagrams](#14-uml-diagrams)
15. [Testing Strategy](#15-testing-strategy)

---

## 1. Purpose

### Problem Statement

Jarvis today is hard-coupled to a single LLM provider. The `Planner` directly depends on `LLMClient`, which directly depends on the `ollama` Python SDK. This creates three critical limitations:

1. **Vendor Lock-In** — Switching to Gemini, OpenAI, Claude, or DeepSeek requires rewriting `LLMClient` and every caller.
2. **No Intelligent Selection** — The user manually sets `JARVIS_MODEL` via an environment variable. The system cannot choose the optimal model for a given request.
3. **No Resilience** — If Ollama crashes, the entire pipeline fails. There is no fallback, no retry across providers, no graceful degradation.

### Solution

The **Model Router** is an abstraction layer that sits between the Jarvis pipeline and all AI providers. It:

- Presents a **single, stable interface** to the rest of Jarvis (identical to the current `generate()` contract).
- Maintains a **registry of providers** with declared capabilities, health status, and cost profiles.
- **Automatically selects the best provider** for each request based on required capabilities, availability, cost, latency, user preferences, and network conditions.
- **Falls back transparently** when a provider fails, ensuring the pipeline never sees a single-provider outage as a fatal error.

### Design Philosophy

> The best provider decision is the one the user never has to make.

The user interacts with Jarvis. Jarvis interacts with the Model Router. The Model Router interacts with providers. The user never knows — and never needs to know — which model answered.

### Integration Surface

The Model Router replaces the current `LLMClient` in the dependency graph:

```
BEFORE:
    Config → LLMClient → Planner

AFTER:
    Config → ModelRouter → Planner
                 │
                 ├── OllamaProvider
                 ├── GeminiProvider
                 ├── OpenAIProvider
                 ├── ClaudeProvider
                 ├── DeepSeekProvider
                 └── ... (future)
```

The `Planner` continues to call `generate(system_prompt, user_prompt) → str`. It is completely unaware that routing is happening.

---

## 2. Responsibilities

The Model Router subsystem is responsible for:

| # | Responsibility | Description |
|---|---|---|
| R1 | **Provider Abstraction** | Hide all provider-specific SDKs, APIs, authentication, and wire protocols behind a uniform interface. |
| R2 | **Capability Declaration** | Maintain a registry of what each provider can do (chat, vision, embeddings, audio, reasoning, tool-use). |
| R3 | **Intelligent Routing** | For every inference request, select the optimal provider based on required capabilities, availability, cost, latency, and preferences. |
| R4 | **Transparent Fallback** | When the selected provider fails, automatically retry with the next-best provider. The caller never sees the retry. |
| R5 | **Health Monitoring** | Continuously track provider availability. Remove unhealthy providers from the candidate pool. Restore them when they recover. |
| R6 | **Configuration Management** | Load provider definitions and routing policies from configuration files. Support hot-reload without restart. |
| R7 | **Request Enrichment** | Attach routing metadata (selected provider, latency, fallback count) to every response so upstream components can log and display it. |
| R8 | **Cost Tracking** | Track per-request and cumulative cost for paid providers. Enforce budget limits. |

---

## 3. Non-Responsibilities

The Model Router must **never**:

| # | Non-Responsibility | Rationale |
|---|---|---|
| N1 | Parse LLM output | That is the `Parser`'s job. The Router returns raw text. |
| N2 | Normalize aliases | That is the `Normalizer`'s job. |
| N3 | Validate tasks | That is the `Validator`'s job. |
| N4 | Execute tools | That is the `Executor`'s job. |
| N5 | Build prompts | That is the `Planner`'s job. The Router receives finished prompts. |
| N6 | Store conversation history | That is the `MemoryManager`'s job. |
| N7 | Manage API keys directly | API keys are loaded from configuration. The Router passes them to providers but never generates, rotates, or validates them. |
| N8 | Make business decisions about user intent | It routes based on declared capabilities, not by interpreting user meaning. |
| N9 | Modify the prompt content | The Router is a transparent pipe. It forwards prompts verbatim. |
| N10 | Render UI | The Router is headless. The GUI reads routing metadata for display. |

---

## 4. Public Interfaces

### 4.1 `ModelGateway` — The Primary Interface

This is the **only interface** the rest of Jarvis interacts with. It replaces `LLMClient` in the dependency graph. The Planner depends on this abstraction, never on a concrete provider.

```
ModelGateway (ABC)
│
├── generate(system_prompt, user_prompt, requirements?) → ModelResponse
│
├── generate_with_images(system_prompt, user_prompt, images, requirements?) → ModelResponse
│
├── embed(text, requirements?) → EmbeddingResponse
│
└── health() → GatewayHealthReport
```

#### Method Contracts

**`generate`**
- Input: system prompt (str), user prompt (str), optional `InferenceRequirements`
- Output: `ModelResponse` containing raw text + routing metadata
- Raises: `AllProvidersExhaustedError` if no provider can fulfill the request
- Guarantee: The caller receives a response or a definitive exception. Never hangs.

**`generate_with_images`**
- Same as `generate` but with image payloads for vision models
- Automatically constrains routing to providers with `supports_vision`

**`embed`**
- Input: text (str), optional `InferenceRequirements`
- Output: `EmbeddingResponse` containing vector + routing metadata
- Automatically constrains routing to providers with `supports_embeddings`

**`health`**
- Returns the aggregate health status of all registered providers
- No side effects

### 4.2 `ModelResponse` — Response Envelope

Every response carries routing metadata alongside the raw output:

```
ModelResponse
├── text: str                    # Raw model output (verbatim)
├── provider_id: str             # Which provider answered (e.g. "ollama")
├── model_id: str                # Specific model used (e.g. "qwen3:8b")
├── latency_ms: int              # End-to-end inference time
├── fallback_count: int          # Number of fallback attempts (0 = first try)
├── token_usage: TokenUsage      # Input/output token counts (if available)
└── cost: Cost | None            # Estimated cost (None for local models)
```

### 4.3 `EmbeddingResponse` — Embedding Envelope

```
EmbeddingResponse
├── vector: list[float]          # Embedding vector
├── dimensions: int              # Vector dimensionality
├── provider_id: str             # Which provider produced it
├── model_id: str                # Specific model used
└── latency_ms: int              # Inference time
```

### 4.4 `InferenceRequirements` — Routing Hints

Callers may optionally declare what they need. If omitted, the Router uses defaults.

```
InferenceRequirements
├── capabilities: set[Capability]       # Required capabilities (e.g. {CHAT, REASONING})
├── max_latency_ms: int | None          # Latency ceiling
├── max_cost_per_request: float | None  # Cost ceiling (USD)
├── min_context_length: int | None      # Minimum context window (tokens)
├── prefer_local: bool                  # Prefer local providers over remote
├── prefer_provider: str | None         # Soft preference (hint, not mandate)
└── task_complexity: TaskComplexity      # SIMPLE, MODERATE, COMPLEX
```

### 4.5 `BaseProvider` — Provider Contract

Every provider implements this. The Model Router never calls provider-specific APIs directly.

```
BaseProvider (ABC)
│
├── provider_id: str (property)                    # Unique identifier
├── display_name: str (property)                   # Human-readable name
├── capabilities: frozenset[Capability] (property) # Declared capabilities
├── is_local: bool (property)                      # True for Ollama, LM Studio, etc.
│
├── initialize() → None                            # One-time setup (load SDK, validate keys)
├── generate(request: ProviderRequest) → ProviderResponse
├── embed(text: str, model: str) → list[float]
├── health_check() → ProviderHealthStatus
├── list_models() → list[ModelInfo]
├── shutdown() → None                              # Graceful cleanup
│
├── supports(capability: Capability) → bool
└── estimate_cost(input_tokens: int, output_tokens: int, model: str) → float
```

---

## 5. Internal Components

### 5.1 Component Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                       Model Router Subsystem                    │
│                                                                 │
│   ┌──────────────┐    ┌───────────────────┐                     │
│   │ Model Gateway │───▶│  Selection Engine │                     │
│   │ (public API)  │    │                   │                     │
│   └──────┬───────┘    │  ┌─────────────┐  │                     │
│          │            │  │  Capability  │  │                     │
│          │            │  │  Analyzer    │  │                     │
│          │            │  └─────────────┘  │                     │
│          │            │  ┌─────────────┐  │                     │
│          │            │  │  Selection   │  │                     │
│          │            │  │  Policy      │  │                     │
│          │            │  └─────────────┘  │                     │
│          │            │  ┌─────────────┐  │                     │
│          │            │  │  Cost        │  │                     │
│          │            │  │  Estimator   │  │                     │
│          │            │  └─────────────┘  │                     │
│          │            └───────────────────┘                     │
│          │                                                      │
│          │            ┌───────────────────┐                     │
│          ├───────────▶│ Provider Registry │                     │
│          │            │                   │                     │
│          │            │  ┌─────────────┐  │                     │
│          │            │  │  Provider A  │  │                     │
│          │            │  │  Provider B  │  │                     │
│          │            │  │  Provider C  │  │                     │
│          │            │  │  ...         │  │                     │
│          │            │  └─────────────┘  │                     │
│          │            └───────────────────┘                     │
│          │                                                      │
│          │            ┌───────────────────┐                     │
│          ├───────────▶│  Fallback Manager │                     │
│          │            └───────────────────┘                     │
│          │                                                      │
│          │            ┌───────────────────┐                     │
│          ├───────────▶│  Health Monitor   │                     │
│          │            └───────────────────┘                     │
│          │                                                      │
│          │            ┌───────────────────┐                     │
│          └───────────▶│  Config Manager   │                     │
│                       └───────────────────┘                     │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 Provider Registry

**Purpose**: Holds all registered `BaseProvider` instances. Single source of truth for what providers exist, their declared capabilities, and their current status.

**Key Operations**:
- Register a provider instance
- Unregister a provider by ID
- Query providers by capability (e.g., "give me all providers that support vision")
- Query providers by availability (healthy + enabled)
- List all providers with status
- Get a specific provider by ID

**Design Decisions**:
- Providers are registered at startup from configuration, not discovered dynamically
- The registry is thread-safe (multiple `ChatView` workers may route concurrently)
- Provider IDs are globally unique strings (e.g., `"ollama"`, `"gemini"`, `"openai"`)
- Registration order defines default priority when all else is equal

### 5.3 Capability Analyzer

**Purpose**: Given an `InferenceRequirements` object (or defaults), determines which providers in the registry are eligible candidates.

**Process**:
1. Filter by required capabilities (hard constraint — provider must declare all of them)
2. Filter by health status (only healthy providers)
3. Filter by enabled status (respects admin disable)
4. Filter by context length (if `min_context_length` specified)
5. Return the ordered candidate set

**Design Decisions**:
- Capability matching is conjunctive: if the request requires `{CHAT, REASONING}`, the provider must support **both**
- The analyzer is stateless — it queries the registry each time
- An empty candidate set triggers `NoCapableProviderError` before any inference is attempted

### 5.4 Selection Policy

**Purpose**: Given a list of eligible candidates from the Capability Analyzer, selects the **single best provider** for this request.

**Selection Dimensions** (evaluated in priority order):

| Priority | Dimension | Logic |
|---|---|---|
| 1 | **Hard Constraints** | Already filtered by Capability Analyzer |
| 2 | **User Preference** | If `prefer_provider` is set and available, prefer it |
| 3 | **Locality** | If `prefer_local` is true, rank local providers higher |
| 4 | **Task Complexity** | `COMPLEX` → largest model; `SIMPLE` → fastest model |
| 5 | **Cost** | If `max_cost_per_request` is set, exclude over-budget providers |
| 6 | **Latency** | If `max_latency_ms` is set, exclude historically slow providers |
| 7 | **Historical Performance** | Use exponentially weighted moving average of past latencies |
| 8 | **Registration Order** | Tiebreaker — first registered wins |

**Design Decisions**:
- The policy is a **strategy object** — it can be replaced or extended without modifying the Router
- The default policy is `WeightedScorePolicy`, which computes a composite score across dimensions
- Advanced users can provide a custom `SelectionPolicy` implementation
- The policy never makes network calls — it operates on cached metadata only

### 5.5 Cost Estimator

**Purpose**: Estimates the monetary cost of a request before it is sent. Enforces budget limits.

**Inputs**:
- Approximate input token count (estimated from prompt length)
- Expected output token count (configurable default, e.g., 1024)
- Provider's pricing table (from configuration)

**Outputs**:
- Estimated cost in USD
- Boolean: within budget?

**Design Decisions**:
- Token count estimation uses a simple heuristic: `len(text) / 4` for English text
- Pricing tables are loaded from configuration, not hardcoded
- Local providers (Ollama, LM Studio) always report cost = 0.00
- Cost tracking is cumulative per session and per calendar day

### 5.6 Fallback Manager

**Purpose**: When the selected provider fails, the Fallback Manager transparently retries with the next-best provider.

**Behavior**:
1. Selection Engine selects Provider A → fails
2. Fallback Manager marks Provider A as temporarily degraded
3. Selection Engine selects Provider B (next-best) → succeeds
4. Response is returned with `fallback_count = 1`
5. Provider A is re-checked by Health Monitor later

**Configuration**:
- `max_fallback_attempts`: Maximum providers to try before giving up (default: 3)
- `fallback_cooldown_seconds`: How long a failed provider is excluded (default: 60)

**Design Decisions**:
- Fallback is transparent to the caller — `generate()` either returns a response or raises `AllProvidersExhaustedError`
- The Fallback Manager does NOT retry the same provider — it always moves to the next candidate
- Fallback attempts are logged at `WARNING` level
- Each fallback attempt uses the same prompt verbatim — no prompt modification

### 5.7 Health Monitor

**Purpose**: Tracks provider health in the background. Disables providers that are down. Re-enables them when they recover.

**Health States**:

```
HEALTHY ──(3 consecutive failures)──▶ DEGRADED ──(5 more failures)──▶ UNAVAILABLE
    ▲                                     │                              │
    │                                     │                              │
    └────────(health check passes)────────┘                              │
    └────────(health check passes)───────────────────────────────────────┘
```

| State | Behavior |
|---|---|
| `HEALTHY` | Fully eligible for routing |
| `DEGRADED` | Eligible but ranked lower; health checks increase in frequency |
| `UNAVAILABLE` | Excluded from routing; periodic health checks continue |

**Health Checks**:
- Passive: Track success/failure of real requests (no extra network calls)
- Active: Periodic lightweight ping (e.g., list models) every N seconds
- Active checks are only sent to `DEGRADED` and `UNAVAILABLE` providers

**Design Decisions**:
- Health state is an internal detail — callers never see it
- The Health Monitor runs on a background thread (or timer) and updates the Provider Registry
- Circuit-breaker pattern: rapidly failing providers are removed from the pool quickly, then slowly re-introduced
- Active health check interval: 30s for DEGRADED, 120s for UNAVAILABLE

### 5.8 Configuration Manager

**Purpose**: Loads provider definitions, routing policies, and operational parameters from configuration files. Supports hot-reload.

**Sources** (in priority order):
1. Environment variables (highest priority — overrides everything)
2. `~/.jarvis/providers.yaml` (user-level configuration)
3. Built-in defaults (lowest priority)

**Design Decisions**:
- Configuration is loaded once at startup and cached
- Hot-reload watches the config file for changes and rebuilds the provider registry
- API keys are read from environment variables, never from config files (security)
- The config manager validates all entries at load time and fails fast on invalid configuration

---

## 6. Provider Lifecycle

### 6.1 State Machine

```
                  ┌────────────┐
 (defined in      │            │
  config file) ──▶│ REGISTERED │
                  │            │
                  └─────┬──────┘
                        │ initialize()
                        ▼
                  ┌────────────┐
                  │            │  health_check() passes
                  │ VALIDATING │──────────────────────────────┐
                  │            │                              │
                  └─────┬──────┘                              │
                        │ validation fails                    │
                        ▼                                     ▼
                  ┌────────────┐                      ┌────────────┐
                  │            │                      │            │
                  │  INVALID   │                      │   ACTIVE   │
                  │ (logged,   │                      │ (healthy,  │
                  │  skipped)  │                      │  routable) │
                  │            │                      │            │
                  └────────────┘                      └──┬────┬───┘
                                                         │    │
                                          3+ failures    │    │  admin disable
                                                         ▼    ▼
                                                   ┌──────────────┐
                                                   │              │
                                                   │  SUSPENDED   │
                                                   │ (excluded    │
                                                   │  from pool)  │
                                                   │              │
                                                   └──────┬───────┘
                                                          │
                                            health check  │  admin remove
                                            recovers      │
                                                 │        ▼
                                                 │  ┌──────────────┐
                                                 │  │              │
                                                 │  │   REMOVED    │
                                                 │  │ (shutdown,   │
                                                 │  │  cleanup)    │
                                                 │  │              │
                                                 │  └──────────────┘
                                                 │
                                                 └────▶ ACTIVE
```

### 6.2 Lifecycle Operations

| Phase | Trigger | Actions |
|---|---|---|
| **Registration** | Config file loaded at startup | Provider class instantiated, added to registry with `REGISTERED` status |
| **Initialization** | Immediately after registration | `provider.initialize()` called — loads SDK, validates API key format, resolves endpoint |
| **Validation** | After initialization | `provider.health_check()` confirms actual connectivity. On success → `ACTIVE`. On failure → `INVALID` (logged, skipped). |
| **Selection** | Every inference request | Selection Engine picks from `ACTIVE` providers only |
| **Suspension** | Consecutive failures exceed threshold | Provider moved to `SUSPENDED`, excluded from routing. Health Monitor begins active checks. |
| **Recovery** | Health check passes while `SUSPENDED` | Provider restored to `ACTIVE` |
| **Disabling** | Admin action (config change or API call) | Provider moved to `SUSPENDED` regardless of health |
| **Removal** | Config change removes a provider | `provider.shutdown()` called, provider removed from registry |

---

## 7. Capability System

### 7.1 Capability Enum

Capabilities are fine-grained, binary flags. A provider either supports a capability or does not. There is no partial support.

```
Capability (Enum)
│
├── CHAT                    # Basic text-in → text-out conversation
├── REASONING               # Extended chain-of-thought / thinking models
├── VISION                  # Image understanding (multimodal input)
├── EMBEDDINGS              # Text → vector encoding
├── AUDIO_INPUT             # Speech-to-text / audio understanding
├── AUDIO_OUTPUT            # Text-to-speech generation
├── IMAGE_GENERATION        # Text → image generation
├── TOOL_USE                # Function calling / structured output
├── CODE_GENERATION         # Specialized code synthesis
├── LONG_CONTEXT            # Context window ≥ 100K tokens
├── STREAMING               # Token-by-token streaming support
├── JSON_MODE               # Guaranteed JSON output mode
└── STRUCTURED_OUTPUT       # Schema-constrained output
```

### 7.2 Capability Declaration

Each provider declares its capabilities statically at registration time:

```
OllamaProvider:
    capabilities = {CHAT, REASONING, CODE_GENERATION, STREAMING, TOOL_USE}

GeminiProvider:
    capabilities = {CHAT, REASONING, VISION, EMBEDDINGS, LONG_CONTEXT,
                    STREAMING, JSON_MODE, STRUCTURED_OUTPUT, TOOL_USE,
                    AUDIO_INPUT, CODE_GENERATION}

OpenAIProvider:
    capabilities = {CHAT, REASONING, VISION, EMBEDDINGS, IMAGE_GENERATION,
                    STREAMING, JSON_MODE, STRUCTURED_OUTPUT, TOOL_USE,
                    AUDIO_INPUT, AUDIO_OUTPUT, CODE_GENERATION}

ClaudeProvider:
    capabilities = {CHAT, REASONING, VISION, LONG_CONTEXT, STREAMING,
                    JSON_MODE, STRUCTURED_OUTPUT, TOOL_USE, CODE_GENERATION}

DeepSeekProvider:
    capabilities = {CHAT, REASONING, CODE_GENERATION, LONG_CONTEXT,
                    STREAMING, TOOL_USE}
```

### 7.3 Model-Level Capabilities

A single provider may host multiple models with different capability sets. The `ModelInfo` structure captures this:

```
ModelInfo
├── model_id: str                       # e.g. "gpt-4o", "qwen3:8b"
├── display_name: str                   # Human-readable name
├── capabilities: frozenset[Capability] # Model-specific capabilities
├── context_length: int                 # Max tokens
├── input_cost_per_million: float       # USD per 1M input tokens
├── output_cost_per_million: float      # USD per 1M output tokens
└── is_default: bool                    # Default model for this provider
```

### 7.4 Capability Resolution

When a request arrives:

1. If `InferenceRequirements.capabilities` is specified → use it
2. If not specified → infer defaults from the calling context:
   - `Planner.plan()` → `{CHAT}` (minimum) or `{CHAT, REASONING}` (if complex)
   - Vision tool → `{CHAT, VISION}`
   - Academy embeddings → `{EMBEDDINGS}`
   - Voice tool → `{AUDIO_INPUT}` or `{AUDIO_OUTPUT}`

### 7.5 Extensibility

Adding a new capability:

1. Add the new value to the `Capability` enum
2. Declare it in the relevant provider's capability set
3. Consumers can now require it in `InferenceRequirements`
4. No existing code changes — Open/Closed Principle

---

## 8. Routing Strategy

### 8.1 Routing Decision Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    Routing Decision Flow                     │
│                                                             │
│   InferenceRequirements                                     │
│          │                                                  │
│          ▼                                                  │
│   ┌──────────────────┐                                      │
│   │ Capability Filter │  "Which providers CAN do this?"     │
│   │                  │                                      │
│   │ - Required caps  │                                      │
│   │ - Health = OK    │                                      │
│   │ - Enabled = true │                                      │
│   └────────┬─────────┘                                      │
│            │                                                │
│            │  Candidates: [A, B, C]                         │
│            │  (may be empty → NoCapableProviderError)       │
│            ▼                                                │
│   ┌──────────────────┐                                      │
│   │ Constraint Filter │  "Which providers SHOULD do this?"  │
│   │                  │                                      │
│   │ - Max cost       │                                      │
│   │ - Max latency    │                                      │
│   │ - Min context    │                                      │
│   └────────┬─────────┘                                      │
│            │                                                │
│            │  Eligible: [A, B]                              │
│            ▼                                                │
│   ┌──────────────────┐                                      │
│   │ Preference Sort   │  "Which provider is BEST?"          │
│   │                  │                                      │
│   │ - User pref      │                                      │
│   │ - Locality       │                                      │
│   │ - Complexity     │                                      │
│   │ - Perf history   │                                      │
│   │ - Reg. order     │                                      │
│   └────────┬─────────┘                                      │
│            │                                                │
│            │  Ranked: [B, A]                                │
│            ▼                                                │
│   ┌──────────────────┐                                      │
│   │ Final Selection   │                                     │
│   │                  │                                      │
│   │ Pick rank #1     │                                      │
│   │ Retain rest as   │                                      │
│   │ fallback chain   │                                      │
│   └────────┬─────────┘                                      │
│            │                                                │
│            │  Selected: B                                   │
│            │  Fallbacks: [A]                                │
│            ▼                                                │
│   ┌──────────────────┐                                      │
│   │ Execute Request   │                                     │
│   │                  │                                      │
│   │ B.generate(req)  │─── success ──▶ return ModelResponse  │
│   │                  │                                      │
│   │                  │─── failure ──▶ Fallback Manager      │
│   │                  │               try A.generate(req)    │
│   └──────────────────┘                                      │
└─────────────────────────────────────────────────────────────┘
```

### 8.2 Routing Inputs

| Input | Source | Effect |
|---|---|---|
| **Required Capabilities** | `InferenceRequirements` or inferred | Hard filter — provider must support all |
| **User Preferences** | Configuration file | Soft boost for preferred provider |
| **Offline Mode** | Network status detection | Eliminates all remote providers |
| **Provider Availability** | Health Monitor | Eliminates DEGRADED/UNAVAILABLE providers |
| **Cost** | Provider pricing tables + budget config | Eliminates over-budget providers |
| **Latency** | Exponential moving average of past calls | Ranks faster providers higher |
| **Context Length** | `ModelInfo.context_length` | Eliminates models with insufficient context |
| **Task Complexity** | `InferenceRequirements.task_complexity` | COMPLEX → prefer larger models; SIMPLE → prefer faster |
| **Locality** | `BaseProvider.is_local` + `prefer_local` flag | Local providers ranked higher when flag is set |

### 8.3 Default Behavior (No Requirements Specified)

When the Planner calls `generate()` without explicit requirements:

1. Capability defaults to `{CHAT}`
2. If a local provider is available and healthy → select it (privacy-first)
3. Otherwise → select the cheapest remote provider
4. Task complexity defaults to `MODERATE`

This ensures backward compatibility: existing Planner code continues to work unchanged.

### 8.4 Network Awareness

```
Network Status         Routing Effect
─────────────         ──────────────
ONLINE                All providers eligible
METERED               Prefer local; warn on large remote requests
OFFLINE               Local providers only
```

Network status is detected passively from failed health checks, not from OS APIs.

---

## 9. Fallback Strategy

### 9.1 Fallback Chain

When the primary provider fails, the Router automatically walks the fallback chain:

```
Request arrives
     │
     ▼
Provider A (rank #1) ──── success ──▶ return response
     │
     failure (timeout, 5xx, connection error)
     │
     ▼
Log WARNING: "Provider A failed, falling back to B"
Mark A as DEGRADED
     │
     ▼
Provider B (rank #2) ──── success ──▶ return response (fallback_count=1)
     │
     failure
     │
     ▼
Provider C (rank #3) ──── success ──▶ return response (fallback_count=2)
     │
     failure
     │
     ▼
All providers exhausted
     │
     ▼
Raise AllProvidersExhaustedError
```

### 9.2 Failure Scenarios

| Scenario | Behavior |
|---|---|
| **Gemini API returns 500** | Mark Gemini as DEGRADED. Retry with next provider (e.g., OpenAI or Ollama). |
| **Ollama process crashes** | Health check detects failure. Ollama moved to UNAVAILABLE. All requests route to remote providers until Ollama recovers. |
| **No provider supports Vision** | `NoCapableProviderError` raised immediately (before any network call). Caller receives a clear error explaining missing capability. |
| **Network completely unavailable** | All remote providers fail health checks → UNAVAILABLE. Only local providers remain. If no local provider exists → `AllProvidersExhaustedError`. |
| **API key expired** | Provider returns 401/403 → provider marked DEGRADED. Logged at ERROR with instruction to update configuration. Fallback to next provider. |
| **Rate limit exceeded** | Provider returns 429 → provider marked DEGRADED with cooldown matching `Retry-After` header. Fallback to next provider. |
| **Response timeout** | Request killed after configured timeout. Provider penalized in latency scores. Fallback to next provider. |

### 9.3 Degradation Strategies

When the system is in a degraded state (limited providers available):

| Available Providers | Strategy |
|---|---|
| Multiple healthy providers | Normal routing — select best |
| Single healthy provider | Route all requests to it; log WARNING |
| Zero healthy, some degraded | Attempt degraded providers with shorter timeout; log ERROR |
| Zero healthy, zero degraded | Raise `AllProvidersExhaustedError`; log CRITICAL |

---

## 10. Error Handling

### 10.1 Exception Hierarchy

All Model Router exceptions inherit from `JarvisError` to maintain compatibility with the existing exception hierarchy.

```
JarvisError (existing)
└── RouterError (new base)
    ├── ProviderError
    │   ├── ProviderConnectionError      # Cannot reach provider endpoint
    │   ├── ProviderAuthenticationError   # Invalid/expired API key
    │   ├── ProviderRateLimitError        # 429 Too Many Requests
    │   ├── ProviderTimeoutError          # Request exceeded timeout
    │   ├── ProviderResponseError         # Unexpected response format
    │   └── ProviderModelNotFoundError    # Requested model doesn't exist
    │
    ├── RoutingError
    │   ├── NoCapableProviderError        # No provider supports required capabilities
    │   ├── AllProvidersExhaustedError     # All providers tried and failed
    │   ├── BudgetExceededError           # Request would exceed cost budget
    │   └── ContextLengthExceededError    # Prompt too long for all candidates
    │
    └── ConfigurationError
        ├── InvalidProviderConfigError    # Malformed provider definition
        ├── MissingApiKeyError            # Required API key not set
        └── InvalidPolicyConfigError      # Malformed routing policy
```

### 10.2 Error Propagation Contract

| Error Level | Handling |
|---|---|
| **Individual provider failure** | Caught by Fallback Manager. Logged. Retried with next provider. Never exposed to caller unless all providers fail. |
| **All providers exhausted** | `AllProvidersExhaustedError` raised to caller. Contains details of every attempt (provider ID, error type, latency). |
| **No capable provider** | `NoCapableProviderError` raised before any network call. Contains required capabilities and what's available. |
| **Configuration error** | `ConfigurationError` raised at startup. Prevents the application from launching with invalid config. |
| **Budget exceeded** | `BudgetExceededError` raised before any network call. Caller decides how to handle (skip or alert user). |

### 10.3 Backward Compatibility

The existing `LLMConnectionError` must continue to work for the Planner. The `ModelGateway` implementation should translate:

- `AllProvidersExhaustedError` → can be caught as `RouterError` or `JarvisError`
- The Planner's existing `except JarvisError` clause catches all router errors transparently

---

## 11. Logging Strategy

### 11.1 What MUST Be Logged

| Event | Level | Example |
|---|---|---|
| Provider registered | `INFO` | `Registered provider: ollama (3 models, 5 capabilities)` |
| Provider initialized | `INFO` | `Provider ollama initialized in 120ms` |
| Provider validation passed | `INFO` | `Provider ollama health check passed` |
| Provider validation failed | `WARNING` | `Provider gemini health check failed: ConnectionError` |
| Routing decision made | `INFO` | `Routed to ollama/qwen3:8b (candidates: 3, latency_est: 450ms)` |
| Successful inference | `DEBUG` | `ollama/qwen3:8b responded in 823ms (147 input, 312 output tokens)` |
| Provider failure + fallback | `WARNING` | `Provider gemini failed (TimeoutError), falling back to ollama` |
| All providers exhausted | `ERROR` | `All 3 providers failed for request. Last error: ConnectionError` |
| Provider health state change | `WARNING` | `Provider gemini: HEALTHY → DEGRADED (3 consecutive failures)` |
| Provider health recovery | `INFO` | `Provider gemini: DEGRADED → HEALTHY (health check passed)` |
| Cost tracking | `DEBUG` | `Request cost: $0.0023 (gemini/gemini-2.0-flash). Daily total: $0.15` |
| Budget threshold warning | `WARNING` | `Daily cost $4.50 approaching budget limit $5.00` |
| Configuration loaded | `INFO` | `Loaded 4 providers from ~/.jarvis/providers.yaml` |
| Configuration error | `ERROR` | `Invalid provider config: 'gemini' missing required field 'models'` |

### 11.2 What MUST NEVER Be Logged

| Data | Reason |
|---|---|
| **API keys** | Security. Keys must never appear in logs, even partially. |
| **Full prompt text** | Privacy. User instructions may contain sensitive information. Log length only. |
| **Full response text** | Privacy. Model responses may contain sensitive content. Log length only. |
| **User-identifiable information** | GDPR/privacy compliance. |
| **Embedding vectors** | Large, useless in logs, and potentially reconstructible. |
| **Image binary data** | Size and privacy. Log dimensions and byte count only. |

### 11.3 Log Format

All Model Router logs use the existing Jarvis format and logger hierarchy:

```
logger = logging.getLogger("jarvis.router")
logger = logging.getLogger("jarvis.router.provider.ollama")
logger = logging.getLogger("jarvis.router.health")
logger = logging.getLogger("jarvis.router.fallback")
```

---

## 12. Configuration

### 12.1 Provider Configuration File

**Location**: `~/.jarvis/providers.yaml`

```yaml
# ─── Provider Definitions ─────────────────────────────

providers:
  ollama:
    enabled: true
    display_name: "Ollama (Local)"
    provider_type: "ollama"
    is_local: true
    endpoint: "http://localhost:11434"
    priority: 1                          # Lower = higher priority
    models:
      - id: "qwen3:8b"
        display_name: "Qwen 3 8B"
        capabilities: [chat, reasoning, code_generation, streaming, tool_use]
        context_length: 32768
        is_default: true
      - id: "llava:13b"
        display_name: "LLaVA 13B"
        capabilities: [chat, vision]
        context_length: 4096
      - id: "nomic-embed-text"
        display_name: "Nomic Embed"
        capabilities: [embeddings]
        context_length: 8192

  gemini:
    enabled: true
    display_name: "Google Gemini"
    provider_type: "gemini"
    is_local: false
    api_key_env: "GEMINI_API_KEY"        # Env var name, never the key itself
    priority: 2
    models:
      - id: "gemini-2.0-flash"
        display_name: "Gemini 2.0 Flash"
        capabilities: [chat, reasoning, vision, streaming, json_mode, tool_use, long_context]
        context_length: 1048576
        input_cost_per_million: 0.075
        output_cost_per_million: 0.30
        is_default: true

  openai:
    enabled: false                       # Disabled by default
    display_name: "OpenAI"
    provider_type: "openai"
    is_local: false
    api_key_env: "OPENAI_API_KEY"
    priority: 3
    models:
      - id: "gpt-4o"
        display_name: "GPT-4o"
        capabilities: [chat, reasoning, vision, streaming, json_mode, structured_output, tool_use]
        context_length: 128000
        input_cost_per_million: 2.50
        output_cost_per_million: 10.00
        is_default: true

# ─── Routing Policy ───────────────────────────────────

routing:
  default_capabilities: [chat]
  prefer_local: true                     # Privacy-first default
  max_fallback_attempts: 3
  fallback_cooldown_seconds: 60
  request_timeout_seconds: 30

# ─── Health Monitoring ────────────────────────────────

health:
  degraded_threshold: 3                  # Consecutive failures → DEGRADED
  unavailable_threshold: 8               # Total failures → UNAVAILABLE
  check_interval_degraded_seconds: 30
  check_interval_unavailable_seconds: 120
  recovery_required_successes: 2         # Successes needed to recover

# ─── Cost Management ─────────────────────────────────

cost:
  daily_budget_usd: 5.00                 # Daily spending limit
  warn_at_percent: 80                    # Warn when 80% of budget used
  track_local: false                     # Don't track local provider costs
```

### 12.2 Environment Variables

API keys and sensitive values are **always** loaded from environment variables, never from the config file:

| Variable | Purpose |
|---|---|
| `GEMINI_API_KEY` | Google Gemini API authentication |
| `OPENAI_API_KEY` | OpenAI API authentication |
| `ANTHROPIC_API_KEY` | Claude API authentication |
| `DEEPSEEK_API_KEY` | DeepSeek API authentication |
| `XAI_API_KEY` | Grok/xAI API authentication |
| `JARVIS_ROUTER_CONFIG` | Override config file path |
| `JARVIS_PREFER_LOCAL` | Override `routing.prefer_local` |
| `JARVIS_DAILY_BUDGET` | Override `cost.daily_budget_usd` |

### 12.3 Default Behavior (No Config File)

If `~/.jarvis/providers.yaml` does not exist, the Model Router falls back to a single Ollama provider with the model specified in `JARVIS_MODEL` (current behavior). This ensures **100% backward compatibility**.

---

## 13. Future Expansion

### 13.1 Vision

The capability system already defines `VISION`. When the Vision Tool is implemented:

1. The Vision Tool calls `gateway.generate_with_images(...)` instead of `gateway.generate(...)`
2. The Router automatically constrains to providers with `{CHAT, VISION}`
3. Routes to `ollama/llava:13b` locally or `gemini/gemini-2.0-flash` remotely
4. No Router code changes — the capability filter handles it

### 13.2 Voice

Audio capabilities (`AUDIO_INPUT`, `AUDIO_OUTPUT`) are pre-defined in the Capability enum:

1. Voice Tool calls a future `gateway.transcribe(audio)` or `gateway.speak(text)` method
2. Router filters to `{AUDIO_INPUT}` or `{AUDIO_OUTPUT}` providers
3. New `WhisperProvider` (local) or `OpenAIAudioProvider` (remote) registered

### 13.3 MCP (Model Context Protocol)

The `BaseProvider` interface is transport-agnostic. An `MCPProvider` implementation could:

1. Connect to any MCP-compatible server
2. Declare capabilities dynamically from the server's capability advertisement
3. Register models discovered from the MCP server
4. Route like any other provider

### 13.4 Plugin Marketplace

Third-party tool plugins may need specific capabilities. The routing system supports this:

1. Plugin manifest declares required capabilities: `requires: [chat, tool_use]`
2. Planner passes these as `InferenceRequirements` when planning for that plugin
3. Router ensures only capable providers are selected
4. Plugin never interacts with providers directly

### 13.5 Jarvis Academy

The learning subsystem needs embeddings for semantic memory. Integration:

1. Academy calls `gateway.embed(text)` for memory vectorization
2. Router selects an `{EMBEDDINGS}` provider (e.g., `ollama/nomic-embed-text`)
3. Academy stores vectors in a vector database
4. No direct provider coupling in the Academy code

### 13.6 Multi-Agent Systems

Multiple specialized agents may need different models:

1. Each agent constructs its own `InferenceRequirements` (e.g., code agent → `{CHAT, CODE_GENERATION}`)
2. A single `ModelGateway` instance serves all agents
3. Each agent's requests are routed independently
4. A meta-agent can query `gateway.health()` to understand system capacity
5. The Router naturally load-balances across providers

---

## 14. UML Diagrams

### 14.1 Class Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                          Class Diagram                              │
└─────────────────────────────────────────────────────────────────────┘

    ┌───────────────────────┐          ┌──────────────────────┐
    │  «abstract»           │          │ InferenceRequirements│
    │  ModelGateway          │          ├──────────────────────┤
    ├───────────────────────┤          │ capabilities         │
    │                       │          │ max_latency_ms       │
    ├───────────────────────┤          │ max_cost_per_request │
    │ generate()            │─────────▶│ min_context_length   │
    │ generate_with_images()│          │ prefer_local         │
    │ embed()               │          │ prefer_provider      │
    │ health()              │          │ task_complexity       │
    └───────────┬───────────┘          └──────────────────────┘
                │
                │ implements
                ▼
    ┌───────────────────────┐       ┌──────────────────────┐
    │  DefaultModelRouter    │──────▶│  ProviderRegistry    │
    ├───────────────────────┤       ├──────────────────────┤
    │ _registry             │       │ _providers           │
    │ _selection_engine     │       ├──────────────────────┤
    │ _fallback_manager     │       │ register()           │
    │ _health_monitor       │       │ unregister()         │
    │ _config_manager       │       │ get_by_id()          │
    ├───────────────────────┤       │ get_by_capability()  │
    │ generate()            │       │ list_all()           │
    │ generate_with_images()│       │ list_healthy()       │
    │ embed()               │       └──────────┬───────────┘
    │ health()              │                  │ contains
    └───────────────────────┘                  ▼
                │                   ┌──────────────────────┐
                │                   │  «abstract»          │
                │                   │  BaseProvider         │
                ▼                   ├──────────────────────┤
    ┌───────────────────────┐       │ provider_id          │
    │  SelectionEngine       │       │ display_name         │
    ├───────────────────────┤       │ capabilities         │
    │ _capability_analyzer  │       │ is_local             │
    │ _selection_policy     │       ├──────────────────────┤
    │ _cost_estimator       │       │ initialize()         │
    ├───────────────────────┤       │ generate()           │
    │ select()              │       │ embed()              │
    │ rank_candidates()     │       │ health_check()       │
    └───────────────────────┘       │ list_models()        │
                │                   │ shutdown()           │
                │ uses              │ supports()           │
                ▼                   │ estimate_cost()      │
    ┌───────────────────────┐       └──────────┬───────────┘
    │ «interface»           │                  │
    │ SelectionPolicy        │                  │ implemented by
    ├───────────────────────┤                  │
    │ select(candidates,    │       ┌──────────┴───────────────────────┐
    │        requirements)  │       │          │           │           │
    │  → ProviderRanking    │       ▼          ▼           ▼           ▼
    └───────────────────────┘   ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
                │               │Ollama  │ │Gemini  │ │OpenAI  │ │Claude  │
                │ implemented   │Provider│ │Provider│ │Provider│ │Provider│
                ▼               └────────┘ └────────┘ └────────┘ └────────┘
    ┌───────────────────────┐
    │ WeightedScorePolicy    │
    ├───────────────────────┤       ┌──────────────────────┐
    │ _weights              │       │  ModelResponse        │
    ├───────────────────────┤       ├──────────────────────┤
    │ select()              │       │ text                 │
    └───────────────────────┘       │ provider_id          │
                                    │ model_id             │
    ┌───────────────────────┐       │ latency_ms           │
    │  FallbackManager       │       │ fallback_count       │
    ├───────────────────────┤       │ token_usage          │
    │ _max_attempts         │       │ cost                 │
    │ _cooldown_seconds     │       └──────────────────────┘
    ├───────────────────────┤
    │ execute_with_fallback()│      ┌──────────────────────┐
    └───────────────────────┘       │  Capability (Enum)   │
                                    ├──────────────────────┤
    ┌───────────────────────┐       │ CHAT                 │
    │  HealthMonitor         │       │ REASONING            │
    ├───────────────────────┤       │ VISION               │
    │ _provider_states      │       │ EMBEDDINGS           │
    ├───────────────────────┤       │ AUDIO_INPUT          │
    │ record_success()      │       │ AUDIO_OUTPUT         │
    │ record_failure()      │       │ IMAGE_GENERATION     │
    │ check_health()        │       │ TOOL_USE             │
    │ get_state()           │       │ CODE_GENERATION      │
    └───────────────────────┘       │ LONG_CONTEXT         │
                                    │ STREAMING            │
    ┌───────────────────────┐       │ JSON_MODE            │
    │  ConfigManager         │       │ STRUCTURED_OUTPUT    │
    ├───────────────────────┤       └──────────────────────┘
    │ _config_path          │
    ├───────────────────────┤
    │ load()                │
    │ reload()              │
    │ get_provider_configs()│
    │ get_routing_policy()  │
    └───────────────────────┘
```

### 14.2 Sequence Diagram — Successful Request

```
┌──────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐  ┌──────────┐
│ Planner  │  │ ModelGateway │  │ Selection    │  │  Fallback    │  │  Provider  │  │ Health   │
│          │  │ (Router)     │  │  Engine      │  │  Manager     │  │  Registry  │  │ Monitor  │
└────┬─────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └─────┬──────┘  └────┬─────┘
     │               │                │                │                │              │
     │  generate(    │                │                │                │              │
     │  sys_prompt,  │                │                │                │              │
     │  user_prompt) │                │                │                │              │
     │──────────────▶│                │                │                │              │
     │               │                │                │                │              │
     │               │  select(       │                │                │              │
     │               │  requirements) │                │                │              │
     │               │───────────────▶│                │                │              │
     │               │                │                │                │              │
     │               │                │ get_by_        │                │              │
     │               │                │ capability()   │                │              │
     │               │                │────────────────┼───────────────▶│              │
     │               │                │                │                │              │
     │               │                │ candidates     │                │              │
     │               │                │◀───────────────┼────────────────│              │
     │               │                │                │                │              │
     │               │                │  get_state()   │                │              │
     │               │                │────────────────┼───────────────┼─────────────▶│
     │               │                │  health states │                │              │
     │               │                │◀───────────────┼───────────────┼──────────────│
     │               │                │                │                │              │
     │               │  ranked list   │                │                │              │
     │               │◀──────────────│                │                │              │
     │               │                │                │                │              │
     │               │  execute_with_fallback(         │                │              │
     │               │  ranked_list, request)          │                │              │
     │               │────────────────┼───────────────▶│                │              │
     │               │                │                │                │              │
     │               │                │                │  get_by_id()   │              │
     │               │                │                │───────────────▶│              │
     │               │                │                │  provider_A    │              │
     │               │                │                │◀───────────────│              │
     │               │                │                │                │              │
     │               │                │                │  provider_A.   │              │
     │               │                │                │  generate(req) │              │
     │               │                │                │───────────────▶│              │
     │               │                │                │                │──┐           │
     │               │                │                │                │  │ LLM call  │
     │               │                │                │                │◀─┘           │
     │               │                │                │  raw response  │              │
     │               │                │                │◀───────────────│              │
     │               │                │                │                │              │
     │               │                │                │  record_       │              │
     │               │                │                │  success()     │              │
     │               │                │                │────────────────┼─────────────▶│
     │               │                │                │                │              │
     │               │  ModelResponse │                │                │              │
     │               │◀───────────────┼────────────────│                │              │
     │               │                │                │                │              │
     │  raw_text     │                │                │                │              │
     │◀──────────────│                │                │                │              │
     │               │                │                │                │              │
```

### 14.3 Sequence Diagram — Fallback Scenario

```
┌──────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐  ┌────────────┐  ┌──────────┐
│ Planner  │  │ ModelGateway │  │  Fallback    │  │ Provider A │  │ Provider B │  │ Health   │
│          │  │ (Router)     │  │  Manager     │  │ (Gemini)   │  │ (Ollama)   │  │ Monitor  │
└────┬─────┘  └──────┬───────┘  └──────┬───────┘  └─────┬──────┘  └─────┬──────┘  └────┬─────┘
     │               │                │                │              │              │
     │  generate()   │                │                │              │              │
     │──────────────▶│                │                │              │              │
     │               │                │                │              │              │
     │               │  execute_with_ │                │              │              │
     │               │  fallback()    │                │              │              │
     │               │───────────────▶│                │              │              │
     │               │                │                │              │              │
     │               │                │  generate(req) │              │              │
     │               │                │───────────────▶│              │              │
     │               │                │                │──┐           │              │
     │               │                │                │  │ TIMEOUT   │              │
     │               │                │                │◀─┘           │              │
     │               │                │  TimeoutError  │              │              │
     │               │                │◀───────────────│              │              │
     │               │                │                │              │              │
     │               │                │  record_failure()             │              │
     │               │                │──────────────────────────────┼─────────────▶│
     │               │                │                │              │              │
     │               │                │  LOG WARNING: "Gemini failed, │              │
     │               │                │  falling back to Ollama"      │              │
     │               │                │                │              │              │
     │               │                │  generate(req) │              │              │
     │               │                │──────────────────────────────▶│              │
     │               │                │                │              │──┐           │
     │               │                │                │              │  │ LLM call  │
     │               │                │                │              │◀─┘           │
     │               │                │  raw response  │              │              │
     │               │                │◀──────────────────────────────│              │
     │               │                │                │              │              │
     │               │                │  record_success()             │              │
     │               │                │──────────────────────────────┼─────────────▶│
     │               │                │                │              │              │
     │               │  ModelResponse │                │              │              │
     │               │  (fallback_count=1)             │              │              │
     │               │◀───────────────│                │              │              │
     │               │                │                │              │              │
     │  raw_text     │                │                │              │              │
     │◀──────────────│                │                │              │              │
```

### 14.4 Component Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         JARVIS APPLICATION                              │
│                                                                         │
│   ┌──────────────────────────────────────────────────┐                  │
│   │            Existing Pipeline (unchanged)          │                  │
│   │                                                  │                  │
│   │   GUI / CLI ──▶ Agent ──▶ Planner ──▶ ...        │                  │
│   │                              │                   │                  │
│   │                              │ generate()        │                  │
│   │                              │ (same contract    │                  │
│   │                              │  as LLMClient)    │                  │
│   └──────────────────────────────┼───────────────────┘                  │
│                                  │                                      │
│   ┌──────────────────────────────┼───────────────────────────────────┐  │
│   │                   MODEL ROUTER SUBSYSTEM                         │  │
│   │                              │                                   │  │
│   │                              ▼                                   │  │
│   │   ┌──────────────────────────────────────────┐                   │  │
│   │   │           ModelGateway (interface)        │                   │  │
│   │   └────────────────────┬─────────────────────┘                   │  │
│   │                        │                                         │  │
│   │                        ▼                                         │  │
│   │   ┌──────────────────────────────────────────┐                   │  │
│   │   │         DefaultModelRouter               │                   │  │
│   │   └──┬──────────┬──────────┬────────────┬────┘                   │  │
│   │      │          │          │            │                        │  │
│   │      ▼          ▼          ▼            ▼                        │  │
│   │  ┌────────┐ ┌────────┐ ┌────────┐ ┌──────────┐                  │  │
│   │  │Selection│ │Fallback│ │Health  │ │  Config  │                  │  │
│   │  │ Engine │ │Manager │ │Monitor │ │ Manager  │                  │  │
│   │  └───┬────┘ └────────┘ └────────┘ └─────┬────┘                  │  │
│   │      │                                  │                        │  │
│   │      ▼                                  ▼                        │  │
│   │  ┌───────────┐  ┌───────────┐    ┌───────────────┐               │  │
│   │  │ Capability │  │ Selection │    │ providers.yaml│               │  │
│   │  │ Analyzer   │  │  Policy   │    └───────────────┘               │  │
│   │  └───────────┘  └───────────┘                                    │  │
│   │                                                                  │  │
│   │   ┌──────────────────────────────────────────┐                   │  │
│   │   │           Provider Registry              │                   │  │
│   │   │  ┌────────────────────────────────────┐  │                   │  │
│   │   │  │  ┌────────┐ ┌────────┐ ┌────────┐ │  │                   │  │
│   │   │  │  │ Ollama │ │ Gemini │ │ OpenAI │ │  │                   │  │
│   │   │  │  │Provider│ │Provider│ │Provider│ │  │                   │  │
│   │   │  │  └───┬────┘ └───┬────┘ └───┬────┘ │  │                   │  │
│   │   │  │      │          │          │       │  │                   │  │
│   │   │  └──────┼──────────┼──────────┼───────┘  │                   │  │
│   │   └─────────┼──────────┼──────────┼──────────┘                   │  │
│   │             │          │          │                               │  │
│   └─────────────┼──────────┼──────────┼───────────────────────────────┘  │
│                 │          │          │                                   │
│   ──────────────┼──────────┼──────────┼──── NETWORK BOUNDARY ──────────  │
│                 │          │          │                                   │
│                 ▼          ▼          ▼                                   │
│           ┌────────┐  ┌────────┐  ┌────────┐                            │
│           │ Ollama │  │ Gemini │  │ OpenAI │                            │
│           │ Server │  │  API   │  │  API   │                            │
│           │(local) │  │(cloud) │  │(cloud) │                            │
│           └────────┘  └────────┘  └────────┘                            │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 15. Testing Strategy

### 15.1 Unit Tests — Capability Analyzer

| Test Case | Description |
|---|---|
| `test_filter_by_single_capability` | Given providers with different capabilities, filter by one required capability returns only matching providers |
| `test_filter_by_multiple_capabilities` | Require `{CHAT, VISION}`, only providers declaring both are returned |
| `test_filter_excludes_unhealthy` | Provider with `UNAVAILABLE` health is excluded even if capabilities match |
| `test_filter_excludes_disabled` | Provider with `enabled=false` is excluded |
| `test_empty_result_when_no_match` | No provider supports `{AUDIO_OUTPUT}` → empty candidate set |
| `test_filter_by_context_length` | Provider with 4K context excluded when 100K is required |
| `test_all_providers_match` | When all providers support `{CHAT}`, all are returned |

### 15.2 Unit Tests — Selection Policy

| Test Case | Description |
|---|---|
| `test_prefer_local_when_flag_set` | With `prefer_local=true`, local provider is ranked first |
| `test_prefer_specific_provider` | With `prefer_provider="gemini"`, Gemini is ranked first |
| `test_complex_task_prefers_larger_model` | `task_complexity=COMPLEX` ranks larger context models higher |
| `test_simple_task_prefers_fastest` | `task_complexity=SIMPLE` ranks historically fastest provider higher |
| `test_cost_constraint_excludes_expensive` | Provider exceeding `max_cost_per_request` is excluded |
| `test_latency_constraint_excludes_slow` | Provider exceeding `max_latency_ms` historical average is excluded |
| `test_registration_order_tiebreaker` | When scores are equal, first-registered wins |
| `test_empty_candidates_raises_error` | Zero candidates → `NoCapableProviderError` |
| `test_single_candidate_selected` | One candidate → selected without scoring |

### 15.3 Unit Tests — Fallback Manager

| Test Case | Description |
|---|---|
| `test_first_provider_succeeds_no_fallback` | Primary provider succeeds → `fallback_count=0` |
| `test_first_fails_second_succeeds` | Primary fails → fallback to second → `fallback_count=1` |
| `test_all_providers_fail` | All candidates fail → `AllProvidersExhaustedError` |
| `test_max_attempts_respected` | With `max_fallback_attempts=2`, only 2 providers tried |
| `test_cooldown_excludes_recently_failed` | Provider that failed < cooldown ago is skipped |
| `test_same_provider_never_retried` | Same provider is never attempted twice in one request |
| `test_failure_details_in_exception` | `AllProvidersExhaustedError` contains all attempt details |

### 15.4 Unit Tests — Health Monitor

| Test Case | Description |
|---|---|
| `test_initial_state_is_healthy` | New provider starts with `HEALTHY` state |
| `test_consecutive_failures_trigger_degraded` | 3 failures → `DEGRADED` |
| `test_continued_failures_trigger_unavailable` | 8 total failures → `UNAVAILABLE` |
| `test_success_resets_failure_count` | Success after 2 failures resets counter |
| `test_recovery_from_degraded` | Health check passes while `DEGRADED` → `HEALTHY` |
| `test_recovery_from_unavailable` | 2 consecutive health check passes while `UNAVAILABLE` → `HEALTHY` |
| `test_single_success_insufficient_for_unavailable_recovery` | 1 pass while `UNAVAILABLE` → still `UNAVAILABLE` |

### 15.5 Unit Tests — Provider Registry

| Test Case | Description |
|---|---|
| `test_register_provider` | Provider registered and retrievable by ID |
| `test_duplicate_id_raises_error` | Registering two providers with same ID raises `ValueError` |
| `test_register_non_baseprovider_raises_error` | Non-provider instance raises `TypeError` |
| `test_unregister_provider` | Provider removed and no longer retrievable |
| `test_get_by_capability` | Returns only providers declaring the queried capability |
| `test_list_healthy` | Returns only `HEALTHY` and `DEGRADED` providers |
| `test_empty_registry` | Empty registry returns empty lists |

### 15.6 Unit Tests — Model Gateway

| Test Case | Description |
|---|---|
| `test_generate_returns_model_response` | Successful call returns `ModelResponse` with text + metadata |
| `test_generate_backward_compatible` | Response `.text` field matches what `LLMClient.generate()` would return |
| `test_generate_with_requirements` | Custom requirements influence provider selection |
| `test_generate_default_requirements` | No requirements → defaults to `{CHAT}` + `prefer_local=true` |
| `test_embed_returns_embedding_response` | Successful embed returns vector + metadata |
| `test_health_returns_report` | `health()` returns aggregate status of all providers |

### 15.7 Unit Tests — Configuration Manager

| Test Case | Description |
|---|---|
| `test_load_valid_config` | Valid YAML parsed into provider configs and policies |
| `test_missing_config_uses_defaults` | No config file → single Ollama provider with defaults |
| `test_invalid_yaml_raises_error` | Malformed YAML → `InvalidProviderConfigError` |
| `test_missing_required_field_raises_error` | Provider missing `provider_type` → validation error |
| `test_api_key_from_env_var` | `api_key_env: "GEMINI_API_KEY"` reads from `os.environ` |
| `test_missing_api_key_logs_warning` | Missing env var → provider registered but logged as warning |
| `test_env_var_overrides_config` | `JARVIS_PREFER_LOCAL=false` overrides `routing.prefer_local: true` |

### 15.8 Unit Tests — Cost Estimator

| Test Case | Description |
|---|---|
| `test_local_provider_zero_cost` | Ollama always returns cost = $0.00 |
| `test_remote_provider_cost_calculation` | Correct cost from token count × pricing table |
| `test_budget_exceeded_detected` | Request exceeding daily budget returns `within_budget=false` |
| `test_cumulative_tracking` | Multiple requests accumulate correctly |
| `test_daily_reset` | Cost resets at midnight UTC |

### 15.9 Integration Tests

| Test Case | Description |
|---|---|
| `test_end_to_end_single_provider` | Full pipeline with one Ollama provider: Planner → Router → Ollama → response |
| `test_end_to_end_fallback` | Mock first provider to fail, verify second provider is used transparently |
| `test_end_to_end_no_provider_available` | All providers down → clean `AllProvidersExhaustedError` to Planner |
| `test_backward_compatibility_no_config` | No `providers.yaml` → behaves identically to current `LLMClient` |
| `test_concurrent_requests` | Multiple threads call `generate()` simultaneously without data races |
| `test_health_monitor_recovery_cycle` | Provider fails → DEGRADED → health check passes → ACTIVE → receives traffic again |
| `test_config_hot_reload` | Modify `providers.yaml` at runtime → Router picks up new provider without restart |

### 15.10 Contract Tests (Per Provider)

Each `BaseProvider` implementation must pass the same contract test suite:

| Test Case | Description |
|---|---|
| `test_provider_id_is_nonempty_string` | `provider_id` returns non-empty string |
| `test_capabilities_is_frozenset` | `capabilities` returns `frozenset[Capability]` |
| `test_generate_returns_provider_response` | `generate()` returns valid `ProviderResponse` |
| `test_generate_raises_on_failure` | Network error → raises `ProviderConnectionError` |
| `test_health_check_returns_status` | `health_check()` returns `ProviderHealthStatus` |
| `test_list_models_returns_model_info` | `list_models()` returns `list[ModelInfo]` |
| `test_supports_matches_capabilities` | `supports(X)` returns `True` iff `X in capabilities` |
| `test_shutdown_is_idempotent` | Calling `shutdown()` twice doesn't raise |

---

## Appendix A: Glossary

| Term | Definition |
|---|---|
| **Provider** | An AI service backend (Ollama, Gemini, OpenAI, etc.) that can execute inference |
| **Capability** | A discrete feature a provider supports (chat, vision, embeddings, etc.) |
| **Routing** | The process of selecting the optimal provider for a given request |
| **Fallback** | Automatically retrying a failed request with a different provider |
| **Health State** | The current availability status of a provider (HEALTHY, DEGRADED, UNAVAILABLE) |
| **Gateway** | The public interface through which the Jarvis pipeline accesses AI models |
| **Selection Policy** | The algorithm that ranks eligible providers to pick the best one |
| **Circuit Breaker** | Pattern that quickly removes failing providers and slowly re-introduces them |

## Appendix B: Decision Log

| Decision | Rationale | Alternatives Considered |
|---|---|---|
| Abstract `ModelGateway` interface | Planner depends on abstraction, not concrete router | Direct provider calls from Planner |
| Capability enum over string tags | Type safety, IDE autocomplete, exhaustiveness checks | Freeform string tags |
| YAML config over TOML/JSON | Human-readable, comments supported, Python ecosystem standard | TOML (less readable for nested), JSON (no comments) |
| API keys in env vars only | Security — keys never on disk in plaintext | Encrypted config file (complex), keyring (platform-specific) |
| Passive + active health checks | Passive avoids extra network calls; active enables recovery detection | Passive only (can't detect recovery), Active only (wasteful) |
| Weighted score policy as default | Flexible, tunable, handles multi-dimensional optimization | Round-robin (ignores quality), Random (unpredictable), Rule-based (rigid) |
| `fallback_count` in response | Enables upstream logging/display without coupling to router internals | Exceptions for fallback (too noisy), Silent fallback (no observability) |

---

*End of Document*
