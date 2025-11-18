from pydantic import BaseModel
from typing import Dict, Any, Optional

class GenerateSchemaRequest(BaseModel):
    description: str

class ERModelResponse(BaseModel):
    entities: list
    relationships: list

class GenerateSchemaResponse(BaseModel):
    schema: Dict[str, Any]
    er_model: Optional[ERModelResponse] = None
    ddl: str
    session_id: str

class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None