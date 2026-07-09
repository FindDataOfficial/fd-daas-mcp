describe('Scores', () => {
  it('loads the scores page with both sections', () => {
    cy.visit('/scores');
    cy.get('h1', { timeout: 30000 }).should('contain', 'Scores');
    // Default scores section + table.
    cy.contains('h2', 'Default scores').should('exist');
    cy.contains('th', 'Default score').should('exist');
    // Collection scores section.
    cy.contains('h2', 'Collection scores').should('exist');
  });

  it('renders the collection picker', () => {
    cy.visit('/scores');
    cy.contains('Collection:').should('exist');
    cy.get('select').should('exist');
  });

  it('nav: reaches scores from another page', () => {
    cy.visit('/cron');
    cy.contains('nav a', 'Scores').click();
    cy.url().should('include', '/scores');
    cy.get('h1', { timeout: 30000 }).should('contain', 'Scores');
  });
});
