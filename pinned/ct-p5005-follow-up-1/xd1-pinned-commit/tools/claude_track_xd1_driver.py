"""XD-1 driver: one XD-1 run on the L0 path, its event chain stamped on one clock (CT-P3-044c-1 1e-4b-1).

Class T EXPLORATORY development evidence on Regtest, not S17-PREP. Sources: B's unit draft #258
issuecomment-6418049931 (sections 2-4, 6) and A's answer issuecomment-6419729708 (all eight defaults, with
conditions); docs/claude-track/plans/CT-P3-044C1_1E_PREP_EN.md section 4.5 (Runs, Clock, Events, Order, Per-run
cap); 045b section 5.1. Record format: docs/claude-track/formats/XD1_EVENT_CHAIN_V2.md (`BITAGI_CT_XD1_RUN_V2`).

  run --index I --records DIR --node-a BIN --node-b BIN --work NEW_DIR [--cargo C] [--offline-target D]
      [--online-target D] [--mode EXPLORATORY|CONFIRMATORY] [--decision scripted|live]
      [--console-dir DIR] [--registration-sha256 HEX]

One run, on fresh nodes and data directories, writes `run-<I>.json` once and never again (N is fixed; no rerun,
no extension). The run follows `claude_track_regtest_offline_export.run_l0` (#484 L0): the charge and the Sign
hand-off at H0 - 2, the offline signature, the import, then the floor block H0 - 1 and the host's H0 - 1
processes. That module is imported and changed only by A's choice for `decoderawtransaction` (its `extra_rpcs`;
A, Q1; #258 issuecomment-6423146186); its import has no side effect (pinned by a test).

* One clock, `time.monotonic_ns` (`CLOCK`), owns every stamp: the driver's own events (S0, S1, D0, D1, ACK, I)
  and each host line, stamped when the driver first reads it from the process's event file.
* S0 is stamped before the `generatetodescriptor` call for H0 - 1, S1 when it returns.
* The first H0 - 1 process gets the ack FIFO (`BITAGI_E3D3_XD1_ACK`). After stamping S2 the driver reads
  getblockhash(H0 - 1) on both nodes, stamps every line already in the file, then stamps ACK and writes
  `XD1_ACK_V1 <seq>`. The host's own ack waits (30 s, at most 60 s) are unchanged; the driver sets none.
* The host takes no decision input (crates/ is unchanged), so the scripted decision is empty: D0 and D1 are
  stamped right after the STEP_9_END line, before any later line.
* H0 - 1 is read on both nodes at S1 (after the generate returns and both nodes hold it), at S2 and at the run's
  end (after I). The H of each `run_prestate` call is the hash of the raw block it compared. Six reads and
  every H must be one hash, or the run stops `H0_MINUS_1_CHANGED` (T = infinity, the record kept).
* Both nodes' `incrementalfee` is converted to sat/kvB as a Decimal, never a float (AGENTS.md section 4); both
  nodes decode the exact bytes to send (`decoderawtransaction`) and both vsizes are recorded.
* No broadcast process is started again within a run (A, Q4): a process that ends without its O lines leaves
  a record with BASE_EVENT_MISSING. Nothing is mined after H0 - 1 until both O lines are stamped.
* run_id, run_attempt and head_sha come only from GITHUB_RUN_ID, GITHUB_RUN_ATTEMPT and GITHUB_SHA.

Live decision (V3, docs/claude-track/formats/XD1_EVENT_CHAIN_V3.md section 4; A's decisions XA2 and XA5 of
2026-11-10), `--decision live`, the only decision of `--mode CONFIRMATORY`: the second H0 - 1 process gets a
decision FIFO (`BITAGI_E3D3_XD1_DECISION`). After the STEP_9_END line the driver stamps D0, makes a console FIFO
and writes a prompt (run index, candidate txid and its display digest) in `--console-dir`, and waits, until the
run cap, for the Founder's line `XD1_DECISION_V1 <run_index> <txid> BROADCAST|REFUSE` on that FIFO. A line that
names this run and candidate stamps D1; only BROADCAST writes the gate line `XD1_ACK_V1 <seq>` (seq: the
STEP_9_END line's own sequence number, the `xd1::AckLines` grammar) to the worker's FIFO. REFUSE, a closed or
malformed console input, or another run's line closes the worker's FIFO without a line (stop reason
DECISION_REFUSED); the cap closes it too (RUN_CAP). The record is V3 (decision BROADCAST, REFUSED or NONE).
Scripted runs (the default) are unchanged and V2.

The driver stops at its own cap (`XD1_RUN_CAP`, stop reason RUN_CAP); the supervisor
(`claude_track_xd1_supervisor.py`) kills a driver that does not. Exit codes: 0 the record was written and the run
has no stop reason; 2 the record was written with a stop reason, or the record already exists (nothing run);
3 a missing prerequisite before the run (the GITHUB_* values, the records directory); 4 internal error (setting
up the lab included: one line with the error's type, no traceback), or the record could not be written; 5 under
-O. Stdlib only; no reference/ code is read here (run_prestate runs the
documented producer as a black box on a real-node run only).
"""
from __future__ import annotations

import argparse
import decimal
import hashlib
import json
import os
import re
import select
import shutil
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path

import claude_track_regtest_offline_export as oe
import claude_track_xd1_check as check

