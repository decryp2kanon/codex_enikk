"""Small, removable upstream-derived Korean exact-token dictionary layer."""
import re

# Registry IDs and upstream provenance are maintained in manifest.json.
RULES = {
    'AI': '에이아이',       # UDK-001
    'CEO': '씨이오',        # UDK-002
    'CCTV': '씨씨티비',     # UDK-003
    'PC': '피씨',           # UDK-004
    'SNS': '에스엔에스',    # UDK-005
    'KOREA': '코리아',      # UDK-006
    'IDOL': '아이돌',       # UDK-007
    'IT': '아이티',         # UDK-008
    'IQ': '아이큐',         # UDK-009
}

_TOKEN = re.compile(
    r'(?<![A-Za-z0-9_./@+\-=<>#])(?:AI|CEO|CCTV|PC|SNS|KOREA|IDOL|IT|IQ)'
    r'(?![A-Za-z0-9_/@+\-=<>#]|\.(?=[A-Za-z0-9_]))'
)


def apply(text):
    """Convert only exact uppercase prose tokens, preserving technical literals."""
    if not isinstance(text, str):
        raise TypeError('text must be str')
    return _TOKEN.sub(lambda match: RULES[match.group()], text)
