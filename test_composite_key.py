from schema_generator import parse_natural_language_to_schema, convert_to_relational_schema, generate_mysql_ddl
import json

# 使用test_api.py中的description
description = """我们要开发一个智能仓储与物流调度系统。系统中有仓库管理员、配送员和客户，所有内部人员（管理员和配送员）都归属于一个仓库（Warehouse），每个仓库有名称、所在城市、容量上限和负责人（必须是仓库管理员）。客户可以创建发货订单（Orders），每个订单包含收货地址、期望送达时间、货物类型（普通、易碎、冷藏）和总件数。系统根据订单自动分配最近的可用仓库，并生成一条出库任务（OutboundTask），记录预计打包时间、实际完成时间、及状态（待处理、已打包、已发货、已取消）。每个仓库维护其库存明细（InventoryItems），记录每种商品（由 SKU 唯一标识）的当前数量、安全库存阈值和最后盘点时间。当库存低于阈值时，系统自动生成补货申请（ReplenishmentRequest），并通知采购人员。配送员通过系统接收配送任务（DeliveryTasks），每个任务关联一个或多个订单，包含路线规划、预计出发/到达时间、车辆编号。配送完成后，客户可对本次配送进行签收确认和服务评分（1-5星），并可上传异常照片（如货物破损）。系统支持定义运输规则（ShippingRules），例如"冷藏货物必须使用冷链车辆"、"易碎品需单独包装"，规则应用于订单审核阶段。所有关键操作（如创建订单、修改库存、分配配送员、取消任务）均记录到操作审计日志（AuditLogs），包含操作人、操作对象 ID、变更前/后值（JSON）、时间戳和 IP 地址。此外，系统采用基于角色的访问控制（RBAC）：用户角色包括客户、仓库管理员、配送员、采购专员和系统运维；一个内部用户可拥有多个角色（如某人既是仓库管理员又是采购专员），但客户不能拥有内部角色。所有主数据（仓库、用户、订单、库存、配送任务、补货申请）均支持软删除（is_active 字段），并自动维护 created_at 与 updated_at 时间戳。"""

print("步骤1: 调用parse_natural_language_to_schema生成schema")
try:
    schema = parse_natural_language_to_schema(description)
    print("成功生成schema")
    print("Schema 摘要:")
    print(f"实体数量: {len(schema.get('entities', []))}")
    for ent in schema.get('entities', []):
        pk_count = sum(1 for attr in ent.get('attributes', []) if attr.get('is_primary_key'))
        if pk_count > 1:
            print(f"  {ent['name']}: 联合主键 ({pk_count} 个字段)")
except Exception as e:
    print(f"失败: {e}")
    exit(1)

print("\n步骤2: 调用convert_to_relational_schema转换为关系模式")
try:
    tables = convert_to_relational_schema(schema)
    print("成功转换")
    print("Tables 摘要:")
    for table in tables:
        if table.primary_keys:
            print(f"  {table.name}: 联合主键 {table.primary_keys}")
        else:
            print(f"  {table.name}: 单列主键")
except Exception as e:
    print(f"失败: {e}")
    exit(1)

print("\n步骤3: 调用generate_mysql_ddl生成DDL")
try:
    create_statements, alter_statements = generate_mysql_ddl(tables)
    print("成功生成DDL")
    print("CREATE 语句:")
    print(create_statements[:500] + "..." if len(create_statements) > 500 else create_statements)
    print("ALTER 语句:")
    print(alter_statements[:500] + "..." if len(alter_statements) > 500 else alter_statements)
except Exception as e:
    print(f"失败: {e}")
    exit(1)

print("\n步骤4: 检查联合主键")
composite_keys = []
for table in tables:
    if len(table.primary_keys) > 1:
        composite_keys.append((table.name, table.primary_keys))
if composite_keys:
    print("发现联合主键:")
    for name, keys in composite_keys:
        print(f"  {name}: {keys}")
else:
    print("未发现联合主键")