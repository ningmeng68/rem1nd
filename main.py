from flask import Flask, render_template, request, jsonify
import sqlite3
import os
from datetime import datetime, UTC
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from apscheduler.schedulers.background import BackgroundScheduler
import json

# 初始化 Flask 应用
app = Flask(__name__)

# 配置
DATABASE = 'data/rem1nd.db'

# 初始化数据库
def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # 检查 reminders 表是否存在
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='reminders'")
    table_exists = cursor.fetchone()
    
    if not table_exists:
        # 如果表不存在，创建表
        cursor.execute('''
            CREATE TABLE reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                trigger_time DATETIME NOT NULL,
                recipient_email TEXT NOT NULL,
                sent INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                repeat_type TEXT DEFAULT NULL,
                repeat_interval INTEGER DEFAULT NULL,
                next_trigger_time DATETIME,
                last_sent_time DATETIME
            )
        ''')
    else:
        # 检查是否需要添加字段
        cursor.execute("PRAGMA table_info(reminders)")
        columns = [column[1] for column in cursor.fetchall()]
        
        # 添加缺失的字段
        if 'repeat_type' not in columns:
            cursor.execute("ALTER TABLE reminders ADD COLUMN repeat_type TEXT DEFAULT NULL")
        if 'repeat_interval' not in columns:
            cursor.execute("ALTER TABLE reminders ADD COLUMN repeat_interval INTEGER DEFAULT NULL")
        if 'next_trigger_time' not in columns:
            cursor.execute("ALTER TABLE reminders ADD COLUMN next_trigger_time DATETIME")
        if 'last_sent_time' not in columns:
            cursor.execute("ALTER TABLE reminders ADD COLUMN last_sent_time DATETIME")
    
    # 检查 smtp_config 表是否存在
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='smtp_config'")
    smtp_table_exists = cursor.fetchone()
    
    if not smtp_table_exists:
        # 如果表不存在，创建表
        cursor.execute('''
            CREATE TABLE smtp_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                server TEXT NOT NULL,
                port INTEGER NOT NULL,
                sender_email TEXT NOT NULL,
                password TEXT NOT NULL,
                sender_name TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
    
    conn.commit()
    conn.close()

# 初始化数据库（无论使用哪种方式运行，都会执行）
init_db()

# 获取数据库连接
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# 加载 SMTP 配置
def load_smtp_config():
    conn = get_db()
    cursor = conn.cursor()
    
    # 从数据库读取配置
    cursor.execute('SELECT * FROM smtp_config ORDER BY updated_at DESC LIMIT 1')
    config = cursor.fetchone()
    conn.close()
    
    if config:
        # 数据库中有配置，返回
        return {
            'server': config['server'],
            'port': config['port'],
            'sender_email': config['sender_email'],
            'password': config['password'],
            'sender_name': config['sender_name']
        }
    
    # 数据库中没有配置，返回 None
    return None

# 保存 SMTP 配置
def save_smtp_config(config):
    conn = get_db()
    cursor = conn.cursor()
    
    # 检查是否已有配置
    cursor.execute('SELECT id FROM smtp_config LIMIT 1')
    existing = cursor.fetchone()
    
    if existing:
        # 更新现有配置
        cursor.execute('''
            UPDATE smtp_config 
            SET server = ?, port = ?, sender_email = ?, password = ?, sender_name = ?, updated_at = CURRENT_TIMESTAMP 
            WHERE id = ?
        ''', (
            config['server'], config['port'], config['sender_email'], 
            config['password'], config['sender_name'], existing['id']
        ))
    else:
        # 插入新配置
        cursor.execute('''
            INSERT INTO smtp_config (server, port, sender_email, password, sender_name)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            config['server'], config['port'], config['sender_email'], 
            config['password'], config['sender_name']
        ))
    
    conn.commit()
    conn.close()

# 发送邮件
def send_email(smtp_config, to_email, subject, body):
    try:
        print(f"[{datetime.now()}] 准备发送邮件")
        print(f"[{datetime.now()}] 发件人: {smtp_config['sender_name']} <{smtp_config['sender_email']}>")
        print(f"[{datetime.now()}] 收件人: {to_email}")
        print(f"[{datetime.now()}] 主题: {subject}")
        
        msg = MIMEMultipart()
        msg['From'] = f"{smtp_config['sender_name']} <{smtp_config['sender_email']}>"
        msg['To'] = to_email
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'plain'))
        
        # 根据端口选择连接方式（465通常用于SSL，587用于TLS）
        port = smtp_config['port']
        print(f"[{datetime.now()}] 连接到 SMTP 服务器: {smtp_config['server']}:{port}")
        
        if port == 465:
            # SSL连接
            print(f"[{datetime.now()}] 使用 SSL 连接")
            server = smtplib.SMTP_SSL(smtp_config['server'], port)
        else:
            # TLS连接
            print(f"[{datetime.now()}] 使用 TLS 连接")
            server = smtplib.SMTP(smtp_config['server'], port)
            server.starttls()
        
        print(f"[{datetime.now()}] 登录 SMTP 服务器...")
        server.login(smtp_config['sender_email'], smtp_config['password'])
        print(f"[{datetime.now()}] 登录成功")
        
        text = msg.as_string()
        print(f"[{datetime.now()}] 发送邮件...")
        server.sendmail(smtp_config['sender_email'], to_email, text)
        print(f"[{datetime.now()}] 邮件发送成功")
        server.quit()
        print(f"[{datetime.now()}] SMTP 连接已关闭")
        return True
    except Exception as e:
        print(f"[{datetime.now()}] 邮件发送失败: {e}")
        return False

