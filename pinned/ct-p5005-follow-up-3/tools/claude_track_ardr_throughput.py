#!/usr/bin/env python3
"""CT-P5-001 D1t: host-turn throughput and L0 launch cost on the ARDR driver's four-node topology.

Class T Regtest development evidence only; EXPLORATORY; never mainnet, never S17-PREP, and no verdict. It
measures; A decides #258's item 2 seat ((ㄱ) default or (ㄷ) fallback). Sources: A's unit request #258
issuecomment-6537782009 sections 3 and 4 ("처리량 측정"), B's acknowledgement -6537801599 (b), A -6538196742
section 3 (b); `docs/claude-track/plans/ASSURANCE_APPLICATION_TABLE_KO.md` 4.2 and 4.3 (about 6,100 blocks
per witness, "host turn throughput not measured"). The result format is
`docs/claude-track/formats/ARDR_THROUGHPUT_V1.md`.

  measure --node-a BIN --node-b BIN --work NEW_DIR --out RESULT.json --log RAW.jsonl
          [--blocks N] [--launches K] [--cargo C] [--offline-target D] [--online-target D]

Topology: the D1 driver's miner and relay nodes (`RoleNode`, Core 31.1, the miner process `MinerProcess`)
and, as Node A (31.1) and Node B (30.3), `claude_track_regtest_offline_export.Pair`'s nodes, because the
launch host reads both with oe's public Class T fixture read user. The relay connects to the miner, A and B.

(b) One L0 launch: four fresh nodes, then `oe.run_l0` unchanged up to `l0_broadcast` (its chain and floor
block are its own `Pair.mine`; it is stopped at its first block past H0 - 1, so 1e-2b-2a's phases are not
part of a launch), then the inclusion: D1's miner builds block H0 from the miner node's template, which must hold
the launch transaction, all four nodes accept it, and one host turn (below) must decide `Done:Born`. Timed
parts: node startup, worker processes (`oe.run_stage`, host or signer by package), chain (`Pair.mine` and
the inclusion block), prestate comparison (`oe.run_prestate`), the wait for the launch transaction to
reach the miner node (`relay_wait`) and the remainder. A launch has 8 worker processes: 7 in `oe.run_l0` to
the broadcast (5 host, 2 signer) and the inclusion turn, each timed once.

(a) On the last launch's deployment, for each of N blocks above H0: D1's miner builds the block from the
template (its own coinbase, merkle root and proof of work) and submits it; the driver waits until all four
nodes' best block is that block (D1's `oe.wait_for` polling); then one host turn: one process of the ignored
worker `launch_idle_worker` (`crates/bitagi-launch-host/tests/two_node_launch_accept.rs`), a freshly started
`LaunchHost` taking one production turn, as every L0 and cases turn is taken. No `generate*` call in (a).

One clock: `time.monotonic_ns` (the D1 driver's `CLOCK`). Durations are integer nanoseconds; a derived
duration is rounded up and a derived rate down, so no cost is understated. Exit codes (AGENTS.md section 12):
0 done, 2 validation failure, 3 missing prerequisite, 4 internal error, 5 a run secret would enter the log,
6 optimized Python. Stdlib only; TEST_ONLY material only (D1's P2WSH(OP_TRUE) outputs and oe's TEST_ONLY
fixtures).
"""
from __future__ import annotations

import argparse
import contextlib
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).absolute().parent))
import claude_track_ardr_driver as D  # noqa: E402

oe = D.oe
Refusal, invalid = D.Refusal, D.invalid
EXIT_DONE, EXIT_VALIDATION, EXIT_PREREQUISITE, EXIT_INTERNAL, EXIT_SECURITY, EXIT_REFUSAL = (
    D.EXIT_DONE, D.EXIT_VALIDATION, D.EXIT_PREREQUISITE, D.EXIT_INTERNAL, D.EXIT_SECURITY, D.EXIT_REFUSAL)
CLOCK = D.CLOCK

SCHEMA = 'BITAGI_CT_ARDR_THROUGHPUT_V1'
EVIDENCE_STATUS = 'EXPLORATORY'
LABELS = [*D.LABELS, 'EXPLORATORY', 'THROUGHPUT_MEASUREMENT_NOT_VERDICT']
H0 = oe.GATE
DEFAULT_BLOCKS, MAX_BLOCKS = 6100, 20000
DEFAULT_LAUNCHES, MAX_LAUNCHES = 5, 50
WITNESS_BLOCKS = 6100          # the assurance table's "about 6,100 blocks" per witness
PROJECTED_LAUNCHES = 200       # #258 6537782009 section 3: "about 200 L0 launches"
BUCKET_BLOCKS = 1000
NS_PER_HOUR = 3600 * 10**9
POLICY = 'ITEM2_DEFAULT'
IDLE_WORKER = 'launch_idle_worker'
IDLE_LINES = ['tip', 'decision', 'marked_final', 'persisted', 'ledger_rotated', 'ledger_events', 'turn_ms',
              'idle_stage']
