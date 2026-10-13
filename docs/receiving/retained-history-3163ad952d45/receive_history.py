"""Receive the published history CLI on one original retained workflow."""
from pathlib import Path, PurePosixPath
import argparse
import collections
import datetime
import hashlib
import json
import platform
import socket
import sqlite3
import subprocess
import sys

COMMIT = '6d76703f8a3d5a29e56bf9fab97523935b06e61c'
TREE = '831af49f435ba629c99c4ac6ab3ab0a1ecde58ce'
MANIFEST_SHA = 'b30b12a07ebf0e4dd06252ffa206d35b763e6c76fcf1d0eae19f28ef18622e3a'
DATABASE_SHA = 'e17a509e8407d150ee9df3d80e24c6d4f99adaefb09534c8e9aa2bf4916a713d'
PROJECT = 'native-dataset-review'
PART = 'map-05'


def encode(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(',', ':'), allow_nan=False) + '\n').encode('utf-8')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def verify_source(source):
    require(not source.is_symlink(), 'Source root must not be a symlink')
    manifest = json.loads((source / 'SOURCE.json').read_bytes())
    require(sha(source / 'SOURCE.json') == MANIFEST_SHA, 'Manifest differs')
    require(manifest['repository'] == 'Jacob-Met/multi-agent-fanout-engine'
            and manifest['commit'] == COMMIT and manifest['tree'] == TREE,
            'Source identity differs')
    rows = manifest['files']
    require(len(rows) == 10 and len({r['path'] for r in rows}) == 10,
            'Selected inventory differs')
    expected = {'SOURCE.json'} | {r['path'] for r in rows}
    require({str(p.relative_to(source)) for p in source.rglob('*') if p.is_file()} == expected,
            'Unexpected or missing selected file')
    found = {'SOURCE.json': MANIFEST_SHA}
    for row in rows:
        rel = PurePosixPath(row['path'])
        path = source / rel
        require(not rel.is_absolute() and '..' not in rel.parts
                and not any(p.is_symlink() for p in [path, *path.parents]), 'Unsafe source path')
        body = path.read_bytes()
        blob = hashlib.sha1(b'blob ' + str(len(body)).encode() + b'\0' + body).hexdigest()
        require(len(body) == row['bytes'] and sha(path) == row['sha256']
                and blob == row['git_blob'], 'Source differs: ' + row['path'])
        found[row['path']] = row['sha256']
    return found


def sidecars(database):
    return {s: sha(Path(str(database) + s)) if Path(str(database) + s).is_file() else None
            for s in ('-wal', '-shm', '-journal')}


def direct_snapshot(database):
    """Read complete persisted rows without importing the selected package."""
    db = sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    try:
        db.execute('BEGIN')
        return {
            'projects': [dict(r) for r in db.execute('SELECT * FROM projects ORDER BY project_id')],
            'parts': [dict(r) for r in db.execute('SELECT * FROM parts ORDER BY project_id,part_id')],
            'events': [dict(r) for r in db.execute('SELECT * FROM events ORDER BY seq')],
            'sqlite_sequence': [dict(r) for r in db.execute('SELECT * FROM sqlite_sequence ORDER BY name')],
        }
    finally:
        db.close()


def expected_reports(snapshot):
    require(len(snapshot['projects']) == 1 and snapshot['projects'][0]['project_id'] == PROJECT,
            'Retained project differs')
    project = snapshot['projects'][0]
    plan = json.loads(project['plan_json'])
    require(len(plan['parts']) == 26 and len(snapshot['parts']) == 26
            and all(r['state'] == 'completed' for r in snapshot['parts']),
            'Retained completed parts differ')
    events = snapshot['events']
    require(len(events) == 79 and all(r['project_id'] == PROJECT for r in events),
            'Retained event inventory differs')
    require(dict(collections.Counter(r['event'] for r in events)) == {
        'plan_recorded': 1, 'dispatch_started': 26, 'dispatch_accepted': 25,
        'completed': 25, 'outcome_unknown': 1, 'reconciled': 1}, 'Retained event counts differ')
    selected = [r for r in events if r['part_id'] == PART]
    require([r['event'] for r in selected] == ['dispatch_started', 'outcome_unknown', 'reconciled'],
            'Retained map-05 sequence differs')
    reports = {}
    for label, part in [('project', None), ('map-05', PART)]:
        reports[label] = {
            'schema_version': 1, 'project_id': PROJECT, 'plan_digest': project['plan_digest'],
            'part_id': part,
            'events': [{**r, 'detail': json.loads(r['detail_json'])} for r in events
                       if part is None or r['part_id'] == part],
        }
    return reports


