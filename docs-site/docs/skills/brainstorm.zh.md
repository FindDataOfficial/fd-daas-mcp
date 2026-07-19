# fd-daas-brainstorm

**在构建任何东西之前澄清研究目标。** 当你确定要研究什么但还没想清楚具体研究什么时使用。

## 何时触发

如：

- "我想研究一只股票但还没想清楚"
- "help me brainstorm a research goal"
- "帮我理一下研究思路"
- "research idea for X but not sure where to start"
- "what should I study about this stock"

……或任何仍模糊的"research / 研究 / 分析"意图。

## 做什么

1. **与你对话** 澄清目标 -- 哪个实体、什么问题、什么时间范围、怎样算"好"。
2. 让你**引用一个或多个著名投资方法/大师** 来锚定计划（价值、动量、GARP 等）。
3. **写一份研究计划 Markdown** 到 `daas-doc/research/<plan-slug>.md`。
4. **提议移交** 给 `fd-daas-research` 真正构建。

## 不做什么

它只产出**计划**。不构建指标、表、看板或研究包，也不写**任何 `daas.db` 状态**。那是 `fd-daas-research` 的事。

## 示例

> 我想研究一只中国新能源股但不确定从哪开始。

技能会问澄清问题（哪只股票、什么角度 -- 估值？动量？竞争地位？），让你锚定一个方法，然后写 `daas-doc/research/<slug>.md` 并提议移交给 `fd-daas-research`。

## 路由

- 澄清阶段用**本**技能。
- 目标明确、要指标 + 看板 + 持久化研究包时用 `fd-daas-research`。
- **不要**用 `fd-daas-research` 做 brainstorm -- 它会跳过澄清对话。

## 产物

```text
daas-doc/research/<plan-slug>.md
```

路径规则见 [daas-doc 约定](../contributor/schema.md)。
