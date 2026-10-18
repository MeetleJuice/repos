"""Repeatable deterministic-review benchmark. No model requests or generated code execution."""
import ast
import json
from pathlib import Path
import platform
import statistics
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from forge import __version__
from forge.contracts import review_plan


def main() -> None:
    data = Path(__file__).with_name('fixture_data')
    # Trusted validation function copied from our published 0.5 archive, not uploaded code.
    tree = ast.parse((data / 'validator-v05.txt').read_text())
    namespace = {'json': json}
    exec(compile(tree, 'published-v05-validator', 'exec'), namespace)
    baseline = namespace['validate_plan']
    cases = [json.loads((data / f'notes-plan-{number}.json').read_text()) for number in [1, 2]]
    times = []
    for _ in range(1000):
        started = time.perf_counter_ns()
        for case in cases:
            review_plan(case, 'notes')
        times.append((time.perf_counter_ns() - started) / len(cases) / 1e6)
    report = {'version': __version__, 'python': platform.python_version(), 'platform': platform.system(),
              'cases': len(cases), 'baseline_bad_cases_accepted': sum(bool(baseline(case)) for case in cases),
              'new_bad_cases_accepted': sum(review_plan(case, 'notes').passed for case in cases),
              'batch_samples': len(times), 'review_ms_median': round(statistics.median(times), 4),
              'review_ms_p95': round(sorted(times)[949], 4),
              'scope': 'Per-proposal time averaged over each two-case batch. No live model or GPU benchmark.'}
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
