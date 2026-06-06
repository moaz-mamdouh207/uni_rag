"""
shared/tracing.py — Langfuse v4 (OTEL-based) wrapper.

Usage:
    from shared.tracing import observe, observe_generation, flush_traces

    # Wrapping a block of work:
    with observe("agent_turn", input={...}, metadata={...}) as span:
        span.update(output={...})

        with observe("tool/retrieve", input={...}) as child:
            child.update(output={...})

        with observe_generation("llm_call", model="gemini-...") as gen:
            gen.update(output={...}, usage={...})

    # At app shutdown:
    flush_traces()
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Generator

logger = logging.getLogger(__name__)

from pydantic import BaseModel


class LangfuseSettings(BaseModel):
    enabled:    bool = True
    public_key: str  = ""
    secret_key: str  = ""
    host:       str  = "https://cloud.langfuse.com"
    
# ---------------------------------------------------------------------------
# Lazy client initialisation
# ---------------------------------------------------------------------------

_initialised = False
_enabled = False


def _get_client():
    global _initialised, _enabled

    if not _initialised:
        _initialised = True
        try:
            from core.config import settings
            cfg = settings.langfuse
            _enabled = cfg.enabled and bool(cfg.public_key) and bool(cfg.secret_key)

            if _enabled:
                import os
                # v4 SDK reads credentials from env vars
                os.environ.setdefault("LANGFUSE_PUBLIC_KEY",  cfg.public_key)
                os.environ.setdefault("LANGFUSE_SECRET_KEY",  cfg.secret_key)
                os.environ.setdefault("LANGFUSE_BASE_URL",    cfg.host)

                from langfuse import get_client
                client = get_client()
                logger.info("Langfuse tracing enabled — host=%s", cfg.host)
                return client
        except Exception as exc:
            logger.warning("Langfuse init failed, tracing disabled: %s", exc)
            _enabled = False

    if _enabled:
        try:
            from langfuse import get_client
            return get_client()
        except Exception:
            pass

    return None


# ---------------------------------------------------------------------------
# _NoopSpan — returned when tracing is disabled
# ---------------------------------------------------------------------------

class _NoopSpan:
    def update(self, **kwargs) -> None:
        pass

    def set_attribute(self, key: str, value: Any) -> None:
        pass


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

@contextmanager
def observe(
    name: str,
    as_type: str = "span",
    input: dict | None = None,
    metadata: dict | None = None,
) -> Generator[Any, None, None]:
    """
    Context manager that creates a Langfuse span (or trace root).
    Nesting is automatic via OTEL context propagation.

    with observe("tool/retrieve", input={"query": "..."}) as span:
        ...
        span.update(output={"results": 3})
    """
    client = _get_client()
    if client is None:
        yield _NoopSpan()
        return

    kwargs: dict = {"name": name, "as_type": as_type}
    if input is not None:
        kwargs["input"] = input
    if metadata is not None:
        kwargs["metadata"] = metadata

    try:
        with client.start_as_current_observation(**kwargs) as span:
            yield span
    except Exception as exc:
        logger.debug("observe(%s) failed: %s", name, exc)
        yield _NoopSpan()


@contextmanager
def observe_generation(
    name: str,
    model: str | None = None,
    input: dict | None = None,
    metadata: dict | None = None,
) -> Generator[Any, None, None]:
    """
    Context manager that creates a Langfuse generation span.
    Langfuse renders these specially in the UI with token counts and cost.

    with observe_generation("llm_call", model="gemini-2.0-flash") as gen:
        response = await llm.ainvoke(messages)
        gen.update(output={"tool_calls": [...]}, usage={"input": 100, "output": 50})
    """
    client = _get_client()
    if client is None:
        yield _NoopSpan()
        return

    kwargs: dict = {"name": name, "as_type": "generation"}
    if model is not None:
        kwargs["model"] = model
    if input is not None:
        kwargs["input"] = input
    if metadata is not None:
        kwargs["metadata"] = metadata

    try:
        with client.start_as_current_observation(**kwargs) as gen:
            yield gen
    except Exception as exc:
        logger.debug("observe_generation(%s) failed: %s", name, exc)
        yield _NoopSpan()


def set_trace_attributes(**kwargs) -> None:
    """
    Set attributes on the current root trace (user_id, session_id, etc.).
    Safe to call even when tracing is disabled.

    set_trace_attributes(
        user_id="user-123",
        session_id="conv-456",
        metadata={"course_id": "..."},
    )
    """
    client = _get_client()
    if client is None:
        return
    try:
        from langfuse import propagate_attributes
        propagate_attributes(**kwargs)
    except Exception as exc:
        logger.debug("set_trace_attributes failed: %s", exc)


def flush_traces() -> None:
    """Flush all buffered Langfuse events. Call at app shutdown."""
    client = _get_client()
    if client is None:
        return
    try:
        client.flush()
        logger.debug("Langfuse flush complete")
    except Exception as exc:
        logger.debug("Langfuse flush failed: %s", exc)


# ---------------------------------------------------------------------------
# Truncation helper used by loop + tools
# ---------------------------------------------------------------------------

def safe_truncate(data: dict, max_str_len: int = 300) -> dict:
    """Truncate long string values so Langfuse payloads stay readable."""
    out = {}
    for k, v in data.items():
        if isinstance(v, str) and len(v) > max_str_len:
            out[k] = v[:max_str_len] + f"... [{len(v)} chars total]"
        elif isinstance(v, list):
            out[k] = v[:10]
        else:
            out[k] = v
    return out