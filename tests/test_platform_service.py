"""
Unit and Integration Tests for Phase 8A: Platform Service Layer.

Validates:
A. Valid LIVE request
B. Valid HISTORICAL request
C. Historical request without as_of_date
D. Invalid ticker handling
E. Invalid execution mode handling
F. Missing valuation result graceful degradation
G. Missing filing intelligence graceful degradation
H. Point-in-time date propagation
I. Provenance and lineage preservation
J. Evidence validation state quarantine
K. Service immutability and non-mutation of domain objects
L. Response schema integrity
M. Architectural test (service independence, zero Streamlit import, zero duplicated domain math)
N. Phase 7 research disclosure immutability
"""
import sys
import unittest
from unittest.mock import MagicMock, patch

from src.data.db import DatabaseManager
from src.service.contracts import (
    AnalysisResponse,
    CompanyProfile,
    CompanyRequest,
    FilingIntelligenceResponse,
    FilingSignal,
    InvalidTickerError,
    MissingCompanyError,
    MissingPITDateError,
    ResearchDisclosure,
    UnsupportedModeError,
    ValuationRequest,
    ValuationResponse,
    ValuationUnavailableError,
)
from src.service.platform_service import PlatformService
from src.valuation.engine import ValuationEngine
from src.valuation.models import IncompleteValuationInputsError


