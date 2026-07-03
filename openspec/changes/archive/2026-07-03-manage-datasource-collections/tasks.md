## 1. Backend: `update_collection` in daas-mcp

- [x] 1.1 Add `update_collection(self, name, new_name=None, description=None)` to `mcp/daas-mcp/registry_service.py` (locate the collection by `name`; raise `ValueError` if not found; require at least one of `new_name`/`description`; when `new_name` is set and differs from current name, enforce uniqueness; commit with rollback-on-error; return `coll.to_dict()`). Mirror the style of `rename_collection` (lines ~621–643).
- [x] 1.2 Add `update_collection(name, new_name=None, description=None)` tool wrapper to `mcp/daas-mcp/daas_tools.py` (follow `create_collection`/`rename_collection` wrapper pattern at ~314–379).
- [x] 1.3 Add `update` to the `choices` list and a dispatch branch in `mcp/daas-mcp/collection_writer.py` `main()` — call `svc.update_collection(name=args["name"], new_name=args.get("new_name"), description=args.get("description"))`. Update the module docstring's command list.
- [x] 1.4 Smoke-test the writer directly: create a temp collection, then `uv run --directory mcp/daas-mcp python collection_writer.py update --json '{"name":"<test>","description":"x"}'`, then `... rename ...`, then `delete`. Confirm output JSON and that a not-found / no-fields call exits non-zero with `{"error": ...}`.

## 2. API: extend PATCH `/api/collections/[name]`

- [x] 2.1 In `dashboard/src/app/api/collections/[name]/route.ts`, extend `PATCH` to read `body.new_name` (optional) and `body.description` (optional); require at least one; dispatch to `runPythonCli('collection_writer.py', 'update', { name, new_name, description })` (omit `new_name`/`description` keys when absent so the writer sees `args.get(...)` as `None`).
- [x] 2.2 Preserve the existing `{ new_name }`-only contract: a PATCH sending only `{ new_name }` must still succeed (workspace rename control keeps working). Map error strings to status codes: `not found` → 404, `already exists` → 409, `at least one` → 400.
- [x] 2.3 Confirm `POST /api/collections` already passes `description` through (it does — `route.ts` reads `body.description`); no change needed, just verify with a manual `curl`.

## 3. Frontend: management home page

- [x] 3.1 Create `dashboard/src/app/collections/manage/page.tsx` (server component): `export const dynamic = 'force-dynamic'`; call `loadCollections()` from `@/lib/collections`; render a header and pass `collections` to a new client `<CollectionManager>`.
- [x] 3.2 Create `dashboard/src/components/collections/collection-manager.tsx` (client): render a grid of cards (name, description-or-"No description", `item_count`, `updated_at`) with actions **Open** (Link → `/collections/[name]`), **Edit** (opens modal), **Delete** (`confirm()` then `DELETE /api/collections/[name]`, then `router.refresh()`). Add a **+ New collection** button opening the create modal. Render an empty state when `collections.length === 0`.
- [x] 3.3 Create `dashboard/src/components/collections/collection-edit-dialog.tsx` (client): a modal with `name` + `description` fields. Mode `create` → `POST /api/collections { name, description }`; mode `edit` → `PATCH /api/collections/[name]` with the changed field(s) only (`new_name` if name changed, `description` if changed). Show API errors inline; on success close + `router.refresh()`. Reuse the input/button styling from `collection-switcher.tsx`.
- [x] 3.4 Add a **Manage** link to `dashboard/src/components/nav.tsx` pointing at `/collections/manage` (keep the existing "Collections" link as-is).

## 4. Verification

- [x] 4.1 Typecheck/build the dashboard: `cd dashboard && npm run build` (fix any TS errors in the new components). — New/edited files type-check clean (`tsc --noEmit` reports 0 errors in them). The full `next build` fails on 4 **pre-existing** type errors in `src/app/api/chat/route.ts` + `src/app/chat/page.tsx` (AI SDK v5 drift: `maxSteps`, `sendMessage`, `transport`, `UIMessage`), unmodified by this change — out of scope.
- [x] 4.2 Manual smoke (dashboard running): create a collection with a description from `/collections/manage`; edit the description; rename; confirm the card updates; open the workspace from the card; delete with confirmation; confirm the workspace rename control (`/collections/[name]` switcher) still works against the extended PATCH route. — All passed via curl against `next dev` (create-with-desc, update-desc-only, rename-only, both, 400/404/409 errors, card re-render, delete). **Note:** required `DAAS_DATABASE_URL` to be an absolute path — see the issue note below; the dashboard's `.env.local` ships a relative URL that the writer (spawned via `uv run --directory mcp/daas-mcp`) cannot resolve.
- [x] 4.3 Regression: confirm `/collections` (picker) and `/collections/[name]` (workspace) behave as before — no changes to those routes/components. — Confirmed: only the PATCH route body was extended (backward-compatible; `{ new_name }`-only still 200s, verified in smoke step 5); nav gained a link; no workspace/picker code touched.
