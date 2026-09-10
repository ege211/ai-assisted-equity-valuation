"""
Platform Service Layer.

Acts as a thin, decoupled application facade orchestrating the audited domain engines
(valuation, normalization, filing intelligence, research) for future UI and client applications.

CRITICAL ARCHITECTURAL CONSTRAINTS:
1. Thin orchestrator: Does NOT compute DCF, WACC, financial ratios, or LLM extraction independently.
2. Domain engine isolation: Delegates all calculations to existing domain modules.
3. Strict Point-in-Time compliance: Propagates temporal constraints to underlying engines.
4. Clean error handling: Translates raw database/engine failures into strongly typed service exceptions.
"""
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional

from src.data.db import DatabaseManager, DEFAULT_DB_PATH
from src.service.contracts import (
    AnalysisResponse,
    ChangeSignalDTO,
    CompanyProfile,
    CompanyRequest,
    FilingIntelligenceResponse,
    FilingSignal,
    ForecastPeriodDTO,
    InvalidTickerError,
    MissingCompanyError,
    MissingPITDateError,
    RelativeValuationSummary,
    ResearchDisclosure,
    SensitivityGridDTO,
    UnsupportedModeError,
    ValuationRequest,
    ValuationResponse,
    ValuationScenarioSummary,
    ValuationUnavailableError,
    FinancialPeriodDTO,
    FinancialFeatureDTO,
    FundamentalsResponse,
    FilingSectionDTO,
    FilingSummaryDTO,
    FilingExplorerResponse,
    ValuationBridgeRecordDTO,
    SourceProvenanceDTO,
    LineageStepDTO,
    DataLineageDTO,
    QualitativeEvidenceLineageDTO,
    ValuationBridgeLineageDTO,
    FundamentalChangeDTO,
    WhatChangedResponse,
)
from src.valuation.engine import ValuationEngine
from src.valuation.models import ValuationError

logger = logging.getLogger(__name__)


def _format_pit_cutoff(as_of_date: Optional[str]) -> Optional[str]:
    """Ensure point-in-time timestamp parameter has correct SQL format."""
    if not as_of_date:
        return None
    s = str(as_of_date).strip()
    if " " in s or "T" in s:
        return s
    return f"{s} 23:59:59"


