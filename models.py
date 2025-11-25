from pydantic import BaseModel, EmailStr, Field
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
    username: str = Field(..., min_length=3, max_length=50, description="用户名长度3-50字符")
    email: EmailStr = Field(..., description="有效的邮箱地址")
    password: str = Field(..., min_length=6, description="密码至少6位")

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