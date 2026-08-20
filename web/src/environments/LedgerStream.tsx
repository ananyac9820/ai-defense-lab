import { useMemo } from 'react';
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from 'recharts';
import { Empty, GlassPanel, Metric } from '../components/ui';
import { pct } from '../lib/data';
import { useStore } from '../lib/store';
import { axisProps, tooltipProps } from './chartTheme';

/**
 * Pillar 2, Generate (PDF S5).
 *
 * The point of this view is the sparsity. At a 1% base rate the fraud is nearly
 * invisible against legitimate volume, and that visual is a better argument for why
 * detection is hard than any table of metrics. Building the fixture at 50% fraud would
 * have quietly destroyed it - which is why the fixture is held at 1% too.
 */
export default function LedgerStream() {
  const { bundle, perspective } = useStore();
  const attacker = perspective === 'attacker';

  const { bins, points, stats } = useMemo(() => {
    if (!bundle) return { bins: [], points: [], stats: null };
    const txns = bundle.ledger.tables.transactions;
    const times = txns.map((t) => Date.parse(t.timestamp));
    const min = Math.min(...times);
    const max = Math.max(...times);
    const nBins = 72;
    const width = (max - min) / nBins || 1;

    const bins = Array.from({ length: nBins }, (_, i) => ({
      t: i,
      hour: new Date(min + i * width).toISOString().slice(5, 13).replace('T', ' '),
      legit: 0,
      fraud: 0,
    }));
    const points: { t: number; amount: number; vector: string; z: number }[] = [];

    for (const tx of txns) {
      const i = Math.min(nBins - 1, Math.floor((Date.parse(tx.timestamp) - min) / width));
      if (tx.is_fraud) {
        bins[i].fraud += 1;
        points.push({ t: i, amount: tx.amount_inr, vector: tx.vector_id ?? '—', z: 90 });
      } else {
        bins[i].legit += 1;
      }
    }

    const fraud = txns.filter((t) => t.is_fraud);
    return {
      bins,
      points,
      stats: {
        total: txns.length,
        fraud: fraud.length,
        prevalence: fraud.length / txns.length,
        value: fraud.reduce((s, t) => s + t.amount_inr, 0),
        declined: txns.filter((t) => t.auth_result === 'declined').length,
      },
    };
  }, [bundle]);

  if (!bundle || !stats) return <Empty what="ledger" />;

  return (
    <div className="flex flex-col gap-6">
      <GlassPanel
        kicker={attacker ? 'cover' : 'the needle in the haystack'}
        title={
          attacker
            ? 'Legitimate volume is the camouflage'
            : `Transaction stream at ${pct(stats.prevalence, 2)} fraud`
        }
      >
        <div className="mb-5 grid grid-cols-2 gap-6 md:grid-cols-4">
          <Metric label="Transactions in slice" value={stats.total.toLocaleString()} />
          <Metric label="Fraudulent" value={stats.fraud.toLocaleString()} hint="one in a hundred" />
          <Metric label="Prevalence" value={pct(stats.prevalence, 2)} hint="stated beside every metric" />
          <Metric label="Fraud value" value={stats.value} currency />
        </div>

        <div className="h-56">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={bins} margin={{ top: 4, right: 12, bottom: 0, left: -18 }}>
              <defs>
                <linearGradient id="legit-fill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="var(--accent-2)" stopOpacity={0.35} />
                  <stop offset="100%" stopColor="var(--accent-2)" stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="rgba(232,237,240,0.05)" vertical={false} />
              <XAxis dataKey="hour" {...axisProps} interval={11} />
              <YAxis {...axisProps} />
              <Tooltip {...tooltipProps} />
              <Area
                type="monotone"
                dataKey="legit"
                name="legitimate"
                stroke="var(--accent-2)"
                strokeWidth={1.2}
                fill="url(#legit-fill)"
              />
              <Area
                type="monotone"
                dataKey="fraud"
                name="fraud"
                stroke="var(--color-attack-2)"
                strokeWidth={1.6}
                fill="var(--color-attack-2)"
                fillOpacity={0.25}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </GlassPanel>

      <GlassPanel kicker="every fraudulent transaction in the slice" title="Flares against volume">
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <ScatterChart margin={{ top: 8, right: 12, bottom: 0, left: 4 }}>
              <CartesianGrid stroke="rgba(232,237,240,0.05)" />
              <XAxis dataKey="t" name="time bin" {...axisProps} />
              <YAxis
                dataKey="amount"
                name="amount"
                scale="log"
                domain={['auto', 'auto']}
                tickFormatter={(v: number) => `₹${v >= 1e5 ? `${(v / 1e5).toFixed(0)}L` : (v / 1e3).toFixed(0) + 'k'}`}
                {...axisProps}
              />
              <ZAxis dataKey="z" range={[40, 90]} />
              <Tooltip {...tooltipProps} cursor={{ strokeDasharray: '3 3' }} />
              <Scatter data={points} fill="var(--accent)" fillOpacity={0.75} />
            </ScatterChart>
          </ResponsiveContainer>
        </div>
        <p className="mt-3 text-sm leading-relaxed text-[var(--color-slate)]">
          Both populations come out of the same simulator through the same code path. Mixing
          public-dataset rows with generated fraud would let a tree separate them on
          formatting alone and report an F1 near 0.99 that means nothing — the failure the
          strategy document rates as the only fatal one. A provenance-only classifier is
          tested against exactly that.
        </p>
      </GlassPanel>
    </div>
  );
}