# 计算下一次触发时间
def calculate_next_trigger_time(trigger_time, repeat_type, repeat_interval):
    from datetime import timedelta
    
    dt = datetime.fromisoformat(trigger_time)
    
    if repeat_type == 'daily':
        return (dt + timedelta(days=1)).isoformat()
    elif repeat_type == 'weekly':
        return (dt + timedelta(weeks=1)).isoformat()
    elif repeat_type == 'monthly':
        return (dt + timedelta(days=30)).isoformat()
    elif repeat_type == 'yearly':
        return (dt + timedelta(days=365)).isoformat()
    elif repeat_type == 'custom' and repeat_interval:
        return (dt + timedelta(days=repeat_interval)).isoformat()
    else:
        return None

# 检查并发送到期提醒
def check_reminders():
    try:
        print(f"[{datetime.now()}] 开始检查到期提醒")
        conn = get_db()
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        print(f"[{datetime.now()}] 当前时间: {datetime.now()}")
        
        # 检查 next_trigger_time 或 trigger_time
        cursor.execute('''
            SELECT * FROM reminders 
            WHERE ((next_trigger_time <= ? AND next_trigger_time IS NOT NULL) 
            OR (trigger_time <= ? AND next_trigger_time IS NULL)) 
            AND sent = 0
        ''', (now, now))
        reminders = cursor.fetchall()
        
        print(f"[{datetime.now()}] 找到 {len(reminders)} 个到期提醒")
        
        smtp_config = load_smtp_config()
        if not smtp_config:
            print(f"[{datetime.now()}] 未找到 SMTP 配置，跳过发送")
            return
        
        print(f"[{datetime.now()}] 使用 SMTP 配置: {smtp_config['server']}:{smtp_config['port']}")
        
        for reminder in reminders:
            print(f"[{datetime.now()}] 处理提醒: {reminder['title']} (ID: {reminder['id']})")
            print(f"[{datetime.now()}] 收件人: {reminder['recipient_email']}")
            print(f"[{datetime.now()}] 触发时间: {reminder['trigger_time']}")
            
            if send_email(
                smtp_config,
                reminder['recipient_email'],
                f"提醒: {reminder['title']}",
                reminder['content']
            ):
                print(f"[{datetime.now()}] 邮件发送成功")
                repeat_type = reminder['repeat_type']
                
                if repeat_type and repeat_type != 'none':
                    print(f"[{datetime.now()}] 这是循环提醒，类型: {repeat_type}")
                    # 计算下一次触发时间
                    current_trigger = reminder['next_trigger_time'] or reminder['trigger_time']
                    next_trigger = calculate_next_trigger_time(
                        current_trigger,
                        repeat_type,
                        reminder['repeat_interval']
                    )
                    
                    if next_trigger:
                        # 记录当前时间为上次发送时间
                        last_sent = datetime.now().isoformat()
                        # 更新为下一次触发时间，保持 sent = 0
                        cursor.execute(
                            'UPDATE reminders SET next_trigger_time = ?, sent = 0, last_sent_time = ? WHERE id = ?',
                            (next_trigger, last_sent, reminder['id'])
                        )
                        print(f"[{datetime.now()}] 已更新下一次触发时间: {next_trigger}")
                        print(f"[{datetime.now()}] 已记录上次发送时间: {last_sent}")
                else:
                    # 非循环提醒，标记为已发送
                    cursor.execute('UPDATE reminders SET sent = 1 WHERE id = ?', (reminder['id'],))
                    print(f"[{datetime.now()}] 已标记为已发送")
                
                conn.commit()
                print(f"[{datetime.now()}] 数据库已更新")
            else:
                print(f"[{datetime.now()}] 邮件发送失败")
        
        conn.close()
        print(f"[{datetime.now()}] 检查提醒完成")
    except Exception as e:
        print(f"[{datetime.now()}] 检查提醒失败: {e}")

# 简化调度器启动逻辑
# 直接启动调度器，不进行复杂的进程检查
# 在Flask调试模式下，虽然会创建多个进程，但APScheduler会自动处理重复作业

# 初始化并启动调度器
scheduler = BackgroundScheduler()
scheduler.add_job(func=check_reminders, trigger="interval", seconds=30)
scheduler.start()

