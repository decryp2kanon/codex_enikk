#!/usr/bin/env python3
"""Local Codex continuity wrapper. Python standard library only."""
import io
import hashlib
import ctypes
import signal
import time
import fcntl
import errno
import socket
import sqlite3
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import termios
from datetime import datetime, timezone
from latest import Mirror
from core_runtime import app_server
from continuity import Continuity
from persistence import DATABASES, snapshots, validate_database, validate_rollouts

VERSION = '2.2.0'
SUPPORTED_CODEX_VERSIONS = frozenset({'0.158.0', '0.160.0'})


def supported_codex_version(output):
    return output.strip() in {f'codex-cli {version}' for version in SUPPORTED_CODEX_VERSIONS}


LATEST_TRANSCRIPT_FILE = None
TRANSCRIPT_PART_BYTES = 10_000_000
INSTANCE_SOCKET_PREFIX = '\0codex_enikk.instance.'
ANSI = re.compile(r'\x1b\][^\x07]*(?:\x07|\x1b\\)|\x1b\[[0-?]*[ -/]*[@-~]')
HELP = '''codex_enikk — 기존 대화를 원래 Codex 화면으로 이어가기

  codex_enikk                 연결된 대화를 Codex TUI + YOLO로 재개
  codex_enikk --resume        같은 동작 (호환 옵션)
  codex_enikk --yolo          기본 동작과 동일 (호환 옵션)
  codex_enikk -i IMAGE        이미지 파일 첨부
  codex_enikk -m MODEL        시작 모델 지정
  codex_enikk --tts-debug     별도 터미널 창에서 현재 TTS 로그 보기
  codex_enikk --continuity-check   세션·원문·DB 검사 (읽기 전용)
  codex_enikk --history-search TEXT [--direct-user-only]  보존 원문 검색
  codex_enikk --help          도움말
  codex_enikk --version       버전

기본 실행은 YOLO 모드입니다. 명령 실행 승인과 샌드박스 제한을 사용하지 않습니다.
Codex 자체 입력창, 이미지 붙여넣기, /model 등 슬래시 명령을 그대로 사용합니다.
추가 인수는 codex resume에 전달합니다. 옵션 설명: codex resume --help
시작 시 연결된 세션 ID를 사용하며, TUI 안의 세션 전환 명령은 차단하지 않습니다.
저장 위치: /var/tmp/codex_enikk-사용자UID/
'''



def codex_home():
    return Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))).expanduser().resolve()


def data_dir():
    configured = Path(os.environ.get(
        'CODEX_ENIKK_DATA_DIR', f'/var/tmp/codex_enikk-{os.getuid()}')).expanduser()
    if not configured.is_absolute():
        raise ValueError('CODEX_ENIKK_DATA_DIR는 절대 경로여야 합니다.')
    path = configured.resolve()
    if any((parent / '.git').exists() for parent in (path, *path.parents)):
        raise ValueError(f'Codex Enikk 저장 위치는 Git 저장소 밖이어야 합니다: {path}')
    return path


def validate_storage_dir(path):
    path = Path(path).expanduser()
    if not path.is_absolute():
        raise ValueError('대화문 저장 위치는 절대 경로여야 합니다.')
    path = path.resolve()
    if any((parent / '.git').exists() for parent in (path, *path.parents)):
        raise ValueError(f'대화문은 Git 저장소 안에 저장할 수 없습니다: {path}')
    return path


def validate_backup_dir(value):
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise ValueError('백업 위치는 절대 경로여야 합니다.')
    path = path.resolve()
    for parent in (path, *path.parents):
        if (parent / '.git').exists():
            ignored = subprocess.run(['git', '-C', str(parent), 'check-ignore', '-q', '--no-index', str(path)],
                                     capture_output=True)
            if ignored.returncode != 0:
                raise ValueError(f'백업 폴더가 Git에서 제외되지 않았습니다: {path}')
    return path


def backup_settings():
    config = Path.home() / '.config' / 'codex_enikk' / 'backup.json'
    return json.loads(config.read_text(encoding='utf-8')) if config.exists() else {}


def backup_dir():
    configured = backup_settings().get('primary')
    if configured:
        return validate_backup_dir(configured)
    if 'CODEX_ENIKK_DATA_DIR' in os.environ:
        return data_dir() / 'backups'
    return Path.home() / 'Enikk-backups' / 'backups'


