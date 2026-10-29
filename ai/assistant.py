"""The AI analyst's agent loop: Claude + Yahoo Finance tools + web search, streamed as UI events.

History is append-only (required for prompt caching and preserved thinking): each turn appends
user message -> app-context system message -> assistant/tool-result turns. A turn that fails with
an API error is rolled back so the history stays valid.
"""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Iterator

import anthropic

import config
from ai import tools
from ai.citations import SourceLog, collect_from_content
from ai.prompts import SYSTEM_PROMPT
from ai.web_search import WEB_SEARCH_TOOL, search_status_label

MAX_STEPS = 14
MAX_TOKENS = 64000
FALLBACK_BETA = "server-side-fallback-2026-07-01"

TOOL_LABELS = {
    "get_company_snapshot": "company snapshot",
    "get_key_statistics": "key statistics",
    "get_price_history": "price history",
    "get_financial_statement": "financial statement",
    "get_financial_ratios": "financial ratios",
    "get_holders": "ownership data",
    "get_company_news": "company news",
    "compare_companies": "peer comparison",
    "calculate": "calculation",
    "search_companies": "ticker lookup",
}


@dataclass
class Event:
    kind: str  # text | status | tool_done | error | refusal | done
    text: str = ""
    data: dict = field(default_factory=dict)


def describe_tool_call(name: str, tool_input: Any) -> str:
    label = TOOL_LABELS.get(name, name)
    if not isinstance(tool_input, dict):
        return f"Fetching {label}"
    target = tool_input.get("symbol") or ", ".join(tool_input.get("symbols") or [])
    extra = " ".join(str(tool_input[k]) for k in ("frequency", "statement", "period", "operation") if tool_input.get(k))
    return f"Fetching {label}" + (f" · {target}" if target else "") + (f" ({extra})" if extra else "")


class Analyst:
    def __init__(self, client: anthropic.Anthropic | None = None, model: str | None = None, effort: str | None = None):
        self.client = client or anthropic.Anthropic(api_key=config.anthropic_api_key())
        self.model = model or config.ANALYST_MODEL
        self.effort = effort or config.ANALYST_EFFORT

    def _request(self, history: list) -> dict:
        return dict(
            model=self.model,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=history,
            tools=[*tools.TOOL_DEFINITIONS, WEB_SEARCH_TOOL],
            thinking={"type": "adaptive"},
            output_config={"effort": self.effort},
            cache_control={"type": "ephemeral"},
            betas=[FALLBACK_BETA],
            fallbacks="default",
        )

    def run(self, history: list, user_text: str, context_note: str) -> Iterator[Event]:
        """Append one user turn to `history` (mutated in place) and stream the answer."""
        start_len = len(history)
        history.append({"role": "user", "content": user_text})
        history.append({"role": "system", "content": context_note})
        sources = SourceLog()
        json_retries = 0
        stop_reason = None
        try:
            step = 0
            while step < MAX_STEPS:
                step += 1
                try:
                    with self.client.beta.messages.stream(**self._request(history)) as stream:
                        for event in stream:
                            if event.type == "text":
                                yield Event("text", event.text)
                            elif event.type == "content_block_start":
                                block = event.content_block
                                if block.type == "server_tool_use":
                                    yield Event("status", search_status_label(None))
                                elif block.type == "tool_use":
                                    yield Event("status", f"Fetching {TOOL_LABELS.get(block.name, block.name)}…")
                        response = stream.get_final_message()
                    json_retries = 0
                except ValueError:
                    # Tool input JSON the SDK could not parse at all; re-issue the step (bounded).
                    json_retries += 1
                    if json_retries > 2:
                        raise
                    step -= 1
                    continue

                history.append({"role": "assistant", "content": response.content})
                collect_from_content(response.content, sources)
                for q in sources.queries[-3:]:
                    yield Event("status", search_status_label(q))
                stop_reason = response.stop_reason

                if stop_reason == "pause_turn":  # server tool (web search) paused a long turn
                    continue
                if stop_reason == "refusal":
                    details = getattr(response, "stop_details", None)
                    yield Event("refusal", "The model declined to answer this request.",
                                {"category": getattr(details, "category", None)})
                    break

                tool_uses = [b for b in response.content if b.type == "tool_use"]
                if not tool_uses:
                    if stop_reason == "max_tokens":
                        yield Event("error", "The answer was cut off because it reached the length limit.")
                    break

                if stop_reason == "max_tokens":
                    # A truncated tool input parses as a partial object: don't run it, keep history valid.
                    history.append({"role": "user", "content": [
                        {"type": "tool_result", "tool_use_id": b.id, "is_error": True,
                         "content": "Tool input was truncated (max_tokens); not executed."} for b in tool_uses]})
                    yield Event("error", "The answer was cut off because it reached the length limit.")
                    break

                for b in tool_uses:
                    yield Event("status", describe_tool_call(b.name, b.input))
                with ThreadPoolExecutor(max_workers=min(6, len(tool_uses))) as pool:
                    outputs = list(pool.map(lambda b: tools.execute(b.name, b.input), tool_uses))
                results = []
                for b, (content, is_error) in zip(tool_uses, outputs):
                    if not is_error:
                        sources.add_tool_result(b.name, b.input if isinstance(b.input, dict) else {}, content)
                    results.append({"type": "tool_result", "tool_use_id": b.id, "content": content, "is_error": is_error})
                    yield Event("tool_done", describe_tool_call(b.name, b.input), {"is_error": is_error})
                history.append({"role": "user", "content": results})
            else:
                yield Event("error", "Stopped after too many research steps; the answer may be incomplete.")
        except anthropic.AuthenticationError:
            del history[start_len:]
            yield Event("error", "Anthropic API key is missing or invalid. Set ANTHROPIC_API_KEY and reload.")
        except anthropic.RateLimitError:
            del history[start_len:]
            yield Event("error", "Rate limited by the Anthropic API. Please wait a moment and try again.")
        except anthropic.APIStatusError as exc:
            del history[start_len:]
            yield Event("error", f"Anthropic API error ({exc.status_code}): {exc.message}")
        except anthropic.APIConnectionError:
            del history[start_len:]
            yield Event("error", "Could not reach the Anthropic API. Check your network connection.")
        except ValueError as exc:
            del history[start_len:]
            yield Event("error", f"Malformed tool call from the model: {exc}")
        yield Event("done", data={"sources": sources.to_dict(), "stop_reason": stop_reason})


def history_to_transcript(history: list) -> str:
    """Debug helper: compact JSON-ish view of the conversation."""
    def block_text(b):
        t = getattr(b, "type", None) or (b.get("type") if isinstance(b, dict) else None)
        return t or "text"
    lines = []
    for m in history:
        c = m["content"]
        lines.append(f"{m['role']}: " + (c[:200] if isinstance(c, str) else json.dumps([block_text(b) for b in c])))
    return "\n".join(lines)
