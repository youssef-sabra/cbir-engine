"""Unit tests for the retrieval-quality metric math."""

from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

# Load the sibling module by path (it's a script, not an installed package).
_spec = importlib.util.spec_from_file_location(
    "retrieval_quality", Path(__file__).resolve().parents[1] / "retrieval_quality.py"
)
rq = importlib.util.module_from_spec(_spec)
# Register before exec so dataclass __module__ resolution works.
sys.modules["retrieval_quality"] = rq
_spec.loader.exec_module(rq)


def _e(ranked, relevant):
    return rq.QueryEval(query="q", ranked_ids=ranked, relevant_ids=set(relevant))


def test_recall_at_k():
    assert rq.recall_at_k(_e(["a", "b", "c"], ["a", "b"]), 3) == 1.0
    assert rq.recall_at_k(_e(["a", "x", "y"], ["a", "b"]), 3) == 0.5
    assert rq.recall_at_k(_e(["x", "y", "a"], ["a"]), 2) == 0.0  # relevant beyond k


def test_precision_at_k():
    assert rq.precision_at_k(_e(["a", "b", "x"], ["a", "b"]), 2) == 1.0
    assert rq.precision_at_k(_e(["a", "x", "y"], ["a"]), 2) == 0.5


def test_mrr():
    assert rq.reciprocal_rank(_e(["a", "b"], ["a"])) == 1.0
    assert rq.reciprocal_rank(_e(["x", "a"], ["a"])) == 0.5
    assert rq.reciprocal_rank(_e(["x", "y"], ["a"])) == 0.0


def test_ndcg_perfect_and_imperfect():
    perfect = rq.ndcg_at_k(_e(["a", "b"], ["a", "b"]), 2)
    assert math.isclose(perfect, 1.0)
    # one relevant at rank 2 only: dcg = 1/log2(3); idcg = 1 (one relevant)
    partial = rq.ndcg_at_k(_e(["x", "a"], ["a"]), 2)
    assert math.isclose(partial, 1.0 / math.log2(3))


def test_evaluate_aggregates():
    evals = [_e(["a", "b"], ["a", "b"]), _e(["x", "a"], ["a"])]
    metrics = rq.evaluate(evals, k=2)
    assert set(metrics) == {"recall@2", "precision@2", "mrr", "ndcg@2"}
    assert metrics["mrr"] == (1.0 + 0.5) / 2


def test_fixture_eval_set_passes_default_thresholds():
    path = Path(__file__).resolve().parents[1] / "eval_set.json"
    metrics = rq.evaluate(rq.load_offline(str(path)), k=10)
    # The committed fixture is constructed to clear the 0.8 gate.
    assert metrics["recall@10"] >= 0.8
    assert metrics["ndcg@10"] >= 0.8
    assert metrics["mrr"] >= 0.8
