from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.upload_service import UploadService

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post("/api")
async def upload_file(file: UploadFile = File(...), db: Session = Depends(get_db)):
    return await UploadService(db).save_upload(file)
