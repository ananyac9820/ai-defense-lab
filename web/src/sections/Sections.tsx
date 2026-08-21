import { lazy, Suspense, useEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react';
import { Figure, Hatch, Hero, Leader, Placeholder, Plate, SectionMark, Skeleton } from '../components/plate';
import { BarPlot, ContributionPlot, LinePlot } from '../components/draw';
import { formatInr, lift, pct } from '../lib/data';
import { useStore } from '../lib/store';
import { useTrack } from '../lib/useMotion';

/**
 * The six views, written as sections of one document rather than pages of an app.
 *
 * Sections overlap deliberately: each one pulls up into the whitespace of the last and
 * hangs an annotation plate across the boundary, so the eye never meets a seam. The
 * hairline ground behind them never restarts, which is what actually does the bleeding.
 */

function Body({ children }: { children: React.ReactNode }) {
  return <p className="max-w-[62ch] text-[15px] leading-[1.55] text-[var(--fg-2)]">{children}</p>;
}

/* ------------------------------------------------------------------ 01 IDENTIFY */

export function Constellation() {
  const { bundle, perspective, selectedVector, selectVector } = useStore();
  const attacker = perspective === 'attacker';
  const vectorList = useTrack<HTMLUListElement>();
  if (!bundle) return <Skeleton rows={5} label="reading attacks.json" />;

  const vectors = bundle.attacks.vectors;
  const selected = vectors.find((v) => v.vector_id === selectedVector) ?? vectors[0];
  const primitives = new Set(vectors.flatMap((v) => v.chain));
  const cells = new Set(vectors.map((v) => `${v.channel}|${v.ai_capability}|${v.objective}`));

  return (
    <section id="constellation" className="relative z-10 pt-14 pb-16">
      <SectionMark index="01" title="Identify" note="compositional attack grammar" />

      <div className="mt-7 grid gap-8 lg:grid-cols-[1.35fr_1fr]">
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

          <Hero
            value="444,573"
            caption="valid chains in the grammar"
            note="The space the red team searches. Nineteen primitives, five stages, composition rules."
          />

          <div className="mt-7 grid grid-cols-2 gap-x-8 gap-y-4 sm:grid-cols-4">
            <Figure label="Vectors" value={String(vectors.length)} note="generation 0" />
            <Figure label="Primitives" value={`${primitives.size}/19`} />
            <Figure label="Grid cells" value={`${cells.size}/343`} note="channel x capability x objective" />
          </div>

          <ul ref={vectorList} className="stagger mt-7 border-t border-[var(--fg)]">
            {vectors.map((v, i) => {
              const on = v.vector_id === selected.vector_id;
              return (
                <li
                  key={v.vector_id}
                  className="border-b border-[var(--rule)]"
                  style={{ '--i': i } as React.CSSProperties}
                >
                  <button
                    onClick={() => selectVector(v.vector_id)}
                    className="hit group flex w-full items-baseline gap-4 py-3 text-left"
                    style={{ color: on ? 'var(--spot-sm)' : undefined }}
                  >
                    <span className="mono w-8 text-[11px] text-[var(--fg-3)]">
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
            <p className="mt-1 text-[13px] leading-[1.5] text-[var(--fg-2)]">
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
            <p className="mt-1 text-[13px] leading-[1.5] text-[var(--fg-2)]">
              {selected.data_signature}
            </p>

            <div className="tag mt-4">chain</div>
            <ol className="mono mt-1 text-[11px]">
              {selected.chain.map((p, i) => (
                <li key={p + i} className="flex gap-2 border-b border-[var(--rule)] py-1">
                  <span className="text-[var(--fg-3)]">{i + 1}</span>
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
  const ledgerFigure = useTrack<SVGSVGElement>();

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
    <section id="ledger" className="relative z-10 pt-14 pb-16">
      <SectionMark index="02" title="Generate" note="single-source simulator" />

      <div className="mt-7 grid gap-8 lg:grid-cols-[1fr_1.4fr]">
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
          <Hero
            value={pct(stats.prevalence, 2)}
            caption="fraud base rate"
            note="Stated beside every metric in this project, without exception."
          />
          <div className="mt-7 grid grid-cols-2 gap-x-8 gap-y-4">
            <Figure label="Rows in slice" value={stats.total.toLocaleString()} />
            <Figure label="Fraudulent" value={stats.nFraud.toLocaleString()} />
            <Figure label="Prevalence" value={pct(stats.prevalence, 2)} note="stated beside every metric" />
            <Figure label="Value at risk" value={formatInr(stats.value)} />
          </div>
        </div>

        <div>
          <div className="tag mb-2">volume per interval, fraud marked below the rule</div>
          <svg ref={ledgerFigure} viewBox="0 0 640 260" className="w-full">
            {stats.legit.map((v, i) => (
              <rect
                key={`l${i}`}
                x={i * (640 / stats.legit.length)}
                y={130 - v * 110}
                width={640 / stats.legit.length - 1.5}
                height={Math.max(v * 110, 0.6)}
                fill="var(--fg)"
                opacity={0.24}
              />
            ))}
            <line className="draw" pathLength={1} x1={0} x2={640} y1={130} y2={130} stroke="var(--fg)" strokeWidth={1} />
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
            <text x={4} y={122} className="mono" fontSize={11} fill="var(--fg-2)">
              LEGITIMATE
            </text>
            <text x={4} y={146} className="mono" fontSize={11} fill="var(--spot-sm)">
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
  const [nebulaRef, nebulaNear, loadNebula] = useNearViewport<HTMLDivElement>();
  const nebulaTrack = useTrack<HTMLDivElement>('cover');
  const nebulaProgress = useSceneProgress(nebulaTrack);

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
    <section id="nebula" className="relative z-10 pt-14 pb-16">
      <SectionMark index="03" title="Graph" note="the level a row cannot represent" />

      {/* Full bleed. The graph result is the payoff, so it gets the width of the page
          rather than a column inside it. */}
      <div ref={nebulaTrack} className="mt-7 -mx-6 md:-mx-10" style={{ minHeight: 520 }}>
       <div ref={nebulaRef}>
        {nebulaNear ? (
          <Suspense fallback={<div className="tag grid h-[520px] place-items-center">loading the graph</div>}>
            <AccountNebula3D
              nodes={nodes3d}
              edges={edges3d}
              attacker={attacker}
              reduced={reduced}
              progress={nebulaProgress}
            />
          </Suspense>
        ) : (
          <SceneGate label="the graph" onLoad={loadNebula} />
        )}
       </div>
      </div>

      <div className="mt-7 grid gap-8 lg:grid-cols-[1.2fr_1fr]">
        <div className="relative">
          <div className="tag mb-2">flat projection, the reduced-motion path</div>
          <svg viewBox={`0 0 ${W} ${H}`} className="w-full">
            <rect x={0.5} y={0.5} width={W - 1} height={H - 1} fill="none" stroke="var(--rule)" />
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
                  stroke="var(--fg)"
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
                <circle key={n.id} cx={p.x} cy={p.y} r={s / 2} fill="none" stroke="var(--fg)" strokeWidth={1}>
                  <title>{n.id}</title>
                </circle>
              );
            })}
            <text x={12} y={22} className="mono" fontSize={11} fill="var(--fg-2)">
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

          <Hero
            value={String(graph.flagged)}
            caption="pass-through accounts flagged"
            note="Money in and money out within 15%. Accounts defined by what they never do, which is hold a balance."
          />
          <div className="mt-7 grid grid-cols-2 gap-x-8 gap-y-4">
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
                <li key={f} className="flex gap-3 border-b border-[var(--rule)] py-1 last:border-0">
                  <span className="text-[var(--fg-3)]">{String(i + 1).padStart(2, '0')}</span>
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
    <section id="surface" className="relative z-10 pt-14 pb-16">
      <SectionMark index="04" title="Defend" note="threshold as an economic choice" />

      <div className="mt-7 grid gap-8 lg:grid-cols-[1fr_1.3fr]">
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

          <Hero
            value={formatInr(at.net).replace('INR ', '')}
            caption="net value protected, rupees"
            note="Fraud caught less the cost of reviewing false positives. Moving the threshold moves this number."
          />
          <div className="mt-7 grid grid-cols-2 gap-x-8 gap-y-4">
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
                <div className="mono mb-2 text-[11px] text-[var(--fg-2)]">
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
function useNearViewport<T extends HTMLElement>(margin = 600) {
  const ref = useRef<T>(null);
  const [near, setNear] = useState(false);

  useEffect(() => {
    if (near) return;
    const node = ref.current;
    if (!node) return;

    // Measured on scroll rather than through IntersectionObserver. The observer worked
    // locally and never fired on the deployed page under a driven browser, and a demo
    // whose centrepiece depends on one API behaving is a demo with a way to fail in a
    // room. A rect measurement on a passive scroll listener cannot not-fire.
    const check = () => {
      const rect = node.getBoundingClientRect();
      if (rect.top < window.innerHeight + margin && rect.bottom > -margin) setNear(true);
    };
    check();
    window.addEventListener('scroll', check, { passive: true });
    window.addEventListener('resize', check, { passive: true });
    return () => {
      window.removeEventListener('scroll', check);
      window.removeEventListener('resize', check);
    };
  }, [near, margin]);

  return [ref, near, () => setNear(true)] as const;
}

/** Placeholder that also lets a viewer force the scene, so nothing depends on scrolling. */
function SceneGate({ label, onLoad }: { label: string; onLoad: () => void }) {
  return (
    <div className="grid h-[460px] place-items-center border border-[var(--rule)]">
      <button onClick={onLoad} className="hit mono border border-[var(--fg)] px-3 py-1.5 text-[11px] uppercase tracking-[0.14em]">
        load {label}
      </button>
    </div>
  );
}

/**
 * Reads the scroll progress written onto an element by the driver. Passed to the 3D
 * scenes as a getter so they can sample it inside their own frame loop, which keeps the
 * whole camera path scroll-driven without React re-rendering at 60fps.
 */
function useSceneProgress(ref: React.RefObject<HTMLElement | null>) {
  return useMemo(
    () => () => {
      const el = ref.current;
      if (!el) return 1;
      return parseFloat(getComputedStyle(el).getPropertyValue('--p') || '0') || 0;
    },
    [ref]
  );
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
  const [helixRef, helixNear, loadHelix] = useNearViewport<HTMLDivElement>();
  const helixTrack = useTrack<HTMLDivElement>('cover');
  const helixProgress = useSceneProgress(helixTrack);
  if (!bundle) return <Skeleton rows={5} label="reading the run manifest" />;

  const { manifest, misses } = bundle;
  const gens = manifest.generations;
  const current = gens[Math.min(generation, gens.length - 1)];
  const baseline = manifest.baseline.metrics;
  const gMisses = misses.find((m) => m.generation === current.generation);
  const perVector = [...(gMisses?.per_vector ?? [])].sort((a, b) => a.detection_rate - b.detection_rate);

  return (
    <section id="helix" className="relative z-10 pt-14 pb-16">
      <SectionMark index="05" title="The loop" note="the novelty claim" />

      <div className="mt-7">
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

      <div ref={helixTrack} className="mt-7 -mx-6 md:-mx-10" style={{ minHeight: 520 }}>
       <div ref={helixRef}>
        {helixNear ? (
          <Suspense
            fallback={
              <div className="tag grid h-[520px] place-items-center">loading the helix</div>
            }
          >
            <LoopHelix3D
              generations={gens}
              misses={misses}
              selected={current.generation}
              attacker={attacker}
              reduced={reduced}
              progress={helixProgress}
            />
          </Suspense>
        ) : (
          <SceneGate label="the helix" onLoad={loadHelix} />
        )}
       </div>
      </div>

      <div className="mt-7 grid gap-8 lg:grid-cols-[1.4fr_1fr]">
        <div>
          <div className="tag mb-2">detection rate per generation, flat view</div>
          {/* Three series, because the obvious one cannot be read on its own. The current
              attack set changes composition every generation, so its line mixes "the
              detector improved" with "the mix got easier". The fixed set holds the
              population constant; the new-vectors line asks whether the attacker is still
              getting through. */}
          <LinePlot
            xLabels={gens.map((g) => `G${g.generation}`)}
            series={[
              {
                label: 'fixed evaluation set',
                values: gens.map((g) => g.detection_rate_fixed_set ?? g.detection_rate ?? 0),
                spot: true,
              },
              {
                label: 'new vectors only',
                values: gens.map((g) => g.detection_rate_new_vectors ?? NaN),
                dashed: true,
              },
              {
                label: 'current attack set',
                values: gens.map((g) => g.detection_rate ?? 0),
                dashed: true,
              },
            ]}
            height={230}
          />
          <div className="tag mt-2 max-w-[62ch] normal-case tracking-[0.02em]">
            Solid: generation 0's attack population scored by every generation's model, so
            movement means the detector moved. Dashed pale: only the vectors that
            generation introduced. Dashed dark: whatever the attack set happened to be
            that round, which is the line that cannot be read as a trend.
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            {gens.map((g) => (
              <button
                key={g.generation}
                onClick={() => setGeneration(g.generation)}
                className="hit mono border px-2 py-1 text-[11px]"
                style={{
                  borderColor: g.generation === current.generation ? 'var(--spot)' : 'var(--edge)',
                  color: g.generation === current.generation ? 'var(--spot-sm)' : 'var(--fg-2)',
                }}
              >
                G{g.generation}
              </button>
            ))}
          </div>
        </div>

        <div className="self-start">
          <Hero
            value={pct(current.detection_rate ?? 0, 1)}
            caption="instance recall"
            note="An incident, not a row. A sweep of twenty probes counts once."
          />
        </div>
      </div>

      <div className="mt-8 grid gap-8 lg:grid-cols-[1.4fr_1fr]">
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

      <div className="mt-8 grid gap-8 lg:grid-cols-2">
        <div>
          <div className="tag mb-3">per vector, weakest first</div>
          <ul className="border-t border-[var(--fg)]">
            {perVector.map((v) => (
              <li key={v.vector_id} className="flex items-center gap-3 border-b border-[var(--rule)] py-2">
                <span className="mono w-12 text-[11px]">{v.vector_id}</span>
                <span className="relative h-[7px] flex-1 border border-[var(--edge)]">
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
          <p className="mt-4 text-[13px] leading-[1.5] text-[var(--fg-2)]">
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
    <section id="mirror" className="relative z-10 pt-14 pb-16">
      <SectionMark index="06" title="Evidence" note="fidelity as a number" />

      <div className="mt-7 grid gap-8 lg:grid-cols-[1fr_1fr]">
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

          <Hero
            value={auc == null ? 'PENDING' : auc.toFixed(3)}
            caption="discriminator AUC"
            note="0.50 means a classifier cannot tell our rows from reference rows. Pending until a reference profile is on disk."
          />
          <div className="mt-7">
            <div className="tag mb-2">discriminator</div>
            <div className="relative h-8 border border-[var(--fg)]">
              <div className="absolute inset-y-0 left-1/2 w-px bg-[var(--fg)]" />
              {auc != null && (
                <div
                  className="absolute inset-y-0"
                  style={{ left: '50%', width: `${Math.abs(auc - 0.5) * 100}%`, background: 'var(--spot)' }}
                />
              )}
              {auc == null && (
                <div className="mono flex h-full items-center justify-center text-[11px] text-[var(--fg-3)]">
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
            <div className="mono mt-1 text-[11px] text-[var(--fg-3)]">
              {f.excluded_columns.join(', ')}
            </div>
          </Plate>
        </div>
      </div>
    </section>
  );
}