BORN = 'Decided:Done:Born'
SPAWN_SAMPLES = 20
SPAWN_FILTER = 'launch_idle_worker_none'   # matches no test: the worker binary starts and runs nothing
# What was measured, as run (B's addition (1) on the D1t plan): A and B are oe's nodes, not D1's.
TOPOLOGY = {
    'miner': 'D1 RoleNode, Core 31.1; the miner process user whitelisted for exactly MINER_RPCS',
    'relay': 'D1 RoleNode, Core 31.1; connects to miner, A and B',
    'A': "oe.Pair Node, Core 31.1; oe's whitelists (driver user ALLOWED_RPCS, the public Class T fixture read "
         "user the launch host reads with, the send-only user), not D1's ROLE_RPCS",
    'B': "oe.Pair Node, Core 30.3; as A",
    'l0_chain': 'oe.run_l0 unchanged up to l0_broadcast, stopped at its first Pair.mine past H0 - 1: its '
                'chain to H0 - 2 and the floor block H0 - 1 by Pair.mine (generatetodescriptor on A)',
    'inclusion_and_measured_blocks': "D1 MinerProcess from the miner node's getblocktemplate; no generate*",
    'difference_from_d1': "A and B whitelist more users and methods than D1's exact sets, and the L0 chain is "
                          "generated, not template-built; whitelists are checked per RPC call and do not change "
                          "the work per call, so no material timing effect is expected; D3a-1 reconciles "
                          "run_l0 with D1's topology",
}
PARTS = ('node_startup', 'worker_host', 'worker_signer', 'chain', 'prestate', 'relay_wait', 'other')


# ---------------------------------------------------------------------------------------------------------
# Arithmetic (pure; unit-tested with fixed inputs).

def check_count(value, low: int, high: int, code: str) -> int:
    if type(value) is not int or not low <= value <= high:
        raise invalid(code)
    return value


