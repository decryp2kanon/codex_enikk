"""Opt-in wrapper-owned local trigger and shared native submission proxy."""
import argparse
import fcntl
import hashlib
import json
import os
import re
from pathlib import Path
import signal
import socket
import stat
import subprocess
import tempfile
import threading
import time
from datetime import datetime, timezone

from voice_events import Publisher as VoicePublisher
from submission_arbiter import Arbiter, Busy, UnknownEffect
from trigger_transport import accept_websocket, connect, peer_uid, rpc_object

FIXTURE = '파일이나 코드를 변경하지 말고 다음 한 문장만 답해. 도로시 로컬 트리거 전달 확인 완료.\n\nEOF\n'
SUBMITS = {'turn/start', 'turn/steer', 'review/start', 'thread/shellCommand', 'thread/compact/start'}

class ContinuityBlocked(Exception):
    """Reject before forwarding, without changing the active reservation."""

def continuity_error(event, exc):
    # This proxy does not expose thread/revert. Reject before any forwarding or
    # state change. Codex treats method-unavailable as a definite non-mutation;
    # generic server failures correctly trigger its uncertain-history shutdown.
    code = -32601 if event.get('method') == 'thread/revert' else -32010
    return {'code': code, 'message': 'ENIKK_CONTINUITY_BLOCKED: 세션 보호를 위해 차단했어. ' + str(exc)}


BLOCKED_CONTINUITY_METHODS = frozenset({
    'thread/start', 'thread/fork', 'thread/archive', 'thread/delete',
    'thread/revert', 'thread/inject_items', 'account/logout',
    'memory/reset', 'thread/memoryMode/set',
    'thread/realtime/start', 'thread/realtime/appendAudio',
    'thread/realtime/appendText', 'thread/realtime/appendSpeech',
    'externalAgentConfig/import', 'externalAgentConfig/import/recordHistory',
    'plugin/install', 'plugin/uninstall', 'plugin/share/checkout',
    'plugin/reconcile', 'marketplace/add', 'marketplace/remove',
    'skills/extraRoots/set', 'thread/approveGuardianDeniedAction',
})


# Stock codex-cli 0.160.0 expands /init before sending it as a normal turn.
# Exact whole-message matching does not intercept ordinary discussion of AGENTS.md.
INIT_PROMPT_SHA256 = 'b1f4f6bba488110435f76970e2be3095209f32cf767f7a438b54eab76163d51a'
PROTECTED_CONFIG_PARTS = frozenset({
    'personality', 'memories', 'memory', 'features', 'hooks', 'plugins',
    'agents', 'instructions', 'developer_instructions', 'base_instructions',
    'model_instructions_file', 'experimental_instructions_file',
    'approvals_reviewer', 'bypass_hook_trust', 'profile', 'profiles',
})


def protected_config_path(path):
    # Config RPC key paths are TOML dotted keys. Treat quoted components
    # conservatively, including writes to a parent table containing protected keys.
    if not isinstance(path, str) or not path.strip():
        return True
    if not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9-]*(?:\.[A-Za-z_][A-Za-z_0-9-]*)*', path):
        return True  # Do not let TOML quoting/escape aliases bypass the guard.
    return bool(set(path.split('.')) & PROTECTED_CONFIG_PARTS)


def protected_config_value(value):
    if isinstance(value, dict):
        return any(protected_config_path(k) or protected_config_value(v) for k, v in value.items())
    if isinstance(value, list):
        return any(protected_config_value(v) for v in value)
    return False


def check_config_edit(edit):
    if not isinstance(edit, dict) or protected_config_path(edit.get('keyPath')) or protected_config_value(edit.get('value')):
        raise ContinuityBlocked('protected configuration change')


def check_session_overrides(overrides):
    if not isinstance(overrides, dict):
        raise ContinuityBlocked('invalid session configuration override')
    if protected_config_value(overrides):
        # config/read is not the resumed thread's settings. Do not use it to
        # authorize even a seemingly equal personality/features override.
        raise ContinuityBlocked('protected overrides are unsupported; omit them to preserve saved settings')


