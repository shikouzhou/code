from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
import logging
import uuid
from schema_generator import (
    parse_natural_language_to_schema,
    build_er_model,
    convert_to_relational_schema,
    generate_mysql_ddl
)
from models import GenerateSchemaRequest, GenerateSchemaResponse, ErrorResponse

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
async def generate_schema(request: GenerateSchemaRequest):
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)