"""
Phase 3 Comprehensive Unit Test Suite.

Verifies Criteria A through Y:
A. Q1 YTD -> standalone Q1
B. Q2 YTD - Q1 YTD -> standalone Q2
C. Q3 YTD - Q2 YTD -> standalone Q3
D. Annual financials
E. 52-week fiscal year
F. 53-week fiscal year
G. Missing previous YTD
H. Incompatible periods
I. Unit mismatch
J. LTM four-quarter calculation
K. LTM annual-plus-YTD calculation / consistency
L. Point-in-time filtering
M. Amendment handling
N. Restatement protection
O. NOPAT calculation
P. Effective tax rate edge cases
Q. ROIC calculation & Invested Capital averaging
R. Working capital & Operating Working Capital
S. Operating margins
T. Historical growth metrics
U. Free Cash Flow (FCF)
V. Net Debt
W. Zero/negative denominators
X. Lineage traceability
Y. All 30 companies in DuckDB
"""
import os
import unittest

from src.data.db import DatabaseManager
from src.normalization.concept_normalizer import ConceptNormalizer
from src.normalization.quarterly_engine import QuarterlyEngine, get_duration_days
from src.normalization.ltm_engine import LTMEngine
from src.normalization.feature_engine import FeatureEngine
from src.normalization.pit_filter import PITFilter


