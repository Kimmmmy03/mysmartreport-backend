"""
MySmartReport — Draft Routes

POST /api/draft/generate — AI-enrich selected weeks for a session.
GET  /api/draft/{session_id} — Retrieve a saved draft.
PUT  /api/draft/{session_id} — Update draft with user edits.
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from models import (
    SessionDraft, GenerateDraftRequest, UpdateDraftRequest, WeekData
)
from services.firebase_service import save_draft, get_draft
from services.gemini_service import enrich_week
from services.auth_service import get_current_user
import asyncio
import json

router = APIRouter()


@router.post("/draft/generate")
async def generate_draft_stream(
    request: GenerateDraftRequest,
    user: dict = Depends(get_current_user)
):
    """
    Stream AI enrichment progress per-week via SSE.
    Sends 'progress' events for each completed week, then 'done' with full draft.
    Requires Firebase Auth Token. Free users can only generate Week 1.
    """
    draft = get_draft(request.session_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Sesi tidak dijumpai.")

    # Restrict Free users to Week 1
    tier = user.get("tier", "free")
    role = user.get("role", "user")
    
    if role != "admin" and tier == "free":
        # Ensure only week 1 is selected
        if request.selected_weeks and any(w != 1 for w in request.selected_weeks):
            raise HTTPException(
                status_code=403, 
                detail="Akaun Percuma hanya boleh menjana Minggu 1. Sila langgan untuk ciri penuh."
            )
        elif not request.selected_weeks:
            request.selected_weeks = [1] # Force to only week 1 if none specified

    # Update user parameters
    draft.tarikh = request.tarikh
    draft.kumpulan_list = request.kumpulan_list

    # Apply metadata overrides from frontend edits
    if request.nama_kursus is not None:
        draft.metadata.nama_kursus = request.nama_kursus
    if request.kod_kursus is not None:
        draft.metadata.kod_kursus = request.kod_kursus
    if request.pensyarah is not None:
        draft.metadata.pensyarah = request.pensyarah

    # Apply per-week tarikh updates from frontend
    if request.weeks:
        tarikh_map = {w.minggu: w.tarikh for w in request.weeks if w.tarikh}
        for week in draft.weeks:
            if week.minggu in tarikh_map:
                week.tarikh = tarikh_map[week.minggu]

    # Filter weeks to enrich (sorted by minggu to ensure sequential processing)
    if request.selected_weeks:
        weeks_to_enrich = sorted(
            [w for w in draft.weeks if w.minggu in request.selected_weeks],
            key=lambda w: w.minggu,
        )
        weeks_to_skip = [w for w in draft.weeks if w.minggu not in request.selected_weeks]
    else:
        weeks_to_enrich = sorted(draft.weeks, key=lambda w: w.minggu)
        weeks_to_skip = []

    total = len(weeks_to_enrich)

    async def event_stream():
        try:
            enriched_weeks = []
            for i, week in enumerate(weeks_to_enrich):
                # Send progress event
                progress_data = json.dumps({
                    "current": i + 1,
                    "total": total,
                    "minggu": week.minggu,
                    "topik": week.topik,
                })
                yield f"event: progress\ndata: {progress_data}\n\n"

                # Enrich this week
                result = await enrich_week(
                    week.topik, week.minggu,
                    nama_kursus=draft.metadata.nama_kursus,
                    program=draft.metadata.program,
                    detail_level=request.detail_level,
                )
                week_dict = week.model_dump()
                week_dict.update(result)
                enriched_weeks.append(WeekData(**week_dict))

                # Small delay between requests
                if total > 1 and i < total - 1:
                    await asyncio.sleep(1)

            # Merge enriched weeks back with skipped weeks
            all_weeks = enriched_weeks + weeks_to_skip
            all_weeks.sort(key=lambda w: w.minggu)
            draft.weeks = all_weeks

            # Persist
            save_draft(draft.session_id, draft)

            # Send final done event with full draft
            done_data = json.dumps(draft.model_dump())
            yield f"event: done\ndata: {done_data}\n\n"

        except Exception as e:
            print(f"[Generate Error] SSE generator failed: {e}")
            import traceback
            traceback.print_exc()
            error_data = json.dumps({"error": str(e)})
            yield f"event: error\ndata: {error_data}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Transfer-Encoding": "chunked",
            "Access-Control-Allow-Origin": "*",
        },
    )


@router.get("/draft/{session_id}", response_model=SessionDraft)
async def get_session_draft(session_id: str):
    """Retrieve a saved draft by session ID."""
    draft = get_draft(session_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Sesi tidak dijumpai.")
    return draft


@router.put("/draft/{session_id}", response_model=SessionDraft)
async def update_draft(session_id: str, request: UpdateDraftRequest):
    """Update a draft with user edits (modified week data or parameters)."""
    draft = get_draft(session_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Sesi tidak dijumpai.")

    # Update weeks
    draft.weeks = request.weeks

    # Update optional params if provided
    if request.tarikh is not None:
        draft.tarikh = request.tarikh
    if request.kumpulan_list is not None:
        draft.kumpulan_list = request.kumpulan_list

    save_draft(session_id, draft)
    return draft
