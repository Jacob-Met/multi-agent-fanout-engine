"""Independent native CLI receiving for root's compare_retained adapter."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile

SOURCE = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[3]
ADAPTER = SOURCE / 'fanout_engine/compare_retained.py'
EXPECTED = '8d3b64e2b4efd61bca56a9f7dbc482f1794866de45bb9527f679a384555bf17e'
sys.path.insert(0, str(SOURCE))
from fanout_engine import Ledger, LedgerError, Part, Plan
from fanout_engine.compare_retained import compare_retained_plan

def require(ok, message):
    if not ok:
        raise RuntimeError(message)

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def cli(database, candidate, cwd, project='consumer-test'):
    command = [sys.executable, '-B'] + (['-O'] if not __debug__ else [])
    command += ['-m', 'fanout_engine.compare_retained', '--database', str(database),
                '--project', project, '--after', str(candidate)]
    return subprocess.run(command, cwd=cwd, env={**os.environ, 'PYTHONPATH': str(SOURCE)},
                          capture_output=True, text=True, timeout=12)

def main():
    require(digest(ADAPTER) == EXPECTED, 'adapter hash changed')
    results = []
    with tempfile.TemporaryDirectory(prefix='consumer retained #? é ') as tmp:
        directory = Path(tmp)
        dbpath = directory / 'retained #?& é.sqlite3'
        candidatepath = directory / 'draft #?& é.json'
        before = Plan('consumer-test', (
            Part('c', 'A running independent check.', tags=('z','a','z')),
            Part('a', 'Source from an accepted artifact.'),
            Part('b', 'Failed review.', ('a',)),
        ))
        after = Plan('consumer-test', (
            Part('b', 'Revised review with a citation.', ('a',)),
            Part('a', 'Source from an accepted artifact.'),
            Part('d', 'A new dependent task.', ('b',)),
        ))
        route = {'model':'authored-fixture', 'effort':'low'}
        evidence = {'source':'Consumer independent fixture','locator':'attempt:b','finding':'local fixture failure'}
        with Ledger(str(dbpath)) as ledger:
            ledger.record_plan(before)
            for name in ('a','b','c'):
                ledger.mark_dispatching(before.project_id, name, 'consumer-fixture', route)
                ledger.mark_running(before.project_id, name, 'fixture-'+name)
            ledger.mark_completed(before.project_id, 'a', 'artifact:fixture-a')
            ledger.mark_outcome_unknown(before.project_id, 'b', evidence)
            ledger.reconcile_unknown(before.project_id, 'b', verdict='failed', evidence=evidence)
            events = ledger.events(before.project_id)
            try:
                ledger.record_plan(after)
                raise RuntimeError('native ledger unexpectedly accepts edited saved plan')
            except LedgerError as exc:
                require('different plan' in str(exc), 'wrong motivating refusal')
        candidatepath.write_text(json.dumps(after.to_dict(), ensure_ascii=False), encoding='utf-8')
        old_hashes = (digest(dbpath), digest(candidatepath))
        old_mtime = dbpath.stat().st_mtime_ns
        run = cli(dbpath,candidatepath,directory)
        require(run.returncode == 0 and not run.stderr, 'real comparison CLI failed: '+run.stderr)
        report = json.loads(run.stdout)
        require(report['before']['plan'] == before.to_dict(), 'retained direct tags/order changed')
        require(report['before']['plan_digest'] == before.digest, 'before identity changed')
        require(report['after']['plan_digest'] == after.digest, 'after identity wrong')
        require(report['added_part_ids'] == ['d'] and report['removed_part_ids'] == ['c'], 'added/removed wrong')
        require(report['changed_parts'] == [{'fields':['instruction'], 'part_id':'b'}], 'field diff wrong')
        require(report['part_order_changed'] and not report['project_id_changed'], 'plan identity classification wrong')
        require(report['retained']['part_states'] == [
            {'part_id':'c','state':'running'}, {'part_id':'a','state':'completed'}, {'part_id':'b','state':'failed'}],
            'saved order/states changed')
        require(all(row['changed'] for row in report['idempotency_keys']), 'whole-plan key invalidation hidden')
        require({r['part_id']:r['before'] for r in report['idempotency_keys']} == {
            'a':before.idempotency_key('a'),'b':before.idempotency_key('b'),'c':before.idempotency_key('c'),'d':None},
            'reported old keys differ from native keys')
        require((digest(dbpath),digest(candidatepath)) == old_hashes and dbpath.stat().st_mtime_ns == old_mtime,
                'CLI modified inputs')
        with Ledger.open_readonly(dbpath) as ledger:
            require(ledger.events(before.project_id) == events, 'CLI wrote event history')
            same = compare_retained_plan(ledger,before.project_id,before)
        require(same['same_plan'] and all(not r['changed'] for r in same['idempotency_keys']), 'identical-native control failed')
        require(cli(dbpath,candidatepath,directory).stdout == run.stdout, 'same retained course nondeterministic')
        results.append({'case':'actual_record_conflict_then_compare', 'result':'pass','saved_states':report['retained']['part_states'],
                        'before_digest':before.digest,'after_digest':after.digest,'events_preserved':len(events)})

        external = sqlite3.connect(dbpath,isolation_level=None)
        require(external.execute('PRAGMA journal_mode=WAL').fetchone()[0] == 'wal','not WAL')
        external.execute("UPDATE parts SET state='outcome_unknown' WHERE part_id='c'")
        external.execute('BEGIN IMMEDIATE')
        external.execute("UPDATE parts SET state='completed' WHERE part_id='c'")
        walpath = Path(str(dbpath)+'-wal')
        files_before = (digest(dbpath),digest(walpath))
        run = cli(dbpath,candidatepath,directory)
        require(run.returncode == 0,'WAL reader blocked/refused')
        state = {r['part_id']:r['state'] for r in json.loads(run.stdout)['retained']['part_states']}
        require(state['c'] == 'outcome_unknown','saw uncommitted state or stale main-file state')
        require(external.in_transaction and (digest(dbpath),digest(walpath)) == files_before, 'disturbed external writer or DB')
        external.rollback()
        external.close()
        results.append({'case':'committed_WAL_with_active_external_writer','result':'pass','read_state':'outcome_unknown'})

        with sqlite3.connect(dbpath) as db:
            db.execute("UPDATE parts SET evidence_json='{\"x\":1,\"x\":2}' WHERE part_id='b'")
        file_before = digest(dbpath)
        run = cli(dbpath,candidatepath,directory)
        require(run.returncode == 2 and not run.stdout and 'invalid_record' in run.stderr and 'Traceback' not in run.stderr,
                'malformed late evidence received as partial comparison')
        require(digest(dbpath) == file_before,'invalid-data refusal changed database')
        results.append({'case':'duplicate_key_in_saved_part_evidence','result':'pass','exit':run.returncode})

        missing = directory/'nonexistent-parent'/'new.sqlite3'
        run = cli(missing,candidatepath,directory)
        require(run.returncode == 2 and not run.stdout and not missing.parent.exists(),'created missing ledger or accepted it')
        run = cli(dbpath,candidatepath,directory,project='not-here')
        require(run.returncode == 3 and not run.stdout and 'project_not_found' in run.stderr,'missing project not distinct')
        results.append({'case':'missing_database_and_project','result':'pass','missing_project_exit':run.returncode})

        candidatepath.write_bytes(b'{"project":"consumer-test","parts":[{"id":"a","instruction":"x"}],"project":"other"}')
        run = cli(dbpath,candidatepath,directory)
        require(run.returncode == 2 and not run.stdout and 'duplicate JSON' in run.stderr,'candidate duplicate key accepted')
        fifo = directory/'authored-plan.fifo'
        os.mkfifo(fifo)
        run = cli(dbpath,fifo,directory)
        require(run.returncode == 2 and not run.stdout and 'regular file' in run.stderr,'FIFO blocked or accepted')
        results.append({'case':'candidate_duplicate_key_and_FIFO','result':'pass'})
    require(digest(ADAPTER) == EXPECTED,'source changed during review')
    return {'reviewer':'Consumer /root/consumer','adapter_sha256':EXPECTED,'python':sys.version.split()[0],
            'optimized':not __debug__,'result':'accepted','cases':results,
            'boundary':'Native isolated SQLite/CLI receiving only; no provider calls or live estate database'}

if __name__ == '__main__':
    print(json.dumps(main(), indent=2))
