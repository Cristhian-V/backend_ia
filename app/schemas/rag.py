from pydantic import BaseModel


class RAGQuery(BaseModel):
    query: str
    top_k: int | None = None
    response_mode: str = "simple"


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
