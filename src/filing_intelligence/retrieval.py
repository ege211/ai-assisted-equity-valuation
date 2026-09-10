"""
Passage Chunking and Targeted Relevance Retrieval Engine.

Splits filing section text into coherent paragraphs/passages (300-1,500 chars)
and matches them against targeted topical signatures across the 12 qualitative
categories, ensuring only relevant evidence-bearing text is forwarded to the LLM.
"""
import logging
import re
from typing import Dict, List, Optional, Tuple

from src.filing_intelligence.schemas import FilingPassage, FilingSection, QualitativeCategory

logger = logging.getLogger(__name__)

# Category Keyword and Lexical Pattern Signatures
CATEGORY_SIGNATURES: Dict[QualitativeCategory, List[str]] = {
    QualitativeCategory.REGULATORY_RISK: [
        r"\bregulat(?:ion|ory|ed|ing)\b", r"\bcompliance\b", r"\bantitrust\b",
        r"\bsec\b", r"\bftc\b", r"\bfda\b", r"\bdoj\b", r"\bsanction\b",
        r"\blegislat(?:ion|ive)\b", r"\bstatut(?:e|ory)\b", r"\bgdpr\b",
    ],
    QualitativeCategory.LITIGATION_RISK: [
        r"\blawsuit\b", r"\blitigat(?:ion|ed|ing)\b", r"\bproceeding(?:s)?\b",
        r"\barbitrat(?:ion|or)\b", r"\bplaintiff(?:s)?\b", r"\bdefendant(?:s)?\b",
        r"\bsettlement\b", r"\binfringement\b", r"\bpatent\s+dispute\b",
    ],
    QualitativeCategory.DEMAND_UNCERTAINTY: [
        r"\bdemand\b", r"\bsoften(?:ing|ed)\b", r"\bdecelerat(?:ion|ing|ed)\b",
        r"\bheadwind(?:s)?\b", r"\bcustomer\s+spending\b", r"\bvolatilit(?:y|ies)\b",
        r"\border\s+cancellation\b", r"\bweakness\s+in\s+demand\b",
    ],
    QualitativeCategory.MARGIN_PRESSURE: [
        r"\bmargin(?:s)?\b", r"\bgross\s+margin\b", r"\boperating\s+margin\b",
        r"\bcost\s+inflation\b", r"\binput\s+cost(?:s)?\b", r"\bcompress(?:ion|ed|ing)\b",
        r"\bwage\s+pressure\b", r"\btariff(?:s)?\b", r"\bpricing\s+pressure\b",
    ],
    QualitativeCategory.STRATEGIC_CHANGE: [
        r"\bstrategic\s+priorit(?:y|ies)\b", r"\brestructur(?:ing|ed)\b",
        r"\bacqui(?:sition|re|red)\b", r"\bdivest(?:iture|ment|ed)\b",
        r"\breorganiz(?:ation|ed)\b", r"\bpivot\b", r"\bnew\s+product\s+line\b",
    ],
    QualitativeCategory.CAPITAL_ALLOCATION_CHANGE: [
        r"\bshare\s+repurchase(?:s)?\b", r"\bshare\s+buyback(?:s)?\b",
        r"\bdividend(?:s)?\b", r"\bcapital\s+expenditure(?:s)?\b", r"\bcapex\b",
        r"\bdebt\s+repayment\b", r"\bleverage\s+ratio\b", r"\bshareholder\s+return\b",
    ],
    QualitativeCategory.GUIDANCE_DIRECTION: [
        r"\bguidance\b", r"\boutlook\b", r"\bforecast(?:ing|ed|s)?\b",
        r"\bfull[\-\s]year\s+guidance\b", r"\bexpect(?:ed|ing|s)?\b",
        r"\bproject(?:ed|ing|ion|ions)?\b", r"\btarget(?:ed|ing|s)?\b",
    ],
    QualitativeCategory.LIQUIDITY_RISK: [
        r"\bliquidit(?:y|ies)\b", r"\bcredit\s+facilit(?:y|ies)\b",
        r"\brevolving\s+credit\b", r"\bcovenant(?:s)?\b", r"\bdebt\s+maturit(?:y|ies)\b",
        r"\bcash\s+flow\s+adequacy\b", r"\bborrowing\s+capacit(?:y|ies)\b",
    ],
    QualitativeCategory.SUPPLY_CHAIN_RISK: [
        r"\bsuppl(?:y|ier|iers|ying)\b", r"\bcomponent\s+shortage\b",
        r"\blogistics\b", r"\bfreight\b", r"\bsingle[\-\s]source\b",
        r"\bbottleneck(?:s)?\b", r"\blead\s+time(?:s)?\b", r"\bvendor(?:s)?\b",
    ],
    QualitativeCategory.COMPETITIVE_PRESSURE: [
        r"\bcompetit(?:ion|or|ors|ive)\b", r"\bmarket\s+share\b",
        r"\bcompetitive\s+landscape\b", r"\bpricing\s+concession(?:s)?\b",
        r"\balternative\s+product(?:s)?\b",
    ],
    QualitativeCategory.MATERIAL_BUSINESS_CHANGE: [
        r"\bmaterial\s+(?:adverse\s+)?change\b", r"\bimpairment(?:s)?\b",
        r"\bgoodwill\s+impairment\b", r"\bdiscontinued\s+operations\b",
        r"\bplant\s+clos(?:ure|ures|ing)\b", r"\bcasualt(?:y|ies)\b",
    ],
    QualitativeCategory.MANAGEMENT_OUTLOOK: [
        r"\bmanagement\s+outlook\b", r"\bmacroeconomic\s+environment\b",
        r"\bforward[\-\s]looking\b", r"\bcommercial\s+momentum\b",
        r"\bfiscal\s+trend(?:s)?\b", r"\blong[\-\s]term\s+trajectory\b",
    ],
}


