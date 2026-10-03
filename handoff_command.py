#!/usr/bin/env python3
"""Explicit Dorothy/Enikk command-document writer; never applied to reports."""
import argparse
import os
from pathlib import Path
import sys
import tempfile


def validate(text):
    """Require one blank separator and an exact final EOF line."""
    if not text.endswith('\n\nEOF\n') or text.splitlines()[-1] != 'EOF':
        raise ValueError('command must end with a blank line and EOF')
    if not text[:-5].strip():
        raise ValueError('empty command')


def format_command(text):
    """Only normalize the terminal framing, never rewrite command content."""
    body = text.rstrip('\r\n')
    if body.split('\n')[-1].rstrip('\r') == 'EOF':
        body = body[:-3].rstrip('\r\n')
    result = body + '\n\nEOF\n'
    validate(result)
    return result


def save_command(path, text, *, replace=False):
    """Atomically publish, preserving existing snapshots unless opted in.

    Replace is for a mutable command inbox only, never an immutable snapshot or
    append-only journal. Callers must designate command documents explicitly.
    """
    path = Path(path)
    data = format_command(text).encode('utf-8')
    if path.is_symlink():
        raise ValueError('refusing symlink destination')
    fd, temporary = tempfile.mkstemp(prefix='.command-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        validate(Path(temporary).read_text(encoding='utf-8'))
        if replace:
            os.replace(temporary, path)
        else:
            os.link(temporary, path, follow_symlinks=False)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        validate(path.read_text(encoding='utf-8'))
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path', type=Path)
    parser.add_argument('--check', action='store_true', help='validate without modifying')
    parser.add_argument('--replace-inbox', action='store_true', help='replace a mutable inbox; never use for task snapshots')
    args = parser.parse_args(argv)
    if args.check and args.replace_inbox:
        parser.error('--check and --replace-inbox cannot be combined')
    try:
        if args.check:
            validate(args.path.read_text(encoding='utf-8'))
        else:
            save_command(args.path, sys.stdin.read(), replace=args.replace_inbox)
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