class TestPhase3Features(unittest.TestCase):
    """Test suite covering requirements A through Y for Phase 3."""

    def setUp(self) -> None:
        self.engine = QuarterlyEngine()
        self.db = DatabaseManager()

    # Test A: Q1 YTD -> standalone Q1
    def test_A_q1_ytd_to_standalone_q1(self) -> None:
        comp_meta = {"ticker": "TEST", "cik": "0000000001", "sector": "Technology"}
        raw_facts = [
            {
                "fact_id": "f1", "concept": "RevenueFromContractWithCustomerExcludingAssessedTax",
                "fiscal_year": 2023, "fiscal_period": "Q1", "form": "10-Q", "unit": "USD",
                "val": 100.0, "start_date": "2023-01-01", "end_date": "2023-03-31",
                "filing_date": "2023-04-15", "accession_number": "ACC-01"
            }
        ]
        q_stmts, _ = self.engine.process_company(comp_meta, raw_facts, {}, [2023])
        q1 = next((q for q in q_stmts if q["fiscal_quarter"] == "Q1"), None)
        self.assertIsNotNone(q1)
        self.assertEqual(q1["revenue"], 100.0)
        self.assertEqual(q1["deaccumulation_status"], "DIRECT_STANDARD")

    # Test B: Q2 YTD - Q1 YTD -> standalone Q2
    def test_B_q2_ytd_minus_q1_ytd(self) -> None:
        comp_meta = {"ticker": "TEST", "cik": "0000000001", "sector": "Technology"}
        raw_facts = [
            {
                "fact_id": "f1", "concept": "NetCashProvidedByUsedInOperatingActivities",
                "fiscal_year": 2023, "fiscal_period": "Q1", "form": "10-Q", "unit": "USD",
                "val": 100.0, "start_date": "2023-01-01", "end_date": "2023-03-31",
                "filing_date": "2023-04-15", "accession_number": "ACC-01"
            },
            {
                "fact_id": "f2", "concept": "NetCashProvidedByUsedInOperatingActivities",
                "fiscal_year": 2023, "fiscal_period": "Q2", "form": "10-Q", "unit": "USD",
                "val": 230.0, "start_date": "2023-01-01", "end_date": "2023-06-30", # 6m YTD
                "filing_date": "2023-07-15", "accession_number": "ACC-02"
            }
        ]
        q_stmts, _ = self.engine.process_company(comp_meta, raw_facts, {}, [2023])
        q2 = next((q for q in q_stmts if q["fiscal_quarter"] == "Q2"), None)
        self.assertIsNotNone(q2)
        self.assertEqual(q2["cfo"], 130.0) # 230 - 100 = 130
        self.assertTrue(q2["is_derived_quarter"])
        self.assertIn("Q2_YTD - Q1_YTD", q2["deaccumulation_status"])

    # Test C: Q3 YTD - Q2 YTD -> standalone Q3
    def test_C_q3_ytd_minus_q2_ytd(self) -> None:
        comp_meta = {"ticker": "TEST", "cik": "0000000001", "sector": "Technology"}
        raw_facts = [
            {
                "fact_id": "f1", "concept": "NetCashProvidedByUsedInOperatingActivities",
                "fiscal_year": 2023, "fiscal_period": "Q2", "form": "10-Q", "unit": "USD",
                "val": 230.0, "start_date": "2023-01-01", "end_date": "2023-06-30",
                "filing_date": "2023-07-15", "accession_number": "ACC-02"
            },
            {
                "fact_id": "f2", "concept": "NetCashProvidedByUsedInOperatingActivities",
                "fiscal_year": 2023, "fiscal_period": "Q3", "form": "10-Q", "unit": "USD",
                "val": 360.0, "start_date": "2023-01-01", "end_date": "2023-09-30", # 9m YTD
                "filing_date": "2023-10-15", "accession_number": "ACC-03"
            }
        ]
        q_stmts, _ = self.engine.process_company(comp_meta, raw_facts, {}, [2023])
        q3 = next((q for q in q_stmts if q["fiscal_quarter"] == "Q3"), None)
        self.assertIsNotNone(q3)
        self.assertEqual(q3["cfo"], 130.0) # 360 - 230 = 130
        self.assertTrue(q3["is_derived_quarter"])
        self.assertIn("Q3_YTD - Q2_YTD", q3["deaccumulation_status"])

    # Test D: Annual financials normalization
    def test_D_annual_financials(self) -> None:
        comp_meta = {"ticker": "TEST", "cik": "0000000001", "sector": "Technology"}
        raw_facts = [
            {
                "fact_id": "f1", "concept": "RevenueFromContractWithCustomerExcludingAssessedTax",
                "fiscal_year": 2023, "fiscal_period": "FY", "form": "10-K", "unit": "USD",
                "val": 1000.0, "start_date": "2023-01-01", "end_date": "2023-12-31",
                "filing_date": "2024-02-15", "accession_number": "ACC-10K"
            },
            {
                "fact_id": "f2", "concept": "Assets",
                "fiscal_year": 2023, "fiscal_period": "FY", "form": "10-K", "unit": "USD",
                "val": 5000.0, "start_date": "2023-12-31", "end_date": "2023-12-31",
                "is_instant": True, "filing_date": "2024-02-15", "accession_number": "ACC-10K"
            }
        ]
        _, ann_stmts = self.engine.process_company(comp_meta, raw_facts, {}, [2023])
        self.assertEqual(len(ann_stmts), 1)
        self.assertEqual(ann_stmts[0]["revenue"], 1000.0)
        self.assertEqual(ann_stmts[0]["total_assets"], 5000.0)
        self.assertEqual(ann_stmts[0]["fiscal_period"], "FY")

    # Test E: 52-week fiscal year
    def test_E_52_week_fiscal_year(self) -> None:
        # 52 weeks = 364 days
        days = get_duration_days("2023-01-01", "2023-12-31")
        self.assertEqual(days, 364)
        comp_meta = {"ticker": "TEST52", "cik": "0000000002", "sector": "Retail"}
        raw_facts = [
            {
                "fact_id": "f1", "concept": "RevenueFromContractWithCustomerExcludingAssessedTax",
                "fiscal_year": 2023, "fiscal_period": "FY", "form": "10-K", "unit": "USD",
                "val": 800.0, "start_date": "2023-01-01", "end_date": "2023-12-31",
                "filing_date": "2024-02-10", "accession_number": "ACC-52"
            }
        ]
        _, ann = self.engine.process_company(comp_meta, raw_facts, {}, [2023])
        self.assertEqual(len(ann), 1)
        self.assertEqual(ann[0]["revenue"], 800.0)

    # Test F: 53-week fiscal year
    def test_F_53_week_fiscal_year(self) -> None:
        # 53 weeks = 371 days
        days = get_duration_days("2022-01-30", "2023-02-05")
        self.assertEqual(days, 371)
        comp_meta = {"ticker": "TEST53", "cik": "0000000003", "sector": "Retail"}
        raw_facts = [
            {
                "fact_id": "f1", "concept": "RevenueFromContractWithCustomerExcludingAssessedTax",
                "fiscal_year": 2023, "fiscal_period": "FY", "form": "10-K", "unit": "USD",
                "val": 950.0, "start_date": "2022-01-30", "end_date": "2023-02-05",
                "filing_date": "2023-03-25", "accession_number": "ACC-53"
            }
        ]
        _, ann = self.engine.process_company(comp_meta, raw_facts, {}, [2023])
        self.assertEqual(len(ann), 1)
        self.assertEqual(ann[0]["revenue"], 950.0)

    # Test G: Missing previous YTD -> UNRESOLVED
    def test_G_missing_previous_ytd(self) -> None:
        comp_meta = {"ticker": "TESTG", "cik": "0000000004", "sector": "Technology"}
        # Q2 YTD exists, but Q1 YTD is missing
        raw_facts = [
            {
                "fact_id": "f2", "concept": "NetCashProvidedByUsedInOperatingActivities",
                "fiscal_year": 2023, "fiscal_period": "Q2", "form": "10-Q", "unit": "USD",
                "val": 250.0, "start_date": "2023-01-01", "end_date": "2023-06-30",
                "filing_date": "2023-07-15", "accession_number": "ACC-02"
            }
        ]
        q_stmts, _ = self.engine.process_company(comp_meta, raw_facts, {}, [2023])
        q2 = next((q for q in q_stmts if q["fiscal_quarter"] == "Q2"), None)
        # Because Q1 YTD is missing and no 3-month standalone exists, cfo must be None
        if q2:
            self.assertIsNone(q2["cfo"])

    # Test H: Incompatible periods
    def test_H_incompatible_periods(self) -> None:
        # Duration negative or zero
        days = get_duration_days("2023-06-30", "2023-01-01")
        self.assertEqual(days, 0)

    # Test I: Unit mismatch rejection
    def test_I_unit_mismatch(self) -> None:
        comp_meta = {"ticker": "TESTI", "cik": "0000000005", "sector": "Technology"}
        raw_facts = [
            {
                "fact_id": "f1", "concept": "RevenueFromContractWithCustomerExcludingAssessedTax",
                "fiscal_year": 2023, "fiscal_period": "Q1", "form": "10-Q", "unit": "EUR", # Non-USD unit
                "val": 100.0, "start_date": "2023-01-01", "end_date": "2023-03-31",
                "filing_date": "2023-04-15", "accession_number": "ACC-01"
            }
        ]
        q_stmts, _ = self.engine.process_company(comp_meta, raw_facts, {}, [2023])
        q1 = next((q for q in q_stmts if q["fiscal_quarter"] == "Q1"), None)
        self.assertIsNone(q1) # Rejected due to non-USD unit

    # Test J: LTM four-quarter calculation
    def test_J_ltm_four_quarter_calculation(self) -> None:
        q_stmts = [
            {"ticker": "TST", "company_id": "US_TST", "cik": "1", "sector": "Tech",
             "fiscal_year": 2023, "fiscal_quarter": "Q1", "period_end_date": "2023-03-31",
             "revenue": 100.0, "cfo": 30.0, "capex": 10.0, "total_assets": 1000.0, "acceptance_datetime": "2023-04-15T00:00:00Z"},
            {"ticker": "TST", "company_id": "US_TST", "cik": "1", "sector": "Tech",
             "fiscal_year": 2023, "fiscal_quarter": "Q2", "period_end_date": "2023-06-30",
             "revenue": 120.0, "cfo": 40.0, "capex": 15.0, "total_assets": 1050.0, "acceptance_datetime": "2023-07-15T00:00:00Z"},
            {"ticker": "TST", "company_id": "US_TST", "cik": "1", "sector": "Tech",
             "fiscal_year": 2023, "fiscal_quarter": "Q3", "period_end_date": "2023-09-30",
             "revenue": 130.0, "cfo": 45.0, "capex": 15.0, "total_assets": 1100.0, "acceptance_datetime": "2023-10-15T00:00:00Z"},
            {"ticker": "TST", "company_id": "US_TST", "cik": "1", "sector": "Tech",
             "fiscal_year": 2023, "fiscal_quarter": "Q4", "period_end_date": "2023-12-31",
             "revenue": 150.0, "cfo": 60.0, "capex": 20.0, "total_assets": 1200.0, "acceptance_datetime": "2024-02-15T00:00:00Z"},
        ]
        ltm = LTMEngine.generate_ltm_statements(q_stmts)
        self.assertEqual(len(ltm), 1)
        self.assertEqual(ltm[0]["revenue"], 500.0) # 100 + 120 + 130 + 150
        self.assertEqual(ltm[0]["cfo"], 175.0)     # 30 + 40 + 45 + 60
        self.assertEqual(ltm[0]["capex"], 60.0)    # 10 + 15 + 15 + 20
        self.assertEqual(ltm[0]["fcf"], 115.0)      # 175 - 60
        self.assertEqual(ltm[0]["total_assets"], 1200.0) # Balance sheet from latest quarter
        self.assertEqual(ltm[0]["acceptance_datetime"], "2024-02-15T00:00:00Z") # Max acceptance datetime

    # Test K: LTM annual-plus-YTD consistency
    def test_K_ltm_annual_plus_ytd_reconciliation(self) -> None:
        # Sum of 4 quarters for Q4 LTM matches the annual statement
        q_stmts = [
            {"ticker": "TST", "company_id": "US_TST", "cik": "1", "sector": "Tech",
             "fiscal_year": 2023, "fiscal_quarter": "Q1", "period_end_date": "2023-03-31",
             "revenue": 250.0, "acceptance_datetime": "2023-04-15T00:00:00Z"},
            {"ticker": "TST", "company_id": "US_TST", "cik": "1", "sector": "Tech",
             "fiscal_year": 2023, "fiscal_quarter": "Q2", "period_end_date": "2023-06-30",
             "revenue": 250.0, "acceptance_datetime": "2023-07-15T00:00:00Z"},
            {"ticker": "TST", "company_id": "US_TST", "cik": "1", "sector": "Tech",
             "fiscal_year": 2023, "fiscal_quarter": "Q3", "period_end_date": "2023-09-30",
             "revenue": 250.0, "acceptance_datetime": "2023-10-15T00:00:00Z"},
            {"ticker": "TST", "company_id": "US_TST", "cik": "1", "sector": "Tech",
             "fiscal_year": 2023, "fiscal_quarter": "Q4", "period_end_date": "2023-12-31",
             "revenue": 250.0, "acceptance_datetime": "2024-02-15T00:00:00Z"},
        ]
        ltm = LTMEngine.generate_ltm_statements(q_stmts)
        self.assertEqual(ltm[0]["revenue"], 1000.0)

    # Test L: Point-in-time filtering
    def test_L_point_in_time_filtering(self) -> None:
        facts = [
            {"ticker": "AAPL", "acceptance_datetime": "2023-02-01T12:00:00Z", "fiscal_year": 2022, "fiscal_period": "FY", "canonical_variable": "revenue", "value": 100.0},
            {"ticker": "AAPL", "acceptance_datetime": "2023-05-01T12:00:00Z", "fiscal_year": 2023, "fiscal_period": "Q1", "canonical_variable": "revenue", "value": 110.0},
        ]
        # Query as of 2023-03-01: Q1 fact must be excluded
        pit = PITFilter.filter_facts_as_of(facts, "2023-03-01T00:00:00Z")
        self.assertEqual(len(pit), 1)
        self.assertEqual(pit[0]["fiscal_period"], "FY")

    # Test M: Amendment handling
    def test_M_amendment_handling(self) -> None:
        facts = [
            {"ticker": "AAPL", "form": "10-K", "acceptance_datetime": "2023-02-01T12:00:00Z", "fiscal_year": 2022, "fiscal_period": "FY", "canonical_variable": "revenue", "value": 100.0},
            {"ticker": "AAPL", "form": "10-K/A", "acceptance_datetime": "2023-03-01T12:00:00Z", "fiscal_year": 2022, "fiscal_period": "FY", "canonical_variable": "revenue", "value": 102.0},
        ]
        # Query as of 2023-04-01: amendment supersedes original
        pit = PITFilter.filter_facts_as_of(facts, "2023-04-01T00:00:00Z")
        self.assertEqual(len(pit), 1)
        self.assertEqual(pit[0]["value"], 102.0)
        self.assertEqual(pit[0]["form"], "10-K/A")

    # Test N: Restatement protection
    def test_N_restatement_protection(self) -> None:
        facts = [
            {"ticker": "AAPL", "form": "10-K", "acceptance_datetime": "2023-02-01T12:00:00Z", "fiscal_year": 2022, "fiscal_period": "FY", "canonical_variable": "revenue", "value": 100.0},
            {"ticker": "AAPL", "form": "10-K/A", "acceptance_datetime": "2024-01-01T12:00:00Z", "fiscal_year": 2022, "fiscal_period": "FY", "canonical_variable": "revenue", "value": 102.0},
        ]
        # As of 2023-06-01, amendment has NOT happened yet. Must see only original 100.0!
        pit = PITFilter.filter_facts_as_of(facts, "2023-06-01T00:00:00Z")
        self.assertEqual(len(pit), 1)
        self.assertEqual(pit[0]["value"], 100.0)
        self.assertEqual(pit[0]["form"], "10-K")

    # Test O: NOPAT calculation
    def test_O_nopat_calculation(self) -> None:
        ltm = [{
            "ticker": "TST", "company_id": "US_TST", "cik": "1", "sector": "Tech",
            "as_of_fiscal_year": 2023, "as_of_fiscal_quarter": "Q4", "period_end_date": "2023-12-31",
            "acceptance_datetime": "2024-02-15T00:00:00Z", "constituent_quarters": "2023Q1+2023Q2+2023Q3+2023Q4",
            "constituent_accessions": "A1,A2,A3,A4", "ebit": 100.0, "pretax_income": 100.0, "tax_expense": 20.0,
        }]
        feats = FeatureEngine.compute_all_features([], [], ltm)
        nopat = next((f for f in feats if f["feature_name"] == "nopat"), None)
        self.assertIsNotNone(nopat)
        # Tax rate = 20 / 100 = 20% (0.20), NOPAT = 100 * (1 - 0.20) = 80.0
        self.assertAlmostEqual(nopat["feature_value"], 80.0, places=2)

    # Test P: Effective tax rate edge cases
    def test_P_effective_tax_rate_edge_cases(self) -> None:
        # Case 1: Pre-tax <= 0 -> statutory fallback (21% for 2023)
        ltm_neg = [{
            "ticker": "TST", "company_id": "US_TST", "cik": "1", "sector": "Tech",
            "as_of_fiscal_year": 2023, "as_of_fiscal_quarter": "Q4", "period_end_date": "2023-12-31",
            "acceptance_datetime": "2024-02-15T00:00:00Z", "constituent_quarters": "Q1+Q2+Q3+Q4",
            "constituent_accessions": "A1", "ebit": -50.0, "pretax_income": -60.0, "tax_expense": 5.0,
        }]
        feats = FeatureEngine.compute_all_features([], [], ltm_neg)
        tax = next((f for f in feats if f["feature_name"] == "normalized_tax_rate"), None)
        self.assertIsNotNone(tax)
        self.assertEqual(tax["feature_value"], 0.21)

        # Case 2: Abnormal rate > 50% -> statutory fallback (21%)
        ltm_high = [{
            "ticker": "TST", "company_id": "US_TST", "cik": "1", "sector": "Tech",
            "as_of_fiscal_year": 2023, "as_of_fiscal_quarter": "Q4", "period_end_date": "2023-12-31",
            "acceptance_datetime": "2024-02-15T00:00:00Z", "constituent_quarters": "Q1+Q2+Q3+Q4",
            "constituent_accessions": "A1", "ebit": 100.0, "pretax_income": 10.0, "tax_expense": 8.0, # 80% rate
        }]
        feats_high = FeatureEngine.compute_all_features([], [], ltm_high)
        tax_high = next((f for f in feats_high if f["feature_name"] == "normalized_tax_rate"), None)
        self.assertEqual(tax_high["feature_value"], 0.21)

    # Test Q: ROIC calculation & Invested Capital averaging
    def test_Q_roic_calculation(self) -> None:
        ltm_stmts = [
            {"ticker": "TST", "company_id": "US_TST", "cik": "1", "sector": "Tech",
             "as_of_fiscal_year": 2022, "as_of_fiscal_quarter": "Q4", "period_end_date": "2022-12-31",
             "acceptance_datetime": "2023-02-15T00:00:00Z", "constituent_quarters": "Q1+Q2+Q3+Q4",
             "constituent_accessions": "A1", "ebit": 100.0, "pretax_income": 100.0, "tax_expense": 20.0,
             "total_assets": 1000.0, "current_liabilities": 200.0, "cash": 100.0, "debt_current": 0.0},
            {"ticker": "TST", "company_id": "US_TST", "cik": "1", "sector": "Tech",
             "as_of_fiscal_year": 2023, "as_of_fiscal_quarter": "Q4", "period_end_date": "2023-12-31",
             "acceptance_datetime": "2024-02-15T00:00:00Z", "constituent_quarters": "Q1+Q2+Q3+Q4",
             "constituent_accessions": "A2", "ebit": 120.0, "pretax_income": 120.0, "tax_expense": 24.0,
             "total_assets": 1200.0, "current_liabilities": 250.0, "cash": 150.0, "debt_current": 0.0}
        ]
        feats = FeatureEngine.compute_all_features([], [], ltm_stmts)
        roic = next((f for f in feats if f["feature_name"] == "roic" and f["fiscal_year"] == 2023), None)
        self.assertIsNotNone(roic)
        # 2022 IC = 1000 - 100 - 200 = 700
        # 2023 IC = 1200 - 150 - 250 = 800
        # Average IC = (700 + 800) / 2 = 750
        # 2023 NOPAT = 120 * (1 - 0.20) = 96.0
        # ROIC = 96 / 750 = 12.8%
        self.assertAlmostEqual(roic["feature_value"], 0.128, places=3)

    # Test R: Working capital & Operating Working Capital
    def test_R_working_capital(self) -> None:
        ltm = [{
            "ticker": "TST", "company_id": "US_TST", "cik": "1", "sector": "Tech",
            "as_of_fiscal_year": 2023, "as_of_fiscal_quarter": "Q4", "period_end_date": "2023-12-31",
            "acceptance_datetime": "2024-02-15T00:00:00Z", "constituent_quarters": "Q1+Q2+Q3+Q4",
            "constituent_accessions": "A1", "revenue": 1000.0, "current_assets": 500.0,
            "current_liabilities": 300.0, "cash": 100.0, "debt_current": 50.0,
        }]
        feats = FeatureEngine.compute_all_features([], [], ltm)
        wc = next((f for f in feats if f["feature_name"] == "working_capital"), None)
        owc = next((f for f in feats if f["feature_name"] == "operating_working_capital"), None)
        self.assertIsNotNone(wc)
        self.assertIsNotNone(owc)
        self.assertEqual(wc["feature_value"], 200.0) # 500 - 300 = 200
        # OWC = (500 - 100) - (300 - 50) = 400 - 250 = 150
        self.assertEqual(owc["feature_value"], 150.0)

    # Test S: Operating margins
    def test_S_margins(self) -> None:
        ltm = [{
            "ticker": "TST", "company_id": "US_TST", "cik": "1", "sector": "Tech",
            "as_of_fiscal_year": 2023, "as_of_fiscal_quarter": "Q4", "period_end_date": "2023-12-31",
            "acceptance_datetime": "2024-02-15T00:00:00Z", "constituent_quarters": "Q1+Q2+Q3+Q4",
            "constituent_accessions": "A1", "revenue": 1000.0, "gross_profit": 600.0,
            "ebit": 300.0, "net_income": 200.0, "cfo": 250.0, "capex": 50.0, "fcf": 200.0
        }]
        feats = FeatureEngine.compute_all_features([], [], ltm)
        gm = next((f for f in feats if f["feature_name"] == "gross_margin"), None)
        em = next((f for f in feats if f["feature_name"] == "ebit_margin"), None)
        nm = next((f for f in feats if f["feature_name"] == "net_margin"), None)
        fcfm = next((f for f in feats if f["feature_name"] == "fcf_margin"), None)
        self.assertEqual(gm["feature_value"], 0.60)
        self.assertEqual(em["feature_value"], 0.30)
        self.assertEqual(nm["feature_value"], 0.20)
        self.assertEqual(fcfm["feature_value"], 0.20)

    # Test T: Historical growth metrics
    def test_T_growth(self) -> None:
        ltm_stmts = [
            {"ticker": "TST", "company_id": "US_TST", "cik": "1", "sector": "Tech",
             "as_of_fiscal_year": 2022, "as_of_fiscal_quarter": "Q4", "period_end_date": "2022-12-31",
             "acceptance_datetime": "2023-02-15T00:00:00Z", "constituent_quarters": "Q1+Q2+Q3+Q4",
             "constituent_accessions": "A1", "revenue": 1000.0, "ebit": 200.0},
            {"ticker": "TST", "company_id": "US_TST", "cik": "1", "sector": "Tech",
             "as_of_fiscal_year": 2023, "as_of_fiscal_quarter": "Q4", "period_end_date": "2023-12-31",
             "acceptance_datetime": "2024-02-15T00:00:00Z", "constituent_quarters": "Q1+Q2+Q3+Q4",
             "constituent_accessions": "A2", "revenue": 1150.0, "ebit": 250.0},
        ]
        feats = FeatureEngine.compute_all_features([], [], ltm_stmts)
        rev_g = next((f for f in feats if f["feature_name"] == "revenue_growth_yoy" and f["fiscal_year"] == 2023), None)
        ebit_g = next((f for f in feats if f["feature_name"] == "ebit_growth_yoy" and f["fiscal_year"] == 2023), None)
        self.assertAlmostEqual(rev_g["feature_value"], 0.15, places=2)  # (1150 / 1000) - 1 = 15%
        self.assertAlmostEqual(ebit_g["feature_value"], 0.25, places=2) # (250 - 200) / 200 = 25%

    # Test U: Free Cash Flow (CFO - CapEx)
    def test_U_fcf_calculation(self) -> None:
        comp_meta = {"ticker": "TST", "cik": "0000000001", "sector": "Tech"}
        raw_facts = [
            {"fact_id": "f1", "concept": "NetCashProvidedByUsedInOperatingActivities", "fiscal_year": 2023, "fiscal_period": "FY", "form": "10-K", "unit": "USD", "val": 500.0, "start_date": "2023-01-01", "end_date": "2023-12-31", "filing_date": "2024-02-15", "accession_number": "ACC-1"},
            {"fact_id": "f2", "concept": "PaymentsToAcquirePropertyPlantAndEquipment", "fiscal_year": 2023, "fiscal_period": "FY", "form": "10-K", "unit": "USD", "val": 150.0, "start_date": "2023-01-01", "end_date": "2023-12-31", "filing_date": "2024-02-15", "accession_number": "ACC-1"},
        ]
        _, ann = self.engine.process_company(comp_meta, raw_facts, {}, [2023])
        self.assertEqual(ann[0]["cfo"], 500.0)
        self.assertEqual(ann[0]["capex"], 150.0)
        self.assertEqual(ann[0]["fcf"], 350.0) # 500 - 150 = 350

    # Test V: Net Debt (Total Debt - Cash)
    def test_V_net_debt(self) -> None:
        comp_meta = {"ticker": "TST", "cik": "0000000001", "sector": "Tech"}
        raw_facts = [
            {"fact_id": "f1", "concept": "LongTermDebtNoncurrent", "fiscal_year": 2023, "fiscal_period": "FY", "form": "10-K", "unit": "USD", "val": 800.0, "start_date": "2023-12-31", "end_date": "2023-12-31", "is_instant": True, "filing_date": "2024-02-15", "accession_number": "ACC-1"},
            {"fact_id": "f2", "concept": "LongTermDebtCurrent", "fiscal_year": 2023, "fiscal_period": "FY", "form": "10-K", "unit": "USD", "val": 200.0, "start_date": "2023-12-31", "end_date": "2023-12-31", "is_instant": True, "filing_date": "2024-02-15", "accession_number": "ACC-1"},
            {"fact_id": "f3", "concept": "CashAndCashEquivalentsAtCarryingValue", "fiscal_year": 2023, "fiscal_period": "FY", "form": "10-K", "unit": "USD", "val": 300.0, "start_date": "2023-12-31", "end_date": "2023-12-31", "is_instant": True, "filing_date": "2024-02-15", "accession_number": "ACC-1"},
        ]
        _, ann = self.engine.process_company(comp_meta, raw_facts, {}, [2023])
        feats = FeatureEngine.compute_all_features([], ann, [])
        nd = next((f for f in feats if f["feature_name"] == "net_debt"), None)
        self.assertIsNotNone(nd)
        # Total debt = 800 + 200 = 1000; Net Debt = 1000 - 300 = 700
        self.assertEqual(nd["feature_value"], 700.0)

    # Test W: Zero/negative denominators
    def test_W_zero_negative_denominators(self) -> None:
        ltm_zero_rev = [{
            "ticker": "TST", "company_id": "US_TST", "cik": "1", "sector": "Tech",
            "as_of_fiscal_year": 2023, "as_of_fiscal_quarter": "Q4", "period_end_date": "2023-12-31",
            "acceptance_datetime": "2024-02-15T00:00:00Z", "constituent_quarters": "Q1+Q2+Q3+Q4",
            "constituent_accessions": "A1", "revenue": 0.0, "gross_profit": 50.0,
            "ebit": 10.0, "invested_capital": -100.0, "average_invested_capital": -100.0
        }]
        feats = FeatureEngine.compute_all_features([], [], ltm_zero_rev)
        gm = next((f for f in feats if f["feature_name"] == "gross_margin"), None)
        roic = next((f for f in feats if f["feature_name"] == "roic"), None)
        self.assertIsNone(gm["feature_value"])
        self.assertEqual(gm["data_status"], "UNRESOLVED")
        self.assertIsNone(roic["feature_value"]) # Negative IC -> UNRESOLVED
        self.assertEqual(roic["data_status"], "UNRESOLVED")

    # Test X: Lineage traceability
    def test_X_lineage(self) -> None:
        with self.db.get_connection() as con:
            sample = con.execute("""
                SELECT feature_name, calculation_method, source_periods, source_accessions, data_status
                FROM financial_features
                WHERE ticker = 'AAPL' AND feature_value IS NOT NULL
                LIMIT 5
            """).fetchall()
            self.assertEqual(len(sample), 5)
            for row in sample:
                self.assertTrue(len(row[1]) > 0) # calculation_method populated
                self.assertTrue(len(row[2]) > 0) # source_periods populated
                self.assertTrue(len(row[3]) > 0) # source_accessions populated
                self.assertIn(row[4], ["DIRECT_STANDARD", "DERIVED"])

    # Test Y: All 30 companies populated across all 4 Phase 3 tables
    def test_Y_all_30_companies(self) -> None:
        with self.db.get_connection() as con:
            comp_count = con.execute("SELECT COUNT(DISTINCT ticker) FROM quarterly_financials").fetchone()[0]
            self.assertEqual(comp_count, 30)

            ann_count = con.execute("SELECT COUNT(DISTINCT ticker) FROM annual_financials").fetchone()[0]
            self.assertEqual(ann_count, 30)

            ltm_count = con.execute("SELECT COUNT(DISTINCT ticker) FROM ltm_financials").fetchone()[0]
            self.assertEqual(ltm_count, 30)

            feat_count = con.execute("SELECT COUNT(DISTINCT ticker) FROM financial_features").fetchone()[0]
            self.assertEqual(feat_count, 30)

            total_features = con.execute("SELECT COUNT(*) FROM financial_features").fetchone()[0]
            self.assertGreater(total_features, 30000)


if __name__ == "__main__":
    unittest.main()