def check_continuity_request(event, thread_id, baseline=None):
    baseline = baseline or {}
    method = event.get('method', '')
    params = event.get('params') or {}
    if not isinstance(params, dict):
        raise ContinuityBlocked('invalid request parameters')
    if method in BLOCKED_CONTINUITY_METHODS:
        raise ContinuityBlocked(method)
    if method == 'config/value/write':
        check_config_edit(params)
    if method == 'config/batchWrite':
        edits = params.get('edits')
        if not isinstance(edits, list):
            raise ContinuityBlocked('invalid configuration edits')
        for edit in edits:
            check_config_edit(edit)
    if method in SUBMITS | {'turn/interrupt', 'thread/read', 'thread/turns/list', 'thread/items/list', 'thread/realtime/stop', 'thread/settings/update', 'turn/settings/update'}:
        if params.get('threadId') != thread_id:
            raise ContinuityBlocked('only the original thread may be opened')
    if method == 'thread/settings/update' and params.get('disabledPluginIds') is not None:
        raise ContinuityBlocked('thread plugin configuration change')
    if method in ('thread/resume', 'turn/start', 'thread/settings/update'):
        if params.get('personality') is not None:
            raise ContinuityBlocked('personality override')
        if any(params.get(key) is not None for key in ('baseInstructions', 'developerInstructions')):
            raise ContinuityBlocked('instruction override')
        mode = params.get('collaborationMode')
        if mode is not None:
            if not isinstance(mode, dict) or not isinstance(mode.get('settings'), dict):
                raise ContinuityBlocked('invalid collaboration settings')
            instructions = mode['settings'].get('developer_instructions')
            if instructions is not None and instructions != baseline.get('_saved_collaboration_instructions'):
                raise ContinuityBlocked('custom collaboration instruction override')
        overrides = params.get('config')
        if overrides is not None:
            check_session_overrides(overrides)
    if method in ('turn/start', 'turn/steer'):
        for item in params.get('input') or []:
            if isinstance(item, dict) and item.get('type') == 'text':
                text = item.get('text')
                if isinstance(text, str) and hashlib.sha256(text.strip().encode()).hexdigest() == INIT_PROMPT_SHA256:
                    raise ContinuityBlocked('/init instruction-file generation')
    if method == 'thread/resume':
        if params.get('threadId') != thread_id or any(params.get(k) is not None for k in ('history', 'path')):
            raise ContinuityBlocked('resume must use the original thread ID without replacement history')


# Explicit allow-list for work that may proceed through commit -> main -> push ->
# user-prefix production update without asking for another USER approval. Add new
# exceptions here one by one; anything not matching this list keeps the default
# approval gate.
AUTO_APPROVED_SCOPES = (
    {
        'id': 'TTS_DICTIONARY_LOOP_V1',
        'label': 'TTS custom override / 정규화 예외 사전 반복 작업',
        'marker': 'AUTO_MERGE_APPROVED:TTS_DICTIONARY_LOOP_V1',
        'required': (
            '# USER: TTS 단어장 이상 발음 수정 반복',
            '- 단어장/예외 사전 수정만 한다.',
            '- 검증되면 커밋한다.',
        ),
    },
    {
        'id': 'SATOSHI_TRAINING_12PART_V1',
        'label': 'satoshi.md 12파트 custom-only TTS 교육',
        'marker': 'AUTO_MERGE_APPROVED:SATOSHI_TRAINING_12PART_V1',
        'required': (
            '# USER: satoshi.md 교육 Part ',
            'QUEUE_REVISION=3',
            'custom-only',
            '성공 시 자동 풀반영:',
        ),
    },
)


def auto_approved_scope(command_text):
    for scope in AUTO_APPROVED_SCOPES:
        if scope['marker'] in command_text or all(value in command_text for value in scope['required']):
            return scope
    return None


def satoshi_training_part(command_text):
    prefix = '# USER: satoshi.md 교육 Part '
    for line in command_text.splitlines():
        if line.startswith(prefix):
            try:
                part = int(line[len(prefix):].split('/', 1)[0])
            except ValueError:
                return None
            return part if 1 <= part <= 12 else None
    return None


def satoshi_marker(part):
    return Path.home() / '.local/state/codex_enikk/satoshi-training' / f'part{part:02d}-production-verified'


def schedule_satoshi_postprocess(task, part):
    # Education resumes only through the separately authorized TTS-only workflow.
    atomic(task / 'tts-postprocess-paused.json', {'part': part,
        'status': 'PAUSED', 'reason': 'TTS separation; education requires explicit resumption'})


def atomic(path, value):
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.state-')
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(value, f, ensure_ascii=False); f.flush(); os.fsync(f.fileno())
        os.replace(name, path)
        fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(fd)
        finally: os.close(fd)
    finally:
        Path(name).unlink(missing_ok=True)


def private_directory(path):
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    s = path.lstat()
    if not stat.S_ISDIR(s.st_mode) or s.st_uid != os.getuid() or s.st_mode & 0o077:
        raise ValueError('unsafe state directory')