# 应用关闭时关闭调度器
import atexit
atexit.register(lambda: scheduler.shutdown())

# 路由

# 首页
@app.route('/')
def index():
    return render_template('index.html')

# SMTP 配置 API
@app.route('/api/smtp/config', methods=['GET', 'POST'])
def smtp_config():
    if request.method == 'GET':
        config = load_smtp_config()
        return jsonify(config if config else {})
    elif request.method == 'POST':
        config = {
            "server": request.form.get('server'),
            "port": int(request.form.get('port')),
            "sender_email": request.form.get('sender_email'),
            "password": request.form.get('password'),
            "sender_name": request.form.get('sender_name')
        }
        save_smtp_config(config)
        return jsonify({"status": "success"})

# 测试 SMTP 配置
@app.route('/api/smtp/test', methods=['POST'])
def test_smtp():
    config = {
        "server": request.form.get('server'),
        "port": int(request.form.get('port')),
        "sender_email": request.form.get('sender_email'),
        "password": request.form.get('password'),
        "sender_name": request.form.get('sender_name')
    }
    test_email = request.form.get('test_email')
    
    if send_email(
        config,
        test_email,
        "SMTP 配置测试",
        "这是一封测试邮件，用于验证您的 SMTP 配置是否正确。"
    ):
        return jsonify({"status": "success"})
    else:
        return jsonify({"status": "error"}), 400

# 提醒管理 API
@app.route('/api/reminders', methods=['GET', 'POST'])
def reminders():
    if request.method == 'GET':
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM reminders ORDER BY trigger_time')
        reminders = cursor.fetchall()
        conn.close()
        
        return jsonify([dict(r) for r in reminders])
    elif request.method == 'POST':
        try:
            title = request.form.get('title')
            content = request.form.get('content')
            trigger_time_str = request.form.get('trigger_time')
            recipient_email = request.form.get('recipient_email')
            repeat_type = request.form.get('repeat_type') or 'none'
            repeat_interval = request.form.get('repeat_interval')
            
            # 将 datetime-local 格式转换为完整的 ISO 格式
            trigger_time = datetime.strptime(trigger_time_str, '%Y-%m-%dT%H:%M')
            trigger_time_iso = trigger_time.isoformat()
            
            next_trigger_time = trigger_time_iso
            
            # 处理循环间隔
            if repeat_interval:
                repeat_interval = int(repeat_interval)
            else:
                repeat_interval = None
            
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO reminders (title, content, trigger_time, recipient_email, repeat_type, repeat_interval, next_trigger_time) VALUES (?, ?, ?, ?, ?, ?, ?)',
                (title, content, trigger_time_iso, recipient_email, repeat_type, repeat_interval, next_trigger_time)
            )
            conn.commit()
            
            reminder_id = cursor.lastrowid
            cursor.execute('SELECT * FROM reminders WHERE id = ?', (reminder_id,))
            reminder = dict(cursor.fetchone())
            conn.close()
            
            return jsonify({"status": "success", "reminder": reminder})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 400

# 单个提醒管理 API
@app.route('/api/reminders/<int:reminder_id>', methods=['PUT', 'DELETE'])
def reminder(reminder_id):
    if request.method == 'PUT':
        try:
            title = request.form.get('title')
            content = request.form.get('content')
            trigger_time_str = request.form.get('trigger_time')
            recipient_email = request.form.get('recipient_email')
            repeat_type = request.form.get('repeat_type') or 'none'
            repeat_interval = request.form.get('repeat_interval')
            
            # 将 datetime-local 格式转换为完整的 ISO 格式
            trigger_time = datetime.strptime(trigger_time_str, '%Y-%m-%dT%H:%M')
            trigger_time_iso = trigger_time.isoformat()
            
            next_trigger_time = trigger_time_iso
            
            # 处理循环间隔
            if repeat_interval:
                repeat_interval = int(repeat_interval)
            else:
                repeat_interval = None
            
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE reminders SET title = ?, content = ?, trigger_time = ?, recipient_email = ?, repeat_type = ?, repeat_interval = ?, next_trigger_time = ? WHERE id = ?',
                (title, content, trigger_time_iso, recipient_email, repeat_type, repeat_interval, next_trigger_time, reminder_id)
            )
            conn.commit()
            
            cursor.execute('SELECT * FROM reminders WHERE id = ?', (reminder_id,))
            reminder = dict(cursor.fetchone())
            conn.close()
            
            return jsonify({"status": "success", "reminder": reminder})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 400
    elif request.method == 'DELETE':
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM reminders WHERE id = ?', (reminder_id,))
            conn.commit()
            conn.close()
            return jsonify({"status": "success"})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 400

# 主程序入口
if __name__ == '__main__':
    init_db()
    # 开发环境运行，生产环境应使用WSGI服务器
    app.run(host='0.0.0.0', debug=False, port=5000)