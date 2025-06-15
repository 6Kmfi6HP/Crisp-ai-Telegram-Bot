import sqlite3
import os

db_file = 'session_data.db'

if os.path.exists(db_file):
    print(f"数据库文件存在: {db_file}")
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    # 检查表结构
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print(f"表: {tables}")
    
    if tables:
        # 检查sessions表的数据
        cursor.execute("SELECT * FROM sessions")
        data = cursor.fetchall()
        print(f"会话数据条数: {len(data)}")
        for row in data:
            print(f"  {row}")
    
    conn.close()
else:
    print(f"数据库文件不存在: {db_file}")

# 检查persistence模块是否能正常导入
try:
    from persistence import SessionPersistence
    print("persistence模块导入成功")
except Exception as e:
    print(f"persistence模块导入失败: {e}")