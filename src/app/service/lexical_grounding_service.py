"""
Lexical grounding service (ADK + Google Search).

Single-pass mode:
- Search + lexical report generation in one ADK call.
- If ADK fails or returns low-quality content, callers can fallback to legacy.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from app.client.client import ModelTier
from app.service.bible_service import get_specific_verses
from app.utils.logger import get_logger

try:
    from langsmith import Client, traceable
except ImportError:
    Client = None

    def traceable(*args, **kwargs):
        def decorator(func):
            return func

        return decorator


logger = get_logger(__name__)
PROMPT_NAME = "theological-agent-lexical-prompt"
FALLBACK_FILE = os.path.normpath(
    os.path.join(
        os.path.dirname(__file__), "..", "utils", "fallbacks", "prompts_fallback.json"
    )
)
_ls_client: Client | None = None
_lexical_prompt_cache: dict[str, str | None] | None = None


@dataclass
class LexicalGroundingResult:
    used_grounding: bool
    lexical_report_markdown: str
    grounded_lexical_context: str
    sources: list[dict]
    provider: str
    error: str | None = None
    duration_ms: int = 0
    search_calls: int = 0
    tokens_consumed: dict = field(default_factory=lambda: {"input": 0, "output": 0})
    prompt_commit_hash: str | None = None
    prompt_source: str = "unknown"


def _get_ls_client() -> Client:
    global _ls_client
    if Client is None:
        raise RuntimeError("langsmith package is not available")
    if _ls_client is None:
        _ls_client = Client()
    return _ls_client


def _extract_templates(messages: list[Any]) -> tuple[str, str]:
    system_template = ""
    human_template = ""

    for msg in messages:
        msg_type = ""
        if isinstance(msg, dict):
            # Plain-dict messages (local JSON fallback): must read 'type' from the dict
            msg_type = (msg.get("type") or "").lower()
            template_text = msg.get("template") or msg.get("content") or ""
        elif hasattr(msg, "type"):
            msg_type = str(getattr(msg, "type", "")).lower()
            if hasattr(msg, "prompt") and hasattr(msg.prompt, "template"):
                template_text = msg.prompt.template
            elif hasattr(msg, "content"):
                template_text = msg.content
            else:
                template_text = str(msg)
        else:
            # Last resort: infer from class name
            msg_type = "system" if "System" in type(msg).__name__ else "human"
            if hasattr(msg, "prompt") and hasattr(msg.prompt, "template"):
                template_text = msg.prompt.template
            elif hasattr(msg, "content"):
                template_text = msg.content
            else:
                template_text = str(msg)

        if msg_type == "system" and not system_template:
            system_template = str(template_text or "")
        elif msg_type in {"human", "user"} and not human_template:
            human_template = str(template_text or "")

    return system_template, human_template


def _load_prompt_from_hub() -> dict[str, str | None]:
    chain = _get_ls_client().pull_prompt(
        PROMPT_NAME, include_model=True, secrets_from_env=True
    )
    prompt_template = getattr(chain, "first", chain)
    prompt_metadata = getattr(prompt_template, "metadata", {}) or {}
    prompt_commit_hash = (
        prompt_metadata.get("lc_hub_commit_hash")
        if isinstance(prompt_metadata, dict)
        else None
    )
    raw_messages = getattr(prompt_template, "messages", [])
    system_template, human_template = _extract_templates(raw_messages)
    if not system_template and not human_template:
        raise ValueError("Prompt template did not include readable messages")

    return {
        "system_template": system_template,
        "human_template": human_template,
        "prompt_commit_hash": prompt_commit_hash,
        "prompt_source": "langsmith_hub",
    }


def _load_prompt_from_local_fallback() -> dict[str, str | None]:
    with open(FALLBACK_FILE, "r", encoding="utf-8") as file:
        fallback_data = json.load(file).get(PROMPT_NAME) or {}
    raw_messages = fallback_data.get("messages") or []
    system_template, human_template = _extract_templates(raw_messages)
    if not system_template and not human_template:
        raise ValueError(f"{PROMPT_NAME} not found in local fallback file")

    return {
        "system_template": system_template,
        "human_template": human_template,
        "prompt_commit_hash": fallback_data.get("prompt_commit_hash"),
        "prompt_source": "local_fallback_json",
    }


def _get_lexical_prompt_config() -> dict[str, str | None]:
    global _lexical_prompt_cache
    if _lexical_prompt_cache is not None:
        return _lexical_prompt_cache

    try:
        prompt_config = _load_prompt_from_hub()
        logger.info(
            "Lexical ADK prompt loaded from LangSmith Hub",
            extra={
                "event": "lexical_prompt_loaded",
                "prompt_name": PROMPT_NAME,
                "prompt_source": prompt_config["prompt_source"],
                "prompt_commit_hash": prompt_config.get("prompt_commit_hash"),
            },
        )
        _lexical_prompt_cache = prompt_config
        return prompt_config
    except Exception as hub_error:
        logger.warning(
            "Failed to load lexical prompt from LangSmith Hub; trying local fallback.",
            extra={
                "event": "lexical_prompt_hub_failed",
                "prompt_name": PROMPT_NAME,
                "error": str(hub_error),
            },
        )

    try:
        prompt_config = _load_prompt_from_local_fallback()
        logger.info(
            "Lexical ADK prompt loaded from local fallback JSON",
            extra={
                "event": "lexical_prompt_loaded",
                "prompt_name": PROMPT_NAME,
                "prompt_source": prompt_config["prompt_source"],
                "prompt_commit_hash": prompt_config.get("prompt_commit_hash"),
            },
        )
        _lexical_prompt_cache = prompt_config
        return prompt_config
    except Exception as fallback_error:
        logger.warning(
            "Failed to load lexical prompt from local fallback; using built-in template.",
            extra={
                "event": "lexical_prompt_local_fallback_failed",
                "prompt_name": PROMPT_NAME,
                "error": str(fallback_error),
            },
        )
        raise RuntimeError(
            f"Could not load '{PROMPT_NAME}' from LangSmith Hub or local fallback. "
            "ADK grounding cannot proceed without a valid prompt."
        ) from fallback_error


def _parse_int_env(name: str, default: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        return max(1, int(raw))
    except (TypeError, ValueError):
        return default


def _parse_csv_env(name: str) -> list[str]:
    raw = os.getenv(name, "")
    if not raw:
        return []
    return [item.strip().lower() for item in raw.split(",") if item.strip()]


def _safe_excerpt(text: str, max_len: int = 450) -> str:
    text = (text or "").strip()
    if len(text) <= max_len:
        return text
    return text[:max_len].rstrip() + "..."


def _extract_text_from_event(event: Any) -> str:
    content = getattr(event, "content", None)
    if content is None:
        return ""

    parts = getattr(content, "parts", None)
    if not parts:
        return ""

    texts: list[str] = []
    for part in parts:
        text = getattr(part, "text", None)
        if text:
            texts.append(str(text).strip())

    return "\n".join([t for t in texts if t]).strip()


def _to_primitive(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_to_primitive(v) for v in value]
    if isinstance(value, dict):
        return {k: _to_primitive(v) for k, v in value.items()}
    if hasattr(value, "model_dump"):
        try:
            return _to_primitive(value.model_dump())
        except Exception:
            pass
    if hasattr(value, "dict"):
        try:
            return _to_primitive(value.dict())
        except Exception:
            pass
    if hasattr(value, "__dict__"):
        try:
            return _to_primitive(vars(value))
        except Exception:
            pass
    return str(value)


def _extract_sources_from_payload(payload: Any) -> list[dict]:
    candidates: list[dict] = []

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            url = node.get("url") or node.get("uri")
            title = node.get("title") or node.get("source") or ""
            snippet = node.get("snippet") or node.get("text") or ""

            if isinstance(url, str) and url.startswith(("http://", "https://")):
                domain = urlparse(url).netloc.lower()
                candidates.append(
                    {
                        "url": url,
                        "title": str(title).strip(),
                        "snippet": _safe_excerpt(str(snippet), max_len=220),
                        "domain": domain,
                    }
                )

            for child in node.values():
                visit(child)
            return

        if isinstance(node, list):
            for item in node:
                visit(item)

    visit(payload)

    seen: set[tuple[str, str]] = set()
    deduped: list[dict] = []
    for src in candidates:
        key = (src.get("url", ""), src.get("title", ""))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(src)
    return deduped


def _filter_sources(sources: list[dict], exclude_domains: list[str]) -> list[dict]:
    if not exclude_domains:
        return sources

    filtered: list[dict] = []
    for src in sources:
        domain = (src.get("domain") or "").lower()
        if any(blocked in domain for blocked in exclude_domains):
            continue
        filtered.append(src)
    return filtered


def _render_template(template: str, variables: dict[str, Any]) -> str:
    rendered = template or ""
    for key, value in variables.items():
        rendered = rendered.replace("{" + key + "}", str(value))
    return rendered


def _build_adk_prompt(
    book: str,
    chapter: int,
    verse_numbers: list[int],
    verse_texts: list[str],
    max_sources: int,
    exclude_domains: list[str],
) -> tuple[str, str, str, str | None]:
    reference = f"{book} {chapter}:{','.join(str(v) for v in verse_numbers)}"
    verse_lines = [
        f"{number}. {text}"
        for number, text in zip(verse_numbers, verse_texts, strict=False)
        if text
    ]
    exclude_note = ", ".join(exclude_domains) if exclude_domains else "nenhum"
    variables = {
        "reference": reference,
        "verses": "\n".join(verse_lines),
        "max_sources": max_sources,
        "exclude_note": exclude_note,
    }
    prompt_config = _get_lexical_prompt_config()
    instruction = _render_template(
        str(prompt_config.get("system_template")), variables
    ).strip()
    user_query = _render_template(
        str(prompt_config.get("human_template")), variables
    ).strip()

    return (
        instruction,
        user_query,
        str(prompt_config.get("prompt_source") or "unknown"),
        (
            str(prompt_config["prompt_commit_hash"])
            if prompt_config.get("prompt_commit_hash")
            else None
        ),
    )


async def _run_adk_grounding_async(
    instruction: str,
    user_query: str,
    model_name: str,
    timeout_seconds: float,
    afc_max_remote_calls: int,
) -> tuple[str, list[dict], int, dict]:
    from google.adk.agents import Agent
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.adk.tools import google_search
    from google.genai import types

    app_name = "theological_agent_lexical_grounding"
    user_id = "lexical_grounding_user"
    session_id = str(uuid.uuid4())

    root_agent = Agent(
        name="lexical_grounding_agent",
        model=model_name,
        description="Grounded lexical helper for theological exegesis.",
        instruction=instruction,
        generate_content_config=types.GenerateContentConfig(
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                maximum_remote_calls=afc_max_remote_calls
            )
        ),
        tools=[google_search],
    )

    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name=app_name, user_id=user_id, session_id=session_id
    )
    runner = Runner(
        agent=root_agent, app_name=app_name, session_service=session_service
    )

    user_message = types.Content(role="user", parts=[types.Part(text=user_query)])
    events = runner.run_async(
        user_id=user_id, session_id=session_id, new_message=user_message
    )

    async def collect() -> tuple[str, list[dict], int, dict]:
        final_text = ""
        raw_events: list[Any] = []
        async for event in events:
            raw_events.append(event)
            if hasattr(event, "is_final_response") and event.is_final_response():
                maybe_text = _extract_text_from_event(event)
                if maybe_text:
                    final_text = maybe_text

        payload = _to_primitive(raw_events)
        sources = _extract_sources_from_payload(payload)
        search_calls = _estimate_search_calls(payload, source_count=len(sources))
        tokens = _extract_tokens_from_payload(payload)
        return final_text, sources, search_calls, tokens

    return await asyncio.wait_for(collect(), timeout=timeout_seconds)


def _estimate_search_calls(payload: Any, source_count: int = 0) -> int:
    """
    Best-effort search call count extracted from ADK event payload.
    """
    serialized = str(payload).lower()
    search_call_hits = len(re.findall(r"google_search_call", serialized))
    tool_name_hits = len(re.findall(r"name['\"]?:\s*['\"]google_search", serialized))
    total = max(search_call_hits, tool_name_hits)
    if total == 0 and source_count > 0:
        total = 1
    return total


def _extract_tokens_from_payload(payload: Any) -> dict:
    usage = {"input": 0, "output": 0}
    seen_metadata = set()

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            # Google GenAI `usage_metadata` struct (standard or camelCase)
            if "prompt_token_count" in node or "promptTokenCount" in node:
                # Use object id to avoid double counting if the same metadata appears
                # twice in the tree (e.g., inside 'model_response' and 'event')
                node_id = id(node)
                if node_id not in seen_metadata:
                    seen_metadata.add(node_id)
                    in_toks = (
                        node.get("prompt_token_count")
                        or node.get("promptTokenCount")
                        or 0
                    )
                    out_toks = (
                        node.get("candidates_token_count")
                        or node.get("candidatesTokenCount")
                        or 0
                    )
                    usage["input"] += int(in_toks)
                    usage["output"] += int(out_toks)
                return  # Stop recursion for this node

            for child in node.values():
                visit(child)
        elif isinstance(node, list):
            for item in node:
                visit(item)

    visit(payload)
    return usage


def _looks_like_lexical_report(markdown: str, min_chars: int) -> bool:
    content = (markdown or "").strip()
    if len(content) < min_chars:
        return False

    lower = content.lower()
    has_lemas = "lemas" in lower
    has_evidencias = ("evidências" in lower) or ("evidencias" in lower)
    has_fontes = "fontes" in lower
    return has_lemas and has_evidencias and has_fontes


def _build_grounded_context(sources: list[dict], max_chars: int = 1200) -> str:
    """
    Build a compact grounding context from extracted sources.

    This keeps `grounded_lexical_context` semantically distinct from
    `lexical_report_markdown` in single-pass mode.
    """
    if not sources:
        return ""

    chunks: list[str] = []
    for src in sources:
        title = (src.get("title") or "").strip()
        url = (src.get("url") or "").strip()
        snippet = (src.get("snippet") or "").strip()

        line = f"- {title} ({url})"
        if snippet:
            line += f"\n  {snippet}"
        chunks.append(line)

    context = "Fontes grounding consultadas:\n" + "\n".join(chunks)
    if len(context) <= max_chars:
        return context
    return context[:max_chars].rstrip() + "..."


def _run_coro_sync(coro, timeout_seconds: float = 30.0):
    try:
        return asyncio.run(coro)
    except RuntimeError as err:
        if "asyncio.run() cannot be called from a running event loop" not in str(err):
            raise

        result: dict[str, Any] = {}
        error: dict[str, Exception] = {}

        def target():
            try:
                result["value"] = asyncio.run(coro)
            except Exception as thread_err:  # pragma: no cover
                error["value"] = thread_err

        thread = threading.Thread(target=target, daemon=True)
        thread.start()
        thread.join(timeout=timeout_seconds)
        if thread.is_alive():
            raise TimeoutError(
                f"ADK grounding thread exceeded {timeout_seconds:.1f}s timeout"
            )
        if "value" in error:
            raise error["value"]
        return result.get("value")


@traceable(name="adk_lexical_agent", run_type="chain")
def run_lexical_grounding(
    book: str, chapter: int, verses: list[str]
) -> LexicalGroundingResult:
    """
    Generate grounded lexical context using ADK + Google Search.

    Returns a non-throwing result. On failures, `used_grounding=False` and
    `error` is populated so callers can fallback to legacy prompt logic.
    """
    provider = "adk_google_search"
    timeout_ms = _parse_int_env("LEXICAL_GROUNDING_TIMEOUT_MS", 35000)
    max_sources = _parse_int_env("LEXICAL_GROUNDING_MAX_SOURCES", 5)
    afc_max_remote_calls = _parse_int_env("LEXICAL_ADK_AFC_MAX_REMOTE_CALLS", 3)
    min_report_chars = _parse_int_env("LEXICAL_ADK_MIN_REPORT_CHARS", 300)
    exclude_domains = _parse_csv_env("LEXICAL_GROUNDING_EXCLUDE_DOMAINS")
    timeout_seconds = timeout_ms / 1000.0
    started = time.time()

    logger.info(
        "Lexical grounding config: "
        f"timeout={timeout_ms}ms, max_sources={max_sources}, "
        f"afc_max_remote_calls={afc_max_remote_calls}, "
        f"min_report_chars={min_report_chars}, exclude_domains={exclude_domains}",
        extra={"event": "lexical_grounding_config"},
    )

    try:
        if not os.getenv("GOOGLE_API_KEY"):
            raise ValueError(
                "GOOGLE_API_KEY is not set. ADK lexical grounding requires this env var."
            )

        verse_numbers = [int(v) for v in verses if str(v).strip().isdigit()]
        if not verse_numbers:
            raise ValueError("No valid verse numbers to build grounding context.")

        verse_texts = get_specific_verses(book, chapter, verse_numbers)
        if not verse_texts:
            raise ValueError(
                f"Unable to load verse text from NAA for {book} {chapter}:{verse_numbers}."
            )

        instruction, user_query, prompt_source, prompt_commit_hash = _build_adk_prompt(
            book=book,
            chapter=chapter,
            verse_numbers=verse_numbers,
            verse_texts=verse_texts,
            max_sources=max_sources,
            exclude_domains=exclude_domains,
        )
        logger.info(
            "Lexical ADK prompt resolved",
            extra={
                "event": "lexical_prompt_resolved",
                "prompt_name": PROMPT_NAME,
                "prompt_source": prompt_source,
                "prompt_commit_hash": prompt_commit_hash,
            },
        )

        grounded_text, sources, search_calls, tokens_consumed = _run_coro_sync(
            _run_adk_grounding_async(
                instruction=instruction,
                user_query=user_query,
                model_name=ModelTier.FLASH,
                timeout_seconds=timeout_seconds,
                afc_max_remote_calls=afc_max_remote_calls,
            ),
            timeout_seconds=timeout_seconds,
        )

        if not grounded_text or not grounded_text.strip():
            raise ValueError("ADK returned empty grounded lexical content.")
        if not _looks_like_lexical_report(grounded_text, min_report_chars):
            raise ValueError(
                "ADK lexical output did not pass minimum quality gate "
                f"(min_chars={min_report_chars}, required headings)."
            )

        sources = _filter_sources(sources, exclude_domains)[:max_sources]
        duration_ms = int((time.time() - started) * 1000)
        cleaned_markdown = grounded_text.strip()
        grounded_context = _build_grounded_context(sources)

        logger.info(
            "Lexical grounding completed",
            extra={
                "event": "lexical_grounding_success",
                "duration_ms": duration_ms,
                "search_calls": search_calls,
                "sources_count": len(sources),
                "tokens": tokens_consumed,
                "provider": provider,
            },
        )

        return LexicalGroundingResult(
            used_grounding=True,
            lexical_report_markdown=cleaned_markdown,
            grounded_lexical_context=grounded_context,
            sources=sources,
            provider=provider,
            error=None,
            duration_ms=duration_ms,
            search_calls=search_calls,
            tokens_consumed=tokens_consumed,
            prompt_commit_hash=prompt_commit_hash,
            prompt_source=prompt_source,
        )

    except Exception as exc:
        duration_ms = int((time.time() - started) * 1000)
        error_detail = f"{type(exc).__name__}: {exc}" if str(exc) else repr(exc)
        logger.warning(
            f"Lexical grounding failed; using legacy fallback path: {error_detail}",
            extra={
                "event": "lexical_grounding_failed",
                "error_type": type(exc).__name__,
                "error_detail": error_detail,
                "duration_ms": duration_ms,
                "provider": provider,
                "book": book,
                "chapter": chapter,
                "verses": verses,
            },
        )
        return LexicalGroundingResult(
            used_grounding=False,
            lexical_report_markdown="",
            grounded_lexical_context="",
            sources=[],
            provider=provider,
            error=error_detail,
            duration_ms=duration_ms,
            search_calls=0,
        )
