# 调试邮件发送功能
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# 请手动填写以下信息进行测试
smtp_config = {
    "server": "smtp.qq.com",  # 例如：smtp.qq.com, smtp.gmail.com, smtp.163.com
    "port": 465,  # 465 (SSL) 或 587 (TLS)
    "sender_email": "your_email@example.com",  # 发件人邮箱
    "password": "your_password",  # 授权码或密码
    "sender_name": "测试发送者"  # 发件人昵称
}

to_email = "recipient@example.com"  # 测试收件人邮箱
subject = "测试邮件"
body = "这是一封测试邮件，用于调试邮件发送功能。"

try:
    print("===== SMTP 调试信息 =====")
    print(f"SMTP 服务器: {smtp_config['server']}")
    print(f"端口: {smtp_config['port']}")
    print(f"发件人: {smtp_config['sender_name']} <{smtp_config['sender_email']}>")
    print(f"收件人: {to_email}")
    print("========================")
    
    port = smtp_config['port']
    
    if port == 465:
        print("正在使用 SSL 连接...")
        server = smtplib.SMTP_SSL(smtp_config["server"], port)
    else:
        print("正在使用 TLS 连接...")
        server = smtplib.SMTP(smtp_config["server"], port)
        server.set_debuglevel(1)  # 启用调试模式，显示详细信息
        print("正在启动 TLS...")
        server.starttls()
    
    server.set_debuglevel(1)  # 启用调试模式，显示详细信息
    
    print("正在登录...")
    server.login(smtp_config["sender_email"], smtp_config["password"])
    
    print("正在创建邮件...")
    msg = MIMEMultipart()
    msg["From"] = f"{smtp_config['sender_name']} <{smtp_config['sender_email']}>"
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))
    
    print("正在发送邮件...")
    text = msg.as_string()
    server.sendmail(smtp_config["sender_email"], to_email, text)
    
    print("邮件发送成功！")
    server.quit()
    print("========================")
except Exception as e:
    print(f"邮件发送失败: {e}")
    print("========================")
    print("可能的原因：")
    print("1. SMTP服务器地址或端口错误")
    print("2. 发件人邮箱或密码/授权码错误")
    print("3. SMTP服务未开启或授权码未生成")
    print("4. 网络连接问题")
    print("5. 防火墙或安全软件阻止")
    print("========================")
