from pydantic import BaseModel
from typing import Dict, Any, Optional, List
from datetime import datetime

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

# 用户认证相关模型
class UserRegister(BaseModel):
    username: str
    email: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

# 交互记录相关模型
class InteractionRecordBase(BaseModel):
    description: str
    schema_result: Dict[str, Any]
    er_model_result: Optional[Dict[str, Any]] = None
    ddl_result: str
    session_id: str

class InteractionRecord(InteractionRecordBase):
    id: int
    user_id: int
    created_at: datetime

    class Config:
        from_attributes = True

class InteractionRecordResponse(BaseModel):
    id: int
    description: str
    schema_result: Dict[str, Any]
    er_model_result: Optional[Dict[str, Any]] = None
    ddl_result: str
    session_id: str
    created_at: datetime

class UserHistoryResponse(BaseModel):
    total_count: int
    records: List[InteractionRecordResponse]