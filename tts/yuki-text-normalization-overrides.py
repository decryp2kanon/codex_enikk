"""Yuki custom input pronunciations; independent of external normalizers.

Order: path descriptions (engine, once) -> narrow protection/names/units ->
normalization callback -> checked restoration. No external runtime imports.
Each exception's reproducer lives in test_text_normalization.py or PathTests
in test_tts_delivery.py; education grammars have test_education_2_7.py fixtures.
Korean G2P and voice controls are absent.
"""
import re
from functools import lru_cache

# User-defined names, not a general pronunciation dictionary.
NAMES = {'Yuki': '유키', 'Enikk': '에닉', 'Sugarchain': '슈가체인'}
NAME_TOKEN = re.compile(
    r'''(?<![A-Za-z0-9_./@=:#`"'()\[\]{}+-])(?:Yuki|Enikk|Sugarchain)'''
    r'''(?![A-Za-z0-9_/@=:#`"'()\[\]{}+-]|\.[A-Za-z0-9_])''')
NAME_LITERAL = re.compile(r'[./@_=:0-9`"\'()\[\]{}+-]')


def surrounding_token(text, start, end):
    """Inspect only a match's token, never rescan the preceding paragraph."""
    while start and not text[start-1].isspace():
        start -= 1
    while end < len(text) and not text[end].isspace():
        end += 1
    return text[start:end]


def proper_names(text):
    def replace(match):
        token = surrounding_token(text, *match.span()).rstrip('.,!?;')
        return match.group() if NAME_LITERAL.search(token) else NAMES[match.group()]
    return NAME_TOKEN.sub(replace, text)


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
_CARDINAL_LARGE = ('', '만', '억', '조', '경', '해', '자', '양')
_CARDINAL_LIMIT = 10 ** (4 * len(_CARDINAL_LARGE))


def korean_cardinal(value):
    """Read a non-negative integer as Korean Sino-Korean cardinal numerals."""
    value = int(value)
    if not 0 <= value < _CARDINAL_LIMIT:
        raise ValueError('cardinal outside supported non-negative range')
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
        spoken.append(''.join(part) + _CARDINAL_LARGE[position])
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


# 작성자: 에닉(유키짱)
# Complete numeric inputs only; technical literals in prose keep existing rules.
PLAIN_NUMBER = re.compile(r'[+-]?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?|[+-]?[1-9][0-9]{0,2}(?:,[0-9]{3})+(?:\.[0-9]+)?')


def scalar_number(text):
    value = text.strip()
    if len(value) <= 100 and PLAIN_NUMBER.fullmatch(value):
        integer = value.lstrip('+-').split('.')[0].replace(',', '')
        if len(integer) <= 32:
            spoken = ('플러스 ' + korean_number(value[1:]) if value.startswith('+') else korean_number(value))
            return text[:len(text)-len(text.lstrip())] + spoken + text[len(text.rstrip()):]
    return None
