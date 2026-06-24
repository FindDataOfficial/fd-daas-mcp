FROM python:3.11-slim

RUN pip install --no-cache-dir scrapling[fetchers] mcp sqlalchemy

COPY server.py /app/server.py

WORKDIR /app

ENTRYPOINT ["python", "server.py"]
