"""Leak-free splitting.

PDF S6.2 requires both conditions, not either: split by time AND by account. An
unqualified random split leaks in two directions - the same account appears in both
halves, and future transactions train a model evaluated on the past.

Rows that fail either condition are dropped rather than reassigned. The dropped count is
reported: a split that silently discards half the data is a different experiment from the
one being described.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class Split:
    train: pd.DataFrame
    test: pd.DataFrame
    cut: pd.Timestamp
    embargo_days: int
    n_dropped_time: int
    n_dropped_account: int

    def describe(self) -> str:
        total = len(self.train) + len(self.test) + self.n_dropped_time + self.n_dropped_account
        return (
            f"train {len(self.train):,} · test {len(self.test):,} · "
            f"dropped {self.n_dropped_time:,} to the embargo and "
            f"{self.n_dropped_account:,} to account disjointness "
            f"({(self.n_dropped_time + self.n_dropped_account) / total:.1%} of rows) · "
            f"cut at {self.cut:%Y-%m-%d}"
        )


def _account_bucket(account_id: str, salt: str = "adl-split-v1") -> float:
    digest = hashlib.blake2b(f"{salt}:{account_id}".encode(), digest_size=8).digest()
    return int.from_bytes(digest, "big") / 2**64


def time_and_account_split(
    features: pd.DataFrame,
    train_fraction: float = 0.7,
    embargo_days: int = 3,
    account_train_fraction: float | None = None,
) -> Split:
    """Train on the earlier window and the train accounts; test on the later window and
    the test accounts. Nothing crosses either boundary.

    ``account_train_fraction`` defaults to ``train_fraction``. It is deterministic in the
    account id, so the same account lands on the same side across runs and across
    generations of the loop - otherwise generation 3 would be evaluated on accounts that
    generation 2 trained on.
    """
    account_train_fraction = (
        train_fraction if account_train_fraction is None else account_train_fraction
    )
    ts = pd.to_datetime(features["timestamp"], utc=True)
    cut = ts.quantile(train_fraction)
    embargo_end = cut + pd.Timedelta(days=embargo_days)

    bucket = features["account_id"].map(_account_bucket)
    in_train_accounts = bucket < account_train_fraction

    before = ts <= cut
    after = ts >= embargo_end

    train_mask = before & in_train_accounts
    test_mask = after & ~in_train_accounts

    n_dropped_time = int((~before & ~after).sum())
    n_dropped_account = int(
        ((before & ~in_train_accounts) | (after & in_train_accounts)).sum()
    )

    return Split(
        train=features[train_mask].copy(),
        test=features[test_mask].copy(),
        cut=cut,
        embargo_days=embargo_days,
        n_dropped_time=n_dropped_time,
        n_dropped_account=n_dropped_account,
    )


def assert_leak_free(split: Split) -> None:
    """Cheap, and the failure it catches is expensive."""
    shared = set(split.train["account_id"]) & set(split.test["account_id"])
    if shared:
        raise AssertionError(
            f"{len(shared)} accounts appear in both halves, e.g. {sorted(shared)[:3]}"
        )
    if not split.train.empty and not split.test.empty:
        latest_train = pd.to_datetime(split.train["timestamp"], utc=True).max()
        earliest_test = pd.to_datetime(split.test["timestamp"], utc=True).min()
        if earliest_test <= latest_train:
            raise AssertionError(
                f"test window starts {earliest_test} before train ends {latest_train}"
            )
        gap_days = (earliest_test - latest_train).total_seconds() / 86400
        if gap_days < split.embargo_days - 1e-6:
            raise AssertionError(f"embargo gap {gap_days:.2f}d < {split.embargo_days}d")


def prevalence(frame: pd.DataFrame) -> float:
    return float(np.mean(frame["is_fraud"])) if len(frame) else 0.0
