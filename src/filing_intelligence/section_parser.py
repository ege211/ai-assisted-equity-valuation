"""
Section Identification and Boundary Detection Engine for SEC Filings.

Identifies major structural sections in 10-K and 10-Q filings:
- 10-K:
  - Item 1 (Business)
  - Item 1A (Risk Factors)
  - Item 3 (Legal Proceedings)
  - Item 7 (MD&A)
  - Item 7A (Market Risk)
  - Item 8 (Financial Statements and Notes)
- 10-Q:
  - Part I Item 1 (Financial Statements)
  - Part I Item 2 (MD&A)
  - Part II Item 1 (Legal Proceedings)
  - Part II Item 1A (Risk Factors)

Implements Table of Contents (TOC) filtering and boundary detection to isolate
the true substantive body of each section.
"""
import logging
import re
from typing import Dict, List, Optional, Tuple
import uuid

from src.filing_intelligence.schemas import FilingSection

logger = logging.getLogger(__name__)

# Section Heading Patterns (10-K)
PATTERNS_10K = [
    ("ITEM_1_BUSINESS", r"(?:ITEM\s+1[\.\:\s\–\-]+BUSINESS)(?![\.\:\s\–\-]+RISK)", "Item 1. Business"),
    ("ITEM_1A_RISK_FACTORS", r"ITEM\s+1A[\.\:\s\–\-]+RISK\s+FACTORS", "Item 1A. Risk Factors"),
    ("ITEM_1B_STAFF_COMMENTS", r"ITEM\s+1B[\.\:\s\–\-]+UNRESOLVED\s+STAFF\s+COMMENTS", "Item 1B. Staff Comments"),
    ("ITEM_1C_CYBERSECURITY", r"ITEM\s+1C[\.\:\s\–\-]+CYBERSECURITY", "Item 1C. Cybersecurity"),
    ("ITEM_2_PROPERTIES", r"ITEM\s+2[\.\:\s\–\-]+PROPERTIES", "Item 2. Properties"),
    ("ITEM_3_LEGAL_PROCEEDINGS", r"ITEM\s+3[\.\:\s\–\-]+LEGAL\s+PROCEEDINGS", "Item 3. Legal Proceedings"),
    ("ITEM_4_MINE_SAFETY", r"ITEM\s+4[\.\:\s\–\-]+MINE\s+SAFETY", "Item 4. Mine Safety"),
    ("ITEM_7_MDA", r"ITEM\s+7[\.\:\s\–\-]+MANAGEMENT(?:'S|\x92S)?\s+DISCUSSION\s+AND\s+ANALYSIS", "Item 7. MD&A"),
    ("ITEM_7A_MARKET_RISK", r"ITEM\s+7A[\.\:\s\–\-]+QUANTITATIVE\s+AND\s+QUALITATIVE\s+DISCLOSURES", "Item 7A. Market Risk"),
    ("ITEM_8_FINANCIAL_STATEMENTS", r"ITEM\s+8[\.\:\s\–\-]+FINANCIAL\s+STATEMENTS", "Item 8. Financial Statements"),
    ("ITEM_9_DISAGREEMENTS", r"ITEM\s+9[\.\:\s\–\-]+CHANGES\s+IN\s+AND\s+DISAGREEMENTS", "Item 9. Changes in Accounting"),
]

# Section Heading Patterns (10-Q)
PATTERNS_10Q = [
    ("PART_I_ITEM_1_FINANCIALS", r"(?:PART\s+I[\.\s]+)?ITEM\s+1[\.\:\s\–\-]+FINANCIAL\s+STATEMENTS", "Part I Item 1. Financial Statements"),
    ("PART_I_ITEM_2_MDA", r"(?:PART\s+I[\.\s]+)?ITEM\s+2[\.\:\s\–\-]+MANAGEMENT(?:'S|\x92S)?\s+DISCUSSION\s+AND\s+ANALYSIS", "Part I Item 2. MD&A"),
    ("PART_I_ITEM_3_MARKET_RISK", r"(?:PART\s+I[\.\s]+)?ITEM\s+3[\.\:\s\–\-]+QUANTITATIVE\s+AND\s+QUALITATIVE", "Part I Item 3. Market Risk"),
    ("PART_I_ITEM_4_CONTROLS", r"(?:PART\s+I[\.\s]+)?ITEM\s+4[\.\:\s\–\-]+CONTROLS\s+AND\s+PROCEDURES", "Part I Item 4. Controls"),
    ("PART_II_ITEM_1_LEGAL", r"(?:PART\s+II[\.\s]+)?ITEM\s+1[\.\:\s\–\-]+LEGAL\s+PROCEEDINGS", "Part II Item 1. Legal Proceedings"),
    ("PART_II_ITEM_1A_RISK_FACTORS", r"(?:PART\s+II[\.\s]+)?ITEM\s+1A[\.\:\s\–\-]+RISK\s+FACTORS", "Part II Item 1A. Risk Factors"),
    ("PART_II_ITEM_6_EXHIBITS", r"(?:PART\s+II[\.\s]+)?ITEM\s+6[\.\:\s\–\-]+EXHIBITS", "Part II Item 6. Exhibits"),
]


