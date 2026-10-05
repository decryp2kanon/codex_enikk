"""Yuki-specific text exceptions; independent of NVIDIA package implementation.

Order: path descriptions (engine, once) -> narrow protection/names/units ->
public NeMo TN (callback) -> checked restoration. No GPU or NeMo imports.
Each exception's reproducer lives in test_text_normalization.py or PathTests
in test_tts_delivery.py. General grammar, Korean G2P and voice controls are absent.
"""
import re

# User-defined names, not a general pronunciation dictionary.
NAMES = {'Yuki': '유키', 'Enikk': '에닉', 'Sugarchain': '슈가체인'}


def proper_names(text):
    return re.sub(r'(?<![A-Za-z])(?:Yuki|Enikk|Sugarchain)(?![A-Za-z])',
                  lambda m: NAMES[m.group()], text, flags=0)


# Reproduced NeMo errors and USER-confirmed unit readings. Case matters: GB != Gb.
# Other numeric/SI rules, ordinary Korean and mathematical operators stay upstream.
GROUPED_INTEGER = re.compile(r'(?<![A-Za-z0-9_.,])[1-9]\d{0,2}(?:,\d{3})+(?!\d|,\d)')
KNOWN_UNITS = {'GB': '기가바이트', 'MB': '메가바이트', 'TB': '테라바이트',
               'kHz': '킬로헤르츠', 'kbps': '킬로비트 퍼 초', 'km/h': '킬로미터 퍼 아워'}
NUMBER_UNIT = re.compile(r'(?<![A-Za-z0-9_.,+-])(?P<number>-?\d+(?:\.\d+)?)'
                        r'(?P<unit>GB|MB|TB|kHz|kbps|km/h)(?![A-Za-z0-9_])')
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
# NeMo reproduces "작은 일요일 부터" here; protect only this confirmed context.
WORK_NOUN_PHRASE = re.compile(r'(?<!\w)작은 일부터(?!\w)')


# Explicit USER listening failures only; not a general English or letter dictionary.
HEARD_ERRORS = {'Python': '파이썬', 'CPU': '씨피유', 'TTS': '티티에스',
                'API': '에이피아이', 'GPU': '지피유', 'VRAM': '브이램',
                'km/h': '킬로미터 퍼 아워'}
HEARD_TOKEN = re.compile(r'(?<![A-Za-z0-9_./@-])(?:Python|CPU|TTS|API|GPU|VRAM|km/h)'
                         r'(?![A-Za-z0-9_/@-]|\.[A-Za-z0-9_])')


def heard_error_readings(text):
    def replace(match):
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
    text = SINGLE_HOUR.sub(lambda match: protect('한 시간'), text)
    text = KNOWN_PROTECTED.sub(lambda match: protect(match.group()), text)
    # Strip commas only from syntactically valid thousands groups, not prose commas.
    text = GROUPED_INTEGER.sub(lambda match: match.group().replace(',', ''), text)

    def unit(match):
        number = normalize(match.group('number'))
        if not number.strip():
            raise RuntimeError('empty normalized number')
        return protect(number + ' ' + KNOWN_UNITS[match.group('unit')])

    text = NUMBER_UNIT.sub(unit, text)
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
            # Keep version digits for NeMo, and do not rewrite ordinary 'report'.
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
