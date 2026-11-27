#!/usr/bin/env python3
"""CT-P5-001 D2-3a: the ARDR item-1 and pool campaigns on D1's topology, with D2-1's generator.

Class T Regtest development evidence only; never mainnet, never S17-PREP, and no ARDR verdict. Sources: A's
answer #258 issuecomment-6543158220 (Q1, Q2, Q3, Q6, Q7 and the D2-3a/D2-3b split), B's fact memo
-6542840327 and acknowledgement -6543176330, A's unit request -6537782009 (row D2), and the 045b draft
sections 4.3, 4.5 and 4.6 (`CT-P3-045b_PREREGISTRATION_DRAFT_EN.md`), a draft input, not frozen bytes. Every
value here is PENDING_FREEZE / DRAFT. Format: `docs/claude-track/formats/ARDR_RUN_V1.md` sections 14-19.

What D2-3a builds:

- ITEM1 (045b 4.6 `item 1 gate winners`): one run of gates 0-199 on one chain. One PUBLIC SYNTHETIC seat
  per gate, the gate's winner, rung 0 at feerate `b` (no fee draw, 045b :450). Gates 100-119: the planted
  owner's wallet `j mod m`, no draw; every other gate: `WINNER_G<ggg>`, wallet `W<value>`. The miner policy
  ITEM1_WINNER_ONLY keeps only the winner's REGISTER at block G. The unit is the gate (A Q2): GATE_START and
  GATE_END per gate in the raw log; a gate without GATE_END is EXCLUDED (a job that dies at gate g leaves
  g-199 EXCLUDED; no run replaces it). At the end of the run, before teardown, the driver writes the ground
  truth, D2-2's three inputs (`claude_track_ardr_truth.py`) and runs D2-2 on Node A (the reader node, whose
  cookie alone gets D2-2's READ_RPCS); its output bytes and their SHA-256 go into the raw log.
- POOL (045b 4.5 pool row, A Q3): k gates per run, one PUBLIC SYNTHETIC seat at `b`; every block's producer
  is `PRODUCER_H<height>` (n = 100: below 50 A, below 80 B, else C), built by that producer's miner process
  (three miner processes, three whitelisted miner users on the miner node) with a producer tag in its
  coinbase. The judge reads the producer from the block bytes (`coinbase_producers`); a block G without
  exactly one tag is missing data (excluded and counted). HHI is the judge's, pooled over all pool gates.
- Chained BIRTH (`Worker.births`): the Core replay of a run of consecutive blocks in one worker call; the
  client checks every row (a birth outside G is refused, BIRTH_OUTSIDE_GATE) and writes CORE_REPLAY per height.
- Per-phase timing (mine, birth, build, cluster) in RUN_END.

Exit codes (AGENTS.md section 12) as D1's. Optimized Python (-O) is refused. Stdlib only. TEST_ONLY material
only: every key is a TEST_ONLY key from the policy seed (DRAFT rule, PENDING_FREEZE).
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).absolute().parent))
import claude_track_ardr_bidders as B  # noqa: E402
import claude_track_ardr_driver as D  # noqa: E402
import claude_track_ardr_truth as T  # noqa: E402
import claude_track_regtest_offline_export as oe  # noqa: E402

Refusal, invalid = D.Refusal, D.invalid

ITEM1_GATES = 200                 # 045b 4.6: 200 contested gates, numbered 0-199
PLANTED = range(100, 120)         # gates 100-119: the planted owner's wallets, no draw
POOL_GATES = 4                    # A Q3: gates per pool run (DEFAULT, PENDING_FREEZE)
POLL_SECONDS = 0.02               # the campaign's poll while the four nodes take a block
BIRTHS_CHUNK_BYTES = 3 * 1024 * 1024   # one BIRTHS request stays under the worker's 4 MiB request bound
CLUSTER_TOOL = Path(__file__).absolute().parent / 'claude_track_ardr_cluster.py'   # D2-2 (PR #616)
SEAT = 'S0'


# ---------------------------------------------------------------------------------------------------------
# Item 1 winners and the bidder lists (045b 4.6; A Q1, Q6).

def item1_winner(seed: bytes, run: int, plan: dict, gate: int) -> tuple[str, dict | None]:
    """The winner wallet of item-1 gate `gate` and its draw (None for a planted gate): gates 100-119 go to
    the planted owner's wallet at position `j mod m` (j = gate - 100, m its wallet count, ascending order);
    every other gate draws `WINNER_G<ggg>` (n = 40), winner `W<value>`."""
    if not (type(gate) is int and 0 <= gate < ITEM1_GATES):
        raise invalid('ITEM1_GATE')
    if gate in PLANTED:
        wallets = plan['owners'][plan['planted_owner']]['wallets']
        return wallets[(gate - PLANTED.start) % len(wallets)], None
    label = f'WINNER_G{gate:03d}'
    value, k = D.draw(seed, 'ITEM1', run, label, 40)
    return B.wallet_id(value), {'e': 'ITEM1', 'r': run, 'label': label, 'k': k, 'value': value}


def item1_bidders(seed: bytes, run: int, plan: dict, gates: list[int]) -> tuple[dict, list[dict]]:
    """The ITEM1 bidder list generated from the frozen rules (A Q6): one PUBLIC SYNTHETIC seat per gate, the
    gate's winner. Returns the list (`BITAGI_CT_ARDR_BIDDERS_V1`, checked by `parse_bidders`) and the draws."""
    rows, draws = [], []
    for g in gates:
        wallet, drew = item1_winner(seed, run, plan, g)
        rows.append({'gate': g, 'seats': [{'seat': SEAT, 'kind': 'SYNTHETIC', 'wallet': wallet, 'path': 'PUBLIC'}]})
        draws.append({'gate': g, 'wallet': wallet, 'draw': drew})
    doc = {'schema': B.BIDDERS_SCHEMA, 'gates': rows}
    B.parse_bidders(json.dumps(doc).encode('ascii'))
    return doc, draws


