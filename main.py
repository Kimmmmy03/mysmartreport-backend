"""
MySmartReport Backend — FastAPI Entry Point
"""

import os
import json
import firebase_admin
from firebase_admin import credentials
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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


@app.get("/")
async def root():
    return {"message": "MySmartReport API is running", "version": "1.0.0"}
