# 组合一个 MCP

**复合（composite）** 是一个精选的 MCP 表面：从一个或多个上游 MCP 服务器里挑出少量工具，可选地嵌入已注册的工作流清单，附上一段系统提示词，然后把整体作为一个命名 MCP 提供出来。复合存储在 `daas.db` 中，由合并后的 `fd-daas-mcp` 服务器在进程内提供。

本页是作者流程：清单格式 → 工具选择 → 工作流嵌入 → 提示词 → 运行。逐工具参考见
[工具组](groups.md)。引导式脚手架可使用 `fd-coding-mcp-creator` 技能。

## 清单格式

复合清单（由 `composite_create_manifest` 写入）是一个 JSON 对象：

```json
{
  "name": "macro-analyst",
  "description": "宏观取数 + 指标，限定在主权系列",
  "upstreams": [
    {"key": "data", "transport": "http", "url": "http://127.0.0.1:8300"}
  ],
  "tools": [
    {"upstream": "data", "tool": "read"}
  ],
  "workflows": ["data-fetch", "indicators"],
  "prompt": "你是一名宏观数据分析师，只取主权和央行系列……"
}
```

| 字段 | 用途 |
| --- | --- |
| `name` | 唯一的复合名；用 `COMPOSITE=<name>` 来提供它。 |
| `description` | 可选的人类可读标签。 |
| `upstreams` | 复合代理的 MCP 服务器。`key` 是挂载命名空间（提供出来的工具名为 `<key>_<tool>`）。`transport` = `http`（需要 `url`）或 `stdio`（需要 `command`/`args`/`env`/`cwd`）。规范上游是 `fd-open-data-mcp`，HTTP 地址 `http://127.0.0.1:8300`。 |
| `tools` | `{upstream: <key>, tool: <name>}` 列表。每个都被代理并以 `<key>_<tool>` 提供。 |
| `workflows` | 已注册工作流清单的名称（`workflows` 表中的行，通过 `workflow_register` 注册）。每个都作为一个惰性工具出现，调用时运行工作流引擎。 |
| `prompt` | 应用到复合 FastMCP 表面的系统提示词。 |

## 作者流程

### 1. 选上游

几乎总是只用 `fd-open-data-mcp`（HTTP @ :8300，key `data`）。它覆盖全部数据取数。只有当你需要一个数据层未前置的服务器时，才加第二个上游。

### 2. 选工具

列出一个上游暴露了什么，再挑你需要的少数：

```
composite_list_available_tools(composite="macro-analyst", upstream_key="data")
composite_add_tool(composite="macro-analyst", upstream_key="data", tool_name="read")
```

或者在清单模式下，一次性传入整组：

```
composite_create_manifest(
    name="macro-analyst",
    upstreams=[{"key": "data", "transport": "http", "url": "http://127.0.0.1:8300"}],
    tools=[{"upstream": "data", "tool": "read"}],
)
```

### 3. 嵌入工作流

嵌入一个已注册的工作流，调用者就能在不记步骤的情况下触发多步取数。用 `workflow_list()` 列出已注册工作流，然后在 `workflows` 里传它们的名称：

```
composite_create_manifest(..., workflows=["data-fetch", "indicators"])
```

每个名称在复合里变成一个惰性工具——调用它会用你传入的参数运行工作流引擎。

### 4. 附提示词

一段简短的系统提示词界定服务端代理的范围。保持简短——范围胜过剧本：

```
composite_create_manifest(..., prompt="你是一名宏观数据分析师，只取主权和央行系列。")
```

### 5. 运行

```bash
COMPOSITE=macro-analyst fd-daas-mcp/bin/fd-daas-mcp-server
```

提供出来的表面包含：每个选中的工具（名为 `<key>_<tool>`）、每个嵌入的工作流（作为独立工具），外加管理工具——全部在系统提示词之下。

## 维护

- **更新** — `composite_update_manifest(name, ...)`；注意 `upstreams`/`tools` 在给出时会整体替换现有集合。
- **列出** — `composite_list_manifests()`。
- **删除** — `composite_delete_manifest(name)`（级联删除上游/工具/链）。

## 原则

- **精选而非新建。** 复合只选择已存在的工具/工作流；从不发明新的。若需要的工具不存在，先构建上游（`fd-coding-daas-datasource-builder`）或注册工作流（`workflow_register`）。
- **默认一个上游。** `fd-open-data-mcp` 覆盖全部数据取数。
- **提示词是范围，不是剧本。** 简短的边界胜过冗长的剧本。
