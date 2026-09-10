# Documentation Index: AI-Assisted Equity Valuation & Investment Intelligence Platform

Welcome to the institutional documentation archive for the **AI-Assisted Equity Valuation & Investment Intelligence Platform**. This index provides a structured roadmap across academic research papers, technical reproducibility manuals, data dictionaries, and historical phase implementation reports.

---

## 1. Primary Academic & Research Package

* [**Academic Research Paper**](RESEARCH_PAPER.md): Complete 18-section academic working paper: *Empirical Limits of Textual Intelligence in Structural Equity Valuation: An Out-of-Sample Walk-Forward Study on SEC 10-K Filings*. Covers theoretical framework, 5-tier XBRL cascade, deterministic DCF formulation, 12 pre-specified linguistic dimensions, walk-forward econometric evaluation ($N=46$ complete cases, 2 folds), feature ablations, and Appendices A–F.
* [**Reproducibility Guide**](REPRODUCIBILITY_GUIDE.md): Step-by-step CLI reproduction instructions, hardware/software prerequisites, full unit test suite execution (260/260 passing), pipeline sequence, Streamlit terminal launch, and cryptographic checksum verification.
* [**Experiment Registry**](EXPERIMENT_REGISTRY.md): Comprehensive, immutable registry of all empirical experiments (`EXP-P6-CROSSSECTIONAL`, `EXP-P7-PANEL-PRIMARY`, `EXP-P7-PANEL-SECONDARY`, `EXP-P7-PANEL-BINARY`, `EXP-P7-ABLATION`, `EXP-P7-ROBUSTNESS`, `EXP-P5-FILING-EVIDENCE`).
* [**Data Provenance & Lineage Architecture**](DATA_PROVENANCE.md): Forensic data origin documentation, tri-temporal coordinate system (`period_end_date`, `filing_date`, `acceptance_datetime`), point-in-time filtering rules (`acceptance_datetime <= cutoff 23:59:59`), DuckDB relational schema, and XBRL fallback logic.
* [**GitHub Public Release Preparation**](PHASE_9_GITHUB_RELEASE_PREPARATION.md): Security audit (0 secrets, 0 hardcoded paths), public vs. local file tracking inventory, versioning strategy (`v1.0.0`), and pre-release gates.

---

## 2. Platform Architecture & Service Specifications

* [**Platform Architecture Specification**](PHASE_8_ARCHITECTURE_SPECIFICATION.md): Comprehensive system specification for the decoupled, multi-tier institutional research terminal, defining the `PlatformService` orchestrator, immutable DTO contracts, and the six specialized analytical presentation views.

---

## 3. Phase Implementation Reports (Phases 0 through 10)

* [**Phase 0: Feasibility & Foundation**](PHASE_0_FEASIBILITY_REPORT.md): Initial econometric feasibility study and architectural blueprint.
* [**Phase 1: Data Universe Audit**](PHASE_1_DATA_UNIVERSE_AUDIT.md): 30-company universe audit, SEC CIK mappings, and 10-year XBRL taxonomy coverage analysis.
* [**Phase 2: Financial Pipeline Report**](PHASE_2_FINANCIAL_PIPELINE_REPORT.md): Ingestion and processing pipeline for SEC EDGAR company facts and filings.
* [**Phase 3: Accounting Feature Report**](PHASE_3_ACCOUNTING_FEATURE_REPORT.md): Five-tier XBRL concept normalization, LTM ratio synthesis, and financial feature store.
* [**Phase 4: Valuation Engine Report**](PHASE_4_VALUATION_ENGINE_REPORT.md): Pure-Python, 100% deterministic structural DCF and reverse DCF root-finding engine.
* [**Phase 5: Filing Intelligence Report**](PHASE_5_FILING_INTELLIGENCE_REPORT.md): Statutory 10-K section parser (Items 1, 1A, 7) and 12-dimension linguistic signal extraction.
* [**Phase 6: Empirical Evaluation Report**](PHASE_6_EMPIRICAL_EVALUATION_REPORT.md): Exploratory cross-sectional LOOCV evaluation ($N=30$) and initial feature ablations.
* [**Phase 7: Expanded Out-of-Sample Research Report**](PHASE_7_EXPANDED_OOS_RESEARCH_REPORT.md): Primary chronological walk-forward panel study ($N=46$ complete cases, 2 expanding folds).
* [**Phase 8A: Service Layer & DTO Contracts**](PHASE_8A_IMPLEMENTATION_REPORT.md): Orchestration layer implementation and immutable contract decoupling.
* [**Phase 8C: Interactive Visual Components**](PHASE_8C_IMPLEMENTATION_REPORT.md): Presentation modules for Executive Overview, Valuation Terminal, and Accounting Explorer.
* [**Phase 8D: Qualitative Evidence & What Changed**](PHASE_8D_IMPLEMENTATION_REPORT.md): Verified evidence grounding cards and longitudinal disclosure delta tracking.
* [**Phase 8E: Point-in-Time Temporal Interface**](PHASE_8E_IMPLEMENTATION_REPORT.md): Global LIVE vs. HISTORICAL mode controls and microsecond timestamp barrier enforcement.
* [**Phase 8F: Provenance & Data Lineage**](PHASE_8F_IMPLEMENTATION_REPORT.md): End-to-end data lineage expanders, accession tracking, and mathematical calculation audits.
* [**Phase 8G: Final UI & Terminal Polish**](PHASE_8G_IMPLEMENTATION_REPORT.md): Institutional presentation QA, formatting hygiene, and full 260-test regression verification.
* [**Phase 9: Academic Documentation Package**](PHASE_9_IMPLEMENTATION_REPORT.md): Formal audit and verification of publication-grade academic papers and reproducibility artifacts.
* [**Phase 10: Final Forensic Audit & Release Report**](PHASE_10_FINAL_RELEASE_REPORT.md): Pre-release forensic security scan, repository sanitization, and release verification.
