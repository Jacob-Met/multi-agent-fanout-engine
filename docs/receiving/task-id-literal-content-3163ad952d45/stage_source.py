"""Create an exact Git-object source capsule for the task-ID receiving observers."""
from pathlib import Path
import argparse
import ast
import hashlib
import json
import os
import re
import subprocess
import sys

REPOSITORY = 'Jacob-Met/multi-agent-fanout-engine'
MODULES = ('__init__', 'dispatch', 'inspection', 'ledger', 'plan', 'routing')


def digest(kind, body):
    return hashlib.sha1((kind + ' ' + str(len(body))).encode() + bytes([0]) + body).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def git(checkout, *arguments):
    environment = os.environ.copy()
    environment['GIT_OPTIONAL_LOCKS'] = '0'
    command = ['git', '--no-replace-objects', '-C', str(checkout), *arguments]
    result = subprocess.run(command, capture_output=True, env=environment, timeout=30)
    if result.returncode != 0:
        raise ValueError('Git object read failed: ' + result.stderr.decode('utf-8', 'replace').strip())
    return result.stdout


def read_object(checkout, kind, oid):
    require(re.fullmatch('[0-9a-f]{40}', oid) is not None, 'Expected a complete SHA-1 object identity')
    body = git(checkout, 'cat-file', kind, oid)
    require(digest(kind, body) == oid, 'Git object content differs from its identity')
    return body


def entries(checkout, tree):
    parsed = {}
    for record in git(checkout, 'ls-tree', '-z', tree).split(bytes([0])):
        if not record:
            continue
        metadata, name = record.split(b'\t', 1)
        mode, kind, oid = metadata.decode('ascii').split(' ')
        name = name.decode('utf-8')
        require(name not in parsed, 'Duplicate Git tree entry')
        parsed[name] = {'mode': mode, 'kind': kind, 'oid': oid}
    return parsed


def stage(checkout, commit, output):
    """Resolve objects before creating a new output; never read working source bytes."""
    require(re.fullmatch('[0-9a-f]{40}', commit) is not None,
            'Use the complete immutable commit SHA, not a branch or abbreviated ref')
    require(not output.exists() and not output.is_symlink(),
            'Output must be new; inspect any earlier operation before retrying')
    commit_body = read_object(checkout, 'commit', commit)
    first = commit_body.split(b'\n', 1)[0].decode('ascii')
    require(first.startswith('tree '), 'Commit has no root tree header')
    tree = first.removeprefix('tree ')
    read_object(checkout, 'tree', tree)
    root_entries = entries(checkout, tree)
    package = root_entries.get('fanout_engine')
    require(package is not None and package['kind'] == 'tree' and package['mode'] == '040000',
            'Selected commit has no native fanout_engine tree')
    read_object(checkout, 'tree', package['oid'])
    package_entries = entries(checkout, package['oid'])
    payloads, files = {}, []
    for module in MODULES:
        name = module + '.py'
        entry = package_entries.get(name)
        require(entry is not None and entry['kind'] == 'blob'
                and entry['mode'] in ('100644', '100755'),
                'Expected regular source module: ' + name)
        body = read_object(checkout, 'blob', entry['oid'])
        # These two observers use this reviewed six-module closure. Refuse a
        # changed closure instead of silently omitting a new local dependency.
        for node in ast.walk(ast.parse(body.decode('utf-8'), filename=name)):
            if isinstance(node, ast.ImportFrom) and node.level:
                require(node.level == 1 and node.module in MODULES,
                        'Selected source requires a different local dependency closure: ' + name)
        relative = 'fanout_engine/' + name
        payloads[relative] = body
        files.append({'path': relative, 'bytes': len(body),
                      'sha256': hashlib.sha256(body).hexdigest(),
                      'git_blob': entry['oid'], 'git_mode': entry['mode']})
    manifest = {
        'repository': REPOSITORY, 'commit': commit, 'tree': tree,
        'scope': 'Six exact Git-object modules for the task-ID receiving observers. The caller selects a reviewed commit from the established project checkout.',
        'git_objects_verified': {'commit': commit, 'root_tree': tree,
                                 'package_tree': package['oid']},
        'stager_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'files': files,
    }
    output.mkdir(parents=True, exist_ok=False)
    for relative, body in payloads.items():
        path = output / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as destination:
            destination.write(body)
    # Write the admission manifest last. An incomplete output has no success
    # manifest and remains available for inspection after an I/O failure.
    manifest_body = (json.dumps(manifest, sort_keys=True, indent=2) + '\n').encode('utf-8')
    with (output / 'SOURCE.json').open('xb') as destination:
        destination.write(manifest_body)
    return {'staged': True, 'source_commit': commit, 'source_tree': tree,
            'source_manifest_sha256': hashlib.sha256(manifest_body).hexdigest(),
            'source_modules': len(files), 'output': str(output),
            'candidate_contract_qualified': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkout', type=Path, required=True,
                        help='existing authorized checkout of this repository')
    parser.add_argument('--commit', required=True, help='complete reviewed commit SHA')
    parser.add_argument('--output', type=Path, required=True, help='new source capsule directory')
    args = parser.parse_args()
    try:
        result = stage(args.checkout.resolve(strict=True), args.commit, args.output.absolute())
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print('task-ID source staging failed: ' + str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
