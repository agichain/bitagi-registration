#!/usr/bin/env python3
"""The monitor loop over `bitagi monitor tick` (CT-P5-004-2c-2, B3-04, Claude track).

A #258 issuecomment-6894736990 (Q2c-7, Q2c-8, Q2c-9, Q2c-13 accepted with B's defaults), B's questions
6894080883. The one-shot tick is CT-P5-004-2c-1 (`crates/bitagi-cli/src/monitor_tick.rs`); this loop calls
it, writes the JSONL log of `docs/claude-track/formats/MONITOR_LOG_V1.md` and turns the tick's alarm states
into edges. Unit note: docs/claude-track/plans/notes/CT-P5-001_DRIVER_EN/2026-11-15_p5004-2c2.md.

`run`: every poll (default 120 s, fixed rate on CLOCK_MONOTONIC) it writes the tick request (the template's
members, with `mono_ns` the loop's monotonic reading and `critical_heights` the heights not yet reached),
runs `<bitagi> monitor tick <request>` once and writes one TICK line with the tick's exit and its one JSON
line (or its refusal line). Edges are per episode key: the alarm, the sub-kind (the `kind` of a `sub_kinds`
entry) and, for HEART_NAMED_NOT_CURRENT its `reason` and for STORE_NOT_SYNCED its `standing` and the class
of its `reason` (`EPISODE_KEY_MEMBERS`, `REASON_CLASS`); an alarm raised without sub-kinds has one key,
sub-kind null. ALARM_START when a key appears in a raised alarm (one raised on the first tick starts there),
ALARM_CLEAR when it leaves it or the alarm turns false (`raised` null, that is HEART_NOT_CURRENT or
NOT_MEASURED, changes nothing; so does a sub-kind the tick did not judge, `judged_at`: for example S14 while a
node is not READ, a named Heart behind a store that is not SYNCED; one judged for the first time since the watch
began is not a `B_detect` sample). The loop never reads the tick's `heart.failure`. CRITICAL_HEIGHT is
written the first time both nodes reached a requested critical height, which is then dropped from the next
request. Three failed ticks in a row (any `tick_error`) start the loop's own alarm `MONITOR_TICK_FAILING`; a
checked tick clears it.
It fills the two `B_detect` fields of FBO :282 on the host UTC wall clock: fault start to emission on each
ALARM_START (fault start is a driver's injection mark when one was accepted, else the observation time of the
first tick at which the sub-kind held), emission to acknowledgement on each ALARM_ACK (stamped when the loop
reads the acknowledgement line from its input, a file or stdin; inputs are read every 0.5 s, while the tick
runs too). `mono_ns` orders lines and finds gaps (with CLOCK_BOOTTIME for a suspend); it never measures an
elapsed time. A tick that exits 5 or 6, or 2 before the first checked tick, ends the loop with a STOP line and
that exit; a later exit 2 is a failed tick. Any unexpected error ends with STOP INTERNAL_ERROR; stderr lines
never block (one not written is dropped and counted).

The loop only reads and writes its own log: it calls no command but the tick, opens no network connection,
and holds, releases or signs nothing (alarms only, FBO :123, P5:650).

`check`: reads a log and prints one JSON summary line (order, gaps, suspends, clock steps, alarm starts, the
last line).

Exit codes (AGENTS.md section 12; A Q2c-13): `run` 0 normal stop (`--max-ticks` reached, SIGTERM, SIGINT or
SIGHUP, every stderr line written), 2 bad arguments (before any log line; an existing log path is refused and
left unchanged) or a tick exit 2 before the first checked tick (after the STOP line), 4 a log write failure
(after one attempt at a STOP line), an internal error (STOP INTERNAL_ERROR) or any stop after a stderr line
was dropped (a tick's exit 2, 5 or 6 then stays in STOP `tick_exit`), 5 optimized Python or a tick exit 5, 6 a
tick exit 6; `check` 0 a well-formed log that ends
with STOP, 3 a well-formed log without STOP, 2 one that is not well formed.
Class T development tooling, release authorization NONE. Stdlib only.
"""
from __future__ import annotations

import argparse
import calendar
import errno
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import select
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time

sys.dont_write_bytecode = True

LOG_SCHEMA = 'BITAGI_CT_MONITOR_LOG_V1'
REQUEST_SCHEMA = 'BITAGI_CT_MONITOR_TICK_REQUEST_V1'
RESULT_SCHEMA = 'BITAGI_CT_MONITOR_TICK_RESULT_V1'
REFUSAL_SCHEMA = 'BITAGI_CLASS_T_REFUSAL_V1'
FORMAT_DOC = 'docs/claude-track/formats/MONITOR_LOG_V1.md'
KINDS = ('START', 'TICK', 'ALARM_START', 'ALARM_CLEAR', 'ALARM_ACK', 'CRITICAL_HEIGHT', 'STOP')
CLOCK = 'HOST_UTC_WALL_CLOCK'
LOOP_ALARM = 'MONITOR_TICK_FAILING'   # the loop's own alarm: TICK_FAILING_AFTER failed ticks in a row
LOOP_KEY = (LOOP_ALARM, None, ())
TICK_FAILING_AFTER = 3
DEFAULT_POLL_S = 120           # A Q2c-5
DEFAULT_TICK_TIMEOUT_S = 60
MAX_POLL_S = 3600
MAX_CRITICAL_HEIGHTS = 16      # monitor_tick::MAX_CRITICAL_HEIGHTS
MAX_INPUT_BYTES = 1 << 20      # request template, one tick's stdout or stderr
MAX_INPUT_READ = 1 << 16       # one read of an input (an ack or mark file, or stdin)
MAX_INPUT_LINE = 4096          # one acknowledgement or mark line
WAIT_SLICE_S = 0.5             # how often the inputs are read, while waiting and while a tick runs
GAP_FACTOR = 2                 # a TICK more than 2 polls after the one before is a gap
CLOCK_STEP_S = 5               # UTC and boot-clock elapsed differing by more than 5 s is a clock step
SUSPEND_S = 2                  # CLOCK_BOOTTIME gaining more than 2 s on CLOCK_MONOTONIC between TICKs: a suspend
                               # (A, For A 25: P5-002's SUSPEND value, so the two records agree)
STOP_TICK_EXITS = (2, 5, 6)    # A Q2c-13; a tick exit 2 ends the loop only before the first checked tick
STDERR_WAIT_S = 0.1            # a stderr line not writable within this is dropped and counted
STDERR_WRITE_MIN_S = 0.01      # the shortest bound on one stderr write (after a drop, when `select` waits 0)
STDERR_LINE_MAX = 512          # a longer stderr line is cut
MAX_INPUT_LINES = 64           # ack lines taken per read of the inputs (the rest wait for the next read)
MAX_REFUSED_MARKS = 256        # refused marks listed in STOP and written to stderr (the rest are counted)
STOP_SIGNALS = ('SIGTERM', 'SIGINT', 'SIGHUP')
EXIT_OK, EXIT_ARGS, EXIT_MISSING, EXIT_WRITE, EXIT_SECURITY = 0, 2, 3, 4, 5
UTC_RE = re.compile(r'^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})Z$')
# Matched with `fullmatch` (Codex/A F-5): `$` alone would let one trailing LF through.
TOKEN_RE = re.compile(r'[A-Za-z0-9_.:-]{1,64}')
TICK_ALARM_RE = re.compile(r'AL-[0-9a-z]{1,4}')
ALARM_ID_RE = re.compile(r'AL-[0-9a-z]{1,4}|MONITOR_TICK_FAILING')
SUB_KIND_RE = re.compile(r'[A-Z][A-Z0-9_]{0,63}')
# The members that, with the alarm id and the entry's `kind`, key an episode (format section 5's key table);
# every other kind is keyed by `kind` alone. A change of one of these values is an ALARM_CLEAR of the old
# episode and an ALARM_START of the new one. `reason_class` is not an entry member: it is the class of the
# entry's `reason` (REASON_CLASS).
EPISODE_KEY_MEMBERS = {'HEART_NAMED_NOT_CURRENT': ('reason',), 'STORE_NOT_SYNCED': ('standing', 'reason_class')}
# "Judged at this tick" (format section 5's judgement table, from -2c-1 at its branch head 7fb61dff). A
# sub-kind of a measured alarm is judged at a tick when it has an entry whose values are not in UNJUDGED (a
# judged entry), or when it has no entry at all and no entry of that alarm is of a kind its NOT_JUDGED_WHEN row
# names (a kind outside the table: only with its entry); otherwise it is not judged: its open episodes stay
# open, nothing starts for it and it takes no mark.
SUB_KINDS = {'AL-0a': ('NODE_UNAVAILABLE', 'NODE_CONTEXT_MISMATCH', 'TIP_RACE_NOT_SETTLED', 'NODES_LAG',
                       'S14_HASH_MISMATCH', 'STORE_NOT_SYNCED', 'HEART_NAMED_NOT_CURRENT'),
             'AL-0b': ('TIP_TIMES_UNREAD', 'TIP_TIMES_DISAGREE', 'TIP_CLOCK_UNREADABLE', 'TIP_CLOCK_BEHIND',
                       'TIP_STALE')}
