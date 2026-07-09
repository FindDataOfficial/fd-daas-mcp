describe('Specialist Agents', () => {
  it('loads the agents list with table and New agent link', () => {
    cy.visit('/agents');
    cy.get('h1', { timeout: 30000 }).should('contain', 'Specialist Agents');
    cy.contains('a', 'New agent').should('exist');
    // Table with expected headers renders (seeded: 11 agents).
    cy.get('table').should('exist');
    cy.contains('th', 'Upstream').should('exist');
    cy.contains('th', 'Enabled').should('exist');
  });

  it('loads the new-agent form', () => {
    cy.visit('/agents/new');
    cy.get('h1', { timeout: 30000 }).should('contain', 'New specialist agent');
    cy.contains('Back to agents').should('exist');
  });

  it('loads the agent detail page for a seeded agent', () => {
    cy.visit('/agents/akshare-agent');
    cy.get('h1', { timeout: 30000 }).should('contain', 'akshare-agent');
    // Detail fields render.
    cy.contains('Upstream').should('exist');
    cy.contains('Role').should('exist');
    cy.contains('Goal').should('exist');
  });

  it('loads the agent edit form', () => {
    cy.visit('/agents/akshare-agent/edit');
    cy.get('h1', { timeout: 30000 }).should('contain', 'Edit agent');
    // Edit page links back to the agent detail (singular "Back to agent").
    cy.contains('Back to agent').should('exist');
  });
});
