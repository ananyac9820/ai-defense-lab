import { useEffect, useRef, useState } from 'react';
import { ENVIRONMENTS, useStore } from './lib/store';
import { FixtureMark, Hatch, Leader, Plate, SectionMark } from './components/plate';
import { Constellation, Helix, Ledger, Mirror, Nebula, Surface } from './sections/Sections';
import { Legal } from './pages/Legal';
import { prefersReducedMotion, remeasure } from './lib/motion';
import { useTrack } from './lib/useMotion';

/**
 * One continuous document.
 *
 * There is no page switch and no panel that replaces another. The six views are sections
 * of a single scroll laid over one fixed hairline ground, and each one overlaps the last
 * so the boundaries are never drawn. Terms and privacy are the only separate routes,
 * because they are documents rather than views.
 */

/**
 * A full-bleed ground with the content held to the measure inside it.
 *
 * Three depths of hairline field move at different rates, and the ink ground wipes in
 * through the band's own top padding rather than at a fixed line. The wipe deliberately
 * covers only padding and decorative zones: text never crosses a moving edge, because a
 * contrast ratio that dips to 4:1 for half a second looks fine on a desk and is
 * unreadable from the back of a room.
 */
function Band({ tone, children }: { tone: 'paper' | 'ink'; children: React.ReactNode }) {
  const wipe = useTrack<HTMLDivElement>('enter');
  return (
    <div className={`band band-${tone}`}>
      {tone === 'ink' && <div ref={wipe} className="band-wipe" aria-hidden />}
      <div className="depth-fore" aria-hidden />
      <div className="mx-auto max-w-[1360px] px-6">{children}</div>
    </div>
  );
}

/**
 * Pointer presence. One fixed element, transform only, written outside React so moving
 * the mouse never renders. It sits below the content layer and only ever brightens the
 * hairline field, so it cannot touch the contrast of any text.
 */
function Reticle() {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (prefersReducedMotion()) return;
    const el = ref.current;
    if (!el) return;
    let frame = 0;
    let x = 0;
    let y = 0;
    const move = (e: PointerEvent) => {
      x = e.clientX;
      y = e.clientY;
      if (!frame) {
        frame = requestAnimationFrame(() => {
          frame = 0;
          el.style.setProperty('--mx', `${x}px`);
          el.style.setProperty('--my', `${y}px`);
        });
      }
    };
    window.addEventListener('pointermove', move, { passive: true });
    return () => {
      window.removeEventListener('pointermove', move);
      if (frame) cancelAnimationFrame(frame);
    };
  }, []);
  return <div ref={ref} className="reticle" aria-hidden />;
}

