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
    def __init__(self, name: str, columns: List[Column], foreign_keys: List[str] = None, primary_keys: List[str] = None):
        self.name = name
        self.columns = columns
        self.foreign_keys = foreign_keys or []
        self.primary_keys = primary_keys or []

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
你是一个专业的数据库建模专家。请根据用户提供的自然语言需求描述，自动生成一个结构完整、符合第三范式（3NF）的关系模型，并以严格指定的 JSON 格式输出。

你的核心任务是：
- 忠实提取用户显式提到的所有实体、属性和关系；
- **主动推断并补全所有在业务逻辑上必要或高度合理的隐含元素**（包括字段、外键、关联表等）；
- 所有**未在用户原始描述中逐字出现的内容**（包括表、字段、外键、中间表、时间戳、状态字段等），其 `comment` 字段**必须包含 `[inferred]` 标记**。

请严格遵守以下规则：

#### 一、实体与字段设计
1. **主键**：每个表必须包含 `id INT` 作为主键，`is_primary_key: true`，`comment: "[inferred] 主键"`。
2. **通用字段（若未提及）**：
   - `created_at DATETIME` → `comment: "[inferred] 记录创建时间"`
   - `updated_at DATETIME` → `comment: "[inferred] 记录最后更新时间"`
   - `is_active BOOLEAN`（适用于用户、部门、项目、角色、任务等实体）→ `comment: "[inferred] 是否激活"`
3. **归属与管理关系**：
   - 若“A 属于 B”、“A 被分配给 B” → 在 A 表中添加 `b_id` 外键（如 `users.department_id`）。
   - 若“B 有负责人/创建者/管理者（是 A）” → 在 B 表中添加 `a_id` 外键（如 `departments.manager_id`）。
4. **多对多关系**：必须通过**中间表**实现，且：
   - 中间表**不得包含任何自增 `id` 字段**；
   - 使用 `(entity1_id, entity2_id)` 作为**联合主键**（两个字段 `is_primary_key: true`）；
   - 中间表名必须由两个实体名称以下划线连接而成（例如：user_role、product_tag），不得包含花括号，仅使用小写字母和下划线。
   - 两个 ID 字段均标注为 `"[inferred]"`。

5.：中间表命名约定
- **仅当表名为 中间表格式时**，才视为中间表，即当表名符合 中间表 格式时，必须视为中间表，并应用上述多对多关系规则；
- 如果不符合该格式，则不应自动识别为中间表，并遵循普通表的设计原则（包含 `id` 主键）。

#### 二、外键方向（绝对强制规则 — 违反将导致输出无效）

外键表示 **“依赖”关系：子表记录的存在依赖于父表记录**。因此必须严格遵守：

1. **外键字段只能出现在“依赖方”（子表）中**，引用“被依赖方”（父表）的主键；
2. **主键（如 users.id）永远是被引用的目标，绝不能作为外键去引用其他表**；
3. **禁止任何形式的“反向外键”**（即主键主动引用非主键或子表），例如：
   -  错误：`parent.id REFERENCES child(foreign_key_column)`  
     （父实体主键不能引用子实体的外键字段）
   -  错误：`master.id REFERENCES junction_table(detail_id)`  
     （主表主键不能引用中间关联表的 ID 字段）
   -  错误：`users.id REFERENCES any_other_table(some_id)`  
     （人员主键绝不能作为外键指向任何业务表）

4. **正确模式模板（通用建模范式）**：
   - 当实体 B 与实体 A 存在 “归属”、“指派”、“创建”、“负责” 等单向关联时：
     - 在 **B 表中添加外键字段 `a_id`**
     - 外键关系为：`B.a_id → A.id`
   - 示例（不依赖具体业务）：
     - “某实体有负责人（人员）” → `entity.responsible_user_id → users.id`
     - “子项属于父项” → `child.parent_id → parent.id`
     - “记录由某用户创建” → `record.created_by → users.id`

5. **特别强调（通用原则）**：
   - 所有人员角色（无论称为客户、员工、审核人、操作员、联系人等）统一建模为 `users` 表；
   - 因此，**任何指向“人员”的字段（如 `assigned_to`, `owner_id`, `approver_id`）必须是外键，位于非 users 表中，引用 `users.id`**；
   - **`users` 表本身不得包含以 `id` 为主键并引用其他业务表的外键约束**（即禁止 `users.id → X.y_id`）。

