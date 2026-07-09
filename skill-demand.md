# Skill Demand

I want to use the **fd-skills-creator** skill to create skills that help me use MCP better. Below are the skills and their demands.

## `fd-daas-fetch-data`

End-to-end data-fetching workflow:

1. **Check the entities** — look up entities in the daas registry.
2. **Find the related datasource** — resolve which datasource covers each entity.
3. **Create indicators** — define the indicators to compute over the source data manually.

## `fd-daas-indicators-creator`

End-to-end create-indicators workflow. If steps 1–3 have already been run, just run steps 4–6.

1. Use the `fd-daas-fetch-data` skill.
2. **Create the table** — set up the storage table (`scraw_<slug>`).
3. **Save the data** — fetch and persist the data into the table.
4. **Create a cron** — schedule a cron job to refresh the data.

## `fd-daas-dashboard-creator`

1. First, create the dashboard structure, show it as text, and ask for permission.
2. After the user accepts, create the dashboard and ask permission to open it in the default browser.
3. If the user wants changes, make them; if the user accepts, save the dashboard URL through the MCP.

## `fd-daas-research`

1. Analyze the demand and create an analysis plan plus the indicators demand.
2. Use the `fd-daas-indicators-creator` skill.
3. Use the `fd-daas-dashboard-creator` skill.

## `fd-daas-workflow-creator`

Summarize the flow and create a workflow through the MCP.





 create a  skill fd-daas-complex-analysis
 refer the skill fd-daas-research
1.make the entitis and indicators and build a file in this research task analysis file
2. ask people to read and confirm
3. use fd-daas-entities-collection-creator to create colection
4. create the rules to .use fd-daas-indicators-collection-creator to create the collection
5. ask people whether to create dashboard and 