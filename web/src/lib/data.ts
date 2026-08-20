/**
 * Artefact loading.
 *
 * The prototype reads what the pipeline emits and holds no business logic of its own
 * (PDF S3). Filenames are resolved here and nowhere else, so the Phase 5 swap from
 * fixtures to live artefacts is a change to this file plus web/scripts/sync-data.mjs.
 */

import type { AttacksFile, Ledger, MissesFile, RunManifest } from './contracts';

const base = `${import.meta.env.BASE_URL}data/`;

async function getJson<T>(candidates: string[]): Promise<T> {
  let lastError: unknown;
  for (const name of candidates) {
    try {
      const res = await fetch(base + name);
      if (res.ok) return (await res.json()) as T;
      lastError = new Error(`${res.status} ${res.statusText} for ${name}`);
    } catch (err) {
      lastError = err;
    }
  }
  throw new Error(
    `could not load any of [${candidates.join(', ')}] from ${base}: ${String(lastError)}`
  );
}

/** Fixture and live artefacts share a shape but not a filename. Try both. */
const alt = (stem: string, ext = 'json') => [`${stem}.${ext}`, `${stem}.fixture.${ext}`];

export const loadManifest = () => getJson<RunManifest>(alt('run_manifest'));
export const loadAttacks = () => getJson<AttacksFile>(alt('attacks'));
export const loadLedger = () => getJson<Ledger>([...alt('demo_slice'), ...alt('ledger')]);
export const loadMisses = (generation: number) =>
  getJson<MissesFile>(alt(`misses.g${generation}`));

export interface Bundle {
  manifest: RunManifest;
  attacks: AttacksFile;
  ledger: Ledger;
  misses: MissesFile[];
}

export async function loadBundle(): Promise<Bundle> {
  const [manifest, attacks, ledger] = await Promise.all([
    loadManifest(),
    loadAttacks(),
    loadLedger(),
  ]);
  const misses = await Promise.all(
    manifest.generations.map((g) => loadMisses(g.generation).catch(() => null))
  );
  return {
    manifest,
    attacks,
    ledger,
    misses: misses.filter((m): m is MissesFile => m !== null),
  };
}

/** Percentage lift of `value` over `baseline`, the only form a headline is reported in. */
export function lift(value: number, baseline: number): number {
  if (!baseline) return 0;
  return ((value - baseline) / baseline) * 100;
}

export function formatInr(n: number): string {
  if (n >= 1e7) return `₹${(n / 1e7).toFixed(2)} Cr`;
  if (n >= 1e5) return `₹${(n / 1e5).toFixed(2)} L`;
  if (n >= 1e3) return `₹${(n / 1e3).toFixed(1)}k`;
  return `₹${n.toFixed(0)}`;
}

export const pct = (n: number, dp = 1) => `${(n * 100).toFixed(dp)}%`;
