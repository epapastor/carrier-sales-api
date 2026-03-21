#search loads
from fastapi import APIRouter
from pydantic import BaseModel, validator
from app.database import get_connection
import math
import httpx
import os
import sqlite3
from datetime import datetime
from typing import Union


router = APIRouter()
class SearchLoadsRequest(BaseModel):
    current_location: str
    equipment_type:   str
    max_weight:       Union[int, str]  # accepts both
    available_date:   str
    call_id:          str

    @validator("max_weight", pre=True)
    def parse_max_weight(cls, v):
        try:
            return int(float(str(v).strip()))
        except:
            return 44000  # default if parsing fails

def get_all_coordenates():
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS COORDINATES (
            load_id          TEXT PRIMARY KEY,
            origin_lat       FLOAT,
            origin_lon       FLOAT
        )
    """)
    cursor.execute("SELECT load_id, origin FROM loads")
    rows = cursor.fetchall()  # returns a list of all rows
    for row in rows:
        origin = row["origin"]
        load_id = row["load_id"]
    
    # call nominatim for origin
        response_origin = httpx.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": origin, "format": "json"},
            headers={"User-Agent": "carrier-sales-api"}
        )
        data = response_origin.json()

        if not data:
            print(f"Could not find coordinates for {origin}")
            continue
        
        lat_origin = data[0]["lat"]
        lon_origin = data[0]["lon"]
        

        cursor.execute(
            "INSERT OR IGNORE INTO COORDINATES VALUES (?, ?, ?)",
            (load_id, lat_origin, lon_origin)
        )

    conn.commit()
    conn.close()

def haversine(lat1, lon1, lat2, lon2):
    # radius of Earth in miles
    R = 3958.8
    
    # convert degrees to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [float(lat1), float(lon1), float(lat2), float(lon2)])
    
    # haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    return R * c  # returns distance in miles
# define a Pydantic model

class AddressRequest(BaseModel):
    address: str
def get_coords_carrier(address_obj: AddressRequest):
    address = address_obj.address
    response_origin = httpx.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": address, "format": "json"},
            headers={"User-Agent": "carrier-sales-api"}
        )
    data = response_origin.json()
    if not data:
        return None
        
    lat_origin = data[0]["lat"]
    lon_origin = data[0]["lon"]
    return lat_origin, lon_origin


# 1. Simplifica esta función para que reciba el texto directamente
def get_coords_carrier(address: str): 
    # Ya no necesitas 'address_obj.address', usa 'address' directamente
    response_origin = httpx.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": address, "format": "json"},
            headers={"User-Agent": "carrier-sales-api"}
        )
    data = response_origin.json()
    if not data:
        return None
        
    return data[0]["lat"], data[0]["lon"]


def find_closest_load(address: str, eligible_load_ids: list = None):
    carrier_coords = get_coords_carrier(address)
    
    if not carrier_coords:
        return "No se encontraron coordenadas", 0
        
    conn = get_connection()
    # IMPORTANTE: Esto permite usar row["columna"]
    conn.row_factory = sqlite3.Row 
    cursor = conn.cursor()
    if eligible_load_ids:
        # only search among eligible loads
        placeholders = ",".join("?" * len(eligible_load_ids))
        cursor.execute(f"SELECT * FROM COORDINATES WHERE load_id IN ({placeholders})", eligible_load_ids)
    else:
        cursor.execute("SELECT * FROM COORDINATES")
    rows = cursor.fetchall()
    
    closest = None
    min_distance = float("inf")
    
    for row in rows:
        # Asegúrate de usar los nombres exactos del CREATE TABLE:
        # origin_lat y origin_lon
        distance = haversine(
            carrier_coords[0], carrier_coords[1],
            row["origin_lat"], row["origin_lon"] 
        )
        if distance < min_distance:
            min_distance = distance
            closest = dict(row)

    conn.close()
    return closest, min_distance

class requirements(BaseModel):
    load_id : str
    equipment_type: str
    weight: int


# group equipment types by family
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
    return equipment  # return as-is if no family found

def check_equipment(carrier_equipment: str, load_equipment: str) -> bool:
    # compare families instead of exact strings
    carrier_family = get_equipment_family(carrier_equipment)
    load_family    = get_equipment_family(load_equipment)
    return carrier_family == load_family

def check_weight(carrier_max_weight: int, load_weight: int) -> bool:
    return carrier_max_weight >= load_weight



def check_availability(carrier_available_date: str, pickup_datetime: str) -> bool:
    # parse both strings into datetime objects
    carrier_dt = datetime.strptime(carrier_available_date, "%Y-%m-%d %H:%M")
    pickup_dt  = datetime.strptime(pickup_datetime, "%Y-%m-%d %H:%M")
    return carrier_dt <= pickup_dt

def meets_requirements(carrier, load) -> dict:
    equipment_ok  = check_equipment(carrier["equipment_type"], load["equipment_type"])
    weight_ok     = check_weight(carrier["max_weight"], load["weight"])
    available_ok  = check_availability(carrier["available_date"], load["pickup_datetime"])
    
    return {
        "load_id": load["load_id"],
        "eligible": equipment_ok and weight_ok and available_ok,
        "equipment_match": equipment_ok,
        "weight_ok": weight_ok,
        "available": available_ok
    }

class SearchLoadsRequest(BaseModel):
    # carrier location
    current_location: str      # "49 Washington St, Newark, NJ"
    # carrier capabilities
    equipment_type: str        # "Dry Van"
    max_weight: int            # 44000
    available_date: str        # "2026-03-21 08:00"
    
    # for tracking
    call_id: str


@router.post("/search-loads")
def search_loads(request: SearchLoadsRequest):

    # step 1 - filter by requirements
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM loads")
    all_loads = cursor.fetchall()
    conn.close()

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
        return {"found": False, "reason": "No loads match your requirements"}

    # step 2 - find closest among eligible
    eligible_ids = [load["load_id"] for load in eligible_loads]
    closest, distance = find_closest_load(request.current_location, eligible_ids)

    if not closest:
        return {"found": False, "reason": "Could not calculate distances"}

    return {
        "found":          True,
        "load":           closest,
        "distance_miles": round(distance, 2)
    }



if __name__ == "__main__":
    
    # fake carrier looking for a load
    fake_request = SearchLoadsRequest(
        current_location = "350 Fifth Ave, New York, NY 10118",  # Empire State Building
        equipment_type   = "Dry Van",
        max_weight       = 50000,
        available_date   = "2026-03-23 06:00",
        call_id          = "test-001"
    )
    
    result = search_loads(fake_request)
    print(result)
