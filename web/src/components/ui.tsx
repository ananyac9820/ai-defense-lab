import type { ReactNode } from 'react';
import { formatInr } from '../lib/data';

export function GlassPanel({
  children,
  className = '',
  title,
  kicker,
}: {
  children: ReactNode;
  className?: string;
  title?: string;
  kicker?: string;
}) {
  return (
    <section className={`glass p-6 ${className}`}>
      {(title || kicker) && (
        <header className="mb-4">
          {kicker && <div className="label-caps mb-1">{kicker}</div>}
          {title && (
            <h2 className="text-xl font-medium tracking-tight text-[var(--color-bone)]">{title}</h2>
          )}
        </header>
      )}
      {children}
    </section>
  );
}

/**
 * A metric is never shown as a bare score (build brief requirement 2, NOTES.md D-002).
 * The absolute value is the small print; the lift over baseline is the headline.
 */
export function Metric({
  label,
  value,
  lift,
  hint,
  currency,
}: {
  label: string;
  value: number | string;
  lift?: number | null;
  hint?: string;
  currency?: boolean;
}) {
  const shown = currency && typeof value === 'number' ? formatInr(value) : value;
  return (
    <div className="min-w-0">
      <div className="label-caps truncate">{label}</div>
      <div className="mt-1 flex items-baseline gap-2">
        <span className="tabular text-2xl text-[var(--color-bone)]">{shown}</span>
        {lift != null && (
          <span
            className="tabular text-sm"
            style={{ color: lift >= 0 ? 'var(--accent)' : 'var(--color-attack-2)' }}
          >
            {lift >= 0 ? '+' : ''}
            {lift.toFixed(0)}% vs baseline
          </span>
        )}
      </div>
      {hint && <div className="mt-1 text-xs text-[var(--color-slate)]">{hint}</div>}
    </div>
  );
}

export function Chip({ children, tone = 'muted' }: { children: ReactNode; tone?: 'muted' | 'accent' }) {
  return (
    <span
      className="rounded-full border px-2.5 py-1 text-[11px] tracking-wide"
      style={
        tone === 'accent'
          ? {
              borderColor: 'color-mix(in oklab, var(--accent) 45%, transparent)',
              color: 'var(--accent)',
              background: 'color-mix(in oklab, var(--accent) 10%, transparent)',
            }
          : { borderColor: 'var(--color-edge)', color: 'var(--color-slate)' }
      }
    >
      {children}
    </span>
  );
}

/** Fixture data must never be mistaken for a result. */
export function FixtureBadge({ isFixture }: { isFixture: boolean }) {
  if (!isFixture) return null;
  return (
    <div
      className="rounded-full border px-3 py-1 text-[11px] tracking-[0.16em] uppercase"
      style={{
        borderColor: 'color-mix(in oklab, var(--color-attack) 50%, transparent)',
        color: 'var(--color-attack)',
        background: 'color-mix(in oklab, var(--color-attack) 12%, transparent)',
      }}
      title="Fixture data. Shapes are real, numbers are invented. Replaced by live artefacts in Phase 5."
    >
      Fixture data
    </div>
  );
}

/**
 * Marks one element - not the whole page - as a synthesised shape rather than a measured
 * result. Tracked in PLACEHOLDERS.md, and nothing ships with one of these still attached.
 */
export function PlaceholderBadge({ id, what }: { id: string; what: string }) {
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] tracking-[0.14em] uppercase"
      style={{
        borderColor: 'color-mix(in oklab, var(--color-attack) 55%, transparent)',
        color: 'var(--color-attack)',
        background: 'color-mix(in oklab, var(--color-attack) 12%, transparent)',
      }}
      title={`${id}: ${what}`}
    >
      <span aria-hidden>▲</span> placeholder · {id}
    </span>
  );
}


export function Empty({ what }: { what: string }) {
  return (
    <div className="grid h-64 place-items-center text-sm text-[var(--color-slate)]">
      no {what} in this artefact
    </div>
  );
}
