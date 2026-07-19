# 编写技能

DAAS 技能位于 `.claude/skills/`。两个元技能处理创建 -- 对 daas 技能要用领域封装，而非通用那个。

## 用哪个创建器

| 你要创建 | 用 |
| --- | --- |
| `fd-daas-*` 数据技能 | `fd-daas-skill-creator`（封装 `fd-coding-skill-creator`，注入 daas 护栏） |
| `fd-coding-*` 基础设施/构建技能 | `fd-coding-skill-creator` 直接用（若有领域封装则用） |
| 文档站技能 | `fd-coding-documents-builder` / `fd-coding-documents-add` |

**不要**对 daas 技能直接用 `fd-coding-skill-creator` -- 你会跳过 daas 护栏（实时表面检查、`daas.db` 表、dispatch 前缀、`daas-doc/` 路径、run-notification、缺陷词汇）。

## 创建循环

`fd-coding-skill-creator` 跑：**草稿 -> 评测 -> 审查 -> 迭代 ->（可选）描述优化**。`fd-daas-skill-creator` 把机制委托给它，并在上面叠加 daas 正确性。

1. **捕获意图** -- 技能做什么、何时触发（中英文表述）、预期输出、是否需要测试用例。对 daas 技能还要钉：读写哪些 `daas.db` 表、哪个 dispatch 前缀（若获取）、写哪个 `daas-doc/` 路径、是否采用 `skill-run-notification`。
2. **把工艺委托给** `fd-coding-skill-creator`。
3. **应用 daas 护栏** -- 新技能的 `description` 触发其意图**且不与**已有家族冲突（`routing-drift`）；不引用已移除表面（`stale-ref`）；用正确的表名 + dispatch 前缀；文档写到 `daas-doc/`；若跑工作流则采用 `skill-run-notification`。
4. **验证** 用下面的检视/校验流程。

## 技能结构

```
.claude/skills/<name>/
  SKILL.md            # frontmatter（name、description）+ 指令
  scripts/            # 辅助脚本（可选）
  references/         # 领域知识 markdown（可选）
```

`description` 是路由键 -- 它必须触发正确意图且**不与**兄弟技能冲突。

## 检视/审查已有技能

```bash
uv run python .claude/skills/fd-daas-skill-review/scripts/skill_smoke_test.py --skill <name>
```

缺陷词汇：`malformed`、`script-bug`、`stale-ref`、`routing-drift`。每条报为 `<defect-class>: <skill>: <detail>`，通过 `fd-coding-skill-creator`（编辑路径）修复。

## 参考

- `fd-daas-skill-creator` -> `references/daas-concepts.md` -- 架构、表、前缀、`daas-doc/`、run-notification、缺陷词汇、已移除表面、技能家族路由边界的唯一事实来源。
