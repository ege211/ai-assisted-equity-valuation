"""
AI-Assisted Equity Valuation & Investment Intelligence Platform
Phase 8G — Institutional Valuation Terminal Interface
File: app/pages/valuation.py

Renders the deterministic equity valuation view following the strict institutional hierarchy:
1. VALUATION SUMMARY (Base Fair Value, Market Price, Implied Upside/Downside, WACC, g, Scenario Range)
2. DCF ASSUMPTIONS & 5-YEAR PROJECTIONS (Discrete Free Cash Flow schedule)
3. MULTI-SCENARIO VALUATION GRID (Base, Bull, Bear)
4. INTERACTIVE ANALYST SCENARIO SANDBOX (In-memory parameter exploration)
5. 2D SENSITIVITY GRID (WACC × Terminal Growth Rate matrix heatmap)
6. RELATIVE VALUATION MULTIPLES BENCHMARK (P/E, EV/EBITDA, EV/Sales vs Sector Peers)
7. WHY THIS FAIR VALUE? (Deterministic DCF calculation pipeline expander)
8. WHY THIS WACC? (CAPM cost of capital derivation expander)
9. PROVENANCE / LINEAGE CITATION
"""

from typing import Any, Dict, List, Optional
from src.service.contracts import (
    AnalysisResponse,
    SensitivityGridDTO,
    ValuationScenarioSummary,
)
from src.service.platform_service import PlatformService
from app.components.kpi_cards import format_currency, format_percent
from app.components.temporal_context import render_temporal_context
from app.components.provenance import (
    render_why_this_number_expander,
    render_source_provenance_badge,
)

try:
    import streamlit as st
except ImportError:
    st = None


def _build_markdown_table(headers: List[str], rows: List[List[str]]) -> str:
    """Generate a clean GitHub-flavored markdown table."""
    header_line = "| " + " | ".join(headers) + " |"
    separator_line = "| " + " | ".join(["---"] * len(headers)) + " |"
    row_lines = ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join([header_line, separator_line] + row_lines)


