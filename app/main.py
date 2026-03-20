# Import FastAPI - this is the framework that creates our API
from fastapi import FastAPI

# Import BaseModel from pydantic - this lets us define the shape of our data
from pydantic import BaseModel

# Create the app - this is the main object, everything hangs off this
app = FastAPI()

# This is our fake database - a simple dictionary
# Key = MC number, Value = carrier info
CARRIERS = {
    "123456": {"name": "Swift Transport LLC", "status": "ACTIVE", "authorized": True},
    "234567": {"name": "Eagle Freight Inc",   "status": "ACTIVE", "authorized": True},
    "999999": {"name": "Blacklisted Carrier", "status": "REVOKED", "authorized": False},
}

# This defines the SHAPE of data we expect to receive
# When HappyRobot calls this endpoint, it must send these two fields
class CarrierRequest(BaseModel):
    mc_number: str   # the carrier's ID number
    call_id: str     # unique ID of the call, so we can track it

# This is the endpoint
# @app.post means it responds to POST requests
# "/verify-carrier" is the URL path
@app.post("/verify-carrier")
def verify_carrier(request: CarrierRequest):  # request will contain the data HappyRobot sent
    
    # Extract the mc_number from the request
    mc = request.mc_number

    # Check if this MC number exists in our fake database
    if mc in CARRIERS:
        carrier = CARRIERS[mc]
        # Return the carrier info as a dictionary
        # FastAPI automatically converts this to JSON
        return {
            "mc_number": mc,
            "authorized": carrier["authorized"],
            "carrier_name": carrier["name"],
            "status": carrier["status"]
        }
    
    # If MC number not found, return unauthorized
    return {
        "mc_number": mc,
        "authorized": False,
        "carrier_name": None,
        "status": "NOT_FOUND"
    }