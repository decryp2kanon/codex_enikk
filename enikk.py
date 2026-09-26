#!/usr/bin/env python3
"""Local Codex continuity wrapper. Python standard library only."""
import io
import fcntl
import errno
import socket
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
from datetime import datetime, timezone

VERSION = '2.1.1'
INSTANCE_SOCKET_PREFIX = '\0codex_enikk.instance.'
ANSI = re.compile(r'\x1b\][^\x07]*(?:\x07|\x1b\\)|\x1b\[[0-?]*[ -/]*[@-~]')
HELP = '''codex_enikk — 기존 대화를 원래 Codex 화면으로 이어가기

  codex_enikk                 연결된 대화를 Codex TUI + YOLO로 재개
  codex_enikk --resume        같은 동작 (호환 옵션)
  codex_enikk --yolo          기본 동작과 동일 (호환 옵션)
  codex_enikk -i IMAGE        이미지 파일 첨부
  codex_enikk -m MODEL        시작 모델 지정
  codex_enikk --help          도움말
  codex_enikk --version       버전

기본 실행은 YOLO 모드입니다. 명령 실행 승인과 샌드박스 제한을 사용하지 않습니다.
Codex 자체 입력창, 이미지 붙여넣기, /model 등 슬래시 명령을 그대로 사용합니다.
추가 인수는 codex resume에 전달합니다. 옵션 설명: codex resume --help
시작 시 연결된 세션 ID를 사용하며, TUI 안의 세션 전환 명령은 차단하지 않습니다.
시작·종료 시 백업: ~/git/codex-enikk-session-backups/
'''



def codex_home():
    return Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))).expanduser().resolve()


def backup_dir():
    return Path(os.environ.get('CODEX_ENIKK_BACKUP_DIR', str(Path.home() / 'git/codex-enikk-session-backups'))).expanduser()


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
        paths = []
        for folder in ('sessions', 'archived_sessions'):
            root = source / folder
            if root.is_symlink():
                raise OSError(f'심볼릭 링크 세션 폴더는 백업할 수 없습니다: {root}')
            if root.exists():
                paths.extend(root.rglob('*.jsonl'))
        paths.extend(source / name for name in ('history.jsonl', 'session_index.jsonl', 'enikk-continuity.json'))
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
            allowed = (len(parts) == 2 and parts[1] in ('history.jsonl', 'session_index.jsonl', 'enikk-continuity.json')) or (
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


def export_changed(baseline, cwd, output, session_id=None):
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
        fd, temporary = tempfile.mkstemp(prefix='.transcript-', dir=output)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                stream.write(transcript(path))
            os.replace(temporary, output / f'codex-session-{safe_id}.txt')
        finally:
            Path(temporary).unlink(missing_ok=True)
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
    # The kernel releases it on exit; never delete a lock file to unlock it.
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as guard:
        try:
            guard.bind(INSTANCE_SOCKET_PREFIX + str(os.getuid()))
        except OSError as exc:
            if exc.errno == errno.EADDRINUSE:
                raise ValueError('codex_enikk가 이미 실행 중입니다. 기존 창을 사용하세요.') from None
            raise
        yield guard


def conversation(session_id, instance_fd, args=()):
    """Let the native TUI own the terminal, clipboard, slash commands and rendering."""
    yolo = '--dangerously-bypass-approvals-and-sandbox'
    options = []
    literal = False
    for arg in args:
        if arg == '--':
            literal = True
        if not literal and arg in ('--yolo', yolo):
            continue  # Always enabled below; keep aliases idempotent.
        options.append(arg)
    command = ['codex', 'resume', session_id, yolo, *options]
    # Inherit stdin/stdout/stderr and the foreground terminal. Do not pipe or
    # parse TUI output: doing so breaks image paste, raw input and rendering.
    child = subprocess.Popen(command, pass_fds=(instance_fd,))
    try:
        while True:
            try:
                status = child.wait()
                return status if status >= 0 else 128 - status
            except KeyboardInterrupt:
                # The foreground child receives Ctrl+C too; let Codex handle it.
                continue
    except BaseException:
        if child.poll() is None:
            child.terminate()
        try:
            child.wait(timeout=10)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()
        raise


def main(args=None):
    args = list(sys.argv[1:] if args is None else args)
    if args in (['--help'], ['-h']):
        print(HELP)
        return 0
    if args == ['--version']:
        print(f'codex_enikk {VERSION}')
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
            session_id = pinned_session()
            backup()
            cwd = Path.cwd()
            output = Path(os.environ.get('CODEX_ENIKK_LOG_DIR', str(backup_dir() / 'transcripts'))).expanduser()
            baseline = {}
            stop = threading.Event()
            save_errors = set()
            def watcher():
                while not stop.wait(2):
                    try:
                        export_changed(baseline, cwd, output, session_id)
                    except (OSError, ValueError) as exc:
                        save_errors.add(str(exc))  # Do not corrupt the active TUI.
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
                for operation in (lambda: export_changed(baseline, cwd, output, session_id), backup):
                    try:
                        operation()
                    except (OSError, ValueError) as exc:
                        print(f'종료 시 저장 실패: {exc}. 원본 세션은 CODEX_HOME에 남아 있습니다.', file=sys.stderr)
                        if status == 0:
                            status = 1
            return status


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, tarfile.TarError, KeyboardInterrupt) as error:
        print(f'codex_enikk: {error}', file=sys.stderr)
        sys.exit(1)
