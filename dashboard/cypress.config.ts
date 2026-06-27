import { defineConfig } from 'cypress';

export default defineConfig({
  e2e: {
    baseUrl: 'http://localhost:3459',
    supportFile: false,
    defaultCommandTimeout: 30000,
    specPattern: 'cypress/e2e/**/*.cy.ts',
  },
});
