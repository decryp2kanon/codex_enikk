# Dorothy/Enikk command documents

Every newly authored command document ends with one blank separator line followed
by an exact `EOF` line. This applies to full tasks, additions, corrections,
continuations, recovery/handoff instructions and even single-line status commands.
Do not add explanations after that line. Do not add another marker to an already
terminated document. Reports such as `~/enikk-result.md` and logs are not commands.

From the repository, save a new command with:

```sh
python3 handoff_command.py /path/to/new-command.md < /path/to/draft.txt
python3 handoff_command.py /path/to/new-command.md --check
```

The writer validates the resulting file, uses atomic publication and refuses to
overwrite an existing file by default. Only for an explicitly mutable inbox such
as `~/dorothy-command.md`, use `--replace-inbox`. Input is UTF-8. Command content
and internal whitespace are preserved; only terminal blank lines/EOF framing are
normalized. A final standalone EOF line is treated as the document terminator.

Never rewrite an existing immutable task snapshot or append-only instruction
entry to migrate its format. New journal entries should be formatted before
publication and hashing. Existing snapshot hashes and running tasks stay intact.
The separate pipeline repository is not bundled by this change: its current
documentation-only adapter is not widened to arbitrary code changes. This tool
is invoked explicitly by the handoff author; it does not watch files, execute
instructions, parse task JSON, or alter Enikk/Yuki runtime and installation.
