FROM python:3.10-alpine as build

# 安装构建依赖
RUN apk update && apk add --no-cache --virtual .build-deps \
    git build-base libffi-dev libstdc++ rust cargo

# 设置Rust缓存目录
ENV CARGO_HOME=/usr/local/cargo
ENV RUSTUP_HOME=/usr/local/rustup
ENV PATH=/usr/local/cargo/bin:$PATH

# 创建缓存挂载点
RUN --mount=type=cache,target=/usr/local/cargo/registry \
    --mount=type=cache,target=/usr/local/cargo/git \
    --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip

# 复制requirements.txt并安装依赖
COPY requirements.txt /build/requirements.txt
WORKDIR /build

# 使用缓存挂载安装Python依赖
RUN --mount=type=cache,target=/usr/local/cargo/registry \
    --mount=type=cache,target=/usr/local/cargo/git \
    --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r ./requirements.txt

# 清理构建依赖
RUN apk del .build-deps

FROM python:3.10-alpine

# 复制已安装的Python包
COPY --from=build /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages

# 复制应用代码
COPY . /Crisp-Telegram-Bot
WORKDIR /Crisp-Telegram-Bot

# 设置执行权限
RUN chmod +x ./docker-entrypoint.sh

ENTRYPOINT [ "./docker-entrypoint.sh" ]
CMD ["python3","bot.py"]