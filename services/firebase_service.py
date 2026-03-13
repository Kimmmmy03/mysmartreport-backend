"""
MySmartReport — Storage Service (Firebase Storage + Firestore + In-Memory Cache)

L1: In-memory cache for fast access during session
L2: Firebase Storage for uploaded files, Firestore for metadata/dedup/patterns
"""

import hashlib
import json
import traceback
from datetime import datetime
from typing import Optional
from models import SessionDraft

# ---------------------------------------------------------------------------
# In-memory L1 cache
# ---------------------------------------------------------------------------
_memory_store: dict[str, dict] = {}
_input_files: dict[str, bytes] = {}
_file_hashes: dict[str, str] = {}  # content_hash → session_id
_extraction_patterns: dict[str, dict] = {}  # fingerprint → pattern_data


# ---------------------------------------------------------------------------
# Firebase helpers (lazy init)
# ---------------------------------------------------------------------------
_bucket = None
_db = None


def _get_bucket():
    """Lazy-init Firebase Storage bucket."""
    global _bucket
    if _bucket is None:
        try:
            from firebase_admin import storage
            _bucket = storage.bucket()
            print(f"[Firebase] Storage bucket initialized: {_bucket.name}")
        except Exception as e:
            print(f"[Firebase] Storage bucket init failed: {e}")
    return _bucket


def _get_db():
    """Lazy-init Firestore client."""
    global _db
    if _db is None:
        try:
            from firebase_admin import firestore
            _db = firestore.client()
            print("[Firebase] Firestore client initialized")
        except Exception as e:
            print(f"[Firebase] Firestore init failed: {e}")
    return _db


# ---------------------------------------------------------------------------
# Firebase Storage — Upload/Download files
# ---------------------------------------------------------------------------
def upload_to_storage(session_id: str, file_bytes: bytes, filename: str) -> bool:
    """Upload a file to Firebase Storage under uploads/{session_id}/{filename}."""
    try:
        bucket = _get_bucket()
        if not bucket:
            return False
        blob_path = f"uploads/{session_id}/{filename}"
        blob = bucket.blob(blob_path)
        blob.upload_from_string(file_bytes, content_type="application/octet-stream")
        print(f"[Firebase Storage] Uploaded {blob_path} ({len(file_bytes)} bytes)")
        return True
    except Exception as e:
        print(f"[Firebase Storage] Upload failed: {e}")
        traceback.print_exc()
        return False


