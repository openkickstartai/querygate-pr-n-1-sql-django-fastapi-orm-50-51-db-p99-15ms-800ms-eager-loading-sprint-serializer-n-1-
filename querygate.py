"""QueryGate - N+1 query detection & query count regression gate."""
import re
import json
import hashlib
from pathlib import Path
from collections import Counter
from contextlib import contextmanager


def fingerprint(sql):
    """Normalize SQL to a canonical fingerprint, replacing all literals."""
    s = re.sub(r"'[^']*'", "?", sql)
    s = re.sub(r"\b\d+\b", "?", s)
    s = re.sub(r"\s+", " ", s).strip().upper()
    return hashlib.md5(s.encode()).hexdigest()[:12]


class Gate:
    """Track SQL queries, detect N+1 patterns, enforce query budgets."""

    def __init__(self, budget=None):
        self.queries = []
        self.budget = budget

    def record(self, sql):
        self.queries.append(sql)

    @property
    def count(self):
        return len(self.queries)

    def detect_nplus1(self, threshold=2):
        """Find query fingerprints repeated more than threshold times."""
        fps = Counter(fingerprint(q) for q in self.queries)
        results = []
        for fp, n in fps.items():
            if n > threshold:
                example = next(q for q in self.queries if fingerprint(q) == fp)
                results.append({"fingerprint": fp, "count": n, "example": example,
                                "severity": "critical" if n > 10 else "warning"})
        return sorted(results, key=lambda x: -x["count"])

    def assert_budget(self):
        if self.budget is not None and self.count > self.budget:
            raise BudgetExceeded(
                f"Query budget exceeded: {self.count} > {self.budget}")

    def reset(self):
        self.queries.clear()


class BudgetExceeded(Exception):
    """Raised when query count exceeds the configured budget."""


@contextmanager
def track(budget=None):
    """Context manager that tracks queries and enforces budget on exit."""
    g = Gate(budget=budget)
    yield g
    g.assert_budget()


def load_baseline(path=".querygate.json"):
    p = Path(path)
    return json.loads(p.read_text()) if p.exists() else {}


def save_baseline(data, path=".querygate.json"):
    Path(path).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def check_regression(baseline, test_id, current, tolerance=0):
    """Compare current query count against baseline. Returns status dict."""
    if test_id not in baseline:
        return {"status": "new", "current": current}
    expected = baseline[test_id]
    if current > expected + tolerance:
        return {"status": "fail", "expected": expected,
                "current": current, "delta": current - expected}
    if current < expected:
        return {"status": "improved", "expected": expected, "current": current}
    return {"status": "pass", "expected": expected, "current": current}