# Entry values that say the sub-kind was not judged: a named Heart behind a store that is not SYNCED is not
# read; a store UNAVAILABLE because of a node (class NODE) was not judged, but only when the same tick's alarm
# shows that node fault (UNJUDGED_ONLY_WITH): then the node sub-kind carries the tick. Without it the entry is
# judged and starts its own (UNAVAILABLE, NODE) episode: the store judge's own node read failed while step 1
# read both nodes, or a block arrived between step 1 and the judge (NODES_DISAGREE, TIP_RACE_NOT_SETTLED after
# its attempts), a one-tick episode that is a sample and can take a store mark. Members are read as
# `key_value` reads them (`reason_class` from `reason`).
UNJUDGED = {'HEART_NAMED_NOT_CURRENT': {'reason': 'STORE_NOT_SYNCED'}, 'STORE_NOT_SYNCED': {'reason_class': 'NODE'}}
UNJUDGED_ONLY_WITH = {'STORE_NOT_SYNCED': ('NODE_UNAVAILABLE', 'NODE_CONTEXT_MISMATCH', 'TIP_RACE_NOT_SETTLED',
                                           'NODES_LAG', 'S14_HASH_MISMATCH')}
# Judged entry values that hold the sub-kind's other open keys open (each member's value one of those listed):
# a store whose state was not read, because of a node (NODE) or because another process had it open or wrote it
# during the read (WRITER, A's decision 17(a)/20a), never clears a SYNCING, STORE or other episode, and does not
# count as judging the store for the first-judged rule.
HOLDS = {'STORE_NOT_SYNCED': {'reason_class': ('NODE', 'WRITER')}}
# The kinds whose presence makes a sub-kind's absence "not compared" rather than "no fault": the tick compares
# no tip race, lag or S14 heights unless both nodes are READ, nor lag or S14 while the tips race; it reads no
# Heart unless the store is SYNCED; 555-a decides the tip age in the order times unread, times disagree, clock
# unreadable, clock behind, then the age, so a state is not decided when an earlier one holds.
_NODES_NOT_READ = ('NODE_UNAVAILABLE', 'NODE_CONTEXT_MISMATCH')
NOT_JUDGED_WHEN = {'TIP_RACE_NOT_SETTLED': _NODES_NOT_READ,
                   'NODES_LAG': _NODES_NOT_READ + ('TIP_RACE_NOT_SETTLED',),
                   'S14_HASH_MISMATCH': _NODES_NOT_READ + ('TIP_RACE_NOT_SETTLED',),
                   'HEART_NAMED_NOT_CURRENT': ('STORE_NOT_SYNCED',),
                   'TIP_TIMES_DISAGREE': ('TIP_TIMES_UNREAD',),
                   'TIP_CLOCK_UNREADABLE': ('TIP_TIMES_UNREAD', 'TIP_TIMES_DISAGREE'),
                   'TIP_CLOCK_BEHIND': ('TIP_TIMES_UNREAD', 'TIP_TIMES_DISAGREE', 'TIP_CLOCK_UNREADABLE'),
                   'TIP_STALE': ('TIP_TIMES_UNREAD', 'TIP_TIMES_DISAGREE', 'TIP_CLOCK_UNREADABLE',
                                 'TIP_CLOCK_BEHIND')}
# STORE_NOT_SYNCED `reason` -> class (format section 5's class table; -2c-1 `read_store` at 7fb61dff): NODE
# when the store was not judged because a node was unusable or on another context (unjudged, above), WRITER
# when another process had the store open or wrote it during the read, STORE for the store's own state. A
# reason not listed is STORE; a null reason (SYNCING) has a null class.
REASON_CLASS = {'NODE_UNAVAILABLE': 'NODE', 'NODE_CONTEXT_MISMATCH': 'NODE', 'NODE_GENESIS_MISMATCH': 'NODE',
                'NODES_DISAGREE': 'NODE', 'TIP_RACE_NOT_SETTLED': 'NODE', 'STORE_DIVERGED': 'STORE',
                'STORE_IN_USE': 'WRITER', 'STORE_WAL_RECOVERY_REQUIRED': 'STORE', 'REPLAY_STATE_ERROR': 'STORE',
                'STORE_CHANGED_DURING_READ': 'WRITER', 'STORE_MISSING': 'STORE'}
# Every kind of the judgement table; a kind outside it is judged only at ticks where it has an entry (F-3).
TABLE_KINDS = frozenset(kind for kinds in SUB_KINDS.values() for kind in kinds)
# Fault start sources that are not a `B_detect` sample: the fault may predate the watch.
NOT_SAMPLES = ('PRESENT_AT_FIRST_TICK', 'PRESENT_WHEN_FIRST_JUDGED')
DEFAULT_REASON_CLASS = 'STORE'


class Refusal(Exception):
    """A bad argument or input, before the log has a line."""

    def __init__(self, code: str, detail: str = ''):
        super().__init__(code)
        self.code, self.detail = code, detail


class LogWriteFailed(Exception):
    """The log could not take a line."""


class TickInvalid(ValueError):
    """The tick's output is not a result the loop can read; `code` says which check failed."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


PARSE_ERRORS = (ValueError, RecursionError)   # what reading untrusted JSON can raise (S-2, S-3)


# ---------------------------------------------------------------------------------------------------------
# Strict JSON (AGENTS.md section 4: no float), UTC text.

def _no_float(text):
    raise ValueError(f'FLOAT {text}')


def _no_constant(text):
    raise ValueError(f'CONSTANT {text}')


def _unique(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError(f'DUPLICATE {key}')
        out[key] = value
    return out


def loads(data: bytes):
    """One JSON value: UTF-8, no float, no NaN or Infinity, no duplicate member. ValueError otherwise."""
    return json.loads(data.decode('utf-8'), parse_float=_no_float, parse_constant=_no_constant,
                      object_pairs_hook=_unique)


def dumps(value) -> bytes:
    return json.dumps(value, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode('ascii')


def is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def rfc3339(seconds: int) -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(seconds))


def parse_utc(text) -> int | None:
    """Whole seconds of an RFC 3339 `YYYY-MM-DDTHH:MM:SSZ` text; None for anything else, an impossible calendar
    value included (month 13, day 32, hour 24, 30 February: `timegm` refuses it or the round trip differs)."""
    if not isinstance(text, str):
        return None
    match = UTC_RE.match(text)
    if match is None:
        return None
    try:
        seconds = calendar.timegm(tuple(int(part) for part in match.groups()) + (0, 0, 0))
        return seconds if rfc3339(seconds) == text else None
    except (ValueError, OverflowError, OSError):
        return None


def is_gap(since_prev_ns: int, poll_s: int) -> bool:
    return since_prev_ns > GAP_FACTOR * poll_s * 1_000_000_000


def key_inputs(kind: str) -> tuple:
    """The entry members a kind's episode key is read from (`reason` for `reason_class`)."""
    return tuple('reason' if member == 'reason_class' else member for member in EPISODE_KEY_MEMBERS.get(kind, ()))


def key_value(entry: dict, member: str):
    if member == 'reason_class':
        reason = entry.get('reason')
        return None if reason is None else REASON_CLASS.get(reason, DEFAULT_REASON_CLASS)
    return entry.get(member)


def episode_key(entry: dict) -> tuple:
    """The key members' (name, value) pairs of one `sub_kinds` entry; empty for a kind keyed by `kind` alone.
    A missing member reads as null."""
    return tuple((member, key_value(entry, member)) for member in EPISODE_KEY_MEMBERS.get(entry['kind'], ()))


def has_values(entry: dict, values) -> bool:
    return values is not None and all(key_value(entry, member) == value for member, value in values.items())


def unjudged(entry: dict, present=()) -> bool:
    """Whether the entry says its sub-kind was not judged at this tick (UNJUDGED), given the kinds `present`
    in its alarm at that tick (UNJUDGED_ONLY_WITH)."""
    only = UNJUDGED_ONLY_WITH.get(entry['kind'])
    return has_values(entry, UNJUDGED.get(entry['kind'])) and (only is None or any(kind in present for kind in only))


def holds(entry: dict) -> bool:
    """Whether a judged entry keeps its sub-kind's other open keys open (HOLDS)."""
    values = HOLDS.get(entry['kind'])
    return values is not None and all(key_value(entry, member) in allowed for member, allowed in values.items())


