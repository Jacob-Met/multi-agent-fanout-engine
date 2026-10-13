"""Bounded independent review of task-ID native-content normalization.

This observes the pinned, unmodified public dispatcher. The paired control
normalizes the adapter's response before dispatch; it is not a source repair.
"""
from pathlib import Path
import argparse
import dataclasses
import hashlib
import json
import platform
import sqlite3
import sys


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source = args.source.resolve()
    manifest_path = source / 'SOURCE.json'
    manifest = json.loads(manifest_path.read_bytes())
    before = {row['path']: digest(source / row['path']) for row in manifest['files']}
    if any(before[row['path']] != row['sha256'] for row in manifest['files']):
        raise SystemExit('Pinned source changed')
    if args.output.exists():
        raise SystemExit('Output must be new')
    sys.path.insert(0, str(source))
    from fanout_engine import EffortRouter, Ledger, Plan, Route, dispatch_ready
    for module in ('fanout_engine', 'fanout_engine.dispatch', 'fanout_engine.ledger',
                   'fanout_engine.plan', 'fanout_engine.routing', 'fanout_engine.inspection'):
        if not Path(sys.modules[module].__file__).resolve().is_relative_to(source):
            raise SystemExit('Unexpected imported source: ' + module)
    literal = '  reçu-東京-🧭  '
    hooks = []

    class FalseyID(str):
        def __bool__(self):
            hooks.append('false')
            return False

    class RaisingID(str):
        def __bool__(self):
            hooks.append('raised')
            raise RuntimeError('local truthiness fixture')

    cases = []
    for kind in (FalseyID, RaisingID):
        for mode in ('raw-adapter-id', 'native-string-adapter-control'):
            hooks.clear()
            value = kind(literal)
            if mode == 'native-string-adapter-control':
                value = str.__str__(value)
            plan = Plan.from_dict({'project': kind.__name__ + '-' + mode, 'parts': [
                {'id': 'first', 'instruction': 'Retain the exact local acknowledgement.'},
                {'id': 'independent', 'instruction': 'Receive unrelated local work.'},
                {'id': 'dependent', 'instruction': 'Wait for first.', 'depends_on': ['first']},
            ]})
            calls = []

            class LocalHub:
                def submit(self, part, *, route, worker_id, idempotency_key):
                    calls.append(part.id)
                    return {'task_id': value if part.id == 'first' else 'local-independent'}

            router = EffortRouter({'local-model': ['low']}, pool=[Route('local-model', 'low')])
            error = None
            report = None
            with Ledger() as ledger:
                try:
                    report = dataclasses.asdict(dispatch_ready(
                        plan, ledger, LocalHub(), router, worker_for=lambda part: 'local-worker'))
                except Exception as exc:
                    error = {'type': type(exc).__name__, 'message': str(exc)}
                snapshot = ledger.project_snapshot(plan.project_id)
                parts = {row['part_id']: {'state': row['state'], 'task_id': row['task_id']}
                         for row in snapshot['parts']}
                events = [{'event': row['event'], 'part_id': row['part_id'], 'detail': row['detail']}
                          for row in ledger.events(plan.project_id)]
            case = {'class': kind.__name__, 'mode': mode, 'adapter_return_type': type(value).__name__,
                    'literal': literal, 'hook_calls': list(hooks), 'exception': error,
                    'report': report, 'parts': parts, 'events': events, 'submissions': calls}
            case['expected_valid_receipt_workflow'] = (
                error is None and parts['first'] == {'state': 'running', 'task_id': literal}
                and parts['independent']['state'] == 'running' and parts['dependent']['state'] == 'queued'
                and calls == ['first', 'independent'])
            if mode == 'native-string-adapter-control' and not case['expected_valid_receipt_workflow']:
                raise SystemExit('Native string control failed')
            cases.append(case)
    after = {path: digest(source / path) for path in before}
    if after != before:
        raise SystemExit('Source changed during review')
    result = {'scope': 'Four paired in-memory SQLite dispatch observations; no source overlay, provider, or native qualification.',
              'source_commit': manifest['commit'], 'source_tree': manifest['tree'],
              'source_manifest_sha256': digest(manifest_path), 'source_files_preserved': after,
              'python': platform.python_version(), 'sqlite': sqlite3.sqlite_version,
              'runner_sha256': digest(Path(__file__)), 'cases': cases}
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + '\n')
    print(json.dumps({'receipt': str(args.output), 'receipt_sha256': digest(args.output),
                      'cases': [{'class': row['class'], 'mode': row['mode'], 'exception': row['exception'],
                                 'parts': row['parts'], 'matches': row['expected_valid_receipt_workflow']}
                                for row in cases]}, sort_keys=True))


if __name__ == '__main__':
    main()
