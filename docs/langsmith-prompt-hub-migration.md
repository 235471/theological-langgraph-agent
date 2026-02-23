# Migrating Prompts to LangSmith Prompt Hub

## 1. Overview
Currently, our prompts are hardcoded as strings in `src/app/utils/prompts.py`, and model hyperparameters (temperature, max_tokens) are hardcoded in `src/app/client/client.py`.

Migrating to **LangSmith Prompt Hub** allows us to:
1. **Decouple Prompts from Code:** Theologians or domain experts can refine instructions directly in the UI without deploying new code.
2. **Version Control:** LangSmith automatically versions every prompt change.
3. **Observability Sync:** Traces in LangSmith will cleanly link back to the exact prompt version that generated them.
4. **Centralized Hyperparameters:** We can manage `temperature` and `max_tokens` inside the Hub alongside the prompt text.

## 2. Configuration in LangSmith Hub (UI Steps)

For each node (Panorama, Lexical, Historical, Intertextual, Validator, Synthesizer), follow these steps in the LangSmith UI (https://smith.langchain.com/hub):

1. Click **"New Prompt"**.
2. **Name the Prompt:** Use a namespaced convention, e.g., `theological-agent/panorama-prompt`.
3. **Set the Chat Pattern:**
   * **System Message:** Paste the `<IDENTITY>`, `<TASK>`, `<INSTRUCTIONS>`, etc.
   * **Human Message:** Use variables like `{livro} {capitulo}:{versiculos}`.
4. **Configure the Model & Hyperparameters:**
   * In the top-right or configuration panel, select the provider (Google GenAI) and model (e.g., `gemini-2.5-flash-lite`).
   * Set the parameters according to our current `client.py`:
     * **Panorama:** Temp `0.2`
     * **Lexical:** Temp `0.1`
     * **Historical:** Temp `0.2`
     * **Intertextual:** Temp `0.2`
     * **Validator:** Temp `0.1`, Max Tokens `10000`
     * **Synthesizer:** Temp `0.4`, Max Tokens `10000`
5. Click **Commit** to save the first version (e.g., `v1`).

## 3. Code Integration Strategy

Once the prompts are in the Hub, we update our code to pull them.

### A. Install Dependencies
Ensure `langchainhub` is installed:
```bash
pip install langchainhub
```

### B. Fetching the Prompt in Code
In `src/app/agent/build.py`, instead of importing `PANORAMA_PROMPT` from `prompts.py`, we pull it from the hub:

```python
from langchain import hub

# Pull the latest version (or pin to a specific commit hash for production stability)
# The boolean `include_model_kwargs=True` ensures we get the temperature/params from the Hub
prompt = hub.pull("theological-agent/panorama-prompt", include_model_kwargs=True)
```

### C. Integrating with the LLM Client
Because the Prompt Hub can store the model configuration (temperature, max tokens), the way we instantiate our chain changes slightly. 

Currently we do:
```python
model = get_panorama_model() # Hardcoded temp=0.2 in client.py
messages = [SystemMessage(...), HumanMessage(...)]
response = model.invoke(messages)
```

**New Approach (Using Langchain LCEL):**
When pulling a prompt from the Hub that includes model configurations, it's often easiest to construct a chain. If we want to keep our fallback logic (`get_llm_client_with_fallback`), we can pass the downloaded prompt to our existing model client.

```python
from langchain import hub

def panorama_node(state: TheologicalState):
    start = time.time()
    model = get_panorama_model() # You can simplify this to just get a base client if hyperparams move to Hub
    
    # Hub pull (this is fast, but in production we can cache the prompt in memory)
    prompt_template = hub.pull("theological-agent/panorama-prompt")
    
    # Create the chain: prompt | model
    chain = prompt_template | model
    
    # Invoke with variables
    response = chain.invoke({
        "livro": state["bible_book"],
        "capitulo": state["chapter"],
        "versiculos": " ".join(state["verses"])
    })
    
    return _build_node_result(
        state, "panorama_agent", ModelTier.FLASH, response, start,
        output_field="panorama_content", raw_response=response
    )
```

## 4. Next Steps
1. Create the repository inside LangSmith Hub for each of the 6 agents.
2. Copy the strings from `src/app/utils/prompts.py` into the respective Hub prompts.
3. Replace the local prompt definitions in `build.py` with `hub.pull("seu-usuario/nome-do-prompt")`.
4. Run a test analysis to verify that the traces show the linked Prompt Hub commit.