def judged_at(alarm: dict, kind) -> bool:
    """Whether `kind` (a sub-kind, or None) of this raised alarm is judged at this tick (format section 5): it
    has a judged entry (a judged entry wins over an unjudged one), or it has no entry and no entry of the alarm
    is of a kind its NOT_JUDGED_WHEN row names."""
    entries = [entry for entry in alarm['sub_kinds'] if entry['kind'] == kind]
    present = {entry['kind'] for entry in alarm['sub_kinds']}
    if any(not unjudged(entry, present) for entry in entries):
        return True
    if not entries and kind is not None and kind not in TABLE_KINDS:
        return False   # a kind outside the table: judged only with its entry
    return not entries and not any(entry['kind'] in NOT_JUDGED_WHEN.get(kind, ()) for entry in alarm['sub_kinds'])


def utc_drift_s(utc_delta_s: int, mono_delta_ns: int) -> int:
    """UTC elapsed minus monotonic elapsed, whole seconds (monotonic rounded to the nearest second)."""
    return utc_delta_s - (mono_delta_ns + 500_000_000) // 1_000_000_000


# ---------------------------------------------------------------------------------------------------------
# The host: clocks, the pause, the tick process. Tests replace the clocks and the pause.


class StderrWriteLate(Exception):
    """A bounded stderr write that waited past its bound."""


_ALARM_ARMED = [False]


def _on_alarm(_number, _frame) -> None:
    if _ALARM_ARMED[0]:   # a timer that fires after its write returned is ignored
        raise StderrWriteLate()


def bounded_write(fd: int, data: bytes, bound_s: float) -> int:
    """`os.write` that a one-shot SIGALRM timer interrupts after `bound_s` (main thread only). An interrupted
    write raises StderrWriteLate, also when the timer fires just after the write (the line counts as dropped)."""
    if signal.getsignal(signal.SIGALRM) is not _on_alarm:
        signal.signal(signal.SIGALRM, _on_alarm)
    signal.pthread_sigmask(signal.SIG_UNBLOCK, [signal.SIGALRM])
    try:
        _ALARM_ARMED[0] = True
        signal.setitimer(signal.ITIMER_REAL, bound_s)
        return os.write(fd, data)
    finally:
        _ALARM_ARMED[0] = False
        signal.setitimer(signal.ITIMER_REAL, 0)

class Host:
    def mono_ns(self) -> int:
        return time.clock_gettime_ns(time.CLOCK_MONOTONIC)

    def utc_s(self) -> int:
        return time.time_ns() // 1_000_000_000

    def boot_ns(self) -> int | None:
        """CLOCK_BOOTTIME (counts a suspend, which CLOCK_MONOTONIC does not), or None where there is none."""
        try:
            return time.clock_gettime_ns(time.CLOCK_BOOTTIME)
        except (AttributeError, OSError):
            return None

    def write_stderr(self, data: bytes, wait_s: float = STDERR_WAIT_S) -> bool:
        """One stderr line without blocking for long (S-1): written only when fd 2 takes it within `wait_s`;
        False when it was not written whole (a stopped terminal, a pipe nobody reads, a closed stream). The
        write itself is bounded by a SIGALRM timer, not by a `select` before it: another writer sharing the
        pipe can fill it after a `select` saw room (Desktop 6906749844). fd 2 is never set non-blocking: its
        open file description is shared with those writers."""
        try:
            info = os.fstat(2)
            if (info.st_dev, info.st_ino) == getattr(self, 'log_identity', None):
                return False   # fd 2 is the log itself: never write stderr text into it
            return bounded_write(2, data, max(wait_s, STDERR_WRITE_MIN_S)) == len(data)
        except (OSError, ValueError, StderrWriteLate):
            return False

    def pause(self, seconds: float) -> None:
        time.sleep(seconds)

    def run_tick(self, argv: list[str], timeout_s: int, work: Path, on_slice):
        """(returncode, stdout, stderr, error). The tick writes into two files in `work`; every WAIT_SLICE_S
        while it runs `on_slice()` is called and the files' sizes are checked. error: `TICK_SPAWN_FAILED`,
        `TICK_TIMEOUT` or `TICK_OUTPUT_TOO_LARGE` (the process group killed; returncode None), else None."""
        out_path, err_path = work / 'tick.stdout', work / 'tick.stderr'
        try:
            with open(out_path, 'wb') as out, open(err_path, 'wb') as err:
                process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                           start_new_session=True)
        except OSError:
            return None, b'', b'', 'TICK_SPAWN_FAILED'
        deadline = time.monotonic() + timeout_s
        try:
            while True:
                try:
                    code = process.wait(timeout=WAIT_SLICE_S)
                    break
                except subprocess.TimeoutExpired:
                    pass
                on_slice()
                if process.poll() is not None:   # it ended while the inputs were read: no timeout
                    code = process.returncode
                    break
                try:
                    size = max(out_path.stat().st_size, err_path.stat().st_size)
                except OSError:
                    return None, b'', b'', 'TICK_OUTPUT_LOST'   # the files or the folder were removed (S-4)
                if size > MAX_INPUT_BYTES:
                    return None, b'', b'', 'TICK_OUTPUT_TOO_LARGE'
                if time.monotonic() >= deadline:
                    return None, b'', b'', 'TICK_TIMEOUT'
        finally:
            if process.returncode is None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except OSError:
                    pass
                process.wait()
        try:
            with open(out_path, 'rb') as out, open(err_path, 'rb') as err:
                stdout, stderr = out.read(MAX_INPUT_BYTES + 1), err.read(MAX_INPUT_BYTES + 1)
        except OSError:
            return code, b'', b'', 'TICK_OUTPUT_LOST'
        if max(len(stdout), len(stderr)) > MAX_INPUT_BYTES:
            return code, b'', b'', 'TICK_OUTPUT_TOO_LARGE'
        return code, stdout, stderr, None


class FileLines:
    """Complete lines appended to a file, read from where the last read ended. A missing file has none yet;
    one that cannot be read (a folder, no permission) has none and sets `error` until it can be read again."""

    def __init__(self, path: Path):
        self.path, self.offset, self.partial, self.error = path, 0, b'', None
        self.discarding = False   # inside a line already refused as too long, until its LF
        self.start_size = 0       # the file's size at START: its lines up to there were there before the loop
        self.early = False        # the last read was of those bytes only

    def poll(self) -> list[bytes]:
        try:
            fd = os.open(self.path, os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC)   # a FIFO never blocks the open
        except FileNotFoundError:
            self.error = None
            return []
        except OSError as error:
            self.error = errno.errorcode.get(error.errno, 'OSError')
            return []
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                self.error = 'NOT_A_REGULAR_FILE'   # a FIFO, a device or a folder is never read (S-7)
                return []
            os.lseek(fd, self.offset, os.SEEK_SET)
            self.early = self.offset < self.start_size   # a read never crosses the START size
            data = os.read(fd, min(MAX_INPUT_READ, self.start_size - self.offset) if self.early else MAX_INPUT_READ)
        except OSError as error:
            self.error = errno.errorcode.get(error.errno, 'OSError')
            return []
        finally:
            os.close(fd)
        self.error = None
        self.offset += len(data)
        return split_lines(self, data)


class StdinLines:
    """Complete lines on standard input, read without blocking; EOF or a read error ends the input, not the
    loop (a read error also sets `error`)."""

    def __init__(self, fd: int = 0):
        self.fd, self.partial, self.closed, self.error = fd, b'', False, None
        self.discarding = False   # inside a line already refused as too long, until its LF

    def poll(self) -> list[bytes]:
        """At most MAX_INPUT_READ read per call, as for a file, so a flood on stdin never holds the loop."""
        lines, read = [], 0
        try:
            while not self.closed and read < MAX_INPUT_READ and select.select([self.fd], [], [], 0)[0]:
                data = os.read(self.fd, MAX_INPUT_READ - read)
                if not data:
                    self.closed = True
                    break
                read += len(data)
                lines += split_lines(self, data)
        except (OSError, ValueError) as error:
            self.closed = True
            self.error = errno.errorcode.get(getattr(error, 'errno', None), 'OSError')
        return lines


def split_lines(source, data: bytes) -> list[bytes]:
    """The complete lines of `data` after what `source` holds. A line longer than MAX_INPUT_LINE is given once,
    as soon as that much of it is read without an LF (so it is refused as too long); every byte up to and
    including its LF, over any number of reads, belongs to that refused line and is dropped."""
    *lines, rest = (source.partial + data).split(b'\n')
    if source.discarding and lines:
        lines.pop(0)                   # the end of the refused line
        source.discarding = False
    if source.discarding:
        rest = b''                     # still inside the refused line
    elif len(rest) > MAX_INPUT_LINE:
        lines.append(rest)             # refused as too long, once
        rest, source.discarding = b'', True
    source.partial = rest
    return lines


# ---------------------------------------------------------------------------------------------------------
# The log.

