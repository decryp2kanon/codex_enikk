"""Stage immutable TTS releases and atomically select one; never update core."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import uuid

ROOT_FILES = ('tts_control.py', 'tts_release.py')
FILES = ('yuki-text-normalization.py', 'yuki-text-normalization-overrides.py',
         'yuki-chatterbox-engine.py', 'yuki-codex-notify.py', 'yuki-codex-stream.py',
         'independent_service.py', 'README.md', 'DEFERRED-ISSUES.md')

def manifest(directory):
    return {str(p.relative_to(directory)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(directory.rglob('*')) if p.is_file() and p.name != 'manifest.json'}

def verify(directory):
    expected = json.loads((directory / 'manifest.json').read_text())
    if manifest(directory) != expected:
        raise ValueError('TTS release hash mismatch')
    for p in directory.glob('*.py'):
        compile(p.read_text(), str(p), 'exec')
    if (directory / 'PROTOCOL').read_text().strip() != '1':
        raise ValueError('unsupported release protocol')
    # Import without writing caches or loading the GPU/model.
    subprocess.run([sys.executable, '-B', '-c',
        'import sys;sys.path.insert(0,sys.argv[1]);import independent_service',
        str(directory)], check=True)

def select(base, release):
    verify(release)
    old = base / 'active'
    previous = old.resolve() if old.exists() else None
    temp = base / ('.active-' + uuid.uuid4().hex)
    temp.symlink_to(release.relative_to(base))
    os.replace(temp, old)
    fd = os.open(base, os.O_RDONLY | os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)
    if previous: print('Previous TTS release:', previous.name)
    print('Selected TTS release:', release.name)

def stage(source, base):
    source = Path(source).resolve()
    releases = base / 'releases'
    releases.mkdir(mode=0o700, parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='.stage-', dir=releases))
    try:
        for name in FILES:
            p = source / 'tts' / name
            if p.is_symlink(): raise ValueError('release source symlink')
            shutil.copyfile(p, staging / name)
        for name in ROOT_FILES:
            if (source / name).is_symlink(): raise ValueError('release source symlink')
            shutil.copyfile(source / name, staging / name)
        shutil.copyfile(source / 'VERSION', staging / 'VERSION')
        (staging / 'PROTOCOL').write_text('1\n')
        (staging / 'manifest.json').write_text(json.dumps(manifest(staging), sort_keys=True))
        verify(staging)
        key = hashlib.sha256((staging / 'manifest.json').read_bytes()).hexdigest()[:16]
        target = releases / key
        for p in staging.iterdir():
            if p.is_file():
                with p.open('rb') as f: os.fsync(f.fileno())
        if target.exists():
            verify(target)
        else:
            staging.rename(target)
        fd = os.open(releases, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(fd)
        finally: os.close(fd)
        return target
    finally:
        if staging.exists(): shutil.rmtree(staging)

def main(args=None):
    args = list(sys.argv[1:] if args is None else args)
    if len(args) != 2 or args[0] not in ('update', 'rollback'):
        print('enikk_tts update SOURCE | rollback RELEASE')
        return 2
    base = Path(os.environ.get('ENIKK_TTS_INSTALL', str(Path.home() / '.local/lib/enikk_tts'))).resolve()
    runtime = Path(os.environ.get('XDG_RUNTIME_DIR', '/run/user/' + str(os.getuid())))
    with (runtime / 'enikk-tts-control.lock').open('a+b') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if args[0] == 'update':
            release = stage(args[1], base)
        else:
            release = (base / 'releases' / args[1]).resolve()
            if release.parent != base / 'releases': raise ValueError('invalid release name')
        select(base, release)
    print('Apply with: enikk_tts restart (core stays running)')
    return 0

if __name__ == '__main__':
    sys.exit(main())
