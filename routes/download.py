"""
MySmartReport — Download Route

POST /api/download — Generate and stream Excel or ZIP files.
Supports format=xlsx (single Excel with all weeks as sheets) or format=zip (ZIP with subfolders per kumpulan).
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from models import DownloadRequest
from services.firebase_service import get_draft, get_input_file
from services.excel_generator import generate_combined_zip, generate_single_excel

router = APIRouter()


@router.post("/download")
async def download_weeks(request: DownloadRequest):
    """
    Generate Excel files for selected weeks from the draft.
    format = "xlsx" → single Excel file with each week as a separate sheet.
    format = "zip"  → ZIP with subfolders for each kumpulan group.
    """
    draft = get_draft(request.session_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Sesi tidak dijumpai.")

    if not request.selected_weeks:
        raise HTTPException(status_code=400, detail="Sila pilih sekurang-kurangnya satu minggu.")

    download_format = getattr(request, "format", "zip") or "zip"

    try:
        if download_format == "xlsx":
            # Single Excel workbook with one sheet per week
            input_bytes = get_input_file(request.session_id) if request.include_input else None
            excel_buffer = generate_single_excel(draft, request.selected_weeks, input_bytes=input_bytes)
            kod = draft.metadata.kod_kursus or "RPP"
            weeks_str = "_".join(str(w) for w in sorted(request.selected_weeks))
            filename = f"RPP_Mingguan_{kod} - Minggu {weeks_str}.xlsx"

            return StreamingResponse(
                excel_buffer,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={
                    "Content-Disposition": f'attachment; filename="{filename}"'
                },
            )
        else:
            # ZIP with subfolders
            zip_buffer = generate_combined_zip(draft, request.selected_weeks)
            group_label = draft.kumpulan_list[0].nama if draft.kumpulan_list else "Output"
            num_groups = len(draft.kumpulan_list) if draft.kumpulan_list else 1
            filename = f"RPP_Mingguan_{group_label}{'_dan_lain' if num_groups > 1 else ''}.zip"

            return StreamingResponse(
                zip_buffer,
                media_type="application/zip",
                headers={
                    "Content-Disposition": f'attachment; filename="{filename}"'
                },
            )

    except FileNotFoundError:
        raise HTTPException(
            status_code=500,
            detail="Fail template.xlsx tidak dijumpai di pelayan. Sila hubungi pentadbir."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ralat menjana fail: {str(e)}")
