from datetime import datetime
from pydantic import BaseModel


class DocumentResponse(BaseModel):
    id: str
    filename: str
    page_count: int = 0
    doc_type: str = "otro"
    doc_number: str | None = None
    doc_title: str | None = None
    doc_date: str | None = None
    issuing_body: str | None = None
    chunks_count: int
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ChunkItem(BaseModel):
    id: str
    chunk_index: int
    text: str
    chapter_title: str = ""
    page_start: int = 0
    page_end: int = 0


class DocumentUploadResponse(BaseModel):
    id: str
    filename: str
    chunks_count: int
    status: str
