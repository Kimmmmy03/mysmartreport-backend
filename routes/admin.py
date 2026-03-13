"""
MySmartReport — Admin Routes

Admin-only API endpoints for managing failed uploads.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from io import BytesIO

from services.firebase_service import download_failed_file, delete_failed_upload

router = APIRouter()


@router.get("/admin/failed-files/{fail_id}/download")
async def download_failed(fail_id: str):
    """Download a failed upload file by its ID."""
    file_bytes, filename = download_failed_file(fail_id)
    if not file_bytes:
        raise HTTPException(status_code=404, detail="Fail tidak dijumpai.")

    return StreamingResponse(
        BytesIO(file_bytes),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.delete("/admin/failed-files/{fail_id}")
async def delete_failed(fail_id: str):
    """Delete a failed upload (removes from both Storage and Firestore)."""
    success = delete_failed_upload(fail_id)
    if not success:
        raise HTTPException(status_code=404, detail="Fail tidak dijumpai.")
    return {"message": "Berjaya dipadam.", "id": fail_id}
