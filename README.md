# 自然语言到数据库模式生成器

基于阿里云通义千问的数据库模式自动生成服务，支持用户认证和交互记录。

## 功能特性

- 自然语言到数据库模式的转换
- ER模型生成
- MySQL DDL自动生成
- 用户注册和登录
- JWT认证
- 用户交互历史记录

## 安装依赖

```bash
pip install -r requirements.txt
```

## 数据库配置

在环境变量中设置数据库连接：

```bash
export DATABASE_URL="mysql+mysqlconnector://root:845464115w@localhost/db_generator"
export SECRET_KEY="your-secret-key-here"
```

或者直接在代码中使用默认配置（已设置root用户密码为845464115w）

## 初始化数据库

```bash
python init_db.py
```

## 启动服务

```bash
python app.py
```

服务将在 http://localhost:8000 启动

## API接口

### 认证接口

- `POST /auth/register` - 用户注册
- `POST /auth/login` - 用户登录

### 业务接口

- `POST /generate-schema` - 生成数据库模式（需要认证）
- `GET /user/history` - 获取用户历史记录（需要认证）

### 示例请求

#### 用户注册
```bash
curl -X POST "http://localhost:8000/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "password123"
  }'
```

#### 用户登录
```bash
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "password": "password123"
  }'
```

#### 生成数据库模式
```bash
curl -X POST "http://localhost:8000/generate-schema" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "description": "一个学生管理系统，包含学生、课程和成绩信息"
  }'
```

#### 获取历史记录
```bash
curl -X GET "http://localhost:8000/user/history" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

## 数据库表结构

- `users` - 用户表
- `interaction_records` - 交互记录表

## 环境变量

- `DATABASE_URL` - 数据库连接URL
- `SECRET_KEY` - JWT密钥