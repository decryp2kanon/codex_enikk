"""Yuki-specific text exceptions; independent of NVIDIA package implementation.

Order: path descriptions (engine, once) -> narrow protection/names/units ->
normalization callback -> checked restoration. No external runtime imports.
Each exception's reproducer lives in test_text_normalization.py or PathTests
in test_tts_delivery.py. General grammar, Korean G2P and voice controls are absent.
"""
import re

# User-defined names, not a general pronunciation dictionary.
NAMES = {'Yuki': '유키', 'Enikk': '에닉', 'Sugarchain': '슈가체인'}


def proper_names(text):
    return re.sub(r'(?<![A-Za-z])(?:Yuki|Enikk|Sugarchain)(?![A-Za-z])',
                  lambda m: NAMES[m.group()], text, flags=0)


# USER-confirmed narrow readings and protections. Case matters: GB != Gb.
# Other numeric/SI rules, ordinary Korean and mathematical operators are left unchanged.
GROUPED_INTEGER = re.compile(r'(?<![A-Za-z0-9_.,])[1-9]\d{0,2}(?:,\d{3})+(?!\d|,\d)')
# Reproduced 46개/61개/282개/284개/1,024개 were split into smaller counts.
# Keep correct native readings for other two-digit counts; use public cardinal TN.
LARGE_ITEM_COUNT = re.compile(r'(?<![\w.,+/@-])(46|48|61|[1-9]\d{2,})개(?![A-Za-z0-9_./])')
# Narrow custom readings for the verified units100 corpus. Case is significant:
# b means bit and B means byte. Longest alternatives prevent suffix matches.
KNOWN_UNITS = {
    'ms/op': '밀리세컨드 퍼 오퍼레이션',
    'block/day': '블록 퍼 데이', 'block/min': '블록 퍼 분', 'block/h': '블록 퍼 시간',
    'block/s': '블록 퍼 세컨드', 'request/s': '리퀘스트 퍼 세컨드',
    'connection/s': '커넥션 퍼 세컨드', 'process/s': '프로세스 퍼 세컨드',
    'session/s': '세션 퍼 세컨드', 'packet/s': '패킷 퍼 세컨드',
    'thread/s': '스레드 퍼 세컨드', 'event/s': '이벤트 퍼 세컨드',
    'query/s': '쿼리 퍼 세컨드', 'retry/s': '리트라이 퍼 세컨드',
    'peer/min': '피어 퍼 분', 'peer/s': '피어 퍼 세컨드',
    'error/min': '에러 퍼 분', 'frame/s': '프레임 퍼 세컨드',
    'write/s': '라이트 퍼 세컨드', 'read/s': '리드 퍼 세컨드',
    'byte/s': '바이트 퍼 세컨드', 'hash/s': '해시 퍼 세컨드',
    'node/s': '노드 퍼 세컨드', 'task/s': '태스크 퍼 세컨드',
    'call/s': '콜 퍼 세컨드', 'fail/h': '페일 퍼 시간',
    'tx/min': '티엑스 퍼 분', 'tx/s': '티엑스 퍼 세컨드',
    'req/s': '알이큐 퍼 세컨드', 'msg/s': '메시지 퍼 세컨드',
    'job/s': '잡 퍼 세컨드', 'op/s': '오퍼레이션 퍼 세컨드',
    'km/h': '킬로미터 퍼 아워', 'm/s²': '미터 퍼 세컨드 제곱',
    'm/s': '미터 퍼 세컨드',
    'GB/day': '기가바이트 퍼 데이', 'TB/day': '테라바이트 퍼 데이',
    'GB/min': '기가바이트 퍼 분', 'MB/min': '메가바이트 퍼 분',
    'GB/s': '기가바이트 퍼 세컨드', 'MB/s': '메가바이트 퍼 세컨드',
    'kB/s': '킬로바이트 퍼 세컨드', 'kH/s': '킬로해시 퍼 세컨드',
    'TH/s': '테라해시 퍼 세컨드', 'GH/s': '기가해시 퍼 세컨드',
    'MH/s': '메가해시 퍼 세컨드', 'Mbps': '메가비트 퍼 세컨드',
    'Gbps': '기가비트 퍼 세컨드', 'kb/s': '킬로비트 퍼 세컨드',
    'fps': '에프피에스', 'IOPS': '아이옵스', 'GiB': '기비바이트',
    'GHz': '기가헤르츠', 'MHz': '메가헤르츠', 'kHz': '킬로헤르츠',
    'µs': '마이크로세컨드', 'ns': '나노세컨드', 'sec': '세컨드',
    'min': '분', 'hr': '아워', 'Hz': '헤르츠', 'km/h': '킬로미터 퍼 아워',
    'GB': '기가바이트', 'MB': '메가바이트', 'TB': '테라바이트',
    'kB': '킬로바이트', 'KB': '킬로바이트', 'ms': '밀리세컨드',
    'tx': '티엑스', 'peer': '피어', 'node': '노드', 'req': '알이큐',
    'request': '리퀘스트', 'msg': '메시지', 'packet': '패킷', 'event': '이벤트',
    'job': '잡', 'task': '태스크', 'thread': '스레드', 'process': '프로세스',
    'frame': '프레임', 'block': '블록', 'hash': '해시', 'byte': '바이트',
    'bit': '비트', 'call': '콜', 'query': '쿼리', 'write': '라이트',
    'read': '리드', 'connection': '커넥션', 'session': '세션', 'retry': '리트라이',
    'error': '에러', 'fail': '페일', 'core': '코어', 'GHz': '기가헤르츠',
    's': '초', 'h': '시간', 'V': '볼트', 'A': '암페어', 'W': '와트',
    '°C': '도씨', '%': '퍼센트',
}
# Read one maximal compact unit token, then accept it only by exact registry
# lookup. This keeps candidate screening independent of registry size.
NUMBER_UNIT = re.compile(
    r'(?<![A-Za-z0-9_.,/@:=+-])(?P<number>-?(?:\d{1,3}(?:,\d{3})+|\d+)'
    r'(?:\.\d+)?)(?P<space>\s*)(?P<unit>[A-Za-zµ°²/%]+)'
    r'(?![A-Za-z0-9_/@]|\.[A-Za-z0-9_])')
