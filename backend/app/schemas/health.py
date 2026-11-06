from datetime import datetime

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
    version: str


class ReadinessResponse(BaseModel):
    status: str
    database: str
    timestamp: datetime
