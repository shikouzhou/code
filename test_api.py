import requests
import json

# 测试API
def test_generate_schema():
    url = "http://localhost:8000/generate-schema"
    payload = {
        "description": "学生选课系统：学生有学号、姓名；课程有课程号、名称；学生可以选多门课，每门课可被多个学生选。"
    }

    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            data = response.json()
            print("✅ API调用成功！")
            print("Schema:", json.dumps(data["schema"], indent=2, ensure_ascii=False))
            print("DDL:")
            print(data["ddl"])
            print("Session ID:", data["session_id"])
        else:
            print(f"❌ API调用失败: {response.status_code}")
            print(response.text)
    except requests.exceptions.ConnectionError:
        print("❌ 无法连接到服务器，请确保FastAPI应用正在运行")
    except Exception as e:
        print(f"💥 错误: {e}")

if __name__ == "__main__":
    test_generate_schema()