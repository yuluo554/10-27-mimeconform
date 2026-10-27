# 离线镜像：证明"零第三方运行时依赖 + 运行期无网络"。
# 关键：**不 pip install**。构建期只 COPY 源码，运行期零安装。
FROM python:3.12-slim

WORKDIR /work
COPY . /work

# 不装任何包；直接用系统 CPython 跑
ENV PYTHONUTF8=1 \
    PYTHONDONTWRITEBYTECODE=1

CMD ["python", "-m", "mimeconform", "--version"]
