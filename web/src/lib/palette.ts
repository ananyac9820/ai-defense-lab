/**
 * The palette, in one place.
 *
 * CSS owns theming everywhere it can, but WebGL materials cannot read a custom
 * property, so the three.js scenes need real hex. Rather than let those drift, both the
 * CSS variables and the scenes read the values from here.
 */

export const GROUND_BASE = '#0d1f17';
export const GROUND_RAISE = '#142c20';
export const BONE = '#e8ede6';

/** Hairline ink on the green ground, matched to --rule at the raised band. */
export const LINE = '#7d8c82';

/**
 * Defence reads 9.2:1 on the raised ground and needed no change. Attack could not stay
 * at #c43d18: it measures 2.86:1 there and is unreadable. Lightened to keep the hue and
 * clear the bar, with a paler value for anything small enough to be audited at 7:1.
 */
export const DEFEND = '#17e88f';

/**
 * Attack needs two values here, and the audit is why.
 *
 * #c43d18 measures 2.86:1 on the raised ground and is unreadable. #ff7a4d fixes the
 * graphics but still lands at 6.6:1 as 11px text and 6.6:1 for dark text sitting on it,
 * both short of the 7:1 bar. So the fill is #ff8a5c, which clears 7.4:1 for the label
 * inside it, and small text on the ground uses #ffa07a at 7.5:1.
 *
 * Signal green needed no such split: it reads 9.2:1 either way.
 */
export const ATTACK = '#ff8a5c';
export const ATTACK_SMALL = '#ffa07a';
export const WARN = '#ffa07a';

export const spotFor = (attacker: boolean): string => (attacker ? ATTACK : DEFEND);
export const spotSmallFor = (attacker: boolean): string =>
  attacker ? ATTACK_SMALL : DEFEND;
