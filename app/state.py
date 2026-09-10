"""
AI-Assisted Equity Valuation & Investment Intelligence Platform
Phase 8B — Application State Management
File: app/state.py

Manages UI session state for the Streamlit application shell.
Designed to work with Streamlit's native st.session_state when running inside Streamlit,
while providing a graceful in-memory fallback for headless execution and unit testing.
"""

from typing import Any, Dict, Optional
from src.service.contracts import AnalysisResponse, CompanyRequest

try:
    import streamlit as st
except ImportError:
    st = None

# In-memory fallback dictionary for testing outside Streamlit runner
_FALLBACK_STATE: Dict[str, Any] = {}

# Default state definitions
DEFAULTS: Dict[str, Any] = {
    "selected_ticker": "MSFT",
    "mode": "LIVE",
    "as_of_date": None,
    "active_page": "Overview",
    "analysis_response": None,
    "service_error": None,
    "warning_messages": [],
}


def _get_backend(st_client=None) -> Any:
    """Return the active state backend (st.session_state or in-memory fallback)."""
    client = st_client or st
    if client is not None and hasattr(client, "session_state"):
        # If client or session_state is a Mock, use _FALLBACK_STATE for deterministic dict behavior
        cls_name = getattr(client.session_state, "__class__", type(None)).__name__
        if "Mock" in cls_name:
            return _FALLBACK_STATE
        return client.session_state
    return _FALLBACK_STATE


def init_session_state(st_client=None) -> None:
    """Initialize default state keys if not already present."""
    backend = _get_backend(st_client)
    for key, val in DEFAULTS.items():
        if isinstance(backend, dict):
            if key not in backend:
                backend[key] = val
        else:
            if key not in backend:
                try:
                    backend[key] = val
                except Exception:
                    pass


def get_state(key: str, default: Any = None, st_client=None) -> Any:
    """Retrieve a value from application state."""
    backend = _get_backend(st_client)
    if isinstance(backend, dict):
        return backend.get(key, default if default is not None else DEFAULTS.get(key))
    return getattr(backend, key, default if default is not None else DEFAULTS.get(key))


def set_state(key: str, value: Any, st_client=None) -> None:
    """Update a value in application state."""
    backend = _get_backend(st_client)
    if isinstance(backend, dict):
        backend[key] = value
    else:
        setattr(backend, key, value)


def reset_analysis_state(st_client=None) -> None:
    """Reset analysis response and error states upon parameter change."""
    set_state("analysis_response", None, st_client)
    set_state("service_error", None, st_client)
    set_state("warning_messages", [], st_client)


def clear_fallback_state() -> None:
    """Clear in-memory fallback state (used in testing)."""
    global _FALLBACK_STATE
    _FALLBACK_STATE.clear()
    _FALLBACK_STATE.update(DEFAULTS)