# 작성자: 에닉(유키짱)
# Lexical roots: shared across prose, plurals and registered compound concepts.
TECH_ROOTS = dict(item.split('=', 1) for item in '''
block=블록 wallet=월렛 key=키 node=노드 value=밸류 transaction=트랜잭션 peer=피어 hash=해시 chain=체인 json=제이슨
script=스크립트 address=어드레스 input=인풋 output=아웃풋 coin=코인 mem=멤 pool=풀 pub=퍼브
fee=피 time=타임 amount=어마운트 v=브이 out=아웃 in=인 height=하이트 version=버전 consensus=컨센서스 tip=팁
message=메시지 request=리퀘스트 state=스테이트 index=인덱스 byte=바이트 buffer=버퍼 param=파라미터 entry=엔트리
result=리절트 check=체크 error=에러 lock=락 path=패스 file=파일 data=데이터 count=카운트 name=네임 context=컨텍스트
span=스팬 invalid=인밸리드 valid=밸리드 number=넘버 network=네트워크 mining=마이닝 miner=마이너 nonce=논스
header=헤더 merkle=머클 signature=시그니처 verify=베리파이 relay=릴레이 orphan=오펀 checkpoint=체크포인트
 difficulty=디피컬티 target=타깃 proof=프루프 work=워크 seed=시드 socket=소켓 protocol=프로토콜 packet=패킷 ban=밴
connection=커넥션 inbound=인바운드 outbound=아웃바운드 sync=싱크 download=다운로드 upload=업로드 cache=캐시
 database=데이터베이스 level=레벨 db=디비 serialize=시리얼라이즈 deserialize=디시리얼라이즈 stream=스트림 thread=스레드
mutex=뮤텍스 atomic=아토믹 event=이벤트 queue=큐 policy=폴리시 dust=더스트 change=체인지 sig=시그 witness=위트니스
seg=세그 wit=위트 subsidy=섭시디 re=리 org=오그 git=깃 clone=클론 init=이닛 add=애드 status=스테이터스
 diff=디프 log=로그 show=쇼 branch=브랜치 switch=스위치 checkout=체크아웃 merge=머지 rebase=리베이스 reset=리셋
restore=리스토어 fetch=페치 pull=풀 push=푸시 remote=리모트 origin=오리진 upstream=업스트림 tag=태그 stash=스태시
cherry=체리 pick=픽 revert=리버트 bisect=바이섹트 blame=블레임 grep=그렙 clean=클린 archive=아카이브 tree=트리
submodule=서브모듈 config=컨피그 commit=커밋 amend=어멘드 squash=스쿼시 fix=픽스 up=업 head=헤드 main=메인
master=마스터 develop=디벨롭 feature=피처 release=릴리스 hot=핫 fork=포크 repository=리포지터리 repo=레포 issue=이슈
review=리뷰 approve=어프루브 base=베이스 conflict=컨플릭트 resolve=리졸브 ours=아워스 theirs=데어스 stage=스테이지
unstage=언스테이지 tracked=트랙트 untracked=언트랙트 ignored=이그노어드 working=워킹 detached=디태치드 fast=패스트
forward=포워드 force=포스 with=위드 lease=리스 prune=프룬 describe=디스크라이브 rev=레브 parse=파스 cat=캣
object=오브젝트 update=업데이트 read=리드 write=라이트 symbolic=심볼릭 ref=레프 for=포 each=이치 apply=어플라이
format=포맷 patch=패치 send=센드 email=이메일 note=노트 hook=훅 pre=프리 flow=플로 action=액션 runner=러너
artifact=아티팩트 milestone=마일스톤 label=레이블 assignee=어사이니 project=프로젝트 discussion=디스커션
 touch=터치 less=레스 more=모어 tail=테일 sed=세드 awk=오크 find=파인드 args=아그스 sort=소트 uniq=유니크 cut=컷
tee=티 print=프린트 echo=에코 date=데이트 which=위치 where=웨어 is=이즈 locate=로케이트 stat=스탯 mount=마운트
sudo=수도 su=에스유 id=아이디 who=후 am=앰 i=아이 group=그룹 top=톱 kill=킬 nice=나이스 job=잡 screen=스크린
 system=시스템 journal=저널 host=호스트 ping=핑 curl=컬 tar=타르 zip=집 snap=스냅 make=메이크 trace=트레이스
perf=퍼프 free=프리 export=익스포트 source=소스 bash=배시 no=노 hup=헙 ctl=씨티엘 get=겟 un=언
kernel=커널 primitive=프리미티브 util=유틸 crypto=크립토 test=테스트 bench=벤치 functional=펑셔널 fuzz=퍼즈
contrib=컨트리브 dev=데브 tool=툴 depends=디펜즈 package=패키지 bitcoin=비트코인 chainstate=체인스테이트 debug=디버그 text=텍스트
'''.split())
# Function words are lexical entries, never whole-input overrides.
# Keep the existing single token scan and literal boundary policy.
FUNCTION_WORDS = dict(item.split('=', 1) for item in '''
a=어 an=앤 the=더 and=앤드 or=오어 but=벗 so=소 as=애즈
if=이프 because=비커즈 though=도우 while=와일 when=웬 where=웨어 whether=웨더 than=댄
of=오브 in=인 on=온 at=앳 by=바이 for=포 from=프롬 to=투
with=위드 without=위드아웃 about=어바웃 against=어겐스트 among=어몽 between=비트윈 into=인투 through=스루
during=듀어링 before=비포 after=애프터 above=어버브 below=빌로 under=언더 over=오버 I=아이
me=미 my=마이 mine=마인 we=위 us=어스 our=아워 ours=아워스 you=유
your=유어 yours=유어스 he=히 him=힘 his=히즈 she=쉬 her=허 it=잇
its=잇츠 they=데이 them=뎀 their=데어 this=디스 that=댓 these=디즈 those=도즈
who=후 whose=후즈 which=위치 what=왓 is=이즈 am=앰 are=아 was=워즈
were=워 be=비 been=빈 being=비잉 do=두 does=더즈 did=디드 have=해브
has=해즈 had=해드 can=캔 could=쿠드 will=윌 would=우드 should=슈드 may=메이
might=마이트 must=머스트 not=낫 no=노 some=썸 any=애니 each=이치 every=에브리
all=올 both=보스 either=이더 neither=니더
'''.split())


def function_reading(token):
    if token in FUNCTION_WORDS:
        return FUNCTION_WORDS[token]
    # Sentence-initial title case is prose; opaque uppercase acronyms remain so.
    if len(token) > 1 and token.istitle():
        return FUNCTION_WORDS.get(token.lower())
    return None


