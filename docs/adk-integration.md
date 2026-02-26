# ADK Integration Reference: Agent-in-an-Agent

This document explains the architectural decisions, trade-offs, and mechanics behind the Lexical Agent's **Agent Development Kit (ADK)** grounding implementation in the LangGraph system.

## The Challenge: Web-Grounded Exegesis

Theological exegesis requires extreme accuracy. For the Lexical analysis node, a standard LLM often relies too much on its training weights and risks hallucinative etymologies. We needed a way to ground the lexical analysis in authoritative academic sources.

Instead of writing a complex LangChain tool for Tavily or Google Search, we embedded Google's **Agent Development Kit (ADK)** inside our LangGraph architecture.

## Architecture: The "Single-Pass" Approach

Originally, we considered a two-pass approach:
1. ADK searches the web and extracts "grounding context".
2. A secondary LangChain `execute_with_fallback` call formats the final response.

**The shift:** ADK is already an autonomous agent. We instructed ADK to perform the web search *and* synthesize the final Markdown report in **a single pass**. 

### Latency vs Autonomy Trade-off
Why ADK instead of a simple REST search API (like Tavily) passed into LangChain?
- **Pro:** Autonomy. The ADK decides *when* to search, reads the results, and can execute multiple remote calls (AFC) until it gathers enough lexical evidence to fulfill its exact prompt instructions.
- **Con:** Latency. ADK requires creating session storage, invoking the internal Google Search gRPC tool, and managing its own event stream. A typical cold start takes ~15-20 seconds.

## Implementation Mechanics

The ADK integration is isolated within `src/app/service/lexical_grounding_service.py`. It implements several advanced patterns to fit cleanly into a LangGraph + Uvicorn/Streamlit environment.

### 1. Threaded `asyncio` Sync (`_run_coro_sync`)

The ADK `Runner` operates exclusively asynchronously and relies heavily on event streaming. However, our overarching LangGraph architecture relies on synchronous node functions to ensure predictable state propagation. Since Uvicorn and Streamlit already run their own active event loops, calling `asyncio.run()` directly inside the graph throws a `RuntimeError`.

To bridge this, we spawn a daemon `threading.Thread` containing a fresh event loop specifically for the ADK payload. 

**The Timeout Guard:** If the ADK gRPC process hangs internally, `asyncio.wait_for` might not catch it. We enforce the fallback SLA directly at the synchronization boundary by calling `thread.join(timeout=...)`.

### 2. Telemetry Extraction (Tokens & Search Calls)

When bypassing `langchain`, we lose its automatic token-counting features. Left untreated, the Lexical Agent would appear as a "black box" in our audit logs, corrupting ROI governance.

We extract the metrics manually from the ADK's binary event payload tree:
```python
def _extract_tokens_from_payload(payload):
    # Recursively searches the ADK event tree for `prompt_token_count` and
    # `candidates_token_count`. Prevents double counting metadata structs
    # that appear multiple times in the payload graph using the `id()` hash.
```
This parsed dictionary is passed up to `build.py` where it populates `usage_metadata` mock objects, keeping the LangGraph completely isolated from the ADK SDK details.

### 3. LangSmith Tracing

Even though the ADK agent doesn't natively integrate with LangSmith, we've restored observability by injecting:
```python
@traceable(name="adk_lexical_agent", run_type="chain")
```
Because the parent LangGraph execution maintains standard Python context variables, LangSmith automatically associates this ADK execution as a child `chain` span to the main analysis trace.

### 4. Seamless Fallback Resilience

If the ADK single-pass encounters any anomaly—a network timeout (exceeding 15-25 seconds), an empty response, or poor formatting missing the necessary markdown headers—the error is safely swallowed and logged.

The `lexical_node` then immediately falls back to execute `prompt_name="theological-agent-lexical-prompt-legacy"` via LangChain, skipping grounding and ensuring the user always receives a response.
