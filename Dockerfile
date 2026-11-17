FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LINHVUONG_DATA_DIR=/data \
    LINHVUONG_WEB_HOST=0.0.0.0 \
    LINHVUONG_WEB_PORT=8000

WORKDIR /app

COPY pyproject.toml ./
COPY linhvuong ./linhvuong
COPY qrcode.png linhvuong.png linhvuong_menu.png ./

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir ".[web]" \
    && mkdir -p /data

VOLUME ["/data"]
EXPOSE 8000

STOPSIGNAL SIGTERM
CMD ["linhvuong-web", "--host", "0.0.0.0", "--port", "8000"]
