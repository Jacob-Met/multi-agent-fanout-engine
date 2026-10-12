"""Memory's bounded consumer review of Product's frozen plan comparison."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

SOURCE = Path('/workspace/scratch/375aad573428/product/fanout-compare-plans')
MANIFEST = Path('/workspace/scratch/375aad573428/product/compare-plans-publication-manifest.json')
sys.path.insert(0, str(SOURCE))
from fanout_engine import Part, Plan
from fanout_engine.compare import compare_plans, ComparisonError


def require(value, message):
    if not value:
        raise RuntimeError(message)


def sha(value):
    return hashlib.sha256(value).hexdigest()


def verify_sources():
    rows = json.loads(MANIFEST.read_text())['files']
    for row in rows:
        require(sha((SOURCE / row['path']).read_bytes()) == row['sha256'], 'frozen source changed')
    return rows


def main():
    hashes = verify_sources()
    original = Plan('review', (Part('root', 'Read sources.\nKeep café exact.'),
                              Part('extra', 'Optional work.'),
                              Part('use', 'Use two.', ('root', 'extra'), ('z', 'z', 'a'))))
    edited = Plan('review', (Part('new', 'New work.'),
                            Part('use', 'Use one.', ('root',), ('a', 'z')),
                            Part('root', 'Read sources.\nKeep café exact.')))
    before_bytes = json.dumps(original.to_dict(), ensure_ascii=False).encode()
    report = compare_plans(original, edited)
    require(report['changed_parts'] == [{'part_id': 'use', 'fields': ['instruction', 'depends_on', 'tags']}], 'field delta incomplete')
    require(report['added_part_ids'] == ['new'] and report['removed_part_ids'] == ['extra'], 'directional additions/removals incorrect')
    require(report['part_order_changed'] and not report['project_id_changed'] and not report['same_plan'], 'identity flags incorrect')
    require([r['part_id'] for r in report['idempotency_keys']] == ['new', 'use', 'root', 'extra'], 'key order incorrect')
    require(report['before']['plan']['parts'][2]['tags'] == ['z', 'z', 'a'], 'native tags normalized')
    api_pairs = [(original, edited), (edited, original), (original, original),
                 (original, Plan('new-project', original.parts)),
                 (original, Plan('review', tuple(reversed(original.parts)))),
                 (original, Plan('review', (*original.parts[:2], Part('use', 'Use two.', ('extra', 'root'), ('z', 'z', 'a')))))]
    for before, after in api_pairs:
        result = compare_plans(before, after)
        reverse = compare_plans(after, before)
        require(set(result['added_part_ids']) == set(reverse['removed_part_ids']), 'reverse direction disagrees')
        require(result['before'] == reverse['after'] and result['after'] == reverse['before'], 'reverse capture disagrees')
        for label, plan in [('before', before), ('after', after)]:
            native = result[label]['plan']
            independently_encoded = json.dumps(native, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode()
            digest = sha(independently_encoded)
            require(digest == result[label]['plan_digest'] == plan.digest, 'native digest mismatch')
            for row in result['idempotency_keys']:
                expected = None if row['part_id'] not in {p.id for p in plan.parts} else 'fanout-' + sha((plan.project_id + '\0' + digest + '\0' + row['part_id']).encode())
                require(row[label] == expected, 'independent key mismatch')
                require(row['changed'] == (row['before'] != row['after']), 'key flag disagrees')
    report['before']['plan']['parts'][2]['tags'].clear()
    require(json.dumps(original.to_dict(), ensure_ascii=False).encode() == before_bytes, 'output aliases input')
    chain = Plan('chain', tuple(Part('p' + str(i), str(i), ('p' + str(i-1),) if i else ()) for i in range(256)))
    require(compare_plans(chain, chain)['same_plan'], '256 part graph refused')
    try:
        too_many = Plan('wide', tuple(Part('p' + str(i), str(i)) for i in range(257)))
        compare_plans(chain, too_many)
        raise RuntimeError('257 part graph accepted')
    except ComparisonError:
        pass
    cli_cases = []
    with tempfile.TemporaryDirectory(prefix='memory-compare-receive-') as td:
        receiving = Path(td)
        a = receiving / 'before $ literal # café.json'
        b = receiving / 'after (literal).json'
        sentinel = receiving / 'retained.sqlite3'
        sentinel.write_bytes(b'existing consumer state untouched\x00\xff')
        a.write_bytes(b'{"project":"p","parts":[{"id":"a","instruction":"Keep","tags":["z","a","z"]}]}')
        normalized = b'{"parts":[{"tags":["a","z"],"instruction":"Keep","id":"a","depends_on":[]}],"project":"p"}'
        command = [sys.executable, '-B'] + (['-O'] if sys.flags.optimize else []) + ['-m', 'fanout_engine.compare', '--before', str(a), '--after', str(b)]
        env = dict(os.environ, PYTHONPATH=str(SOURCE), PYTHONDONTWRITEBYTECODE='1')
        snapshots = {a.name: a.read_bytes(), sentinel.name: sentinel.read_bytes()}
        for name, raw, status in [
            ('native-normalization', normalized, 0),
            ('exact-1MiB', normalized + b' ' * (1024*1024 - len(normalized)), 0),
            ('one-byte-over', normalized + b' ' * (1024*1024 + 1 - len(normalized)), 2),
            ('excessive-nesting', b'[' * 3000 + b'0' + b']' * 3000, 2),
            ('lone-surrogate', b'{"project":"p","parts":[{"id":"a","instruction":"\\ud800"}]}', 2),
            ('duplicate-key', b'{"project":"p","project":"p","parts":[]}', 2),
        ]:
            b.write_bytes(raw)
            received = subprocess.run(command, cwd=receiving, env=env, capture_output=True, timeout=10)
            require(received.returncode == status, 'CLI status ' + name + ': ' + repr(received.stderr))
            require(b'Traceback' not in received.stderr, 'uncontrolled CLI failure')
            if status == 0:
                value = json.loads(received.stdout)
                require(value['same_plan'] and not any(r['changed'] for r in value['idempotency_keys']), 'normalization changed identity')
                require(value['input_sha256'] == {'before': sha(a.read_bytes()), 'after': sha(raw)}, 'captured byte hashes incorrect')
                require(received.stderr == b'' and received.stdout.endswith(b'\n'), 'successful framing incorrect')
                again = subprocess.run(command, cwd=receiving, env=env, capture_output=True, timeout=10)
                require(again.stdout == received.stdout, 'CLI report not deterministic')
            else:
                require(received.stdout == b'', 'invalid second input emitted report prefix')
            require(b.read_bytes() == raw, 'after input changed')
            require(all((receiving / name).read_bytes() == content for name, content in snapshots.items()), 'other consumer bytes changed')
            require(sorted(p.name for p in receiving.iterdir()) == sorted([a.name, b.name, sentinel.name]), 'CLI created consumer files')
            cli_cases.append({'case': name, 'exit': status, 'stdout_bytes': len(received.stdout)})
    verify_sources()
    return {'reviewer': 'Memory /root/memory', 'candidate_sha256': hashes[0]['sha256'],
            'python': sys.version.split()[0], 'optimized': bool(sys.flags.optimize),
            'api_plan_pairs': len(api_pairs), 'native_digest_and_keys': 'independently derived',
            'direct_tag_order_preserved': True, 'input_detachment': True,
            'part_limit_boundary': '256 accepted; 257 refused', 'cli_cases': cli_cases,
            'separate_cwd_received': True, 'consumer_files_unchanged': True,
            'all_four_frozen_files_unchanged': True, 'findings': [], 'result': 'accepted'}


if __name__ == '__main__':
    print(json.dumps(main(), indent=2))
