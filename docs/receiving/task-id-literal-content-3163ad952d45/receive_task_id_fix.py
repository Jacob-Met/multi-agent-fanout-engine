"""Run the two frozen task-ID consumers and enforce the native-content contract."""
from pathlib import Path, PurePosixPath
import argparse
import datetime
import hashlib
import json
import os
import platform
import re
import socket
import sqlite3
import subprocess
import sys

OBSERVERS = {
    'reproduce_task_id_strip.py': 'c074e8df6dbcd1d2944128de8e73db0c62e9971bd0c848cb545dc45468f2c404',
    'review_task_id_truthiness.py': 'bdd83c6dd8001a0bc20e9092574e436ec050efd9f2a19a9ab1b18a0dc10671b2',
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_source(source, expected_commit):
    manifest_path = source / 'SOURCE.json'
    manifest = json.loads(manifest_path.read_bytes())
    if manifest.get('repository') != 'Jacob-Met/multi-agent-fanout-engine':
        raise ValueError('Unexpected repository')
    if manifest.get('commit') != expected_commit or not re.fullmatch('[0-9a-f]{40}', expected_commit):
        raise ValueError('Source does not match the explicitly selected commit')
    if not re.fullmatch('[0-9a-f]{40}', manifest.get('tree', '')):
        raise ValueError('An exact source tree is required')
    paths = [row['path'] for row in manifest['files']]
    required = {'fanout_engine/' + name + '.py' for name in
                ('__init__', 'dispatch', 'inspection', 'ledger', 'plan', 'routing')}
    if len(paths) != len(set(paths)) or not required.issubset(paths):
        raise ValueError('Incomplete or duplicate source inventory')
    for row in manifest['files']:
        relative = PurePosixPath(row['path'])
        path = source / relative
        if relative.is_absolute() or '..' in relative.parts or path.is_symlink():
            raise ValueError('Unsafe source path')
        body = path.read_bytes()
        blob = hashlib.sha1(('blob ' + str(len(body))).encode() + bytes([0]) + body).hexdigest()
        if len(body) != row['bytes'] or hashlib.sha256(body).hexdigest() != row['sha256'] or blob != row['git_blob']:
            raise ValueError('Source content differs: ' + row['path'])
    return manifest, sha(manifest_path)


def evaluate(strip, truthiness):
    """Evaluate recorded outcomes; process exit status alone is insufficient."""
    strip_cases = strip.get('cases', [])
    truth_cases = truthiness.get('cases', [])
    return {
        'four_strip_cases': len(strip_cases) == 4,
        'no_strip_contract_violations': strip.get('observed_contract_violations') == [],
        'all_strip_workflow_checks': bool(strip_cases) and all(
            row.get('contract_matches') is True and row.get('checks')
            and all(value is True for value in row['checks'].values()) for row in strip_cases),
        'no_strip_hooks': strip.get('strip_override_calls') == [],
        'four_truthiness_cases': len(truth_cases) == 4,
        'all_truthiness_workflows': bool(truth_cases) and all(
            row.get('expected_valid_receipt_workflow') is True for row in truth_cases),
        'no_truthiness_hooks': bool(truth_cases) and all(row.get('hook_calls') == [] for row in truth_cases),
        'no_dispatch_exception': bool(truth_cases) and all(row.get('exception') is None for row in truth_cases),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--expected-commit', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source = args.source.resolve()
    output = args.output.absolute()
    here = Path(__file__).resolve().parent
    manifest, manifest_sha = verify_source(source, args.expected_commit)
    for name, expected in OBSERVERS.items():
        if sha(here / name) != expected:
            raise SystemExit('Frozen observer differs: ' + name)
    if output.exists() or output.is_symlink():
        raise SystemExit('Output must be new; inspect existing operations before retrying')
    output.mkdir(parents=True, exist_ok=False)
    environment = os.environ.copy()
    environment.pop('PYTHONOPTIMIZE', None)
    environment['PYTHONDONTWRITEBYTECODE'] = '1'
    invocations = [
        ('strip', 'reproduce_task_id_strip.py', output / 'strip'),
        ('truthiness', 'review_task_id_truthiness.py', output / 'truthiness.json'),
    ]
    executions = []
    for label, name, destination in invocations:
        command = [sys.executable, '-B', str(here / name), '--source', str(source), '--output', str(destination)]
        timed_out, timeout_seconds = False, None
        try:
            result = subprocess.run(command, cwd=output, env=environment, capture_output=True, timeout=60)
            stdout, stderr, exit_code = result.stdout, result.stderr, result.returncode
        except subprocess.TimeoutExpired as exc:
            stdout, stderr, exit_code = exc.stdout or b'', exc.stderr or b'', None
            timed_out, timeout_seconds = True, exc.timeout
        stdout_path, stderr_path = output / (label + '.stdout'), output / (label + '.stderr')
        stdout_path.write_bytes(stdout)
        stderr_path.write_bytes(stderr)
        executions.append({'observer': name, 'command': command, 'exit_code': exit_code,
                           'timed_out': timed_out, 'timeout_seconds': timeout_seconds,
                           'stdout_sha256': sha(stdout_path), 'stderr_sha256': sha(stderr_path)})
        if exit_code != 0:
            (output / 'failed-operation.json').write_text(json.dumps(executions, sort_keys=True, indent=2) + '\n')
            failure = 'Observer timed out' if timed_out else 'Observer failed'
            raise SystemExit(failure + '; preserve this output and inspect before retrying')
    strip_path, truth_path = output / 'strip/receipt.json', output / 'truthiness.json'
    strip, truth = json.loads(strip_path.read_bytes()), json.loads(truth_path.read_bytes())
    checks = evaluate(strip, truth)
    checks['source_identity_in_both_observers'] = all(
        row.get('source_commit') == args.expected_commit and row.get('source_tree') == manifest['tree']
        and row.get('source_manifest_sha256') == manifest_sha for row in (strip, truth))
    expected_files = {row['path']: row['sha256'] for row in manifest['files']}
    checks['both_observers_preserved_source'] = all(
        row.get('source_files_preserved') == expected_files for row in (strip, truth))
    checks['source_verified_after'] = verify_source(source, args.expected_commit)[1] == manifest_sha
    checks['frozen_observers_preserved'] = all(sha(here / name) == expected for name, expected in OBSERVERS.items())
    accepted = all(value is True for value in checks.values())
    receipt = {
        'schema': 'hamon.fanout.task-id-fix.receiving.v1',
        'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'scope': 'Eight local-adapter task-ID cases through pinned source and actual SQLite. This is a bounded receipt-contract gate.',
        'repository': manifest['repository'], 'source_commit': args.expected_commit,
        'source_tree': manifest['tree'], 'source_manifest_sha256': manifest_sha,
        'source_files_preserved': expected_files, 'frozen_observers': OBSERVERS,
        'host': socket.gethostname(), 'python': platform.python_version(),
        'sqlite': sqlite3.sqlite_version, 'platform': platform.platform(),
        'driver_sha256': sha(Path(__file__)), 'executions': executions,
        'strip_receipt_sha256': sha(strip_path), 'truthiness_receipt_sha256': sha(truth_path),
        'retained_database_sha256': sha(output / 'strip/retained.sqlite3'),
        'checks': checks, 'accepted': accepted,
    }
    receipt_path = output / 'receipt.json'
    receipt_path.write_text(json.dumps(receipt, sort_keys=True, indent=2) + '\n')
    print(json.dumps({'accepted': accepted, 'source_commit': args.expected_commit,
                      'failed_checks': [name for name, passed in checks.items() if not passed],
                      'receipt_sha256': sha(receipt_path), 'output': str(output)}, sort_keys=True))
    if not accepted:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
