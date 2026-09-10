"""
HTML and SEC Document Text Normalization Engine.

Strips markup, scripts, and styling from SEC EDGAR HTML documents, unescapes
HTML entities, normalizes whitespace and unicode characters, and produces
clean, paragraph-structured plain text for section analysis and evidence retrieval.
"""
from html import unescape
from html.parser import HTMLParser
import re
from typing import Tuple


class _SECHTMLTextExtractor(HTMLParser):
    """Custom streaming HTML parser converting markup to clean paragraph text."""

    BLOCK_TAGS = {
        "p", "div", "h1", "h2", "h3", "h4", "h5", "h6",
        "tr", "table", "li", "ul", "ol", "blockquote", "hr", "br",
    }
    IGNORE_TAGS = {"script", "style", "noscript", "xml", "head"}

    def __init__(self) -> None:
        super().__init__()
        self.pieces = []
        self.ignore_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        lower_tag = tag.lower()
        if lower_tag in self.IGNORE_TAGS:
            self.ignore_depth += 1
        elif lower_tag in self.BLOCK_TAGS and self.ignore_depth == 0:
            self.pieces.append("\n")

    def handle_endtag(self, tag: str) -> None:
        lower_tag = tag.lower()
        if lower_tag in self.IGNORE_TAGS:
            self.ignore_depth = max(0, self.ignore_depth - 1)
        elif lower_tag in self.BLOCK_TAGS and self.ignore_depth == 0:
            self.pieces.append("\n")

    def handle_data(self, data: str) -> None:
        if self.ignore_depth == 0 and data:
            self.pieces.append(data)


def parse_sec_html(raw_html: str) -> Tuple[str, int, int]:
    """
    Transform raw SEC HTML document into normalized, paragraph-separated text.

    Parameters
    ----------
    raw_html : str
        Raw HTML source from SEC EDGAR.

    Returns
    -------
    Tuple[str, int, int]
        (clean_text, character_count, word_count)
    """
    if not raw_html:
        return "", 0, 0

    # Quick pre-strip of heavy XML/script tags if present
    cleaned_html = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", " ", raw_html, flags=re.DOTALL | re.IGNORECASE)

    extractor = _SECHTMLTextExtractor()
    extractor.feed(cleaned_html)
    raw_text = "".join(extractor.pieces)

    # Decode HTML entities (e.g. &nbsp;, &amp;, &#160;)
    text = unescape(raw_text)

    # Normalize unicode spaces and hyphens
    text = text.replace("\u00a0", " ").replace("\u200b", "").replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("\u2014", " - ").replace("\u2013", " - ")

    # Normalize inline whitespace while preserving paragraph line-breaks
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    
    # Reassemble paragraphs
    clean_lines = []
    prev_blank = False
    for line in lines:
        if not line:
            if not prev_blank:
                clean_lines.append("")
                prev_blank = True
        else:
            clean_lines.append(line)
            prev_blank = False

    clean_text = "\n".join(clean_lines).strip()
    char_count = len(clean_text)
    word_count = len(clean_text.split())

    return clean_text, char_count, word_count
