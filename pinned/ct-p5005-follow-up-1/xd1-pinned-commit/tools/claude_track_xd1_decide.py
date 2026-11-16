"""XD-1 live decision: the Founder's console for the driver's broadcast prompt (V3 section 4; A's XA2).

Class T Regtest. The Founder installs this file and `claude_track_exit.py` once, from merged main, as root-owned
copies in /usr/local/lib/bitagi-xd1/ (directory 0755, this file 0755, the helper 0644, all root:root; each sha256
compared with the value A gives; VPS prep document 2.4 and 3.3). It never runs from a file the runner account can
write. The Founder starts it at the VPS console, as the runner account and on a new pseudo-terminal, for the
whole session (one prompt per run):

  runuser -P -u runner01 -- python3 -I /usr/local/lib/bitagi-xd1/claude_track_xd1_decide.py

  decide [--console-dir DIR] [--once --answer BROADCAST|REFUSE]

`-P` gives the helper its own pseudo-terminal, so neither it nor anything the runner account starts can push input
into root's terminal (TIOCSTI) or hold it after it ends; the VPS also sets `dev.tty.legacy_tiocsti = 0`. The
helper refuses to run as root (exit 5).

It waits for the driver's prompt (`prompt.json` in the console directory, written after the run's STEP_9_END line),
shows the run index, the candidate txid, its display digest and the seconds left before the run cap, discards any
input typed before the prompt appeared (`tcflush`, so a line typed or pasted early never answers a run), and
reads the Founder's answer from the terminal: the word BROADCAST or REFUSE (anything else is discarded with any
further pending input and asked again; the end of input stops the console and writes nothing, so the run waits
until its cap and counts T = infinity). The answer goes to the console FIFO as one line,
`XD1_DECISION_V1 <run_index> <txid> BROADCAST|REFUSE`, only while the same prompt is still there and the FIFO is a
FIFO with a reader (opened without following a link); a run that is no longer waiting is reported as not
delivered, and without --once the console waits for the next prompt. The decision time counts inside T (045b
:596-602), so the console shows each prompt as soon as it appears. Standard input must be a terminal; the console
directory defaults to `xd1-console` in the running account's home directory (from the account database).
`--answer` (tests only, never in a session) gives the answer without asking and needs `--once`.

Exit codes: 0 delivered (with --once) or the input ended; 2 a decision not delivered (--once), or --answer without
--once; 3 the console directory missing; 4 internal error; 5 under -O, run as root, or standard input not a
terminal without --answer. Stdlib only; Python 3.12 or later.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import pwd
import re
import stat
import sys
import termios
import time

# The installed copy runs under `python3 -I`, which leaves this file's folder off sys.path; claude_track_exit is
# installed beside it in the same root-owned folder.
sys.path.insert(0, str(Path(__file__).resolve().parent))

PROMPT_FORMAT = 'BITAGI_CT_XD1_DECISION_PROMPT_V1'   # claude_track_xd1_driver.PROMPT_FORMAT
PROMPT_NAME, CONSOLE_FIFO = 'prompt.json', 'decision.fifo'
PROMPT_KEYS = {'format', 'run_index', 'run_id', 'txid', 'raw_tx_sha256', 'display_digest', 'fifo', 'cap_seconds_left'}
PROMPT_LIMIT = 4096
HEX64 = re.compile(r'[0-9a-f]{64}')
ANSWERS = ('BROADCAST', 'REFUSE')
POLL_SECONDS = 0.1


class NotDelivered(Exception):
    """Exit 2 with this label."""


def read_prompt(console: Path) -> tuple[bytes, dict] | None:
    """The prompt's bytes and value, or None while there is none; a malformed one is NotDelivered."""
    path = console / PROMPT_NAME
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return None
    except OSError:
        raise NotDelivered('PROMPT_MALFORMED') from None
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):   # a FIFO or a directory there is not a prompt
            raise NotDelivered('PROMPT_MALFORMED')
        raw = os.read(fd, PROMPT_LIMIT + 1)
    except OSError:
        raise NotDelivered('PROMPT_MALFORMED') from None
    finally:
        os.close(fd)
    try:
        value = json.loads(raw.decode('ascii'))
    except (UnicodeDecodeError, ValueError):
        raise NotDelivered('PROMPT_MALFORMED') from None
    ok = (len(raw) <= PROMPT_LIMIT and type(value) is dict and set(value) == PROMPT_KEYS
          and value['format'] == PROMPT_FORMAT and value['fifo'] == CONSOLE_FIFO
          and type(value['run_index']) is int and 1 <= value['run_index'] <= 99
          and type(value['run_id']) is int and type(value['cap_seconds_left']) is int
          and all(type(value[k]) is str and HEX64.fullmatch(value[k]) for k in ('txid', 'raw_tx_sha256'))
          and value['display_digest'] == f"{value['txid'][:8]}..{value['txid'][-8:]}")
    if not ok:
        raise NotDelivered('PROMPT_MALFORMED')
    return raw, value


def wait_prompt(console: Path, seen: bytes | None) -> tuple[bytes, dict]:
    """The next well-formed prompt whose bytes are not `seen` (the one already decided). A malformed file (a
    killed run's leftover; the driver writes a prompt whole) is not shown: the console keeps waiting."""
    while True:
        try:
            got = read_prompt(console)
        except NotDelivered:
            got = None
        if got is not None and got[0] != seen:
            return got
        time.sleep(POLL_SECONDS)