class Log:
    """The new log file: created exclusively, appended line by line, each line written whole and fsynced."""

    def __init__(self, path: Path, host: Host):
        self.path, self.host, self.seq, self.size = path, host, 0, 0
        raw = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_APPEND | os.O_CLOEXEC, 0o600)
        try:
            self.fd = fcntl.fcntl(raw, fcntl.F_DUPFD_CLOEXEC, 3)   # never fd 0, 1 or 2 (a closed stdio)
        except OSError:
            made = os.fstat(raw)
            try:
                now = os.lstat(path)
                if (now.st_dev, now.st_ino) == (made.st_dev, made.st_ino):
                    os.unlink(path)   # the empty file this run created: a refused start leaves no log
            except OSError:
                pass
            raise
        finally:
            os.close(raw)
        info = os.fstat(self.fd)
        host.log_identity = (info.st_dev, info.st_ino)   # stderr text never goes into the log
        try:
            folder = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(folder)
            finally:
                os.close(folder)
        except OSError:
            pass   # the folder's fsync is best effort; the line writes are not

    def write(self, kind: str, fields: dict, utc_s: int | None = None, mono_ns: int | None = None,
              sync: bool = True) -> dict:
        """Append one line. `utc_s` and `mono_ns` are the line's clock readings when the caller took them (an
        emission, a TICK's interval), else they are read now. `sync` False (the lines taken at a stop) leaves
        the fsync to the STOP line's, which covers every line before it."""
        mono_ns = self.host.mono_ns() if mono_ns is None else mono_ns
        line = {'schema': LOG_SCHEMA, 'seq': self.seq, 'mono_ns': mono_ns,
                'utc': rfc3339(self.host.utc_s() if utc_s is None else utc_s), 'kind': kind, **fields}
        data = dumps(line) + b'\n'
        try:
            view = memoryview(data)
            while view:
                view = view[os.write(self.fd, view):]
            if sync:
                os.fsync(self.fd)
        except OSError as error:
            raise LogWriteFailed(str(error)) from error
        self.seq += 1
        self.size += len(data)
        return line

    def drop_partial(self) -> None:
        """Cut a line a failed write left half written, so the file ends with whole lines."""
        try:
            os.ftruncate(self.fd, self.size)
        except OSError:
            pass

    def close(self) -> None:
        try:
            os.close(self.fd)
        except OSError:
            pass


# ---------------------------------------------------------------------------------------------------------
# One tick.

def read_template(path: Path) -> tuple[dict, bytes]:
    try:
        with open(path, 'rb') as stream:
            data = stream.read(MAX_INPUT_BYTES + 1)
    except OSError as error:
        raise Refusal('REQUEST_UNREADABLE', type(error).__name__) from error
    if len(data) > MAX_INPUT_BYTES:
        raise Refusal('REQUEST_TOO_LARGE')
    try:
        template = loads(data)
    except PARSE_ERRORS as error:
        raise Refusal('REQUEST_NOT_JSON', str(error)[:80]) from error
    if not isinstance(template, dict) or template.get('schema') != REQUEST_SCHEMA:
        raise Refusal('REQUEST_SCHEMA')
    critical = template.get('critical_heights')
    if (not isinstance(critical, list) or len(critical) > MAX_CRITICAL_HEIGHTS
            or not all(is_int(height) and height >= 0 for height in critical)
            or any(a >= b for a, b in zip(critical, critical[1:]))):
        raise Refusal('REQUEST_CRITICAL_HEIGHTS')
    return template, data


def check_tick(stdout: bytes, mono_ns: int) -> dict:
    """The tick's one result line, checked for what the loop reads. TickInvalid (its code) otherwise."""
    if not stdout.endswith(b'\n') or stdout.count(b'\n') != 1:
        raise TickInvalid('ONE_LINE')
    try:
        tick = loads(stdout[:-1])
    except PARSE_ERRORS as error:   # not strict JSON, or nested too deeply to read (S-2)
        raise TickInvalid('NOT_JSON') from error
    if not isinstance(tick, dict) or tick.get('schema') != RESULT_SCHEMA:
        raise TickInvalid('SCHEMA')
    clock = tick.get('clock')
    if not isinstance(clock, dict) or clock.get('mono_ns') != mono_ns:
        raise TickInvalid('MONO_NS_ECHO')
    if clock.get('utc') is not None and parse_utc(clock.get('utc')) is None:
        raise TickInvalid('CLOCK_UTC')
    alarms = tick.get('alarms')
    if not isinstance(alarms, list) or not alarms:
        raise TickInvalid('ALARMS')
    seen = set()
    for alarm in alarms:
        if (not isinstance(alarm, dict) or not isinstance(alarm.get('id'), str)
                or not TICK_ALARM_RE.fullmatch(alarm['id']) or alarm['id'] in seen
                or not (alarm.get('raised') is None or isinstance(alarm.get('raised'), bool))
                or not isinstance(alarm.get('sub_kinds'), list)
                or not all(isinstance(entry, dict) and isinstance(entry.get('kind'), str)
                           and SUB_KIND_RE.fullmatch(entry['kind'])
                           and all(entry.get(member) is None or isinstance(entry.get(member), str)
                                   for member in key_inputs(entry['kind']))
                           for entry in alarm['sub_kinds'])):
            raise TickInvalid('ALARM')
        seen.add(alarm['id'])
    reached = tick['critical_heights'].get('reached') if isinstance(tick.get('critical_heights'), dict) else None
    if not isinstance(reached, list) or not all(
            isinstance(row, dict) and is_int(row.get('height')) and isinstance(row.get('equal'), bool)
            and isinstance(row.get('hash_a_display'), str) and isinstance(row.get('hash_b_display'), str)
            for row in reached):
        raise TickInvalid('CRITICAL_HEIGHTS')
    if not isinstance(tick.get('countdown'), dict) or not isinstance(tick['countdown'].get('status'), str):
        raise TickInvalid('COUNTDOWN')
    return tick


def refusal_line(stderr: bytes):
    """The tick's refusal object when its stderr is exactly one refusal line; None otherwise (never the text)."""
    try:
        value = loads(stderr.rstrip(b'\n')) if stderr.count(b'\n') <= 1 else None
    except PARSE_ERRORS:
        return None
    return value if isinstance(value, dict) and value.get('schema_version') == REFUSAL_SCHEMA else None


# ---------------------------------------------------------------------------------------------------------
# The loop.

