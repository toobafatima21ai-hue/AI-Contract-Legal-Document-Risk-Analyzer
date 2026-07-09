FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_TIMEOUT=600 \
    PIP_RETRIES=10 \
    PIP_PREFER_BINARY=1

WORKDIR /app

# Upgrade pip first
RUN pip install --upgrade pip

# Install packages in separate layers
# Each RUN is cached independently — if one fails, Docker resumes from here
RUN pip install streamlit==1.35.0
RUN pip install requests==2.32.3
RUN pip install pandas==2.2.2

COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--server.enableCORS=false", \
     "--server.enableXsrfProtection=false"]