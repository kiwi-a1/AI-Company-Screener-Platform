"""AI analyst sidebar: persistent chat that follows the selected company and active section."""
from __future__ import annotations

from html import escape

import streamlit as st

import config
from ai.context_manager import build_context_note
from ai.prompts import SUGGESTED_PROMPTS
from utils.formatting import fmt_age, to_datetime


def _init_state() -> None:
    st.session_state.setdefault("chat_histories", {})  # provider -> API messages (append-only)
    st.session_state.setdefault("chat_display", [])  # what the user sees
    st.session_state.setdefault("chat_turn_start", None)
    st.session_state.setdefault("pending_prompt", None)


def ask(prompt: str) -> None:
    """Queue a question for the analyst (used by buttons on pages)."""
    st.session_state.pending_prompt = prompt


def _md(text: str) -> str:
    # Streamlit renders $...$ as LaTeX; financial text is full of dollar signs.
    return text.replace("$", "\\$")


def _recover_interrupted_turn() -> None:
    """If a rerun interrupted an answer mid-stream, drop the partial turn so the history stays valid."""
    start = st.session_state.chat_turn_start
    if start is not None:
        hist = st.session_state.chat_histories.get(config.analyst_provider(), [])
        del hist[start:]
        st.session_state.chat_turn_start = None
        if st.session_state.chat_display and st.session_state.chat_display[-1]["role"] == "user":
            st.session_state.chat_display.append(
                {"role": "assistant", "text": "_This answer was interrupted (the page changed). Ask again to retry._",
                 "sources": None, "steps": []}
            )


def _render_sources(sources: dict | None, steps: list[str]) -> None:
    if not sources and not steps:
        return
    web = (sources or {}).get("web") or []
    data = (sources or {}).get("data") or []
    queries = (sources or {}).get("queries") or []
    label = f"Sources & steps ({len(web)} web, {len(data)} data)"
    with st.expander(label, expanded=False):
        if data:
            st.markdown("**Yahoo Finance data used**")
            seen = set()
            for d in data:
                key = (d["tool"], d.get("symbol"))
                if key in seen:
                    continue
                seen.add(key)
                when = to_datetime(d.get("retrieved_at"))
                st.markdown(
                    f"- {escape(d['tool'].replace('_', ' '))}"
                    f"{' · ' + escape(d['symbol']) if d.get('symbol') else ''}"
                    f" — retrieved {fmt_age(when)}{' (stale)' if d.get('stale') else ''}"
                )
        if web:
            st.markdown("**Web & news sources**")
            for w in web[:15]:
                date = f" — {escape(str(w['page_age']))}" if w.get("page_age") else ""
                cited = " ✓ cited" if w.get("cited") else ""
                title = escape(w["title"]).replace("[", "(").replace("]", ")")
                st.markdown(f"- [{title}]({w['url']}){date}{cited}")
        if queries:
            st.markdown("**Searches:** " + "; ".join(f"“{escape(q)}”" for q in queries))
        if steps:
            st.markdown("**Steps:** " + " → ".join(escape(s) for s in steps))


def _run_turn(prompt: str, symbol: str, info: dict | None, page_context: dict | None) -> None:
    provider = config.analyst_provider()
    if provider == "gemini":
        from ai.gemini_assistant import GeminiAnalyst as Analyst  # lazy: only when the analyst is used
    else:
        from ai.assistant import Analyst

    st.session_state.chat_display.append({"role": "user", "text": prompt})
    with st.chat_message("user"):
        st.markdown(_md(prompt))

    note = build_context_note(symbol, info, page_context)
    history = st.session_state.chat_histories.setdefault(provider, [])  # formats differ per provider
    st.session_state.chat_turn_start = len(history)

    with st.chat_message("assistant"):
        status = st.status("Analyzing…", expanded=False)
        placeholder = st.empty()
        text, steps, sources, error = "", [], None, None
        for ev in Analyst().run(history, prompt, note):
            if ev.kind == "text":
                text += ev.text
                placeholder.markdown(_md(text) + "▌")
            elif ev.kind == "status":
                status.update(label=ev.text)
            elif ev.kind == "tool_done":
                steps.append(ev.text.replace("Fetching ", ""))
                status.write(("⚠️ " if ev.data.get("is_error") else "✓ ") + ev.text)
            elif ev.kind in ("error", "refusal"):
                error = ev.text
            elif ev.kind == "done":
                sources = ev.data.get("sources")
        status.update(label="Done" if not error else "Finished with issues", state="error" if error and not text else "complete")
        if error:
            text = (text + "\n\n" if text else "") + f"⚠️ {error}"
        if not text:
            text = "_No answer was produced._"
        placeholder.markdown(_md(text))
        _render_sources(sources, steps)

    st.session_state.chat_turn_start = None
    st.session_state.chat_display.append({"role": "assistant", "text": text, "sources": sources, "steps": steps})


def render_sidebar(symbol: str, info: dict | None, page_context: dict | None) -> None:
    _init_state()
    _recover_interrupted_turn()
    section = (page_context or {}).get("section") or "Summary"

    with st.sidebar:
        top = st.columns([3, 2], vertical_alignment="center")
        top[0].markdown("### 🤖 AI Analyst")
        if top[1].button("New chat", icon="➕", width="stretch", disabled=not st.session_state.chat_display):
            st.session_state.chat_histories = {}
            st.session_state.chat_display = []
            st.session_state.pending_prompt = None
            st.rerun()
        name = (info or {}).get("name") or symbol
        st.markdown(
            f'<div class="ctx-badge">Context: <b>{escape(symbol)}</b> · {escape(name[:32])} · {escape(section)}</div>',
            unsafe_allow_html=True,
        )

        provider = config.analyst_provider()
        if provider is None:
            st.info(
                "Add **ANTHROPIC_API_KEY** (Claude) or **GEMINI_API_KEY** (Google Gemini) in Streamlit secrets, "
                "a `.env` file or the environment to enable the AI analyst.",
                icon="🔑",
            )
            return
        st.caption(f"Powered by {'Claude (Anthropic)' if provider == 'anthropic' else 'Gemini (Google)'}")

        for msg in st.session_state.chat_display:
            with st.chat_message(msg["role"]):
                st.markdown(_md(msg["text"]))
                if msg["role"] == "assistant":
                    _render_sources(msg.get("sources"), msg.get("steps") or [])

        if not st.session_state.chat_display:
            st.caption("Ask about the selected company, compare it with peers, or research recent developments. "
                       "Answers separate reported data, calculations, external evidence and interpretation.")
        suggestion = st.pills("Suggested", SUGGESTED_PROMPTS.get(section, []), key=f"sugg_{section}_{len(st.session_state.chat_display)}",
                              label_visibility="collapsed")
        prompt = st.chat_input(f"Ask about {symbol}…", key="chat_input")
        prompt = prompt or suggestion or st.session_state.pending_prompt
        st.session_state.pending_prompt = None
        if prompt:
            _run_turn(prompt.strip()[:4000], symbol, info, page_context)
        st.caption("AI analysis may be wrong; verify against primary sources. Not investment advice.")
