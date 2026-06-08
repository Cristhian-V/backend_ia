from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.query_log import QueryLog
from app.schemas.rag import RAGQuery, RAGResponse
from app.schemas.query_log import QueryLogResponse
from app.services.rag import rag_service

router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/query", response_model=RAGResponse)
async def rag_query(body: RAGQuery, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await rag_service.query(body.query, body.top_k)

    log = QueryLog(
        user_id=current_user.id,
        query=body.query,
        answer=result["answer"][:8000],
        model=result["model"],
        chunks_count=len(result["chunks"]),
    )
    db.add(log)
    await db.commit()

    return result


@router.get("/history", response_model=list[QueryLogResponse])
async def get_history(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(QueryLog).where(QueryLog.user_id == current_user.id).order_by(QueryLog.created_at.desc()).limit(50)
    )
    return result.scalars().all()


@router.get("/history/{log_id}", response_model=QueryLogResponse)
async def get_history_item(
    log_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(QueryLog).where(QueryLog.id == log_id, QueryLog.user_id == current_user.id)
    )
    log = result.scalar_one_or_none()
    if not log:
        raise HTTPException(status_code=404, detail="Consulta no encontrada")
    return log