def pool_bidders(gates: list[int]) -> dict:
    """The POOL bidder list (A Q3): one PUBLIC SYNTHETIC seat per gate, wallet `W<gate mod 40>` (DEFAULT)."""
    doc = {'schema': B.BIDDERS_SCHEMA, 'gates': [
        {'gate': g, 'seats': [{'seat': SEAT, 'kind': 'SYNTHETIC', 'wallet': B.wallet_id(g % B.WALLETS),
                               'path': 'PUBLIC'}]} for g in gates]}
    B.parse_bidders(json.dumps(doc).encode('ascii'))
    return doc


def doc_sha256(doc: dict) -> str:
    """The SHA-256 of a generated list's canonical bytes (sorted keys, no spaces, ASCII)."""
    return hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(',', ':')).encode('ascii')).hexdigest()


def gate_observation_id(experiment: str, run: int, gate: int) -> str:
    """The observation id of one gate (A Q2: the item-1 unit is the gate inside the run): D4's run-level id
    `OBS-<e><run:07>` and `-G<gate:03>` (DEFAULT for D4's list format's new version)."""
    if not (type(gate) is int and 0 <= gate < 1000 and type(run) is int and 0 <= run < 10**7):
        raise invalid('OBSERVATION_ID')
    return 'OBS-%d%07d-G%03d' % (D.EXPERIMENTS.index(experiment) + 1, run, gate)


def rung0_fee(b: int, v: int = B.CANDIDATE_VSIZE) -> int:
    """Item 1 and pool: rung 0 at feerate b, f_0 = ceil(b v / 1000) (no fee draw)."""
    if not (type(b) is int and b >= 1):
        raise invalid('PARAM_B')
    return B.ceil_div(b * v, 1000)


# ---------------------------------------------------------------------------------------------------------
# Pool producers (045b 4.6 draw table, `PRODUCER_H<height>`).

def producer(seed: bytes, run: int, height: int) -> tuple[str, int, int]:
    """The producer of block `height` in pool run `run`: A below 50, B below 80, else C; and value, k."""
    value, k = D.draw(seed, 'POOL', run, f'PRODUCER_H{height}', 100)
    return ('A' if value < 50 else 'B' if value < 80 else 'C'), value, k


def coinbase_producers(block_hex: str) -> list[str]:
    """The producer tags the block's coinbase scriptSig carries (each push equal to PRODUCER_TAG and one
    letter of PRODUCERS), read from the block bytes; the judge counts a block with not exactly one tag as
    missing data."""
    raw = bytes.fromhex(block_hex)
    reader = D.Reader(raw[80:])
    if reader.varint() < 1:
        raise invalid('BLOCK_NO_COINBASE')
    reader.take(4)
    if reader.data[reader.at:reader.at + 2] == b'\x00\x01':
        reader.take(2)
    if reader.varint() != 1:
        raise invalid('COINBASE_SHAPE')
    reader.take(36)
    script = reader.take(reader.varint())
    tags = []
    for push in script_pushes(script):
        if len(push) == len(D.PRODUCER_TAG) + 1 and push.startswith(D.PRODUCER_TAG):
            letter = push[-1:].decode('ascii', 'replace')
            if letter in D.PRODUCERS:
                tags.append(letter)
    return tags


PUSHDATA_WIDTH = {0x4c: 1, 0x4d: 2, 0x4e: 4}   # OP_PUSHDATA1, 2, 4: the length's width (little-endian)


def script_pushes(script: bytes) -> list[bytes]:
    """The data pushes of a script in order (round 1, P3-3): OP_0 (an empty push), OP_PUSHBYTES_1-75,
    OP_PUSHDATA1/2/4 with their little-endian lengths; every other opcode carries no data and is skipped. A
    push that runs past the script's end is refused (COINBASE_PUSH_TRUNCATED, exit 2)."""
    pushes, at = [], 0
    while at < len(script):
        op = script[at]
        at += 1
        if op > 0x4e:
            continue
        if op in PUSHDATA_WIDTH:
            width = PUSHDATA_WIDTH[op]
            if at + width > len(script):
                raise invalid('COINBASE_PUSH_TRUNCATED')
            n = int.from_bytes(script[at:at + width], 'little')
            at += width
        else:
            n = op
        if at + n > len(script):
            raise invalid('COINBASE_PUSH_TRUNCATED')
        pushes.append(script[at:at + n])
        at += n
    return pushes


# ---------------------------------------------------------------------------------------------------------
# Chained Core replay.

class Chain:
    """The blocks from H0 on not yet replayed, and the canonical state of the last replayed one. `flush`
    replays them in chunks (one `BIRTHS` call each), writes one CORE_REPLAY line per height and returns the
    rows."""

    def __init__(self, worker: B.Worker, h0: int, log: D.RawLog, timing: dict):
        self.worker, self.h0, self.log, self.timing = worker, h0, log, timing
        self.state: str | None = None
        self.next_height = h0
        self.pending: list[str] = []
        self.tip = 0   # the height of the last block mined in the run (setup starts at 0, the genesis)

    def add(self, block: dict) -> None:
        if block['height'] != self.tip + 1:
            raise invalid('CHAIN_HEIGHT')
        self.tip = block['height']
        if block['height'] < self.h0:
            return
        if block['height'] != self.next_height + len(self.pending):
            raise invalid('CHAIN_HEIGHT')
        self.pending.append(block['block_hex'])

    def flush(self, unit: dict, gate: int | None = None) -> list[dict]:
        rows = []
        while self.pending:
            chunk, size = [], 0
            for block_hex in self.pending:
                if chunk and size + len(block_hex) > BIRTHS_CHUNK_BYTES:
                    break
                chunk.append(block_hex)
                size += len(block_hex) + 1
            t0 = D.CLOCK()
            answer = self.worker.births(self.next_height, chunk, self.state, gate)
            self.timing['birth_ns'] += D.CLOCK() - t0
            self.timing['birth_calls'] += 1
            for row in answer['rows']:
                self.log.write('CORE_REPLAY', unit, height=row['height'], born=row['born'],
                               next_birth=row['next_birth'], state_sha256=row['state_sha256'])
            rows.extend(answer['rows'])
            self.state = answer['state']
            self.next_height += len(chunk)
            del self.pending[:len(chunk)]
        return rows


