"""Observe acknowledgement admission using literal blank/nonblank SQLite controls."""
from pathlib import Path
import argparse
import dataclasses
import hashlib
import json
import platform
import sqlite3
import sys


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source, output = args.source.resolve(), args.output.resolve()
    source_manifest = json.loads((source / 'SOURCE.json').read_bytes())
    preserved = {row['path']: sha(source / row['path']) for row in source_manifest['files']}
    if any(preserved[row['path']] != row['sha256'] for row in source_manifest['files']):
        raise SystemExit('Pinned source changed')
    sys.path.insert(0, str(source))
    from fanout_engine import EffortRouter, Ledger, Plan, Route, dispatch_ready
    for module in ('fanout_engine', 'fanout_engine.dispatch', 'fanout_engine.ledger',
                   'fanout_engine.plan', 'fanout_engine.routing', 'fanout_engine.inspection'):
        if not Path(sys.modules[module].__file__).resolve().is_relative_to(source):
            raise SystemExit('Unexpected imported source: ' + module)
    output.mkdir(parents=True, exist_ok=False)
    database = output / 'retained.sqlite3'
    strip_calls = []

    class MisleadingStrip(str):
        def strip(self, *args, **kwargs):
            strip_calls.append('misleading')
            return 'apparently-nonblank'

    class RefusingStrip(str):
        def strip(self, *args, **kwargs):
            strip_calls.append('refusing')
            return ''

    blank = ' \t \n'
    valid = '  reçu-東京-🧭  '
    fixtures = [
        ('ordinary-blank', blank, False),
        ('overridden-blank', MisleadingStrip(blank), False),
        ('ordinary-valid', valid, True),
        ('overridden-valid', RefusingStrip(valid), True),
    ]
    rows = []
    for label, task_id, expected_accepted in fixtures:
        plan = Plan.from_dict({
            'project': 'task-id-strip-' + label,
            'parts': [
                {'id': 'first', 'instruction': 'Receive the literal task identifier.'},
                {'id': 'independent', 'instruction': 'Receive unrelated local work.'},
                {'id': 'dependent', 'instruction': 'Wait for the first result.', 'depends_on': ['first']},
            ],
        })
        calls = []

        class LocalHub:
            def submit(self, part, *, route, worker_id, idempotency_key):
                calls.append({'part': part.id, 'key': idempotency_key})
                return {'task_id': task_id if part.id == 'first' else 'local-independent'}

        router = EffortRouter({'local-model': ['low']}, pool=[Route('local-model', 'low')])
        with Ledger(str(database)) as ledger:
            report = dispatch_ready(plan, ledger, LocalHub(), router, worker_for=lambda part: 'local-worker')
            first = ledger.part(plan.project_id, 'first')
            events = ledger.events(plan.project_id, 'first')
        before_readonly = sha(database)
        with Ledger.open_readonly(database) as readonly:
            reopened = readonly.part(plan.project_id, 'first')
            reopened_events = readonly.events(plan.project_id, 'first')
        with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True) as connection:
            stored_task_id, stored_type = connection.execute(
                "SELECT task_id, typeof(task_id) FROM parts WHERE project_id=? AND part_id='first'",
                (plan.project_id,),
            ).fetchone()
        expected_state = 'running' if expected_accepted else 'outcome_unknown'
        checks = {
            'expected_state': first['state'] == expected_state,
            'expected_task_id': stored_task_id == (valid if expected_accepted else None),
            'unrelated_part_started': 'independent' in report.started,
            'dependent_remains_blocked': report.not_ready == ('dependent',),
            'two_local_submissions_only': [row['part'] for row in calls] == ['first', 'independent'],
            'readonly_reopen_matches': first == reopened and events == reopened_events,
            'readonly_database_unchanged': sha(database) == before_readonly,
        }
        rows.append({
            'case': label, 'input_text': str(task_id), 'input_type': type(task_id).__name__,
            'expected_accepted': expected_accepted, 'expected_state': expected_state,
            'observed_state': first['state'], 'stored_task_id': stored_task_id,
            'sqlite_storage_type': stored_type, 'report': dataclasses.asdict(report),
            'retained_part': first, 'retained_events': events, 'submissions': calls,
            'checks': checks, 'contract_matches': all(checks.values()),
        })
    preserved_after = {path: sha(source / path) for path in preserved}
    if preserved_after != preserved:
        raise SystemExit('Source changed during reproduction')
    if not all(row['checks']['readonly_reopen_matches'] and row['checks']['readonly_database_unchanged']
               and row['checks']['unrelated_part_started'] for row in rows):
        raise SystemExit('Fixture preservation/control failed')
    violations = [row['case'] for row in rows if not row['contract_matches']]
    result = {
        'scope': 'Four literal task-ID fixtures through current pinned dispatch and actual retained SQLite. New counterexample only; no provider or accepted772 receiving change.',
        'source_commit': source_manifest['commit'], 'source_tree': source_manifest['tree'],
        'source_manifest_sha256': sha(source / 'SOURCE.json'),
        'python': platform.python_version(), 'sqlite': sqlite3.sqlite_version,
        'database': str(database), 'database_sha256': sha(database),
        'source_files_preserved': preserved, 'strip_override_calls': strip_calls,
        'observed_contract_violations': violations, 'cases': rows,
        'originating_owner': {'pr': 25, 'branch': 'estate/0be8845b-native-string-receipts'},
        'runner_sha256': sha(Path(__file__)),
    }
    receipt = output / 'receipt.json'
    receipt.write_text(json.dumps(result, sort_keys=True, indent=2) + '\n')
    print(json.dumps({'source_commit': source_manifest['commit'],
                      'violations': violations,
                      'observed': {row['case']: {'state': row['observed_state'],
                                   'stored_task_id': row['stored_task_id']} for row in rows},
                      'receipt_sha256': sha(receipt), 'database_sha256': sha(database)}, sort_keys=True))


if __name__ == '__main__':
    main()
