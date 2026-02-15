#!/usr/bin/env python3
"""QueryGate CLI - N+1 detection & query count regression gate."""
import sys
import json
import argparse
from querygate import load_baseline, save_baseline, check_regression, Gate

SYMBOLS = {"pass": "\u2713", "fail": "\u2717", "new": "\u25cf", "improved": "\u2b07"}


def cmd_check(args):
    """Check query counts against baseline, exit 1 on regression."""
    baseline = load_baseline(args.baseline)
    results = json.loads(open(args.results).read())
    failed = []
    for tid, count in sorted(results.items()):
        r = check_regression(baseline, tid, count, args.tolerance)
        sym = SYMBOLS[r["status"]]
        suffix = ""
        if r["status"] == "fail":
            suffix = f" (expected <={r['expected']}, +{r['delta']})"
            failed.append(tid)
        elif r["status"] == "improved":
            suffix = f" (was {r['expected']})"
        print(f"  {sym} {tid}: {count} queries{suffix}")
    print()
    if failed:
        print(f"\u2717 {len(failed)} regression(s) detected. Gate BLOCKED.")
        return 1
    print(f"\u2713 All {len(results)} test(s) passed query gate.")
    return 0


def cmd_baseline(args):
    """Save current results as the new baseline."""
    results = json.loads(open(args.results).read())
    save_baseline(results, args.baseline)
    print(f"\u2713 Baseline saved: {len(results)} test(s) -> {args.baseline}")
    return 0


def cmd_analyze(args):
    """Analyze raw SQL list for N+1 patterns."""
    queries = json.loads(open(args.queries).read())
    g = Gate()
    for q in queries:
        g.record(q)
    violations = g.detect_nplus1(args.threshold)
    if violations:
        for v in violations:
            print(f"  \u2717 N+1: {v['count']}x [{v['severity']}] {v['example'][:80]}")
        print(f"\n\u2717 {len(violations)} N+1 pattern(s) found in {g.count} queries.")
        return 1
    print(f"\u2713 No N+1 patterns in {g.count} queries.")
    return 0


def main():
    p = argparse.ArgumentParser(prog="querygate",
                                description="N+1 & query regression gate for CI")
    sub = p.add_subparsers(dest="cmd")
    ch = sub.add_parser("check", help="Check results against baseline")
    ch.add_argument("results", help="JSON {test_id: query_count}")
    ch.add_argument("-b", "--baseline", default=".querygate.json")
    ch.add_argument("-t", "--tolerance", type=int, default=0)
    bl = sub.add_parser("baseline", help="Save current results as baseline")
    bl.add_argument("results", help="JSON {test_id: query_count}")
    bl.add_argument("-b", "--baseline", default=".querygate.json")
    an = sub.add_parser("analyze", help="Detect N+1 in raw SQL list")
    an.add_argument("queries", help="JSON list of SQL strings")
    an.add_argument("-t", "--threshold", type=int, default=2)
    args = p.parse_args()
    if not args.cmd:
        p.print_help()
        return 1
    return {"check": cmd_check, "baseline": cmd_baseline,
            "analyze": cmd_analyze}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