# ---------------------------------------------------------------------------------------------------------
# The campaign run.

def new_timing() -> dict:
    return {'setup_ns': 0, 'mine_ns': 0, 'mine_blocks': 0, 'birth_ns': 0, 'birth_calls': 0, 'build_ns': 0,
            'build_calls': 0, 'cluster_ns': 0, 'total_ns': 0}


def campaign(experiment: str, params: dict, seed: bytes, run: int, node_a: Path, node_b: Path, work: Path,
             log: D.RawLog, topology: D.Topology, cargo: str, cluster_tool: Path | None = None,
             gates: list[int] | None = None, method_policy: dict | None = None, mode: str = 'EXPLORATORY',
             observation_start: dict | None = None, deadline: dict | None = None,
             draft_fault: dict | None = None) -> dict:
    """One ITEM1 or POOL run on a started-later `topology` (built with `reader` for ITEM1, `pool` for POOL).
    `params`: `b`, `H0`, `gates_per_run` (checked by the policy read). `gates`: the gate numbers (default:
    ITEM1 0..gates_per_run-1, POOL 0..gates_per_run-1). `deadline`: the driver's gate-loop deadline (U3, A Q5),
    written in RUN_START whole, its monotonic `clock_ns` included (U3 pre-PR P3-3: the same clock as each line's
    `t_ns`, so the stop is provable from the log; a number, not a secret). U3 (A #636 decision (i)): the topology starts, and its version check runs, BEFORE
    RUN_START, so a setup failure leaves no raw-log line (the unit stays BEFORE_START, re-dispatchable, and the
    slice stops). `draft_fault` (D2-3c, Python API only, never CONFIRMATORY): a test fault at one gate
    (`check_draft_fault`). Returns the RUN_END summary."""
    if experiment not in ('ITEM1', 'POOL'):
        raise invalid('CAMPAIGN_EXPERIMENT')
    tool = (cluster_tool or CLUSTER_TOOL) if experiment == 'ITEM1' else None
    if tool is not None and not tool.is_file():
        raise oe.Prerequisite('CLUSTER_TOOL_MISSING')   # round 1, P2-2: before any node starts
    if tool is not None and mode == 'CONFIRMATORY' and tool.resolve() != CLUSTER_TOOL.resolve():
        raise invalid('CLUSTER_TOOL_IN_CONFIRMATORY')   # round 1, P3-7: CONFIRMATORY runs the tree's own D2-2
    if experiment == 'ITEM1':   # round 1, P3-4: D2-2's bounds and the window, before any node starts
        T.check_method_bounds(T.method_values(method_policy or DRAFT_METHOD_POLICY, mode)[0], params)
    b, h0, count = params['b'], params['H0'], params['gates_per_run']
    gates = list(range(count)) if gates is None else gates
    check_draft_fault(draft_fault, gates, mode)   # D2-3c: before any node starts
    plan = B.assignment(seed, run)
    if experiment == 'ITEM1':
        bidders, draws = item1_bidders(seed, run, plan, gates)
    else:
        bidders, draws = pool_bidders(gates), []
    worker_dir = work / 'worker'
    worker_dir.mkdir()
    worker = B.Worker(cargo, seed, run, h0, worker_dir)
    timing = new_timing()
    done: set[int] = set()
    prefix: dict = {}   # D2-3c: `_gates` snapshots the state of every gate that reached GATE_END
    t_start = D.CLOCK()
    run_unit = D.unit_id(experiment, run)
    miners: dict[str, D.MinerProcess] = {}
    phase = 'GATES'
    try:
        topology.start()   # U3 decision (i): before RUN_START; a failure here writes no line at all
        try:
            policy = D.CAMPAIGN_MINER[experiment]
            log.write('RUN_START', run_unit,
                      observation_start=observation_start or {'source': 'LOCAL_EXPLORATORY', 'utc': None},
                      miner_policy=policy, node_versions=D.ROLE_VERSIONS, params=params,
                      bidders_sha256=doc_sha256(bidders), gates=gates,
                      deadline=deadline,
                      draft_fault=draft_fault)
            log.write('BIDDERS', run_unit, bidders=bidders, bidders_sha256=doc_sha256(bidders), draws=draws)
            nodes = topology.nodes
            if experiment == 'ITEM1':
                miners['A'] = D.MinerProcess(nodes['miner'], policy)
            else:
                for letter, user in topology.producer_users().items():
                    miners[letter] = D.MinerProcess(nodes['miner'], policy, user=user, producer=letter)
            ctx = _gates(experiment, bidders['gates'], plan, seed, run, b, h0, log, nodes, miners, worker,
                         timing, run_unit, draft_fault, prefix, done, deadline=deadline)
            # round 2, P3-A: ITEM1 from the last GATE_END on, before the truth (section 16); D2-3c (A
            # 6548007197 For-A 1): POOL's truth and producer description run in their own phase POST_GATES.
            phase = 'CLUSTER' if experiment == 'ITEM1' else 'POST_GATES'
            result = _truth(ctx, seed, run, plan, worker)
            if experiment == 'ITEM1':
                t_cluster = D.CLOCK()
                result['summary']['cluster'] = run_cluster(log, run_unit, topology.nodes['A'], work,
                                                           result['truth'], method_policy or DRAFT_METHOD_POLICY,
                                                           mode, tool)
                timing['cluster_ns'] = D.CLOCK() - t_cluster
            phase = 'END'
            timing['total_ns'] = D.CLOCK() - t_start
            # U3 Part C (A Q5): a run stopped by its gate-loop deadline ends DONE over the gates it finished;
            # the gates it did not start are missing (A Q2), named here and in the collection (NOT_STARTED).
            log.write('RUN_END', run_unit, status='DONE', timing=timing, **result['summary'],
                      deadline_reached=bool(ctx['gates_not_started']), gates_not_started=ctx['gates_not_started'])
        except Exception as error:
            outcome = no_prefix(experiment, phase)
            try:
                if outcome is None:   # D2-3c: ITEM1 failed in phase GATES; Node A is still up (teardown below)
                    outcome = run_prefix(log, run_unit, prefix, error, topology, seed, run, plan, worker, work,
                                         method_policy or DRAFT_METHOD_POLICY, mode, tool, timing,
                                         failed_gate_of(gates, done, phase))
            finally:   # RUN_END FAILED whatever the prefix did; the first error is the one raised
                run_failed(log, run_unit, experiment, run, gates, done, phase, timing, error, outcome)
            if outcome[0] == 'FAILED' and outcome[1] in PREFIX_EXIT_5:   # B decision (D2-3c round 3, For A)
                raise Refusal(outcome[1], D.EXIT_SECURITY) from error
            raise
        return {**result['summary'], 'timing': timing, 'truth': result['truth']}
    finally:
        for miner in miners.values():
            miner.stop()
        topology.stop()
        shutil.rmtree(worker_dir, ignore_errors=True)


