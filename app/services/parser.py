import io

from pypdf import PdfReader
from docx import Document


class ParserService:
    async def parse_pages(self, filename: str, content: bytes) -> list[str]:
        ext = filename.rsplit(".", 1)[-1].lower()
        if ext == "pdf":
            return self._parse_pdf_pages(content)
        elif ext in ("docx", "doc"):
            text = self._parse_docx(content)
            return [p.strip() for p in text.split("\n\n") if p.strip()]
        raise ValueError(f"Formato no soportado: .{ext}")

    def _parse_pdf_pages(self, content: bytes) -> list[str]:
        reader = PdfReader(io.BytesIO(content))
        pages = []
        for page in reader.pages:
            text = page.extract_text()
            pages.append(text.strip() if text else "")
        return pages

    def _parse_docx(self, content: bytes) -> str:
        doc = Document(io.BytesIO(content))
        paragraphs = []
        for para in doc.paragraphs:
            text = para.text.strip()
            if text:
                paragraphs.append(text)
        return "\n\n".join(paragraphs)


parser_service = ParserService()
