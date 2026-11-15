"""Referral reward ladder: the more friends you bring, the more each new friend is worth, up to the cap."""
from __future__ import annotations

BASE, STEP = 300, 100


def referral_reward(previous_refs: int, cap: int = 700) -> int:
    """Coins for the next referral. 300, 400, 500, 600, then 700 (the cap) for every friend after that."""
    return max(1, min(cap, BASE + STEP * max(0, previous_refs)))
