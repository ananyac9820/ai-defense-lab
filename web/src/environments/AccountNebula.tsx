import { useMemo } from 'react';
import { Empty, GlassPanel, Metric } from '../components/ui';
import { useStore } from '../lib/store';

/**
 * The account graph (PDF S6.1, graph level).
 *
 * This is the visual proof of the Mastercard-graph requirement: their AI Garage doubled
 * compromised-card detection by combining generative AI with graph technology over
 * relationships between accounts, devices and cards. Mule layering is a topology, not a
 * row - fan-out, short cycles, pass-through accounts that never hold a balance.
 *
 * 2D fallback: a deterministic radial layout of the highest pass-through accounts, plus
 * the graph features the detector actually consumes. The 3D force-directed version
 * replaces the layout, not the features.
 */

interface Node {
  id: string;
  inflow: number;
  outflow: number;
  degIn: number;
  degOut: number;
  passthrough: number;
  isMule: boolean;
}

export default function AccountNebula() {
  const { bundle, perspective } = useStore();
  const attacker = perspective === 'attacker';

  const { nodes, edges, stats } = useMemo(() => {
    if (!bundle) return { nodes: [] as Node[], edges: [], stats: null };
    const { accounts, graph_edges } = bundle.ledger.tables;
    const muleSet = new Set(accounts.filter((a) => a.label_is_mule).map((a) => a.account_id));

    const acc = new Map<string, Node>();
    const touch = (id: string): Node => {
      let n = acc.get(id);
      if (!n) {
        n = {
          id,
          inflow: 0,
          outflow: 0,
          degIn: 0,
          degOut: 0,
          passthrough: 0,
          isMule: muleSet.has(id),
        };
        acc.set(id, n);
      }
      return n;
    };

    const transfers = graph_edges.filter((e) => e.edge_type === 'transfer');
    for (const e of transfers) {
      const s = touch(e.source_account);
      const t = touch(e.target_account);
      s.outflow += e.amount_inr;
      s.degOut += 1;
      t.inflow += e.amount_inr;
      t.degIn += 1;
    }
    for (const n of acc.values()) {
      // Pass-through: money in and money out are near-equal and neither is zero. A mule
      // account is defined by what it does not do - hold a balance.
      const total = n.inflow + n.outflow;
      n.passthrough =
        total > 0 && n.inflow > 0 && n.outflow > 0
          ? 1 - Math.abs(n.inflow - n.outflow) / total
          : 0;
    }

    const ranked = [...acc.values()]
      .filter((n) => n.degIn + n.degOut >= 2)
      .sort((a, b) => b.passthrough * (b.degIn + b.degOut) - a.passthrough * (a.degIn + a.degOut))
      .slice(0, 34);
    const keep = new Set(ranked.map((n) => n.id));

    const flagged = ranked.filter((n) => n.passthrough > 0.85 && n.degIn + n.degOut >= 3);
    return {
      nodes: ranked,
      edges: transfers.filter((e) => keep.has(e.source_account) && keep.has(e.target_account)),
      stats: {
        accounts: accounts.length,
        transfers: transfers.length,
        flagged: flagged.length,
        mules: accounts.filter((a) => a.label_is_mule).length,
        volume: transfers.reduce((s, e) => s + e.amount_inr, 0),
      },
    };
  }, [bundle]);

  if (!bundle || !stats) return <Empty what="account graph" />;

  const R = 190;
  const pos = new Map(
    nodes.map((n, i) => {
      const angle = (i / nodes.length) * Math.PI * 2 - Math.PI / 2;
      // two rings: high pass-through pulled inward, which is the mule signature
      const r = R * (n.passthrough > 0.8 ? 0.55 : 1);
      return [n.id, { x: 240 + Math.cos(angle) * r, y: 230 + Math.sin(angle) * r }] as const;
    })
  );

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_22rem]">
      <GlassPanel
        kicker={attacker ? 'the route' : 'the topology'}
        title={attacker ? 'Where the money goes to disappear' : 'Account graph — mule structure'}
      >
        <svg viewBox="0 0 480 460" className="h-[26rem] w-full">
          <defs>
            <radialGradient id="nebula-glow">
              <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.30" />
              <stop offset="100%" stopColor="var(--accent)" stopOpacity="0" />
            </radialGradient>
          </defs>
          <circle cx="240" cy="230" r="200" fill="url(#nebula-glow)" />
          {edges.map((e, i) => {
            const a = pos.get(e.source_account)!;
            const b = pos.get(e.target_account)!;
            return (
              <line
                key={i}
                x1={a.x}
                y1={a.y}
                x2={b.x}
                y2={b.y}
                stroke="var(--accent-2)"
                strokeOpacity={0.22}
                strokeWidth={0.9}
              />
            );
          })}
          {nodes.map((n) => {
            const p = pos.get(n.id)!;
            const r = 3 + Math.min(7, (n.degIn + n.degOut) * 0.55);
            const hot = n.passthrough > 0.85;
            return (
              <g key={n.id}>
                <circle
                  cx={p.x}
                  cy={p.y}
                  r={r}
                  fill={hot ? 'var(--accent)' : 'rgba(232,237,240,0.35)'}
                  stroke={hot ? 'var(--accent)' : 'transparent'}
                  strokeOpacity={0.5}
                  strokeWidth={hot ? 6 : 0}
                  style={{ transition: 'fill 800ms' }}
                >
                  <title>
                    {n.id} · pass-through {(n.passthrough * 100).toFixed(0)}% · in {n.degIn} / out{' '}
                    {n.degOut}
                  </title>
                </circle>
              </g>
            );
          })}
        </svg>
        <p className="mt-2 text-sm leading-relaxed text-[var(--color-slate)]">
          Nodes pulled inward are pass-through accounts: money in and money out near-equal,
          nothing resting.{' '}
          {attacker
            ? 'From this side it is a route.'
            : 'From this side it is the detection surface.'}{' '}
          Neither reading changes a single edge.
        </p>
      </GlassPanel>

      <div className="flex flex-col gap-6">
        <GlassPanel kicker="graph level" title="Features the detector consumes">
          <div className="grid grid-cols-2 gap-5">
            <Metric label="Accounts" value={stats.accounts.toLocaleString()} />
            <Metric label="Transfer edges" value={stats.transfers.toLocaleString()} />
            <Metric label="Pass-through flagged" value={stats.flagged} hint=">85% in/out balance" />
            <Metric label="Volume" value={stats.volume} currency />
          </div>
          <ul className="mt-5 flex flex-col gap-2 text-sm text-[var(--color-slate)]">
            {[
              'degree ratio (fan-in / fan-out, 24h)',
              'pass-through score',
              'cycle membership, length ≤ 4',
              'shortest path to a flagged node',
              'community density',
              'shared-device edges between unrelated accounts',
            ].map((f) => (
              <li key={f} className="flex gap-2">
                <span style={{ color: 'var(--accent)' }}>·</span>
                {f}
              </li>
            ))}
          </ul>
        </GlassPanel>

        <GlassPanel kicker="why this pillar exists" title="Mastercard's own approach">
          <p className="text-sm leading-relaxed text-[var(--color-slate)]">
            Mastercard's AI Garage doubled compromised-card detection by combining
            generative AI with graph technology — relationships between accounts, devices
            and cards. A row-level classifier cannot represent a topology no matter how it
            is tuned, which is why the graph level is a level and not a feature.
          </p>
        </GlassPanel>
      </div>
    </div>
  );
}
