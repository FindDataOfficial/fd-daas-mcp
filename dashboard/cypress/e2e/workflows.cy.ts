describe('Workflows', () => {
  it('loads the workflows list with stats and table', () => {
    cy.visit('/workflows');
    cy.get('h1', { timeout: 30000 }).should('contain', 'Workflows');
    // Stats labels render.
    cy.contains('Total Runs').should('exist');
    cy.contains('Active Runs').should('exist');
    // Workflows table renders (seeded or empty).
    cy.get('table').should('exist');
  });

  it('loads the workflow detail page for a seeded workflow', () => {
    // The repo ships the `pingan-bank-business-dev` workflow (seeded).
    cy.visit('/workflows/pingan-bank-business-dev');
    cy.get('h1', { timeout: 30000 }).should('contain', 'pingan-bank-business-dev');
    // Steps + Recent Runs sections render.
    cy.contains('Steps').should('exist');
    cy.contains('Recent Runs').should('exist');
  });

  it('nav: reaches workflows from databases', () => {
    cy.visit('/databases');
    cy.contains('nav a', 'Workflows').click();
    cy.url().should('include', '/workflows');
    cy.get('h1', { timeout: 30000 }).should('contain', 'Workflows');
  });
});
