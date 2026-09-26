#!/usr/bin/env python3
"""Local Codex continuity wrapper. Python standard library only."""
import io
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import threading
from datetime import datetime, timezone

VERSION = '1.0.0'
ANSI = re.compile(r'\x1b\][^\x07]*(?:\x07|\x1b\\)|\x1b\[[0-?]*[ -/]*[@-~]')
HELP = '''codex_enikk — Codex 세션 이어가기

  codex_enikk                    마지막 세션 재개 (현재 작업 폴더 기준)
  codex_enikk --resume           기존 세션 선택
  codex_enikk --resume ID        지정 세션 재개
  codex_enikk --help             이 도움말
  codex_enikk --version          버전

추가 옵션은 codex resume에 전달합니다. --new는 지원하지 않습니다.
백업: ~/git/codex-enikk-session-backups/ (시작 전 / 종료 후)
복구: codex_enikk_restore BACKUP.tar.gz
'''


def codex_home():
    return Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))).expanduser().resolve()


def backup_dir():
    return Path(os.environ.get('CODEX_ENIKK_BACKUP_DIR', str(Path.home() / 'git/codex-enikk-session-backups'))).expanduser()


def records(path):
    with path.open(encoding='utf-8', errors='replace') as stream:
        for line in stream:
            try:
                yield json.loads(line)
            except (ValueError, TypeError):
                continue  # A running Codex process may still be writing the last line.


def private_dir(path):
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink() or not path.is_dir():
        raise OSError(f'일반 디렉터리가 아닙니다: {path}')
    path.chmod(0o700)


def backup():
    source = codex_home()
    target = backup_dir()
    private_dir(target)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    fd, temporary = tempfile.mkstemp(prefix='.incomplete-', dir=target)
    result = target / f'codex-enikk-{stamp}.tar.gz'
    try:
        paths = []
        for folder in ('sessions', 'archived_sessions'):
            root = source / folder
            if root.is_symlink():
                raise OSError(f'심볼릭 링크 세션 폴더는 백업할 수 없습니다: {root}')
            if root.exists():
                paths.extend(root.rglob('*.jsonl'))
        paths.extend(source / name for name in ('history.jsonl', 'session_index.jsonl'))
        manifest = {'version': VERSION, 'created_utc': stamp, 'files': [],
                    'scope': 'session JSONL and history; not a filesystem snapshot'}
        with os.fdopen(fd, 'wb') as raw, tarfile.open(fileobj=raw, mode='w:gz') as archive:
            for path in sorted(set(paths)):
                if not path.exists():
                    continue
                if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(source):
                    raise OSError(f'백업 범위 밖 경로: {path}')
                data = path.read_bytes()
                name = 'codex/' + path.relative_to(source).as_posix()
                info = tarfile.TarInfo(name)
                info.size, info.mode, info.mtime = len(data), 0o600, int(path.stat().st_mtime)
                archive.addfile(info, io.BytesIO(data))
                manifest['files'].append(name)
            data = json.dumps(manifest, ensure_ascii=False, indent=2).encode()
            info = tarfile.TarInfo('manifest.json')
            info.size, info.mode = len(data), 0o600
            archive.addfile(info, io.BytesIO(data))
        os.replace(temporary, result)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
    print(f'세션 백업: {result}', flush=True)
    return result


def restore(archive_path):
    """Restore missing files only, preserving existing conversations and archives."""
    source = codex_home()
    private_dir(source)
    restored = skipped = 0
    with tarfile.open(archive_path, 'r:gz') as archive:
        members = archive.getmembers()
        # Validate every entry before writing anything. Never extractall().
        for item in members:
            if item.name == 'manifest.json' and item.isfile():
                continue
            parts = Path(item.name).parts
            allowed = (len(parts) == 2 and parts[1] in ('history.jsonl', 'session_index.jsonl')) or (
                len(parts) >= 3 and parts[1] in ('sessions', 'archived_sessions') and item.name.endswith('.jsonl'))
            if not item.isfile() or not parts or parts[0] != 'codex' or '..' in parts or not allowed:
                raise ValueError(f'허용되지 않은 백업 항목: {item.name}')
            destination = source.joinpath(*parts[1:])
            if not destination.resolve().is_relative_to(source) or any(p.is_symlink() for p in [destination, *destination.parents] if p != source):
                raise ValueError(f'복구 경로에 심볼릭 링크가 있습니다: {item.name}')
        for item in members:
            if item.name == 'manifest.json':
                continue
            destination = source.joinpath(*Path(item.name).parts[1:])
            destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            try:
                fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                skipped += 1
                continue
            try:
                with os.fdopen(fd, 'wb') as out, archive.extractfile(item) as src:
                    shutil.copyfileobj(src, out)
            except BaseException:
                destination.unlink(missing_ok=True)
                raise
            restored += 1
    print(f'복구: {restored}개, 기존 파일 유지: {skipped}개')
    return restored