def is_refusal(error: BaseException) -> bool:
    """A driver Refusal from either copy of the driver module (round 1, P3-1: run as a script the driver is
    `__main__`, and its Refusal is another class than `claude_track_ardr_driver.Refusal`)."""
    return (type(error).__name__ == 'Refusal' and isinstance(getattr(error, 'code', None), str)
            and type(getattr(error, 'exit_code', None)) is int)


def failure_code(error: BaseException) -> str:
    if is_refusal(error):
        return error.code
    if isinstance(error, (oe.Prerequisite, oe.Mismatch)):
        return D.error_code(type(error).__name__.upper(), error)
    return 'INTERNAL ' + type(error).__name__.upper()


def run_failed(log, run_unit, experiment, run, gates, done, phase, timing, error, outcome=None) -> None:
    """RUN_END FAILED (format doc section 16). Phase GATES: a gate without GATE_END is EXCLUDED (A Q2), the
    failed gate and every later one; no run replaces them. For ITEM1 (D2-3c, A 6548007197 For-A 2) that
    holds only when the prefix D2-2 ran OK on the gates that reached GATE_END; a prefix that FAILED or was
    NOT_RUN leaves no gate with a D2-2 output, so every gate is EXCLUDED and `cluster_failed` is true.
    Phase POST_GATES (POOL, D2-3c): the truth or the producer description failed after the last GATE_END;
    the gates without GATE_END are EXCLUDED (none, normally). Phase CLUSTER (round 1, P2-2; round 2, P3-A):
    ITEM1 failed after the last GATE_END (the ground truth, the anchor keys, the placed members, D2-2's
    inputs, or D2-2 failed, timed out or was refused), so no gate has its D2-2 output: every gate of the run
    is EXCLUDED (CLUSTER_FAILED). Phase END: RUN_END DONE itself could not be written. `outcome` is the
    prefix's `(cluster_prefix, reason)`. A job killed outside Python leaves no RUN_END; the reader applies
    the same rule. If this line cannot be written either, the first error stands (the caller re-raises it)."""
    status, reason = outcome or no_prefix(experiment, phase) or ('NOT_RUN', 'NO_OUTCOME')
    cluster_failed = phase == 'CLUSTER' or (experiment == 'ITEM1' and phase == 'GATES' and status != 'OK')
    excluded = list(gates) if cluster_failed else [g for g in gates if g not in done]
    # A 6549827052 Q2: the report names g (the first gate without GATE_END; null when every gate has one) and
    # the death cause (`code`); whether a prefix ran depends only on these two, never on a result. Round 3:
    # only a failure in phase GATES has a g; after the last GATE_END (CLUSTER, POST_GATES, END) it is null.
    failed_gate = failed_gate_of(gates, done, phase)
    try:
        log.write('RUN_END', run_unit, status='FAILED', code=failure_code(error), phase=phase,
                  failed_gate=failed_gate, cluster_failed=cluster_failed, cluster_prefix=status,
                  cluster_prefix_reason=reason,
                  timing=timing, excluded_gates=excluded,
                  excluded_observation_ids=[gate_observation_id(experiment, run, g) for g in excluded])
    except Exception:   # noqa: BLE001 - the original error is the one reported
        pass


def failed_gate_of(gates, done, phase) -> int | None:
    """g: the first gate without GATE_END, for a failure in phase GATES only (null after the last GATE_END)."""
    return next((g for g in gates if g not in done), None) if phase == 'GATES' else None


# ---------------------------------------------------------------------------------------------------------
# D2-3c: D2-2 on a failed ITEM1 prefix (A #632 6548007197 For-A 2) and the DRAFT test fault.

