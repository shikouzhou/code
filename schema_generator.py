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
将以下自然语言描述转换为数据库schema的JSON格式。

输出格式示例：
{{
  "entities": [
    {{"name": "Student", "attributes": ["student_id", "name"], "primary_key": "student_id"}},
    {{"name": "Course", "attributes": ["course_id", "name"], "primary_key": "course_id"}}
  ],
  "relationships": [
    {{"name": "Enrollment", "entities": ["Student", "Course"], "cardinality": "M:N"}}
  ]
}}

自然语言描述：{prompt}

请确保输出是有效的JSON，不要包含其他文本。
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
        entities.append(Entity(ent["name"], ent["attributes"], ent["primary_key"]))

    relationships = []
    for rel in schema["relationships"]:
        relationships.append(Relationship(rel["name"], rel["entities"], rel["cardinality"]))

    return ERModel(entities, relationships)

# 转换为关系模式
def convert_to_relational_schema(er_model: ERModel) -> List[Table]:
    """
    将ER模型转换为关系模式，处理多对多关系。
    """
    tables = []

    # 为每个实体创建表
    for entity in er_model.entities:
        columns = []
        # 主键
        pk_col = Column(entity.primary_key, "INT", ["AUTO_INCREMENT", "PRIMARY KEY"])
        columns.append(pk_col)
        # 其他属性
        for attr in entity.attributes:
            if attr != entity.primary_key:
                columns.append(Column(attr, "VARCHAR(255)"))
        tables.append(Table(entity.name, columns))

    # 处理关系
    for rel in er_model.relationships:
        if rel.cardinality == "M:N":
            # 创建连接表
            table_name = rel.name
            ent1, ent2 = rel.entities
            fk1 = f"{ent1.lower()}_id"
            fk2 = f"{ent2.lower()}_id"
            columns = [
                Column("id", "INT", ["AUTO_INCREMENT", "PRIMARY KEY"]),
                Column(fk1, "INT", ["NOT NULL"]),
                Column(fk2, "INT", ["NOT NULL"])
            ]
            foreign_keys = [
                f"FOREIGN KEY ({fk1}) REFERENCES {ent1}({ent1.lower()}_id)",
                f"FOREIGN KEY ({fk2}) REFERENCES {ent2}({ent2.lower()}_id)"
            ]
            tables.append(Table(table_name, columns, foreign_keys))
        elif rel.cardinality == "1:N":
            # 在N端添加外键
            one_ent, many_ent = rel.entities
            fk_name = f"{one_ent.lower()}_id"
            for table in tables:
                if table.name == many_ent:
                    table.columns.append(Column(fk_name, "INT", ["NOT NULL"]))
                    table.foreign_keys.append(f"FOREIGN KEY ({fk_name}) REFERENCES {one_ent}({one_ent.lower()}_id)")
                    break

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
def modify_entity(schema: Dict[str, Any], entity_name: str, new_attributes: List[str] = None, new_pk: str = None) -> Dict[str, Any]:
    """
    修改实体属性或主键。
    """
    for ent in schema["entities"]:
        if ent["name"] == entity_name:
            if new_attributes:
                ent["attributes"] = new_attributes
            if new_pk:
                ent["primary_key"] = new_pk
            break
    return schema

def add_relationship(schema: Dict[str, Any], rel: Dict[str, Any]) -> Dict[str, Any]:
    """
    添加关系。
    """
    schema["relationships"].append(rel)
    return schema