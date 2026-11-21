"""P5-002 endurance driver (VPS side): two private Signet nodes, the sampler, block producer and replayer daemon,
the monitor loop, the checkpoints and the finish (XA13, PR-1, PR-2b).

Class T, private Signet, scope (b). The interface is docs/claude-track/formats/P5002_ENDURANCE_V1.md (sections 3
and 4): this tool writes one attempt's records and decides nothing. The checker
(`tools/claude_track_p5002_check.py`) is the only module imported besides the standard library, and only by the
names of the document's section 13; the hosted report recomputes every result from the raw records.

  start --declaration FILE --source-sha256 HEX --node-a BIN_DIR --node-b BIN_DIR --bin-dir DIR --records NEW_DIR
        --work NEW_DIR
  checkpoint --records DIR --work DIR --index K [--github-output FILE]
  finish --records DIR --work DIR
  daemon --records DIR --work DIR                    (internal: only `start` spawns it)

* `start` (steps S1..S8) checks the hosted build job's two binaries (`--bin-dir` holds `bitagi` and
  `test_only_signet_store_fixture`; each SHA-256 is the declaration's) and copies them into `<work>/bin/`, then
  starts Node A and Node B (`BIN_DIR` holds `bitcoind` and `bitcoin-cli`) on one private Signet with the
  declaration's challenge, each in its own new session with `NODE_ARGS`: loopback only, connected only to each
  other, no DNS seed, no fixed seed, no discovery, no wallet, and an RPC auth line for the public Class T fixture
  user (a fresh salt per node per attempt; B's Rust tools authenticate with it). It checks the challenge through
  both nodes, reads height 0, mines heights 1..H0 - 1 with alternating producers, reads H0 - 1, builds the replay
  store at H0 - 1 with B's fixture (S5r; skipped when that read disagreed), writes `environment.json` and the fixed
  records, spawns the monitor loop in its own new session and waits for its START line (S6m), spawns the daemon in
  its own new session and, once sample 0 is written, `marker.json`. A refusal after a node was started kills what
  was started; no marker is left.
* `daemon` is the sampler, in a second thread the block producer and in a third the replayer (a slow block or a
  slow follow never delays a sample). The replayer runs the fixture's `--follow` once every `sample_seconds`, one at
  a time, and writes one `replay.jsonl` row each; no follow starts after the stop and one in flight is awaited. The
  sampler writes one chained line per sample period, each one `os.write` on an append-only descriptor, and after
  each sample applies the stopping rule with the checker's `intervals()`. It compares each node's tip with that
  node's last `ok` sample, so a replaced tip is found after failed samples too, and a fork point whose read got
  no answer makes the sample a failed one and is read again at the next. The producer makes block n (height
  H0 + n) when it is due, `a` for even n and `b` for odd n, one at a time, late rather than skipped, and never on
  a tip that is not the block before. No new `generatetodescriptor` call starts after the stop; a call already
  in flight is awaited and its block keeps its row. A second daemon never extends a chain: `samples.jsonl` is
  created new. A stop request (SIGTERM or SIGINT, as `finish` sends) only sets a flag the sampler reads within
  a second; the daemon then ends with `FINISH` and leaves no stop reason of its own.
* `checkpoint` waits for slot K or the daemon's end and writes `checkpoint-K.json` once with the chain head of
  the last complete sample line and the daemon's state (`RUNNING`, `STOPPED`, or `DEAD` for a daemon that is
  gone without a stop reason).
* `finish` (steps F1..F5) stops the daemon, stops the monitor (SIGTERM, F1m), runs one last follow (F1r),
  re-reads the critical heights and each challenge on the nodes that still answer, stops both nodes, kills the four
  sessions' process groups, counts what is left (and any live process of the two copied binaries, wherever its
  session), copies each `debug.log` and the monitor's log unless it holds credential words, and writes
  `final.json`. A credential word is `rpcpassword` or `__cookie__` anywhere, or `rpcauth` anywhere but in one of
  Core's two lines for a command-line -rpcauth (CORE_AUTH_LINES: the redacted `rpcauth=****` and the method line
  `Using rpcauth authentication.`, each with its newline). `nodes_stopped` is true for a node whose
  session holds no process when F3 ends. The daemon's own output and error output (`daemon.out`, `daemon.err`:
  its closing line, and a traceback when it died) are copied beside the node logs under the same rule, each cut
  to its last 64 KiB; `final.json` names what became of each (`daemon_logs`). In every copy the work
  directory's path is written as `<work>` and the runner user's home directory as `<home>` (the copies hold no
  path of the host). With both a withheld log and a process left, the line is `CREDENTIAL_MATERIAL`.
* `start` records a critical read whose two hashes differ like any other read (the row and its incident file)
  and does not refuse for it: an attempt that reaches the marker is counted and reported with S14 FAIL.
* No node is ever restarted: a node that stops answering gives failed samples until the end.
* Every RPC goes through that node's own `bitcoin-cli` (`CLI_ARGS`), whose cookie authentication is its own:
  this tool never opens, reads, copies or prints a cookie file, and `bitcoin-cli`'s error text is discarded. The
  RPC auth line is computed from the public fixture recipe (no secret exists) and never written to a record:
  `environment.json` names it `-rpcauth=<CLASS_T_PUBLIC_FIXTURE>`.
* Between the commands the work directory holds `state.json` (each node's binary directory, each session's
  leader pid and its start time in clock ticks: the nodes, the daemon, the monitor) and, once the daemon stopped by
  its rule, `daemon-stop.json`; also `bin/` (the two binaries), `replay/` (the fixture's store) and `monitor/`
  (the request, the log, the loop's output and error output, and its temporary folder).
  The daemon's own output line (`daemon.out`) and its error output (`daemon.err`) are written there and copied
  to the records by `finish`, since the work directory is never uploaded.
* `World` holds what the commands reach outside their record files (the clocks, the host and its processes, the
  two nodes, the two Rust tools); the tests pass fakes, so the logic runs without a node and on injected clocks.

Every command prints one line of canonical JSON on stdout (section 3) and never echoes input text, a label, a
file name or a path. Exit codes: 0 done; 2 validation; 3 unavailable; 4 internal; 5 security; 6 refusal
(optimized Python among them). No `assert` is a control. Stdlib only; nothing of ARDR or XD-1 and no
`tools/common.py` is imported. Linux `/proc`.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path
import platform
import re
import secrets
import shutil
import signal
import stat
import subprocess
import sys
import threading
import time
import traceback

import claude_track_p5002_check as check

TOOL = 'p5002_driver'
NS = 10**9

# Section 3, S2: a node's arguments and every RPC's `bitcoin-cli` arguments (the method and its parameters follow).
NODE_ARGS = ('-signet', '-signetchallenge={challenge}', '-datadir={datadir}', '-server=1', '-listen=1',
             '-bind=127.0.0.1:{p2p}', '-rpcbind=127.0.0.1', '-rpcallowip=127.0.0.1', '-rpcport={rpc}',
             '-rpcauth={auth}', '-connect=127.0.0.1:{other_p2p}', '-dnsseed=0', '-fixedseeds=0', '-discover=0',
             '-listenonion=0', '-disablewallet=1', '-printtoconsole=0')
# PR-2b, A's decision 1: the public Class T fixture user of crates/bitagi-bitcoin/src/rpc_credentials.rs, which B's
# fixture and `bitagi monitor tick` authenticate as; the recipe and the user are copied from
# tools/claude_track_regtest_store_commands.py (not imported), and are not a secret. Each node gets its own line with
# a fresh salt; a record names it AUTH_RECORDED, never the salted line.
AUTH_RECIPE = 'BITAGI/P3-008/PUBLIC-AUTH/V1'
AUTH_USER = '-'.join(('bitagi', 'class', 't'))
AUTH_RECORDED = '<CLASS_T_PUBLIC_FIXTURE>'
CLI_ARGS = ('-signet', '-datadir={datadir}', '-rpcport={rpc}', '-rpcclienttimeout={seconds}')
TEXT_METHODS = frozenset({'getblockhash', 'stop'})    # bitcoin-cli prints these answers as bare text
COINBASE_DESCRIPTOR = 'raw(51)'     # OP_TRUE: no wallet and no key (section 2)
# One call's nonce tries. The local smoke of 2026-11-15 (1,000,000 tries: 0.25 s a call, 16 calls a block;
# 4,000,000 tries: 1.9 calls a block) fits a block template stamped with its second, so that a call repeated
# within that second tries the same nonces again. The tries are sized to last about a second on such a host
# and to return within half of RPC_SECONDS on one ten times slower. A harness constant, not a criterion: no
# result reads it (the format document's section 4.4).
GENERATE_TRIES = 4_000_000
ANSWER_LIMIT = 1 << 20              # the bytes of one RPC answer

READY_SECONDS = 120                 # S3: both nodes answer and each has a peer
SEEN_SECONDS = 60                   # S4, S5: a pre-mined block is on the other node
PREMINE_SECONDS = 3_000             # the whole pre-mine, inside the `start` step's 70 minutes
REPLAY_SECONDS = 330                # one fixture run (S5r, a follow, F1r): its own replay session is bounded at 300 s
MONITOR_START_SECONDS = 60          # S6m: the monitor's START line
DAEMON_START_SECONDS = 120          # S7: sample 0
POLL_SECONDS = 1
NODE_STOP_SECONDS = 60              # F3: a node's own shutdown after RPC `stop`
DAEMON_STOP_SECONDS = REPLAY_SECONDS + 10      # F1: a follow in flight (the producer's call is shorter)
MONITOR_STOP_SECONDS = check.MONITOR_TICK_TIMEOUT_SECONDS + 30     # F1m: a tick that runs, then the STOP line
LEFT_SECONDS = 30                   # F3: a killed group disappears
MAX_FORK_WALK = 1_000               # the headers walked back from a replaced tip
NODE_LOG_LIMIT = 64 << 20           # F4: a debug.log's last bytes that are copied
DAEMON_LOG_LIMIT = 64 << 10         # F4: the last bytes of the daemon's own output and error output
CREDENTIAL_WORDS = (b'rpcpassword', b'rpcauth', b'__cookie__')
REDACTED_AUTH = b'rpcauth=****\n'   # F4: Core's own line for a command-line -rpcauth
# F4 (the 11-18 scaled pilot, run 44214465515): Core 30.3 and 31.1 also write this line at RPC start when -rpcauth is
# given; both node logs were withheld for it. Each allowed line with the offset of `rpcauth` in it; no other
# `rpcauth` is allowed.
AUTH_IN_USE = b'Using rpcauth authentication.\n'
CORE_AUTH_LINES = ((REDACTED_AUTH, 0), (AUTH_IN_USE, AUTH_IN_USE.index(b'rpcauth')))
SCAN_CHUNK = 1 << 20
SMALL_READ = 64 << 10               # S6m: the bytes of the monitor log read for its START line
WORK_MARK, HOME_MARK = b'<work>', b'<home>'     # F4: what a copied log shows for the two host paths

STATE_NAME, STOP_NAME = 'state.json', 'daemon-stop.json'
# The daemon's stdout and stderr in the work directory; F4 copies both to node-logs/ (final.json's daemon_logs).
DAEMON_LOG_NAMES = {'out': 'daemon.out', 'err': 'daemon.err'}
# The monitor loop: the tool beside this one in the tree, and its files under <work>/monitor/ (S6m, F4)
MONITOR_PATH = Path(__file__).resolve().parent / 'claude_track_monitor.py'
MONITOR_NAMES = {'request': 'request.json', 'log': 'monitor.jsonl', 'out': 'monitor.out', 'err': 'monitor.err',
                 'tmp': 'tmp'}
DAEMON_STOPS = ('STOP_RULE', 'DEADLINE')
NODE_KEYS = ('ok', 'pid', 'uptime', 'chain', 'blocks', 'bestblockhash', 'mediantime', 'signet_challenge',
             'genesis_hash', 'connections', 'networkactive', 'mempool_size')
CRITICAL = ('GENESIS', 'H0_MINUS_1', 'H0')
INT_MAX = 2**63 - 1
HEX64 = re.compile(r'[0-9a-f]{64}')
CHAIN_NAME = re.compile(r'[a-z0-9]{1,16}')
CHALLENGE_HEX = re.compile(r'[0-9a-f]{0,1024}')
BOOT_ID_PATH = '/proc/sys/kernel/random/boot_id'
CLOCKSOURCE_PATH = '/sys/devices/system/clocksource/clocksource0/current_clocksource'


def _let_go(process) -> int:
    """The pid of a child that is meant to outlive this command: it is never waited for here."""
    process.returncode = 0
    return process.pid


class NodeError(Exception):
    """A node did not answer a read: no answer within RPC_SECONDS, an error, or an answer of another shape."""


def is_hash(value) -> bool:
    return type(value) is str and HEX64.fullmatch(value) is not None


def is_count(value, low=0) -> bool:
    return type(value) is int and low <= value <= INT_MAX


def other(key: str) -> str:
    return check.NODES[1 - check.NODES.index(key)]


def node_args(key: str, datadir: str, challenge: str, auth: str = AUTH_RECORDED) -> list[str]:
    ports = check.PORTS
    return [arg.format(challenge=challenge, datadir=datadir, p2p=ports[key]['p2p'], rpc=ports[key]['rpc'],
                       auth=auth, other_p2p=ports[other(key)]['p2p']) for arg in NODE_ARGS]


def auth_line() -> str:
    """`<user>:<salt>$<hmac>` for the public fixture credential, with a fresh salt (the regtest tools' recipe)."""
    fixture = hashlib.sha256(AUTH_RECIPE.encode('ascii')).hexdigest()
    salt = secrets.token_hex(16)
    digest = hmac.new(salt.encode('ascii'), fixture.encode('ascii'), hashlib.sha256).hexdigest()
    return f'{AUTH_USER}:{salt}${digest}'


def tool_path(work: Path, key: str) -> Path:
    """`<work>/bin/<name>` of a binary of check.BINARY_NAMES (S1b copies it there)."""
    return Path(work) / 'bin' / check.BINARY_NAMES[key]


def fixture_argv(work: Path, h0: int, genesis: str, challenge: str, as_of: str | None = None) -> list[str]:
    """The fixture's command line: the build of the store at H0 - 1 (`as_of`, that block's hash), or one `--follow`."""
    ports = [str(check.PORTS[key]['rpc']) for key in check.NODES]
    store = str(Path(work) / 'replay')
    if as_of is None:
        return [str(tool_path(work, 'fixture')), '--follow', store, str(h0), genesis, challenge, *ports]
    return [str(tool_path(work, 'fixture')), store, str(h0), as_of, genesis, challenge, *ports]


def monitor_argv(work: Path) -> list[str]:
    """The monitor loop's command line (A's decision 6): absolute paths, the poll and the tick timeout, no
    acknowledgement or mark input."""
    folder = Path(work) / 'monitor'
    return [sys.executable or 'python3', '-B', str(MONITOR_PATH), 'run', '--bitagi', str(tool_path(work, 'bitagi')),
            '--request', str(folder / MONITOR_NAMES['request']), '--log', str(folder / MONITOR_NAMES['log']),
            '--poll-s', str(check.MONITOR_POLL_SECONDS), '--tick-timeout-s', str(check.MONITOR_TICK_TIMEOUT_SECONDS)]


# ------------------------------------------------------------------------------------------------ files ----
def read_file(path, limit):
    """The bytes of a regular file that is not a link, at most `limit` + 1 of them; None when absent."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return None
    except OSError:
        raise check.Refusal('PATH_NOT_REGULAR') from None
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise check.Refusal('PATH_NOT_REGULAR')
        chunks, size = [], 0
        while size <= limit:
            chunk = os.read(fd, min(SCAN_CHUNK, limit + 1 - size))
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
    finally:
        os.close(fd)
    return b''.join(chunks)


def _write_all(fd, raw):
    view = memoryview(raw)
    while view:
        view = view[os.write(fd, view):]
    os.fsync(fd)


def write_new(path, raw: bytes) -> None:
    """A new file, never over another: OUTPUT_EXISTS for a file there, PATH_NOT_REGULAR for a link."""
    if os.path.islink(path):
        raise check.Refusal('PATH_NOT_REGULAR')
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    except FileExistsError:
        raise check.Refusal('OUTPUT_EXISTS') from None
    try:
        _write_all(fd, raw)
    finally:
        os.close(fd)


def replace_file(path, raw: bytes) -> None:
    """A work-directory state file, complete or absent for every reader (written beside it, then renamed)."""
    beside = f'{path}.new'
    fd = os.open(beside, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    try:
        _write_all(fd, raw)
    finally:
        os.close(fd)
    os.replace(beside, path)


def existing_dir(path, code) -> Path:
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        raise check.Refusal(code) from None
    if stat.S_ISLNK(info.st_mode):
        raise check.Refusal('PATH_NOT_REGULAR')
    if not stat.S_ISDIR(info.st_mode):
        raise check.Refusal(code)
    return Path(os.path.abspath(path))


def complete(raw: bytes) -> bytes:
    """The complete lines of a `.jsonl` file: a line still being written is not one."""
    return raw[:raw.rfind(b'\n') + 1]


def read_samples(records: Path) -> tuple[list[dict], bytes]:
    """The validated, chained samples written so far and their bytes (none when the file is absent). A file
    above LINES_LIMIT is RECORD_INVALID, never read as its first bytes."""
    raw = read_file(records / 'samples.jsonl', check.LINES_LIMIT)
    if raw is not None and len(raw) > check.LINES_LIMIT:
        raise check.Refusal('RECORD_INVALID')
    raw = b'' if raw is None else complete(raw)
    return check.read_samples(raw), raw


def read_rows(records: Path, name: str) -> list[dict]:
    """The validated rows of blocks.jsonl or critical_heights.jsonl. RECORD_INVALID."""
    raw = read_file(records / name, check.LINES_LIMIT)
    try:
        if raw is None or len(raw) > check.LINES_LIMIT:
            raise ValueError('rows')
        rows = [json.loads(text) for text in complete(raw).split(b'\n')[:-1]]
    except ValueError:
        raise check.Refusal('RECORD_INVALID') from None
    check.validate_record(name, rows)
    return rows


def read_record(path: Path, name: str) -> dict:
    """One validated `.json` record. RECORD_INVALID."""
    raw = read_file(path, check.SMALL_LIMIT)
    try:
        if raw is None or len(raw) > check.SMALL_LIMIT:
            raise ValueError('record')
        value = json.loads(raw)
    except ValueError:
        raise check.Refusal('RECORD_INVALID') from None
    check.validate_record(name, value)
    return value


class Lines:
    """An append-only `.jsonl` record: each line is one `os.write`, and no line is ever rewritten."""

    def __init__(self, path, new: bool):
        if new:
            write_new(path, b'')
            self.count = 0
        else:
            raw = read_file(path, check.LINES_LIMIT)
            if raw is None or not (raw == b'' or raw.endswith(b'\n')):
                raise check.Refusal('RECORD_INVALID')
            self.count = raw.count(b'\n')
        self.fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW)

    def append(self, value: dict) -> bytes:
        raw = check.line(value)
        if os.write(self.fd, raw) != len(raw):
            raise OSError('a line was not written whole')
        os.fsync(self.fd)
        self.count += 1
        return raw

    def close(self) -> None:
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None


# ------------------------------------------------------------------------------- the world outside ----
class Clock:
    """The three clocks of section 4, read in that order by the caller, and the one way to wait."""

    def monotonic_ns(self) -> int:
        return time.monotonic_ns()

    def boottime_ns(self) -> int:
        return time.clock_gettime_ns(time.CLOCK_BOOTTIME)

    def realtime_ns(self) -> int:
        return time.time_ns()

    def wait_until(self, monotonic_ns: int, wake=None) -> None:
        """Sleeps until the monotonic clock reaches the value; `wake` (a threading.Event) ends it early."""
        seconds = (monotonic_ns - time.monotonic_ns()) / NS
        if seconds > 0:
            if wake is None:
                time.sleep(seconds)
            else:
                wake.wait(seconds)


class Node:
    """One node: its binaries, its data directory under the work directory, and its RPC through `bitcoin-cli`."""

    def __init__(self, key: str, bin_dir, work):
        self.key = key
        self.bin_dir = Path(bin_dir)
        self.datadir = Path(work) / f'node-{key}'

    def binary_sha256(self) -> str:
        """The SHA-256 of `bitcoind`; `bitcoin-cli` is there too. NODE_BINARY_MISSING."""
        digest = hashlib.sha256()
        try:
            if not (self.bin_dir / 'bitcoin-cli').is_file():
                raise OSError('bitcoin-cli')
            with open(self.bin_dir / 'bitcoind', 'rb') as stream:
                if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                    raise OSError('bitcoind')
                for chunk in iter(lambda: stream.read(SCAN_CHUNK), b''):
                    digest.update(chunk)
        except OSError:
            raise check.Refusal('NODE_BINARY_MISSING') from None
        return digest.hexdigest()

    def launch(self, challenge: str) -> int:
        """Starts the node in its own new session on a new data directory, with its own RPC auth line for the public
        fixture user (a fresh salt); the session leader's pid."""
        os.mkdir(self.datadir)
        try:
            process = subprocess.Popen(
                [str(self.bin_dir / 'bitcoind'), *node_args(self.key, str(self.datadir), challenge, auth_line())],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True, cwd=str(self.datadir))
        except OSError:
            raise check.Refusal('NODE_BINARY_MISSING') from None
        return _let_go(process)

    def call(self, method: str, *params):
        """One RPC's answer: text for `TEXT_METHODS`, else parsed JSON. NodeError when the node does not answer.
        `bitcoin-cli` authenticates by itself; its error text is discarded, never read."""
        command = [str(self.bin_dir / 'bitcoin-cli'),
                   *(arg.format(datadir=self.datadir, rpc=check.PORTS[self.key]['rpc'], seconds=check.RPC_SECONDS)
                     for arg in CLI_ARGS), method, *(str(param) for param in params)]
        try:
            done = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL, timeout=check.RPC_SECONDS + 5, check=False)
        except (OSError, subprocess.TimeoutExpired):
            raise NodeError(method) from None
        if done.returncode != 0 or len(done.stdout) > ANSWER_LIMIT:
            raise NodeError(method)
        try:
            text = done.stdout.decode('ascii').strip()
            return text if method in TEXT_METHODS else json.loads(text)
        except ValueError:
            raise NodeError(method) from None

    def pid(self):
        """The integer in the node's pid file, or None."""
        try:
            with open(self.datadir / 'signet' / 'bitcoind.pid', 'rb') as stream:
                text = stream.read(32).strip()
        except OSError:
            return None
        return int(text) if text.isdigit() and len(text) <= 18 else None

    def log_path(self) -> Path:
        return self.datadir / 'signet' / 'debug.log'


