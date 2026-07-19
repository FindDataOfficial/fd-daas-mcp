---
name: fd-coding-documents-builder
description: Scaffold a new MkDocs Material documentation site (a docs-site/) for a project - create the directory structure, mkdocs.yml with role-based navigation (User Guide / Contributor Guide / Examples / Skills / MCP Tools / Concepts / Roadmap), the GitHub Pages workflow, a site README, and the docs-site-conventions guardrail. Use this skill whenever the user wants to build, scaffold, or generate a documentation site / docs project - phrases like "build a docs site", "scaffold the documentation project", "create a docs site like DAAS", "给这个项目建一个文档站点", "搭一个 mkdocs 文档站". This skill wraps fd-coding-skill-creator for the skill-authoring loop and injects the docs-site conventions (role-based nav, frontmatter, live-surface check, no-secrets, strict-build, deploy). Do NOT use this to add a single page to an existing site - use fd-coding-documents-add for that. Do NOT use fd-daas-skill-creator (that is for fd-daas-* data skills); this skill is for documentation projects.
---

# fd-coding-documents-builder

A docs-site wrapper around `fd-coding-skill-creator`. The skill-creator handles
the generic craft (draft -> evals -> review -> iterate -> description
optimization); this skill layers the **docs-site conventions** on top so a
scaffolded site is correct by default: role-based nav, frontmatter rules,
live-surface fact-checking, no embedded secrets, a passing `mkdocs build
--strict`, and a GitHub Pages deploy path.

## The docs-site domain knowledge

Before scaffolding, read **`references/docs-site-conventions.md`** (in this
skill). It is the single source of truth for: location & generator (MkDocs
Material at `docs-site/`), the role-based nav sections, frontmatter & page
rules, the live-surface check (no removed surfaces), the no-secrets rule, the
strict-build gate, deploy (GitHub Pages + WiFi/tunnel), and the relationship to
`daas-doc/` and the repo `README.md`. Inject these as guardrails; do not copy
them verbatim into the generated site - copy `references/docs-site-conventions.md`
into the generated `docs-site/references/` and link to it.

## Workflow

### Scaffold a new docs-site

1. **Capture intent** - target directory (default repo-root `docs-site/`), site
   name/url, repo URL, and which nav sections the project needs (the default
   seven: User Guide, Examples, Concepts, Skills, MCP Tools, Contributor Guide,
   Roadmap). Confirm whether to add the `mkdocs-material` dev dependency and the
   GitHub Pages workflow.
2. **Delegate the craft to `fd-coding-skill-creator`** for any iterative
   refinement of this skill itself; the scaffold is produced by the steps below.
3. **Produce the scaffold** (this is what this skill adds):
   - `docs-site/mkdocs.yml` - Material theme, search, nav with the role sections,
     and the `i18n` plugin (zh default + English, suffix convention).
   - `docs-site/docs/` skeleton - one index page per nav section (H1 + one-line
     placeholder), so `mkdocs build --strict` passes immediately.
   - `docs-site/docs/index.md` - site home.
   - `docs-site/README.md` - build/serve/deploy commands.
   - `docs-site/references/docs-site-conventions.md` - copy of this skill's
     guardrail (the generated site's source of truth for adding pages).
   - `.github/workflows/docs.yml` - GitHub Pages build + deploy.
   - `.gitignore` entry for `docs-site/site/`.
   - Add `mkdocs-material` (pinned, `==9.5.*`) to the `dev` dependency group in
     `pyproject.toml` when not already present.
4. **Apply the guardrails**:
   - The generated `mkdocs.yml` `nav` matches the role sections in
     `docs-site-conventions.md` §2.
   - Generated content references **only live surfaces** - no removed CLIs,
     dropped MCP groups, stale `mcp__*` tools, or old DB URLs (§4). For a DAAS
     site, reuse the removed-surfaces list from
     `fd-daas-skill-creator/references/daas-concepts.md` §8.
   - **No secrets** - examples use placeholders like `<YOUR_API_KEY>` (§5).
5. **Verify** - run `uv run mkdocs build --strict` from `docs-site/` and confirm
   zero warnings before handing back.

### Idempotency / non-destructive

The skill **refuses to overwrite an existing `docs-site/mkdocs.yml`**. If one
exists, report the conflict and require an explicit confirmation (or `--force`)
before replacing, and **back up** the existing file first
(`mkdocs.yml.bak-<timestamp>`).

## Guardrails

- **Compose, don't fork.** Delegate skill-authoring mechanics to
  `fd-coding-skill-creator`; this skill only adds docs-site guardrails.
- **Copy, don't inline.** Copy `references/docs-site-conventions.md` into the
  generated `docs-site/references/`; the generated site links to it.
- **No removed surfaces.** A scaffolded site that references a deleted CLI or
  dropped MCP group is a `stale-ref` defect - catch it before hand-off.
- **Strict build is the gate.** Never hand back a site whose
  `uv run mkdocs build --strict` fails.
- **No secrets.** Use placeholders; never embed `.env` values.

## Reference files

- `references/docs-site-conventions.md` - the docs-site domain knowledge
  (location, nav, frontmatter, live-surface check, no-secrets, strict-build,
  deploy, relationship to `daas-doc/` + `README.md`).
- `fd-coding-documents-add` (sibling skill) - adds pages to a site this skill
  scaffolds.
- `fd-coding-skill-creator` - the generic skill-creation loop.
