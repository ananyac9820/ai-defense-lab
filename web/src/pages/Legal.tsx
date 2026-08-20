import { SectionMark } from '../components/plate';

/**
 * Terms and privacy. Short, specific, and true of this particular artefact.
 *
 * A prototype with no terms and no privacy notice is a tell in itself, and in a payments
 * context it is the wrong signal to send to a panel that regulates for a living. Both
 * documents say what is actually the case here rather than reciting boilerplate written
 * for a product that collects something.
 */

const TERMS: [string, string][] = [
  [
    'What this is',
    'A research prototype built for the Mastercard Innovation Challenge at GFF 2026 by Team Code Ops. It demonstrates a closed adversarial loop over synthetic payment data. It is not a product, it is not a service, and it is not offered for commercial use.',
  ],
  [
    'The data is synthetic',
    'Every account, device, merchant, transaction, session and graph edge shown here was produced by the simulator in this repository. No record corresponds to a real person, a real card, a real merchant or a real payment. Public reference datasets calibrated the distributions and supplied no rows.',
  ],
  [
    'Scope boundary',
    'The Generate pillar produces labelled data. It does not produce functional attack tooling. There is no voice cloning, no phishing generation, no deepfake code, and nothing in the repository capable of reaching a live endpoint. Attack mechanisms are described only to the level of detail needed to model their observable data footprint.',
  ],
  [
    'Cited incidents',
    'Each attack vector cites a documented public incident so that its plausibility can be checked. Those citations describe real events reported by others; we make no claim of our own about the facts of any case, and the links are provided for verification rather than as endorsement of the reporting.',
  ],
  [
    'No warranty, no advice',
    'The metrics on this page describe the behaviour of one detector on one synthetic dataset at a stated prevalence. They are not a prediction of performance on real payment traffic, and nothing here constitutes security, financial or regulatory advice.',
  ],
  [
    'Reuse',
    'The repository is published for review by the challenge organisers. If you want to build on it, ask first.',
  ],
];

const PRIVACY: [string, string][] = [
  [
    'The short version',
    'This prototype collects nothing about you. There is no account, no login, no form, no analytics, no advertising and no third-party tracker on any page.',
  ],
  [
    'Cookies',
    'None are set. There is no consent banner because there is nothing to consent to.',
  ],
  [
    'What is stored in your browser',
    'Only the state needed to render the page while you are on it, held in memory and discarded when the tab closes. Your choice of attacker or defender view is not persisted.',
  ],
  [
    'What the page loads',
    'Static artefact files produced by the pipeline in this repository, plus a webfont from Google Fonts. The font request is made by your browser directly to Google and is subject to their handling; if that matters to you, the fonts can be self-hosted on request and the page will render without them regardless.',
  ],
  [
    'Personal data in the dataset',
    'There is none. Every identifier shown is generated. If any string here resembles a real account number or name, that is coincidence in a synthetic namespace and not a record of any person.',
  ],
  [
    'Contact',
    'Raise an issue on the repository.',
  ],
];

export function Legal({ kind }: { kind: 'terms' | 'privacy' }) {
  const terms = kind === 'terms';
  const rows = terms ? TERMS : PRIVACY;

  return (
    <article className="relative z-10 pt-14 pb-24">
      <SectionMark index={terms ? 'T' : 'P'} title={terms ? 'Terms of use' : 'Privacy notice'} />
      <h1 className="display mt-8 max-w-[16ch] text-[clamp(2.4rem,6vw,4.6rem)]">
        {terms ? 'What this is, and is not.' : 'Nothing is collected.'}
      </h1>

      <div className="mt-12 max-w-[1000px] border-t border-[var(--color-ink)]">
        {rows.map(([heading, body], i) => (
          <section key={heading} className="grid gap-4 border-b border-[var(--color-rule)] py-6 md:grid-cols-[8rem_1fr]">
            <div>
              <div className="mono text-[11px] text-[var(--color-ink-40)]">
                {String(i + 1).padStart(2, '0')}
              </div>
              <h2 className="mono mt-1 text-[11px] uppercase tracking-[0.14em]">{heading}</h2>
            </div>
            <p className="max-w-[68ch] text-[15px] leading-[1.6] text-[var(--color-ink-60)]">{body}</p>
          </section>
        ))}
      </div>

      <a href="#/" className="hit mono mt-10 inline-block text-[11px] uppercase tracking-[0.16em] underline underline-offset-4">
        Back to the dossier
      </a>
    </article>
  );
}