PREFIX_STATUSES = ('OK', 'FAILED', 'NOT_RUN')
NO_PREFIX_ERRORS = ('SECRET_IN_LOG', 'LOG_BOUND')   # the log refused a line: nothing more is written to it
# B decision (D2-3c round 3, For A): a security failure in the prefix ends the run with exit 5, as in phase
# CLUSTER (where D2-2's exit 5 passes through, `cluster_exit`): the log refusing the prefix's own
# CLUSTER_TOOL line for a secret (the prefix wrote its truth and D2-2's inputs into `cluster_prefix`), or
# D2-2 itself exiting 5 on the prefix. RUN_END FAILED keeps the first error's `code`; the raised refusal
# carries the prefix's reason with exit 5. Any other prefix failure keeps the first error's exit.
PREFIX_EXIT_5 = ('SECRET_IN_LOG', 'CLUSTER_TOOL_FAILED 5')
# First errors that skip the prefix (an oe.Prerequisite whose text is the key; U4's timeouts): the prefix
# would wait on the same thing again. Round 4 (P2-b, B decision): a node-call timeout on Node A (the probe
# would wait again). Round 5 (A 6551799924 P3-3, B default): a worker timeout (the prefix's `_truth` asks the
# worker for the ANCHOR_KEY scripts, up to 1,800 s more, then D2-2 up to CLUSTER_SECONDS).
PREFIX_SKIP_TIMEOUTS = {'NODE_CALL_TIMEOUT A': 'NODE_A_TIMEOUT', 'WORKER_TIMEOUT': 'WORKER_TIMEOUT'}


def no_prefix(experiment: str, phase: str) -> tuple[str, str] | None:
    """The prefix outcome fixed by the experiment and the phase alone, or None when a prefix may run (ITEM1,
    phase GATES)."""
    if experiment != 'ITEM1':
        return ('NOT_RUN', 'NO_CLUSTER')
    if phase != 'GATES':
        return ('NOT_RUN', 'PHASE_' + phase)
    return None


def run_prefix(log, run_unit, prefix, error, topology, seed, run, plan, worker, work, method_policy, mode, tool,
               timing, failed_gate=None) -> tuple[str, str | None]:
    """D2-2 on the gates of a failed ITEM1 run that reached GATE_END (A 6548007197 For-A 2), before
    teardown, on Node A: the truth of that prefix, a `CLUSTER_TOOL` line with `prefix` true and the prefix's
    gates, D2-2 bounded by the same CLUSTER_SECONDS. Never after SECRET_IN_LOG or LOG_BOUND (the log refused
    a line), never with no gate done, never when Node A or the worker timed out or Node A does not answer.
    Round 4 (P2-a): before the first slow step it writes PREFIX_START with the first error's code, the phase,
    g and the prefix's gates, so a unit killed during the prefix (no RUN_END) still has its death cause in
    the log. Returns
    `(cluster_prefix, reason)`; it never raises an Exception, so the first error and its RUN_END stand."""
    if is_refusal(error) and error.code in NO_PREFIX_ERRORS:
        return ('NOT_RUN', error.code)
    if not prefix.get('rows'):
        return ('NOT_RUN', 'NO_GATE_DONE')
    skip = PREFIX_SKIP_TIMEOUTS.get(str(error)) if isinstance(error, oe.Prerequisite) else None
    if skip is not None:   # round 4 (P2-b), round 5 (P3-3): that part already timed out; no second wait
        return ('NOT_RUN', skip)
    try:
        log.write('PREFIX_START', run_unit, code=failure_code(error), phase='GATES', failed_gate=failed_gate,
                  gates=[row['gate'] for row in prefix['rows']])
    except Exception as failed:   # noqa: BLE001 - the line refused; the first error stands
        return ('FAILED', failure_code(failed))
    try:
        reader = topology.nodes['A']
        reader.rpc('getblockchaininfo')
    except Exception:   # noqa: BLE001 - any failure to answer is the reason, never the run's error
        return ('NOT_RUN', 'NODE_A_DOWN')
    t0 = D.CLOCK()
    try:
        result = _truth(prefix, seed, run, plan, worker)
        run_cluster(log, run_unit, reader, work, result['truth'], method_policy, mode, tool, prefix=True)
    except Exception as failed:   # noqa: BLE001 - the prefix's error never masks the first error
        return ('FAILED', failure_code(failed))
    finally:
        timing['cluster_ns'] = D.CLOCK() - t0
    return ('OK', None)


DRAFT_FAULT_WHEN = ('BEFORE_GATE_END', 'AFTER_GATE_END')


def check_draft_fault(fault: dict | None, gates: list[int], mode: str) -> None:
    """The DRAFT test fault (D2-3c; Python API only, no CLI flag): `{'gate': g, 'when': BEFORE_GATE_END |
    AFTER_GATE_END}` makes gate g raise DRAFT_FAULT (exit 4) just before or just after its GATE_END. Refused
    in CONFIRMATORY (DRAFT_FAULT_IN_CONFIRMATORY) and when malformed (DRAFT_FAULT_SHAPE), before any node
    starts; RUN_START records it (`draft_fault`)."""
    if fault is None:
        return
    if mode == 'CONFIRMATORY':
        raise invalid('DRAFT_FAULT_IN_CONFIRMATORY')
    if not (isinstance(fault, dict) and set(fault) == {'gate', 'when'} and type(fault['gate']) is int
            and fault['gate'] in gates and fault['when'] in DRAFT_FAULT_WHEN):
        raise invalid('DRAFT_FAULT_SHAPE')


def draft_fault_at(fault: dict | None, gate: int, when: str) -> None:
    if fault is not None and fault['gate'] == gate and fault['when'] == when:
        raise Refusal('DRAFT_FAULT', D.EXIT_INTERNAL)


def _mine(log, unit, nodes, miners, held, last, timing, chain, seed, run, experiment, gate=None):
    t0 = D.CLOCK()
    if experiment == 'POOL':
        height = chain.tip + 1
        letter, value, k = producer(seed, run, height)
        log.write('DRAW', unit, e='POOL', r=run, label=f'PRODUCER_H{height}', k=k, value=value, producer=letter)
        miner = miners[letter]
    else:
        miner = miners['A']
    block = D.mine(log, unit, nodes, miner, held, last, gate=gate, poll=POLL_SECONDS)
    if experiment == 'POOL' and block.get('producer') != letter:
        raise invalid('PRODUCER_MINER')
    timing['mine_ns'] += D.CLOCK() - t0
    timing['mine_blocks'] += 1
    chain.add(block)
    return block


