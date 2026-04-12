from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import Session

from app.integrations import get_storage_provider
from app.models.chat_upload import ChatUpload
from app.models.couple import Couple
from app.models.user import User
from app.parsers.base import ParserFieldMapping
from app.parsers.registry import get_parser_for_filename
from app.services.ingest.message_pipeline import run_parse_for_upload
from app.services.core.timekeys import to_day_key


def create_upload_record(
    db: Session,
    couple: Couple,
    user: User,
    filename: str,
    file_bytes: bytes,
    field_mapping: ParserFieldMapping | None = None,
) -> ChatUpload:
    storage = get_storage_provider()
    ext = Path(filename).suffix or ".txt"
    key = f"couple_{couple.id}/{uuid4().hex}{ext}"
    path = storage.save_bytes(key, file_bytes)

    ext_lower = Path(filename).suffix.lower()
    if ext_lower not in (".csv", ".json"):
        field_mapping = None

    parser = get_parser_for_filename(filename)
    upload_date = to_day_key(datetime.now(timezone.utc), couple.timezone, couple.day_start_hour)

    upload = ChatUpload(
        couple_id=couple.id,
        uploaded_by=user.id,
        source_type=parser.source_type,
        original_filename=filename,
        file_path=path,
        upload_date=upload_date,
        parse_status="pending",
    )
    db.add(upload)
    db.commit()
    db.refresh(upload)

    try:
        run_parse_for_upload(db, couple, upload, file_bytes, field_mapping=field_mapping)
        db.commit()
    except Exception:
        db.commit()
        raise
    db.refresh(upload)
    return upload
