from typing import Annotated, Union
from firebase_admin import storage
from fastapi import HTTPException, status, APIRouter, Security, UploadFile, File, Form
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
import os
from dotenv import load_dotenv
import motor.motor_asyncio
from bson import ObjectId
from typing import List
from datetime import datetime
from uuid import uuid4

from authentication import get_current_user

load_dotenv()

router = APIRouter()

MONGODB_URL = os.getenv("MONGODB_URL")

client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URL)
db = client.plant_monitoring

########################################################################
# MARK: MODELS
########################################################################

class Plant(BaseModel):
    id: str
    name: str
    type: str
    location: str
    description: str
    imageUrl: str


class CreatePlant(BaseModel):
    _id: ObjectId
    name: str
    type: str
    location: str
    description: str


class SensorOutput(BaseModel):
    id: str
    plant_id: str
    timestamp: datetime
    temperature: float
    soil_moisture: float
    light_level: float
    humidity: float


class CreateSensorOutput(BaseModel):
    plant_id: str
    temperature: float
    soil_moisture: float
    light_level: float
    humidity: float
    
class Device(BaseModel):
    plant_id: str | None
    device_name: str

class CreateDevice(BaseModel):
    plant_id: str | None = None
    device_name: str
    
class UpdateDevice(BaseModel):
    plant_id: str | None = None
    device_name: str

########################################################################
# MARK: PLANT
########################################################################