def nearest_rank(values: list[int], percent: int) -> int:
    """The nearest-rank percentile: the value at 1-based rank ceil(percent / 100 * n) of the sorted values."""
    if not values or not 0 < percent <= 100:
        raise invalid('PERCENTILE_INPUT')
    ordered = sorted(values)
    rank = -(-percent * len(ordered) // 100)
    return ordered[rank - 1]


def mean(values: list[int]) -> Fraction:
    if not values:
        raise invalid('MEAN_INPUT')
    return Fraction(sum(values), len(values))


def ceil_int(value: Fraction) -> int:
    return -(-value.numerator // value.denominator)


def stats(values: list[int], unit: str = 'ns') -> dict:
    """count, sum, mean (rounded up to the unit), p50, p95, min and max of non-negative integers in `unit`
    (nanoseconds unless named: `ms` for the worker's own turn time, `events` for ledger events)."""
    if any(type(v) is not int or v < 0 for v in values):
        raise invalid('DURATION_VALUE')
    return {'count': len(values), f'sum_{unit}': sum(values), f'mean_{unit}': ceil_int(mean(values)),
            f'p50_{unit}': nearest_rank(values, 50), f'p95_{unit}': nearest_rank(values, 95),
            f'min_{unit}': min(values), f'max_{unit}': max(values)}


def milli_text(value: Fraction, up: bool) -> str:
    """A non-negative `value` to three decimals, rounded up or down exactly (integers only), as text."""
    if value < 0:
        raise invalid('NEGATIVE_VALUE')
    scaled = value * 1000
    q = ceil_int(scaled) if up else scaled.numerator // scaled.denominator
    return f'{q // 1000}.{q % 1000:03d}'


def seconds_up(ns: int | Fraction) -> str:
    return milli_text(Fraction(ns) / 10**9, True)


def hours_up(ns: int | Fraction) -> str:
    return milli_text(Fraction(ns) / NS_PER_HOUR, True)


def per_hour_down(count: int, span_ns: int) -> str:
    """`count` events over `span_ns` nanoseconds, per hour, rounded down."""
    if span_ns <= 0:
        raise invalid('SPAN_NOT_POSITIVE')
    return milli_text(Fraction(count * NS_PER_HOUR, span_ns), False)


def project(values: list[int], times: int) -> dict:
    """`times` repetitions at the measured mean and at the measured p95, rounded up."""
    at_mean = ceil_int(mean(values) * times)
    at_p95 = nearest_rank(values, 95) * times
    return {'times': times, 'at_mean_ns': at_mean, 'at_mean_hours': hours_up(at_mean), 'at_p95_ns': at_p95,
            'at_p95_hours': hours_up(at_p95)}


def buckets(heights: list[int], values: list[int], size: int = BUCKET_BLOCKS) -> list[dict]:
    """Mean per-block time over consecutive runs of `size` blocks (drift over the chain)."""
    out = []
    for start in range(0, len(values), size):
        chunk = values[start:start + size]
        out.append({'from_height': heights[start], 'to_height': heights[start + len(chunk) - 1],
                    'blocks': len(chunk), 'mean_ns': ceil_int(mean(chunk))})
    return out


# ---------------------------------------------------------------------------------------------------------
# Timed spans: one clock, attributed to the launch parts.

class Spans:
    """Nanoseconds per part on `clock`; `timed(part, fn)` wraps a callable so each call adds to `part`."""

    def __init__(self, clock=None):
        self.clock = clock or CLOCK
        self.ns = dict.fromkeys(PARTS, 0)
        self.calls = dict.fromkeys(PARTS, 0)

    def add(self, part: str, ns: int) -> None:
        if part not in self.ns or ns < 0:
            raise invalid('SPAN_PART')
        self.ns[part] += ns
        self.calls[part] += 1

    def timed(self, part, fn):
        """`part` is a name or a function of the call's arguments that gives one."""
        def wrapper(*args, **kwargs):
            start = self.clock()
            try:
                return fn(*args, **kwargs)
            finally:
                self.add(part(*args, **kwargs) if callable(part) else part, self.clock() - start)
        return wrapper


def worker_part(command, *_args, **_kwargs) -> str:
    """A worker process's part by its package: the launch host's or the signer's."""
    return 'worker_host' if oe.HOST_PACKAGE in command else 'worker_signer'


@contextlib.contextmanager
def patched(owner, name: str, replacement):
    original = getattr(owner, name)
    setattr(owner, name, replacement)
    try:
        yield
    finally:
        setattr(owner, name, original)


class L0Broadcast(Exception):
    """`oe.run_l0` asked for a block past the floor block after `l0_broadcast`: the launch's L0 part ends."""


def run_l0_to_broadcast(pair, *args) -> str:
    """`oe.run_l0` through `l0_broadcast` and its submission check; returns the broadcast txid.

    `oe.check_submitted` is the last L0 check after the broadcast; the next `pair.mine` (since 1e-2b-2a the
    H0 block of its own reorg phases) stops the run, since the launch's H0 block is D1's miner's."""
    seen = {}
    check, mine = oe.check_submitted, pair.mine

    def submitted(pair_, tip, funding, txid, *rest):
        check(pair_, tip, funding, txid, *rest)
        seen['txid'] = txid

    def stop_past_floor(*a, **k):
        if 'txid' in seen:
            raise L0Broadcast
        return mine(*a, **k)

    with patched(oe, 'check_submitted', submitted), patched(pair, 'mine', stop_past_floor):
        try:
            oe.run_l0(pair, *args)
        except L0Broadcast:
            pass
    if 'txid' not in seen:
        raise oe.Mismatch('L0_NOT_BROADCAST')
    return seen['txid']


def l0_then_inclusion(spans: Spans, l0, inclusion):
    """`l0()` with `oe.run_stage` and `oe.run_prestate` timed, then `inclusion(txid)` after those patches are
    gone: the inclusion turn goes through the unpatched `oe.run_stage` and is timed once, by `Run.inclusion`
    (pre-PR round 1 P2-1: inside the patch it was timed twice)."""
    with patched(oe, 'run_stage', spans.timed(worker_part, oe.run_stage)), \
            patched(oe, 'run_prestate', spans.timed('prestate', oe.run_prestate)):
        txid = l0()
    return inclusion(txid)


def stop_all(miner, topology) -> None:
    """Stops the miner process, then the nodes, even if the miner's stop raises (its error propagates)."""
    try:
        if miner is not None:
            miner.stop()
    finally:
        topology.stop()


def launch_parts(spans: Spans, total_ns: int) -> dict:
    """The parts of one launch; `other` is the remainder, which may not be negative."""
    measured = sum(spans.ns[p] for p in PARTS if p != 'other')
    if measured > total_ns:
        raise invalid('SPANS_EXCEED_TOTAL')
    return {**{f'{p}_ns': spans.ns[p] for p in PARTS if p != 'other'}, 'other_ns': total_ns - measured,
            'total_ns': total_ns, 'worker_processes': spans.calls['worker_host'] + spans.calls['worker_signer'],
            'chain_calls': spans.calls['chain']}


# ---------------------------------------------------------------------------------------------------------
# Topology: D1's miner and relay, oe's A and B (module docs).

class ThroughputTopology:
    def __init__(self, node_a: Path, node_b: Path, work: Path):
        self.send, self.admin = oe.RunUser(oe.SEND_USER), oe.RunUser(oe.ADMIN_USER)
        self.pair = oe.Pair(node_a, node_b, work / 'pair', self.send, self.admin)
        self.miner_user = oe.RunUser('bitagi-ardr-mine')
        self.users = {role: oe.RunUser(f'bitagi-ardr-{role}') for role in ('miner', 'relay')}
        self.miner = D.RoleNode('miner', node_a, work / 'miner', self.users['miner'], D.ROLE_RPCS['miner'],
                                miner_user=self.miner_user)
        self.relay = D.RoleNode('relay', node_a, work / 'relay', self.users['relay'], D.ROLE_RPCS['relay'])
        self.started: list = []

    def nodes(self) -> dict:
        return {'miner': self.miner, 'relay': self.relay, 'A': self.pair.a, 'B': self.pair.b}

    def needles(self) -> tuple[str, ...]:
        users = (self.send, self.admin, self.miner_user, *self.users.values())
        return tuple(n for user in users for n in user.needles())

    def ports(self) -> tuple[int, ...]:
        return tuple(p for node in self.nodes().values() for p in (node.rpcport, node.port))

    def start(self) -> dict:
        """Starts and connects the four nodes; returns each node's version and subversion."""
        self.started.append(self.pair)
        self.pair.start()
        for node in (self.miner, self.relay):
            self.started.append(node)
            node.start()
            node.cookie_refused()
        versions = {}
        for role, node in self.nodes().items():
            info = node.call('getnetworkinfo')
            versions[role] = {'version': info['version'], 'subversion': info['subversion']}
            if info['version'] != D.ROLE_VERSIONS[role]:
                raise oe.Prerequisite(f'NODE_VERSION {role}')
        for node in (self.miner, self.pair.a, self.pair.b):
            self.relay.call('addnode', f'127.0.0.1:{node.port}', 'onetry')
        try:
            oe.wait_for(lambda: self.relay.call('getconnectioncount') >= 3, 'the four nodes to connect')
        except oe.Prerequisite as error:
            if D.node_call_timeout(error):   # U4: a node call's own timeout keeps its code
                raise
            raise oe.Prerequisite('NODES_NOT_CONNECTED') from None
        return versions

    def stop(self) -> None:
        for node in reversed(self.started):
            node.stop()
        self.started = []


# ---------------------------------------------------------------------------------------------------------
# Blocks and turns.

def accept_block(nodes: dict, block: dict) -> None:
    if block['submit_result'] is not None:
        raise oe.Mismatch('SUBMITBLOCK_REFUSED')
    try:
        oe.wait_for(lambda: all(node.call('getbestblockhash') == block['block_hash'] for node in nodes.values()),
                    'all four nodes to accept the block', D.ACCEPT_SECONDS)
    except oe.Prerequisite as error:
        if D.node_call_timeout(error):   # U4: a node call's own timeout keeps its code
            raise
        raise oe.Mismatch('BLOCK_NOT_ACCEPTED') from None


def check_turn(got: dict, height: int) -> dict:
    """An idle turn's lines: the tip the driver mined, nothing raised, the stage PASS. Returns the typed values."""
    if got['idle_stage'] != 'PASS':
        raise oe.Mismatch('IDLE_STAGE')
    if not (got['tip'].isdigit() and int(got['tip']) == height):
        raise oe.Mismatch('TURN_TIP')
    if got['persisted'] != '0':
        raise oe.Mismatch('IDLE_RAISED')
    for key in ('marked_final', 'ledger_rotated'):
        if got[key] not in ('0', '1'):
            raise oe.Mismatch('TURN_LINE')
    for key in ('ledger_events', 'turn_ms'):
        if not got[key].isdigit():
            raise oe.Mismatch('TURN_LINE')
    return {'decision': got['decision'], 'marked_final': got['marked_final'] == '1',
            'ledger_rotated': got['ledger_rotated'] == '1', 'ledger_events': int(got['ledger_events']),
            'turn_ms': int(got['turn_ms'])}


class Run:
    """One measurement: its log, its clock and the four things that touch nodes or processes."""

    def __init__(self, log, nodes: dict, miner, turn, clock=None):
        self.log, self.nodes, self.miner, self.turn = log, nodes, miner, turn
        self.clock = clock or CLOCK

    def unit(self, launch: int | None = None) -> dict:
        return {'experiment': 'THROUGHPUT', 'run': launch, 'gate': None, 'cohort': None}

    def inclusion(self, txid: str, launch: int, spans: Spans) -> dict:
        """Block H0 from the template, holding `txid`, accepted by all four nodes; then one turn: `Done:Born`."""
        try:
            spans.timed('relay_wait', oe.wait_for)(lambda: txid in self.nodes['miner'].call('getrawmempool'),
                                                   'the launch tx at the miner')
        except oe.Prerequisite as error:
            if D.node_call_timeout(error):   # U4: a node call's own timeout keeps its code
                raise
            raise oe.Prerequisite('LAUNCH_TX_NOT_AT_MINER') from None
        start = self.clock()
        block = self.miner.build_block()
        if block['height'] != H0 or txid not in [item['txid'] for item in block['order']]:
            raise oe.Mismatch('INCLUSION_MISSING')
        accept_block(self.nodes, block)
        spans.add('chain', self.clock() - start)
        self.log.write('BLOCK', self.unit(launch), **{k: block[k] for k in (
            'height', 'block_hash', 'block_hex', 'coinbase_txid', 'order', 'submit_result')})
        got = check_turn(spans.timed('worker_host', self.turn)(H0), H0)
        if got['decision'] != BORN:
            raise oe.Mismatch('INCLUSION_NOT_BORN')
        self.log.write('TURN', self.unit(launch), height=H0, **got)
        return got

    def blocks(self, count: int) -> dict:
        """(a): `count` blocks above H0, each built, accepted by four nodes, then turned once.

        A block's time runs from the end of the previous block's log write to the end of its turn; the log
        write (`log_write`) is timed apart, so `span_ns` is the sum of the blocks' times (the breakdown) and
        `wall_ns` is `span_ns` plus the log writes. The rates and the witness projection are on the wall
        clock (each block with its log write, `per_block_wall`): what a run takes."""
        check_count(count, 1, MAX_BLOCKS, 'BLOCKS_RANGE')
        rows, writes = [], []
        decisions: dict[str, int] = {}
        marked = []
        t_start = self.clock()
        t0 = t_start
        for _ in range(count):
            block = self.miner.build_block()
            t1 = self.clock()
            accept_block(self.nodes, block)
            t2 = self.clock()
            height = block['height']
            got = check_turn(self.turn(height), height)
            t3 = self.clock()
            row = {'height': height, 'build_ns': t1 - t0, 'accept_ns': t2 - t1, 'turn_ns': t3 - t2,
                   'block_ns': t3 - t0, **got}
            self.log.write('BLOCK_TURN', self.unit(), t_ns=t3, block_hash=block['block_hash'],
                           block_hex=block['block_hex'], **row)
            rows.append(row)
            decisions[got['decision']] = decisions.get(got['decision'], 0) + 1
            if got['marked_final']:
                marked.append(height)
            t0 = self.clock()
            writes.append(t0 - t3)
        wall = t0 - t_start
        per_block = [r['block_ns'] for r in rows]
        per_block_wall = [ns + write for ns, write in zip(per_block, writes)]
        span = sum(per_block)
        return {
            'count': count, 'first_height': rows[0]['height'], 'last_height': rows[-1]['height'],
            'span_ns': span, 'span_hours': hours_up(span), 'wall_ns': wall, 'log_write': stats(writes),
            'blocks_per_hour': per_hour_down(count, wall), 'turns_per_hour': per_hour_down(count, wall),
            'per_block': stats(per_block), 'per_block_wall': stats(per_block_wall), 'build': stats([r['build_ns'] for r in rows]),
            'accept': stats([r['accept_ns'] for r in rows]), 'turn_process': stats([r['turn_ns'] for r in rows]),
            'turn_in_process': stats([r['turn_ms'] for r in rows], 'ms'),
            'ledger_events': stats([r['ledger_events'] for r in rows], 'events'),
            'decisions': dict(sorted(decisions.items())), 'marked_final_heights': marked,
            'ledger_rotated_heights': [r['height'] for r in rows if r['ledger_rotated']],
            'buckets': buckets([r['height'] for r in rows], per_block),
            'witness_projection': {'blocks': WITNESS_BLOCKS, 'extrapolated': count < WITNESS_BLOCKS,
                                   **project(per_block_wall, WITNESS_BLOCKS)},
        }


def launch_summary(launches: list[dict]) -> dict:
    """(b) over the launches: per part the statistics, the 200-launch projection, and its split by part."""
    totals = [launch['total_ns'] for launch in launches]
    split = {p: ceil_int(mean([launch[f'{p}_ns'] for launch in launches]) * PROJECTED_LAUNCHES) for p in PARTS}
    return {
        'count': len(launches),
        'stats': {p: stats([launch[f'{p}_ns'] for launch in launches]) for p in (*PARTS, 'total')},
        'projection': {**project(totals, PROJECTED_LAUNCHES),
                       'split_at_mean_ns': split,
                       'split_at_mean_hours': {p: hours_up(ns) for p, ns in split.items()}},
    }


def witness_estimate(blocks: dict, launches: dict) -> dict:
    """One witness: one L0 launch (its mean) and `WITNESS_BLOCKS` block turns (their mean), rounded up."""
    ns = launches['stats']['total']['mean_ns'] + blocks['witness_projection']['at_mean_ns']
    return {'launch_mean_ns': launches['stats']['total']['mean_ns'],
            'blocks_ns': blocks['witness_projection']['at_mean_ns'], 'total_ns': ns, 'total_hours': hours_up(ns)}


def log_header() -> dict:
    """What every raw-log line carries (D1's header keys): EXPLORATORY, no policy, the labels."""
    return {'mode': 'EXPLORATORY', 'evidence_status': EVIDENCE_STATUS, 'policy_sha256': None,
            'registration_sha256': None, 'labels': LABELS}


def spawn_summary(samples: list[int], blocks: dict) -> dict:
    """An empty worker invocation (cargo and the test binary start, no test runs) against the turn process
    (B's addition (2)): how much of a turn is process start, not host work."""
    spawn = stats(samples)
    return {'samples': spawn, 'turn_process_mean_ns': blocks['turn_process']['mean_ns'],
            'turn_minus_spawn_mean_ns': blocks['turn_process']['mean_ns'] - spawn['mean_ns']}


def result_document(env: dict, blocks_asked: int, build: dict, launches: list[dict], blocks: dict,
                    spawn: list[int]) -> dict:
    """The result file's object (format doc section 2) without `raw_log_sha256`."""
    if blocks is None or blocks['count'] != blocks_asked or not launches or len(spawn) != SPAWN_SAMPLES:
        raise invalid('RESULT_INCOMPLETE')
    launch_stats = launch_summary(launches)
    return {
        'schema': SCHEMA, 'evidence_status': EVIDENCE_STATUS, 'labels': LABELS, 'environment': env,
        'topology': TOPOLOGY,
        'parameters': {'blocks': blocks_asked, 'launches': len(launches), 'h0': H0,
                       'witness_blocks': WITNESS_BLOCKS, 'projected_launches': PROJECTED_LAUNCHES,
                       'miner_policy': POLICY},
        'build': build, 'launches': launches, 'launch_summary': launch_stats, 'blocks': blocks,
        'witness_estimate': witness_estimate(blocks, launch_stats), 'spawn': spawn_summary(spawn, blocks),
    }


# ---------------------------------------------------------------------------------------------------------
# The real run.

def environment(versions: dict) -> dict:
    try:
        affinity = len(os.sched_getaffinity(0))
    except (AttributeError, OSError):
        affinity = None
    return {'cpu_count': os.cpu_count(), 'cpu_affinity': affinity, 'python': platform.python_version(),
            'machine': platform.machine(), 'system': platform.system(), 'core': versions,
            'host': 'LOCAL', 'clock': 'time.monotonic_ns'}


def build_commands(cargo: str) -> list[tuple[str, list[str], bool]]:
    """The workers' builds, as `oe.worker_command` runs them, with `--no-run`: (name, command, offline)."""
    def no_run(command: list[str]) -> list[str]:
        return [*command[:command.index('--')], '--no-run']
    return [
        ('online', no_run(oe.worker_command(cargo, oe.HOST_TEST, IDLE_WORKER, [], oe.HOST_PACKAGE)), False),
        ('offline', no_run(oe.worker_command(cargo, oe.LAUNCH_SIGNER_TEST, oe.CHARGE_WORKER,
                                             ['--features', 'offline-ceremony'], oe.SIGNER_PACKAGE)), True),
    ]


def spawn_command(cargo: str) -> list[str]:
    """The idle worker's invocation with a filter that matches no test."""
    command = oe.worker_command(cargo, oe.HOST_TEST, IDLE_WORKER, [], oe.HOST_PACKAGE)
    command[command.index(IDLE_WORKER)] = SPAWN_FILTER
    return command


def spawn_samples(cargo: str, env: dict, count: int = SPAWN_SAMPLES, clock=None) -> list[int]:
    clock = clock or CLOCK
    samples = []
    for _ in range(count):
        start = clock()
        done = subprocess.run(spawn_command(cargo), env=env, cwd=oe.ROOT, capture_output=True, check=False)
        samples.append(clock() - start)
        if done.returncode != 0 or b'running 0 tests' not in done.stdout:
            raise Refusal('SPAWN_FAILED', EXIT_PREREQUISITE)
    return samples


def envs(offline_target: Path, online_target: Path) -> tuple[dict, dict]:
    """The offline and online builds' environments without stage values, as `oe.run` makes them."""
    if 'RUSTFLAGS' in os.environ:
        raise Refusal('RUSTFLAGS_SET', EXIT_PREREQUISITE)
    base = {k: v for k, v in os.environ.items() if k != oe.OFFLINE_FLAGS_VARIABLE}
    base['CARGO_INCREMENTAL'] = '0'
    offline = {**base, 'RUSTFLAGS': oe.OFFLINE_RUSTFLAGS, 'CARGO_TARGET_DIR': str(offline_target)}
    online = {**base, 'CARGO_TARGET_DIR': str(online_target)}
    return offline, online


def measure_launch(index: int, topology, launch_dir: Path, cargo: str, offline_env: dict, online_env: dict,
                   log, blocks_count: int | None = None, clock=None):
    """(b) one launch on `topology`'s fresh nodes, then, if `blocks_count`, (a) on its deployment; the miner
    process and the nodes are stopped after, even on failure. Returns (its `Run`, its launch record, the
    blocks or None, the nodes' versions). `run()`'s per-launch body, moved here unchanged (the same calls in
    the same order) so the stubs drive `run()`'s own wiring of `l0_then_inclusion` (delta review P3-a)."""
    clock = clock or CLOCK
    spans = Spans(clock)
    miner = None
    try:
        start = clock()
        versions = spans.timed('node_startup', topology.start)()
        miner = D.MinerProcess(topology.miner, POLICY)
        secrets_ = oe.run_secrets(launch_dir, (topology.pair,), topology.send, topology.admin)
        secrets_ = oe.Secrets(secrets_.needles + topology.needles(), secrets_.ports + topology.ports())
        pair = topology.pair
        pair.mine = spans.timed('chain', pair.mine)
        launch = launch_dir / 'l0' / 'launch'
        turn_env = {**online_env, 'BITAGI_E3D3_NODE_A_PORT': str(pair.a.rpcport),
                    'BITAGI_E3D3_NODE_B_PORT': str(pair.b.rpcport),
                    'BITAGI_E3D3_NODE_A_LOG': pair.a.log_path, 'BITAGI_E3D3_NODE_B_LOG': pair.b.log_path,
                    'BITAGI_E3D3_LAUNCH': str(launch.resolve())}

        def turn(_height, env=turn_env, secrets_=secrets_):
            command = oe.worker_command(cargo, oe.HOST_TEST, IDLE_WORKER, [], oe.HOST_PACKAGE)
            return oe.run_stage(command, env, IDLE_WORKER, IDLE_LINES, secrets_=secrets_)

        measured = Run(log, topology.nodes(), miner, turn, clock)
        l0_then_inclusion(   # both called here, in this iteration
            spans,
            lambda: run_l0_to_broadcast(pair, launch_dir, cargo, offline_env, online_env, topology.send, secrets_),
            lambda txid: measured.inclusion(txid, index, spans))
        total = clock() - start
        parts = launch_parts(spans, total)
        record = {'index': index, **parts}
        log.write('LAUNCH', measured.unit(index), **parts)
        blocks = measured.blocks(blocks_count) if blocks_count is not None else None
    finally:
        stop_all(miner, topology)
    return measured, record, blocks, versions


def run(args) -> dict:
    check_count(args.blocks, 1, MAX_BLOCKS, 'BLOCKS_RANGE')
    check_count(args.launches, 1, MAX_LAUNCHES, 'LAUNCHES_RANGE')
    for path in (args.out, args.log, args.work):
        if path.exists():
            raise Refusal('OUTPUT_EXISTS', EXIT_PREREQUISITE)
    offline_env, online_env = envs(args.offline_target, args.online_target)
    oe.check_ancestors(args.work)
    work = oe.private(args.work)
    build = {}
    for name, command, offline in build_commands(args.cargo):
        start = CLOCK()
        done = subprocess.run(command, env=offline_env if offline else online_env, cwd=oe.ROOT,
                              capture_output=True, check=False)
        build[f'{name}_ns'] = CLOCK() - start
        if done.returncode != 0:
            raise Refusal(f'BUILD_FAILED {name.upper()}', EXIT_PREREQUISITE)
    topologies = [ThroughputTopology(args.node_a, args.node_b, work / f'launch-{i}') for i in range(args.launches)]
    needles = tuple(n for t in topologies for n in t.needles()) + (str(work), str(work.resolve()))
    log = D.RawLog(args.log, log_header(), needles)
    launches, blocks, versions = [], None, {}
    try:
        log.write('RUN_START', {'experiment': 'THROUGHPUT', 'run': None, 'gate': None, 'cohort': None},
                  blocks=args.blocks, launches=args.launches, build=build)
        for index, topology in enumerate(topologies):
            last = index == len(topologies) - 1
            measured, record, got, versions = measure_launch(
                index, topology, work / f'launch-{index}', args.cargo, offline_env, online_env, log,
                args.blocks if last else None)
            launches.append(record)
            if last:
                blocks = got
        spawn = spawn_samples(args.cargo, online_env)
        log.write('SPAWN', measured.unit(), samples_ns=spawn)
        result = result_document(environment(versions), args.blocks, build, launches, blocks, spawn)
        log.write('RUN_END', measured.unit(), status='DONE')
    finally:
        log.close()
    result['raw_log_sha256'] = hashlib.sha256(args.log.read_bytes()).hexdigest()
    text = json.dumps(result, sort_keys=True, indent=1) + '\n'
    # Both forms: `text` is json.dumps output, so a needle with a backslash, a double quote or a non-ASCII
    # character appears there escaped (as #617 does in the driver's RawLog and in oe.scan_secrets).
    if any(n and (n in text or json.dumps(n)[1:-1] in text) for n in needles):
        raise Refusal('SECRET_IN_RESULT', EXIT_SECURITY)
    with args.out.open('x', encoding='ascii', newline='') as stream:
        stream.write(text)
    return {'out_sha256': hashlib.sha256(text.encode('ascii')).hexdigest(),
            'blocks_per_hour': blocks['blocks_per_hour'],
            'witness_hours': result['witness_estimate']['total_hours'],
            'l0_200_hours': result['launch_summary']['projection']['at_mean_hours']}


def bounded(low: int, high: int):
    def parse(text: str) -> int:
        try:
            value = int(text, 10)
        except ValueError:
            raise argparse.ArgumentTypeError('an integer') from None
        if not low <= value <= high:
            raise argparse.ArgumentTypeError(f'from {low} to {high}')
        return value
    return parse


def parser() -> argparse.ArgumentParser:
    top = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = top.add_subparsers(dest='command', required=True)
    m = sub.add_parser('measure')
    m.add_argument('--node-a', required=True, type=Path, help='Core 31.1 bin dir (miner, relay, Node A)')
    m.add_argument('--node-b', required=True, type=Path, help='Core 30.3 bin dir (Node B)')
    m.add_argument('--work', required=True, type=Path, help='new directory for the nodes and launches')
    m.add_argument('--out', required=True, type=Path, help='new result file')
    m.add_argument('--log', required=True, type=Path, help='new raw-log file')
    m.add_argument('--blocks', type=bounded(1, MAX_BLOCKS), default=DEFAULT_BLOCKS)
    m.add_argument('--launches', type=bounded(1, MAX_LAUNCHES), default=DEFAULT_LAUNCHES)
    m.add_argument('--cargo', default='cargo')
    m.add_argument('--offline-target', type=Path, default=oe.ROOT / 'target/offline-build')
    m.add_argument('--online-target', type=Path, default=oe.ROOT / 'target')
    return top


def main(argv: list[str] | None = None) -> int:
    if not __debug__:
        print(json.dumps({'result': 'FAIL', 'code': 'OPTIMIZED_PYTHON', 'exit': EXIT_REFUSAL}))
        return EXIT_REFUSAL
    args = parser().parse_args(argv)
    for name in ('node_a', 'node_b', 'work', 'out', 'log', 'offline_target', 'online_target'):
        setattr(args, name, getattr(args, name).absolute())
    try:
        try:
            summary = run(args)
        except Refusal:
            raise
        except oe.Prerequisite as error:   # the message can hold a node's stderr or a path: codes only
            raise Refusal(D.error_code('PREREQUISITE', error), EXIT_PREREQUISITE) from None
        except oe.Mismatch as error:
            raise Refusal(D.error_code('MISMATCH', error), EXIT_VALIDATION) from None
    except Refusal as refusal:
        print(json.dumps({'result': 'FAIL', 'code': refusal.code, 'exit': refusal.exit_code}, sort_keys=True))
        return refusal.exit_code
    print(json.dumps({'result': 'DONE', **summary, 'exit': EXIT_DONE}, sort_keys=True))
    return EXIT_DONE


if __name__ == '__main__':
    import claude_track_exit
    claude_track_exit.run(main)
