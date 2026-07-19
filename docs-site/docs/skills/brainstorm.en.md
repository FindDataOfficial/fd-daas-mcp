# fd-daas-brainstorm

**Clarify a research goal before building anything.** Use this when you know
you want to research something but haven't pinned down what, exactly.

## When it triggers

Phrases like:

- "我想研究一只股票但还没想清楚"
- "help me brainstorm a research goal"
- "帮我理一下研究思路"
- "research idea for X but not sure where to start"
- "what should I study about this stock"

...or any "research / 研究 / 分析" intent that is still fuzzy.

## What it does

1. **Chats with you** to clarify the goal - what entity, what question, what
   timeframe, what "good" looks like.
2. Lets you **reference one or more famous investment methods/masters** to
   anchor the plan (value, momentum, GARP, etc.).
3. **Writes a research-plan markdown** to `daas-doc/research/<plan-slug>.md`.
4. **Offers to hand off** to `fd-daas-research` to actually build it.

## What it does NOT do

It produces **only the plan**. It does not build indicators, tables,
dashboards, or a research bundle, and it writes **no `daas.db` state**. That is
`fd-daas-research`'s job.

## Example

> I want to research a Chinese EV stock but I'm not sure where to start.

The skill will ask clarifying questions (which stock, what angle - valuation?
momentum? competitive position?), let you anchor on a method, then write
`daas-doc/research/<slug>.md` and offer to hand off to `fd-daas-research`.

## Routing

- Use **this** skill for the *clarifying* stage.
- Use `fd-daas-research` once the goal is concrete and you want indicators + a
  dashboard + a persisted bundle.
- Do **not** use `fd-daas-research` for brainstorming - it will skip the
  clarifying dialogue.

## Output

```text
daas-doc/research/<plan-slug>.md
```

See the [daas-doc conventions](../contributor/schema.md) for path rules.
