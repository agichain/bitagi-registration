"""XD-1 supervisor: one driver run in its own process group, killed at the cap (CT-P3-044c-1 1e-4b-1).

Class T EXPLORATORY, Regtest only. Sources: 1E section 4.5 Runs and Per-run cap
(docs/claude-track/plans/CT-P3-044C1_1E_PREP_EN.md :1061-1072, :1244-1252); B's unit draft #258
issuecomment-6418049931 section 2 and A's answer issuecomment-6419729708 ("supervisor").

  run --work DIR -- DRIVER_COMMAND...

The driver command starts in a new session, so its process group holds the driver, the host workers and the
nodes. The group is killed (SIGKILL) at `XD1_RUN_CAP` + `XD1_KILL_MARGIN` (900 + 60 s), and also when the
driver exits first, early or not: nothing of the run outlives it. A killed run has no record and counts as
T = infinity (the checker's RECORD_MISSING); the supervisor writes no record.

After the kill it confirms that no process of the group is left and that no bitcoind is left at all: a
bitcoind that escaped the group may hold a port or a data directory the next run would use, and one whose
command line names `--work` holds this run's data directory. Then the next run must not start: exit 2.

Exit codes: 0 the run ended and nothing is left (whatever the driver's own result, which its record holds);
2 a process is left, so the next run must not start; 3 the driver command could not be started; 4 internal
error; 5 under -O. One JSON line on stdout, and nothing else: the driver's stdout (its own WRITTEN line)
goes to the supervisor's stderr, so a caller can read stdout as one JSON document (Codex P1 r4379891947).
Stdlib only; Linux /proc.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

XD1_RUN_CAP_S = 900
XD1_KILL_MARGIN_S = 60
LEFT_WAIT_S = 30.0   # how long the killed group may take to disappear
POLL_S = 0.05


def processes():
    """(pid, pgid, name, argv) of every process /proc lists that is still readable."""
    found = []
    for entry in os.listdir('/proc'):
        if not entry.isdigit():
            continue
        try:
            stat = Path(f'/proc/{entry}/stat').read_text()
            argv = Path(f'/proc/{entry}/cmdline').read_bytes().split(b'\0')
        except OSError:
            continue
        name = stat[stat.index('(') + 1:stat.rindex(')')]
        fields = stat[stat.rindex(')') + 2:].split()
        if fields[0] == 'Z':   # a zombie holds no port or file
            continue
        found.append((int(entry), int(fields[2]), name, [a.decode('utf-8', 'replace') for a in argv if a]))
    return found


def left(pgid: int, work: Path):
    """What remains that the next run could collide with: any process of the group, any bitcoind."""
    out = []
    for pid, group, name, argv in processes():
        program = os.path.basename(argv[0]) if argv else ''
        if group == pgid:
            out.append({'pid': pid, 'why': 'GROUP'})
        elif 'bitcoind' in (name, program):
            out.append({'pid': pid, 'why': 'DATA_DIR' if any(str(work) in a for a in argv) else 'BITCOIND'})
    return out


def kill_group(pgid: int) -> None:
    try:
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def supervise(command, work: Path, cap_s: float = XD1_RUN_CAP_S + XD1_KILL_MARGIN_S) -> tuple[int, dict]:
    try:
        child = subprocess.Popen(command, start_new_session=True, stdout=sys.stderr.fileno())
    except OSError:
        return 3, {'result': 'NOT_STARTED'}
    pgid = child.pid
    try:
        code = child.wait(timeout=cap_s)
        capped = False
    except subprocess.TimeoutExpired:
        code, capped = None, True
    kill_group(pgid)   # at the cap, and after a driver that exited first
    if capped:
        code = child.wait()
    deadline = time.monotonic() + LEFT_WAIT_S
    remaining = left(pgid, work)
    while any(r['why'] == 'GROUP' for r in remaining) and time.monotonic() < deadline:
        time.sleep(POLL_S)
        remaining = left(pgid, work)
    summary = {'result': 'LEFTOVER' if remaining else 'RUN_ENDED', 'killed_at_cap': capped, 'driver_exit': code,
               'left': remaining}
    return (2 if remaining else 0), summary


def parser():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest='mode', required=True)
    run = sub.add_parser('run')
    run.add_argument('--work', type=Path, required=True, help="the run's work directory (the driver's --work)")
    run.add_argument('command', nargs=argparse.REMAINDER)
    return p


def main(argv=None) -> int:
    if not __debug__:
        print(json.dumps({'result': 'REFUSED', 'failure': 'OPTIMIZED_PYTHON'}), file=sys.stderr)
        return 5
    a = parser().parse_args(sys.argv[1:] if argv is None else argv)
    command = a.command[1:] if a.command[:1] == ['--'] else a.command
    if not command:
        print(json.dumps({'result': 'NOT_STARTED'}))
        return 3
    code, summary = supervise(command, a.work.resolve())
    print(json.dumps(summary, sort_keys=True))
    return code


if __name__ == '__main__':
    import claude_track_exit
    claude_track_exit.run(main)