CLOCK = time.monotonic_ns   # the run's one clock (1E Clock, Q25); every stamp calls it
XD1_RUN_CAP_NS = check.XD1_RUN_CAP_NS
POLL_SECONDS = 0.01
FIFO_OPEN_SECONDS = 30.0   # the host opens its end when it starts; bounded like its own wait
HEIGHT = oe.TIP_HEIGHT     # H0 - 1
PENDING, COMPARED = 'pending l0_broadcast', 'l0_broadcast'
ACK_SEQ = oe.EVENT_LINES[PENDING].index('S2') + 1
# decoderawtransaction decodes and submits nothing; offline_export's own list stays as it is.
XD1_EXTRA_RPCS = frozenset({'decoderawtransaction'})   # offline_export's EXTRA_RPCS, asked for by name (A, (가))
NODES = check.NODES
# The live decision (V3). The worker's gate (M4: crates/bitagi-launch-host/tests/two_node_launch_accept.rs) reads
# DECISION_ENV; the console side is the prompt and the FIFO in --console-dir, the runner account's own directory.
# The Founder's console writes the line there, but so could any process of that account: the line binds the run
# and the candidate, and what makes it the Founder's is the registered tree and the guard (review S3; the unit
# note's CR-21 condition 4), not the directory.
DECISION_ENV = 'BITAGI_E3D3_XD1_DECISION'
DECISION_FIFO = 'xd1-decision.fifo'
PROMPT_FORMAT = 'BITAGI_CT_XD1_DECISION_PROMPT_V1'
PROMPT_NAME, CONSOLE_FIFO = 'prompt.json', 'decision.fifo'
CONSOLE_LINE = re.compile(r'XD1_DECISION_V1 ([1-9][0-9]?) ([0-9a-f]{64}) (BROADCAST|REFUSE)\n')
MAX_CONSOLE_LINE = 128


class Live:
    """A live-decision run's settings (V3): its mode, its registration hash (CONFIRMATORY) and the console
    directory where the prompt and the console FIFO are made."""

    def __init__(self, mode: str, registration_sha256: str | None, console: Path):
        if mode not in check.MODES_V3 or (registration_sha256 is None) != (mode == 'EXPLORATORY'):
            raise oe.Prerequisite('--mode and --registration-sha256')
        if registration_sha256 is not None and not check.is_hash(registration_sha256):
            raise oe.Prerequisite('--registration-sha256 is not 64 lowercase hex')
        self.mode, self.registration_sha256, self.console = mode, registration_sha256, console


class Stop(Exception):
    """The run stops with this stop reason (V2 section 3)."""

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def fee_sat_per_kvb(btc_per_kvb) -> int:
    """`incrementalfee` (BTC/kvB, read as a JSON Decimal) in sat/kvB, exact; a float is refused."""
    if type(btc_per_kvb) not in (decimal.Decimal, int) or btc_per_kvb < 0:
        raise oe.Mismatch('INCREMENTALFEE')
    return oe.sats(decimal.Decimal(btc_per_kvb))


def block_hash(raw_hex: str) -> str:
    """The display hash of a raw block: SHA-256d of its 80-byte header, reversed."""
    header = bytes.fromhex(raw_hex.strip())[:80]
    return hashlib.sha256(hashlib.sha256(header).digest()).digest()[::-1].hex()


def export_raw(path: Path, raw_tx_sha256: str) -> str:
    """The raw transaction of a version 2 export container (offline_container.rs layout: magic, version 2,
    raw_tx_sha256 at 52, the lengths at 84/88/92, the raw bytes at 328), checked against its digest."""
    data = path.read_bytes()
    if len(data) < 328 or data[:16] != b'BITAGI_OFFL_EXPT' or int.from_bytes(data[16:20], 'little') != 2:
        raise oe.Mismatch('EXPORT_CONTAINER')
    lengths = [int.from_bytes(data[at:at + 4], 'little') for at in (84, 88, 92)]
    raw = data[328:328 + lengths[0]]
    if 328 + sum(lengths) != len(data) or not hashlib.sha256(raw).hexdigest() == data[52:84].hex() == raw_tx_sha256:
        raise oe.Mismatch('EXPORT_RAW')
    return raw.hex()


def run_ids(environ) -> tuple[int, int, str]:
    """(run_id, run_attempt, head_sha), only from GITHUB_RUN_ID, GITHUB_RUN_ATTEMPT and GITHUB_SHA."""
    run_id, attempt, sha = (environ.get(k, '') for k in ('GITHUB_RUN_ID', 'GITHUB_RUN_ATTEMPT', 'GITHUB_SHA'))
    if not (re.fullmatch(r'[1-9][0-9]{0,18}', run_id) and re.fullmatch(r'[1-9][0-9]{0,9}', attempt)
            and check.HEX40.fullmatch(sha)):
        raise oe.Prerequisite('GITHUB_RUN_ID, GITHUB_RUN_ATTEMPT and GITHUB_SHA')
    return int(run_id), int(attempt), sha


DIAGNOSTIC_CODE = re.compile(r"[A-Za-z0-9_:./ =,'\[\]-]{1,300}")   # a tool-authored code, phrase or file listing


class Chain:
    """The run's events in stamping order; each time is CLOCK's, taken under the lock that appends it."""

    def __init__(self):
        self.events: list[dict] = []
        self.lock = threading.Lock()

    def stamp(self, name: str, **extra) -> int:
        with self.lock:
            item = {'event': name, 't_ns': CLOCK(), **extra}
            self.events.append(item)
            return item['t_ns']

    def has(self, name: str) -> bool:
        with self.lock:
            return any(e['event'] == name for e in self.events)


