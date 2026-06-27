describe('MCP Dashboard', () => {
  it('US1: redirects / to /databases', () => {
    cy.visit('/');
    cy.url().should('include', '/databases');
  });

  it('US1: shows database list with known databases', () => {
    cy.visit('/databases');
    cy.get('h1', { timeout: 30000 }).should('contain', 'Databases');
    cy.contains('daas.db', { timeout: 30000 }).should('exist');
    cy.contains('leader_mcp.db').should('exist');
  });

  it('US1: navigates to table browser and shows data', () => {
    cy.visit('/databases');
    cy.get('a[href="/databases/daas/sources"]').first().click();
    cy.url().should('include', '/databases/daas/sources');
    cy.get('table', { timeout: 30000 }).should('exist');
  });

  it('US2: cron page loads with stats', () => {
    cy.visit('/cron');
    cy.get('h1', { timeout: 30000 }).should('contain', 'Cron Tasks');
    cy.contains('Tasks').should('exist');
    cy.contains('Schedules').should('exist');
  });

  it('US2: cron page shows tasks and schedules tables', () => {
    cy.visit('/cron');
    cy.get('table', { timeout: 30000 }).should('have.length.at.least', 2);
    cy.contains('th', 'Name').should('exist');
    cy.contains('th', 'Status').should('exist');
  });

  it('US2: cron edit task page loads', () => {
    cy.visit('/cron');
    // Click first Edit link in the tasks table
    cy.get('table').first().contains('Edit').click();
    cy.url().should('include', '/cron/tasks/');
    cy.get('h1, .text-2xl, .text-gray-900').should('contain', 'Edit Task');
    // Form fields present
    cy.get('label').contains('Command').should('exist');
    cy.get('label').contains('Description').should('exist');
    cy.get('label').contains('Timeout').should('exist');
    // Save and Delete buttons
    cy.contains('button', 'Save Changes').should('exist');
    cy.contains('button', 'Delete Task').should('exist');
    // Linked schedules section
    cy.contains('Linked Schedules').should('exist');
  });

  it('US2: cron edit task — save updates the task', () => {
    cy.visit('/cron');
    cy.get('table').first().contains('Edit').click();

    // Clear and type new description
    cy.get('input').eq(2).clear().type('E2E test updated description');
    cy.contains('button', 'Save Changes').click();
    cy.contains('Task updated.', { timeout: 10000 }).should('exist');
  });

  it('US2: cron schedule toggle and delete buttons exist', () => {
    cy.visit('/cron');
    // Schedule actions column should have Pause/Resume and Delete buttons
    cy.contains('th', 'Actions').should('exist');
    // Verify toggle button exists
    cy.get('button').contains(/Pause|Resume/).should('exist');
  });

  it('US3: datasources page loads', () => {
    cy.visit('/datasources');
    cy.get('h1', { timeout: 30000 }).should('contain', 'Datasources');
    cy.get('table').should('exist');
  });

  it('US3: datasource columns page works', () => {
    cy.visit('/datasources/1/columns');
    cy.contains('Datasources', { timeout: 30000 }).should('exist');
    cy.contains('columns').should('exist');
  });

  it('sidebar navigation works', () => {
    cy.visit('/databases');
    cy.contains('nav a', 'Cron Tasks').click();
    cy.url().should('include', '/cron');
    cy.contains('nav a', 'Datasources').click();
    cy.url().should('include', '/datasources');
    cy.contains('nav a', 'Databases').click();
    cy.url().should('include', '/databases');
  });

  it('chat page loads with input and empty state', () => {
    cy.visit('/chat');
    cy.contains('h1', 'AI Chat', { timeout: 30000 }).should('exist');
    cy.contains('Start a conversation').should('exist');
    cy.get('textarea').should('exist');
    cy.contains('button', 'Send').should('exist');
  });

  it('chat page has New Chat button', () => {
    cy.visit('/chat');
    cy.contains('button', 'New Chat').should('exist');
  });

  it('chat page accessible from nav', () => {
    cy.visit('/cron');
    cy.contains('nav a', 'Chat').click();
    cy.url().should('include', '/chat');
  });
});
