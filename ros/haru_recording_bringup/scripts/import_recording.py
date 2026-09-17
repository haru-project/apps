#!/usr/bin/env python3
"""Copy one existing recording into the isolated library; never change the source."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from haru_recording_bringup.launches import workspace


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('--destination',type=Path,default=workspace()/'data/library')
    args=parser.parse_args()
    source=args.source.expanduser().resolve()
    manifest=source/'manifest.json'
    if not manifest.is_file() or not (source/'bag/metadata.yaml').is_file(): parser.error('Expected a session directory containing manifest.json and bag/metadata.yaml')
    try: value=json.loads(manifest.read_text())
    except ValueError: parser.error('Malformed manifest; repair a separate copy explicitly before import')
    if not isinstance(value,dict): parser.error('Manifest must be a JSON object')
    if any(p.is_symlink() for p in source.rglob('*')): parser.error('Source contains symlinks; resolve them explicitly before import')
    parent=args.destination.expanduser().resolve()
    if parent==source or source in parent.parents: parser.error('Destination must be outside the source')
    parent.mkdir(parents=True,exist_ok=True)
    target=parent/(source.name+'-'+hashlib.sha256(str(source).encode()).hexdigest()[:8])
    if target.exists(): parser.error('Import already exists: '+str(target))
    with tempfile.TemporaryDirectory(prefix='.import-',dir=parent) as temporary:
        staging=Path(temporary)/'session'
        # Reflinks save space when supported; never hard-link writable manifests or bags.
        subprocess.run(['cp','--reflink=auto','--sparse=always','-a',str(source),str(staging)],check=True)
        (staging/'import-source.json').write_text(json.dumps({'source':str(source),'manifest_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest()},indent=2)+'\n')
        staging.rename(target)
    print(target)

if __name__=='__main__':main()
