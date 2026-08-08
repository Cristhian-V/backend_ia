from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.services.transbel_service import process_excel

router = APIRouter(prefix="/transbel", tags=["transbel"])


@router.post("/clasificar")
async def clasificar(
    archivo: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not archivo.filename or not (
        archivo.filename.endswith(".xls") or archivo.filename.endswith(".xlsx")
    ):
        raise HTTPException(400, "Archivo Excel requerido (.xls o .xlsx)")

    file_bytes = await archivo.read()

    try:
        result_bytes, download_name = await process_excel(db, file_bytes, archivo.filename)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Error interno: {e}")

    return Response(
        content=result_bytes,
        media_type="application/vnd.ms-excel",
        headers={
            "Content-Disposition": f'attachment; filename="{download_name}"'
        },
    )
