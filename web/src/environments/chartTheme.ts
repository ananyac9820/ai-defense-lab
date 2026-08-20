/** Shared Recharts styling so the 2D views read as one system. */

export const axisProps = {
  stroke: 'rgba(232,237,240,0.25)',
  tick: { fill: '#6B7C8A', fontSize: 11, fontFamily: 'JetBrains Mono, monospace' },
  tickLine: false,
  axisLine: { stroke: 'rgba(232,237,240,0.10)' },
} as const;

export const tooltipProps = {
  contentStyle: {
    background: 'rgba(12,18,24,0.94)',
    border: '1px solid rgba(232,237,240,0.10)',
    borderRadius: 14,
    fontFamily: 'JetBrains Mono, monospace',
    fontSize: 12,
  },
  labelStyle: { color: '#6B7C8A' },
  itemStyle: { color: '#E8EDF0' },
  cursor: { stroke: 'rgba(232,237,240,0.18)' },
} as const;
