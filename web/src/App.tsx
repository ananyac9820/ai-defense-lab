import { lazy, Suspense, type ReactElement } from 'react';
import { motion } from 'framer-motion';
import { ENVIRONMENTS, useStore, type EnvironmentId } from './lib/store';
import { FixtureBadge } from './components/ui';

/**
 * Environments are lazy-loaded so the 2D path never pays for the 3D runtime
 * (design spec, Performance). Today all six are 2D; from Phase 5 four of these
 * imports point at WebGL scenes and the split already exists.
 */
const VIEWS: Record<EnvironmentId, React.LazyExoticComponent<() => ReactElement>> = {
  constellation: lazy(() => import('./environments/ThreatConstellation')),
  ledger: lazy(() => import('./environments/LedgerStream')),
  nebula: lazy(() => import('./environments/AccountNebula')),
  surface: lazy(() => import('./environments/DetectionSurface')),
  helix: lazy(() => import('./environments/LoopHelix')),
  mirror: lazy(() => import('./environments/FidelityMirror')),
};

function PerspectiveToggle() {
  const { perspective, flip } = useStore();
  const attacker = perspective === 'attacker';
  return (
    <button
      onClick={flip}
      className="glass relative flex h-11 w-56 items-center rounded-full px-1 text-sm"
      aria-label={`Switch to ${attacker ? 'defender' : 'attacker'} view`}
      title="Same scene, same data. The meaning inverts."
    >
      <motion.span
        layout
        transition={{ type: 'spring', stiffness: 220, damping: 26 }}
        className="absolute h-9 w-[6.5rem] rounded-full"
        style={{
          background: 'color-mix(in oklab, var(--accent) 22%, transparent)',
          border: '1px solid color-mix(in oklab, var(--accent) 50%, transparent)',
          left: attacker ? 'calc(100% - 6.75rem)' : '0.25rem',
        }}
      />
      <span
        className="relative z-10 flex-1 text-center tracking-wide"
        style={{ color: attacker ? 'var(--color-slate)' : 'var(--accent)' }}
      >
        Defender
      </span>
      <span
        className="relative z-10 flex-1 text-center tracking-wide"
        style={{ color: attacker ? 'var(--accent)' : 'var(--color-slate)' }}
      >
        Attacker
      </span>
    </button>
  );
}

function Rail() {
  const { environment, setEnvironment } = useStore();
  return (
    <nav className="glass flex flex-col gap-1 p-2">
      {ENVIRONMENTS.map((env) => {
        const active = env.id === environment;
        return (
          <button
            key={env.id}
            onClick={() => setEnvironment(env.id)}
            className="group relative rounded-2xl px-4 py-3 text-left transition-colors"
            style={{
              background: active
                ? 'color-mix(in oklab, var(--accent) 12%, transparent)'
                : 'transparent',
            }}
          >
            <div className="label-caps flex items-center gap-2">
              <span>{env.pillar}</span>
              <span
                className="rounded px-1 text-[9px]"
                style={{
                  border: '1px solid var(--color-edge)',
                  color: env.dim === '3D' ? 'var(--accent)' : 'var(--color-slate)',
                }}
              >
                {env.dim}
              </span>
            </div>
            <div
              className="mt-0.5 text-sm"
              style={{ color: active ? 'var(--accent)' : 'var(--color-bone)' }}
            >
              {env.label}
            </div>
          </button>
        );
      })}
    </nav>
  );
}

export default function App() {
  const { environment, bundle, error, perspective } = useStore();
  const View = VIEWS[environment];

  return (
    <div className="mx-auto flex min-h-screen max-w-[1600px] flex-col gap-6 p-6">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="label-caps">Mastercard Innovation Challenge · GFF 2026 · Team Code Ops</div>
          <h1 className="text-2xl font-bold tracking-tight">
            AI Defense Lab
            <span className="ml-3 text-base font-normal text-[var(--color-slate)]">
              {perspective === 'defender'
                ? 'a detection surface'
                : 'a route map'}
            </span>
          </h1>
        </div>
        <div className="flex items-center gap-3">
          <FixtureBadge isFixture={bundle?.manifest.is_fixture ?? false} />
          <PerspectiveToggle />
        </div>
      </header>

      <div className="grid flex-1 grid-cols-[15rem_1fr] gap-6">
        <Rail />
        <main className="min-w-0">
          {error ? (
            <div className="glass p-6 text-sm" style={{ color: 'var(--color-attack-2)' }}>
              <div className="label-caps mb-2">artefact load failed</div>
              {error}
              <div className="mt-3 text-[var(--color-slate)]">
                Run <code className="tabular">npm run sync-data</code> to copy fixtures into
                web/public/data.
              </div>
            </div>
          ) : (
            // Keyed remount rather than AnimatePresence: mode="wait" holds the exiting
            // child until its exit animation resolves, and under React 19 StrictMode with a
            // Suspense boundary inside it never did - the rail highlight moved but the view
            // did not. The real cross-dissolve arrives with the 3D camera in Phase 5; a
            // fade-in is the honest 2D equivalent until then.
            <motion.div
                key={environment}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
              >
                <Suspense
                  fallback={
                    <div className="glass grid h-96 place-items-center text-sm text-[var(--color-slate)]">
                      loading environment…
                    </div>
                  }
                >
                  <View />
                </Suspense>
              </motion.div>
          )}
        </main>
      </div>

      <footer className="label-caps flex flex-wrap items-center justify-between gap-2">
        <span>
          2D views · reduced-motion path and venue fallback · built against{' '}
          {bundle?.manifest.is_fixture ? 'fixtures' : 'live artefacts'}
        </span>
        {bundle && (
          <span className="tabular">
            run {bundle.manifest.run_id} · seed {bundle.manifest.seed} · prevalence{' '}
            {(bundle.manifest.prevalence * 100).toFixed(2)}%
          </span>
        )}
      </footer>
    </div>
  );
}