# 작성자: 에닉(유키짱)
# Reuse verified roots; duplicate lexical entries never replace prior readings.
CODEX_ROOTS = dict(item.split('=', 1) for item in '''
codex=코덱스 agent=에이전트 assistant=어시스턴트 user=유저 prompt=프롬프트 response=리스폰스 reasoning=리즈닝 instruction=인스트럭션
system=시스템 developer=디벨로퍼 turn=턴 session=세션 conversation=컨버세이션 history=히스토리 memory=메모리 token=토큰
model=모델 tool=툴 function=펑션 call=콜 command=커맨드 shell=셸 terminal=터미널 process=프로세스
runtime=런타임 environment=인바이런먼트 workspace=워크스페이스 directory=디렉터리 patch=패치 apply=어플라이 edit=에디트 write=라이트
read=리드 search=서치 test=테스트 build=빌드 lint=린트 format=포맷 validation=밸리데이션 success=석세스
failed=페일드 failure=페일러 warning=워닝 retry=리트라이 timeout=타임아웃 cancel=캔슬 interrupt=인터럽트 resume=리줌
continue=컨티뉴 start=스타트 stop=스톱 complete=컴플리트 completed=컴플리티드 pending=펜딩 queued=큐드 running=러닝
ready=레디 active=액티브 inactive=인액티브 approval=어프루벌 approved=어프루브드 permission=퍼미션 sandbox=샌드박스 restricted=리스트릭티드
unrestricted=언리스트릭티드 configuration=컨피규레이션 argument=아규먼트 parameter=파라미터 option=옵션 flag=플래그 endpoint=엔드포인트 snapshot=스냅샷
reconcile=레컨사일 fallback=폴백 planner=플래너 plan=플랜 task=태스크 subtask=서브태스크 handoff=핸드오프 delegate=델리게이트
delegation=델리게이션 executor=엑시큐터 execution=엑시큐션 invoke=인보크 invocation=인보케이션 item=아이템 result=리절트 analysis=애널리시스
commentary=코멘터리 final=파이널 summary=서머리 rollback=롤백 point=포인트 attachment=어태치먼트 connector=커넥터 plugin=플러그인
capability=케이퍼빌리티 schema=스키마 payload=페이로드
'''.split())
for _word, _reading in CODEX_ROOTS.items():
    TECH_ROOTS.setdefault(_word, _reading)
# Bounded status-label grammar; arbitrary snake_case identifiers stay opaque.
CODEX_LABEL_PREFIXES = ('apply', 'response', 'tool', 'rollback')
CODEX_LABEL_SUFFIXES = ('patch', 'item', 'call', 'result', 'point')
CODEX_LABELS = {prefix + '_' + suffix: TECH_ROOTS[prefix] + ' ' + TECH_ROOTS[suffix]
                for prefix in CODEX_LABEL_PREFIXES for suffix in CODEX_LABEL_SUFFIXES}

LETTER_NAMES = dict(zip('abcdefghijklmnopqrstuvwxyz',
    '에이 비 씨 디 이 에프 지 에이치 아이 제이 케이 엘 엠 엔 오 피 큐 알 에스 티 유 브이 더블유 엑스 와이 지'.split()))
TECH_ABBREVIATIONS = frozenset('''
txid utxo rpc ls cd pwd cp mv rm mkdir rmdir tr wc du df lsblk blkid chmod chown chgrp passwd ps bg fg
 tmux dmesg ip ss ssh scp rsync apt dpkg gcc gdb lsof vmstat iostat env sh qt src
'''.split())
# Only registered compounds can be decomposed; arbitrary branch/identifier names cannot.
TECH_COMPOUNDS = frozenset('''
cherry-pick pull-request request-changes merge-base index-file working-tree fast-forward force-with-lease
rev-parse ls-files ls-tree cat-file hash-object update-index read-tree write-tree commit-tree symbolic-ref
for-each-ref show-ref merge-tree format-patch send-email pre-commit pre-push release-note
'''.split())
TECH_COMPONENTS = dict(item.split('=', 1) for item in '''
mempool=mem+pool pubkey=pub+key vout=v+out vin=v+in leveldb=level+db scriptpubkey=script+pub+key scriptSig=script+sig
segwit=seg+wit coinbase=coin+base reorg=re+org worktree=work+tree fixup=fix+up hotfix=hot+fix reflog=ref+log
workflow=work+flow xargs=x+args printf=print+f whereis=where+is umount=u+mount whoami=who+am+i htop=h+top
pkill=p+kill pgrep=p+grep renice=re+nice nohup=no+hup systemctl=system+ctl journalctl=journal+ctl uname=u+name
hostname=host+name wget=w+get gzip=g+zip gunzip=g+un+zip unzip=un+zip cmake=c+make strace=s+trace uptime=up+time devtools=dev+tools
'''.split())
TECH_PROSE_TOKEN = re.compile(r'```[\s\S]*?```|`[^`]*`|\S+')
TECH_ASCII = re.compile('[A-Za-z]')
HASH_HEX = re.compile(r'[0-9a-fA-F]{7,}')
HASH_ANCHORS = frozenset(('hash', 'commit', 'sha', 'sha1', 'sha-1', 'sha256',
                         'sha-256', 'digest', 'checksum', 'release', 'revision', 'rev'))