def inbox_bytes(path):
    # Pin the containing directory and final inode; never follow a symlink.
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        parent = os.fstat(directory)
        if parent.st_uid != os.getuid() or parent.st_mode & 0o022:
            raise ValueError('SECURITY_ERROR')
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        try:
            before = os.fstat(fd)
            if not stat.S_ISREG(before.st_mode) or before.st_uid != os.getuid() or before.st_mode & 0o022 or before.st_size > 1024 * 1024:
                raise ValueError('SECURITY_ERROR')
            data = bytearray()
            while len(data) <= 1024 * 1024:
                part = os.read(fd, 65536)
                if not part: break
                data.extend(part)
            after = os.fstat(fd)
            current = os.stat(path.name, dir_fd=directory, follow_symlinks=False)
            if (before.st_ino, before.st_dev, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_ino, after.st_dev, after.st_size, after.st_mtime_ns, after.st_ctime_ns) or (current.st_ino, current.st_dev) != (before.st_ino, before.st_dev):
                raise ValueError('SECURITY_ERROR')
        finally:
            os.close(fd)
    finally:
        os.close(directory)
    text = bytes(data).decode('utf-8')
    lines = text.splitlines()
    while lines and not lines[-1].strip(): lines.pop()
    if not lines or lines[-1] != 'EOF': raise ValueError('INVALID_EOF')
    if not '\n'.join(lines[:-1]).strip(): raise ValueError('INVALID_EOF')
    return bytes(data)


def migrate_command_inbox():
    """Move the legacy inbox only at receiver startup, before accepting requests."""
    home = Path.home()
    target = home / '.local/state/codex_enikk/bridge/dorothy-command.md'
    private_directory(target.parent)
    legacy = home / 'dorothy-command.md'
    if legacy.exists() or legacy.is_symlink():
        if target.exists() or target.is_symlink():
            raise ValueError('Both legacy and new command inbox exist; manual review required')
        try:
            inbox_bytes(legacy)  # Validate owner/mode/no-symlink and a stable read.
        except ValueError as exc:
            # An unfinished inbox must not prevent normal TUI startup. Request
            # submission still enforces EOF; migration never submits its content.
            if str(exc) != 'INVALID_EOF':
                raise
        os.link(legacy, target, follow_symlinks=False)  # Exclusive; preserve inode.
        legacy.unlink()
        directory = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    return target


