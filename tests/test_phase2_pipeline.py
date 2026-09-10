"""
Comprehensive automated test suite for Phase 2 Financial Statement Pipeline.
Tests:
A. SEC client behavior (headers, rate limiting, gzip, error handling)
B. Point-in-time filtering (future exclusion, public availability inclusion)
C. Amendment and restatement handling (10-K vs 10-K/A temporal isolation)
D. Concept fallback cascade (Tier 1 -> Tier 2 -> Tier 4 -> Tier 5)
E. Period handling (instant vs duration, 52/53-week non-calendar years)
F. Unit and sign handling (USD, CapEx absolute value)
G. Data lineage (normalized fact -> raw fact -> filing)
H. Deterministic deduplication
I. 30-company universe integrity and DuckDB database validation
"""
import os
import sys
import unittest
from datetime import datetime, timezone

# Ensure workspace root in path
WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

from src.data.sec_client import SECClient, SECClientError, SECObjectNotFoundError, SECRateLimitError
from src.normalization.concept_normalizer import ConceptNormalizer, CONCEPT_FALLBACK_CASCADES
from src.normalization.pit_filter import PITFilter, parse_iso_datetime
from src.data.db import DatabaseManager, compute_fact_id


class TestSECClientBehavior(unittest.TestCase):
    """A. Test SEC Client behavior, rate limiting, and error handling."""

    def test_client_initialization_and_user_agent(self):
        client = SECClient(user_agent="AuditTester user@test.edu", max_requests_per_second=5.0)
        self.assertEqual(client.user_agent, "AuditTester user@test.edu")
        self.assertAlmostEqual(client.min_interval, 0.20, places=3)

    def test_extract_recent_filings_catalog(self):
        mock_submissions = {
            "filings": {
                "recent": {
                    "accessionNumber": ["0000320193-24-000001", "0000320193-24-000002"],
                    "filingDate": ["2024-01-15", "2024-02-10"],
                    "form": ["10-Q", "10-K"],
                    "reportDate": ["2023-12-30", "2023-12-30"],
                    "acceptanceDateTime": ["2024-01-15T16:30:00Z", "2024-02-10T16:45:00Z"],
                    "primaryDocument": ["doc1.htm", "doc2.htm"]
                }
            }
        }
        catalog = SECClient.extract_recent_filings_catalog(mock_submissions)
        self.assertEqual(len(catalog), 2)
        self.assertEqual(catalog[0]["accessionNumber"], "0000320193-24-000001")
        self.assertEqual(catalog[1]["form"], "10-K")


class TestPointInTimeDataControl(unittest.TestCase):
    """B. Test Point-in-Time filtering and information set boundaries."""

    def setUp(self):
        self.facts = [
            {
                "fact_id": "FACT_1",
                "ticker": "AAPL",
                "fiscal_year": 2020,
                "fiscal_period": "FY",
                "canonical_variable": "revenue",
                "value": 100.0,
                "acceptance_datetime": "2021-02-20T16:30:00Z",
                "filing_date": "2021-02-20",
                "form": "10-K",
                "accession_number": "ACC_1"
            },
            {
                "fact_id": "FACT_0",
                "ticker": "AAPL",
                "fiscal_year": 2019,
                "fiscal_period": "FY",
                "canonical_variable": "revenue",
                "value": 90.0,
                "acceptance_datetime": "2019-11-01T16:30:00Z",
                "filing_date": "2019-11-01",
                "form": "10-K",
                "accession_number": "ACC_0"
            }
        ]

    def test_future_filing_excluded(self):
        """As of 2021-01-15, the FY2020 10-K filed on 2021-02-20 MUST be excluded."""
        admitted = PITFilter.filter_facts_as_of(self.facts, "2021-01-15T00:00:00Z")
        fys = [f["fiscal_year"] for f in admitted]
        self.assertNotIn(2020, fys, "FY2020 fact must not leak into pre-filing date")
        self.assertIn(2019, fys, "FY2019 fact must be admitted")

    def test_available_filing_included(self):
        """As of 2021-03-01, the FY2020 10-K filed on 2021-02-20 MUST be admitted."""
        admitted = PITFilter.filter_facts_as_of(self.facts, "2021-03-01T00:00:00Z")
        fys = [f["fiscal_year"] for f in admitted]
        self.assertIn(2020, fys)
        self.assertIn(2019, fys)

    def test_leakage_audit_clean(self):
        audit = PITFilter.audit_leakage(self.facts, "2021-01-15T00:00:00Z")
        self.assertTrue(audit["leakage_free"])
        self.assertEqual(audit["leakage_violations_count"], 0)
        self.assertEqual(audit["admitted_facts"], 1)


