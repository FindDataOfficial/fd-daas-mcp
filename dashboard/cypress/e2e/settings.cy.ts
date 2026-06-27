describe('Settings Page', () => {
  it('US1: settings page loads with correct sections', () => {
    cy.visit('/settings');
    cy.get('h1', { timeout: 30000 }).should('contain', 'Settings');

    // Bootstrap section
    cy.contains('Bootstrap Settings').should('exist');
    cy.contains('Restart Required').should('exist');

    // Runtime section
    cy.contains('Runtime Settings').should('exist');
    cy.contains('Live').should('exist');

    // Per-MCP section
    cy.contains('Per-MCP Proxy Overrides').should('exist');
  });

  it('US1: bootstrap section shows expected keys', () => {
    cy.visit('/settings');
    cy.contains('Bootstrap Settings').parent().within(() => {
      cy.contains('DAAS_DATABASE_URL').should('exist');
      cy.contains('DASHBOARD_PORT').should('exist');
    });
  });

  it('US1: runtime section shows expected keys', () => {
    cy.visit('/settings');
    cy.contains('Runtime Settings').parent().within(() => {
      cy.contains('HTTP_PROXY').should('exist');
      cy.contains('HTTPS_PROXY').should('exist');
      cy.contains('NO_PROXY').should('exist');
      cy.contains('CKAN_URL').should('exist');
      cy.contains('LLM_BASE_URL').should('exist');
      cy.contains('LLM_API_KEY').should('exist');
      cy.contains('LLM_MODEL').should('exist');
    });
  });

  it('US1: per-MCP section lists all MCP servers', () => {
    cy.visit('/settings');
    cy.contains('Per-MCP Proxy Overrides').parent().within(() => {
      cy.contains('daas-mcp').should('exist');
      cy.contains('cron-mcp').should('exist');
      cy.contains('leader-mcp').should('exist');
      cy.contains('ckan-mcp').should('exist');
      cy.contains('akshare-mcp').should('exist');
    });
  });

  it('US2: edit runtime setting — opens modal and saves', () => {
    cy.visit('/settings');
    // Click Edit on HTTP_PROXY in runtime section
    cy.contains('Runtime Settings').parent().within(() => {
      cy.contains('tr', 'HTTP_PROXY').contains('Edit').click();
    });
    // Modal appears
    cy.get('[role="dialog"], .fixed').should('exist');
    cy.contains('HTTP_PROXY').should('exist');
    // Type a value
    cy.get('input[type="text"]').eq(0).clear().type('http://test-proxy:8080');
    // Save
    cy.contains('button', 'Save').click();
    // Modal closes
    cy.get('[role="dialog"], .fixed').should('not.exist');
    // Value appears in table
    cy.contains('Runtime Settings').parent().contains('http://test-proxy:8080').should('exist');
  });

  it('US3: edit bootstrap setting — shows restart warning', () => {
    cy.visit('/settings');
    // Click Edit on DASHBOARD_PORT
    cy.contains('Bootstrap Settings').parent().within(() => {
      cy.contains('tr', 'DASHBOARD_PORT').contains('Edit').click();
    });
    // Type a new value
    cy.get('input[type="text"]').eq(0).clear().type('4000');
    cy.contains('button', 'Save').click();
    // Restart warning appears
    cy.contains('Restart required', { timeout: 5000 }).should('exist');
  });

  it('US4: per-MCP proxy — edit and show custom badge', () => {
    cy.visit('/settings');
    // Click HTTP button on daas-mcp row
    cy.contains('Per-MCP Proxy Overrides').parent().within(() => {
      cy.contains('tr', 'daas-mcp').contains('HTTP').click();
    });
    // Set a custom proxy
    cy.get('input[type="text"]').eq(0).clear().type('socks5://special:1080');
    cy.contains('button', 'Save').click();
    // Custom badge should appear
    cy.contains('Per-MCP Proxy Overrides').parent().within(() => {
      cy.contains('tr', 'daas-mcp').contains('Custom').should('exist');
      cy.contains('socks5://special:1080').should('exist');
    });
  });

  it('US4: per-MCP proxy — clear removes override', () => {
    cy.visit('/settings');
    // First set a value
    cy.contains('Per-MCP Proxy Overrides').parent().within(() => {
      cy.contains('tr', 'daas-mcp').contains('HTTP').click();
    });
    cy.get('input[type="text"]').eq(0).clear().type('socks5://to-clear:1080');
    cy.contains('button', 'Save').click();

    // Now open again and clear
    cy.contains('Per-MCP Proxy Overrides').parent().within(() => {
      cy.contains('tr', 'daas-mcp').contains('HTTP').click();
    });
    cy.contains('button', 'Clear').click();

    // Should show inherited
    cy.contains('Per-MCP Proxy Overrides').parent().within(() => {
      cy.contains('tr', 'daas-mcp').contains('(inherited)').should('exist');
    });
  });

  it('nav: Settings link works', () => {
    cy.visit('/cron');
    cy.contains('nav a', 'Settings').click();
    cy.url().should('include', '/settings');
    cy.get('h1').should('contain', 'Settings');
  });
});
