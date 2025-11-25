#!/usr/bin/env python3
"""
数据库初始化脚本
用于创建数据库表结构
"""

from database import init_db, engine
from sqlalchemy import text

def init_database():
    """初始化数据库"""
    print("正在初始化数据库...")

    # 创建表
    init_db()

    print("数据库初始化完成！")

    # 显示创建的表
    with engine.connect() as conn:
        result = conn.execute(text("SHOW TABLES"))
        tables = result.fetchall()
        print("已创建的表:")
        for table in tables:
            print(f"  - {table[0]}")

if __name__ == "__main__":
    init_database()