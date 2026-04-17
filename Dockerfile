FROM python:3.11-slim

WORKDIR /app

# 系统依赖（TicNote 导出用 playwright 需要；主服务本身不需要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates && rm -rf /var/lib/apt/lists/*

# Python 依赖先装（利用镜像层缓存）
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# 应用代码
COPY .app/ /app/.app/
COPY sample-vault/ /app/sample-vault/
COPY scripts/ /app/scripts/

# 运行时默认：vault 挂 /data，auth 元数据挂 /home
RUN mkdir -p /data /home/.ome365
ENV OME365_VAULT=/data \
    OME365_HOME=/home/.ome365 \
    OME365_PORT=3650 \
    OME365_COMPAT_LEGACY=1

EXPOSE 3650

WORKDIR /app/.app

# 用 uvicorn 直接跑（比 python3 server.py 更干净：无 __main__ 启动逻辑）
# server.py 里的 if __name__ 块只做 dir 初始化，这里已经 mkdir 过了
CMD ["python3", "server.py"]
