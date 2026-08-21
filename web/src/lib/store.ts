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
  { id: 'constellation', label: 'Threat Constellation', pillar: 'Identify', index: '01' },
  { id: 'ledger', label: 'Ledger Stream', pillar: 'Generate', index: '02' },
  { id: 'nebula', label: 'Account Nebula', pillar: 'Graph', index: '03' },
  { id: 'surface', label: 'Detection Surface', pillar: 'Defend', index: '04' },
  { id: 'helix', label: 'Loop Helix', pillar: 'The Loop', index: '05' },
  { id: 'mirror', label: 'Fidelity Mirror', pillar: 'Evidence', index: '06' },
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

/**
 * One spot colour, swapped by the inversion. Viridian reads as the defence, vermilion as
 * the attack. Everything else on the page is paper and ink, so the single swap is
 * legible without any of it being decorative.
 */
export function applyPerspective(p: Perspective): void {
  const root = document.documentElement;
  // Two variants because a colour that reads on paper disappears on ink and the reverse.
  // Bands pick whichever suits their ground, so the inversion stays one state change.
  if (p === 'defender') {
    root.style.setProperty('--spot-paper', '#0f5c4a');
    root.style.setProperty('--spot-ink', '#4bbf95');
  } else {
    root.style.setProperty('--spot-paper', '#c43d18');
    root.style.setProperty('--spot-ink', '#ff7a4d');
  }
  root.dataset.perspective = p;
}
