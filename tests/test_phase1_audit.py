"""
Unit tests for Phase 1 Data & Company Universe Audit.
Validates universe integrity, concept mapping completeness, and audit rules.
"""
import unittest
import csv
import os

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class TestPhase1DataUniverseAudit(unittest.TestCase):
    
    def setUp(self):
        self.universe_csv = os.path.join(WORKSPACE_DIR, 'results/tables/phase1_universe_audit.csv')
        self.concept_csv = os.path.join(WORKSPACE_DIR, 'results/tables/phase1_concept_mapping.csv')
        self.coverage_csv = os.path.join(WORKSPACE_DIR, 'results/tables/phase1_coverage_matrix.csv')
        
    def test_universe_completeness_and_uniqueness(self):
        """Verify exactly 30 unique companies, valid 10-digit CIKs, and valid sectors."""
        self.assertTrue(os.path.exists(self.universe_csv), "Universe CSV must exist")
        with open(self.universe_csv, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        self.assertEqual(len(rows), 30, "Universe must contain exactly 30 companies")
        tickers = [r['ticker'] for r in rows]
        self.assertEqual(len(tickers), len(set(tickers)), "All tickers must be unique")
        
        ciks = [r['cik'] for r in rows]
        self.assertEqual(len(ciks), len(set(ciks)), "All CIKs must be unique")
        for cik in ciks:
            self.assertEqual(len(cik), 10, f"CIK {cik} must be zero-padded to 10 digits")
            self.assertTrue(cik.isdigit(), f"CIK {cik} must be numeric")
            
        allowed_sectors = {
            'Information Technology',
            'Health Care',
            'Consumer Staples',
            'Consumer Discretionary',
            'Industrials',
            'Energy'
        }
        for r in rows:
            self.assertIn(r['sector'], allowed_sectors, f"Sector {r['sector']} must be non-financial")

    def test_concept_mapping_integrity(self):
        """Verify fallback mappings have valid tiers, units, and rationales."""
        self.assertTrue(os.path.exists(self.concept_csv), "Concept mapping CSV must exist")
        with open(self.concept_csv, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            
        canonical_vars = {r['canonical_variable'] for r in rows}
        required_vars = {
            'revenue', 'ebit', 'net_income', 'cash', 'debt_long',
            'assets', 'equity', 'cfo', 'capex', 'da'
        }
        for var in required_vars:
            self.assertIn(var, canonical_vars, f"Canonical variable {var} must have mapped concepts")
            
        for r in rows:
            self.assertTrue(r['fallback_tier'].startswith('Tier'), f"Tier {r['fallback_tier']} must be valid")
            self.assertEqual(r['unit'], 'USD', f"Unit must be USD for financial amounts")
            self.assertTrue(len(r['economic_rationale']) > 10, "Economic rationale must be detailed")

    def test_coverage_matrix_thresholds(self):
        """Verify coverage matrix has 30 rows and passes minimum recovery thresholds."""
        self.assertTrue(os.path.exists(self.coverage_csv), "Coverage matrix CSV must exist")
        with open(self.coverage_csv, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            
        self.assertEqual(len(rows), 30, "Coverage matrix must evaluate all 30 firms")
        for r in rows:
            self.assertEqual(r['min_year'], '2014')
            self.assertEqual(r['max_year'], '2024')
            usable = int(r['usable_years'])
            self.assertGreaterEqual(usable, 7, f"Company {r['ticker']} must have at least 7 usable years")
            self.assertEqual(r['status'], 'PASS')

if __name__ == '__main__':
    unittest.main()
