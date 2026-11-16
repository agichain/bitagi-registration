"""Closed-output exit-code policy for Claude-track tools (#302 Codex review r4260423162, #258 6148738516).

A Claude-track tool that cannot write its stdout or stderr ends with exit 4 (AGENTS.md section 12, internal
error), never 0 or 120, whatever its verdict: a FAIL whose report was lost is still a failure, and a verdict
kept only when the output is small would depend on its size. A stream that was not written, or a descriptor
closed before start (Python then has no stream), does not change the verdict. Nothing new is written to
stderr; the exit code is the signal.

Without it CPython ends a small report written to a closed pipe with 120: print() only fills the buffer, and
the interpreter's own final flush fails after main() has returned. A report larger than the buffer fails
inside print() with BrokenPipeError (exit 1 when uncaught). Flushing is not enough: the failed bytes stay
in the buffer and the final flush fails again, so a stream that fails to flush is pointed at /dev/null.

A tool ends with `claude_track_exit.run(main)` in place of `raise SystemExit(main())`. The import goes in
the `__main__` block, so the module's import surface stays the same; it resolves through the script's
folder on sys.path, so `-I` or `-P` fails closed with exit 1. New Claude-track tools use it from the start;
existing ones adopt it when next touched (byte-pinned inherited tools need their own decision).

Any other exception escaping main() is an internal error too: its traceback is printed and the tool ends with 4,
not the interpreter's 1, which section 12 gives no meaning (Codex review r4269218703, A r4270192960).

While main() runs, sys.stdout and sys.stderr are thin delegates that note a failed write and re-raise it,
so a write that is swallowed (argparse's --help and usage messages, which with `-u` or PYTHONUNBUFFERED fail
inside write() and leave nothing in a buffer for the final flush) still ends with 4, a SystemExit from main()
included (#377 Codex review r4289146735, A #258 6205195908). Every other attribute (buffer, encoding, isatty,
fileno, ...) is the stream's own; an absent stream stays absent; the original streams are put back when main()
ends. Limits: only the text layer's write() and writelines() are noted (a write to the stream's buffer or
descriptor that is swallowed is not, and a swallowed flush() is caught by the final flush, its bytes still
buffered); the delegate is not a context manager or an iterator; a SystemExit with a message, which no adopter
raises, is written by the interpreter after the final flush. No adopter does any of these.
Stdlib only.
"""
from __future__ import annotations

import os
import sys
import traceback

EXIT_INTERNAL = 4   # common.EXIT_INTERNAL (tested); common.py's bytes are pinned, so it is not imported


def _flushed(stream) -> bool:
    """Whether the stream is absent or flushes; one that fails is pointed at /dev/null."""
    if stream is None:
        return True
    try:
        stream.flush()
        return True
    except OSError:
        pass
    devnull = os.open(os.devnull, os.O_WRONLY)
    try:
        os.dup2(devnull, stream.fileno())
    finally:
        os.close(devnull)
    return False


class _Noting:
    """A stream whose failed writes are noted before they propagate; everything else is the stream's own."""

    def __init__(self, stream):
        self._stream = stream
        self.failed = False

    def write(self, text):
        try:
            return self._stream.write(text)
        except OSError:
            self.failed = True
            raise

    def writelines(self, lines):   # through write(), so a failed line is noted too
        for line in lines:
            self.write(line)

    def __getattr__(self, name):
        if name == '_stream':   # an instance built without __init__ (copy, pickle) has none: no recursion
            raise AttributeError(name)
        return getattr(self._stream, name)


def run(main) -> None:
    """Call main() and exit with its code, or with EXIT_INTERNAL when stdout or stderr could not be written."""
    streams = (sys.stdout, sys.stderr)
    noted = [None if stream is None else _Noting(stream) for stream in streams]
    sys.stdout, sys.stderr = (stream if wrapper is None else wrapper for stream, wrapper in zip(streams, noted))
    try:
        code = _call(main)
    finally:
        sys.stdout, sys.stderr = streams
    if any(wrapper is not None and wrapper.failed for wrapper in noted):
        code = EXIT_INTERNAL
    for stream in streams:
        if not _flushed(stream):
            code = EXIT_INTERNAL
    raise SystemExit(code)


def _call(main):
    """main()'s exit code; EXIT_INTERNAL for a broken pipe or any other exception (its traceback printed)."""
    try:
        return main()
    except SystemExit as exit_:   # argparse and require_debug_mode exit from inside main()
        return exit_.code
    except BrokenPipeError:
        return EXIT_INTERNAL
    except Exception:   # an internal error: the traceback the interpreter would print, before the final flush
        try:
            traceback.print_exc()
        except OSError:
            pass   # noted by the stderr delegate
        return EXIT_INTERNAL