function useHashRoute(): string {
  const [route, setRoute] = useState(() => window.location.hash.replace(/^#\/?/, ''));
  useEffect(() => {
    const onChange = () => setRoute(window.location.hash.replace(/^#\/?/, ''));
    window.addEventListener('hashchange', onChange);
    return () => window.removeEventListener('hashchange', onChange);
  }, []);
  return route;
}

function Inversion() {
  const { perspective, flip } = useStore();
  const attacker = perspective === 'attacker';
  return (
    <button
      onClick={flip}
      className="hit mono flex items-stretch border border-[var(--fg)] text-[11px] uppercase tracking-[0.1em]"
      aria-label={`Switch to ${attacker ? 'defender' : 'attacker'} view`}
    >
      <span
        className="px-2.5 py-1.5"
        style={{
          background: attacker ? 'transparent' : '#0f5c4a',
          color: attacker ? 'var(--fg-3)' : '#f3f2ee',
        }}
      >
        Defender
      </span>
      <span
        className="border-l border-[var(--fg)] px-2.5 py-1.5"
        style={{
          background: attacker ? '#c43d18' : 'transparent',
          color: attacker ? '#f3f2ee' : 'var(--fg-3)',
        }}
      >
        Attacker
      </span>
    </button>
  );
}

function Header() {
  const { bundle } = useStore();
  return (
    <header className="band band-paper sticky top-0 z-30 border-b border-[var(--fg)]">
      <div className="mx-auto flex max-w-[1360px] items-center gap-4 px-6 py-2.5">
        <a href="#/" className="mono text-[11px] uppercase tracking-[0.2em]">
          AI Defense Lab
        </a>
        <span className="tag hidden md:inline">Team Code Ops / GFF 2026</span>
        <nav className="mono ml-auto hidden gap-4 text-[11px] uppercase tracking-[0.1em] lg:flex">
          {ENVIRONMENTS.map((e) => (
            <a key={e.id} href={`#${e.id}`} className="hit text-[var(--fg-2)]">
              {e.index} {e.pillar}
            </a>
          ))}
        </nav>
        <FixtureMark on={bundle?.manifest.is_fixture ?? false} />
        <Inversion />
      </div>
    </header>
  );
}

function Masthead() {
  const { bundle, perspective } = useStore();
  const attacker = perspective === 'attacker';
  const m = bundle?.manifest;

  return (
    <section className="relative z-10 pt-10 pb-12">
      <div className="grid gap-8 lg:grid-cols-[1.6fr_1fr]">
        <div>
          <div className="tag">Mastercard Innovation Challenge / submission dossier</div>
          <h1 className="display mt-4 text-[clamp(3rem,9vw,7.5rem)]">
            RED TEAM,
            <br />
            BY DESIGN.
          </h1>
          <div className="mt-5 flex items-start gap-4">
            <Leader length={70} className="mt-3 hidden md:flex" />
            <p className="max-w-[52ch] text-[15px] leading-[1.55] text-[var(--fg-2)]">
              We play the attacker and the defender, and make each one improve the other. The
              same world, read from either side: a mule network is a route from one and a
              detection surface from the other.{' '}
              {attacker ? 'You are reading the attacker side.' : 'You are reading the defender side.'}
            </p>
          </div>
        </div>

        <div className="relative">
          <Plate title="run" index={m ? `seed ${m.seed}` : 'n/a'} className="lg:-mr-4">
            {m ? (
              <dl className="mono text-[11px]">
                {[
                  ['run id', m.run_id],
                  ['prevalence', `${(m.prevalence * 100).toFixed(3)}%`],
                  ['config hash', m.config_hash.slice(0, 16)],
                  ['generations', String(m.generations.length)],
                  ['review cost', `INR ${m.cost_model.review_cost_inr}`],
                ].map(([k, v]) => (
                  <div
                    key={k}
                    className="flex justify-between border-b border-[var(--rule)] py-1 last:border-0"
                  >
                    <dt className="text-[var(--fg-3)]">{k}</dt>
                    <dd>{v}</dd>
                  </div>
                ))}
              </dl>
            ) : (
              <div className="mono text-[11px] text-[var(--fg-3)]">reading run manifest</div>
            )}
          </Plate>

          <Plate title="scope boundary" index="s9" className="mt-4 lg:ml-10">
            <p className="text-[12px] leading-[1.5] text-[var(--fg-2)]">
              This repository generates synthetic data. It does not generate attack tooling.
              Records, session events and graph edges, in full detail. No voice cloning, no
              phishing generators, no deepfake code, nothing that can reach a live endpoint.
            </p>
          </Plate>
        </div>
      </div>

      <Hatch h={14} className="mt-10" />
    </section>
  );
}

function Colophon() {
  const { bundle } = useStore();
  return (
    <section id="colophon" className="relative z-10 pt-14 pb-16">
      <SectionMark index="07" title="Colophon" />
      <div className="mt-6 grid gap-8 lg:grid-cols-3">
        <div>
          <div className="tag">reproduction</div>
          <p className="mono mt-2 text-[11px] leading-relaxed">
            git clone …/ai-defense-lab
            <br />
            pip install -e ".[dev]"
            <br />
            python scripts/reproduce.py
          </p>
          <p className="mt-3 text-[13px] leading-[1.5] text-[var(--fg-2)]">
            Every reported number regenerates from one command and one seed on a clean clone.
          </p>
        </div>
        <div>
          <div className="tag">reference data</div>
          <p className="mt-2 text-[13px] leading-[1.5] text-[var(--fg-2)]">
            IEEE-CIS and PaySim calibrate distributions. Neither supplies a row, and neither is
            redistributed here. Only the derived profile is committed.
          </p>
        </div>
        <div>
          <div className="tag">documents</div>
          <ul className="mono mt-2 text-[11px]">
            <li className="border-b border-[var(--rule)] py-1">
              <a className="hit underline underline-offset-2" href="#/terms">
                Terms of use
              </a>
            </li>
            <li className="border-b border-[var(--rule)] py-1">
              <a className="hit underline underline-offset-2" href="#/privacy">
                Privacy notice
              </a>
            </li>
            <li className="py-1">
              <a
                className="hit underline underline-offset-2"
                href="https://github.com/ananyac9820/ai-defense-lab"
                target="_blank"
                rel="noreferrer"
              >
                Repository
              </a>
            </li>
          </ul>
        </div>
      </div>
      <div className="tag mt-10 border-t border-[var(--fg)] pt-3">
        {bundle?.manifest.is_fixture
          ? 'Rendering fixture artefacts. Shapes are real; numbers are invented and marked.'
          : 'Rendering live artefacts from artifacts/published.'}
      </div>
    </section>
  );
}

export default function App() {
  const { error, load } = useStore();
  const route = useHashRoute();

  useEffect(() => {
    void load();
  }, [load]);

  // Artefacts arriving changes the height of nearly every section, so the scroll driver
  // has to re-measure or every progress value is computed against a stale layout.
  useEffect(() => {
    const id = window.setTimeout(remeasure, 120);
    return () => window.clearTimeout(id);
  }, [error]);

  if (route === 'terms' || route === 'privacy') {
    return (
      <>
        <Header />
        <main className="relative">
          <Band tone="paper">
            <Legal kind={route} />
          </Band>
        </main>
      </>
    );
  }

  return (
    <>
      <Reticle />
      <Header />
      <main className="relative">
        {error ? (
          <div className="plate mt-20 p-4" style={{ borderColor: '#c43d18' }}>
            <div className="tag" style={{ color: '#c43d18' }}>
              artefact load failed
            </div>
            <p className="mono mt-2 text-[12px]">{error}</p>
            <p className="tag mt-3 normal-case tracking-normal">
              Run npm run sync-data to copy artefacts into web/public/data.
            </p>
          </div>
        ) : (
          <>
            {/* Alternating grounds. The scroll needs a pulse: one continuous field reads
                as a default, and the paper sections only look deliberate once something
                else sits next to them. Even sections invert. */}
            <Band tone="paper"><Masthead /></Band>
            <Band tone="paper"><Constellation /></Band>
            <Band tone="ink"><Ledger /></Band>
            <Band tone="paper"><Nebula /></Band>
            <Band tone="ink"><Surface /></Band>
            <Band tone="paper"><Helix /></Band>
            <Band tone="ink"><Mirror /></Band>
            <Band tone="ink"><Colophon /></Band>
          </>
        )}
      </main>
    </>
  );
}
