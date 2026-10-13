from pathlib import Path
import datetime
import hashlib
import json
import os
import signal
import stat
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
FREEZE = json.loads((ROOT / 'INPUT-FREEZE.json').read_bytes())

def stamp():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def observe(path):
    data = path.read_bytes()
    s = path.stat()
    return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
            'mode': stat.S_IMODE(s.st_mode), 'mtime_ns': s.st_mtime_ns}

def absent(pid):
    try:
        os.killpg(pid, 0)
        return False
    except ProcessLookupError:
        return True

def descendants(pid):
    parents = {}
    for p in Path('/proc').iterdir():
        if not p.name.isdigit():
            continue
        try:
            fields = (p / 'stat').read_text().rsplit(')', 1)[1].split()
            parents[int(p.name)] = int(fields[1])
        except (OSError, ValueError, IndexError):
            pass
    owned = {pid}
    while True:
        more = {p for p, parent in parents.items() if parent in owned}
        if more <= owned:
            return owned
        owned |= more

def fence():
    return {name: observe(ROOT / name) for name in FREEZE['inputs']}

record = {'schema': 1, 'classification': FREEZE['classification'],
          'started_utc': stamp(), 'input_freeze': observe(ROOT / 'INPUT-FREEZE.json'),
          'supervisor_before': observe(Path(__file__)), 'courses': [], 'error': None}

try:
    if fence() != FREEZE['inputs']:
        raise RuntimeError('input fence differs before any course')
    for mode, source in [('original', 'original-46bf5b33'), ('candidate', 'candidate-pr84')]:
        output = ROOT / (mode + '-cloud-course')
        command = [sys.executable, '-I', '-B', str(ROOT / 'receive-retained-routes-v1.py'),
                   str(ROOT / source), str(output), mode]
        if mode == 'candidate':
            command += ['--original-output', str(ROOT / 'original-cloud-course')]
        row = {'mode': mode, 'started_utc': stamp(), 'command': command,
               'timeout_seconds': 240, 'signals': [], 'timed_out': False}
        record['courses'].append(row)
        proc = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, start_new_session=True)
        row['pid'] = proc.pid
        started = time.monotonic()
        try:
            stdout, stderr = proc.communicate(timeout=240)
        except subprocess.TimeoutExpired:
            row['timed_out'] = True
            groups = {os.getpgid(p) for p in descendants(proc.pid) if Path('/proc', str(p)).exists()}
            groups.discard(os.getpgrp())
            row['timeout_observed_groups'] = sorted(groups)
            for sig in (signal.SIGTERM, signal.SIGKILL):
                for group in groups:
                    try:
                        os.killpg(group, sig)
                        row['signals'].append({'group': group, 'signal': sig.name})
                    except ProcessLookupError:
                        pass
                try:
                    stdout, stderr = proc.communicate(timeout=5)
                    break
                except subprocess.TimeoutExpired:
                    continue
            else:
                for stream in (proc.stdout, proc.stderr):
                    stream.close()
                raise RuntimeError('outer timeout cleanup did not finish within bounded waits')
        for suffix, data in [('stdout', stdout), ('stderr', stderr)]:
            with (ROOT / (mode + '-supervisor.' + suffix)).open('xb') as stream:
                stream.write(data)
        row.update(returncode=proc.returncode, elapsed_seconds=time.monotonic() - started,
                   finished_utc=stamp(), group_absent=absent(proc.pid),
                   stdout_bytes=len(stdout), stderr_bytes=len(stderr))
        receipt_path = output / 'RECEIVING.json'
        receipt = json.loads(receipt_path.read_bytes())
        row['receipt'] = observe(receipt_path)
        row['result'] = {k: receipt[k] for k in ['mode', 'passed', 'failed', 'error']}
        row['child_groups_absent_rechecked'] = all(absent(c['pid']) for c in receipt['children'])
        row['input_fence_exact'] = fence() == FREEZE['inputs']
        if (proc.returncode != 0 or stderr or receipt['failed'] or receipt['error']
                or row['timed_out'] or row['signals'] or not row['group_absent']
                or not row['child_groups_absent_rechecked'] or not row['input_fence_exact']):
            raise RuntimeError(mode + ' course did not meet acceptance; preserve receipt and outputs')
except Exception as exc:
    record['error'] = {'type': type(exc).__name__, 'message': str(exc)}
finally:
    record['finished_utc'] = stamp()
    record['input_fence_exact_after'] = fence() == FREEZE['inputs']
    record['supervisor_unchanged'] = observe(Path(__file__)) == record['supervisor_before']
    data = (json.dumps(record, ensure_ascii=False, indent=2) + '\n').encode()
    with (ROOT / 'SUPERVISOR-RECEIPT.json').open('xb') as stream:
        stream.write(data)
    print(json.dumps({'courses': [r.get('result') for r in record['courses']],
                      'error': record['error'], 'inputs_exact': record['input_fence_exact_after'],
                      'receipt_bytes': len(data), 'receipt_sha256': hashlib.sha256(data).hexdigest()}))
sys.exit(1 if record['error'] else 0)