WAIT_SECONDS = 120.0


def wait_named(condition, what: str, code: str) -> None:
    """U3 Part C (A #638 check 6552915714 P3-4): a campaign wait past WAIT_SECONDS is exit 3 with its own code
    word (`PREREQUISITE FUNDING_NOT_AT_MINER`, `PREREQUISITE BID_NOT_AT_MINER`), as `D.mine` names
    BLOCK_NOT_ACCEPTED, so RUN_END and PREFIX_START carry a death cause and not the bare word PREREQUISITE. A
    node call's own timeout inside the wait (`NODE_CALL_TIMEOUT <role>`) is re-raised unchanged (U4)."""
    try:
        D.wait_until(condition, what, WAIT_SECONDS, POLL_SECONDS)
    except oe.Prerequisite as error:
        if D.node_call_timeout(error):
            raise
        raise oe.Prerequisite(code) from None


def _gates(experiment, gates, plan, seed, run, b, h0, log, nodes, miners, worker, timing, run_unit, fault, prefix,
           done, deadline=None) -> dict:
    """The setup, the funding and every gate. After a gate's GATE_END (and only then) `prefix` gets a
    snapshot of the run's state (D2-3c), so a failed run still has the rows of the gates that reached
    GATE_END; then the gate joins `done`. U3 Part C (A Q5): before each GATE_START, when the driver's
    `deadline` is set and the monotonic clock is at or past its `clock_ns`, no further gate starts (the rule
    reads the clock only, never a result); the gates left are returned as `gates_not_started`. A deadline
    reached before the first gate is exit 3 `DEADLINE_BEFORE_FIRST_GATE` (no gate to judge)."""
    t0 = D.CLOCK()
    held: set[str] = set()
    last = [0]
    chain = Chain(worker, h0, log, timing)
    coinbases = []
    for _ in range(D.SETUP_BLOCKS):
        block = _mine(log, run_unit, nodes, miners, held, last, timing, chain, seed, run, experiment)
        coinbases.append((block['coinbase_txid'], block['coinbase_value']))
    seats = {s['wallet']: s for g in gates for s in g['seats']}
    keys = worker.keys([(s['kind'], w, B.seat_anchor_label(plan, s, 0)) for w, s in seats.items()])
    layout = B.funding_layout(plan, gates)
    built = B.build_funding(layout, (coinbases[0][0], 0), coinbases[0][1],
                            {w: bytes.fromhex(k['fee_script']) for w, k in keys.items()})
    funding = built['funding']
    for stage, raws in (('FAN_OUT', built['raws'][:1]), ('OWNER', built['raws'][1:])):
        if not raws:
            continue
        sent = []
        for raw in raws:
            tx = D.Tx(raw)
            nodes['relay'].rpc('sendrawtransaction', raw.hex())
            log.write('FUNDING_SENT', run_unit, node='relay', txid=tx.txid, hex=raw.hex(), stage=stage,
                      **B.funding_sent_fields(funding, tx.txid, seats))
            sent.append(tx.txid)
        wait_named(lambda: set(sent) <= set(nodes['miner'].call('getrawmempool')), 'the funding at the miner',
                   'FUNDING_NOT_AT_MINER')
        block = _mine(log, run_unit, nodes, miners, held, last, timing, chain, seed, run, experiment)
        for f in funding.values():
            if f['txid'] in sent:
                f['height'] = block['height']
    if block['height'] >= h0:
        raise invalid('H0_TOO_LOW')   # the setup and funding blocks come before the first gate
    timing['setup_ns'] = D.CLOCK() - t0
    fee = rung0_fee(b)
    height, hearts, winners, rows, producers, anchors = h0, {}, {}, [], [], {}
    not_started: list[int] = []
    for index, entry in enumerate(gates):
        g = entry['gate']
        now = D.CLOCK()   # P3-3: GATE_START carries this reading, so the log shows each start before the deadline
        if deadline is not None and now >= deadline['clock_ns']:   # A Q5: the clock only
            not_started = [e['gate'] for e in gates[index:]]
            if not rows:
                raise oe.Prerequisite('DEADLINE_BEFORE_FIRST_GATE')
            break
        unit = D.unit_id(experiment, run, gate=g)
        seat = entry['seats'][0]
        observation = gate_observation_id(experiment, run, g)
        log.write('GATE_START', unit, t_ns=now, gate=g, height=height, wallet=seat['wallet'],
                  observation_id=observation)
        while block['height'] < height - 1:
            block = _mine(log, unit, nodes, miners, held, last, timing, chain, seed, run, experiment)
        chain.flush(unit)
        tip = (block['height'], block['block_hash'])
        t_build = D.CLOCK()
        rung = worker.build(seat['kind'], seat['wallet'], height, tip, funding[(seat['wallet'], g)],
                            B.seat_anchor_label(plan, seat, hearts.get(seat['wallet'], 0)), [fee], chain.state)[0]
        timing['build_calls'] += 1
        log.write('GENERATED', unit, seat=seat['seat'], ladder=[fee],
                  rungs=[{k: v for k, v in rung.items() if k != 'hex'}])
        for role in ('A', 'B'):
            result = nodes[role].rpc('testmempoolaccept', [rung['hex']])
            log.write('TESTMEMPOOLACCEPT', unit, node=role, txid=rung['txid'], result=result)
            if not (isinstance(result, list) and len(result) == 1 and result[0].get('allowed') is True):
                raise oe.Mismatch('TESTMEMPOOLACCEPT_REGISTER')
        B.hand_off(seat, rung['hex'], nodes['relay'], None, held, log, unit)
        wait_named(lambda: rung['txid'] in nodes['miner'].call('getrawmempool'), 'the bid at the miner',
                   'BID_NOT_AT_MINER')
        timing['build_ns'] += D.CLOCK() - t_build
        context = {'height': height, 'winner': rung['txid'], 'registers': [rung['txid']]} \
            if experiment == 'ITEM1' else None
        block = _mine(log, unit, nodes, miners, held, last, timing, chain, seed, run, experiment, gate=context)
        replay = chain.flush(unit, gate=height)[-1]
        bid = [{'seat': seat, 'j': 0, 'p0': b, 'fees': [fee]}]
        row = B.gate_row(entry, height, bid, replay['born'], {rung['txid']})
        row.update(block_hash=block['block_hash'], next_birth=replay['next_birth'], wallet=seat['wallet'],
                   order=[o['txid'] for o in block['order']])
        if experiment == 'POOL':
            row['producer_tags'] = coinbase_producers(block['block_hex'])
            producers.append(row['producer_tags'])
        rows.append(row)
        anchors[rung['txid']] = D.Tx(bytes.fromhex(rung['hex'])).outputs[1][1].hex()
        winners[rung['txid']] = seat['wallet']
        hearts[seat['wallet']] = hearts.get(seat['wallet'], 0) + 1
        draft_fault_at(fault, g, 'BEFORE_GATE_END')
        log.write('GATE_END', unit, gate=g, height=height, status='OBSERVED', observation_id=observation,
                  winner_txid=rung['txid'],
                  wallet=seat['wallet'], block_hash=block['block_hash'], next_birth=replay['next_birth'],
                  **({'producer_tags': row['producer_tags']} if experiment == 'POOL' else {}))
        prefix.update(experiment=experiment, funding=funding, built=built, rows=list(rows), winners=dict(winners),
                      anchors=dict(anchors), block=block, producers=list(producers))
        done.add(g)
        draft_fault_at(fault, g, 'AFTER_GATE_END')
        height = replay['next_birth']
    return {'experiment': experiment, 'funding': funding, 'winners': winners, 'built': built, 'rows': rows,
            'anchors': anchors, 'block': block, 'producers': producers, 'gates_not_started': not_started}


