# Documentation Index: AI-Assisted Equity Valuation & Investment Intelligence Platform

Welcome to the documentation index for the **AI-Assisted Equity Valuation & Investment Intelligence Platform**. This index provides a structured roadmap across the research paper, technical reproducibility manual, data lineage documentation, and experiment registry.

---

## 1. Research & Reproducibility Package

* [**Academic Research Paper**](RESEARCH_PAPER.md): Complete academic working paper: *Empirical Limits of Textual Intelligence in Structural Equity Valuation: An Out-of-Sample Walk-Forward Study on SEC 10-K Filings*. Covers the theoretical framework, 5-tier XBRL cascade, deterministic DCF formulation, 12 pre-specified linguistic dimensions, walk-forward econometric evaluation ($N=46$ complete cases, 2 folds), feature ablations, and Appendices A–F.
* [**Reproducibility Guide**](REPRODUCIBILITY_GUIDE.md): Step-by-step CLI reproduction instructions, prerequisites, full unit test suite execution (260/260 passing), pipeline sequence, Streamlit dashboard launch, and cryptographic checksum verification.
* [**Experiment Registry**](EXPERIMENT_REGISTRY.md): Comprehensive registry of all empirical experiments (`EXP-P6-CROSSSECTIONAL`, `EXP-P7-PANEL-PRIMARY`, `EXP-P7-PANEL-SECONDARY`, `EXP-P7-PANEL-BINARY`, `EXP-P7-ABLATION`, `EXP-P7-ROBUSTNESS`, `EXP-P5-FILING-EVIDENCE`).
* [**Data Provenance & Lineage Architecture**](DATA_PROVENANCE.md): Data origin documentation, tri-temporal coordinate system (`period_end_date`, `filing_date`, `acceptance_datetime`), point-in-time filtering rules (`acceptance_datetime <= cutoff 23:59:59`), DuckDB relational schema, and XBRL fallback logic.

---

## 2. Research Transparency Note
As an independent high school student researcher, I designed the evaluation framework, curated the 30-firm SEC dataset, and formulated the empirical econometric questions. AI tools were used for code debugging, data pipeline structuring, and editorial formatting. All empirical analyses, results, interpretations, and conclusions are my own. Detailed developer phase logs have been archived off-repo to maintain clean, focused academic documentation.
