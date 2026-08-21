/**
 * Scroll-driven motion.
 *
 * One requestAnimationFrame loop for the whole page. Registered elements get a CSS
 * custom property `--p` written straight onto them, and every animation downstream is
 * plain CSS reading that number. Nothing here calls setState, so scrolling never
 * re-renders React, and nothing reads layout inside the frame except through a cached
 * measurement that is refreshed on resize.
 *
 * That is what holds 60fps: measure rarely, write often, and only ever write transform,
 * opacity and stroke-dashoffset.
 *
 * Everything is tied to scroll position rather than to a timer, so scrubbing back up the
 * page reverses it exactly. Ambient drift is the single exception and lives in CSS
 * keyframes.
 */

export type Range = 'enter' | 'cover' | 'exit';

interface Entry {
  el: MotionElement;
  range: Range;
  /** extra distance in px before the element enters, for staggering siblings */
  offset: number;
  top: number;
  height: number;
}

const entries = new Set<Entry>();
let frame = 0;
let needsMeasure = true;

export const prefersReducedMotion = (): boolean =>
  typeof window !== 'undefined' &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches;

function measure(): void {
  const scrollY = window.scrollY;
  for (const entry of entries) {
    const rect = entry.el.getBoundingClientRect();
    entry.top = rect.top + scrollY;
    entry.height = rect.height;
  }
  needsMeasure = false;
}

function progressFor(entry: Entry, scrollY: number, viewport: number): number {
  const { top, height, range, offset } = entry;
  let start: number;
  let end: number;

  if (range === 'enter') {
    // 0 when the element's top edge reaches the bottom of the viewport, 1 once it has
    // travelled a third of the viewport upward. Short, so things finish drawing while
    // they are still arriving rather than after they have settled.
    start = top - viewport + offset;
    end = top - viewport * 0.42 + offset;
  } else if (range === 'exit') {
    start = top + height - viewport;
    end = top + height;
  } else {
    start = top - viewport;
    end = top + height;
  }

  const span = Math.max(end - start, 1);
  return Math.min(1, Math.max(0, (scrollY - start) / span));
}

function tick(): void {
  frame = 0;
  if (needsMeasure) measure();

  const scrollY = window.scrollY;
  const viewport = window.innerHeight;

  // A single global scroll offset, in px, for the parallax layers to multiply.
  document.documentElement.style.setProperty('--sy', String(scrollY));

  for (const entry of entries) {
    const p = progressFor(entry, scrollY, viewport);
    entry.el.style.setProperty('--p', p.toFixed(4));
  }
}

function schedule(): void {
  if (!frame) frame = requestAnimationFrame(tick);
}

let listening = false;

function listen(): void {
  if (listening) return;
  listening = true;
  window.addEventListener('scroll', schedule, { passive: true });
  window.addEventListener('resize', () => {
    needsMeasure = true;
    schedule();
  });
  // Fonts and lazily mounted scenes both change layout after first paint.
  window.addEventListener('load', () => {
    needsMeasure = true;
    schedule();
  });
}

/**
 * Register an element for scroll progress. Returns an unregister function.
 *
 * Under reduced motion the element is set to its final state once and never tracked, so
 * every draw-on, count-up and stagger lands complete with no motion and no information
 * lost.
 */
/** Anything with a style attribute: SVG elements are Elements, not HTMLElements. */
export type MotionElement = HTMLElement | SVGElement;

export function track(el: MotionElement, range: Range = 'enter', offset = 0): () => void {
  if (prefersReducedMotion()) {
    el.style.setProperty('--p', '1');
    return () => {};
  }
  const entry: Entry = { el, range, offset, top: 0, height: 0 };
  entries.add(entry);
  needsMeasure = true;
  listen();
  schedule();
  return () => {
    entries.delete(entry);
  };
}

/** Force a re-measure, for content that appears after mount (lazy 3D, loaded artefacts). */
export function remeasure(): void {
  needsMeasure = true;
  schedule();
}
