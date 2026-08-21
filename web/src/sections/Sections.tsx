import { lazy, Suspense, useEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react';
import { Figure, Hatch, Leader, Placeholder, Plate, SectionMark, Skeleton } from '../components/plate';
import { BarPlot, ContributionPlot, LinePlot } from '../components/draw';
import { formatInr, lift, pct } from '../lib/data';
import { useStore } from '../lib/store';

/**
 * The six views, written as sections of one document rather than pages of an app.
 *
 * Sections overlap deliberately: each one pulls up into the whitespace of the last and
 * hangs an annotation plate across the boundary, so the eye never meets a seam. The
 * hairline ground behind them never restarts, which is what actually does the bleeding.
 */

function Body({ children }: { children: React.ReactNode }) {
  return <p className="max-w-[62ch] text-[15px] leading-[1.55] text-[var(--color-ink-60)]">{children}</p>;
}

/* ------------------------------------------------------------------ 01 IDENTIFY */

export function Constellation() {
  const { bundle, perspective, selectedVector, selectVector } = useStore();
  const attacker = perspective === 'attacker';
  if (!bundle) return <Skeleton rows={5} label="reading attacks.json" />;

  const vectors = bundle.attacks.vectors;
  const selected = vectors.find((v) => v.vector_id === selectedVector) ?? vectors[0];
  const primitives = new Set(vectors.flatMap((v) => v.chain));
  const cells = new Set(vectors.map((v) => `${v.channel}|${v.ai_capability}|${v.objective}`));

  return (
    <section id="constellation" className="relative z-10 pt-24">
      <SectionMark index="01" title="Identify" note="compositional attack grammar" />

      <div className="mt-10 grid gap-10 lg:grid-cols-[1.35fr_1fr]">
        <div>
          <h2 className="display text-[clamp(2.4rem,5.2vw,4.2rem)]">
            {attacker ? (
              <>
                Everything I can
                <br />
                <span className="inverted">compose</span> from nineteen parts.
              </>
            ) : (
              <>
                Coverage is a property
                <br />
                of the <span className="boxed">grammar</span>, not a list.
              </>
            )}
          </h2>
          <div className="mt-6 flex items-start gap-4">
            <Leader length={54} className="mt-3 hidden md:flex" />
            <Body>
              Nineteen primitives across five stages compose into 444,573 valid chains.
              That number is the space the red team searches, not a denominator: implemented
              over valid would read as failure for any grammar worth having. Coverage is
              stated along the axes instead.
            </Body>
          </div>

          <div className="mt-8 grid grid-cols-2 gap-x-8 gap-y-4 sm:grid-cols-4">
            <Figure label="Vectors" value={String(vectors.length)} note="generation 0" />
            <Figure label="Primitives" value={`${primitives.size}/19`} />
            <Figure label="Grid cells" value={`${cells.size}/343`} note="channel x capability x objective" />
            <Figure label="Chain space" value="444,573" />
          </div>

          <ul className="mt-10 border-t border-[var(--color-ink)]">
            {vectors.map((v, i) => {
              const on = v.vector_id === selected.vector_id;
              return (
                <li key={v.vector_id} className="border-b border-[var(--color-rule)]">
                  <button
                    onClick={() => selectVector(v.vector_id)}
                    className="hit group flex w-full items-baseline gap-4 py-3 text-left"
                    style={{ color: on ? 'var(--spot)' : undefined }}
                  >
                    <span className="mono w-8 text-[11px] text-[var(--color-ink-40)]">
                      {String(i + 1).padStart(2, '0')}
                    </span>
                    <span className="mono w-12 text-[11px]">{v.vector_id}</span>
                    <span className="flex-1 text-[15px] leading-tight">{v.name}</span>
                    <span className="tag hidden shrink-0 sm:block">
                      {v.channel.replace(/_/g, ' ')}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>

        {/* The plate hangs slightly out of the column, the way an annotation sits over a
            drawing rather than beside it. */}
        <div className="relative lg:-mt-16">
          <Plate title={selected.vector_id} index={`/${vectors.length}`} className="lg:-ml-8">
            <div className="text-[17px] leading-tight">{selected.name}</div>

            <div className="tag mt-4">documented incident</div>
            <p className="mt-1 text-[13px] leading-[1.5] text-[var(--color-ink-60)]">
              {selected.source.case}
            </p>
            {selected.source.stat && (
              <div className="mono mt-2 text-[15px]" style={{ color: 'var(--spot)' }}>
                {selected.source.stat}
              </div>
            )}
            <a
              href={selected.source.citation_url}
              target="_blank"
              rel="noreferrer"
              className="tag mt-2 block underline decoration-dotted underline-offset-2"
            >
              {selected.source.doc_ref}
            </a>

            <Hatch h={10} className="my-4" />

            <div className="tag">observable footprint</div>
            <p className="mt-1 text-[13px] leading-[1.5] text-[var(--color-ink-60)]">
              {selected.data_signature}
            </p>

            <div className="tag mt-4">chain</div>
            <ol className="mono mt-1 text-[11px]">
              {selected.chain.map((p, i) => (
                <li key={p + i} className="flex gap-2 border-b border-[var(--color-rule)] py-1">
                  <span className="text-[var(--color-ink-40)]">{i + 1}</span>
                  {p}
                </li>
              ))}
            </ol>
          </Plate>
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ 02 GENERATE */

export function Ledger() {
  const { bundle, perspective } = useStore();
  const attacker = perspective === 'attacker';

  const stats = useMemo(() => {
    if (!bundle) return null;
    const txns = bundle.ledger.tables.transactions;
    const times = txns.map((t) => Date.parse(t.timestamp));
    const min = Math.min(...times);
    const max = Math.max(...times);
    const bins = 60;
    const width = (max - min) / bins || 1;
    const legit = new Array(bins).fill(0);
    const fraud = new Array(bins).fill(0);
    for (const t of txns) {
      const i = Math.min(bins - 1, Math.floor((Date.parse(t.timestamp) - min) / width));
      if (t.is_fraud) fraud[i] += 1;
      else legit[i] += 1;
    }
    const peak = Math.max(...legit, 1);
    const fraudRows = txns.filter((t) => t.is_fraud);
    return {
      legit: legit.map((v) => v / peak),
      fraud: fraud.map((v) => v / peak),
      total: txns.length,
      nFraud: fraudRows.length,
      prevalence: fraudRows.length / txns.length,
      value: fraudRows.reduce((s, t) => s + t.amount_inr, 0),
    };
  }, [bundle]);

  if (!bundle || !stats) return <Skeleton rows={4} label="reading the ledger" />;

  return (
    <section id="ledger" className="relative z-10 pt-28">
      <SectionMark index="02" title="Generate" note="single-source simulator" />

      <div className="mt-10 grid gap-10 lg:grid-cols-[1fr_1.4fr]">
        <div className="lg:sticky lg:top-24 lg:self-start">
          <h2 className="display text-[clamp(2.2rem,4.6vw,3.6rem)]">
            {attacker ? 'Volume is the cover.' : 'One in a hundred.'}
          </h2>
          <Body>
            <span className="mt-5 block">
              Both populations leave the same simulator through the same write path. Mixing
              public-dataset rows with generated fraud lets a tree separate them on timestamp
              precision and amount rounding, and report an F1 near 0.99 that learned only
              which program wrote each row.
            </span>
          </Body>
          <div className="mt-6 grid grid-cols-2 gap-x-8 gap-y-4">
            <Figure label="Rows in slice" value={stats.total.toLocaleString()} />
            <Figure label="Fraudulent" value={stats.nFraud.toLocaleString()} />
            <Figure label="Prevalence" value={pct(stats.prevalence, 2)} note="stated beside every metric" />
            <Figure label="Value at risk" value={formatInr(stats.value)} />
          </div>
        </div>

        <div>
          <div className="tag mb-2">volume per interval, fraud marked below the rule</div>
          <svg viewBox="0 0 640 260" className="w-full">
            {stats.legit.map((v, i) => (
              <rect
                key={`l${i}`}
                x={i * (640 / stats.legit.length)}
                y={130 - v * 110}
                width={640 / stats.legit.length - 1.5}
                height={Math.max(v * 110, 0.6)}
                fill="var(--color-ink)"
                opacity={0.24}
              />
            ))}
            <line x1={0} x2={640} y1={130} y2={130} stroke="var(--color-ink)" strokeWidth={1} />
            {stats.fraud.map((v, i) =>
              v > 0 ? (
                <rect
                  key={`f${i}`}
                  x={i * (640 / stats.fraud.length)}
                  y={130}
                  width={640 / stats.fraud.length - 1.5}
                  height={Math.max(v * 110 * 8, 3)}
                  fill="var(--spot)"
                />
              ) : null
            )}
            <text x={4} y={124} className="mono" fontSize={9} fill="var(--color-ink-40)">
              LEGITIMATE
            </text>
            <text x={4} y={144} className="mono" fontSize={9} fill="var(--spot)">
              FRAUD, SCALED x8 TO BE VISIBLE AT ALL
            </text>
          </svg>
          <div className="tag mt-3 max-w-[54ch] normal-case tracking-normal">
            The fraud row is multiplied eightfold to be visible. At true scale it is a few
            pixels, which is the honest picture of the problem and the reason a fixture built
            at fifty percent fraud would have taught this view the wrong shape.
          </div>
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ 03 GRAPH */

export function Nebula() {
  const { bundle, perspective } = useStore();
  const attacker = perspective === 'attacker';
  const reduced = usePrefersReducedMotion();
  const [nebulaRef, nebulaNear] = useNearViewport<HTMLDivElement>();

  const graph = useMemo(() => {
    if (!bundle) return null;
    const { accounts, graph_edges } = bundle.ledger.tables;
    const mules = new Set(accounts.filter((a) => a.label_is_mule).map((a) => a.account_id));
    const transfers = graph_edges.filter((e) => e.edge_type === 'transfer');

    const nodes = new Map<string, { id: string; in: number; out: number; di: number; do: number }>();
    const touch = (id: string) => {
      let n = nodes.get(id);
      if (!n) nodes.set(id, (n = { id, in: 0, out: 0, di: 0, do: 0 }));
      return n;
    };
    for (const e of transfers) {
      const s = touch(e.source_account);
      const t = touch(e.target_account);
      s.out += e.amount_inr;
      s.do += 1;
      t.in += e.amount_inr;
      t.di += 1;
    }
    const scored = [...nodes.values()].map((n) => {
      const total = n.in + n.out;
      const passthrough = total > 0 && n.in > 0 && n.out > 0 ? 1 - Math.abs(n.in - n.out) / total : 0;
      return { ...n, passthrough, degree: n.di + n.do, isMule: mules.has(n.id) };
    });
    const ranked = scored
      .filter((n) => n.degree >= 2)
      .sort((a, b) => b.passthrough * b.degree - a.passthrough * a.degree)
      .slice(0, 260);
    const keep = new Set(ranked.map((n) => n.id));
    return {
      nodes: ranked,
      edges: transfers.filter((e) => keep.has(e.source_account) && keep.has(e.target_account)),
      flagged: ranked.filter((n) => n.passthrough > 0.85 && n.degree >= 3).length,
      mules: mules.size,
      accounts: accounts.length,
      transfers: transfers.length,
    };
  }, [bundle]);

  if (!bundle || !graph) return <Skeleton rows={4} label="building the account graph" />;

  // Node and edge lists for the 3D layout, indexed rather than keyed by id so the force
  // simulation can work on flat arrays.
  const index = new Map(graph.nodes.map((n, i) => [n.id, i]));
  const nodes3d = graph.nodes.map((n) => ({
    id: n.id,
    passthrough: n.passthrough,
    degree: n.degree,
    isMule: n.isMule,
  }));
  const edges3d = graph.edges
    .map((e) => ({ source: index.get(e.source_account), target: index.get(e.target_account) }))
    .filter((e): e is { source: number; target: number } =>
      e.source !== undefined && e.target !== undefined && e.source !== e.target
    );

  const W = 620;
  const H = 420;
  const pos = new Map(
    graph.nodes.map((n, i) => {
      const a = (i / graph.nodes.length) * Math.PI * 2 - Math.PI / 2;
      const r = n.passthrough > 0.8 ? 108 : 178;
      return [n.id, { x: W / 2 + Math.cos(a) * r, y: H / 2 + Math.sin(a) * r }] as const;
    })
  );

  return (
    <section id="nebula" className="relative z-10 pt-28">
      <SectionMark index="03" title="Graph" note="the level a row cannot represent" />

      <div className="mt-10 grid gap-10 lg:grid-cols-[1.2fr_1fr]">
        <div className="relative" ref={nebulaRef} style={{ minHeight: 460 }}>
          {nebulaNear ? (
            <Suspense
              fallback={<div className="tag grid h-[460px] place-items-center">loading the graph</div>}
            >
              <AccountNebula3D
                nodes={nodes3d}
                edges={edges3d}
                attacker={attacker}
                reduced={reduced}
              />
            </Suspense>
          ) : (
            <div className="tag grid h-[460px] place-items-center">graph loads on approach</div>
          )}

          <div className="tag mt-6 mb-2">flat projection, the reduced-motion path</div>
          <svg viewBox={`0 0 ${W} ${H}`} className="w-full">
            <rect x={0.5} y={0.5} width={W - 1} height={H - 1} fill="none" stroke="var(--color-rule)" />
            {graph.edges.map((e, i) => {
              const a = pos.get(e.source_account)!;
              const b = pos.get(e.target_account)!;
              return (
                <line
                  key={i}
                  x1={a.x}
                  y1={a.y}
                  x2={b.x}
                  y2={b.y}
                  stroke="var(--color-ink)"
                  strokeWidth={0.6}
                  opacity={0.3}
                />
              );
            })}
            {graph.nodes.map((n) => {
              const p = pos.get(n.id)!;
              const hot = n.passthrough > 0.85;
              const s = 4 + Math.min(6, n.degree * 0.5);
              return hot ? (
                <rect key={n.id} x={p.x - s / 2} y={p.y - s / 2} width={s} height={s} fill="var(--spot)">
                  <title>
                    {n.id} pass-through {(n.passthrough * 100).toFixed(0)}%
                  </title>
                </rect>
              ) : (
                <circle key={n.id} cx={p.x} cy={p.y} r={s / 2} fill="none" stroke="var(--color-ink)" strokeWidth={1}>
                  <title>{n.id}</title>
                </circle>
              );
            })}
            <text x={12} y={20} className="mono" fontSize={9} fill="var(--color-ink-40)">
              INNER RING / PASS-THROUGH &gt; 0.80
            </text>
          </svg>
        </div>

        <div>
          <h2 className="display text-[clamp(2rem,4.2vw,3.2rem)]">
            {attacker ? 'A route with no resting place.' : 'A shape, not a row.'}
          </h2>
          <Body>
            <span className="mt-5 block">
              Mastercard's AI Garage doubled compromised-card detection by combining generative
              AI with graph technology over relationships between accounts, devices and cards.
              Mule layering is a topology: fan-out, short cycles, accounts defined by what they
              never do, which is hold a balance.
            </span>
          </Body>

          <div className="mt-6 grid grid-cols-2 gap-x-8 gap-y-4">
            <Figure label="Accounts" value={graph.accounts.toLocaleString()} />
            <Figure label="Transfer edges" value={graph.transfers.toLocaleString()} />
            <Figure label="Pass-through flagged" value={String(graph.flagged)} note="in/out within 15%" />
            <Figure label="Mule accounts" value={String(graph.mules)} note="ground truth, never a feature" />
          </div>

          <Plate title="graph features" index="06" className="mt-8">
            <ol className="mono text-[11px]">
              {[
                'degree ratio, fan-in over fan-out, 24h',
                'pass-through score',
                'cycle membership, length <= 4',
                'shortest path to a flagged node',
                'community density',
                'shared-device edges between unrelated accounts',
              ].map((f, i) => (
                <li key={f} className="flex gap-3 border-b border-[var(--color-rule)] py-1 last:border-0">
                  <span className="text-[var(--color-ink-40)]">{String(i + 1).padStart(2, '0')}</span>
                  {f}
                </li>
              ))}
            </ol>
            <div className="tag mt-3 normal-case tracking-normal">
              <Placeholder id="P-06" what="graph level is specified, not yet computed by the detector" />
            </div>
          </Plate>
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ 04 DEFEND */

export function Surface() {
  const { bundle, perspective, threshold, setThreshold, generation } = useStore();
  const attacker = perspective === 'attacker';

  const curve = useMemo(() => {
    if (!bundle) return [];
    const gen = bundle.manifest.generations[Math.min(generation, bundle.manifest.generations.length - 1)];
    const { recall, precision, alert_rate } = gen.metrics_seen;
    const cost = bundle.manifest.cost_model.review_cost_inr;
    const fraudValue = gen.metrics_seen.net_value_protected_inr ?? 1e7;
    const n = bundle.ledger.tables.transactions.length;
    return Array.from({ length: 41 }, (_, i) => {
      const t = i / 40;
      return {
        threshold: t,
        recall: Math.min(0.995, recall * Math.pow(1 - t, 0.55) * 1.9),
        precision: Math.min(0.98, precision * Math.pow(t + 0.05, 0.45) * 2.2),
        net: fraudValue * Math.min(0.995, recall * Math.pow(1 - t, 0.55) * 1.9)
          - Math.max(0.0002, alert_rate * Math.pow(1 - t, 1.6) * 2.4) * n * cost,
      };
    });
  }, [bundle, generation]);

  const shap = useMemo(() => {
    const misses = bundle?.misses.find((m) => m.generation === generation) ?? bundle?.misses[0];
    return misses?.misses[0] ?? null;
  }, [bundle, generation]);

  if (!bundle || !curve.length) return <Skeleton rows={4} label="reading detector output" />;

  const at = curve.reduce((b, r) => (Math.abs(r.threshold - threshold) < Math.abs(b.threshold - threshold) ? r : b));
  const baseline = bundle.manifest.baseline.metrics;

  return (
    <section id="surface" className="relative z-10 pt-28">
      <SectionMark index="04" title="Defend" note="threshold as an economic choice" />

      <div className="mt-10 grid gap-10 lg:grid-cols-[1fr_1.3fr]">
        <div>
          <h2 className="display text-[clamp(2rem,4.2vw,3.2rem)]">
            {attacker ? 'The gap under the line.' : 'Where the money says to stand.'}
          </h2>
          <Body>
            <span className="mt-5 block">
              Net value protected is the value of fraud caught less the cost of reviewing false
              positives, at 250 rupees a review. Moving the threshold moves the money, which is
              the version of this a payments operator can act on.
            </span>
          </Body>

          <div className="mt-8 flex items-center gap-4">
            <span className="tag w-20">threshold</span>
            <input
              type="range"
              min={0}
              max={1}
              step={0.025}
              value={threshold}
              onChange={(e) => setThreshold(Number(e.target.value))}
              className="flex-1"
            />
            <span className="mono w-14 text-right text-[13px]">{threshold.toFixed(3)}</span>
          </div>

          <div className="mt-6 grid grid-cols-2 gap-x-8 gap-y-4">
            <Figure label="Recall" value={pct(at.recall)} lift={lift(at.recall, baseline.recall)} />
            <Figure label="Precision" value={pct(at.precision)} lift={lift(at.precision, baseline.precision)} />
            <Figure label="Net value protected" value={formatInr(at.net)} />
            <Figure
              label="Scoring latency"
              value={`${bundle.manifest.generations[0].metrics_seen.scoring_latency_p50_ms ?? 'n/a'} ms`}
              note="p50, inside an authorisation budget"
            />
          </div>
        </div>

        <div>
          <div className="mb-2 flex items-center justify-between">
            <span className="tag">threshold sweep</span>
            <Placeholder id="P-01" what="extrapolated from one measured operating point" />
          </div>
          <LinePlot
            xLabels={['0', '.25', '.50', '.75', '1']}
            series={[
              { label: 'recall', values: curve.filter((_, i) => i % 10 === 0).map((r) => r.recall), spot: true },
              { label: 'precision', values: curve.filter((_, i) => i % 10 === 0).map((r) => r.precision), dashed: true },
            ]}
          />

          <Plate title="why this alert scored as it did" index="shap" className="mt-8">
            {shap ? (
              <>
                <div className="mono mb-2 text-[10px] text-[var(--color-ink-40)]">
                  {shap.instance_id} · {shap.vector_id} · score {shap.score.toFixed(3)}
                </div>
                <ContributionPlot rows={[...shap.top_shap].sort((a, b) => b.value - a.value).slice(0, 6)} />
                <div className="tag mt-2 normal-case tracking-normal">
                  Bars left of the rule pushed this instance towards legitimate. Those are what
                  the red team targets next.
                </div>
              </>
            ) : (
              <Skeleton rows={3} label="no miss log yet" />
            )}
          </Plate>
        </div>
      </div>
    </section>
  );
}

/**
 * The 3D helix is lazy-loaded and only ever additive. The 2D curve below it stays, and
 * is the whole view under reduced motion or on a machine without a usable GPU. That is
 * the venue fallback, and it is why the 2D path was built first.
 */
const LoopHelix3D = lazy(() => import('../three/LoopHelix3D'));
const AccountNebula3D = lazy(() => import('../three/AccountNebula3D'));

/**
 * Mount the 3D scene only once its section is near the viewport.
 *
 * three.js is 238KB gzipped. Loading it during the initial paint would spend the entire
 * three-second budget on a scene that is several screens down the page, so the chunk is
 * not fetched until the reader is nearly there.
 */
function useNearViewport<T extends HTMLElement>(margin = '600px') {
  const ref = useRef<T>(null);
  const [near, setNear] = useState(false);
  useEffect(() => {
    const node = ref.current;
    if (!node || near) return;
    const observer = new IntersectionObserver(
      (entries) => entries.forEach((e) => e.isIntersecting && setNear(true)),
      { rootMargin: margin }
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [near, margin]);
  return [ref, near] as const;
}

function usePrefersReducedMotion(): boolean {
  return useSyncExternalStore(
    (cb) => {
      const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
      mq.addEventListener('change', cb);
      return () => mq.removeEventListener('change', cb);
    },
    () => window.matchMedia('(prefers-reduced-motion: reduce)').matches,
    () => false
  );
}

/* ------------------------------------------------------------------ 05 THE LOOP */

export function Helix() {
  const { bundle, perspective, generation, setGeneration } = useStore();
  const attacker = perspective === 'attacker';
  const reduced = usePrefersReducedMotion();
  const [helixRef, helixNear] = useNearViewport<HTMLDivElement>();
  if (!bundle) return <Skeleton rows={5} label="reading the run manifest" />;

  const { manifest, misses } = bundle;
  const gens = manifest.generations;
  const current = gens[Math.min(generation, gens.length - 1)];
  const baseline = manifest.baseline.metrics;
  const gMisses = misses.find((m) => m.generation === current.generation);
  const perVector = [...(gMisses?.per_vector ?? [])].sort((a, b) => a.detection_rate - b.detection_rate);

  return (
    <section id="helix" className="relative z-10 pt-28">
      <SectionMark index="05" title="The loop" note="the novelty claim" />

      <div className="mt-10">
        <h2 className="display max-w-[18ch] text-[clamp(2.6rem,6vw,5rem)]">
          {attacker ? (
            <>
              Each round I lose
              <br />a little more <span className="inverted">ground</span>.
            </>
          ) : (
            <>
              The detector learns
              <br />
              from its own <span className="boxed">failures</span>.
            </>
          )}
        </h2>
      </div>

      <div className="mt-8" ref={helixRef} style={{ minHeight: 460 }}>
        {helixNear ? (
          <Suspense
            fallback={
              <div className="tag grid h-[460px] place-items-center">loading the helix</div>
            }
          >
            <LoopHelix3D
              generations={gens}
              misses={misses}
              selected={current.generation}
              attacker={attacker}
              reduced={reduced}
            />
          </Suspense>
        ) : (
          <div className="tag grid h-[460px] place-items-center">helix loads on approach</div>
        )}
      </div>

      <div className="mt-10 grid gap-10 lg:grid-cols-[1.4fr_1fr]">
        <div>
          <div className="tag mb-2">detection rate per generation, flat view</div>
          <LinePlot
            xLabels={gens.map((g) => `G${g.generation}`)}
            series={[
              {
                label: attacker ? 'evaded' : 'detected',
                values: gens.map((g) => (attacker ? 1 - (g.detection_rate ?? 0) : g.detection_rate ?? 0)),
                spot: true,
              },
              { label: 'recall seen', values: gens.map((g) => g.metrics_seen.recall), dashed: true },
              { label: 'recall unseen', values: gens.map((g) => g.metrics_unseen.recall), dashed: true },
            ]}
            height={230}
          />

          <div className="mt-4 flex flex-wrap gap-2">
            {gens.map((g) => (
              <button
                key={g.generation}
                onClick={() => setGeneration(g.generation)}
                className="hit mono border px-2 py-1 text-[11px]"
                style={{
                  borderColor: g.generation === current.generation ? 'var(--spot)' : 'var(--color-ink-20)',
                  color: g.generation === current.generation ? 'var(--spot)' : 'var(--color-ink-60)',
                }}
              >
                G{g.generation}
              </button>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-x-8 gap-y-4 self-start">
          <Figure
            label="Recall, seen"
            value={pct(current.metrics_seen.recall)}
            lift={lift(current.metrics_seen.recall, baseline.recall)}
            note={`at ${pct(current.metrics_seen.prevalence, 2)} prevalence`}
          />
          <Figure
            label="Recall, unseen"
            value={pct(current.metrics_unseen.recall)}
            lift={lift(current.metrics_unseen.recall, baseline.recall)}
            note="held-out families, never merged"
          />
          <Figure
            label="AUC-PR"
            value={current.metrics_seen.auc_pr.toFixed(3)}
            lift={lift(current.metrics_seen.auc_pr, baseline.auc_pr)}
            note="the honest headline at low prevalence"
          />
          <Figure
            label="Instance recall"
            value={pct(current.detection_rate ?? 0)}
            note="an incident, not a row"
          />
        </div>
      </div>

      <div className="mt-12 grid gap-10 lg:grid-cols-2">
        <div>
          <div className="tag mb-3">per vector, weakest first</div>
          <ul className="border-t border-[var(--color-ink)]">
            {perVector.map((v) => (
              <li key={v.vector_id} className="flex items-center gap-3 border-b border-[var(--color-rule)] py-2">
                <span className="mono w-12 text-[11px]">{v.vector_id}</span>
                <span className="relative h-[7px] flex-1 border border-[var(--color-ink-20)]">
                  <span
                    className="absolute inset-y-0 left-0"
                    style={{
                      width: `${(attacker ? 1 - v.detection_rate : v.detection_rate) * 100}%`,
                      background: 'var(--spot)',
                    }}
                  />
                </span>
                <span className="mono w-12 text-right text-[11px]">
                  {pct(attacker ? 1 - v.detection_rate : v.detection_rate, 0)}
                </span>
              </li>
            ))}
          </ul>
        </div>

        <Plate title="validation layer" index="07">
          <div className="grid grid-cols-2 gap-6">
            <Figure label="Chains proposed" value={String(current.n_chains_proposed ?? 0)} />
            <Figure label="Chains rejected" value={String(current.n_chains_rejected ?? 0)} />
          </div>
          <p className="mt-4 text-[13px] leading-[1.5] text-[var(--color-ink-60)]">
            Every chain the strategist returns is validated against the grammar, deduplicated
            against existing vector ids, and plausibility checked before the simulator touches
            it. The rejection rate is reported rather than hidden: a model that needs heavy
            filtering is a finding about the method.
          </p>
        </Plate>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ 06 EVIDENCE */

export function Mirror() {
  const { bundle, perspective } = useStore();
  const attacker = perspective === 'attacker';
  if (!bundle) return <Skeleton rows={4} label="reading the fidelity report" />;

  const f = bundle.manifest.fidelity;
  const ks = Object.entries(f.ks_per_column ?? {});
  const auc = f.discriminator_auc;

  return (
    <section id="mirror" className="relative z-10 pt-28">
      <SectionMark index="06" title="Evidence" note="fidelity as a number" />

      <div className="mt-10 grid gap-10 lg:grid-cols-[1fr_1fr]">
        <div>
          <h2 className="display text-[clamp(2rem,4.2vw,3.2rem)]">
            {attacker ? 'Does the forgery survive inspection?' : 'Comparing histograms is not evidence.'}
          </h2>
          <Body>
            <span className="mt-5 block">
              A classifier is trained to do one thing: tell our rows from reference rows. If it
              cannot, that is a number worth reporting. The behavioural telemetry is excluded
              from it, because neither IEEE-CIS nor PaySim contains session timing or
              interaction data to compare against.
            </span>
          </Body>

          <div className="mt-8">
            <div className="tag mb-2">discriminator</div>
            <div className="relative h-8 border border-[var(--color-ink)]">
              <div className="absolute inset-y-0 left-1/2 w-px bg-[var(--color-ink)]" />
              {auc != null && (
                <div
                  className="absolute inset-y-0"
                  style={{ left: '50%', width: `${Math.abs(auc - 0.5) * 100}%`, background: 'var(--spot)' }}
                />
              )}
              {auc == null && (
                <div className="mono flex h-full items-center justify-center text-[11px] text-[var(--color-ink-40)]">
                  PENDING / NO REFERENCE PROFILE ON DISK
                </div>
              )}
            </div>
            <div className="mt-1 flex justify-between">
              <span className="tag">0.50 indistinguishable</span>
              <span className="tag">1.00 obviously synthetic</span>
            </div>
          </div>
        </div>

        <div>
          {ks.length > 0 ? (
            <>
              <div className="tag mb-2">two-sample kolmogorov-smirnov, per column</div>
              <BarPlot labels={ks.map(([k]) => k)} values={ks.map(([, v]) => v)} format={(v) => v.toFixed(3)} />
            </>
          ) : (
            <Skeleton rows={3} label="no per-column statistics yet" />
          )}

          <Plate title="scope of the claim" index="/2" className="mt-8">
            <div className="tag">compared against reference</div>
            <div className="mono mt-1 text-[11px]">{f.comparable_columns.join(', ')}</div>
            <Hatch h={8} className="my-3" />
            <div className="tag">excluded, no reference analogue</div>
            <div className="mono mt-1 text-[11px] text-[var(--color-ink-40)]">
              {f.excluded_columns.join(', ')}
            </div>
          </Plate>
        </div>
      </div>
    </section>
  );
}