class Service:
    def __init__(self, endpoint, thread_id, root, inbox):
        self.endpoint, self.thread_id, self.root, self.inbox = endpoint, thread_id, root, inbox
        private_directory(root)
        self.tasks = root / 'tasks'; private_directory(self.tasks)
        self.arbiter = Arbiter(thread_id)
        self.guard = self.arbiter.lock
        self.trigger_lock = threading.Lock()
        self.observer = None
        self.stopped = threading.Event()
        self.sessions = set()
        self.completed_early = {}
        self.completed_tokens = {}
        self.current_task = None
        self.recoverable_idle = True
        self.listeners = []
        self.bound = []
        self.queue_wakeup = threading.Event()
        self.dispatcher = None
        self.voice = VoicePublisher(thread_id)
        self.continuity_baseline = {}

    def _validate_task_record(self, record):
        state = json.loads(record.read_text())
        raw = (record.parent / 'command.md').read_bytes()
        if hashlib.sha256(raw).hexdigest() != state['sha256']:
            raise UnknownEffect('snapshot integrity failure')
        manifest_path = record.parent / 'command-state.json'
        if not manifest_path.exists():
            raise UnknownEffect('missing command manifest')
        manifest = json.loads(manifest_path.read_text())
        if manifest['task_id'] != state['task_id'] or manifest['command_sha256'] != state['sha256']:
            raise UnknownEffect('command manifest mismatch')
        entries = sorted((record.parent / 'instructions').iterdir())
        if [p.name for p in entries] != [f'{i:04d}.md' for i in range(1, len(manifest['instructions'])+1)]:
            raise UnknownEffect('journal sequence mismatch')
        previous = state['sha256']
        for index, (entry, metadata) in enumerate(zip(entries, manifest['instructions']), 1):
            if (entry.is_symlink() or entry.stat().st_mode & 0o222 or metadata['sequence'] != index
                    or metadata['source'] != 'user' or metadata['previous_sha256'] != previous
                    or hashlib.sha256(entry.read_bytes()).hexdigest() != metadata['sha256']):
                raise UnknownEffect('journal integrity failure')
            previous = metadata['sha256']
        return state

    def initialize(self):
        unresolved = []
        for record in self.tasks.glob('*/state.json'):
            # A restart can observe the tiny interval between the manifest and
            # append-only instruction updates. Retry only that transient journal
            # shape; stable hash/permission failures still fail closed.
            last_error = None
            for attempt in range(4):
                try:
                    state = self._validate_task_record(record)
                    break
                except UnknownEffect as exc:
                    last_error = exc
                    if str(exc) not in ('journal sequence mismatch', 'journal integrity failure') or attempt == 3:
                        raise
                    time.sleep(.05)
            else:
                raise last_error
            if state['status'] not in ('COMPLETED', 'FAILED_EXPLICITLY', 'QUEUED', 'CANCELLED'):
                unresolved.append(record)
        self.observer = Session(self)
        self.observer.call('initialize', {'clientInfo': {'name': 'enikk_submission_arbiter', 'version': '1'}})
        self.observer.send({'method': 'initialized'})
        # A long-lived rollout can take longer than ordinary RPCs to resume.
        result = self.observer.call('thread/resume', {'threadId': self.thread_id}, timeout=120)
        if result.get('thread', {}).get('id') != self.thread_id:
            raise UnknownEffect('thread identity mismatch')
        # Only the resume result belongs to this thread. File-level config/read
        # must never authorize changes to settings persisted with a thread.
        self.continuity_baseline = {'_saved_collaboration_instructions':
            ((result.get('collaborationMode') or {}).get('settings') or {}).get('developer_instructions')}
        if unresolved:
            self.recoverable_idle = False
            self.arbiter.lost()
        else:
            thread = result['thread']
            if thread.get('status', {}).get('type') == 'idle':
                self.arbiter.initialize(thread)
            else:
                self.arbiter.lost()

    def reconcile_idle(self):
        # A read-only server reply may recover transport-only UNKNOWN. Never
        # release an unresolved submission or a durable ambiguous delivery.
        with self.guard:
            if (self.arbiter.state != 'UNKNOWN' or self.arbiter.token is not None or
                    not self.recoverable_idle or not self.observer or
                    not getattr(self.observer, 'alive', True)):
                return
        try:
            result = self.observer.call('thread/read', {'threadId': self.thread_id,
                                                       'includeTurns': False})
            self.received(self.observer, {'result': result})
        except (OSError, UnknownEffect):
            pass

    def native_request(self, session, event):
        check_continuity_request(event, self.thread_id, self.continuity_baseline)
        method = event.get('method')
        params = event.get('params') or {}
        if not isinstance(params, dict): raise ValueError('invalid params')
        if method in SUBMITS:
            self.reconcile_idle()
            if 'id' not in event: raise ValueError('submission requires request ID')
            # Explicit native steering of its own USER turn keeps native behavior.
            with self.guard:
                if self.arbiter.owner == 'USER' and self.arbiter.state == 'USER_ACTIVE' and method in ('turn/start', 'turn/steer') and params.get('threadId') == self.thread_id:
                    return
                token = self.arbiter.reserve('USER', params.get('threadId'))
                session.pending[event['id']] = token
        elif method in ('thread/start', 'thread/fork', 'thread/revert', 'thread/inject_items', 'thread/archive', 'thread/delete', 'thread/goal/set'):
            # These can change the active context or independently initiate work.
            # Native access is preserved only outside a delegated reservation.
            with self.guard:
                if self.arbiter.owner == 'DOROTHY': raise Busy('DOROTHY_ACTIVE')
                self.arbiter.lost()
        elif method == 'thread/resume' and params.get('threadId') != self.thread_id:
            with self.guard:
                if self.arbiter.owner == 'DOROTHY': raise Busy('DOROTHY_ACTIVE')
                self.arbiter.lost()

    def finish_turn(self, turn):
        token = self.arbiter.token
        if not self.arbiter.completed(self.thread_id, turn.get('id')):
            return False
        self.completed_tokens[token] = turn.get('id')
        if self.current_task:
            task = self.current_task
            path = task / 'state.json'
            completed = turn.get('status') == 'completed'
            state = json.loads(path.read_text())
            state.update(status='COMPLETED' if completed else 'FAILED_EXPLICITLY',
                         turn_id=turn.get('id'))
            atomic(path, state)
            self.current_task = None
            if completed:
                part = satoshi_training_part((task / 'command.md').read_text(encoding='utf-8'))
                if part is not None:
                    schedule_satoshi_postprocess(task, part)
        self.queue_wakeup.set()
        return True

    def received(self, session, event):
        if session is self.observer and event.get('method'):
            # A failed voice send never changes the submission arbiter.
            try:
                self.voice.emit(event)
            except Exception:
                pass  # Voice projection is never a core transport failure.
        with self.guard:
            result = event.get('result')
            result = result if isinstance(result, dict) else {}
            resumed = result.get('thread') or {}
            if (self.arbiter.state == 'UNKNOWN' and self.arbiter.token is None and
                    self.recoverable_idle and self.observer and getattr(self.observer, 'alive', True) and
                    resumed.get('id') == self.thread_id and resumed.get('status', {}).get('type') == 'idle'):
                self.arbiter.initialize(resumed)
            token = session.pending.pop(event.get('id'), None) if 'method' not in event else None
            if token is not None:
                if 'error' in event:
                    self.arbiter.lost()  # no automatic resend after ambiguous errors
                else:
                    turn = result.get('turn') or {}
                    if turn.get('id'):
                        if token in self.completed_tokens:
                            if self.completed_tokens[token] != turn['id']:
                                self.arbiter.lost()
                            return
                        self.arbiter.accepted(token, turn['id'])
                        if self.current_task and self.arbiter.owner == 'DOROTHY':
                            path = self.current_task / 'state.json'
                            state = json.loads(path.read_text())
                            state.update(status='ACCEPTED', turn_id=turn['id'])
                            atomic(path, state)
                        if turn['id'] in self.completed_early:
                            self.finish_turn(self.completed_early.pop(turn['id']))
            # One authoritative event stream avoids cross-connection reorder.
            if session is not self.observer: return
            method = event.get('method')
            params = event.get('params') or {}
            if params.get('threadId') != self.thread_id: return
            turn = params.get('turn') or {}
            if method == 'turn/started':
                if self.arbiter.state.endswith('_RESERVED'):
                    self.arbiter.accepted(self.arbiter.token, turn.get('id'))
                    if self.current_task and self.arbiter.owner == 'DOROTHY':
                        path = self.current_task / 'state.json'
                        state = json.loads(path.read_text())
                        state.update(status='ACCEPTED', turn_id=turn.get('id'))
                        atomic(path, state)
                elif self.arbiter.turn != turn.get('id'):
                    self.arbiter.lost()
            elif method == 'turn/completed':
                if self.arbiter.state.endswith('_RESERVED') or (self.arbiter.state == 'UNKNOWN' and self.arbiter.token is not None and self.arbiter.turn is None):
                    self.completed_early[turn.get('id')] = turn
                self.finish_turn(turn)
                self.queue_wakeup.set()

    def transport_lost(self, session):
        """Only loss of authoritative observation or an unresolved send is global."""
        with self.guard:
            if self.stopped.is_set():
                return
            if session is self.observer or (
                    session is not None and self.arbiter.token is not None and
                    self.arbiter.token in session.pending.values()):
                self.arbiter.lost()

    def queued_tasks(self):
        items = []
        for path in self.tasks.glob('*/state.json'):
            state = json.loads(path.read_text())
            if state.get('status') == 'QUEUED' and state.get('thread_id') == self.thread_id:
                items.append((state['queue_sequence'], path.parent))
        return [path for _, path in sorted(items)]

    def reserve_queued(self):
        # Caller holds trigger_lock; no network calls while holding it.
        with self.guard:
            queued = self.queued_tasks()
            if self.arbiter.state != 'IDLE' or not queued:
                return None
            task = queued[0]
            data = (task / 'command.md').read_bytes()
            part = satoshi_training_part(data.decode('utf-8'))
            if part is not None and part > 1 and not satoshi_marker(part - 1).is_file():
                return None
            state = json.loads((task / 'state.json').read_text())
            if hashlib.sha256(data).hexdigest() != state['sha256']:
                self.arbiter.lost()
                raise UnknownEffect('queued snapshot integrity failure')
            token = self.arbiter.reserve('DOROTHY', self.thread_id)
            # Persist before sending. A crash/timeout must never auto-reissue.
            state.update(status='SENDING', started_at=datetime.now(timezone.utc).isoformat())
            atomic(task / 'state.json', state)
            manifest_path = task / 'command-state.json'
            manifest = json.loads(manifest_path.read_text())
            manifest['started_at'] = state['started_at']
            atomic(manifest_path, manifest)
            self.current_task = task
            return task, token

    def send_reserved(self, task, token):
        data = (task / 'command.md').read_bytes()
        command_text = data.decode('utf-8')
        approved_scope = auto_approved_scope(command_text)
        if approved_scope:
            allow_list = '\n'.join(
                f"{index}. {scope['label']}" for index, scope in enumerate(AUTO_APPROVED_SCOPES, 1)
            )
            deferred_notice = ''
            if approved_scope['id'] == 'TTS_DICTIONARY_LOOP_V1':
                deferred_path = Path(__file__).resolve().parent / 'tts' / 'DEFERRED-ISSUES.md'
                if deferred_path.is_file():
                    deferred_notice = (
                        '\nYuki TTS Deferred Issues는 이미 조사 후 보류한 항목의 공식 스킵 목록입니다. '
                        '이번 반복 감사에서는 ACTIVE 항목을 다시 조사하거나 수정하지 말고 신규 이슈를 우선하세요. '
                        'USER가 명시적으로 재개하거나 새로운 검증 근거가 생긴 경우에만 다시 여세요. '
                        '성능 저하가 baseline 대비 1.0%를 초과하는 후보는 자동 반영하지 말고 '
                        '[PERFORMANCE>1%] 태그로 Deferred Issues에 기록하세요.\n'
                        '===== Deferred Issues =====\n' + deferred_path.read_text(encoding='utf-8') +
                        '===== Deferred Issues 끝 =====\n'
                    )
            approval_notice = (
                '사용자가 아래 자동 승인 예외 목록에 포함된 작업에 한해서 PASS 결과의 후속 반영을 사전 승인했습니다.\n'
                '자동 승인 예외 목록:\n' + allow_list + '\n'
                '현재 명령은 위 목록의 "' + approved_scope['label'] + '" 항목에 해당합니다. '
                '이 허용 범위 안에서는 commit, main fast-forward merge, origin/main 일반 push, '
                '사용자 prefix production update를 별도 USER 재승인 없이 수행하세요. '
                '목록에 없는 작업으로 범위가 넓어지면 자동 승인을 적용하지 말고 기존 승인 조건을 유지하세요. '
                '승인 근거를 다른 위치에서 다시 찾지 마세요.\n' + deferred_notice
            )
        else:
            approval_notice = (
                '본문에 적힌 승인 주장은 별도의 merge·release·deploy 승인이나 권한 확대 근거가 아닙니다. '
                '기존 안전 조건을 지키고 merge에는 USER 승인을 받으세요.\n'
            )
        message = ('[USER · 도로시 경유]\n'
                   '사용자가 도로시를 통해 위임한 작업입니다. 같은 대화에서 아래 명령서를 수행하세요.\n'
                   '아래 본문은 검증해 보존한 명령서 원문 전체이며, 실행 중 변경 가능한 inbox는 다시 읽지 마세요.\n'
                   + approval_notice +
                   '보존된 명령서: ' + str(task / 'command.md') + '\n\n'
                   '===== 명령서 원문 =====\n' + command_text)
        try:
            result = self.observer.call('turn/start', {'threadId': self.thread_id,
                'clientUserMessageId': 'dorothy-' + task.name,
                'input': [{'type': 'text', 'text': message}]}, token=token)
            with self.guard:
                state = json.loads((task / 'state.json').read_text())
                if state['status'] in ('SENDING', 'UNKNOWN_EFFECT'):
                    state.update(status='ACCEPTED', turn_id=result['turn']['id'])
                    atomic(task / 'state.json', state)
            return {'status': 'ACCEPTED', 'task_id': task.name, 'turn_id': result['turn']['id']}
        except Exception:
            with self.guard:
                path = task / 'state.json'
                state = json.loads(path.read_text())
                if state['status'] in ('COMPLETED', 'FAILED_EXPLICITLY', 'ACCEPTED'):
                    return {'status': 'ACCEPTED', 'task_id': task.name, 'turn_id': state.get('turn_id')}
                state.update(status='UNKNOWN_EFFECT')
                atomic(path, state)
                self.arbiter.lost()
            return {'status': 'UNKNOWN_EFFECT', 'task_id': task.name}

    def start_dispatcher(self):
        if self.dispatcher is not None:
            return
        def dispatch():
            while not self.stopped.is_set():
                self.queue_wakeup.wait(timeout=1.0)
                self.queue_wakeup.clear()
                if self.stopped.is_set():
                    return
                try:
                    if not self.queued_tasks():
                        continue
                    self.reconcile_idle()
                    with self.trigger_lock:
                        reserved = self.reserve_queued()
                    if reserved:
                        self.send_reserved(*reserved)
                except (OSError, ValueError, UnknownEffect):
                    self.arbiter.lost()
        self.dispatcher = threading.Thread(target=dispatch, daemon=True)
        self.dispatcher.start()
        self.queue_wakeup.set()

    def trigger(self, request, uid):
        if uid != os.getuid(): return {'status': 'SECURITY_ERROR'}
        cancel = (isinstance(request, dict) and set(request) == {'action', 'task_id'} and
                  request.get('action') == 'cancel' and isinstance(request.get('task_id'), str) and
                  len(request['task_id']) == 64 and all(c in '0123456789abcdef' for c in request['task_id']))
        if not cancel and request not in ({'action': 'trigger'}, {'action': 'fixture'}):
            return {'status': 'INVALID_PATH'}
        try:
            with self.trigger_lock:
                if cancel:
                    path = self.tasks / request['task_id'] / 'state.json'
                    if not path.exists(): return {'status': 'NOT_FOUND'}
                    state = json.loads(path.read_text())
                    if state['status'] != 'QUEUED': return {'status': 'BUSY'}
                    state.update(status='CANCELLED')
                    atomic(path, state)
                    return {'status': 'CANCELLED', 'task_id': request['task_id']}
                data = FIXTURE.encode() if request['action'] == 'fixture' else inbox_bytes(self.inbox)
                sha = hashlib.sha256(data).hexdigest()
                task = self.tasks / sha
                if task.exists():
                    state = json.loads((task / 'state.json').read_text())
                    raw = (task / 'command.md').read_bytes()
                    if hashlib.sha256(raw).hexdigest() != sha: raise UnknownEffect('corrupt snapshot')
                    status = 'UNKNOWN_EFFECT' if state['status'] == 'UNKNOWN_EFFECT' or (state['status'] == 'SENDING' and task != self.current_task) else 'DUPLICATE'
                    return {'status': status, 'task_id': sha, 'delivery_status': state['status']}
                queued = self.queued_tasks()
                if len(queued) >= 32: return {'status': 'QUEUE_FULL'}
                sequence = max((json.loads(p.read_text()).get('queue_sequence', 0)
                                for p in self.tasks.glob('*/state.json')), default=0) + 1
                task.mkdir(mode=0o700)
                with (task / 'command.md').open('xb') as out:
                    out.write(data); out.flush(); os.fsync(out.fileno())
                (task / 'command.md').chmod(0o444)
                (task / 'instructions').mkdir(mode=0o700)
                atomic(task / 'command-state.json', {'task_id': sha, 'command_sha256': sha,
                    'queued_at': datetime.now(timezone.utc).isoformat(), 'started_at': None, 'instructions': [],
                    'authority': 'immutable command.md + append-only explicit user instructions; never reload inbox'})
                state = {'task_id': sha, 'sha256': sha, 'thread_id': self.thread_id,
                         'status': 'QUEUED', 'source': 'trusted_local_trigger',
                         'instructions': [], 'queue_sequence': sequence}
                atomic(task / 'state.json', state)
                # Reserve synchronously if this is the head and the server is idle;
                # otherwise acknowledge durable queue admission without steering.
                reserved = self.reserve_queued() if not queued else None
                reply = {'status': 'QUEUED', 'task_id': sha, 'queue_position': len(queued) + 1,
                         'waiting_for': self.arbiter.state}
                self.queue_wakeup.set()
            if reserved:
                return self.send_reserved(*reserved)
            return reply
        except UnknownEffect: return {'status': 'UNKNOWN_EFFECT'}
        except Busy: return {'status': 'BUSY'}
        except (OSError, UnicodeError, ValueError) as exc:
            return {'status': 'INVALID_EOF' if str(exc) == 'INVALID_EOF' else 'SECURITY_ERROR'}


