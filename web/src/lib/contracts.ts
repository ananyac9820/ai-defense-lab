/**
 * TypeScript mirrors of the frozen contracts in /contracts.
 *
 * These are hand-maintained rather than generated, and `npm run typecheck` will not
 * catch a drift against the JSON Schema on its own - so the Python side owns
 * validation and this file owns the read shape. If you change one, change both; the
 * contract version below is the tripwire.
 */

export const CONTRACT_VERSION = '0.1.0';

export type Channel =
  | 'cards_cnp'
  | 'upi_instant'
  | 'wallets_tokenisation'
  | 'bank_transfer'
  | 'merchant_payouts'
  | 'kyc_onboarding'
  | 'agentic_commerce';

export type Level = 'transaction' | 'session' | 'graph';

export interface AttackSource {
  case: string;
  stat: string | null;
  citation_url: string;
  doc_ref: string;
  regulator_advisory?: string | null;
}

export interface Vector {
  vector_id: string;
  name: string;
  channel: Channel;
  ai_capability: string;
  objective: string;
  chain: string[];
  data_signature: string;
  parameters: Record<string, unknown>;
  source: AttackSource;
  expected_levels: Level[];
  holdout: 'none' | 'family' | 'composition';
  generation: number;
  parent_vector_id?: string | null;
  mutation_mode?: string | null;
  narrative?: string | null;
}

export interface AttacksFile {
  contract_version: string;
  generated_at: string;
  grammar_version: string;
  vectors: Vector[];
}

export interface Account {
  account_id: string;
  opened_at: string;
  home_geo: string;
  segment: string;
  kyc_level: string;
  label_is_mule: boolean;
  label_is_synthetic_identity: boolean;
}

export interface Transaction {
  transaction_id: string;
  account_id: string;
  device_id: string;
  merchant_id: string | null;
  session_id: string | null;
  timestamp: string;
  amount_inr: number;
  channel: Channel;
  geography: string;
  mcc: string;
  auth_result: 'approved' | 'declined' | 'pending';
  is_fraud: boolean;
  vector_id: string | null;
  chain_position: number | null;
  generation: number | null;
}

export interface SessionEvent {
  type: string;
  t_offset_ms: number;
  screen?: string | null;
  field?: string | null;
  input_method?: 'type' | 'paste' | 'autofill' | 'none' | null;
  dwell_ms?: number | null;
  corrections?: number | null;
}

export interface Session {
  session_id: string;
  account_id: string;
  device_id: string;
  started_at: string;
  channel: Channel;
  events: SessionEvent[];
  outcome: string;
  is_fraud: boolean;
  vector_id: string | null;
}

export interface GraphEdge {
  source_account: string;
  target_account: string;
  timestamp: string;
  amount_inr: number;
  edge_type: string;
  transaction_id: string | null;
}

export interface Ledger {
  contract_version: string;
  label_columns: string[];
  tables: {
    accounts: Account[];
    devices: { device_id: string; os_family: string; is_emulator: boolean }[];
    merchants: { merchant_id: string; mcc: string; risk_tier: string }[];
    transactions: Transaction[];
    sessions: Session[];
    graph_edges: GraphEdge[];
  };
}

export interface Metrics {
  prevalence: number;
  precision: number;
  recall: number;
  f1: number;
  auc_roc: number;
  auc_pr: number;
  alert_rate: number;
  net_value_protected_inr: number | null;
  scoring_latency_p50_ms: number | null;
  scoring_latency_p99_ms: number | null;
  lift_over_baseline: Record<string, number> | null;
}

export interface Generation {
  generation: number;
  n_vectors: number;
  n_transactions: number;
  n_fraud: number;
  metrics_seen: Metrics;
  metrics_unseen: Metrics;
  ablation?: { variant: string; metrics: Metrics }[];
  detection_rate: number | null;
  /** Same evaluation population every generation. Movement here means the detector moved. */
  detection_rate_fixed_set?: number | null;
  /** Only the vectors this generation introduced. Answers whether the attacker got through. */
  detection_rate_new_vectors?: number | null;
  n_chains_proposed: number | null;
  n_chains_rejected: number | null;
}

export interface Fidelity {
  discriminator_auc: number;
  comparable_columns: string[];
  excluded_columns: string[];
  reference_profiles?: { name: string; serves_channels: string[]; available: boolean }[];
  ks_per_column: Record<string, number> | null;
  psi_per_column: Record<string, number> | null;
  correlation_delta_frobenius: number | null;
}

export interface RunManifest {
  contract_version: string;
  run_id: string;
  created_at: string;
  seed: number;
  config_hash: string;
  prevalence: number;
  is_fixture: boolean;
  baseline: { name: string; features: string[]; metrics: Metrics };
  generations: Generation[];
  fidelity: Fidelity;
  cost_model: { review_cost_inr: number; currency: string };
  artefacts: Record<string, unknown>;
}

export interface MissRecord {
  instance_id: string;
  vector_id: string;
  chain: string[];
  primitives_present: string[];
  score: number;
  level_scores: { transaction: number | null; session: number | null; graph: number | null };
  top_shap: { feature: string; value: number }[];
  evasion_hypothesis: string | null;
}

export interface MissesFile {
  contract_version: string;
  run_id: string;
  generation: number;
  threshold: number;
  prevalence: number;
  misses: MissRecord[];
  per_vector: {
    vector_id: string;
    n_instances: number;
    n_detected: number;
    detection_rate: number;
    holdout?: string;
  }[];
}
