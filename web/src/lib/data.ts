/**
 * Artefact loading.
 *
 * The prototype reads what the pipeline emits and holds no business logic of its own
 * (PDF S3). Filenames are resolved here and nowhere else.
 *
 * Two ledger shapes exist and both are handled here rather than in any view: the row-form
 * fixture written by scripts/make_fixtures.py, and the columnar demo slice written by the
 * real pipeline. Columns-of-arrays keeps a 35k-row slice with session telemetry to a few
 * megabytes; rows-of-objects ran to tens.
 */

import type { AttacksFile, Ledger, MissesFile, RunManifest, Session, Transaction } from './contracts';

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

const alt = (stem: string) => [`${stem}.json`, `${stem}.fixture.json`];

export const loadManifest = () => getJson<RunManifest>(alt('run_manifest'));
export const loadAttacks = () => getJson<AttacksFile>(alt('attacks'));
export const loadMisses = (generation: number) => getJson<MissesFile>(alt(`misses.g${generation}`));

interface ColumnarSlice {
  format: 'columnar';
  n_rows: number;
  prevalence: number;
  threshold?: number;
  columns: Record<string, (string | number | boolean | null)[]>;
  sessions: Record<string, Record<string, unknown>[]>;
  graph_edges: Record<string, (string | number)[]>;
  accounts: Record<string, boolean>;
}

/** Columns of arrays back into the row shape the views read. */
function fromColumnar(slice: ColumnarSlice): Ledger {
  const c = slice.columns;
  const n = slice.n_rows;

  const transactions: Transaction[] = Array.from({ length: n }, (_, i) => ({
    transaction_id: String(c.transaction_id[i]),
    account_id: String(c.account_id[i]),
    device_id: String(c.device_id[i]),
    merchant_id: null,
    session_id: null,
    timestamp: String(c.timestamp[i]),
    amount_inr: Number(c.amount_inr[i]),
    channel: c.channel[i] as Transaction['channel'],
    geography: String(c.geography[i]),
    mcc: String(c.mcc[i]),
    auth_result: c.auth_result[i] as Transaction['auth_result'],
    is_fraud: Boolean(c.is_fraud[i]),
    vector_id: c.vector_id[i] === null ? null : String(c.vector_id[i]),
    chain_position: null,
    generation: null,
  }));

  const sessions: Session[] = Object.entries(slice.sessions ?? {}).map(([id, events]) => ({
    session_id: id,
    account_id: '',
    device_id: '',
    started_at: '',
    channel: 'upi_instant',
    events: events as unknown as Session['events'],
    outcome: 'completed',
    is_fraud: true,
    vector_id: null,
  }));

  const g = slice.graph_edges ?? { source_account: [] };
  const edges = (g.source_account ?? []).map((_, i) => ({
    source_account: String(g.source_account[i]),
    target_account: String(g.target_account[i]),
    timestamp: String(g.timestamp[i]),
    amount_inr: Number(g.amount_inr[i]),
    edge_type: String(g.edge_type[i]),
    transaction_id: null,
  }));

  return {
    contract_version: '0.1.0',
    label_columns: [],
    tables: {
      accounts: Object.entries(slice.accounts ?? {}).map(([id, mule]) => ({
        account_id: id,
        opened_at: '',
        home_geo: '',
        segment: '',
        kyc_level: '',
        label_is_mule: Boolean(mule),
        label_is_synthetic_identity: false,
      })),
      devices: [],
      merchants: [],
      transactions,
      sessions,
      graph_edges: edges,
    },
  };
}

export async function loadLedger(): Promise<Ledger> {
  const raw = await getJson<ColumnarSlice | Ledger>([
    'demo_slice.json',
    'demo_slice.fixture.json',
    'ledger.json',
    'ledger.fixture.json',
  ]);
  return 'format' in raw && raw.format === 'columnar' ? fromColumnar(raw) : (raw as Ledger);
}

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
  return { manifest, attacks, ledger, misses: misses.filter((m): m is MissesFile => m !== null) };
}

/** Percentage lift of `value` over `baseline`, the only form a headline is reported in. */
export function lift(value: number, baseline: number): number {
  if (!baseline) return 0;
  return ((value - baseline) / baseline) * 100;
}

export function formatInr(n: number): string {
  const sign = n < 0 ? '-' : '';
  const v = Math.abs(n);
  if (v >= 1e7) return `${sign}INR ${(v / 1e7).toFixed(2)} Cr`;
  if (v >= 1e5) return `${sign}INR ${(v / 1e5).toFixed(2)} L`;
  if (v >= 1e3) return `${sign}INR ${(v / 1e3).toFixed(1)}k`;
  return `${sign}INR ${v.toFixed(0)}`;
}

export const pct = (n: number, dp = 1) => `${(n * 100).toFixed(dp)}%`;
