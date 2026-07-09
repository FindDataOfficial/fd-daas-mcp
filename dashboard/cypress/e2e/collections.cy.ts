describe('Collections Workspace', () => {
  it('loads the collections home with picker', () => {
    cy.visit('/collections');
    // CollectionSwitcher + heading render; either a list of collections or
    // the empty-state copy is fine — assert the page shell renders.
    cy.contains('Datasource Collections', { timeout: 30000 }).should('exist');
  });

  it('loads the collections manage page', () => {
    cy.visit('/collections/manage');
    // CollectionManager renders its header + create button.
    cy.contains('Datasource Collections', { timeout: 30000 }).should('exist');
    cy.contains('button', 'New collection').should('exist');
  });

  it('loads the three-pane workspace for a seeded collection', () => {
    // The repo ships a `core` collection (seeded by daas-mcp).
    cy.visit('/collections/core');
    // Catalog pane renders its search input.
    cy.get('input[placeholder*="Search datasources"]', { timeout: 30000 }).should('exist');
    // Chat pane renders its label.
    cy.contains('Chat').should('exist');
  });

  it('nav: reaches collections from another page', () => {
    cy.visit('/cron');
    cy.contains('nav a', 'Collections').click();
    cy.url().should('include', '/collections');
    cy.contains('Datasource Collections', { timeout: 30000 }).should('exist');
  });
});
