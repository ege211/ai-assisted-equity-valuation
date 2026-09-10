"""
Fetch and cache SEC EDGAR submissions metadata for all 30 companies.
Provides exact acceptanceDateTime, reportDate, and accession catalog.
"""
import os
import sys
import yaml

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, WORKSPACE_DIR)

from src.data.sec_client import SECClient

CONFIG_PATH = os.path.join(WORKSPACE_DIR, "config/universe.yaml")
CACHE_DIR = os.path.join(WORKSPACE_DIR, "data/raw_sec")

def main():
    print("Loading universe configuration...")
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        conf = yaml.safe_load(f)

    universe = conf.get("universe", [])
    print(f"Loaded {len(universe)} companies from {CONFIG_PATH}")

    client = SECClient(cache_dir=CACHE_DIR)
    for comp in universe:
        ticker = comp["ticker"]
        cik = comp["cik"]
        print(f"Fetching submissions for {ticker} (CIK {cik})...")
        try:
            sub = client.get_company_submissions(cik)
            n_filings = len(sub.get("filings", {}).get("recent", {}).get("accessionNumber", []))
            print(f"  OK: {ticker} has {n_filings} recent filings cataloged.")
        except Exception as e:
            print(f"  ERROR for {ticker}: {e}")

    print("Submissions ingestion completed.")

if __name__ == "__main__":
    main()
