"""The single-source test.

PDF S5, boxed, and S10 where it is the only risk rated *Fatal*: if legitimate and
fraudulent traffic come from different generating processes, a gradient-boosted tree
learns which program wrote each row and reports an F1 near 0.99 that means nothing.

The stated remedy is to verify by training a provenance-only classifier and confirming
it fails. This is that test. It is written in Phase 1, before the simulator exists,
deliberately:

  * It xfails now, with ``raises=ModuleNotFoundError``, so it can only pass silently
    for the right reason. Any other failure - an import error elsewhere, a broken
    fixture, a bug in the harness - surfaces as a hard error rather than being
    absorbed into the expected failure.
  * ``strict=True`` means the day the simulator lands and this starts passing, pytest
    fails until the marker is removed. The test cannot be forgotten.

Remove the marker in Phase 2 when adl.generate.simulator exists.
"""

from __future__ import annotations

import pytest

PROVENANCE_AUC_CEILING = 0.60
"""A provenance classifier at 0.5 is chance. Anything above this ceiling means the two
populations are separable on generation artefacts alone and the headline metrics are
worthless."""


@pytest.mark.phase2
@pytest.mark.xfail(
    raises=ModuleNotFoundError,
    strict=True,
    reason="Phase 2: adl.generate.simulator does not exist yet. Remove this marker when it does.",
)
def test_provenance_classifier_performs_at_chance() -> None:
    import numpy as np
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import train_test_split

    from adl.generate.simulator import simulate  # noqa: PLC0415 - must fail late, not at import

    ledger = simulate(n_transactions=40_000, seed=7)
    txns = ledger.transactions

    # The task is deliberately impossible if the single-source rule holds: predict the
    # LABEL from the row, with every feature that could encode intent removed. What is
    # left is formatting - timestamp precision, amount rounding, identifier shape, null
    # patterns - which is exactly what leaks when two generators are mixed.
    y = txns["is_fraud"].to_numpy()
    formatting_only = txns[[
        "amount_inr",
        "timestamp_subsecond_precision",
        "amount_decimal_places",
        "id_numeric_suffix",
        "n_null_fields",
    ]].to_numpy()

    x_tr, x_te, y_tr, y_te = train_test_split(
        formatting_only, y, test_size=0.3, random_state=7, stratify=y
    )
    model = HistGradientBoostingClassifier(random_state=7).fit(x_tr, y_tr)
    auc = roc_auc_score(y_te, model.predict_proba(x_te)[:, 1])

    assert auc == pytest.approx(0.5, abs=PROVENANCE_AUC_CEILING - 0.5), (
        f"provenance-only AUC {auc:.3f} exceeds {PROVENANCE_AUC_CEILING}: legitimate and "
        f"fraudulent rows are distinguishable on formatting alone. Every downstream metric "
        f"is invalid until this is fixed. See PDF S5 and S10 (rated Fatal)."
    )
    assert not np.isnan(auc)