class Loop:
    def __init__(self, args, host: Host, acks=None, marks=None):
        self.args, self.host = args, host
        self.inputs = {name: source for name, source in (('mark', marks), ('ack', acks)) if source is not None}
        self.input_errors = {name: 0 for name in self.inputs}
        self.stop_requested = None          # a signal name once asked to stop
        self.pending: list[int] = []
        self.open: dict[tuple, int] = {}    # episode key (alarm id, sub-kind or None, key pairs) -> start seq
        self.last_clear_s: dict[tuple, int] = {}
        self.episodes: dict[int, dict] = {}
        self.waiting_marks: list[dict] = []
        self.refused_marks: list[dict] = []
        self.refused_total = 0              # every refused mark, listed or not
        self.stderr_blocked = False         # the last stderr line was dropped: the next one does not wait
        self.ticks = self.failed_ticks = self.failing_run = 0
        self.failing_since_s = None
        self.observed = 0                   # ticks with a checked result
        self.alarm_ids: set = set()         # alarm ids a checked tick has reported (a mark names one of them)
        self.judged_once: set = set()       # (alarm id, sub-kind) judged at an earlier checked tick
        self.prev_tick = None               # (mono_ns, utc_s, boot minus mono or None) of the last TICK line
        self.stderr_dropped = 0             # stderr lines not written (S-1)
        self.backlog: dict = {}             # input lines read and not yet taken, per input
        self.work_unusable = False          # the work folder refused the last request write
        self.work: Path | None = None
        self.log: Log | None = None

    # -- inputs -------------------------------------------------------------------------------------------

    def read_inputs(self, final: bool = False) -> None:
        """Each input's new lines. An input is read (at most MAX_INPUT_READ) only when its backlog is empty.
        Every mark line is taken at its read, so it is judged by the loop's state at that read (it writes no log
        line). Each ack line keeps the host UTC and the log's next `seq` of its read, which is all its judgement
        reads (an episode is about it only if its ALARM_START came before that `seq`; acknowledgements change
        only by acks, taken in order). While the loop runs, at most MAX_INPUT_LINES ack lines are taken per call
        and the rest wait in the backlog; at a stop (`final`) every line read is taken, without an fsync per
        line (STOP's covers them): at most one MAX_INPUT_READ read per input."""
        for name, source in self.inputs.items():
            backlog = self.backlog.setdefault(name, [])
            if not backlog:
                was = source.error
                lines = source.poll()
                read_s, read_seq = self.host.utc_s(), self.log.seq
                if getattr(source, 'early', False):
                    read_seq = 1   # in the file at START: read as if right after it (an ack matches nothing)
                backlog += [(line, read_s, read_seq) for line in lines]
                if source.error != was:
                    if source.error is not None:
                        self.input_errors[name] += 1
                        self.say(f'INPUT_UNREADABLE {name} {source.error}: lines are not read until it can be read')
                    else:
                        self.say(f'INPUT_READABLE {name}')
            take = len(backlog) if final or name == 'mark' else min(len(backlog), MAX_INPUT_LINES)
            for _ in range(take):
                line, read_s, read_seq = backlog.pop(0)
                if name == 'mark':
                    self.take_mark(line, read_s, before_first_tick=read_seq == 1)
                else:
                    self.take_ack(line, read_s, read_seq, sync=not final)

    def matching(self, keys, alarm_id: str, sub_kind) -> list[tuple]:
        """The episode keys of `alarm_id` that a mark or acknowledgement naming `sub_kind` (None: any) is
        about, whatever their key members."""
        return [key for key in keys if key[0] == alarm_id and (sub_kind is None or key[1] == sub_kind)]

    def take_mark(self, line: bytes, received_s: int, before_first_tick: bool = False) -> None:
        """A driver's injection mark `{"alarm_id", "fault_start_utc"[, "sub_kind"]}` for the next start."""
        mark = None
        if len(line) <= MAX_INPUT_LINE:
            try:
                mark = loads(line)
            except PARSE_ERRORS:   # a line nested too deeply too (S-3)
                mark = None
        record = {'alarm_id': None, 'sub_kind': None, 'fault_start_utc': None, 'received_utc': rfc3339(received_s),
                  'mark_refused': None}
        if not (isinstance(mark, dict) and {'alarm_id', 'fault_start_utc'} <= set(mark)
                and set(mark) <= {'alarm_id', 'fault_start_utc', 'sub_kind'}
                and isinstance(mark['alarm_id'], str) and ALARM_ID_RE.fullmatch(mark['alarm_id'])
                and (mark.get('sub_kind') is None or (isinstance(mark['sub_kind'], str)
                                                      and SUB_KIND_RE.fullmatch(mark['sub_kind'])))
                and parse_utc(mark['fault_start_utc']) is not None):
            self.refuse_mark(record, 'MARK_MALFORMED')
            return
        record.update(alarm_id=mark['alarm_id'], sub_kind=mark.get('sub_kind'),
                      fault_start_utc=mark['fault_start_utc'])
        fault_s = parse_utc(mark['fault_start_utc'])
        keys = self.matching(self.last_clear_s, record['alarm_id'], record['sub_kind'])
        cleared = [self.last_clear_s[key] for key in keys]
        if self.observed == 0 or before_first_tick:
            self.refuse_mark(record, 'MARK_BEFORE_FIRST_TICK')
        elif record['alarm_id'] not in self.alarm_ids:
            self.refuse_mark(record, 'MARK_UNKNOWN_ALARM')   # so waiting marks stay bounded by what ticks report
        elif record['sub_kind'] is not None and record['sub_kind'] not in SUB_KINDS.get(record['alarm_id'], ()):
            self.refuse_mark(record, 'MARK_UNKNOWN_SUB_KIND')
        elif self.matching(self.open, record['alarm_id'], record['sub_kind']):
            self.refuse_mark(record, 'MARK_WHILE_OPEN')
        elif cleared and fault_s < max(cleared):
            self.refuse_mark(record, 'MARK_BEFORE_LAST_CLEAR')
        elif any(None in (mark['sub_kind'], record['sub_kind']) or mark['sub_kind'] == record['sub_kind']
                 for mark in self.waiting_marks if mark['alarm_id'] == record['alarm_id']):
            self.refuse_mark(record, 'MARK_WHILE_WAITING')   # no two waiting marks one start could take (F-6)
        else:
            self.waiting_marks.append(dict(record, fault_s=fault_s))

    def refuse_mark(self, record: dict, reason: str) -> None:
        """The first MAX_REFUSED_MARKS refusals are listed and get a stderr line; every one is counted."""
        record['mark_refused'] = reason
        self.refused_total += 1
        if len(self.refused_marks) < MAX_REFUSED_MARKS:
            self.refused_marks.append(record)
            self.say(f'MARK_REFUSED {reason} {record["alarm_id"]} {record["sub_kind"]}')

    def take_ack(self, line: bytes, received_s: int, read_seq: int | None = None, sync: bool = True) -> None:
        """One acknowledgement line, stamped `received_s` (when it was read). It can only be about an episode
        whose ALARM_START was in the log when it was read (`seq` below `read_seq`)."""
        fields = {'alarm_id': None, 'sub_kind': None, 'asked_sub_kind': None, 'asked_start_seq': None,
                  'start_seq': None, 'acknowledgment_utc': rfc3339(received_s), 'emission_utc': None,
                  'emission_to_acknowledgment_s': None, 'channel': None, 'channel_utc': None, 'clock': CLOCK,
                  'accepted': False, 'refusal': None}
        ack = None
        if len(line) <= MAX_INPUT_LINE:
            try:
                ack = loads(line)
            except PARSE_ERRORS:   # a line nested too deeply too (S-3)
                ack = None
        if not (isinstance(ack, dict) and 'alarm_id' in ack
                and set(ack) <= {'alarm_id', 'sub_kind', 'start_seq', 'channel', 'channel_utc'}
                and isinstance(ack['alarm_id'], str) and ALARM_ID_RE.fullmatch(ack['alarm_id'])
                and (ack.get('sub_kind') is None or (isinstance(ack['sub_kind'], str)
                                                     and SUB_KIND_RE.fullmatch(ack['sub_kind'])))
                and (ack.get('start_seq') is None or is_int(ack['start_seq']))
                and (ack.get('channel') is None or (isinstance(ack['channel'], str)
                                                    and TOKEN_RE.fullmatch(ack['channel'])))
                and (ack.get('channel_utc') is None or parse_utc(ack['channel_utc']) is not None)):
            fields['refusal'] = 'ACK_MALFORMED'
            self.log.write('ALARM_ACK', fields, sync=sync)
            return
        asked = ack.get('sub_kind')
        fields.update(alarm_id=ack['alarm_id'], asked_sub_kind=asked, asked_start_seq=ack.get('start_seq'),
                      channel=ack.get('channel'), channel_utc=ack.get('channel_utc'))
        if ack.get('start_seq') is not None:
            episode = self.episodes.get(ack['start_seq'])
            if episode is not None and read_seq is not None and episode['start_seq'] >= read_seq:
                episode = None   # its ALARM_START was written after the line was read
            if episode is None or episode['alarm_id'] != ack['alarm_id'] or asked not in (None, episode['sub_kind']):
                fields['refusal'] = 'START_SEQ_UNKNOWN'
            elif episode['ack_seq'] is not None:
                fields['refusal'] = 'ALREADY_ACKNOWLEDGED'
        else:
            unacked = [seq for seq, ep in self.episodes.items() if ep['ack_seq'] is None
                       and (read_seq is None or seq < read_seq) and self.matching([ep['key']], ack['alarm_id'], asked)]
            episode = self.episodes[max(unacked)] if unacked else None
            if episode is None:
                fields['refusal'] = 'NO_UNACKNOWLEDGED_ALARM'
        if fields['refusal'] is None:
            leg = received_s - episode['emission_utc_s']
            fields.update(sub_kind=episode['sub_kind'], start_seq=episode['start_seq'],
                          emission_utc=rfc3339(episode['emission_utc_s']), emission_to_acknowledgment_s=leg,
                          accepted=True)
            line_out = self.log.write('ALARM_ACK', fields, sync=sync)
            episode.update(ack_seq=line_out['seq'], emission_to_acknowledgment_s=leg)
        else:
            self.log.write('ALARM_ACK', fields, sync=sync)

    # -- one tick -----------------------------------------------------------------------------------------

    def ensure_work(self) -> Path:
        """The tick request's path in the work folder; a removed folder is made again, by a new name (S-4)."""
        if not self.work.is_dir() or self.work_unusable:
            old, self.work = self.work, Path(tempfile.mkdtemp(prefix='claude-track-monitor-'))
            self.work_unusable = False
            shutil.rmtree(old, ignore_errors=True)
            self.say(f'WORK_FOLDER_RECREATED {self.work.name}')
        return self.work / 'tick_request.json'

    def tick(self, template: dict) -> int | None:
        """One poll. The tick's exit when it ends the loop, else None."""
        mono_ns = self.host.mono_ns()
        request = dict(template, mono_ns=mono_ns, critical_heights=list(self.pending))
        data = dumps(request)
        try:
            request_path = self.ensure_work()
            partial = request_path.with_name(request_path.name + '.part')
            with open(partial, 'wb') as stream:
                stream.write(data)
            os.replace(partial, request_path)
        except OSError:
            self.work_unusable = True   # the next tick makes a new folder (it may have lost its permissions)
            code, stdout, stderr, error = None, b'', b'', 'REQUEST_WRITE_FAILED'
        else:
            code, stdout, stderr, error = self.host.run_tick(
                [self.args.bitagi, 'monitor', 'tick', str(request_path)], self.args.tick_timeout_s, self.work,
                self.read_inputs)
        tick, refusal, reason = None, None, None
        if error is not None:
            pass
        elif code < 0:
            error, code = 'TICK_KILLED_BY_SIGNAL', None
        elif code == 0:
            try:
                tick = check_tick(stdout, mono_ns)
            except TickInvalid as invalid:
                error, reason = 'TICK_OUTPUT_INVALID', invalid.code
        else:
            error, refusal = 'TICK_REFUSED', refusal_line(stderr)
        now_mono, now_utc, now_boot = self.host.mono_ns(), self.host.utc_s(), self.host.boot_ns()
        offset = None if now_boot is None else now_boot - now_mono   # what the boot clock counted beyond mono
        since, gap, drift, step, suspended, suspend = None, False, None, False, None, False
        if self.prev_tick is not None:
            since = now_mono - self.prev_tick[0]
            if offset is not None and self.prev_tick[2] is not None:
                suspended = max(0, offset - self.prev_tick[2])
                suspend = suspended > SUSPEND_S * 1_000_000_000
            elapsed = since + (suspended or 0)   # host time between the TICKs, a suspend included (S-9)
            gap = is_gap(elapsed, self.args.poll_s)
            drift = utc_drift_s(now_utc - self.prev_tick[1], elapsed)
            step = abs(drift) > CLOCK_STEP_S
        self.prev_tick = (now_mono, now_utc, offset)
        clock = tick['clock'] if tick else {}
        line = self.log.write('TICK', {
            'tick_index': self.ticks, 'tick_exit': code, 'tick_error': error, 'tick_error_reason': reason,
            'request_sha256': hashlib.sha256(data).hexdigest(), 'request_mono_ns': mono_ns,
            'critical_heights_requested': request['critical_heights'],
            'tick_utc': clock.get('utc'), 'countdown_status': tick['countdown']['status'] if tick else None,
            'since_prev_tick_mono_ns': since, 'suspended_ns': suspended, 'suspend': suspend, 'gap': gap,
            'utc_drift_s': drift, 'clock_step': step, 'tick': tick, 'refusal': refusal},
            utc_s=now_utc, mono_ns=now_mono)
        if suspend:
            self.say(f'SUSPEND {suspended // 1_000_000_000} s before seq={line["seq"]}')
        self.ticks += 1
        if tick is not None:
            self.failing_run = 0
            if LOOP_KEY in self.open:
                self.clear(LOOP_KEY, LOOP_ALARM, line['seq'])
            observed_s = parse_utc(clock.get('utc'))
            self.edges(tick, line, now_utc if observed_s is None else observed_s)
            self.critical(tick, line['seq'])
            self.observed += 1
            self.alarm_ids.update(alarm['id'] for alarm in tick['alarms'])
        else:
            self.failed(error, code, line)
        if code in STOP_TICK_EXITS and (code != 2 or self.observed == 0):
            return code   # an exit 2 after a checked tick is a failed tick (A's decision 8, F-2)
        return None

    def failed(self, error: str, code, line: dict) -> None:
        """A tick without a checked result: a stderr line, the count, and the loop's alarm after
        TICK_FAILING_AFTER in a row (fault start: the first of them)."""
        self.failed_ticks += 1
        self.failing_run += 1
        if self.failing_run == 1:
            self.failing_since_s = parse_utc(line['utc'])
        self.say(f'TICK_FAILED {error} tick_exit={code} seq={line["seq"]} in_a_row={self.failing_run}')
        if self.failing_run >= TICK_FAILING_AFTER and LOOP_KEY not in self.open:
            self.start(LOOP_KEY, LOOP_ALARM, [], line['seq'], self.failing_since_s, False, 'FIRST_FAILED_TICK')

    def edges(self, tick: dict, tick_line: dict, held_s: int) -> None:
        """Per episode key (alarm id, sub-kind, key members): for each alarm in the tick's order, its clears
        first (an open episode whose key left a raised alarm, or every open one of a false alarm), in the order
        the episodes started, then its starts (a key of a raised alarm not open yet), in the order each key
        first appears in `sub_kinds`. `raised` null changes nothing. A start that takes no waiting mark at a
        tick where another start takes one is not a `B_detect` sample (format section 5). A sub-kind not judged
        at this tick (`judged_at`) keeps its open episodes open and starts nothing; a holding entry (HOLDS)
        starts its own key and keeps the sub-kind's other open keys open; a sub-kind judged for the first time
        since the watch began starts as PRESENT_WHEN_FIRST_JUDGED, not a sample."""
        first = self.observed == 0
        plan, judged = [], set()
        for alarm in tick['alarms']:
            alarm_id, raised = alarm['id'], alarm['raised']
            if raised is None:
                continue
            now: dict = {}
            held = set()   # sub-kinds not judged at this tick
            hold = set()   # sub-kinds whose judged entries all hold the other open keys open (HOLDS)
            present = {entry['kind'] for entry in alarm['sub_kinds']}
            kinds = set(SUB_KINDS.get(alarm_id, ())) | {entry['kind'] for entry in alarm['sub_kinds']} | {None}
            kinds |= {key[1] for key in self.open if key[0] == alarm_id}   # an open kind outside the table (F-3)
            if raised:
                held = {kind for kind in kinds if not judged_at(alarm, kind)}
                plain = set()
                for entry in alarm['sub_kinds']:
                    if unjudged(entry, present):
                        continue
                    (hold if holds(entry) else plain).add(entry['kind'])
                    now.setdefault((alarm_id, entry['kind'], episode_key(entry)), []).append(entry)
                hold -= plain
                if not alarm['sub_kinds']:
                    now[(alarm_id, None, ())] = []
            judged |= {(alarm_id, kind) for kind in kinds - held - hold
                       if kind is None or kind in TABLE_KINDS or kind in present}   # outside: only with its entry
            clears = [key for key in self.open if key[0] == alarm_id and key not in now and key[1] not in held]
            clears = [key for key in clears if key[1] not in hold]
            starts = [(key, entries) for key, entries in now.items() if key not in self.open]
            plan.append((alarm.get('name'), clears, starts))
        waiting, marked = list(self.waiting_marks), []
        for _, _, starts in plan:
            for key, _ in starts:
                mark = self.mark_for(key, waiting)
                if mark is not None:
                    waiting.remove(mark)
                    marked.append(key)
        for name, clears, starts in plan:
            for key in clears:
                self.clear(key, name, tick_line['seq'])
            for key, entries in starts:
                beside = bool(marked) and key not in marked
                source = ('PRESENT_AT_FIRST_TICK' if first else 'PRESENT_WHEN_FIRST_JUDGED'
                          if key[:2] not in self.judged_once else 'FIRST_TICK_HELD')
                self.start(key, name, entries, tick_line['seq'], held_s, first, source, beside)
        self.judged_once |= judged

    def mark_for(self, key: tuple, marks: list):
        """The first of `marks` that names this episode's alarm and, when it names one, its sub-kind."""
        return next((mark for mark in marks if self.matching([key], mark['alarm_id'], mark['sub_kind'])), None)

    def clear(self, key: tuple, name, tick_seq: int) -> None:
        start_seq = self.open.pop(key)
        line = self.log.write('ALARM_CLEAR', {'alarm_id': key[0], 'sub_kind': key[1], 'episode_key': dict(key[2]),
                                              'name': name, 'tick_seq': tick_seq, 'start_seq': start_seq})
        self.last_clear_s[key] = parse_utc(line['utc'])
        self.episodes[start_seq]['clear_seq'] = line['seq']
        self.say(f'ALARM_CLEAR {key[0]} {key[1]} seq={line["seq"]} start_seq={start_seq}')

    def start(self, key: tuple, name, entries: list, tick_seq: int, held_s: int, first: bool, source: str,
              beside: bool = False) -> None:
        alarm_id, sub_kind, pairs = key
        emission_s = self.host.utc_s()
        mark_refused, fault_s = None, held_s
        mark = self.mark_for(key, self.waiting_marks)
        if mark is not None:
            self.waiting_marks.remove(mark)
            if mark['fault_s'] <= emission_s:
                source, fault_s = 'INJECTION_MARK', mark['fault_s']
            else:
                mark_refused = 'MARK_AFTER_EMISSION'
                self.refuse_mark({key: value for key, value in mark.items() if key != 'fault_s'}, mark_refused)
        misconfiguration = None
        if first and alarm_id == 'AL-0a' and sub_kind == 'NODE_CONTEXT_MISMATCH':
            misconfiguration = 'NODE_CONTEXT_MISMATCH_ON_FIRST_TICK'
        leg = emission_s - fault_s
        sample = source not in NOT_SAMPLES and not beside
        line = self.log.write('ALARM_START', {
            'alarm_id': alarm_id, 'sub_kind': sub_kind, 'episode_key': dict(pairs), 'name': name,
            'sub_kind_entries': entries, 'tick_seq': tick_seq, 'first_tick': first,
            'misconfiguration': misconfiguration, 'clock': CLOCK, 'fault_start_utc': rfc3339(fault_s),
            'fault_start_source': source, 'mark_refused': mark_refused, 'emission_utc': rfc3339(emission_s),
            'fault_to_emission_s': leg, 'b_detect_sample': sample}, utc_s=emission_s)
        self.open[key] = line['seq']
        self.episodes[line['seq']] = {'alarm_id': alarm_id, 'sub_kind': sub_kind, 'episode_key': dict(pairs),
                                      'start_seq': line['seq'], 'clear_seq': None, 'ack_seq': None,
                                      'emission_utc_s': emission_s, 'key': key, 'fault_start_source': source,
                                      'fault_to_emission_s': leg, 'b_detect_sample': sample,
                                      'emission_to_acknowledgment_s': None}
        self.say(f'ALARM_START {alarm_id} {sub_kind} seq={line["seq"]}')
        if misconfiguration:
            self.say(f'misconfiguration: {misconfiguration}: a node is on another context at the first tick')

    def critical(self, tick: dict, tick_seq: int) -> None:
        for row in tick['critical_heights']['reached']:
            if row['height'] in self.pending:
                self.pending.remove(row['height'])
                self.log.write('CRITICAL_HEIGHT', {
                    'height': row['height'], 'hash_a_display': row['hash_a_display'],
                    'hash_b_display': row['hash_b_display'], 'equal': row['equal'], 'tick_seq': tick_seq})
                self.say(f'CRITICAL_HEIGHT {row["height"]} equal={str(row["equal"]).lower()}')

    def say(self, text: str) -> None:
        """One line on stderr for a person watching, never blocking for long: a line that is not written is
        dropped and counted (STOP `stderr_lines_dropped`; a normal stop then exits 4)."""
        data = f'claude-track-monitor: {text}'.encode('ascii', 'replace')[:STDERR_LINE_MAX] + b'\n'
        written = self.host.write_stderr(data, 0 if self.stderr_blocked else STDERR_WAIT_S)
        self.stderr_blocked = not written   # after a dropped line, never wait on stderr until one is written
        if not written:
            self.stderr_dropped += 1

    # -- the run ------------------------------------------------------------------------------------------

    def wait_until(self, deadline_ns: int) -> None:
        while self.stop_requested is None:
            self.read_inputs()
            remaining = deadline_ns - self.host.mono_ns()
            if remaining <= 0:
                return
            self.host.pause(min(WAIT_SLICE_S, remaining / 1_000_000_000))

    def stop(self, reason: str, code: int, tick_exit=None) -> int:
        # The stop's own stderr line goes first, so a drop of it is counted in STOP and turns the exit into 4
        # (AGENTS.md section 12: whatever the judgement, also a tick's exit 2, 5 or 6, which `tick_exit`
        # keeps; Codex r4581792593); the line gives the exit it would have when it is written.
        self.say(f'STOP {reason} exit={EXIT_WRITE if self.stderr_dropped else code}')
        if self.stderr_dropped:
            code = EXIT_WRITE   # stderr could not take every line (AGENTS.md section 12); STOP says so
        self.log.write('STOP', {
            'reason': reason, 'exit': code, 'tick_exit': tick_exit, 'ticks': self.ticks,
            'failed_ticks': self.failed_ticks, 'stderr_lines_dropped': self.stderr_dropped,
            'open_alarms': [{'alarm_id': key[0], 'sub_kind': key[1], 'episode_key': dict(key[2]), 'start_seq': seq}
                            for key, seq in self.open.items()],
            'pending_critical_heights': list(self.pending),
            'unused_fault_marks': len(self.waiting_marks),
            'refused_fault_marks': self.refused_marks,
            'refused_fault_marks_total': self.refused_total,
            'input_errors': self.input_errors,
            'episodes': [{key: value for key, value in episode.items() if key not in ('emission_utc_s', 'key')}
                         | {'b_detect_status': 'MEASURED' if episode['b_detect_sample']
                            and episode['emission_to_acknowledgment_s'] is not None else 'UNMEASURED'}
                         for episode in self.episodes.values()]})
        return code

    def run(self, template: dict, template_bytes: bytes, bitagi_bytes: bytes) -> int:
        """The loop; every way out writes STOP when the log takes it, and a stderr line when it does not."""
        self.pending = list(template['critical_heights'])
        try:
            try:
                return self._run(template, template_bytes, bitagi_bytes)
            except LogWriteFailed:
                self.log.drop_partial()
                try:
                    self.stop('LOG_WRITE_FAILED', EXIT_WRITE)
                except LogWriteFailed:
                    self.log.drop_partial()
                    self.say('LOG_WRITE_FAILED: the log took no STOP line (exit 4)')   # S-5
                return EXIT_WRITE
            except Exception as error:   # anything unexpected still ends with STOP and exit 4 (A, S-1..S-9)
                self.say(f'INTERNAL_ERROR {type(error).__name__}')
                try:
                    self.log.drop_partial()
                    self.stop('INTERNAL_ERROR', EXIT_WRITE)
                except Exception:
                    self.log.drop_partial()
                    self.say('INTERNAL_ERROR: the log took no STOP line (exit 4)')
                return EXIT_WRITE
        finally:
            self.log.close()
            shutil.rmtree(self.work, ignore_errors=True)

    def _run(self, template: dict, template_bytes: bytes, bitagi_bytes: bytes) -> int:
        args = self.args
        self.log.write('START', {
            'format': FORMAT_DOC, 'tool_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'bitagi_path': args.bitagi, 'bitagi_sha256': hashlib.sha256(bitagi_bytes).hexdigest(),
            'request_path': args.request, 'request_sha256': hashlib.sha256(template_bytes).hexdigest(),
            'log_path': str(self.log.path), 'poll_s': args.poll_s, 'tick_timeout_s': args.tick_timeout_s,
            'max_ticks': args.max_ticks, 'critical_heights': list(self.pending),
            'ack_input': ('STDIN' if args.ack_stdin else {'file': args.ack_file} if args.ack_file else None),
            'mark_input': {'file': args.mark_file} if args.mark_file else None,
            'tick_failing_after': TICK_FAILING_AFTER,
            'clock': {'mono_ns': 'CLOCK_MONOTONIC, ORDERING_AND_GAPS_ONLY', 'utc': CLOCK,
                      'suspended_ns': 'CLOCK_BOOTTIME MINUS CLOCK_MONOTONIC, SUSPEND_ONLY'},
            'release_class': 'T', 'release_authorization': 'NONE'})
        for source in self.inputs.values():   # what the files hold at START counts as read before the first tick
            if isinstance(source, FileLines):
                try:
                    source.start_size = os.stat(source.path).st_size
                except OSError:
                    source.start_size = 0
        self.read_inputs()   # what the inputs already hold: acknowledgements match nothing, marks are refused (all
        # of a file's START size, over as many reads as it takes)
        next_ns = self.host.mono_ns()
        while True:
            next_ns += args.poll_s * 1_000_000_000
            ended = self.tick(template)
            if ended is not None:
                self.read_inputs(final=True)   # every line already read is taken
                return self.stop('TICK_EXIT', ended, tick_exit=ended)
            if args.max_ticks is not None and self.ticks >= args.max_ticks:
                self.read_inputs(final=True)   # every line already read is taken
                return self.stop('MAX_TICKS', EXIT_OK)
            self.wait_until(next_ns)
            if self.stop_requested is not None:
                self.read_inputs(final=True)   # every line already read is taken
                return self.stop(f'SIGNAL_{self.stop_requested}', EXIT_OK)
            if self.host.mono_ns() - next_ns >= args.poll_s * 1_000_000_000:
                next_ns = self.host.mono_ns()   # more than a poll late (a stopped or stalled process): no catch-up
                # ticks. A suspend does not get here: CLOCK_MONOTONIC stands still during it (S-9).


