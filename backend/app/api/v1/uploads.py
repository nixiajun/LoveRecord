from __future__ import annotations
import json

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.deps import get_current_couple, get_current_user, get_db_session
from app.models.couple import Couple
from app.models.message import Message
from app.models.user import User
from app.parsers.registry import get_parser_for_filename
from app.schemas.parser_options import ParserOptionsIn
from app.schemas.upload import UploadDetailOut, UploadOut
from app.services.core.couple_access import ensure_couple_id
from app.services.ingest.message_pipeline import delete_upload_record
from app.services.ingest.upload_service import create_upload_record
from app.services.openclaw.openclaw_push_service import OpenClawPushService, build_upload_completed_push

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post("", response_model=UploadOut)
async def create_upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    parser_options: str | None = Form(
        default=None,
        description='可选 JSON：{"time_key":"...","speaker_key":"...","content_key":"...","json_list_key":"..."}，用于 CSV/JSON 自定义列名或键路径',
    ),
    db: Session = Depends(get_db_session),
    couple: Couple = Depends(get_current_couple),
    user: User = Depends(get_current_user),
):
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="缺少文件名")
    try:
        get_parser_for_filename(file.filename)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    field_mapping = None
    if parser_options and parser_options.strip():
        try:
            raw = json.loads(parser_options)
            if not isinstance(raw, dict):
                raise ValueError("parser_options 必须是 JSON 对象")
            opts = ParserOptionsIn.model_validate(raw)
            field_mapping = opts.to_mapping()
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"parser_options 不是合法 JSON: {e}") from e
        except (ValueError, ValidationError) as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    data = await file.read()
    try:
        up = create_upload_record(
            db, couple, user, file.filename, data, field_mapping=field_mapping
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"处理失败: {e}") from e
    ensure_couple_id(couple, up.couple_id)
    if up.parse_status == "done" and (
        (settings.openclaw_push_webhook_url or "").strip()
        or (settings.openclaw_me_push_webhook_url or "").strip()
    ):
        msg_count = (
            db.query(func.count(Message.id))
            .filter(Message.couple_id == couple.id, Message.upload_id == up.id)
            .scalar()
            or 0
        )

        def _push_upload_done(payload: dict) -> None:
            OpenClawPushService().push_json_to_me_bot(payload)

        background_tasks.add_task(
            _push_upload_done,
            build_upload_completed_push(
                couple_id=couple.id,
                user_id=user.id,
                upload_id=up.id,
                filename=up.original_filename,
                parse_status=up.parse_status,
                message_count=int(msg_count),
            ),
        )
    return up


@router.get("", response_model=list[UploadOut])
def list_uploads(db: Session = Depends(get_db_session), couple: Couple = Depends(get_current_couple)):
    from app.models.chat_upload import ChatUpload

    rows = (
        db.query(ChatUpload)
        .filter(ChatUpload.couple_id == couple.id)
        .order_by(ChatUpload.id.desc())
        .limit(100)
        .all()
    )
    return rows


@router.get("/{upload_id}", response_model=UploadDetailOut)
def get_upload_detail(
    upload_id: int,
    db: Session = Depends(get_db_session),
    couple: Couple = Depends(get_current_couple),
):
    from app.models.chat_upload import ChatUpload

    up = db.get(ChatUpload, upload_id)
    if up is None or up.couple_id != couple.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="上传记录不存在")

    uploader = db.get(User, up.uploaded_by)
    display = uploader.display_name if uploader else "未知用户"

    msg_count = (
        db.query(func.count(Message.id))
        .filter(Message.couple_id == couple.id, Message.upload_id == upload_id)
        .scalar()
        or 0
    )

    day_rows = db.execute(
        select(Message.day_key)
        .where(Message.couple_id == couple.id, Message.upload_id == upload_id)
        .distinct()
        .order_by(Message.day_key.asc())
    ).all()
    day_keys = [r[0] for r in day_rows]

    return UploadDetailOut(
        id=up.id,
        couple_id=up.couple_id,
        uploaded_by=up.uploaded_by,
        uploaded_by_display_name=display,
        source_type=up.source_type,
        original_filename=up.original_filename,
        file_path=up.file_path,
        upload_date=up.upload_date,
        parse_status=up.parse_status,
        parse_error=up.parse_error,
        raw_text_excerpt=up.raw_text_excerpt,
        created_at=up.created_at,
        updated_at=up.updated_at,
        message_count=int(msg_count),
        affected_day_keys=day_keys,
    )


@router.delete("/{upload_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_upload(
    upload_id: int,
    db: Session = Depends(get_db_session),
    couple: Couple = Depends(get_current_couple),
):
    try:
        delete_upload_record(db, couple, upload_id)
        db.commit()
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    return None
