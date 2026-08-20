import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { GlassPanel, Metric, Empty } from '../components/ui';
import { lift, pct } from '../lib/data';
import { useStore } from '../lib/store';
import { axisProps, tooltipProps } from './chartTheme';

/**
 * The closed loop (PDF S7). The detection-rate-per-generation curve is the single most
 * compelling artefact in the submission, so it is the landing environment.
 *
 * Defender view reads the curve as hardening. Attacker view reads the same series as
 * survival - which families lasted longest - which PDF S7.2 calls out as a genuine
 * research finding rather than a metric.
 */
export default function LoopHelix() {
  const { bundle, perspective, generation, setGeneration } = useStore();
  if (!bundle) return <Empty what="run manifest" />;

  const { manifest, misses } = bundle;
  const attacker = perspective === 'attacker';
  const baseline = manifest.baseline.metrics;

  const series = manifest.generations.map((g) => ({
    generation: `G${g.generation}`,
    seen: g.metrics_seen.recall,
    unseen: g.metrics_unseen.recall,
    evaded: 1 - (g.detection_rate ?? 0),
    detected: g.detection_rate ?? 0,
    aucpr: g.metrics_seen.auc_pr,
  }));

  const current = manifest.generations[Math.min(generation, manifest.generations.length - 1)];
  const gMisses = misses.find((m) => m.generation === current.generation);
  const survivors = [...(gMisses?.per_vector ?? [])].sort(
    (a, b) => a.detection_rate - b.detection_rate
  );

  return (
    <div className="flex flex-col gap-6">
      <GlassPanel
        kicker={attacker ? 'what survived' : 'the closed loop'}
        title={
          attacker
            ? 'Evasion rate falls as the detector learns from its own misses'
            : 'Detection rate per generation'
        }
      >
        <div className="mb-5 grid grid-cols-2 gap-6 md:grid-cols-4">
          <Metric
            label="Recall, seen attacks"
            value={pct(current.metrics_seen.recall)}
            lift={lift(current.metrics_seen.recall, baseline.recall)}
            hint={`at ${pct(current.metrics_seen.prevalence, 2)} prevalence`}
          />
          <Metric
            label="Recall, unseen families"
            value={pct(current.metrics_unseen.recall)}
            lift={lift(current.metrics_unseen.recall, baseline.recall)}
            hint="held-out families and compositions, never merged with seen"
          />
          <Metric
            label="AUC-PR"
            value={current.metrics_seen.auc_pr.toFixed(3)}
            lift={lift(current.metrics_seen.auc_pr, baseline.auc_pr)}
            hint="the honest headline at low prevalence"
          />
          <Metric
            label="Net value protected"
            value={current.metrics_seen.net_value_protected_inr ?? 0}
            currency
            hint={`less ₹${manifest.cost_model.review_cost_inr}/review`}
          />
        </div>

        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={series} margin={{ top: 8, right: 16, bottom: 0, left: -12 }}>
              <CartesianGrid stroke="rgba(232,237,240,0.06)" vertical={false} />
              <XAxis dataKey="generation" {...axisProps} />
              <YAxis domain={[0, 1]} tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} {...axisProps} />
              <Tooltip
                {...tooltipProps}
                formatter={(v: number, n: string) => [`${(v * 100).toFixed(1)}%`, n]}
              />
              {attacker ? (
                <Line
                  type="monotone"
                  dataKey="evaded"
                  name="evaded detection"
                  stroke="var(--accent)"
                  strokeWidth={2.5}
                  dot={{ r: 3 }}
                />
              ) : (
                <Line
                  type="monotone"
                  dataKey="detected"
                  name="detected"
                  stroke="var(--accent)"
                  strokeWidth={2.5}
                  dot={{ r: 3 }}
                />
              )}
              <Line
                type="monotone"
                dataKey="seen"
                name="recall, seen"
                stroke="var(--accent-2)"
                strokeWidth={1.5}
                strokeDasharray="4 4"
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="unseen"
                name="recall, unseen"
                stroke="var(--color-slate)"
                strokeWidth={1.5}
                strokeDasharray="2 6"
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-2">
          <span className="label-caps mr-2">generation</span>
          {manifest.generations.map((g) => (
            <button
              key={g.generation}
              onClick={() => setGeneration(g.generation)}
              className="tabular rounded-full border px-3 py-1 text-xs"
              style={{
                borderColor:
                  g.generation === current.generation
                    ? 'color-mix(in oklab, var(--accent) 60%, transparent)'
                    : 'var(--color-edge)',
                color: g.generation === current.generation ? 'var(--accent)' : 'var(--color-slate)',
              }}
            >
              G{g.generation}
              {g.n_chains_proposed ? ` · +${g.n_chains_proposed} proposed` : ''}
            </button>
          ))}
        </div>
      </GlassPanel>

      <div className="grid gap-6 lg:grid-cols-2">
        <GlassPanel
          kicker={attacker ? 'longest survivors' : 'weakest coverage'}
          title="Per-vector detection rate"
        >
          <div className="flex flex-col gap-2">
            {survivors.map((v) => (
              <div key={v.vector_id} className="flex items-center gap-3">
                <span className="tabular w-14 text-xs text-[var(--color-slate)]">
                  {v.vector_id}
                </span>
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-[rgba(232,237,240,0.07)]">
                  <div
                    className="h-full rounded-full transition-[width] duration-700"
                    style={{
                      width: `${(attacker ? 1 - v.detection_rate : v.detection_rate) * 100}%`,
                      background: 'var(--accent)',
                    }}
                  />
                </div>
                <span className="tabular w-14 text-right text-xs">
                  {pct(attacker ? 1 - v.detection_rate : v.detection_rate, 0)}
                </span>
              </div>
            ))}
            {!survivors.length && <Empty what="miss log" />}
          </div>
        </GlassPanel>

        <GlassPanel kicker="validation layer" title="Strategist output quality">
          <div className="grid grid-cols-2 gap-6">
            <Metric
              label="Chains proposed"
              value={current.n_chains_proposed ?? 0}
              hint="generation 0 is hand-authored"
            />
            <Metric
              label="Chains rejected"
              value={current.n_chains_rejected ?? 0}
              hint="grammar-invalid, duplicate, or implausible"
            />
          </div>
          <p className="mt-4 text-sm leading-relaxed text-[var(--color-slate)]">
            Every chain the strategist returns is validated against the grammar,
            deduplicated against existing vector_ids, and plausibility-checked before the
            simulator touches it. The rejection rate is reported, not hidden — a model that
            needs heavy filtering is a finding about the method.
          </p>
        </GlassPanel>
      </div>
    </div>
  );
}
