import os
import json
from dotenv import load_dotenv
from langsmith import Client

# Load environment variables
load_dotenv()

PROMPTS_TO_SYNC = [
    "theological-agent-panorama-prompt",
    "theological-agent-lexical-prompt",
    "theological-agent-historical-prompt",
    "theological-agent-intertextual-prompt",
    "theological-agent-validator-prompt",
    "theological-agent-synthesizer-prompt",
]

FALLBACK_FILE = os.path.join(
    "src", "app", "utils", "fallbacks", "prompts_fallback.json"
)


def sync_prompts():
    """
    Fetches LangChain chains from LangSmith and extracts both the strict
    system/human text templates AND the model configuration natively.
    """
    print("Starting LangSmith prompt synchronization...")
    os.makedirs(os.path.dirname(FALLBACK_FILE), exist_ok=True)

    client = Client()
    fallback_data = {}
    success_count = 0

    for prompt_name in PROMPTS_TO_SYNC:
        print(f"Pulling: {prompt_name}...")
        try:
            # Pull full chain (Prompt | Model) using secrets_from_env=True
            chain = client.pull_prompt(
                prompt_name, include_model=True, secrets_from_env=True
            )

            prompt_commit_hash = None

            # 1. Extract Messages from the first part of the chain (ChatPromptTemplate)
            extracted_messages = []
            prompt_template = getattr(chain, "first", chain)
            prompt_metadata = getattr(prompt_template, "metadata", {}) or {}
            if isinstance(prompt_metadata, dict):
                prompt_commit_hash = prompt_metadata.get("lc_hub_commit_hash")

            if hasattr(prompt_template, "messages"):
                for msg in prompt_template.messages:
                    msg_type = "system" if "System" in type(msg).__name__ else "human"
                    if hasattr(msg, "prompt") and hasattr(msg.prompt, "template"):
                        template_text = msg.prompt.template
                    elif hasattr(msg, "content"):
                        template_text = msg.content
                    else:
                        template_text = str(msg)

                    extracted_messages.append(
                        {"type": msg_type, "template": template_text}
                    )
            else:
                extracted_messages.append(
                    {
                        "type": "system",
                        "template": getattr(
                            prompt_template, "template", str(prompt_template)
                        ),
                    }
                )

            # 2. Extract Model Info from the last part of the chain (RunnableBinding -> ChatModel)
            model_info = {}
            model_node = getattr(chain, "last", None)

            if model_node and hasattr(model_node, "bound"):
                bound_model = model_node.bound

                # Extract parameters correctly
                model_name = getattr(
                    bound_model,
                    "model",
                    getattr(bound_model, "model_name", "gemini-2.5-flash"),
                )
                temperature = getattr(bound_model, "temperature", 0.0)

                model_info = {"model_name": model_name, "temperature": temperature}

            fallback_data[prompt_name] = {
                "name": prompt_name,
                "messages": extracted_messages,
                "model_config": model_info,
                "prompt_commit_hash": prompt_commit_hash,
            }

            print(
                f"  -> Success ({len(extracted_messages)} msg, Model: {model_info.get('model_name')}, Commit: {prompt_commit_hash or 'unknown'})"
            )
            success_count += 1

        except Exception as e:
            print(f"  -> Error processing {prompt_name}: {e}")

    # Save to JSON elegantly
    with open(FALLBACK_FILE, "w", encoding="utf-8") as f:
        json.dump(fallback_data, f, indent=4, ensure_ascii=False)

    print(
        f"\nSynchronization complete. Saved {success_count}/{len(PROMPTS_TO_SYNC)} prompts to {FALLBACK_FILE}."
    )


if __name__ == "__main__":
    sync_prompts()
