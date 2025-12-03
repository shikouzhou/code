import requests
import json
import time

BASE_URL = "http://localhost:8000"

def register_user():
    """注册测试用户"""
    url = f"{BASE_URL}/auth/register"
    payload = {
        "username": "testuser",
        "email": "test@example.com",
        "password": "test123"
    }

    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            data = response.json()
            print("✅ 用户注册成功！")
            return data["access_token"]
        else:
            print(f"注册失败: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"注册错误: {e}")
        return None

def login_user():
    """登录获取token"""
    url = f"{BASE_URL}/auth/login"
    payload = {
        "username": "testuser",
        "password": "test123"
    }

    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            data = response.json()
            print("✅ 用户登录成功！")
            return data["access_token"]
        else:
            print(f"登录失败: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"登录错误: {e}")
        return None

def test_generate_schema(token):
    """测试生成数据库模式"""
    url = f"{BASE_URL}/generate-schema"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "description": "我们要开发一个智能仓储与物流调度系统。系统中有仓库管理员、配送员和客户，所有内部人员（管理员和配送员）都归属于一个仓库（Warehouse），每个仓库有名称、所在城市、容量上限和负责人（必须是仓库管理员）。客户可以创建发货订单（Orders），每个订单包含收货地址、期望送达时间、货物类型（普通、易碎、冷藏）和总件数。系统根据订单自动分配最近的可用仓库，并生成一条出库任务（OutboundTask），记录预计打包时间、实际完成时间及状态（待处理、已打包、已发货、已取消）。每个仓库维护其库存明细（InventoryItems），记录每种商品（由 SKU 唯一标识）的当前数量、安全库存阈值和最后盘点时间。当库存低于阈值时，系统自动生成补货申请（ReplenishmentRequest），并通知采购人员。配送员通过系统接收配送任务（DeliveryTasks），每个任务关联一个或多个订单，包含路线规划、预计出发/到达时间、车辆编号。配送完成后，客户可对本次配送进行签收确认和服务评分（1-5星），并可上传异常照片（如货物破损）。系统支持定义运输规则（ShippingRules），例如“冷藏货物必须使用冷链车辆”、“易碎品需单独包装”，规则应用于订单审核阶段。所有关键操作（如创建订单、修改库存、分配配送员、取消任务）均记录到操作审计日志（AuditLogs），包含操作人、操作对象 ID、变更前/后值（JSON）、时间戳和 IP 地址。此外，系统采用基于角色的访问控制（RBAC）：用户角色包括客户、仓库管理员、配送员、采购专员和系统运维；一个内部用户可拥有多个角色（如某人既是仓库管理员又是采购专员），但客户不能拥有内部角色。所有主数据（仓库、用户、订单、库存、配送任务、补货申请）均支持软删除（is_active 字段），并自动维护 created_at 与 updated_at 时间戳。"
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            data = response.json()
            print("✅ 数据库模式生成成功！")
            print("Schema:", json.dumps(data["schema"], indent=2, ensure_ascii=False))
            print("DDL:")
            print(data["ddl"])
            print("Session ID:", data["session_id"])
            return True
        else:
            print(f"❌ 生成失败: {response.status_code}")
            print(response.text)
            # 输出 LLM 生成的 schema
            try:
                from schema_generator import parse_natural_language_to_schema
                schema = parse_natural_language_to_schema(payload["description"])
                print("LLM 生成的 Schema:")
                print(json.dumps(schema, indent=2, ensure_ascii=False))
            except Exception as e:
                print(f"无法获取本地 schema: {e}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ 无法连接到服务器，请确保FastAPI应用正在运行")
        return False
    except Exception as e:
        print(f"💥 错误: {e}")
        return False

def test_get_history(token):
    """测试获取用户历史记录"""
    url = f"{BASE_URL}/user/history"
    headers = {"Authorization": f"Bearer {token}"}

    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            print("✅ 获取历史记录成功！")
            print(f"总记录数: {data['total_count']}")
            if data['records']:
                print("最新记录:")
                record = data['records'][0]
                print(f"  描述: {record['description'][:50]}...")
                print(f"  创建时间: {record['created_at']}")
            return True
        else:
            print(f"❌ 获取历史失败: {response.status_code}")
            print(response.text)
            return False
    except Exception as e:
        print(f"获取历史错误: {e}")
        return False

def main():
    """主测试函数"""
    print("🚀 开始API测试...")

    # 尝试注册用户（如果失败可能是已存在）
    token = register_user()
    if not token:
        # 如果注册失败，尝试登录
        token = login_user()

    if not token:
        print("❌ 无法获取访问令牌，测试终止")
        return

    print("\n" + "="*50)
    print("📝 测试生成数据库模式...")
    success1 = test_generate_schema(token)

    print("\n" + "="*50)
    print("📚 测试获取历史记录...")
    success2 = test_get_history(token)

    print("\n" + "="*50)
    if success1 and success2:
        print("🎉 所有测试通过！")
    else:
        print("⚠️  部分测试失败")

if __name__ == "__main__":
    main()