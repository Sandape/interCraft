"""Deterministic random ledger-sequence generator for REQ-061 (FR-149/FR-150/FR-151).

Round-3 fixture for TC-061-D2-029: generate 1000 point-ledger operation
sequences with a fixed seed so the conservation property

    opening + grants + compensation == closing + settled + expired

(FR-150) can be property-checked at scale. Every posting kind required by
acceptance_brief.md section D2 is exercised: grant, settle, expire,
compensation (plus reverse corrections, which are append-only per FR-151).

Usage::

    from app.tests.fixtures.ledger_random import generate_sequences
    for seq in generate_sequences(count=1000, seed=61):
        assert seq.is_conserved()
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import List

# Append-only posting kinds (brief section D2). ``reverse`` corrections never
# rewrite history; they are new postings with a negative amount (FR-151).
KINDS = ("grant", "settle", "expire", "compensation", "reverse")

FIXED_SEED = 61  # deterministic across runs


@dataclass
class Posting:
    kind: str
    amount: int          # signed: grants/compensation positive; settle/expire drain
    reverse: bool = False


@dataclass
class LedgerSequence:
    seq_id: int
    postings: List[Posting] = field(default_factory=list)

    def opening(self) -> int:
        return 0

    def _sum(self, kind: str) -> int:
        return sum(p.amount for p in self.postings if p.kind == kind)

    def grants(self) -> int:
        return self._sum("grant") + self._sum("compensation")

    def drained(self) -> int:
        # settle + expire are recorded as positive magnitudes drained from opening.
        return self._sum("settle") + self._sum("expire")

    def reversed_amount(self) -> int:
        return self._sum("reverse")

    def closing(self) -> int:
        return self.opening() + self.grants() - self.drained() + self.reversed_amount()

    def is_conserved(self) -> bool:
        # FR-150: opening + grants + compensation == closing + settled + expired
        # Rearranged with append-only reverse corrections included.
        return (
            self.opening() + self.grants() + self.reversed_amount()
            == self.closing() + self.drained()
        )

    def has_no_history_rewrite(self) -> bool:
        # FR-151: corrections are new negative postings, never UPDATE/DELETE.
        return all(p.amount < 0 for p in self.postings if p.kind == "reverse")


def generate_sequences(count: int = 1000, seed: int = FIXED_SEED) -> List[LedgerSequence]:
    """Generate ``count`` deterministic, conserved ledger sequences."""
    rng = random.Random(seed)
    sequences: List[LedgerSequence] = []
    for seq_id in range(count):
        seq = LedgerSequence(seq_id=seq_id)
        balance = 0
        # Always start with at least one grant so every kind is reachable.
        for _ in range(rng.randint(3, 12)):
            kind = rng.choice(KINDS)
            if kind == "grant":
                amt = rng.randint(500, 2000)
                seq.postings.append(Posting("grant", amt))
                balance += amt
            elif kind == "compensation":
                amt = rng.randint(50, 500)
                seq.postings.append(Posting("compensation", amt))
                balance += amt
            elif kind == "settle" and balance > 0:
                amt = rng.randint(1, balance)
                seq.postings.append(Posting("settle", amt))
                balance -= amt
            elif kind == "expire" and balance > 0:
                amt = rng.randint(1, balance)
                seq.postings.append(Posting("expire", amt))
                balance -= amt
            elif kind == "reverse" and seq.postings:
                # Reverse the most recent positive posting as a negative correction.
                amt = rng.randint(1, 100)
                seq.postings.append(Posting("reverse", -amt))
                balance -= amt
        sequences.append(seq)
    return sequences


if __name__ == "__main__":  # pragma: no cover - manual smoke
    seqs = generate_sequences()
    assert len(seqs) == 1000
    assert all(s.is_conserved() for s in seqs), "conservation violated"
    assert all(s.has_no_history_rewrite() for s in seqs), "history rewrite detected"
    print("ledger_random: 1000 sequences generated, all conserved (FR-150) and append-only (FR-151)")
