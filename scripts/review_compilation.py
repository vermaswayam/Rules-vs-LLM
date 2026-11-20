"""Review saved Gemini policy candidates against sources and fixture gates.

This does not generate answers or contact a model. It preserves rejected drafts
and promotes only a candidate with no semantic policy differences after review.
"""
from decimal import Decimal, InvalidOperation
from common.io import ROOT, read_json, write_json, digest
from project_a.compiled import acceptance, load_policy
from project_a.policy import hand_policy
from project_a.llm_query import rule_text
import hashlib
import json


def equivalent(left, right):
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(equivalent(a,b) for a,b in zip(left,right))
    if isinstance(left, str) and isinstance(right, str):
        try:
            return Decimal(left) == Decimal(right)
        except InvalidOperation:
            return left == right
    return type(left) is type(right) and left == right


def review_and_promote():
    records = []
    for path in (ROOT/'artifacts/live').glob('*.json'):
        record = read_json(path)
        if record.get('experiment','').startswith('tax_compile_'):
            records.append(record)
    trials, accepted = [], {}
    for record in sorted(records, key=lambda r:r['created_at']):
        year = record['experiment'].removeprefix('tax_compile_')
        candidate, error, failures = None, None, []
        try:
            candidate = json.loads(record['response']['policy_json'])
            failures = acceptance(candidate,year)
            differences = [k for k,v in hand_policy(year).items() if not equivalent(candidate.get(k),v)]
            if failures or differences:
                error = f'{len(failures)} failed regime results; differing fields: {differences}'
        except (ValueError, TypeError, KeyError) as exc:
            error = str(exc)
        trial = {'financial_year':year,'request_sha256':record['request_sha256'],
                 'created_at':record['created_at'],'model':record['model'],
                 'latency_seconds':record['latency_seconds'],'paid_usd':record['projected_paid_usd'],
                 'gate_status':'accepted' if error is None else 'rejected','error':error}
        trials.append(trial)
        if candidate is not None:
            write_json(ROOT/f"artifacts/candidates/raw_{year}_{record['request_sha256'][:12]}.json",candidate)
        if error is None:
            accepted[year] = (candidate,trial)
    if set(accepted) != {'2024-25','2025-26'}:
        raise ValueError('Both financial years need a source-matching Gemini candidate before promotion')
    review = {'provider':'Gemini','reviewer':'Codex code/source review; no independent human legal approval claimed',
              'trials':trials,'policies':{}}
    for year,(candidate,trial) in accepted.items():
        path = ROOT/f'project_a/policies/compiled_{year}.json'
        bootstrap = ROOT/f'project_a/policies/bootstrap_codex_{year}.json'
        if not bootstrap.exists():
            write_json(bootstrap,read_json(path))
        write_json(path,candidate)
        review['policies'][year] = {'request_sha256':trial['request_sha256'],'sha256':digest(path),
             'source_bundle_sha256':hashlib.sha256(rule_text(year).encode()).hexdigest(),
             'review':'All policy fields match the source-derived reference semantically; frozen fixture gate passed. Decimal zero formatting is preserved.',
             'manual_policy_corrections':[]}
    load_policy.cache_clear()
    write_json(ROOT/'project_a/policies/review.json',review)
    return review


if __name__ == '__main__':
    review = review_and_promote()
    print(json.dumps({'reviewed_years':list(review['policies']), 'trial_statuses':[t['gate_status'] for t in review['trials']]}))
