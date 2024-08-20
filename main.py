import os
import firebase_admin
from fastapi import FastAPI
from dotenv import load_dotenv
from firebase_admin import credentials, initialize_app
from authentication import router as authentication_router
from plant_monitoring import router as plant_monitoring_router

load_dotenv()

# Initialize Firebase
def initialize_firebase():
    if not firebase_admin._apps:  # Check if Firebase is already initialized
        cred = credentials.Certificate("Secrets/serviceAccountKey.json")
        initialize_app(cred, {
            "storageBucket": os.getenv("FIREBASE_BUCKET_NAME")
        })

initialize_firebase()

# Initialize FastAPI app
app = FastAPI(
    title="Plant Monitoring System",
    description="API for plant monitoring app",
    version="1.0.0",
    openapi_tags=[
        {"name": "Authentication", "description": "Endpoints related to user authentication"},
        {"name": "Plant Monitoring", "description": "Endpoints related to Plant Monitoring"}
    ]
)

# ROOT ENDPOINT
@app.get("/")
def read_root():
    return {"Hello": "World"}

# Include routers
app.include_router(authentication_router)
app.include_router(plant_monitoring_router)
