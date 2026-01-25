# 构建阶段
FROM python:3.11-alpine AS builder

# 设置国内源
RUN sed -i 's/dl-cdn.alpinelinux.org/mirrors.aliyun.com/g' /etc/apk/repositories && \
    pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/ && \
    pip config set global.trusted-host mirrors.aliyun.com

# 设置工作目录
WORKDIR /app

# 安装编译依赖
RUN apk add --no-cache gcc musl-dev libffi-dev

# 复制依赖文件
COPY requirements.txt .

# 安装依赖到指定目录
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# 运行阶段
FROM python:3.11-alpine

# 设置国内源
RUN sed -i 's/dl-cdn.alpinelinux.org/mirrors.aliyun.com/g' /etc/apk/repositories

# 设置工作目录
WORKDIR /app

# 从构建阶段复制安装好的依赖
COPY --from=builder /install /usr/local

# 复制项目代码
COPY . .

# 移除不需要的文件
RUN rm -rf __pycache__

# 设置环境变量
ENV FLASK_APP=main.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_RUN_PORT=5000

# 暴露端口
EXPOSE 5000

# 启动命令
CMD ["python", "main.py"]