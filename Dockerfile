FROM python:3.10-slim

WORKDIR /app

# 复制项目文件
COPY . /app/

# 安装依赖
RUN pip install --no-cache-dir -r requirements.txt

# 暴露 Streamlit 默认端口
EXPOSE 8501

# 启动命令
CMD ["streamlit", "run", "src/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
