"""Acquire real API evidence with bounded concurrency and one shared rate limiter.

Small experiment families run before bulk accuracy so a free quota does not get
spent on one family alone. The ordinary benchmark then replays these raw records.
"""
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from datetime import datetime, timezone
from common.gemini import GeminiUnavailable, ModelOutputError
from common.io import ROOT, read_json, write_json
from project_a.cohort import comparison_cases, repeat_case
from project_a.compiled import compile_with_gemini
from project_a.llm_query import calculate_with_llm
from project_a.models import TaxProfile
from project_b.benchmark import prepare_inputs, mixed_batch
from project_b.data import PROBLEMS
from project_b.injector import inject
from project_b.llm_review import review_with_llm
from project_b.hybrid import run_hybrid


def planned_jobs(client, rows_limit=1200, llm_rows=64, live_limit=None):
    cases = read_json(ROOT/'project_a/tests/fixtures/tax_cases.json')
    jobs = []
    for year in ['2024-25', '2025-26']:
        jobs.append((f'compile:{year}', lambda year=year: compile_with_gemini(year, client)))
    profile = TaxProfile.from_dict(repeat_case(cases)['input'])
    for index in range(10):
        jobs.append((f'consistency:{index}', lambda index=index: calculate_with_llm(profile, client, repeat=index)))
    new_cases = [c for c in cases if c['input']['financial_year'] == '2025-26']
    for case in new_cases[::max(1, len(new_cases)//5)][:5]:
        jobs.append(('stale:'+case['id'], lambda case=case: calculate_with_llm(TaxProfile.from_dict(case['input']), client, rule_year='2024-25')))
    _, _, _, reference, controls, cohort = prepare_inputs(rows_limit, llm_rows)
    jobs.append(('dq:control', lambda: review_with_llm(cohort, reference, client, 'dq_control')[1]))
    for problem in PROBLEMS:
        rows = inject(cohort, problem, .1, 71, reference)['rows']
        jobs.append(('dq:'+problem, lambda rows=rows, problem=problem: review_with_llm(rows, reference, client, 'dq_'+problem)[1]))
    mixed_rows, _ = mixed_batch(controls, reference)
    jobs.append(('hybrid:review', lambda: run_hybrid(mixed_rows, reference, client)['records'][0]))
    for case in comparison_cases(cases, live_limit):
        jobs.append(('tax:'+case['id'], lambda case=case: calculate_with_llm(TaxProfile.from_dict(case['input']), client)))
    return jobs


def acquire(client, rows_limit=1200, llm_rows=64, live_limit=None, workers=3):
    jobs = planned_jobs(client, rows_limit, llm_rows, live_limit)
    results = []
    pending = iter(jobs)
    stopped = False
    consecutive_unavailable = 0

    def invoke(name, action):
        try:
            record = action()
            return {'job': name, 'status': 'recorded', 'request_sha256': record['request_sha256'], 'replayed': record['replayed']}
        except ModelOutputError as exc:
            return {'job': name, 'status': 'rejected_output', 'error': str(exc), 'request_sha256': exc.record['request_sha256'], 'replayed': exc.record['replayed']}
        except GeminiUnavailable as exc:
            return {'job': name, 'status': 'unavailable', 'error': str(exc)}

    def checkpoint():
        write_json(ROOT/'artifacts/live_progress.json', {'started_jobs': len(results), 'planned_jobs': len(jobs), 'stopped_on_unavailable': stopped, 'updated_at': datetime.now(timezone.utc).isoformat(), 'results': results})

    print(f'Acquiring up to {len(jobs)} recorded experiments; {workers} workers, starts spaced by {client.interval:g}s', flush=True)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        running = {}
        def submit_next():
            try:
                name, action = next(pending)
            except StopIteration:
                return False
            running[executor.submit(invoke, name, action)] = name
            return True
        for _ in range(workers):
            submit_next()
        while running:
            done, _ = wait(running, return_when=FIRST_COMPLETED)
            for future in done:
                running.pop(future)
                result = future.result()
                results.append(result)
                print(f"{len(results)}/{len(jobs)} {result['job']}: {result['status']}{' (replay)' if result.get('replayed') else ''}", flush=True)
                if result['status'] == 'unavailable':
                    consecutive_unavailable += 1
                    # Quota/authentication errors need an external change; isolated
                    # 5xx failures should not discard the remaining experiment.
                    if 'HTTP 429' in result['error'] or 'HTTP 401' in result['error'] or 'HTTP 403' in result['error'] or consecutive_unavailable >= 3:
                        stopped = True
                elif not result.get('replayed'):
                    consecutive_unavailable = 0
                checkpoint()
            if not stopped:
                for _ in done:
                    submit_next()
    checkpoint()
    return results
