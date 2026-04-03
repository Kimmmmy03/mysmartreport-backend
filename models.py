"""
MySmartReport Backend — Pydantic Models
"""

from pydantic import BaseModel, Field
from typing import Optional


class GroupAttendance(BaseModel):
    """A single student group with its attendance count."""
    nama: str = Field(..., description="Group name from KUMPULAN DIAJAR")
    jumlah_pelajar: int = Field(23, description="Total number of students in this group")
    kehadiran: int = Field(23, description="Number of students who attended")


class WeekData(BaseModel):
    """Single week of the teaching plan."""
    minggu: int = Field(..., description="Week number")
    tarikh: str = Field("", description="Date range for this week")
    topik: str = Field("", description="Topic for this week")
    jam: str = Field("", description="Hours / contact time breakdown")
    hpk: str = Field("HPK", description="HPK")
    catatan: str = Field("", description="Catatan/Refleksi from input")
    hasil_pembelajaran: str = Field("", description="AI-generated learning outcomes")
    strategi_aktiviti: str = Field("", description="AI-generated teaching strategies")
    refleksi: str = Field("", description="AI-generated reflection for Kuliah")
    refleksi_tutorial: str = Field("", description="AI-generated reflection for Tutorial")
    refleksi_epembelajaran: str = Field("", description="AI-generated reflection for E-pembelajaran")


class UploadMetadata(BaseModel):
    """Metadata extracted from input.xlsx — all fields parsed."""
    nama_kursus: str = ""
    kod_kursus: str = ""
    semester: str = ""
    tahun: str = ""
    pensyarah: str = ""
    jabatan: str = ""
    program: str = ""
    ambilan: str = ""
    jumlah_kredit: str = ""
    kumpulan_diajar: list[str] = Field(default_factory=list)


class SessionDraft(BaseModel):
    """Full draft for a session — stored in-memory."""
    session_id: str
    metadata: UploadMetadata
    weeks: list[WeekData] = Field(default_factory=list)
    tarikh: str = ""
    kumpulan_list: list[GroupAttendance] = Field(default_factory=list)


class UploadResponse(BaseModel):
    """Response after uploading input.xlsx."""
    session_id: str
    metadata: UploadMetadata
    weeks: list[WeekData]


class GenerateDraftRequest(BaseModel):
    """Request to generate an AI-enriched draft."""
    session_id: str
    tarikh: str = ""
    kumpulan_list: list[GroupAttendance] = Field(default_factory=list)
    selected_weeks: list[int] = Field(default_factory=list, description="Weeks to enrich; empty = all")
    nama_kursus: Optional[str] = None
    kod_kursus: Optional[str] = None
    pensyarah: Optional[str] = None
    weeks: Optional[list[WeekData]] = None
    detail_level: str = Field("normal", description="AI detail level: 'ringkas', 'normal', or 'terperinci'")


class UpdateDraftRequest(BaseModel):
    """Request to update a draft with user edits."""
    weeks: list[WeekData]
    tarikh: Optional[str] = None
    kumpulan_list: Optional[list[GroupAttendance]] = None


class DownloadRequest(BaseModel):
    """Request to download selected weeks as Excel."""
    session_id: str
    selected_weeks: list[int] = Field(..., description="List of week numbers to include")
    format: str = Field("zip", description="Download format: 'xlsx' or 'zip'")
    include_input: bool = Field(False, description="Whether to include the original input file in xlsx output")
    group_index: Optional[int] = Field(None, description="Specific group index for per-group xlsx download")
