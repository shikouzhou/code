from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import logging
import uuid
from datetime import timedelta
from schema_generator import (
    parse_natural_language_to_schema,
    build_er_model,
    convert_to_relational_schema,
    generate_mysql_ddl
)
from models import (
    GenerateSchemaRequest, GenerateSchemaResponse, ErrorResponse,
    UserRegister, UserLogin, Token, UserHistoryResponse
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
        relational_schema = convert_to_relational_schema(er_model)
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