def chunk_section_into_passages(
    section: FilingSection,
    min_chars: int = 250,
    max_chars: int = 1500,
) -> List[Tuple[int, int, str]]:
    """
    Split a section's text into paragraphs or cohesive blocks with character offsets.

    Returns List of (start_char_offset, end_char_offset, passage_text).
    """
    text = section.section_text or ""
    if not text:
        return []

    # Split on double newlines to isolate paragraphs
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text)]
    chunks: List[Tuple[int, int, str]] = []

    curr_start = 0
    buffer = []
    buffer_len = 0

    for para in paragraphs:
        if not para:
            continue

        p_len = len(para)
        # Find start offset of paragraph in section text
        p_offset = text.find(para, curr_start)
        if p_offset == -1:
            p_offset = curr_start

        if buffer_len + p_len < max_chars:
            buffer.append(para)
            buffer_len += p_len + 2
        else:
            if buffer:
                chunk_text = "\n\n".join(buffer)
                chunk_start = text.find(buffer[0], curr_start)
                if chunk_start == -1:
                    chunk_start = curr_start
                chunk_end = chunk_start + len(chunk_text)
                chunks.append((chunk_start, chunk_end, chunk_text))
                curr_start = chunk_end

            buffer = [para]
            buffer_len = p_len

    if buffer:
        chunk_text = "\n\n".join(buffer)
        chunk_start = text.find(buffer[0], curr_start)
        if chunk_start == -1:
            chunk_start = curr_start
        chunk_end = chunk_start + len(chunk_text)
        chunks.append((chunk_start, chunk_end, chunk_text))

    # Filter out tiny passages (< min_chars) unless it is the only chunk
    final_chunks = [c for c in chunks if len(c[2]) >= min_chars]
    if not final_chunks and chunks:
        final_chunks = chunks

    return final_chunks


def retrieve_relevant_passages(
    sections: List[FilingSection],
    max_passages_per_category: int = 4,
) -> List[FilingPassage]:
    """
    Extract and retrieve evidence candidate passages matching the 12 qualitative categories.

    Parameters
    ----------
    sections : List[FilingSection]
        Sections identified in filing.
    max_passages_per_category : int
        Max top-ranked candidate passages per category.

    Returns
    -------
    List[FilingPassage]
        Structured passages ready for extraction.
    """
    passages: List[FilingPassage] = []
    passage_idx = 1

    # Prioritize substantive qualitative sections
    target_sections = {
        "ITEM_1_BUSINESS", "ITEM_1A_RISK_FACTORS", "ITEM_3_LEGAL_PROCEEDINGS",
        "ITEM_7_MDA", "ITEM_7A_MARKET_RISK", "PART_I_ITEM_2_MDA",
        "PART_II_ITEM_1_LEGAL", "PART_II_ITEM_1A_RISK_FACTORS",
    }

    # Track how many passages we've collected per category
    category_counts: Dict[QualitativeCategory, int] = {cat: 0 for cat in QualitativeCategory}

    for sec in sections:
        if sec.section_name not in target_sections and len(sections) > 3:
            continue

        raw_chunks = chunk_section_into_passages(sec)

        for start_offset, end_offset, text in raw_chunks:
            # Score against each category signature
            best_cat: Optional[QualitativeCategory] = None
            best_score = 0

            for cat, patterns in CATEGORY_SIGNATURES.items():
                match_count = 0
                for pat in patterns:
                    matches = len(re.findall(pat, text, re.IGNORECASE))
                    match_count += matches

                if match_count > best_score:
                    best_score = match_count
                    best_cat = cat

            # If passage contains substantive category matches (score >= 2 or score >= 1 for specific terms)
            if best_cat and best_score >= 1 and category_counts[best_cat] < max_passages_per_category:
                category_counts[best_cat] += 1
                passage = FilingPassage(
                    passage_id=f"pass_{sec.document_id}_{sec.section_name}_{passage_idx}",
                    section_id=sec.section_id,
                    document_id=sec.document_id,
                    accession_number=sec.accession_number,
                    ticker=sec.ticker,
                    section_name=sec.section_name,
                    category_hint=best_cat.value,
                    passage_index=passage_idx,
                    start_char=sec.start_char + start_offset,
                    end_char=sec.start_char + end_offset,
                    passage_text=text,
                )
                passages.append(passage)
                passage_idx += 1

    return passages
