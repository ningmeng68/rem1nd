import sqlite3

# 连接到数据库
conn = sqlite3.connect('rem1nd.db')
cursor = conn.cursor()

# 打印数据库中所有表名
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = cursor.fetchall()
print("=== 数据库中的表 ===")
for table in tables:
    print(f"- {table[0]}")

# 检查 reminders 表
print("\n=== reminders 表 ===")
cursor.execute("PRAGMA table_info(reminders)")
reminder_columns = cursor.fetchall()
print("列名及类型:")
for col in reminder_columns:
    print(f"- {col[1]} ({col[2]})")

cursor.execute('SELECT * FROM reminders LIMIT 5')
reminder_rows = cursor.fetchall()
if reminder_rows:
    print("\n数据记录 (最多显示5条):")
    column_names = [col[1] for col in reminder_columns]
    for row in reminder_rows:
        print(dict(zip(column_names, row)))
else:
    print("\n数据库中没有 reminders 记录")

# 检查 smtp_config 表
print("\n=== smtp_config 表 ===")
cursor.execute("PRAGMA table_info(smtp_config)")
smtp_columns = cursor.fetchall()
print("列名及类型:")
for col in smtp_columns:
    print(f"- {col[1]} ({col[2]})")

cursor.execute('SELECT * FROM smtp_config ORDER BY updated_at DESC')
smtp_rows = cursor.fetchall()
if smtp_rows:
    print("\n数据记录:")
    column_names = [col[1] for col in smtp_columns]
    for row in smtp_rows:
        print(dict(zip(column_names, row)))
else:
    print("\n数据库中没有 smtp_config 记录")

# 关闭连接
conn.close()
