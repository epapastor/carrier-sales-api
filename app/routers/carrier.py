from fastapi import APIRouter
from pydantic import BaseModel
import httpx
import os

router = APIRouter()

# get FMCSA key from environment variable
FMCSA_API_KEY = os.getenv("FMCSA_API_KEY", "")

class CarrierRequest(BaseModel):
    mc_number: str
    call_id:   str

async def verify_with_fmcsa(mc: str) -> dict:
    """Call real FMCSA API."""
    url = f"https://mobile.fmcsa.dot.gov/qc/services/carriers/{mc}?webKey={FMCSA_API_KEY}"
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(url)
        if response.status_code == 200:
            data = response.json()
            carrier = data.get("content", {}).get("carrier", {})
            allowed = carrier.get("allowedToOperate", "N")
            return {
                "authorized":   allowed == "Y",
                "carrier_name": carrier.get("legalName", "Unknown"),
                "status":       carrier.get("statusCode", "UNKNOWN")
            }
    return None

def verify_with_mock(mc: str) -> dict:
    """Fallback mock if FMCSA key not available or call fails."""
    CARRIERS = {
    "123456": {"authorized": True,  "name": "Swift Transport LLC",  "status": "ACTIVE"},
    "234567": {"authorized": True,  "name": "Eagle Freight Inc",    "status": "ACTIVE"},
    "345678": {"authorized": False, "name": "Blue Ridge Trucking",  "status": "INACTIVE"},
    "999999": {"authorized": False, "name": "Blacklisted Carrier",  "status": "REVOKED"},
    }
    if mc in CARRIERS:
        c = CARRIERS[mc]
        return {"authorized": c["authorized"], "carrier_name": c["name"], "status": c["status"]}
    
    return {"authorized": False, "carrier_name": None, "status": "NOT_FOUND"}

@router.post("/verify-carrier")
async def verify_carrier(request: CarrierRequest):
    """
    Verify carrier MC number.
    Uses real FMCSA API if key is available, falls back to mock.
    """
    mc = request.mc_number.strip().replace("MC", "").replace("-", "")

    result = None

    # try real FMCSA first if key exists
    if FMCSA_API_KEY:
        try:
            result = await verify_with_fmcsa(mc)
        except Exception:
            pass  # fall back to mock if FMCSA fails

    # fall back to mock
    if result is None:
        result = verify_with_mock(mc)

    return {
        "mc_number":    mc,
        "authorized":   result["authorized"],
        "carrier_name": result["carrier_name"],
        "status":       result["status"],
        "reason":       None if result["authorized"] else f"Carrier status: {result['status']}"
    }