FROM python:3.11-slim

WORKDIR /app

# Sistem bağımlılıkları (EasyOCR için)
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

COPY . .

# EasyOCR modellerini build sirasinda indir
RUN python -c "import easyocr; easyocr.Reader(['tr', 'en'], gpu=False, download_enabled=True)"

EXPOSE 5050

CMD ["streamlit", "run", "app.py", "--server.port=5050", "--server.address=0.0.0.0"]
