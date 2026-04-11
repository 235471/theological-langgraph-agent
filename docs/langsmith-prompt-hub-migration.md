# LangSmith Prompt Hub Integration

This document explains how prompt management works after the Hub migration.

## 1. Overview

Prompts are managed in [LangSmith Hub](https://smith.langchain.com/hub), not hardcoded in node logic.

Benefits:

1. **UI-driven refinement:** update prompt instructions without editing code.
2. **Versioning:** each published prompt commit can be tracked.
3. **Model coupling:** prompt + model settings travel together at runtime.

## 2. Prompt Naming

Current prompt names follow this pattern:

- `theological-agent-panorama-prompt`
- `theological-agent-lexical-prompt`
- `theological-agent-lexical-prompt-legacy`
- `theological-agent-historical-prompt`
- `theological-agent-intertextual-prompt`
- `theological-agent-validator-prompt`
- `theological-agent-synthesizer-prompt`

## 3. Runtime Integration Pattern

Nodes use `execute_with_fallback(...)` from `app.utils.hub_fallback`.

```python
from app.utils.hub_fallback import execute_with_fallback

response, raw, model_used, prompt_commit_hash = execute_with_fallback(
    prompt_name="theological-agent-panorama-prompt",
    format_vars={
        "livro": state["bible_book"],
        "capitulo": state["chapter"],
        "versiculos": " ".join(state["verses"]),
    },
)
```

This call handles:

1. Hub pull + execution in normal mode.
2. Local JSON fallback when Hub is unavailable.
3. Governance metadata (`model_used`, `prompt_commit_hash`) propagation.

## 4. Syncing the Local Replica

Run from repository root:

```bash
python sync_prompts.py
```

The sync script refreshes `src/app/utils/fallbacks/prompts_fallback.json` with:

- message templates
- model configuration
- prompt commit hash

## 5. Operational Recommendation

Run `sync_prompts.py` as part of CI/CD or pre-release checks so offline fallback stays aligned with your latest published prompts.
