import json
import re
import os
from typing import Dict, List, Any, Optional
import uuid
import dashscope

# 数据结构定义
class Entity:
    def __init__(self, name: str, attributes: List[str], primary_key: str):
        self.name = name
        self.attributes = attributes
        self.primary_key = primary_key

class Relationship:
    def __init__(self, name: str, entities: List[str], cardinality: str):
        self.name = name
        self.entities = entities
        self.cardinality = cardinality

class ERModel:
    def __init__(self, entities: List[Entity], relationships: List[Relationship]):
        self.entities = entities
        self.relationships = relationships

class Column:
    def __init__(self, name: str, data_type: str = "VARCHAR(255)", constraints: List[str] = None):
        self.name = name
        self.data_type = data_type
        self.constraints = constraints or []

class Table:
    def __init__(self, name: str, columns: List[Column], foreign_keys: List[str] = None):
        self.name = name
        self.columns = columns
        self.foreign_keys = foreign_keys or []

# 调用阿里云通义千问API
def call_llm_for_schema(prompt: str) -> Dict[str, Any]:
    """
    调用阿里云通义千问大模型将自然语言转换为结构化schema。
    """
    # 设置API key
    dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")
    if not dashscope.api_key:
        raise ValueError("请设置DASHSCOPE_API_KEY环境变量")

    # 构造prompt，要求输出JSON格式的schema
    full_prompt = f"""
你是一个专业的数据库建模专家。请根据用户提供的自然语言需求描述，自动生成一个结构完整、符合关系数据库范式的概念模型，并以严格指定的 JSON 格式输出。

你的核心任务是：
- 不仅提取用户显式提到的内容，
- 更要**主动联想并补全所有在逻辑上必要或高度可能存在的实体、属性、关联表和关系**（例如：用户说"老师布置作业"，应联想到 teachers、assignments、students、submission_records 等）。
- 所有**非用户直接提及的内容**（包括表、字段、外键、中间表等）**必须明确标注为 [inferred]**。

具体规则如下：

1. **主动联想实体**：
   - 基于常见业务场景（如电商、教务、审批、社交等）推断隐含角色、资源、记录类实体。
   - 若存在多对多关系（如用户-角色、学生-课程），必须创建中间关联表，并视为独立实体。

2. **属性设计**：
   - 自动补充主键（通常为 id）、时间戳（created_at, updated_at）、状态字段（status, is_active）等常见字段，若未被提及。
   - 所有推断字段必须在 `comment` 中包含 `[inferred]`。

3. **关系建模**：
   - 显式建模一对多、多对多关系。
   - 外键字段若未被用户提及，也需推断并标注 `[inferred]`。

4. **命名规范**：
   - 表名：复数、小写、snake_case（如 `users`, `order_items`）。
   - 字段名：snake_case（如 `user_id`, `submitted_at`）。

5. **数据类型**：
   - 合理推测 SQL 类型（如 `INT`, `VARCHAR(255)`, `TEXT`, `DATETIME`, `DECIMAL(10,2)`, `BOOLEAN`）。

6. **外键约束**：
   - 为每个外键指定 `on_delete` 行为（优先 `CASCADE` 或 `SET NULL`，根据语义判断）。

7. **标注要求（关键！）**：
   - **任何未在用户输入中明确出现的表、字段或关系，都必须在 `comment` 字段中标注 `[inferred]`**。
   - 即使是"常识性"内容（如用户表要有 id），只要用户没提，就算推断。

8. **禁止行为**：
   - 不得引入与用户描述场景无关的实体（如"博客系统"中不要加入"支付"）。
   - 不得输出除 JSON 以外的任何文本（包括解释、Markdown、注释）。

输出必须是纯 JSON，且严格遵循以下 Schema：

{{
  "entities": [
    {{
      "table_name": "string",
      "attributes": [
        {{
          "name": "string",
          "data_type": "string",
          "is_primary_key": boolean,
          "comment": "string (若为推断，必须包含 '[inferred]'；可附加简短说明)"
        }}
      ]
    }}
  ],
  "relationships": [
    {{
      "from_table": "string",
      "from_column": "string",
      "to_table": "string",
      "to_column": "string",
      "on_delete": "CASCADE | SET NULL | RESTRICT"
    }}
  ]
}}

现在，请根据以下用户描述生成上述 JSON：
{prompt}
"""

    response = dashscope.Generation.call(
        model='qwen-turbo',
        prompt=full_prompt
    )

    if response.status_code == 200:
        result = response.output.text
        # 尝试解析JSON
        try:
            schema = json.loads(result)
            return schema
        except json.JSONDecodeError:
            # 如果直接解析失败，尝试提取JSON部分
            json_match = re.search(r'\{.*\}', result, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass
            raise ValueError(f"无法解析LLM响应为JSON: {result}")
    else:
        raise ValueError(f"API调用失败: {response.status_code}, {response.message}")

# 核心函数：解析自然语言到schema
def parse_natural_language_to_schema(user_input: str) -> Dict[str, Any]:
    """
    接收自然语言输入，调用LLM生成schema。
    """
    prompt = f"将以下自然语言描述转换为数据库schema JSON格式：{user_input}"
    return call_llm_for_schema(prompt)

# 构建ER模型
def build_er_model(schema: Dict[str, Any]) -> ERModel:
    """
    从schema构建ER模型。
    """
    entities = []
    for ent in schema["entities"]:
        # 从新格式中提取属性名列表和主键
        attributes = [attr["name"] for attr in ent["attributes"]]
        primary_key = next((attr["name"] for attr in ent["attributes"] if attr["is_primary_key"]), None)
        entities.append(Entity(ent["table_name"], attributes, primary_key))

    relationships = []
    for rel in schema["relationships"]:
        # 从新格式的外键关系中推断基数
        # 这里简化处理，假设所有关系都是一对多或多对多
        # 可以通过检查外键列是否唯一来判断，但目前简化
        relationships.append(Relationship(f"{rel['from_table']}_{rel['to_table']}", [rel["from_table"], rel["to_table"]], "1:N"))

    return ERModel(entities, relationships)

# 转换为关系模式
def convert_to_relational_schema(schema: Dict[str, Any]) -> List[Table]:
    """
    直接从新格式schema转换为关系模式。
    """
    tables = []

    # 为每个实体创建表
    for entity in schema["entities"]:
        columns = []
        foreign_keys = []

        # 处理所有属性
        for attr in entity["attributes"]:
            constraints = []
            if attr["is_primary_key"]:
                constraints.extend(["AUTO_INCREMENT", "PRIMARY KEY"])
            elif attr["name"].endswith("_id"):  # 可能是外键
                constraints.append("NOT NULL")

            column = Column(attr["name"], attr["data_type"], constraints)
            columns.append(column)

        # 处理外键约束
        for rel in schema["relationships"]:
            if rel["from_table"] == entity["table_name"]:
                fk_constraint = f"FOREIGN KEY ({rel['from_column']}) REFERENCES {rel['to_table']}({rel['to_column']})"
                if rel.get("on_delete"):
                    fk_constraint += f" ON DELETE {rel['on_delete']}"
                foreign_keys.append(fk_constraint)

        tables.append(Table(entity["table_name"], columns, foreign_keys))

    return tables

# 生成MySQL DDL
def generate_mysql_ddl(tables: List[Table]) -> str:
    """
    生成MySQL CREATE TABLE语句。
    """
    ddl = ""
    for table in tables:
        ddl += f"CREATE TABLE {table.name} (\n"
        cols = []
        for col in table.columns:
            cons = " ".join(col.constraints)
            cols.append(f"  {col.name} {col.data_type} {cons}".strip())
        ddl += ",\n".join(cols)
        if table.foreign_keys:
            ddl += ",\n" + ",\n".join(f"  {fk}" for fk in table.foreign_keys)
        ddl += "\n);\n\n"
    return ddl

# 交互式修正功能
def modify_entity(schema: Dict[str, Any], entity_name: str, new_attributes: List[Dict[str, Any]] = None, new_table_name: str = None) -> Dict[str, Any]:
    """
    修改实体属性或表名。
    """
    for ent in schema["entities"]:
        if ent["table_name"] == entity_name:
            if new_attributes:
                ent["attributes"] = new_attributes
            if new_table_name:
                ent["table_name"] = new_table_name
            break
    return schema

def add_entity(schema: Dict[str, Any], entity: Dict[str, Any]) -> Dict[str, Any]:
    """
    添加实体。
    """
    schema["entities"].append(entity)
    return schema

def delete_entity(schema: Dict[str, Any], entity_name: str) -> Dict[str, Any]:
    """
    删除实体。
    """
    schema["entities"] = [ent for ent in schema["entities"] if ent["table_name"] != entity_name]
    # 同时删除相关关系
    schema["relationships"] = [
        rel for rel in schema["relationships"]
        if rel["from_table"] != entity_name and rel["to_table"] != entity_name
    ]
    return schema

def modify_relationship(schema: Dict[str, Any], old_rel: Dict[str, Any], new_rel: Dict[str, Any]) -> Dict[str, Any]:
    """
    修改关系。
    """
    for i, rel in enumerate(schema["relationships"]):
        if (rel["from_table"] == old_rel["from_table"] and
            rel["from_column"] == old_rel["from_column"] and
            rel["to_table"] == old_rel["to_table"] and
            rel["to_column"] == old_rel["to_column"]):
            schema["relationships"][i] = new_rel
            break
    return schema

def add_relationship(schema: Dict[str, Any], rel: Dict[str, Any]) -> Dict[str, Any]:
    """
    添加关系。
    """
    schema["relationships"].append(rel)
    return schema

def delete_relationship(schema: Dict[str, Any], rel: Dict[str, Any]) -> Dict[str, Any]:
    """
    删除关系。
    """
    schema["relationships"] = [
        r for r in schema["relationships"]
        if not (r["from_table"] == rel["from_table"] and
                r["from_column"] == rel["from_column"] and
                r["to_table"] == rel["to_table"] and
                r["to_column"] == rel["to_column"])
    ]
    return schema