describe('Process Rules & Indicators', () => {
  it('loads the process rules list (empty state ok)', () => {
    cy.visit('/process/rules');
    cy.get('h1', { timeout: 30000 }).should('contain', 'Process Rules');
    cy.contains('a', 'New rule').should('exist');
    // Page renders without throwing whether the table is empty or seeded.
    cy.get('table').should('exist');
  });

  it('loads the process indicators list (empty state ok)', () => {
    cy.visit('/process/indicators');
    cy.get('h1', { timeout: 30000 }).should('contain', 'Process Indicators');
    cy.contains('a', 'New indicator').should('exist');
    cy.get('table').should('exist');
  });

  it('loads the new-rule form', () => {
    cy.visit('/process/rules/new');
    cy.get('h1', { timeout: 30000 }).should('contain', 'New rule');
    cy.contains('Back to rules').should('exist');
  });

  it('loads the new-indicator form', () => {
    cy.visit('/process/indicators/new');
    cy.get('h1', { timeout: 30000 }).should('contain', 'New indicator');
    cy.contains('Back to indicators').should('exist');
  });

  it('nav: reaches process rules from another page', () => {
    cy.visit('/databases');
    cy.contains('nav a', 'Process').click();
    cy.url().should('include', '/process/rules');
    cy.get('h1', { timeout: 30000 }).should('contain', 'Process Rules');
  });
});
