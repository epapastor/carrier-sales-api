#POST /log-call + GET /calls


from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, Literal
from app.database import get_connection

router = APIRouter()

class LogCallRequest(BaseModel):
    call_id:              str
    mc_number:            Optional[str] = None
    carrier_name:         Optional[str] = None
    load_id:              Optional[str] = None
    origin:               Optional[str] = None
    destination:          Optional[str] = None
    loadboard_rate:       Optional[float] = None
    final_agreed_rate:    Optional[float] = None
    negotiation_rounds:   Optional[int] = 0
    outcome:              Literal["booked", "no_deal", "carrier_ineligible", "no_load_found", "abandoned"]
    sentiment:            Literal["positive", "neutral", "negative"]
    call_duration_seconds: Optional[int] = None
    notes:                Optional[str] = None

@router.post("/log-call")
def log_call(request: LogCallRequest):
    conn = get_connection()
    cursor = conn.cursor()

    # create table if not exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS calls (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            call_id               TEXT UNIQUE,
            mc_number             TEXT,
            carrier_name          TEXT,
            load_id               TEXT,
            origin                TEXT,
            destination           TEXT,
            loadboard_rate        REAL,
            final_agreed_rate     REAL,
            negotiation_rounds    INTEGER,
            outcome               TEXT,
            sentiment             TEXT,
            call_duration_seconds INTEGER,
            notes                 TEXT,
            created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        INSERT OR IGNORE INTO calls (
            call_id, mc_number, carrier_name,
            load_id, origin, destination,
            loadboard_rate, final_agreed_rate,
            negotiation_rounds, outcome, sentiment,
            call_duration_seconds, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        request.call_id,
        request.mc_number,
        request.carrier_name,
        request.load_id,
        request.origin,
        request.destination,
        request.loadboard_rate,
        request.final_agreed_rate,
        request.negotiation_rounds,
        request.outcome,
        request.sentiment,
        request.call_duration_seconds,
        request.notes
    ))

    conn.commit()
    conn.close()

    return {"success": True, "call_id": request.call_id}