def show(value: dict, out) -> None:
    out.write('\a\n'
              '==================== XD-1 broadcast decision ====================\n'
              f"run index      {value['run_index']}   (workflow run {value['run_id']})\n"
              f"candidate txid {value['txid']}\n"
              f"display digest {value['display_digest']}\n"
              f"raw tx sha256  {value['raw_tx_sha256']}\n"
              f"cap            {value['cap_seconds_left']} s left at the prompt; the decision time counts in T\n"
              '=================================================================\n')
    out.flush()


def ask(value: dict, fd: int, out) -> str | None:
    """BROADCAST or REFUSE as typed on the terminal `fd` after the prompt, asked again for anything else; None at
    the end of input. Input already pending when the question is asked (typed or pasted before the prompt, or a
    second line after a wrong one) is discarded first (C1), and each read is one line of the terminal's canonical
    mode, read from the descriptor itself, so no earlier line waits in a buffer."""
    while True:
        termios.tcflush(fd, termios.TCIFLUSH)
        out.write(f"Type BROADCAST to broadcast run {value['run_index']}, or REFUSE: ")
        out.flush()
        data = os.read(fd, 1024)
        if not data:
            return None
        answer = data.decode('ascii', 'replace').strip()
        if answer in ANSWERS:
            return answer
        out.write('Only the word BROADCAST or the word REFUSE is taken.\n')


def deliver(console: Path, raw: bytes, value: dict, answer: str) -> None:
    """One line to the console FIFO, only while the same prompt is still there and its run reads the FIFO."""
    got = read_prompt(console)
    if got is None or got[0] != raw:
        raise NotDelivered('PROMPT_GONE: the run is no longer waiting for this decision')
    try:
        fd = os.open(console / CONSOLE_FIFO, os.O_WRONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    except OSError:
        raise NotDelivered('NO_READER: the run is no longer waiting for this decision') from None
    try:
        if not stat.S_ISFIFO(os.fstat(fd).st_mode):   # never a write into a file of another kind
            raise NotDelivered('NOT_A_FIFO')
        os.write(fd, f"XD1_DECISION_V1 {value['run_index']} {value['txid']} {answer}\n".encode('ascii'))
    finally:
        os.close(fd)


def terminal_fd() -> int:
    """Standard input's descriptor when it is a terminal, else -1."""
    try:
        fd = sys.stdin.fileno()
    except (AttributeError, OSError, ValueError):
        return -1
    return fd if os.isatty(fd) else -1


def default_console() -> Path:
    """`xd1-console` in the running account's home directory, from the account database (not $HOME, which
    runuser keeps from root)."""
    return Path(pwd.getpwuid(os.getuid()).pw_dir) / 'xd1-console'


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--console-dir', type=Path, default=None)
    p.add_argument('--once', action='store_true')
    p.add_argument('--answer', choices=ANSWERS)
    return p


def main(argv=None) -> int:
    if not __debug__:
        print(json.dumps({'result': 'REFUSED', 'failure': 'OPTIMIZED_PYTHON'}), file=sys.stderr)
        return 5
    if os.geteuid() == 0:   # S1: never root, whose terminal and files a job-controlled program must not reach
        print(json.dumps({'result': 'REFUSED', 'failure': 'RUN_AS_ROOT'}), file=sys.stderr)
        return 5
    a = parser().parse_args(sys.argv[1:] if argv is None else argv)
    if a.answer is not None and not a.once:   # never an automatic approver for every prompt (C1)
        print(json.dumps({'result': 'REFUSED', 'failure': 'ANSWER_NEEDS_ONCE'}), file=sys.stderr)
        return 2
    stdin = terminal_fd() if a.answer is None else -1
    if a.answer is None and stdin < 0:   # a live answer comes from the terminal only
        print(json.dumps({'result': 'REFUSED', 'failure': 'STDIN_NOT_A_TERMINAL'}), file=sys.stderr)
        return 5
    console = a.console_dir if a.console_dir is not None else default_console()
    if not console.is_dir():
        print(json.dumps({'result': 'PREREQUISITE', 'failure': 'the console directory'}), file=sys.stderr)
        return 3
    seen = None
    try:
        while True:
            raw, value = wait_prompt(console, seen)
            show(value, sys.stdout)
            answer = a.answer or ask(value, stdin, sys.stdout)
            if answer is None:
                print(json.dumps({'result': 'INPUT_ENDED'}))
                return 0
            seen = raw
            try:
                deliver(console, raw, value, answer)
            except NotDelivered as error:   # that run has gone; the console waits for the next prompt
                print(json.dumps({'result': 'NOT_DELIVERED', 'run_index': value['run_index'], 'failure': str(error)}),
                      file=sys.stderr)
                if a.once:
                    return 2
                continue
            print(json.dumps({'result': 'DELIVERED', 'run_index': value['run_index'], 'decision': answer}))
            sys.stdout.flush()
            if a.once:
                return 0
    except KeyboardInterrupt:
        return 0


if __name__ == '__main__':
    import claude_track_exit
    claude_track_exit.run(main)