def _is_table_of_contents_entry(match_start: int, match_end: int, text: str, total_len: int) -> bool:
    """
    Determine if a heading occurrence is a Table of Contents entry.

    Signals:
    - Followed immediately by a page number (e.g. ' 15' or ' ... 15' or ' Page 15').
    - Followed closely by another Item heading within 70 chars (consecutive TOC list).
    """
    after_match = text[match_end:match_end + 150]

    # Signal 1: Immediately followed by page number or dot leader
    if re.match(r"^[ \t\.\–\-]+(?:\d{1,4}|page\s+\d{1,4})\b", after_match, re.IGNORECASE):
        return True

    # Signal 2: Followed closely by another Item heading (consecutive TOC list)
    other_items = list(re.finditer(r"ITEM\s+\d", after_match[:70], re.IGNORECASE))
    if other_items:
        return True

    return False


def parse_sections(
    clean_text: str,
    form: str,
    document_id: str,
    accession_number: str,
    ticker: str,
) -> List[FilingSection]:
    """
    Segment filing text into recognized structural sections.

    Parameters
    ----------
    clean_text : str
        Normalized filing plain text.
    form : str
        Filing form ('10-K', '10-Q', '10-K/A', '10-Q/A').
    document_id : str
        Associated document ID.
    accession_number : str
        Filing accession number.
    ticker : str
        Company ticker symbol.

    Returns
    -------
    List[FilingSection]
        Identified sections with text content and boundaries.
    """
    patterns = PATTERNS_10Q if "10-Q" in form.upper() else PATTERNS_10K
    total_len = len(clean_text)

    # 1. Find all candidate occurrences for each pattern
    candidates: List[Dict[str, Any]] = []

    for name, regex, title in patterns:
        for m in re.finditer(regex, clean_text, re.IGNORECASE):
            start = m.start()
            end = m.end()
            is_toc = _is_table_of_contents_entry(start, end, clean_text, total_len)
            candidates.append({
                "name": name,
                "title": title,
                "start": start,
                "end": end,
                "is_toc": is_toc,
                "match_text": m.group(),
            })

    # Filter out TOC entries
    substantive = [c for c in candidates if not c["is_toc"]]

    # If no substantive found (e.g. non-standard TOC or small filing), fall back to all candidates
    if not substantive:
        substantive = candidates

    # Group by name and keep the occurrence with maximum distance from TOC (or latest sensible start)
    # If multiple occurrences exist for the same section name:
    best_occurrences: Dict[str, Dict[str, Any]] = {}
    for c in substantive:
        name = c["name"]
        if name not in best_occurrences:
            best_occurrences[name] = c
        else:
            # If current is later in document (past TOC), prefer it
            if c["start"] > best_occurrences[name]["start"]:
                best_occurrences[name] = c

    # Sort identified sections by their start character position
    sorted_sections = sorted(best_occurrences.values(), key=lambda x: x["start"])

    sections: List[FilingSection] = []

    for i, curr in enumerate(sorted_sections):
        start_char = curr["start"]
        # End is start of next identified section or end of text
        if i + 1 < len(sorted_sections):
            end_char = sorted_sections[i + 1]["start"]
        else:
            end_char = total_len

        # Clamp slice
        section_content = clean_text[start_char:end_char].strip()
        char_count = len(section_content)

        # Confidence assessment
        confidence = "HIGH"
        if char_count < 200 or curr.get("is_toc"):
            confidence = "UNCERTAIN"

        sec = FilingSection(
            section_id=f"sec_{document_id}_{curr['name']}",
            document_id=document_id,
            accession_number=accession_number,
            ticker=ticker,
            section_name=curr["name"],
            section_title=curr["title"],
            start_char=start_char,
            end_char=end_char,
            char_count=char_count,
            detection_confidence=confidence,
            section_text=section_content,
        )
        sections.append(sec)

    return sections
