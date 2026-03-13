from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from firebase_admin import auth, firestore
from datetime import datetime, timezone

security = HTTPBearer()

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """
    Verifies the Firebase Auth token and returns the user payload.
    Raises 401 Unauthorized if invalid.
    """
    token = credentials.credentials
    try:
        decoded_token = auth.verify_id_token(token)
        return decoded_token
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token tidak sah atau tamat tempoh: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

def get_current_user(token_payload: dict = Depends(verify_token)) -> dict:
    """
    Returns the user's Firestore document (role, tier, etc.) based on their UID.
    """
    uid = token_payload.get("uid")
    if not uid:
        raise HTTPException(status_code=401, detail="Sila log masuk.")

    try:
        db = firestore.client()
        user_ref = db.collection("users").document(uid)
        user_doc = user_ref.get()
        if not user_doc.exists:
            # Fallback for new users
            return {"uid": uid, "role": "user", "tier": "free"}
        data = user_doc.to_dict()
        data["uid"] = uid

        # Process Expiration Boundary
        if data.get("tier") == "premium":
            premium_until = data.get("premium_until")
            if premium_until:
                if datetime.now(timezone.utc) > premium_until:
                    data["tier"] = "free"
                    
        return data
    except Exception as e:
        # If firestore is not set up correctly yet, permit free access temporarily
        return {"uid": uid, "role": "user", "tier": "free"}

def require_premium(user: dict = Depends(get_current_user)) -> dict:
    """
    Dependency that enforces the user to be 'premium' or 'admin'.
    """
    tier = user.get("tier", "free")
    role = user.get("role", "user")
    if tier != "premium" and role != "admin":
        raise HTTPException(
            status_code=403, 
            detail="Akaun anda (Percuma) tidak dibenarkan. Sila langgan untuk ciri penuh."
        )
    return user
