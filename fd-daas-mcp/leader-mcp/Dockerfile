FROM python:3.12-slim

WORKDIR /app

COPY mcp/leader-mcp/ /app/mcp/leader-mcp/
COPY akshare-agent-harness/ /app/akshare-agent-harness/

WORKDIR /app/mcp/leader-mcp
RUN pip install --no-cache-dir -e .

CMD ["python", "server.py"]