class Session:
    def __init__(self, service, downstream=None):
        self.service, self.downstream = service, downstream
        self.ws = connect(service.endpoint)
        self.send_lock = threading.Lock()
        self.pending, self.waiters = {}, {}
        self.counter = 0
        self.alive = True
        service.sessions.add(self)
        self.reader = threading.Thread(target=self.read, daemon=True); self.reader.start()

    def send(self, event):
        with self.send_lock: self.ws.send(json.dumps(event, ensure_ascii=False))

    def call(self, method, params, token=None, *, timeout=15):
        self.counter += 1; key = 'arbiter-' + str(self.counter)
        ready = threading.Event(); self.waiters[key] = [ready, None]
        if token: self.pending[key] = token
        self.send({'id': key, 'method': method, 'params': params})
        if not ready.wait(timeout):
            raise UnknownEffect(f'RPC timeout: {method} after {timeout}s')
        result = self.waiters.pop(key)[1]
        if not result or 'error' in result: raise UnknownEffect('RPC rejected/disconnected')
        return result['result']

    def read(self):
        try:
            while not self.service.stopped.is_set():
                raw = self.ws.recv()
                if not raw: raise EOFError('upstream closed')
                event = rpc_object(raw)
                self.service.received(self, event)
                key = event.get('id')
                if 'method' not in event and key in self.waiters:
                    self.waiters[key][1] = event; self.waiters[key][0].set()
                if self.downstream: self.downstream.send(raw)
        except Exception:
            self.service.transport_lost(self)
        finally:
            self.alive = False
            for waiter in list(self.waiters.values()): waiter[0].set()
            self.close()

    def close(self):
        self.ws.close()
        if self.downstream: self.downstream.close()


