#!/usr/bin/env python3
"""CT-P5-001 D3a-1a / D3a-1b: the L0 project bidder in one of item 2's PUBLIC seats, its whole replacement ladder.

Class T Regtest development evidence only; never mainnet, never S17-PREP, and no ARDR verdict. Sources: B's
D3a draft #258 issuecomment-6550996612, A's answer -6551547851 (Q1: the product's own ladder and budget, the
driver only runs the host turns at the 045b times and never sets L0's fee, the L0 seat draws no `BID_FEE`;
Q2: H0 = 1000; Q7: an L0 exclusion counts like any other, reported per seat), B's D3a-0 result -6551963734 (the
R2 conflict set on real nodes) and A's answer -6552107427 (Q-L1: this tool sets f_k as the operator by 045b
:537; Q-L2: p_0 = ceil(2.5 b); Q-L3: 24 attempts; Q-L4: the exposure is the whole set from the start), the 045b
draft :536-538, frozen as amended at :1053-1054 and :1901 (p_0's rule `CEIL_2_5_B`, 24 attempts, H0 1000). Format: `docs/claude-track/formats/ARDR_RUN_V1.md`
section 22. The unit notes are `docs/claude-track/plans/notes/CT-P5-001_DRIVER_EN/2026-11-01_d3a-1a-l0-seat.md`
and `…/2026-11-01_d3a-1b-l0-ladder.md`. Also frozen: the budget record (:1898). The DEFAULT limits are not; `BUDGET_DRAFT`, `DRAFT_TEST_ONLY` are names only.

`item2_l0_run` runs one item-2 run (`claude_track_ardr_item2.item2_run`) with the L0 seat on this topology;
`run` (the DRAFT CLI, below) runs it from a policy:

- Node A (31.1) and Node B (30.3) are `oe.Pair` nodes (`L0Node`, a subclass: oe's own users, so the launch
  host reads them with oe's public Class T fixture read user and step 8 submits with oe's send user), plus
  one more user, `READ_USER`, whitelisted for exactly item 2's reads on A and B (`READ_RPCS`:
  `getrawmempool`, `testmempoolaccept`), and the loopback noban P2P whitelist item 2 needs. Both come
  through oe.Node's existing extra-argv hook (`miner_lines`), so oe's driver user keeps `ALLOWED_RPCS` and
  no byte of oe changes. The miner and the relay are D1 `RoleNode`s (item 2's).
- The chain: block 1 is mined to oe's `FUNDING_DESCRIPTOR` (`Pair.mine`, L0's funding coinbase that
  `oe.chain_facts` reads at height 1); item 2's setup then runs from height 2 with D1's miner process up to
  H0 − 2.
- The set (D3a-1b; 045a §1.3, R2): this tool, as L0's operator, fixes L0's conflict set before anything is
  charged: the bidders' own `ladder(p_0, b, i, v)` (`item2.l0_ladder`, 045b :537, with its 4b cap and rung 7),
  p_0 = L0's (FD-CT-133), i the larger of Node A's and Node B's `incrementalfee` (read every run), v item 2's
  campaign vsize (213 vB); `item2.check_l0_set` refuses a set the wallet would refuse. The ARDR driver never
  changes a fee.
- `L0Seat` runs, in its own thread, the set workers' stages in the order of `oe.l0_chain` (`MIRRORS`; oe and
  `oe.run_l0` are not called and not patched), with oe's checks between them in their per-txid form
  (`CHECKS_MIRRORED`) except the ones `DEVIATIONS` names (WRD3a1b P3-4): describe; the set charge (every rung reserved and charged
  before rung 0 is signed, 045a item 7); every rung signed at H0 − 2 (the host signs only at its base's tip,
  and the charge writes every base for H0 − 2), rung 0 imported there; after item 2's G − 1, rung 0's step 8;
  then for each rung k ≥ 1 released at all, its import and turns to the broadcast authority right after rung
  k − 1's release, and its step 8 at t0 + rung_seconds × k (to Node A and Node B only). The set's fees and
  `r_inc` reach the signer stages as launch-facts lines (`l0_set_fees`, `l0_set_rinc`, then the budget's
  `l0_set_exact_height_miss` (D3a-2b-1) and `l0_sign_entry`, after D3a-1a's `l0_fee_sat` and `l0_budget`);
  the stages still read one environment value, the facts path.
  Each worker stage is bounded by the time left of the attempt's budget (READY + FLOOR + FINISH), so no
  worker stage outlives `stop`'s wait. Not bounded by that deadline (as D3a-1a): oe's prestate subprocess
  (`PRESTATE_SECONDS`, 300 s), each node call (300 s) and `Pair.agreed`'s wait, so one of them hung near the
  deadline can outlive `stop`'s grace. That is contained: `stop` raises `L0_THREAD_ALIVE`, and the thread
  blocks every later L0 launch in the process (`L0_PREVIOUS_THREAD_ALIVE`) until it has ended (it patches
  nothing, so only its own stage process and node calls are still running).
- What L0 sent is read from the product (the stages' txids, bytes' SHA-256 and candidate ids; step 8's
  `hand_offs` 1 and bytes; the wallet rows' fee and vsize; `budget.json`; the wallet's counters; the host's
  labels after G) and from the nodes (each node's `getmempoolentry` fee and vsize). A computed fee that
  differs from the wallet row's or the charge base's on any rung of the set (released or not, checked right
  after the charge), or from the nodes' on any released rung, fails the run (`L0_FEE_MISMATCH`).

Exit codes as D1's (AGENTS.md section 12). Stdlib only. TEST_ONLY material only (oe's TEST_ONLY fixtures and
D1's P2WSH(OP_TRUE) outputs).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
import time

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).absolute().parent))
import claude_track_ardr_bidders as B  # noqa: E402
import claude_track_ardr_driver as D  # noqa: E402
import claude_track_ardr_item2 as I2  # noqa: E402
import claude_track_ardr_throughput as T  # noqa: E402

oe = D.oe
Refusal, invalid = D.Refusal, D.invalid
CLOCK = D.CLOCK

READ_USER = 'bitagi-ardr-l0-read'
READ_RPCS = frozenset({'getrawmempool', 'testmempoolaccept'})   # item 2's reads on A and B (item2:516, :549, :560)
H0 = I2.L0_H0
READY_SECONDS = 900.0    # DEFAULT: L0's turns to H0 − 2 (charge, sign, offline sign, wait), then it asks for G − 1
FLOOR_SECONDS = 900.0    # DEFAULT: how long L0 waits for item 2's G − 1
FINISH_SECONDS = 900.0   # DEFAULT: L0's H0 − 1 turns (pending, prestate, step 8) after G − 1
STOP_GRACE_SECONDS = 30.0   # DEFAULT: `stop`'s wait past the attempt's deadline (a stage's process ending)
# WRD3a1a P2-1: L0 threads that outlived `stop` (each still runs its own stage process or node call; the seat
# patches nothing, WRD3a1b P3-5); `L0Seat.start` refuses while any of them is alive.
_ALIVE: list[threading.Thread] = []
_ALIVE_LOCK = threading.Lock()
# The L0 budget record of the 045b 4.5 fee row, Class T TEST_ONLY. B-FZ-p (A #258 issuecomment-6743375133,
# -6744276619): A's frozen Class T L0 record, `docs/claude-track/preregistration/CAMPAIGN_BUDGET_V1_CLASS_T_REGTEST_L0.json`
# on #664 (SHA-256 7d0a7a35..; PRODUCT_BUDGET_SHA256 below); these are four of its fields, read for the log
# (max_fee_per_candidate_sat 30,000, was the Q1 draft's 100,000; max_fee_exposure_sat 500,000;
# max_principal_exposure_sat 240,000; max_gate_attempts 24). The record is accepted by its whole digest.
# The charge worker writes it into the product's budget.json (launch facts `l0_budget=`; v2_writer's FROZEN_L0_BUDGET).
# The name BUDGET_DRAFT stays (the L0_LAUNCH_START `budget_source` value); `status` is a logged label (FZ-6: A's record has none).
BUDGET_DRAFT = {'status': 'FROZEN_TEST_ONLY', 'max_fee_per_candidate_sat': 30_000, 'max_fee_exposure_sat': 500_000,
                'max_principal_exposure_sat': 240_000, 'max_gate_attempts': 24,
                'fee_row_threshold_sat_per_attempt': '500000/24'}
BUDGET_FIELDS = ('max_gate_attempts', 'max_fee_per_candidate_sat', 'max_fee_exposure_sat', 'max_principal_exposure_sat')
SENT_BY = I2.L0_SENT_BY
L0_BUDGET_LINE = 'DRAFT_TEST_ONLY'   # launch facts `l0_budget=` (crates/bitagi-signer/tests/launch_host_e2e_sign.rs L0_LINES)
V = B.CANDIDATE_VSIZE   # item 2's campaign vsize (045b 4.6 v), known before the candidate is fixed
P0_RULE = 'largest p_0 >= 2b with a two-rung :537 ladder (FD-CT-133, #807; policy p0_rule MAX_P0_TWO_RUNGS)'   # a logged label
FEE_RULE = "045b :537 rung fee: the bidders' ladder (A -6552107427 Q-L1)"
l0_p0 = I2.l0_p0             # FD-CT-133: one source, item 2's (the bidders' `l0_p0`; two rungs, the last at the cap)
l0_ladder = I2.l0_ladder     # the bidders' `ladder(p_0, b, i, v)` (WRD3a1a P3-7: one source, with its cap)


def attempt_id(observation: str, attempt: int) -> str:
    """The run's L0 attempt id (045b 4.5 counts per PROJECT attempt): `L0ATT-<observation id>-<attempt:02d>`,
    attempts counted from 1 (one per run: the whole set is one attempt, A -6552107427 Q-L4)."""
    if not (type(attempt) is int and 1 <= attempt <= 99):
        raise invalid('L0_ATTEMPT')
    return f'L0ATT-{observation}-{attempt:02d}'


# ---------------------------------------------------------------------------------------------------------
# Topology: oe's A and B with item 2's reads, D1's miner and relay (module docs).

class L0Node(oe.Node):
    """oe.Node with one more user (`READ_USER`, exactly `READ_RPCS`) and the loopback noban whitelist, both
    after oe's own argv through `miner_lines` (oe's lines first, unchanged). Calls of `READ_RPCS` go through
    that user; every other call through oe's driver user (`ALLOWED_RPCS`, oe's refusal kept)."""

    def __init__(self, label: str, bindir: Path, datadir: Path, rpcport: int, send: oe.RunUser,
                 admin: oe.RunUser, read: oe.RunUser, port: int | None = None):
        super().__init__(label, bindir, datadir, rpcport, send, admin, port=port)
        self.read = read

    def miner_lines(self) -> list[str]:
        return [*super().miner_lines(), '-rpcauth=' + self.read.line(),
                f'-rpcwhitelist={self.read.user}:' + ','.join(sorted(READ_RPCS)), D.P2P_WHITELIST]

    def p2p_arguments(self) -> list[str]:
        """The P2P whitelist arguments the node is really started with (item 2's topology check reads them)."""
        return [a for a in self.miner_lines() if a.startswith('-whitelist=')]

    def read_raw(self, *args: str):
        method = oe.rpc_method(args)
        if method not in READ_RPCS:
            raise oe.Mismatch(f'RPC_NOT_ALLOWED {method}')
        try:
            return subprocess.run(
                [str(self.cli), '-regtest', f'-datadir={self.datadir}', f'-rpcport={self.rpcport}',
                 f'-rpcuser={self.read.user}', '-stdinrpcpass', *args],
                input=self.read.password + '\n', capture_output=True, text=True, timeout=300, check=False)
        except subprocess.TimeoutExpired:
            raise node_call_timeout(self.label) from None

    def call(self, *args: str):
        """WRD3a1a P3-3: a call past its 300 s limit is U4's `NODE_CALL_TIMEOUT A` / `B` (exit 3), whichever
        user it goes through; oe.Node's own path (`raw`, `call`) is unchanged."""
        method = oe.rpc_method(args)
        if method not in READ_RPCS:
            try:
                return super().call(*args)
            except subprocess.TimeoutExpired:
                raise node_call_timeout(self.label) from None
        done = self.read_raw(*args)
        if done.returncode != 0:
            raise oe.Prerequisite(f'RPC_FAILED {self.label} {method} {done.stderr.strip()[:200]}')
        return oe.cli_result(args, done.stdout.strip())

    def rpc(self, method: str, *params):
        """D1's `RoleNode.rpc` shape (JSON-typed parameters), which item 2 uses for testmempoolaccept."""
        return self.call(method, *[p if isinstance(p, str) else json.dumps(p) for p in params])


def node_call_timeout(label: str) -> oe.Prerequisite:
    """U4's code for a node call past its limit (section 21), for Node A or Node B: code words only (the
    TimeoutExpired text holds the command line)."""
    return oe.Prerequisite(f'NODE_CALL_TIMEOUT {label}')


class L0Pair(oe.Pair):
    """oe.Pair whose two nodes are `L0Node`s (oe.Pair's other methods unchanged)."""

    def __init__(self, node_a: Path, node_b: Path, work: Path, send: oe.RunUser, admin: oe.RunUser,
                 read: oe.RunUser, ports: list[int] | None = None):
        ports = ports or oe.draw_ports(4)   # #682: (RPC, P2P) for A, then for B
        self.a = L0Node('A', node_a, work / 'a', ports[0], send, admin, read, port=ports[1])
        self.b = L0Node('B', node_b, work / 'b', ports[2], send, admin, read, port=ports[3])


class L0Topology:
    """Item 2's four roles: D1's miner and relay (`RoleNode`, 31.1, noban), oe's A (31.1) and B (30.3) as
    `L0Node`s. The relay connects to the miner; A and B to the relay (and B to A, oe.Pair's link)."""

    def __init__(self, node_a: Path, node_b: Path, work: Path, reorg: bool = False):
        self.send, self.admin = oe.RunUser(oe.SEND_USER), oe.RunUser(oe.ADMIN_USER)
        self.read = oe.RunUser(READ_USER)
        ports = oe.draw_ports(8)   # #682: all four nodes' ports in one draw, distinct
        self.pair = L0Pair(node_a, node_b, work / 'pair', self.send, self.admin, self.read, ports[:4])
        self.miner_user = oe.RunUser('bitagi-ardr-mine')
        self.users = {role: oe.RunUser(f'bitagi-ardr-{role}') for role in ('miner', 'relay')}
        self.nodes = {
            'miner': D.RoleNode('miner', node_a, work / 'miner', self.users['miner'],
                                D.ROLE_RPCS['miner'] | (D.REORG_RPCS if reorg else frozenset()),
                                rpcport=ports[4], port=ports[5], miner_user=self.miner_user, p2p_whitelist=True),
            'relay': D.RoleNode('relay', node_a, work / 'relay', self.users['relay'], D.ROLE_RPCS['relay'],
                                rpcport=ports[6], port=ports[7], p2p_whitelist=True),
            'A': self.pair.a, 'B': self.pair.b}
        self.started: list = []

    def needles(self) -> tuple[str, ...]:
        users = (self.send, self.admin, self.read, self.miner_user, *self.users.values())
        return tuple(n for user in users for n in user.needles())

    def ports(self) -> tuple[int, ...]:
        return tuple(p for node in self.nodes.values() for p in (node.rpcport, node.port))

    def start(self) -> None:
        self.started.append(self.pair)
        self.pair.start()
        for role in ('miner', 'relay'):
            self.started.append(self.nodes[role])
            self.nodes[role].start()
            self.nodes[role].cookie_refused()
        for role, node in self.nodes.items():
            version = node.call('getnetworkinfo')['version']
            if version != D.ROLE_VERSIONS[role]:
                raise oe.Prerequisite(f'NODE_VERSION {role.upper()} {version} expected {D.ROLE_VERSIONS[role]}')
        relay = self.nodes['relay']
        relay.call('addnode', f'127.0.0.1:{self.nodes["miner"].port}', 'onetry')
        for role in ('A', 'B'):
            self.nodes[role].call('addnode', f'127.0.0.1:{relay.port}', 'onetry')
        try:
            oe.wait_for(lambda: relay.call('getconnectioncount') >= 3, 'the four nodes to connect')
        except oe.Prerequisite:
            raise oe.Prerequisite('NODES_NOT_CONNECTED') from None

    def stop(self) -> None:
        for node in reversed(self.started):
            node.stop()
        self.started = []


# ---------------------------------------------------------------------------------------------------------
# The L0 seat.

# The R2 set workers (crates/bitagi-signer/tests/launch_host_e2e_sign.rs and
# crates/bitagi-launch-host/tests/two_node_launch_accept.rs, their D3a-1b sections).
SET_CHARGE_WORKER = 'launch_set_charge_stage_worker'
SET_CHARGE_LINES = ['set_id', 'budget_sha256', 'rungs', 'set_charge_stage']
NAMED_SIGN_WORKER = 'launch_named_sign_stage_worker'
NAMED_SIGN_LINES = ['candidate_id', 'raw_tx_sha256', 'txid', 'export_sha256', 'raw_tx_hex', 'named_sign_stage']
# D3a-2b-1 (A #258 issuecomment-6557723699, the L0 budget decision): the draft budget record's `exact_height_miss`
# for the L0 seat in item 2 and item 4 is 045b :103's draft value; the facts line `l0_set_exact_height_miss`
# carries it to the set charge (signer test `SET_LINES`), which writes it into `budget.json`. B-FZ-p (fix round 1):
# the record is now A's frozen Class T L0 record, which carries the same CONTINUE_WITHIN_LIMITS.
EXACT_HEIGHT_MISS = 'CONTINUE_WITHIN_LIMITS'
EXACT_HEIGHT_MISS_VALUES = ('STOP_CAMPAIGN', 'CONTINUE_WITHIN_LIMITS')
# B-FZ-a FZ-2 (045b F3 command, A #258 issuecomment-6738933506): the SHA-256 of the `budget.json` the product's
# set charge writes, per `exact_height_miss`. Since B-FZ-p the product writes A's frozen Class T L0 record
# (CONTINUE_WITHIN_LIMITS: the file's bytes, 7d0a7a35..; STOP_CAMPAIGN: its one `exact_height_miss` edit,
# 9ea208bd.., EXPLORATORY only, not approved); before B-FZ-p it was the Q1 draft fixture (572ed789.., 3a1050ad..). `confirmatory_l0_seat`
# refuses a policy `budget_sha256` that is not this record's before any node (L0_POLICY_BUDGET_NOT_PRODUCT);
# `L0Seat._budget` still compares the record the charge wrote (L0_POLICY_BUDGET_SHA256). Provenance (FZ-6 F4):
# CONTINUE_WITHIN_LIMITS was observed on real nodes in hosted job 129356708955 (run 42675802567, head a6b01234);
# STOP_CAMPAIGN is derived (the one-field twin), not observed on real nodes. A product change to the record changes
# these; the real-node rows then fail on `L0_BUDGET` (`policy_compare`) until the table follows.
PRODUCT_BUDGET_SHA256 = {
    'STOP_CAMPAIGN': '9ea208bd6e9bc19ab60b07469497887e6b4ce9aa270efb752247b1d3b13a26d0',
    'CONTINUE_WITHIN_LIMITS': '7d0a7a35ffa4df11311955d11e00b8c9c0f0f7df5c6e84c222911d447c7f4dd4',
}
SET_WORKER = 'launch_set_worker'
SET_WORKER_LINES = ['phase', 'rung', 'rungs', 'done', 'prestate_receipt', 'turns', 'turn_log', 'labels', 'flags',
                    'reorg', 'released', 'admitted', 'submitted', 'hand_offs', 'raw_tx_sha256', 'budget_counters', 'ms',
                    'set_stage']
# D3a-2b-1: `flags` (each rung's `opening_block_missed` and `reorged_before_inclusion`, as the core's report set
# them) is read by item 4 (`claude_track_ardr_item4.parse_flags`); item 2's `observe` does not judge it.
SET_PHASES = ('set_sign', 'set_wait', 'set_ready', 'set_send', 'set_broadcast', 'set_observe', 'set_reorged',
              'set_release')
# D3a-2b-2a (item 4's ITEM4_REORG with the L0 seat; A #258 issuecomment-6557723699 Q4): `reorg` (the reorg the
# turn's hook raised or acknowledged, host `set_reorg`) and `released` (the lock a procedure file released) on
# every phase, `-` when none. `set_reorged` is one turn after the reorg (the hook raises Reorg67; the host keeps
# the operator's copy); `set_release` is the phase `RELEASE_REORG67_TEST_ONLY` runs: one turn presenting the TDS
# 6.7 procedure file made from that copy, whose digest is the TEST_ONLY release record's, step 6 not performed.
# Condition (가): Class T Regtest only, never a product path. The mark travels in a file, not an environment
# value (the stages read one input, the facts path): this tool writes `host/release-record.txt`, exactly
# `RELEASE_RECORD_TEST_ONLY` (host `SET_RELEASE_RECORD`, a cell pins the bytes), only after its own checks; the
# host refuses the phase unless the file is those bytes (`E3D3_RELEASE_TEST_ONLY`); this tool refuses the
# release without the mark, off ITEM4_REORG, in a mode other than EXPLORATORY, PR_SMOKE or CONFIRMATORY, or on
# a node whose chain is not regtest (L0_RELEASE_NOT_TEST_ONLY, exit 5), and removes the record and the procedure
# file on every path from the record's write on (pre-PR P3-1: also when the turn, a check of its lines or of the
# procedure file fails). B-B1 (045b :1069, A's decision 2026-11-02 (ㄱ)): CONFIRMATORY takes this path; item 4's
# `item4_run` refuses a CONFIRMATORY ITEM4_REORG run off it before any node (ITEM4_L0_REORG_CONFIRMATORY, exit 3).
# Pre-PR P3-3: the release is a capability, not a keyword: the public `observe_turn` runs only the first two of
# `OBSERVING` (`set_release` is L0_OBSERVE_PHASE there); only `release_reorg67` reaches the release turn, through
# the private `_turn`.
OBSERVING = ('set_observe', 'set_reorged', 'set_release')
OBSERVE_TURN_PHASES = ('set_observe', 'set_reorged')
RELEASE_REORG67_TEST_ONLY = 'RELEASE_REORG67_TEST_ONLY'
RELEASE_RECORD_TEST_ONLY = (b'TEST_ONLY Class T D3a-2b-2a: RELEASE_REORG67_TEST_ONLY, TDS 6.7 procedure record, '
                            b'step 6 not performed (1D3 Q17)\n')   # host `SET_RELEASE_RECORD`, byte for byte
PROCEDURE_SHA256_TEST_ONLY = hashlib.sha256(RELEASE_RECORD_TEST_ONLY).hexdigest()
RELEASED_REORG67 = 'reason:Reorg67;step6:Some(NotPerformed)'
REORG_LINE = re.compile(r'raised:(true|false);local:(0|[1-9][0-9]*):([0-9a-f]{64});at_local:([0-9a-f]{64}|below);'
                        r'ancestor:(-|(0|[1-9][0-9]*):([0-9a-f]{64}))\Z')
# B's condition (a) on D3a-1b: each stage of L0's rung 0 here and the `oe.l0_chain` step it mirrors (oe's line at
# 0aac11d6; `LadderSeat.test_mirrors_oe_l0_chain` checks both orders): (this tool's worker or phase, oe's, oe's line).
# Rung k ≥ 1 adds `set_sign` / named sign at H0 − 2 and `set_ready` before its `set_send`; oe has no rung k.
# The stages are oe's in oe's order; the checks between them are `CHECKS_MIRRORED` (in their per-rung form) and
# `DEVIATIONS` (oe's checks this tool leaves out, each with its reason). WRD3a1b P3-4: not "step for step".
MIRRORS = (
    (oe.DESCRIBE_WORKER, oe.DESCRIBE_WORKER, 2912),   # described = host(DESCRIBE_WORKER, …)
    ('launch_set_charge_stage_worker', oe.CHARGE_WORKER, 2931),   # signer(charge_worker, CHARGE_LINES, …)
    ('set_sign', 'l0_sign', 2937),                    # phase("l0_sign", constructed, None, CASE_CONSTRUCTION)
    ('launch_named_sign_stage_worker', oe.OFFLINE_SIGN_WORKER, 2941),   # signer(OFFLINE_SIGN_WORKER, …)
    ('set_wait', 'l0_wait', 2958),                    # phase("l0_wait", constructed, txid, CASE_CONSTRUCTION)
    ('set_send', 'l0_broadcast', 2962),               # after the floor block (:2960): phase("l0_broadcast", …)
)
# WRD3a1b P3-4: oe.l0_chain's checks between its stages, as this tool makes them for each rung of the set (in
# item 2 the other bidders share Node A's and Node B's mempools, so every mempool check is per txid): (this
# tool's check and code, oe's check, oe's line at 0aac11d6 = d3623ca7). `test_checks_mirrored_in_oe` reads oe's lines.
CHECKS_MIRRORED = (
    ('the set hand-off listing after the charge (L0_SET_HANDOFF)', 'check_boundary(launch, "charge"', 2932),
    ('scan_key_material after the charge (in `_offline`)', 'scan_key_material(work)', 2933),
    ('tip unmoved, funding output unspent (L0_TIP_MOVED, L0_FUNDING_SPENDER)', 'check_nothing_sent(pair, constructed', 2934),
    ('the outbox empty after the charge (L0_OUTBOX)', 'if listing(launch / "outbox")', 2935),
    ('scan_key_material after each `set_sign`', 'scan_key_material(work)', 2938),
    ('the launch tree after each named sign stage (L0_SET_DIR)', 'check_listing(launch, ["export", "handoff", "host", "outbox"], "L0_DIR")', 2946),
    ('the exports so far after each named sign stage (L0_SET_EXPORTS)', 'check_boundary(launch, "export"', 2947),
    ('the outbox unchanged by each named sign stage (L0_SET_OUTBOX)', 'check_boundary(launch, "sign"', 2948),
    ('scan_key_material after each named sign stage (in `_offline`)', 'scan_key_material(work)', 2949),
    ('tip unmoved and funding unspent before G − 1 and before each step 8; no rung in a mempool before its step 8 '
     '(L0_SENT_BEFORE_STEP_8)', 'check_nothing_sent(pair, tip, funding, txid)', 2961),
    ("step 8's bytes are the export's (L0_BYTES)", 'if sent["raw_tx_sha256"] != exported["raw_tx_sha256"]', 2963),
    ('after each step 8: both nodes hold the rung (L0_RUNG_NOT_IN_MEMPOOL), not rung k − 1 (L0_RUNG_NOT_REPLACED), '
     'the rung alone spends the funding output in the mempool and the chain still has it unspent '
     '(L0_FUNDING_SPENDER), the tip is still G − 1 (L0_TIP_MOVED)', 'check_submitted(pair, tip, funding, txid)', 2965),
)
# oe's checks this tool deliberately leaves out: (oe's check, oe's line, the reason). Named in section 22.
DEVIATIONS = (
    ('getmempoolinfo size 0 (check_nothing_sent) and 1 (check_submitted)', 1525,
     "item 2's other bidders share Node A's and Node B's mempools: the checks are per txid instead"),
    ('the steps count of each phase (L0_STEPS)', 2891,
     'the set worker reports turns, not steps: each phase checks its rung\'s final verdict instead '
     '(L0_SET_PHASE_VERDICT)'),
    ('the event lines of each host process (event_names, EVENT_LINES)', 2870,
     'the set worker writes no event lines (it has no BITAGI_E3D3_EVENT_LINES value)'),
    ('every H0 − 1 comparison ran (L0_PENDING)', 2968,
     "the host orders the rungs' comparisons itself (a rung's comparison can come in another rung's phase): "
     'every pending comparison is run and every phase must end with none pending (L0_SET_PHASE), no fixed count'),
)
SENDING = ('set_send', 'set_broadcast')
# WRD3a1b P3-3: the verdict rung k must end each phase with (the set worker's last `labels` line, `set_verdict`'s
# form; host test `launch_set_worker`'s done arms; decision.rs `Wait`, `Step::Broadcast`). Any other, a refusal
# or a final outcome among them, is L0_SET_PHASE_VERDICT. `set_observe` is judged by its labels (`observe`).
PHASE_VERDICTS = {
    'set_sign': ('Wait:OfflineSignaturePending',),
    'set_wait': ('Wait:SignedAwaitingOpeningGate',),
    'set_ready': ('Wait:BroadcastAuthorityRequired',),
    'set_send': ('Act:Broadcast', 'Wait:AwaitingInclusion'),
    'set_broadcast': ('Act:Broadcast', 'Wait:AwaitingInclusion'),
}
LAUNCH_DIRS = ['export', 'handoff', 'host', 'outbox']   # oe.l0_chain's L0_DIR listing (oe:2946)
MAX_COMPARISONS = 4          # DEFAULT: a phase's runs that end at an H0 - 1 comparison (one per rung acting)
COUNTER_FIELDS = ('released', 'gate_attempts', 'fee_exposure_sat', 'principal_exposure_sat')
RUNG_TOKEN = ('k', 'wallet_candidate', 'charge_sequence', 'fee_sat', 'wallet_fee_sat', 'wallet_vsize', 'txid',
              'base_sha256')
HEX64 = re.compile(r'[0-9a-f]{64}\Z')
DECIMAL = re.compile(r'(0|[1-9][0-9]*)\Z')


def l0_set(b: int, i: int) -> list[int]:
    """The L0 seat's conflict set: its ladder (`item2.l0_ladder`, the bidders' `ladder(p_0, b, i, v)`, 045b
    :537, the single source with its 4b cap and rung 7), refused where the wallet would refuse it
    (`item2.check_l0_set`: ITEM2_L0_SET_REFUSED; not two rungs ITEM2_L0_LADDER_NOT_TWO_RUNGS, FD-CT-133)."""
    return I2.check_l0_set(l0_ladder(b, i))


def parse_counters(text: str) -> dict:
    """The set worker's `budget_counters` line (`released=…;gate_attempts=…;fee_exposure_sat=…;
    principal_exposure_sat=…`, the wallet's own counters), exactly that form (L0_BUDGET_COUNTERS)."""
    parts = text.split(';')
    if [p.partition('=')[0] for p in parts] != list(COUNTER_FIELDS):
        raise oe.Mismatch('L0_BUDGET_COUNTERS')
    values = [p.partition('=')[2] for p in parts]
    if not all(DECIMAL.match(v) for v in values):
        raise oe.Mismatch('L0_BUDGET_COUNTERS')
    return dict(zip(COUNTER_FIELDS, map(int, values)))


def parse_rungs(text: str, fees: list[int]) -> list[dict]:
    """The set charge's `rungs` line: one token per rung in rung order (`RUNG_TOKEN`), the fee the set's."""
    rows = []
    for k, token in enumerate(text.split(';')):
        values = token.split(':')
        if len(values) != len(RUNG_TOKEN):
            raise oe.Mismatch('L0_SET_RUNGS')
        row = dict(zip(RUNG_TOKEN, values))
        for name in ('k', 'charge_sequence', 'fee_sat', 'wallet_fee_sat', 'wallet_vsize'):
            if not DECIMAL.match(row[name]):
                raise oe.Mismatch('L0_SET_RUNGS')   # a wallet row without fee or vsize ('-') is refused too
            row[name] = int(row[name])
        if not all(HEX64.match(row[n]) for n in ('wallet_candidate', 'txid', 'base_sha256')):
            raise oe.Mismatch('L0_SET_RUNGS')
        if row['k'] != k or row['charge_sequence'] != k + 1:
            raise oe.Mismatch('L0_SET_RUNGS')
        rows.append(row)
    if [r['fee_sat'] for r in rows] != fees:
        raise oe.Mismatch('L0_SET_RUNGS')
    return rows


def parse_labels(text: str, n: int) -> list[dict]:
    """The set worker's `labels` line: `r<j>=<verdict>/<outcome>` for every rung of the set, once each."""
    labels: dict[int, dict] = {}
    for item in text.split(';') if text else []:
        name, _, value = item.partition('=')
        verdict, _, outcome = value.partition('/')
        if not (name.startswith('r') and DECIMAL.match(name[1:]) and verdict and outcome):
            raise oe.Mismatch('L0_LABELS')
        j = int(name[1:])
        if j in labels or j >= n:
            raise oe.Mismatch('L0_LABELS')
        labels[j] = {'verdict': verdict, 'outcome': outcome}
    if sorted(labels) != list(range(n)):
        raise oe.Mismatch('L0_LABELS')
    return [labels[j] for j in range(n)]


def parse_reorg(text: str) -> dict | None:
    """D3a-2b-2a: the set worker's `reorg` line (host `set_reorg`): None for `-`, else `raised`, `local` (height,
    internal hash), `at_local` (internal hash or `below`) and `ancestor` ((height, internal hash) or None); any
    other form is L0_REORG_LINE."""
    if text == '-':
        return None
    m = REORG_LINE.match(text)
    if not m:
        raise oe.Mismatch('L0_REORG_LINE')
    return {'raised': m.group(1) == 'true', 'local': [int(m.group(2)), m.group(3)], 'at_local': m.group(4),
            'ancestor': None if m.group(5) == '-' else [int(m.group(6)), m.group(7)]}


def check_release_test_only(mark: str, scenario: str, mode: str, chains: dict) -> None:
    """D3a-2b-2a, condition (가): the Reorg67 release runs only as the `RELEASE_REORG67_TEST_ONLY` phase of a
    Class T item-4 ITEM4_REORG run (EXPLORATORY, PR_SMOKE or, since B-B1, CONFIRMATORY: 045b :1069) on Regtest
    nodes: `mark` the constant, `chains` each of Node A's and Node B's `getblockchaininfo` chain `regtest`.
    Otherwise L0_RELEASE_NOT_TEST_ONLY (exit 5, a security-policy refusal), before any host process."""
    if (mark != RELEASE_REORG67_TEST_ONLY or scenario != 'ITEM4_REORG' or mode not in ('EXPLORATORY', 'PR_SMOKE',
            'CONFIRMATORY') or sorted(chains) != ['A', 'B'] or any(chain != 'regtest' for chain in chains.values())):
        raise Refusal('L0_RELEASE_NOT_TEST_ONLY', D.EXIT_SECURITY)


def read_procedure(path: Path) -> dict:
    """Pre-PR P3-1: the TDS 6.7 procedure file's fields, one `name=value` per line. A missing or non-ASCII file,
    a line without `=` or a name given twice is L0_PROCEDURE_NOT_TEST_ONLY (never a bare exception)."""
    try:
        lines = path.read_text(encoding='ascii').splitlines()
    except (OSError, UnicodeDecodeError):
        raise oe.Mismatch('L0_PROCEDURE_NOT_TEST_ONLY') from None
    fields: dict[str, str] = {}
    for line in lines:
        name, sep, value = line.partition('=')
        if not sep or name in fields:
            raise oe.Mismatch('L0_PROCEDURE_NOT_TEST_ONLY')
        fields[name] = value
    return fields


def expected_labels(n: int, included: int | None, born: int | None, next_birth: int, h0: int = H0,
                    miss: str = EXACT_HEIGHT_MISS, released: tuple[int, ...] = ()) -> list[dict]:
    """The host's label for each rung of L0's set after block G (the unit note, section 0), in rung order, from
    the L0 rung block G holds (`included`, or None) and the one the replay found born (`born`, or None; a born
    rung is the included one). WRD3a1b P2-1: not from the latest released rung, which an exclusion
    (RELEASE_NOT_IN_TEMPLATE for the L0 seat) can leave out of G while an earlier rung is in it.
    L0's rung `born`: it is `Done:Born` (at the opening), every other rung of the set
    `Done:ProjectBornByOther` (a sibling of the campaign born; decision.rs:375-399, machine.rs:1439-1454).
    Otherwise no project REGISTER was accepted at H0, so under the STOP_CAMPAIGN budget every rung is refused
    `ExactHeightMissed` before its outcome is read (machine.rs:1317-1332); the report still carries the
    outcome: `IncludedNoEffect` at H0 for the rung block G holds, `Stale` (target H0, the replay's next birth
    height) for every other rung (all of them when G holds none: predicted, no real-node row).
    D3a-2b-1 (A 6557723699): under `CONTINUE_WITHIN_LIMITS` (`miss`, the budget's `exact_height_miss`) no campaign
    stop refuses the rungs: the rung block G holds is `Done:IncludedNoEffect@<H0>` (045b 4.3); a `Stale` rung that
    was released (`released`: its k) `Refuse:GateAdvanced`, one charged but never released
    `Wait:OfflineSignaturePending` (real-node rows, unit note D3a-2b-1 section 6)."""
    if miss not in EXACT_HEIGHT_MISS_VALUES:
        raise invalid('L0_EXACT_HEIGHT_MISS')
    if born is not None:
        if born != included:
            raise oe.Mismatch('L0_IN_G')
        return [{'verdict': f'Done:Born@{h0}+opening', 'outcome': f'Born@{h0}+opening'} if j == born else
                {'verdict': f'Done:ProjectBornByOther@{h0}', 'outcome': f'ProjectBornByOther@{h0}'} for j in range(n)]
    if miss == 'CONTINUE_WITHIN_LIMITS':
        return [{'verdict': f'Done:IncludedNoEffect@{h0}', 'outcome': f'IncludedNoEffect@{h0}'} if j == included
                else {'verdict': CONTINUE_LOST if j in released else CONTINUE_UNRELEASED,
                      'outcome': f'Stale@{h0}>{next_birth}'} for j in range(n)]
    return [{'verdict': 'Refuse:ExactHeightMissed',
             'outcome': f'IncludedNoEffect@{h0}' if j == included else f'Stale@{h0}>{next_birth}'} for j in range(n)]


def set_handoff(n: int) -> list[str]:
    """`launch/handoff/` after the set charge of n rungs (signer test `set_handoff`): rung 0's `base.txt` and
    `launch.txt`, each rung's `base-k.txt` and `launch-k.txt`, the budget record and the wallet ledger."""
    return sorted(['base.txt', 'budget.json', 'launch.txt', 'wallet.sqlite',
                   *(f'{name}-{k}.txt' for k in range(n) for name in ('base', 'launch'))])


CONTINUE_LOST, CONTINUE_UNRELEASED = 'Refuse:GateAdvanced', 'Wait:OfflineSignaturePending'   # real-node rows


class _Aborted(Exception):
    """The run stopped L0 while it waited."""


class L0Seat:
    """The item-2 run's L0 project bidder (`item2_run(l0=…)`): its whole conflict set (module docs). The main
    thread calls `fund`, `start`, `ready`, `floor`, `finish`, `observe`, `stop`; only the main thread writes the
    raw log. Its own thread runs every host and signer stage."""

    def __init__(self, pair, send, work: Path, cargo: str, offline_env: dict, online_env: dict, secrets_,
                 relay=None, clock=None, sleep_until=None, exact_height_miss: str = EXACT_HEIGHT_MISS,
                 budget_sha256: str | None = None, registered: bool = False):
        if exact_height_miss not in EXACT_HEIGHT_MISS_VALUES:
            raise invalid('L0_EXACT_HEIGHT_MISS')
        self.exact_height_miss = exact_height_miss
        self.budget_sha256 = budget_sha256   # D3a-2b-2b: a policy's `l0_seat` value (None: no policy value)
        # B-FZ-a (#667 A 6571519328 P3-1): the policy is a registered one (CONFIRMATORY) or not (EXPLORATORY).
        if registered and budget_sha256 is None:
            raise invalid('L0_REGISTERED_WITHOUT_BUDGET')
        self.registered = registered
        self.pair, self.send, self.work, self.cargo = pair, send, work, cargo
        self.offline_env, self.online_env, self.secrets = offline_env, online_env, secrets_
        self.relay = relay
        self.clock = clock or CLOCK
        self.sleep_until = sleep_until   # tests' stand-in; otherwise `_wait_until`
        self.lock = threading.Lock()
        self.stages: list[dict] = []
        self.logged = 0
        self.attempts = 0
        self.ready_event, self.floor_event, self.done_event = threading.Event(), threading.Event(), threading.Event()
        self.thread = None
        self.error = None
        self.abort = False
        self.got: dict = {'released': []}
        self.schedule: list[tuple[int, int]] = []
        self.deadline: float | None = None
        self.monotonic = time.monotonic   # the deadline's clock (a cell gives a fake one; D3a-1a 1a85450c)

    # The main thread's calls.

    def fund(self, log, unit: dict, nodes: dict) -> dict:
        """Block 1 to oe's `FUNDING_DESCRIPTOR` on Node A (`generatetodescriptor`, oe's driver user), accepted
        by all four nodes before item 2's setup: its coinbase is L0's funding (oe.chain_facts, height 1)."""
        if any(node.call('getbestblockhash') != nodes['A'].call('getbestblockhash') for node in nodes.values()):
            raise oe.Mismatch('L0_FUND_NOT_AT_GENESIS')
        if self.pair.a.height() != 0:
            raise oe.Mismatch('L0_FUND_NOT_AT_GENESIS')
        descriptor = self.pair.a.call('getdescriptorinfo', oe.FUNDING_DESCRIPTOR)['descriptor']
        block_hash = self.pair.mine(descriptor, oe.FUNDING_HEIGHT)
        D.wait_until(lambda: all(node.call('getbestblockhash') == block_hash for node in nodes.values()),
                     'all four nodes at L0 funding block', D.ACCEPT_SECONDS, I2.POLL)
        block = self.pair.a.call('getblock', block_hash, '1')
        block_hex = self.pair.a.call('getblock', block_hash, '0')
        log.write('L0_FUNDING_BLOCK', unit, height=oe.FUNDING_HEIGHT, block_hash=block_hash, block_hex=block_hex,
                  coinbase_txid=block['tx'][0], funding_script=oe.FUNDING_SCRIPT, mined_by='generatetodescriptor')
        return {'height': oe.FUNDING_HEIGHT, 'block_hash': block_hash, 'block_hex': block_hex}

    def start(self, log, unit, seat, observation, b, nodes) -> list[int]:
        """One L0 attempt: its set (`l0_set`, from both nodes' `incrementalfee`), then its thread: describe,
        the set charge and every rung signed at H0 − 2, rung 0 imported. Returns the set's fees (item 2's
        SCHEDULE ladder for this seat)."""
        if self.thread is not None:
            raise invalid('L0_STARTED')
        with _ALIVE_LOCK:
            _ALIVE[:] = [t for t in _ALIVE if t.is_alive()]
            if _ALIVE:
                raise oe.Prerequisite('L0_PREVIOUS_THREAD_ALIVE')   # WRD3a1a P2-1
        self.attempts += 1
        self.attempt = attempt_id(observation, self.attempts)
        self.seat = seat
        increments = {role: oe.sats(nodes[role].call('getnetworkinfo')['incrementalfee']) for role in ('A', 'B')}
        p0, i = l0_p0(b), max(increments.values())
        fees = l0_set(b, i)
        # D3a-1a's fields kept (rung 0's k and f_k; `ladder` is now the whole set L0 charges).
        self.fee = {'rule': FEE_RULE, 'p0_rule': P0_RULE, 'b': b, 'p0': p0, 'increments': increments, 'i': i,
                    'v': V, 'k': 0, 'f_k': fees[0], 'ladder': fees}
        log.write('L0_LAUNCH_START', unit, seat=seat['seat'], kind=seat['kind'], attempt=self.attempts,
                  attempt_id=self.attempt, h0=H0, fee=self.fee, **self.budget_fields(), worker=SET_WORKER,
                  exact_height_miss=self.exact_height_miss)
        self.deadline = self.monotonic() + READY_SECONDS + FLOOR_SECONDS + FINISH_SECONDS
        self.thread = threading.Thread(target=self._run, name='l0-seat', daemon=True)
        self.thread.start()
        return fees

    def budget_fields(self) -> dict:
        """L0_LAUNCH_START's budget (#667 A integration check P3-2): with a policy's values the record the run
        must charge is the policy's `budget_sha256` (compared with the product's record in `_budget`), and
        `budget_source` is REGISTERED_POLICY for a CONFIRMATORY (registered) policy, POLICY_VALUE otherwise
        (B-FZ-a; #667 A 6571519328 P3-1: never REGISTERED_POLICY outside CONFIRMATORY); without one, the
        module's record (`BUDGET_DRAFT`, A's frozen values; `budget_source` BUDGET_DRAFT and `budget_draft`)."""
        if self.budget_sha256 is not None:
            source = 'REGISTERED_POLICY' if self.registered else 'POLICY_VALUE'
            return {'budget_source': source, 'budget_sha256': self.budget_sha256}
        return {'budget_source': 'BUDGET_DRAFT', 'budget_draft': BUDGET_DRAFT}

    def policy_compare(self, digest: str) -> dict:
        """L0_BUDGET's policy comparison (B-FZ-a FZ-1): with a policy's `budget_sha256`, that digest and
        EQUAL (`_budget` raised L0_POLICY_BUDGET_SHA256 on any other); without one, NO_POLICY_VALUE."""
        if self.budget_sha256 is None:
            return {'policy_compare': 'NO_POLICY_VALUE'}
        if digest != self.budget_sha256:
            raise oe.Mismatch('L0_POLICY_BUDGET_SHA256')
        return {'policy_budget_sha256': self.budget_sha256, 'policy_compare': 'EQUAL'}

    def ready(self, log, unit) -> dict:
        """Waits until every rung is signed at H0 − 2 and rung 0 imported (L0 waits for G − 1). Writes
        `L0_SET_CHARGED` (each rung's wallet row and charge base, also when a later stage failed: WRD3a1b P3-1)
        and `L0_READY` (each rung's product txid, bytes' SHA-256 and candidate id)."""
        if not self.ready_event.wait(READY_SECONDS):
            raise oe.Prerequisite('L0_NOT_READY')
        self._log_stages(log, unit)
        charged = self.got.get('charged')
        if charged is not None and 'rows' in self.got:
            log.write('L0_SET_CHARGED', unit, attempt_id=self.attempt, set_id=charged['set_id'],
                      budget_sha256=charged['budget_sha256'], rungs=self.got['rows'], fees=self.fee['ladder'],
                      charge_bases=self.got.get('bases'))
        self._raise()
        first = self.got['exports'][0]
        log.write('L0_READY', unit, attempt_id=self.attempt, t_ready_ns=self.got['ready_ns'], txid=first['txid'],
                  raw_tx_sha256=first['raw_tx_sha256'], candidate_id=first['candidate_id'], rungs=[{'k': k, **{n: e[n] for n in ('txid', 'raw_tx_sha256', 'candidate_id')}}
                         for k, e in enumerate(self.got['exports'])])
        return self.got

    def floor(self, block_hash: str, releases: list[tuple[int, int]]) -> None:
        """G − 1 is at all four nodes. `releases` is item 2's schedule for this seat: (k, due_ns) for every
        rung released at all (rung_seconds × k < t_G), rung 0 first (due t0)."""
        ks = [k for k, _ in releases]
        if not ks or ks != list(range(len(ks))) or len(ks) > len(self.fee['ladder']):
            raise invalid('L0_SCHEDULE')
        self.floor_hash, self.schedule = block_hash, list(releases)
        self.floor_event.set()

    def finish(self, log, unit) -> dict:
        """Waits for L0's last release and returns what it sent, per rung: the product's txid, the nodes'
        fee and vsize, `replaces`, the due and send times, whether the relay saw it. Writes the remaining
        `L0_TURN` lines, one `L0_ADMISSION` per released rung (computed f_k, the wallet row, the charge base,
        both nodes; L0_FEE_MISMATCH where a node differs), `L0_BUDGET` and `L0_LAUNCH_END`. WRD3a1b P3-2: the
        admissions of the rungs released are written also when a later rung failed, before that failure is
        raised. The wallet row and the charge base of every rung were compared right after the charge
        (`_check_charged`, WRD3a1b P3-1)."""  # L0-501: a failed attempt's rung tests are written before its error (:664)
        if self.thread is None:
            raise invalid('L0_NOT_STARTED')
        if not self.done_event.wait(FINISH_SECONDS):
            raise oe.Prerequisite('L0_NOT_FINISHED')
        self.thread.join()
        self._log_stages(log, unit)
        released = self.got['released']
        differs = False
        for rung in released:
            k = rung['k']
            row = self.got['rows'][k]
            computed = {**self.fee, 'k': k, 'f_k': self.fee['ladder'][k]}
            log.write('L0_ADMISSION', unit, attempt_id=self.attempt, k=k, txid=rung['txid'], nodes=rung['nodes'],
                      sent_by=SENT_BY, computed=computed,
                      wallet={'fee_sat': row['wallet_fee_sat'], 'vsize': row['wallet_vsize'], 'source': 'WALLET_ROW',
                              'charge_base': self.got['bases'][k]})
            differs |= {(e['fee'], e['vsize']) for e in rung['nodes'].values()} != {(computed['f_k'], V)}
        self._raise() if I2.l0_rung_tests_before_raise(log, unit, self.attempt, self.got.get('tests', {}), self.error) else None
        if differs:
            raise oe.Mismatch('L0_FEE_MISMATCH')   # A Q-L1, every released rung on both nodes
        # D3a-2b-1 (A 6557890079 request 2): every rung k >= 1 has Node A's and Node B's testmempoolaccept answer,
        # as returned: a released rung's before its step 8 (`_release`), a charged rung never released here,
        # before G (the tip still G - 1, the last released rung in both mempools; else the reason it is untested).
        done = {r['k'] for r in released}
        for k in range(1, len(self.fee['ladder'])):
            if k not in done:
                self._rung_test(k, 'CHARGED_NOT_RELEASED_BEFORE_G')
        for k in range(1, len(self.fee['ladder'])):
            log.write('L0_RUNG_TEST', unit, attempt_id=self.attempt, **self.got['tests'][k])
        product = self._budget()
        log.write('L0_BUDGET', unit, attempt_id=self.attempt, product=product,
                  threshold_sat_per_attempt=BUDGET_DRAFT['fee_row_threshold_sat_per_attempt'],
                  **self.policy_compare(product['budget_sha256']))
        log.write('L0_LAUNCH_END', unit, status='DONE', attempt_id=self.attempt, txid=released[-1]['txid'],
                  released=[r['k'] for r in released], stages=len(self.stages))
        return {'attempt_id': self.attempt, 'released': released, 'fees': self.fee['ladder']}

    def observe(self, log, unit, in_g: list[int], born: list[int], next_birth: int, in_template: list[int],
                excluded: bool) -> dict:
        """After block G (main thread): one host turn (`set_observe`). `in_g`: the ks of L0's released rungs
        block G holds; `born`: those the replay found born (item 2 reads both from G's template and the replay).
        Writes `L0_LABELS` (each rung's verdict and report outcome, and the expected ones: `expected_labels`
        from the rung in G and the one born, WRD3a1b P2-1) and `L0_BUDGET_COUNTERS` (the wallet's counters from
        the worker's line); a label other than the expected one is L0_LABEL_MISMATCH. More than one L0 rung
        in G, or a born rung not in G, is L0_IN_G. A stage due past the attempt's deadline (or after `stop`)
        is L0_DEADLINE (WRD3a1b P3-7). Delta review (WRD3a1b): `in_g` is read from block G's own
        transactions, `in_template` from its template; L0 rungs that differ between them are L0_IN_G always
        (P3-B, fail closed). When item 2's gate is `excluded` (its code), a label mismatch or an inconsistent
        `in_g` / `born` is logged (`L0_LABELS` `match` false) and not raised (P3-A): the exclusion is the
        gate's outcome, and the labels of an excluded gate may rest on a prediction (no L0 rung in G)."""
        released = [r['k'] for r in self.got['released']]
        if sorted(in_g) != sorted(in_template):
            raise oe.Mismatch('L0_IN_G')
        consistent = len(in_g) <= 1 and len(born) <= 1 and set(born) <= set(in_g) and set(in_g) <= set(released)
        if not consistent and not excluded:
            raise oe.Mismatch('L0_IN_G')
        included, won = (in_g or [None])[0], (born or [None])[0]
        try:
            got = self._phase('set_observe', 0, oe.GATE)
        except _Aborted:
            raise oe.Prerequisite('L0_DEADLINE') from None
        finally:
            self._log_stages(log, unit)   # B-J5F: the raw lines (L0_TURN), even if `_phase` or a parse refuses one
        n = len(self.fee['ladder'])
        labels = parse_labels(got['labels'], n)
        latest = released[-1]
        expected = expected_labels(n, included, won, next_birth, miss=self.exact_height_miss,
                                   released=tuple(released)) if consistent else None
        counters = parse_counters(got['budget_counters'])
        match = labels == expected
        log.write('L0_LABELS', unit, attempt_id=self.attempt, won=won is not None, latest=latest, in_g=included,
                  born=won, labels=labels, expected=expected, match=match, excluded=excluded,
                  exact_height_miss=self.exact_height_miss,
                  **({} if consistent else {'in_g_ks': list(in_g), 'born_ks': list(born)}))
        log.write('L0_BUDGET_COUNTERS', unit, attempt_id=self.attempt, counters=counters,
                  source='WALLET_LEDGER_WORKER_LINE', worker=SET_WORKER, phase='set_observe', rung=0)
        if not match and not excluded:
            raise oe.Mismatch('L0_LABEL_MISMATCH')
        return {'labels': labels, 'counters': counters, 'match': match}

    def observe_turn(self, log, unit, phase: str = 'set_observe') -> dict:
        """D3a-2b-1 (item 4, main thread): one host turn after G (`set_observe`, no transport) at the nodes'
        tip, as often as the caller asks (each call a new turn). Returns the worker's `labels` (parsed, every
        rung once), its `flags` line as written (item 4 parses and judges it) and the wallet's counters. A stage
        due past the attempt's deadline (or after `stop`) is L0_DEADLINE, as in `observe`. D3a-2b-2a: `phase`
        may be `set_reorged`; every phase also returns the worker's `reorg` line parsed (`parse_reorg`) and its
        `released` line as written. Pre-PR P3-3: `set_release` (or any other phase) is L0_OBSERVE_PHASE here;
        only `release_reorg67` runs it."""
        if phase not in OBSERVE_TURN_PHASES:
            raise invalid('L0_OBSERVE_PHASE')
        return self._turn(log, unit, phase)

    def _turn(self, log, unit, phase: str) -> dict:
        """One observing host turn (`observe_turn`'s body; `release_reorg67`'s release turn)."""
        if phase not in OBSERVING:
            raise invalid('L0_OBSERVE_PHASE')
        try:
            got = self._phase(phase, 0, oe.GATE)
        except _Aborted:
            raise oe.Prerequisite('L0_DEADLINE') from None
        finally:
            # B-J5F (A 6656311995 B2; #718 P3-1): the worker's raw lines (L0_TURN `lines`) are written here, in
            # `finally`: after `_phase`'s own checks (`done`, the verdict, `budget_counters`) and before the parses
            # below, so a line refused by either still leaves its turn's raw record (#718 P3-2: a refused write wins).
            self._log_stages(log, unit)
        n = len(self.fee['ladder'])
        return {'labels': parse_labels(got['labels'], n), 'flags': got['flags'],
                'counters': parse_counters(got['budget_counters']), 'reorg': parse_reorg(got['reorg']),
                'released': got['released']}

    def release_files(self) -> tuple[Path, Path]:
        """The two files of the `RELEASE_REORG67_TEST_ONLY` phase: the TEST_ONLY release record this tool
        writes and the TDS 6.7 procedure file the worker writes (`host/release-record.txt`,
        `host/procedure.txt`)."""
        return self.launch / 'host' / 'release-record.txt', self.launch / 'host' / 'procedure.txt'

    def remove_release_files(self) -> None:
        """Removes both release files when present (pre-PR P3-1; #450 runbook section 2 item 5, as
        `oe.LostContext.release`): `release_reorg67` on every path from the record's write on, and item 4's
        `reorg_run_l0` again after the RELEASE turn whatever happened there."""
        for path in self.release_files():
            path.unlink(missing_ok=True)

    def release_reorg67(self, log, unit, mark: str, scenario: str, mode: str, nodes: dict,
                        reads: tuple) -> dict:
        """D3a-2b-2a: the `RELEASE_REORG67_TEST_ONLY` phase (A 6557723699 Q4): condition (가) checked first
        (`check_release_test_only`, Node A's and Node B's chain read here), then one `set_release` turn with
        the TEST_ONLY release record written to `host/release-record.txt`, whose `released` line must be the
        Reorg67 release with step 6 not performed (L0_RELEASE_NOT_REORG67). The procedure file the worker
        presented (`host/procedure.txt`) must be `name=value` lines (`read_procedure`) carrying the TEST_ONLY
        record's digest (L0_PROCEDURE_NOT_TEST_ONLY, also for a malformed or missing file) and must be the
        reorg of the caller's own reads (`reads`: local, at_local, ancestor; `oe.check_reorg_procedure`).
        Pre-PR P3-1: from just before the record's write to the end of these checks one try/finally removes
        both files (`remove_release_files`) on every path; the procedure's fields are returned as read."""
        chains = {role: nodes[role].call('getblockchaininfo')['chain'] for role in ('A', 'B')}
        check_release_test_only(mark, scenario, mode, chains)
        record, path = self.release_files()
        try:
            fd = os.open(record, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'wb') as handle:
                handle.write(RELEASE_RECORD_TEST_ONLY)
            got = self._turn(log, unit, 'set_release')
            if got['released'] != RELEASED_REORG67:
                raise oe.Mismatch('L0_RELEASE_NOT_REORG67')
            fields = read_procedure(path)
            if fields.get('procedure_sha256') != PROCEDURE_SHA256_TEST_ONLY:
                raise oe.Mismatch('L0_PROCEDURE_NOT_TEST_ONLY')
            oe.check_reorg_procedure(path, *reads)
        finally:
            self.remove_release_files()
        return {**got, 'procedure': fields, 'chains': chains, 'mark': mark}

    def last_counters(self, log, unit) -> dict:
        """WRD3a1b P3-6: for a gate with no block G (REPLACED_RUNG_NOT_IN_MEMPOOL), after `finish`: the wallet's
        counters as the last set-worker phase's line read them (every phase reports them; no `set_observe`
        without G). Writes `L0_BUDGET_COUNTERS` with that phase and rung."""
        last = self.got.get('counters')
        if last is None:
            raise invalid('L0_NOT_STARTED')
        log.write('L0_BUDGET_COUNTERS', unit, attempt_id=self.attempt, counters=last['counters'],
                  source='WALLET_LEDGER_WORKER_LINE', worker=SET_WORKER, phase=last['phase'], rung=last['rung'])
        return last['counters']

    def stop(self) -> None:
        """Ends L0's thread (item2_run's cleanup, also after a failure). No new stage starts after this, and
        the running one is bounded by the attempt's deadline, so the wait is FINISH_SECONDS or up to that
        deadline plus STOP_GRACE_SECONDS. A thread still alive then is L0_THREAD_ALIVE, and every later
        `start` in the process is refused until it ends (WRD3a1a P2-1)."""
        if self.thread is None:
            return
        self.abort = True
        self.floor_event.set()
        left = 0.0 if self.deadline is None else self.deadline - self.monotonic()
        self.thread.join(max(FINISH_SECONDS, left + STOP_GRACE_SECONDS))
        if self.thread.is_alive():
            with _ALIVE_LOCK:
                _ALIVE.append(self.thread)
            raise oe.Prerequisite('L0_THREAD_ALIVE')

    def _budget(self) -> dict:
        """The budget record the product's set charge wrote and pinned (its SHA-256 must be the stage's). It
        is A's frozen record for the run's `exact_height_miss` by its whole SHA-256 (`PRODUCT_BUDGET_SHA256`,
        B-FZ-p): any other record, the old Q1 draft bytes included, is L0_BUDGET_NOT_FROZEN. Its four
        `BUDGET_FIELDS` are read for the log."""
        data = D.read_input(self.launch / 'handoff' / 'budget.json', D.POLICY_LIMIT)
        digest = hashlib.sha256(data).hexdigest()
        if digest != self.got['charged']['budget_sha256']:
            raise oe.Mismatch('L0_BUDGET_SHA256')
        if self.budget_sha256 is not None and digest != self.budget_sha256:
            raise oe.Mismatch('L0_POLICY_BUDGET_SHA256')   # D3a-2b-2b: the record the policy names
        record = D.parse_json(data, 'L0_BUDGET_JSON')
        if not all(type(record.get(k)) is int for k in BUDGET_FIELDS):
            raise invalid('L0_BUDGET_FIELDS')
        if record.get('exact_height_miss') != self.exact_height_miss:
            raise oe.Mismatch('L0_BUDGET_MISS')   # D3a-2b-1: the product's record carries the run's policy
        if digest != PRODUCT_BUDGET_SHA256[self.exact_height_miss]:
            raise oe.Mismatch('L0_BUDGET_NOT_FROZEN')   # B-FZ-p: A's frozen record, byte for byte
        return {**{k: record[k] for k in BUDGET_FIELDS}, 'exact_height_miss': record['exact_height_miss'],
                'budget_sha256': digest, 'status': BUDGET_DRAFT['status'], 'source': 'PRODUCT_BUDGET_JSON',
                'class': record.get('release_class')}

    def _charge_base(self, k: int) -> dict:
        """The fee the set charge put in rung k's sign base (`base-k.txt` `absolute_fee_sat`), with its
        `signed_weight_wu`, the wallet's declared upper bound on the signed weight, not the transaction's (as
        D3a-1a's `_wallet_fee`; WRD3a1a P3-4)."""
        data = D.read_input(self.launch / 'handoff' / f'base-{k}.txt', D.POLICY_LIMIT)
        fields: dict[str, list[str]] = {}
        for line in data.decode('ascii').splitlines():
            name, _, value = line.partition('=')
            fields.setdefault(name, []).append(value)
        got = {}
        for name in ('absolute_fee_sat', 'signed_weight_wu'):
            values = fields.get(name, [])
            if len(values) != 1 or not values[0].isdigit():
                raise oe.Mismatch('L0_WALLET_FEE')
            got[name] = int(values[0])
        return {**got, 'declared_vsize_bound': -(-got['signed_weight_wu'] // 4), 'source': 'CHARGE_BASE'}

    # The stages.

    def _raise(self) -> None:
        if self.error is not None:
            raise self.error

    def _log_stages(self, log, unit) -> None:
        with self.lock:
            new = self.stages[self.logged:]
            self.logged = len(self.stages)
        for stage in new:
            log.write('L0_TURN', unit, attempt_id=self.attempt, worker=stage['worker'], lines=stage['lines'],
                      start_ns=stage['start_ns'], end_ns=stage['end_ns'])

    def _stage(self, worker, lines, env, features, package, test) -> dict:
        """One worker process. As D3a-1a (WRD3a1a P2-1): no stage starts after `stop`, and none runs past the
        attempt's deadline (oe's STAGE_SECONDS bound unchanged otherwise)."""
        left = (self.deadline - self.monotonic()) if self.deadline is not None else oe.STAGE_SECONDS
        if self.abort or left <= 0:
            raise _Aborted
        command = oe.worker_command(self.cargo, test, worker, features, package)
        start = self.clock()
        got = oe.run_stage(command, env, worker, lines, seconds=min(oe.STAGE_SECONDS, left), secrets_=self.secrets)
        end = self.clock()
        with self.lock:
            self.stages.append({'worker': worker, 'lines': dict(got), 'start_ns': start, 'end_ns': end})
        return {**got, '_start_ns': start, '_end_ns': end}

    def _facts(self, sign_entry: str | None) -> str:
        """The launch facts (oe's lines, the host's descriptor, the H0 − 2 sign tip), then D3a-1a's two L0
        lines and this unit's set lines (signer test `set_lines`): the operator's fees and `r_inc`."""
        fees = self.fee['ladder']
        text = (self.chain + f'descriptor={self.descriptor}\n' + oe.sign_tip_lines(self.constructed, oe.CASE_CONSTRUCTION)
                + f'l0_fee_sat={fees[0]}\nl0_budget={L0_BUDGET_LINE}\n'
                + f"l0_set_fees={','.join(map(str, fees))}\nl0_set_rinc={self.fee['i']}\n"
                + f'l0_set_exact_height_miss={self.exact_height_miss}\n')
        return text + (f'l0_sign_entry={sign_entry}\n' if sign_entry is not None else '')

    def _offline(self, worker, lines, sign_entry=None) -> dict:
        """One offline signer stage with the TEST_ONLY launch facts file. D3a-2c: one try/finally from just
        before the facts file's write, so the file is removed on every path (its write, `chmod` or
        `oe.private` raising included), and the temporary directory whenever `oe.private` returned it (if
        `oe.private` raises after its `mkdir`, an empty `launch-tmp` stays until the run's work directory goes)."""
        facts = self.root / 'launch-facts.txt'
        tmp = None
        try:
            facts.write_text(self._facts(sign_entry), encoding='ascii', newline='')
            facts.chmod(0o600)
            tmp = oe.private(self.root / 'launch-tmp')
            env = {**self.offline_env, 'BITAGI_E3D3_LAUNCH_FILE': str(facts.resolve()), 'TMPDIR': str(tmp.resolve())}
            return self._stage(worker, lines, env, ['--features', 'offline-ceremony'], oe.SIGNER_PACKAGE,
                               oe.LAUNCH_SIGNER_TEST)
        finally:
            facts.unlink(missing_ok=True)
            if tmp is not None:
                shutil.rmtree(tmp)
            shutil.rmtree(self.launch / 'offline', ignore_errors=True)
            oe.scan_key_material(self.work)

    def _phase(self, name: str, k: int, height: int) -> dict:
        """One set-worker phase for rung k; a run that ends at an H0 − 1 comparison is compared (oe.run_prestate)
        and run again. The phase must end done, for rung k, with rung k's last verdict the phase's
        (`PHASE_VERDICTS`, WRD3a1b P3-3: a refusal or a final outcome ends a run done too). Keeps the wallet's
        counters of the phase's line (`last_counters`)."""
        env = {**self.online, 'BITAGI_E3D3_PHASE': name, 'BITAGI_E3D3_RUNG': str(k)}
        if name in SENDING:
            env['BITAGI_E3D3_SEND_AUTH'] = self.send.auth()
        got = self._stage(SET_WORKER, SET_WORKER_LINES, env, [], oe.HOST_PACKAGE, oe.HOST_TEST)
        first = got['_start_ns']
        for _ in range(MAX_COMPARISONS):
            if got['prestate_receipt'] == '-':
                break
            compared = oe.run_prestate(self.pair, self.launch, self.root / 'prestate' / f'{name}-{k}-{len(self.stages)}',
                                       got['prestate_receipt'], height)
            env.update(compared['env'])
            got = self._stage(SET_WORKER, SET_WORKER_LINES, env, [], oe.HOST_PACKAGE, oe.HOST_TEST)
        if (got['phase'], got['rung'], got['rungs'], got['done']) != (name, str(k), str(len(self.fee['ladder'])), 'yes') \
                or got['prestate_receipt'] != '-':
            raise oe.Mismatch(f'L0_SET_PHASE {name} {k}')
        if name in PHASE_VERDICTS and parse_labels(got['labels'], len(self.fee['ladder']))[k]['verdict'] \
                not in PHASE_VERDICTS[name]:
            raise oe.Mismatch(f'L0_SET_PHASE_VERDICT {name} {k}')
        if name in SENDING and (got['hand_offs'] != '1' or got['submitted'] != f'r{k}:Accepted/Accepted'):
            raise oe.Mismatch(f'L0_SET_SEND {k}')
        self.got['counters'] = {'phase': name, 'rung': k, 'counters': parse_counters(got['budget_counters'])}
        return {**got, '_first_ns': first}

    def _entries(self, txid: str) -> dict:
        """Each of Node A's and Node B's mempool entry of `txid` (fee from `fees.base`, vsize), or None."""
        out = {}
        for node in self.pair.both():
            try:
                done = node.raw('getmempoolentry', txid)
            except subprocess.TimeoutExpired:
                raise node_call_timeout(node.label) from None
            if done.returncode != 0:
                if 'error code: -5' not in done.stderr:
                    raise oe.Prerequisite(f'RPC_FAILED {node.label} getmempoolentry')
                out[node.label] = None
                continue
            entry = oe.cli_result(('getmempoolentry', txid), done.stdout.strip())
            out[node.label] = {'in_mempool': True, 'fee': oe.sats(entry['fees']['base']), 'vsize': int(entry['vsize']),
                               'wtxid': entry['wtxid']}
        return out

    def _unsent(self, tip: str, spender: str | None) -> None:
        """oe's `check_nothing_sent` / `check_submitted` in their per-txid form (WRD3a1b P3-4), on Node A and
        Node B: the tip is `tip` (L0_TIP_MOVED); L0's funding output is unspent in the chain and, in the
        mempool, spent by `spender` alone (None: by nothing) (L0_FUNDING_SPENDER)."""
        outpoint = json.dumps([{'txid': self.funding['txid'], 'vout': self.funding['vout']}], separators=(',', ':'))
        for node in self.pair.both():
            if node.call('getbestblockhash') != tip:
                raise oe.Mismatch('L0_TIP_MOVED')
            if not node.call('gettxout', self.funding['txid'], str(self.funding['vout']), 'false'):
                raise oe.Mismatch('L0_FUNDING_SPENDER')
            spending = node.call('gettxspendingprevout', outpoint)
            if [entry.get('spendingtxid') for entry in spending] != [spender]:
                raise oe.Mismatch('L0_FUNDING_SPENDER')

    # The L0 thread.

    def _run(self) -> None:
        try:
            self._prepare()
            self.got['ready_ns'] = self.clock()
            self.ready_event.set()
            if not self.floor_event.wait(FLOOR_SECONDS):
                raise oe.Prerequisite('L0_FLOOR_NOT_MINED')
            if self.abort:
                raise _Aborted
            if self.pair.agreed(oe.TIP_HEIGHT) != self.floor_hash:
                raise oe.Mismatch('L0_FLOOR_NOT_G_MINUS_1')
            for k, due in self.schedule:
                if self.abort:
                    raise _Aborted
                self._release(k, due)
        except _Aborted:
            if self.error is None and not self.abort:
                self.error = oe.Prerequisite('L0_DEADLINE')   # a stage due past the attempt's deadline
        except BaseException as error:   # noqa: BLE001 - handed to the main thread
            self.error = error
        finally:
            self.ready_event.set()
            self.done_event.set()

    def _wait_until(self, at_ns: int) -> None:
        """`D.sleep_until` that `stop` ends (`_Aborted`)."""
        while not self.abort:
            left = at_ns - self.clock()
            if left <= 0:
                return
            time.sleep(min(left / 1e9, 0.25))
        raise _Aborted

    def _prepare(self) -> None:
        """At item 2's H0 − 2 tip: describe, the set charge (every rung reserved and charged before rung 0 is
        signed, 045a item 7), every rung signed (the host signs at its base's tip, H0 − 2), rung 0 imported."""
        self.constructed = self.pair.agreed(oe.CASE_CONSTRUCTION)
        self.chain, self.funding = oe.chain_facts(self.pair, self.constructed, oe.CASE_CONSTRUCTION)
        self.online = {**self.online_env, 'BITAGI_E3D3_NODE_A_PORT': str(self.pair.a.rpcport),
                       'BITAGI_E3D3_NODE_B_PORT': str(self.pair.b.rpcport), 'BITAGI_E3D3_NODE_A_LOG': self.pair.a.log_path,
                       'BITAGI_E3D3_NODE_B_LOG': self.pair.b.log_path}
        genesis = self.chain.split('\n', 1)[0].removeprefix('genesis=')
        # oe.l0_chain :2912 (describe), then :2918-2929 (the launch tree and the facts file).
        described = self._stage(oe.DESCRIBE_WORKER, oe.DESCRIBE_LINES, self.online, [], oe.HOST_PACKAGE, oe.HOST_TEST)
        self.descriptor = oe.check_descriptor(described['descriptor'], genesis)
        self.root = oe.private(self.work / 'l0')
        self.launch = oe.private(self.root / 'launch')
        oe.private(self.root / 'prestate')
        for name in ('handoff', 'outbox', 'export', 'host'):
            oe.private(self.launch / name)
        self.online['BITAGI_E3D3_LAUNCH'] = str(self.launch.resolve())
        self._unsent(self.constructed, None)   # oe.l0_chain :2915
        charged = self._offline(SET_CHARGE_WORKER, SET_CHARGE_LINES)   # oe.l0_chain :2931 (the charge), the whole set
        if not HEX64.match(charged['set_id']) or not HEX64.match(charged['budget_sha256']):
            raise oe.Mismatch('L0_SET_CHARGE')
        self.got['charged'] = charged
        self.got['rows'] = parse_rungs(charged['rungs'], self.fee['ladder'])
        self._check_charged()   # WRD3a1b P3-1: every rung, released or not
        n = len(self.fee['ladder'])
        if oe.listing(self.launch / 'handoff') != set_handoff(n):
            raise oe.Mismatch('L0_SET_HANDOFF')   # oe.l0_chain :2932 (check_boundary "charge")
        self._unsent(self.constructed, None)   # oe.l0_chain :2934
        if oe.listing(self.launch / 'outbox'):
            raise oe.Mismatch('L0_OUTBOX')   # oe.l0_chain :2935
        exports, entries = [], []
        for k in range(n):
            before = set(oe.listing(self.launch / 'outbox'))
            self._phase('set_sign', k, oe.CASE_CONSTRUCTION)   # oe.l0_chain :2937 (l0_sign at H0 − 2)
            oe.scan_key_material(self.work)   # oe.l0_chain :2938
            new = sorted(set(oe.listing(self.launch / 'outbox')) - before)
            if len(new) != 1 or not re.fullmatch(r'sign-input-[0-9a-f]{64}\.txt', new[0]):
                raise oe.Mismatch('L0_SET_OUTBOX')
            entries.append(new[0])
            if oe.listing(self.launch / 'outbox') != sorted(entries):
                raise oe.Mismatch('L0_SET_OUTBOX')
            exported = self._offline(NAMED_SIGN_WORKER, NAMED_SIGN_LINES, new[0])   # oe.l0_chain :2941
            if exported['txid'] != self.got['rows'][k]['txid']:
                raise oe.Mismatch('L0_SET_EXPORT_TXID')   # the signed rung is the charged row's
            if not re.fullmatch(r'(?:[0-9a-f]{2})+', exported['raw_tx_hex']) or \
                    hashlib.sha256(bytes.fromhex(exported['raw_tx_hex'])).hexdigest() != exported['raw_tx_sha256']:
                raise oe.Mismatch('L0_RAW_HEX')   # D3a-2b-1: the hex is the exported bytes
            exports.append(exported)
            # oe.l0_chain :2946-2950 after its offline sign stage, per rung (`_offline` scans for key material).
            if oe.listing(self.launch) != LAUNCH_DIRS:
                raise oe.Mismatch('L0_SET_DIR')
            if oe.listing(self.launch / 'export') != sorted(f"{e['candidate_id']}.export" for e in exports):
                raise oe.Mismatch('L0_SET_EXPORTS')
            if oe.listing(self.launch / 'outbox') != sorted(entries):
                raise oe.Mismatch('L0_SET_OUTBOX')
            self._unsent(self.constructed, None)
            if k == 0:
                self._phase('set_wait', 0, oe.CASE_CONSTRUCTION)   # oe.l0_chain :2958 (l0_wait), rung 0 only
                self._unsent(self.constructed, None)
        self.got['exports'] = exports
        for exported in exports:
            if any(self._entries(exported['txid']).values()):
                raise oe.Mismatch('L0_SENT_BEFORE_STEP_8')

    def _check_charged(self) -> None:
        """WRD3a1b P3-1 (A Q-L1, every rung of the set, also those charged but never released): the wallet
        row's fee and vsize and the charge base's `absolute_fee_sat` of rung k are the computed f_k and v
        (L0_FEE_MISMATCH). Keeps each rung's charge base (`L0_SET_CHARGED`, `L0_ADMISSION`)."""
        self.got['bases'] = [self._charge_base(k) for k in range(len(self.fee['ladder']))]
        for k, (row, base) in enumerate(zip(self.got['rows'], self.got['bases'])):
            f_k = self.fee['ladder'][k]
            if (row['wallet_fee_sat'], row['wallet_vsize']) != (f_k, V) or base['absolute_fee_sat'] != f_k:
                raise oe.Mismatch('L0_FEE_MISMATCH')

    def _release(self, k: int, due: int) -> None:
        """Rung k: for k ≥ 1 imported and readied right after rung k − 1's release (`set_ready`), then step 8 at
        `due` (`set_send`, to Node A and Node B only). Then both nodes hold rung k (and no longer rung k − 1),
        and the relay is polled for it (item 2's relay log for L0's rungs)."""
        txid = self.got['exports'][k]['txid']
        replaces = self.got['exports'][k - 1]['txid'] if k else None
        if k > 0:
            self._phase('set_ready', k, oe.TIP_HEIGHT)
        # oe.l0_chain :2961, after rung k's last phase before its step 8: rung k in neither mempool, rung k − 1
        # alone spending the funding output (nothing for rung 0), the tip still G − 1.
        if any(self._entries(txid).values()):
            raise oe.Mismatch('L0_SENT_BEFORE_STEP_8')
        self._unsent(self.floor_hash, replaces)
        if k > 0:
            self._rung_test(k, 'BEFORE_RELEASE')   # D3a-2b-1: rung k - 1 in both mempools, rung k not sent
            (self.sleep_until or self._wait_until)(due)
        start = self.clock()
        got = self._phase('set_send', k, oe.TIP_HEIGHT)   # oe.l0_chain :2962 (l0_broadcast after the floor, :2960)
        if got['raw_tx_sha256'] != self.got['exports'][k]['raw_tx_sha256']:
            raise oe.Mismatch('L0_BYTES')
        nodes = self._entries(txid)   # as oe.l0_chain's check_submitted (:2965), per txid: other bidders share the pools
        if not all(nodes.values()):
            raise oe.Mismatch('L0_RUNG_NOT_IN_MEMPOOL')
        if replaces is not None and any(self._entries(replaces).values()):
            raise oe.Mismatch('L0_RUNG_NOT_REPLACED')
        self._unsent(self.floor_hash, txid)   # as check_submitted: rung k alone spends it, the tip unmoved
        at_relay, waited = self._at_relay(txid)
        self.got['released'].append({
            'k': k, 'txid': txid, 'raw_tx_sha256': got['raw_tx_sha256'],
            'candidate_id': self.got['exports'][k]['candidate_id'], 'replaces': replaces, 'nodes': nodes,
            'due_ns': due, 'turn_start_ns': start, 'sent_ns': got['_end_ns'], 'at_relay': at_relay,
            'relay_waited_ns': waited})

    def _rung_test(self, k: int, when: str) -> dict:
        """D3a-2b-1: Node A's and Node B's `testmempoolaccept` of rung k's signed bytes (the named sign stage's
        `raw_tx_hex`), each node's answer kept as returned (`allowed`, `reject-reason` ...). Only while both
        nodes' tip is G - 1 (`floor`); otherwise the rung is recorded untested with its reason. A malformed
        answer is L0_RUNG_TEST."""  # L0-501 (A 6764861681): + each node's `replaces_in_mempool`, read first by :1141's condition
        export = self.got['exports'][k]
        record = {'k': k, 'txid': export['txid'], 'when': when, 'source': 'NODE_TESTMEMPOOLACCEPT', 'nodes': None,
                  'untested_reason': None}
        tips = {node.label: node.call('getbestblockhash') for node in self.pair.both()}
        if getattr(self, 'floor_hash', None) is None or set(tips.values()) != {self.floor_hash}:
            record['untested_reason'] = 'TIP_NOT_G_MINUS_1'
        else:
            nodes = {}; replaced = I2.l0_replaced_txid(self.got['exports'], self.got['released'], k, when)
            for node in self.pair.both():
                answer = node.call('testmempoolaccept', json.dumps([export['raw_tx_hex']], separators=(',', ':'))) if isinstance(seen := I2.l0_in_mempool(node, replaced), bool) else None
                if not (isinstance(answer, list) and len(answer) == 1 and isinstance(answer[0], dict)
                        and answer[0].get('txid') == export['txid'] and isinstance(answer[0].get('allowed'), bool)):
                    raise oe.Mismatch('L0_RUNG_TEST')
                nodes[node.label] = answer[0] | I2.l0_replaced_field(answer[0], seen)
            record['nodes'] = nodes
        self.got.setdefault('tests', {})[k] = record
        return record

    def _at_relay(self, txid: str) -> tuple[bool, int]:
        start = self.clock()
        if self.relay is None:
            return False, 0
        deadline = start + int(I2.REPLACED_WAIT_SECONDS * 1e9)
        while True:
            seen = txid in set(self.relay.call('getrawmempool'))
            if seen or self.clock() >= deadline:
                return seen, self.clock() - start
            time.sleep(I2.POLL)


# ---------------------------------------------------------------------------------------------------------
# One run.

def refuse_confirmatory_outside_driver(plan: dict, l0_policy: dict | None) -> None:
    """WR2b2b2c P3-5: a CONFIRMATORY plan reaches the L0 runs from the driver's `_run_l0` only, which always
    passes the policy's `l0_seat` values (`confirmatory_l0_seat`). A CONFIRMATORY plan without them (a Python
    API call: `item2.plan_run(…, 'CONFIRMATORY', l0_seat=…)`, `item4.plan_run(…, 'CONFIRMATORY', l0=True)`) is
    refused before any node, output or worker. FZ-6 n1 (A #759 issuecomment-6749449323; the B-FZ-p LATENT row): a
    CONFIRMATORY plan with values whose `exact_height_miss` is the STOP_CAMPAIGN twin (a hand-built `l0_policy`)
    is L0_STOP_CAMPAIGN_EXPLORATORY_ONLY (exit 6) there too, through the driver's one check; EXPLORATORY and
    PR_SMOKE plans still take either value."""
    if plan.get('mode') == 'CONFIRMATORY' and l0_policy is None:
        raise Refusal('L0_CONFIRMATORY_OUTSIDE_DRIVER', D.EXIT_REFUSAL)
    if plan.get('mode') == 'CONFIRMATORY':
        D.refuse_stop_twin(l0_policy['exact_height_miss'])


def seat_policy(l0_policy: dict | None, plan: dict | None = None) -> dict:
    """D3a-2b-2b: the `L0Seat` arguments a policy's `l0_seat` sets (`confirmatory_l0_seat`); none without one
    (the module defaults). B-FZ-a: `registered` only for a CONFIRMATORY plan (the label `budget_fields` writes)."""
    if l0_policy is None:
        return {}
    return {'exact_height_miss': l0_policy['exact_height_miss'], 'budget_sha256': l0_policy['budget_sha256'],
            'registered': (plan or {}).get('mode') == 'CONFIRMATORY'}


def item2_l0_run(plan: dict, seed: bytes, work: Path, log_path: Path, header: dict, node_a: Path, node_b: Path,
                 cargo: str, offline_target: Path, online_target: Path, observation_start: dict | None = None,
                 clock=None, l0_policy: dict | None = None) -> tuple[dict, dict]:
    """One item-2 run with the L0 seat (`plan_run(…, l0_seat=j)`, H0 1000) on fresh nodes under `work` (new;
    no group- or world-writable ancestor: the offline signer refuses one). Returns (the run's result or the
    refusal's code, the timing in nanoseconds: the run's start, every L0 rung signed (ready) and rung 0's
    H0 − 1 turn start)."""
    if plan.get('l0_seat') is None:
        raise invalid('ITEM2_L0_ADAPTER')
    refuse_confirmatory_outside_driver(plan, l0_policy)
    offline_env, online_env = T.envs(offline_target, online_target)
    oe.check_ancestors(work)
    work = oe.private(work)
    topology = L0Topology(node_a, node_b, work / 'nodes')
    l0_work = oe.private(work / 'l0w')
    secrets_ = oe.run_secrets(l0_work, (topology.pair,), topology.send, topology.admin)
    secrets_ = oe.Secrets(secrets_.needles + topology.needles(), secrets_.ports + topology.ports())
    seat = L0Seat(topology.pair, topology.send, l0_work, cargo, offline_env, online_env, secrets_,
                  relay=topology.nodes['relay'], clock=clock, **seat_policy(l0_policy, plan))
    needles = topology.needles() + (str(work), str(work.resolve()))
    log = D.RawLog(log_path, header, needles)
    clock = clock or CLOCK
    start = clock()
    try:
        try:
            result = I2.item2_run(plan, seed, work, log, topology, cargo, observation_start=observation_start,
                                  l0=seat)
        except Refusal as refusal:
            result = {'status': 'REFUSED', 'code': refusal.code, 'exit': refusal.exit_code}
    finally:
        log.close()
    # WRD3a1b P3-5: rung 0's H0 − 1 turn start (its `set_send`), None when nothing was released.
    released = seat.got['released']
    return result, {'start_ns': start, 'ready_ns': seat.got.get('ready_ns'),
                    'turn_start_ns': released[0]['turn_start_ns'] if released else None}


def item4_l0_run(plan: dict, seed: bytes, work: Path, log_path: Path, header: dict, node_a: Path, node_b: Path,
                 cargo: str, offline_target: Path, online_target: Path, observation_start: dict | None = None,
                 clock=None, l0_policy: dict | None = None) -> tuple[dict, dict]:
    """D3a-2b-1: one item-4 run (`claude_track_ardr_item4.plan_run(…, l0=True)`: ITEM4_SELF_DEALING,
    ITEM4_FEE_ASYMMETRY or ITEM4_CENSORSHIP, H0 1000) with the L0 seat in the project seat, on fresh nodes under
    `work`, as `item2_l0_run`. D3a-2b-2a: ITEM4_REORG too (the miner's driver user gets `invalidateblock`). Python
    API (CONFIRMATORY enters through the driver CLI only: D3a-2b-2b, `claude_track_ardr_driver._run_l0`; a
    CONFIRMATORY plan without the policy's values is refused L0_CONFIRMATORY_OUTSIDE_DRIVER, as in `item2_l0_run`).
    `item4_run` refuses a plan without `l0` (ITEM4_L0_ADAPTER). Returns (the run's result or the refusal's code,
    the timing in nanoseconds)."""
    import claude_track_ardr_item4 as I4   # here, not at the top: item 2's L0 runs never load item 4
    refuse_confirmatory_outside_driver(plan, l0_policy)
    offline_env, online_env = T.envs(offline_target, online_target)
    oe.check_ancestors(work)
    work = oe.private(work)
    # D3a-2b-2a: ITEM4_REORG's miner driver user gets `invalidateblock` (D.REORG_RPCS); no other node does.
    topology = L0Topology(node_a, node_b, work / 'nodes', reorg=plan.get('scenario') == 'ITEM4_REORG')
    l0_work = oe.private(work / 'l0w')
    secrets_ = oe.run_secrets(l0_work, (topology.pair,), topology.send, topology.admin)
    secrets_ = oe.Secrets(secrets_.needles + topology.needles(), secrets_.ports + topology.ports())
    seat = L0Seat(topology.pair, topology.send, l0_work, cargo, offline_env, online_env, secrets_,
                  relay=topology.nodes['relay'], clock=clock, **seat_policy(l0_policy, plan))
    needles = topology.needles() + (str(work), str(work.resolve()))
    log = D.RawLog(log_path, header, needles)
    clock = clock or CLOCK
    start = clock()
    try:
        try:
            result = I4.item4_run(plan, seed, work, log, topology, cargo, observation_start=observation_start,
                                  l0=seat)
        except Refusal as refusal:
            result = {'status': 'REFUSED', 'code': refusal.code, 'exit': refusal.exit_code}
    finally:
        log.close()
    released = seat.got['released']
    return result, {'start_ns': start, 'ready_ns': seat.got.get('ready_ns'),
                    'turn_start_ns': released[0]['turn_start_ns'] if released else None}


# ---------------------------------------------------------------------------------------------------------
# D3a-2b-2b (A 6557723699 Q5-Q6, corrected by 6557914275): a CONFIRMATORY run with the L0 seat (ITEM2 and the
# item-4 experiments; ITEM4_REORG with the TEST_ONLY release only since B-B1, 045b :1069) enters through the
# driver's CLI only (`claude_track_ardr_driver.run`, which imports this module inside `run`); it first asks
# `confirmatory_l0_seat`. A #258 issuecomment-6565897037 Q1: the L0 values A freezes live in the policy
# (`experiments.<E>.l0_seat`, `claude_track_ardr_driver.check_l0_seat_shape`), never in this module's constants,
# which stay the DRAFT / EXPLORATORY defaults. Without the key the run is refused L0_FREEZE_PENDING (exit 3)
# before any node, output or worker; a p_0 rule or attempt count that is not the run's is refused (exit 6);
# the run takes the policy's seat (item 2) and `exact_height_miss`, and `L0Seat` checks the product's budget
# record against the policy's `budget_sha256` after the charge (L0_POLICY_BUDGET_SHA256; `finish`, after L0's
# last release). B-FZ-a FZ-2: a `budget_sha256` that is not the product's record for the policy's
# `exact_height_miss` (`PRODUCT_BUDGET_SHA256`) is refused here already, before any node (exit 6).
CONFIRMATORY_L0_EXPERIMENTS = ('ITEM2',) + D.ITEM4_EXPERIMENTS


def confirmatory_l0_seat(experiment: str, value) -> dict:
    """D3a-2b-2b: the policy's `l0_seat` for a CONFIRMATORY run of `experiment` (the driver checked its shape),
    as the values the run uses: {'seat' (item 2, else None), 'exact_height_miss', 'budget_sha256'}."""
    if experiment not in CONFIRMATORY_L0_EXPERIMENTS:
        raise invalid('L0_CONFIRMATORY_EXPERIMENT')
    if value is None or D.pending(value):
        raise Refusal('L0_FREEZE_PENDING', D.EXIT_PREREQUISITE)
    if value['p0_rule'] != D.L0_P0_RULE:
        raise Refusal('L0_POLICY_P0_RULE', D.EXIT_REFUSAL)   # the run's p_0 is item 2's `l0_p0` (FD-CT-133)
    if value['max_gate_attempts'] != BUDGET_DRAFT['max_gate_attempts']:
        raise Refusal('L0_POLICY_ATTEMPTS', D.EXIT_REFUSAL)   # the budget record the charge writes
    if value['budget_sha256'] != PRODUCT_BUDGET_SHA256[value['exact_height_miss']]:
        raise Refusal('L0_POLICY_BUDGET_NOT_PRODUCT', D.EXIT_REFUSAL)   # B-FZ-a FZ-2: before any node
    return {'seat': value['seat'] if experiment == 'ITEM2' else None,
            'exact_height_miss': value['exact_height_miss'], 'budget_sha256': value['budget_sha256']}


# ---------------------------------------------------------------------------------------------------------
# The DRAFT CLI (D3a-1b; B's brief item 5, ARDR_RUN_V1 section 22): DRAFT / EXPLORATORY only (CONFIRMATORY is
# refused first). A CONFIRMATORY run with the L0 seat enters through the driver's CLI, which imports this
# module lazily inside `run()` as it does item2 and item4 (A #645 correction 6557914275; D3a-2b-2b), so there is
# one CONFIRMATORY entry. (The driver is not in XD-1's static import closure; this module stays out of it too:
# `test_xd1_closure_does_not_reach_this_module`.)

def cli_run(args) -> dict:
    """`run`: one item-2 run with the L0 seat (`plan_run(…, l0_seat=…)`) from a policy with ITEM2 params,
    EXPLORATORY or PR_SMOKE. CONFIRMATORY is refused before anything is read (exit 3): it enters through the
    driver's CLI only. The seat is `--l0-seat`, or with `--policy-l0-seat` (B-FZ-a FZ-1, 045b F3 command) the
    policy's own `experiments.ITEM2.l0_seat`, read through `confirmatory_l0_seat` as a CONFIRMATORY run reads
    it (its seat, `exact_height_miss` and `budget_sha256`, the digest checked before any node and against the
    product's record after the charge); its records label those values POLICY_VALUE, never REGISTERED_POLICY.
    Exactly one of the two flags (L0_SEAT_SOURCE otherwise). With `--policy-l0-seat` the policy must also be
    complete as a CONFIRMATORY one is (B-FZ-a fix round 1): no PENDING anywhere (POLICY_PENDING) and every
    experiment counted (POLICY_COUNT_UNSET), through `load_policy(complete=True)`."""
    if args.mode == 'CONFIRMATORY':
        raise Refusal('CONFIRMATORY_CAMPAIGN_NOT_BUILT', D.EXIT_PREREQUISITE)
    if args.experiment != 'ITEM2':
        raise invalid('ITEM2_L0_EXPERIMENT')
    if (args.l0_seat is None) == (not args.policy_l0_seat):
        raise invalid('L0_SEAT_SOURCE')
    loaded = D.load_policy(args.mode, args.policy, args.experiment, args.registration, args.registration_sha256,
                           complete=args.policy_l0_seat)
    l0_policy = confirmatory_l0_seat(args.experiment, loaded['l0_seat']) if args.policy_l0_seat else None
    seat = args.l0_seat if l0_policy is None else l0_policy['seat']
    if loaded['params'] is None:
        raise invalid('ITEM2_L0_PARAMS')   # D2-3b's item-2 run needs b and H0
    if loaded['seed'] is None:
        raise Refusal('SEED_PENDING', D.EXIT_PREREQUISITE)
    if D.pending(loaded['params']):
        raise Refusal('POLICY_PARAMS_PENDING', D.EXIT_PREREQUISITE)
    plan = I2.plan_run(loaded['seed'], args.run_index, loaded['params'], args.mode, l0_seat=seat)
    for path in (args.out, args.work):
        if path.exists():
            raise Refusal('OUTPUT_EXISTS', D.EXIT_PREREQUISITE)
    started = args.started_at or {'source': 'LOCAL_EXPLORATORY', 'utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    result, _ = item2_l0_run(plan, loaded['seed'], args.work, args.out, D.log_header(loaded), args.node_a,
                             args.node_b, args.cargo, args.offline_target, args.online_target,
                             observation_start=started, l0_policy=l0_policy)
    if result.get('status') == 'REFUSED':
        raise Refusal(result['code'], result['exit'])
    return {k: result[k] for k in ('status', 'gate', 'winner', 'predicted_candidates', 'observed_candidates',
                                   'l0_seat', 'l0_released_ks', 'l0_charged_not_released')}


def seat_index(text: str) -> int:
    """`--l0-seat`: a seat index 0-4 as a plain decimal (the plan checks the private seat)."""
    if not re.fullmatch(r'[0-4]', text):
        raise argparse.ArgumentTypeError('a seat index 0-4')
    return int(text)


def parser() -> argparse.ArgumentParser:
    top = argparse.ArgumentParser(description='CT-P5-001 D3a-1b: one item-2 run with the L0 project seat (DRAFT)')
    sub = top.add_subparsers(dest='command', required=True)
    p = sub.add_parser('run')
    p.add_argument('--mode', required=True, choices=D.MODES)
    p.add_argument('--policy', required=True, type=Path)
    p.add_argument('--experiment', required=True, choices=D.EXPERIMENTS)
    p.add_argument('--registration', type=Path)
    p.add_argument('--registration-sha256')
    p.add_argument('--run-index', type=int, default=0)
    p.add_argument('--l0-seat', type=seat_index, help='DRAFT: the PUBLIC seat L0 takes (0-4)')
    p.add_argument('--policy-l0-seat', action='store_true',
                   help="apply the policy's experiments.ITEM2.l0_seat instead (B-FZ-a; labelled POLICY_VALUE)")
    p.add_argument('--node-a', required=True, type=Path, help='Core 31.1 bin dir (miner, relay, Node A)')
    p.add_argument('--node-b', required=True, type=Path, help='Core 30.3 bin dir (Node B)')
    p.add_argument('--work', required=True, type=Path, help='new directory (no group- or world-writable ancestor)')
    p.add_argument('--out', required=True, type=Path, help='new raw-log file')
    p.add_argument('--started-at', type=D.started_at, help="the GitHub job's started_at (UTC)")
    p.add_argument('--cargo', default='cargo')
    p.add_argument('--offline-target', type=Path, default=oe.ROOT / 'target/offline-build')
    p.add_argument('--online-target', type=Path, default=oe.ROOT / 'target')
    return top


def main(argv: list[str] | None = None) -> int:
    if not __debug__:
        print(json.dumps({'result': 'FAIL', 'code': 'OPTIMIZED_PYTHON', 'exit': D.EXIT_REFUSAL}))
        return D.EXIT_REFUSAL
    args = parser().parse_args(argv)
    for name in ('node_a', 'node_b', 'work', 'out', 'offline_target', 'online_target'):
        setattr(args, name, getattr(args, name).absolute())
    try:
        try:
            summary = cli_run(args)
        except Refusal:
            raise
        except oe.Prerequisite as error:   # the message can hold a node's stderr or a path: codes only
            raise Refusal(D.error_code('PREREQUISITE', error), D.EXIT_PREREQUISITE) from None
        except oe.Mismatch as error:
            raise Refusal(D.error_code('MISMATCH', error), D.EXIT_VALIDATION) from None
    except Refusal as refusal:
        print(json.dumps({'result': 'FAIL', 'code': refusal.code, 'exit': refusal.exit_code}, sort_keys=True))
        return refusal.exit_code
    print(json.dumps({'result': 'DONE', **summary, 'exit': D.EXIT_DONE}, sort_keys=True))
    return D.EXIT_DONE


if __name__ == '__main__':
    import claude_track_exit
    claude_track_exit.run(main)
