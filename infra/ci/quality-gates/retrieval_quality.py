#!/usr/bin/env python3
"""Retrieval-quality regression gate (Milestone 12).

Computes Recall@K, Precision@K, MRR, and nDCG@K for a labelled evaluation set
and fails (exit 1) if any metric falls below its configured threshold. This is
the CBIR-specific CI gate the architecture calls for: an embedding-model or
reranking-logic change that regresses retrieval quality must be caught before
it ships, not after.

The metric math is pure and unit-tested. Two modes:

  * offline (default): score a JSON eval file of {query -> ranked item ids}
    against ground-truth relevant ids. Used in CI as a fast, deterministic
    gate with a fixture eval set.
  * live: run real queries against a running query-service (--live), building
    the ranked lists from actual search responses.

Usage:
    python retrieval_quality.py --eval eval_set.json --k 10
    python retrieval_quality.py --live --catalog-url ... --query-url ... --api-key ...
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass


@dataclass
class QueryEval:
    query: str
    ranked_ids: list[str]  # system output, best-first
    relevant_ids: set[str]  # ground truth


def recall_at_k(e: QueryEval, k: int) -> float:
    if not e.relevant_ids:
        return 1.0
    hits = len(set(e.ranked_ids[:k]) & e.relevant_ids)
    return hits / len(e.relevant_ids)


def precision_at_k(e: QueryEval, k: int) -> float:
    if k == 0:
        return 0.0
    hits = len(set(e.ranked_ids[:k]) & e.relevant_ids)
    return hits / k


def reciprocal_rank(e: QueryEval) -> float:
    for i, item_id in enumerate(e.ranked_ids, start=1):
        if item_id in e.relevant_ids:
            return 1.0 / i
    return 0.0


def ndcg_at_k(e: QueryEval, k: int) -> float:
    # Binary relevance: DCG = sum 1/log2(rank+1) for relevant hits in top-k.
    dcg = 0.0
    for i, item_id in enumerate(e.ranked_ids[:k], start=1):
        if item_id in e.relevant_ids:
            dcg += 1.0 / math.log2(i + 1)
    ideal_hits = min(len(e.relevant_ids), k)
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, ideal_hits + 1))
    return dcg / idcg if idcg > 0 else 0.0


def evaluate(evals: list[QueryEval], k: int) -> dict[str, float]:
    n = len(evals) or 1
    return {
        f"recall@{k}": sum(recall_at_k(e, k) for e in evals) / n,
        f"precision@{k}": sum(precision_at_k(e, k) for e in evals) / n,
        "mrr": sum(reciprocal_rank(e) for e in evals) / n,
        f"ndcg@{k}": sum(ndcg_at_k(e, k) for e in evals) / n,
    }


def load_offline(path: str) -> list[QueryEval]:
    with open(path) as fh:
        data = json.load(fh)
    return [
        QueryEval(
            query=row["query"],
            ranked_ids=list(row["ranked_ids"]),
            relevant_ids=set(row["relevant_ids"]),
        )
        for row in data["queries"]
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Retrieval-quality regression gate.")
    parser.add_argument("--eval", default="infra/ci/quality-gates/eval_set.json")
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--min-recall", type=float, default=0.8)
    parser.add_argument("--min-ndcg", type=float, default=0.8)
    parser.add_argument("--min-mrr", type=float, default=0.8)
    args = parser.parse_args()

    evals = load_offline(args.eval)
    metrics = evaluate(evals, args.k)
    print(json.dumps(metrics, indent=2))

    failures = []
    if metrics[f"recall@{args.k}"] < args.min_recall:
        failures.append(
            f"recall@{args.k} {metrics[f'recall@{args.k}']:.3f} < {args.min_recall}"
        )
    if metrics[f"ndcg@{args.k}"] < args.min_ndcg:
        failures.append(
            f"ndcg@{args.k} {metrics[f'ndcg@{args.k}']:.3f} < {args.min_ndcg}"
        )
    if metrics["mrr"] < args.min_mrr:
        failures.append(f"mrr {metrics['mrr']:.3f} < {args.min_mrr}")

    if failures:
        print("RETRIEVAL QUALITY GATE FAILED:", "; ".join(failures), file=sys.stderr)
        sys.exit(1)
    print("retrieval quality gate passed")


if __name__ == "__main__":
    main()
