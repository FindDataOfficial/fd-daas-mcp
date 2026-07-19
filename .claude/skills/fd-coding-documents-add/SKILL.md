---
name: fd-coding-documents-add
description: Add a single new page or section to an existing MkDocs Material docs-site (docs-site/). Place the markdown file under the correct role directory (docs/user/, docs/contributor/, docs/examples/, docs/skills/, docs/mcp/, docs/concepts/, or docs/roadmap.md), wire it into mkdocs.yml nav with the right frontmatter, then run mkdocs build --strict and roll back on failure. Use this skill whenever the user wants to add a page, section, or doc to an existing documentation site - phrases like "add a page to the docs", "add a contributor guide section", "document X in the docs site", "给文档站加一页", "文档里加一篇". This skill wraps fd-coding-skill-creator for the skill-authoring loop and injects the docs-site conventions (placement, nav wiring, frontmatter, live-surface check, no-secrets, strict-build). Do NOT use this to scaffold a brand-new docs-site - use fd-coding-documents-builder for that. If no docs-site/mkdocs.yml exists, this skill refuses and points the user to fd-coding-documents-builder.
---

# fd-coding-documents-add

A docs-site wrapper around `fd-coding-skill-creator` for the *add-one-page*
operation. The skill-creator handles the generic craft; this skill layers the
**docs-site conventions** so a new page lands in the right place, gets wired
into `nav`, passes `mkdocs build --strict`, and references only live surfaces.

## The docs-site domain knowledge

Read **`../fd-coding-documents-builder/references/docs-site-conventions.md`**
(the canonical guardrail, bundled with the builder skill) before adding a page.
Key rules inlined here:

- **Role placement** (§2): user-facing -> `docs/user/` or `docs/examples/`;
  contributor-only -> `docs/contributor/`; skills -> `docs/skills/`; MCP ->
  `docs/mcp/`; concepts -> `docs/concepts/`; roadmap -> `docs/roadmap.md`.
- **Frontmatter** (§3): single H1 matching the nav label; relative internal
  links; every `nav` entry points to an existing file.
- **Live-surface check** (§4): reference only live skills/MCP groups/CLI
  commands/`daas.db` tables; no removed surfaces.
- **No secrets** (§5): placeholders like `<YOUR_API_KEY>`, never real `.env`
  values.
- **Strict build** (§6): `uv run mkdocs build --strict` is the gate.

## Workflow

### Add one page to an existing docs-site

1. **Require an existing site** - if `docs-site/mkdocs.yml` does not exist,
   **stop** and tell the user to run `fd-coding-documents-builder` first. Do not
   create a site here.
2. **Capture intent** - what the page is about, which role/section it belongs to
   (user / contributor / examples / skills / mcp / concepts / roadmap), and the
   nav label.
3. **Delegate the craft to `fd-coding-skill-creator`** for any iterative
   refinement of this skill itself; the page is produced by the steps below.
4. **Write the page** (both languages if the site is bilingual):
   - If `docs-site/mkdocs.yml` declares the `i18n` plugin, create **both**
     `<name>.zh.md` and `<name>.en.md` side by side (conventions §1a). If only
     one language is available at write time, write that one - the site falls
     back to the default locale for missing translations, but the language
     selector will surface the gap.
   - Place under the role directory matching its section (§2).
   - Start with a single H1 matching the nav label (§3).
   - Use relative internal links only; verify every link target exists.
   - Apply the live-surface check (§4) and no-secrets rule (§5).
5. **Wire nav** - add **one** entry under the matching top-level section in
   `docs-site/mkdocs.yml` `nav`, using the **untranslated base path**
   (`user/mypage.md`, not `user/mypage.zh.md`); the i18n plugin resolves the
   per-locale file. Add a `nav_translations:` entry on the `zh` locale for the
   Chinese label.
6. **Verify + rollback** - run `uv run mkdocs build --strict` from `docs-site/`:
   - If it passes, hand back.
   - If it fails (broken link, missing target, strict warning), **roll back**:
     remove the nav entry and (unless the user wants to keep the file for
     editing) remove the page, then report the failure and the exact `mkdocs`
   warning.

### Bulk adds

This skill adds **one** page per run by design. For bulk content generation,
call it repeatedly or author the pages directly - bulk generation is out of
scope (the builder scaffold + manual authoring cover that).

## Guardrails

- **Compose, don't fork.** Delegate skill-authoring mechanics to
  `fd-coding-skill-creator`; this skill only adds placement/nav/strict-build
  guardrails.
- **Require an existing site.** Never scaffold a new `docs-site/` here - that is
  `fd-coding-documents-builder`'s job.
- **Strict build is the gate.** A page that breaks `mkdocs build --strict` is
  rolled back, not left half-wired.
- **No secrets, no removed surfaces.** Placeholders only; live surfaces only.

## Reference files

- `../fd-coding-documents-builder/references/docs-site-conventions.md` - the
  canonical docs-site guardrail (placement, frontmatter, live-surface,
  no-secrets, strict-build, deploy).
- `fd-coding-documents-builder` (sibling skill) - scaffolds the site this skill
  extends.
- `fd-coding-skill-creator` - the generic skill-creation loop.
