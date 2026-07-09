// Self-check for the /api/mcp-ui/* proxy routes that back the /chat mcp-ui
// rendering flow. Requires composite-mcp to be spawnable by the dashboard
// (mcp/composite-mcp/.venv). Guards:
//   - read-resource returns the UIResource with the MCP-Apps MIME for the
//     composite-mcp demo tool's ui:// resource.
//   - call-tool returns _meta.ui.resourceUri for render_stock_summary.
//
// See openspec/changes/add-mcp-ui-chat (tasks 2.4 + 5.2).

describe('mcp-ui proxy routes', () => {
  it('read-resource returns the UIResource with the MCP-Apps MIME', () => {
    cy.request({
      method: 'POST',
      url: '/api/mcp-ui/read-resource',
      body: {
        server: 'composite-mcp',
        uri: 'ui://composite-mcp/stock-summary/AAPL',
      },
      timeout: 60000, // composite-mcp stdio spawn can take a few seconds
    }).then((resp) => {
      expect(resp.status).to.eq(200);
      const contents = resp.body.contents;
      expect(contents, 'contents array').to.be.an('array').with.length.greaterThan(0);
      const c = contents[0];
      expect(c.mimeType).to.eq('text/html;profile=mcp-app');
      expect(c.text).to.be.a('string');
      expect(c.text).to.contain('Apple');
    });
  });

  it('call-tool returns _meta.ui.resourceUri for render_stock_summary', () => {
    cy.request({
      method: 'POST',
      url: '/api/mcp-ui/call-tool',
      body: {
        server: 'composite-mcp',
        name: 'render_stock_summary',
        arguments: { symbol: 'TSLA' },
      },
      timeout: 60000,
    }).then((resp) => {
      expect(resp.status).to.eq(200);
      const meta = resp.body.meta ?? resp.body._meta;
      expect(meta?.ui?.resourceUri, 'resourceUri').to.eq(
        'ui://composite-mcp/stock-summary/TSLA',
      );
    });
  });

  it('rejects unknown op with 404', () => {
    cy.request({
      method: 'POST',
      url: '/api/mcp-ui/bogus-op',
      body: { server: 'composite-mcp' },
      failOnStatusCode: false,
    }).then((resp) => {
      expect(resp.status).to.eq(404);
    });
  });

  it('rejects GET with 405', () => {
    cy.request({
      method: 'GET',
      url: '/api/mcp-ui/read-resource',
      failOnStatusCode: false,
    }).then((resp) => {
      expect(resp.status).to.eq(405);
    });
  });
});
