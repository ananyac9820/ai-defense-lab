import {
  Bar,
  BarChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { Chip, Empty, GlassPanel, Metric } from '../components/ui';
import { useStore } from '../lib/store';
import { axisProps, tooltipProps } from './chartTheme';

/**
 * Fidelity as evidence, not decoration (PDF S5.3).
 *
 * The discriminator's only job is to separate synthetic rows from reference rows. An AUC
 * approaching 0.5 means it cannot, and that number is directly reportable against the
 * fidelity criterion.
 *
 * The honest part: the behavioural telemetry has no analogue in IEEE-CIS or PaySim, so it
 * is excluded from the discriminator and calibrated against published effect sizes
 * instead. This view says so rather than letting one AUC imply coverage it does not have.
 */
export default function FidelityMirror() {
  const { bundle, perspective } = useStore();
  const attacker = perspective === 'attacker';
  if (!bundle) return <Empty what="fidelity report" />;

  const f = bundle.manifest.fidelity;
  const ks = Object.entries(f.ks_per_column ?? {}).map(([column, value]) => ({ column, value }));
  const distance = Math.abs(f.discriminator_auc - 0.5);

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_22rem]">
      <div className="flex flex-col gap-6">
        <GlassPanel
          kicker={attacker ? 'how convincing is the forgery' : 'how faithful is the data'}
          title="Adversarial discriminator"
        >
          <div className="mb-6 grid grid-cols-2 gap-6 md:grid-cols-3">
            <Metric
              label="Discriminator AUC"
              value={f.discriminator_auc.toFixed(3)}
              hint="0.5 is indistinguishable"
            />
            <Metric
              label="Distance from chance"
              value={distance.toFixed(3)}
              hint={distance < 0.1 ? 'strong' : distance < 0.2 ? 'acceptable' : 'investigate'}
            />
            <Metric
              label="Correlation Δ (Frobenius)"
              value={f.correlation_delta_frobenius?.toFixed(3) ?? '—'}
              hint="joint structure, where naive generators fail"
            />
          </div>

          <div className="relative h-3 overflow-hidden rounded-full bg-[rgba(232,237,240,0.08)]">
            <div
              className="absolute top-0 h-full rounded-full transition-[left,width] duration-700"
              style={{
                left: '50%',
                width: `${distance * 100}%`,
                background: 'var(--accent)',
                opacity: 0.8,
              }}
            />
            <div className="absolute left-1/2 top-0 h-full w-px bg-[rgba(232,237,240,0.5)]" />
          </div>
          <div className="mt-2 flex justify-between text-[11px] text-[var(--color-slate)]">
            <span>0.50 — indistinguishable</span>
            <span>1.00 — obviously synthetic</span>
          </div>

          <p className="mt-5 text-sm leading-relaxed text-[var(--color-slate)]">
            {attacker
              ? 'From this side the question is whether the forgery survives inspection. The same number answers both.'
              : 'Comparing histograms by eye is not evidence. A classifier that cannot tell our rows from reference rows is.'}
          </p>
        </GlassPanel>

        {ks.length > 0 && (
          <GlassPanel kicker="per column" title="Two-sample Kolmogorov–Smirnov">
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={ks} margin={{ top: 8, right: 12, bottom: 0, left: -12 }}>
                  <CartesianGrid stroke="rgba(232,237,240,0.05)" vertical={false} />
                  <XAxis dataKey="column" {...axisProps} />
                  <YAxis {...axisProps} />
                  <Tooltip {...tooltipProps} />
                  <ReferenceLine y={0.1} stroke="var(--color-attack)" strokeDasharray="4 4" />
                  <Bar dataKey="value" fill="var(--accent)" radius={4} />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <p className="mt-2 text-xs text-[var(--color-slate)]">
              Amber line at 0.10. Per-column statistics are necessary and not sufficient —
              correct marginals with wrong joint structure pass a histogram check and fail a
              discriminator.
            </p>
          </GlassPanel>
        )}
      </div>

      <div className="flex flex-col gap-6">
        <GlassPanel kicker="scope of the claim" title="What the discriminator can see">
          <div className="label-caps mb-2">compared against reference</div>
          <div className="mb-4 flex flex-wrap gap-1.5">
            {f.comparable_columns.map((c) => (
              <Chip key={c} tone="accent">
                {c}
              </Chip>
            ))}
          </div>
          <div className="label-caps mb-2">excluded — no reference analogue</div>
          <div className="flex flex-wrap gap-1.5">
            {f.excluded_columns.map((c) => (
              <Chip key={c}>{c}</Chip>
            ))}
          </div>
          <p className="mt-4 text-xs leading-relaxed text-[var(--color-slate)]">
            IEEE-CIS and PaySim contain no session timing or interaction telemetry, so the
            behavioural columns cannot be validated against them. They are calibrated to
            published effect sizes instead. Reporting one AUC over everything would overstate
            what was checked.
          </p>
        </GlassPanel>

        <GlassPanel kicker="reference profiles" title="Calibration sources">
          <div className="flex flex-col gap-3">
            {(f.reference_profiles ?? []).map((p) => (
              <div key={p.name} className="flex items-start justify-between gap-3">
                <div>
                  <div className="text-sm">{p.name.replace('_', '-').toUpperCase()}</div>
                  <div className="text-xs text-[var(--color-slate)]">
                    {p.serves_channels.join(', ')}
                  </div>
                </div>
                <Chip tone={p.available ? 'accent' : 'muted'}>
                  {p.available ? 'profiled' : 'pending'}
                </Chip>
              </div>
            ))}
          </div>
          <p className="mt-4 text-xs leading-relaxed text-[var(--color-slate)]">
            Profiles only. No reference row ever enters the ledger — the public datasets
            calibrate distributions and nothing else.
          </p>
        </GlassPanel>
      </div>
    </div>
  );
}