HASH_NAMES = dict(zip('0123456789abcdef',
    ('제로', '원', '투', '쓰리', '포', '파이브', '식스', '세븐', '에이트', '나인',
     '에이', '비', '씨', '디', '이', '에프')))
PROSE_PARTICLE = r'(?:에서도|에서는|에도|으로|에서|에게|은|는|이|가|을|를|의|에|로|와|과|도)'
HASH_WITH_PARTICLE = re.compile(r'([0-9a-fA-F]{7,})(' + PROSE_PARTICLE + r')')
PROSE_NUMBER = r'-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\\?\.\d+)?'
PROSE_ENDING = PROSE_PARTICLE + r'|입니다|이에요|예요|였습니다|이고|이며|이면|라면|면|일'
PROSE_QUANTITY = re.compile(
    r'(?P<first>' + PROSE_NUMBER + r')(?P<left_unit>[A-Za-zµ°²/%]*)'
    r'(?:(?:\\?~)(?P<second>' + PROSE_NUMBER + r')'
    r'(?P<right_unit>[A-Za-zµ°²/%]*))?'
    r'(?P<counter>개|회|초|명|건)?(?P<particle>' + PROSE_ENDING + r')?')
PROSE_REFERENCE = re.compile(r'\\?#([1-9][0-9]{0,8})(' + PROSE_ENDING + r')?')
PROSE_RATIO = re.compile(r'(\d{1,3}(?:,\d{3})+|\d+)/(\d{1,3}(?:,\d{3})+|\d+)(' + PROSE_ENDING + r')?')
REFERENCE_ANCHORS = frozenset(('pr', 'issue', 'pull-request', '이슈'))
PROSE_SPACE_ENTITY = re.compile(r'^(?:(?:&#32;|&#x20;|&nbsp;))+', re.IGNORECASE)
SHA_ALGORITHM = re.compile(r'SHA-?([1-9][0-9]{0,3})(' + PROSE_PARTICLE + r')?', re.IGNORECASE)
UUID_TOKEN = re.compile(
    r'([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-'
    r'[0-9a-fA-F]{4}-[0-9a-fA-F]{12})(' + PROSE_ENDING + r')?')


def uuid_reading(token):
    """Read complete UUID structure, independently of hash abbreviation."""
    if len(token) < 36 or len(token) > 48 or token[8] != '-':
        return None
    match = UUID_TOKEN.fullmatch(token)
    if match is None:
        return None
    groups = [' '.join(HASH_NAMES[c] for c in group.lower())
              for group in match[1].split('-')]
    return ', 대시, '.join(groups) + (match[2] or '')


def quantity_reading(token):
    """Full prose quantities only; paths, versions and machine tokens stay opaque."""
    if '/' in token:
        ratio = PROSE_RATIO.fullmatch(token)
        if ratio:
            numerator, denominator = (value.replace(',', '') for value in ratio.groups()[:2])
            if max(len(numerator), len(denominator)) <= 32 and int(denominator) != 0:
                return (korean_cardinal(denominator) + ' 분의 ' + korean_cardinal(numerator) +
                        (ratio[3] or ''))
            return None
    match = PROSE_QUANTITY.fullmatch(token)
    if match is None:
        return None
    first, second = match['first'], match['second']
    if any(len(value.lstrip('-').split('.')[0].replace(',', '')) > 32
           for value in (first, second) if value is not None):
        return None
    units = (match['left_unit'], match['right_unit'] or '')
    if any(unit and unit not in KNOWN_UNITS and unit != '/s' for unit in units):
        return None
    # Leave ordinary bare prose numerals to the existing policy.
    if second is None and not any(units) and not match['counter']:
        return None
    def spoken(value, unit):
        reading = korean_number(value.replace('\\.', '.'))
        return reading + (' ' + ('퍼 세컨드' if unit == '/s' else KNOWN_UNITS[unit]) if unit else '')
    result = spoken(first, units[0])
    if second is not None:
        result += '에서 ' + spoken(second, units[1])
    return result + (' ' + match['counter'] if match['counter'] else '') + (match['particle'] or '')


def hash_reading(token, anchored=False):
    """Only a complete hex token; machine punctuation never enters this grammar."""
    if len(token) < (7 if anchored else 32) or not HASH_HEX.fullmatch(token) or token.isdecimal():
        return None
    prefix = token[:7].lower()
    particle = '으로' if prefix[-1] in '17' else '로'
    return (' '.join(HASH_NAMES[c] for c in prefix) + particle +
            ' 시작하는 해시고 총길이 ' + korean_cardinal(len(token)) + ' 글자')

CODE_LITERAL = re.compile(r'```[\s\S]*?(?:```|$)|`[^`]*(?:`|$)')
CUSTOM_TRANSFORM_INPUT = re.compile(r'[A-Za-z\d]')
TECH_WITH_PARTICLE = re.compile(
    r'([A-Za-z][A-Za-z_-]*)(' + PROSE_ENDING +
    r'|하(?:며|고|면|는|기|다|겠습니다|세요|지|도록)|합니다|해(?:요|서|도)?|했(?:다|고|으며|습니다))')


