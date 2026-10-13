"""Prepare only the explicit archived alternative; never run product code."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import stat
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PREFIX = 'docs/qualification/saved-inspection-html-loom-d3745/'

def sha(body):
    return hashlib.sha256(body).hexdigest()

def blob(body):
    return hashlib.sha1(b'blob ' + str(len(body)).encode() + b'\0' + body).hexdigest()

def encode(value):
    return (json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + '\n').encode('ascii')

def capture(row):
    p = Path(row.get('mirror_path', row['source_path']))
    info = p.lstat()
    if not stat.S_ISREG(info.st_mode):
        raise ValueError('nonregular selected input: ' + str(p))
    body = p.read_bytes()
    if (len(body), sha(body)) != (row['bytes'], row['sha256']):
        raise ValueError('selected input changed: ' + str(p))
    if 'git_blob' in row and blob(body) != row['git_blob']:
        raise ValueError('Git body changed: ' + str(p))
    if 'native_mode' in row and 'mirror_path' not in row:
        expected = row['native_mode']
        if isinstance(expected, str):
            expected = int(expected, 8)
        if stat.S_IMODE(info.st_mode) != expected:
            raise ValueError('selected native mode changed: ' + str(p))
    return body, {'read_path': str(p), 'actual_read_mode': oct(stat.S_IMODE(info.st_mode)),
                  'original_source_path': row['source_path'],
                  'native_mode': row.get('native_mode'), 'mirror': 'mirror_path' in row}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--descriptor', type=Path, required=True)
    parser.add_argument('--descriptor-sha256', required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    descriptor_body = args.descriptor.read_bytes()
    if sha(descriptor_body) != args.descriptor_sha256:
        raise ValueError('original descriptor identity differs')
    descriptor = json.loads(descriptor_body)
    if descriptor['prefix'] != PREFIX + 'independent/' or len(descriptor['files']) != 59:
        raise ValueError('original independent selection differs')
    author_body = (HERE / 'author-publication-inputs-v1.json').read_bytes()
    author = json.loads(author_body)
    if len(author['files']) != 29:
        raise ValueError('original author selection differs')
    freeze = json.loads((ROOT / 'author-v1/freeze.json').read_bytes())
    frozen_sources = [r for r in freeze['inputs'] if r['path'].startswith('candidate/')]
    if len(frozen_sources) != 13:
        raise ValueError('frozen source projection differs')
    selected, inventory, support, origins = {}, [], [], []

    def add(destination, mode, body, origin):
        if not destination.startswith(PREFIX) or destination in selected or mode != '100644':
            raise ValueError('unsafe/duplicate archive selection: ' + destination)
        git = blob(body)
        selected[destination] = {'path': destination, 'mode': mode, 'sha': git,
                                 'encoding': 'base64', 'content': base64.b64encode(body).decode('ascii')}
        identity = {'path': destination, 'mode': mode, 'bytes': len(body), 'sha256': sha(body)}
        inventory.append({**identity, 'git_blob': git, 'origin': origin})
        origins.append((origin['read_path'], body))
        return identity

    def row_add(row, destination):
        body, origin = capture(row)
        return add(destination, row['mode'], body, origin)

    archive_sources = []
    for r in frozen_sources:
        relative = r['path'][len('candidate/'):]
        row = {'source_path': str(ROOT / r['path']), 'bytes': r['bytes'],
               'sha256': r['sha256'], 'native_mode': r['mode'], 'mode': '100644'}
        destination = PREFIX + 'archived-source/' + relative
        support.append(row_add(row, destination))
        archive_sources.append({**support[-1], 'original_selected_path': relative,
                                'git_blob': inventory[-1]['git_blob'],
                                'source_path': row['source_path'], 'native_mode': row['native_mode']})
    for row in author['files']:
        support.append(row_add(row, row['path']))
    source_map = {'schema': 'hamon.loom.fanout-html-archive-source-map.v1',
                  'status': 'archived_failed_narrow_visual_gate', 'production_source_files': 0,
                  'original_freeze': {'path': 'author/author-v1/freeze.json',
                                      'sha256': sha((ROOT / 'author-v1/freeze.json').read_bytes())},
                  'files': archive_sources,
                  'limits': ['Selected historical projection, not a maintained runtime or complete checkout.',
                             'Original receipts remain unpublished-at-execution and source-specific.',
                             'Workflow text is inert inside this qualification namespace.']}

    def support_file(source, destination):
        p = Path(source)
        body = p.read_bytes()
        row = {'source_path': str(p), 'mode': '100644', 'native_mode': oct(stat.S_IMODE(p.stat().st_mode)),
               'bytes': len(body), 'sha256': sha(body)}
        support.append(row_add(row, PREFIX + destination))

    for source, destination in [
        (HERE / 'ARCHIVE-README.md', 'README.md'),
        (HERE / 'source-binding-v1.json', 'source-binding-v1.json'),
        (HERE / 'author-publication-inputs-v1.json', 'author-publication-inputs-v1.json'),
        (HERE / 'publication-tools.json', 'publication-tools.json'),
        (HERE / 'source-review-forge.json', 'source-review-forge.json'),
        (ROOT / 'overlap-pr97/static-audit-v1.json', 'pr97-static-review.json'),
        (Path(__file__), 'assemble-archive-v1.py'),
        (args.descriptor, 'independent-publication-inputs-v1.json'),
    ]:
        support_file(source, destination)
    map_bytes = encode(source_map)
    support.append(add(PREFIX + 'archive-source-map-v1.json', '100644', map_bytes,
                       {'read_path': None, 'generated_from': 'exact original author freeze and selected bodies'}))
    for row in descriptor['files']:
        row_add(row, descriptor['prefix'] + row['path'])
    for read_path, body in origins:
        if read_path is not None and Path(read_path).read_bytes() != body:
            raise ValueError('offered body changed during selection: ' + read_path)
    binding = json.loads((HERE / 'source-binding-v1.json').read_bytes())
    packet = {'schema': 'hamon.source-packet/1',
              'source': {'repository': 'Jacob-Met/multi-agent-fanout-engine',
                         'commit': binding['current_parent']['commit'], 'tree': binding['current_parent']['tree']},
              'files': [selected[k] for k in sorted(selected)]}
    policy = {'schema': 'hamon.publication-layout/1', 'source_files': [], 'support_files': support,
              'evidence_prefix': PREFIX, 'descriptor_schema': descriptor['schema'],
              'descriptor_prefix': descriptor['prefix']}
    args.out.mkdir()
    for name, body in [('source-packet.json', encode(packet)), ('layout-policy.json', encode(policy)),
                       ('selection-inventory.json', encode(inventory)), ('archive-source-map-v1.json', map_bytes),
                       ('original-descriptor.json', descriptor_body)]:
        (args.out / name).open('xb').write(body)
    commands = []
    def run(label, argv):
        r = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        for stream in ['stdout', 'stderr']:
            (args.out / (label + '.' + stream)).open('xb').write(getattr(r, stream))
        commands.append({'label': label, 'argv': argv, 'exit_code': r.returncode,
                         'stdout': {'bytes': len(r.stdout), 'sha256': sha(r.stdout)},
                         'stderr': {'bytes': len(r.stderr), 'sha256': sha(r.stderr)}})
        if r.returncode:
            raise RuntimeError('maintained gate refused: ' + label)
    packet_path, plan_path, policy_path = [args.out / n for n in ['source-packet.json','git-object-plan.json','layout-policy.json']]
    run('prepare', [sys.executable, '-B', str(HERE / 'tools/prepare_git_objects.py'), str(packet_path),
                    '--sha256', sha(packet_path.read_bytes()), '--out', str(plan_path)])
    run('layout', [sys.executable, '-B', str(HERE / 'tools/validate_publication_layout.py'), str(plan_path),
                   '--sha256', sha(plan_path.read_bytes()), '--policy', str(policy_path),
                   '--policy-sha256', sha(policy_path.read_bytes()), '--descriptor', str(args.descriptor),
                   '--descriptor-sha256', args.descriptor_sha256])
    for read_path, body in origins:
        if read_path is not None and Path(read_path).read_bytes() != body:
            raise ValueError('offered body changed after preflight: ' + read_path)
    receipt = {'schema': 'hamon.loom.fanout-html-archive-admission.v1', 'accepted': True,
               'production_source_files': 0, 'archived_source_files': 13, 'author_files': 29,
               'support_files': len(support), 'independent_files': 59, 'selected_files': len(selected),
               'descriptor_sha256': args.descriptor_sha256, 'commands': commands,
               'plan': {'bytes': len(plan_path.read_bytes()), 'sha256': sha(plan_path.read_bytes())},
               'scope': 'Archive-only exact selected layout; all paths beneath qualification prefix. No product execution, tree/ref mutation or responsive-product acceptance.'}
    (args.out / 'receipt.json').open('xb').write(encode(receipt))
    print(json.dumps(receipt, sort_keys=True))

if __name__ == '__main__':
    main()
