# negotiation router - Ackerman technique
from fastapi import APIRouter
from pydantic import BaseModel, field_validator
from app.database import get_connection
from typing import Union
router = APIRouter()

FLOOR_PRICE = 0.75  
# Ackerman steps - we start low and come up slowly
# this signals to the carrier we are approaching our limit
ACKERMAN_STEPS = {
    0: 0.80,   # anchor - our first offer (80% of loadboard)
    1: 0.90,   # round 1 - big jump up
    2: 0.95,   # round 2 - smaller jump
    3: 0.997   # round 3 - precise number (Ackerman technique)
}

class NegotiationRequest(BaseModel):
    call_id:       str                  # for tracking
    load_id:       str                  # which load we're negotiating
    carrier_offer: Union[float, str]    # what the carrier is offering
    round:         Union[int, str]      # which round (0, 1, 2, 3)

    @field_validator("carrier_offer", mode="before")
    @classmethod
    def parse_carrier_offer(cls, v):
        if v is None or str(v).strip() == "":
            return 0.0
        try:
            return float(str(v).strip())
        except Exception:
            return 0.0

    @field_validator("round", mode="before")
    @classmethod
    def parse_round(cls, v):
        if v is None or str(v).strip() == "":
            return 0
        try:
            return int(float(str(v).strip()))
        except Exception:
            return 0

    @field_validator("load_id", mode="before")
    @classmethod
    def parse_load_id(cls, v):
        if v is None or str(v).strip() == "":
            return "LD-015"  # default load
        return str(v).strip()

    @field_validator("call_id", mode="before")
    @classmethod
    def parse_call_id(cls, v):
        if v is None or str(v).strip() == "":
            return "unknown"
        return str(v).strip()
def get_loadboard_rate(load_id: str) -> float:
    """Get the listed rate for a load from the database."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT loadboard_rate FROM loads WHERE load_id = ?", (load_id,))
    row = cursor.fetchone()
    conn.close()
    return row["loadboard_rate"]

def calculate_our_offer(round_number: int, loadboard_rate: float):
    """Calculate our counter offer for this round using Ackerman steps."""
    percentage = ACKERMAN_STEPS.get(round_number)
    if percentage is None:
        return None  # no more rounds
    return round(loadboard_rate * percentage, 2)

def evaluate_carrier_offer(carrier_offer: float, our_current_offer: float, loadboard_rate: float) -> str:
    """
    Decide whether to accept, counter or reject carrier's offer.
    - carrier meets or beats our current offer → accept
    - carrier is below floor price → reject  
    - in between → counter
    """
    # carrier met our price → accept
    if carrier_offer >= our_current_offer:
        return "accept"
    # carrier is too low → reject
    elif carrier_offer < loadboard_rate * FLOOR_PRICE:
        return "reject"
    # in between → keep negotiating
    else:
        return "counter"


@router.post("/negotiate")
def negotiate(request: NegotiationRequest):
    """
    Always returns the same keys:
    - decision, message, final_price, our_offer, round
    """
    # step 1 - get loadboard rate
    loadboard_rate = get_loadboard_rate(request.load_id)

    # step 2 - our current offer for this round
    our_current_offer = calculate_our_offer(request.round, loadboard_rate)

    if our_current_offer is None:
        return {
            "decision":    "reject",
            "message":     "We've reached our limit. Thank you for your time.",
            "final_price": None,
            "our_offer":   None,
            "round":       request.round
        }

    # step 3 - evaluate
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
            "round":       request.round
        }

    if decision == "reject":
        return {
            "decision":    "reject",
            "message":     f"Unfortunately we can't go below "
                          f"${loadboard_rate * FLOOR_PRICE:,.2f}. Have a good day!",
            "final_price": None,
            "our_offer":   None,
            "round":       request.round
        }

    # counter
    next_round = request.round + 1
    next_offer = calculate_our_offer(next_round, loadboard_rate)

    if next_offer is None:
        return {
            "decision":    "reject",
            "message":     "We've reached our final offer. Thank you for your time.",
            "final_price": None,
            "our_offer":   None,
            "round":       next_round
        }

    return {
        "decision":    "counter",
        "message":     f"Best I can do is ${next_offer:,.2f}. What do you say?",
        "final_price": None,
        "our_offer":   next_offer,
        "round":       next_round
    }