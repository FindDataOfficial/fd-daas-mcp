FROM python:3.12-slim

WORKDIR /app

COPY mcp/akshare-mcp/ /app/mcp/akshare-mcp/
COPY akshare-agent-harness/ /app/akshare-agent-harness/

WORKDIR /app/mcp/akshare-mcp
RUN pip install --no-cache-dir -e .

CMD ["python", "server.py"]