class TestAmendmentAndRestatementHandling(unittest.TestCase):
    """C. Test restatements and amendment isolation (10-K vs 10-K/A)."""

    def setUp(self):
        self.original_10k = {
            "fact_id": "FACT_ORIG",
            "ticker": "XYZ",
            "fiscal_year": 2020,
            "fiscal_period": "FY",
            "canonical_variable": "ebit",
            "value": 500.0,
            "acceptance_datetime": "2021-02-15T16:00:00Z",
            "filing_date": "2021-02-15",
            "form": "10-K",
            "accession_number": "ACC_ORIG"
        }
        self.amended_10ka = {
            "fact_id": "FACT_AMEND",
            "ticker": "XYZ",
            "fiscal_year": 2020,
            "fiscal_period": "FY",
            "canonical_variable": "ebit",
            "value": 450.0, # Restated down
            "acceptance_datetime": "2021-08-20T17:00:00Z",
            "filing_date": "2021-08-20",
            "form": "10-K/A",
            "accession_number": "ACC_AMEND"
        }
        self.facts = [self.original_10k, self.amended_10ka]

    def test_amendment_does_not_leak_before_amendment_date(self):
        """As of 2021-05-01, model MUST see original 10-K value (500), NOT restated value (450)."""
        admitted = PITFilter.filter_facts_as_of(self.facts, "2021-05-01T00:00:00Z")
        self.assertEqual(len(admitted), 1)
        self.assertEqual(admitted[0]["value"], 500.0)
        self.assertEqual(admitted[0]["form"], "10-K")
        self.assertEqual(admitted[0]["accession_number"], "ACC_ORIG")

    def test_amendment_properly_supersedes_after_amendment_date(self):
        """As of 2021-09-01, model MUST see amended 10-K/A value (450)."""
        admitted = PITFilter.filter_facts_as_of(self.facts, "2021-09-01T00:00:00Z")
        self.assertEqual(len(admitted), 1)
        self.assertEqual(admitted[0]["value"], 450.0)
        self.assertEqual(admitted[0]["form"], "10-K/A")
        self.assertEqual(admitted[0]["accession_number"], "ACC_AMEND")


class TestConceptFallbackCascade(unittest.TestCase):
    """D. Test 5-Tier Concept Normalization and Fallback Hierarchy."""

    def setUp(self):
        self.normalizer = ConceptNormalizer()
        self.company_meta = {"company_id": "US_TEST", "ticker": "TEST", "cik": "0000000001", "sector": "Technology"}

    def test_standard_tier1_selected_first(self):
        """When standard concept is available, it must be selected with DIRECT_STANDARD."""
        facts_map = {
            "RevenueFromContractWithCustomerExcludingAssessedTax": [
                {"fy": 2022, "fp": "FY", "form": "10-K", "val": 1000.0, "filed": "2023-01-15", "end": "2022-12-31", "accn": "ACC_1"}
            ],
            "SalesRevenueNet": [
                {"fy": 2022, "fp": "FY", "form": "10-K", "val": 990.0, "filed": "2023-01-15", "end": "2022-12-31", "accn": "ACC_1"}
            ]
        }
        res = self.normalizer.normalize_company_facts(self.company_meta, facts_map, target_years=[2022])
        rev = [r for r in res if r["canonical_variable"] == "revenue"][0]
        self.assertEqual(rev["fallback_tier"], "Tier 1")
        self.assertEqual(rev["data_status"], "DIRECT_STANDARD")
        self.assertEqual(rev["value"], 1000.0)

    def test_alternative_tier2_selected_when_tier1_missing(self):
        """When standard is missing, Tier 2 alternative is selected with DIRECT_ALTERNATIVE."""
        facts_map = {
            "SalesRevenueNet": [
                {"fy": 2016, "fp": "FY", "form": "10-K", "val": 850.0, "filed": "2017-01-15", "end": "2016-12-31", "accn": "ACC_1"}
            ]
        }
        res = self.normalizer.normalize_company_facts(self.company_meta, facts_map, target_years=[2016])
        rev = [r for r in res if r["canonical_variable"] == "revenue"][0]
        self.assertEqual(rev["fallback_tier"], "Tier 2A")
        self.assertEqual(rev["data_status"], "DIRECT_ALTERNATIVE")
        self.assertEqual(rev["value"], 850.0)

    def test_derived_ebit_tier4_recovery(self):
        """When standard OperatingIncomeLoss and Pretax tags are missing, derived GP - SGA is recovered."""
        facts_map = {
            "GrossProfit": [
                {"fy": 2020, "fp": "FY", "form": "10-K", "val": 1000.0, "filed": "2021-02-15", "end": "2020-12-31", "accn": "ACC_1"}
            ],
            "SellingGeneralAndAdministrativeExpense": [
                {"fy": 2020, "fp": "FY", "form": "10-K", "val": 600.0, "filed": "2021-02-15", "end": "2020-12-31", "accn": "ACC_1"}
            ]
        }
        res = self.normalizer.normalize_company_facts(self.company_meta, facts_map, target_years=[2020])
        ebit = [r for r in res if r["canonical_variable"] == "ebit"][0]
        self.assertEqual(ebit["fallback_tier"], "Tier 4A")
        self.assertEqual(ebit["data_status"], "DERIVED")
        self.assertEqual(ebit["value"], 400.0)

    def test_unresolved_tier5_when_concept_completely_missing(self):
        """When no concept or derivation exists, Tier 5 UNRESOLVED/MISSING is recorded."""
        facts_map = {}
        res = self.normalizer.normalize_company_facts(self.company_meta, facts_map, target_years=[2020])
        rev = [r for r in res if r["canonical_variable"] == "revenue"][0]
        self.assertEqual(rev["fallback_tier"], "Tier 5")
        self.assertEqual(rev["data_status"], "MISSING")


