"""
MySmartReport — Upload Route

POST /api/upload — Receives input file, deduplicates, parses, creates a session.
Supports .xlsx, .xls, and .pdf files.
"""

import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException, Header
from typing import Optional

from models import UploadResponse, SessionDraft
from services.parser import parse_input_xlsx, parse_input_pdf, parse_with_ai
from services.firebase_service import (
    save_draft, save_input_file, get_draft,
    compute_file_hash, find_duplicate, register_file_hash,
    compute_layout_fingerprint, save_extraction_pattern,
    upload_to_storage, store_extraction_result, store_failed_upload,
)

router = APIRouter()


@router.post("/upload", response_model=UploadResponse)
async def upload_input_file(
    file: UploadFile = File(...),
    authorization: Optional[str] = Header(None),
):
    """
    Upload an input file (.xlsx/.xls/.pdf).
    Returns parsed metadata, weekly skeleton, and a new session ID.
    Deduplicates identical files and learns extraction patterns.
    """
    # Validate file type
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xls", ".pdf")):
        raise HTTPException(status_code=400, detail="Sila muat naik fail .xlsx atau .pdf sahaja.")

    try:
        file_bytes = await file.read()
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Ralat membaca fail: {str(e)}")

    # --- Deduplication check ---
    file_hash = compute_file_hash(file_bytes)
    existing_session_id = find_duplicate(file_hash)
    if existing_session_id:
        existing_draft = get_draft(existing_session_id)
        if existing_draft:
            print(f"[Upload] Duplicate detected (hash={file_hash[:12]}), returning cached session {existing_session_id}")
            return UploadResponse(
                session_id=existing_session_id,
                metadata=existing_draft.metadata,
                weeks=existing_draft.weeks,
            )

    # --- Identify user from Firebase token (best effort) ---
    user_email = "anonymous"
    user_uid = ""
    if authorization and authorization.startswith("Bearer "):
        try:
            from firebase_admin import auth
            token = authorization.split(" ", 1)[1]
            decoded = auth.verify_id_token(token)
            user_email = decoded.get("email", "unknown")
            user_uid = decoded.get("uid", "")
        except Exception:
            pass

    # --- Extraction ---
    try:
        # Try AI-powered extraction first
        try:
            metadata, weeks = await parse_with_ai(file_bytes, file.filename)
            used_ai = True
            print(f"[Upload] AI extraction successful: {len(weeks)} weeks")
        except Exception as ai_err:
            print(f"[Upload] AI extraction failed, falling back to regex parser: {ai_err}")
            used_ai = False
            
            # Log AI failure to Firebase for admin review, even if fallback succeeds
            store_failed_upload(
                file_bytes=file_bytes,
                filename=f"[AI_FAIL] {file.filename or 'unknown'}",
                error_msg=f"AI Parser Error: {str(ai_err)}",
                user_email=user_email,
                user_uid=user_uid,
            )
            
            # Fallback to traditional regex/position-based parser
            if file.filename.lower().endswith(".pdf"):
                metadata, weeks = parse_input_pdf(file_bytes)
            else:
                metadata, weeks = parse_input_xlsx(file_bytes)
    except Exception as e:
        # Log complete failure (both AI and fallback failed)
        store_failed_upload(
            file_bytes=file_bytes,
            filename=f"[TOTAL_FAIL] {file.filename or 'unknown'}",
            error_msg=f"Total Parser Error: {str(e)}",
            user_email=user_email,
            user_uid=user_uid,
        )
        raise HTTPException(status_code=422, detail=f"Ralat membaca fail: {str(e)}")

    # --- Adaptive learning: log extraction quality ---
    fields_found = []
    fields_missing = []
    for field in ["nama_kursus", "kod_kursus", "pensyarah", "semester"]:
        if getattr(metadata, field, None):
            fields_found.append(field)
        else:
            fields_missing.append(field)

    # Determine layout type
    is_pdf = file.filename.lower().endswith(".pdf")
    layout_type = "pdf_table" if is_pdf else "standard"
    if not is_pdf and weeks and any(w.jam for w in weeks):
        layout_type = "merged_label"  # has jam data = structured xlsx

    fingerprint = compute_layout_fingerprint(
        file.filename,
        header_row=None,  # simplified fingerprint
        col_count=len(fields_found),
        row_count=len(weeks),
    )
    save_extraction_pattern(fingerprint, {
        "layout_type": layout_type,
        "fields_found": fields_found,
        "fields_missing": fields_missing,
        "used_ai_fallback": used_ai,
        "week_count": len(weeks),
    })
    print(f"[Upload] Pattern saved: fp={fingerprint}, layout={layout_type}, "
          f"found={fields_found}, missing={fields_missing}")

    # --- Create session ---
    session_id = str(uuid.uuid4())

    draft = SessionDraft(
        session_id=session_id,
        metadata=metadata,
        weeks=weeks,
    )
    save_draft(session_id, draft)
    save_input_file(session_id, file_bytes)
    register_file_hash(file_hash, session_id)

    # --- Firebase Storage: persist file & extraction result ---
    upload_to_storage(session_id, file_bytes, file.filename or "input.xlsx")
    store_extraction_result(
        session_id=session_id,
        metadata_dict=metadata.model_dump(),
        weeks_count=len(weeks),
        filename=file.filename or "unknown",
    )

    return UploadResponse(
        session_id=session_id,
        metadata=metadata,
        weeks=weeks,
    )
