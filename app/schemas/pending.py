from pydantic import BaseModel


class PendingResponse(BaseModel):
    id: str
    source_doc_id: str
    source_filename: str
    chapter_title: str = ""
    ref_type: str
    ref_number: str
    ref_title: str
    ref_article: str = ""
    ref_date: str = ""
    relation: str
    resolved: bool = False
    created_at: str


class ResolveRequest(BaseModel):
    document_id: str | None
    cascade: bool = True


class SourceRef(BaseModel):
    ref_id: str
    chapter_title: str
    ref_article: str
    source_filename: str
    chunk_text: str = ""
    resolved: bool = False


class PendingGroupResponse(BaseModel):
    ref_type: str
    ref_number: str
    ref_title: str
    relation: str
    resolved: bool
    refs: list[SourceRef]
    ref_ids: list[str]
