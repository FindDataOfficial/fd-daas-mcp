# scrapling-docker-mcp

Self-built Docker image wrapping scrapling's MCP server. No external image dependency.

## Build

```bash
cd mcp/scrapling-docker-mcp
docker build -t scrapling-mcp .
```

## Config

```json
{
  "mcpServers": {
    "scrapling-docker-mcp": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "scrapling-mcp"]
    }
  }
}
```