class PlatformService:
    """Production application facade mediating between UI and core domain engines."""

    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        valuation_engine: Optional[ValuationEngine] = None,
        db_path: str = DEFAULT_DB_PATH,
    ) -> None:
        self.db = db_manager or DatabaseManager(db_path=db_path)
        self.valuation_engine = valuation_engine or ValuationEngine(db_manager=self.db)
        self._research_disclosure = ResearchDisclosure()

    # ==========================================================================
    # 1. COMPANY PROFILING
    # ==========================================================================

    def get_company_profile(self, ticker: str) -> CompanyProfile:
        """
        Retrieve enterprise metadata and filing coverage details.
        
        Raises:
            InvalidTickerError: If ticker is blank.
            MissingCompanyError: If company is not found in the database.
        """
        clean_ticker = str(ticker).strip().upper() if ticker else ""
        if not clean_ticker:
            raise InvalidTickerError("Ticker symbol cannot be empty.")

        with self.db.get_connection() as con:
            comp_row = con.execute(
                """
                SELECT company_id, ticker, cik, name, sector, fiscal_year_end_month
                FROM companies
                WHERE ticker = ?
                """,
                [clean_ticker],
            ).fetchone()

            if not comp_row:
                raise MissingCompanyError(f"Company with ticker '{clean_ticker}' was not found in universe.")

            cid, tkr, cik, name, sector, fye_month = comp_row

            # Query filing coverage metrics
            coverage_row = con.execute(
                """
                SELECT COUNT(*), MAX(filing_date)::VARCHAR
                FROM filings
                WHERE ticker = ?
                """,
                [clean_ticker],
            ).fetchone()

            filing_count = coverage_row[0] if coverage_row else 0
            latest_fdate = coverage_row[1] if coverage_row else None

        return CompanyProfile(
            ticker=tkr,
            company_name=name,
            cik=cik,
            sector=sector,
            fiscal_year_end_month=fye_month,
            latest_filing_date=latest_fdate,
            covered_filings_count=filing_count,
        )

    def list_covered_companies(self) -> List[CompanyProfile]:
        """List metadata profiles for all companies registered in the universe."""
        with self.db.get_connection() as con:
            rows = con.execute(
                """
                SELECT c.ticker, c.name, c.cik, c.sector, c.fiscal_year_end_month,
                       MAX(f.filing_date)::VARCHAR, COUNT(f.accession_number)
                FROM companies c
                LEFT JOIN filings f ON c.ticker = f.ticker
                GROUP BY c.ticker, c.name, c.cik, c.sector, c.fiscal_year_end_month
                ORDER BY c.ticker ASC
                """
            ).fetchall()

        return [
            CompanyProfile(
                ticker=r[0],
                company_name=r[1],
                cik=r[2],
                sector=r[3],
                fiscal_year_end_month=r[4],
                latest_filing_date=r[5],
                covered_filings_count=r[6],
            )
            for r in rows
        ]

    # ==========================================================================
    # 2. DETERMINISTIC VALUATION
    # ==========================================================================

    def get_valuation(self, request: ValuationRequest) -> ValuationResponse:
        """
        Execute deterministic valuation through the ValuationEngine without computing math in the service.
        
        Raises:
            ValuationUnavailableError: If required point-in-time inputs or shares are missing.
        """
        # Ensure company exists first
        self.get_company_profile(request.ticker)

        val_date = request.as_of_date or "2024-12-31"

        try:
            val_pack = self.valuation_engine.value_company(
                ticker=request.ticker,
                valuation_date=val_date,
                valuation_mode=request.mode,
                persist=request.persist,
            )
        except ValuationError as e:
            raise ValuationUnavailableError(
                f"Deterministic valuation failed for {request.ticker} as of {val_date} (mode: {request.mode}): {e}"
            ) from e
        except Exception as e:
            raise ValuationUnavailableError(
                f"Unexpected valuation execution failure for {request.ticker}: {e}"
            ) from e

        base_res = val_pack["scenarios"].base
        bull_res = val_pack["scenarios"].bull
        bear_res = val_pack["scenarios"].bear

        # Map forecast periods
        periods_dto = [
            ForecastPeriodDTO(
                forecast_year_index=fp.forecast_year_index,
                fiscal_year=fp.fiscal_year,
                revenue=fp.revenue,
                revenue_growth=fp.revenue_growth,
                ebit_margin=fp.ebit_margin,
                ebit=fp.ebit,
                tax_rate=fp.tax_rate,
                tax_expense=fp.tax_expense,
                nopat=fp.nopat,
                da=fp.da,
                capex=fp.capex,
                delta_nwc=fp.delta_nwc,
                fcff=fp.fcff,
                discount_factor=fp.discount_factor,
                pv_fcff=fp.pv_fcff,
            )
            for fp in base_res.forecast_periods
        ]

        # Map scenario summaries
        scenarios_dto = {
            "BASE": ValuationScenarioSummary(
                scenario_name="BASE",
                fair_value_per_share=base_res.fair_value_per_share,
                enterprise_value=base_res.enterprise_value,
                equity_value=base_res.equity_value,
                wacc=base_res.wacc,
                terminal_growth=base_res.terminal_growth,
                upside_downside=base_res.upside_downside,
            ),
            "BULL": ValuationScenarioSummary(
                scenario_name="BULL",
                fair_value_per_share=bull_res.fair_value_per_share,
                enterprise_value=bull_res.enterprise_value,
                equity_value=bull_res.equity_value,
                wacc=bull_res.wacc,
                terminal_growth=bull_res.terminal_growth,
                upside_downside=bull_res.upside_downside,
            ),
            "BEAR": ValuationScenarioSummary(
                scenario_name="BEAR",
                fair_value_per_share=bear_res.fair_value_per_share,
                enterprise_value=bear_res.enterprise_value,
                equity_value=bear_res.equity_value,
                wacc=bear_res.wacc,
                terminal_growth=bear_res.terminal_growth,
                upside_downside=bear_res.upside_downside,
            ),
        }

        # Map sensitivity grids
        sens_dto = {}
        for k, grid in val_pack.get("sensitivities", {}).items():
            sens_dto[k] = SensitivityGridDTO(
                parameter_1_name=grid.parameter_1_name,
                parameter_1_values=grid.parameter_1_values,
                parameter_2_name=grid.parameter_2_name,
                parameter_2_values=grid.parameter_2_values,
                matrix=grid.matrix,
            )

        # Map relative multiples
        rel_dto = [
            RelativeValuationSummary(
                multiple_name=r.multiple_name,
                company_multiple=r.company_multiple,
                peer_median_multiple=r.peer_median_multiple,
                implied_equity_value=r.implied_equity_value,
                implied_fair_value_per_share=r.implied_fair_value_per_share,
                benchmark_source=r.benchmark_source,
            )
            for r in val_pack.get("relative_valuation", [])
        ]

        # Build Source Provenance and Lineage DTOs
        prov = self.get_provenance(
            ticker=base_res.ticker,
            as_of_date=base_res.data_as_of_date,
            mode=base_res.valuation_mode,
        )
        val_lineage = self._build_valuation_lineage_from_data(
            ticker=base_res.ticker,
            as_of_date=base_res.data_as_of_date,
            mode=base_res.valuation_mode,
            fair_value_per_share=base_res.fair_value_per_share,
            enterprise_value=base_res.enterprise_value,
            equity_value=base_res.equity_value,
            wacc=base_res.wacc,
            terminal_growth=base_res.terminal_growth,
            cost_of_equity=base_res.cost_of_equity,
            cost_of_debt=base_res.cost_of_debt,
            risk_free_rate=base_res.risk_free_rate,
            beta=base_res.beta,
            net_debt=base_res.net_debt,
            cash=base_res.cash,
            total_debt=base_res.total_debt,
            diluted_shares=base_res.diluted_shares,
            revenue_growth_summary=base_res.revenue_growth_summary,
            ebit_margin_summary=base_res.ebit_margin_summary,
            forecast_periods=periods_dto,
            prov=prov,
        )
        wacc_lineage = self._build_wacc_lineage_from_data(
            ticker=base_res.ticker,
            wacc=base_res.wacc,
            cost_of_equity=base_res.cost_of_equity,
            cost_of_debt=base_res.cost_of_debt,
            risk_free_rate=base_res.risk_free_rate,
            beta=base_res.beta,
            equity_risk_premium=base_res.erp,
            equity_value=base_res.equity_value,
            total_debt=base_res.total_debt,
            enterprise_value=base_res.enterprise_value,
            prov=prov,
        )

        return ValuationResponse(
            ticker=base_res.ticker,
            company_id=base_res.company_id,
            valuation_date=base_res.valuation_date,
            as_of_date=base_res.data_as_of_date,
            valuation_mode=base_res.valuation_mode,
            current_share_price=base_res.current_share_price,
            fair_value_per_share=base_res.fair_value_per_share,
            enterprise_value=base_res.enterprise_value,
            equity_value=base_res.equity_value,
            total_debt=base_res.total_debt,
            cash=base_res.cash,
            net_debt=base_res.net_debt,
            diluted_shares=base_res.diluted_shares,
            upside_downside=base_res.upside_downside,
            wacc=base_res.wacc,
            terminal_growth=base_res.terminal_growth,
            cost_of_equity=base_res.cost_of_equity,
            cost_of_debt=base_res.cost_of_debt,
            risk_free_rate=base_res.risk_free_rate,
            beta=base_res.beta,
            equity_risk_premium=base_res.erp,
            revenue_growth_summary=base_res.revenue_growth_summary,
            ebit_margin_summary=base_res.ebit_margin_summary,
            forecast_periods=periods_dto,
            scenarios=scenarios_dto,
            sensitivities=sens_dto,
            relative_multiples=rel_dto,
            lineage=base_res.lineage,
            data_sources=base_res.data_sources,
            assumption_sources=base_res.assumption_sources,
            calculation_status=base_res.calculation_status,
            status_reason=base_res.status_reason,
            valuation_lineage=val_lineage,
            wacc_lineage=wacc_lineage,
        )

    # ==========================================================================
    # 3. FILING INTELLIGENCE & EVIDENCE
    # ==========================================================================

    def get_filing_intelligence(
        self,
        ticker: str,
        as_of_date: Optional[str] = None,
        mode: str = "LIVE",
        include_rejected: bool = False,
    ) -> FilingIntelligenceResponse:
        """
        Query verified qualitative claims and change signals without re-running LLMs.
        
        Raises:
            MissingCompanyError: If company does not exist.
            MissingPITDateError: If mode is HISTORICAL and as_of_date is missing.
        """
        clean_ticker = str(ticker).strip().upper() if ticker else ""
        if not clean_ticker:
            raise InvalidTickerError("Ticker symbol cannot be empty.")

        clean_mode = mode.strip().upper() if mode else "LIVE"
        if clean_mode not in ("LIVE", "HISTORICAL"):
            raise UnsupportedModeError(f"Unsupported mode '{mode}'. Must be 'LIVE' or 'HISTORICAL'.")

        if clean_mode == "HISTORICAL" and not as_of_date:
            raise MissingPITDateError("Historical filing intelligence requires an explicit as_of_date.")

        # Ensure company exists
        self.get_company_profile(clean_ticker)

        pit_cutoff = as_of_date if clean_mode == "HISTORICAL" else None

        # 1. Retrieve validated claims
        raw_validated = self.db.query_filing_extractions(
            ticker=clean_ticker,
            validation_status="VALIDATED",
            as_of_date=pit_cutoff,
        )

        raw_rejected = []
        if include_rejected:
            raw_rejected = self.db.query_filing_extractions(
                ticker=clean_ticker,
                validation_status="REJECTED",
                as_of_date=pit_cutoff,
            )

        all_raw = raw_validated + raw_rejected

        signals: List[FilingSignal] = [
            FilingSignal(
                signal_id=r["extraction_id"],
                category=r["category"],
                claim=r["claim"],
                evidence_quote=r["evidence_quote"],
                evidence_location=r["evidence_location"],
                source_identifier=r["source_identifier"],
                direction=r["direction"],
                severity=r["severity"],
                confidence=float(r["confidence"]),
                materiality=r["materiality"],
                validation_status=r["validation_status"],
                validation_reason=r.get("validation_reason"),
                form=r.get("form", ""),
                filing_date=r.get("filing_date", ""),
                acceptance_datetime=r.get("acceptance_datetime"),
                section_name=r.get("section_name", ""),
                accession_number=r.get("accession_number", ""),
            )
            for r in all_raw
        ]

        # 2. Retrieve change signals (enforcing PIT cutoff in HISTORICAL mode)
        with self.db.get_connection() as con:
            if pit_cutoff:
                change_rows = con.execute(
                    """
                    SELECT s.signal_id, s.ticker, s.category, s.change_type, s.current_claim,
                           s.previous_claim, s.direction_shift, s.severity_shift, s.materiality,
                           s.summary, s.current_accession, s.previous_accession,
                           f_cur.filing_date::VARCHAR, f_prev.filing_date::VARCHAR
                    FROM filing_change_signals s
                    JOIN filings f ON s.current_accession = f.accession_number
                    LEFT JOIN filings f_cur ON s.current_accession = f_cur.accession_number
                    LEFT JOIN filings f_prev ON s.previous_accession = f_prev.accession_number
                    WHERE s.ticker = ? 
                      AND f.acceptance_datetime <= ?::TIMESTAMPTZ
                      AND (s.previous_accession IS NULL OR f_prev.acceptance_datetime IS NULL OR f_prev.acceptance_datetime <= ?::TIMESTAMPTZ)
                    ORDER BY s.category ASC, s.change_type ASC
                    """,
                    [clean_ticker, f"{pit_cutoff} 23:59:59", f"{pit_cutoff} 23:59:59"],
                ).fetchall()
            else:
                change_rows = con.execute(
                    """
                    SELECT s.signal_id, s.ticker, s.category, s.change_type, s.current_claim,
                           s.previous_claim, s.direction_shift, s.severity_shift, s.materiality,
                           s.summary, s.current_accession, s.previous_accession,
                           f_cur.filing_date::VARCHAR, f_prev.filing_date::VARCHAR
                    FROM filing_change_signals s
                    LEFT JOIN filings f_cur ON s.current_accession = f_cur.accession_number
                    LEFT JOIN filings f_prev ON s.previous_accession = f_prev.accession_number
                    WHERE s.ticker = ?
                    ORDER BY s.category ASC, s.change_type ASC
                    """,
                    [clean_ticker],
                ).fetchall()

            # 2b. Retrieve existing valuation bridge linkage if available
            bridge_sql = """
                SELECT comparison_id, ticker, valuation_date::VARCHAR, primary_signal_category,
                       key_assumption_adjusted, adjustment_magnitude, evidence_citation,
                       baseline_fair_value, enhanced_fair_value, fair_value_pct_change
                FROM valuation_comparison_results
                WHERE ticker = ?
            """
            b_params: List[Any] = [clean_ticker]
            if pit_cutoff:
                bridge_sql += " AND valuation_date <= ?::DATE"
                b_params.append(pit_cutoff)
            bridge_sql += " ORDER BY valuation_date DESC LIMIT 1"
            b_row = con.execute(bridge_sql, b_params).fetchone()
            bridge_record = (
                ValuationBridgeRecordDTO(
                    comparison_id=str(b_row[0]),
                    ticker=str(b_row[1]),
                    valuation_date=str(b_row[2]),
                    primary_signal_category=str(b_row[3]),
                    key_assumption_adjusted=str(b_row[4]),
                    adjustment_magnitude=float(b_row[5]),
                    evidence_citation=str(b_row[6]),
                    baseline_fair_value=float(b_row[7]),
                    enhanced_fair_value=float(b_row[8]),
                    fair_value_pct_change=float(b_row[9]),
                )
                if b_row and len(b_row) >= 10
                else None
            )

        change_signals: List[ChangeSignalDTO] = [
            ChangeSignalDTO(
                signal_id=row[0],
                ticker=row[1],
                category=row[2],
                change_type=row[3],
                current_claim=row[4],
                previous_claim=row[5],
                direction_shift=row[6],
                severity_shift=row[7],
                materiality=row[8],
                summary=row[9],
                current_accession=row[10],
                previous_accession=row[11],
                current_filing_date=row[12] if len(row) > 12 else None,
                previous_filing_date=row[13] if len(row) > 13 else None,
            )
            for row in change_rows
        ]

        # 3. Compile covered accession numbers
        covered_accs = sorted(list(set(s.accession_number for s in signals if s.accession_number)))

        validated_count = len(raw_validated)
        rejected_count = len(raw_rejected)
        total_count = len(all_raw)

        if total_count > 0:
            pct_val = (validated_count / total_count) * 100.0
            evidence_status = f"{validated_count}/{total_count} claims ({pct_val:.1f}%) validated with verbatim filing quotes."
        else:
            evidence_status = "No qualitative filing disclosures recorded for this period."

        return FilingIntelligenceResponse(
            ticker=clean_ticker,
            as_of_date=as_of_date,
            mode=clean_mode,
            total_claims_retrieved=total_count,
            validated_claims_count=validated_count,
            rejected_claims_count=rejected_count,
            signals=signals,
            change_signals=change_signals,
            covered_accessions=covered_accs,
            evidence_status_summary=evidence_status,
            valuation_bridge=bridge_record,
        )

    # ==========================================================================
    # 4. RESEARCH & EMPIRICAL DISCLOSURE
    # ==========================================================================

    def get_research_disclosure(self) -> ResearchDisclosure:
        """Return the frozen Phase 7 empirical findings and academic disclosures."""
        return self._research_disclosure

    # ==========================================================================
    # 5. UNIFIED ORCHESTRATION PIPELINE
    # ==========================================================================

    def analyze_company(self, request: CompanyRequest) -> AnalysisResponse:
        """
        Execute full analytical aggregation across profiling, valuation, and filing intelligence.
        """
        warnings: List[str] = []
        provenance: Dict[str, Any] = {}

        # 1. Company Profile
        profile = self.get_company_profile(request.ticker)
        provenance["company_cik"] = profile.cik
        provenance["sector"] = profile.sector

        # 2. Valuation
        valuation_resp: Optional[ValuationResponse] = None
        try:
            val_req = ValuationRequest(
                ticker=request.ticker,
                as_of_date=request.as_of_date,
                mode=request.mode,
                persist=False,
            )
            valuation_resp = self.get_valuation(val_req)
            provenance["valuation_lineage"] = valuation_resp.lineage
            provenance["valuation_sources"] = valuation_resp.data_sources
        except ValuationUnavailableError as e:
            warnings.append(f"Valuation unavailable: {e}")
            logger.warning("Valuation unavailable for %s: %s", request.ticker, e)

        # 3. Filing Intelligence
        filing_resp: Optional[FilingIntelligenceResponse] = None
        try:
            filing_resp = self.get_filing_intelligence(
                ticker=request.ticker,
                as_of_date=request.as_of_date,
                mode=request.mode,
                include_rejected=False,
            )
            provenance["filing_accessions"] = filing_resp.covered_accessions
            provenance["filing_evidence_summary"] = filing_resp.evidence_status_summary
            if filing_resp.total_claims_retrieved == 0:
                warnings.append(f"No qualitative filing disclosures found for {request.ticker} as of {request.as_of_date or 'latest'}.")
        except Exception as e:
            warnings.append(f"Filing intelligence query failed: {e}")
            logger.warning("Filing intelligence query failed for %s: %s", request.ticker, e)

        # 4. What Changed Analysis
        what_changed_resp: Optional[WhatChangedResponse] = None
        try:
            what_changed_resp = self.get_company_changes(
                ticker=request.ticker,
                as_of_date=request.as_of_date,
                mode=request.mode,
            )
            if what_changed_resp and what_changed_resp.is_longitudinal_valid:
                provenance["current_accession"] = what_changed_resp.current_accession
                provenance["previous_accession"] = what_changed_resp.previous_accession
                provenance["longitudinal_valid"] = True
            elif what_changed_resp:
                provenance["longitudinal_valid"] = False
                provenance["rejection_reason"] = what_changed_resp.rejection_reason
        except Exception as e:
            logger.warning("What-changed analysis failed for %s: %s", request.ticker, e)

        # 5. Status Evaluation
        if valuation_resp and filing_resp:
            status = "SUCCESS"
        elif valuation_resp or filing_resp:
            status = "PARTIAL"
        else:
            status = "ERROR"

        return AnalysisResponse(
            request=request,
            profile=profile,
            valuation=valuation_resp,
            filing_intelligence=filing_resp,
            research_disclosure=self.get_research_disclosure(),
            warnings=warnings,
            provenance=provenance,
            status=status,
            error_message=warnings[0] if status == "ERROR" and warnings else None,
            what_changed=what_changed_resp,
        )

    # ==========================================================================
    # 5. PHASE 8C: INTERACTIVE SCENARIO ANALYSIS
    # ==========================================================================

    def calculate_analyst_scenario(
        self,
        ticker: str,
        as_of_date: Optional[str] = None,
        mode: str = "LIVE",
        wacc_override: Optional[float] = None,
        terminal_growth_override: Optional[float] = None,
        target_margin_override: Optional[float] = None,
    ) -> ValuationScenarioSummary:
        """
        Execute an on-demand deterministic analyst DCF scenario without mutating baseline results.
        
        Delegates all calculation to existing domain functions in src.valuation.
        Does NOT persist results to DuckDB and never overwrites baseline models.
        """
        import copy
        from src.valuation.assumptions import build_forecast_assumptions
        from src.valuation.dcf import calculate_dcf as _calc_dcf
        from src.valuation.wacc import calculate_wacc as _calc_wacc

        clean_ticker = str(ticker).strip().upper() if ticker else ""
        if not clean_ticker:
            raise InvalidTickerError("Ticker symbol cannot be empty.")
        
        # Ensure company exists
        self.get_company_profile(clean_ticker)

        val_date = as_of_date or "2024-12-31"

        try:
            inputs = self.valuation_engine.prepare_valuation_inputs(
                ticker=clean_ticker,
                valuation_date=val_date,
                valuation_mode=mode,
            )
            wacc_inputs = self.valuation_engine.prepare_wacc_inputs(inputs)
            base_assumptions = build_forecast_assumptions("BASE", inputs)

            # 1. Custom Assumptions
            scenario_assumptions = copy.deepcopy(base_assumptions)
            scenario_assumptions.scenario_name = "ANALYST_SCENARIO"

            if terminal_growth_override is not None:
                scenario_assumptions.terminal_growth_rate = float(terminal_growth_override)

            if target_margin_override is not None:
                scenario_assumptions.ebit_margins = [
                    float(target_margin_override)
                ] * len(scenario_assumptions.ebit_margins)

            # 2. Custom WACC Calibration
            scenario_wacc_inputs = copy.deepcopy(wacc_inputs)
            if wacc_override is not None:
                base_wacc_out = _calc_wacc(wacc_inputs)
                we = base_wacc_out.weight_equity
                wd = base_wacc_out.weight_debt
                tax = max(0.0, min(0.40, scenario_wacc_inputs.tax_rate))
                after_tax_rd = scenario_wacc_inputs.cost_of_debt * (1.0 - tax)
                target_w = float(wacc_override)
                required_rf = (target_w - (wd * after_tax_rd)) / we - (scenario_wacc_inputs.beta * scenario_wacc_inputs.equity_risk_premium)
                scenario_wacc_inputs.risk_free_rate = required_rf

            dcf_res = _calc_dcf(
                inputs=inputs,
                assumptions=scenario_assumptions,
                wacc_inputs=scenario_wacc_inputs,
                valuation_mode=mode,
            )
            wacc_calc = _calc_wacc(scenario_wacc_inputs)

            return ValuationScenarioSummary(
                scenario_name="ANALYST_SCENARIO",
                fair_value_per_share=dcf_res.fair_value_per_share,
                enterprise_value=dcf_res.enterprise_value,
                equity_value=dcf_res.equity_value,
                wacc=wacc_calc.wacc,
                terminal_growth=scenario_assumptions.terminal_growth_rate,
                upside_downside=dcf_res.upside_downside,
            )
        except Exception as e:
            raise ValuationUnavailableError(
                f"Failed to calculate analyst scenario for {clean_ticker}: {e}"
            ) from e

    # ==========================================================================
    # 6. PHASE 8C: CANONICAL FUNDAMENTALS EXPLORER
    # ==========================================================================

    def get_fundamentals(
        self,
        ticker: str,
        as_of_date: Optional[str] = None,
        mode: str = "LIVE",
    ) -> FundamentalsResponse:
        """
        Retrieve canonical normalized multi-period statements and pre-computed features from DuckDB.
        Enforces point-in-time constraints in HISTORICAL mode.
        """
        clean_ticker = str(ticker).strip().upper() if ticker else ""
        if not clean_ticker:
            raise InvalidTickerError("Ticker symbol cannot be empty.")
        clean_mode = mode.strip().upper() if mode else "LIVE"
        if clean_mode not in ("LIVE", "HISTORICAL"):
            raise UnsupportedModeError(f"Unsupported mode '{mode}'.")
        if clean_mode == "HISTORICAL" and not as_of_date:
            raise MissingPITDateError("Historical fundamentals require an explicit as_of_date.")

        profile = self.get_company_profile(clean_ticker)

        pit_cutoff = as_of_date if clean_mode == "HISTORICAL" else None

        with self.db.get_connection() as con:
            # 1. Annual Financials
            annual_query = """
                SELECT 'ANNUAL', fiscal_year, fiscal_period, period_end_date::VARCHAR, filing_date::VARCHAR,
                       acceptance_datetime::VARCHAR, form, accession_number,
                       revenue, cogs, gross_profit, sga, ebit, interest_expense, pretax_income,
                       tax_expense, net_income, da, cash, current_assets, accounts_receivable,
                       inventory, total_assets, current_liabilities, accounts_payable, total_debt,
                       total_equity, cfo, capex, fcf
                FROM annual_financials
                WHERE ticker = ?
            """
            params: List[Any] = [clean_ticker]
            if pit_cutoff:
                annual_query += " AND acceptance_datetime <= ?::TIMESTAMPTZ"
                params.append(f"{pit_cutoff} 23:59:59")
            annual_query += " ORDER BY period_end_date DESC"

            ann_rows = con.execute(annual_query, params).fetchall()

            # 2. Quarterly Financials
            q_query = """
                SELECT 'QUARTERLY', fiscal_year, 'Q' || fiscal_quarter, period_end_date::VARCHAR, filing_date::VARCHAR,
                       acceptance_datetime::VARCHAR, form, accession_number,
                       revenue, cogs, gross_profit, sga, ebit, interest_expense, pretax_income,
                       tax_expense, net_income, da, cash, current_assets, accounts_receivable,
                       inventory, total_assets, current_liabilities, accounts_payable, total_debt,
                       total_equity, cfo, capex, fcf
                FROM quarterly_financials
                WHERE ticker = ?
            """
            q_params: List[Any] = [clean_ticker]
            if pit_cutoff:
                q_query += " AND acceptance_datetime <= ?::TIMESTAMPTZ"
                q_params.append(f"{pit_cutoff} 23:59:59")
            q_query += " ORDER BY period_end_date DESC"

            q_rows = con.execute(q_query, q_params).fetchall()

            # 3. Financial Features
            feat_query = """
                SELECT feature_name, feature_value, unit, fiscal_year, fiscal_period, period_end_date::VARCHAR,
                       calculation_method, source_concepts, source_accessions
                FROM financial_features
                WHERE ticker = ?
            """
            feat_params: List[Any] = [clean_ticker]
            if pit_cutoff:
                feat_query += " AND as_of_date <= ?::TIMESTAMPTZ"
                feat_params.append(f"{pit_cutoff} 23:59:59")
            feat_query += " ORDER BY period_end_date DESC, feature_name ASC"

            feat_rows = con.execute(feat_query, feat_params).fetchall()

        def _map_statement_row(r) -> FinancialPeriodDTO:
            acc = str(r[7]) if r[7] else None
            form = str(r[6]) if r[6] else ""
            fdate = str(r[4]) if r[4] else None
            adt = str(r[5]) if r[5] else None
            cik_clean = profile.cik.lstrip("0") if profile.cik else ""
            acc_clean = acc.replace("-", "") if acc else ""
            sec_url = f"https://www.sec.gov/Archives/edgar/data/{cik_clean}/{acc_clean}/{acc}.txt" if acc else None

            stmt_prov = (
                SourceProvenanceDTO(
                    source_type="SEC_FILING",
                    primary_source=f"SEC Form {form} / CIK {profile.cik} / Accession {acc}",
                    accession_number=acc,
                    filing_date=fdate,
                    acceptance_datetime=adt,
                    sec_url=sec_url,
                    calculation_method="Direct primary extraction from SEC EDGAR XBRL / HTML disclosure",
                    source_concepts=["us-gaap:Revenues", "us-gaap:OperatingIncomeLoss", "us-gaap:NetIncomeLoss"],
                    as_of_date=pit_cutoff,
                    mode=clean_mode,
                    is_pit_compliant=True,
                    pit_rejection_reason=None,
                )
                if acc
                else None
            )

            return FinancialPeriodDTO(
                period_type=r[0],
                fiscal_year=int(r[1]) if r[1] is not None else 0,
                fiscal_period=str(r[2]),
                period_end_date=str(r[3]),
                filing_date=str(r[4]),
                acceptance_datetime=str(r[5]),
                form=str(r[6]),
                accession_number=str(r[7]),
                revenue=float(r[8]) if r[8] is not None else None,
                cogs=float(r[9]) if r[9] is not None else None,
                gross_profit=float(r[10]) if r[10] is not None else None,
                sga=float(r[11]) if r[11] is not None else None,
                ebit=float(r[12]) if r[12] is not None else None,
                interest_expense=float(r[13]) if r[13] is not None else None,
                pretax_income=float(r[14]) if r[14] is not None else None,
                tax_expense=float(r[15]) if r[15] is not None else None,
                net_income=float(r[16]) if r[16] is not None else None,
                da=float(r[17]) if r[17] is not None else None,
                cash=float(r[18]) if r[18] is not None else None,
                current_assets=float(r[19]) if r[19] is not None else None,
                accounts_receivable=float(r[20]) if r[20] is not None else None,
                inventory=float(r[21]) if r[21] is not None else None,
                total_assets=float(r[22]) if r[22] is not None else None,
                current_liabilities=float(r[23]) if r[23] is not None else None,
                accounts_payable=float(r[24]) if r[24] is not None else None,
                total_debt=float(r[25]) if r[25] is not None else None,
                total_equity=float(r[26]) if r[26] is not None else None,
                cfo=float(r[27]) if r[27] is not None else None,
                capex=float(r[28]) if r[28] is not None else None,
                fcf=float(r[29]) if r[29] is not None else None,
                source_provenance=stmt_prov,
            )

        annual_dtos = [_map_statement_row(r) for r in ann_rows]
        q_dtos = [_map_statement_row(r) for r in q_rows]
        feat_dtos = [
            FinancialFeatureDTO(
                feature_name=r[0],
                feature_value=float(r[1]) if r[1] is not None else None,
                unit=str(r[2]),
                fiscal_year=int(r[3]) if r[3] is not None else 0,
                fiscal_period=str(r[4]),
                period_end_date=str(r[5]),
                source_provenance=(
                    SourceProvenanceDTO(
                        source_type="DERIVED",
                        primary_source=f"Pre-computed feature / Accessions: {r[8]}",
                        accession_number=str(r[8]) if r[8] else None,
                        filing_date=None,
                        acceptance_datetime=None,
                        sec_url=None,
                        calculation_method=str(r[6]) if r[6] else "Deterministic financial ratio formula",
                        source_concepts=str(r[7]).split(",") if r[7] else [],
                        as_of_date=pit_cutoff,
                        mode=clean_mode,
                        is_pit_compliant=True,
                        pit_rejection_reason=None,
                    )
                    if (len(r) > 8 and r[8])
                    else None
                ),
            )
            for r in feat_rows
        ]

        return FundamentalsResponse(
            ticker=clean_ticker,
            as_of_date=pit_cutoff,
            mode=clean_mode,
            annual_statements=annual_dtos,
            quarterly_statements=q_dtos,
            features=feat_dtos,
            as_of_cutoff_datetime=f"{pit_cutoff} 23:59:59" if pit_cutoff else None,
        )

    # ==========================================================================
    # 7. PHASE 8C: SEC FILING & SECTION EXPLORER
    # ==========================================================================

    def get_filing_explorer_data(
        self,
        ticker: str,
        as_of_date: Optional[str] = None,
        mode: str = "LIVE",
        form_filter: Optional[List[str]] = None,
    ) -> FilingExplorerResponse:
        """
        Retrieve SEC filings catalog and section-by-section breakdown.
        Enforces point-in-time acceptance date cutoff in HISTORICAL mode.
        """
        clean_ticker = str(ticker).strip().upper() if ticker else ""
        if not clean_ticker:
            raise InvalidTickerError("Ticker symbol cannot be empty.")
        clean_mode = mode.strip().upper() if mode else "LIVE"
        if clean_mode not in ("LIVE", "HISTORICAL"):
            raise UnsupportedModeError(f"Unsupported mode '{mode}'.")
        if clean_mode == "HISTORICAL" and not as_of_date:
            raise MissingPITDateError("Historical filing exploration requires an explicit as_of_date.")

        # Ensure company exists
        profile = self.get_company_profile(clean_ticker)

        pit_cutoff = as_of_date if clean_mode == "HISTORICAL" else None

        with self.db.get_connection() as con:
            # Query all-time filings count for PIT exclusion accounting
            all_filings_sql = "SELECT COUNT(*) FROM filings WHERE ticker = ?"
            all_f_params: List[Any] = [clean_ticker]
            if form_filter:
                placeholders = ", ".join(["?"] * len(form_filter))
                all_filings_sql += f" AND form IN ({placeholders})"
                all_f_params.extend(form_filter)
            all_filings_count_row = con.execute(all_filings_sql, all_f_params).fetchone()
            all_filings_count = int(all_filings_count_row[0]) if all_filings_count_row and all_filings_count_row[0] is not None else 0

            # Aggregate form counts under PIT cutoff
            counts_sql = """
                SELECT 
                    COUNT(CASE WHEN form = '10-K' THEN 1 END) as ten_k_cnt,
                    COUNT(CASE WHEN form = '10-Q' THEN 1 END) as ten_q_cnt
                FROM filings
                WHERE ticker = ?
            """
            c_params: List[Any] = [clean_ticker]
            if pit_cutoff:
                counts_sql += " AND acceptance_datetime <= ?::TIMESTAMPTZ"
                c_params.append(f"{pit_cutoff} 23:59:59")
            counts_row = con.execute(counts_sql, c_params).fetchone()
            ten_k_count = int(counts_row[0]) if counts_row and counts_row[0] is not None else 0
            ten_q_count = int(counts_row[1]) if counts_row and counts_row[1] is not None else 0

            # Aggregate claim counts under PIT cutoff
            claims_sql = """
                SELECT 
                    COUNT(*) as total_claims,
                    COUNT(CASE WHEN validation_status = 'VALIDATED' THEN 1 END) as val_claims,
                    COUNT(CASE WHEN validation_status != 'VALIDATED' THEN 1 END) as rej_claims
                FROM filing_extractions
                WHERE ticker = ?
            """
            cl_params: List[Any] = [clean_ticker]
            if pit_cutoff:
                claims_sql += " AND (acceptance_datetime <= ?::TIMESTAMPTZ OR filing_date <= ?::DATE)"
                cl_params.append(f"{pit_cutoff} 23:59:59")
                cl_params.append(pit_cutoff)
            claims_row = con.execute(claims_sql, cl_params).fetchone()
            total_claims = int(claims_row[0]) if claims_row and claims_row[0] is not None else 0
            val_claims = int(claims_row[1]) if claims_row and claims_row[1] is not None else 0
            rej_claims = int(claims_row[2]) if claims_row and claims_row[2] is not None else 0

            filings_sql = """
                SELECT f.accession_number, f.ticker, f.form, f.filing_date::VARCHAR,
                       f.report_date::VARCHAR, f.acceptance_datetime::VARCHAR,
                       COUNT(DISTINCT s.section_id) as section_count,
                       COUNT(DISTINCT e.extraction_id) as claim_count
                FROM filings f
                LEFT JOIN filing_sections s ON f.accession_number = s.accession_number
                LEFT JOIN filing_extractions e ON f.accession_number = e.accession_number
                WHERE f.ticker = ?
            """
            params: List[Any] = [clean_ticker]
            if pit_cutoff:
                filings_sql += " AND f.acceptance_datetime <= ?::TIMESTAMPTZ"
                params.append(f"{pit_cutoff} 23:59:59")
            
            if form_filter:
                placeholders = ", ".join(["?"] * len(form_filter))
                filings_sql += f" AND f.form IN ({placeholders})"
                params.extend(form_filter)

            filings_sql += """
                GROUP BY f.accession_number, f.ticker, f.form, f.filing_date, f.report_date, f.acceptance_datetime
                ORDER BY f.acceptance_datetime DESC, f.filing_date DESC
            """
            filing_rows = con.execute(filings_sql, params).fetchall()

            if filing_rows:
                matching_accs = [r[0] for r in filing_rows]
                acc_placeholders = ", ".join(["?"] * len(matching_accs))
                sec_sql = f"""
                    SELECT section_id, accession_number, section_name, section_title,
                           char_count, detection_confidence, SUBSTRING(section_text, 1, 500)
                    FROM filing_sections
                    WHERE accession_number IN ({acc_placeholders})
                    ORDER BY accession_number, section_id ASC
                """
                sec_rows = con.execute(sec_sql, matching_accs).fetchall()
                sections_by_acc: Dict[str, List[FilingSectionDTO]] = {}
                for sr in sec_rows:
                    dto = FilingSectionDTO(
                        section_id=sr[0],
                        section_name=sr[2],
                        section_title=sr[3],
                        char_count=int(sr[4]),
                        detection_confidence=sr[5],
                        section_preview=sr[6] if sr[6] else "",
                    )
                    sections_by_acc.setdefault(sr[1], []).append(dto)
            else:
                sections_by_acc = {}

        filing_dtos = [
            FilingSummaryDTO(
                accession_number=r[0],
                ticker=r[1],
                form=r[2],
                filing_date=r[3],
                report_date=r[4],
                acceptance_datetime=r[5],
                section_count=int(r[6]),
                claim_count=int(r[7]),
                sections=sections_by_acc.get(r[0], []),
            )
            for r in filing_rows
        ]

        latest_filing = filing_rows[0][3] if filing_rows else None
        latest_acc = filing_rows[0][5] if filing_rows else None
        excluded_count = max(0, all_filings_count - len(filing_dtos)) if pit_cutoff else 0

        return FilingExplorerResponse(
            ticker=clean_ticker,
            as_of_date=pit_cutoff,
            mode=clean_mode,
            filings=filing_dtos,
            total_filings_count=len(filing_dtos),
            ten_k_count=ten_k_count,
            ten_q_count=ten_q_count,
            latest_filing_date=latest_filing,
            latest_acceptance_datetime=latest_acc,
            total_claims_count=total_claims,
            validated_claims_count=val_claims,
            rejected_claims_count=rej_claims,
            company_name=profile.company_name,
            cik=profile.cik,
            excluded_future_filings_count=excluded_count,
        )

    # ==========================================================================
    # 8. PHASE 8F: PROVENANCE, DATA LINEAGE & WHAT CHANGED ENGINE
    # ==========================================================================

    def _build_valuation_lineage_from_data(
        self,
        ticker: str,
        as_of_date: Optional[str],
        mode: str,
        fair_value_per_share: float,
        enterprise_value: float,
        equity_value: float,
        wacc: float,
        terminal_growth: float,
        cost_of_equity: float,
        cost_of_debt: float,
        risk_free_rate: float,
        beta: float,
        net_debt: float,
        cash: float,
        total_debt: float,
        diluted_shares: float,
        revenue_growth_summary: str,
        ebit_margin_summary: str,
        forecast_periods: List[ForecastPeriodDTO],
        prov: SourceProvenanceDTO,
    ) -> DataLineageDTO:
        """Construct 4-stage numerical data lineage for fair value per share."""
        pv_fcff_total = sum(p.pv_fcff for p in forecast_periods) if forecast_periods else 0.0

        step1 = LineageStepDTO(
            step_number=1,
            step_name="RAW_SEC_EXTRACTION",
            description="Point-in-time extraction of balance sheet and LTM operational figures from verified SEC filings.",
            input_values={
                "ticker": ticker,
                "as_of_date": as_of_date,
                "mode": mode,
            },
            output_value={
                "cash_and_equivalents": round(cash, 2),
                "total_debt": round(total_debt, 2),
                "net_debt": round(net_debt, 2),
                "diluted_shares": round(diluted_shares, 2),
            },
            transformation_rule="Point-in-time extraction of balance sheet items; Net Debt = Total Debt - Cash.",
        )

        step2 = LineageStepDTO(
            step_number=2,
            step_name="FCFF_NORMALIZATION",
            description="5-year deterministic Free Cash Flow to Firm (FCFF) forecast schedule generation.",
            input_values={
                "forecast_years": len(forecast_periods),
                "revenue_growth_profile": revenue_growth_summary,
                "ebit_margin_profile": ebit_margin_summary,
            },
            output_value={
                "forecast_fcff": [round(p.fcff, 2) for p in forecast_periods],
                "sum_pv_fcff": round(pv_fcff_total, 2),
            },
            transformation_rule="NOPAT = EBIT * (1 - TaxRate); FCFF = NOPAT + D&A - Capex - DeltaNWC.",
        )

        step3 = LineageStepDTO(
            step_number=3,
            step_name="DISCOUNTING_AND_WACC",
            description="Discounting discrete forecast cash flows to present value using calibrated WACC.",
            input_values={
                "wacc": round(wacc, 4),
                "cost_of_equity": round(cost_of_equity, 4),
                "cost_of_debt": round(cost_of_debt, 4),
                "risk_free_rate": round(risk_free_rate, 4),
                "beta": round(beta, 4),
            },
            output_value={
                "discounted_cash_flows_pv": round(pv_fcff_total, 2),
                "discount_factors": [round(p.discount_factor, 4) for p in forecast_periods],
            },
            transformation_rule="PV(FCFF_t) = FCFF_t / (1 + WACC)^t for forecast years 1 to 5.",
        )

        step4 = LineageStepDTO(
            step_number=4,
            step_name="TERMINAL_VALUE_AND_EQUITY_BRIDGE",
            description="Perpetual growth terminal value calculation and enterprise-to-equity bridge.",
            input_values={
                "terminal_growth_rate": round(terminal_growth, 4),
                "wacc": round(wacc, 4),
                "enterprise_value": round(enterprise_value, 2),
                "net_debt": round(net_debt, 2),
                "diluted_shares": round(diluted_shares, 2),
            },
            output_value={
                "enterprise_value": round(enterprise_value, 2),
                "equity_value": round(equity_value, 2),
                "fair_value_per_share": round(fair_value_per_share, 2),
            },
            transformation_rule="TV = FCFF_5 * (1 + g) / (WACC - g); EV = sum(PV_FCFF) + PV(TV); Equity = EV - Net Debt; Fair Value = Equity / Diluted Shares.",
        )

        return DataLineageDTO(
            entity_ticker=ticker,
            target_metric="Fair Value Per Share",
            metric_name="Fair Value Per Share",
            final_value=fair_value_per_share,
            unit="USD/share",
            calculation_summary=f"Deterministic DCF (5-year forecast + Gordon Growth TV at {wacc*100:.2f}% WACC and {terminal_growth*100:.2f}% terminal growth)",
            steps=[step1, step2, step3, step4],
            source_provenance=prov,
        )

    def _build_wacc_lineage_from_data(
        self,
        ticker: str,
        wacc: float,
        cost_of_equity: float,
        cost_of_debt: float,
        risk_free_rate: float,
        beta: float,
        equity_risk_premium: float,
        equity_value: float,
        total_debt: float,
        enterprise_value: float,
        prov: SourceProvenanceDTO,
    ) -> DataLineageDTO:
        """Construct 4-stage numerical data lineage for WACC derivation."""
        ev = enterprise_value if enterprise_value > 0 else (equity_value + total_debt)
        we = max(0.0, min(1.0, equity_value / ev)) if ev > 0 else 1.0
        wd = 1.0 - we

        step1_wacc = LineageStepDTO(
            step_number=1,
            step_name="COST_OF_EQUITY_CAPM",
            description="Capital Asset Pricing Model (CAPM) estimation for cost of equity.",
            input_values={
                "risk_free_rate": round(risk_free_rate, 4),
                "beta": round(beta, 4),
                "equity_risk_premium": round(equity_risk_premium, 4),
            },
            output_value={"cost_of_equity": round(cost_of_equity, 4)},
            transformation_rule="Ke = Rf + (Beta * ERP)",
        )

        step2_wacc = LineageStepDTO(
            step_number=2,
            step_name="COST_OF_DEBT",
            description="Pre-tax and after-tax cost of debt calculation.",
            input_values={"pretax_cost_of_debt": round(cost_of_debt, 4)},
            output_value={"cost_of_debt": round(cost_of_debt, 4)},
            transformation_rule="Kd_after_tax = Kd_pretax * (1 - TaxRate)",
        )

        step3_wacc = LineageStepDTO(
            step_number=3,
            step_name="CAPITAL_STRUCTURE_WEIGHTS",
            description="Market value weighting of equity and debt capital components.",
            input_values={
                "equity_value": round(equity_value, 2),
                "total_debt": round(total_debt, 2),
                "enterprise_value": round(ev, 2),
            },
            output_value={
                "weight_equity": round(we, 4),
                "weight_debt": round(wd, 4),
            },
            transformation_rule="We = Equity / (Equity + Debt); Wd = Debt / (Equity + Debt)",
        )

        step4_wacc = LineageStepDTO(
            step_number=4,
            step_name="WACC_COMBINATION",
            description="Blended Weighted Average Cost of Capital calculation.",
            input_values={
                "weight_equity": round(we, 4),
                "cost_of_equity": round(cost_of_equity, 4),
                "weight_debt": round(wd, 4),
                "cost_of_debt": round(cost_of_debt, 4),
            },
            output_value={"wacc": round(wacc, 4)},
            transformation_rule="WACC = (We * Ke) + (Wd * Kd_after_tax)",
        )

        return DataLineageDTO(
            entity_ticker=ticker,
            target_metric="Weighted Average Cost of Capital (WACC)",
            metric_name="Weighted Average Cost of Capital (WACC)",
            final_value=wacc,
            unit="%",
            calculation_summary=f"Blended cost of capital: {we*100:.1f}% Equity ({cost_of_equity*100:.2f}%) + {wd*100:.1f}% Debt ({cost_of_debt*100:.2f}%)",
            steps=[step1_wacc, step2_wacc, step3_wacc, step4_wacc],
            source_provenance=prov,
        )

    def get_provenance(
        self,
        ticker: str,
        as_of_date: Optional[str] = None,
        mode: str = "LIVE",
        accession_number: Optional[str] = None,
    ) -> SourceProvenanceDTO:
        """
        Retrieve authoritative source provenance for a company's financial data.
        Enforces point-in-time acceptance date cutoff in HISTORICAL mode.
        """
        clean_ticker = str(ticker).strip().upper() if ticker else ""
        if not clean_ticker:
            raise InvalidTickerError("Ticker symbol cannot be empty.")
        clean_mode = mode.strip().upper() if mode else "LIVE"
        if clean_mode not in ("LIVE", "HISTORICAL"):
            raise UnsupportedModeError(f"Unsupported mode '{mode}'.")
        if clean_mode == "HISTORICAL" and not as_of_date:
            raise MissingPITDateError("Historical provenance requires an explicit as_of_date.")

        profile = self.get_company_profile(clean_ticker)
        pit_cutoff = as_of_date if clean_mode == "HISTORICAL" else None

        with self.db.get_connection() as con:
            if accession_number:
                row = con.execute(
                    """
                    SELECT accession_number, form, filing_date::VARCHAR, acceptance_datetime::VARCHAR
                    FROM filings
                    WHERE ticker = ? AND accession_number = ?
                    """,
                    [clean_ticker, accession_number],
                ).fetchone()
            else:
                sql = """
                    SELECT accession_number, form, filing_date::VARCHAR, acceptance_datetime::VARCHAR
                    FROM filings
                    WHERE ticker = ?
                """
                params: List[Any] = [clean_ticker]
                if pit_cutoff:
                    sql += " AND acceptance_datetime <= ?::TIMESTAMPTZ"
                    params.append(_format_pit_cutoff(pit_cutoff))
                sql += " ORDER BY acceptance_datetime DESC, filing_date DESC LIMIT 1"
                row = con.execute(sql, params).fetchone()

        if not row:
            is_compliant = False
            rejection_reason = (
                f"No filings found on or before point-in-time cutoff {pit_cutoff} 23:59:59."
                if pit_cutoff
                else f"No filing records found for {clean_ticker}."
            )
            return SourceProvenanceDTO(
                source_name="SEC EDGAR",
                source_type="FILING_XBRL",
                source_identifier=accession_number or clean_ticker,
                accession_number=accession_number,
                form=None,
                filing_date=None,
                acceptance_datetime=None,
                fiscal_period=None,
                fiscal_year=None,
                section_name=None,
                concept=None,
                unit="USD",
                observation_date=None,
                pit_cutoff=_format_pit_cutoff(pit_cutoff),
                is_pit_compliant=is_compliant,
                provenance_note=rejection_reason,
                primary_source=f"SEC EDGAR / CIK {profile.cik}",
                sec_url=f"https://www.sec.gov/edgar/browse/?CIK={profile.cik}",
                calculation_method=None,
                source_concepts=[],
                as_of_date=pit_cutoff,
                mode=clean_mode,
                pit_rejection_reason=rejection_reason,
            )

        acc, form, fdate, adt = row

        is_compliant = True
        rejection_reason = None
        if pit_cutoff and adt:
            adt_str = str(adt)
            cutoff_dt = _format_pit_cutoff(pit_cutoff) or ""
            if adt_str[:10] > str(pit_cutoff)[:10]:
                is_compliant = False
                rejection_reason = (
                    f"Accession {acc} accepted at {adt} violates point-in-time cutoff {cutoff_dt}."
                )

        cik_clean = profile.cik.lstrip("0") if profile.cik else ""
        acc_clean = acc.replace("-", "") if acc else ""
        sec_url = (
            f"https://www.sec.gov/Archives/edgar/data/{cik_clean}/{acc_clean}/{acc}.txt"
            if acc
            else f"https://www.sec.gov/edgar/browse/?CIK={profile.cik}"
        )

        return SourceProvenanceDTO(
            source_name="SEC EDGAR",
            source_type="FILING_XBRL",
            source_identifier=acc or clean_ticker,
            accession_number=acc,
            form=form,
            filing_date=fdate,
            acceptance_datetime=adt,
            fiscal_period=None,
            fiscal_year=None,
            section_name=None,
            concept=None,
            unit="USD",
            observation_date=fdate,
            pit_cutoff=_format_pit_cutoff(pit_cutoff),
            is_pit_compliant=is_compliant,
            provenance_note=rejection_reason or f"Audited filing for {clean_ticker} from SEC EDGAR",
            primary_source=f"SEC Form {form} / CIK {profile.cik} / Accession {acc}",
            sec_url=sec_url,
            calculation_method="Direct primary extraction from SEC EDGAR XBRL / HTML disclosure",
            source_concepts=[
                "us-gaap:Revenues",
                "us-gaap:OperatingIncomeLoss",
                "us-gaap:NetIncomeLoss",
                "us-gaap:Assets",
                "us-gaap:Liabilities",
            ],
            as_of_date=pit_cutoff,
            mode=clean_mode,
            pit_rejection_reason=rejection_reason,
        )

    def get_valuation_lineage(
        self,
        ticker: str,
        as_of_date: Optional[str] = None,
        mode: str = "LIVE",
    ) -> DataLineageDTO:
        """Retrieve complete 4-stage data lineage for fair value per share."""
        val_resp = self.get_valuation(
            ValuationRequest(ticker=ticker, as_of_date=as_of_date, mode=mode, persist=False)
        )
        if val_resp.valuation_lineage:
            return val_resp.valuation_lineage
        prov = self.get_provenance(ticker=ticker, as_of_date=as_of_date, mode=mode)
        return self._build_valuation_lineage_from_data(
            ticker=val_resp.ticker,
            as_of_date=val_resp.as_of_date,
            mode=val_resp.valuation_mode,
            fair_value_per_share=val_resp.fair_value_per_share,
            enterprise_value=val_resp.enterprise_value,
            equity_value=val_resp.equity_value,
            wacc=val_resp.wacc,
            terminal_growth=val_resp.terminal_growth,
            cost_of_equity=val_resp.cost_of_equity,
            cost_of_debt=val_resp.cost_of_debt,
            risk_free_rate=val_resp.risk_free_rate,
            beta=val_resp.beta,
            net_debt=val_resp.net_debt,
            cash=val_resp.cash,
            total_debt=val_resp.total_debt,
            diluted_shares=val_resp.diluted_shares,
            revenue_growth_summary=val_resp.revenue_growth_summary,
            ebit_margin_summary=val_resp.ebit_margin_summary,
            forecast_periods=val_resp.forecast_periods,
            prov=prov,
        )

    def get_wacc_lineage(
        self,
        ticker: str,
        as_of_date: Optional[str] = None,
        mode: str = "LIVE",
    ) -> DataLineageDTO:
        """Retrieve complete 4-stage data lineage for WACC derivation."""
        val_resp = self.get_valuation(
            ValuationRequest(ticker=ticker, as_of_date=as_of_date, mode=mode, persist=False)
        )
        if val_resp.wacc_lineage:
            return val_resp.wacc_lineage
        prov = self.get_provenance(ticker=ticker, as_of_date=as_of_date, mode=mode)
        return self._build_wacc_lineage_from_data(
            ticker=val_resp.ticker,
            wacc=val_resp.wacc,
            cost_of_equity=val_resp.cost_of_equity,
            cost_of_debt=val_resp.cost_of_debt,
            risk_free_rate=val_resp.risk_free_rate,
            beta=val_resp.beta,
            equity_risk_premium=val_resp.equity_risk_premium,
            equity_value=val_resp.equity_value,
            total_debt=val_resp.total_debt,
            enterprise_value=val_resp.enterprise_value,
            prov=prov,
        )

    def get_evidence_lineage(
        self,
        ticker: str,
        as_of_date: Optional[str] = None,
        mode: str = "LIVE",
    ) -> List[QualitativeEvidenceLineageDTO]:
        """
        Retrieve complete 6-stage qualitative evidence lineage for verified disclosures:
        Filing -> Section -> Passage -> Extraction -> Validation -> Signal.
        """
        clean_ticker = str(ticker).strip().upper() if ticker else ""
        if not clean_ticker:
            raise InvalidTickerError("Ticker symbol cannot be empty.")
        clean_mode = mode.strip().upper() if mode else "LIVE"
        if clean_mode not in ("LIVE", "HISTORICAL"):
            raise UnsupportedModeError(f"Unsupported mode '{mode}'.")
        if clean_mode == "HISTORICAL" and not as_of_date:
            raise MissingPITDateError("Historical evidence lineage requires an explicit as_of_date.")

        profile = self.get_company_profile(clean_ticker)
        pit_cutoff = as_of_date if clean_mode == "HISTORICAL" else None

        sql = """
            SELECT e.extraction_id, e.category, e.claim, e.evidence_quote, e.evidence_location,
                   e.source_identifier, e.direction, e.severity, e.confidence, e.materiality,
                   e.validation_status, e.validation_reason, e.section_name, e.passage_id,
                   f.form, f.filing_date::VARCHAR, f.acceptance_datetime::VARCHAR, f.accession_number,
                   e.extraction_model
            FROM filing_extractions e
            JOIN filings f ON e.accession_number = f.accession_number
            WHERE e.ticker = ?
              AND e.validation_status = 'VALIDATED'
        """
        params: List[Any] = [clean_ticker]
        if pit_cutoff:
            sql += " AND f.acceptance_datetime <= ?::TIMESTAMPTZ"
            params.append(_format_pit_cutoff(pit_cutoff))
        sql += " ORDER BY f.acceptance_datetime DESC, e.extraction_id ASC"

        with self.db.get_connection() as con:
            rows = con.execute(sql, params).fetchall()

        lineage_list: List[QualitativeEvidenceLineageDTO] = []
        for r in rows:
            lineage_list.append(
                QualitativeEvidenceLineageDTO(
                    ticker=clean_ticker,
                    claim_id=str(r[0]),
                    company_name=profile.company_name,
                    cik=profile.cik,
                    form=str(r[14]),
                    accession_number=str(r[17]),
                    filing_date=str(r[15]),
                    acceptance_datetime=str(r[16]),
                    section_name=str(r[12]),
                    passage_id=str(r[13]) if r[13] else "",
                    verbatim_quote=str(r[3]),
                    extraction_category=str(r[1]),
                    direction=str(r[6]),
                    severity=str(r[7]),
                    materiality=str(r[9]),
                    confidence=float(r[8]) if r[8] is not None else 1.0,
                    validation_status=str(r[10]),
                    validation_reason=str(r[11]) if r[11] else "Exact quote verified against filing text",
                    valuation_bridge_link=None,
                    category=str(r[1]),
                    filing_stage={
                        "form": str(r[14]),
                        "filing_date": str(r[15]),
                        "acceptance_datetime": str(r[16]),
                        "accession_number": str(r[17]),
                    },
                    section_stage={
                        "section_name": str(r[12]),
                        "source_identifier": str(r[5]) if r[5] else "",
                        "evidence_location": str(r[4]) if r[4] else "",
                    },
                    passage_stage={
                        "passage_id": str(r[13]) if r[13] else "",
                        "verbatim_quote": str(r[3]),
                    },
                    extraction_stage={
                        "claim": str(r[2]),
                        "confidence": float(r[8]) if r[8] is not None else 1.0,
                        "severity": str(r[7]),
                        "direction": str(r[6]),
                        "model": str(r[18]) if r[18] else "audited-nlp",
                    },
                    validation_stage={
                        "status": str(r[10]),
                        "reason": str(r[11]) if r[11] else "Exact quote verified against filing text",
                        "is_exact_match": (str(r[10]).upper() == "VALIDATED"),
                    },
                    signal_stage={
                        "category": str(r[1]),
                        "materiality": str(r[9]),
                        "direction": str(r[6]),
                        "severity": str(r[7]),
                    },
                )
            )
        return lineage_list

    def get_valuation_bridge_lineage(
        self,
        ticker: str,
        as_of_date: Optional[str] = None,
        mode: str = "LIVE",
    ) -> Optional[ValuationBridgeLineageDTO]:
        """
        Retrieve empirical Valuation Bridge linking verified qualitative disclosures
        to quantitative DCF adjustments.
        """
        clean_ticker = str(ticker).strip().upper() if ticker else ""
        if not clean_ticker:
            raise InvalidTickerError("Ticker symbol cannot be empty.")
        clean_mode = mode.strip().upper() if mode else "LIVE"
        if clean_mode not in ("LIVE", "HISTORICAL"):
            raise UnsupportedModeError(f"Unsupported mode '{mode}'.")
        if clean_mode == "HISTORICAL" and not as_of_date:
            raise MissingPITDateError("Historical valuation bridge requires an explicit as_of_date.")

        self.get_company_profile(clean_ticker)
        pit_cutoff = as_of_date if clean_mode == "HISTORICAL" else None

        sql = """
            SELECT comparison_id, valuation_date::VARCHAR, baseline_fair_value,
                   enhanced_fair_value, fair_value_pct_change, primary_signal_category,
                   key_assumption_adjusted, adjustment_magnitude, evidence_citation
            FROM valuation_comparison_results
            WHERE ticker = ?
        """
        params: List[Any] = [clean_ticker]
        if pit_cutoff:
            sql += " AND valuation_date <= ?::DATE"
            params.append(pit_cutoff)
        sql += " ORDER BY valuation_date DESC LIMIT 1"

        with self.db.get_connection() as con:
            row = con.execute(sql, params).fetchone()

        if not row:
            return None

        return ValuationBridgeLineageDTO(
            comparison_id=str(row[0]),
            valuation_date=str(row[1]),
            baseline_fair_value=float(row[2]),
            enhanced_fair_value=float(row[3]),
            fair_value_pct_change=float(row[4]),
            primary_signal_category=str(row[5]),
            key_assumption_adjusted=str(row[6]),
            adjustment_magnitude=float(row[7]),
            evidence_citation=str(row[8]),
            is_pit_valid=True,
        )

    def get_company_changes(
        self,
        ticker: str,
        as_of_date: Optional[str] = None,
        mode: str = "LIVE",
    ) -> WhatChangedResponse:
        """
        Synthesize multi-period changes across fundamental financials, valuation assumptions,
        and qualitative disclosure signals.
        Enforces strict Dual-Accession Point-in-Time Lock in HISTORICAL mode:
        both Period T (current) and Period T-1 (previous) accessions must satisfy
        acceptance_datetime <= as_of_date 23:59:59.
        """
        clean_ticker = str(ticker).strip().upper() if ticker else ""
        if not clean_ticker:
            raise InvalidTickerError("Ticker symbol cannot be empty.")
        clean_mode = mode.strip().upper() if mode else "LIVE"
        if clean_mode not in ("LIVE", "HISTORICAL"):
            raise UnsupportedModeError(f"Unsupported mode '{mode}'.")
        if clean_mode == "HISTORICAL" and not as_of_date:
            raise MissingPITDateError("Historical changes query requires an explicit as_of_date.")

        self.get_company_profile(clean_ticker)
        pit_cutoff = as_of_date if clean_mode == "HISTORICAL" else None

        with self.db.get_connection() as con:
            stmt_sql = """
                SELECT fiscal_year, fiscal_period, period_end_date::VARCHAR, filing_date::VARCHAR,
                       acceptance_datetime::VARCHAR, accession_number,
                       revenue, gross_profit, ebit, net_income, cash, total_debt, capex, fcf
                FROM annual_financials
                WHERE ticker = ?
            """
            params: List[Any] = [clean_ticker]
            if pit_cutoff:
                stmt_sql += " AND acceptance_datetime <= ?::TIMESTAMPTZ"
                params.append(_format_pit_cutoff(pit_cutoff))
            stmt_sql += " ORDER BY period_end_date DESC"

            rows = con.execute(stmt_sql, params).fetchall()

            is_annual = True
            if len(rows) < 2:
                q_sql = """
                    SELECT fiscal_year, 'Q' || fiscal_quarter, period_end_date::VARCHAR, filing_date::VARCHAR,
                           acceptance_datetime::VARCHAR, accession_number,
                           revenue, gross_profit, ebit, net_income, cash, total_debt, capex, fcf
                    FROM quarterly_financials
                    WHERE ticker = ?
                """
                q_params: List[Any] = [clean_ticker]
                if pit_cutoff:
                    q_sql += " AND acceptance_datetime <= ?::TIMESTAMPTZ"
                    q_params.append(_format_pit_cutoff(pit_cutoff))
                q_sql += " ORDER BY period_end_date DESC"
                q_rows = con.execute(q_sql, q_params).fetchall()
                if len(q_rows) >= 2:
                    rows = q_rows
                    is_annual = False

            if len(rows) < 2:
                rejection = (
                    f"Insufficient statements available on or before point-in-time cutoff {_format_pit_cutoff(pit_cutoff)} "
                    f"(found {len(rows)}, need at least 2 for longitudinal comparison)."
                    if pit_cutoff
                    else f"Insufficient historical statements found for {clean_ticker} to form a longitudinal comparison."
                )
                return WhatChangedResponse(
                    ticker=clean_ticker,
                    mode=clean_mode,
                    as_of_date=pit_cutoff,
                    information_cutoff=_format_pit_cutoff(pit_cutoff) or "LIVE",
                    current_period_label="N/A",
                    previous_period_label="N/A",
                    current_period="N/A",
                    previous_period="N/A",
                    current_accession="N/A",
                    previous_accession="N/A",
                    fundamental_changes=[],
                    valuation_changes=[],
                    qualitative_signals=[],
                    qualitative_changes=[],
                    valuation_assumption_changes=[],
                    summary_narrative=rejection,
                    is_pit_valid=False,
                    is_longitudinal_valid=False,
                    rejection_reason=rejection,
                )

            curr_row = rows[0]
            prev_row = rows[1]

            curr_period = f"FY{curr_row[0]}" if is_annual else f"FY{curr_row[0]}-{curr_row[1]}"
            prev_period = f"FY{prev_row[0]}" if is_annual else f"FY{prev_row[0]}-{prev_row[1]}"
            curr_acc = str(curr_row[5])
            prev_acc = str(prev_row[5])
            curr_adt = str(curr_row[4])
            prev_adt = str(prev_row[4])

            # Dual-Accession Point-in-Time Lock Verification
            if pit_cutoff:
                cutoff_date = str(pit_cutoff)[:10]
                if str(curr_adt)[:10] > cutoff_date:
                    msg = f"Current period accession {curr_acc} accepted at {curr_adt} is post-cutoff ({_format_pit_cutoff(pit_cutoff)})."
                    return WhatChangedResponse(
                        ticker=clean_ticker,
                        mode=clean_mode,
                        as_of_date=pit_cutoff,
                        information_cutoff=_format_pit_cutoff(pit_cutoff) or "LIVE",
                        current_period_label=curr_period,
                        previous_period_label=prev_period,
                        current_period=curr_period,
                        previous_period=prev_period,
                        current_accession=curr_acc,
                        previous_accession=prev_acc,
                        fundamental_changes=[],
                        valuation_changes=[],
                        qualitative_signals=[],
                        qualitative_changes=[],
                        valuation_assumption_changes=[],
                        summary_narrative=msg,
                        is_pit_valid=False,
                        is_longitudinal_valid=False,
                        rejection_reason=msg,
                    )
                if str(prev_adt)[:10] > cutoff_date:
                    msg = f"Previous period accession {prev_acc} accepted at {prev_adt} is post-cutoff ({_format_pit_cutoff(pit_cutoff)})."
                    return WhatChangedResponse(
                        ticker=clean_ticker,
                        mode=clean_mode,
                        as_of_date=pit_cutoff,
                        information_cutoff=_format_pit_cutoff(pit_cutoff) or "LIVE",
                        current_period_label=curr_period,
                        previous_period_label=prev_period,
                        current_period=curr_period,
                        previous_period=prev_period,
                        current_accession=curr_acc,
                        previous_accession=prev_acc,
                        fundamental_changes=[],
                        valuation_changes=[],
                        qualitative_signals=[],
                        qualitative_changes=[],
                        valuation_assumption_changes=[],
                        summary_narrative=msg,
                        is_pit_valid=False,
                        is_longitudinal_valid=False,
                        rejection_reason=msg,
                    )

            # Compute Fundamental Deltas
            metric_definitions = [
                ("Revenue", 6, "$", "REVENUE"),
                ("Gross Profit", 7, "$", "PROFITABILITY"),
                ("Operating Income (EBIT)", 8, "$", "PROFITABILITY"),
                ("Net Income", 9, "$", "PROFITABILITY"),
                ("Cash & Cash Equivalents", 10, "$", "LIQUIDITY_DEBT"),
                ("Total Debt", 11, "$", "LIQUIDITY_DEBT"),
                ("Capital Expenditures (Capex)", 12, "$", "CASH_FLOW"),
                ("Free Cash Flow (FCF)", 13, "$", "CASH_FLOW"),
            ]

            fund_changes: List[FundamentalChangeDTO] = []
            for name, idx, unit, cat in metric_definitions:
                c_val = float(curr_row[idx]) if curr_row[idx] is not None else 0.0
                p_val = float(prev_row[idx]) if prev_row[idx] is not None else 0.0
                abs_chg = c_val - p_val
                if p_val != 0.0:
                    pct_chg = (abs_chg / abs(p_val)) * 100.0
                else:
                    pct_chg = 0.0 if abs_chg == 0.0 else 100.0

                is_meaningful = (abs(pct_chg) >= 0.1) and (abs(abs_chg) >= 1000.0)

                if not is_meaningful:
                    interpretation = "Flat / within rounding noise threshold (<0.1% change)"
                elif abs_chg > 0:
                    interpretation = f"Increased by +{pct_chg:.1f}% (+${abs_chg / 1e6:,.1f}M)"
                else:
                    interpretation = f"Decreased by {pct_chg:.1f}% (-${abs(abs_chg) / 1e6:,.1f}M)"

                fund_changes.append(
                    FundamentalChangeDTO(
                        metric_name=name,
                        category=cat,
                        current_period=curr_period,
                        current_value=c_val,
                        previous_period=prev_period,
                        previous_value=p_val,
                        absolute_change=abs_chg,
                        percent_change=pct_chg,
                        unit=unit,
                        direction="INCREASED" if abs_chg > 0 else ("DECREASED" if abs_chg < 0 else "UNCHANGED"),
                        is_meaningful=is_meaningful,
                        explanation=interpretation,
                        source_provenance=None,
                        percentage_change=pct_chg,
                        interpretation=interpretation,
                    )
                )

            # Query Valuation Changes
            val_changes: List[FundamentalChangeDTO] = []
            bridge_sql = """
                SELECT baseline_fair_value, enhanced_fair_value, fair_value_difference,
                       fair_value_pct_change, primary_signal_category, key_assumption_adjusted
                FROM valuation_comparison_results
                WHERE ticker = ?
            """
            b_params: List[Any] = [clean_ticker]
            if pit_cutoff:
                bridge_sql += " AND valuation_date <= ?::DATE"
                b_params.append(str(pit_cutoff)[:10])
            bridge_sql += " ORDER BY valuation_date DESC LIMIT 1"
            b_row = con.execute(bridge_sql, b_params).fetchone()

            if b_row:
                base_fv, enh_fv, fv_diff, fv_pct, sig_cat, adj_assump = b_row
                interp = f"Adjustment of {float(fv_pct):+.2f}% driven by qualitative {sig_cat} ({adj_assump})"
                val_changes.append(
                    FundamentalChangeDTO(
                        metric_name="Fair Value Per Share (Qualitative Integration)",
                        category="VALUATION_ASSUMPTION",
                        current_period="Enhanced Model (Model B)",
                        current_value=float(enh_fv),
                        previous_period="Baseline Model (Model A)",
                        previous_value=float(base_fv),
                        absolute_change=float(fv_diff),
                        percent_change=float(fv_pct),
                        unit="USD/share",
                        direction="INCREASED" if float(fv_diff) > 0 else ("DECREASED" if float(fv_diff) < 0 else "UNCHANGED"),
                        is_meaningful=(abs(float(fv_pct)) >= 0.1),
                        explanation=interp,
                        source_provenance=None,
                        percentage_change=float(fv_pct),
                        interpretation=interp,
                    )
                )

            # Query Qualitative Disclosure Signals
            sig_sql = """
                SELECT s.signal_id, s.ticker, s.category, s.change_type, s.current_claim,
                       s.previous_claim, s.direction_shift, s.severity_shift, s.materiality,
                       s.summary, s.current_accession, s.previous_accession,
                       f_cur.filing_date::VARCHAR, f_prev.filing_date::VARCHAR
                FROM filing_change_signals s
                JOIN filings f_cur ON s.current_accession = f_cur.accession_number
                LEFT JOIN filings f_prev ON s.previous_accession = f_prev.accession_number
                WHERE s.ticker = ?
            """
            s_params: List[Any] = [clean_ticker]
            if pit_cutoff:
                sig_sql += """
                    AND f_cur.acceptance_datetime <= ?::TIMESTAMPTZ
                    AND (s.previous_accession IS NULL OR f_prev.acceptance_datetime IS NULL OR f_prev.acceptance_datetime <= ?::TIMESTAMPTZ)
                """
                s_params.append(_format_pit_cutoff(pit_cutoff))
                s_params.append(_format_pit_cutoff(pit_cutoff))
            sig_sql += " ORDER BY s.category ASC, s.change_type ASC"
            s_rows = con.execute(sig_sql, s_params).fetchall()

            qual_signals = [
                ChangeSignalDTO(
                    signal_id=row[0],
                    ticker=row[1],
                    category=row[2],
                    change_type=row[3],
                    current_claim=row[4],
                    previous_claim=row[5],
                    direction_shift=row[6],
                    severity_shift=row[7],
                    materiality=row[8],
                    summary=row[9],
                    current_accession=row[10],
                    previous_accession=row[11],
                    current_filing_date=row[12] if len(row) > 12 else None,
                    previous_filing_date=row[13] if len(row) > 13 else None,
                )
                for row in s_rows
            ]

        return WhatChangedResponse(
            ticker=clean_ticker,
            mode=clean_mode,
            as_of_date=pit_cutoff,
            information_cutoff=_format_pit_cutoff(pit_cutoff) or "LIVE",
            current_period_label=curr_period,
            previous_period_label=prev_period,
            fundamental_changes=fund_changes,
            qualitative_changes=qual_signals,
            valuation_assumption_changes=val_changes,
            summary_narrative=f"Longitudinal comparison of {clean_ticker} between {curr_period} and {prev_period}.",
            is_pit_valid=True,
            current_period=curr_period,
            previous_period=prev_period,
            current_accession=curr_acc,
            previous_accession=prev_acc,
            valuation_changes=val_changes,
            qualitative_signals=qual_signals,
            is_longitudinal_valid=True,
            rejection_reason=None,
        )