def run_cli(label, command, source, output, environment):
    try:
        result = subprocess.run(command, cwd=source, env=environment,
                                capture_output=True, timeout=30)
        stdout, stderr = result.stdout, result.stderr
        op = {'command': command, 'exit_code': result.returncode, 'timed_out': False}
    except subprocess.TimeoutExpired as exc:
        stdout, stderr = exc.stdout or b'', exc.stderr or b''
        op = {'command': command, 'exit_code': None, 'timed_out': True,
              'timeout_seconds': exc.timeout}
    (output / (label + '.stdout')).write_bytes(stdout)
    (output / (label + '.stderr')).write_bytes(stderr)
    op.update(label=label, stdout_sha256=hashlib.sha256(stdout).hexdigest(),
              stdout_bytes=len(stdout), stderr_sha256=hashlib.sha256(stderr).hexdigest())
    (output / (label + '.operation.json')).write_bytes(encode(op))
    return op


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source, database, output = args.source.absolute(), args.database.absolute(), args.output.absolute()
    require(database.is_file() and not database.is_symlink() and sha(database) == DATABASE_SHA,
            'Original retained database differs')
    source_before = verify_source(source)
    require(not output.exists() and not output.is_symlink(), 'Choose a fresh output; inspect old operations before retry')
    output.mkdir(parents=True, exist_ok=False)
    for folder in ('home', 'tmp'):
        (output / folder).mkdir()
    before_sidecars = sidecars(database)
    environment = {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8',
                   'HOME': str(output / 'home'), 'TMPDIR': str(output / 'tmp')}
    receipt = {
        'schema': 'hamon.fanout.retained-history.receiving.v1',
        'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'source_commit': COMMIT, 'source_tree': TREE, 'source_manifest_sha256': MANIFEST_SHA,
        'host': socket.gethostname(), 'python': platform.python_version(),
        'sqlite': sqlite3.sqlite_version, 'platform': platform.platform(),
        'driver_sha256': sha(Path(__file__)), 'database': str(database),
        'database_before_sha256': DATABASE_SHA, 'source_before': source_before,
        'scope': 'Two read-only history CLI processes on the original 26-part/79-event ledger. Recording order only; no dispatch, retry, reconciliation, provider or service operation.',
        'operations': [], 'accepted': False,
    }
    try:
        snapshot = direct_snapshot(database)
        reports = expected_reports(snapshot)
        (output / 'direct-ledger-snapshot.json').write_bytes(encode(snapshot))
        for label, report in reports.items():
            expected = encode(report)
            (output / (label + '.expected.json')).write_bytes(expected)
            command = [sys.executable, '-B', '-S', '-m', 'fanout_engine.history',
                       '--database', str(database), '--project', PROJECT]
            if report['part_id'] is not None:
                command += ['--part', report['part_id']]
            op = run_cli(label, command, source, output, environment)
            receipt['operations'].append(op)
            require(op['exit_code'] == 0 and not op['timed_out'], 'History process did not complete: ' + label)
            require((output / (label + '.stdout')).read_bytes() == expected,
                    'Complete history bytes differ from raw rows: ' + label)
            require((output / (label + '.stderr')).read_bytes() == b'', 'Unexpected diagnostic: ' + label)
            require(sha(database) == DATABASE_SHA and sidecars(database) == before_sidecars,
                    'Database or sidecars changed: ' + label)
        require(direct_snapshot(database) == snapshot, 'Complete persisted rows changed')
        require(verify_source(source) == source_before, 'Selected source changed')
        receipt.update(accepted=True, project_events=79, part_events=3,
                       map_05_recorded_sequence=[r['event'] for r in reports['map-05']['events']],
                       checks={'project_complete_bytes_match': True, 'part_complete_bytes_match': True,
                               'stored_json_text_and_decoded_detail_preserved': True,
                               'recorded_unknown_and_reconciliation_both_visible': True,
                               'all_persisted_rows_preserved': True, 'source_preserved': True,
                               'database_bytes_preserved': True, 'sqlite_sidecars_preserved': True})
    except Exception as exc:
        receipt['error'] = {'type': type(exc).__name__, 'message': str(exc)}
    finally:
        receipt['database_after_sha256'] = sha(database)
        receipt['sidecars_before'], receipt['sidecars_after'] = before_sidecars, sidecars(database)
        (output / 'receipt.json').write_bytes(encode(receipt))
    print(json.dumps({'accepted': receipt['accepted'], 'error': receipt.get('error'),
                      'receipt_sha256': sha(output / 'receipt.json')}, sort_keys=True))
    if not receipt['accepted']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