# ---------------------------------------------------------------------------------------------------------
# check: read a log back.

def check_log(data: bytes) -> dict:
    """A summary of a log; `errors` lists what makes it not a MONITOR_LOG_V1 log (empty when it is one). A
    malformed line gives errors, never an exception: a value is compared or subtracted only once it is known to
    have its type (`mono_ns` against the last integer `mono_ns` before it; the gap and step loop only for a log
    without errors)."""
    errors, lines = [], data.split(b'\n')
    incomplete = lines.pop() != b''
    rows, last_mono = [], None
    for index, raw in enumerate(lines):
        try:
            row = loads(raw)
        except (UnicodeDecodeError, ValueError, RecursionError):
            errors.append(f'line {index}: NOT_JSON')
            break
        if not isinstance(row, dict) or row.get('schema') != LOG_SCHEMA or row.get('kind') not in KINDS:
            errors.append(f'line {index}: SCHEMA_OR_KIND')
            break
        if row.get('seq') != index:
            errors.append(f'line {index}: SEQ')
        mono = row.get('mono_ns')
        if not is_int(mono) or (last_mono is not None and mono < last_mono):
            errors.append(f'line {index}: MONO_NS_ORDER')
        if is_int(mono):
            last_mono = mono
        if parse_utc(row.get('utc')) is None:
            errors.append(f'line {index}: UTC')
        rows.append(row)
    if not errors:
        if not rows or rows[0]['kind'] != 'START':
            errors.append('FIRST_LINE_NOT_START')
        inside = rows[1:-1] + ([rows[-1]] if len(rows) > 1 and rows[-1]['kind'] == 'START' else [])
        if any(row['kind'] in ('START', 'STOP') for row in inside):
            errors.append('START_OR_STOP_INSIDE')
    if errors:
        return {'valid': False, 'errors': errors[:8]}
    poll_s = rows[0].get('poll_s')
    ticks = [row for row in rows if row['kind'] == 'TICK']
    gaps, steps, utc_back, suspends = [], [], [], []
    for before, after in zip(ticks, ticks[1:]):
        suspended = after.get('suspended_ns') if is_int(after.get('suspended_ns')) else 0
        since = after['mono_ns'] - before['mono_ns'] + suspended
        utc_delta = parse_utc(after['utc']) - parse_utc(before['utc'])
        if is_int(poll_s) and is_gap(since, poll_s):
            gaps.append(after['seq'])
        if abs(utc_drift_s(utc_delta, since)) > CLOCK_STEP_S:
            steps.append(after['seq'])
        if utc_delta < 0:
            utc_back.append(after['seq'])
        if suspended > SUSPEND_S * 1_000_000_000:
            suspends.append(after['seq'])
    stop = rows[-1] if rows[-1]['kind'] == 'STOP' else None
    return {'valid': True, 'errors': [], 'lines': len(rows), 'incomplete_last_line': incomplete,
            'kinds': {kind: sum(row['kind'] == kind for row in rows) for kind in KINDS},
            'ticks': len(ticks), 'gaps_at_seq': gaps, 'clock_steps_at_seq': steps, 'utc_backwards_at_seq': utc_back,
            'suspends_at_seq': suspends,
            'last_line': {'seq': rows[-1]['seq'], 'kind': rows[-1]['kind'], 'utc': rows[-1]['utc']},
            'alarm_starts': [{'seq': row['seq'], 'alarm_id': row.get('alarm_id'), 'sub_kind': row.get('sub_kind')}
                             for row in rows if row['kind'] == 'ALARM_START'],
            'stopped': stop is not None, 'stop': None if stop is None else {'reason': stop.get('reason'),
                                                                            'exit': stop.get('exit')}}


