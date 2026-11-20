"""Export only the recorded assignment jobs, never arbitrary service requests."""
import re
from common.gemini import Gemini
from common.io import ROOT, read_json, write_json, digest


def export():
    identifiers = set()
    for name in ['live_progress.json', 'live_progress_initial_503.json']:
        path = ROOT / 'artifacts' / name
        if path.exists():
            for row in read_json(path)['results']:
                identifier = row.get('request_sha256')
                if identifier and re.fullmatch(r'[0-9a-f]{64}', identifier):
                    identifiers.add(identifier)
    client = Gemini()
    output = ROOT / 'data/experiments/gemini'
    output.mkdir(parents=True, exist_ok=True)
    written = []
    for identifier in sorted(identifiers):
        source = ROOT / 'artifacts/live' / (identifier + '.json')
        if not source.exists():
            continue
        raw = source.read_bytes()
        if client.key and client.key.encode() in raw:
            raise ValueError('A benchmark evidence record contains the configured key; export stopped')
        record = read_json(source)
        if record.get('request_sha256') != identifier:
            raise ValueError('Evidence identifier mismatch')
        target = output / source.name
        target.write_bytes(raw)
        written.append({'request_sha256': identifier, 'sha256': digest(target), 'experiment': record.get('experiment')})
    write_json(ROOT/'data/experiments/manifest.json', {'scope':'Only named assignment benchmark jobs; public 311 and synthetic tax/PII inputs.', 'records':written})
    return len(written)


if __name__ == '__main__':
    print('Exported benchmark evidence records:', export())