class Host:
    """The machine: its identity and clock facts, and the sessions this attempt started. A session is named by
    its leader's pid and that process's start time, so a pid the kernel gave to another process is never
    signalled or counted."""

    @staticmethod
    def _stat(pid):
        """(state, session id, start time in clock ticks) of a process, or None."""
        try:
            text = Path(f'/proc/{pid}/stat').read_text(encoding='ascii', errors='replace')
            fields = text[text.rindex(')') + 2:].split()
            return fields[0], int(fields[3]), int(fields[19])
        except (OSError, ValueError, IndexError):
            return None

    def ident(self, pid: int) -> dict:
        found = self._stat(pid)
        return {'pid': pid, 'start_ticks': 0 if found is None else found[2]}

    def _ours(self, ident) -> bool:
        leader = self._stat(ident['pid'])
        return leader is None or leader[2] == ident['start_ticks']

    def alive(self, ident) -> bool:
        leader = self._stat(ident['pid'])
        return leader is not None and leader[0] != 'Z' and leader[2] == ident['start_ticks']

    def left(self, ident) -> int:
        """The processes left in that session (a zombie holds no port and no file)."""
        if not self._ours(ident):
            return 0
        count = 0
        for entry in os.listdir('/proc'):
            if entry.isdigit():
                found = self._stat(entry)
                if found is not None and found[0] != 'Z' and found[1] == ident['pid']:
                    count += 1
        return count

    def terminate(self, ident) -> None:
        """Asks the session's leader to stop (SIGTERM)."""
        if self.alive(ident):
            try:
                os.kill(ident['pid'], signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                pass

    def strays(self, paths, leaders) -> int:
        """F3: the live processes (not zombies) of one of `paths` (an executable's absolute path, as
        `/proc/<pid>/exe` names it) whose session is none of `leaders`: a tick a killed monitor left behind runs in
        a session of its own."""
        wanted = {os.fsencode(str(path)) for path in paths}
        count = 0
        for entry in os.listdir('/proc'):
            if entry.isdigit():
                found = self._stat(entry)
                if found is None or found[0] == 'Z' or found[1] in leaders:
                    continue
                try:
                    exe = os.readlink(os.fsencode(f'/proc/{entry}/exe'))
                except OSError:
                    continue
                if exe.removesuffix(b' (deleted)') in wanted:
                    count += 1
        return count

    def kill_session(self, ident) -> None:
        """SIGKILL to the session's process group, when anything of it is left."""
        if self.left(ident):
            try:
                os.killpg(ident['pid'], signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass

    def spawn_daemon(self, records: Path, work: Path) -> dict:
        """The daemon in its own new session and process group, so it outlives the `start` step."""
        streams = [os.open(work / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                   for name in (DAEMON_LOG_NAMES['out'], DAEMON_LOG_NAMES['err'])]
        try:
            process = subprocess.Popen(
                [sys.executable or 'python3', '-B', str(Path(__file__).resolve()), 'daemon',
                 '--records', str(records), '--work', str(work)],
                stdin=subprocess.DEVNULL, stdout=streams[0], stderr=streams[1], start_new_session=True,
                cwd=str(work), env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
        finally:
            for fd in streams:
                os.close(fd)
        return self.ident(_let_go(process))

    def boot_id(self) -> str:
        return Path(BOOT_ID_PATH).read_text(encoding='ascii').strip()

    def home(self) -> str:
        """The runner user's home directory, as a node started by this user names it."""
        return os.path.expanduser('~')

    def clock_info(self) -> dict:
        """The kernel's clocksource ('' when not readable) and whether the clock is NTP-synchronized (or None)."""
        try:
            source = Path(CLOCKSOURCE_PATH).read_text(encoding='ascii').strip()
        except (OSError, ValueError):
            source = ''
        try:
            done = subprocess.run(['timedatectl', 'show', '--property=NTPSynchronized', '--value'],
                                  stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                  timeout=10, check=False)
            synchronized = {b'yes': True, b'no': False}.get(done.stdout.strip()) if done.returncode == 0 else None
        except (OSError, subprocess.TimeoutExpired):
            synchronized = None
        return {'source': source if 1 <= len(source) <= 32 else '', 'ntp_synchronized': synchronized}

    def facts(self, work: Path) -> dict:
        memory = 0
        try:
            for text in Path('/proc/meminfo').read_text(encoding='ascii', errors='replace').splitlines():
                if text.startswith('MemTotal:'):
                    memory = int(text.split()[1])
        except (OSError, ValueError, IndexError):
            memory = 0
        return {'nproc': os.cpu_count() or 0, 'mem_total_kb': memory,
                'disk_free_kb': shutil.disk_usage(work).free // 1024, 'kernel': platform.release()[:64],
                'python': platform.python_version()[:64]}


class Tools:
    """The two Rust tools of the attempt: B's fixture (each run a child of the caller, so a follow runs in the
    daemon's session) and the monitor loop over `bitagi monitor tick` (its own new session)."""

    def run(self, argv, timeout: int):
        """One run of the fixture: (its exit code or None, stdout, stderr, None), or (None, b'', b'', error) with
        error SPAWN_FAILED or TIMEOUT (the child killed and awaited). A signal's end is 128 + its number."""
        try:
            process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE)
        except OSError:
            return None, b'', b'', 'SPAWN_FAILED'
        try:
            out, err = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
            return None, b'', b'', 'TIMEOUT'
        code = process.returncode
        return (code if code >= 0 else 128 - code), out, err, None

    def spawn_monitor(self, argv, folder: Path) -> int:
        """The monitor loop in its own new session and process group (it outlives the `start` step), its output
        and error output in `folder` (never dropped: MONITOR_LOG_V1 section 1) and its temporary folder under
        `folder` (TMPDIR). The leader's pid; MONITOR_NOT_STARTED when it cannot be spawned."""
        streams = [os.open(folder / MONITOR_NAMES[name], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                   for name in ('out', 'err')]
        try:
            process = subprocess.Popen(
                argv, stdin=subprocess.DEVNULL, stdout=streams[0], stderr=streams[1], start_new_session=True,
                cwd=str(folder),
                env=dict(os.environ, TMPDIR=str(folder / MONITOR_NAMES['tmp']), PYTHONDONTWRITEBYTECODE='1'))
        except OSError:
            raise check.Refusal('MONITOR_NOT_STARTED') from None
        finally:
            for fd in streams:
                os.close(fd)
        return _let_go(process)


class World:
    """What the commands reach outside their record files. The tests pass fakes with these four members."""

    def __init__(self, clock=None, host=None, node=None, tools=None):
        self.clock = Clock() if clock is None else clock
        self.host = Host() if host is None else host
        self.node = Node if node is None else node       # node(key, bin_dir, work)
        self.tools = Tools() if tools is None else tools


def pause(clock, seconds, wake=None) -> None:
    clock.wait_until(clock.monotonic_ns() + int(seconds * NS), wake)


# --------------------------------------------------------------------------------------- node reads ----
def rpc_object(node, method: str, *params) -> dict:
    value = node.call(method, *params)
    if type(value) is not dict:
        raise NodeError(method)
    return value


def block_hash(node, height: int) -> str:
    value = node.call('getblockhash', height)
    if not is_hash(value):
        raise NodeError('getblockhash')
    return value


def not_ok() -> dict:
    return dict(dict.fromkeys(NODE_KEYS), ok=False)


def read_node(node) -> dict:
    """One node's part of a sample (section 4.3): every value, or `ok` false and nulls."""
    try:
        info = rpc_object(node, 'getblockchaininfo')
        net = rpc_object(node, 'getnetworkinfo')
        pool = rpc_object(node, 'getmempoolinfo')
        value = {'ok': True, 'pid': node.pid(), 'uptime': node.call('uptime'), 'chain': info.get('chain'),
                 'blocks': info.get('blocks'), 'bestblockhash': info.get('bestblockhash'),
                 'mediantime': info.get('mediantime'), 'signet_challenge': info.get('signet_challenge'),
                 'genesis_hash': block_hash(node, 0), 'connections': net.get('connections'),
                 'networkactive': net.get('networkactive'), 'mempool_size': pool.get('size')}
    except NodeError:
        return not_ok()
    counts = all(is_count(value[name]) for name in ('uptime', 'blocks', 'mediantime', 'connections', 'mempool_size'))
    texts = (type(value['chain']) is str and CHAIN_NAME.fullmatch(value['chain']) is not None
             and type(value['signet_challenge']) is str
             and CHALLENGE_HEX.fullmatch(value['signet_challenge']) is not None)
    if not (counts and texts and is_count(value['pid'], 1) and is_hash(value['bestblockhash'])
            and type(value['networkactive']) is bool):
        return not_ok()
    return value


def make_block(node, height: int):
    """One try at the block of `height` on its producer: (the hash or None, whether `generatetodescriptor` was
    called, whether to wait before the next try). No call is made unless the node's tip is the block before: a
    block an earlier call left behind is taken as it is, and no block is ever made on a lower tip."""
    try:
        count = node.call('getblockcount')
        if not is_count(count):
            raise NodeError('getblockcount')
        if count >= height:
            return block_hash(node, height), False, False
        if count < height - 1:
            return None, False, True
    except NodeError:
        return None, False, True
    try:
        answer = node.call('generatetodescriptor', 1, COINBASE_DESCRIPTOR, GENERATE_TRIES)
    except NodeError:
        return None, True, True
    if type(answer) is list and len(answer) == 1 and is_hash(answer[0]):
        return answer[0], True, False
    return None, True, False       # the tries ran out: the next call follows at once


def seen_on(node, height: int, block: str) -> bool:
    try:
        return block_hash(node, height) == block
    except NodeError:
        return False


def block_row(n, phase, height, block, producer, tries, produced, seen) -> dict:
    return {'n': n, 'phase': phase, 'height': height, 'hash': block, 'producer': producer, 'tries': max(tries, 1),
            'produced_monotonic_ns': produced[0], 'produced_realtime_ns': produced[1],
            'seen_other_monotonic_ns': None if seen is None else seen[0],
            'seen_other_realtime_ns': None if seen is None else seen[1]}


class Critical:
    """critical_heights.jsonl (section 4.5) and the incidents folder: one writer at a time, here under a lock."""

    def __init__(self, world, nodes, records: Path, declaration: dict, new: bool):
        self.clock, self.nodes, self.records = world.clock, nodes, records
        self.run_id, self.attempt = declaration['run_id'], declaration['attempt']
        self.lines = Lines(records / 'critical_heights.jsonl', new)
        self.lock = threading.Lock()

    def read(self, kind: str, read: str, height: int, seq=None, node=None):
        """The row of one read, or None when a node did not answer (no row is written then)."""
        try:
            hash_a = block_hash(self.nodes['a'], height)
            hash_b = block_hash(self.nodes['b'], height)
        except NodeError:
            return None
        with self.lock:
            row = {'n': self.lines.count, 'kind': kind, 'read': read, 'height': height, 'hash_a': hash_a,
                   'hash_b': hash_b, 'agree': hash_a == hash_b, 'seq': seq, 'node': node,
                   'monotonic_ns': self.clock.monotonic_ns(), 'realtime_ns': self.clock.realtime_ns()}
            self.lines.append(row)
            if not row['agree']:      # the observation continues; the report recounts from the rows
                write_new(self.records / 'incidents' / f's14-disagreement-{row["n"]}.json',
                          check.line(check.disagreement(self.run_id, self.attempt, row)))
        return row


# ------------------------------------------------------------------------------------------ replay ----
def replay_build(world, work: Path, records: Path, declaration: dict, floor: dict, genesis: str) -> dict:
    """S5r: the replay store at H0 - 1, built by the fixture when the H0_MINUS_1 / FIRST read (`floor`) agrees:
    `replay_build.json` with BUILT when the fixture exits 0 with one BUILD line of this network, genesis, challenge,
    H0, as-of height and block, and a `store_path` that is the real path of `<work>/replay/store.sqlite3`. A read
    that disagrees builds nothing (NOT_BUILT_S14_DISAGREEMENT) and `start` goes on: the attempt has S14 FAIL. Any
    other outcome is written (REFUSED, TIMEOUT, SPAWN_FAILED, OUTPUT_INVALID) and then refused
    (REPLAY_BUILD_FAILED). The fixture's text is never copied."""
    clock, constants = world.clock, declaration['constants']
    value = {'format': check.FORMAT_REPLAY_BUILD, 'run_id': declaration['run_id'], 'attempt': declaration['attempt'],
             'result': 'NOT_BUILT_S14_DISAGREEMENT', 'exit': None, 'refusal': None, 'started_monotonic_ns': None,
             'ended_monotonic_ns': None, 'line': None, 'label': check.REPLAY_LABEL}
    if floor['agree']:
        h0, challenge = constants['h0'], constants['signet_challenge_hex']
        started = clock.monotonic_ns()
        code, out, err, error = world.tools.run(fixture_argv(work, h0, genesis, challenge, floor['hash_a']),
                                                REPLAY_SECONDS)
        value.update(started_monotonic_ns=started, ended_monotonic_ns=clock.monotonic_ns(), exit=code)
        line = check.fixture_line(out, 'BUILD') if error is None and code == 0 else None
        if error is not None:
            value['result'] = error
        elif code != 0:
            value.update(result='REFUSED', refusal=check.fixture_refusal(err)[0])
        elif line is None or not (
                line['genesis_hash_display'] == genesis and line['signet_challenge_hex'] == challenge
                and line['first_effective_height'] == h0 and line['as_of_height'] == h0 - 1
                and line['as_of_block_hash_display'] == floor['hash_a']
                and line['store_path'] == os.path.realpath(Path(work) / 'replay' / 'store.sqlite3')):
            value['result'] = 'OUTPUT_INVALID'
        else:
            value.update(result='BUILT', line={key: item for key, item in line.items() if key != 'store_path'})
    check.validate_record('replay_build.json', value)
    write_new(records / 'replay_build.json', check.line(value))
    if value['result'] not in ('BUILT', 'NOT_BUILT_S14_DISAGREEMENT'):
        raise check.Refusal('REPLAY_BUILD_FAILED')
    return value


def follow(world, work: Path, lines: Lines, read: str, constants: dict, genesis: str) -> dict:
    """One `--follow` of the replay store (the daemon's POLL rows, finish's FINAL row): its `replay.jsonl` row. A
    follow that the fixture refuses is a row (its code from the one stderr line, never the text), not a refusal."""
    clock = world.clock
    started = (clock.monotonic_ns(), clock.realtime_ns())
    code, out, err, error = world.tools.run(
        fixture_argv(work, constants['h0'], genesis, constants['signet_challenge_hex']), REPLAY_SECONDS)
    row = {'n': lines.count, 'read': read, 'started_monotonic_ns': started[0], 'started_realtime_ns': started[1],
           'ended_monotonic_ns': clock.monotonic_ns(), 'exit': code, 'result': error, 'refusal': None,
           'refusal_node': None, 'line': None}
    if error is None and code != 0:
        row['result'] = 'REFUSED'
        row['refusal'], row['refusal_node'] = check.fixture_refusal(err)
    elif error is None:
        row['line'] = check.fixture_line(out, 'FOLLOW')
        row['result'] = 'OUTPUT_INVALID' if row['line'] is None else 'FOLLOWED'
    lines.append(row)
    return row


def file_sha256(path: Path):
    """The SHA-256 of a regular file that is not a link, or None (final.json's replay_store_sha256)."""
    digest = hashlib.sha256()
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        return None
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            return None
        for chunk in iter(lambda: os.read(fd, SCAN_CHUNK), b''):
            digest.update(chunk)
    finally:
        os.close(fd)
    return digest.hexdigest()


# ----------------------------------------------------------------------------------------- monitor ----
def start_monitor(world, work: Path, records: Path, genesis: str, declaration: dict, build: dict, state: dict):
    """S6m: `monitor/request.json` (monitor_request(), in the work directory and in the records) and the monitor
    loop in its own new session (its leader in `state['monitor']`), then at most MONITOR_START_SECONDS for its
    START line (MONITOR_NOT_STARTED, also when the loop is gone before it). Nothing is started without a built
    store: the request names the build's deployment id."""
    if build['result'] != 'BUILT':
        return
    clock, constants = world.clock, declaration['constants']
    folder = work / 'monitor'
    os.makedirs(folder / MONITOR_NAMES['tmp'])
    os.makedirs(records / 'monitor', exist_ok=True)
    raw = check.line(check.monitor_request(genesis, constants['signet_challenge_hex'],
                                           build['line']['deployment_id_internal'], constants['h0']))
    write_new(folder / MONITOR_NAMES['request'], raw)
    write_new(records / check.MONITOR_FILES[0], raw)
    state['monitor'] = world.host.ident(world.tools.spawn_monitor(monitor_argv(work), folder))
    save_state(work, state)
    deadline = clock.monotonic_ns() + MONITOR_START_SECONDS * NS
    while True:
        first = read_file(folder / MONITOR_NAMES['log'], SMALL_READ)
        first = b'' if first is None else first[:first.find(b'\n') + 1]
        try:
            if first and json.loads(first).get('kind') == 'START':
                return
        except (ValueError, AttributeError):
            pass
        if not world.host.alive(state['monitor']) or clock.monotonic_ns() >= deadline:
            raise check.Refusal('MONITOR_NOT_STARTED')
        pause(clock, POLL_SECONDS)


def stop_monitor(world, ident) -> None:
    """F1m: SIGTERM to the monitor loop's leader (it ends a running tick, writes STOP `SIGNAL_SIGTERM` and exits 0),
    at most MONITOR_STOP_SECONDS for it, then its session is killed and awaited."""
    clock, host = world.clock, world.host
    host.terminate(ident)
    deadline = clock.monotonic_ns() + MONITOR_STOP_SECONDS * NS
    while host.alive(ident) and clock.monotonic_ns() < deadline:
        pause(clock, POLL_SECONDS)
    host.kill_session(ident)
    deadline = clock.monotonic_ns() + LEFT_SECONDS * NS
    while host.left(ident) and clock.monotonic_ns() < deadline:
        pause(clock, POLL_SECONDS)


def monitor_end(path: Path) -> dict:
    """final.json's `exit` and `stop_reason` of the monitor: its log's last complete line, when it is a STOP line of
    a closed reason; nulls otherwise (the loop was killed or never started)."""
    end = {'exit': None, 'stop_reason': None}
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        return end
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            return end
        size = os.fstat(fd).st_size
        os.lseek(fd, max(0, size - check.SMALL_LIMIT), os.SEEK_SET)
        tail = os.read(fd, check.SMALL_LIMIT)
    finally:
        os.close(fd)
    lines = tail.split(b'\n')[:-1]
    try:
        value = json.loads(lines[-1]) if lines else None
    except ValueError:
        value = None
    if type(value) is dict and value.get('kind') == 'STOP' and value.get('reason') in check.MONITOR_STOPS and (
            type(value.get('exit')) is int and 0 <= value['exit'] <= 255):
        end.update(exit=value['exit'], stop_reason=value['reason'])
    return end


# ------------------------------------------------------------------------------------- work state ----
def save_state(work: Path, state: dict) -> None:
    replace_file(work / STATE_NAME, check.line(state))


def sessions_of(state: dict) -> list[dict]:
    """The sessions `start` recorded: the nodes', the daemon's and the monitor's (each when started)."""
    return [*state['nodes'].values()] + [state[name] for name in ('daemon', 'monitor') if state[name] is not None]


def load_state(work: Path) -> dict:
    """The sessions `start` recorded. DAEMON_STATE_MISSING when the file is absent or not a state."""
    raw = read_file(work / STATE_NAME, check.SMALL_LIMIT)
    try:
        value = json.loads(raw) if raw is not None else None
        sessions = sessions_of(value)
        valid = (set(value) == {'nodes', 'daemon', 'monitor'} and set(value['nodes']) <= set(check.NODES)
                 and all(is_count(entry['pid'], 1) and is_count(entry['start_ticks']) for entry in sessions)
                 and all(type(entry['bin']) is str for entry in value['nodes'].values()))
    except (ValueError, TypeError, KeyError, AttributeError):
        valid = False
    if not valid:
        raise check.Refusal('DAEMON_STATE_MISSING')
    return value


def read_stop(work: Path):
    """The daemon's own stop reason (STOP_RULE or DEADLINE), or None while it has not stopped by its rule."""
    raw = read_file(work / STOP_NAME, check.SMALL_LIMIT)
    if raw is None:
        return None
    reason = json.loads(raw).get('stop_reason')
    if reason not in DAEMON_STOPS:
        raise ValueError('daemon stop')
    return reason


def daemon_state(world, work: Path, ident) -> tuple[str, str | None]:
    """(RUNNING, None), (STOPPED, its reason) or (DEAD, None). The process is looked at first: a daemon writes
    its stop reason before it exits."""
    alive = world.host.alive(ident)
    reason = read_stop(work)
    if reason is not None:
        return 'STOPPED', reason
    return ('RUNNING', None) if alive else ('DEAD', None)


def session_nodes(world, state: dict, work: Path) -> dict:
    return {key: world.node(key, entry['bin'], work) for key, entry in state['nodes'].items()}


def kill_sessions(world, state: dict) -> None:
    for entry in sessions_of(state):
        world.host.kill_session(entry)


# -------------------------------------------------------------------------------------------- daemon ----
class Daemon:
    """The sampler, the block producer and the replayer (sections 4.3, 4.4, 4.7, 5). `sample_step`, `produce_step`
    and `replay_step` each do one pass and return the monotonic time of their next pass (None once stopped); `run`
    drives the sampler in this thread and the other two in theirs."""

    def __init__(self, world, records: Path, work: Path, pid=None):
        self.world, self.clock = world, world.clock
        self.records, self.work = Path(records), Path(work)
        self.declaration = check.read_declaration(self.records / 'declaration.json')
        self.constants = self.declaration['constants']
        self.genesis = read_record(self.records / 'environment.json', 'environment.json')['genesis_hash']
        # the replayer follows only a store `start` built (S5r)
        self.replaying = read_record(self.records / 'replay_build.json', 'replay_build.json')['result'] == 'BUILT'
        state = load_state(self.work)
        if set(state['nodes']) != set(check.NODES):
            raise check.Refusal('DAEMON_STATE_MISSING')
        self.nodes = session_nodes(world, state, self.work)
        self.pid = os.getpid() if pid is None else pid
        self.samples = Lines(self.records / 'samples.jsonl', new=True)
        self.blocks = Lines(self.records / 'blocks.jsonl', new=False)
        self.replays = Lines(self.records / 'replay.jsonl', new=True)
        self.critical = Critical(world, self.nodes, self.records, self.declaration, new=False)
        self.stop = threading.Event()       # set by the stopping rule, after a stop request, or by a failure
        self.stop_reason = None             # STOP_RULE or DEADLINE; None for a stop request
        self.asked = False                  # a stop request (a signal handler only sets this)
        self.failure = None
        self.t0 = None
        self.previous, self.prev_sha256 = None, check.ZERO_HASH
        self.tips = {}                      # each node's part of its last `ok` sample (tip replacement)
        self.window, self.forks = [], []    # the samples of the open interval; this run's FORK_POINT rows
        self.block_index, self.tries, self.pending, self.h0_read = 0, 0, None, False

    # ---- the sampler
    def sample_step(self):
        """The deadline check, one sample, the stopping rule. Returns when the next sample is due."""
        if self.stop.is_set():
            return None
        c = self.constants
        if self.t0 is not None and (
                self.clock.monotonic_ns() >= self.t0 + c['checkpoints'] * c['checkpoint_seconds'] * NS):
            return self._stopped('DEADLINE')
        sample = self._take()
        if self.t0 is None:
            self.t0 = sample['monotonic_ns']
        length = self._open_interval(sample)
        if length is not None and length >= (c['required_seconds'] + c['stop_margin_seconds']) * NS:
            return self._stopped('STOP_RULE')
        return sample['monotonic_ns'] + c['sample_seconds'] * NS

    def _stopped(self, reason):
        self.stop_reason = reason
        self.stop.set()
        return None

    def _take(self) -> dict:
        seq = self.samples.count
        clocks = (self.clock.monotonic_ns(), self.clock.boottime_ns(), self.clock.realtime_ns())
        nodes = {key: read_node(self.nodes[key]) for key in check.NODES}
        for key in check.NODES:             # tip replacement (section 4.3), against the node's last `ok` sample
            before = self.tips.get(key)
            if before is None or not nodes[key]['ok']:
                continue
            try:
                replaced = (nodes[key]['blocks'] < before['blocks']
                            or block_hash(self.nodes[key], before['blocks']) != before['bestblockhash'])
                height = self._fork_height(key, before['bestblockhash']) if replaced else None
            except NodeError:               # a read of that node did not answer: the sample is a failed one
                nodes[key] = not_ok()
                continue
            if height is not None:
                row = self.critical.read('FORK_POINT', 'EVENT', height, seq, key)
                if row is None:             # no row was written: a failed sample, and the fork point stays due
                    nodes[key] = not_ok()   # (the tip compared next time is still the one before the fork)
                    continue
                self.forks.append(row)
        for key in check.NODES:
            if nodes[key]['ok']:
                self.tips[key] = nodes[key]
        sample = {'seq': seq, 'prev_sha256': self.prev_sha256, 'monotonic_ns': clocks[0], 'boottime_ns': clocks[1],
                  'realtime_ns': clocks[2], 'boot_id': self.world.host.boot_id(), 'sampler_pid': self.pid,
                  'nodes': nodes}
        check.validate_sample(sample, seq, self.prev_sha256)
        self.prev_sha256 = check.line_sha256(self.samples.append(sample))
        self.previous = sample
        return sample

    def _fork_height(self, key: str, tip: str) -> int:
        """Walks back from the replaced tip to the first header still on that node's chain."""
        for _ in range(MAX_FORK_WALK):
            header = rpc_object(self.nodes[key], 'getblockheader', tip)
            confirmations, height = header.get('confirmations'), header.get('height')
            if type(confirmations) is not int or not is_count(height):
                raise NodeError('getblockheader')
            if confirmations >= 1:
                return height
            tip = header.get('previousblockhash')
            if not is_hash(tip):
                raise NodeError('getblockheader')
        raise NodeError('getblockheader')

    def _open_interval(self, sample: dict):
        """The length in ns of the interval holding this sample (None when it holds none), by the checker's
        `intervals()` over the samples of the open interval only: a sample before the open interval's first
        cannot change it, since that first sample opened it whatever came before."""
        self.window.append(sample)
        current = check.intervals(self.window, self.forks, self.constants, self.genesis)['current']
        if current is None:
            self.window = []
            return None
        self.window = [item for item in self.window if item['seq'] >= current['first_seq']]
        return current['monotonic_ns']

    # ---- the producer
    def produce_step(self):
        """At most one `generatetodescriptor` call, or one poll of the other node. Returns when to come back."""
        c = self.constants
        stopping = self.stop.is_set()
        if self.pending is not None:
            block = self.pending
            seen = None
            if seen_on(self.nodes[other(block['producer'])], block['height'], block['hash']):
                seen = (self.clock.monotonic_ns(), self.clock.realtime_ns())
            elif not stopping and self.clock.monotonic_ns() < block['give_up_ns']:
                return self.clock.monotonic_ns() + POLL_SECONDS * NS
            self.blocks.append(block_row(self.blocks.count, 'INTERVAL', block['height'], block['hash'],
                                         block['producer'], block['tries'], block['produced'], seen))
            self.pending, self.tries = None, 0
            self.block_index += 1
        if not self.h0_read and self.block_index > 0:       # H0 / FIRST, once block 0 is on both nodes
            self.h0_read = self.critical.read('H0', 'FIRST', c['h0']) is not None
        if stopping:
            return None
        due = self.t0 + (self.block_index + 1) * c['block_seconds'] * NS
        if self.clock.monotonic_ns() < due:
            return due
        producer = check.NODES[self.block_index % 2]
        block, called, wait = make_block(self.nodes[producer], c['h0'] + self.block_index)
        self.tries += called
        now = self.clock.monotonic_ns()
        if block is None:
            return now + (POLL_SECONDS * NS if wait else 0)
        self.pending = {'height': c['h0'] + self.block_index, 'hash': block, 'producer': producer,
                        'tries': self.tries, 'produced': (now, self.clock.realtime_ns()),
                        'give_up_ns': now + min(SEEN_SECONDS, c['block_seconds']) * NS}
        return now

    # ---- the replayer
    def replay_step(self):
        """At most one `--follow` (A's decision 7): one every `sample_seconds` from sample 0, one at a time, never
        after the stop. Returns when the next is due (at once after a follow longer than the period)."""
        if self.stop.is_set() or not self.replaying:
            return None
        started = self.clock.monotonic_ns()
        follow(self.world, self.work, self.replays, 'POLL', self.constants, self.genesis)
        return started + self.constants['sample_seconds'] * NS

    def _loop(self, step):
        try:
            due = step()
            while due is not None:
                self.clock.wait_until(due, self.stop)
                due = step()
        except BaseException as failure:    # noqa: BLE001 - the daemon ends with it; nothing is produced blind
            self.failure = failure
            self.stop.set()

    def _produce_loop(self):
        self._loop(self.produce_step)

    def _replay_loop(self):
        self._loop(self.replay_step)

    # ---- the whole
    def request_stop(self) -> None:
        """A stop request (`finish`, or a signal): safe inside a signal handler, since it takes no lock. The
        sampler's thread sees it within POLL_SECONDS."""
        self.asked = True

    def run(self) -> None:
        threads = [threading.Thread(target=self._produce_loop, name='producer', daemon=True),
                   threading.Thread(target=self._replay_loop, name='replayer', daemon=True)]
        try:
            due = self.sample_step()        # sample 0: t0
            for thread in threads:
                thread.start()
            while due is not None:
                while not (self.asked or self.stop.is_set()) and self.clock.monotonic_ns() < due:
                    self.clock.wait_until(min(due, self.clock.monotonic_ns() + POLL_SECONDS * NS), self.stop)
                if self.asked:
                    self.stop.set()
                due = self.sample_step()
        finally:
            self.stop.set()
        for thread in threads:              # a call or a follow in flight is awaited, not cut
            thread.join(DAEMON_STOP_SECONDS)
        if self.failure is not None:
            raise self.failure
        if any(thread.is_alive() for thread in threads):
            raise RuntimeError('a pass did not end')
        self.close()

    def close(self) -> None:
        """After both passes ended: the stop reason for the later commands, when the daemon stopped by its rule."""
        if self.stop_reason in DAEMON_STOPS:
            replace_file(self.work / STOP_NAME,
                         check.line({'samples': self.samples.count, 'stop_reason': self.stop_reason}))
        for lines in (self.samples, self.blocks, self.replays, self.critical.lines):
            lines.close()


# ------------------------------------------------------------------------------------------- commands ----
def start_command(args, world, environ) -> dict:
    clock = world.clock
    began = (clock.monotonic_ns(), clock.realtime_ns())
    # S1
    declaration = check.read_declaration(Path(args.declaration))
    declaration_raw = read_file(args.declaration, check.SMALL_LIMIT)
    if declaration_raw != check.line(declaration):
        raise check.Refusal('DECLARATION_INVALID')
    if (environ.get('GITHUB_RUN_ID'), environ.get('GITHUB_SHA'), environ.get('GITHUB_RUN_ATTEMPT')) != (
            str(declaration['run_id']), declaration['head_sha'], '1') or declaration['run_attempt'] != 1:
        raise check.Refusal('DECLARATION_OTHER_RUN')
    if args.source_sha256 != declaration['source_sha256']:
        raise check.Refusal('SOURCE_MISMATCH')
    constants = declaration['constants']
    challenge, h0 = constants['signet_challenge_hex'], constants['h0']
    records, work = Path(os.path.abspath(args.records)), Path(os.path.abspath(args.work))
    for path in (records, work):
        if os.path.lexists(path):
            raise check.Refusal('PATH_NOT_REGULAR' if os.path.islink(path) else 'OUTPUT_EXISTS')
    try:
        for path in (records, work):
            os.makedirs(path.parent, exist_ok=True)
            os.mkdir(path)
        for name in ('incidents', 'node-logs'):
            os.mkdir(records / name)
    except FileExistsError:
        raise check.Refusal('OUTPUT_EXISTS') from None
    # S1b
    tools = copy_binaries(Path(args.bin_dir), work, declaration['binaries'])
    # S2
    nodes = {key: world.node(key, os.path.abspath(path), work)
             for key, path in zip(check.NODES, (args.node_a, args.node_b))}
    digests = {key: nodes[key].binary_sha256() for key in check.NODES}
    state = {'nodes': {}, 'daemon': None, 'monitor': None}
    try:
        for key, path in zip(check.NODES, (args.node_a, args.node_b)):
            pid = nodes[key].launch(challenge)
            state['nodes'][key] = dict(world.host.ident(pid), bin=os.path.abspath(path))
            save_state(work, state)
        # S3
        versions = await_nodes(world, nodes, challenge)
        # S4, S5
        critical = Critical(world, nodes, records, declaration, new=True)
        blocks = Lines(records / 'blocks.jsonl', new=True)
        try:
            genesis = critical.read('GENESIS', 'FIRST', 0)
            if genesis is None:
                raise check.Refusal('NODE_NOT_READY')
            premine(world, nodes, blocks, h0)
            floor = critical.read('H0_MINUS_1', 'FIRST', h0 - 1)
            if floor is None:
                raise check.Refusal('PREMINE_FAILED')
        finally:
            blocks.close()
            critical.lines.close()
        # S5r
        build = replay_build(world, work, records, declaration, floor, genesis['hash_a'])
        # S6
        environment = {
            'format': check.FORMAT_ENVIRONMENT, 'mode': declaration['mode'], 'attempt': declaration['attempt'],
            'head_sha': declaration['head_sha'], 'run_id': declaration['run_id'],
            'source_sha256': args.source_sha256,
            'nodes': {key: {'name': check.NODE_NAMES[key], 'version': versions[key],
                            'bitcoind_sha256': digests[key],
                            'args': node_args(key, f'<work>/node-{key}', challenge),
                            'p2p_port': check.PORTS[key]['p2p'], 'rpc_port': check.PORTS[key]['rpc']}
                      for key in check.NODES},
            'binaries': tools, 'signet_challenge_hex': challenge, 'genesis_hash': genesis['hash_a'], 'h0': h0,
            'boot_id': world.host.boot_id(), 'clock': world.host.clock_info(),
            'host': dict(world.host.facts(work), runner_name=environ.get('RUNNER_NAME', '')[:128]),
            'start_monotonic_ns': began[0], 'start_realtime_ns': began[1], 'labels': declaration['labels'],
            'transferability': check.TRANSFERABILITY, 'scope_b': check.SCOPE_B,
            's14_not_covered': check.S14_NOT_COVERED}
        check.validate_record('environment.json', environment)
        write_new(records / 'environment.json', check.line(environment))
        write_new(records / 'components.json', check.line(check.components()))
        for name in ('txs.jsonl', 'reserve_snapshots.jsonl'):
            write_new(records / name, check.scope_file(name))
        write_new(records / 'declaration.json', declaration_raw)
        # S6m
        start_monitor(world, work, records, genesis['hash_a'], declaration, build, state)
        # S7
        state['daemon'] = world.host.spawn_daemon(records, work)
        save_state(work, state)
        deadline = clock.monotonic_ns() + DAEMON_START_SECONDS * NS
        while True:
            raw = read_file(records / 'samples.jsonl', check.LINES_LIMIT)
            first = b'' if raw is None else raw[:raw.find(b'\n') + 1]
            if first:
                break
            if not world.host.alive(state['daemon']) or clock.monotonic_ns() >= deadline:
                raise check.Refusal('DAEMON_NOT_STARTED')
            pause(clock, POLL_SECONDS)
        check.read_samples(first)           # sample 0 itself: seq 0 after 64 zeros
        # S8
        marker = check.line(check.marker(declaration, check.line_sha256(first), clock.monotonic_ns(),
                                         clock.realtime_ns()))
        write_new(records / 'marker.json', marker)
    except BaseException:                   # a refusal before S8 leaves no marker and nothing running
        kill_sessions(world, state)
        raise
    return {'samples': 1, 'head_sha256': check.line_sha256(first), 'premine_blocks': h0 - 1,
            'marker_sha256': hashlib.sha256(marker).hexdigest()}


def copy_binaries(source: Path, work: Path, binaries: dict) -> dict:
    """S1b: the hosted build job's two binaries in `source` (regular files that are not links, executable:
    TOOL_BINARY_MISSING), each of the declaration's SHA-256 (BINARY_MISMATCH), copied into `<work>/bin/` and hashed
    again there, so every path a log names lies in the work directory. Returns environment.json's `binaries`."""
    os.mkdir(work / 'bin')
    found = {}
    for key, name in check.BINARY_NAMES.items():
        try:
            info = os.lstat(source / name)
        except OSError:
            raise check.Refusal('TOOL_BINARY_MISSING') from None
        if not stat.S_ISREG(info.st_mode) or not info.st_mode & stat.S_IXUSR:
            raise check.Refusal('TOOL_BINARY_MISSING')
        target = tool_path(work, key)
        try:
            fd = os.open(source / name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        except OSError:
            raise check.Refusal('TOOL_BINARY_MISSING') from None
        digest = hashlib.sha256()
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise check.Refusal('TOOL_BINARY_MISSING')
            out = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o755)
            try:
                for chunk in iter(lambda: os.read(fd, SCAN_CHUNK), b''):
                    digest.update(chunk)
                    _write_all(out, chunk)
            finally:
                os.close(out)
        finally:
            os.close(fd)
        if digest.hexdigest() != binaries[key + '_sha256']:
            raise check.Refusal('BINARY_MISMATCH')
        os.chmod(target, 0o755)
        found[key] = file_sha256(target)
        if found[key] != binaries[key + '_sha256']:
            raise check.Refusal('BINARY_MISMATCH')
    return found


def await_nodes(world, nodes, challenge) -> dict:
    """S3: within READY_SECONDS both nodes answer on the private Signet of that challenge and each has a peer.
    Returns each node's `getnetworkinfo` version."""
    clock = world.clock
    deadline = clock.monotonic_ns() + READY_SECONDS * NS
    answers = {}
    while True:
        for key in check.NODES:
            if key not in answers:
                try:
                    answers[key] = (rpc_object(nodes[key], 'getblockchaininfo'),
                                    rpc_object(nodes[key], 'getnetworkinfo'))
                except NodeError:
                    pass
        if len(answers) == len(check.NODES):
            break
        if clock.monotonic_ns() >= deadline:
            raise check.Refusal('NODE_NOT_READY')
        pause(clock, POLL_SECONDS)
    if any(info.get('chain') == 'main' for info, _ in answers.values()):
        raise check.Refusal('MAINNET_REFUSED')
    if any(info.get('chain') != 'signet' or info.get('signet_challenge') != challenge
           for info, _ in answers.values()):
        raise check.Refusal('UNSUPPORTED_SIGNET_CONTEXT')
    versions = {key: answers[key][1].get('version') for key in check.NODES}
    if not all(is_count(version) for version in versions.values()):
        raise check.Refusal('NODE_NOT_READY')
    while True:
        try:
            peers = [rpc_object(nodes[key], 'getnetworkinfo').get('connections') for key in check.NODES]
        except NodeError:
            peers = []
        if len(peers) == len(check.NODES) and all(is_count(count, 1) for count in peers):
            return versions
        if clock.monotonic_ns() >= deadline:
            raise check.Refusal('PEERS_NOT_CONNECTED')
        pause(clock, POLL_SECONDS)


def premine(world, nodes, blocks: Lines, h0: int) -> None:
    """S4, S5: heights 1..h0 - 1 in chunks of PREMINE_CHUNK, producers alternating from `a`; each block is on the
    other node within SEEN_SECONDS. PREMINE_FAILED."""
    clock = world.clock
    deadline = clock.monotonic_ns() + PREMINE_SECONDS * NS
    for height in range(1, h0):
        producer = check.NODES[(height - 1) // check.PREMINE_CHUNK % 2]
        tries = 0
        while True:
            block, called, wait = make_block(nodes[producer], height)
            tries += called
            if block is not None:
                break
            if clock.monotonic_ns() >= deadline:
                raise check.Refusal('PREMINE_FAILED')
            if wait:
                pause(clock, POLL_SECONDS)
        produced = (clock.monotonic_ns(), clock.realtime_ns())
        while not seen_on(nodes[other(producer)], height, block):
            if clock.monotonic_ns() >= produced[0] + SEEN_SECONDS * NS:
                raise check.Refusal('PREMINE_FAILED')
            pause(clock, POLL_SECONDS)
        seen = (clock.monotonic_ns(), clock.realtime_ns())
        blocks.append(block_row(blocks.count, 'PREMINE', height, block, producer, tries, produced, seen))


def daemon_command(args, world, environ) -> dict:
    records = existing_dir(args.records, 'RECORDS_MISSING')
    work = existing_dir(args.work, 'DAEMON_STATE_MISSING')
    daemon = Daemon(world, records, work)
    for number in (signal.SIGTERM, signal.SIGINT):
        signal.signal(number, lambda *_: daemon.request_stop())
    daemon.run()
    return {'stop_reason': daemon.stop_reason or 'FINISH', 'samples': daemon.samples.count}


def github_output(path, scheduled: bool) -> None:
    if path is None:
        return
    try:
        fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o644)
    except OSError:
        raise check.Refusal('PATH_NOT_REGULAR') from None
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise check.Refusal('PATH_NOT_REGULAR')
        _write_all(fd, b'scheduled=true\n' if scheduled else b'scheduled=false\n')
    finally:
        os.close(fd)


def checkpoint_command(args, world, environ) -> dict:
    k = args.index
    if not 1 <= k <= check.MAX_CHECKPOINTS:
        raise check.Refusal('CHECKPOINT_INDEX')
    records = existing_dir(args.records, 'RECORDS_MISSING')
    declaration = check.read_declaration(records / 'declaration.json')
    c = declaration['constants']
    if k > c['checkpoints']:
        github_output(args.github_output, False)
        return {'index': k, 'scheduled': False, 'daemon_state': None, 'seq': None, 'head_sha256': None}
    path = records / f'checkpoint-{k}.json'
    if os.path.lexists(path):               # written once
        raise check.Refusal('PATH_NOT_REGULAR' if os.path.islink(path) else 'OUTPUT_EXISTS')
    work = existing_dir(args.work, 'DAEMON_STATE_MISSING')
    ident = load_state(work)['daemon']
    if ident is None:
        raise check.Refusal('DAEMON_STATE_MISSING')
    samples, _ = read_samples(records)
    if not samples:
        raise check.Refusal('RECORD_INVALID')
    clock = world.clock
    due = samples[0]['monotonic_ns'] + k * c['checkpoint_seconds'] * NS
    state, reason = daemon_state(world, work, ident)
    while state == 'RUNNING' and clock.monotonic_ns() < due:
        clock.wait_until(min(due, clock.monotonic_ns() + POLL_SECONDS * NS))
        state, reason = daemon_state(world, work, ident)
    if k == c['checkpoints']:               # the last anchor holds the daemon's last sample
        limit = clock.monotonic_ns() + 3 * c['sample_seconds'] * NS
        while state == 'RUNNING' and clock.monotonic_ns() < limit:
            clock.wait_until(min(limit, clock.monotonic_ns() + POLL_SECONDS * NS))
            state, reason = daemon_state(world, work, ident)
    samples, raw = read_samples(records)
    critical = read_rows(records, 'critical_heights.jsonl')
    genesis = read_record(records / 'environment.json', 'environment.json')['genesis_hash']
    current = check.intervals(samples, [row for row in critical if row['kind'] == 'FORK_POINT'], c,
                              genesis)['current']
    value = {'format': check.FORMAT_CHECKPOINT, 'run_id': declaration['run_id'],
             'attempt': declaration['attempt'], 'index': k, 'due_monotonic_ns': due,
             'monotonic_ns': clock.monotonic_ns(), 'realtime_ns': clock.realtime_ns(), 'seq': len(samples) - 1,
             'head_sha256': check.chain_head(raw), 'daemon_state': state, 'stop_reason': reason,
             'blocks': len(read_rows(records, 'blocks.jsonl')), 'critical_reads': len(critical),
             's14_disagreements': sum(1 for row in critical if not row['agree']),
             'current_interval_seconds': None if current is None else current['monotonic_ns'] // NS}
    check.validate_record('checkpoint.json', value)
    write_new(path, check.line(value))
    github_output(args.github_output, True)
    return {'index': k, 'scheduled': True, 'daemon_state': state, 'seq': value['seq'],
            'head_sha256': value['head_sha256']}


def stop_daemon(world, work: Path, ident) -> str:
    """F1: the stop reason, with the daemon's session ended. A running daemon is asked to stop (`FINISH`) unless
    it stopped by its own rule meanwhile; one that is gone without a stop reason is `DAEMON_DEAD`."""
    clock, host = world.clock, world.host
    state, reason = daemon_state(world, work, ident)
    if state == 'RUNNING':
        host.terminate(ident)
    deadline = clock.monotonic_ns() + DAEMON_STOP_SECONDS * NS
    while state != 'DEAD' and host.alive(ident) and clock.monotonic_ns() < deadline:
        pause(clock, POLL_SECONDS)
    host.kill_session(ident)
    deadline = clock.monotonic_ns() + LEFT_SECONDS * NS
    while host.alive(ident) and clock.monotonic_ns() < deadline:      # no writer is left before F2 appends
        pause(clock, POLL_SECONDS)
    if state == 'DEAD':
        return 'DAEMON_DEAD'
    return read_stop(work) or 'FINISH'


def host_paths(work, home) -> list[tuple[bytes, bytes]]:
    """F4: the two host paths a copied log must not show, each with its mark: the work directory first (it may
    lie under the home directory), then the runner user's home. A value that is not an absolute path below the
    root is left out."""
    pairs = []
    for path, mark in ((work, WORK_MARK), (home, HOME_MARK)):
        old = os.fsencode(str(path)).rstrip(b'/')
        if old.startswith(b'/') and len(old) > 1 and old not in [item for item, _ in pairs]:
            pairs.append((old, mark))
    return pairs


def without_paths(chunks, pairs):
    """The chunks with every whole occurrence of a path of `pairs` written as its mark, an occurrence that lies
    across two chunks included. Where two paths begin at one place the first of `pairs` is taken."""
    if not pairs:
        yield from chunks
        return
    pattern = re.compile(b'|'.join(re.escape(old) for old, _ in pairs))
    marks = dict(pairs)
    reach = max(len(old) for old, _ in pairs) - 1
    held = b''
    for chunk in chunks:
        data = held + chunk
        decided = len(data) - reach         # an occurrence that begins before this place is whole in `data`
        out, at = [], 0
        for match in pattern.finditer(data):
            if match.start() >= decided:
                break
            out += [data[at:match.start()], marks[match.group()]]
            at = match.end()
        cut = max(at, decided)
        out.append(data[at:cut])
        held = data[cut:]
        yield b''.join(out)
    yield pattern.sub(lambda match: marks[match.group()], held)


def core_auth_line(data: bytes, at: int) -> bool:
    """Whether the `rpcauth` at `at` lies in one of CORE_AUTH_LINES, whole, at its own offset."""
    return any(at >= offset and data[at - offset:at - offset + len(line)] == line for line, offset in CORE_AUTH_LINES)


def holds_credential(fd) -> bool:
    """F4's rule (A's decision 1), over the file read from where `fd` stands: `rpcpassword` or `__cookie__`
    anywhere, or `rpcauth` anywhere except inside one of CORE_AUTH_LINES (Core's two lines for a command-line
    -rpcauth, each with its newline); an occurrence that lies across two chunks included."""
    after = max(len(line) - offset for line, offset in CORE_AUTH_LINES) - 1     # no word reaches further
    back = max(offset for _, offset in CORE_AUTH_LINES)       # the bytes of an allowed line before its `rpcauth`
    held, start = b'', 0
    while True:
        chunk = os.read(fd, SCAN_CHUNK)
        data = held + chunk
        decided = len(data) - after if chunk else len(data)     # an occurrence that starts before it is decidable
        for word in CREDENTIAL_WORDS:
            at = data.find(word, start)
            while 0 <= at < decided:
                if word != b'rpcauth' or not core_auth_line(data, at):
                    return True
                at = data.find(word, at + 1)
        if not chunk:
            return False
        start = max(decided, start)                 # the first occurrence not yet decided
        keep = max(start - back, 0)                 # with the bytes an allowed line needs before it
        held, start = data[keep:], start - keep


def copy_log(source: Path, target: Path, limit: int | None = None, paths=(), whole: bool = False) -> str:
    """F4: `COPIED` (the last `limit` bytes; NODE_LOG_LIMIT when not given), `WITHHELD_CREDENTIAL_SCAN` when the
    log holds a credential word (holds_credential()), or `MISSING`. With `whole` (the monitor's log) the file is
    copied whole, never cut, or not at all when it is above check.LINES_LIMIT (`TOO_LARGE`). The copy shows each
    path of `paths` (host_paths()) as its mark; the credential scan reads the log as it is."""
    limit = NODE_LOG_LIMIT if limit is None else limit
    try:
        fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        return 'MISSING'
    try:
        size = os.fstat(fd).st_size
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            return 'MISSING'
        if holds_credential(fd):
            return 'WITHHELD_CREDENTIAL_SCAN'
        if whole:
            if size > check.LINES_LIMIT:
                return 'TOO_LARGE'
            limit = size
        os.lseek(fd, max(0, size - limit), os.SEEK_SET)

        def last_bytes():
            left = limit
            while left > 0:
                chunk = os.read(fd, min(SCAN_CHUNK, left))
                if not chunk:
                    break
                left -= len(chunk)
                yield chunk

        out = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o644)
        try:
            for chunk in without_paths(last_bytes(), list(paths)):
                _write_all(out, chunk)
        finally:
            os.close(out)
    finally:
        os.close(fd)
    return 'COPIED'


def finish_command(args, world, environ) -> dict:
    clock, host = world.clock, world.host
    records = existing_dir(args.records, 'RECORDS_MISSING')
    if os.path.lexists(records / 'final.json'):
        raise check.Refusal('OUTPUT_EXISTS')
    work = existing_dir(args.work, 'DAEMON_STATE_MISSING')
    state = load_state(work)
    nodes = session_nodes(world, state, work)
    held = None                             # a refusal is kept until the sessions are ended
    declaration = None
    try:
        if state['daemon'] is None or set(nodes) != set(check.NODES):
            raise check.Refusal('DAEMON_STATE_MISSING')
        declaration = check.read_declaration(records / 'declaration.json')
        # F1
        stop_reason = stop_daemon(world, work, state['daemon'])
        # F1m
        if state['monitor'] is not None:
            stop_monitor(world, state['monitor'])
        # F1r: no block follows once the daemon stopped, so this follow is the replay's last word
        if read_record(records / 'replay_build.json', 'replay_build.json')['result'] == 'BUILT':
            replays = Lines(records / 'replay.jsonl', new=False)
            try:
                follow(world, work, replays, 'FINAL', declaration['constants'],
                       read_record(records / 'environment.json', 'environment.json')['genesis_hash'])
            finally:
                replays.close()
        # F2
        h0 = declaration['constants']['h0']
        critical = Critical(world, nodes, records, declaration, new=False)
        for kind, height in zip(CRITICAL, (0, h0 - 1, h0)):
            critical.read(kind, 'FINAL', height)
        critical.lines.close()
        challenge = {}
        for key in check.NODES:
            try:
                answer = rpc_object(nodes[key], 'getblockchaininfo').get('signet_challenge')
            except NodeError:
                answer = None
            challenge[key] = answer if type(answer) is str and CHALLENGE_HEX.fullmatch(answer) else None
    except Exception as failure:            # noqa: BLE001 - raised again once nothing is left running
        held = failure
    # F3
    for node in nodes.values():
        try:
            node.call('stop')
        except NodeError:
            pass
    deadline = clock.monotonic_ns() + NODE_STOP_SECONDS * NS
    while any(host.alive(entry) for entry in state['nodes'].values()) and clock.monotonic_ns() < deadline:
        pause(clock, POLL_SECONDS)
    kill_sessions(world, state)
    sessions = sessions_of(state)
    deadline = clock.monotonic_ns() + LEFT_SECONDS * NS
    while any(host.left(entry) for entry in sessions) and clock.monotonic_ns() < deadline:
        pause(clock, POLL_SECONDS)
    if held is not None:
        raise held
    stopped = {key: host.left(state['nodes'][key]) == 0 for key in check.NODES}
    # A's decision 13: a tick a killed monitor left behind runs in a session of its own, so the two binaries'
    # live processes outside the four sessions are counted by their executable's path
    leftover = sum(host.left(entry) for entry in sessions) + host.strays(
        [tool_path(work, key) for key in check.BINARY_NAMES], [entry['pid'] for entry in sessions])
    # F4
    os.makedirs(records / 'node-logs', exist_ok=True)
    # no copy names a path of this host: the work directory is written <work>, the runner user's home <home>
    paths = host_paths(work, host.home())
    logs = {key: copy_log(nodes[key].log_path(), records / 'node-logs' / f'node-{key}.log', paths=paths)
            for key in check.NODES}
    # the daemon's own closing line and its error output (a dead daemon's traceback): the work directory is
    # never uploaded, so both go beside the node logs, cut to their last 64 KiB, under the same two rules
    daemon_logs = {key: copy_log(work / name, records / 'node-logs' / name, DAEMON_LOG_LIMIT, paths)
                   for key, name in DAEMON_LOG_NAMES.items()}
    # the monitor's log whole (its START and STOP both survive) and its error output's last 64 KiB, under the same
    # rules; its exit and stop reason are its STOP line's
    folder = work / 'monitor'
    os.makedirs(records / 'monitor', exist_ok=True)
    monitor = {'log': copy_log(folder / MONITOR_NAMES['log'], records / check.MONITOR_FILES[1], paths=paths,
                               whole=True),
               'err': copy_log(folder / MONITOR_NAMES['err'], records / 'monitor' / MONITOR_NAMES['err'],
                               DAEMON_LOG_LIMIT, paths),
               **monitor_end(folder / MONITOR_NAMES['log'])}
    withheld = 'WITHHELD_CREDENTIAL_SCAN' in [*logs.values(), *daemon_logs.values(), monitor['log'], monitor['err']]
    # F5
    samples, raw = read_samples(records)
    rows = read_rows(records, 'critical_heights.jsonl')
    genesis = read_record(records / 'environment.json', 'environment.json')['genesis_hash']
    result = check.intervals(samples, [row for row in rows if row['kind'] == 'FORK_POINT'],
                             declaration['constants'], genesis)
    longest = result['longest']
    final = {'format': check.FORMAT_FINAL, 'run_id': declaration['run_id'], 'attempt': declaration['attempt'],
             'stop_reason': stop_reason, 'samples': len(samples), 'head_sha256': check.chain_head(raw),
             'monotonic_ns': clock.monotonic_ns(), 'realtime_ns': clock.realtime_ns(),
             'challenge_final': challenge, 'nodes_stopped': stopped, 'leftover_processes': leftover,
             'node_logs': logs, 'daemon_logs': daemon_logs, 'monitor': monitor,
             'replay_store_sha256': {key: file_sha256(work / 'replay' / name)
                                     for key, name in (('profile', 'profile.bin'), ('store', 'store.sqlite3'))},
             'vps_summary': {'longest_interval_seconds': None if longest is None else longest['monotonic_ns'] // NS,
                             'breaks': len(result['breaks']),
                             's14_disagreements': sum(1 for row in rows if not row['agree'])},
             'fleet_scale': 'NOT_MEASURED'}
    check.validate_record('final.json', final)
    final_raw = check.line(final)
    write_new(records / 'final.json', final_raw)
    if withheld:
        raise check.Refusal('CREDENTIAL_MATERIAL')
    if leftover:
        raise check.Refusal('LEFTOVER_PROCESS')
    return {'stop_reason': stop_reason, 'samples': len(samples), 'head_sha256': final['head_sha256'],
            'leftover_processes': leftover, 'final_sha256': hashlib.sha256(final_raw).hexdigest()}


COMMANDS = {'start': start_command, 'checkpoint': checkpoint_command, 'finish': finish_command,
            'daemon': daemon_command}


def _digits(text: str) -> int:
    if re.fullmatch(r'[0-9]{1,18}', text) is None:
        raise argparse.ArgumentTypeError('an integer')
    return int(text)


def _optional_text(text: str):
    return None if text == '' else text


def parser():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest='command', required=True)
    q = sub.add_parser('start')
    for name in ('--declaration', '--source-sha256', '--node-a', '--node-b', '--bin-dir', '--records', '--work'):
        q.add_argument(name, required=True)
    q = sub.add_parser('checkpoint')
    q.add_argument('--records', required=True)
    q.add_argument('--work', required=True)
    q.add_argument('--index', required=True, type=_digits)
    q.add_argument('--github-output', type=_optional_text)
    for name in ('finish', 'daemon'):
        q = sub.add_parser(name)
        q.add_argument('--records', required=True)
        q.add_argument('--work', required=True)
    return p


def main(argv=None, world=None, environ=None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)

    def emit(command, result, exit_code, code=None, **keys) -> int:
        sys.stdout.write(check.output_line(TOOL, command, result, exit_code, code, **keys).decode('ascii'))
        return exit_code

    if not __debug__:   # before anything else, argparse included
        return emit(argv[0] if argv and argv[0] in COMMANDS else None, 'REFUSED', check.EXIT_REFUSAL,
                    'OPTIMIZED_PYTHON')
    args = parser().parse_args(argv)
    try:
        keys = COMMANDS[args.command](args, World() if world is None else world,
                                      os.environ if environ is None else environ)
    except check.Refusal as refusal:
        return emit(args.command, 'REFUSED', refusal.exit_code, refusal.code)
    except Exception:   # noqa: BLE001 - one closed line on stdout; no text of the failure is printed there
        if args.command == 'daemon':        # its stderr is a file of the work directory, never a job log
            traceback.print_exc()
        return emit(args.command, 'INTERNAL', check.EXIT_INTERNAL, 'INTERNAL_ERROR')
    return emit(args.command, 'DONE', check.EXIT_OK, **keys)


if __name__ == '__main__':
    import claude_track_exit
    claude_track_exit.run(main)
