import { useTrack } from '../lib/useMotion';

/**
 * Plots drawn as hairline technical figures.
 *
 * Every stroke carries pathLength="1" and the `draw` class, so the dash offset is a
 * unit-free function of the figure's own scroll progress. Nothing measures a path in
 * JavaScript and nothing animates on a timer: scrub back up and the lines retract.
 *
 * Deliberately hand-built SVG rather than a chart library: the reference draws its
 * figures with rules, ticks and monospace labels, and a charting default style would
 * fight that at every turn. These are small enough to read in full.
 */

export interface Series {
  label: string;
  values: number[];
  dashed?: boolean;
  spot?: boolean;
}

const PAD = { top: 12, right: 16, bottom: 26, left: 44 };

export function LinePlot({
  series,
  xLabels,
  height = 190,
  yMax = 1,
  format = (v: number) => `${Math.round(v * 100)}`,
}: {
  series: Series[];
  xLabels: string[];
  height?: number;
  yMax?: number;
  format?: (v: number) => string;
}) {
  const ref = useTrack<SVGSVGElement>();
  const w = 640;
  const innerW = w - PAD.left - PAD.right;
  const innerH = height - PAD.top - PAD.bottom;
  const n = Math.max(xLabels.length - 1, 1);
  const x = (i: number) => PAD.left + (i / n) * innerW;
  const y = (v: number) => PAD.top + innerH - (v / yMax) * innerH;

  return (
    <svg ref={ref} viewBox={`0 0 ${w} ${height}`} className="w-full" role="img">
      {[0, 0.25, 0.5, 0.75, 1].map((t) => (
        <g key={t}>
          <line
            className="draw"
            pathLength={1}
            x1={PAD.left}
            x2={w - PAD.right}
            y1={y(t * yMax)}
            y2={y(t * yMax)}
            stroke="var(--rule)"
            strokeWidth={1}
          />
          <text
            x={PAD.left - 6}
            y={y(t * yMax) + 3}
            textAnchor="end"
            className="mono"
            fontSize={11}
            fill="var(--fg-2)"
          >
            {format(t * yMax)}
          </text>
        </g>
      ))}
      {xLabels.map((label, i) => (
        <text
          key={label + i}
          x={x(i)}
          y={height - 6}
          textAnchor="middle"
          className="mono fade-in"
          fontSize={11}
          fill="var(--fg-2)"
        >
          {label}
        </text>
      ))}
      {series.map((s) => (
        <g key={s.label}>
          <polyline
            className="draw"
            pathLength={1}
            fill="none"
            stroke={s.spot ? 'var(--spot)' : 'var(--fg)'}
            strokeWidth={s.spot ? 1.6 : 1}
            strokeDasharray={s.dashed ? '3 3' : undefined}
            points={s.values
              .map((v, i) => (Number.isFinite(v) ? `${x(i)},${y(v)}` : null))
              .filter(Boolean)
              .join(' ')}
          />
          {s.spot &&
            s.values.map((v, i) =>
              Number.isFinite(v) ? (
                <rect className="fade-in" key={i} x={x(i) - 2.5} y={y(v) - 2.5} width={5} height={5} fill="var(--spot)" />
              ) : null
            )}
        </g>
      ))}
    </svg>
  );
}

export function BarPlot({
  labels,
  values,
  height = 150,
  format = (v: number) => v.toFixed(2),
}: {
  labels: string[];
  values: number[];
  height?: number;
  format?: (v: number) => string;
}) {
  const ref = useTrack<SVGSVGElement>();
  const w = 640;
  const innerW = w - PAD.left - PAD.right;
  const innerH = height - PAD.top - PAD.bottom;
  const max = Math.max(...values.map(Math.abs), 1e-9);
  const bw = innerW / values.length;

  return (
    <svg ref={ref} viewBox={`0 0 ${w} ${height}`} className="w-full" role="img">
      <line
        className="draw"
        pathLength={1}
        x1={PAD.left}
        x2={w - PAD.right}
        y1={PAD.top + innerH}
        y2={PAD.top + innerH}
        stroke="var(--fg)"
        strokeWidth={1}
      />
      {values.map((v, i) => {
        const h = (Math.abs(v) / max) * innerH;
        return (
          <g key={labels[i] + i}>
            <rect
              style={{ transformOrigin: `0 ${PAD.top + innerH}px`, transform: 'scaleY(var(--p, 1))' }}
              x={PAD.left + i * bw + bw * 0.22}
              y={PAD.top + innerH - h}
              width={bw * 0.56}
              height={h}
              fill={v < 0 ? 'var(--attack)' : 'var(--fg)'}
            />
            <text
              x={PAD.left + i * bw + bw / 2}
              y={PAD.top + innerH - h - 4}
              textAnchor="middle"
              className="mono"
              fontSize={11}
              fill="var(--fg-2)"
            >
              {format(v)}
            </text>
            <text
              x={PAD.left + i * bw + bw / 2}
              y={height - 6}
              textAnchor="middle"
              className="mono"
              fontSize={11}
              fill="var(--fg-2)"
            >
              {labels[i]}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

/** Horizontal signed bars, for feature contributions. */
export function ContributionPlot({
  rows,
  height = 170,
}: {
  rows: { feature: string; value: number }[];
  height?: number;
}) {
  const ref = useTrack<SVGSVGElement>();
  const w = 640;
  const mid = 300;
  const max = Math.max(...rows.map((r) => Math.abs(r.value)), 1e-9);
  const rh = rows.length ? (height - 8) / rows.length : 0;

  return (
    <svg ref={ref} viewBox={`0 0 ${w} ${height}`} className="w-full" role="img">
      <line className="draw" pathLength={1} x1={mid} x2={mid} y1={0} y2={height} stroke="var(--fg)" strokeWidth={1} />
      {rows.map((r, i) => {
        const len = (Math.abs(r.value) / max) * 250;
        const negative = r.value < 0;
        return (
          <g key={r.feature}>
            <rect
              style={{
                transformOrigin: `${mid}px 0`,
                transform: `scaleX(clamp(0, calc(var(--p, 1) * 2 - ${(i * 0.12).toFixed(2)}), 1))`,
              }}
              x={negative ? mid - len : mid}
              y={i * rh + rh * 0.28}
              width={len}
              height={rh * 0.44}
              fill={negative ? 'var(--attack)' : 'var(--fg)'}
            />
            <text
              x={negative ? mid + 8 : mid - 8}
              y={i * rh + rh * 0.62}
              textAnchor={negative ? 'start' : 'end'}
              className="mono"
              fontSize={11}
              fill="var(--fg-2)"
            >
              {r.feature}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