class Watcher(threading.Thread):
    """Stamps each new line of one host process's event file when the driver first reads it. With a FIFO
    (the first H0 - 1 process), acks S2 after the S2 reads and after stamping every line already there."""

    def __init__(self, xd1: 'Run', path: Path, fifo: Path | None):
        super().__init__(daemon=True)
        self.xd1, self.path, self.fifo = xd1, path, fifo
        self.seen = 0
        self.done = threading.Event()
        self.error: BaseException | None = None

    def poll(self) -> bool:
        """Stamps the complete lines not yet stamped, in file order; whether S2 was among them."""
        try:
            data = self.path.read_bytes()
        except FileNotFoundError:
            return False
        if len(data) > oe.MAX_EVENT_FILE:
            raise oe.Mismatch('EVENT_FILE_BOUND')
        lines = data.decode('ascii').split('\n')[:-1]
        s2 = False
        for i in range(self.seen, len(lines)):
            prefix = f'XD1_LINE_V1 {i + 1} '
            name = lines[i][len(prefix):]
            if not lines[i].startswith(prefix) or name not in oe.EVENT_NAMES:
                raise oe.Mismatch(f'event line {i + 1} malformed')
            self.seen = i + 1
            if name.startswith('O_'):
                self.xd1.chain.stamp(name[:3], outcome=name[4:])
            else:
                self.xd1.chain.stamp(name)
            if name == 'STEP_9_END' and self.xd1.live is not None:   # V3: D0, then the Founder's decision
                self.xd1.chain.stamp('D0')
                self.xd1.begin_decision(i + 1)
            elif name == 'STEP_9_END':   # the empty scripted decision, before any later line (D12)
                self.xd1.chain.stamp('D0')
                self.xd1.chain.stamp('D1')
            s2 = s2 or name == 'S2'
        return s2

    def ack(self) -> None:
        self.xd1.read_h0_minus_1('S2')   # after stamping S2, before the ack (A, (a))
        self.poll()                      # every line already in the file is stamped before ACK (D1)
        changed = self.xd1.changed()
        deadline = time.monotonic() + FIFO_OPEN_SECONDS
        while True:
            try:
                fd = os.open(self.fifo, os.O_WRONLY | os.O_NONBLOCK)
                break
            except OSError:
                if time.monotonic() > deadline:
                    raise oe.Mismatch('ACK_FIFO') from None
                time.sleep(POLL_SECONDS)
        try:
            if changed:
                self.xd1.set_stop(changed)   # no ack: the host reads a closed input and starts no step
            else:
                self.xd1.chain.stamp('ACK')
                os.write(fd, f'XD1_ACK_V1 {ACK_SEQ}\n'.encode('ascii'))
        finally:
            os.close(fd)

    def run(self) -> None:
        try:
            while True:
                finished = self.done.is_set()   # one more poll after the process has ended
                if self.poll() and self.fifo is not None:
                    self.ack()
                if finished:
                    return
                time.sleep(POLL_SECONDS)
        except BaseException as exc:  # noqa: BLE001 - re-raised by Run.host
            self.error = exc


