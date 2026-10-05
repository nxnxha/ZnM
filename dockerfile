FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    ffmpeg \
    libopus0 \
    libopus-dev \
    libffi-dev \
    build-essential \
    pkg-config \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && ldconfig

WORKDIR /app

COPY requirements.txt .

RUN python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements.txt

COPY . .

# Vérification et configuration de libopus
RUN echo "===== LIBOPUS =====" \
    && find /usr /lib -type f -name "libopus.so*" 2>/dev/null || true \
    && ldconfig -p | grep opus || true \
    && echo "===== FIN LIBOPUS ====="

CMD ["python", "-u", "MiriZeydan.py"]