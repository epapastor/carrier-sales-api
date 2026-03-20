# verify carrier router
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

# Mock carrier database
CARRIERS = {
    "123456": {"name": "Swift Transport LLC", "status": "ACTIVE",   "authorized": True},
    "234567": {"name": "Eagle Freight Inc",   "status": "ACTIVE",   "authorized": True},
    "345678": {"name": "Blue Ridge Trucking", "status": "INACTIVE", "authorized": False},
    "999999": {"name": "Blacklisted Carrier", "status": "REVOKED",  "authorized": False},
}

class CarrierRequest(BaseModel):
    mc_number: str  # carrier's MC number
    call_id:   str  # unique call ID for tracking

@router.post("/verify-carrier")
def verify_carrier(request: CarrierRequest):
    """Verify if a carrier is authorized to work with us via FMCSA (mocked)."""
    mc = request.mc_number.strip()

    if mc in CARRIERS:
        carrier = CARRIERS[mc]
        return {
            "mc_number":    mc,
            "authorized":   carrier["authorized"],
            "carrier_name": carrier["name"],
            "status":       carrier["status"],
            "reason":       None if carrier["authorized"] else f"Carrier status is {carrier['status']}"
        }

    # default: if numeric and 5+ digits → treat as valid
    if mc.isdigit() and len(mc) >= 5:
        return {
            "mc_number":    mc,
            "authorized":   True,
            "carrier_name": f"Carrier MC#{mc}",
            "status":       "ACTIVE",
            "reason":       None
        }

    return {
        "mc_number":    mc,
        "authorized":   False,
        "carrier_name": None,
        "status":       "NOT_FOUND",
        "reason":       "MC number not found in FMCSA database"
    }
