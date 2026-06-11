import re

from app.services.ollama import ollama_service


REFERENCE_ONLY_PROMPT = """Eres un analista de documentos legales especializado en normativas aduaneras bolivianas. Recibiras el texto de UN SOLO articulo de un reglamento. Tienes DOS tareas:

1. Identificar el titulo exacto del articulo tal como aparece en el texto.
2. Identificar todas las referencias a otros documentos legales mencionados.

Responde UNICAMENTE con el siguiente formato:

TITLE: ARTICULO 9.- (EJERCICIO DE LAS FUNCIONES DE CONTROL POSTERIOR)
---REFERENCE---
TYPE: ley
NUMBER: 2492
TITLE: Codigo Tributario Boliviano
ARTICLE: Articulo 26
RELATION: referencia
---REFERENCE---
TYPE: decreto
NUMBER: 2731 O
TITLE: Decreto Supremo
ARTICLE: Articulos 48, 49
RELATION: base_legal

Si no hay referencias, responde:
TITLE: ARTICULO 9.- (EJERCICIO DE LAS FUNCIONES DE CONTROL POSTERIOR)
NINGUNA

Reglas:
- TITLE: copia EXACTAMENTE el encabezado del articulo como aparece en el texto, sin modificarlo
- TYPE: resolucion, circular, ley, decreto, reglamento, otro
- NUMBER: numero o codigo del documento (ej: "RD 01-098-24", "323/2024", "2492", "CTB")
- TITLE de REFERENCE: nombre del documento referenciado
- ARTICLE: articulos citados separados por coma
- RELATION: deroga, modifica, referencia, complementa, base_legal"""


class ChapterService:
    async def extract_references(self, article_title: str, article_text: str) -> tuple[str, list[dict]]:
        user_prompt = f"Articulo: {article_title}\n\n{article_text}"

        messages = [
            {"role": "system", "content": REFERENCE_ONLY_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        raw_response = await ollama_service.chat(messages)
        cleaned = raw_response.strip()

        extracted_title = self._extract_title_from_response(cleaned) or article_title

        if "NINGUNA" in cleaned.upper():
            return extracted_title, []

        _, references = self._parse_response(cleaned)
        return extracted_title, references

    def _extract_title_from_response(self, raw: str) -> str:
        match = re.search(r"^TITLE:\s*(.+?)(?:\n|$)", raw, re.IGNORECASE | re.MULTILINE)
        return match.group(1).strip() if match else ""

    def _parse_response(self, raw: str) -> tuple[list[dict], list[dict]]:
        raw = raw.strip()
        raw = raw.replace("```", "").strip()

        blocks = re.split(r"\n?---(CHAPTER|REFERENCE)---\n?", raw)

        chapters = []
        references = []

        i = 1
        while i < len(blocks) - 1:
            block_type = blocks[i]
            block_content = blocks[i + 1].strip()
            i += 2

            if block_type == "REFERENCE":
                ref = self._parse_reference_block(block_content)
                if ref:
                    references.append(ref)

        return chapters, references

    def _parse_reference_block(self, block: str) -> dict | None:
        ref_type = self._extract_field(block, "TYPE")
        ref_number = self._extract_field(block, "NUMBER")
        ref_title = self._extract_field(block, "TITLE")
        ref_article = self._extract_field(block, "ARTICLE")
        relation = self._extract_field(block, "RELATION")

        if not ref_number or not ref_title:
            return None

        ref_number = self._clean_field(ref_number)
        ref_title = self._clean_field(ref_title)

        if not ref_number or not ref_title:
            return None

        return {
            "ref_type": ref_type or "otro",
            "ref_number": ref_number,
            "ref_title": ref_title,
            "ref_article": ref_article or "",
            "relation": relation or "referencia",
        }

    def _clean_field(self, value: str) -> str:
        value = value.strip()
        value = re.sub(r"^TITLE:\s*", "", value, flags=re.IGNORECASE)
        value = re.sub(r"^NUMBER:\s*", "", value, flags=re.IGNORECASE)
        value = re.sub(r"^TYPE:\s*", "", value, flags=re.IGNORECASE)
        value = re.sub(r"^ARTICLE:\s*", "", value, flags=re.IGNORECASE)
        value = re.sub(r"^RELATION:\s*", "", value, flags=re.IGNORECASE)
        return value.strip()

    def _extract_field(self, block: str, field: str) -> str:
        match = re.search(rf"{field}:\s*(.+?)(?:\n|$)", block, re.DOTALL)
        return match.group(1).strip() if match else ""


chapter_service = ChapterService()