def _truth(ctx: dict, seed: bytes, run: int, plan: dict, worker: B.Worker) -> dict:
    """After the last GATE_END (round 2, P3-A): the ground truth, the ANCHOR_KEY scripts (a `worker.keys`
    call) and the placed members. The campaign enters this in phase CLUSTER for ITEM1, so a failure here,
    before D2-2's output exists, excludes every gate (section 16)."""
    winners, built, rows, block = ctx['winners'], ctx['built'], ctx['rows'], ctx['block']
    truth = B.ground_truth(seed, run, plan, B.funding_by_wallet(ctx['funding']), [], winners=winners,
                           excluded_txids=built['excluded_txids'],
                           gates=[{k: r[k] for k in ('gate', 'height', 'born', 'status', 'block_hash')}
                                  for r in rows])
    labels = sorted({g['anchor_label'] for g in truth['link_groups'] if g['kind'] == 'ANCHOR_KEY'})
    label_keys = worker.keys([('SYNTHETIC', label.split('_')[1], label) for label in labels]) if labels else {}
    B.record_anchor_placed(truth, ctx['anchors'], {label: label_keys[label.split('_')[1]]['anchor_script']
                                                   for label in labels})
    summary = {'gates': rows, 'winners': winners, 'excluded_txids': built['excluded_txids'],
               'owner_txids': built['owner_txids'], 'tip': [block['height'], block['block_hash']]}
    if ctx['experiment'] == 'POOL':
        summary['producers_description'] = describe_producers(ctx['producers'])
    return {'summary': summary, 'truth': truth}


DRAFT_METHOD_POLICY = {'schema': T.METHOD_POLICY_SCHEMA, **{k: 'PENDING_FREEZE' for k in T.METHOD_FIELDS}}
CLUSTER_SECONDS = 3600


def run_cluster(log: D.RawLog, unit: dict, reader: D.RoleNode, work: Path, truth: dict, method_policy: dict,
                mode: str, tool: Path, prefix: bool = False) -> dict:
    """At the end of an ITEM1 run, before teardown (A Q7): the ground truth and D2-2's three inputs
    (`claude_track_ardr_truth`) into a new 0700 directory, then D2-2 as a subprocess on the reader node (Node
    A, whose cookie alone has READ_RPCS; bitcoin-cli reads the cookie from the node's data directory; the
    driver itself never uses it). The raw log gets the truth, the three inputs, D2-2's output bytes, every
    SHA-256 and D2-2's exit code; a D2-2 refusal is then a run refusal (CLUSTER_TOOL_FAILED, exit 2). D2-3c:
    the record carries `prefix` (true for D2-2 on a failed run's prefix, in its own `cluster_prefix`
    directory) and `gates` (the truth's gate numbers, the gates D2-2 judged)."""
    if not tool.is_file():
        raise oe.Prerequisite('CLUSTER_TOOL_MISSING')
    folder = oe.private(work / ('cluster_prefix' if prefix else 'cluster'))
    truth_bytes = B.write_lf(folder / 'truth.json', truth)
    converted = T.convert(truth, method_policy, mode)
    hashes = T.write_inputs(folder, converted)
    out = folder / 'cluster.json'
    command = [sys.executable, str(tool), '--gates', str(folder / 'gates.json'), '--method',
               str(folder / 'method.json'), '--truth', str(folder / 'cluster_truth.json'), '--out', str(out),
               '--chain', 'regtest', '--bitcoin-cli', str(reader.cli), '--datadir', str(reader.datadir),
               '--rpcport', str(reader.rpcport)]
    env = {k: v for k, v in os.environ.items() if not k.startswith('PYTHON')}
    try:
        done = subprocess.run(command, capture_output=True, timeout=CLUSTER_SECONDS, check=False, env=env,
                              stdin=subprocess.DEVNULL)   # bytes: a non-UTF-8 stdout is data (round 2, P3-D)
    except subprocess.TimeoutExpired:
        raise oe.Prerequisite('CLUSTER_TOOL_TIMEOUT') from None   # round 1, P2-2
    except OSError:
        raise oe.Prerequisite('CLUSTER_TOOL_NOT_RUN') from None
    output = out.read_bytes() if out.is_file() else b''
    try:
        summary = json.loads(done.stdout)
    except ValueError:
        summary = None
    record = {'prefix': prefix, 'gates': [g['gate'] for g in truth['gates']],
              'tool_sha256': hashlib.sha256(tool.read_bytes()).hexdigest(), 'exit': done.returncode,
              'stdout': summary, 'truth_sha256': hashlib.sha256(truth_bytes).hexdigest(), 'inputs_sha256': hashes,
              'drafted_method_fields': converted['drafted'], 'output_sha256': hashlib.sha256(output).hexdigest(),
              'output_bytes': len(output)}
    inputs = {name: converted[name] for name in ('cluster_truth', 'gates', 'method')}
    try:   # round 2, P3-D: the record is written whatever the output bytes are; non-ASCII output is null
        text = output.decode('ascii')
    except UnicodeDecodeError:
        text = None
    log.write('CLUSTER_TOOL', unit, **record, truth=truth, inputs=inputs, output=text)
    if done.returncode != 0 or not output:
        raise Refusal(f'CLUSTER_TOOL_FAILED {done.returncode}', cluster_exit(done.returncode))
    if text is None:
        raise invalid('CLUSTER_OUTPUT_NOT_ASCII')
    metrics = json.loads(output)['metrics']
    return {**record, 'metrics': {k: metrics[k] for k in ('link_recall', 'link_precision', 'planted_pairs',
                                                          'detected_pairs', 'observed_wallets')}}


