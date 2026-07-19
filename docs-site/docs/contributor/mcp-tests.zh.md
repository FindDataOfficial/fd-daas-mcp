# MCP 测试套件

`fd-daas-mcp` 服务器带一个离线 pytest 套件和一个 selfcheck。在改动服务器或某组前后都跑一下。

## 跑测试

```bash
fd-daas-mcp/.venv/bin/python -m pytest fd-daas-mcp/tests
```

套件是离线的 -- 不碰网络。覆盖 registry 构建、各组工具接线、合并层。

## 自检（离线不变量）

```bash
fd-daas-mcp/.venv/bin/python -m fd_daas_mcp.selfcheck
```

`selfcheck.py` 跑 `run_invariants()` -- 确认服务器接线正确（registry 从各 `<group>-mcp/` 收割工具、服务器与 CLI 表面一致等）。

## 手动启动服务器

```bash
fd-daas-mcp/bin/fd-daas-mcp-server
```

`.mcp.json` 把 `command` 指向此脚本 -- 一个自定位 POSIX shell，设置 `PYTHONPATH` 并 exec `.venv/bin/python -m fd_daas_mcp.server`。

## 布局

```
fd-daas-mcp/
  daas/fd_daas_mcp/    # server.py / registry.py / cli.py / selfcheck.py
  <group>-mcp/         # alerts/cron/composite/daas/dashboard/leader/pdf/research
  bin/fd-daas-mcp-server
  tests/               # 离线 pytest 套件
  pyproject.toml
```

## 添加一个 MCP 工具

1. 在其组包里加工具（`fd-daas-mcp/<group>-mcp/`）。
2. `registry.build()` 自动 AST 收割它（各组 `sys.modules` 隔离）-- 以 `<group>_<tool>` 出现在服务器和 CLI 上。
3. 跑测试 + 自检。
4. 若面向用户，在 [MCP 工具 -> 工具组](../mcp/groups.md) 加一行。
