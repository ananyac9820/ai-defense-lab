/**
 * The palette, in one place.
 *
 * CSS owns theming everywhere it can, but WebGL materials cannot read a custom property,
 * so the three.js scenes need real hex. Rather than let those drift, both the CSS
 * variables and the scenes read their values from here.
 *
 * Two grounds, paper and ink, and every accent needs a value for each: a colour that
 * reads on paper disappears on ink and the reverse. Small text needs a different value
 * again, because 11px has to clear 7:1 where a 55px figure does not.
 */

export const PAPER = '#f3f2ee';
export const INK = '#0e0e0c';

/** Hairline colour for the WebGL scenes, which sit on the paper band. */
export const LINE = '#14140f';

/*
  Accents, solved against the ground they sit on.

    on paper (#f3f2ee)          on ink (#0e0e0c)
      defence  #0f5c4a            #4bbf95
      attack   #c43d18            #ff7a4d

  Vermilion measures 4.65:1 on paper, which is fine behind a 55px figure and not fine for
  an 11px label, so small text takes a darker #94290c on paper and a lighter #ff9a72 on
  ink. Only the value moves; the hue does not.
*/
export const DEFEND_PAPER = '#0f5c4a';
export const DEFEND_INK = '#4bbf95';
export const ATTACK_PAPER = '#c43d18';
export const ATTACK_INK = '#ff7a4d';

export const DEFEND_SM_PAPER = '#0f5c4a';
export const DEFEND_SM_INK = '#4bbf95';
export const ATTACK_SM_PAPER = '#94290c';
export const ATTACK_SM_INK = '#ff9a72';

export const WARN_PAPER = '#94290c';
export const WARN_INK = '#ff9a72';

/** The 3D scenes render on the paper band, so they take the paper values. */
export const spotFor = (attacker: boolean): string =>
  attacker ? ATTACK_PAPER : DEFEND_PAPER;
