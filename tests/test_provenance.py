"""The single-source test.

PDF S5, boxed, and S10 where it is the only risk rated *Fatal*: if legitimate and
fraudulent traffic come from different generating processes, a gradient-boosted tree
learns which program wrote each row and reports an F1 near 0.99 that means nothing.

The stated remedy is to verify by training a provenance-only classifier and confirming it
fails. This is that test.

It was written in Phase 1 with ``xfail(raises=ModuleNotFoundError, strict=True)`` so that
it could only pass silently for the right reason, and so that pytest would go red the day
the simulator landed and the marker was still attached. The simulator landed in Phase 2
and the marker came off, which is the mechanism working as designed.

The formatting features are derived HERE rather than emitted by the simulator. A
generator that helpfully exposes its own formatting artefacts would be marking its own
homework - and worse, those columns would then be available to the detector.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score

from adl.evaluate.splits import assert_leak_free, time_and_account_split
from adl.generate.simulator import simulate

PROVENANCE_AUC_CEILING = 0.60
"""A provenance classifier at 0.5 is chance. Above this ceiling the two populations are
separable on generation artefacts alone and every headline metric is worthless."""


def _formatting_only(txns) -> np.ndarray:
    """Features that describe how a row was WRITTEN, not what it means.

    Timestamp sub-second precision, amount rounding, identifier shape, null patterns.
    These are exactly the tells that appear when two different programs produce the two
    classes, and none of them should carry any signal about fraud.
    """
    ts = txns["timestamp"]
    amounts = txns["amount_inr"].to_numpy(dtype=float)
    cents = np.round((amounts - np.floor(amounts)) * 100).astype(int)

    return np.column_stack([
        ts.dt.microsecond.to_numpy(),
        ts.dt.second.to_numpy(),
        cents,
        (cents == 0).astype(int),
        np.floor(amounts) % 10,
        txns["transaction_id"].str[1:].astype(int).to_numpy() % 1000,
    ])


# Two things are deliberately NOT in this feature set, and both exclusions took a failing
# run to get right.
#
# Null patterns (merchant_id, session_id). A bank transfer genuinely has no merchant, and
# fraud does favour transfer rails, so nullity carries real signal about the transaction
# rather than about the program that wrote it.
#
# Raw entity identifiers (account_id, device_id). Handed the full identifier under a
# random split, a gradient-boosted tree simply memorises which accounts are mules and
# scores 0.99 - that is identity memorisation, not a formatting artefact, and it is
# exactly what the account-disjoint split in adl.evaluate.splits exists to prevent. The
# ordinal position of transaction_id stays in, because it tests something real: that
# identifiers are assigned after the run is sorted by time.


@pytest.fixture(scope="module")
def ledger():
    return simulate(n_transactions=60_000, seed=7, n_accounts=8_000)


def test_provenance_classifier_performs_at_chance(ledger) -> None:
    """Under the SAME split protocol the real detector uses.

    A random split makes this test measure something else. Fraudulent rows arrive in
    bursts that share a burst timestamp and occupy adjacent transaction ids, so a random
    split puts part of a burst in train and the rest in test, and the model memorises the
    burst rather than learning a formatting artefact. Every individual feature sat at
    chance while the combination reached 0.69 - all of it burst memorisation.

    Splitting by time and account, as adl.evaluate.splits does, means a burst cannot span
    the boundary and the number measures what it claims to.
    """
    txns = ledger.transactions
    frame = pd.DataFrame(
        _formatting_only(txns),
        columns=["microsecond", "second", "cents", "cents_zero", "rupee_digit", "txn_ordinal"],
    )
    frame["timestamp"] = txns["timestamp"].to_numpy()
    frame["account_id"] = txns["account_id"].to_numpy()
    frame["is_fraud"] = txns["is_fraud"].to_numpy().astype(int)

    split = time_and_account_split(frame, train_fraction=0.7, embargo_days=3)
    assert_leak_free(split)
    assert split.train["is_fraud"].sum() > 30, "not enough fraud in train to mean anything"
    assert split.test["is_fraud"].sum() > 10, "not enough fraud in test to mean anything"

    columns = ["microsecond", "second", "cents", "cents_zero", "rupee_digit", "txn_ordinal"]
    model = HistGradientBoostingClassifier(random_state=7).fit(
        split.train[columns].to_numpy(), split.train["is_fraud"].to_numpy()
    )
    auc = roc_auc_score(
        split.test["is_fraud"].to_numpy(),
        model.predict_proba(split.test[columns].to_numpy())[:, 1],
    )

    assert not np.isnan(auc)
    assert auc < PROVENANCE_AUC_CEILING, (
        f"provenance-only AUC {auc:.3f} exceeds {PROVENANCE_AUC_CEILING}: legitimate and "
        f"fraudulent rows are separable on formatting alone. Every downstream metric is "
        f"invalid until this is fixed. See PDF S5 and S10, rated Fatal."
    )


def test_account_identifiers_do_not_encode_mule_status(ledger) -> None:
    """Mules must be scattered through the identifier space.

    The first version of the simulator took the mule pool from the end of the account id
    range, which made the raw identifier predict the label at AUC 0.72 on its own. Nothing
    downstream can undo an id that encodes ground truth, so it is checked here directly
    rather than left to the provenance classifier to rediscover.
    """
    accounts = ledger.accounts
    ordinal = accounts["account_id"].str[1:].astype(int).to_numpy(dtype=float)
    is_mule = accounts["label_is_mule"].to_numpy().astype(int)
    auc = roc_auc_score(is_mule, ordinal)
    # Roughly fifty mules in a few thousand accounts, so the sampling error on this AUC is
    # around 0.04. The tolerance is set to leave room for that rather than to be tight for
    # its own sake; the selection is a uniform choice without replacement, so this is a
    # regression guard, not an estimate.
    assert abs(auc - 0.5) < 0.15, (
        f"account_id ordinal predicts mule status at AUC {auc:.3f}; the mule pool is not "
        f"scattered through the identifier space"
    )


def test_no_provenance_columns_exist_in_the_ledger(ledger) -> None:
    """The columns the contract forbids are absent by construction, not by filtering."""
    from adl.common.contracts import load_schema

    forbidden = set(load_schema("ledger")["properties"]["provenance_forbidden_columns"]["const"])
    for table in ("transactions", "sessions", "graph_edges"):
        assert not set(getattr(ledger, table).columns) & forbidden


def test_identifiers_carry_no_class_signal(ledger) -> None:
    """Identifiers are assigned after the run is sorted by time.

    If they were sequential by creation order, every attack instance would occupy a
    contiguous block of transaction_ids and the provenance classifier above would find it
    instantly - so this is the specific mechanism that test depends on.
    """
    txns = ledger.transactions
    numeric = txns["transaction_id"].str[1:].astype(int).to_numpy()
    fraud = txns["is_fraud"].to_numpy().astype(bool)
    auc = roc_auc_score(fraud.astype(int), numeric)
    assert abs(auc - 0.5) < 0.08, (
        f"transaction_id ordering predicts the label at AUC {auc:.3f}; identifiers are "
        f"leaking creation order"
    )