NUMBER_OR_GROUPED_INTEGER = re.compile(
    r'(?:(?<![A-Za-z0-9_.,/@:=+-])(?P<number_unit>'
    r'(?P<unit_number>-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)'
    r'(?P<unit_space>\s*)(?P<unit_token>[A-Za-zµ°²/%]+))'
    r'(?![A-Za-z0-9_/@]|\.[A-Za-z0-9_])'
    r'|(?<![A-Za-z0-9_.,+/@-])(?P<grouped_integer>'
    r'[1-9]\d{0,2}(?:,\d{3})+)(?!\d|,\d))')

_CARDINAL_DIGITS = '영일이삼사오육칠팔구'
_CARDINAL_SMALL = ('', '십', '백', '천')
_CARDINAL_LARGE = ('', '만', '억', '조')


def korean_cardinal(value):
    """Read a non-negative integer as Korean Sino-Korean cardinal numerals."""
    value = int(value)
    if value == 0:
        return '영'
    groups = []
    while value:
        groups.append(value % 10000)
        value //= 10000
    spoken = []
    for position, group in reversed(list(enumerate(groups))):
        if not group:
            continue
        part = []
        for place in range(3, -1, -1):
            digit = group // (10 ** place) % 10
            if digit:
                part.append((_CARDINAL_SMALL[place] if digit == 1 and place else
                             _CARDINAL_DIGITS[digit] + _CARDINAL_SMALL[place]))
        spoken.append(''.join(part) + (_CARDINAL_LARGE[position]
                                       if position < len(_CARDINAL_LARGE) else ''))
    return ''.join(spoken)


def korean_number(value):
    """Read integer/decimal input; decimal digits are spoken one by one."""
    value = value.replace(',', '')
    negative = value.startswith('-')
    if negative:
        value = value[1:]
    if '.' in value:
        integer, fraction = value.split('.', 1)
        spoken = korean_cardinal(integer) + ' 쩜 ' + ' '.join(
            _CARDINAL_DIGITS[int(digit)] for digit in fraction)
    else:
        spoken = korean_cardinal(value)
    return ('마이너스 ' if negative else '') + spoken
# Relative filename tokens and the known digit-bearing extension remain identifiers.
# Absolute filesystem paths have already gone through the separate path-description layer.
KNOWN_PROTECTED = re.compile(
    r'(?<![\w])일반(?![\w])'
    r'|(?<![\w/])(?=[A-Za-z0-9_.-]*\d)[A-Za-z0-9][A-Za-z0-9_.-]*\.(?:py|md|sh|json|txt|wav|mp3|log|toml|yaml|yml|cpp|rs|js|ts)(?![A-Za-z0-9_.])'
    r'|(?<![\w.])\.mp3(?![A-Za-z0-9_])')


