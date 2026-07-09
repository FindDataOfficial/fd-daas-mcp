/**
 * TypeScript mirrors of mcp/models/models.py tables.
 * Schema changes MUST be made in mcp/models/models.py first, then reflected here.
 */

// Schema types mirroring the actual SQLite tables

export interface DatabaseInfo {
  name: string;
  tables: string[];
  readonly: boolean;
}

export interface TableData {
  columns: string[];
  rows: Record<string, unknown>[];
  page: number;
  totalPages: number;
  totalRows: number;
}

// daas.db / leader_mcp.db
export interface FunctionRow {
  id: number;
  harness?: string;
  source_id?: number;
  name?: string;
  command?: string;
  label?: string;
  category: string;
  source?: string;
  description: string;
  parameters: string; // JSON
  output_type?: string;
}

export interface FunctionColumnRow {
  id: number;
  function_id: number;
  name?: string;
  column_name?: string;
  label?: string;
  type?: string;
  column_type?: string;
  description?: string;
  column_description?: string;
  nullable?: number;
}

// daas.db / cron.db
export interface SourceRow {
  id: number;
  name: string;
  label: string;
  description: string;
  url: string;
  enabled: number;
  config: string; // JSON
}

export interface ScheduleRow {
  id: string;
  name: string;
  cron_expr: string;
  task_name: string;
  agent?: string;
  prompt?: string;
  enabled: number;
  timezone: string;
  created_at: string;
  updated_at: string;
  last_run_at?: string;
  next_run_at?: string;
}

export interface ExecutionRow {
  id: string;
  schedule_id: string;
  started_at: string;
  finished_at?: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  output?: string;
}

export interface TaskRow {
  id: string;
  name: string;
  description: string;
  command: string;
  timeout: number;
  created_at: string;
  updated_at: string;
}

export interface ObservationRow {
  id: number;
  source: string;
  function_name: string;
  indicator: string;
  date: string;
  value: string;
  metadata: string; // JSON
}

export interface ScrawConfigRow {
  id: number;
  url: string;
  name: string;
  columns_json: string;
  created_at: string;
  updated_at: string;
}

// dashboard.db
export interface DatasourceRow {
  id: number;
  name: string;
  db_type: string;
  connection_string: string;
  description: string;
  is_readonly: number;
  created_at: string;
  updated_at: string;
}

export interface DatasourceColumnRow {
  id: number;
  datasource_id: number;
  table_name: string;
  column_name: string;
  column_type: string;
  is_primary_key: number;
  is_nullable: number;
  description: string;
  source_field: string;
  unit: string;
  semantic_type: string;
}

// daas.db data_snapshots
export interface DataSnapshotRow {
  id: number;
  function_id: number;
  params_json: string;
  fetched_at: string;
  status: string;
  data_json: string;
  row_count: number;
}

// daas.db — categories, forms, sections, collections (daas-mcp management)
export interface CategoryRow {
  id: number;
  name: string;
  label: string | null;
  parent_id: number | null;
  sort_order: number | null;
}

export interface DatasourceFormRow {
  id: number;
  source_id: number;
  form_type: string;
  label: string | null;
}

export interface DatasourceSectionRow {
  id: number;
  form_id: number;
  section_name: string;
  instruction: string | null;
  sort_order: number | null;
}

