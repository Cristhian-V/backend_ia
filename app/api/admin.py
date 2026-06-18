from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.document import Document
from app.models.document_reference import DocumentReference
from app.services.reference_scheduler import (
    process_pending_documents,
    log,
)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/process-references")
async def trigger_process_references(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado: se requiere administrador")

    log("📋 Iniciando extraccion de referencias manual...")
    await process_pending_documents()

    # Get updated counts
    total = await db.execute(select(Document).where(Document.status == "ready"))
    total_docs = len(total.scalars().all())

    with_refs = await db.execute(
        select(DocumentReference.source_document_id).distinct()
    )
    docs_with_refs = len(with_refs.scalars().all())

    return {
        "status": "completed",
        "total_documents": total_docs,
        "documents_with_references": docs_with_refs,
        "pending": total_docs - docs_with_refs,
    }