# Reproduced in runtime log: "1시간 제한" -> "일 시간 제한".
# Native numeral for this one-hour duration only; exclude decimals, signs,
# identifiers and ordinal 제1시간 rather than overriding general number grammar.
# Runtime reproduction also includes attached 에만; do not match 에만큼.
SINGLE_HOUR = re.compile(r'(?<![\w.,+~\-/@:])1시간'
                         r'(?:(?![\w./])|(?=에만(?=\s|[!?,]|$|\.(?=\s|$))))')


# Runtime phrase "작은 일부터" means tasks, not the abbreviated weekday 일.
# Protect only this confirmed context.
WORK_NOUN_PHRASE = re.compile(r'(?<!\w)작은 일부터(?!\w)')

# Runtime duration "수 초가 더 걸렸어" became "수요일 초가 더 걸렸어".
# Protect only the reproduced few-seconds phrase with its subject particle.
FEW_SECONDS_SUBJECT = re.compile(r'(?<![\w/@-])수 초가(?!\w|\.[A-Za-z0-9_])')
SU_ITTOROK_PHRASE = re.compile(r'(?<![\w/@-])수 있도록(?!\w|\.[A-Za-z0-9_])')
# Observed model input: "단정할 수 없어" -> "단정할 수요일 없어".
# Only this confirmed inflection; leave weekdays and other 수 contexts unchanged.
SU_EOPSEO_PHRASE = re.compile(r'(?<![\w/@-])수 없어(?!\w|\.[A-Za-z0-9_])')
# Both reproduced in runtime: "설치할 수 있으므로", "섞일 수 있어".
SU_ISSEO_PHRASE = re.compile(r'(?<![\w/@-])수 (?:있으므로|있어)(?!\w|\.[A-Za-z0-9_])')
# Deep-audit fixtures reproduced weekday substitution in these exact forms.
AUDITED_NOUN_PHRASE = re.compile(
    r'(?<![\w/@-])(?:수 (?:있습니다|없어요|없어서|있는|있다)|일 하나를)'
    r'(?!\w|\.[A-Za-z0-9_])')
# Book-prose cases found in round 29: protect these dependent-noun
# readings to Wednesday. Keep only reproduced endings; do not protect bare 수.
LITERARY_SU_PHRASE = re.compile(
    r'(?<![\w/@-])수 (?:있을지|없는|없이|있었다)(?!\w|\.[A-Za-z0-9_])')
# In prose, this means several moves ahead (for example, in a board game).
SEVERAL_MOVES_AHEAD = re.compile(
    r'(?<![\w/@-])몇 수 앞을(?!\w|\.[A-Za-z0-9_])')
# Protect the numeral-duration phrase "일 년".
ONE_YEAR_DURATION = re.compile(
    r'(?<![\w/@-])일 년(?!\w|\.[A-Za-z0-9_])')
# Round-27 fixtures: inflected ability, throat/gold/work/day-count contexts.
# Protect complete confirmed spans; never replace bare weekday initials globally.
WEEKDAY_COLLISION_PHRASE = re.compile(
    r'(?<![\w/@-])(?:수 (?:없다|없으면|있어서|있어도|없지만|없습니다)'
    r'(?!\w|\.[A-Za-z0-9_])'
    r'|(?:목 (?:건강|안쪽)|금 (?:가격|한 돈)|일 (?:처리|하나|두 개)'
    r'|일수 계산|이번 월 말|분노의 화 관리|흙의 토 (?:분류|색상))'
    r'(?=$|[\s!?,]|\.(?![A-Za-z0-9_])|(?:에서|으로|부터|은|는|이|가|을|를|에|의|도)'
    r'(?=$|[\s!?,]|\.(?![A-Za-z0-9_]))))')
WEEKDAY_INITIAL_FILENAME = re.compile(
    r'(?<!\S)(?:월\.py|화\.txt|수\.md|목\.json|금\.wav|토\.sh|일\.log)'
    r'(?=$|\s|[,!?;]|\.(?=\s|$))')


# Explicit USER listening failures only; not a general English or letter dictionary.
HEARD_ERRORS = {'Python': '파이썬', 'CPU': '씨피유', 'TTS': '티티에스',
                'API': '에이피아이', 'GPU': '지피유', 'VRAM': '브이램',
                'km/h': '킬로미터 퍼 아워',
                # USER-reported failure; raw/1.25x Whisper small/base reproduced it.
                'branch': '브랜치'}
