import { useEffect, useRef } from 'react';
import { remeasure, track, type MotionElement, type Range } from './motion';

/**
 * Attach an element to the scroll driver. The element receives `--p` from 0 to 1 and CSS
 * does the rest, so nothing in this file causes a render while scrolling.
 */
export function useTrack<T extends MotionElement>(range: Range = 'enter', offset = 0) {
  const ref = useRef<T>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    return track(el, range, offset);
  }, [range, offset]);
  return ref;
}

/** Re-measure once a dependency has changed layout, e.g. artefacts finishing loading. */
export function useRemeasure(dep: unknown): void {
  useEffect(() => {
    const id = window.setTimeout(remeasure, 60);
    return () => window.clearTimeout(id);
  }, [dep]);
}
