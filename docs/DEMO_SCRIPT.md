# Demo run sheet — 2 minutes 40 seconds

For the backup video and for the live pitch. Judges have minutes per team and will not
read the codebase, so this is built to survive being watched at speed with the sound off.

**Record in a private window at 1440×900, browser zoom 100%, no bookmarks bar.** Open
https://ananyac9820.github.io/ai-defense-lab/ and let it settle before you start.

Before recording: click **load the graph** and **load the helix** once, then reload. The
WebGL chunk will be cached and neither scene will stall on camera.

---

## 0:00–0:20 · The claim

**On screen:** masthead. Do not scroll yet.

> "Generative AI made payment fraud cheap to produce and fast to mutate. We built both
> sides of that fight: an attacker that composes fraud from a grammar, and a defender
> that learns from its own failures."

Click **Attacker**, wait for the colour to cross over, click back to **Defender**.

> "Same world, same data. From one side a mule network is a route. From the other it's a
> detection surface."

---

## 0:20–0:50 · Identify

**Scroll to 01.** Land on the hero number.

> "Nineteen primitives, five stages, four hundred and forty-four thousand valid attack
> chains. That's the space our red team searches — not a list of twenty-five attacks we
> brainstormed."

Click **V003** in the vector list.

> "Every vector is grounded in a documented incident. This one is the forty-three lakh
> Pune deepfake investment scam. The card shows the case, the citation, and the data
> footprint we simulate — which is records and events, never tooling."

---

## 0:50–1:20 · Generate

**Scroll to 02** (the first ink band).

> "One percent fraud. Both populations come out of the same simulator through the same
> code path — mix public-dataset rows with generated fraud and a tree separates them on
> timestamp precision, not on behaviour. We test for that: a classifier trained only on
> formatting has to perform at chance."

Point at the flare row.

> "The fraud line is multiplied eight times to be visible at all. That's the honest
> picture of the problem."

---

## 1:20–2:00 · Defend — the finding

**Scroll to 03**, let the graph rotate for three seconds.

> "The graph level is where Mastercard's own AI Garage doubled compromised-card
> detection. Filled cubes are pass-through accounts — money in, money out, nothing ever
> resting. It's a topology, not a row, and it's worth nine points of recall on its own."

**Scroll to 04.**

> "Here's our real finding, and we didn't assume it — we measured it. We held out an
> attack family the detector had never seen: cloned-voice takeover, new device, new
> tokenisation. It caught it perfectly. Because all fraud has to move money eventually,
> and money movement looks the same however you got in.
>
> So we held out the extraction itself — value leaving through a merchant acquiring
> account, never touching a transfer rail. Detection fell to a third.
>
> The detector doesn't recognise attack families. It recognises extraction. That tells a
> red team exactly where to point: at new rails, not at parameter space."

---

## 2:00–2:30 · The loop

**Scroll to 05.** Let the helix turn.

> "Five generations. The strategist reads which features caught it and mutates against
> them. It found the merchant-payout weakness on its own, without being told, and by the
> third generation it was substituting extraction rails — the same axis we'd reasoned our
> way to.
>
> Two spirals: the fixed evaluation set, and only the vectors each generation invented.
> The new ones are caught more easily than the originals. Adversarial search inside a
> grammar hardens you against variation, not against novelty."

---

## 2:30–2:40 · Close

**Scroll to the colophon.**

> "Every number on this page and in our walkthrough document is read from the run
> artefacts — nothing is typed by hand, and a build fails if any artefact is older than
> the code that made it. One command reproduces all of it from one seed."

---

## Things to say only if asked

- **"What was your baseline?"** A tuned XGBoost on transaction features, selected on a
  time-ordered slice of the training window. Not the logistic regression — that's
  reported as a floor and labelled. Lift over the honest baseline is +17% AUC-PR.
- **"Why is unseen AUC-PR so much lower?"** Mostly prevalence. The held-out slices carry
  one vector's fraud against the same legitimate traffic, so their base rate is about an
  eighth. We compare instance recall instead and always print prevalence beside a metric.
- **"Did the behavioural signals work?"** No. We tested two and both were very slightly
  harmful. The ablation is in the document. We didn't tune them to make them work.
- **"Is the fraud data realistic?"** Partly. Discriminator AUC against a reference profile
  is pending — the datasets aren't on disk. We say so rather than quoting a number for
  something we haven't measured.

## Do not

- Do not scroll while talking through the finding. Land, stop, then speak.
- Do not open the attacker view more than twice; the point is made in five seconds.
- Do not read the metric tables aloud. They are there for the person who pauses.
