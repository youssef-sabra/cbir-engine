"""Perceptual-hash deduplication (FR1.2)."""

from __future__ import annotations


def hamming_distance(a: str, b: str) -> int:
    """Bit difference between two hex perceptual hashes. aHash makes
    perceptually similar images differ in only a few bits."""
    return bin(int(a, 16) ^ int(b, 16)).count("1")


def find_duplicate(phash: str, existing: list[tuple[str, str]], threshold: int) -> str | None:
    """Return the id of the closest existing item within `threshold` bits, or
    None. Ties resolve to the first (most-recently-indexed, per the store's
    ordering) — deterministic."""
    best_id: str | None = None
    best_distance = threshold + 1
    for item_id, existing_phash in existing:
        if not existing_phash:
            continue
        distance = hamming_distance(phash, existing_phash)
        if distance <= threshold and distance < best_distance:
            best_id, best_distance = item_id, distance
            if distance == 0:
                break
    return best_id
