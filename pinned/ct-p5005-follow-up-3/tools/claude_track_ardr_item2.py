#!/usr/bin/env python3
"""CT-P5-001 D2-3b: the ARDR item-2 run (release schedule, replacement rungs, t_G) on D1's topology.

Class T Regtest development evidence only; never mainnet, never S17-PREP, and no ARDR verdict. Sources: A's
answer #258 issuecomment-6543158220 (Q4: the item-2 mapping; Q5: the time rule), A's correction -6546351822
(RELEASE_NOT_IN_TEMPLATE checks each bidder's last released rung only), B's fact memo -6542840327 (group 나),
and the 045b draft sections 4.5 and 4.6 (`CT-P3-045b_PREREGISTRATION_DRAFT_EN.md`), a draft input, not frozen
bytes. Every value here is PENDING_FREEZE / DRAFT. Format: `docs/claude-track/formats/ARDR_RUN_V1.md`
section 20.

One item-2 run is one contested gate of a new chain, run index r = 0 … 199 (A Q4):

- Even r: private present, seat 0 (W00) PRIVATE, seats 1-4 (W01-W04) PUBLIC. r = 0, 2, …, 98 are the 50
  order-constrained runs (`PRIVATE_FEE`, then `PUBLIC_FEE_1..4` in [private fee, 4b]); r = 100 … 198 draw
  `BID_FEE_0..4`. Odd r: five PUBLIC seats W00-W04 with `BID_FEE_0..4`. Where L0 sits is A's at the freeze
  (`L0_SEAT`, PENDING). D3a-1a (A -6551547851 Q1, Q2, Q7): a DRAFT `l0_seat` (the Python API, and the L0
  tool's own DRAFT CLI) puts the L0 project bidder (`claude_track_ardr_l0`) in one PUBLIC seat: that seat
  draws no fee, and the run needs H0 = 1000 (`L0_H0`; ARDR_RUN_V1 section 22). D3a-1b (A -6552107427): its
  ladder is its conflict set (`l0_ladder`, the bidders' `ladder` at L0's p_0, FD-CT-133; `check_l0_set`), every
  rung charged before rung 0 is signed; its rungs are released by the rule below, each by L0's own step 8 to
  Node A and Node B; the rungs with rung_seconds × k ≥ t_G are charged but not released (GATE_END
  `l0_charged_not_released`).
- t_G = `GATE_INTERVAL` + 1 s. One monotonic clock (D.CLOCK, the driver and the miner process on one host).
  t0 = the miner's CLOCK reading when it sends block G − 1 (`t_submit_ns`). Rung 0 is released once G − 1 is
  at the relay node (and at Node A and Node B, whose testmempoolaccept needs it); rung k ≥ 1 at
  t0 + 60k s, only for 60k < t_G. The set of rungs is fixed from t_G before any node starts (the ladder
  lengths once Node A's incremental relay fee is read, before G − 1). Block G's template is taken at
  t0 + t_G (`D.mine(at_ns=…)`).
- Every rung of a bidder spends the same funding output, so rung k replaces rung k − 1: public rungs at the
  relay (`sendrawtransaction`), the private rung in the miner process (`replace`). Each release is first
  tested with testmempoolaccept on Node A and Node B.
- RELEASE_NOT_IN_TEMPLATE (A -6546351822): only each bidder's LAST released rung is checked, a public one
  against block G's template, the private one against the private set the miner process adds. A miss
  EXCLUDES the gate (RUN_END EXCLUDED, exit 2). Earlier rungs are observation candidates from the relay
  log (the relay's mempool after each release step), not from the template.
- WR23b: a release sent at or after t0 + t_G EXCLUDES the gate (RELEASE_AFTER_G; after RELEASE_NOT_IN_TEMPLATE,
  before G_LATE: `gate_code`); a public rung k ≥ 1 waits (up to `REPLACED_WAIT_SECONDS`) for rung k − 1 in
  Node A's and Node B's mempools, else the gate is EXCLUDED (REPLACED_RUNG_NOT_IN_MEMPOOL); the topology must
  carry the loopback noban whitelist (ITEM2_TOPOLOGY_WHITELIST).
- ITEM2 CONFIRMATORY runs only with the L0 seat (045b 4.5 counts PROJECT attempts), through the driver's CLI
  (D3a-2b-2b, `claude_track_ardr_driver._run_l0`), on the seat the policy's `experiments.ITEM2.l0_seat.seat`
  names (A #258 issuecomment-6565897037 Q1; `L0_SEAT` stays the DRAFT / EXPLORATORY default only): without the
  key the driver refuses L0_FREEZE_PENDING (exit 3); a PENDING key is refused POLICY_PENDING (exit 3) earlier,
  by the driver's policy read. `plan_run` refuses CONFIRMATORY without a seat (CONFIRMATORY_NEEDS_L0_SEAT,
  exit 3) and with a schedule override (ITEM2_OVERRIDE_CONFIRMATORY).

Exit codes (AGENTS.md section 12) as D1's. Optimized Python (-O) is refused. Stdlib only. TEST_ONLY material
only: every key is a TEST_ONLY key from the policy seed (DRAFT rule, PENDING_FREEZE).
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).absolute().parent))
import claude_track_ardr_bidders as B  # noqa: E402
import claude_track_ardr_campaign as C  # noqa: E402
import claude_track_ardr_driver as D  # noqa: E402
import claude_track_regtest_offline_export as oe  # noqa: E402

Refusal, invalid = D.Refusal, D.invalid

ITEM2_RUNS = 200            # A Q4: r = 0 … 199, one contested gate each (045b 4.6: 100 per condition)
CONSTRAINED_RUNS = 50       # 045b 4.6: the first 50 private-present runs (r = 0, 2, …, 98)
SEATS = 5                   # 045b 4.6: 5 bidders per gate, bidder 0 private when present
RUNG_SECONDS = 60           # 045b 4.6: rung k ≥ 1 exactly 60 × k seconds after G − 1
G_LATE_NS = 1_000_000_000   # DEFAULT (B): block G's template taken 1 s or more after t0 + t_G is G_LATE
L0_SEAT = 'PENDING_FREEZE'  # A Q4: the public seat L0 takes is decided at the freeze with D3a-1
L0_H0 = oe.GATE             # A Q2 (-6551547851): H0 = 1000; the L0 profile equals the item-2 replay's only then
L0_KIND, L0_WALLET = 'L0_PROJECT', 'L0'


def l0_p0(b: int) -> int:
    """L0's p_0 (FD-CT-133, #807; rule MAX_P0_TWO_RUNGS): the largest integer p_0 >= 2b whose 045b :537 ladder has
    two rungs, at i = 0 and v = 213 (`B.l0_p0`, the one source; was ceil(2.5 b), A -6552107427 Q-L2)."""
    if not (type(b) is int and b >= 1):
        raise invalid('ITEM2_L0_FEE_INPUT')
    return B.l0_p0(b, B.CANDIDATE_VSIZE)


def l0_ladder(b: int, i: int) -> list[int]:
    """L0's ladder is the bidders' `ladder` (045b :537; WRD3a1a P3-7) at `l0_p0(b)`. FD-CT-133 (#807, A QL-1): at
    the run's `i` it must be two rungs whose last is the cap fee floor(4b × v / 1000), else NOT_TWO_RUNGS before
    the seat's charge, signing or broadcast (`_gate`'s fund and setup run first; Desktop #823). A b with
    no two-rung p_0 (b × v below about 667, e.g. b = 1) is `l0_p0`'s L0_P0_NO_TWO_RUNGS."""
    fees = B.ladder(l0_p0(b), b, i, B.CANDIDATE_VSIZE)
    if len(fees) != 2 or fees[-1] != 4 * b * B.CANDIDATE_VSIZE // 1000:
        raise invalid('ITEM2_L0_LADDER_NOT_TWO_RUNGS')
    return fees


# D3a-1b: what the wallet refuses of the L0 seat's conflict set. B-FZ-p: A's frozen Class T L0 budget record's
# `max_fee_per_candidate_sat` and `max_rungs_per_conflict_set` 8 (045b :537 rung 7); before B-FZ-p the Q1 draft
# record's (A #258 issuecomment-6545342828, -6552107427 Q-L3). test_ardr_l0 ties both to the record's bytes.
L0_MAX_FEE_PER_CANDIDATE_SAT = 30_000   # B-FZ-p: A's frozen Class T L0 record (was the Q1 draft's 100,000)
L0_MAX_SET_RUNGS = 8
MINER_POLICY = 'ITEM2_DEFAULT'
POLL = C.POLL_SECONDS
REPLACED_WAIT_SECONDS = 5.0  # DEFAULT (WR23b P3-4): how long a public rung k ≥ 1 waits for rung k − 1 at A and B
ROLES = ('miner', 'relay', 'A', 'B')


# ---------------------------------------------------------------------------------------------------------
# The plan: everything fixed before any node starts.

def condition(run: int) -> dict:
    """Private present on even r; the 50 order-constrained runs are r = 0, 2, …, 98 (A Q4)."""
    if not (type(run) is int and 0 <= run < ITEM2_RUNS):
        raise invalid('ITEM2_RUN')
    present = run % 2 == 0
    return {'private_present': present, 'order_constrained': present and run // 2 < CONSTRAINED_RUNS}


def check_l0_seat(run: int, l0_seat) -> None:
    """D3a-1a: the L0 seat is a PUBLIC seat index of run r (never seat 0 of an even run, the private seat)."""
    if not (type(l0_seat) is int and 0 <= l0_seat < SEATS):
        raise invalid('ITEM2_L0_SEAT')
    if condition(run)['private_present'] and l0_seat == 0:
        raise invalid('ITEM2_L0_SEAT_PRIVATE')


def item2_bidders(run: int, l0_seat: int | None = None) -> dict:
    """The run's bidder list: one gate (number r), seats S0-S4 with wallets W00-W04; S0 PRIVATE when the
    private bidder is present (045b 4.6: bidder 0). D3a-1a: seat `l0_seat` is the L0 project bidder
    (`L0_PROJECT`, wallet `L0`, PUBLIC)."""
    present = condition(run)['private_present']
    seats = [{'seat': f'S{j}', 'kind': 'SYNTHETIC', 'wallet': B.wallet_id(j),
              'path': 'PRIVATE' if present and j == 0 else 'PUBLIC'} for j in range(SEATS)]
    if l0_seat is not None:
        check_l0_seat(run, l0_seat)
        seats[l0_seat] = {'seat': f'S{l0_seat}', 'kind': L0_KIND, 'wallet': L0_WALLET, 'path': 'PUBLIC'}
    doc = {'schema': B.BIDDERS_SCHEMA, 'gates': [{'gate': run, 'seats': seats}]}
    B.parse_bidders(json.dumps(doc).encode('ascii'), l0=l0_seat is not None)
    return doc


def feerates(seed: bytes, run: int, b: int, l0_seat: int | None = None) -> tuple[list[int | None], list[dict]]:
    """Seat j's rung-0 feerate p_0 (sat/kvB) and the draws. Order-constrained: the private p = b +
    `PRIVATE_FEE` (n = b + 1), public j = p + `PUBLIC_FEE_j` (n = 4b − p + 1). Otherwise b + `BID_FEE_j`
    (n = 3b + 1). D3a-1a (A Q1): the L0 seat draws nothing (its feerate is None: the product sets its fee);
    every other seat's draw is the one without L0 (each label is drawn on its own)."""
    if not (type(b) is int and b >= 1):
        raise invalid('PARAM_B')
    draws = []

    def one(label: str, n: int, base: int) -> int:
        value, k = D.draw(seed, 'ITEM2', run, label, n)
        draws.append({'e': 'ITEM2', 'r': run, 'label': label, 'n': n, 'k': k, 'value': value,
                      'feerate': base + value})
        return base + value

    if condition(run)['order_constrained']:
        private = one('PRIVATE_FEE', b + 1, b)
        rates = [private] + [None if j == l0_seat else one(f'PUBLIC_FEE_{j}', 4 * b - private + 1, private)
                             for j in range(1, SEATS)]
    else:
        rates = [None if j == l0_seat else one(f'BID_FEE_{j}', 3 * b + 1, b) for j in range(SEATS)]
    return rates, draws


def check_l0_set(fees: list[int]) -> list[int]:
    """D3a-1b: L0's conflict set (its ladder, `l0_ladder`) is refused where the wallet would refuse it
    (ITEM2_L0_SET_REFUSED): more than `L0_MAX_SET_RUNGS` rungs, or a rung above the frozen record's
    `max_fee_per_candidate_sat` (B-FZ-p; a ladder not of two rungs is `l0_ladder`'s refusal, FD-CT-133)."""
    if not fees or len(fees) > L0_MAX_SET_RUNGS or max(fees) > L0_MAX_FEE_PER_CANDIDATE_SAT:
        raise invalid('ITEM2_L0_SET_REFUSED')
    return fees


def release_rungs(t_gate: int, rung_seconds: int = RUNG_SECONDS) -> list[int]:
    """The rung numbers released at all: k with rung_seconds × k < t_G (rung 0 always, t_G ≥ 1), at most
    rung 7 (045b 4.6)."""
    if not (type(t_gate) is int and t_gate >= 1 and type(rung_seconds) is int and rung_seconds >= 1):
        raise invalid('ITEM2_SCHEDULE')
    return [k for k in range(B.MAX_RUNG + 1) if rung_seconds * k < t_gate]


def schedule(ks: list[int], ladders: list[list[int]], rung_seconds: int = RUNG_SECONDS) -> list[dict]:
    """The release steps: for each k in `ks`, the seats whose ladder has rung k, released k × rung_seconds
    after t0 (rung 0: when G − 1 is at the relay)."""
    rounds = []
    for k in ks:
        seats = [j for j, fees in enumerate(ladders) if k < len(fees)]
        if seats:
            rounds.append({'k': k, 'offset_seconds': rung_seconds * k, 'seats': seats})
    return rounds


def predicted_candidates(rounds: list[dict]) -> int:
    """045b 4.6: the rungs released strictly before t_G, summed over bidders."""
    return sum(len(r['seats']) for r in rounds)


# The G − 1 block is prepared on its own after the setup and funding blocks (_gate), so item 2 needs one more
# block than the shared check's MIN_H0 (setup 103, fan-out 104, owner 105): H0 ≥ 107. The driver's
# check_params refuses it for ITEM2 (check-policy and every run); plan_run checks it again.
ITEM2_MIN_H0 = D.ITEM2_MIN_H0


def plan_run(seed: bytes, run: int, params: dict, mode: str, override: dict | None = None,
             l0_seat: int | None = None) -> dict:
    """Everything fixed before any node starts: the condition, the bidders, the fee draws, t_G and the rung
    numbers released. `override` (`t_gate_seconds`, `rung_seconds`; the Python API only, never the driver
    CLI or the policy) shortens the schedule for tests and exploration; it is refused in CONFIRMATORY and
    marked DRAFT_OVERRIDE in the log. `l0_seat` (D3a-1a, DRAFT, the Python API; D3a-2b-2b: the driver's
    CONFIRMATORY run passes the policy's `l0_seat.seat`): the PUBLIC seat the L0 project bidder takes; the run then
    needs H0 = `L0_H0` (ITEM2_L0_H0). CONFIRMATORY needs the seat (CONFIRMATORY_NEEDS_L0_SEAT, exit 3) and no
    override (ITEM2_OVERRIDE_CONFIRMATORY)."""
    if mode == 'CONFIRMATORY' and l0_seat is None:
        raise Refusal('CONFIRMATORY_NEEDS_L0_SEAT', D.EXIT_PREREQUISITE)   # 045b 4.5 counts PROJECT attempts
    if mode == 'CONFIRMATORY' and override is not None:
        raise invalid('ITEM2_OVERRIDE_CONFIRMATORY')
    if mode not in D.MODES:
        raise invalid('MODE')
    if not (isinstance(params, dict) and set(params) == set(D.PARAM_KEYS)):
        raise invalid('POLICY_PARAMS')
    if D.pending(params):
        raise Refusal('POLICY_PARAMS_PENDING', D.EXIT_PREREQUISITE)
    D.check_params('ITEM2', params)
    b, h0 = params['b'], params['H0']
    if h0 < ITEM2_MIN_H0:
        raise invalid('H0_TOO_LOW')   # Codex r4433308775: a defence after check_params, before any node
    if l0_seat is not None:
        check_l0_seat(run, l0_seat)
        if h0 != L0_H0:
            raise invalid('ITEM2_L0_H0')   # A Q2: L0's profile (H0 1000) must be the replay's deployment
        # before any node: the L0 seat has a rung 0 (rung 0 does not depend on i), and D3a-1b: its set with
        # i = 0 is one the wallet takes (the start checks it again with the real i).
        check_l0_set(l0_ladder(b, 0))
    t_gate, k = D.gate_interval_seconds(seed, run)
    drawn = {'e': 'ITEM2', 'r': run, 'label': 'GATE_INTERVAL', 'k': k, 'value': t_gate - 1, 't_gate_seconds': t_gate}
    rung_seconds = RUNG_SECONDS
    if override is not None:
        if not (isinstance(override, dict) and set(override) == {'t_gate_seconds', 'rung_seconds'}):
            raise invalid('ITEM2_SCHEDULE_OVERRIDE')
        t_gate, rung_seconds = override['t_gate_seconds'], override['rung_seconds']
    ks = release_rungs(t_gate, rung_seconds)
    rates, draws = feerates(seed, run, b, l0_seat)
    if l0_seat is None and not any(B.ladder(p, b, 0, B.CANDIDATE_VSIZE) for p in rates):
        raise invalid(f'RUN_GATE_NO_BID_G{run}')   # as D2-1's plan_gates: no seat can bid (the L0 seat always bids)
    return {'run': run, 'mode': mode, 'b': b, 'H0': h0, 'params': dict(params), **condition(run),
            'bidders': item2_bidders(run, l0_seat), 'feerates': rates, 'draws': draws, 'gate_interval': drawn,
            't_gate_seconds': t_gate, 'rung_seconds': rung_seconds, 'release_ks': ks,
            'override': override is not None, 'fault': None, 'l0_seat': l0_seat}


# ---------------------------------------------------------------------------------------------------------
# The check of A -6546351822.

def release_misses(last: dict, template: dict, private_set: list[dict]) -> list[dict]:
    """Each bidder's LAST released rung (`last`: seat → {"txid", "path", "k"}) against block G: a PUBLIC rung
    must be in the template, the PRIVATE rung in the private set the miner process added. Returns the
    misses (empty: the gate is not excluded). Earlier rungs are not checked here."""
    listed = {item['txid'] for item in template['transactions']}
    private = {item['txid'] for item in private_set}
    misses = []
    for seat in sorted(last):
        rung = last[seat]
        where = private if rung['path'] == 'PRIVATE' else listed
        if rung['txid'] not in where:
            misses.append({'seat': seat, **rung})
    return misses


def late_releases(released: list[dict], due_g: int) -> list[dict]:
    """The releases sent at or after t0 + t_G (WR23b P3-1; 045b 4.6: a rung is released while block G has not
    been produced, and the prediction counts rungs released strictly before t_G). `sent_ns` is the release's
    CLOCK reading just before the hand-off."""
    return [{'seat': r['seat'], 'txid': r['txid'], 'k': r['k'], 'sent_ns': r['sent_ns'], 'due_ns': r['due_ns'],
             'g_due_ns': due_g} for r in released if r['sent_ns'] >= due_g]


def gate_code(misses: list, late: list, lag_ns: int) -> str | None:
    """The gate's exclusion code after block G, or None (OBSERVED). Precedence: RELEASE_NOT_IN_TEMPLATE, then
    RELEASE_AFTER_G, then G_LATE (block G's template taken `G_LATE_NS` or more after t0 + t_G)."""
    if misses:
        return 'RELEASE_NOT_IN_TEMPLATE'
    if late:
        return 'RELEASE_AFTER_G'
    if lag_ns >= G_LATE_NS:
        return 'G_LATE'
    return None


def code_seats(code: str | None, misses: list, late: list) -> list[str]:
    """D3a-1a (A Q7): the seats behind the gate's exclusion code, so the judge can report exclusions per seat
    and per code (the L0 seat on its own line). G_LATE is the miner's, no seat's."""
    if code == 'RELEASE_NOT_IN_TEMPLATE':
        return sorted({m['seat'] for m in misses})
    if code == 'RELEASE_AFTER_G':
        return sorted({r['seat'] for r in late})
    return []


class GateExcluded(Exception):
    """A gate excluded during its release steps (REPLACED_RUNG_NOT_IN_MEMPOOL): no block G is mined."""

    def __init__(self, code: str, detail: dict):
        super().__init__(code)
        self.code, self.detail = code, detail


def check_topology(topology) -> dict[str, list[str]]:
    """WR23b P3-3: the item-2 run needs the four nodes with the loopback noban whitelist (A Q5). Returns what
    each node is really started with (RUN_START `p2p_arguments`)."""
    nodes = getattr(topology, 'nodes', None)
    if not (isinstance(nodes, dict) and set(nodes) == set(ROLES)):
        raise invalid('ITEM2_TOPOLOGY_WHITELIST')
    arguments = {role: list(nodes[role].p2p_arguments()) for role in ROLES}
    if any(args != [D.P2P_WHITELIST] for args in arguments.values()):
        raise invalid('ITEM2_TOPOLOGY_WHITELIST')
    return arguments


# ---------------------------------------------------------------------------------------------------------
# The run.

class _Prepared:
    """D.mine's `miner` for block G − 1: the block the miner process already built (`prepare`) is sent."""

    def __init__(self, miner: D.MinerProcess):
        self.miner = miner

    def build_block(self) -> dict:
        return self.miner.submit_prepared()


def build_ladders(worker: B.Worker, bids: list[dict], gate_height: int, tip: tuple[int, str], funding: dict,
                  plan: dict) -> dict[int, list[dict]]:
    """Every bidder's ladder in one worker call (one BUILD line per bidder, all on G − 1's hash). Checks as
    `Worker.build`: one RUNG per fee, the txid of the bytes, the campaign's vsize, every rung spending the
    bidder's one funding output."""
    lines = []
    for bid in bids:
        s, f = bid['seat'], funding[(bid['seat']['wallet'], bid['gate'])]
        lines.append(['BUILD', s['kind'], s['wallet'], gate_height, tip[0], tip[1], f['txid'], f['vout'],
                      f['value'], f['height'], B.seat_anchor_label(plan, s, 0), ','.join(map(str, bid['fees'])),
                      '-'])
    rows = worker.ask(lines)
    keys = ('kind', 'set', 'wallet', 'gate', 'rung', 'fee', 'txid', 'vsize', 'raw_sha256', 'ledger_id',
            'candidate_id', 'lineage', 'hex')
    out: dict[int, list[dict]] = {}
    at = 0
    for bid in bids:
        part = [dict(zip(keys, row)) for row in rows[at:at + len(bid['fees'])]]
        at += len(bid['fees'])
        s = bid['seat']
        if len(part) != len(bid['fees']) or any(r['kind'] != 'RUNG' or r['wallet'] != s['wallet'] for r in part):
            raise invalid('WORKER_RUNG')
        f = funding[(s['wallet'], bid['gate'])]
        for k, r in enumerate(part):
            r.pop('kind')
            for name in ('gate', 'rung', 'fee', 'vsize'):
                r[name] = int(r[name])
            tx = D.Tx(bytes.fromhex(r['hex']))
            if tx.txid != r['txid'] or r['rung'] != k or r['fee'] != bid['fees'][k]:
                raise invalid('WORKER_TXID')
            if r['vsize'] != B.CANDIDATE_VSIZE:
                raise invalid('CANDIDATE_VSIZE')
            if tx.inputs != [(f['txid'], f['vout'])]:
                raise invalid('RUNG_FUNDING')   # every rung spends the same output: rung k replaces k − 1
        out[bid['j']] = part
    if at != len(rows):
        raise invalid('WORKER_RUNG')
    return out


def new_timing() -> dict:
    return {'setup_ns': 0, 'build_ns': 0, 'release_ns': 0, 'mine_ns': 0, 'mine_blocks': 0, 'birth_ns': 0,
            'birth_calls': 0, 'g_lag_ns': None, 'total_ns': 0}


def l0_seat_source(plan: dict, l0=None) -> str:
    """RUN_START's `l0_seat_source` (#667 A integration check P3-2): PENDING_FREEZE without a seat; in
    CONFIRMATORY the seat is the registered policy's `experiments.ITEM2.l0_seat.seat` (only the driver's
    `_run_l0` builds such a plan and reaches the run with the policy's values: `item2_l0_run` refuses it
    otherwise, L0_CONFIRMATORY_OUTSIDE_DRIVER), REGISTERED_POLICY. Outside CONFIRMATORY (B-FZ-a; #667 A
    6571519328 P3-1, the same rule as L0_LAUNCH_START's `budget_source`): POLICY_VALUE when the L0 seat runs
    with a policy's `l0_seat` values (the L0 CLI's `--policy-l0-seat`, which takes the policy's seat), else the
    Python API's DRAFT_PARAMETER."""
    if plan.get('l0_seat') is None:
        source = 'PENDING_FREEZE'
    elif plan.get('mode') == 'CONFIRMATORY':
        source = 'REGISTERED_POLICY'
    elif getattr(l0, 'budget_sha256', None) is not None:
        source = 'POLICY_VALUE'
    else:
        source = 'DRAFT_PARAMETER'
    return source   # a log value, not a refusal code (DocTables reads `return '<CODE>'` as one)


def item2_run(plan: dict, seed: bytes, work: Path, log: D.RawLog, topology: D.Topology, cargo: str,
              observation_start: dict | None = None, l0=None) -> dict:
    """One item-2 run on a not yet started `topology` (built with `p2p_whitelist=True`; otherwise
    ITEM2_TOPOLOGY_WHITELIST before anything starts). Returns the summary of RUN_END. A gate excluded
    (RELEASE_NOT_IN_TEMPLATE, RELEASE_AFTER_G, G_LATE, REPLACED_RUNG_NOT_IN_MEMPOOL) writes GATE_END EXCLUDED
    and RUN_END EXCLUDED, then raises that code (exit 2). D3a-1a: `l0` is the L0 seat's adapter
    (`claude_track_ardr_l0.L0Seat`) exactly when the plan has an `l0_seat` (ITEM2_L0_ADAPTER otherwise)."""
    if (plan.get('l0_seat') is None) != (l0 is None):
        raise invalid('ITEM2_L0_ADAPTER')
    p2p_arguments = check_topology(topology)
    run = plan['run']
    unit = D.unit_id('ITEM2', run, gate=run)
    run_unit = D.unit_id('ITEM2', run)
    worker_dir = work / 'worker'
    worker_dir.mkdir()
    worker = B.Worker(cargo, seed, run, plan['H0'], worker_dir)
    timing = new_timing()
    t_start = D.CLOCK()
    miner = None
    ended = [False]
    phase = ['SETUP']
    failed: list[BaseException] = []
    try:
        try:
            log.write('RUN_START', run_unit,
                      observation_start=observation_start or {'source': 'LOCAL_EXPLORATORY', 'utc': None},
                      miner_policy=MINER_POLICY, node_versions=D.ROLE_VERSIONS, params=plan['params'],
                      gates=[run], private_present=plan['private_present'],
                      order_constrained=plan['order_constrained'], bidders_sha256=C.doc_sha256(plan['bidders']),
                      t_gate_seconds=plan['t_gate_seconds'], rung_seconds=plan['rung_seconds'],
                      release_ks=plan['release_ks'],
                      l0_seat=L0_SEAT if plan.get('l0_seat') is None else plan['l0_seat'],
                      l0_seat_source=l0_seat_source(plan, l0),
                      schedule_source='DRAFT_OVERRIDE' if plan['override'] else 'GATE_INTERVAL_DRAW',
                      p2p_arguments=p2p_arguments)
            log.write('DRAW', run_unit, **plan['gate_interval'], applied=not plan['override'])
            log.write('BIDDERS', run_unit, bidders=plan['bidders'], bidders_sha256=C.doc_sha256(plan['bidders']),
                      draws=plan['draws'], feerates=plan['feerates'])
            topology.start()
            nodes = topology.nodes
            miner = D.MinerProcess(nodes['miner'], MINER_POLICY)
            result = _gate(plan, seed, log, unit, run_unit, nodes, miner, worker, timing, ended, phase, l0)
            timing['total_ns'] = D.CLOCK() - t_start
            phase[0] = 'END'
            log.write('RUN_END', run_unit, status=result['status'], timing=timing,
                      **{k: v for k, v in result.items() if k != 'status'})
            ended[0] = True
            if result['status'] != 'DONE':
                raise invalid(result['code'])
            return {**result, 'timing': timing}
        except BaseException as error:
            failed.append(error)
            if isinstance(error, Exception) and not ended[0]:
                try:
                    log.write('RUN_END', run_unit, status='FAILED', code=C.failure_code(error), phase=phase[0],
                              timing=timing, excluded_gates=[run],
                              excluded_observation_ids=[observation_id(run)])
                except Exception:   # noqa: BLE001 - the original error is the one reported
                    pass
            raise
    finally:
        try:
            if l0 is not None:
                try:
                    l0.stop()   # its thread ends before the nodes stop
                except Exception as stop_error:
                    if not failed:
                        raise
                    # WRD3a1a P3-2: the run's own failure stays the one raised; the stop failure is logged
                    # and chained to it (its __context__ and a note), never put in its place.
                    try:
                        log.write('L0_STOP_FAILED', run_unit, code=C.failure_code(stop_error),
                                  failure=C.failure_code(failed[0]))
                    except Exception:   # noqa: BLE001 - the original error is the one reported
                        pass
                    failed[0].add_note(f'L0 stop: {C.failure_code(stop_error)}')
                    raise failed[0]   # implicit chaining: its __context__ is the stop failure
        finally:
            if miner is not None:
                miner.stop()
            topology.stop()
            shutil.rmtree(worker_dir, ignore_errors=True)


def observation_id(run: int) -> str:
    """The item-2 unit is the run (one gate): D4's run-level id `OBS-<e><run:07>`."""
    return 'OBS-%d%07d' % (D.EXPERIMENTS.index('ITEM2') + 1, run)


def _setup(plan, log, run_unit, nodes, miner, held, last, timing, chain, worker, gates):
    """Setup blocks, the bidders' keys and funding (as D2-3a's campaign), then blocks to G − 2."""
    coinbases = []
    for _ in range(D.SETUP_BLOCKS):
        block = _mine(log, run_unit, nodes, miner, held, last, timing, chain)
        coinbases.append((block['coinbase_txid'], block['coinbase_value']))
    seats = {s['wallet']: s for g in gates for s in g['seats']}
    keys = worker.keys([(s['kind'], w, B.seat_anchor_label(plan['assignment'], s, 0)) for w, s in seats.items()])
    built = B.build_funding(B.funding_layout(plan['assignment'], gates), (coinbases[0][0], 0), coinbases[0][1],
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
        D.wait_until(lambda: set(sent) <= set(nodes['miner'].call('getrawmempool')), 'the funding at the miner',
                     120.0, POLL)
        block = _mine(log, run_unit, nodes, miner, held, last, timing, chain)
        for f in funding.values():
            if f['txid'] in sent:
                f['height'] = block['height']
    if block['height'] >= plan['H0'] - 1:
        raise invalid('H0_TOO_LOW')   # G − 1 is prepared on its own, after the funding blocks
    while block['height'] < plan['H0'] - 2:
        block = _mine(log, run_unit, nodes, miner, held, last, timing, chain)
    return funding


def _mine(log, unit, nodes, miner, held, last, timing, chain, at_ns=None):
    t0 = D.CLOCK()
    block = D.mine(log, unit, nodes, miner, held, last, poll=POLL, at_ns=at_ns)
    timing['mine_ns'] += D.CLOCK() - t0
    timing['mine_blocks'] += 1
    chain.add(block)
    return block


def _gate(plan, seed, log, unit, run_unit, nodes, miner, worker, timing, ended, phase, l0=None) -> dict:
    run, b, h0 = plan['run'], plan['b'], plan['H0']
    j_l0 = plan.get('l0_seat')
    if (j_l0 is None) != (l0 is None):
        raise invalid('ITEM2_L0_ADAPTER')
    t_setup = D.CLOCK()
    held: set[str] = set()
    last = [0]
    chain = C.Chain(worker, h0, log, timing)
    plan['assignment'] = B.assignment(seed, run)
    gates = plan['bidders']['gates']
    seats = gates[0]['seats']
    if l0 is not None:
        # D3a-1a: block 1's coinbase is L0's funding (oe.chain_facts reads height 1); item 2's setup follows.
        chain.add(l0.fund(log, run_unit, nodes))
    synthetic = [{'gate': run, 'seats': [s for s in seats if s['kind'] != L0_KIND]}]
    funding = _setup(plan, log, run_unit, nodes, miner, held, last, timing, chain, worker, synthetic)
    timing['setup_ns'] = D.CLOCK() - t_setup
    phase[0] = 'GATE'
    l0_set = None
    if l0 is not None:
        # D3a-1b: its conflict set is fixed (L0 as operator, 045b :537), then every rung charged and signed at
        # H0 − 2 beside the ladders.
        l0_set = l0.start(log, unit, seats[j_l0], observation_id(run), b, nodes)
    # D3a-1b (A on #642): both nodes' increments are logged. D3a-2b-1 (A 6557890079 request 1): the synthetic
    # ladders use the larger of A's and B's too, as the L0 seat does (its L0_LAUNCH_START `increments`).
    increment, increments = B.node_increments(nodes)
    # The L0 seat's ladder is its conflict set, whose fees the L0 tool set (A Q-L1): it counts in the
    # prediction like any ladder; the driver builds and hands off none of it (A Q1).
    ladders = [list(l0_set) if j == j_l0 else B.ladder(p, b, increment, B.CANDIDATE_VSIZE)
               for j, p in enumerate(plan['feerates'])]
    rounds = schedule(plan['release_ks'], ladders, plan['rung_seconds'])
    predicted = predicted_candidates(rounds)
    log.write('GATE_START', unit, gate=run, height=h0, observation_id=observation_id(run))
    log.write('SCHEDULE', unit, increment=increment, increments=increments, increment_rule='MAX_NODE_A_NODE_B',
              ladders=ladders, rounds=rounds,
              predicted_candidates=predicted, t_gate_seconds=plan['t_gate_seconds'],
              rung_seconds=plan['rung_seconds'], l0_seat=j_l0)
    for j, fees in enumerate(ladders):
        if not fees:
            log.write('LADDER_EMPTY', unit, seat=seats[j]['seat'], kind=seats[j]['kind'],
                      feerate=plan['feerates'][j])
    bids = [{'seat': seats[j], 'j': j, 'gate': run, 'p0': plan['feerates'][j], 'fees': fees}
            for j, fees in enumerate(ladders) if fees and j != j_l0]
    if not bids and l0 is None:
        raise invalid('GATE_NO_BID')
    # Block G − 1: built (its hash is the rungs' tip), the ladders built on it, then sent; t0 = its send time.
    prepared = miner.prepare_block()
    if prepared['height'] != h0 - 1:
        raise invalid('ITEM2_PREPARED_HEIGHT')
    t_build = D.CLOCK()
    rungs = build_ladders(worker, bids, h0, (h0 - 1, prepared['block_hash']), funding, plan['assignment']) \
        if bids else {}
    timing['build_ns'] = D.CLOCK() - t_build
    for bid in bids:
        log.write('GENERATED', unit, seat=bid['seat']['seat'], ladder=bid['fees'],
                  rungs=[{k: v for k, v in r.items() if k != 'hex'} for r in rungs[bid['j']]])
    if l0 is not None:
        l0.ready(log, unit)   # L0 has signed every rung at H0 − 2 and asks for the floor block
    block = _mine(log, unit, nodes, _Prepared(miner), held, last, timing, chain)
    if block['block_hash'] != prepared['block_hash']:
        raise invalid('ITEM2_PREPARED_HASH')
    t0 = block['t_submit_ns']
    if l0 is not None:
        # L0's H0 − 1 turns start: rung k's step 8 at its release time (rung 0 now), only while 60k < t_G.
        l0.floor(block['block_hash'], [(r['k'], t0 + r['offset_seconds'] * 1_000_000_000)
                                       for r in rounds if j_l0 in r['seats']])
    due_g = t0 + plan['t_gate_seconds'] * 1_000_000_000
    last_rung: dict[str, dict] = {}
    released: list[dict] = []
    seen_relay: set[str] = set()
    t_release = D.CLOCK()
    excluded = None
    try:
        for step in rounds:
            k = step['k']
            due = t0 + step['offset_seconds'] * 1_000_000_000
            if k > 0:
                if due >= due_g:
                    raise invalid('ITEM2_RELEASE_AFTER_G')   # unreachable: the plan keeps rung_seconds × k < t_G
                D.sleep_until(due)
            for j in step['seats']:
                if j == j_l0:
                    continue   # L0 releases its own rungs (its step 8 to Node A and Node B)
                released.append(_release(plan, log, unit, nodes, miner, held, seats[j], rungs[j], k, due,
                                         last_rung))
            seen_relay |= relay_log(log, unit, nodes, held, k)
    except GateExcluded as caught:
        excluded = caught
    l0_done = None
    if l0 is not None:
        # Also after an exclusion: L0 hands off on its own, so its released rungs are logged.
        l0_done = _l0_release(log, unit, nodes, l0, seats[j_l0], last_rung)
        released.extend(l0_done['records'])
        seen_relay |= l0_done['seen_relay'] | relay_log(log, unit, nodes, held, l0_done['records'][-1]['k'])
    if excluded is not None:
        timing['release_ns'] = D.CLOCK() - t_release
        summary = {'gate': run, 'height': h0, 'block_hash': None, 'born': [], 'winner': None,
                   'predicted_candidates': predicted, 'observed_candidates': observed_candidates(released, seen_relay),
                   'last_rungs': last_rung, 'misses': [], 'late_releases': [], 'order': [], 'next_birth': None,
                   'code_seats': [excluded.detail['replaced_missing']['seat']],
                   **l0_fields(j_l0, seats, released, l0_set),
                   # WRD3a1b P3-6: no block G, so no `set_observe`: the wallet's counters of L0's last phase.
                   **({'l0_budget_counters': l0.last_counters(log, unit)} if l0 is not None else {}),
                   **excluded.detail}
        log.write('GATE_END', unit, status='EXCLUDED', code=excluded.code, observation_id=observation_id(run),
                  **summary)
        return {'status': 'EXCLUDED', 'code': excluded.code, 'excluded_gates': [run],
                'excluded_observation_ids': [observation_id(run)], **summary}
    timing['release_ns'] = D.CLOCK() - t_release
    late = late_releases(released, due_g)
    block = _mine(log, unit, nodes, miner, held, last, timing, chain, at_ns=due_g)
    lag = block['t_template_ns'] - due_g
    timing['g_lag_ns'] = lag
    log.write('G_TIMING', unit, t0_ns=t0, due_ns=due_g, template_ns=block['t_template_ns'],
              submit_ns=block['t_submit_ns'], lag_ns=lag, t_gate_seconds=plan['t_gate_seconds'])
    misses = release_misses(last_rung, block['template'], block['private_set'])
    replay = chain.flush(unit, gate=h0)[-1]
    by_txid = {r['txid']: seats[j]['seat'] for j, ladder in rungs.items() for r in ladder}
    by_txid.update({r['txid']: r['seat'] for r in released if r.get('sent_by') == L0_SENT_BY})
    born = replay['born']
    code = gate_code(misses, late, lag)
    winner = by_txid.get(born[0]) if len(born) == 1 else None
    if l0 is not None:
        # D3a-1b: the host's labels for every rung of L0's set after block G, and the wallet's counters. WRD3a1b
        # P2-1: the expected labels follow the L0 rung block G holds and the one born, so an L0 exclusion
        # (its latest rung not in G) is judged by `code` below like any seat's, not as a label mismatch.
        # Delta review P3-B: the rung in G is read from block G's own transactions (`order`); the template's
        # L0 rungs must be the same (L0_IN_G otherwise, fail closed). P3-A: an excluded gate's labels are
        # logged (`match`) and never fail the run.
        listed = {item['txid'] for item in block['template']['transactions']}
        in_block = {item['txid'] for item in block['order']}
        mine = [r for r in released if r.get('sent_by') == L0_SENT_BY]
        l0_done['observed'] = l0.observe(log, unit, in_g=[r['k'] for r in mine if r['txid'] in in_block],
                                         born=[r['k'] for r in mine if r['txid'] in born],
                                         next_birth=replay['next_birth'],
                                         in_template=[r['k'] for r in mine if r['txid'] in listed],
                                         excluded=code is not None)
    if code is None:
        B.gate_row(gates[0], h0, bids or [{'seat': seats[j_l0]}], born, {r['txid'] for r in released})
    observed = observed_candidates(released, seen_relay)
    summary = {'gate': run, 'height': h0, 'block_hash': block['block_hash'], 'born': born,
               'winner': winner, 'predicted_candidates': predicted,
               'observed_candidates': observed, 'last_rungs': last_rung, 'misses': misses, 'late_releases': late,
               'order': [o['txid'] for o in block['order']], 'next_birth': replay['next_birth'],
               'code_seats': code_seats(code, misses, late), **l0_fields(j_l0, seats, released, l0_set),
               **({'l0_budget_counters': l0_done['observed']['counters'],
                   'l0_charged_not_released_after_g': l0_held_after_g(l0_fields(j_l0, seats, released, l0_set),
                                                                      l0_set, l0_done['observed']['labels'])}
                  if l0 is not None else {})}
    if code is not None:
        log.write('GATE_END', unit, status='EXCLUDED', code=code, observation_id=observation_id(run), **summary)
        return {'status': 'EXCLUDED', 'code': code, 'excluded_gates': [run],
                'excluded_observation_ids': [observation_id(run)], **summary}
    log.write('GATE_END', unit, status='OBSERVED', observation_id=observation_id(run), **summary)
    return {'status': 'DONE', **summary}


L0_SENT_BY = 'L0_STEP8'


def l0_fields(j_l0, seats, released, l0_set=None) -> dict:
    """GATE_END's L0 fields: the seat, the attempt id, the rungs released and those charged but not released
    before t_G (A Q-L4: their count, fee sum and k list); all None without the L0 seat."""
    if j_l0 is None:
        return {'l0_seat': None, 'l0_attempt_id': None, 'l0_released_ks': None, 'l0_charged_not_released': None}
    mine = [r for r in released if r.get('sent_by') == L0_SENT_BY]
    ks = [r['k'] for r in mine]
    held = [k for k in range(len(l0_set or [])) if k not in ks]
    return {'l0_seat': seats[j_l0]['seat'], 'l0_attempt_id': mine[0]['attempt_id'] if mine else None,
            'l0_released_ks': ks,
            'l0_charged_not_released': {'count': len(held), 'fee_sum_sat': sum(l0_set[k] for k in held), 'ks': held}}


def l0_held_after_g(fields: dict, l0_set: list[int], labels: list[dict]) -> list[dict]:
    """D3a-2b-1 (B on A 6557723699 Q7): for each L0 rung charged and never released, its fee and the host's own
    verdict and outcome for it at the first turn after G (the set worker's `labels` line: the product's
    answer, e.g. `Wait:OfflineSignaturePending` / `Stale`), never a reason the driver computes."""
    return [{'k': k, 'fee_sat': l0_set[k], 'verdict_after_g': labels[k]['verdict'],
             'outcome_after_g': labels[k]['outcome'], 'source': 'SET_WORKER_LABELS_FIRST_TURN_AFTER_G'}
            for k in fields['l0_charged_not_released']['ks']]


def _l0_release(log, unit, nodes, l0, seat, last_rung) -> dict:
    """D3a-1b (A Q1): the L0 seat's released rungs, as L0 released them. `l0.finish` waits for L0's last step
    8 and returns what it sent, per rung: txid, the bytes' SHA-256 and candidate id from the product's stage
    lines; fee and vsize from Node A's and Node B's mempool entries; `replaces` (rung k − 1's txid); the due
    time (t0 + rung_seconds × k) and `sent_ns` (the end of rung k's step-8 turn, the hand-off inside it). The
    driver neither prices nor hands off any of them. Writes GENERATED once (the set's fees as the ladder, the
    released rungs), and per rung RELEASE and L0_RELAY; `last_rungs` gets the latest released rung."""
    got = l0.finish(log, unit)
    rungs, records, seen = [], [], set()
    for r in got['released']:
        fee, vsize = r['nodes']['A']['fee'], r['nodes']['A']['vsize']   # the nodes' entry, never a formula
        rungs.append({'rung': r['k'], 'fee': fee, 'txid': r['txid'], 'vsize': vsize, 'raw_sha256': r['raw_tx_sha256'],
                      'candidate_id': r['candidate_id'], 'source': 'L0_PRODUCT'})
    log.write('GENERATED', unit, seat=seat['seat'], kind=seat['kind'], ladder=got['fees'], rungs=rungs)
    for r, rung in zip(got['released'], rungs):
        record = {'seat': seat['seat'], 'path': seat['path'], 'kind': seat['kind'], 'k': r['k'], 'txid': r['txid'],
                  'fee': rung['fee'], 'vsize': rung['vsize'], 'replaces': r['replaces'], 'due_ns': r['due_ns'],
                  'turn_start_ns': r['turn_start_ns'], 'sent_ns': r['sent_ns'], 'lag_ns': r['sent_ns'] - r['due_ns'],
                  'handed_off': True, 'sent_by': L0_SENT_BY, 'fee_source': 'NODE_MEMPOOL_ENTRY',
                  'attempt_id': got['attempt_id']}
        log.write('RELEASE', unit, **record)
        log.write('L0_RELAY', unit, txid=r['txid'], k=r['k'], at_relay=r['at_relay'], waited_ns=r['relay_waited_ns'])
        if r['at_relay']:
            seen.add(r['txid'])
        records.append(record)
        last_rung[seat['seat']] = {'txid': r['txid'], 'path': seat['path'], 'k': r['k']}
    return {'records': records, 'seen_relay': seen}


def _release(plan, log, unit, nodes, miner, held, seat, ladder, k, due, last_rung) -> dict:
    """Rung k of one bidder: testmempoolaccept on Node A and Node B, then the hand-off: PUBLIC to the relay
    (`sendrawtransaction`, a replacement for k ≥ 1), PRIVATE to the miner process (`private` for rung 0,
    `replace` after). For a PUBLIC rung k ≥ 1 the test is a replacement test only once rung k − 1 is in Node
    A's and Node B's mempools: it waits for that (WR23b P3-4), and if rung k − 1 is still missing the gate is
    EXCLUDED (REPLACED_RUNG_NOT_IN_MEMPOOL) before rung k is tested or sent. RELEASE records the due time, the
    send time and the lag."""
    rung = ladder[k]
    present = {'A': None, 'B': None}
    if seat['path'] == 'PUBLIC' and k > 0:
        present = wait_replaced(nodes, ladder[k - 1]['txid'])
        if not all(present.values()):
            log.write('REPLACED_RUNG_MISSING', unit, seat=seat['seat'], k=k, txid=rung['txid'],
                      replaces=ladder[k - 1]['txid'], replaces_in_mempool=present, waited_seconds=REPLACED_WAIT_SECONDS)
            raise GateExcluded('REPLACED_RUNG_NOT_IN_MEMPOOL', {'replaced_missing': {
                'seat': seat['seat'], 'k': k, 'txid': rung['txid'], 'replaces': ladder[k - 1]['txid'],
                'replaces_in_mempool': present}})
    for role in ('A', 'B'):
        result = nodes[role].rpc('testmempoolaccept', [rung['hex']])
        log.write('TESTMEMPOOLACCEPT', unit, node=role, txid=rung['txid'], rung=k, result=result,
                  replaces_in_mempool=present[role])
        if not (isinstance(result, list) and len(result) == 1 and result[0].get('allowed') is True):
            raise oe.Mismatch('TESTMEMPOOLACCEPT_REGISTER' if k == 0 else 'TESTMEMPOOLACCEPT_REPLACEMENT')
    fault = plan['fault'] == {'seat': seat['seat'], 'k': k}
    t_send = D.CLOCK()
    accepted = True
    if fault:
        accepted = False   # a test's fault: logged as released, never handed off (RELEASE `fault`)
    elif seat['path'] == 'PRIVATE' and k > 0:
        answer = miner.replace_private(rung['hex'])
        if answer['txid'] != rung['txid'] or answer['replaced'] != ladder[k - 1]['txid']:
            raise invalid('PRIVATE_REPLACE_TXID')
        held.discard(answer['replaced'])
        held.add(rung['txid'])
        log.write('PRIVATE_REPLACE', unit, txid=rung['txid'], replaced=answer['replaced'], hex=rung['hex'],
                  seat=seat['seat'], kind=seat['kind'])
    else:
        B.hand_off(seat, rung['hex'], nodes['relay'], miner, held, log, unit)
    record = {'seat': seat['seat'], 'path': seat['path'], 'k': k, 'txid': rung['txid'], 'fee': rung['fee'],
              'replaces': ladder[k - 1]['txid'] if k else None, 'due_ns': due, 'sent_ns': t_send,
              'lag_ns': t_send - due, 'handed_off': accepted}
    log.write('RELEASE', unit, **record, **({'fault': 'NOT_HANDED_OFF'} if fault else {}))
    last_rung[seat['seat']] = {'txid': rung['txid'], 'path': seat['path'], 'k': k}
    return record


def wait_replaced(nodes, txid: str) -> dict[str, bool]:
    """Polls Node A's and Node B's mempools (every `POLL` s) until both hold `txid` or `REPLACED_WAIT_SECONDS`
    have passed. Returns whether each holds it at the last poll."""
    deadline = D.CLOCK() + int(REPLACED_WAIT_SECONDS * 1e9)
    while True:
        present = {role: txid in set(nodes[role].call('getrawmempool')) for role in ('A', 'B')}
        if all(present.values()) or D.CLOCK() >= deadline:
            return present
        time.sleep(POLL)


def relay_log(log, unit, nodes, held, k) -> set[str]:
    """The relay log after a release step: every node's mempool (a held private txid in any of them is a
    leak, PRIVATE_IN_MEMPOOL). Returns the relay's."""
    pools = {}
    for role in ('relay', 'miner', 'A', 'B'):
        pools[role] = sorted(nodes[role].call('getrawmempool'))
        if held & set(pools[role]):
            raise oe.Mismatch('PRIVATE_IN_MEMPOOL')
    log.write('RELEASE_MEMPOOLS', unit, k=k, mempools=pools)
    return set(pools['relay'])


def observed_candidates(released: list[dict], seen_relay: set[str]) -> int:
    """Distinct REGISTER candidates seen in the gate: a PUBLIC rung once the relay's mempool held it after a
    release step (the relay log), a PRIVATE rung once the miner process took it."""
    return len({r['txid'] for r in released if r['handed_off']
                and (r['path'] == 'PRIVATE' or r['txid'] in seen_relay)})


if __name__ == '__main__':
    sys.exit(D.EXIT_REFUSAL)   # no CLI: the driver runs ITEM2 (`run --experiment ITEM2`)


# ---------------------------------------------------------------------------------------------------------
# L0-501 (A #258 issuecomment-6764861681, FD-CT-67): the L0 seat's rung-test helpers, called from
# `claude_track_ardr_l0` (`L0Seat._rung_test` :1139, :1141, :1145 and `L0Seat.finish` :664, each a same-line
# append there). The frozen 045b cites both files by line, so they sit after this file's last line and no line
# above moves. This module has no CLI (the `__main__` block above only refuses), so they exist whenever it is
# imported, which is the only way the L0 module reaches them (as `l0_ladder` and `check_l0_set`).
import subprocess  # noqa: E402

L0_NOT_IN_MEMPOOL = ('error code: -5', 'Transaction not in mempool')   # bitcoin-cli's stderr for RPC error -5


def l0_replaced_txid(exports: list[dict], released: list[dict], k: int, when: str) -> str:
    """The L0 rung that rung k's `testmempoolaccept` would replace (A 6764861681 item 1): for a released rung
    (`BEFORE_RELEASE`, right before its step 8) rung k − 1, which is then the last rung released; for a rung
    charged and never released (`CHARGED_NOT_RELEASED_BEFORE_G`, from `finish`) the last rung released at that
    time. Anything else (another `when`, k < 1, no rung released, a last released rung that is not k − 1 before a
    release or not below k after the releases) is L0_RUNG_TEST."""
    if when == 'BEFORE_RELEASE' and 1 <= k < len(exports) and released and released[-1]['k'] == k - 1:
        return exports[k - 1]['txid']
    if when == 'CHARGED_NOT_RELEASED_BEFORE_G' and released and released[-1]['k'] < k:
        return released[-1]['txid']
    raise oe.Mismatch('L0_RUNG_TEST')


def l0_in_mempool(node, txid: str) -> bool:
    """`getmempoolentry` of `txid` on Node A or Node B (oe's driver user, `node.raw`, as `L0Seat._entries`), read
    on that node right before its `testmempoolaccept` of the replacing rung (`L0Seat._rung_test`: the condition of
    l0 :1141's conditional expression, which Python evaluates before the call). True when the node answers with an
    entry (one JSON object); False when bitcoin-cli fails with RPC error -5 and Core's "Transaction not in mempool"
    (both stderr lines, `L0_NOT_IN_MEMPOOL`, as bitcoin-cli prints them). Fail closed otherwise, in the seat's own
    codes: any other error (another code, or -5 with another message) is `PREREQUISITE RPC_FAILED A getmempoolentry`
    / `B` (exit 3, as `_entries`), a call past its 300 s limit `PREREQUISITE NODE_CALL_TIMEOUT A` / `B` (exit 3, U4),
    and an answer that is not one JSON object `MISMATCH L0_RUNG_TEST` (exit 2). The value means what item 2's
    synthetic TESTMEMPOOLACCEPT `replaces_in_mempool` means (`_release`: whether rung k − 1 was in that node's
    mempool when rung k was tested); item 2 reads it from `getrawmempool`, the L0 seat from `getmempoolentry`."""
    try:
        done = node.raw('getmempoolentry', txid)
    except subprocess.TimeoutExpired:
        raise oe.Prerequisite(f'NODE_CALL_TIMEOUT {node.label}') from None
    if done.returncode != 0:
        if all(line in done.stderr.splitlines() for line in L0_NOT_IN_MEMPOOL):
            return False
        raise oe.Prerequisite(f'RPC_FAILED {node.label} getmempoolentry')
    try:
        entry = oe.cli_result(('getmempoolentry', txid), done.stdout.strip())
    except (ValueError, ArithmeticError):   # JSONDecodeError; decimal.InvalidOperation
        raise oe.Mismatch('L0_RUNG_TEST') from None
    if type(entry) is not dict:
        raise oe.Mismatch('L0_RUNG_TEST')
    return True


def l0_replaced_field(answer: dict, seen) -> dict:
    """The field L0-501 adds to a node's answer in L0_RUNG_TEST `nodes[<label>]` (l0 :1145): `replaces_in_mempool`,
    that node's `l0_in_mempool` read. An answer that already holds the key (the node's own words are never
    overwritten) or a read that is not a bool is L0_RUNG_TEST."""
    if 'replaces_in_mempool' in answer or type(seen) is not bool:
        raise oe.Mismatch('L0_RUNG_TEST')
    return {'replaces_in_mempool': seen}


def l0_rung_tests_before_raise(log, unit: dict, attempt_id: str, tests: dict, error) -> bool:
    """A 6764861681 item 2, on `finish`'s line that raises the L0 thread's error (l0 :664, the condition of its
    conditional expression, so it runs before `self._raise()`). When the attempt failed (`error`, the thread's, is
    set) it writes the rung tests gathered so far (`tests`, by k ascending) as L0_RUNG_TEST lines, so a FAILED
    attempt's raw log keeps a refusal: a released rung's test is gathered right before its step 8 (`_release`).
    `_raise()` then raises that error, so `finish`'s own L0_RUNG_TEST loop (:674-675) is not reached in that call.
    Without an error it writes nothing, and `finish` goes on exactly as before: its loop writes every rung k ≥ 1
    once, in its old place and order. So each rung's line is written once per `finish`: the two writers run on
    the two values of one test, and the error cannot change between this call and `_raise()`, since the L0
    thread (its only writer) has been joined (:651). Returns True, so :664 always runs `self._raise()` as before."""
    if error is not None:
        for k in sorted(tests):
            log.write('L0_RUNG_TEST', unit, attempt_id=attempt_id, **tests[k])
    return True