PROSE_READINGS = {**TECH_ROOTS, **FUNCTION_WORDS, **CODEX_LABELS}
PROSE_READINGS.update({'URL': '유알엘', 'UUID': '유유아이디',
                       'url': '유알엘', 'uuid': '유유아이디'})
CODEX_PROSE_READINGS = {word.title(): TECH_ROOTS[word] for word in CODEX_ROOTS}
CODEX_PROSE_READINGS.update(CODEX_LABELS)
PROSE_READINGS.update(CODEX_PROSE_READINGS)
PROSE_READINGS.update({word.title(): reading for word, reading in FUNCTION_WORDS.items()
                       if len(word) > 1})


def lexical_reading(token):
    """Registered words and productive plurals; unknown machine tokens are opaque."""
    if token[:3].lower() == 'sha':
        algorithm = SHA_ALGORITHM.fullmatch(token)
        if algorithm:
            return '에스 에이치 에이 ' + korean_cardinal(algorithm[1]) + (algorithm[2] or '')
        if token.lower() == 'sha':
            return '에스 에이치 에이'
    reading = PROSE_READINGS.get(token)
    if reading is not None:
        return reading
    if token == 'HEAD':
        return TECH_ROOTS['head']
    if token in TECH_ABBREVIATIONS:
        return ''.join(LETTER_NAMES[letter] for letter in token)
    if token in TECH_COMPONENTS:
        return ''.join(lexical_reading(part) or LETTER_NAMES.get(part, part)
                        for part in TECH_COMPONENTS[token].split('+'))
    if token in TECH_COMPOUNDS:
        return ' '.join(lexical_reading(part) or part for part in token.split('-'))
    for suffix in ('es', 's'):
        if token.endswith(suffix):
            stem = token[:-len(suffix)]
            if stem in TECH_ROOTS or stem in CODEX_PROSE_READINGS or stem in TECH_COMPONENTS or stem in TECH_ABBREVIATIONS:
                return lexical_reading(stem) + '스'
    particle = TECH_WITH_PARTICLE.fullmatch(token)
    if particle:
        stem, ending = particle.groups()
        if stem in PROSE_READINGS or stem in TECH_COMPONENTS or stem in TECH_ABBREVIATIONS or stem in TECH_COMPOUNDS or stem == 'HEAD':
            return lexical_reading(stem) + ending
    return None


def technical_prose(text):
    # Single registry scan. Literal dots, slashes, underscores, options and
    # embedded code delimiters never match a registered word.
    if not CUSTOM_TRANSFORM_INPUT.search(text):
        return text
    previous = None
    previous_end = 0
    def replace(match):
        nonlocal previous, previous_end
        raw = match.group()
        raw = PROSE_SPACE_ENTITY.sub('', raw)
        anchored = previous in HASH_ANCHORS and '\n' not in text[previous_end:match.start()] and '\r' not in text[previous_end:match.start()]
        reference_context = previous in REFERENCE_ANCHORS and '\n' not in text[previous_end:match.start()] and '\r' not in text[previous_end:match.start()]
        previous, previous_end = raw.lower(), match.end()
        if raw.startswith('`'):
            return raw
        token = raw.rstrip(',!?;')
        punctuation = raw[len(token):]
        if token.endswith('.') and (token.count('.') == 1 or token[:1].isdigit()):
            token, punctuation = token[:-1], '.' + punctuation
        particle = HASH_WITH_PARTICLE.fullmatch(token) if len(token) >= 8 else None
        hash_token = particle[1] if particle else token
        reading = uuid_reading(token) if len(token) >= 36 else None
        if reading is None:
            reading = hash_reading(hash_token, anchored) if len(hash_token) >= 7 else None
        if reading is not None and particle:
            reading += particle[2]
        if reading is None and token[:1] in '-0123456789' and token:
            reading = quantity_reading(token)
        if reading is None and reference_context and token.startswith(('#', '\\#')):
            reference = PROSE_REFERENCE.fullmatch(token)
            if reference:
                reading = korean_cardinal(reference[1]) + ' 번' + (reference[2] or '')
        return (reading or lexical_reading(token) or token) + punctuation
    return TECH_PROSE_TOKEN.sub(replace, text)
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


# 작성자: 에닉(유키짱)
# Symbol atoms and longest-match operators are shared across unseen combinations.
SYMBOL_ATOMS = dict(zip('#*_ -+=><:;.,/\\|&!?@$%^~`\'"()[]{}'.replace(' ', ''),
    ['해시', '별표', '밑줄', '마이너스', '플러스', '등호', '크다', '작다',
     '콜론', '세미콜론', '마침표', '쉼표', '슬래시', '백슬래시', '파이프',
     '앰퍼샌드', '느낌표', '물음표', '골뱅이', '달러', '퍼센트', '캐럿',
     '물결', '백틱', '작은따옴표', '큰따옴표', '여는 소괄호', '닫는 소괄호',
     '여는 대괄호', '닫는 대괄호', '여는 중괄호', '닫는 중괄호']))
