# negotiation router - Ackerman technique
from fastapi import APIRouter
from pydantic import BaseModel
from app.database import get_connection

router = APIRouter()

FLOOR_PRICE = 0.75  # never go below 75% of loadboard rate

# Ackerman steps - we start low and come up slowly
# this signals to the carrier we are approaching our limit
ACKERMAN_STEPS = {
    0: 0.80,   # anchor - our first offer (80% of loadboard)
    1: 0.90,   # round 1 - big jump up
    2: 0.95,   # round 2 - smaller jump
    3: 0.997   # round 3 - precise number (Ackerman technique)
}

class NegotiationRequest(BaseModel):
    call_id:       str    # for tracking
    load_id:       str    # which load we're negotiating
    carrier_offer: float  # what the carrier is offering us
    round:         int    # which round (0, 1, 2, 3)

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
    Evaluate carrier's offer and respond with accept, counter or reject.
    HappyRobot calls this once per negotiation round.
    """
    # step 1 - get loadboard rate
    loadboard_rate = get_loadboard_rate(request.load_id)

    # step 2 - what is our current offer for this round?
    our_current_offer = calculate_our_offer(request.round, loadboard_rate)

    if our_current_offer is None:
        return {
            "decision": "reject",
            "message":  "We've reached our limit. Thank you for your time."
        }

    # step 3 - evaluate carrier's offer against ours
    decision = evaluate_carrier_offer(
        request.carrier_offer,
        our_current_offer,
        loadboard_rate
    )

    if decision == "accept":
        return {
            "decision":    "accept",
            "final_price": request.carrier_offer,
            "message":     "We have a deal! Transfer was successful, you can now wrap up the conversation."
        }

    if decision == "reject":
        return {
            "decision": "reject",
            "message":  f"Unfortunately we can't go below ${loadboard_rate * FLOOR_PRICE:,.2f}. Have a good day!"
        }

    # counter - next round
    next_round = request.round + 1
    next_offer = calculate_our_offer(next_round, loadboard_rate)

    if next_offer is None:
        return {
            "decision": "reject",
            "message":  "We've reached our final offer. Thank you for your time."
        }

    return {
        "decision":  "counter",
        "our_offer": next_offer,
        "round":     next_round,
        "message":   f"Best I can do is ${next_offer:,.2f}. What do you say?"
    }
