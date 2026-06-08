import re

from app.services.ollama import ollama_service
from app.services.window_service import PageWindow


SYSTEM_PROMPT = """Eres un analista de documentos legales. Recibiras varias paginas consecutivas de un reglamento o normativa. Tu tarea es identificar los capitulos, secciones o articulos principales y dividir el texto en bloques tematicos completos.

Responde UNICAMENTE con el siguiente formato delimitado, sin texto adicional ni explicaciones. Cada bloque separado exactamente por "---CHAPTER---":

---CHAPTER---
TITLE: nombre del capitulo o seccion
CONTENT:
texto completo del bloque, sin resumir. Puede contener saltos de linea, comillas y cualquier caracter, no importa.
---CHAPTER---
TITLE: nombre del siguiente bloque
CONTENT:
texto completo del siguiente bloque...

Reglas:
- Cada bloque debe contener el contenido completo, sin cortes a mitad de oracion
- Usa los encabezados y numeracion del documento para identificar las divisiones
- Si un bloque comienza en estas paginas pero su contenido continua mas alla, incluye todo lo disponible
- Si no encuentras divisiones claras, devuelve un solo bloque con TITLE: Texto
- El CONTENT debe ser el texto original del documento, no un resumen
- No inventes contenido, solo estructura el texto proporcionado"""


class ChapterService:
    async def detect_chapters(self, window: PageWindow) -> list[dict]:
        text = "\n\n".join(
            f"--- PAGINA {window.page_start + i + 1} ---\n{p}"
            for i, p in enumerate(window.pages)
        )
        mark_start = window.page_start + 1
        mark_end = window.page_end + 1
        user_prompt = f"Analiza el siguiente documento (paginas {mark_start} a {mark_end}):\n\n{text}"

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        raw_response = await ollama_service.chat(messages)
        chapters = self._parse_delimited(raw_response)
        if not chapters:
            raise ValueError(f"El modelo no pudo identificar capitulos en el lote. Respuesta: {raw_response[:300]}...")
        return chapters

    def _parse_delimited(self, raw: str) -> list[dict]:
        raw = raw.strip()
        raw = raw.replace("```", "").strip()

        blocks = re.split(r"\n?---CHAPTER---\n?", raw)

        chapters = []
        for block in blocks:
            block = block.strip()
            if not block:
                continue

            title_match = re.search(r"TITLE:\s*(.+?)(?:\n|$)", block, re.DOTALL)
            content_match = re.search(r"CONTENT:\s*\n?(.*)", block, re.DOTALL)

            if not title_match:
                continue

            title = title_match.group(1).strip()
            content = content_match.group(1).strip() if content_match else ""

            if not content:
                content = block[content_match.end():].strip() if content_match else block

            if content:
                chapters.append({"title": title, "content": content})

        return chapters


chapter_service = ChapterService()