SYMBOL_OPERATORS = {
    '===': '엄격한 동등 비교', '!==': '엄격한 비동등 비교',
    '==': '동등 비교', '!=': '비동등 비교', '>=': '크거나 같다', '<=': '작거나 같다',
    '&&': '논리 앤드', '||': '논리 오어', '++': '증가 연산자',
    '->>': '오른쪽 이중 화살표', '<<-': '왼쪽 이중 화살표',
    '<=>': '양방향 이중 화살표', '<->': '양방향 화살표',
    '->': '오른쪽 화살표', '<-': '왼쪽 화살표', '=>': '오른쪽 이중선 화살표',
    '>>>': '부호 없는 오른쪽 시프트', '>>': '오른쪽 시프트', '<<': '왼쪽 시프트',
    '::': '이중 콜론', '...': '말줄임표', '??': '널 병합 연산자', '?.': '옵셔널 체이닝',
    '<!-- -->': '빈 에이치티엠엘 주석', '<!--': '에이치티엠엘 주석 시작',
    '-->': '에이치티엠엘 주석 끝', '</>': '빈 닫는 태그', '</': '닫는 태그 시작',
    '/>': '자기 닫힘 태그 끝', '()': '소괄호 쌍', '[]': '대괄호 쌍',
    '{}': '중괄호 쌍', '<>': '꺾쇠괄호 쌍',
}
SYMBOL_DIRECT = {atom * count: name + (' ' + korean_cardinal(str(count)) + ' 개' if count > 1 else '')
                 for atom, name in SYMBOL_ATOMS.items() for count in range(1, 9)}
SYMBOL_DIRECT.update(SYMBOL_OPERATORS)
PROSE_READINGS.update(SYMBOL_DIRECT)
SYMBOL_KEYS = tuple(sorted(SYMBOL_OPERATORS, key=lambda key: (-len(key), key)))
SYMBOL_HINT = re.compile(r'[#*_+=<>:;.,/\\|&!?@$%^~`\'"()\[\]{}-]')
SYMBOL_OR_CUSTOM = re.compile(r'[A-Za-z0-9#*_+=<>:;.,/\\|&!?@$%^~`\'"()\[\]{}-]')
SYMBOL_WORD = re.compile(r'(?<!\S)\S+(?!\S)')
CODE_EXPRESSION = re.compile(r'[A-Za-z_][A-Za-z0-9_]*\s*(?:===|!==|==|!=|<=|>=|=|<|>|&&|\|\|)\s*[A-Za-z_0-9][A-Za-z0-9_]*;?')
MARKDOWN_HEADING = re.compile(r'(?m)^(#{1,6})[ \t]+(.+)$')


def symbol_reading(token):
    direct = SYMBOL_DIRECT.get(token)
    if direct is not None:
        return direct
    if not token or any(ch not in SYMBOL_ATOMS for ch in token):
        return None
    # Repeated identical markers are counts, not a row-specific lookup.
    if len(set(token)) == 1:
        if len(token) == 1:
            return SYMBOL_ATOMS[token]
        return SYMBOL_ATOMS[token[0]] + ' ' + korean_cardinal(str(len(token))) + ' 개'
    result = []
    index = 0
    while index < len(token):
        key = next((key for key in SYMBOL_KEYS if token.startswith(key, index)), None)
        if key:
            result.append(SYMBOL_OPERATORS[key]); index += len(key)
        else:
            result.append(SYMBOL_ATOMS[token[index]]); index += 1
    return ' '.join(result)


def symbol_prose(text):
    # Only space-separated symbol tokens; machine literals remain maximal tokens.
    # A backtick-bearing mixed input is code and keeps the existing protection.
    if not SYMBOL_HINT.search(text):
        return text
    isolated = symbol_reading(text.strip())
    if isolated is not None:
        return isolated
    if '`' in text:
        return text
    text = MARKDOWN_HEADING.sub(lambda m: korean_cardinal(str(len(m[1]))) + ' 단계 제목 ' + m[2], text)
    return SYMBOL_WORD.sub(lambda m: symbol_reading(m[0]) or m[0], text)


