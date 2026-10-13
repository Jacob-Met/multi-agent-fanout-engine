"""Verify this exact retained-history packet as data; do not extract or execute it."""
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import io
import json
import tarfile

ARCHIVE_SHA = '0fcd83ae30a52c959b6c8332e5cb5dd20b899c2df61ef5f607b481a0a6257a9b'
MANIFEST_SHA = 'b38e8d6014aec7a72d9853e214ebb71d60de34532f162085dfadcd7948a77475'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(body):
    return hashlib.sha256(body).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    args = parser.parse_args()
    require(args.archive.stat().st_size == 51302, 'Archive size differs')
    raw = args.archive.read_bytes()
    require(digest(raw) == ARCHIVE_SHA, 'Archive hash differs')
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as archive:
        members = archive.getmembers()
        require(len(members) == 29 and len({m.name for m in members}) == 29, 'Archive inventory differs')
        for member in members:
            path = PurePosixPath(member.name)
            require(member.isfile() and member.mode == 0o644 and not path.is_absolute()
                    and '..' not in path.parts, 'Unsafe member')
        data = {m.name: archive.extractfile(m).read() for m in members}
    require(digest(data['MANIFEST.json']) == MANIFEST_SHA, 'Manifest differs')
    manifest = json.loads(data['MANIFEST.json'])
    require(len(manifest['files']) == 28 and set(data) == {'MANIFEST.json'} | {r['path'] for r in manifest['files']},
            'Payload inventory differs')
    for row in manifest['files']:
        body = data[row['path']]
        require(len(body) == row['bytes'] and digest(body) == row['sha256'], 'Payload differs: ' + row['path'])
    source = json.loads(data['source/SOURCE.json'])
    for row in source['files']:
        body = data['source/' + row['path']]
        blob = hashlib.sha1(b'blob ' + str(len(body)).encode() + b'\0' + body).hexdigest()
        require(blob == row['git_blob'] and digest(body) == row['sha256'], 'Source identity differs')
    result = json.loads(data['native-result/receipt.json'])
    require(result['accepted'] is True and all(result['checks'].values()), 'Recorded course did not accept')
    print(json.dumps({'verified': True, 'payloads': 28, 'source_commit': source['commit'],
                      'recorded_project_events': 79, 'recorded_part_events': 3,
                      'source_execution': False, 'extracted_files': 0}, sort_keys=True))


if __name__ == '__main__':
    main()
