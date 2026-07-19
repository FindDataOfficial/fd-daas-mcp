---
name: fd-daas-brainstorm
description: Brainstorm and clarify a research goal before building indicators and a dashboard. Use this skill whenever the user wants to think through what to research, frame a goal, pick an investment method or master to anchor it, or turn a vague idea into a concrete research plan - phrases like "我想研究一只股票但还没想清楚", "help me brainstorm a research goal", "帮我理一下研究思路", "research idea for X but not sure where to start", "what should I study about this stock", or any "research/研究/分析" intent that is still fuzzy. This skill chats with the user to clarify the goal, lets them reference one or more famous investment methods/masters, and writes a research-plan markdown to daas-doc/research/. It does NOT build indicators, tables, dashboards, or a research bundle - it produces only the plan, then offers to hand off to fd-daas-research. Do NOT use fd-daas-research for the clarifying stage - use this skill first.
---

# fd-daas-brainstorm

The upstream "what should I research?" step. Chat with the user until the
research goal is concrete, anchor it in one or more investment methods/masters,
then write a plan markdown that `fd-daas-research` can consume. This skill
produces **only the plan doc** - it does not touch `daas.db` (no `researches`
row, no indicators, no `scraw_*` tables, no dashboards).

## Mental model

1. **Clarify** - ask focused questions until the goal is concrete.
2. **Anchor** - let the user pick one or more methods/masters from
   `references/investment-methods-and-masters.md` to frame the goal.
3. **Plan** - draft the research plan (research name, entity/group, question,
   time horizon, indicators implied by the lens, dashboard shape, referenced
   methods).
4. **Write** - save it to `daas-doc/research/<plan-slug>.md`.
5. **Notify + offer** - emit the run-notification block and ask whether to run
   `fd-daas-research` (do not auto-invoke).

## Step 1 - Clarify the goal

Ask focused questions (one or two at a time, not a form). You need:

- **Entity or group** - a single stock/company/country/index, or a group
  (watchlist, a rule like "SSE banks", an explicit code list).
- **The question** - what does the user want to answer? ("is BYD cheap?",
  "does this momentum hold?", "how do these banks compare on quality?").
- **Time horizon** - days/weeks/months/years; which window for the indicators.
- **Intended output** - a dashboard? a comparison? a signal/alert?

Don't move on until the goal is concrete enough that you could name the
indicators it implies. If the user is vague ("研究一下比亚迪"), ask: "What do you
want to know about it - valuation, momentum, fundamentals comparison, or
something else?"

## Step 2 - Anchor in a method/master

Read `references/investment-methods-and-masters.md`. Offer 1-3 lenses that fit
the goal and let the user pick one (or more). The lens is not decoration - it
decides the indicators and the dashboard shape:

- **Value (Graham/Buffett/Munger)** -> valuation ratios (P/E, P/B, EV/EBITDA,
  dividend yield) + margin-of-safety trigger.
- **Growth / GARP (Fisher/Lynch)** -> revenue/earnings growth %, PEG.
- **Momentum / trend (Livermore/Wyckoff)** -> SMA/EMA crossovers, RSI, relative
  strength, 52-week high.
- **Macro / reflexivity (Soros/Druckenmiller)** -> index breadth, rates/FX,
  correlation, sentiment.
- **Quant / factor (Simons/Markowitz/Dalio)** -> z-score, rolling std, factor
  exposure, volatility/correlation.
- **Quality (Buffett/Munger)** -> ROE/ROIC, margins, debt/equity, free cash flow.

If the user already names a method ("I want a Graham-style value check"), use
it directly. A primary lens + optional secondary is fine.

## Step 3 - Draft the plan

Draft the plan as markdown using this template (fill every section; mark
anything genuinely undecided as "TBD - confirm at research stage"):

```markdown
# Research plan: <plan-slug>

**Research name (for fd-daas-research):** <kebab/snake handle, e.g. byd-value>
**Lens:** <method/master, e.g. Graham value investing; secondary: Munger quality>
**Date:** <YYYY-MM-DD>

## Goal
<1-2 sentences: the question this research answers.>

## Entity / group
<single entity (name + code) OR collection (name + membership rule / code list).>

## Time horizon
<e.g. daily, 5-year daily, monthly; window for indicators.>

## Indicators implied
<Per the lens. e.g. P/E, P/B, EV/EBITDA, dividend yield, margin-of-safety band.
Name the op + params + the source_table/value_column they'd run on, where known.>

## Dashboard shape
<e.g. valuation-ratio history vs. peers; price + SMA overlay + RSI pane;
multi-series macro regime panel.>

## Next
Built by `fd-daas-research` - it will read this plan, build the indicators +
dashboard, and persist the study as a `research` bundle.
```

Show the draft to the user and confirm before writing.

## Step 4 - Write the plan doc

Write the confirmed plan to `daas-doc/research/<plan-slug>.md` (create
`daas-doc/research/` on first use). `<plan-slug>` is the research name (kebab).
This path is what `fd-daas-research` reads to pre-fill its analysis (see the
`fd-daas-research` auto-detect step).

## Step 5 - Notify + offer hand-off

Emit the run-notification block:

```
## Run Complete

**Skill:** fd-daas-brainstorm
**Status:** plan written
**Produced:** daas-doc/research/<plan-slug>.md (research name `<handle>`, lens: <...>)
**Next:** run `fd-daas-research` to build the indicators + dashboard from this plan?
```

Then **ask the user** whether to run `fd-daas-research`. Do NOT auto-invoke it -
the user stays in control of when to spend the build.

## Boundaries

- **No `daas.db` mutation.** This skill writes only `daas-doc/research/<plan>.md`.
  It creates no `researches` row, no `indicator_rules`, no `scraw_*` tables, no
  dashboards. If the user wants those, hand off to `fd-daas-research`.
- **Read-only context is fine** - you may `sqlite3 daas.db "SELECT ... FROM
  entities WHERE ..."` to confirm an entity exists or list a collection, but you
  write nothing.
- **Keep it a dialogue.** Don't dump the full method/master table; offer the
  1-3 lenses that fit and let the user choose.
- **The lens must drive the indicators + dashboard.** A plan where the lens and
  the indicators don't match is a sign to re-clarify.