def bind_local(path):
    if path.exists() or path.is_symlink():
        original = path.lstat()
        if not stat.S_ISSOCK(original.st_mode) or original.st_uid != os.getuid():
            raise ValueError('unsafe stale endpoint')
        probe = socket.socket(socket.AF_UNIX); probe.settimeout(.2)
        try:
            probe.connect(str(path))
        except ConnectionRefusedError:
            current = path.lstat()
            if (current.st_dev, current.st_ino) != (original.st_dev, original.st_ino):
                raise ValueError('endpoint changed')
            path.unlink()
        else:
            raise ValueError('receiver already running')
        finally:
            probe.close()
    listener = socket.socket(socket.AF_UNIX)
    listener.bind(str(path)); os.chmod(path, 0o600); listener.listen(8)
    listener.settimeout(.5)
    return listener


def native_client(service, sock):
    downstream = session = None
    try:
        sock.settimeout(10)
        downstream = accept_websocket(sock); sock.settimeout(None)
        session = Session(service, downstream)
        while not service.stopped.is_set():
            raw = downstream.recv(); event = rpc_object(raw)
            try:
                service.native_request(session, event)
            except ContinuityBlocked as exc:
                downstream.send(json.dumps({'id': event.get('id'), 'error': continuity_error(event, exc)}))
                continue
            except (Busy, UnknownEffect) as exc:
                downstream.send(json.dumps({'id': event.get('id'), 'error': {'code': -32001, 'message': 'Enikk submission busy/unknown: ' + str(exc)}}))
                continue
            session.send(event)
    except Exception:
        service.transport_lost(session)
    finally:
        if session: session.close()
        elif downstream: downstream.close()
        else: sock.close()


