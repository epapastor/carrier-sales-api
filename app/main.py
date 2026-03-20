from fastapi import FastAPI
from app.routers import loads, negotiation

# Create the main app
app = FastAPI(
    title="Inbound Carrier Sales API",
    description="Backend API for AI-powered inbound carrier load sales",
    version="1.0.0"
)

# Connect routers
app.include_router(loads.router)        # /search-loads, /find_closest_load
app.include_router(negotiation.router)  # /negotiate

@app.get("/")
def root():
    return {"status": "ok", "message": "Inbound Carrier Sales API is running"}

@app.get("/health")
def health():
    return {"status": "healthy"}
