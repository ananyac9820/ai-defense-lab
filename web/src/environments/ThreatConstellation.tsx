import { useMemo } from 'react';
import { Chip, Empty, GlassPanel, Metric } from '../components/ui';
import { useStore } from '../lib/store';

/**
 * Pillar 1, Identify (PDF S4).
 *
 * Coverage is stated along the axes rather than as implemented-over-valid: the grammar
 * admits hundreds of thousands of chains, so that fraction would read as failure rather
 * than as a deliberately small, axis-spread selection. What is defensible is which
 * primitives, which stage transitions and which grid cells are exercised.
 *
 * Every vector carries a real cited case, and the card surfaces it - requirement 4 of
 * the build brief, and the thing to say out loud in the demo.
 */
export default function ThreatConstellation() {
  const { bundle, perspective, selectedVector, selectVector } = useStore();
  const attacker = perspective === 'attacker';

  const grouped = useMemo(() => {
    if (!bundle) return [];
    const by = new Map<string, typeof bundle.attacks.vectors>();
    for (const v of bundle.attacks.vectors) {
      const list = by.get(v.channel) ?? [];
      list.push(v);
      by.set(v.channel, list);
    }
    return [...by.entries()].sort(([a], [b]) => a.localeCompare(b));
  }, [bundle]);

  if (!bundle) return <Empty what="attack taxonomy" />;
  const vectors = bundle.attacks.vectors;
  const selected = vectors.find((v) => v.vector_id === selectedVector) ?? vectors[0];

  const primitives = new Set(vectors.flatMap((v) => v.chain));
  const cells = new Set(vectors.map((v) => `${v.channel}|${v.ai_capability}|${v.objective}`));

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_24rem]">
      <div className="flex flex-col gap-6">
        <GlassPanel
          kicker={attacker ? 'the arsenal' : 'the attack surface'}
          title={attacker ? 'Chains available to compose' : 'Coverage of the grammar space'}
        >
          <div className="mb-5 grid grid-cols-2 gap-5 md:grid-cols-4">
            <Metric label="Vectors" value={vectors.length} hint="generation 0, hand-authored" />
            <Metric label="Primitives used" value={`${primitives.size} / 19`} />
            <Metric label="Grid cells" value={`${cells.size} / 343`} hint="channel × capability × objective" />
            <Metric label="Channels" value={`${grouped.length} / 7`} />
          </div>

          <div className="flex flex-col gap-4">
            {grouped.map(([channel, list]) => (
              <div key={channel}>
                <div className="label-caps mb-2">{channel.replace(/_/g, ' ')}</div>
                <div className="flex flex-wrap gap-2">
                  {list.map((v) => {
                    const active = v.vector_id === selected.vector_id;
                    return (
                      <button
                        key={v.vector_id}
                        onClick={() => selectVector(v.vector_id)}
                        className="glass max-w-sm px-4 py-3 text-left transition-transform hover:-translate-y-0.5"
                        style={{
                          borderColor: active
                            ? 'color-mix(in oklab, var(--accent) 55%, transparent)'
                            : undefined,
                          boxShadow: active
                            ? '0 0 0 1px color-mix(in oklab, var(--accent) 35%, transparent), 0 24px 60px -30px rgba(0,0,0,0.9)'
                            : undefined,
                        }}
                      >
                        <div className="tabular text-[11px]" style={{ color: 'var(--accent)' }}>
                          {v.vector_id}
                        </div>
                        <div className="mt-0.5 text-sm">{v.name}</div>
                        <div className="mt-2 flex flex-wrap gap-1">
                          {v.chain.map((p, i) => (
                            <span
                              key={`${p}-${i}`}
                              className="rounded px-1.5 py-0.5 text-[10px] text-[var(--color-slate)]"
                              style={{ border: '1px solid var(--color-edge)' }}
                            >
                              {p}
                            </span>
                          ))}
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </GlassPanel>
      </div>

      <GlassPanel kicker="grounded in a real case" title={selected.name}>
        <div className="mb-4 flex flex-wrap gap-2">
          <Chip tone="accent">{selected.vector_id}</Chip>
          <Chip>{selected.ai_capability.replace(/_/g, ' ')}</Chip>
          <Chip>{selected.objective.replace(/_/g, ' ')}</Chip>
          {selected.expected_levels.map((l) => (
            <Chip key={l}>{l} level</Chip>
          ))}
        </div>

        <div className="label-caps mb-1">real incident</div>
        <p className="text-sm leading-relaxed">{selected.source.case}</p>
        {selected.source.stat && (
          <div className="tabular mt-2 text-lg" style={{ color: 'var(--accent)' }}>
            {selected.source.stat}
          </div>
        )}
        <a
          href={selected.source.citation_url}
          target="_blank"
          rel="noreferrer"
          className="mt-2 block text-xs underline decoration-dotted"
          style={{ color: 'var(--color-slate)' }}
        >
          {selected.source.doc_ref}
        </a>
        {selected.source.regulator_advisory && (
          <div className="mt-1 text-xs text-[var(--color-slate)]">
            advisory: {selected.source.regulator_advisory}
          </div>
        )}

        <div className="label-caps mt-5 mb-1">data signature</div>
        <p className="text-sm leading-relaxed text-[var(--color-slate)]">
          {selected.data_signature}
        </p>

        <div className="label-caps mt-5 mb-2">simulator parameters</div>
        <div className="flex flex-col gap-1">
          {Object.entries(selected.parameters).map(([k, v]) => (
            <div key={k} className="flex justify-between gap-3 text-xs">
              <span className="text-[var(--color-slate)]">{k}</span>
              <span className="tabular">{Array.isArray(v) ? v.join(' – ') : String(v)}</span>
            </div>
          ))}
        </div>
      </GlassPanel>
    </div>
  );
}
