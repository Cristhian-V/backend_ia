import uuid
import asyncio

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.document import Document
from app.schemas.document import ChunkItem, DocumentResponse, DocumentUploadResponse
from app.services.parser import parser_service
from app.services.vector_store import process_and_store, vector_store
from app.services.progress import progress_tracker
from app.services.reference_service import reference_service

router = APIRouter(prefix="/documents", tags=["documents"])


async def _process_document(
    filename: str, content: bytes, doc_id: str, pages: list[str], user_id: int,
    extract_references: bool = True,
):
    async def on_progress(stage, current, total, message, **extra):
        await progress_tracker.update(doc_id, stage, current, total, message, **extra)

    try:
        from app.core.database import async_session

        async with async_session() as db:
            chunks, all_chapters, all_references, filtered_titles, doc_meta = await process_and_store(
                filename, content, doc_id, pages,
                on_progress=on_progress,
                db=db,
                extract_references=extract_references,
            )
            await progress_tracker.set_done(doc_id, chunks)

            result = await db.execute(select(Document).where(Document.id == doc_id))
            doc = result.scalar_one_or_none()
            if doc:
                doc.chunks_count = chunks
                doc.page_count = len(pages)
                doc.status = "ready"
                if doc_meta:
                    doc.doc_type = doc_meta.get("doc_type", "otro")
                    doc.doc_number = doc_meta.get("doc_number")
                    doc.doc_number_nrm = doc_meta.get("doc_number_nrm")
                    doc.doc_title = doc_meta.get("doc_title")
                    doc.doc_date = doc_meta.get("doc_date")
                    doc.issuing_body = doc_meta.get("issuing_body", "")
                await db.commit()

            if extract_references and all_references:
                await progress_tracker.update(doc_id, "referencing", 1, 1, "Verificando referencias a otros documentos...")
                pending_count = await reference_service.process_references(
                    db, user_id, doc_id, all_references, all_chapters, filtered_titles
                )
                await reference_service.resolve_existing_references(
                    db, doc_id, doc_meta.get("doc_number_nrm", "")
                )
                print(f"  🔗 {pending_count} documentos pendientes registrados")

    except Exception as e:
        await progress_tracker.set_error(doc_id, str(e))

        async with async_session() as db:
            result = await db.execute(select(Document).where(Document.id == doc_id))
            doc = result.scalar_one_or_none()
            if doc:
                doc.status = "error"
                await db.commit()


@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    extract_references: bool = Form(True),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Nombre de archivo requerido")

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ("pdf", "docx", "doc"):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos PDF y DOCX")

    content = await file.read()
    pages = await parser_service.parse_pages(file.filename, content)

    doc_id = str(uuid.uuid4())
    doc = Document(
        id=doc_id,
        user_id=current_user.id,
        filename=file.filename,
        chunks_count=0,
        status="processing",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    await progress_tracker.init(doc_id, message=f"Iniciando procesamiento de {file.filename}...")
    asyncio.create_task(_process_document(file.filename, content, doc_id, pages, current_user.id, extract_references))

    return doc


@router.get("/{doc_id}/progress")
async def get_progress(
    doc_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Document).where(Document.id == doc_id, Document.user_id == current_user.id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    prog = await progress_tracker.get(doc_id)
    if not prog:
        return {"status": "processing", "stage": "starting", "current": 0, "total": 0, "message": "Iniciando..."}
    return prog


@router.get("/", response_model=list[DocumentResponse])
async def list_documents(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Document).where(Document.user_id == current_user.id).order_by(Document.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{doc_id}/chunks", response_model=list[ChunkItem])
async def get_document_chunks(
    doc_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Document).where(Document.id == doc_id, Document.user_id == current_user.id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    return vector_store.get_document_chunks(doc_id)


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    doc_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Document).where(Document.id == doc_id, Document.user_id == current_user.id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    vector_store.delete_document(doc_id)
    await db.delete(doc)
    await db.commit()