HEARD_TOKEN = re.compile(r'(?<![A-Za-z0-9_./@-])(?:Python|CPU|TTS|API|GPU|VRAM|km/h|'
                         r'branch과(?=\s+switch(?=[가-힣\s.,!?]|$))|branch(?!과[._/@-]))'
                         r'(?![A-Za-z0-9_/@-]|\.[A-Za-z0-9_])')


def heard_error_readings(text):
    def replace(match):
        if match.group() == 'branch과':
            # ``branch`` is read as 브랜치, which takes the coordinating 와.
            return '브랜치와'
        # Do not reinterpret tokens inside URL/email literals as prose words.
        left = re.search(r'\S*$', text[:match.start()]).group()
        right = re.match(r'\S*', text[match.end():]).group()
        token = left + match.group() + right
        if '://' in token or '@' in token:
            return match.group()
        return HEARD_ERRORS[match.group()]
    return HEARD_TOKEN.sub(replace, text)


def normalize_with_exceptions(text, normalize):
    """Protect reproduced errors, run public TN, restore only our own exact spans.

    Each transformed span is normalized once. Opaque markers never reach the GPU.
    The private-use markers are chosen outside the input and checked for loss or
    duplication rather than repairing arbitrary words in the final output.
    """
    if not text.strip():
        return text
    # Exact scalar measurement tokens are common input units and need no prose
    # protection pipeline. Keep this full-token fast path ahead of all generic
    # exceptions; embedded values still use the guarded combined scan below.
    scalar = NUMBER_UNIT.fullmatch(text)
    if scalar and scalar.group('unit') in KNOWN_UNITS:
        return (korean_number(scalar.group('number')) + ' ' +
                KNOWN_UNITS[scalar.group('unit')])
    text = proper_names(text)
    protected = {}
    available = (chr(i) for i in range(0xE000, 0xF900) if chr(i) not in text)

    def protect(value):
        token = next(available, None)
        if token is None:
            raise ValueError('too many protected normalization spans')
        protected[token] = value
        return token

    text = WORK_NOUN_PHRASE.sub(lambda match: protect(match.group()), text)
    text = FEW_SECONDS_SUBJECT.sub(lambda match: protect(match.group()), text)
    text = SU_ITTOROK_PHRASE.sub(lambda match: protect(match.group()), text)
    text = SU_EOPSEO_PHRASE.sub(lambda match: protect(match.group()), text)
    text = SU_ISSEO_PHRASE.sub(lambda match: protect(match.group()), text)
    text = AUDITED_NOUN_PHRASE.sub(lambda match: protect(match.group()), text)
    text = LITERARY_SU_PHRASE.sub(lambda match: protect(match.group()), text)
    text = SEVERAL_MOVES_AHEAD.sub(lambda match: protect(match.group()), text)
    text = ONE_YEAR_DURATION.sub(lambda match: protect(match.group()), text)
    text = WEEKDAY_INITIAL_FILENAME.sub(lambda match: protect(match.group()), text)
    text = WEEKDAY_COLLISION_PHRASE.sub(lambda match: protect(match.group()), text)
    text = SINGLE_HOUR.sub(lambda match: protect('한 시간'), text)
    text = KNOWN_PROTECTED.sub(lambda match: protect(match.group()), text)
    # One scan handles spoken number/unit forms and valid standalone thousands groups.
    def number_or_grouped(match):
        if match.group('grouped_integer') is not None:
            return match.group('grouped_integer').replace(',', '')
        unit_name = match.group('unit_token')
        if unit_name not in KNOWN_UNITS:
            if ',' in match.group('unit_number'):
                return (match.group('unit_number').replace(',', '') +
                        match.group('unit_space') + unit_name)
            return match.group()
        return korean_number(match.group('unit_number')) + ' ' + KNOWN_UNITS[unit_name]

    text = NUMBER_OR_GROUPED_INTEGER.sub(number_or_grouped, text)
    text = LARGE_ITEM_COUNT.sub(
        lambda match: protect(normalize(match.group(1)) + ' 개'), text)

    text = heard_error_readings(text)
    result = normalize(text)
    for token, value in protected.items():
        if result.count(token) != 1:
            raise RuntimeError('protected normalization span lost or duplicated')
        result = result.replace(token, value)
    return result


