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
