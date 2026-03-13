from fastapi import APIRouter, Depends, HTTPException
from services.auth_service import get_current_user, require_premium
from firebase_admin import firestore
from datetime import datetime, timezone, timedelta

router = APIRouter()

@router.get("/auth/me")
async def get_my_profile(user: dict = Depends(get_current_user)):
    """Returns the current user's profile."""
    return user

@router.post("/auth/redeem")
async def redeem_promo_code(code: str, user: dict = Depends(get_current_user)):
    """
    Verifies a promo code and upgrades the user to premium if valid.
    """
    uid = user.get("uid")
    if not uid:
        raise HTTPException(401, "Sila log masuk.")

    try:
        db = firestore.client()
        promo_ref = db.collection("promo_codes").document(code)
        promo_doc = promo_ref.get()

        if not promo_doc.exists:
            raise HTTPException(404, "Kod promo tidak sah.")
        
        data = promo_doc.to_dict()
        if data.get("status") == "used":
            raise HTTPException(400, "Kod promo ini telah digunakan.")

        duration_days = data.get("duration_days", 30) # Default 30 if old legacy code was used

        # Atomic update setup
        batch = db.batch()
        batch.update(promo_ref, {
            "status": "used",
            "used_by": user.get("email") or uid
        })
        user_ref = db.collection("users").document(uid)
        
        # Calculate Rolling Expiration
        user_doc_fresh = user_ref.get()
        user_data = user_doc_fresh.to_dict() if user_doc_fresh.exists else {}
        
        now = datetime.now(timezone.utc)
        current_expiration = user_data.get("premium_until")
        
        if current_expiration and current_expiration > now:
            new_expiration = current_expiration + timedelta(days=duration_days)
        else:
            new_expiration = now + timedelta(days=duration_days)

        batch.update(user_ref, {
            "tier": "premium",
            "premium_until": new_expiration
        })
        batch.commit()

        # Format readable expiration date for frontend
        formatted_date = new_expiration.strftime("%d/%m/%Y")
        return {
            "message": f"Berjaya! Akaun anda bernilai Premium sehingga {formatted_date}.",
            "premium_until": new_expiration.isoformat(),
            "duration_days": duration_days,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Ralat sistem: {str(e)}")
