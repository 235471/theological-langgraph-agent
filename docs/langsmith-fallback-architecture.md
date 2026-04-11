# LangSmith Prompt Hub Fallback Architecture

This project uses a resilient fallback strategy so analysis can continue even when LangSmith is unavailable.

## 1. Runtime Strategy

The fallback flow is centralized in `src/app/utils/hub_fallback.py` via:

- `execute_with_fallback(prompt_name, format_vars, structured_schema=None, max_tokens=None)`

Execution order:

1. **Primary path (LangSmith Hub):**
   - Pull prompt + model with `Client().pull_prompt(..., include_model=True, secrets_from_env=True)`.
   - Execute with template variables.
   - Return parsed/structured output plus model and prompt commit hash metadata.
2. **Fallback path (Local JSON):**
   - Load prompt replica from `src/app/utils/fallbacks/prompts_fallback.json`.
   - Rebuild messages and model configuration from JSON.
   - Execute locally using `GOOGLE_API_KEY` from environment.

## 2. Why This Design Works

- **No single point of failure:** prompt execution works even when Hub calls fail.
- **Audit continuity:** prompt commit hash and model used are still propagated for governance.
- **Operational simplicity:** one utility handles both normal and degraded modes.

## 3. Local Replica Synchronization

The local fallback file is maintained by:

```bash
python sync_prompts.py
```

The script pulls all configured prompts from LangSmith and updates:

- `src/app/utils/fallbacks/prompts_fallback.json`

## 4. Fallback JSON Shape

```json
{
  "theological-agent-panorama-prompt": {
    "name": "theological-agent-panorama-prompt",
    "messages": [
      {"type": "system", "template": "..."},
      {"type": "human", "template": "..."}
    ],
    "model_config": {
      "model_name": "gemini-3.1-flash-lite-preview",
      "temperature": 0.2
    },
    "prompt_commit_hash": "a7b2c3d..."
  }
}
```

## 5. Notes

- The fallback path performs safe manual placeholder replacement to avoid template-format issues with markdown content containing braces.
- If both Hub and local fallback fail, the utility raises a combined error with both failure causes.