def text_content(content):
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ''
    return '\n'.join(str(p.get('text', '')) for p in content
                     if isinstance(p, dict) and p.get('type') in ('text', 'input_text', 'output_text'))


def transcript(path):
    events, responses = [], []
    for record in records(path):
        payload = record.get('payload') or {}
        if record.get('type') == 'event_msg':
            kind = payload.get('type')
            if kind in ('user_message', 'agent_message'):
                role = '사용자' if kind == 'user_message' else 'CODEX'
                events.append((role, payload.get('message', '')))
            elif kind == 'item_completed':
                item = payload.get('item') or {}
                if item.get('type') in ('UserMessage', 'AgentMessage'):
                    events.append(('사용자' if item['type'] == 'UserMessage' else 'CODEX', text_content(item.get('content'))))
        elif record.get('type') == 'response_item' and payload.get('type') == 'message':
            role = payload.get('role')
            if role in ('user', 'assistant'):
                responses.append(('사용자' if role == 'user' else 'CODEX', text_content(payload.get('content'))))
    return '\n\n'.join(f'[{role}]\n{ANSI.sub("", str(body))}' for role, body in (events or responses) if body) + '\n'


def export_changed(baseline, cwd, output):
    for path in (codex_home() / 'sessions').rglob('*.jsonl'):
        if path.is_symlink() or not path.resolve().is_relative_to(codex_home()):
            continue
        stat = path.stat()
        if baseline.get(str(path)) == (stat.st_mtime_ns, stat.st_size):
            continue
        meta = next((r.get('payload', {}) for r in records(path) if r.get('type') == 'session_meta'), {})
        if meta.get('cwd') != str(cwd):
            continue
        private_dir(output)
        safe_id = re.sub(r'[^a-zA-Z0-9_-]', '_', str(meta.get('id') or path.stem))
        fd, temporary = tempfile.mkstemp(prefix='.transcript-', dir=output)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                stream.write(transcript(path))
            os.replace(temporary, output / f'codex-session-{safe_id}.txt')
        finally:
            Path(temporary).unlink(missing_ok=True)
        baseline[str(path)] = (stat.st_mtime_ns, stat.st_size)


def main(args=None):
    args = list(sys.argv[1:] if args is None else args)
    if args == ['--help'] or args == ['-h']:
        print(HELP)
        return 0
    if args == ['--version']:
        print(f'codex_enikk {VERSION}')
        return 0
    if '--new' in args:
        print('--new는 지원하지 않습니다. 기존 세션은 그대로 유지됩니다.', file=sys.stderr)
        return 2
    explicit = bool(args and args[0] == '--resume')
    if explicit:
        args.pop(0)
    command = ['codex', 'resume'] + ([] if explicit else ['--last']) + args
    if shutil.which('codex') is None:
        print('codex CLI를 먼저 설치해주세요.', file=sys.stderr)
        return 127
    try:
        backup()
    except (OSError, ValueError) as exc:
        print(f'시작 전 백업 실패: {exc}', file=sys.stderr)
        return 1
    cwd = Path.cwd()
    output = Path(os.environ.get('CODEX_ENIKK_LOG_DIR', str(backup_dir() / 'transcripts'))).expanduser()
    baseline = {str(p): (p.stat().st_mtime_ns, p.stat().st_size)
                for p in (codex_home() / 'sessions').rglob('*.jsonl') if p.is_file()}
    stop = threading.Event()
    def watcher():
        while not stop.wait(2):
            try:
                export_changed(baseline, cwd, output)
            except (OSError, ValueError) as exc:
                print(f'대화문 저장 경고: {exc}', file=sys.stderr)
    thread = threading.Thread(target=watcher, daemon=True)
    thread.start()
    status = 1
    child = None
    previous = {}
    def forward(signum, frame):
        if child is not None and child.poll() is None:
            child.send_signal(signum)
    try:
        for sig in (signal.SIGINT, signal.SIGTERM):
            previous[sig] = signal.signal(sig, forward)
        child = subprocess.Popen(command)
        status = child.wait()
    finally:
        stop.set()
        thread.join()
        for sig, handler in previous.items():
            signal.signal(sig, handler)
        for operation in (lambda: export_changed(baseline, cwd, output), backup):
            try:
                operation()
            except (OSError, ValueError) as exc:
                print(f'종료 시 저장 실패: {exc}. 원본 세션은 CODEX_HOME에 남아 있습니다.', file=sys.stderr)
                if status == 0:
                    status = 1
    return status if status >= 0 else 128 - status


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, tarfile.TarError) as error:
        print(f'codex_enikk: {error}', file=sys.stderr)
        sys.exit(1)