class Decision(threading.Thread):
    """V3: the Founder's live decision for one run, on its own thread so the watcher keeps stamping lines (a host
    that did not wait for the gate shows as attempts before D1: D1_LE_EVERY_B). Started at the STEP_9_END line
    with that line's sequence number; ends at the decision, at the run cap, or when the host process ends."""

    def __init__(self, xd1: 'Run', seq: int):
        super().__init__(daemon=True)
        self.xd1, self.seq = xd1, seq
        self.cancel = threading.Event()
        self.error: BaseException | None = None
        self.deadline_ns = xd1.start_ns + XD1_RUN_CAP_NS

    def run(self) -> None:
        console = self.xd1.live.console
        fifo, prompt = console / CONSOLE_FIFO, console / PROMPT_NAME
        rfd = None
        try:
            for stale in (prompt, fifo):   # a killed run's prompt or FIFO names no live run
                if os.path.lexists(stale):
                    os.unlink(stale)
            os.mkfifo(fifo, 0o600)
            rfd = os.open(fifo, os.O_RDONLY | os.O_NONBLOCK)   # opened before the prompt names it
            candidate = self.xd1.lab.candidate()
            self.write_prompt(prompt, candidate)
            line, why = self.read_line(rfd)
            got = CONSOLE_LINE.fullmatch(line) if line is not None else None
            if got and int(got.group(1)) == self.xd1.index and got.group(2) == candidate['txid']:
                self.xd1.chain.stamp('D1')   # the Founder's decision, as the driver reads it
                if got.group(3) == 'BROADCAST':
                    self.xd1.decision = 'BROADCAST'
                    self.deliver(f'XD1_ACK_V1 {self.seq}\n'.encode('ascii'))
                    return
                self.xd1.decision = 'REFUSED'
            if why == 'CAP':
                self.xd1.set_stop('RUN_CAP')
            elif why != 'CANCELLED':
                self.xd1.set_stop('DECISION_REFUSED')
            self.deliver(None)
        except BaseException as exc:  # noqa: BLE001 - re-raised by Run.host after the host ends
            self.error = exc
            self.xd1.set_stop('DRIVER_EXIT')
            self.deliver(None)
        finally:
            if rfd is not None:
                os.close(rfd)
            for path in (prompt, fifo):
                try:
                    os.unlink(path)
                except OSError:
                    pass

    def write_prompt(self, path: Path, candidate: dict) -> None:
        """The prompt the Founder's console shows (claude_track_xd1_decide.py), written whole under its name."""
        txid = candidate['txid']
        value = {'format': PROMPT_FORMAT, 'run_index': self.xd1.index, 'run_id': self.xd1.ids[0], 'txid': txid,
                 'raw_tx_sha256': candidate['raw_tx_sha256'], 'display_digest': f'{txid[:8]}..{txid[-8:]}',
                 'fifo': CONSOLE_FIFO, 'cap_seconds_left': max(0, (self.deadline_ns - CLOCK()) // 10**9)}
        raw = (json.dumps(value, sort_keys=True) + '\n').encode('ascii')
        partial = path.with_name(path.name + '.partial')
        fd = os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
        try:
            os.write(fd, raw)
        finally:
            os.close(fd)
        os.replace(partial, path)

    def read_line(self, rfd: int) -> tuple[str | None, str]:
        """(the first line, why the wait ended): LINE, CLOSED (the writer went without a whole line), CAP or
        CANCELLED. At most MAX_CONSOLE_LINE bytes are read; anything after the first line is ignored."""
        poller = select.poll()
        poller.register(rfd, select.POLLIN)
        data = b''
        while True:
            if self.cancel.is_set():
                return None, 'CANCELLED'
            left = self.deadline_ns - CLOCK()
            if left <= 0:
                return None, 'CAP'
            events = poller.poll(min(left // 10**6 + 1, int(POLL_SECONDS * 1000) * 10))
            if not events:
                continue
            chunk = os.read(rfd, MAX_CONSOLE_LINE + 1 - len(data))
            data += chunk
            if b'\n' in data:
                head = data.split(b'\n', 1)[0] + b'\n'
                try:
                    return head.decode('ascii'), 'LINE'
                except UnicodeDecodeError:
                    return None, 'CLOSED'
            if not chunk or len(data) > MAX_CONSOLE_LINE:
                return None, 'CLOSED'

    def deliver(self, line: bytes | None) -> None:
        """Opens the worker's decision FIFO (once its gate has opened its end), writes the gate line or nothing,
        and closes it; gives up when the host process has ended or the run's cap has passed."""
        fifo = self.xd1.decision_fifo
        while True:
            try:
                fd = os.open(fifo, os.O_WRONLY | os.O_NONBLOCK)
                break
            except OSError:
                if self.cancel.is_set() or CLOCK() > self.deadline_ns:
                    return
                time.sleep(POLL_SECONDS)
        try:
            if line is not None:
                os.write(fd, line)
        finally:
            os.close(fd)


class Run:
    """One XD-1 run against `lab` (L0Lab on real nodes; a TEST_ONLY stand-in in the tests). `live` (a Live) makes
    it a V3 run with the Founder's decision; None is the scripted V2 run."""

    def __init__(self, lab, index: int, ids: tuple[int, int, str], live: Live | None = None):
        self.lab, self.index, self.ids, self.live = lab, index, ids, live
        self.decision = 'NONE'
        self.decider: Decision | None = None
        self.decision_fifo: Path | None = None
        self.chain = Chain()
        self.reads = {at: {n: None for n in NODES} for at in check.READ_POINTS}
        self.calls: list[dict] = []
        self.fee = {n: None for n in NODES}
        self.vsize = {n: None for n in NODES}
        self.stop: str | None = None
        self.hosts: list[str] = []
        self.start_ns = self.end_ns = 0

    def set_stop(self, reason: str) -> None:
        if self.stop is None:
            self.stop = reason

    def begin_decision(self, seq: int) -> None:
        """V3: the decision thread for the STEP_9_END line `seq` (once: a second STEP_9_END fails the chain)."""
        if self.decider is None and self.decision_fifo is not None:
            self.decider = Decision(self, seq)
            self.decider.start()

    def remaining(self) -> int:
        return max(1, (self.start_ns + XD1_RUN_CAP_NS - CLOCK()) // 10**9)

    def read_h0_minus_1(self, at: str) -> None:
        self.reads[at] = self.lab.floor_hashes()

    def changed(self) -> str | None:
        hashes = {h for read in self.reads.values() for h in read.values() if h is not None}
        hashes |= {call['hash'] for call in self.calls}
        if len(hashes) > 1 or any(call['height'] != HEIGHT for call in self.calls):
            return 'H0_MINUS_1_CHANGED'
        return None

    def halt_if_changed(self) -> None:
        if self.changed():
            raise Stop(self.changed())

    def host(self, key: str, env: dict, ack: bool = False, decision: bool = False) -> dict:
        """One host process: its own event file, watched while it runs; never started twice (A, Q4). With
        `decision` (V3) it gets the worker's decision FIFO, and its decision thread ends with it."""
        if key in self.hosts:
            raise oe.Mismatch(f'{key}: a second process')
        self.hosts.append(key)
        lines = self.lab.work / f'lines-{key.replace(" ", "-")}.txt'
        stage = {**env, 'BITAGI_E3D3_EVENT_LINES': str(lines.resolve())}
        fifo = None
        if ack:
            fifo = self.lab.work / 'xd1-ack.fifo'
            os.mkfifo(fifo, 0o600)
            stage['BITAGI_E3D3_XD1_ACK'] = str(fifo.resolve())
        if decision:
            self.decision_fifo = self.lab.work / DECISION_FIFO
            os.mkfifo(self.decision_fifo, 0o600)
            stage[DECISION_ENV] = str(self.decision_fifo.resolve())
        watcher = Watcher(self, lines, fifo)
        watcher.start()
        try:
            got = self.lab.host(key, stage, self.remaining())
        finally:
            watcher.done.set()
            watcher.join()
            if self.decider is not None:   # the host process has ended: no decision reaches it any more
                self.decider.cancel.set()
                self.decider.join()
        if watcher.error is not None:
            raise watcher.error
        if self.decider is not None and self.decider.error is not None:
            raise self.decider.error
        self.lab.check_lines(key, lines)
        return got

    def body(self) -> None:
        self.lab.start()
        self.fee = {n: fee_sat_per_kvb(v) for n, v in self.lab.incremental_fees().items()}
        raw = self.lab.prepare(self.remaining)
        self.vsize = self.lab.vsizes(raw)
        if self.vsize['A'] != self.vsize['B']:
            raise oe.Mismatch('CANDIDATE_VSIZE_DISAGREES')
        self.chain.stamp('S0')   # before the generate call starts (1E Clock, S0 bound)
        self.lab.generate_floor()
        self.chain.stamp('S1')
        self.read_h0_minus_1('S1')
        self.halt_if_changed()
        pending = self.host(PENDING, self.lab.stage_env(), ack=True)
        if self.stop:
            raise Stop(self.stop)
        try:
            env, call = self.lab.prestate(pending)
        except oe.Mismatch:
            raise Stop('COMPARATOR_UNAVAILABLE') from None
        self.calls.append(call)
        self.halt_if_changed()
        self.host(COMPARED, {**self.lab.stage_env(), **env}, decision=self.live is not None)
        if not (self.chain.has('O_A') and self.chain.has('O_B')):
            raise oe.Mismatch('O_LINES')   # nothing is mined without both outcomes (D13)
        self.lab.check_sent()
        self.chain.stamp('I', included=self.lab.mine_h0())

    def execute(self) -> dict:
        self.start_ns = CLOCK()
        try:
            self.body()
        except Stop as stop:
            self.set_stop(stop.reason)
        except Exception as exc:  # noqa: BLE001 - every run keeps its record (A, Q4); the reason is its stop reason
            self.set_stop('RUN_CAP' if CLOCK() - self.start_ns > XD1_RUN_CAP_NS else 'DRIVER_EXIT')
            self.diagnose(exc)
        try:
            self.read_h0_minus_1('RUN_END')   # after I, before the record
        except Exception:  # noqa: BLE001 - a read not made stays null (RUN_FACT_UNREAD)
            pass
        if self.changed():
            self.set_stop(self.changed())
        try:
            self.lab.stop()
        finally:
            self.end_ns = CLOCK()
        return self.record()

    def diagnose(self, exc: BaseException) -> None:
        """One bounded stderr line for a run stopped by an error, the smoke job's only trace of its cause (the
        record keeps the stop reason only): the error's type, its tool-authored code if it is one, the file and
        line it was raised at, and the last event stamped. No other text from a node or the host. The line
        passes the run's `Secrets` check, as the record does (A #534 issuecomment-6425964822 H8). A line that
        fails it loses its code (`DIAGNOSTIC_WITHHELD`) and is checked again; one that still fails is withheld
        whole: the same keys, `DIAGNOSTIC_WITHHELD` and nulls (B's review)."""
        frames = traceback.extract_tb(exc.__traceback__)
        text = str(exc)
        code = text if isinstance(exc, (oe.Mismatch, oe.Prerequisite)) and DIAGNOSTIC_CODE.fullmatch(text) else None
        with self.chain.lock:
            last = self.chain.events[-1]['event'] if self.chain.events else None
        fields = {'driver_error': type(exc).__name__, 'code': code,
                  'at': f'{Path(frames[-1].filename).name}:{frames[-1].lineno}' if frames else None, 'last_event': last}
        secrets_ = getattr(self.lab, 'secrets', None)
        for candidate in (fields, {**fields, 'code': 'DIAGNOSTIC_WITHHELD'}):
            line = json.dumps(candidate, sort_keys=True)
            if secrets_ is None:
                break
            try:
                secrets_.check(line, 'diagnostic')
                break
            except oe.Mismatch:
                continue
        else:
            line = json.dumps({'driver_error': 'DIAGNOSTIC_WITHHELD', 'code': None, 'at': None, 'last_event': None},
                              sort_keys=True)
        print(line, file=sys.stderr)

    def record(self) -> dict:
        run_id, attempt, sha = self.ids
        value = {'format': check.FORMAT_RUN_V2, 'run_index': self.index, 'run_id': run_id, 'run_attempt': attempt,
                 'head_sha': sha, 'labels': list(check.REQUIRED_LABELS), 'transferability': check.TRANSFERABILITY,
                 'incrementalfee_sat_per_kvb': dict(self.fee), 'candidate_vsize': dict(self.vsize),
                 'events': list(self.chain.events), 'run_start_ns': self.start_ns, 'run_end_ns': self.end_ns,
                 'h0_minus_1_height': HEIGHT, 'h0_minus_1_reads': [{'at': at, **self.reads[at]}
                                                                    for at in check.READ_POINTS],
                 'prestate_calls': list(self.calls)}
        if self.live is not None:   # V3 (XA5): the mode's labels, the registration and the live decision
            value.update({'format': check.FORMAT_RUN_V3, 'labels': list(check.LABELS_V3[self.live.mode]),
                          'transferability': check.TRANSFERABILITY_V3, 'mode': self.live.mode,
                          'registration_sha256': self.live.registration_sha256, 'decision': self.decision})
        if self.stop is not None:
            value['stop_reason'] = self.stop
        return value


# ------------------------------------------------------------------------------------- real nodes ----
class L0Lab:
    """The real nodes and the L0 host path (`run_l0`'s steps and checks), for one run."""

    def __init__(self, node_a: Path, node_b: Path, work: Path, cargo: str, offline_target: Path,
                 online_target: Path):
        if 'RUSTFLAGS' in os.environ:
            raise oe.Prerequisite('RUSTFLAGS is set; the offline cfg comes only from ' + oe.OFFLINE_FLAGS_VARIABLE)
        if os.environ.get(oe.OFFLINE_FLAGS_VARIABLE) != oe.OFFLINE_RUSTFLAGS:
            raise oe.Prerequisite(f'{oe.OFFLINE_FLAGS_VARIABLE} must be exactly {oe.OFFLINE_RUSTFLAGS!r}')
        oe.check_ancestors(work)
        work.mkdir(parents=True, exist_ok=False)
        work.chmod(0o700)
        self.root, self.cargo = work, cargo
        self.work = oe.private(work / 'xd1')
        self.send, admin = oe.RunUser(oe.SEND_USER), oe.RunUser(oe.ADMIN_USER)
        self.pair = oe.Pair(node_a, node_b, work / 'l0-nodes', self.send, admin, XD1_EXTRA_RPCS)
        self.secrets = oe.run_secrets(work, (self.pair,), self.send, admin)
        base = {k: v for k, v in os.environ.items() if k != oe.OFFLINE_FLAGS_VARIABLE}
        self.offline = {**base, 'RUSTFLAGS': oe.OFFLINE_RUSTFLAGS, 'CARGO_TARGET_DIR': str(offline_target)}
        self.online = {**base, 'CARGO_TARGET_DIR': str(online_target)}
        self.started = False

    def start(self) -> None:
        self.started = True
        self.pair.start()
        versions = tuple(node.call('getnetworkinfo')['version'] for node in self.pair.both())
        if versions != oe.NODE_VERSIONS:
            raise oe.Prerequisite(f'node versions {versions}, expected {oe.NODE_VERSIONS}')

    def stop(self) -> None:
        if self.started:
            self.pair.stop()

    def incremental_fees(self) -> dict:
        return {node.label: node.call('getnetworkinfo')['incrementalfee'] for node in self.pair.both()}

    def stage(self, worker: str, lines: list[str], env: dict, seconds: int, signer: bool = False) -> dict:
        if signer:
            command = oe.worker_command(self.cargo, oe.LAUNCH_SIGNER_TEST, worker, ['--features', 'offline-ceremony'],
                                        oe.SIGNER_PACKAGE)
        else:
            command = oe.worker_command(self.cargo, oe.HOST_TEST, worker, [], oe.HOST_PACKAGE)
        return oe.run_stage(command, env, worker, lines, seconds=seconds, secrets_=self.secrets)

    def stage_env(self) -> dict:
        return {**self.nodes_env, 'BITAGI_E3D3_PHASE': COMPARED, 'BITAGI_E3D3_SEND_AUTH': self.send.auth()}

    def l0_phase(self, name: str, tip: str, txid: str | None, height: int, remaining) -> None:
        """`run_l0`'s phases below H0 - 1 (`l0_sign`, `l0_wait`): no event line, nothing sent."""
        lines = self.work / f'lines-{name}.txt'
        env = {**self.nodes_env, 'BITAGI_E3D3_PHASE': name, 'BITAGI_E3D3_EVENT_LINES': str(lines.resolve())}
        got = self.stage(oe.L0_WORKER, oe.L0_LINES, env, remaining())
        if oe.event_names(lines, self.secrets) != oe.EVENT_LINES[name]:
            raise oe.Mismatch(f'{name} event lines')
        if (got['phase'], got['steps'], got['prestate_receipt'], got['hand_offs']) != (name, oe.L0_STEPS[name], '-', '0'):
            raise oe.Mismatch(f'{name}: steps {got["steps"]}')
        if got['prestate_ms'] != '0' or got['raw_tx_sha256'] != '-':
            raise oe.Mismatch(f'{name}: a prestate turn or bytes below H0 - 1')
        if name == 'l0_sign':
            outbox = oe.listing(self.launch / 'outbox')
            self.entry = outbox[0].removeprefix('sign-input-').removesuffix('.txt') if len(outbox) == 1 else '-'
        oe.check_boundary(self.launch, 'sign', {'entry': self.entry})
        oe.check_nothing_sent(self.pair, tip, self.funding, txid, height)

    def prepare(self, remaining) -> str:
        """`run_l0` up to the import at H0 - 2; returns the hex of the bytes step 8 will send."""
        pair = self.pair
        self.descriptor = pair.a.call('getdescriptorinfo', oe.FUNDING_DESCRIPTOR)['descriptor']
        self.constructed = pair.mine(self.descriptor, oe.CASE_CONSTRUCTION)
        chain, self.funding = oe.chain_facts(pair, self.constructed, oe.CASE_CONSTRUCTION)
        self.nodes_env = {**self.online, 'BITAGI_E3D3_NODE_A_PORT': str(pair.a.rpcport),
                          'BITAGI_E3D3_NODE_B_PORT': str(pair.b.rpcport), 'BITAGI_E3D3_NODE_A_LOG': pair.a.log_path,
                          'BITAGI_E3D3_NODE_B_LOG': pair.b.log_path}
        genesis = chain.split('\n', 1)[0].removeprefix('genesis=')
        described = self.stage(oe.DESCRIBE_WORKER, oe.DESCRIBE_LINES, self.nodes_env, remaining())
        descriptor = oe.check_descriptor(described['descriptor'], genesis)
        root = oe.private(self.root / 'l0')
        self.launch = oe.private(root / 'launch')
        self.prestate_dir = oe.private(root / 'prestate')
        for name in ('handoff', 'outbox', 'export', 'host'):
            oe.private(self.launch / name)
        self.entry = '-'
        facts = root / 'launch-facts.txt'
        facts.write_text(chain + f'descriptor={descriptor}\n' + oe.sign_tip_lines(self.constructed, oe.CASE_CONSTRUCTION),
                         encoding='ascii', newline='')
        facts.chmod(0o600)
        tmp = oe.private(root / 'launch-tmp')
        offline = {**self.offline, 'BITAGI_E3D3_LAUNCH_FILE': str(facts.resolve()), 'TMPDIR': str(tmp.resolve())}
        self.nodes_env['BITAGI_E3D3_LAUNCH'] = str(self.launch.resolve())
        try:
            self.stage(oe.CHARGE_WORKER, oe.CHARGE_LINES, offline, remaining(), signer=True)
            oe.check_boundary(self.launch, 'charge', {})
            oe.scan_key_material(self.root)
            self.l0_phase('l0_sign', self.constructed, None, oe.CASE_CONSTRUCTION, remaining)
            try:
                self.exported = self.stage(oe.OFFLINE_SIGN_WORKER, oe.OFFLINE_SIGN_LINES, offline, remaining(),
                                           signer=True)
            except BaseException:
                shutil.rmtree(self.launch / 'offline', ignore_errors=True)
                raise
            oe.check_listing(self.launch, ['export', 'handoff', 'host', 'outbox'], 'L0_DIR')
            oe.check_boundary(self.launch, 'export', {'candidate': self.exported['candidate_id']})
            oe.scan_key_material(self.root)
        finally:
            shutil.rmtree(tmp)
            facts.unlink()
        self.txid = self.exported['txid']
        if not re.fullmatch(r'[0-9a-f]{64}', self.txid):
            raise oe.Mismatch("the export's txid is not a digest")
        self.l0_phase('l0_wait', self.constructed, self.txid, oe.CASE_CONSTRUCTION, remaining)
        export = self.launch / 'export' / f'{self.exported["candidate_id"]}.export'
        return export_raw(export, self.exported['raw_tx_sha256'])

    def vsizes(self, raw: str) -> dict:
        sizes = {node.label: node.call('decoderawtransaction', raw)['vsize'] for node in self.pair.both()}
        if not all(type(v) is int and v >= 1 for v in sizes.values()):
            raise oe.Mismatch('VSIZE')
        return sizes

    def generate_floor(self) -> None:
        self.pair.a.call('generatetodescriptor', '1', self.descriptor)

    def floor_hashes(self) -> dict:
        oe.wait_for(lambda: all(node.height() >= HEIGHT for node in self.pair.both()), 'both nodes at H0 - 1')
        return {node.label: node.call('getblockhash', str(HEIGHT)) for node in self.pair.both()}

    def host(self, key: str, env: dict, seconds: int) -> dict:
        got = self.stage(oe.L0_WORKER, oe.L0_LINES, env, seconds)
        if key == PENDING:
            if (got['phase'], got['steps'], got['hand_offs']) != (COMPARED, oe.L0_PENDING[COMPARED], '0'):
                raise oe.Mismatch(f'{key}: steps {got["steps"]}')
            oe.check_nothing_sent(self.pair, self.pair.agreed(HEIGHT), self.funding, self.txid)
        else:
            expected = (COMPARED, oe.L0_STEPS[COMPARED], '-', oe.L0_HAND_OFFS[COMPARED])
            if (got['phase'], got['steps'], got['prestate_receipt'], got['hand_offs']) != expected:
                raise oe.Mismatch(f'{key}: steps {got["steps"]}')
            if got['raw_tx_sha256'] != self.exported['raw_tx_sha256']:
                raise oe.Mismatch('the broadcast bytes are not the offline export\'s')
            # As run_l0: the sign boundary is checked after the phase, not between its pending process and the
            # compared one (the second smoke run, 40365203881, stopped on LAUNCH_SIGN right after the pending one).
            oe.check_boundary(self.launch, 'sign', {'entry': self.entry})
        return got

    def check_lines(self, key: str, lines: Path) -> None:
        if oe.event_names(lines, self.secrets) != oe.EVENT_LINES[key]:
            raise oe.Mismatch(f'{key} event lines')

    def prestate(self, pending: dict) -> tuple[dict, dict]:
        directory = self.prestate_dir / COMPARED
        compared = oe.run_prestate(self.pair, self.launch, directory, pending['prestate_receipt'], HEIGHT)
        raw = (directory / 'inputs' / 'h0_minus_1.hex').read_text(encoding='ascii')
        return compared['env'], {'height': HEIGHT, 'hash': block_hash(raw)}

    def check_sent(self) -> None:
        oe.check_submitted(self.pair, self.pair.agreed(HEIGHT), self.funding, self.txid)

    def candidate(self) -> dict:
        """V3: what the Founder's prompt names: the offline export's txid and raw transaction SHA-256."""
        return {'txid': self.txid, 'raw_tx_sha256': self.exported['raw_tx_sha256']}

    def mine_h0(self) -> bool:
        """Mines H0 and reads it (I): whether it includes the transaction."""
        tip = self.pair.mine(self.descriptor, 1)
        return self.txid in self.pair.a.call('getblock', tip, '1')['tx']


# -------------------------------------------------------------------------------------------- record ----
def write_record(path: Path, value: dict) -> None:
    """Writes the record once: a new file, never over another (no rerun of a declared run). The bytes go to
    `<name>.partial` first and are linked to the final name only when whole and synced, so a write cut short
    (ENOSPC, the supervisor's kill) leaves no partial `run-<i>.json` for the checker to refuse the report on:
    the run is RECORD_MISSING, T = infinity, still counted (045b section 5.1; B's review F3). The checker never
    reads a `.partial` file."""
    raw = (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode('ascii')
    if len(raw) > check.RECORD_LIMIT:
        raise oe.Mismatch('RECORD_LIMIT')
    partial = path.with_name(path.name + '.partial')
    fd = os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    try:
        try:
            view = memoryview(raw)
            while view:
                view = view[os.write(fd, view):]
            os.fsync(fd)
        finally:
            os.close(fd)
        os.link(partial, path)   # fails if the final name exists, as O_EXCL did
    finally:
        os.unlink(partial)


def drive(lab, index: int, ids, records: Path, live: Live | None = None) -> int:
    """Runs one run and writes `run-<index>.json`: 0 no stop reason, 2 a stop reason or the record exists."""
    path = records / f'run-{index}.json'
    if os.path.lexists(path):
        print(json.dumps({'result': 'REFUSED', 'failure': 'RECORD_EXISTS'}), file=sys.stderr)
        return 2
    value = Run(lab, index, ids, live).execute()
    secrets_ = getattr(lab, 'secrets', None)
    if secrets_ is not None:
        secrets_.check(json.dumps(value, sort_keys=True), 'record')
    write_record(path, value)
    print(json.dumps({'result': 'WRITTEN', 'run_index': index, 'stop_reason': value.get('stop_reason')}))
    return 0 if 'stop_reason' not in value else 2


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest='mode', required=True)
    run = sub.add_parser('run')
    run.add_argument('--index', type=int, required=True)
    run.add_argument('--records', type=Path, required=True)
    run.add_argument('--node-a', type=Path, required=True, help='bin directory of Core 31.1')
    run.add_argument('--node-b', type=Path, required=True, help='bin directory of Core 30.3')
    run.add_argument('--work', type=Path, required=True, help='a new directory for this run')
    run.add_argument('--cargo', default='cargo')
    run.add_argument('--offline-target', type=Path, default=oe.ROOT / 'target/offline-build')
    run.add_argument('--online-target', type=Path, default=oe.ROOT / 'target')
    run.add_argument('--mode', choices=check.MODES_V3, default='EXPLORATORY')
    run.add_argument('--decision', choices=('scripted', 'live'), default='scripted')
    run.add_argument('--console-dir', type=Path, help='live: the directory of the prompt and the console FIFO')
    run.add_argument('--registration-sha256', help='CONFIRMATORY: the registration the run is evaluated under')
    return p


def live_of(a) -> Live | None:
    """The run's Live, or None for the scripted run; a CONFIRMATORY run is live only (XA2)."""
    if a.decision == 'scripted':
        if a.mode != 'EXPLORATORY' or a.console_dir is not None or a.registration_sha256 is not None:
            raise oe.Prerequisite('a scripted run is EXPLORATORY, with no console or registration')
        return None
    if a.console_dir is None or not a.console_dir.is_dir():
        raise oe.Prerequisite('--console-dir')
    return Live(a.mode, a.registration_sha256, a.console_dir.resolve())


def main(argv=None) -> int:
    if not __debug__:
        print(json.dumps({'result': 'REFUSED', 'failure': 'OPTIMIZED_PYTHON'}), file=sys.stderr)
        return 5
    a = parser().parse_args(sys.argv[1:] if argv is None else argv)
    try:
        if not 1 <= a.index <= check.MAX_XD1_RUNS:
            raise oe.Prerequisite('--index outside 1..MAX_XD1_RUNS')
        if not a.records.is_dir():
            raise oe.Prerequisite('the records directory')
        ids = run_ids(os.environ)
        live = live_of(a)
        lab = L0Lab(a.node_a.resolve(), a.node_b.resolve(), a.work.resolve(), a.cargo, a.offline_target.resolve(),
                    a.online_target.resolve())
    except oe.Prerequisite as error:
        print(json.dumps({'result': 'PREREQUISITE', 'failure': str(error)}), file=sys.stderr)
        return 3
    except Exception as error:  # noqa: BLE001 - setting up the lab (A #540 issuecomment-6429217537 F2): its
        # type only, never a traceback or the error's text, which no Secrets check has seen
        print(json.dumps({'result': 'FAIL', 'failure': 'INTERNAL:' + type(error).__name__}), file=sys.stderr)
        return 4
    try:
        return drive(lab, a.index, ids, a.records.resolve(), live)
    except Exception as error:  # noqa: BLE001 - one bounded internal-error line, no free text
        print(json.dumps({'result': 'FAIL', 'failure': 'INTERNAL:' + type(error).__name__}), file=sys.stderr)
        return 4


if __name__ == '__main__':
    import claude_track_exit
    claude_track_exit.run(main)
