FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir fastapi uvicorn python-multipart faster-whisper

# Copy app code only (vault is mounted as volume)
COPY .app/ /app/.app/
COPY sample-vault/ /app/sample-vault/

# Init vault if empty
RUN mkdir -p /data/Journal/Daily /data/Journal/Weekly /data/Journal/Monthly /data/Journal/Quarterly \
    /data/Notes /data/Decisions /data/Contacts/people /data/Projects /data/AI-Logs /data/Templates

EXPOSE 3650

# Vault is mounted at /data
ENV OME365_VAULT=/data

WORKDIR /app/.app
CMD ["python3", "server.py"]