6. **惩罚机制**：
   - 若生成任何 `from_table: "users", from_column: "id"` 的 relationship，视为严重错误；
   - 若生成 `to_column` 不是 `"id"` 的 relationship（除非明确说明唯一索引），视为错误。

#### 三、ON DELETE 策略选择标准
- `CASCADE`：子记录完全依赖父记录，无独立意义（如评论、任务分配 → 删除任务则删除它们）
- `SET NULL`：子记录可保留，但需解除关联（如部门 manager_id → 删除用户后设为 NULL）
  - 此时外键字段**必须允许 NULL**（不能有 `NOT NULL`）
- `RESTRICT`：禁止删除正在被引用的记录（如项目经理仍有项目时，禁止删除该用户）

#### 四、命名与类型规范
严格遵守
- 表名：复数、小写、snake_case（如 `users`, `task_assignments`）
- 字段名：snake_case（如 `project_manager_id`）
- 数据类型：
  - 名称/邮箱/状态码：`VARCHAR(255)`
  - 描述/内容：`TEXT`
  - 时间：`DATETIME`
  - 开关/状态：`BOOLEAN`
  
#### 五、输出格式与完整性要求
- 输出**必须是纯 JSON**，仅包含 `entities` 和 `relationships` 两个顶级字段。
- 每个 `relationship` 的 `from_column` 必须在 `from_table` 的 `attributes` 中存在，且数据类型匹配。
- 中间表的两个外键都必须在 `relationships` 中声明。
- 不得遗漏显而易见的归属关系（如“任务属于项目” → `tasks` 必须有 `project_id`）。

#### 六、禁止行为（违反将导致输出无效）
-  字段名使用 MySQL 保留关键字。(如usage、order等)
-  在中间表中添加 `id` 字段（无论是否自增）
-  外键方向颠倒（被引用表引用引用表）
-  `NOT NULL` 字段使用 `ON DELETE SET NULL`
-  未标注 `[inferred]` 的推断内容
-  输出任何非 JSON 文本（包括解释、注释、SQL）
 **任何 relationship 的 `to_column` 必须是目标表的主键（即字段名必须为 "id"）**；
- 禁止引用目标表的外键字段、状态字段、名称字段等非主键列；
- 正确：`to_table: "users", to_column: "id"`
- 错误：`to_table: "warehouses", to_column: "manager_id"`（manager_id 不是主键）
#### 七、字段命名安全规范（必须严格执行）
- 为避免 MySQL 语法错误，以下业务术语必须映射为指定的安全字段名：

    | 业务语义        | 禁止字段名       | 必须使用字段名         |
    |----------------|----------------- |------------------------|
    | 用法 / 使用方式 | usage            | instructions           |
    | 排序 / 顺序     | order            | sort_order             |
    | 分组            | group            | group_name 或 category |
    | 状态            | status           | state                  |
    | 描述            | desc             | description            |
    | 关键字          | key              | keyword                |

- 任何情况下都不得直接使用禁止字段名，即使用户需求中出现了对应词汇。

现在，请基于用户的需求描述，生成符合上述所有规则的 JSON 模型。
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
    schema = call_llm_for_schema(prompt)
    # 修复非法外键关系
    schema = fix_relationships(schema)
    return schema

