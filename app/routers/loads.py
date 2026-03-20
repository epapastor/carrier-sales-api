# search loads router
from pydantic import BaseModel
from fastapi import APIRouter
from app.database import get_connection
from datetime import datetime
import math
import httpx
import sqlite3

# Use APIRouter instead of FastAPI()
# this gets connected to main.py via app.include_router()
router = APIRouter()

# --- Coordinate helpers ---

def get_coords_carrier(address: str):
    """Convert an address string to (lat, lon) using Nominatim."""
    response = httpx.get(
        "https://nominatim.openstreetmap.org/search",
        params={"q": address, "format": "json"},
        headers={"User-Agent": "carrier-sales-api"}
    )
    data = response.json()
    if not data:
        return None
    return data[0]["lat"], data[0]["lon"]

def get_all_coordinates():
    """Fetch coordinates for all loads and store in COORDINATES table."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS COORDINATES (
            load_id    TEXT PRIMARY KEY,
            origin_lat FLOAT,
            origin_lon FLOAT
        )
    """)
    cursor.execute("SELECT load_id, origin FROM loads")
    rows = cursor.fetchall()
    for row in rows:
        coords = get_coords_carrier(row["origin"])
        if coords:
            cursor.execute(
                "INSERT OR IGNORE INTO COORDINATES VALUES (?, ?, ?)",
                (row["load_id"], coords[0], coords[1])
            )
    conn.commit()
    conn.close()

def haversine(lat1, lon1, lat2, lon2):
    """Calculate distance in miles between two lat/lon points."""
    R = 3958.8
    lat1, lon1, lat2, lon2 = map(math.radians, [float(lat1), float(lon1), float(lat2), float(lon2)])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))

def find_closest_load(address: str, eligible_load_ids: list = None):
    """Find the closest load to a given address, optionally filtered by eligible IDs."""
    carrier_coords = get_coords_carrier(address)
    if not carrier_coords:
        return None, 0

    conn = get_connection()
    cursor = conn.cursor()

    if eligible_load_ids:
        placeholders = ",".join("?" * len(eligible_load_ids))
        cursor.execute(
            f"SELECT * FROM COORDINATES WHERE load_id IN ({placeholders})",
            eligible_load_ids
        )
    else:
        cursor.execute("SELECT * FROM COORDINATES")

    rows = cursor.fetchall()
    conn.close()

    closest = None
    min_distance = float("inf")

    for row in rows:
        distance = haversine(
            carrier_coords[0], carrier_coords[1],
            row["origin_lat"], row["origin_lon"]
        )
        if distance < min_distance:
            min_distance = distance
            closest = dict(row)

    return closest, min_distance

# --- Requirements checkers ---

EQUIPMENT_FAMILIES = {
    "dry van": ["dry van", "van", "53ft", "48ft"],
    "reefer":  ["reefer", "refrigerated", "temp controlled"],
    "flatbed": ["flatbed", "flat bed", "flat", "step deck"],
}

def get_equipment_family(equipment: str) -> str:
    equipment = equipment.lower().strip()
    for family, synonyms in EQUIPMENT_FAMILIES.items():
        for synonym in synonyms:
            if synonym in equipment or equipment in synonym:
                return family
    return equipment

def check_equipment(carrier_equipment: str, load_equipment: str) -> bool:
    return get_equipment_family(carrier_equipment) == get_equipment_family(load_equipment)

def check_weight(carrier_max_weight: int, load_weight: int) -> bool:
    return carrier_max_weight >= load_weight

def check_availability(carrier_available_date: str, pickup_datetime: str) -> bool:
    carrier_dt = datetime.strptime(carrier_available_date, "%Y-%m-%d %H:%M")
    pickup_dt  = datetime.strptime(pickup_datetime, "%Y-%m-%d %H:%M")
    return carrier_dt <= pickup_dt

def meets_requirements(carrier: dict, load: dict) -> dict:
    equipment_ok = check_equipment(carrier["equipment_type"], load["equipment_type"])
    weight_ok    = check_weight(carrier["max_weight"], load["weight"])
    available_ok = check_availability(carrier["available_date"], load["pickup_datetime"])
    return {
        "load_id":         load["load_id"],
        "eligible":        equipment_ok and weight_ok and available_ok,
        "equipment_match": equipment_ok,
        "weight_ok":       weight_ok,
        "available":       available_ok
    }

# --- Pydantic models ---

class SearchLoadsRequest(BaseModel):
    current_location: str   # carrier's current address
    equipment_type:   str   # "Dry Van", "Reefer", "Flatbed"
    max_weight:       int   # max weight carrier can handle
    available_date:   str   # "2026-03-21 08:00"
    call_id:          str   # for tracking

# --- Endpoints ---

@router.post("/search-loads")
def search_loads(request: SearchLoadsRequest):
    """
    1. Filter loads that meet carrier requirements
    2. Among eligible loads, find the closest one to carrier
    """
    # step 1 - get all loads
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM loads")
    all_loads = cursor.fetchall()
    conn.close()

    # step 2 - filter by requirements
    carrier = {
        "equipment_type": request.equipment_type,
        "max_weight":     request.max_weight,
        "available_date": request.available_date
    }

    eligible_loads = []
    for load in all_loads:
        load = dict(load)
        result = meets_requirements(carrier, load)
        if result["eligible"]:
            eligible_loads.append(load)

    if not eligible_loads:
        return {"found": False, "reason": "No loads match your equipment and availability"}

    # step 3 - find closest among eligible
    eligible_ids = [load["load_id"] for load in eligible_loads]
    closest_coords, distance = find_closest_load(request.current_location, eligible_ids)

    if not closest_coords:
        return {"found": False, "reason": "Could not calculate distances"}

    # step 4 - get full load details from DB
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM loads WHERE load_id = ?", (closest_coords["load_id"],))
    full_load = dict(cursor.fetchone())
    conn.close()

    return {
        "found":          True,
        "load":           full_load,
        "distance_miles": round(distance, 2)
    }
