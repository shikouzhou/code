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
        "description": "学生选课系统：学生有学号、姓名；课程有课程号、名称；学生可以选多门课，每门课可被多个学生选。"
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