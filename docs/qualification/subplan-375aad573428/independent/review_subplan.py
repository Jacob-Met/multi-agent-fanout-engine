"""Memory's independent bounded native producer and consumer receiving."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source-root', type=Path, required=True)
parser.add_argument('--manifest', type=Path, required=True)
args = parser.parse_args()
SOURCE = args.source_root.resolve()
MANIFEST = args.manifest.resolve()
sys.path.insert(0, str(SOURCE))
from fanout_engine import EffortRouter, Ledger, Part, Plan, Route
from fanout_engine.preview import preview_plan
from fanout_engine.subplan import SubplanError, select_subplan


def require(value, why):
    if not value:
        raise RuntimeError(why)


def encoded(document):
    return json.dumps(document, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def verify_sources():
    rows = json.loads(MANIFEST.read_text())['files']
    for row in rows:
        raw = (SOURCE / row['path']).read_bytes()
        require(len(raw) == row['bytes'] and sha(raw) == row['sha256'], 'frozen file changed: ' + row['path'])
    return rows


def main():
    hashes = verify_sources()
    original = Plan('Source', (
        Part('final', 'Retain café exactly.\nSecond line.', ('left', 'right'), ('z', 'z', 'a')),
        Part('unused', 'Another branch.'),
        Part('right', 'Right.', ('seed',)),
        Part('seed', 'Shared prerequisite.'),
        Part('left', 'Left.', ('seed',)),
    ))
    original_bytes = encoded(original.to_dict())
    selected = select_subplan(original, ['left', 'final'], 'Reused')
    require([p.id for p in selected.parts] == ['final', 'right', 'seed', 'left'], 'source order or closure changed')
    require(selected.parts[0].tags == ('z', 'z', 'a') and selected.parts[0].depends_on == ('left', 'right'), 'native fields changed')
    require(encoded(original.to_dict()) == original_bytes, 'source changed')
    require(all(p is not q for p in selected.parts for q in original.parts), 'output Part aliases source')
    require(select_subplan(original, ['final', 'left'], 'Reused') == selected, 'request order changed result')
    require(select_subplan(original, ['seed'], 'Seed').parts == (original.parts[3],), 'ancestor-only selection expanded descendants')

    rng = random.Random(375573428)
    # A transitive reachability matrix is an independent oracle for closure;
    # it does not repeat the producer's stack traversal.
    for course in range(32):
        n = rng.randrange(3, 10)
        direct = [[False] * n for _ in range(n)]
        parts = []
        for i in range(n):
            deps = [j for j in range(i) if rng.random() < 0.35]
            rng.shuffle(deps)
            for j in deps:
                direct[i][j] = True
            parts.append(Part('p' + str(i), 'row-' + str(i), tuple('p' + str(j) for j in deps), ('tag', 'tag') if i % 2 else ()))
        reachable = [row[:] for row in direct]
        for k in range(n):
            for i in range(n):
                for j in range(n):
                    reachable[i][j] |= reachable[i][k] and reachable[k][j]
        rng.shuffle(parts)
        plan = Plan('Course' + str(course), tuple(parts))
        targets = rng.sample(range(n), rng.randrange(1, min(n, 3) + 1))
        expected_ids = {j for j in range(n) if j in targets or any(reachable[i][j] for i in targets)}
        result = select_subplan(plan, ['p' + str(i) for i in targets], 'Copy' + str(course))
        expected = [p.to_dict() for p in parts if int(p.id[1:]) in expected_ids]
        require(result.to_dict() == {'project': 'Copy' + str(course), 'parts': expected}, 'matrix closure or exact fields disagree')
        digest = sha(encoded(result.to_dict()))
        require(digest == result.digest, 'independently derived native digest disagrees')
        for p in result.parts:
            key = 'fanout-' + sha((result.project_id + '\0' + digest + '\0' + p.id).encode())
            require(result.idempotency_key(p.id) == key, 'independently derived native key disagrees')

    route = Route('authored-offline', 'high')
    preview = preview_plan(selected, EffortRouter({route.model: (route.effort,)}, pool=(route,)))
    require(preview['plan'] == selected.to_dict(), 'existing preview changed produced plan')
    require(preview['dependency_ready_without_completions'] == ['seed'], 'native readiness incorrect')
    cli_receipts = []
    with tempfile.TemporaryDirectory(prefix='memory-subplan-native-') as td:
        root = Path(td)
        db_path = root / 'retained.sqlite3'
        with Ledger(str(db_path)) as ledger:
            ledger.record_plan(original)
            ledger.mark_dispatching('Source', 'seed', 'authored-worker', {'model': 'authored-offline', 'effort': 'high'})
            ledger.mark_running('Source', 'seed', 'authored-task')
            ledger.mark_completed('Source', 'seed', 'authored-artifact')
            original_snapshot = ledger.project_snapshot('Source')
            original_events = ledger.events('Source')
            require(ledger.record_plan(selected), 'new Plan not admitted')
            require(not ledger.record_plan(selected), 'same Plan not idempotent')
            require(all(ledger.part_state('Reused', p.id) == 'queued' for p in selected.parts), 'source completion state transferred')
            require(ledger.completed_ids('Reused') == set(), 'source completions reused')
            require(ledger.project_snapshot('Source') == original_snapshot and ledger.events('Source') == original_events, 'original retained project changed')
            target_snapshot = ledger.project_snapshot('Reused')
        baseline_db = db_path.read_bytes()
        with Ledger.open_readonly(db_path) as reopened:
            require(reopened.project_snapshot('Source') == original_snapshot, 'reopened source differs')
            require(reopened.project_snapshot('Reused') == target_snapshot, 'reopened selected Plan differs')
        require(db_path.read_bytes() == baseline_db, 'readonly reopening changed database')

        plan_path = root / 'authored $ plan # café.json'
        raw = encoded(original.to_dict())
        plan_path.write_bytes(raw)
        command = [sys.executable, '-B'] + (['-O'] if sys.flags.optimize else []) + ['-m', 'fanout_engine.subplan', '--plan', str(plan_path)]
        environment = dict(os.environ, PYTHONPATH=str(SOURCE), PYTHONDONTWRITEBYTECODE='1')
        def cli(arguments):
            return subprocess.run(command + arguments, cwd=root, env=environment, capture_output=True, timeout=10)
        valid = cli(['--part', 'final', '--part', 'seed', '--project', 'CliCopy'])
        require(valid.returncode == 0 and valid.stderr == b'', 'real CLI refused valid authored Plan')
        value = json.loads(valid.stdout)
        received = Plan.from_dict(value)
        require(set(value) == {'project', 'parts'}, 'CLI output not ordinary native Plan')
        require([p.id for p in received.parts] == ['final', 'right', 'seed', 'left'], 'CLI closure incorrect')
        require(received.parts[0].tags == ('a', 'z'), 'CLI native tag normalization differs')
        require(valid.stdout == encoded(received.to_dict()) + b'\n', 'CLI output framing differs')
        require(valid.stdout == cli(['--part', 'seed', '--part', 'final', '--project', 'CliCopy']).stdout, 'request order affected CLI bytes')
        cli_receipts.append({'course': 'complete-native-plan', 'exit': 0, 'bytes': len(valid.stdout)})
        for course, arguments in [('duplicate-selection', ['--part', 'final', '--part', 'final', '--project', 'Copy']), ('unknown-selection', ['--part', 'missing', '--project', 'Copy']), ('same-project', ['--part', 'final', '--project', 'Source'])]:
            out = cli(arguments)
            require(out.returncode == 2 and out.stdout == b'' and b'Traceback' not in out.stderr, 'CLI refusal contract failed')
            cli_receipts.append({'course': course, 'exit': out.returncode, 'bytes': len(out.stdout)})
        malformed = original.to_dict()
        malformed['parts'][1]['depends_on'] = ['absent']
        bad_raw = encoded(malformed)
        plan_path.write_bytes(bad_raw)
        out = cli(['--part', 'seed', '--project', 'Copy'])
        require(out.returncode == 2 and out.stdout == b'', 'unselected malformed source escaped validation')
        require(plan_path.read_bytes() == bad_raw and db_path.read_bytes() == baseline_db, 'CLI changed consumer bytes')
        require(sorted(p.name for p in root.iterdir()) == sorted([db_path.name, plan_path.name]), 'CLI created consumer files')
        cli_receipts.append({'course': 'malformed-unselected-source', 'exit': out.returncode, 'bytes': len(out.stdout)})
    verify_sources()
    return {'reviewer': 'Memory /root/memory', 'python': sys.version.split()[0], 'optimized': bool(sys.flags.optimize),
            'candidate_sha256': hashes[0]['sha256'], 'matrix_oracle_courses': 32,
            'exact_native_fields_and_declaration_order': True, 'detached_parts': True,
            'independent_digest_and_keys': True, 'native_preview_ready': ['seed'],
            'existing_completed_source_preserved': True, 'new_project_states': 'all queued',
            'real_sqlite_reopen_unchanged': True, 'cli_courses': cli_receipts,
            'frozen_three_files_unchanged': True, 'findings': [], 'result': 'accepted'}


if __name__ == '__main__':
    print(json.dumps(main(), indent=2))
