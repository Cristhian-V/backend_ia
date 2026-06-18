import re

ARTICLE_SPLIT_PATTERN = re.compile(
    r"^(ART[IÍ]CULO\s+\d+\b\s*(?:[º°]|\.(?:\s*[-–—])?)?)"
    r"\s*(?!\s*de\s+la\b|\s*del\b|\s*de\s+los\b|\s*de\s+las\b)",
    re.IGNORECASE | re.MULTILINE,
)

RESOLUCION_SPLIT_PATTERN = re.compile(
    r"^(PRIMERO|SEGUNDO|TERCERO|CUARTO|QUINTO|SEXTO|S[EÉ]PTIMO|"
    r"OCTAVO|NOVENO|D[EÉ]CIMO|UND[EÉ]CIMO|DUOD[EÉ]CIMO|"
    r"VIG[EÉ]SIMO)\s*\.[\s\-–—]*",
    re.IGNORECASE | re.MULTILINE,
)

ANEXO_SPLIT_PATTERN = re.compile(
    r"^(ANEXO\s+N?[°º]?\s*\d+)",
    re.IGNORECASE | re.MULTILINE,
)

NUMERAL_ROMANO_SPLIT_PATTERN = re.compile(
    r"^((?:X{0,3}(?:IX|IV|V?I{0,3}))\.\s+\S)",
    re.IGNORECASE | re.MULTILINE,
)

LITERAL_SPLIT_PATTERN = re.compile(
    r"^(([A-Z])\.\s+[A-ZÁÉÍÓÚ])",
    re.MULTILINE,
)

CASCADE_PATTERNS: list[tuple[re.Pattern, str, int]] = [
    (RESOLUCION_SPLIT_PATTERN, "resolucion", 1),
    (ANEXO_SPLIT_PATTERN, "anexo", 1),
    (NUMERAL_ROMANO_SPLIT_PATTERN, "numeral_romano", 2),
    (LITERAL_SPLIT_PATTERN, "literal", 3),
]

FOOTER_PATTERNS = [
    re.compile(r"Al momento de ser impreso.*$", re.IGNORECASE | re.DOTALL),
    re.compile(r"documento controlado.*$", re.IGNORECASE | re.DOTALL),
    re.compile(r"Edificio de la Oficina Central.*$", re.IGNORECASE | re.DOTALL),
    re.compile(r"INSTITUCI[OÓ]N\s*CERTIFICADA.*$", re.IGNORECASE | re.DOTALL),
]


class ArticleSplitter:
    def split(self, text: str) -> list[str]:
        # Priority 1: always check ARTICULO pattern first (most common)
        if list(ARTICLE_SPLIT_PATTERN.finditer(text)):
            chunks = self._split_with(text, ARTICLE_SPLIT_PATTERN)
            print(f"     Splitter: patron 'articulo' -> {len(chunks)} fragmentos")
            return chunks

        # Priority 2: cascade patterns, best-split wins
        best_chunks: list[str] = [text.strip()] if text.strip() else []
        best_pattern = "ninguno"

        for pattern, name, min_chunks in CASCADE_PATTERNS:
            chunks = self._split_with(text, pattern)
            if len(chunks) > len(best_chunks) and len(chunks) > min_chunks:
                best_chunks = chunks
                best_pattern = name

        if best_pattern != "ninguno":
            print(f"     Splitter: patron '{best_pattern}' -> {len(best_chunks)} fragmentos")
        else:
            print(f"     Splitter: sin patron coincidente, 1 fragmento")

        return best_chunks

    def _split_with(self, text: str, pattern: re.Pattern) -> list[str]:
        matches = list(pattern.finditer(text))
        if not matches:
            return [text.strip()] if text.strip() else []

        chunks: list[str] = []
        last_end = 0

        for m in matches:
            before = text[last_end:m.start()].strip()
            if before:
                chunks.append(before)
            last_end = m.start()

        remaining = text[last_end:].strip()
        if remaining:
            chunks.append(remaining)

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