def cluster_exit(code: int) -> int:
    """D2-2's exit code as the run's (round 1, P3-6; AGENTS.md section 12): 2, 3, 5 and 6 pass through; any
    other failure (4, a signal, an unknown code, or exit 0 without an output file) is an internal error, 4."""
    return code if code in (D.EXIT_VALIDATION, D.EXIT_PREREQUISITE, D.EXIT_SECURITY, D.EXIT_REFUSAL) \
        else D.EXIT_INTERNAL


def describe_producers(tags: list[list[str]]) -> dict:
    """A per-run description of block-G producers (counts; the missing-data count). No verdict: the pooled
    HHI over all pool gates is the judge's (A Q3)."""
    counts = {p: 0 for p in D.PRODUCERS}
    missing = 0
    for t in tags:
        if len(t) != 1:
            missing += 1
        else:
            counts[t[0]] += 1
    return {'counts': counts, 'missing': missing}


def wall(ns: int) -> float:
    return round(ns / 1e9, 3)


def main(argv: list[str] | None = None) -> int:
    """The local exploratory CLI. It ends through claude_track_exit.run (AGENTS.md section 12; #632 Codex review
    r4432937214, A 6548007197): `-O`, a Refusal, a Prerequisite and a Mismatch end as one FAIL JSON line with
    their exit code, as in the driver; a lost output or any other exception exits 4."""
    if not __debug__:
        print(json.dumps({'result': 'FAIL', 'code': 'OPTIMIZED_PYTHON', 'exit': D.EXIT_REFUSAL}))
        return D.EXIT_REFUSAL
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--experiment', default='ITEM1', choices=('ITEM1', 'POOL'))
    p.add_argument('--gates', type=int, default=10)
    p.add_argument('--first-gate', type=int, default=0)
    p.add_argument('--b', type=int, default=3000)
    p.add_argument('--h0', type=int, default=110)
    p.add_argument('--seed', default='11' * 32)
    p.add_argument('--run', type=int, default=0)
    p.add_argument('--node-a', type=Path, required=True)
    p.add_argument('--node-b', type=Path, required=True)
    p.add_argument('--work', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--cargo', default='cargo')
    p.add_argument('--cluster-tool', type=Path)
    a = p.parse_args(argv)
    try:
        return _cli_run(a)
    except Exception as error:   # the message can hold a node's stderr or a path: codes only
        if is_refusal(error):
            code, exit_code = error.code, error.exit_code
        elif isinstance(error, oe.Prerequisite):
            code, exit_code = D.error_code('PREREQUISITE', error), D.EXIT_PREREQUISITE
        elif isinstance(error, oe.Mismatch):
            code, exit_code = D.error_code('MISMATCH', error), D.EXIT_VALIDATION
        else:
            raise
        print(json.dumps({'result': 'FAIL', 'code': code, 'exit': exit_code}, sort_keys=True))
        return exit_code


def _cli_run(a) -> int:   # pragma: no cover - local exploratory helper; its run needs real nodes
    work = oe.private(a.work)
    topology = D.Topology(a.node_a, a.node_b, work / 'nodes', pool=a.experiment == 'POOL',
                          reader=a.experiment == 'ITEM1')
    header = D.log_header({'mode': 'EXPLORATORY', 'evidence_status': 'EXPLORATORY', 'policy_sha256': None,
                           'registration_sha256': None})
    log = D.RawLog(a.out, header, topology.needles() + (str(work), str(work.resolve())))
    try:
        result = campaign(a.experiment, {'b': a.b, 'H0': a.h0, 'gates_per_run': a.gates}, bytes.fromhex(a.seed),
                          a.run, a.node_a, a.node_b, work, log, topology, a.cargo, cluster_tool=a.cluster_tool,
                          gates=list(range(a.first_gate, a.first_gate + a.gates)))
    finally:
        log.close()
    t = result['timing']
    print(json.dumps({k: (wall(v) if k.endswith('_ns') else v) for k, v in t.items()}, sort_keys=True))
    if 'cluster' in result:
        print(json.dumps(result['cluster']['metrics'], sort_keys=True))
    return D.EXIT_DONE


if __name__ == '__main__':
    import claude_track_exit
    claude_track_exit.run(main)
