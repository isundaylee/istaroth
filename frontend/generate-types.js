#!/usr/bin/env node
/**
 * Generate TypeScript types from OpenAPI specification.
 * This script reads the openapi.json file and generates TypeScript definitions.
 */

import { execSync } from 'child_process';
import { existsSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Path to the OpenAPI spec file (relative to project root)
const OPENAPI_SPEC_PATH = join(__dirname, '..', 'openapi.json');
const OUTPUT_PATH = join(__dirname, 'src', 'types', 'api-generated.ts');

function generateTypes() {
  // Check if OpenAPI spec exists
  if (!existsSync(OPENAPI_SPEC_PATH)) {
    console.error('❌ OpenAPI spec not found at:', OPENAPI_SPEC_PATH);
    console.error('   Run the backend OpenAPI generation script first:');
    console.error('   PYTHONPATH=. env/bin/python scripts/generate_openapi.py');
    process.exit(1);
  }

  console.log('📖 Reading OpenAPI spec from:', OPENAPI_SPEC_PATH);
  console.log('📝 Generating TypeScript types to:', OUTPUT_PATH);

  // Generate TypeScript types using openapi-typescript
  const command = `npx openapi-typescript "${OPENAPI_SPEC_PATH}" --output "${OUTPUT_PATH}"`;

  execSync(command, {
    stdio: 'inherit',
    cwd: __dirname
  });

  console.log('✅ TypeScript types generated successfully!');
  console.log('   Import from: ./src/types/api-generated');
}

generateTypes();