def markdown_spoken(text):
    """Called before decoration removal; complete code blocks remain hidden."""
    isolated = symbol_reading(text.strip())
    if isolated is not None:
        return isolated
    if not any(marker in text for marker in ('#', '*', '_', '~', '`', '<')):
        return text
    # Complete/unfinished fences are never reintroduced into speech.
    text = re.sub(r'(?m)^\s*(```|~~~)[^\n]*\n[\s\S]*?(?:^\s*\1[^\n]*$|\Z)', ' ', text)
    inline = {}
    available = (chr(i) for i in range(0xE000, 0xF900) if chr(i) not in text)
    def protect_inline(match):
        marker = next(available, None)
        if marker is None:
            raise ValueError('too many inline code spans')
        inline[marker] = match[0]
        return marker
    text = re.sub(r'`[^`]*(?:`|$)', protect_inline, text)
    text = MARKDOWN_HEADING.sub(lambda m: korean_cardinal(str(len(m[1]))) + ' 단계 제목 ' + m[2], text)
    text = re.sub(r'<!--([\s\S]*?)-->', lambda m: ' 에이치티엠엘 주석 ' + m[1] + ' 주석 끝 ', text)
    text = re.sub(r'</?([A-Za-z][A-Za-z0-9-]*)\s*/?>',
                  lambda m: (' 닫는 태그 ' if m[0].startswith('</') else ' 여는 태그 ') + m[1] + ' ', text)
    # Restrict emphasis to non-identifier boundaries and a non-empty body.
    for marker, label in [('***', '굵게 기울임'), ('___', '굵게 기울임'),
                          ('**', '굵게'), ('__', '굵게'), ('~~', '취소선'),
                          ('*', '기울임'), ('_', '기울임')]:
        if marker not in text:
            continue
        escaped = re.escape(marker)
        pattern = r'(?<!\S)' + escaped + r'([^\n]+?)' + escaped + r'(?![\w*~_`])'
        text = re.sub(pattern, lambda m: label + ' ' + m[1] + ' 강조 끝', text)
    for marker, raw in inline.items():
        text = text.replace(marker, raw)
    return text


def normalize_with_exceptions(text, normalize=None):
    """Read custom grammar, optionally call a normalizer, and restore our spans.

    Each transformed span is normalized once. Opaque markers never reach the GPU.
    The private-use markers are chosen outside the input and checked for loss or
    duplication rather than repairing arbitrary words in the final output.
    Omitting the callback explicitly selects the independent custom-only path.
    """
    if not text.strip():
        return text
    # Exact scalar measurement tokens are common input units and need no prose
    # protection pipeline. Keep this full-token fast path ahead of all generic
    # exceptions; embedded values still use the guarded combined scan below.
    scalar = NUMBER_UNIT.fullmatch(text)
    if scalar and scalar.group('unit') in KNOWN_UNITS:
        value = scalar.group('number')
        if len(value) <= 32 or len(value.lstrip('-').split('.')[0].replace(',', '')) <= 32:
            return korean_number(value) + ' ' + KNOWN_UNITS[scalar.group('unit')]
        return text
    if text.lstrip()[:1] in '+-0123456789':
        numeric = scalar_number(text)
        if numeric is not None:
            return numeric
    reading = lexical_reading(text)
    if reading is not None:
        return reading
    if normalize is None and not SYMBOL_OR_CUSTOM.search(text):
        return text
    if text[0].isascii() and CODE_EXPRESSION.fullmatch(text.strip()):
        return text
    text = symbol_prose(text)
    if normalize is None:
        # All custom transformations require a Latin name/word or a numeral.
        # Pure Korean path descriptions need no protect/restore identity pass.
        if not CUSTOM_TRANSFORM_INPUT.search(text):
            return text
        normalize = lambda value: value
    protected = {}
    available = (chr(i) for i in range(0xE000, 0xF900) if chr(i) not in text)

    def protect(value):
        token = next(available, None)
        if token is None:
            raise ValueError('too many protected normalization spans')
        protected[token] = value
        return token

    if '`' in text:
        text = CODE_LITERAL.sub(lambda match: protect(match.group()), text)
    text = proper_names(text)

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
        # Keep compact ranges intact for the full-token quantity grammar below.
        token = surrounding_token(text, *match.span()).rstrip(',!?;.')
        if '~' in token:
            return match.group()
        if match.group('grouped_integer') is not None:
            return match.group('grouped_integer').replace(',', '')
        unit_name = match.group('unit_token')
        if unit_name not in KNOWN_UNITS:
            if ',' in match.group('unit_number'):
                return (match.group('unit_number').replace(',', '') +
                        match.group('unit_space') + unit_name)
            return match.group()
        if len(match.group('unit_number').lstrip('-').split('.')[0].replace(',', '')) > 32:
            return match.group()
        return korean_number(match.group('unit_number')) + ' ' + KNOWN_UNITS[unit_name]

    text = NUMBER_OR_GROUPED_INTEGER.sub(number_or_grouped, text)
    text = LARGE_ITEM_COUNT.sub(
        lambda match: protect(korean_cardinal(match.group(1)) + ' 개'), text)

    text = heard_error_readings(text)
    result = normalize(technical_prose(text))
    for token, value in protected.items():
        if result.count(token) != 1:
            raise RuntimeError('protected normalization span lost or duplicated')
        result = result.replace(token, value)
    return result


