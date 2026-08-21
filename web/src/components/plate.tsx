import type { CSSProperties, ReactNode } from 'react';

/**
 * The annotation vocabulary of the page.
 *
 * Every element here is drawn from rules and type. No icon set, no shadow, no radius,
 * no gradient. A plate is a bordered spec sheet with a title bar and an index; a leader
 * is the hairline that ties an annotation to the thing it annotates; a tag is the
 * tracked-out monospace micro-label that carries most of the writing.
 */

export function Plate({
  title,
  index,
  children,
  className = '',
  style,
}: {
  title?: string;
  index?: string;
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
}) {
  return (
    <div className={`plate ${className}`} style={style}>
      {(title || index) && (
        <div className="flex items-center justify-between border-b border-[var(--fg)] px-2 py-1">
          <span className="mono text-[11px] uppercase tracking-[0.12em]">{title}</span>
          {index && <span className="mono text-[11px] text-[var(--fg-3)]">{index}</span>}
        </div>
      )}
      <div className="px-3 py-2.5">{children}</div>
    </div>
  );
}

/** A hairline that runs from an annotation to its anchor, ending in a filled square. */
export function Leader({
  direction = 'right',
  length = 64,
  className = '',
}: {
  direction?: 'right' | 'left' | 'down';
  length?: number;
  className?: string;
}) {
  const horizontal = direction !== 'down';
  return (
    <span
      className={`pointer-events-none inline-flex items-center ${className}`}
      style={
        horizontal
          ? { width: length, flexDirection: direction === 'right' ? 'row' : 'row-reverse' }
          : { height: length, flexDirection: 'column' }
      }
      aria-hidden
    >
      <span
        className="bg-[var(--fg-3)]"
        style={horizontal ? { height: 1, flex: 1 } : { width: 1, flex: 1 }}
      />
      <span className="bg-[var(--fg)]" style={{ width: 5, height: 5 }} />
    </span>
  );
}

/** Section number and rule, the way a drawing sheet numbers its views. */
export function SectionMark({ index, title, note }: { index: string; title: string; note?: string }) {
  return (
    <div className="flex items-baseline gap-3 border-t border-[var(--fg)] pt-2">
      <span className="mono text-[11px] tracking-[0.18em]">{index}</span>
      <span className="mono text-[11px] uppercase tracking-[0.18em]">{title}</span>
      {note && <span className="tag ml-auto hidden md:block">{note}</span>}
    </div>
  );
}

/**
 * A measured figure. The number is large and set in mono so it does not shift as it
 * animates; the lift over baseline sits beside it because a bare score is not a claim.
 */
export function Figure({
  label,
  value,
  lift,
  note,
}: {
  label: string;
  value: string;
  lift?: number | null;
  note?: string;
}) {
  return (
    <div className="border-t border-[var(--rule)] pt-2">
      <div className="tag">{label}</div>
      <div className="mt-1 flex items-baseline gap-2">
        <span className="mono text-[34px] leading-none tracking-[-0.03em]">{value}</span>
        {lift != null && Number.isFinite(lift) && (
          <span className="mono text-[12px]" style={{ color: 'var(--spot)' }}>
            {lift >= 0 ? '+' : ''}
            {lift.toFixed(0)}% vs base
          </span>
        )}
      </div>
      {note && <div className="tag mt-1 normal-case tracking-normal">{note}</div>}
    </div>
  );
}

/** Marks a synthesised shape. Tracked in PLACEHOLDERS.md; nothing ships wearing one. */
export function Placeholder({ id, what }: { id: string; what: string }) {
  return (
    <span
      className="mono inline-flex items-center gap-1.5 border px-2 py-1 text-[11px] uppercase tracking-[0.12em]"
      style={{ borderColor: 'var(--warn)', color: 'var(--warn)' }}
      title={`${id}: ${what}`}
    >
      placeholder {id}
    </span>
  );
}

export function FixtureMark({ on }: { on: boolean }) {
  if (!on) return null;
  return (
    <span
      className="mono border px-2 py-1 text-[11px] uppercase tracking-[0.12em]"
      style={{ borderColor: 'var(--warn)', color: 'var(--warn)' }}
    >
      fixture data
    </span>
  );
}

/** Real skeleton, shown while artefacts load. Hairline bars, no shimmer. */
export function Skeleton({ rows = 4, label = 'reading artefacts' }: { rows?: number; label?: string }) {
  return (
    <div className="plate p-3" role="status" aria-live="polite">
      <div className="tag mb-3">{label}</div>
      <div className="flex flex-col gap-2">
        {Array.from({ length: rows }, (_, i) => (
          <div
            key={i}
            className="skeleton-bar"
            style={{ height: 1, width: `${100 - i * 11}%`, animationDelay: `${i * 90}ms` }}
          />
        ))}
      </div>
    </div>
  );
}

/** Hatched block, used the way the reference uses hatching to weight a column. */
export function Hatch({ h = 40, className = '' }: { h?: number; className?: string }) {
  return (
    <div
      className={className}
      aria-hidden
      style={{
        height: h,
        backgroundImage:
          'repeating-linear-gradient(45deg, var(--fg) 0 1px, transparent 1px 5px)',
        opacity: 0.5,
      }}
    />
  );
}

/**
 * The one number a section is about, set large enough to be the first thing read.
 *
 * Scale contrast is the typographic idea: a 96px figure against 11px annotation and
 * almost nothing in between. It is also the only place on a paper section where the spot
 * colour appears at size, which gives each band exactly one colour event.
 */
export function Hero({
  value,
  caption,
  note,
}: {
  value: string;
  caption: string;
  note?: string;
}) {
  return (
    <div className="border-t border-[var(--fg)] pt-3">
      <div className="tag">{caption}</div>
      <div className="hero-number mt-2">{value}</div>
      {note && (
        <div className="tag mt-2 max-w-[46ch] normal-case tracking-[0.02em]">{note}</div>
      )}
    </div>
  );
}