# ---------------------------------------------------------------------------------------------------------
# main.

def bounded(low: int, high: int):
    def parse(text: str) -> int:
        if not re.fullmatch(r'[0-9]{1,7}', text) or not low <= int(text) <= high:
            raise argparse.ArgumentTypeError(f'an integer from {low} to {high}')
        return int(text)
    return parse


def parser() -> argparse.ArgumentParser:
    top = argparse.ArgumentParser(description=__doc__.splitlines()[0], allow_abbrev=False)
    commands = top.add_subparsers(dest='command', required=True)
    run = commands.add_parser('run', allow_abbrev=False)
    run.add_argument('--bitagi', required=True, help='absolute path of the bitagi binary')
    run.add_argument('--request', required=True, help='the tick request template')
    run.add_argument('--log', required=True, help='absolute path of the new log file')
    run.add_argument('--poll-s', type=bounded(1, MAX_POLL_S), default=DEFAULT_POLL_S)
    run.add_argument('--tick-timeout-s', type=bounded(1, MAX_POLL_S), default=DEFAULT_TICK_TIMEOUT_S)
    run.add_argument('--max-ticks', type=bounded(1, 10_000_000))
    acks = run.add_mutually_exclusive_group()
    acks.add_argument('--ack-file')
    acks.add_argument('--ack-stdin', action='store_true')
    run.add_argument('--mark-file')
    check = commands.add_parser('check', allow_abbrev=False)
    check.add_argument('--log', required=True)
    return top


