# negotiation router - Ackerman technique
from fastapi import APIRouter
from pydantic import BaseModel, field_validator
from app.database import get_connection
from typing import Union

router = APIRouter()

# we never pay more than the loadboard rate
CEILING_PRICE = 1.5

# Ackerman steps - we start low and come up slowly
ACKERMAN_STEPS = {
    3: 0.80,   # anchor - our first offer (80% of loadboard)
    2: 0.90,   # round 2 - come up to 90%
    1: 0.995,  # round 1 - almost full rate (Ackerman precise number)
}

class NegotiationRequest(BaseModel):
    call_id:       str
    load_id:       str
    carrier_offer: Union[float, str]
    round_left:    Union[int, str]

    @field_validator("carrier_offer", mode="before")
    @classmethod
    def parse_carrier_offer(cls, v):
        if v is None or str(v).strip() == "":
            return 0.0
        try:
            return float(str(v).strip())
        except Exception:
            return 0.0

    @field_validator("round_left", mode="before")
    @classmethod
    def parse_round(cls, v):
        if v is None or str(v).strip() == "":
            return 3
        try:
            return int(float(str(v).strip()))
        except Exception:
            return 3

    @field_validator("load_id", mode="before")
    @classmethod
    def parse_load_id(cls, v):
        if v is None or str(v).strip() == "":
            return "LD-015"
        return str(v).strip()

    @field_validator("call_id", mode="before")
    @classmethod
    def parse_call_id(cls, v):
        if v is None or str(v).strip() == "":
            return "unknown"
        return str(v).strip()

def get_loadboard_rate(load_id: str) -> float:
    """Get the listed rate for a load from the database."""
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT loadboard_rate FROM loads WHERE load_id = ?",
        (load_id,)
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return 2400.0  # default rate
    return row["loadboard_rate"]

def calculate_our_offer(round_number: int, loadboard_rate: float):
    """Calculate our offer for this round using Ackerman steps."""
    percentage = ACKERMAN_STEPS.get(round_number)
    if percentage is None:
        return None
    return round(loadboard_rate * percentage, 2)

def evaluate_carrier_offer(
    carrier_offer:     float,
    our_current_offer: float,
    loadboard_rate:    float
) -> str:
    """
    Broker wants to pay carrier as LITTLE as possible.
    - carrier accepts our offer or lower → accept
    - carrier demands more than loadboard rate → reject
    - in between → counter with slightly higher offer
    """
    # carrier accepts our price or asks for less → accept
    if carrier_offer <= our_current_offer:
        return "accept"

    # carrier demands more than loadboard rate → reject
    elif carrier_offer > loadboard_rate * CEILING_PRICE:
        return "reject"

    # carrier wants more but below ceiling → counter
    else:
        return "counter"

@router.post("/negotiate")
def negotiate(request: NegotiationRequest):
    """
    Always returns the same keys:
    decision, message, final_price, our_offer, round_left
    """
    # step 1 - get loadboard rate
    loadboard_rate = get_loadboard_rate(request.load_id)

    # step 2 - our current offer for this round
    our_current_offer = calculate_our_offer(
        request.round_left,
        loadboard_rate
    )

    if our_current_offer is None:
        return {
            "decision":    "reject",
            "message":     "We've reached our limit. Thank you for your time.",
            "final_price": None,
            "our_offer":   None,
            "round_left":  0
        }

    # step 3 - evaluate carrier's offer
    decision = evaluate_carrier_offer(
        request.carrier_offer,
        our_current_offer,
        loadboard_rate
    )

    if decision == "accept":
        return {
            "decision":    "accept",
            "message":     "We have a deal! Transfer was successful, "
                          "you can now wrap up the conversation.",
            "final_price": request.carrier_offer,
            "our_offer":   our_current_offer,
            "round_left":  0
        }

    if decision == "reject":
        return {
            "decision":    "reject",
            "message":     f"Unfortunately we can't go above "
                          f"${loadboard_rate:,.2f}. Have a good day!",
            "final_price": None,
            "our_offer":   None,
            "round_left":  0
        }

    # counter - move to next round
    next_round = request.round_left - 1
    next_offer = calculate_our_offer(next_round, loadboard_rate)

    if next_offer is None or next_round < 0:
        return {
            "decision":    "reject",
            "message":     "We've reached our final offer. Thank you for your time.",
            "final_price": None,
            "our_offer":   None,
            "round_left":  0
        }

    return {
        "decision":    "counter",
        "message":     f"Best I can do is ${next_offer:,.2f}. What do you say?",
        "final_price": None,
        "our_offer":   next_offer,
        "round_left":  next_round
    }