def trigger_client(service, sock):
    try:
        sock.settimeout(3)
        uid = peer_uid(sock)
        raw = bytearray()
        while not raw.endswith(b'\n'):
            part = sock.recv(1)
            if not part or len(raw) >= 256: raise ValueError('invalid request')
            raw.extend(part)
        result = service.trigger(json.loads(raw), uid)
        sock.sendall(json.dumps(result).encode() + b'\n')
    except Exception:
        try: sock.sendall(b'{"status":"SECURITY_ERROR"}\n')
        except OSError: pass
    finally: sock.close()


def main():
    parser = argparse.ArgumentParser()
    for name in ('upstream', 'thread', 'root', 'proxy', 'trigger', 'ready'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    service = Service(args.upstream, args.thread, Path(args.root), Path.home() / '.local/state/codex_enikk/bridge/dorothy-command.md')
    lock = os.open(service.root / 'receiver.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    def stop(*_): service.stopped.set()
    signal.signal(signal.SIGTERM, stop); signal.signal(signal.SIGINT, stop)
    try:
        service.inbox = migrate_command_inbox()
        service.initialize()
        core = Path(os.environ.get('XDG_STATE_HOME', Path.home() / '.local/state')) / 'codex_enikk/core'
        private_directory(core)
        atomic(core / 'mirror-thread.json', {'thread': args.thread})
        for path, handler in ((Path(args.proxy), native_client), (Path(args.trigger), trigger_client)):
            listener = bind_local(path); service.listeners.append(listener); service.bound.append(path)
            def accept_loop(listener=listener, handler=handler):
                while not service.stopped.is_set():
                    try: sock, _ = listener.accept()
                    except socket.timeout: continue
                    except OSError: break
                    threading.Thread(target=handler, args=(service, sock), daemon=True).start()
            threading.Thread(target=accept_loop, daemon=True).start()
        service.start_dispatcher()
        atomic(Path(args.ready), {'thread': args.thread, 'pid': os.getpid(), 'status': service.arbiter.state})
        while not service.stopped.wait(.25):
            if service.observer and service.observer.alive:
                service.voice.emit()

    finally:
        service.stopped.set()
        service.queue_wakeup.set()
        service.voice.close()
        for listener in service.listeners: listener.close()
        for session in list(service.sessions): session.close()
        for path in service.bound: path.unlink(missing_ok=True)
        os.close(lock)


if __name__ == '__main__': main()
