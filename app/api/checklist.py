from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.checklist import Checklist

router = APIRouter(prefix="/checklist", tags=["checklist"])


@router.get("/stats")
async def checklist_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    total_result = await db.execute(select(func.count(Checklist.id)))
    total = total_result.scalar() or 0

    subido_result = await db.execute(
        select(func.count(Checklist.id)).where(Checklist.subido == True)
    )
    subidos = subido_result.scalar() or 0

    by_categoria_result = await db.execute(
        select(Checklist.categoria, func.count(Checklist.id), func.count(Checklist.id).filter(Checklist.subido == True))
        .group_by(Checklist.categoria)
        .order_by(Checklist.categoria)
    )
    categorias = [
        {"categoria": row[0], "total": row[1], "subidos": row[2] or 0}
        for row in by_categoria_result.all()
    ]

    return {
        "total": total,
        "subidos": subidos,
        "porcentaje": round(subidos / total * 100, 1) if total > 0 else 0,
        "categorias": categorias,
    }


@router.get("/")
async def list_checklist(
    categoria: str | None = None,
    subido: bool | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Checklist).order_by(Checklist.categoria, Checklist.codigo)

    if categoria:
        query = query.where(Checklist.categoria == categoria)
    if subido is not None:
        query = query.where(Checklist.subido == subido)

    result = await db.execute(query)
    rows = result.scalars().all()

    return [
        {
            "id": r.id,
            "indice": r.indice,
            "categoria": r.categoria,
            "codigo": r.codigo,
            "subido": r.subido,
            "documento_id": r.documento_id,
        }
        for r in rows
    ]