def render_sensitivity_matrix(
    grid: SensitivityGridDTO,
    base_wacc: Optional[float] = None,
    base_g: Optional[float] = None,
    st_client: Any = None,
) -> List[Dict[str, Any]]:
    """
    Render a clean 2D WACC x Terminal Growth sensitivity table.
    
    Returns structured rows for testing/headless execution.
    """
    ctx = st_client or st
    rows = []

    wacc_vals = grid.parameter_1_values
    g_vals = grid.parameter_2_values
    matrix = grid.matrix

    effective_base_wacc = base_wacc if base_wacc is not None else (wacc_vals[len(wacc_vals) // 2] if wacc_vals else None)
    effective_base_g = base_g if base_g is not None else (g_vals[len(g_vals) // 2] if g_vals else None)

    for r_idx, w in enumerate(wacc_vals):
        row_dict: Dict[str, Any] = {"WACC": f"{w * 100:.2f}%"}
        for c_idx, g in enumerate(g_vals):
            col_key = f"g = {g * 100:.1f}%"
            val = matrix[r_idx][c_idx] if r_idx < len(matrix) and c_idx < len(matrix[r_idx]) else None
            
            is_base = (
                effective_base_wacc is not None
                and effective_base_g is not None
                and abs(w - effective_base_wacc) < 0.003
                and abs(g - effective_base_g) < 0.003
            )
            
            cell_str = format_currency(val)
            if is_base and val is not None:
                cell_str = f"★ {cell_str} (Base)"
            row_dict[col_key] = cell_str
        rows.append(row_dict)

    if ctx is not None:
        ctx.markdown("### 2D WACC × Terminal Growth Rate Sensitivity Matrix")
        ctx.caption(
            "Taxonomy: [MODEL OUTPUT] Fair Value per Share evaluated across deterministic cost of capital and perpetual growth bounds. "
            "Cells with '★ (Base)' indicate the baseline calibrated scenario. 'N/A' indicates mathematically invalid bounds (g ≥ WACC)."
        )
        ctx.dataframe(rows, use_container_width=True)

    return rows


def render_valuation_page(
    response: Optional[AnalysisResponse],
    service: Optional[PlatformService] = None,
    mode: str = "LIVE",
    as_of_date: Optional[str] = None,
    st_client: Any = None,
) -> Dict[str, Any]:
    """
    Render the institutional valuation terminal dashboard.

    Args:
        response: Optional AnalysisResponse DTO from PlatformService.
        service: Optional PlatformService instance for on-demand scenario recalculation.
        mode: Valuation mode ('LIVE' or 'HISTORICAL').
        as_of_date: Cutoff date string (if HISTORICAL).
        st_client: Optional Streamlit module or mock.

    Returns:
        Structured dictionary summarizing valuation outputs for verification.
    """
    ctx = st_client or st

    val_data: Dict[str, Any] = {}

    eff_mode = (response.request.mode if (response and response.request) else mode).upper()
    eff_as_of_date = response.request.as_of_date if (response and response.request) else as_of_date
    cutoff_str = f"{eff_as_of_date} 23:59:59" if eff_mode == "HISTORICAL" else "LIVE (LATEST)"

    if response is not None and response.valuation is not None:
        v = response.valuation
        base = v.scenarios.get("BASE")
        bull = v.scenarios.get("BULL")
        bear = v.scenarios.get("BEAR")

        val_data = {
            "status": "AVAILABLE",
            "valuation_date": v.valuation_date,
            "valuation_mode": v.valuation_mode,
            "mode": eff_mode,
            "as_of_date": eff_as_of_date,
            "information_cutoff": cutoff_str,
            "lineage": v.lineage,
            "fair_value_per_share": v.fair_value_per_share,
            "current_share_price": v.current_share_price,
            "upside_downside": v.upside_downside,
            "enterprise_value": v.enterprise_value,
            "equity_value": v.equity_value,
            "wacc": v.wacc,
            "terminal_growth": v.terminal_growth,
            "scenarios": v.scenarios,
            "base": {
                "fair_value_per_share": base.fair_value_per_share if base else v.fair_value_per_share,
                "enterprise_value": base.enterprise_value if base else v.enterprise_value,
                "equity_value": base.equity_value if base else v.equity_value,
                "wacc": base.wacc if base else v.wacc,
                "terminal_growth_rate": base.terminal_growth if base else v.terminal_growth,
            },
            "bull": {
                "fair_value_per_share": bull.fair_value_per_share if bull else None,
                "enterprise_value": bull.enterprise_value if bull else None,
                "equity_value": bull.equity_value if bull else None,
                "wacc": bull.wacc if bull else None,
                "terminal_growth_rate": bull.terminal_growth if bull else None,
            },
            "bear": {
                "fair_value_per_share": bear.fair_value_per_share if bear else None,
                "enterprise_value": bear.enterprise_value if bear else None,
                "equity_value": bear.equity_value if bear else None,
                "wacc": bear.wacc if bear else None,
                "terminal_growth_rate": bear.terminal_growth if bear else None,
            },
            "forecast_periods_count": len(v.forecast_periods),
            "sensitivities": {},
            "analyst_scenario": None,
            "valuation_lineage": v.valuation_lineage,
            "wacc_lineage": v.wacc_lineage,
            "relative_multiples": v.relative_multiples,
        }

        sens_grid = v.sensitivities.get("wacc_terminal_growth")
        val_data["sensitivity_grid"] = sens_grid
        if sens_grid:
            val_data["sensitivities"]["wacc_terminal_growth"] = sens_grid

    if ctx is not None:
        ctx.header("Deterministic Discounted Cash Flow (DCF) Valuation")
        render_temporal_context(mode=eff_mode, as_of_date=eff_as_of_date, st_client=ctx)
        ctx.caption(
            "Powered by Phase 4 Deterministic Engine | Zero Hallucinated Numbers | Pure Financial Mathematics"
        )

        if not val_data:
            if eff_mode == "HISTORICAL":
                ctx.warning(f"Valuation input unavailable as of {eff_as_of_date}. Zero look-ahead fallback enforced: no LIVE data substituted.")
                ctx.write("**Valuation Date:** `N/A`")
                ctx.write(f"**Information Cutoff:** `{cutoff_str}`")
            else:
                ctx.warning("Valuation data is currently unavailable for this company.")
            return {
                "status": "UNAVAILABLE",
                "mode": eff_mode,
                "as_of_date": eff_as_of_date,
                "information_cutoff": cutoff_str,
                "fair_value_per_share": None,
            }

        ctx.write(f"**Valuation Date:** `{val_data['valuation_date']}` | **Information Cutoff:** `{cutoff_str}`")

        # ======================================================================
        # 1. VALUATION SUMMARY
        # ======================================================================
        ctx.markdown("### 1. Valuation Executive Summary `[MODEL OUTPUT]`")
        s_cols = ctx.columns(5) if hasattr(ctx, "columns") else (ctx, ctx, ctx, ctx, ctx)
        if isinstance(s_cols, (list, tuple)) and len(s_cols) == 5:
            fv = val_data["base"]["fair_value_per_share"]
            mp = val_data.get("current_share_price")
            up = val_data.get("upside_downside")
            wacc_val = val_data["base"]["wacc"]
            g_val = val_data["base"]["terminal_growth_rate"]

            s_cols[0].metric(
                "DCF Base Fair Value",
                format_currency(fv),
                help="[MODEL OUTPUT] Base-case DCF intrinsic value per share.",
            )
            s_cols[1].metric(
                "Market Price",
                format_currency(mp),
                help="[MARKET PRICE] Observed trading price at valuation date.",
            )
            delta_str = f"{up * 100:+.1f}%" if up is not None else None
            s_cols[2].metric(
                "Implied Upside / (Downside)",
                delta_str or "N/A",
                delta=delta_str,
                help="[MODEL OUTPUT] Relative difference between DCF fair value and market price.",
            )
            s_cols[3].metric(
                "Cost of Capital (WACC)",
                format_percent(wacc_val),
                help="[ANALYST ASSUMPTION] Calibrated discount rate.",
            )
            s_cols[4].metric(
                "Terminal Growth (g)",
                format_percent(g_val),
                help="[ANALYST ASSUMPTION] Perpetual growth rate.",
            )

        bear_fv = format_currency(val_data["bear"]["fair_value_per_share"])
        base_fv = format_currency(val_data["base"]["fair_value_per_share"])
        bull_fv = format_currency(val_data["bull"]["fair_value_per_share"])
        ctx.caption(f"**Scenario Valuation Range:** Bear: `{bear_fv}` | Base: `{base_fv}` | Bull: `{bull_fv}`")

        ctx.markdown("---")

        # ======================================================================
        # 2. DCF ASSUMPTIONS & 5-YEAR PROJECTIONS
        # ======================================================================
        ctx.markdown("### 2. Discrete 5-Year Free Cash Flow Projections `[MODEL OUTPUT]`")
        ctx.caption("Discrete deterministic forecast schedule: Revenue $\\to$ NOPAT $\\to$ Reinvestment $\\to$ FCFF.")
        if response and response.valuation and response.valuation.forecast_periods:
            table_rows = []
            for p in response.valuation.forecast_periods:
                table_rows.append({
                    "Forecast Year": f"Year {p.forecast_year_index} ({p.fiscal_year})",
                    "Revenue ($M)": round(p.revenue / 1e6, 1),
                    "EBIT ($M)": round(p.ebit / 1e6, 1),
                    "NOPAT ($M)": round(p.nopat / 1e6, 1),
                    "Capex ($M)": round(p.capex / 1e6, 1),
                    "FCFF ($M)": round(p.fcff / 1e6, 1),
                    "Discount Factor": round(p.discount_factor, 4),
                    "PV of FCFF ($M)": round(p.pv_fcff / 1e6, 1),
                })
            ctx.dataframe(table_rows, use_container_width=True)

        ctx.markdown("---")

        # ======================================================================
        # 3. BASE / BULL / BEAR SCENARIO CARDS
        # ======================================================================
        ctx.markdown("### 3. Multi-Scenario Intrinsic Valuation Summary")
        ctx.markdown(
            "> **Taxonomy:** `[MODEL OUTPUT]` DCF Fair Values are computed deterministically from normalized LTM statements and explicit forecast parameters."
        )

        vcols = ctx.columns(3)
        c_bear, c_base, c_bull = vcols if (isinstance(vcols, (list, tuple)) and len(vcols) == 3) else (ctx, ctx, ctx)
        with c_bear:
            ctx.subheader("Bear Scenario")
            ctx.metric("Fair Value / Share", format_currency(val_data["bear"]["fair_value_per_share"]))
            ctx.write(f"**Enterprise Value:** {format_currency(val_data['bear']['enterprise_value'] / 1e9, decimals=1)}B" if val_data['bear']['enterprise_value'] else "**Enterprise Value:** N/A")
            ctx.write(f"**WACC:** {format_percent(val_data['bear']['wacc'])}")
            ctx.write(f"**Terminal Growth:** {format_percent(val_data['bear']['terminal_growth_rate'])}")

        with c_base:
            ctx.subheader("Base Scenario (Official)")
            ctx.metric("Fair Value / Share", format_currency(val_data["base"]["fair_value_per_share"]))
            ctx.write(f"**Enterprise Value:** {format_currency(val_data['base']['enterprise_value'] / 1e9, decimals=1)}B" if val_data['base']['enterprise_value'] else "**Enterprise Value:** N/A")
            ctx.write(f"**WACC:** {format_percent(val_data['base']['wacc'])}")
            ctx.write(f"**Terminal Growth:** {format_percent(val_data['base']['terminal_growth_rate'])}")

        with c_bull:
            ctx.subheader("Bull Scenario")
            ctx.metric("Fair Value / Share", format_currency(val_data["bull"]["fair_value_per_share"]))
            ctx.write(f"**Enterprise Value:** {format_currency(val_data['bull']['enterprise_value'] / 1e9, decimals=1)}B" if val_data['bull']['enterprise_value'] else "**Enterprise Value:** N/A")
            ctx.write(f"**WACC:** {format_percent(val_data['bull']['wacc'])}")
            ctx.write(f"**Terminal Growth:** {format_percent(val_data['bull']['terminal_growth_rate'])}")

        ctx.markdown("---")

        # ======================================================================
        # 4. INTERACTIVE ANALYST DCF SCENARIO CONTROLS
        # ======================================================================
        ctx.markdown("### 4. Interactive Analyst Scenario Sandbox")
        ctx.markdown(
            "> **Governance Rule:** Scenario exploration runs strictly in-memory. "
            "Adjusting parameters does **NOT** overwrite or mutate the audited Base Model in the database."
        )

        base_wacc_pct = float(round(val_data["base"]["wacc"] * 100, 2)) if val_data["base"]["wacc"] else 9.5
        base_g_pct = float(round(val_data["base"]["terminal_growth_rate"] * 100, 2)) if val_data["base"]["terminal_growth_rate"] else 2.5
        base_margin_pct = 40.0

        cols_raw = ctx.columns(3) if hasattr(ctx, "columns") else (ctx, ctx, ctx)
        if isinstance(cols_raw, (list, tuple)) and len(cols_raw) >= 3:
            s_col1, s_col2, s_col3 = cols_raw[0], cols_raw[1], cols_raw[2]
        else:
            s_col1, s_col2, s_col3 = ctx, ctx, ctx

        with s_col1:
            analyst_wacc = ctx.slider(
                "Cost of Capital (WACC) % [ANALYST ASSUMPTION]",
                min_value=5.0,
                max_value=16.0,
                value=base_wacc_pct,
                step=0.25,
                help="Calibrate discount rate. Higher WACC lowers intrinsic valuation.",
            )
        with s_col2:
            analyst_g = ctx.slider(
                "Terminal Growth Rate (g) % [ANALYST ASSUMPTION]",
                min_value=0.5,
                max_value=4.5,
                value=base_g_pct,
                step=0.1,
                help="Perpetual growth rate for Gordon Growth terminal value. Must be strictly less than WACC.",
            )
        with s_col3:
            analyst_margin = ctx.slider(
                "Target Operating Margin % [ANALYST ASSUMPTION]",
                min_value=10.0,
                max_value=60.0,
                value=base_margin_pct,
                step=1.0,
                help="Target normalized EBIT margin across the 5-year discrete projection horizon.",
            )

        svc = service or PlatformService()
        analyst_wacc_dec = analyst_wacc / 100.0
        analyst_g_dec = analyst_g / 100.0
        analyst_margin_dec = analyst_margin / 100.0

        try:
            scenario_res = svc.calculate_analyst_scenario(
                ticker=response.profile.ticker,
                as_of_date=eff_as_of_date,
                mode=eff_mode,
                wacc_override=analyst_wacc_dec,
                terminal_growth_override=analyst_g_dec,
                target_margin_override=analyst_margin_dec,
            )
            val_data["analyst_scenario"] = scenario_res

            ctx.markdown("#### Scenario Comparison: Base Model vs Analyst Sandbox")
            delta_val = scenario_res.fair_value_per_share - val_data["base"]["fair_value_per_share"]
            delta_pct = (delta_val / val_data["base"]["fair_value_per_share"]) * 100.0 if val_data["base"]["fair_value_per_share"] else 0.0

            comp_cols = ctx.columns(4) if hasattr(ctx, "columns") else (ctx, ctx, ctx, ctx)
            comp_cols[0].metric(
                label="Base Model Fair Value",
                value=format_currency(val_data["base"]["fair_value_per_share"]),
                help="[MODEL OUTPUT] Audited baseline DCF result.",
            )
            comp_cols[1].metric(
                label="Analyst Scenario Fair Value",
                value=format_currency(scenario_res.fair_value_per_share),
                delta=f"{delta_val:+.2f} ({delta_pct:+.1f}%)",
                help="[MODEL OUTPUT] On-demand scenario evaluated under analyst assumptions.",
            )
            comp_cols[2].metric(
                label="Analyst Implied EV",
                value=f"{format_currency(scenario_res.enterprise_value / 1e9, decimals=1)}B",
                help="[MODEL OUTPUT] Enterprise value under analyst scenario.",
            )
            comp_cols[3].metric(
                label="Analyst WACC / g",
                value=f"{format_percent(scenario_res.wacc)} / {format_percent(scenario_res.terminal_growth)}",
                help="[ANALYST ASSUMPTION] Explicit parameter inputs.",
            )

        except Exception as e:
            ctx.info(f"Analyst scenario calculation status: {e}")

        ctx.markdown("---")

        # ======================================================================
        # 5. 2D SENSITIVITY GRID HEATMAP
        # ======================================================================
        if "wacc_terminal_growth" in val_data.get("sensitivities", {}):
            render_sensitivity_matrix(
                grid=val_data["sensitivities"]["wacc_terminal_growth"],
                base_wacc=val_data["base"]["wacc"],
                base_g=val_data["base"]["terminal_growth_rate"],
                st_client=ctx,
            )

        ctx.markdown("---")

        # ======================================================================
        # 6. RELATIVE VALUATION MULTIPLES BENCHMARK
        # ======================================================================
        ctx.markdown("### 5. Relative Valuation Multiples Benchmark `[MODEL OUTPUT]`")
        ctx.caption("Market-based multiple calibration benchmarked against sector peers.")

        if response and response.valuation and response.valuation.relative_multiples:
            rel_headers = [
                "Multiple Name",
                "Company Multiple",
                "Peer Median",
                "Implied Fair Value",
                "Benchmark Source",
            ]
            rel_rows = []
            for rm in response.valuation.relative_multiples:
                comp_mult = f"{rm.company_multiple:.1f}x" if rm.company_multiple is not None else "N/A"
                peer_mult = f"{rm.peer_median_multiple:.1f}x" if rm.peer_median_multiple is not None else "N/A"
                implied_fv = format_currency(rm.implied_fair_value_per_share) if rm.implied_fair_value_per_share is not None else "N/A"
                rel_rows.append([
                    f"**{rm.multiple_name}**",
                    comp_mult,
                    peer_mult,
                    implied_fv,
                    rm.benchmark_source or "Audited Sector Comps",
                ])
            ctx.markdown(_build_markdown_table(rel_headers, rel_rows))
        else:
            ctx.info("Relative valuation multiples are currently unavailable for this company.")

        ctx.markdown("---")

        # ======================================================================
        # 7. AUDITABLE PROVENANCE & DATA LINEAGE DRILLDOWN
        # ======================================================================
        ctx.markdown("### 6. Auditable Provenance & Data Lineage `[CALCULATION PIPELINE]`")
        ctx.caption("Exhaustive mathematical verification: trace final valuation outputs back to SEC filings.")
        render_why_this_number_expander(
            "Why this Fair Value? (Deterministic DCF Lineage & Derivation)",
            val_data.get("valuation_lineage"),
            st_client=ctx,
        )
        render_why_this_number_expander(
            "Why this WACC? (Capital Asset Pricing Model & Capital Structure Lineage)",
            val_data.get("wacc_lineage"),
            st_client=ctx,
        )

        ctx.caption(f"Lineage Provenance: `{val_data.get('lineage', 'N/A')}`")

    return val_data
