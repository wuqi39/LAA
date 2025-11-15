import sqlite3
import os

# 数据库路径
db_path = os.path.join('resource', 'laa_data.db')

# 连接数据库
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 查看表
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()
print("数据库中的表:", tables)

# 查看任务表
if ('tasks',) in tables:
    cursor.execute("SELECT * FROM tasks")
    tasks = cursor.fetchall()
    print("\n任务表内容:")
    for task in tasks:
        print(task)

# 查看笔记表
if ('notes',) in tables:
    cursor.execute("SELECT * FROM notes")
    notes = cursor.fetchall()
    print("\n笔记表内容:")
    for note in notes:
        print(note)

conn.close()