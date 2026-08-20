// Copy pipeline artefacts into the Vite public directory.
//
// The prototype reads artefacts; it contains no business logic of its own (PDF S3).
// This script is the seam: today it copies fixtures, and from Phase 5 it copies
// artifacts/published instead. Nothing in the frontend changes when that happens.

import { cp, mkdir, readdir, rm, stat } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const repo = resolve(here, '..', '..');
const dest = resolve(here, '..', 'public', 'data');

const live = join(repo, 'artifacts', 'published');
const fixtures = join(repo, 'fixtures');
const source = existsSync(live) && (await readdir(live)).length > 0 ? live : fixtures;

await rm(dest, { recursive: true, force: true });
await mkdir(dest, { recursive: true });
await cp(source, dest, { recursive: true });

const files = await readdir(dest);
let bytes = 0;
for (const f of files) bytes += (await stat(join(dest, f))).size;

console.log(
  `sync-data: ${source === live ? 'LIVE artefacts' : 'FIXTURES'} -> web/public/data ` +
    `(${files.length} files, ${(bytes / 1024).toFixed(0)} KB)`
);
