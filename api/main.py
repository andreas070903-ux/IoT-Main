"""REST API for receiving and generating wind turbine sensor measurements."""

import logging
import os
from functools import lru_cache
from typing import Annotated, Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from turbine_control.state import (
    get_turbine_control,
    list_turbine_controls,
    set_turbine_running,
    turbine_is_stopped,
)


load_dotenv()
logger = logging.getLogger(__name__)
app = FastAPI(title="IoT Sensor and Turbine Simulation API", version="1.0.0")


class SensorMeasurement(BaseModel):
    """A wind turbine sensor measurement."""

    model_config = ConfigDict(extra="forbid")

    Timestamp: str = Field(min_length=1)
    Turbine_ID: str = Field(min_length=1, max_length=100)
    Wind_Speed_m_s: float = Field(ge=0, le=100)
    Wind_Direction_deg: float = Field(ge=0, le=360)
    Ambient_Temp_C: float = Field(ge=-80, le=70)
    Rotor_Speed_RPM: float = Field(ge=0)
    Power_Output_kW: float = Field(ge=0)
    Expected_Power_kW: float = Field(ge=0)
    Gearbox_Temp_C: float
    Generator_Temp_C: float
    Vibration_mm_s: float = Field(ge=0)
    Alarm_Flag: bool
    Status: Literal["OK", "WARNING", "ALARM", "CRITICAL", "OFFLINE"]
    Maintenance_Required: Literal["YES", "NO"]


class TurbineControlCommand(BaseModel):
    """A simulated start/stop command for a turbine."""

    command: Literal["start", "stop"]


@lru_cache(maxsize=4)
def mongo_client(uri: str) -> MongoClient:
    """Reuse a MongoDB client for each configured URI."""
    return MongoClient(uri, serverSelectionTimeoutMS=10_000)


def get_collection() -> Collection:
    uri = os.getenv("MONGODB_URI")
    database = os.getenv("MONGODB_DATABASE")
    collection_name = os.getenv("MONGODB_COLLECTION")
    if not uri or not database or not collection_name:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Set MONGODB_URI, MONGODB_DATABASE, and MONGODB_COLLECTION in .env.",
        )
    return mongo_client(uri)[database][collection_name]


def save_measurement(measurement: SensorMeasurement) -> dict:
    try:
        result = get_collection().insert_one(measurement.model_dump())
    except PyMongoError as exc:
        logger.exception("Could not save sensor measurement to MongoDB")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB operation failed; check the connection and database settings.",
        ) from exc
    return {"id": str(result.inserted_id), "measurement": measurement}


@app.get("/health")
def health() -> dict[str, str]:
    try:
        get_collection().database.client.admin.command("ping")
    except PyMongoError as exc:
        logger.exception("MongoDB health check failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB is unavailable; check the connection and database settings.",
        ) from exc
    return {"status": "ok", "mongodb": "connected"}


@app.post("/measurements", status_code=status.HTTP_201_CREATED)
def create_measurement(measurement: SensorMeasurement) -> dict:
    """Receive a reading from an IoT device and store it."""
    if turbine_is_stopped(measurement.Turbine_ID):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{measurement.Turbine_ID} is stopped in the simulation.",
        )
    return save_measurement(measurement)


@app.get("/measurements")
def list_measurements(
    limit: Annotated[int, Query(ge=1, le=10000)] = 100,
) -> list[dict]:
    """Return the newest stored measurements."""
    try:
        documents = (
            get_collection()
            .find({})
            .sort("Timestamp", -1)
            .limit(limit)
        )
        return [
            {"id": str(document.pop("_id")), **document}
            for document in documents
        ]
    except PyMongoError as exc:
        logger.exception("Could not read sensor measurements from MongoDB")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB operation failed; check the connection and database settings.",
        ) from exc


@app.get("/turbines/control")
def get_all_turbine_controls() -> list[dict[str, str]]:
    """Return control states for the simulated turbines."""
    return list_turbine_controls()


@app.get("/turbines/{turbine_id}/control")
def get_one_turbine_control(turbine_id: str) -> dict[str, str]:
    """Return the simulated control state for one turbine."""
    try:
        return get_turbine_control(turbine_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown simulated turbine: {turbine_id}",
        ) from exc


@app.post("/turbines/{turbine_id}/control")
def control_turbine(
    turbine_id: str, command: TurbineControlCommand
) -> dict[str, str]:
    """Start or stop a turbine in the simulation."""
    try:
        return set_turbine_running(turbine_id, command.command == "start")
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown simulated turbine: {turbine_id}",
        ) from exc
