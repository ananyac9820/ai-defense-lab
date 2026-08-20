import { useEffect, useState } from 'react';
import { ENVIRONMENTS, useStore } from './lib/store';
import { FixtureMark, Hatch, Leader, Plate, SectionMark } from './components/plate';
import { Constellation, Helix, Ledger, Mirror, Nebula, Surface } from './sections/Sections';
import { Legal } from './pages/Legal';

/**
 * One continuous document.
 *
 * There is no page switch and no panel that replaces another. The six views are sections
 * of a single scroll laid over one fixed hairline ground, and each one overlaps the last
 * so the boundaries are never drawn. Terms and privacy are the only separate routes,
 * because they are documents rather than views.
 */

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
      className="hit mono flex items-stretch border border-[var(--color-ink)] text-[10px] uppercase tracking-[0.16em]"
      aria-label={`Switch to ${attacker ? 'defender' : 'attacker'} view`}
    >
      <span
        className="px-2.5 py-1.5"
        style={{
          background: attacker ? 'transparent' : 'var(--color-defend)',
          color: attacker ? 'var(--color-ink-40)' : 'var(--color-paper)',
        }}
      >
        Defender
      </span>
      <span
        className="border-l border-[var(--color-ink)] px-2.5 py-1.5"
        style={{
          background: attacker ? 'var(--color-attack)' : 'transparent',
          color: attacker ? 'var(--color-paper)' : 'var(--color-ink-40)',
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
    <header className="sticky top-0 z-30 border-b border-[var(--color-ink)] bg-[var(--color-paper)]">
      <div className="mx-auto flex max-w-[1360px] items-center gap-4 px-6 py-2.5">
        <a href="#/" className="mono text-[11px] uppercase tracking-[0.2em]">
          AI Defense Lab
        </a>
        <span className="tag hidden md:inline">Team Code Ops / GFF 2026</span>
        <nav className="mono ml-auto hidden gap-4 text-[10px] uppercase tracking-[0.14em] lg:flex">
          {ENVIRONMENTS.map((e) => (
            <a key={e.id} href={`#${e.id}`} className="hit text-[var(--color-ink-60)]">
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
    <section className="relative z-10 pt-14">
      <div className="grid gap-8 lg:grid-cols-[1.5fr_1fr]">
        <div>
          <div className="tag">Mastercard Innovation Challenge / submission dossier</div>
          <h1 className="display mt-4 text-[clamp(3rem,9vw,7.5rem)]">
            RED TEAM,
            <br />
            BY DESIGN.
          </h1>
          <div className="mt-6 flex items-start gap-4">
            <Leader length={70} className="mt-3 hidden md:flex" />
            <p className="max-w-[52ch] text-[15px] leading-[1.55] text-[var(--color-ink-60)]">
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
                    className="flex justify-between border-b border-[var(--color-rule)] py-1 last:border-0"
                  >
                    <dt className="text-[var(--color-ink-40)]">{k}</dt>
                    <dd>{v}</dd>
                  </div>
                ))}
              </dl>
            ) : (
              <div className="mono text-[11px] text-[var(--color-ink-40)]">reading run manifest</div>
            )}
          </Plate>

          <Plate title="scope boundary" index="s9" className="mt-6 lg:ml-10">
            <p className="text-[12px] leading-[1.5] text-[var(--color-ink-60)]">
              This repository generates synthetic data. It does not generate attack tooling.
              Records, session events and graph edges, in full detail. No voice cloning, no
              phishing generators, no deepfake code, nothing that can reach a live endpoint.
            </p>
          </Plate>
        </div>
      </div>

      <Hatch h={14} className="mt-16" />
    </section>
  );
}

function Colophon() {
  const { bundle } = useStore();
  return (
    <section id="colophon" className="relative z-10 pt-28 pb-20">
      <SectionMark index="07" title="Colophon" />
      <div className="mt-8 grid gap-10 lg:grid-cols-3">
        <div>
          <div className="tag">reproduction</div>
          <p className="mono mt-2 text-[11px] leading-relaxed">
            git clone …/ai-defense-lab
            <br />
            pip install -e ".[dev]"
            <br />
            python scripts/reproduce.py
          </p>
          <p className="mt-3 text-[13px] leading-[1.5] text-[var(--color-ink-60)]">
            Every reported number regenerates from one command and one seed on a clean clone.
          </p>
        </div>
        <div>
          <div className="tag">reference data</div>
          <p className="mt-2 text-[13px] leading-[1.5] text-[var(--color-ink-60)]">
            IEEE-CIS and PaySim calibrate distributions. Neither supplies a row, and neither is
            redistributed here. Only the derived profile is committed.
          </p>
        </div>
        <div>
          <div className="tag">documents</div>
          <ul className="mono mt-2 text-[11px]">
            <li className="border-b border-[var(--color-rule)] py-1">
              <a className="hit underline underline-offset-2" href="#/terms">
                Terms of use
              </a>
            </li>
            <li className="border-b border-[var(--color-rule)] py-1">
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
      <div className="tag mt-14 border-t border-[var(--color-ink)] pt-3">
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

  if (route === 'terms' || route === 'privacy') {
    return (
      <>
        <div className="ground" aria-hidden />
        <Header />
        <main className="relative mx-auto max-w-[1360px] px-6">
          <Legal kind={route} />
        </main>
      </>
    );
  }

  return (
    <>
      <div className="ground" aria-hidden />
      <Header />
      <main className="relative mx-auto max-w-[1360px] px-6">
        {error ? (
          <div className="plate mt-20 p-4" style={{ borderColor: 'var(--color-attack)' }}>
            <div className="tag" style={{ color: 'var(--color-attack)' }}>
              artefact load failed
            </div>
            <p className="mono mt-2 text-[12px]">{error}</p>
            <p className="tag mt-3 normal-case tracking-normal">
              Run npm run sync-data to copy artefacts into web/public/data.
            </p>
          </div>
        ) : (
          <>
            <Masthead />
            <Constellation />
            <Ledger />
            <Nebula />
            <Surface />
            <Helix />
            <Mirror />
            <Colophon />
          </>
        )}
      </main>
    </>
  );
}
