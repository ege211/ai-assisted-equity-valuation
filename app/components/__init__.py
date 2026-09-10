"""
AI-Assisted Equity Valuation & Investment Intelligence Platform
Phase 8B — Application Components Package
File: app/components/__init__.py
"""

from .header import render_header
from .company_selector import render_company_selector
from .kpi_cards import (
    render_kpi_cards,
    format_currency,
    format_percent,
    format_multiple,
    format_count,
)
from .navigation import render_navigation
from .temporal_context import render_temporal_context, format_temporal_label
from .provenance import (
    render_source_provenance_badge,
    render_lineage_pipeline,
    render_why_this_number_expander,
    render_what_changed_table,
)

__all__ = [
    "render_header",
    "render_company_selector",
    "render_kpi_cards",
    "format_currency",
    "format_percent",
    "format_multiple",
    "format_count",
    "render_navigation",
    "render_temporal_context",
    "format_temporal_label",
    "render_source_provenance_badge",
    "render_lineage_pipeline",
    "render_why_this_number_expander",
    "render_what_changed_table",
]