# 修复非法外键关系
def fix_relationships(schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    自动修复非法的外键关系。

    系统约束：
    - 所有表的主键字段名都是 "id"。
    - 所有人员角色统一存储在 users 表中。
    - 外键只能从子表指向父表的主键（即 to_column 必须是 "id"）。
    - 如果某关系是 from_table="users", from_column="id"，且 to_table 不是 "users"，
      这极可能是方向颠倒，应反转为：to_table 中某个 _id 字段 → users.id。

    自动修正：
    a. 强制所有 to_column 为 "id"（因为只有主键可被引用）。
    b. 检测 users.id → X.y_id 类型的反向外键，尝试反转方向：
       - 在 X 表的 attributes 中查找最可能的外键字段（如包含 "user"、"manager"、"owner" 或以 "_id" 结尾）。
       - 若找到，生成新关系：{"from_table": X, "from_column": candidate_col, "to_table": "users", "to_column": "id", ...}
       - 若未找到，跳过并打印警告。
    """
    import copy
    fixed_schema = copy.deepcopy(schema)  # 深拷贝以避免修改原件

    # 获取所有表名
    table_names = {ent["name"] for ent in fixed_schema["entities"]}

    # 修正 relationships
    new_relationships = []

    for rel in fixed_schema["relationships"]:
        # 检查 to_table 是否有单个主键 "id"
        to_entity = next((e for e in fixed_schema["entities"] if e["name"] == rel["to_table"]), None)
        if to_entity:
            pk_fields = [attr["name"] for attr in to_entity["attributes"] if attr.get("is_primary_key", False)]
            if len(pk_fields) == 1 and pk_fields[0] == "id":
                # 强制 to_column 为 "id"
                rel["to_column"] = "id"
            # 如果不是单个 "id" 主键，保持原样

        # 检查是否是反向外键：from_table="users", from_column="id", to_table != "users"
        if rel["from_table"] == "users" and rel["from_column"] == "id" and rel["to_table"] != "users":
            # 尝试反转
            to_table = rel["to_table"]
            # 在 to_table 中查找候选外键字段
            to_entity = next((e for e in fixed_schema["entities"] if e["name"] == to_table), None)
            if to_entity:
                candidate_cols = []
                for attr in to_entity["attributes"]:
                    name = attr["name"]
                    if name != "id" and (name.endswith("_id") or "user" in name.lower() or "manager" in name.lower() or "owner" in name.lower()):
                        candidate_cols.append(name)
                if candidate_cols:
                    # 选择第一个候选
                    candidate_col = candidate_cols[0]
                    # 创建新关系
                    new_rel = {
                        "from_table": to_table,
                        "from_column": candidate_col,
                        "to_table": "users",
                        "to_column": "id",
                        "on_delete": rel.get("on_delete", "CASCADE")  # 保留 on_delete
                    }
                    new_relationships.append(new_rel)
                    print(f"反转关系: {rel} -> {new_rel}")
                else:
                    print(f"警告: 无法找到 {to_table} 中的候选外键字段，跳过关系: {rel}")
            else:
                print(f"警告: 表 {to_table} 不存在，跳过关系: {rel}")
        else:
            # 正常关系
            new_relationships.append(rel)

    fixed_schema["relationships"] = new_relationships
    return fixed_schema

# 构建ER模型
def build_er_model(schema: Dict[str, Any]) -> ERModel:
    """
    从schema构建ER模型。
    """
    if "entities" not in schema or "relationships" not in schema:
        raise ValueError("Schema 必须包含 'entities' 和 'relationships' 键")

    entities = []
    for ent in schema["entities"]:
        if not isinstance(ent, dict) or "name" not in ent or "attributes" not in ent:
            raise ValueError(f"实体格式错误: {ent}")
        # 从新格式中提取属性名列表和主键
        attributes = [attr.get("name") for attr in ent["attributes"] if isinstance(attr, dict) and "name" in attr]
        primary_key = next((attr.get("name") for attr in ent["attributes"] if isinstance(attr, dict) and attr.get("is_primary_key")), None)
        entities.append(Entity(ent["name"], attributes, primary_key))

    relationships = []
    for rel in schema["relationships"]:
        if not isinstance(rel, dict) or "from_table" not in rel or "to_table" not in rel:
            raise ValueError(f"关系格式错误: {rel}")
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
    if "entities" not in schema or "relationships" not in schema:
        raise ValueError("Schema 必须包含 'entities' 和 'relationships' 键")

    # 补全缺失的中间表实体
    from collections import defaultdict
    existing_tables = {ent["name"] for ent in schema["entities"]}
    all_tables = set()
    table_fks = defaultdict(list)
    for rel in schema["relationships"]:
        all_tables.add(rel["from_table"])
        all_tables.add(rel["to_table"])
        table_fks[rel["from_table"]].append(rel["from_column"])
    missing_tables = all_tables - existing_tables
    for table in missing_tables:
        fks = table_fks[table]
        if len(fks) >= 2 and all(col.endswith("_id") for col in fks):
            # 补全中间表
            attributes = []
            for col in fks:
                attributes.append({
                    "name": col,
                    "type": "INT",
                    "is_primary_key": True,
                    "comment": "[inferred] 外键字段"
                })
            schema["entities"].append({
                "name": table,
                "attributes": attributes
            })
            print(f"补全缺失中间表: {table}")

    tables = []

    # 为每个实体创建表
    for entity in schema["entities"]:
        if "name" not in entity or "attributes" not in entity:
            raise ValueError(f"实体缺少 'name' 或 'attributes': {entity}")

        columns = []
        foreign_keys = []
        primary_keys = []

        # 收集主键字段
        pk_fields = [attr["name"] for attr in entity["attributes"] if attr.get("is_primary_key", False)]

        # 判断是否为中间表：多个主键字段且均为 _id 结尾
        is_junction = len(pk_fields) > 1 and all(field.endswith("_id") for field in pk_fields)

        # 处理所有属性
        for attr in entity["attributes"]:
            if "name" not in attr or "type" not in attr:  # 注意：LLM 用 "type" 而不是 "data_type"
                raise ValueError(f"属性缺少 'name' 或 'type': {attr}")

            constraints = []
            if attr.get("is_primary_key", False):
                constraints.append("NOT NULL")
                # 对于单列主键，添加 AUTO_INCREMENT 和 PRIMARY KEY
                if len(pk_fields) == 1 and pk_fields[0] == attr["name"]:
                    constraints.extend(["AUTO_INCREMENT", "PRIMARY KEY"])
            else:
                # 非主键字段：检查是否为外键，根据 on_delete 设置 NULL 约束
                is_fk = any(rel.get("from_table") == entity["name"] and rel.get("from_column") == attr["name"] for rel in schema["relationships"])
                if is_fk:
                    rel = next((r for r in schema["relationships"] if r.get("from_table") == entity["name"] and r.get("from_column") == attr["name"]), None)
                    if rel and rel.get("on_delete") == "SET NULL":
                        pass  # 允许 NULL
                    else:
                        constraints.append("NOT NULL")

            column = Column(attr["name"], attr["type"], constraints)  # 用 "type"
            columns.append(column)

        # 处理外键约束
        for rel in schema["relationships"]:
            if rel.get("from_table") == entity["name"]:
                if "from_column" not in rel or "to_table" not in rel or "to_column" not in rel:
                    raise ValueError(f"关系缺少必要字段: {rel}")
                # 校验 to_table 存在
                to_table_entity = next((e for e in schema["entities"] if e["name"] == rel["to_table"]), None)
                if not to_table_entity:
                    raise ValueError(f"外键引用不存在的表: {rel['to_table']}")
                # 校验 to_column 是主键或唯一索引
                referenced_pk_fields = [attr["name"] for attr in to_table_entity["attributes"] if attr.get("is_primary_key", False)]
                if len(referenced_pk_fields) == 1 and rel["to_column"] not in referenced_pk_fields:
                    raise ValueError(f"外键引用非主键列: {rel['to_table']}.{rel['to_column']}")
                # 对于联合主键表，暂时不校验
                fk_constraint = f"FOREIGN KEY ({rel['from_column']}) REFERENCES {rel['to_table']}({rel['to_column']})"
                if rel.get("on_delete"):
                    fk_constraint += f" ON DELETE {rel['on_delete']}"
                foreign_keys.append(fk_constraint)

        # 设置主键：多列主键使用表级PRIMARY KEY，单列使用列级
        if len(pk_fields) > 1:
            primary_keys = pk_fields
        # 单列主键已在列约束中设置

        # 过滤 primary_keys，只保留实际存在的列
        primary_keys = [pk for pk in primary_keys if any(col.name == pk for col in columns)]

        tables.append(Table(entity["name"], columns, foreign_keys, primary_keys))

    # 后处理：补全缺失字段
    for table in tables:
        # 补全缺失的外键字段
        for rel in schema["relationships"]:
            if rel.get("from_table") == table.name:
                if not any(col.name == rel.get("from_column") for col in table.columns):
                    # 安全校验：仅当表为中间表（表名包含下划线）且字段以 _id 结尾时，才补全缺失的外键字段
                    # 防止向普通表（如 roles）错误添加外键字段（如 user_id），导致表结构污染
                    if '_' in table.name and rel["from_column"].endswith("_id"):
                        # 根据 on_delete 设置约束
                        constraints = []
                        if rel.get("on_delete") != "SET NULL":
                            constraints.append("NOT NULL")
                        fk_col = Column(rel["from_column"], "INT", constraints)
                        table.columns.append(fk_col)

    return tables

# 拓扑排序表，确保被引用表先创建
def topological_sort_tables(tables: List[Table]) -> List[Table]:
    """
    使用拓扑排序对表进行排序，确保被引用表先创建。
    对于循环依赖的表，按原顺序添加。
    """
    import re
    from collections import deque, defaultdict

    # 构建图：table -> 被引用表列表
    graph = defaultdict(list)
    in_degree = {table.name: 0 for table in tables}
    table_dict = {table.name: table for table in tables}

    for table in tables:
        for fk in table.foreign_keys:
            # 解析外键：FOREIGN KEY (col) REFERENCES to_table(col)
            match = re.search(r'REFERENCES (\w+)\(', fk)
            if match:
                to_table = match.group(1)
                if to_table in table_dict:  # 只考虑存在的表
                    graph[table.name].append(to_table)
                    in_degree[to_table] += 1

    # Kahn's algorithm
    queue = deque([name for name, deg in in_degree.items() if deg == 0])
    sorted_tables = []

    while queue:
        name = queue.popleft()
        sorted_tables.append(table_dict[name])
        for neighbor in graph[name]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    # 处理循环依赖：剩下的表按原顺序添加
    remaining = [table for table in tables if table.name not in {t.name for t in sorted_tables}]
    sorted_tables.extend(remaining)

    return sorted_tables

# 生成MySQL DDL
def generate_mysql_ddl(tables: List[Table]) -> tuple[str, str]:
    """
    生成MySQL DDL：返回 (create_statements, alter_statements)
    第一阶段：CREATE TABLE 语句（无外键）
    第二阶段：ALTER TABLE 添加外键
    """
    # 排序表以确保被引用表先创建
    tables = topological_sort_tables(tables)

    create_statements = ""
    alter_statements = ""

    # 断言：确保主键字段存在于列中
    for table in tables:
        for pk in table.primary_keys:
            if not any(col.name == pk for col in table.columns):
                raise ValueError(f"主键字段 '{pk}' 在表 '{table.name}' 的列中不存在")

    # 第一阶段：生成所有 CREATE TABLE 语句（无外键）
    for table in tables:
        create_statements += f"CREATE TABLE {table.name} (\n"
        cols = []
        for col in table.columns:
            cons = " ".join(col.constraints)
            cols.append(f"  {col.name} {col.data_type} {cons}".strip())
        create_statements += ",\n".join(cols)
        # 添加联合主键（如果有）
        if table.primary_keys:
            pk_str = ", ".join(table.primary_keys)
            create_statements += f",\n  PRIMARY KEY ({pk_str})"
        create_statements += "\n);\n\n"

    # 第二阶段：生成所有 ALTER TABLE 添加外键
    for table in tables:
        for fk in table.foreign_keys:
            alter_statements += f"ALTER TABLE {table.name} ADD {fk};\n"

    return create_statements, alter_statements

# 交互式修正功能
def modify_entity(schema: Dict[str, Any], entity_name: str, new_attributes: List[Dict[str, Any]] = None, new_table_name: str = None) -> Dict[str, Any]:
    """
    修改实体属性或表名。
    """
    for ent in schema["entities"]:
        if ent.get("name") == entity_name:
            if new_attributes:
                ent["attributes"] = new_attributes
            if new_table_name:
                ent["name"] = new_table_name
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
    schema["entities"] = [ent for ent in schema["entities"] if ent.get("name") != entity_name]
    # 同时删除相关关系
    schema["relationships"] = [
        rel for rel in schema["relationships"]
        if rel.get("from_table") != entity_name and rel.get("to_table") != entity_name
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