class TestPlatformService(unittest.TestCase):
    """Test harness for the application service layer facade."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.db = DatabaseManager()
        cls.service = PlatformService(db_manager=cls.db)

    def test_01_valid_live_request(self) -> None:
        """Verify successful LIVE analysis request for a universe company."""
        req = CompanyRequest(ticker="MSFT", mode="LIVE")
        resp = self.service.analyze_company(req)

        self.assertIsInstance(resp, AnalysisResponse)
        self.assertEqual(resp.status, "SUCCESS")
        self.assertEqual(resp.request.ticker, "MSFT")
        self.assertEqual(resp.request.mode, "LIVE")

        # Company Profile
        self.assertIsInstance(resp.profile, CompanyProfile)
        self.assertEqual(resp.profile.ticker, "MSFT")
        self.assertEqual(resp.profile.company_name, "Microsoft Corp.")
        self.assertEqual(resp.profile.cik, "0000789019")
        self.assertEqual(resp.profile.sector, "Information Technology")
        self.assertGreater(resp.profile.covered_filings_count, 0)

        # Valuation
        self.assertIsNotNone(resp.valuation)
        val = resp.valuation
        self.assertIsInstance(val, ValuationResponse)
        self.assertEqual(val.ticker, "MSFT")
        self.assertGreater(val.fair_value_per_share, 0.0)
        self.assertGreater(val.enterprise_value, 0.0)
        self.assertGreater(val.equity_value, 0.0)
        self.assertGreater(val.wacc, 0.0)
        self.assertGreater(val.terminal_growth, 0.0)
        self.assertEqual(len(val.forecast_periods), 5)
        self.assertIn("BASE", val.scenarios)
        self.assertIn("BULL", val.scenarios)
        self.assertIn("BEAR", val.scenarios)
        self.assertGreater(len(val.relative_multiples), 0)

        # Filing Intelligence
        self.assertIsNotNone(resp.filing_intelligence)
        fi = resp.filing_intelligence
        self.assertIsInstance(fi, FilingIntelligenceResponse)
        self.assertEqual(fi.ticker, "MSFT")
        self.assertEqual(fi.mode, "LIVE")
        self.assertGreater(fi.total_claims_retrieved, 0)
        self.assertGreater(fi.validated_claims_count, 0)
        self.assertGreater(len(fi.signals), 0)

    def test_02_valid_historical_request(self) -> None:
        """Verify successful HISTORICAL analysis request with exact point-in-time propagation."""
        req = CompanyRequest(ticker="MSFT", as_of_date="2024-12-31", mode="HISTORICAL")
        resp = self.service.analyze_company(req)

        self.assertEqual(resp.status, "SUCCESS")
        self.assertEqual(resp.request.mode, "HISTORICAL")
        self.assertEqual(resp.request.as_of_date, "2024-12-31")

        self.assertIsNotNone(resp.valuation)
        self.assertEqual(resp.valuation.valuation_mode, "HISTORICAL")
        self.assertEqual(resp.valuation.valuation_date, "2024-12-31")

        self.assertIsNotNone(resp.filing_intelligence)
        self.assertEqual(resp.filing_intelligence.mode, "HISTORICAL")
        self.assertEqual(resp.filing_intelligence.as_of_date, "2024-12-31")

    def test_03_historical_request_without_date_raises_error(self) -> None:
        """Verify that HISTORICAL requests without as_of_date strictly raise MissingPITDateError."""
        with self.assertRaises(MissingPITDateError):
            CompanyRequest(ticker="MSFT", mode="HISTORICAL", as_of_date=None)

        with self.assertRaises(MissingPITDateError):
            self.service.get_filing_intelligence(ticker="MSFT", mode="HISTORICAL", as_of_date=None)

    def test_04_invalid_ticker_handling(self) -> None:
        """Verify that blank or missing tickers raise appropriate strongly typed errors."""
        with self.assertRaises(InvalidTickerError):
            CompanyRequest(ticker="", mode="LIVE")

        with self.assertRaises(InvalidTickerError):
            CompanyRequest(ticker="   ", mode="LIVE")

        with self.assertRaises(MissingCompanyError):
            self.service.get_company_profile("UNKNOWN_TICKER_XYZ_99")

        with self.assertRaises(MissingCompanyError):
            self.service.analyze_company(CompanyRequest(ticker="UNKNOWN_TICKER_XYZ_99", mode="LIVE"))

    def test_05_invalid_mode_handling(self) -> None:
        """Verify that unrecognized modes raise UnsupportedModeError."""
        with self.assertRaises(UnsupportedModeError):
            CompanyRequest(ticker="MSFT", mode="BACKTEST")

        with self.assertRaises(UnsupportedModeError):
            self.service.get_filing_intelligence(ticker="MSFT", mode="RANDOM_MODE", as_of_date="2024-12-31")

    def test_06_missing_valuation_handled_gracefully(self) -> None:
        """Verify that a valuation engine failure degrades gracefully to PARTIAL status in analyze_company."""
        mock_val_engine = MagicMock(spec=ValuationEngine)
        mock_val_engine.value_company.side_effect = IncompleteValuationInputsError("Missing balance sheet fact.")

        svc = PlatformService(db_manager=self.db, valuation_engine=mock_val_engine)

        # get_valuation directly should raise ValuationUnavailableError
        with self.assertRaises(ValuationUnavailableError):
            svc.get_valuation(ValuationRequest(ticker="MSFT", mode="LIVE"))

        # analyze_company should catch it, set valuation=None, add warning, and return PARTIAL
        resp = svc.analyze_company(CompanyRequest(ticker="MSFT", mode="LIVE"))
        self.assertEqual(resp.status, "PARTIAL")
        self.assertIsNone(resp.valuation)
        self.assertIsNotNone(resp.filing_intelligence)
        self.assertTrue(any("Valuation unavailable" in w for w in resp.warnings))

    def test_07_missing_filing_intelligence_handled_gracefully(self) -> None:
        """Verify that missing filing intelligence produces an empty response without crashing."""
        mock_db = MagicMock(spec=DatabaseManager)
        # Mock company profile return
        mock_con = MagicMock()
        mock_con.execute.return_value.fetchone.side_effect = [
            ("comp_fake", "FAKE", "0000000000", "Fake Corp", "Technology", 12),  # company
            (10, "2024-01-01"),  # filings count
            [],  # change signals
        ]
        mock_con.execute.return_value.fetchall.return_value = []
        mock_db.get_connection.return_value.__enter__.return_value = mock_con
        mock_db.query_filing_extractions.return_value = []

        svc = PlatformService(db_manager=mock_db)
        fi = svc.get_filing_intelligence(ticker="FAKE", mode="LIVE")

        self.assertEqual(fi.total_claims_retrieved, 0)
        self.assertEqual(fi.validated_claims_count, 0)
        self.assertEqual(len(fi.signals), 0)
        self.assertIn("No qualitative filing disclosures", fi.evidence_status_summary)

    def test_08_pit_date_propagation(self) -> None:
        """Verify that as_of_date is properly passed to valuation and database query filters."""
        mock_val_engine = MagicMock(spec=ValuationEngine)
        mock_db = MagicMock(spec=DatabaseManager)

        # Mock company existence
        mock_con = MagicMock()
        mock_con.execute.return_value.fetchone.return_value = (
            "comp_1", "AAPL", "0000320193", "Apple Inc.", "Information Technology", 9
        )
        mock_con.execute.return_value.fetchall.return_value = []
        mock_db.get_connection.return_value.__enter__.return_value = mock_con
        mock_db.query_filing_extractions.return_value = []

        svc = PlatformService(db_manager=mock_db, valuation_engine=mock_val_engine)

        val_req = ValuationRequest(ticker="AAPL", as_of_date="2023-12-31", mode="HISTORICAL", persist=False)
        try:
            svc.get_valuation(val_req)
        except Exception:
            pass

        mock_val_engine.value_company.assert_called_once_with(
            ticker="AAPL",
            valuation_date="2023-12-31",
            valuation_mode="HISTORICAL",
            persist=False,
        )

        svc.get_filing_intelligence(ticker="AAPL", as_of_date="2023-12-31", mode="HISTORICAL")
        mock_db.query_filing_extractions.assert_called_with(
            ticker="AAPL",
            validation_status="VALIDATED",
            as_of_date="2023-12-31",
        )

    def test_09_provenance_preservation(self) -> None:
        """Verify that lineage strings and source citations are completely preserved in the DTO."""
        req = CompanyRequest(ticker="MSFT", mode="LIVE")
        resp = self.service.analyze_company(req)

        self.assertIsNotNone(resp.valuation)
        self.assertIsNotNone(resp.valuation.lineage)
        self.assertIn("LTM Stmt:", resp.valuation.lineage)
        self.assertIn("SharesConcept:", resp.valuation.lineage)

        self.assertIsNotNone(resp.filing_intelligence)
        for sig in resp.filing_intelligence.signals:
            self.assertIsInstance(sig, FilingSignal)
            self.assertIsNotNone(sig.evidence_quote)
            self.assertIsNotNone(sig.source_identifier)
            self.assertEqual(sig.validation_status, "VALIDATED")

        self.assertIn("valuation_lineage", resp.provenance)
        self.assertIn("filing_accessions", resp.provenance)

    def test_10_evidence_validation_state_quarantine(self) -> None:
        """Verify that default filing intelligence strictly excludes REJECTED unverified claims."""
        fi = self.service.get_filing_intelligence(ticker="MSFT", mode="LIVE", include_rejected=False)
        self.assertEqual(fi.rejected_claims_count, 0)
        for sig in fi.signals:
            self.assertEqual(sig.validation_status, "VALIDATED")

    def test_11_service_immutability_and_non_mutation(self) -> None:
        """Verify that calling the service repeatedly produces identical results without altering database."""
        req = CompanyRequest(ticker="MSFT", as_of_date="2024-12-31", mode="HISTORICAL")

        resp1 = self.service.analyze_company(req)
        resp2 = self.service.analyze_company(req)

        self.assertEqual(resp1.valuation.fair_value_per_share, resp2.valuation.fair_value_per_share)
        self.assertEqual(resp1.valuation.enterprise_value, resp2.valuation.enterprise_value)
        self.assertEqual(
            resp1.filing_intelligence.total_claims_retrieved,
            resp2.filing_intelligence.total_claims_retrieved,
        )

    def test_12_response_schema_integrity(self) -> None:
        """Verify that all response DTOs are frozen dataclasses and cannot be mutated by callers."""
        req = CompanyRequest(ticker="MSFT", mode="LIVE")
        resp = self.service.analyze_company(req)

        with self.assertRaises(Exception):
            resp.status = "MUTATED"  # type: ignore

        with self.assertRaises(Exception):
            resp.profile.company_name = "Mutated Name"  # type: ignore

        with self.assertRaises(Exception):
            resp.valuation.fair_value_per_share = 99999.99  # type: ignore

    def test_13_architectural_independence_and_no_ui_imports(self) -> None:
        """
        Architectural Test: Verify that src.service does NOT import Streamlit or any UI framework,
        and does NOT contain mathematical valuation calculation code.
        """
        import src.service
        import src.service.contracts
        import src.service.platform_service

        # 1. UI framework isolation
        self.assertNotIn("streamlit", sys.modules, "Streamlit must NOT be imported into the service layer.")
        self.assertNotIn("dash", sys.modules, "Dash must NOT be imported into the service layer.")

        # 2. Mathematical independence: verify platform_service does not define valuation math functions
        self.assertFalse(hasattr(src.service.platform_service, "calculate_dcf"))
        self.assertFalse(hasattr(src.service.platform_service, "calculate_wacc"))
        self.assertFalse(hasattr(src.service.platform_service, "calculate_terminal_value"))

    def test_14_phase7_research_disclosure_immutability(self) -> None:
        """Verify that ResearchDisclosure accurately presents frozen Phase 7 audit figures."""
        disc = self.service.get_research_disclosure()

        self.assertIsInstance(disc, ResearchDisclosure)
        self.assertEqual(disc.primary_target, "forward_ebit_margin_change")
        self.assertEqual(disc.sample_size_longitudinal, 46)
        self.assertEqual(disc.walk_forward_folds, 2)
        self.assertEqual(disc.baseline_mae, 0.0777)
        self.assertEqual(disc.enhanced_mae, 0.0781)
        self.assertEqual(disc.delta_mae_pct, -0.60)
        self.assertEqual(disc.p_value, 0.2335)
        self.assertEqual(disc.hypothesis_decision, "Fail to reject H0")
        self.assertIn("do not provide statistically significant incremental predictive power", disc.key_takeaway)
        self.assertIn("-13.14%", disc.curse_of_dimensionality_finding)
        self.assertIn("0.8714", disc.filing_only_parity_finding)
        self.assertEqual(len(disc.limitations), 3)

    def test_15_list_covered_companies(self) -> None:
        """Verify listing of all universe companies with filing counts."""
        companies = self.service.list_covered_companies()
        self.assertEqual(len(companies), 30)
        tickers = set(c.ticker for c in companies)
        self.assertIn("MSFT", tickers)
        self.assertIn("AAPL", tickers)
        self.assertIn("NVDA", tickers)
        self.assertIn("XOM", tickers)


if __name__ == "__main__":
    unittest.main()
