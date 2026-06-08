from pydantic import BaseModel


class RAGQuery(BaseModel):
    query: str
    top_k: int | None = None


class RAGChunk(BaseModel):
    doc_id: str
    text: str
    distance: float
    chapter_title: str = ""
    document_filename: str = ""


class RAGResponse(BaseModel):
    answer: str
    chunks: list[RAGChunk]
    model: str