# GET endpoint to retrieve all plants
@router.get("/GetPlants/", response_description="List all plants", response_model=List[Plant], tags=["Plant Monitoring"])
async def get_plants(current_user: dict = Security(get_current_user)):
    roles = current_user.get("role", [])
    
    if "plant_monitoring" not in roles and "admin" not in roles:
        raise HTTPException(status_code=401, detail="You do not have access to send request to this endpoint.")
    try:
        # Use the aggregation framework to convert _id to string
        pipeline = [
            {
                "$project": {
                    "id": {
                        "$toString": "$_id"
                    },
                    "name": 1,
                    "type": 1,
                    "location": 1,
                    "description": 1,
                    "imageUrl": 1
                }
            }
        ]

        # Apply the aggregation pipeline to the collection
        plants_cursor: motor.motor_asyncio.AsyncIOMotorCollection = db["plants"].aggregate(
            pipeline)

        plants = await plants_cursor.to_list(length=None)
        return plants
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# GET endpoint to get a plant
@router.get("/GetPlant", response_description="Get a plant", response_model=Plant, tags=["Plant Monitoring"])
async def get_plant(request_body: dict, current_user: dict = Security(get_current_user)):
    roles = current_user.get("role", [])
    
    if "plant_monitoring" not in roles and "admin" not in roles:
        raise HTTPException(status_code=401, detail="You do not have access to send request to this endpoint.")
    
    try:
        # Use the aggregation framework to convert _id to string
        plant_id = request_body.get("id")

        # Ensure that the plant_id is provided in the request body
        if not plant_id:
            return Response(content="Plant ID not provided in the request body", status_code=status.HTTP_400_BAD_REQUEST)

        # Convert the provided plant_id to an ObjectId
        plant_object_id = ObjectId(plant_id)

        pipeline = [
            {
                "$match": {
                    "_id": plant_object_id
                }
            },
            {
                "$project": {
                    "id": {
                        "$toString": "$_id"
                    },
                    "name": 1,
                    "type": 1,
                    "location": 1,
                    "description": 1,
                    "imageUrl": 1
                }
            }
        ]

        try:
            plant = await db["plants"].aggregate(pipeline).next()
            return plant
        except:
            return Response(content="Plant not found", status_code=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# PUT endpoint to update a plant
@router.put("/UpdatePlant/", response_description="Update a plant by ID", response_model=Plant, tags=["Plant Monitoring"])
async def update_plant(updated_plant: Plant, current_user: dict = Security(get_current_user)):
    roles = current_user.get("role", [])
    
    if "plant_monitoring" not in roles and "admin" not in roles:
        raise HTTPException(status_code=401, detail="You do not have access to send request to this endpoint.")
    
    try:
        plant_id = updated_plant.id
        plant_object_id = ObjectId(plant_id)

        existing_plant = await db["plants"].find_one({"_id": plant_object_id})

        if existing_plant is None:
            return Response(content="Plant not found", status_code=status.HTTP_400_BAD_REQUEST)

        update_data = updated_plant.model_dump(exclude={"id"})

        # Update the plant with the provided data
        update_response = await db["plants"].update_one({"_id": plant_object_id}, {"$set": update_data})

        update_details = {
            "plant_id": plant_id,
            "matchedCount": update_response.matched_count,
            "modifiedCount": update_response.modified_count,
            "upsertedId": str(update_response.upserted_id),
            "acknowledged": update_response.acknowledged,
        }

        return JSONResponse(status_code=status.HTTP_201_CREATED, content=update_details)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# DELETE endpoint to delete a plant
@router.delete("/DeletePlant/", response_description="Delete a plant by ID", tags=["Plant Monitoring"])
async def delete_plant(request_body: dict, current_user: dict = Security(get_current_user)):
    roles = current_user.get("role", [])
    
    if "plant_monitoring" not in roles and "admin" not in roles:
        raise HTTPException(status_code=401, detail="You do not have access to send request to this endpoint.")
    
    try:
        # Use the aggregation framework to convert _id to string
        plant_id = request_body.get("id")

        # Ensure that the plant_id is provided in the request body
        if not plant_id:
            return Response(content="Plant ID not provided in the request body", status_code=status.HTTP_400_BAD_REQUEST)

        # Convert the provided plant_id to an ObjectId
        plant_object_id = ObjectId(plant_id)

        # Check if the plant with the provided ID exists
        existing_plant = await db["plants"].find_one({"_id": plant_object_id})
        if existing_plant is None:
            return Response(content="Plant not found", status_code=status.HTTP_400_BAD_REQUEST)

        # Delete the plant with the provided ID
        delete_result = await db["plants"].delete_one({"_id": plant_object_id})

        # Check if the deletion was successful
        if delete_result.deleted_count == 1:
            delete_details = {
                "message": "Plant deleted successfully",
                "plant_id": plant_id,
                "acknowledged": delete_result.acknowledged,
                "deletedCount": delete_result.deleted_count
            }
            return JSONResponse(status_code=status.HTTP_201_CREATED, content=delete_details)
        else:
            raise HTTPException(
                status_code=500, detail="Failed to delete plant")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# POST endpoint to add a new plant
@router.post("/CreatePlant/", response_description="Add a new plant", response_model=CreatePlant, tags=["Plant Monitoring"])
async def create_plant(plant: CreatePlant, current_user: dict = Security(get_current_user)):
    roles = current_user.get("role", [])
    
    if "plant_monitoring" not in roles and "admin" not in roles:
        raise HTTPException(status_code=401, detail="You do not have access to send request to this endpoint.")
    
    try:
        plant = jsonable_encoder(plant)
        new_plant = await db["plants"].insert_one(plant)
        return JSONResponse(status_code=status.HTTP_201_CREATED, content={"_id": str(new_plant.inserted_id)})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# POST endpoint to upload image
@router.post("/UploadPlantImage/", tags=["Plant Monitoring"])
async def upload_plant_image( plant_id: str = Form(...), file: UploadFile = File(...), current_user: dict = Security(get_current_user)):
    bucket = storage.bucket()
    roles = current_user.get("role", [])

    if "plant_monitoring" not in roles and "admin" not in roles:
        raise HTTPException(status_code=401, detail="You do not have access to send request to this endpoint.")
    try:
        plant_object_id = ObjectId(plant_id)
        
        existing_plant = await db["plants"].find_one({"_id": plant_object_id})
        
        if existing_plant is None:
            return Response(content="Plant not found", status_code=status.HTTP_403_FORBIDDEN)
        
        # Generate unique name and store on firebase
        blob = bucket.blob(f"plants/{uuid4()}.jpg")
        blob.upload_from_file(file.file)
        blob.make_public()
        image_url = blob.public_url

        # Store imageURL in MongoDB for the specified plant
        update_response = await db["plants"].update_one({"_id": plant_object_id}, {"$set" : {"imageUrl": image_url}})
                                                        
        update_details = {
            "plant_id": plant_id,
            "matchedCount": update_response.matched_count,
            "modifiedCount": update_response.modified_count,
            "upsertedId": str(update_response.upserted_id),
            "acknowledged": update_response.acknowledged,
            "imageUrl": image_url
        }

        return JSONResponse(status_code=status.HTTP_200_OK, content=update_details)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload an image: {str(e)}")

########################################################################
# MARK: SENSOR OUTPUT
########################################################################

# GET endpoint to retrieve all sensor outputs by a given plant ID

@router.get("/GetSensorOutputs/", response_description="List all Sensor Outputs By Plant ID", response_model=List[SensorOutput], tags=["Plant Monitoring"])
async def get_sensor_outputs(request_body: dict, current_user: dict = Security(get_current_user)):
    roles = current_user.get("role", [])
    
    if "plant_monitoring" not in roles and "admin" not in roles:
        raise HTTPException(status_code=401, detail="You do not have access to send request to this endpoint.")
    
    try:
        # Use the aggregation framework to convert _id to string
        plant_id = request_body.get("id")

        # Ensure that the plant_id is provided in the request body
        if not plant_id:
            return Response(content="Plant ID not provided in the request body", status_code=status.HTTP_400_BAD_REQUEST)

        # Convert the provided plant_id to an ObjectId
        plant_object_id = ObjectId(plant_id)

        # Use the aggregation framework to convert _id to string
        pipeline = [
            {
                "$match": {
                    "plant_id": plant_object_id
                }
            },
            {
                "$project": {
                    "id": {
                        "$toString": "$_id"
                    },
                    "plant_id": {
                        "$toString": "$plant_id"
                    },
                    "timestamp": 1,
                    "temperature": 1,
                    "soil_moisture": 1,
                    "light_level": 1,
                    "humidity": 1
                }
            }
        ]

        # Apply the aggregation pipeline to the collection
        senor_outputs_cursor: motor.motor_asyncio.AsyncIOMotorCollection = db["sensor_outputs"].aggregate(
            pipeline)
        sensor_outputs = await senor_outputs_cursor.to_list(length=None)

        if not sensor_outputs:
            return Response(content="No sensor values found for the specified plant", status_code=status.HTTP_404_NOT_FOUND)

        return sensor_outputs
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# POST endpoint to add a new plant
@router.post("/CreateSensorOutput/", response_description="Create a sensor output by a Plant ID", response_model=CreateSensorOutput, tags=["Plant Monitoring"])
async def create_sensor_output(sensor_output: CreateSensorOutput, current_user: dict = Security(get_current_user)):
    roles = current_user.get("role", [])
    
    if "plant_monitoring" not in roles and "admin" not in roles:
        raise HTTPException(status_code=401, detail="You do not have access to send request to this endpoint.")
    
    try:
        plant_id = ObjectId(sensor_output.plant_id)

        new_sensor_output_object = {
            "plant_id": plant_id,
            "timestamp": datetime.now().isoformat(),
            "temperature": sensor_output.temperature,
            "soil_moisture": sensor_output.soil_moisture,
            "light_level": sensor_output.light_level,
            "humidity": sensor_output.humidity
        }

        new_sensor_output = await db["sensor_outputs"].insert_one(new_sensor_output_object)
        return JSONResponse(status_code=status.HTTP_201_CREATED, content={"_id": str(new_sensor_output.inserted_id)})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# GET endpoint to list all devices
@router.get("/GetDevices/", response_description="List all devices", response_model=List[Device], tags=["Devices"])
async def get_devices(current_user: dict = Security(get_current_user)):
    roles = current_user.get("role", [])
    
    if "plant_monitoring" not in roles and "admin" not in roles:
        raise HTTPException(status_code=401, detail="You do not have access to this endpoint.")
    
    try:
        devices_cursor = db["devices"].find({})
        devices = await devices_cursor.to_list(length=None)
        
        # Convert ObjectId to string for proper JSON response
        for device in devices:
            device["_id"] = str(device["_id"])
        
        return devices
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# POST endpoint to create a new device
@router.post("/CreateDevice/", response_description="Create a new device", response_model=CreateDevice, tags=["Devices"])
async def create_device(device: CreateDevice, current_user: dict = Security(get_current_user)):
    roles = current_user.get("role", [])
    
    if "plant_monitoring" not in roles and "admin" not in roles:
        raise HTTPException(status_code=401, detail="You do not have access to this endpoint.")
    
    try:
        device_data = device.dict()
        new_device = await db["devices"].insert_one(device_data)
        return JSONResponse(status_code=status.HTTP_201_CREATED, content={"_id": str(new_device.inserted_id)})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# GET endpoint to get a specific device by ID
@router.get("/GetDevice", response_description="Get a device by ID", response_model=Device, tags=["Devices"])
async def get_device(request_body: dict, current_user: dict = Security(get_current_user)):
    roles = current_user.get("role", [])
    
    if "plant_monitoring" not in roles and "admin" not in roles:
        raise HTTPException(status_code=401, detail="You do not have access to this endpoint.")
    
    try:
        device_id = request_body.get("id")
        
        if not device_id:
            return Response(content="Device ID not provided in the request body", status_code=status.HTTP_400_BAD_REQUEST)

        device_object_id = ObjectId(device_id)
        
        device = await db["devices"].find_one({"_id": device_object_id})
        
        if not device:
            return Response(content="Device not found", status_code=status.HTTP_404_NOT_FOUND)
        
        device["_id"] = str(device["_id"])
        return device
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# PUT endpoint to update a device
@router.put("/UpdateDevice/", response_description="Update a device by ID", response_model=Device, tags=["Devices"])
async def update_device(request_body: dict, current_user: dict = Security(get_current_user)):
    roles = current_user.get("role", [])
    
    if "plant_monitoring" not in roles and "admin" not in roles:
        raise HTTPException(status_code=401, detail="You do not have access to this endpoint.")
    
    try:
        device_id = request_body.get("id")
        update_data = request_body.get("update_data", {})

        if not device_id:
            return Response(content="Device ID not provided", status_code=status.HTTP_400_BAD_REQUEST)

        device_object_id = ObjectId(device_id)

        result = await db["devices"].update_one({"_id": device_object_id}, {"$set": update_data})

        if result.matched_count == 0:
            return Response(content="Device not found", status_code=status.HTTP_404_NOT_FOUND)

        return Response(content="Device updated successfully", status_code=status.HTTP_200_OK)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# DELETE endpoint to delete a device by ID
@router.delete("/DeleteDevice/", response_description="Delete a device by ID", tags=["Devices"])
async def delete_device(request_body: dict, current_user: dict = Security(get_current_user)):
    roles = current_user.get("role", [])
    
    if "plant_monitoring" not in roles and "admin" not in roles:
        raise HTTPException(status_code=401, detail="You do not have access to this endpoint.")
    
    try:
        device_id = request_body.get("id")

        if not device_id:
            return Response(content="Device ID not provided", status_code=status.HTTP_400_BAD_REQUEST)

        device_object_id = ObjectId(device_id)

        result = await db["devices"].delete_one({"_id": device_object_id})

        if result.deleted_count == 0:
            return Response(content="Device not found", status_code=status.HTTP_404_NOT_FOUND)

        return Response(content="Device deleted successfully", status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))