def download_from_storage(session_id: str, filename: str) -> Optional[bytes]:
    """Download a file from Firebase Storage."""
    try:
        bucket = _get_bucket()
        if not bucket:
            return None
        blob_path = f"uploads/{session_id}/{filename}"
        blob = bucket.blob(blob_path)
        if blob.exists():
            return blob.download_as_bytes()
        return None
    except Exception as e:
        print(f"[Firebase Storage] Download failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Firebase Storage — Failed Uploads
# ---------------------------------------------------------------------------
def store_failed_upload(file_bytes: bytes, filename: str, error_msg: str,
                        user_email: str = "anonymous", user_uid: str = "") -> bool:
    """Store a failed upload file in Firebase Storage and log to Firestore."""
    try:
        import uuid
        fail_id = str(uuid.uuid4())[:8]
        
        # Upload file to Firebase Storage under failed_uploads/
        bucket = _get_bucket()
        if bucket:
            blob_path = f"failed_uploads/{fail_id}/{filename}"
            blob = bucket.blob(blob_path)
            blob.upload_from_string(file_bytes, content_type="application/octet-stream")
            print(f"[Firebase Storage] Failed file stored: {blob_path}")
        
        # Log to Firestore
        db = _get_db()
        if db:
            db.collection("failed_uploads").document(fail_id).set({
                "filename": filename,
                "error": str(error_msg)[:500],
                "user_email": user_email,
                "user_uid": user_uid,
                "file_size": len(file_bytes),
                "storage_path": f"failed_uploads/{fail_id}/{filename}",
                "created_at": _server_timestamp(),
            })
            print(f"[Firestore] Failed upload logged: {fail_id} by {user_email}")
        return True
    except Exception as e:
        print(f"[Firebase] Store failed upload error: {e}")
        return False


def download_failed_file(fail_id: str) -> tuple[Optional[bytes], str]:
    """Download a failed file from Firebase Storage. Returns (bytes, filename)."""
    try:
        db = _get_db()
        if not db:
            return None, ""
        doc = db.collection("failed_uploads").document(fail_id).get()
        if not doc.exists:
            return None, ""
        data = doc.to_dict()
        storage_path = data.get("storage_path", "")
        filename = data.get("filename", "unknown")
        
        bucket = _get_bucket()
        if not bucket or not storage_path:
            return None, filename
        blob = bucket.blob(storage_path)
        if blob.exists():
            return blob.download_as_bytes(), filename
        return None, filename
    except Exception as e:
        print(f"[Firebase] Download failed file error: {e}")
        return None, ""


def delete_failed_upload(fail_id: str) -> bool:
    """Delete a failed upload from both Storage and Firestore."""
    try:
        db = _get_db()
        if db:
            doc = db.collection("failed_uploads").document(fail_id).get()
            if doc.exists:
                data = doc.to_dict()
                storage_path = data.get("storage_path", "")
                
                # Delete from Storage
                if storage_path:
                    bucket = _get_bucket()
                    if bucket:
                        blob = bucket.blob(storage_path)
                        if blob.exists():
                            blob.delete()
                            print(f"[Firebase Storage] Deleted: {storage_path}")
                
                # Delete from Firestore
                db.collection("failed_uploads").document(fail_id).delete()
                print(f"[Firestore] Deleted failed upload: {fail_id}")
                return True
        return False
    except Exception as e:
        print(f"[Firebase] Delete failed upload error: {e}")
        return False


# ---------------------------------------------------------------------------
# Firestore — Dedup & Extraction Results
# ---------------------------------------------------------------------------
def store_extraction_result(session_id: str, metadata_dict: dict,
                            weeks_count: int, filename: str) -> bool:
    """Store extraction result metadata in Firestore for comparison."""
    try:
        db = _get_db()
        if not db:
            return False
        doc_ref = db.collection("extraction_results").document(session_id)
        doc_ref.set({
            "session_id": session_id,
            "filename": filename,
            "metadata": metadata_dict,
            "weeks_count": weeks_count,
            "created_at": _server_timestamp(),
        })
        print(f"[Firestore] Stored extraction result for session {session_id}")
        return True
    except Exception as e:
        print(f"[Firestore] Store extraction result failed: {e}")
        return False


def store_file_hash_firestore(file_hash: str, session_id: str) -> bool:
    """Store file hash in Firestore for persistent dedup across restarts."""
    try:
        db = _get_db()
        if not db:
            return False
        doc_ref = db.collection("file_hashes").document(file_hash[:20])
        doc_ref.set({
            "hash": file_hash,
            "session_id": session_id,
            "created_at": _server_timestamp(),
        })
        return True
    except Exception as e:
        print(f"[Firestore] Store hash failed: {e}")
        return False


def find_duplicate_firestore(file_hash: str) -> Optional[str]:
    """Check Firestore for a duplicate file hash. Returns session_id or None."""
    try:
        db = _get_db()
        if not db:
            return None
        doc_ref = db.collection("file_hashes").document(file_hash[:20])
        doc = doc_ref.get()
        if doc.exists:
            data = doc.to_dict()
            if data.get("hash") == file_hash:
                return data.get("session_id")
        return None
    except Exception as e:
        print(f"[Firestore] Find duplicate failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Firestore — Adaptive Learning Patterns
# ---------------------------------------------------------------------------
def store_learning_pattern(fingerprint: str, pattern_data: dict) -> bool:
    """
    Store an extraction pattern in Firestore for adaptive learning.
    When future uploads have similar layout fingerprints, the system
    can use past successes/failures to improve extraction.
    """
    try:
        db = _get_db()
        if not db:
            return False
        doc_ref = db.collection("learning_patterns").document(fingerprint)

        # Merge with existing pattern data if it exists
        existing = doc_ref.get()
        if existing.exists:
            old_data = existing.to_dict()
            # Increment attempt counter
            pattern_data["attempts"] = old_data.get("attempts", 0) + 1
            # Track fields that were previously missing but now found
            old_missing = set(old_data.get("fields_missing", []))
            new_found = set(pattern_data.get("fields_found", []))
            pattern_data["newly_resolved"] = list(old_missing & new_found)
        else:
            pattern_data["attempts"] = 1

        pattern_data["updated_at"] = _server_timestamp()
        doc_ref.set(pattern_data, merge=True)
        print(f"[Firestore] Learning pattern stored: fp={fingerprint}, "
              f"attempts={pattern_data.get('attempts', 1)}")
        return True
    except Exception as e:
        print(f"[Firestore] Store learning pattern failed: {e}")
        return False


def get_learning_pattern(fingerprint: str) -> Optional[dict]:
    """Retrieve a known extraction pattern from Firestore."""
    try:
        db = _get_db()
        if not db:
            return None
        doc = db.collection("learning_patterns").document(fingerprint).get()
        if doc.exists:
            return doc.to_dict()
        return None
    except Exception as e:
        print(f"[Firestore] Get learning pattern failed: {e}")
        return None


def _server_timestamp():
    """Get Firestore server timestamp."""
    try:
        from firebase_admin import firestore
        return firestore.SERVER_TIMESTAMP
    except Exception:
        from datetime import datetime
        return datetime.utcnow().isoformat()


# ---------------------------------------------------------------------------
# Hash & Dedup (L1 in-memory + L2 Firestore)
# ---------------------------------------------------------------------------
def compute_file_hash(file_bytes: bytes) -> str:
    """Compute SHA-256 hash of file contents."""
    return hashlib.sha256(file_bytes).hexdigest()


def find_duplicate(file_hash: str) -> Optional[str]:
    """Check for duplicate: L1 memory first, then L2 Firestore."""
    # L1 — in-memory
    result = _file_hashes.get(file_hash)
    if result:
        return result
    # L2 — Firestore
    result = find_duplicate_firestore(file_hash)
    if result:
        _file_hashes[file_hash] = result  # warm L1 cache
    return result


def register_file_hash(file_hash: str, session_id: str) -> None:
    """Register hash in both L1 memory and L2 Firestore."""
    _file_hashes[file_hash] = session_id
    store_file_hash_firestore(file_hash, session_id)


# ---------------------------------------------------------------------------
# Extraction Pattern Learning (L1 + L2)
# ---------------------------------------------------------------------------
def save_extraction_pattern(fingerprint: str, pattern_data: dict) -> None:
    """Save pattern to L1 memory and L2 Firestore."""
    _extraction_patterns[fingerprint] = pattern_data
    store_learning_pattern(fingerprint, pattern_data)


def get_extraction_pattern(fingerprint: str) -> Optional[dict]:
    """Get pattern from L1 memory first, fallback to L2 Firestore."""
    result = _extraction_patterns.get(fingerprint)
    if result:
        return result
    result = get_learning_pattern(fingerprint)
    if result:
        _extraction_patterns[fingerprint] = result
    return result


def compute_layout_fingerprint(filename: str, header_row: int | None,
                                col_count: int, row_count: int) -> str:
    """Generate a fingerprint for a document's structure."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "unknown"
    raw = f"{ext}|hr={header_row}|cols={col_count}|rows={row_count}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


# ---------------------------------------------------------------------------
# CRUD (L1 in-memory + L2 Firestore)
# ---------------------------------------------------------------------------
def save_draft(session_id: str, draft: SessionDraft) -> None:
    """Persist a draft in L1 memory and L2 Firestore."""
    # 1. Update L1 Memory Cache
    data = draft.model_dump()
    _memory_store[session_id] = data

    # 2. Update L2 Firestore
    try:
        db = _get_db()
        if db:
            db.collection("drafts").document(session_id).set(data)
            print(f"[Firestore] Draft saved: {session_id}")
    except Exception as e:
        print(f"[Firestore] Save draft failed for {session_id}: {e}")


def get_draft(session_id: str) -> Optional[SessionDraft]:
    """Retrieve a draft by session ID from L1 or L2."""
    # 1. Check L1 Memory Cache
    data = _memory_store.get(session_id)
    if data:
        return SessionDraft(**data)

    # 2. Check L2 Firestore
    try:
        db = _get_db()
        if db:
            doc = db.collection("drafts").document(session_id).get()
            if doc.exists:
                data = doc.to_dict()
                _memory_store[session_id] = data  # Warm up L1 cache
                return SessionDraft(**data)
    except Exception as e:
        print(f"[Firestore] Get draft failed for {session_id}: {e}")

    return None


def delete_draft(session_id: str) -> None:
    """Delete a draft from L1 and L2."""
    # 1. Remove from L1 Memory
    _memory_store.pop(session_id, None)
    _input_files.pop(session_id, None)

    # 2. Remove from L2 Firestore
    try:
        db = _get_db()
        if db:
            db.collection("drafts").document(session_id).delete()
            print(f"[Firestore] Draft deleted: {session_id}")
    except Exception as e:
        print(f"[Firestore] Delete draft failed for {session_id}: {e}")


def save_input_file(session_id: str, file_bytes: bytes) -> None:
    """Save original input file bytes (L1 in-memory)."""
    _input_files[session_id] = file_bytes


def get_input_file(session_id: str) -> bytes | None:
    """Retrieve original input file bytes."""
    return _input_files.get(session_id)