def prepare(args, host: Host) -> tuple[Loop, dict, bytes, bytes]:
    """Every check made before the log exists; the log is created last, and only when it is new."""
    log = Path(args.log)
    if not log.is_absolute():
        raise Refusal('LOG_PATH_NOT_ABSOLUTE')
    bitagi = Path(args.bitagi)
    if not bitagi.is_absolute():
        raise Refusal('BITAGI_PATH_NOT_ABSOLUTE', 'the binary that runs is the one START hashes')
    if not bitagi.is_file() or not os.access(bitagi, os.X_OK):
        raise Refusal('BITAGI_NOT_EXECUTABLE')
    template, template_bytes = read_template(Path(args.request))
    for name, path in (('ACK', args.ack_file), ('MARK', args.mark_file)):
        try:
            if path is not None and not stat.S_ISREG(os.stat(path).st_mode):
                raise Refusal(f'{name}_FILE_NOT_REGULAR', 'a FIFO, a device or a folder is never read (S-7)')
        except FileNotFoundError:
            pass   # made later by the channel or the driver
        except OSError as error:
            raise Refusal(f'{name}_FILE_UNREADABLE', errno.errorcode.get(error.errno, '?')) from error
    if args.ack_stdin and os.isatty(0):
        raise Refusal('ACK_STDIN_IS_A_TERMINAL', 'a background loop would be stopped by SIGTTIN (S-8)')
    loop = Loop(args, host,
                acks=StdinLines() if args.ack_stdin else FileLines(Path(args.ack_file)) if args.ack_file else None,
                marks=FileLines(Path(args.mark_file)) if args.mark_file else None)
    bitagi_bytes = bitagi.read_bytes()
    try:
        loop.work = Path(tempfile.mkdtemp(prefix='claude-track-monitor-'))   # before the log (S-18)
    except OSError as error:
        raise Refusal('WORK_FOLDER_FAILED', errno.errorcode.get(error.errno, '?')) from error
    try:
        loop.log = Log(log, host)
    except FileExistsError as error:
        shutil.rmtree(loop.work, ignore_errors=True)
        raise Refusal('LOG_EXISTS', 'a monitor log is a new file only') from error
    except OSError as error:
        shutil.rmtree(loop.work, ignore_errors=True)
        raise Refusal('LOG_CREATE_FAILED', errno.errorcode.get(error.errno, '?')) from error
    return loop, template, template_bytes, bitagi_bytes


def open_closed_stdio() -> None:
    """Point each of fds 0, 1 and 2 that is closed at /dev/null, so no file the tool opens takes its place."""
    for fd in (0, 1, 2):
        try:
            os.fstat(fd)
        except OSError:
            null = os.open(os.devnull, os.O_RDWR)
            if null != fd:
                os.dup2(null, fd)
                os.close(null)
    for fd, name in ((1, 'stdout'), (2, 'stderr')):
        if getattr(sys, name) is None:   # Python started with the fd closed: its text goes to /dev/null now
            setattr(sys, name, open(fd, 'w', encoding='utf-8', errors='replace', closefd=False, buffering=1))


def main(argv: list[str] | None = None, host: Host | None = None) -> int:
    if sys.flags.optimize:
        return EXIT_SECURITY
    open_closed_stdio()
    args = parser().parse_args(argv)
    if args.command == 'check':
        try:
            data = Path(args.log).read_bytes()
        except OSError as error:
            print(f'claude-track-monitor: refused: LOG_UNREADABLE: {type(error).__name__}', file=sys.stderr)
            return EXIT_ARGS
        summary = check_log(data)
        print(dumps(summary).decode('ascii'))
        if not summary['valid']:
            return EXIT_ARGS
        return EXIT_OK if summary['stopped'] else EXIT_MISSING   # no STOP: the loop was killed or still runs
    real = host is None
    try:
        loop, template, template_bytes, bitagi_bytes = prepare(args, Host() if real else host)
    except Refusal as refusal:
        detail = f': {refusal.detail}' if refusal.detail else ''
        print(f'claude-track-monitor: refused: {refusal.code}{detail}', file=sys.stderr)
        return EXIT_ARGS
    if real:
        def asked(number, _frame):
            loop.stop_requested = signal.Signals(number).name
        for name in STOP_SIGNALS:
            signal.signal(getattr(signal, name), asked)
        signal.pthread_sigmask(signal.SIG_UNBLOCK, [getattr(signal, name) for name in STOP_SIGNALS])   # inherited
        # A background write to a terminal goes through (TOSTOP would stop the process at it; ignoring SIGTTOU
        # lets the write proceed), so a background loop is never stopped by its own stderr line (S-1).
        signal.signal(signal.SIGTTOU, signal.SIG_IGN)
    return loop.run(template, template_bytes, bitagi_bytes)


if __name__ == '__main__':
    import claude_track_exit

    claude_track_exit.run(main)
