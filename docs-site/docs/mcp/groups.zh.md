# 工具组

`fd-daas-mcp` 服务器把工具注册为 `<group>_<tool>`。下面是每组选列 -- 运行中的服务器是事实来源（数量会随时间增长，所以本站不引用固定总数）。

## daas_*

目录 + 数据层。

- `daas_search_entities` / `daas_list_entities` / `daas_get_entity`
- `daas_get_entity_coverage` / `daas_link_entity_datasource` / `daas_unlink_entity_datasource`
- `daas_list_sources` / `daas_search_functions` / `daas_get_function_detail` / `daas_fetch_data`
- `daas_create_datasource` / `daas_update_datasource` / `daas_delete_datasource`
- `daas_create_indicator` / `daas_list_indicators` / `daas_run_indicator` / `daas_calculate_indicator`
- `daas_list_indicator_ops`
- `daas_create_entity_collection` / `daas_add_entity_to_collection` / `daas_sync_entity_collection`
- `daas_create_indicator_collection` / `daas_add_indicator_to_collection` / `daas_sync_indicator_collection`
- `daas_create_rule` / `daas_run_rule` / `daas_test_rule` / `daas_sync_*_collection`
- `daas_extract_file` / `daas_extract_text` / `daas_extract_image`（LLM 抽取）
- `daas_add_pipeline_item` / `daas_enable_pipeline_item` / `daas_disable_pipeline_item`

## research_*

- `research_create` / `research_get` / `research_list` / `research_update` / `research_delete`
- `research_generate_report` / `research_refresh`
- `research_add_component` / `research_remove_component`

## dashboard_*

- `dashboard_register` / `dashboard_list` / `dashboard_get` / `dashboard_update` / `dashboard_delete`
- `dashboard_search` / `dashboard_query_table`
- `dashboard_list_databases` / `dashboard_list_datasources` / `dashboard_get_stats` / `dashboard_get_executions`

## cron_*

- `cron_create_task` / `cron_update_task` / `cron_delete_task` / `cron_list_db_tasks`
- `cron_create_schedule` / `cron_list_schedules` / `cron_get_schedule` / `cron_pause_schedule` / `cron_resume_schedule`
- `cron_run_now` / `cron_list_executions`

## alerts_*

- `alerts_create_alert_rule` / `alerts_update_alert_rule` / `alerts_delete_alert_rule` / `alerts_list_alert_rules`
- `alerts_get_series_latest` / `alerts_list_series`
- `alerts_run_alert_rule` / `alerts_list_events`
- `alerts_list_channels`

## gateway_*

- `gateway_list_data_mcps` / `gateway_list_data_mcp_tools` / `gateway_call_data_mcp`
- `gateway_add_data_mcp` / `gateway_remove_data_mcp` / `gateway_get_data_mcp` / `gateway_health`

## workflow_*

- `workflow_register` / `workflow_get` / `workflow_list` / `workflow_update` / `workflow_delete`
- `workflow_run` / `workflow_inspect` / `workflow_resume`

## pdf_*

可选 -- 取决于 `sqlite-vec`。

- `pdf_ingest_document` / `pdf_ingest_text` / `pdf_list_documents` / `pdf_get_document` / `pdf_delete_document`
- `pdf_search_documents`

## composite_*

- `composite_create` / `composite_list`
- `composite_add_upstream` / `composite_add_tool` / `composite_add_chained_tool`
- `composite_list_upstreams` / `composite_list_tools` / `composite_list_chained_tools`
- `composite_remove_upstream` / `composite_remove_tool` / `composite_remove_chained_tool`

## 发现实时表面

查看每个工具当前描述的最快方式是问运行中的服务器（或浏览 `fd-daas-mcp` CLI 帮助）。上面的列表是可导航的地图，不是穷尽契约 -- 实时注册表才是权威。
