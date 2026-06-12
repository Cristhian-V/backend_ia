import re

ARTICLE_SPLIT_PATTERN = re.compile(
    r"^(ART[IÍ]CULO\s+\d+\b\s*(?:[º°]|\.(?:\s*[-–—])?)?)"
    r"\s*(?!\s*de\s+la\b|\s*del\b|\s*de\s+los\b|\s*de\s+las\b)",
    re.IGNORECASE | re.MULTILINE,
)

FOOTER_PATTERNS = [
    re.compile(r"Al momento de ser impreso.*$", re.IGNORECASE | re.DOTALL),
    re.compile(r"documento controlado.*$", re.IGNORECASE | re.DOTALL),
    re.compile(r"Edificio de la Oficina Central.*$", re.IGNORECASE | re.DOTALL),
    re.compile(r"INSTITUCI[OÓ]N\s*CERTIFICADA.*$", re.IGNORECASE | re.DOTALL),
]


class ArticleSplitter:
    def split(self, text: str) -> list[str]:
        parts = ARTICLE_SPLIT_PATTERN.split(text)
        chunks: list[str] = []
        current: list[str] = []

        for part in parts:
            if part and ARTICLE_SPLIT_PATTERN.match(part):
                if current:
                    chunks.append("".join(current).strip())
                    current = []
                current.append(part)
            elif part:
                current.append(part)

        if current:
            chunks.append("".join(current).strip())

        if chunks:
            chunks[-1] = self._strip_footer(chunks[-1])

        return chunks

    def _strip_footer(self, text: str) -> str:
        for pattern in FOOTER_PATTERNS:
            match = pattern.search(text)
            if match:
                text = text[:match.start()].strip()
        return text


article_splitter = ArticleSplitter()
