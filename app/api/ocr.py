import io
import uuid

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.services.progress import progress_tracker

router = APIRouter(prefix="/ocr", tags=["ocr"])

VALID_EXTENSIONS = (".pdf",)


@router.post("/extract")
async def extract_pdf(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not file.filename or not file.filename.lower().endswith(VALID_EXTENSIONS):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Solo se aceptan archivos PDF")

    pdf_bytes = await file.read()
    if len(pdf_bytes) == 0:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="El archivo esta vacio")

    print(f"\n  📤 OCR: Solicitud recibida de '{current_user.email}' — archivo: {file.filename} ({len(pdf_bytes)//1024}KB)")

    task_id = str(uuid.uuid4())

    await progress_tracker.init(task_id, total=1, message="Iniciando extraccion OCR...")

    from app.services.ocr_service import extract_pdf_to_word
    from app.core.config import settings

    async def on_progress(current, total, message):
        await progress_tracker.update(task_id, "processing", current, total, message)

    try:
        await progress_tracker.update(task_id, "processing", 0, 1, "Procesando PDF...")

        ocr_model = "gemma4:26b-32k"
        docx_bytes = await extract_pdf_to_word(pdf_bytes, file.filename, ocr_model, on_progress=on_progress)

        await progress_tracker.set_done(task_id, chunks=1)

        base_name = file.filename.rsplit(".", 1)[0]
        docx_filename = f"{base_name}.docx"

        print(f"  📤 OCR: Enviando .docx a '{current_user.email}' — {len(docx_bytes)//1024}KB")

        return StreamingResponse(
            io.BytesIO(docx_bytes),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{docx_filename}"'},
        )
    except Exception as e:
        await progress_tracker.set_error(task_id, str(e))
        print(f"  ❌ OCR: Error procesando {file.filename}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error procesando PDF: {e}")


@router.get("/progress/{task_id}")
async def get_ocr_progress(
    task_id: str,
    current_user: User = Depends(get_current_user),
):
    return await progress_tracker.get(task_id)
