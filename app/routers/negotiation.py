# evaluate offer
from fastapi import FastAPI
import sqlite3
from app.database import get_connection
"""

La Técnica Ackerman (Regateo en 4 pasos): Si tienes que hacer concesiones de precio, hazlo de forma decreciente para señalar que estás llegando a tu límite:
Tu oferta inicial (ej. 65% de tu objetivo).
Sube al 85% (un salto grande).
Sube al 95% (un salto pequeño).
Precio final con un número muy preciso (ej. 99.7%) y un beneficio no monetario.

"""
app = FastAPI()


class negotiation_state:
    def __init__(self, load_id, offer, offer_number, carrier_acceptance = False):
        self.load_id = load_id
        self.offer = offer
        self.offer_number = offer_number
        self.carrier_acceptance = carrier_acceptance

def get_loadboard_rate(negotiation_info : negotiation_state):
    load_id = negotiation_info.load_id
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT loadboard_rate FROM loads WHERE load_id = ?", (load_id,))
    loadboard_rate = cursor.fetchall()
    return loadboard_rate


def calculate_offer(negotiation_info: negotiation_state, loadboard_rate): 
    #It is the initial anchor
    if negotiation_info.offer_number == 0:
        return loadboard_rate * 0.80
    # Handle up to 3 back and forth’s negotiating the offer
    elif negotiation_info.offer_number == 1: 
        return loadboard_rate * 0.90
    elif negotiation_info.offer_number == 2: 
        return loadboard_rate * 0.97
    elif negotiation_info.offer_number == 3: 
        return loadboard_rate * 0.997
    else:
        return None

@app.post("/negotiate")
def negotating_offer(negotiation_info : negotiation_state):
    offer_number = 0
    loadboard_rate = get_loadboard_rate(negotiation_info)
    while True:
        if negotiation_info.carrier_acceptance:
            print("DEAL done")
            return 1
        else:
            price = calculate_offer(negotiation_info , loadboard_rate)
            if price == None:
                print("Expectation too high")
                return 0
            else:
                offer_number +=1 
                negotiation_info.offer_number =  offer_number
            

from fastapi import FastAPI
from pydantic import BaseModel
from app.database import get_connection

app = FastAPI()

FLOOR_PRICE = 0.75  # never go below 75% of loadboard rate

# Ackerman steps
ACKERMAN_STEPS = {
    0: 0.75,  # anchor - start at 80%
    1: 0.90,  # round 1
    2: 0.95,  # round 2
    3: 0.997  # round 3 - precise number (Ackerman technique)
}

class NegotiationRequest(BaseModel):
    call_id:       str
    load_id:       str
    carrier_offer: float   # what the carrier is offering
    round:         int     # which round we're on (0, 1, 2, 3)

def get_loadboard_rate(load_id: str) -> float:
    conn = get_connection()
    cursor = conn.cursor()
    # fix the SQL query - use ? placeholder
    cursor.execute("SELECT loadboard_rate FROM loads WHERE load_id = ?", (load_id,))
    row = cursor.fetchone()
    conn.close()
    return row["loadboard_rate"]

def calculate_our_offer(round: int, loadboard_rate: float) -> float:
    # get the percentage for this round from ACKERMAN_STEPS
    percentage = ACKERMAN_STEPS.get(0)
    if percentage is None:
        return None
    return round(loadboard_rate * percentage, 2)

def evaluate_carrier_offer(carrier_offer: float, loadboard_rate: float) -> str:
    if carrier_offer >= loadboard_rate * 1.5:
        return  "reject"
    elif carrier_offer < loadboard_rate * 0.75:
        return "accept"
    else:
        return "counter"

@app.post("/negotiate")
def negotiate(request: NegotiationRequest):
    
    # step 1 - get loadboard rate from DB
    loadboard_rate = get_loadboard_rate(request.load_id)
    
    # step 2 - evaluate carrier's offer
    decision = evaluate_carrier_offer(request.carrier_offer, loadboard_rate)
    
    # step 3 - if accept or reject, return immediately
    if decision == "accept":
        return {
            "decision":    "accept",
            "final_price": request.carrier_offer,
            "message":     "Deal! Transferring you to our sales rep now."
        }
    
    if decision == "reject":
        return {
            "decision": "reject",
            "message":  "Unfortunately we can't go that low. Have a good day!"
        }
    
    # step 4 - counter offer using Ackerman
    our_offer = calculate_our_offer(request.round, loadboard_rate)
    
    # step 5 - if no more rounds left
    if our_offer is None:
        return {
            "decision": "reject",
            "message":  "We've reached our limit. Thank you for your time."
        }
    
    return {
        "decision":  "counter",
        "our_offer": our_offer,
        "round":     request.round,
        "message":   f"Best I can do is ${our_offer:.2f}. What do you say?"
    }