def normalize_paths(text):
    """TTS-only filesystem descriptions, before splitting or number conversion.

    Return explicit replacements as well as text; never mutate the source job.
    URLs and ordinary slash expressions cannot start a match.
    """
    extensions = {
        'py': '파이썬 파일', 'md': '마크다운 파일', 'sh': '셸 스크립트',
        'json': '제이슨 파일', 'txt': '텍스트 파일', 'wav': '웨이브 오디오 파일',
        'log': '로그 파일', 'toml': '톰엘 설정 파일', 'yaml': '야믈 설정 파일',
        'yml': '야믈 설정 파일', 'cpp': '씨 플러스 플러스 소스 파일',
        'cc': '씨 플러스 플러스 소스 파일', 'h': '헤더 파일', 'hpp': '헤더 파일',
        'rs': '러스트 소스 파일', 'js': '자바스크립트 파일', 'ts': '타입스크립트 파일',
    }
    names = {'yuki': '유키', 'engine': '엔진', 'enikk': '에닉', 'readme': '리드미',
             'install': '인스톨', 'license': '라이선스', 'changelog': '체인지로그',
             'makefile': '메이크파일', 'chatterbox': '채터박스', 'test': '테스트', 'output': '아웃풋',
             'approval': '승인', 'marker': '표시'}
    # Delimited paths may contain Korean filenames. Attached Korean particles
    # after a known extension are prose, not part of that filename.
    pattern = re.compile(
        r"(?<![\w/:.])(?P<path>`?(?:(?:/(?:home|tmp|usr|etc|var|opt)/|~/|\.\.?/)[^\s`\"'<>()[\]{}]+"
        r"|(?P<known_report>(?<![@-])report_v31\.1\.md(?![A-Za-z0-9_-]|\.[A-Za-z0-9_])))`?)"
        r"(?(known_report)(?:(?P<filename_particle>으로|에서|을|를|은|는|이|가|에|로|와|과|도)(?=\s|[.!?,]|$))?|)"
        r"(?:\s+(?:파일|경로)(?P<particle>에서|으로|을|를|은|는|이|가|에|로|(?(known_report)도|(?!)))?(?=\s|[.!?,]|$))?")
    records = []

    def replace(match):
        raw = match.group('path')
        path = raw.strip('`')
        tail = ''
        while path and path[-1] in '.,!?:;':
            tail = path[-1] + tail
            path = path[:-1]
        attached = re.search(r'\.(?:' + '|'.join(extensions) + r')(을|를|은|는|이|가|에서|에|로|으로)$', path, re.I)
        if attached:
            tail = attached.group(1) + tail
            path = path[:-len(attached.group(1))]
        basename = path.rstrip('/').rsplit('/', 1)[-1]
        stem, dot, extension = basename.rpartition('.')
        if not dot:
            stem, extension = basename, ''
        description = extensions.get(extension.lower(), '파일')
        # Machine identifiers are intentionally described, not spelled out.
        machine = (len(stem) > 48 or bool(re.fullmatch(r'[0-9a-fA-F-]{16,}', stem))
                   or any(len(token) > 20 for token in re.split(r'[-_.]', stem)))
        spoken = '' if machine else ' '.join(names.get(token.lower(), token)
                                             for token in re.split(r'[-_.]+', stem) if token)
        if basename == 'report_v31.1.md':
            if '/' not in path:
                surrounding = (re.search(r'\S*$', text[:match.start()]).group()
                               + match.group() + re.match(r'\S*', text[match.end():]).group())
                if '://' in surrounding or '@' in surrounding:
                    return match.group()
            # USER-confirmed bad filename reading; preserve original/span accounting.
            # Keep version digits unchanged, and do not rewrite ordinary 'report'.
            spoken = '리포트 버전 31 점 1'
        kind = '경로' if '/' in path else ''
        result = ' '.join(filter(None, (spoken, description, kind)))
        tail += match.group('filename_particle') or match.group('particle') or ''
        if not kind:
            tail = re.sub(r'^(를|는|가|와)', lambda m: {'를': '을', '는': '은', '가': '이', '와': '과'}[m[0]], tail)
        if kind:
            tail = re.sub(r'^(을|이|은|으로)', lambda m: {'을': '를', '이': '가', '은': '는', '으로': '로'}[m[0]], tail)
        records.append({'original': raw, 'description': result, 'span': match.span(),
                        'replaced_text': match.group(0), 'spoken': result + tail})
        return result + tail

    normalized = pattern.sub(replace, text)
    return normalized, records
