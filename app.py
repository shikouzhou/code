from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import logging
import uuid
from datetime import timedelta
from typing import Dict, Any
from schema_generator import (
    parse_natural_language_to_schema,
    build_er_model,
    convert_to_relational_schema,
    generate_mysql_ddl,
    modify_entity,
    add_entity,
    delete_entity,
    modify_relationship,
    add_relationship,
    delete_relationship
)
from models import (
    GenerateSchemaRequest, GenerateSchemaResponse, ErrorResponse,
    UserRegister, UserLogin, Token, UserHistoryResponse,
    ModifyEntityRequest, AddEntityRequest, DeleteEntityRequest,
    ModifyRelationshipRequest, AddRelationshipRequest, DeleteRelationshipRequest,
    ModifySchemaResponse, AttributeModel, EntityModel, RelationshipModel
)
from database import get_db, init_db, User, InteractionRecord
from auth import (
    authenticate_user, create_access_token, get_current_active_user,
    get_password_hash, ACCESS_TOKEN_EXPIRE_MINUTES
)

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="自然语言到数据库模式生成器",
    description="基于阿里云通义千问的数据库模式自动生成服务",
    version="1.0.0"
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该设置具体的域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post(
    "/generate-schema",
    response_model=GenerateSchemaResponse,
    summary="生成数据库模式",
    description="根据自然语言描述生成数据库schema、ER模型和MySQL DDL"
)
async def generate_schema(
    request: GenerateSchemaRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    主生成接口：将自然语言转换为数据库模式
    """
    try:
        logger.info(f"收到生成请求: {request.description[:50]}...")

        # 1. 解析自然语言到schema
        schema = parse_natural_language_to_schema(request.description)
        logger.info("Schema生成成功")

        # 2. 构建ER模型
        er_model = build_er_model(schema)
        er_model_dict = {
            "entities": [
                {"name": e.name, "attributes": e.attributes, "primary_key": e.primary_key}
                for e in er_model.entities
            ],
            "relationships": [
                {"name": r.name, "entities": r.entities, "cardinality": r.cardinality}
                for r in er_model.relationships
            ]
        }
        logger.info("ER模型构建成功")

        # 3. 转换为关系模式
        relational_schema = convert_to_relational_schema(schema)
        logger.info("关系模式转换成功")

        # 4. 生成MySQL DDL
        ddl = generate_mysql_ddl(relational_schema)
        logger.info("DDL生成成功")

        # 5. 生成session_id
        session_id = str(uuid.uuid4())

        response = GenerateSchemaResponse(
            schema=schema,
            er_model=er_model_dict,
            ddl=ddl,
            session_id=session_id
        )

        # 保存交互记录到数据库
        interaction_record = InteractionRecord(
            user_id=current_user.id,
            description=request.description,
            schema_result=schema,
            er_model_result=er_model_dict,
            ddl_result=ddl,
            session_id=session_id
        )
        db.add(interaction_record)
        db.commit()
        db.refresh(interaction_record)

        logger.info(f"请求处理完成，session_id: {session_id}")
        return response

    except ValueError as e:
        logger.error(f"值错误: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"内部错误: {str(e)}")
        raise HTTPException(status_code=500, detail="内部服务器错误")

@app.get("/")
async def root():
    """
    健康检查接口
    """
    return {"message": "自然语言到数据库模式生成器API", "status": "running"}

@app.get("/health")
async def health():
    """
    健康检查
    """
    return {"status": "healthy"}

@app.post("/auth/register", response_model=Token)
async def register_user(user: UserRegister, db: Session = Depends(get_db)):
    """
    用户注册
    """
    # 检查用户名是否已存在
    db_user = db.query(User).filter(User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="用户名已存在")

    # 检查邮箱是否已存在
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="邮箱已被注册")

    # 创建新用户
    hashed_password = get_password_hash(user.password)
    db_user = User(username=user.username, email=user.email, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    # 创建访问令牌
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/user/history", response_model=UserHistoryResponse)
async def get_user_history(
    skip: int = 0,
    limit: int = 10,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    获取用户的历史记录
    """
    # 查询总数
    total_count = db.query(InteractionRecord).filter(
        InteractionRecord.user_id == current_user.id
    ).count()

    # 查询记录
    records = db.query(InteractionRecord).filter(
        InteractionRecord.user_id == current_user.id
    ).order_by(InteractionRecord.created_at.desc()).offset(skip).limit(limit).all()

    # 转换为响应格式
    record_responses = []
    for record in records:
        record_responses.append({
            "id": record.id,
            "description": record.description,
            "schema_result": record.schema_result,
            "er_model_result": record.er_model_result,
            "ddl_result": record.ddl_result,
            "session_id": record.session_id,
            "created_at": record.created_at
        })

    return UserHistoryResponse(total_count=total_count, records=record_responses)

def get_schema_by_session(session_id: str, user_id: int, db: Session) -> Dict[str, Any]:
    """根据session_id获取schema"""
    record = db.query(InteractionRecord).filter(
        InteractionRecord.session_id == session_id,
        InteractionRecord.user_id == user_id
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="Session not found")
    return record.schema_result

def update_schema_in_db(session_id: str, user_id: int, schema: Dict[str, Any],
                       er_model: Dict[str, Any], ddl: str, db: Session):
    """更新数据库中的schema"""
    record = db.query(InteractionRecord).filter(
        InteractionRecord.session_id == session_id,
        InteractionRecord.user_id == user_id
    ).first()
    if record:
        record.schema_result = schema
        record.er_model_result = er_model
        record.ddl_result = ddl
        db.commit()

@app.put("/modify-entity", response_model=ModifySchemaResponse)
async def modify_entity_endpoint(
    request: ModifyEntityRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """修改实体"""
    try:
        # 获取当前schema
        schema = get_schema_by_session(request.session_id, current_user.id, db)

        # 执行修改
        modified_schema = modify_entity(schema, request.entity_name,
                                      request.new_attributes, request.new_table_name)

        # 重新生成ER模型、关系模式和DDL
        er_model = build_er_model(modified_schema)
        er_model_dict = {
            "entities": [
                {"name": e.name, "attributes": e.attributes, "primary_key": e.primary_key}
                for e in er_model.entities
            ],
            "relationships": [
                {"name": r.name, "entities": r.entities, "cardinality": r.cardinality}
                for r in er_model.relationships
            ]
        }
        relational_schema = convert_to_relational_schema(modified_schema)
        ddl = generate_mysql_ddl(relational_schema)

        # 更新数据库
        update_schema_in_db(request.session_id, current_user.id,
                          modified_schema, er_model_dict, ddl, db)

        return ModifySchemaResponse(
            schema=modified_schema,
            er_model=er_model_dict,
            ddl=ddl,
            session_id=request.session_id
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="内部服务器错误")

@app.post("/add-entity", response_model=ModifySchemaResponse)
async def add_entity_endpoint(
    request: AddEntityRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """添加实体"""
    try:
        # 获取当前schema
        schema = get_schema_by_session(request.session_id, current_user.id, db)

        # 执行添加
        entity_dict = {
            "table_name": request.entity.table_name,
            "attributes": [
                {
                    "name": attr.name,
                    "data_type": attr.data_type,
                    "is_primary_key": attr.is_primary_key,
                    "comment": attr.comment
                }
                for attr in request.entity.attributes
            ]
        }
        modified_schema = add_entity(schema, entity_dict)

        # 重新生成ER模型、关系模式和DDL
        er_model = build_er_model(modified_schema)
        er_model_dict = {
            "entities": [
                {"name": e.name, "attributes": e.attributes, "primary_key": e.primary_key}
                for e in er_model.entities
            ],
            "relationships": [
                {"name": r.name, "entities": r.entities, "cardinality": r.cardinality}
                for r in er_model.relationships
            ]
        }
        relational_schema = convert_to_relational_schema(modified_schema)
        ddl = generate_mysql_ddl(relational_schema)

        # 更新数据库
        update_schema_in_db(request.session_id, current_user.id,
                          modified_schema, er_model_dict, ddl, db)

        return ModifySchemaResponse(
            schema=modified_schema,
            er_model=er_model_dict,
            ddl=ddl,
            session_id=request.session_id
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="内部服务器错误")

@app.delete("/delete-entity", response_model=ModifySchemaResponse)
async def delete_entity_endpoint(
    request: DeleteEntityRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """删除实体"""
    try:
        # 获取当前schema
        schema = get_schema_by_session(request.session_id, current_user.id, db)

        # 执行删除
        modified_schema = delete_entity(schema, request.entity_name)

        # 重新生成ER模型、关系模式和DDL
        er_model = build_er_model(modified_schema)
        er_model_dict = {
            "entities": [
                {"name": e.name, "attributes": e.attributes, "primary_key": e.primary_key}
                for e in er_model.entities
            ],
            "relationships": [
                {"name": r.name, "entities": r.entities, "cardinality": r.cardinality}
                for r in er_model.relationships
            ]
        }
        relational_schema = convert_to_relational_schema(modified_schema)
        ddl = generate_mysql_ddl(relational_schema)

        # 更新数据库
        update_schema_in_db(request.session_id, current_user.id,
                          modified_schema, er_model_dict, ddl, db)

        return ModifySchemaResponse(
            schema=modified_schema,
            er_model=er_model_dict,
            ddl=ddl,
            session_id=request.session_id
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="内部服务器错误")

@app.put("/modify-relationship", response_model=ModifySchemaResponse)
async def modify_relationship_endpoint(
    request: ModifyRelationshipRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """修改关系"""
    try:
        # 获取当前schema
        schema = get_schema_by_session(request.session_id, current_user.id, db)

        # 执行修改
        old_rel = {
            "from_table": request.old_relationship.from_table,
            "from_column": request.old_relationship.from_column,
            "to_table": request.old_relationship.to_table,
            "to_column": request.old_relationship.to_column,
            "on_delete": request.old_relationship.on_delete
        }
        new_rel = {
            "from_table": request.new_relationship.from_table,
            "from_column": request.new_relationship.from_column,
            "to_table": request.new_relationship.to_table,
            "to_column": request.new_relationship.to_column,
            "on_delete": request.new_relationship.on_delete
        }
        modified_schema = modify_relationship(schema, old_rel, new_rel)

        # 重新生成ER模型、关系模式和DDL
        er_model = build_er_model(modified_schema)
        er_model_dict = {
            "entities": [
                {"name": e.name, "attributes": e.attributes, "primary_key": e.primary_key}
                for e in er_model.entities
            ],
            "relationships": [
                {"name": r.name, "entities": r.entities, "cardinality": r.cardinality}
                for r in er_model.relationships
            ]
        }
        relational_schema = convert_to_relational_schema(modified_schema)
        ddl = generate_mysql_ddl(relational_schema)

        # 更新数据库
        update_schema_in_db(request.session_id, current_user.id,
                          modified_schema, er_model_dict, ddl, db)

        return ModifySchemaResponse(
            schema=modified_schema,
            er_model=er_model_dict,
            ddl=ddl,
            session_id=request.session_id
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="内部服务器错误")

@app.post("/add-relationship", response_model=ModifySchemaResponse)
async def add_relationship_endpoint(
    request: AddRelationshipRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """添加关系"""
    try:
        # 获取当前schema
        schema = get_schema_by_session(request.session_id, current_user.id, db)

        # 执行添加
        rel = {
            "from_table": request.relationship.from_table,
            "from_column": request.relationship.from_column,
            "to_table": request.relationship.to_table,
            "to_column": request.relationship.to_column,
            "on_delete": request.relationship.on_delete
        }
        modified_schema = add_relationship(schema, rel)

        # 重新生成ER模型、关系模式和DDL
        er_model = build_er_model(modified_schema)
        er_model_dict = {
            "entities": [
                {"name": e.name, "attributes": e.attributes, "primary_key": e.primary_key}
                for e in er_model.entities
            ],
            "relationships": [
                {"name": r.name, "entities": r.entities, "cardinality": r.cardinality}
                for r in er_model.relationships
            ]
        }
        relational_schema = convert_to_relational_schema(modified_schema)
        ddl = generate_mysql_ddl(relational_schema)

        # 更新数据库
        update_schema_in_db(request.session_id, current_user.id,
                          modified_schema, er_model_dict, ddl, db)

        return ModifySchemaResponse(
            schema=modified_schema,
            er_model=er_model_dict,
            ddl=ddl,
            session_id=request.session_id
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="内部服务器错误")

@app.delete("/delete-relationship", response_model=ModifySchemaResponse)
async def delete_relationship_endpoint(
    request: DeleteRelationshipRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """删除关系"""
    try:
        # 获取当前schema
        schema = get_schema_by_session(request.session_id, current_user.id, db)

        # 执行删除
        rel = {
            "from_table": request.relationship.from_table,
            "from_column": request.relationship.from_column,
            "to_table": request.relationship.to_table,
            "to_column": request.relationship.to_column,
            "on_delete": request.relationship.on_delete
        }
        modified_schema = delete_relationship(schema, rel)

        # 重新生成ER模型、关系模式和DDL
        er_model = build_er_model(modified_schema)
        er_model_dict = {
            "entities": [
                {"name": e.name, "attributes": e.attributes, "primary_key": e.primary_key}
                for e in er_model.entities
            ],
            "relationships": [
                {"name": r.name, "entities": r.entities, "cardinality": r.cardinality}
                for r in er_model.relationships
            ]
        }
        relational_schema = convert_to_relational_schema(modified_schema)
        ddl = generate_mysql_ddl(relational_schema)

        # 更新数据库
        update_schema_in_db(request.session_id, current_user.id,
                          modified_schema, er_model_dict, ddl, db)

        return ModifySchemaResponse(
            schema=modified_schema,
            er_model=er_model_dict,
            ddl=ddl,
            session_id=request.session_id
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="内部服务器错误")

@app.post("/auth/login", response_model=Token)
async def login_user(user: UserLogin, db: Session = Depends(get_db)):
    """
    用户登录
    """
    db_user = authenticate_user(db, user.username, user.password)
    if not db_user:
        raise HTTPException(
            status_code=401,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# 启动时初始化数据库
init_db()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)