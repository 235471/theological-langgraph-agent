# LangSmith Prompt Hub Fallback Architecture

## 1. The Sync Script (Offline/Cron Job)
A dedicated script `sync_prompts.py` runs periodically (or manually) to fetch the latest production prompts from LangSmith.
It saves the raw JSON structure of the prompt templates to `src/app/utils/prompts_fallback.json`.

## 2. The Application Flow (`build.py`)
Inside each agent node, we implement a robust try/except block.

### Step 2a: The Primary Route (Online Hub)
The application attempts to connect to LangSmith to fetch the prompt dynamically.
```python
from langchain import hub

try:
    chain = hub.pull("theological-agent-panorama-prompt", include_model=True, secrets_from_env=True)
    # The chain is a RunnableSequence (Prompt + Model) configured by the UI
    response = chain.invoke(...)
```

### Step 2b: The Fallback Route (Offline JSON)
If the LangSmith API is down, or times out, the `except` block catches the error and falls back to the local JSON file.

We need a helper function to read the JSON and reconstruct a LangChain `ChatPromptTemplate`:

```python
import json
from langchain_core.prompts import ChatPromptTemplate
from app.client.client import get_panorama_model

def load_fallback_prompt(prompt_name: str) -> ChatPromptTemplate:
    with open("src/app/utils/prompts_fallback.json", "r") as f:
        data = json.load(f)
        
    prompt_data = data.get(prompt_name)
    if not prompt_data:
        raise ValueError(f"Prompt {prompt_name} not found in fallback JSON.")
    
    # In Langchain, the prompt_dict usually holds a list of messages under 'messages'
    # For a conversational prompt, we can often reconstruct it from the raw dictionaries
    # However, parsing the raw LangSmith dict back into a LangChain object can be tricky if the format changes.
    
    # A safer approach is to extract the content strings from the JSON and build a simple SystemMessage/HumanMessage pair manually,
    # OR we use langchain.prompts.load.load_prompt if we save the file using the official LangChain serialization (json/yaml).
```

## 3. Recommended Approach for Serialization
Instead of manually dumping `prompt.dict()`, LangChain provides built-in tools for saving and loading prompts cleanly.

**In `sync_prompts.py`:**
We should use LangChain's built-in `prompt.save()` method to save as `.yaml` or `.json`, which preserves the exact structure needed to reconstruct the prompt object later.

```python
# sync_prompts.py
from langchain import hub

prompt = hub.pull("theological-agent-panorama-prompt") # Without include_model
prompt.save("src/app/utils/fallbacks/panorama-prompt.yaml")
```

**In `build.py`:**
```python
# build.py
from langchain.prompts import load_prompt

# Inside the except block:
prompt_template = load_prompt("src/app/utils/fallbacks/panorama-prompt.yaml")
model = get_panorama_model()
chain = prompt_template | model
response = chain.invoke(...)
```

**Conclusion:** Using LangChain's native `.save()` and `load_prompt()` is significantly safer and cleaner than writing custom JSON parsers. It cleanly separates the prompt text from the model execution, allowing us to still use our robust `client.py` fallback logic when LangSmith is offline.
