"""
MySmartReport Backend — FastAPI Entry Point
"""

import os
import json
import firebase_admin
from firebase_admin import credentials
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from firebase_admin import firestore as admin_firestore

from config import settings
from routes.upload import router as upload_router
from routes.draft import router as draft_router
from routes.download import router as download_router
from routes.auth import router as auth_router
from routes.admin import router as admin_router

# Initialize Firebase Admin SDK
firebase_env_cred = os.getenv("FIREBASE_ADMIN_CREDENTIALS")
cred_path = os.path.join(os.path.dirname(__file__), "firebase-adminsdk.json")

if firebase_env_cred:
    # Running in production (Koyeb) using Environment Variables
    cred_dict = json.loads(firebase_env_cred)
    cred = credentials.Certificate(cred_dict)
    firebase_admin.initialize_app(cred, {
        'storageBucket': 'mysmartreport.firebasestorage.app'
    })
elif os.path.exists(cred_path):
    # Running locally using file
    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred, {
        'storageBucket': 'mysmartreport.firebasestorage.app'
    })
else:
    print(f"WARNING: Firebase credentials not found at {cred_path} nor in environment variables.")

app = FastAPI(
    title="MySmartReport API",
    description="Automated weekly teaching plan generator for IPG lecturers",
    version="1.0.0",
)

# CORS — allow Flutter web frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(upload_router, prefix="/api", tags=["Upload"])
app.include_router(draft_router, prefix="/api", tags=["Draft"])
app.include_router(download_router, prefix="/api", tags=["Download"])
app.include_router(auth_router, prefix="/api", tags=["Auth"])
app.include_router(admin_router, prefix="/api", tags=["Admin"])


@app.on_event("startup")
async def sync_admin_roles():
    """Ensure all ADMIN_EMAILS have role='admin' in Firestore."""
    try:
        db = admin_firestore.client()
        for email in settings.ADMIN_EMAILS:
            docs = db.collection("users").where("email", "==", email).limit(1).get()
            for doc in docs:
                if doc.to_dict().get("role") != "admin":
                    doc.reference.update({"role": "admin"})
                    print(f"Synced admin role for {email}")
    except Exception as e:
        print(f"Admin sync warning: {e}")


@app.post("/api/admin/sync-roles")
async def force_sync_admin_roles():
    """Clear all admin roles, then reinject from ADMIN_EMAILS config."""
    db = admin_firestore.client()
    cleared = []
    injected = []

    # Step 1: Clear all existing admins
    admin_docs = db.collection("users").where("role", "==", "admin").get()
    for doc in admin_docs:
        doc.reference.update({"role": "user"})
        cleared.append(doc.to_dict().get("email", doc.id))

    # Step 2: Reinject from config
    for email in settings.ADMIN_EMAILS:
        docs = db.collection("users").where("email", "==", email).limit(1).get()
        for doc in docs:
            doc.reference.update({"role": "admin"})
            injected.append(email)

    return {"cleared": cleared, "injected": injected}


@app.get("/api/debug/users")
async def debug_all_users():
    """DEBUG: List all users and their roles/tiers from Firestore."""
    db = admin_firestore.client()
    docs = db.collection("users").get()
    users = []
    for doc in docs:
        data = doc.to_dict()
        users.append({
            "uid": doc.id,
            "email": data.get("email"),
            "role": data.get("role"),
            "tier": data.get("tier"),
            "premium_until": str(data.get("premium_until")) if data.get("premium_until") else None,
        })
    return {"users": users}


@app.get("/")
async def root():
    return {"message": "MySmartReport API is running", "version": "1.0.0"}
