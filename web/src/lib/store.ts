import { create } from 'zustand';
import { loadBundle, type Bundle } from './data';

/**
 * One world, two perspectives.
 *
 * The inversion is a single piece of state. Everything downstream - accent colours,
 * copy, which face of a panel is showing - reads from it, which is what keeps the flip
 * an 800ms morph of one scene rather than a navigation between two.
 */
export type Perspective = 'defender' | 'attacker';

export const ENVIRONMENTS = [
  { id: 'constellation', label: 'Threat Constellation', pillar: 'Identify', dim: '3D' },
  { id: 'ledger', label: 'Ledger Stream', pillar: 'Generate', dim: '2D' },
  { id: 'nebula', label: 'Account Nebula', pillar: 'Graph', dim: '3D' },
  { id: 'surface', label: 'Detection Surface', pillar: 'Defend', dim: '3D' },
  { id: 'helix', label: 'Loop Helix', pillar: 'The Loop', dim: '3D' },
  { id: 'mirror', label: 'Fidelity Mirror', pillar: 'Evidence', dim: '2D' },
] as const;

export type EnvironmentId = (typeof ENVIRONMENTS)[number]['id'];

interface State {
  perspective: Perspective;
  environment: EnvironmentId;
  generation: number;
  threshold: number;
  selectedVector: string | null;
  bundle: Bundle | null;
  error: string | null;

  flip: () => void;
  setPerspective: (p: Perspective) => void;
  setEnvironment: (e: EnvironmentId) => void;
  setGeneration: (g: number) => void;
  setThreshold: (t: number) => void;
  selectVector: (v: string | null) => void;
  load: () => Promise<void>;
}

export const useStore = create<State>((set, get) => ({
  perspective: 'defender',
  environment: 'helix',
  generation: 0,
  threshold: 0.5,
  selectedVector: null,
  bundle: null,
  error: null,

  flip: () => set({ perspective: get().perspective === 'defender' ? 'attacker' : 'defender' }),
  setPerspective: (perspective) => set({ perspective }),
  setEnvironment: (environment) => set({ environment }),
  setGeneration: (generation) => set({ generation }),
  setThreshold: (threshold) => set({ threshold }),
  selectVector: (selectedVector) => set({ selectedVector }),

  load: async () => {
    try {
      set({ bundle: await loadBundle(), error: null });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : String(err) });
    }
  },
}));

/** Accent pair for the current side. Read this, never a hard-coded hex. */
export function accents(p: Perspective): { a: string; b: string } {
  return p === 'defender'
    ? { a: 'var(--color-defend)', b: 'var(--color-defend-2)' }
    : { a: 'var(--color-attack)', b: 'var(--color-attack-2)' };
}

/** Applies the perspective to the CSS custom properties the whole app reads. */
export function applyPerspective(p: Perspective): void {
  const { a, b } = accents(p);
  const root = document.documentElement;
  root.style.setProperty('--accent', a);
  root.style.setProperty('--accent-2', b);
  root.dataset.perspective = p;
}
