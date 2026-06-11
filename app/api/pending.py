from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.document import Document
from app.models.document_reference import DocumentReference
from app.schemas.pending import PendingResponse, ResolveRequest, PendingGroupResponse
from app.services.reference_service import reference_service

router = APIRouter(prefix="/pending", tags=["pending"])


@router.get("/", response_model=list[PendingResponse])
async def get_pending(
    source_doc_id: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await reference_service.get_pending(db, current_user.id, source_doc_id)


@router.get("/grouped", response_model=list[PendingGroupResponse])
async def get_grouped_pending(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await reference_service.get_grouped_pending(db, current_user.id)


@router.put("/{ref_id}/resolve")
async def resolve_reference(
    ref_id: str,
    body: ResolveRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DocumentReference).where(
            DocumentReference.id == ref_id,
            DocumentReference.user_id == current_user.id,
        )
    )
    ref = result.scalar_one_or_none()
    if not ref:
        raise HTTPException(status_code=404, detail="Referencia no encontrada")

    if body.document_id:
        doc_result = await db.execute(
            select(Document).where(
                Document.id == body.document_id,
                Document.user_id == current_user.id,
            )
        )
        if not doc_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Documento no encontrado")

    ref.resolved_document_id = body.document_id
    await db.commit()
    return {"status": "ok"}


@router.delete("/{ref_id}/resolve", status_code=status.HTTP_204_NO_CONTENT)
async def unresolve_reference(
    ref_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DocumentReference).where(
            DocumentReference.id == ref_id,
            DocumentReference.user_id == current_user.id,
        )
    )
    ref = result.scalar_one_or_none()
    if not ref:
        raise HTTPException(status_code=404, detail="Referencia no encontrada")

    ref.resolved_document_id = None
    await db.commit()
