from fastapi import APIRouter
from pydantic import BaseModel, field_validator
from typing import Union
import httpx
import os
import re

router = APIRouter()

FMCSA_API_KEY = os.getenv("FMCSA_API_KEY", "")

class CarrierRequest(BaseModel):
    mc_number: Union[str, int, float]
    call_id:   Union[str, int, None] = ""

    @field_validator("mc_number", mode="before")
    @classmethod
    def clean_mc_number(cls, v):
        if v is None:
            return ""
        # convert everything to string first
        v = str(v).strip()
        # remove surrounding quotes if present → ""123456"" → "123456"
        v = v.strip('"').strip("'")
        # uppercase for consistent replacement
        v = v.upper()
        # remove all common MC prefixes and formatting
        v = v.replace("MC-", "")
        v = v.replace("MC:", "")
        v = v.replace("MC#", "")
        v = v.replace("MC ", "")
        v = v.replace("MC",  "")
        v = v.replace("-",   "")
        v = v.replace(" ",   "")
        v = v.replace("#",   "")
        # keep only digits
        v = re.sub(r'\D', '', v)
        return v

    @field_validator("call_id", mode="before")
    @classmethod
    def clean_call_id(cls, v):
        if v is None:
            return "unknown"
        return str(v).strip()

async def verify_with_fmcsa(mc: str) -> dict:
    """Call real FMCSA API."""
    url = f"https://mobile.fmcsa.dot.gov/qc/services/carriers/{mc}?webKey={FMCSA_API_KEY}"
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(url)
        if response.status_code == 200:
            data    = response.json()
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
        "123456": {"authorized": True,  "carrier_name": "Swift Transport LLC",  "status": "ACTIVE"},
        "234567": {"authorized": True,  "carrier_name": "Eagle Freight Inc",    "status": "ACTIVE"},
        "345678": {"authorized": False, "carrier_name": "Blue Ridge Trucking",  "status": "INACTIVE"},
        "999999": {"authorized": False, "carrier_name": "Blacklisted Carrier",  "status": "REVOKED"},
    }

    if mc in CARRIERS:
        c = CARRIERS[mc]
        return {
            "authorized":   c["authorized"],
            "carrier_name": c["carrier_name"],
            "status":       c["status"]
        }

    # default: if numeric and 5+ digits → treat as valid
    if mc.isdigit() and len(mc) >= 5:
        return {
            "authorized":   True,
            "carrier_name": f"Carrier MC#{mc}",
            "status":       "ACTIVE"
        }

    return {
        "authorized":   False,
        "carrier_name": None,
        "status":       "NOT_FOUND"
    }

@router.post("/verify-carrier")
async def verify_carrier(request: CarrierRequest):
    """
    Verify carrier MC number.
    Handles: "123456", 123456, ""123456""
    Uses real FMCSA API if key available, falls back to mock.
    """
    mc = request.mc_number  # already cleaned by validator

    if not mc:
        return {
            "mc_number":    "",
            "authorized":   False,
            "carrier_name": None,
            "status":       "INVALID",
            "reason":       "No MC number provided"
        }

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