PATH_EXTENSIONS = {
    'py': '파이썬 파일', 'md': '마크다운 파일', 'sh': '셸 스크립트',
    'json': '제이슨 파일', 'txt': '텍스트 파일', 'wav': '웨이브 오디오 파일',
    'log': '로그 파일', 'dat': '데이터 파일', 'conf': '설정 파일',
    'toml': '톰엘 설정 파일', 'yaml': '야믈 설정 파일',
    'yml': '야믈 설정 파일', 'cpp': '씨 플러스 플러스 소스 파일',
    'cc': '씨 플러스 플러스 소스 파일', 'h': '헤더 파일', 'hpp': '헤더 파일',
    'rs': '러스트 소스 파일', 'js': '자바스크립트 파일', 'ts': '타입스크립트 파일',
}
PATH_NAMES = {'yuki': '유키', 'engine': '엔진', 'enikk': '에닉', 'readme': '리드미',
         'install': '인스톨', 'license': '라이선스', 'changelog': '체인지로그',
         'makefile': '메이크파일', 'chatterbox': '채터박스', 'test': '테스트', 'output': '아웃풋',
         'approval': '승인', 'marker': '표시'}
# Delimited paths may contain Korean filenames. Attached Korean particles
# after a known extension are prose, not part of that filename.
PATH_PATTERN = re.compile(
    r"(?<![\w/:.])(?P<path>`?(?:(?:/(?:home|tmp|usr|etc|var|opt)/|~/|\.\.?/)[^\s`\"'<>()[\]{}]+"
    r"|(?P<known_report>(?<![@-])report_v31\.1\.md(?![A-Za-z0-9_-]|\.[A-Za-z0-9_])))`?)"
    r"(?(known_report)(?:(?P<filename_particle>으로|에서|을|를|은|는|이|가|에|로|와|과|도)(?=\s|[.!?,]|$))?|)"
    r"(?:\s+(?:파일|경로)(?P<particle>에서|으로|을|를|은|는|이|가|에|로|(?(known_report)도|(?!)))?(?=\s|[.!?,]|$))?")

@lru_cache(maxsize=256)
def path_component(value):
    """Bounded cache of component readings, never complete source paths."""
    hidden = value.startswith('.')
    value = value[1:] if hidden else value
    if re.fullmatch('[0-9a-fA-F]{16,}', value) or len(value) > 48:
        return ('숨김 ' if hidden else '') + '식별자'
    local_names = {'home': '홈', 'sugarchain': '슈가체인', 'readme': '리드미'}
    tokens = []
    for token in re.split('[-_]', value):
        if re.fullmatch(r'v[0-9]+(?:\.[0-9]+)*', token):
            numbers = token[1:].split('.')
            tokens.append('버전 ' + ('식별자' if any(len(n) > 32 for n in numbers) else
                          ' 쩜 '.join(' '.join(_CARDINAL_DIGITS[int(d)] for d in n)
                                     if len(n) > 1 and n.startswith('0') else korean_cardinal(int(n))
                                     for n in numbers)))
        else:
            read = (local_names.get(token.lower()) or PATH_NAMES.get(token.lower()) or
                    lexical_reading(token))
            if read is None and token.isascii() and token.isalpha():
                read = ''.join(LETTER_NAMES[char.lower()] for char in token)
            tokens.append(read or token)
    return ('숨김 ' if hidden else '') + ' '.join(tokens)


def project_path_description(path, extensions):
    """Describe a project path structurally without resolving or reading disk.

    Preserve every traversal component. Other path families retain the existing
    basename description policy. This is an opt-in project vocabulary scope,
    never an exact path lookup.
    """
    parts = path.split('/')
    if not any(part in ('sugarchain', '.sugarchain', 'bitcoin', '.bitcoin') for part in parts):
        return None
    spoken = []
    if path.startswith('/'):
        spoken.append('루트 디렉터리')
    nonempty = [part for part in parts if part]
    for index, part in enumerate(nonempty):
        if part == '~':
            spoken.append('홈 디렉터리')
        elif part == '..':
            spoken.append('상위 디렉터리')
        elif part == '.':
            spoken.append('현재 디렉터리')
        elif index == len(nonempty)-1 and not path.endswith('/'):
            stem, dot, extension = part.rpartition('.')
            if dot and stem and extension.isalpha():
                spoken.append(path_component(stem) + ' ' + extensions.get(extension.lower(), '파일'))
            else:
                spoken.append(path_component(part) + ' 디렉터리')
        else:
            spoken.append(path_component(part))
    return ' 아래 '.join(spoken) + ' 경로'


def normalize_paths(text):
    """TTS-only filesystem descriptions, before splitting or number conversion.

    Return explicit replacements as well as text; never mutate the source job.
    URLs and ordinary slash expressions cannot start a match.
    """
    extensions, names, pattern = PATH_EXTENSIONS, PATH_NAMES, PATH_PATTERN
    records = []

    def replace(match):
        raw = match.group('path')
        surrounding = surrounding_token(text, *match.span())
        if '://' in surrounding or '@' in surrounding:
            return match.group()
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
            # USER-confirmed bad filename reading; preserve original/span accounting.
            # Keep version digits unchanged, and do not rewrite ordinary 'report'.
            spoken = '리포트 버전 31 점 1'
        kind = '경로' if '/' in path else ''
        result = (project_path_description(path, extensions) or
                  ' '.join(filter(None, (spoken, description, kind))))
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

# EOF