export interface DatasourceCollectionRow {
  id: number;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface DatasourceCollectionItemRow {
  id: number;
  collection_id: number;
  source_id: number;
  section_id: number | null;
  sort_order: number;
  created_at: string;
}

/**
 * Derived shapes used by the collections workspace. These don't map 1:1 to
 * tables — they're the result of loadCatalog() / loadCollection() joins.
 */
export interface CatalogSection {
  id: number;
  section_name: string;
  instruction: string | null;
}

export interface CatalogForm {
  id: number;
  form_type: string;
  label: string | null;
  sections: CatalogSection[];
}

export interface CatalogSource {
  id: number;
  name: string;
  label: string;
  description: string | null;
  category_id: number | null;
  category_name: string | null;
  forms: CatalogForm[];
}

export interface CatalogGroup {
  category_id: number | null; // null = uncategorized
  category_name: string;       // "(uncategorized)" when null
  sources: CatalogSource[];
}

export interface CollectionItem {
  item_id: number;
  source_id: number;
  source_name: string;
  source_label: string;
  section_id: number | null;
  section_name: string | null;
  form_type: string | null;
  instruction: string | null;
  sort_order: number;
  item_score: number | null;
  source_default_score: number | null;
  score: number | null; // resolved effective score (item override if set, else source default)
}

export interface CollectionDetail {
  id: number;
  name: string;
  description: string | null;
  items: CollectionItem[];
}

// ─── Scores ───────────────────────────────────────────────────────
// A datasource's default score (row in `sources`) — managed on the /scores page.
export interface SourceScoreRow {
  id: number;
  name: string;
  label: string;
  description: string | null;
  score: number | null; // default score; null = unset
}

// One item in a collection, with its per-collection score override + the
// datasource's default score for reference + the resolved effective score.
export interface CollectionScoreItem {
  item_id: number;
  source_id: number;
  source_name: string;
  source_label: string;
  section_id: number | null;
  section_name: string | null;
  sort_order: number;
  item_score: number | null; // per-collection override; null = inherit default
  source_default_score: number | null; // the datasource's default score
  score: number | null; // resolved: item_score if set, else source_default_score
}

// ─── Entity collections ───────────────────────────────────────────
// Named groups of entities (stocks + countries) — watchlists / portfolios.
// Mirrors `entity_collections` / `entity_collection_items` /
// `entity_collection_changes` in mcp/models/models.py.

export interface EntityCollectionRow {
  id: number;
  name: string;
  description: string | null;
  rule: Record<string, any> | null; // membership rule; null = manual collection
  item_count: number;
  created_at: string | null;
  updated_at: string | null;
}

export interface EntityCollectionMemberRow {
  item_id: number;
  entity_id: number;
  sort_order: number;
  added_at: string | null;
  added_reason: string | null;
  entity_type: string | null;
  code: string | null;
  name: string | null;
  ticker: string | null;
  exchange: string | null;
  country_code: string | null;
}

export interface EntityCollectionDetail {
  id: number;
  name: string;
  description: string | null;
  rule: Record<string, any> | null;
  created_at: string | null;
  updated_at: string | null;
  members: EntityCollectionMemberRow[];
}

// One row in the add-in / remove-out audit log (`entity_collection_changes`).
export interface EntityCollectionChangeRow {
  id: number;
  collection_id: number;
  collection_name: string | null;
  entity_id: number | null;
  entity_code: string | null;
  entity_name: string | null;
  action: 'add_in' | 'remove_out';
  source: 'manual' | 'cron';
  reason: string | null;
  changed_at: string | null;
}

// ── Indicator scores (indicator_rules.score + 3-level resolution) ──

export interface IndicatorScoreRow {
  id: number;
  name: string;
  datasource: string | null;
  function_name: string | null;
  op: string | null;
  value_column: string | null;
  indicator_name: string | null;
  enabled: boolean;
  score: number | null; // raw indicator_rules.score; null = inherit datasource default
  datasource_default_score: number | null; // sources.score for the indicator's datasource
  effective_default_score: number | null; // COALESCE(indicator.score, sources.score)
  latest_value: number | string | null;
  latest_date: string | null;
}

// ── Indicator collections ──

export interface IndicatorCollectionSummary {
  id: number;
  name: string;
  description: string | null;
  item_count: number;
  created_at: string | null;
  updated_at: string | null;
}

export interface IndicatorCollectionScoreItem {
  item_id: number;
  indicator_id: number;
  indicator_name: string;
  sort_order: number;
  item_score: number | null; // raw per-collection override; null = inherit
  indicator_default_score: number | null; // indicator_rules.score
  source_default_score: number | null; // sources.score for the datasource
  score: number | null; // resolved effective: COALESCE(item, indicator, datasource)
}

export interface IndicatorCollectionDetail {
  id: number;
  name: string;
  description: string | null;
  created_at: string | null;
  updated_at: string | null;
  items: IndicatorCollectionScoreItem[];
}

// One row in the add-in / remove-out audit log (`indicator_collection_changes`).
export interface IndicatorCollectionChangeRow {
  id: number;
  collection_id: number;
  collection_name: string | null;
  indicator_name: string;
  action: 'add_in' | 'remove_out';
  source: 'manual' | 'cron';
  reason: string | null;
  changed_at: string | null;
}