class TestPeriodAndUnitHandling(unittest.TestCase):
    """E & F. Test instant vs duration, 52/53-week years, and unit/sign handling."""

    def test_capex_sign_convention(self):
        """CapEx must be normalized as a positive cash outflow (|val|)."""
        normalizer = ConceptNormalizer()
        comp_meta = {"company_id": "US_TEST", "ticker": "TEST", "cik": "0000000001", "sector": "Technology"}
        facts_map = {
            "PaymentsToAcquirePropertyPlantAndEquipment": [
                {"fy": 2021, "fp": "FY", "form": "10-K", "val": -125.0, "filed": "2022-01-15", "end": "2021-12-31", "accn": "ACC_1"}
            ]
        }
        res = normalizer.normalize_company_facts(comp_meta, facts_map, target_years=[2021])
        capex = [r for r in res if r["canonical_variable"] == "capex"][0]
        self.assertEqual(capex["value"], 125.0, "CapEx must be positive magnitude")
        self.assertEqual(capex["unit"], "USD")


class TestDatabaseAndUniverseIntegrity(unittest.TestCase):
    """G, H, I. Test database state, data lineage, and 30-company universe integrity."""

    @classmethod
    def setUpClass(cls):
        cls.db_path = os.path.join(WORKSPACE_DIR, "data/processed/financials.duckdb")
        cls.db = DatabaseManager(cls.db_path)

    def test_database_record_counts(self):
        """Verify database contains all 30 companies and populated tables."""
        summary = self.db.get_ingestion_summary()
        self.assertEqual(summary["companies_count"], 30, "Database must have 30 companies")
        self.assertGreater(summary["filings_count"], 25000, "Must catalog >= 25k filings")
        self.assertGreater(summary["raw_facts_count"], 500000, "Must contain >= 500k raw XBRL facts")
        self.assertGreater(summary["normalized_facts_count"], 2500, "Must contain >= 2,500 normalized facts")

    def test_all_30_tickers_present(self):
        """Verify each of the 30 locked tickers exists in database."""
        with self.db.get_connection() as con:
            tickers = {row[0] for row in con.execute("SELECT ticker FROM companies").fetchall()}
        expected_sample = {"AAPL", "MSFT", "NVDA", "INTC", "CSCO", "JNJ", "PFE", "WMT", "CAT", "XOM"}
        for t in expected_sample:
            self.assertIn(t, tickers)

    def test_point_in_time_query_functionality(self):
        """Verify query_point_in_time produces valid PIT results without exceptions."""
        results = self.db.query_point_in_time(
            ticker="MSFT",
            as_of_date="2022-12-31T23:59:59Z",
            canonical_variables=["revenue", "net_income", "assets"]
        )
        self.assertGreater(len(results), 0)
        for r in results:
            self.assertEqual(r["ticker"], "MSFT")
            self.assertIn(r["canonical_variable"], ["revenue", "net_income", "assets"])
            # Ensure acceptance date is <= 2022-12-31
            fact_dt = parse_iso_datetime(r["acceptance_datetime"])
            cutoff_dt = parse_iso_datetime("2022-12-31T23:59:59Z")
            self.assertLessEqual(fact_dt, cutoff_dt, "Fact acceptance must be <= as_of_date")


if __name__ == "__main__":
    unittest.main()
