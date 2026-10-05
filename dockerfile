FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    ffmpeg \
    libopus0 \
    libopus-dev \
    libffi-dev \
    build-essential \
    pkg-config \
    ca-certificates \
    && ldconfig \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements.txt

COPY . .

RUN echo "=== VERIFICATION LIBOPUS ===" \
    && ldconfig -p | grep opus || true \
    && find /usr -name "libopus.so*" 2>/dev/null || true \
    && echo "=== FIN VERIFICATION LIBOPUS ==="

CMD ["python", "-u", "MiriZeydan.py"]