def mirror_backup(source):
    settings = backup_settings()
    if not settings.get('secondary'):
        return
    mount = Path(settings['secondary_mount'])
    if not mount.is_mount():
        raise OSError(f'백업 디스크가 마운트되지 않았습니다: {mount}')
    target = validate_backup_dir(settings['secondary'])
    private_dir(target)
    destination = target / source.name
    fd, temporary = tempfile.mkstemp(prefix='.incomplete-', dir=target)
    try:
        digest = hashlib.sha256()
        with source.open('rb') as reader, os.fdopen(fd, 'wb') as writer:
            while chunk := reader.read(1024 * 1024):
                writer.write(chunk)
                digest.update(chunk)
            writer.flush()
            os.fsync(writer.fileno())
        with Path(temporary).open('rb') as reader:
            check = hashlib.file_digest(reader, 'sha256').hexdigest() if hasattr(hashlib, 'file_digest') else None
            if check is None:
                hashed = hashlib.sha256()
                while chunk := reader.read(1024 * 1024):
                    hashed.update(chunk)
                check = hashed.hexdigest()
        if check != digest.hexdigest():
            raise OSError('두 번째 백업의 SHA256 검증에 실패했습니다.')
        os.link(temporary, destination)
        directory_fd = os.open(target, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        Path(temporary).unlink(missing_ok=True)
    print(f'두 번째 디스크 백업: {destination}', flush=True)


def transcript_dir():
    return data_dir() / 'transcripts'


def latest_transcript_dir():
    return data_dir() / 'latest'


def records(path):
    with path.open(encoding='utf-8', errors='replace') as stream:
        for line in stream:
            try:
                record = json.loads(line)
                if isinstance(record, dict):
                    yield record
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
        with tempfile.TemporaryDirectory(prefix='.sqlite-', dir=target) as directory:
            stage = Path(directory)
            timings = snapshots(source, stage)
            paths = []
            for folder in ('sessions', 'archived_sessions'):
                root = source / folder
                if root.is_symlink():
                    raise OSError(f'심볼릭 링크 세션 폴더는 백업할 수 없습니다: {root}')
                if root.exists():
                    paths.extend(root.rglob('*.jsonl'))
            paths.extend(source / name for name in ('history.jsonl', 'session_index.jsonl', 'enikk-continuity.json'))
            version = None
            if timings:
                try:
                    process = subprocess.run(['codex', '--version'], stdin=subprocess.DEVNULL,
                                             capture_output=True, text=True, timeout=3)
                    if process.returncode == 0:
                        version = process.stdout.strip()
                except (OSError, subprocess.TimeoutExpired):
                    pass
            manifest = {'version': VERSION, 'format_version': 2, 'codex_cli_version': version,
                        'created_utc': stamp, 'source_codex_home': str(source), 'files': [],
                        'sha256': {}, 'components': [],
                        'sqlite_snapshot_seconds': timings,
                        'scope': 'conversation files and SQLite snapshots; not a filesystem snapshot',
                        'consistency': 'per-database live snapshot; close Codex for a cross-file point-in-time backup'}
            entries = []
            for path in sorted(set(paths)):
                if not path.exists():
                    continue
                if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(source):
                    raise OSError(f'백업 범위 밖 경로: {path}')
                entries.append(('codex/' + path.relative_to(source).as_posix(), path))
            entries.extend(('codex/' + name, stage / name) for name in timings)
            manifest['components'] = sorted({Path(name).parts[1] for name, _ in entries})
            sizes = {}
            # Compression level changes size/CPU only; snapshots, validation and
            # atomic publication retain exactly the same backup semantics.
            with os.fdopen(fd, 'wb') as raw, tarfile.open(fileobj=raw, mode='w:gz', compresslevel=1) as archive:
                fd = None
                for name, path in entries:
                    data = path.read_bytes()
                    info = tarfile.TarInfo(name)
                    info.size, info.mode, info.mtime = len(data), 0o600, int(path.stat().st_mtime)
                    archive.addfile(info, io.BytesIO(data))
                    sizes[name] = len(data)
                    manifest['files'].append(name)
                    manifest['sha256'][name] = hashlib.sha256(data).hexdigest()
                validate_rollouts(stage, source, sizes)
                data = json.dumps(manifest, ensure_ascii=False, indent=2).encode()
                info = tarfile.TarInfo('manifest.json')
                info.size, info.mode = len(data), 0o600
                archive.addfile(info, io.BytesIO(data))
            # Never replace an existing backup, even if a clock repeats a timestamp.
            os.link(temporary, result)
            Path(temporary).unlink()
    except BaseException:
        if fd is not None:
            os.close(fd)
        Path(temporary).unlink(missing_ok=True)
        raise
    with result.open('rb') as durable:
        os.fsync(durable.fileno())
    directory_fd = os.open(target, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
    print(f'세션 백업: {result}', flush=True)
    mirror_backup(result)
    return result


def restore(archive_path):
    """Preflight all data; SQLite restores require an empty persistence store."""
    source = codex_home()
    private_dir(source)
    restored = skipped = 0
    with tempfile.TemporaryDirectory(prefix='.restore-', dir=source.parent) as directory:
        stage = Path(directory)
        with tarfile.open(archive_path, 'r:gz') as archive:
            members = archive.getmembers()
            names = [item.name for item in members]
            if len(names) != len(set(names)):
                raise ValueError('중복된 백업 항목입니다.')
            manifest = {}
            if 'manifest.json' in names:
                item = archive.getmember('manifest.json')
                if not item.isfile():
                    raise ValueError('잘못된 manifest입니다.')
                manifest = json.load(archive.extractfile(item))
                if not isinstance(manifest, dict):
                    raise ValueError('잘못된 manifest입니다.')
            modern = manifest.get('format_version') == 2
            has_sqlite = any(name == 'codex/' + db for name in names for db in DATABASES)
            if has_sqlite and not modern:
                raise ValueError('SQLite 복구에는 검증 가능한 format 2 manifest가 필요합니다.')
            if has_sqlite and any((source / (db + suffix)).exists() or (source / (db + suffix)).is_symlink()
                                  for db in DATABASES for suffix in ('', '-wal', '-shm', '-journal')):
                raise ValueError('기존 SQLite가 있습니다. 덮어쓰기/병합하지 않습니다. 빈 CODEX_HOME에 복구하세요.')
            payloads = set(names) - {'manifest.json'}
            if modern and (set(manifest.get('files', [])) != payloads or
                           set(manifest.get('sha256', {})) != payloads):
                raise ValueError('백업 manifest와 파일 목록이 일치하지 않습니다.')
            for item in members:
                if item.name == 'manifest.json':
                    continue
                parts = Path(item.name).parts
                allowed = (len(parts) == 2 and parts[1] in (
                    'history.jsonl', 'session_index.jsonl', 'enikk-continuity.json', *DATABASES)) or (
                    len(parts) >= 3 and parts[1] in ('sessions', 'archived_sessions') and item.name.endswith('.jsonl'))
                if not item.isfile() or not parts or parts[0] != 'codex' or '..' in parts or not allowed:
                    raise ValueError(f'허용되지 않은 백업 항목: {item.name}')
                destination = source.joinpath(*parts[1:])
                if has_sqlite and destination.exists():
                    raise ValueError('SQLite 복구 대상에 기존 대화 파일이 있습니다. 빈 CODEX_HOME을 사용하세요.')
                if not destination.resolve().is_relative_to(source) or any(
                        p.is_symlink() for p in [destination, *destination.parents] if p != source):
                    raise ValueError(f'복구 경로에 심볼릭 링크가 있습니다: {item.name}')
                staged = stage.joinpath(*parts[1:])
                staged.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                digest = hashlib.sha256()
                with archive.extractfile(item) as incoming, staged.open('xb') as out:
                    while chunk := incoming.read(1024 * 1024):
                        digest.update(chunk)
                        out.write(chunk)
                staged.chmod(0o600)
                if staged.stat().st_size != item.size or (modern and digest.hexdigest() != manifest['sha256'][item.name]):
                    raise ValueError(f'손상된 백업 항목: {item.name}')
            # Consume the gzip trailer too, before installing any restored files.
            while archive.fileobj.read(1024 * 1024):
                pass
            for name in DATABASES:
                if (stage / name).exists():
                    validate_database(stage / name)
            if has_sqlite:
                original = Path(manifest.get('source_codex_home', ''))
                if not original.is_absolute():
                    raise ValueError('원본 CODEX_HOME 경로가 올바르지 않습니다.')
                validate_rollouts(stage, original, {m.name: m.size for m in members}, relocate_to=source)
            # No writes into CODEX_HOME until every entry and DB has passed validation.
            for item in members:
                if item.name == 'manifest.json':
                    continue
                relative = Path(*Path(item.name).parts[1:])
                destination = source / relative
                destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                try:
                    # Same-filesystem atomic publish; existing files are never replaced.
                    os.link(stage / relative, destination)
                except FileExistsError:
                    if has_sqlite:
                        raise ValueError('복구 중 대상 파일이 생성됐습니다. Codex를 종료하고 빈 경로에서 다시 복구하세요.')
                    skipped += 1
                    continue
                restored += 1
    print(f'복구: {restored}개, 기존 파일 유지: {skipped}개')
    return restored


def text_content(content):
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ''
    return '\n'.join(str(p.get('text', '')) for p in content
                     if isinstance(p, dict) and str(p.get('type', '')).lower() in ('text', 'input_text', 'output_text'))


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


def write_transcript_parts(output, safe_id, text, limit=TRANSCRIPT_PART_BYTES):
    """Atomically update numbered UTF-8 files, each at most 10 MB by default."""
    if limit < 4:
        raise ValueError('TXT 분할 크기는 최소 4바이트여야 합니다.')
    output = validate_storage_dir(output)
    private_dir(output)
    data = text.encode('utf-8')
    start = 0
    index = 1
    active = set()
    while start < len(data) or index == 1:
        end = min(start + limit, len(data))
        # Move a boundary back to the start of a multibyte character.
        while end < len(data) and data[end] & 0xC0 == 0x80:
            end -= 1
        chunk = data[start:end]
        destination = output / f'codex-session-{safe_id}-part-{index:06d}.txt'
        active.add(destination)
        if destination.is_symlink():
            raise OSError(f'대화문 경로가 심볼릭 링크입니다: {destination}')
        if not destination.exists() or destination.read_bytes() != chunk:
            fd, temporary = tempfile.mkstemp(prefix='.transcript-', dir=output)
            try:
                with os.fdopen(fd, 'wb') as stream:
                    stream.write(chunk)
                os.replace(temporary, destination)
            finally:
                Path(temporary).unlink(missing_ok=True)
        start = end
        index += 1
    # If the source was shortened, retain old trailing parts outside the active set.
    stale = [p for p in output.glob(f'codex-session-{safe_id}-part-*.txt') if p not in active]
    if stale:
        archive = output / ('superseded-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ'))
        private_dir(archive)
        for path in stale:
            path.rename(archive / path.name)
    return sorted(active)


def write_latest_transcript(path, target=200_000):
    """Local-only handoff, retaining complete messages and the latest result."""
    global LATEST_TRANSCRIPT_FILE
    events, fallback = [], []
    for record in records(path):
        payload = record.get('payload') or {}
        role, phase, body = None, None, ''
        destination = events
        if record.get('type') == 'event_msg':
            kind = payload.get('type')
            if kind in ('user_message', 'agent_message'):
                role = 'user' if kind == 'user_message' else 'assistant'
                phase = payload.get('phase', 'final_answer')
                body = payload.get('message', '')
            elif kind == 'item_completed':
                item = payload.get('item') or {}
                role = {'UserMessage': 'user', 'AgentMessage': 'assistant'}.get(item.get('type'))
                phase = item.get('phase', 'final_answer')
                body = text_content(item.get('content'))
        elif record.get('type') == 'response_item' and payload.get('type') == 'message':
            role = payload.get('role')
            phase = payload.get('phase') or payload.get('channel') or 'final_answer'
            body = text_content(payload.get('content'))
            destination = fallback
        if role not in ('user', 'assistant') or not body:
            continue
        if role == 'assistant' and phase not in ('commentary', 'final', 'final_answer', None):
            continue
        final = role == 'assistant' and phase != 'commentary'
        label = '사용자' if role == 'user' else ('CODEX 최종' if final else 'CODEX 진행')
        block = f'[{label}]\n{ANSI.sub("", str(body))}\n\n'
        destination.append((block, final))
    messages = events or fallback
    protected = {len(messages) - 1}
    latest_final = next((i for i in range(len(messages) - 1, -1, -1) if messages[i][1]), None)
    if latest_final is not None:
        protected.add(latest_final)
    sizes = [len(block.encode('utf-8')) for block, _ in messages]
    total = sum(sizes)
    keep = set(range(len(messages)))
    for i, size in enumerate(sizes):
        if total <= target:
            break
        if i not in protected:
            keep.remove(i)
            total -= size
    data = ''.join(block for i, (block, _) in enumerate(messages) if i in keep).encode('utf-8')
    output = latest_transcript_dir()
    private_dir(output)
    if LATEST_TRANSCRIPT_FILE is None:
        while True:
            candidate = output / datetime.now().strftime('codex-latest-%y%m%d-%H%M%S.txt')
            try:
                reserved = os.open(candidate, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError:
                time.sleep(0.1)  # A simultaneous run must not overwrite this file.
                continue
            os.close(reserved)
            LATEST_TRANSCRIPT_FILE = candidate
            break
    destination = LATEST_TRANSCRIPT_FILE
    if destination.is_symlink():
        raise OSError(f'최신 대화 경로가 심볼릭 링크입니다: {destination}')
    if destination.exists() and destination.read_bytes() == data:
        return destination
    fd, temporary = tempfile.mkstemp(prefix='.latest-', dir=output)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
        os.replace(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return destination


def export_changed(baseline, cwd, output, session_id=None, latest=True):
    for path in (codex_home() / 'sessions').rglob('*.jsonl'):
        if path.is_symlink() or not path.resolve().is_relative_to(codex_home()):
            continue
        stat = path.stat()
        if baseline.get(str(path)) == (stat.st_mtime_ns, stat.st_size):
            continue
        meta = next((r.get('payload', {}) for r in records(path) if r.get('type') == 'session_meta'), {})
        if (session_id and meta.get('id') != session_id) or (not session_id and meta.get('cwd') != str(cwd)):
            continue
        private_dir(output)
        safe_id = re.sub(r'[^a-zA-Z0-9_-]', '_', str(meta.get('id') or path.stem))
        # Serialise the built-in watcher and an optional live saver for this session.
        lock_path = output / f'.codex-session-{safe_id}.lock'
        fd = os.open(lock_path, os.O_CREAT | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            write_transcript_parts(output, safe_id, transcript(path))
            if session_id and latest:
                write_latest_transcript(path)
        baseline[str(path)] = (stat.st_mtime_ns, stat.st_size)


def session_metadata():
    for path in (codex_home() / 'sessions').rglob('*.jsonl'):
        if path.is_symlink() or not path.resolve().is_relative_to(codex_home()):
            continue
        meta = next((r.get('payload', {}) for r in records(path) if r.get('type') == 'session_meta'), {})
        if meta.get('id'):
            yield path, meta


def pinned_session():
    state = codex_home() / 'enikk-continuity.json'
    sessions = list(session_metadata())
    if state.exists():
        if state.is_symlink():
            raise ValueError('연속성 기록이 심볼릭 링크입니다. 중단합니다.')
        data = json.loads(state.read_text())
        if not isinstance(data, dict):
            raise ValueError('연속성 기록이 손상되었습니다. 백업을 복구해주세요.')
        session_id = data.get('session_id')
        match = next(((p, m) for p, m in sessions if m['id'] == session_id), None)
        if not match:
            raise ValueError('연결된 대화가 없습니다. 백업을 복구해주세요. 다른 대화로 전환하지 않습니다.')
        return session_id
    active = os.environ.get('CODEX_THREAD_ID')
    candidates = [(p, m) for p, m in sessions if m['id'] == active] if active else []
    if not candidates:
        candidates = [(p, m) for p, m in sessions if m.get('cwd') == str(Path.cwd())]
    if not candidates:
        candidates = sessions
    if not candidates:
        raise ValueError('저장된 기존 대화가 없습니다. 백업을 복구해주세요. 새 대화는 만들지 않습니다.')
    _, meta = max(candidates, key=lambda item: item[0].stat().st_mtime_ns)
    session_id = meta['id']
    if not isinstance(session_id, str) or not re.fullmatch(r'[a-zA-Z0-9_-]+', session_id):
        raise ValueError('올바르지 않은 세션 ID입니다.')
    fd, temporary = tempfile.mkstemp(prefix='.enikk-state-', dir=codex_home())
    try:
        with os.fdopen(fd, 'w') as out:
            json.dump({'session_id': session_id, 'version': 1}, out)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, state)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return session_id


@contextmanager
def single_instance():
    # Linux abstract socket: per OS user, independent of cwd/HOME/CODEX_HOME.
    # Only the wrapper owns this fd; never pass it to Codex or its daemons.
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as guard:
        try:
            guard.bind(INSTANCE_SOCKET_PREFIX + str(os.getuid()))
        except OSError as exc:
            if exc.errno == errno.EADDRINUSE:
                raise ValueError('codex_enikk가 이미 실행 중입니다. 기존 창을 사용하세요.') from None
            raise
        yield guard


def process_table():
    """Linux process identities include start time to avoid signalling reused PIDs."""
    table = {}
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit():
            continue
        try:
            fields = (entry / 'stat').read_text().rsplit(')', 1)[1].split()
            table[int(entry.name)] = (int(fields[1]), fields[19])
        except (OSError, ValueError, IndexError):
            continue
    return table


def signal_owned(pid, started, signum):
    try:
        fd = os.pidfd_open(pid)
    except ProcessLookupError:
        return
    try:
        if process_table().get(pid, (None, None))[1] == started:
            signal.pidfd_send_signal(fd, signum)
    except ProcessLookupError:
        pass
    finally:
        os.close(fd)


def stop_children(existing, grace=2.0):
    """Reap our adopted descendants too, including children that called setsid()."""
    deadline = time.monotonic() + grace
    signalled = set()
    while True:
        table = process_table()
        owned = {pid for pid, (parent, born) in table.items()
                 if parent == os.getpid() and (pid, born) not in existing}
        while True:
            more = {pid for pid, (parent, _) in table.items() if parent in owned}
            if more <= owned:
                break
            owned.update(more)
        if not owned:
            return
        for pid in owned:
            born = table[pid][1]
            # Collect children already exited instead of waiting on zombies.
            try:
                if os.waitpid(pid, os.WNOHANG)[0]:
                    continue
            except (ChildProcessError, ProcessLookupError):
                pass
            force = time.monotonic() >= deadline
            if force or (pid, born) not in signalled:
                signal_owned(pid, born, signal.SIGKILL if force else signal.SIGTERM)
                signalled.add((pid, born))
        if time.monotonic() > deadline + 3:
            print("경고: 종료 신호 후에도 일부 자식이 남아 있습니다.", file=sys.stderr)
            return
        time.sleep(0.02)


@contextmanager
def owned_processes():
    # Adopt orphaned grandchildren so cleanup can still find and reap them.
    libc = ctypes.CDLL(None, use_errno=True)
    previous = ctypes.c_int()
    if libc.prctl(37, ctypes.byref(previous), 0, 0, 0) != 0:  # PR_GET_CHILD_SUBREAPER
        raise OSError(ctypes.get_errno(), 'Cannot read child subreaper state')
    if libc.prctl(36, 1, 0, 0, 0) != 0:  # PR_SET_CHILD_SUBREAPER
        raise OSError(ctypes.get_errno(), 'Cannot supervise Codex children')
    existing = {(pid, born) for pid, (parent, born) in process_table().items()
                if parent == os.getpid()}
    handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGHUP, signal.SIGTERM)}
    def terminate(signum, frame):
        raise SystemExit(128 + signum)
    try:
        for sig in handlers:
            signal.signal(sig, terminate)
        yield
    finally:
        for sig in handlers:
            signal.signal(sig, signal.SIG_IGN)
        try:
            stop_children(existing)
        finally:
            libc.prctl(36, previous.value, 0, 0, 0)
            for sig, handler in handlers.items():
                signal.signal(sig, handler)


@contextmanager
def submission_proxy(endpoint, session_id, python):
    """Wrapper owns both submission paths; never spawn another Codex/TTS worker."""
    if not endpoint or os.environ.get('CODEX_ENIKK_TRIGGER', '1') != '1':
        yield endpoint
        return
    version = subprocess.run(['codex', '--version'], capture_output=True, text=True, timeout=5)
    if version.returncode or version.stdout.strip() != 'codex-cli 0.160.0':
        raise RuntimeError('Submission arbiter requires verified Codex 0.160.0')
    script = Path(__file__).resolve().parent / 'trigger_service.py'
    root = Path(os.environ.get('XDG_STATE_HOME', Path.home() / '.local/state')) / 'codex_enikk/trigger'
    private_dir(root)
    with tempfile.TemporaryDirectory(prefix='enikk-arbiter-') as directory:
        proxy, ready = Path(directory) / 'native.sock', Path(directory) / 'ready.json'
        with (root / 'receiver.log').open('ab') as log:
            process = subprocess.Popen([str(python), str(script), '--upstream', endpoint.removeprefix('unix://'),
                '--thread', session_id, '--root', str(root), '--proxy', str(proxy),
                '--trigger', str(root / 'trigger.sock'), '--ready', str(ready)],
                stdin=subprocess.DEVNULL, stdout=log, stderr=log, close_fds=True, start_new_session=True)
            try:
                # Allow initialize (15s), resume (120s), and journal/startup overhead.
                deadline = time.monotonic() + 180
                while not ready.exists() and process.poll() is None and time.monotonic() < deadline:
                    time.sleep(.05)
                if not ready.exists() or process.poll() is not None:
                    raise RuntimeError('Submission arbiter failed to initialize; no unsafe direct fallback')
                yield 'unix://' + str(proxy)
            finally:
                if process.poll() is None:
                    process.terminate()
                    try: process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.kill(); process.wait()


@contextmanager
def terminal_restore():
    """Restore the caller's terminal even when the native TUI leaves raw mode."""
    fd = None
    saved = None
    restored = False
    try:
        candidate = sys.stdin.fileno()
        if os.isatty(candidate):
            saved = termios.tcgetattr(candidate)
            # stdin may be read-only; DEC cleanup needs a writable descriptor
            # for this exact terminal (never another process's terminal).
            fd = os.open(os.ttyname(candidate), os.O_RDWR | os.O_NOCTTY | os.O_CLOEXEC)
    except (AttributeError, OSError, ValueError, termios.error):
        pass

    def restore():
        nonlocal restored
        if fd is None or restored:
            return
        # Disable reports before restoring shell echo. Each cleanup step is
        # independent, so a failed ioctl cannot skip the DEC-mode reset.
        try:
            reset = (b'\x1b[?9l\x1b[?1000l\x1b[?1001l\x1b[?1002l\x1b[?1003l'
                     b'\x1b[?1004l\x1b[?1005l\x1b[?1006l\x1b[?1015l\x1b[?1016l'
                     b'\x1b[?2004l\x1b[?1049l\x1b[0m\x1b[?25h\r\x1b[J')
            pending = memoryview(reset)
            while pending:
                written = os.write(fd, pending)
                if not written:
                    raise OSError('terminal cleanup made no progress')
                pending = pending[written:]
            termios.tcdrain(fd)
        except (OSError, termios.error):
            pass
        try:
            # Discard unread TUI input (including queued mouse reports/paste)
            # instead of allowing it to become shell commands after exit.
            termios.tcsetattr(fd, termios.TCSAFLUSH, saved)
            restored = True
        except (OSError, termios.error):
            pass  # A closed terminal must not prevent session cleanup.

    try:
        yield restore
    finally:
        restore()
        if fd is not None:
            os.close(fd)


def open_tts_debug_window(state):
    """Read-only log viewer; it never starts another TTS worker."""
    terminal = shutil.which('gnome-terminal')
    if not terminal or not (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')):
        print('TTS debug 창을 열 수 없습니다: GUI 터미널이 필요합니다.', file=sys.stderr)
        return
    log = Path(state) / 'runtime.log'
    log.touch(exist_ok=True)
    events = Path(state) / 'notify.log'
    events.touch(exist_ok=True)
    try:
        subprocess.Popen([terminal, '--window', '--title=Yuki TTS debug', '--',
                          'tail', '-n', '80', '-F', '--pid=' + str(os.getpid()), str(log), str(events)],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, close_fds=True, start_new_session=True)
    except OSError as exc:
        print(f'TTS debug 창 시작 실패: {exc}', file=sys.stderr)


def conversation(session_id, instance_fd, args=()):
    """Let the native TUI own the terminal, clipboard, slash commands and rendering."""
    yolo = '--dangerously-bypass-approvals-and-sandbox'
    options = []
    tts_debug = False
    literal = False
    for arg in args:
        if arg == '--':
            literal = True
        if not literal and arg == '--tts-debug':
            tts_debug = True
            continue
        if not literal and arg in ('--yolo', yolo, '--no-daemon'):
            continue  # Always enabled below; keep aliases idempotent.
        options.append(arg)
    # The scoped watcher owns legacy TTS too; global notify hooks may point at
    # obsolete copies without run identity and must not race the watcher.
    command = ['codex', 'resume', session_id, yolo, '--no-daemon', '-c', 'notify=[]', *options]
    # Inherit stdin/stdout/stderr and the foreground terminal. Do not pipe or
    # parse TUI output: doing so breaks image paste, raw input and rendering.
    core_state = Path(os.environ.get('XDG_STATE_HOME', Path.home() / '.local/state')) / 'codex_enikk/core'
    private_dir(core_state)
    if tts_debug:
        print('음성 상태와 로그: enikk_tts status / journalctl --user -u enikk-tts', file=sys.stderr)
    log_dir = Path.home() / 'Enikk-logs'
    private_dir(log_dir)
    # Core owns the server, mirror and trigger even when TTS is not installed.
    with terminal_restore() as restore_terminal, owned_processes(), Mirror(
            codex_home() / 'thread_history_1.sqlite', session_id,
            log_dir / 'codex-latest.txt', core_state / 'mirror-thread.json'):
        with app_server() as upstream, submission_proxy(upstream, session_id, sys.executable) as endpoint:
            if endpoint:
                command = ['codex', 'resume', session_id, '--remote', endpoint, *options]
            previous_suspend = signal.signal(signal.SIGTSTP, signal.SIG_IGN)
            try:
                child = subprocess.Popen(command, close_fds=True)
            except BaseException:
                signal.signal(signal.SIGTSTP, previous_suspend)
                raise
            try:
                while True:
                    try:
                        status = child.wait()
                        return status if status >= 0 else 128 - status
                    except KeyboardInterrupt:
                        continue
            finally:
                signal.signal(signal.SIGTSTP, previous_suspend)
                if child.poll() is not None:
                    child.wait()
                    restore_terminal()


def main(args=None):
    os.environ['CODEX_ENIKK_STARTUP_NS'] = str(time.monotonic_ns())
    args = list(sys.argv[1:] if args is None else args)
    if args in (['--help'], ['-h']):
        print(HELP)
        return 0
    if args == ['--version']:
        print(f'codex_enikk {VERSION}')
        return 0
    evidence = Continuity(codex_home(), data_dir() / 'continuity')
    if args == ['--continuity-check']:
        evidence.require_binding()
        pin = json.loads((codex_home() / 'enikk-continuity.json').read_text())['session_id']
        matches = [p for p, m in session_metadata() if m['id'] == pin]
        if len(matches) != 1:
            raise ValueError('Pinned rollout missing or ambiguous')
        print(json.dumps(evidence.inspect(pin, matches[0], allow_partial=True), ensure_ascii=False))
        return 0
    if args[:1] == ['--history-search']:
        if len(args) not in (2, 3) or len(args) == 3 and args[2] != '--direct-user-only':
            raise ValueError('Usage: --history-search TEXT [--direct-user-only]')
        for item in evidence.search(args[1], direct_user_only=len(args) == 3):
            print(json.dumps(item, ensure_ascii=False))
        return 0
    if args[:1] == ['--resume']:
        args.pop(0)
    if shutil.which('codex') is None:
        print('codex CLI를 먼저 설치해주세요.', file=sys.stderr)
        return 127
    with single_instance() as guard:
        private_dir(codex_home())
        # Keep one process per Codex home, including first-time session binding.
        with (codex_home() / 'enikk-continuity.lock').open('a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise ValueError('이미 이 대화를 이어가는 앱이 실행 중입니다.')
            evidence.require_binding()
            session_id = pinned_session()
            matches = [p for p, m in session_metadata() if m['id'] == session_id]
            if len(matches) != 1:
                raise ValueError('Pinned rollout missing or ambiguous')
            rollout = matches[0]
            evidence.inspect(session_id, rollout, save=True)
            backup()
            cwd = Path.cwd()
            output = transcript_dir()
            baseline = {}
            stop = threading.Event()
            save_errors = set()
            def watcher():
                next_checkpoint = time.monotonic() + 60
                while not stop.wait(2):
                    try:
                        export_changed(baseline, cwd, output, session_id, latest=False)
                    except (OSError, ValueError) as exc:
                        save_errors.add(str(exc))
                    if time.monotonic() >= next_checkpoint:
                        try:
                            evidence.inspect(session_id, rollout, save=True, allow_partial=True)
                        except (OSError, ValueError, sqlite3.Error) as exc:
                            print(f'연속성 검사 실패: {exc}. 원문을 보존하고 실행을 종료합니다.', file=sys.stderr)
                            os.kill(os.getpid(), signal.SIGTERM)
                            return
                        next_checkpoint = time.monotonic() + 60
            thread = threading.Thread(target=watcher, daemon=True)
            thread.start()
            status = 1
            try:
                status = conversation(session_id, guard.fileno(), args)
            finally:
                stop.set()
                thread.join()
                for error in sorted(save_errors):
                    print(f'대화문 저장 경고: {error}', file=sys.stderr)
                for operation in (lambda: evidence.inspect(session_id, rollout, save=True),
                                  lambda: export_changed(baseline, cwd, output, session_id, latest=False), backup):
                    try:
                        operation()
                    except (OSError, ValueError, sqlite3.Error) as exc:
                        print(f'종료 시 저장 실패: {exc}. 원본 세션은 CODEX_HOME에 남아 있습니다.', file=sys.stderr)
                        if status == 0:
                            status = 1
            return status


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, tarfile.TarError, sqlite3.Error, KeyboardInterrupt) as error:
        print(f'codex_enikk: {error}', file=sys.stderr)
        sys.exit(1)
