import { useMemo } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { Empty, GlassPanel, Metric } from '../components/ui';
import { formatInr, lift, pct } from '../lib/data';
import { useStore } from '../lib/store';
import { axisProps, tooltipProps } from './chartTheme';

/**
 * Pillar 3, Defend (PDF S6).
 *
 * Threshold selection is an economic choice, not an arbitrary one: net value protected
 * is the value of fraud caught less the cost of reviewing false positives. Moving the
 * slider moves the money, which is the version of this a payments operator cares about.
 *
 * SHAP values are shown as signed contributions - in 3D they become force vectors
 * pushing a point toward or away from the boundary, which is the same information.
 */
export default function DetectionSurface() {
  const { bundle, perspective, threshold, setThreshold, generation } = useStore();
  const attacker = perspective === 'attacker';

  const curve = useMemo(() => {
    if (!bundle) return [];
    const gen =
      bundle.manifest.generations[Math.min(generation, bundle.manifest.generations.length - 1)];
    const { recall, precision, alert_rate } = gen.metrics_seen;
    const cost = bundle.manifest.cost_model.review_cost_inr;
    const fraudValue = gen.metrics_seen.net_value_protected_inr ?? 1e7;
    const n = bundle.ledger.tables.transactions.length;

    // A monotone family around the operating point. Real curves replace this in Phase 3;
    // the shape and the trade-off it encodes are what the view is built to show.
    return Array.from({ length: 41 }, (_, i) => {
      const t = i / 40;
      const r = Math.min(0.995, recall * Math.pow(1 - t, 0.55) * 1.9);
      const p = Math.min(0.98, precision * Math.pow(t + 0.05, 0.45) * 2.2);
      const alerts = Math.max(0.0002, alert_rate * Math.pow(1 - t, 1.6) * 2.4);
      const reviewCost = alerts * n * cost;
      return {
        threshold: Number(t.toFixed(3)),
        recall: r,
        precision: p,
        alert_rate: alerts,
        net: fraudValue * r - reviewCost,
      };
    });
  }, [bundle, generation]);

  const shap = useMemo(() => {
    const misses = bundle?.misses.find((m) => m.generation === generation);
    const first = misses?.misses[0];
    return first
      ? { instance: first, bars: [...first.top_shap].sort((a, b) => a.value - b.value) }
      : null;
  }, [bundle, generation]);

  if (!bundle) return <Empty what="detector output" />;

  const at = curve.reduce((best, row) =>
    Math.abs(row.threshold - threshold) < Math.abs(best.threshold - threshold) ? row : best
  );
  const optimum = curve.reduce((best, row) => (row.net > best.net ? row : best));
  const baseline = bundle.manifest.baseline.metrics;

  return (
    <div className="flex flex-col gap-6">
      <GlassPanel
        kicker={attacker ? 'the gap under the boundary' : 'the decision boundary'}
        title={attacker ? 'Where a transaction survives scoring' : 'Threshold is an economic choice'}
      >
        <div className="mb-4 grid grid-cols-2 gap-6 md:grid-cols-4">
          <Metric
            label="Recall at threshold"
            value={pct(at.recall)}
            lift={lift(at.recall, baseline.recall)}
          />
          <Metric
            label="Precision at threshold"
            value={pct(at.precision)}
            lift={lift(at.precision, baseline.precision)}
          />
          <Metric
            label="Alert rate"
            value={pct(at.alert_rate, 2)}
            hint="determines review staffing"
          />
          <Metric label="Net value protected" value={at.net} currency hint={`optimum at ${optimum.threshold}`} />
        </div>

        <div className="mb-4 flex items-center gap-4">
          <span className="label-caps w-24">threshold</span>
          <input
            type="range"
            min={0}
            max={1}
            step={0.025}
            value={threshold}
            onChange={(e) => setThreshold(Number(e.target.value))}
            className="h-1 flex-1 cursor-pointer appearance-none rounded-full"
            style={{
              background: `linear-gradient(to right, var(--accent) ${threshold * 100}%, rgba(232,237,240,0.12) ${threshold * 100}%)`,
            }}
          />
          <span className="tabular w-14 text-right">{threshold.toFixed(3)}</span>
        </div>

        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={curve} margin={{ top: 8, right: 16, bottom: 0, left: -8 }}>
              <CartesianGrid stroke="rgba(232,237,240,0.05)" vertical={false} />
              <XAxis dataKey="threshold" {...axisProps} />
              <YAxis yAxisId="rate" domain={[0, 1]} tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} {...axisProps} />
              <YAxis
                yAxisId="money"
                orientation="right"
                tickFormatter={(v: number) => formatInr(v)}
                {...axisProps}
              />
              <Tooltip {...tooltipProps} />
              <ReferenceLine x={at.threshold} yAxisId="rate" stroke="var(--accent)" strokeDasharray="3 3" />
              <Line yAxisId="rate" type="monotone" dataKey="recall" stroke="var(--accent)" strokeWidth={2} dot={false} />
              <Line yAxisId="rate" type="monotone" dataKey="precision" stroke="var(--accent-2)" strokeWidth={2} dot={false} />
              <Line
                yAxisId="money"
                type="monotone"
                dataKey="net"
                name="net value protected"
                stroke="var(--color-slate)"
                strokeWidth={1.5}
                strokeDasharray="5 4"
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </GlassPanel>

      <div className="grid gap-6 lg:grid-cols-2">
        <GlassPanel kicker="explainability" title="Why this alert scored the way it did">
          {shap ? (
            <>
              <div className="tabular mb-3 text-xs text-[var(--color-slate)]">
                {shap.instance.instance_id} · {shap.instance.vector_id} · score{' '}
                {shap.instance.score.toFixed(3)}
              </div>
              <div className="h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={shap.bars} layout="vertical" margin={{ left: 60, right: 12 }}>
                    <XAxis type="number" {...axisProps} />
                    <YAxis type="category" dataKey="feature" width={150} {...axisProps} />
                    <Tooltip {...tooltipProps} />
                    <ReferenceLine x={0} stroke="rgba(232,237,240,0.2)" />
                    <Bar dataKey="value" radius={3}>
                      {shap.bars.map((b, i) => (
                        <Cell
                          key={i}
                          fill={b.value >= 0 ? 'var(--accent)' : 'var(--color-attack-2)'}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <p className="mt-2 text-xs leading-relaxed text-[var(--color-slate)]">
                Negative contributions pushed this instance towards legitimate. Those are what
                the red-team strategist targets in the next generation.
              </p>
            </>
          ) : (
            <Empty what="miss log" />
          )}
        </GlassPanel>

        <GlassPanel kicker="three levels of evidence" title="What each level catches">
          <div className="flex flex-col gap-4 text-sm">
            {[
              ['Transaction', 'amount, hour, channel, MCC, device match, geography delta', 'point anomalies, obvious drains'],
              ['Session', 'rolling counts, distinct beneficiaries, inter-arrival timing, decline ratio, paste ratio, confirm dwell', 'card testing, probing, coerced transfers'],
              ['Graph', 'degree ratios, cycle membership, pass-through score, community density', 'mule networks, layering, collusion rings'],
            ].map(([level, features, catches]) => (
              <div key={level}>
                <div className="flex items-baseline gap-2">
                  <span style={{ color: 'var(--accent)' }}>{level}</span>
                  <span className="text-xs text-[var(--color-slate)]">{catches}</span>
                </div>
                <div className="mt-1 text-xs text-[var(--color-slate)]">{features}</div>
              </div>
            ))}
          </div>
          <p className="mt-4 text-xs leading-relaxed text-[var(--color-slate)]">
            The lift each level contributes is reported as an ablation. So is the lift from
            the coercion signal specifically — a behavioural signal we invented is detectable
            by construction, so its contribution has to be a stated number rather than a
            hidden crutch.
          </p>
        </GlassPanel>
      </div>
    </div>
  );
}
