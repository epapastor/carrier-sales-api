from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.routers import loads, negotiation, carrier
from app.database import init_db, insert_data

# this runs automatically when the app starts
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()      # creates the tables
    insert_data()  # inserts the loads
    yield          # app runs normally after this

app = FastAPI(
    title="Inbound Carrier Sales API",
    description="Backend API for AI-powered inbound carrier load sales",
    version="1.0.0",
    lifespan=lifespan  # ← connect the startup function
)

app.include_router(carrier.router)
app.include_router(loads.router)
app.include_router(negotiation.router)

@app.get("/")
def root():
    return {"status": "ok", "message": "API is running"}

@app.get("/health")
def health():
    return {"status": "healthy"}
