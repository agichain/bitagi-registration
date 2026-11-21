#!/usr/bin/env python3
"""CT-P5-001 D3a-2a: ARDR item 4's miner side and run shape, with a synthetic stand-in project seat.

Class T Regtest development evidence only; never mainnet, never S17-PREP, and no ARDR verdict. Sources: B's
D3a draft #258 issuecomment-6550996612 (fact 3, the D3a-2 line), A's answer -6551547851 (Q3-Q7), B's split
note -6554438116 (D3a-2a / D3a-2b and the B defaults this builds on), and the 045b draft item 4 rows
(`CT-P3-045b_PREREGISTRATION_DRAFT_EN.md` :383, :407-424, :524, :541-543), a draft input, not frozen bytes.
Every value here is PENDING_FREEZE / DRAFT. Format: `docs/claude-track/formats/ARDR_RUN_V1.md` section 23.

One item-4 run is one contested gate G = H0 of a new chain, run index r = 0 … 49 per sub-scenario (045b :524),
on D1's topology with the loopback noban whitelist (item 2's). The project seat is a synthetic stand-in
(`PROJECT_STANDIN`, SYNTHETIC wallet W01): D3a-2b puts the L0 project host there, so the stand-in is EXPLORATORY
and PR_SMOKE only; CONFIRMATORY with the stand-in is refused (`CONFIRMATORY_NEEDS_L0_SEAT`, exit 3) before any
node (D3a-2b-2b: CONFIRMATORY runs the L0 seat, below).

- ITEM4_SELF_DEALING (`ITEM4_SELF_FIRST_ZERO_FEE`): the miner's own REGISTER (seat S0, PRIVATE: handed to
  the miner process only) is placed at index 0 of block G whatever its fee. The product signer refuses a
  0-fee REGISTER (`crates/bitagi-signer/src/semantic.rs:714`, :767-778; unit note section 0), so the self
  REGISTER pays the product floor `SELF_FEE` and the zero-fee self REGISTER is on the not-run list.
- ITEM4_CENSORSHIP (`ITEM4_CENSOR_144`): the synthetic competitor holds G (A Q4); blocks G … G + 143 drop
  the stand-in's transactions (by txid and by its funding outpoint: its rung 1, released after G with a new
  txid, is dropped too) and their descendants; G + 144 holds the stand-in's last rung.
- ITEM4_REORG (`ITEM4_REORG_REPLACE`): the stand-in wins G; the competitor is released after G. Depth
  d = 1 for even r, 2 for odd r (A Q5): d = 2 mines G + 1 first. The miner node's driver user
  (`invalidateblock`, this topology only) invalidates G; the miner builds d + 1 replacement blocks on
  G − 1 without the replaced winner (the template offers it again); the intermediate ones wait for the
  miner node only, the last for all four (more work: the reorg reaches the others by P2P).
- ITEM4_FEE_ASYMMETRY (`ITEM2_DEFAULT`): seat S0 is the asymmetric bidder, S1 the stand-in (its configured p0
  = L0's p_0 (FD-CT-133), no draw: A Q1's L0 seat draws nothing), S2-S4 draw `BID_FEE_j` (n = 3b + 1) as item 2. The
  asymmetric bidder pays one rung at `ASYMMETRY_FACTOR` × the honest median (nearest rank p50 of the four
  rung-0 feerates, all fixed before any release: A 6554792879 Q1), outside the 4b ladder cap.

No t_G (A Q6): every bidder released before G releases rung 0 once G − 1 is at the relay, A and B; block G
is mined once every released public rung is at the miner node; its template is then checked
(`RELEASE_NOT_IN_TEMPLATE`, item 2's check, excludes the gate). Self, censorship and reorg runs draw
nothing: the stand-in pays L0's p0 (FD-CT-133) at 213 vB, the competitor 2 × the stand-in's fee + 1 (oe's `competitor_fee` at
equal vsize). H0 = 1000 by default (A Q2, B Q7). The Core replay of the final chain (and in a reorg run of
the replaced blocks) gives the births.

Exit codes (AGENTS.md section 12) as D1's. Optimized Python (-O) is refused by the driver. Stdlib only.
TEST_ONLY material only: every key is a TEST_ONLY key from the policy seed (DRAFT rule, PENDING_FREEZE).

D3a-2b-1 (ARDR_RUN_V1 section 24; B's unit note #258 issuecomment-6557558721 and its defaults, A's answer
-6554792879 and -6557723699, binding): `plan_run(..., l0=True)` puts the L0 project host
(`claude_track_ardr_l0.L0Seat`, run by that module's `item4_l0_run` on its `L0Topology`) in the project seat of
ITEM4_SELF_DEALING, ITEM4_FEE_ASYMMETRY and ITEM4_CENSORSHIP (`_gate_l0`). L0 sets its own fee (its conflict set,
every rung charged, the budget's `exact_height_miss` CONTINUE_WITHIN_LIMITS; item 4 has no t_G, so only rung 0 is
released, A Q6), and the host's labels are read after block G (and in the censorship run after G + 143 and
G + 144, or at every block in the local control row) with the two report flags from the set worker's `flags`
line; they are judged against `ITEM4_LABELS` (045b 4.3) by verdict, outcome and flags (A Q1). D3a-2b-2b
(ARDR_RUN_V1 section 26): CONFIRMATORY runs this L0 path for SELF, ASYM and CENSOR (ITEM4_REORG refused,
ITEM4_L0_REORG_CONFIRMATORY, until A decides the release in CONFIRMATORY), entered through the driver CLI only
(`claude_track_ardr_driver._run_l0`, after the L0 freeze values are set: L0_FREEZE_PENDING until then);
`ITEM4_L0_NOT_BUILT` is retired. This module does not import the L0 module.

D3a-2b-2a (ARDR_RUN_V1 section 25; A -6557723699 Q4 (가)-(다), -6554792879 Q6): ITEM4_REORG with the L0 seat
(`_gate_l0`, `reorg_run_l0`). L0 alone releases rung 0 before G and wins G; the host turns at G (and at G + 1
for depth 2) and reports `Done:Born`; the competitor is released after G; the miner invalidates G and builds
d + 1 replacement blocks without any L0 transaction (checked by txid and by L0's funding outpoint,
`reorg_block_check_l0`); the host's `set_reorged` turn raises Reorg67 (`Refuse:Locked(Reorg67)`); the
`RELEASE_REORG67_TEST_ONLY` phase (`L0Seat.release_reorg67`, TEST_ONLY and Class T Regtest only) releases it
through the TDS 6.7 procedure file; a last turn reads `Stale`. The label line (`ITEM4_L0_LABEL_LINE`) keeps
every step, `Done:Born` → `Refuse:Locked(Reorg67)` → (release) → `Stale`, and is judged with every turn.
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).absolute().parent))
import claude_track_ardr_bidders as B  # noqa: E402
import claude_track_ardr_campaign as C  # noqa: E402
import claude_track_ardr_driver as D  # noqa: E402
import claude_track_ardr_item2 as I2  # noqa: E402
import claude_track_regtest_offline_export as oe  # noqa: E402

Refusal, invalid = D.Refusal, D.invalid

SCENARIOS = D.ITEM4_EXPERIMENTS
L0_SCENARIOS = ('ITEM4_SELF_DEALING', 'ITEM4_FEE_ASYMMETRY', 'ITEM4_CENSORSHIP', 'ITEM4_REORG')   # REORG: D3a-2b-2a
PROJECT_L0 = I2.L0_KIND   # the L0 seat's role and kind (`L0_PROJECT`, wallet `L0`, PUBLIC)
ITEM4_RUNS = 50              # 045b :524: 50 runs per sub-scenario
ASYMMETRY_FACTOR = 10        # 045b :541, A Q5 (PENDING_FREEZE): 10 × the median honest feerate
SELF_FEE = D.ITEM4_SELF_FEE  # the product floor: 2,000 sat/kvB over the fixture's 1,200 WU (300 vB) signed weight
MAX_REGISTER_FEE = 90_000    # the generator's caps: fee + the 10,000-sat successor within 100,000 sat
CENSOR_STANDIN_RUNGS = 2     # rung 0 before G, rung 1 (a new txid) inside the window
PROJECT_STANDIN = 'PROJECT_STANDIN'
MINER_POLICY = D.ITEM4_MINER
# Core's getblocktemplate keeps its last template while the tip is the same one and for 5 s after a mempool
# change (rpc/mining.cpp). After `invalidateblock` G the tip is G − 1 again, so within 5 s of G's own
# template a depth-1 run would get G's template back (measured: the competitor released after G missing from
# G'). The reorg waits until this long after G's template before it invalidates G (DEFAULT, PENDING_FREEZE).
TEMPLATE_CACHE_NS = 6_000_000_000   # from when G's template answer arrived (pre-PR P3-4), not when it was asked
POLL = C.POLL_SECONDS
ROLES = I2.ROLES

# The seats per scenario: (seat, kind, wallet, path, role). Seat 0 is the PRIVATE one when present (D2-1).
SEATS = {
    'ITEM4_SELF_DEALING': (('S0', 'SYNTHETIC', 'W00', 'PRIVATE', 'SELF'),
                           ('S1', 'SYNTHETIC', 'W01', 'PUBLIC', PROJECT_STANDIN)),
    'ITEM4_CENSORSHIP': (('S0', 'SYNTHETIC', 'W01', 'PUBLIC', PROJECT_STANDIN),
                         ('S1', 'COMPETITOR', 'C00', 'PUBLIC', 'COMPETITOR')),
    'ITEM4_REORG': (('S0', 'SYNTHETIC', 'W01', 'PUBLIC', PROJECT_STANDIN),
                    ('S1', 'COMPETITOR', 'C00', 'PUBLIC', 'COMPETITOR')),
    'ITEM4_FEE_ASYMMETRY': (('S0', 'SYNTHETIC', 'W00', 'PUBLIC', 'ASYMMETRIC'),
                            ('S1', 'SYNTHETIC', 'W01', 'PUBLIC', PROJECT_STANDIN),
                            ('S2', 'SYNTHETIC', 'W02', 'PUBLIC', 'HONEST'),
                            ('S3', 'SYNTHETIC', 'W03', 'PUBLIC', 'HONEST'),
                            ('S4', 'SYNTHETIC', 'W04', 'PUBLIC', 'HONEST')),
}
# The reorg run's competitor is released after block G; every other seat before it.
AFTER_G = {'ITEM4_REORG': ('COMPETITOR',)}

# A Q4 and 045b :383 ("a scenario not run is listed as not run"): what these runs do not cover.
NOT_RUN = (
    {'scenario': 'ITEM4_CENSORSHIP', 'case': 'DONE_BORN_LATE_NOT_AT_OPENING',
     'label': 'Done:Born{late, at_opening: false}',
     'reason': 'A 6551547851 Q4: the synthetic competitor holds G in every censorship run'},
    {'scenario': 'ITEM4_SELF_DEALING', 'case': 'ITEM4_SELF_ZERO_FEE_REGISTER', 'label': None,
     'reason': 'the generator panics BelowTargetFeeRate at crates/bitagi-signer/tests/ardr_bidder_generator.rs:341 '
               '(crates/bitagi-wallet/src/register.rs:1924), and the product signer refuses a 0-fee REGISTER '
               'under any policy (crates/bitagi-signer/src/semantic.rs:714, :767-778); the self REGISTER pays '
               'SELF_FEE (the product floor); a zero-fee one needs a crates/*/src change (FD-CT-62)'},
    {'scenario': '*', 'case': 'L0_PROJECT_SEAT', 'label': None,
     'reason': 'D3a-2b: the L0 project host in the project seat (here PROJECT_STANDIN)'},
)
# D3a-2b-1: what the L0 runs do not cover (045b :383). E7 is in no item-4 flow (B 6557558721 Q2).
NOT_RUN_L0 = (
    NOT_RUN[0], NOT_RUN[1],
    {'scenario': '*', 'case': 'E7_REORG_BEFORE_INCLUSION',
     'label': 'Stale{reorged_before_inclusion: true}, then IncludedNoEffect',
     'reason': 'no item-4 miner policy reorgs a released rung out before its inclusion (A 6557723699 Q2); '
               "1e-2b-2b's E7 real-node row covers this label for item 4's entry set"},
)

# D3a-2b-1: 045b 4.3's item-4 labels (`:407-424`), per scenario and host turn after G: (turn, blocks after G).
L0_TURNS = {'ITEM4_SELF_DEALING': (('G', 0),), 'ITEM4_FEE_ASYMMETRY': (('G', 0),),
            'ITEM4_CENSORSHIP': (('G', 0), ('G+143', D.CENSOR_BLOCKS - 1), ('G+144', D.CENSOR_BLOCKS)),
            'ITEM4_REORG': None}   # by depth: `reorg_turns`
# Rung 0's report outcome at each turn: INCLUDED (`IncludedNoEffect` at the height it was mined: G, or G + 144
# when the censor is lifted) or STALE (`Stale{target G, next birth}`, P0 not mined). Every other rung of L0's set
# is charged and never released: STALE at every turn. Every rung at every turn: `opening_block_missed` true (no
# project REGISTER born at G), `reorged_before_inclusion` false. A 6557723699 Q1: the verdict is judged too,
# against `expected_verdict` for the run's budget `exact_height_miss` (L0_LAUNCH_START, L0_BUDGET).
ITEM4_LABELS = {
    ('ITEM4_SELF_DEALING', 'G'): 'INCLUDED',      # E10-s: the self REGISTER is born first in G; P0 after it
    ('ITEM4_FEE_ASYMMETRY', 'G'): 'INCLUDED',     # the asymmetric seat is born; P0 in G after it
    ('ITEM4_CENSORSHIP', 'G'): 'STALE',           # lost gate, P0 not mined
    ('ITEM4_CENSORSHIP', 'G+143'): 'STALE',
    ('ITEM4_CENSORSHIP', 'G+144'): 'INCLUDED',    # lost gate, P0 mined later
}
L0_FLAGS = ('opening_block_missed', 'reorged_before_inclusion')
INCLUDED, STALE = 'INCLUDED', 'STALE'   # `ITEM4_LABELS`' two rung-0 kinds


# D3a-2b-2a: the reorg run's turns. On the replaced chain: G, and G + 1 for depth 2 (so the host has seen every
# block the reorg replaces). On the replacement tip G + d: REORGED (`set_reorged`), RELEASE (`set_release`, the
# `RELEASE_REORG67_TEST_ONLY` phase) and STALE (`set_observe`).
REORG_TIP_TURNS = (('REORGED', 'set_reorged'), ('RELEASE', 'set_release'), ('STALE', 'set_observe'))
LOCKED_REORG67 = 'Refuse:Locked(Reorg67)'
RELEASE_REORG67_TEST_ONLY = 'RELEASE_REORG67_TEST_ONLY'   # the L0 module's phase name (a cell pins them equal)


def reorg_turns(d: int) -> list[tuple[str, int]]:
    """The ITEM4_REORG L0 run's host turns at depth `d` (1 or 2): (turn, blocks after G)."""
    if d not in (1, 2):
        raise invalid('ITEM4_DEPTH')
    return [('G', 0)] + [(f'G+{k}', k) for k in range(1, d)] + [(name, d) for name, _ in REORG_TIP_TURNS]


def l0_turns(scenario: str, control: bool = False, d: int | None = None) -> list[tuple[str, int]]:
    """The host turns of an L0 run: `L0_TURNS` (ITEM4_REORG: `reorg_turns(d)`), or with `control` (A 6557723699
    Q3: the censorship run's local control row) a turn at every block G … G + 144, whose G + 143 and G + 144
    labels must equal the three-turn run's (ITEM4_L0_CONTROL for any other scenario)."""
    if scenario == 'ITEM4_REORG' and not control:
        return reorg_turns(d)
    if not control:
        return list(L0_TURNS[scenario])
    if scenario != 'ITEM4_CENSORSHIP':
        raise invalid('ITEM4_L0_CONTROL')
    return [('G', 0)] + [(f'G+{k}', k) for k in range(1, D.CENSOR_BLOCKS + 1)]


def label_kind(scenario: str, offset: int) -> str:
    """`ITEM4_LABELS`' rung-0 kind at a turn `offset` blocks after G (a control turn inside the window is a
    censorship STALE turn)."""
    if scenario == 'ITEM4_CENSORSHIP':
        return INCLUDED if offset == D.CENSOR_BLOCKS else STALE
    return ITEM4_LABELS[(scenario, 'G')]
# The expected verdict by the budget's `exact_height_miss`, the rung's outcome, whether it was released and
# whether the turn is at G (offset 0) or later (real-node rows, unit note section 6). CONTINUE_WITHIN_LIMITS (A
# 6557723699, 045b :103's draft value; 045b 4.3): the included rung `Done:IncludedNoEffect@<height>`; a released
# rung not mined `Refuse:GateAdvanced` (the product refuses it after G: A Q7's reason, read from the host); a
# rung charged and signed but never released `Wait:OfflineSignaturePending` (the product's answer to the L0 flow's
# import order: rung k is imported only after rung k − 1's release, so a rung never released is never imported).
# STOP_CAMPAIGN (the D3a-1b budget): every rung `Refuse:ExactHeightMissed` at G and
# `Refuse:StopOpen(ExactHeightMissed)` later.
CONTINUE_LOST, CONTINUE_UNRELEASED = 'Refuse:GateAdvanced', 'Wait:OfflineSignaturePending'
STOP_AT_G, STOP_LATER = 'Refuse:ExactHeightMissed', 'Refuse:StopOpen(ExactHeightMissed)'
EXPECTED_FLAGS = {'opening_block_missed': True, 'reorged_before_inclusion': False}


# ---------------------------------------------------------------------------------------------------------
# The plan: everything fixed before any node starts.

def depth(run: int) -> int:
    """A Q5: even r → depth 1 (G replaced), odd r → depth 2 (G and G + 1 replaced)."""
    return 1 if run % 2 == 0 else 2


def p50(values: list[int]) -> int:
    """045b's percentile estimator: nearest rank (the ceil(n / 2)-th smallest)."""
    if not values:
        raise invalid('ITEM4_P50_EMPTY')
    ordered = sorted(values)
    return ordered[-(-len(ordered) // 2) - 1]


def asymmetric_fee(median: int, vsize: int = B.CANDIDATE_VSIZE, factor: int = ASYMMETRY_FACTOR) -> int:
    """The asymmetric bidder's one rung: ceil(factor × median × vsize / 1000) sat."""
    return B.ceil_div(factor * median * vsize, 1000)


def honest_feerates(seed: bytes, run: int, b: int) -> tuple[list[int], list[dict]]:
    """The four honest rung-0 feerates (sat/kvB), all fixed before any rung is released (A 6554792879 Q1): the
    project seat's configured p_0 = L0's (FD-CT-133; no draw) and seats 2-4's `BID_FEE_j`. Never a fee read from
    a mempool or a template."""
    rates, draws = [D.item4_project_p0(b)], []
    for j in (2, 3, 4):
        value, k = D.draw(seed, 'ITEM4_FEE_ASYMMETRY', run, f'BID_FEE_{j}', 3 * b + 1)
        draws.append({'e': 'ITEM4_FEE_ASYMMETRY', 'r': run, 'label': f'BID_FEE_{j}', 'n': 3 * b + 1, 'k': k,
                      'value': value, 'feerate': b + value})
        rates.append(b + value)
    return rates, draws


def seat_rows(scenario: str, l0: bool = False) -> tuple:
    """SEATS[scenario]; with `l0` (D3a-2b-1) the project seat is the L0 project bidder (kind and role
    `L0_PROJECT`, wallet `L0`, PUBLIC) in place of PROJECT_STANDIN."""
    if not l0:
        return SEATS[scenario]
    return tuple((s, PROJECT_L0, I2.L0_WALLET, 'PUBLIC', PROJECT_L0) if role == PROJECT_STANDIN
                 else (s, kind, w, path, role) for s, kind, w, path, role in SEATS[scenario])


def project_role(plan: dict) -> str:
    return PROJECT_L0 if plan.get('l0') else PROJECT_STANDIN


def bidders(scenario: str, run: int, l0: bool = False) -> dict:
    seats = [{'seat': s, 'kind': kind, 'wallet': w, 'path': path} for s, kind, w, path, _ in seat_rows(scenario, l0)]
    doc = {'schema': B.BIDDERS_SCHEMA, 'gates': [{'gate': run, 'seats': seats}]}
    B.parse_bidders(json.dumps(doc).encode('ascii'), l0=l0)
    return doc


def plan_run(scenario: str, seed: bytes, run: int, params: dict, mode: str, l0: bool = False,
             l0_control: bool = False) -> dict:
    """The run's plan: seats, roles, fixed fees or the asymmetry draws, the depth. D3a-2b-2b: CONFIRMATORY only
    with `l0` (the driver's `_run_l0`; CONFIRMATORY_NEEDS_L0_SEAT, exit 3, for the stand-in), never with
    `l0_control` (ITEM4_L0_CONTROL_CONFIRMATORY: the control row is a local check) and not for ITEM4_REORG yet
    (ITEM4_L0_REORG_CONFIRMATORY, exit 3: waits for A's decision on the release in CONFIRMATORY).
    D3a-2b-1: `l0` (the Python API, `claude_track_ardr_l0.item4_l0_run`) puts
    the L0 project bidder in the project seat: its fee is the product's (`fees` None for it), H0 must be
    `I2.L0_H0` (ITEM4_L0_H0). D3a-2b-2a: ITEM4_REORG takes the L0 seat too (its turns by depth, `reorg_turns`)."""
    if mode == 'CONFIRMATORY' and not l0:
        raise Refusal('CONFIRMATORY_NEEDS_L0_SEAT', D.EXIT_PREREQUISITE)   # item 4 is judged on L0's labels
    if mode == 'CONFIRMATORY' and l0_control:
        raise invalid('ITEM4_L0_CONTROL_CONFIRMATORY')
    if mode == 'CONFIRMATORY' and scenario == 'ITEM4_REORG':
        # D3a-2b-2b (B's decision, A asked): the TEST_ONLY Reorg67 release stays EXPLORATORY / PR_SMOKE only
        # (`claude_track_ardr_l0.check_release_test_only`), so a CONFIRMATORY reorg run waits for A's decision on
        # (가) in CONFIRMATORY: refused here, before any node or output, not mid-run at the release.
        raise Refusal('ITEM4_L0_REORG_CONFIRMATORY', D.EXIT_PREREQUISITE)
    if mode not in D.MODES:
        raise invalid('MODE')
    if scenario not in SCENARIOS:
        raise invalid('ITEM4_SCENARIO')
    if not (type(run) is int and 0 <= run < ITEM4_RUNS):
        raise invalid('ITEM4_RUN')
    if not (isinstance(params, dict) and set(params) == set(D.PARAM_KEYS)):
        raise invalid('POLICY_PARAMS')
    if D.pending(params):
        raise Refusal('POLICY_PARAMS_PENDING', D.EXIT_PREREQUISITE)
    D.check_item4_params(params, scenario)
    b, h0 = params['b'], params['H0']
    if l0_control and not l0:
        raise invalid('ITEM4_L0_CONTROL')
    if l0:
        if h0 != I2.L0_H0:
            raise invalid('ITEM4_L0_H0')   # A Q7 / A Q2: L0's profile (H0 1000) is the replay's deployment
        if D.item4_project_p0(b) != I2.l0_p0(b):
            raise invalid('ITEM4_L0_P0_TWO_SOURCES')   # one p_0 in effect (A Q1): the median's and L0's
        I2.check_l0_set(I2.l0_ladder(b, 0))   # as item 2: L0's set has a rung 0 and the wallet takes it
    if (B.CANDIDATE_VSIZE, D.ITEM4_VSIZE) != (213, 213):
        raise invalid('CANDIDATE_VSIZE')
    standin = D.item4_project_fee(b)   # the project seat's configured p_0 (L0's, FD-CT-133) at 213 vB
    roles = {s: role for s, _, _, _, role in seat_rows(scenario, l0)}
    fees: dict[str, list[int] | None] = {}
    plan = {'scenario': scenario, 'run': run, 'mode': mode, 'b': b, 'H0': h0, 'params': dict(params),
            'bidders': bidders(scenario, run, l0), 'roles': roles, 'draws': [], 'feerates': None,
            'depth': depth(run) if scenario == 'ITEM4_REORG' else None, 'asymmetric': None, 'fault': None,
            'miner_policy': MINER_POLICY[scenario], 'not_run': [n for n in (NOT_RUN_L0 if l0 else NOT_RUN)
                                                                  if n['scenario'] in (scenario, '*')],
            'l0': l0, 'l0_turns': l0_turns(scenario, l0_control, depth(run)) if l0 else None,
            'l0_control': l0_control}
    if scenario == 'ITEM4_FEE_ASYMMETRY':
        rates, draws = honest_feerates(seed, run, b)
        median = p50(rates)
        fee = asymmetric_fee(median)
        if fee > MAX_REGISTER_FEE:
            raise invalid('ITEM4_ASYMMETRIC_FEE_CAP')   # before any node: the generator could not build it
        honest = [B.ladder(p, b, 0, B.CANDIDATE_VSIZE)[:1] for p in rates]
        if not all(honest):
            raise invalid('ITEM4_HONEST_LADDER_EMPTY')
        fees = {'S0': [fee], **{f'S{j + 1}': honest[j] for j in range(4)}}
        if l0:
            fees['S1'] = None   # the L0 seat's fee is the product's (its set); rates[0] is its configured p_0
        plan.update(draws=draws, feerates=rates, asymmetric={'median': median, 'factor': ASYMMETRY_FACTOR,
                                                             'feerate': ASYMMETRY_FACTOR * median, 'fee': fee,
                                                             'honest_feerates': rates})
    else:
        for s, role in roles.items():
            fees[s] = {'SELF': [SELF_FEE], 'COMPETITOR': [2 * standin + 1], PROJECT_STANDIN: [standin],
                       PROJECT_L0: None}[role]
    plan['fees'] = fees
    return plan


def asymmetric_record(plan: dict, released: list[dict]) -> dict:
    """The ASYMMETRIC_BID line after the rung-0 releases: the planned median and fee (fixed before any
    release, A 6554792879 Q1) and, apart, what the project seat really sent (`project_sent`) so the judge can
    compare. The asymmetric seat's released fee must be the planned one (ITEM4_ASYMMETRIC_FEE_MOVED)."""
    roles = plan['roles']
    seat = next(s for s, role in roles.items() if role == 'ASYMMETRIC')
    sent = {r['seat']: r for r in released}
    if sent[seat]['fee'] != plan['asymmetric']['fee']:
        raise invalid('ITEM4_ASYMMETRIC_FEE_MOVED')
    project = next(s for s, role in roles.items() if role == PROJECT_STANDIN)
    return {'seat': seat, **plan['asymmetric'], 'project_seat': project,
            'project_configured_p0': plan['asymmetric']['honest_feerates'][0],
            'project_sent': {'fee': sent[project]['fee'], 'txid': sent[project]['txid']}}


def asymmetric_record_l0(plan: dict, released: list[dict]) -> dict:
    """D3a-2b-1: ASYMMETRIC_BID with the L0 seat. The median and the asymmetric fee are the plan's (fixed
    before any release from the configured p_0 and `BID_FEE_2..4`, A 6554792879 Q1: never from what L0 sent).
    `project_sent` is L0's rung 0 as the nodes hold it (its RELEASE from `L0_ADMISSION`: `getmempoolentry` fee
    and vsize, `fee_source` NODE_MEMPOOL_ENTRY), logged beside the configured p_0 for the judge."""
    roles = plan['roles']
    seat = next(s for s, role in roles.items() if role == 'ASYMMETRIC')
    sent = {r['seat']: r for r in released}
    if sent[seat]['fee'] != plan['asymmetric']['fee']:
        raise invalid('ITEM4_ASYMMETRIC_FEE_MOVED')
    project = next(s for s, role in roles.items() if role == PROJECT_L0)
    rung = sent[project]
    if rung.get('sent_by') != I2.L0_SENT_BY or rung.get('fee_source') != 'NODE_MEMPOOL_ENTRY':
        raise invalid('ITEM4_L0_SENT_SOURCE')
    return {'seat': seat, **plan['asymmetric'], 'project_seat': project,
            'project_configured_p0': plan['asymmetric']['honest_feerates'][0],
            'project_p0_sources': {'item4_project_p0': D.item4_project_p0(plan['b']), 'l0_p0': I2.l0_p0(plan['b'])},
            'project_sent': {'fee': rung['fee'], 'vsize': rung['vsize'], 'txid': rung['txid'], 'k': rung['k'],
                             'source': 'L0_ADMISSION', 'fee_source': rung['fee_source']}}


def parse_flags(text: str, n: int) -> list[dict]:
    """D3a-2b-1: the set worker's `flags` line, `r<j>=opening_block_missed:<true|false>,
    reorged_before_inclusion:<true|false>` for every rung of the set once (host `set_flags`), as the core's
    report set them; any other form is ITEM4_L0_FLAGS. Nothing here computes a flag."""
    flags: dict[int, dict] = {}
    for item in text.split(';') if text else []:
        name, _, value = item.partition('=')
        parts = value.split(',')
        if not (name.startswith('r') and name[1:].isdigit() and str(int(name[1:])) == name[1:]
                and [p.partition(':')[0] for p in parts] == list(L0_FLAGS)
                and all(p.partition(':')[2] in ('true', 'false') for p in parts)):
            raise invalid('ITEM4_L0_FLAGS')
        j = int(name[1:])
        if j in flags or j >= n:
            raise invalid('ITEM4_L0_FLAGS')
        flags[j] = {p.partition(':')[0]: p.partition(':')[2] == 'true' for p in parts}
    if sorted(flags) != list(range(n)):
        raise invalid('ITEM4_L0_FLAGS')
    return [flags[j] for j in range(n)]


def expected_verdict(miss: str, outcome: str, offset: int, released: bool) -> str:
    """The verdict a rung with report `outcome` (released or not) has at a turn `offset` blocks after G, by
    the budget's `exact_height_miss` (see `CONTINUE_LOST`). Any other policy: ITEM4_L0_MISS."""
    if miss == 'CONTINUE_WITHIN_LIMITS':
        if outcome.startswith('IncludedNoEffect@'):
            return f'Done:{outcome}'
        return CONTINUE_LOST if released else CONTINUE_UNRELEASED
    if miss == 'STOP_CAMPAIGN':
        return STOP_AT_G if offset == 0 else STOP_LATER
    raise invalid('ITEM4_L0_MISS')


def expected_reorg_labels(turn: str, n: int, h0: int, next_birth: int,
                          miss: str = 'CONTINUE_WITHIN_LIMITS') -> list[dict]:
    """D3a-2b-2a: 045b 4.3's E9-d row with A 6557723699 Q4 (나)'s lock step, for every rung of L0's set at
    one turn of the reorg run (product logic, unit note section 0; never read from the host):

    - G and G + 1 (the replaced chain): rung 0 born at H0 (`Done:Born@<H0>+opening`, outcome
      `Born@<H0>+opening`); every other rung `Done:ProjectBornByOther@<H0>`; no flag set.
    - REORGED and RELEASE (the replacement tip): the open Reorg67 lock refuses every rung
      (`Refuse:Locked(Reorg67)`; the release turn decides before step 6 releases the lock); the report is
      the facts' at the agreed tip: `Stale@<H0>><next birth>`, `opening_block_missed` true.
    - STALE: as a lost gate (`expected_verdict`): rung 0 released, not mined `Refuse:GateAdvanced`; every
      other rung `Wait:OfflineSignaturePending`; `Stale@<H0>><next birth>`, `opening_block_missed` true.

    `reorged_before_inclusion` is false at every turn: block H0 − 1, where rung 0 was submitted, is never
    replaced (machine.rs `reorged_before_inclusion`). Only CONTINUE_WITHIN_LIMITS (ITEM4_L0_MISS)."""
    if miss != 'CONTINUE_WITHIN_LIMITS':
        raise invalid('ITEM4_L0_MISS')
    if turn == 'G' or turn.startswith('G+'):
        return [{'verdict': f'Done:Born@{h0}+opening' if j == 0 else f'Done:ProjectBornByOther@{h0}',
                 'outcome': f'Born@{h0}+opening' if j == 0 else f'ProjectBornByOther@{h0}',
                 'opening_block_missed': False, 'reorged_before_inclusion': False} for j in range(n)]
    stale = f'Stale@{h0}>{next_birth}'
    if turn in ('REORGED', 'RELEASE'):
        return [{'verdict': LOCKED_REORG67, 'outcome': stale, **EXPECTED_FLAGS} for _ in range(n)]
    if turn == 'STALE':
        return [{'verdict': expected_verdict(miss, stale, 1, j == 0), 'outcome': stale, **EXPECTED_FLAGS}
                for j in range(n)]
    raise invalid('ITEM4_L0_TURNS')


def expected_label_line(d: int, h0: int, next_birth: int) -> list[dict]:
    """D3a-2b-2a, A 6557723699 Q4 (나): rung 0's label line, every step kept: `Done:Born` at G (and G + 1),
    `Refuse:Locked(Reorg67)` at REORGED and RELEASE, the release itself (`RELEASE_REORG67_TEST_ONLY`, Reorg67,
    step 6 not performed), then `Stale` at STALE."""
    line = []
    for turn, _ in reorg_turns(d):
        label = expected_reorg_labels(turn, 1, h0, next_birth)[0]
        line.append({'turn': turn, 'verdict': label['verdict'], 'outcome': label['outcome']})
        if turn == 'RELEASE':
            line.append({'step': 'RELEASE_REORG67_TEST_ONLY', 'released': 'reason:Reorg67;step6:Some(NotPerformed)'})
    return line


def expected_l0_labels(scenario: str, offset: int, n: int, h0: int, next_birth: int,
                       miss: str = 'CONTINUE_WITHIN_LIMITS') -> list[dict]:
    """`ITEM4_LABELS` for every rung of L0's set at one turn: the verdict (`expected_verdict` for the run's
    `exact_height_miss`), the report outcome (`IncludedNoEffect@<height>` or `Stale@<G>><next birth>`, the
    host's `set_outcome` form) and the two flags (`EXPECTED_FLAGS`). `next_birth` is the Core replay's next
    birth height at the turn's height."""
    stale = f'Stale@{h0}>{next_birth}'
    first = f'IncludedNoEffect@{h0 + offset}' if label_kind(scenario, offset) == 'INCLUDED' else stale
    outcomes = [first if j == 0 else stale for j in range(n)]
    return [{'verdict': expected_verdict(miss, o, offset, j == 0), 'outcome': o, **EXPECTED_FLAGS}
            for j, o in enumerate(outcomes)]


def judge_l0_labels(log, unit, plan: dict, observations: list[dict], rows: dict[int, dict], miss: str) -> bool:
    """After the final replay: each host turn's verdicts, outcomes and flags against `expected_l0_labels` for
    the run's `exact_height_miss` (A 6557723699 Q1: all three; any one different is a mismatch). One
    ITEM4_LABELS line per turn (`match`, `exact_height_miss`). Returns whether all match; the caller raises
    ITEM4_LABEL_MISMATCH after writing them all."""
    turns = [t for t, _ in plan['l0_turns']]
    if [o['turn'] for o in observations] != turns or any(o['height'] != plan['H0'] + k for o, (_, k)
                                                         in zip(observations, plan['l0_turns'])):
        raise invalid('ITEM4_L0_TURNS')
    ok = True
    for obs in observations:
        n = len(obs['labels'])
        if plan['scenario'] == 'ITEM4_REORG':
            expected = expected_reorg_labels(obs['turn'], n, plan['H0'], rows[obs['height']]['next_birth'], miss)
        else:
            expected = expected_l0_labels(plan['scenario'], obs['height'] - plan['H0'], n, plan['H0'],
                                          rows[obs['height']]['next_birth'], miss)
        got = [{'verdict': label['verdict'], 'outcome': label['outcome'], **flags}
               for label, flags in zip(obs['labels'], obs['flags'])]
        match = got == expected
        ok &= match
        log.write('ITEM4_LABELS', unit, turn=obs['turn'], height=obs['height'], block_hash=obs['block_hash'],
                  labels=got, expected=expected, match=match, exact_height_miss=miss,
                  judged=['verdict', 'outcome', *L0_FLAGS], rule='045b 4.3 (ITEM4_LABELS)')
    return ok


def check_l0_topology(topology, scenario: str) -> list[str]:
    """D3a-2b-1 / D3a-2b-2a: the L0 topology (`L0Topology`). oe's A and B are `oe.Node`s with no `rpcs` set
    (their driver user is oe's `ALLOWED_RPCS`), so this reads `.rpcs` on the miner and the relay only
    (`check_reorg_topology` reads it on A and B: the LATENT of D3a-2b-1's note section 4, fixed for the L0 path
    here). The miner's driver user is its D1 set plus `invalidateblock` exactly for ITEM4_REORG, the relay's
    its D1 set; A and B must be oe nodes (ITEM4_REORG_TOPOLOGY otherwise). Returns the miner driver user's set."""
    if scenario not in L0_SCENARIOS:
        raise invalid('ITEM4_SCENARIO')
    miner = D.ROLE_RPCS['miner'] | (D.REORG_RPCS if scenario == 'ITEM4_REORG' else frozenset())
    if set(topology.nodes['miner'].rpcs) != miner or set(topology.nodes['relay'].rpcs) != D.ROLE_RPCS['relay']:
        raise invalid('ITEM4_REORG_TOPOLOGY')
    if not all(isinstance(topology.nodes[role], oe.Node) for role in ('A', 'B')):
        raise invalid('ITEM4_REORG_TOPOLOGY')
    return sorted(topology.nodes['miner'].rpcs)


def observation_id(scenario: str, run: int) -> str:
    """The item-4 unit is the run: D4's run-level id `OBS-<e><run:07>`."""
    return 'OBS-%d%07d' % (D.EXPERIMENTS.index(scenario) + 1, run)


def check_reorg_topology(topology, scenario: str) -> list[str]:
    """`invalidateblock` on the miner node's driver user exactly when the scenario is ITEM4_REORG
    (ITEM4_REORG_TOPOLOGY otherwise, before anything starts). Returns the miner driver user's set."""
    rpcs = set(topology.nodes['miner'].rpcs)
    if ('invalidateblock' in rpcs) != (scenario == 'ITEM4_REORG') or rpcs - D.ROLE_RPCS['miner'] - D.REORG_RPCS:
        raise invalid('ITEM4_REORG_TOPOLOGY')
    if any(set(topology.nodes[role].rpcs) != D.ROLE_RPCS[role] for role in ('relay', 'A', 'B')):
        raise invalid('ITEM4_REORG_TOPOLOGY')
    return sorted(rpcs)


# ---------------------------------------------------------------------------------------------------------
# Checks after a block (pure: the cells call them directly).

def project_hit(order: list[dict], txids: set[str], outpoint: tuple[str, int], txs: dict[str, D.Tx]) -> list[str]:
    """The block's transactions that are the project's: a listed txid or a spend of its funding outpoint."""
    return [o['txid'] for o in order if o['txid'] in txids
            or o['txid'] in txs and outpoint in set(txs[o['txid']].inputs)]


def _tx_end(reader: D.Reader) -> int:
    """Move `reader` past one serialized transaction (the layout `D.Tx` parses) and return where it ends."""
    reader.take(4)
    segwit = reader.data[reader.at:reader.at + 2] == b'\x00\x01'
    if segwit:
        reader.take(2)
    count = reader.varint()
    for _ in range(count):
        reader.take(36)
        reader.take(reader.varint())
        reader.take(4)
    for _ in range(reader.varint()):
        reader.take(8)
        reader.take(reader.varint())
    if segwit:
        for _ in range(count):
            for _ in range(reader.varint()):
                reader.take(reader.varint())
    reader.take(4)
    return reader.at


def block_transactions(block: dict) -> dict[str, D.Tx]:
    """D3a-2b-1 (WRD3a2b1 P3-1): the block's own transactions, read from the bytes the miner submitted
    (`block_hex`) and keyed by txid, coinbase left out. The header must hash to `block_hash` (the tip every
    waited node reported, `mine4`), the merkle root must be the txids', and the transactions after the coinbase
    must be the block's `order` (same txids, same order), so `project_hit` over `order` with these reads every
    input of every transaction the block holds. ITEM4_BLOCK_BYTES otherwise."""
    try:
        raw = bytes.fromhex(block['block_hex'])
        if len(raw) <= 80 or D.dsha(raw[:80])[::-1].hex() != block['block_hash']:
            raise invalid('ITEM4_BLOCK_BYTES')
        reader = D.Reader(raw)
        reader.take(80)
        txs = []
        for _ in range(reader.varint()):
            begin = reader.at
            txs.append(D.Tx(raw[begin:_tx_end(reader)]))
    except (TypeError, ValueError, KeyError, D.Refusal):   # bad hex, truncated or malformed bytes, wrong hash
        raise invalid('ITEM4_BLOCK_BYTES') from None
    if (reader.at != len(raw) or not txs
            or D.merkle_root([bytes.fromhex(t.txid)[::-1] for t in txs]) != raw[36:68]
            or [t.txid for t in txs[1:]] != [o['txid'] for o in block['order']]):
        raise invalid('ITEM4_BLOCK_BYTES')
    return {t.txid: t for t in txs[1:]}


def block_hit(block: dict, txids: set[str], outpoint: tuple[str, int]) -> list[str]:
    """The L0 path's per-block check input: `project_hit` over the block's own transactions
    (`block_transactions`), so a spend of the funding outpoint is found whatever its txid."""
    return project_hit(block['order'], txids, outpoint, block_transactions(block))


def censor_check(height: int, first: int, hits: list[str]) -> str | None:
    """Inside G … G + 143 no project transaction may be in the block (ITEM4_CENSOR_LEAK); at G + 144 one must be
    (ITEM4_CENSOR_NOT_LIFTED; the stand-in's `censor_run` also requires its last released rung there). Otherwise
    None."""
    index = height - first
    if 0 <= index < D.CENSOR_BLOCKS and hits:
        return 'ITEM4_CENSOR_LEAK'
    if index == D.CENSOR_BLOCKS and not hits:
        return 'ITEM4_CENSOR_NOT_LIFTED'
    return None


def self_check(block: dict, self_txid: str, rivals: set[str]) -> None:
    """Block G: the self REGISTER first (ITEM4_SELF_NOT_FIRST), and its feerate strictly below every other
    released rung's in the block (ITEM4_SELF_FEE_NOT_LOWEST), so the order is the policy's, not the
    feerates'."""
    if not block['order'] or block['order'][0]['txid'] != self_txid:
        raise invalid('ITEM4_SELF_NOT_FIRST')
    own = block['order'][0]
    others = [o for o in block['order'][1:] if o['txid'] in rivals]
    if len(others) != len(rivals) or any(own['fee'] * o['vsize'] >= o['fee'] * own['vsize'] for o in others):
        raise invalid('ITEM4_SELF_FEE_NOT_LOWEST')


def winner_check(block: dict, winner: str, outpoint: tuple[str, int]) -> bool:
    """A replacement block must not hold the replaced winner (ITEM4_WINNER_READDED), by its txid or by any
    spend of the stand-in's funding outpoint, whatever its txid (D3a-2c: `block_hit`, from the block's own
    bytes, as `reorg_block_check_l0`). Returns whether the template offered the winner."""
    if block_hit(block, {winner}, outpoint):
        raise invalid('ITEM4_WINNER_READDED')
    return winner in {t['txid'] for t in block['template']['transactions']}


def replacement_waits(d: int) -> list[tuple[str, ...]]:
    """The roles each of the d + 1 replacement blocks waits for: the miner node only, the last all four."""
    return [('miner',)] * d + [ROLES]


# ---------------------------------------------------------------------------------------------------------
# One block (D.mine with an item-4 context and a chosen set of nodes to wait for; D.mine is unchanged).

def mine4(log, unit, nodes, miner, held, last, timing, context: dict | None = None,
          wait: tuple[str, ...] = ROLES, prepared: bool = False) -> dict:
    t_start = D.CLOCK()
    D.snapshots(log, unit, nodes, held, True)
    if prepared:
        block = miner.submit_prepared()
    elif context is not None:
        block = miner.build_block(item4=context)
    else:
        block = miner.build_block()
    log.write('TEMPLATE', unit, t_ns=block['t_template_ns'], template=block['template'],
              private_set=block['private_set'])
    interval = D.whole_seconds(block['t_submit_ns'] - last[0]) if last[0] else None
    last[0] = block['t_submit_ns']
    log.write('BLOCK', unit, t_ns=block['t_submit_ns'], **{k: block[k] for k in (
        'height', 'block_hex', 'block_hash', 'coinbase_txid', 'coinbase_value', 'miner_policy', 'order', 'cut',
        'dropped', 'private_unresolved', 'submit_result')}, interval_seconds=interval)
    if 'item4' in block:
        log.write('MINER_FILTER', unit, height=block['height'], block_hash=block['block_hash'], **block['item4'])
    if block['submit_result'] is not None:
        raise oe.Mismatch('SUBMITBLOCK_REFUSED')

    def accepted() -> bool:
        return all(nodes[role].call('getbestblockhash') == block['block_hash'] for role in wait)

    try:
        D.wait_until(accepted, 'the block at the waited nodes', D.ACCEPT_SECONDS, POLL)
    except oe.Prerequisite as error:
        if D.node_call_timeout(error):
            raise
        raise oe.Mismatch('BLOCK_NOT_ACCEPTED') from None
    log.write('BLOCK_ACCEPTED', unit, block_hash=block['block_hash'], nodes=sorted(wait))
    held -= {item['txid'] for item in block['order']}
    timing['mine_ns'] += D.CLOCK() - t_start
    timing['mine_blocks'] += 1
    return block


# ---------------------------------------------------------------------------------------------------------
# The run.

def item4_run(plan: dict, seed: bytes, work: Path, log: D.RawLog, topology: D.Topology, cargo: str,
              observation_start: dict | None = None, l0=None) -> dict:
    """One item-4 run on a not yet started `topology` (loopback noban whitelist; `reorg` exactly for
    ITEM4_REORG). Returns the RUN_END summary. An excluded gate writes GATE_END and RUN_END EXCLUDED, then
    raises its code (exit 2). D3a-2b-1: `l0` is the L0 seat (`claude_track_ardr_l0.L0Seat`) exactly when the
    plan has `l0` (ITEM4_L0_ADAPTER otherwise); its thread is stopped before the miner and the nodes, and a
    stop failure never replaces the run's own failure (as item 2's run). B-J5F (A 6656311995 B3): RUN_START
    carries `l0_control` on every item-4 run, true exactly for the censorship run's local control row."""
    if bool(plan.get('l0')) != (l0 is not None):
        raise invalid('ITEM4_L0_ADAPTER')
    p2p_arguments = I2.check_topology(topology)
    miner_rpcs = (check_l0_topology if l0 is not None else check_reorg_topology)(topology, plan['scenario'])
    scenario, run = plan['scenario'], plan['run']
    unit = D.unit_id(scenario, run, gate=run)
    run_unit = D.unit_id(scenario, run)
    worker_dir = work / 'worker'
    worker_dir.mkdir()
    worker = B.Worker(cargo, seed, run, plan['H0'], worker_dir)
    timing = I2.new_timing()
    t_start = D.CLOCK()
    miner = None
    ended = [False]
    phase = ['SETUP']
    failed: list[BaseException] = []
    try:
        try:
            log.write('RUN_START', run_unit,
                      observation_start=observation_start or {'source': 'LOCAL_EXPLORATORY', 'utc': None},
                      miner_policy=plan['miner_policy'], node_versions=D.ROLE_VERSIONS, params=plan['params'],
                      scenario=scenario, gates=[run], depth=plan['depth'], roles=plan['roles'],
                      fees=plan['fees'], project_seat=project_role(plan),
                      self_fee=SELF_FEE if scenario == 'ITEM4_SELF_DEALING' else None, self_fee_rule=(
                          'PRODUCT_FLOOR_ZERO_FEE_NEEDS_SRC' if scenario == 'ITEM4_SELF_DEALING' else None),
                      bidders_sha256=C.doc_sha256(plan['bidders']), p2p_arguments=p2p_arguments,
                      miner_driver_rpcs=miner_rpcs, l0_control=plan.get('l0_control') is True)
            log.write('BIDDERS', run_unit, bidders=plan['bidders'], bidders_sha256=C.doc_sha256(plan['bidders']),
                      draws=plan['draws'], feerates=plan['feerates'])
            log.write('SCENARIO_NOT_RUN', run_unit, not_run=plan['not_run'])
            topology.start()
            nodes = topology.nodes
            miner = D.MinerProcess(nodes['miner'], plan['miner_policy'])
            if l0 is None:
                result = _gate(plan, seed, log, unit, run_unit, nodes, miner, worker, timing, phase)
            else:
                result = _gate_l0(plan, seed, log, unit, run_unit, nodes, miner, worker, timing, phase, l0)
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
                              excluded_observation_ids=[observation_id(scenario, run)])
                except Exception:   # noqa: BLE001 - the original error is the one reported
                    pass
            raise
    finally:
        try:
            if l0 is not None:
                try:
                    l0.stop()   # its thread ends before the nodes stop (item 2's order)
                except Exception as stop_error:
                    if not failed:
                        raise
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


def _gate(plan, seed, log, unit, run_unit, nodes, miner, worker, timing, phase) -> dict:
    scenario, run, b, h0 = plan['scenario'], plan['run'], plan['b'], plan['H0']
    t_setup = D.CLOCK()
    held: set[str] = set()
    last = [0]
    chain = C.Chain(worker, h0, log, timing)
    plan['assignment'] = B.assignment(seed, run)
    gates = plan['bidders']['gates']
    seats = gates[0]['seats']
    by_role = {plan['roles'][s['seat']]: s for s in seats}
    funding = I2._setup(plan, log, run_unit, nodes, miner, held, last, timing, chain, worker, gates)
    timing['setup_ns'] = D.CLOCK() - t_setup
    phase[0] = 'GATE'
    increment, increments = B.node_increments(nodes)   # D3a-2b-1: the larger of Node A's and Node B's
    fees = dict(plan['fees'])
    if scenario == 'ITEM4_CENSORSHIP':
        s = by_role[PROJECT_STANDIN]['seat']
        fees[s] = B.ladder(D.item4_project_p0(b), b, increment, B.CANDIDATE_VSIZE)[:CENSOR_STANDIN_RUNGS]
        if len(fees[s]) != CENSOR_STANDIN_RUNGS:
            raise invalid('ITEM4_STANDIN_LADDER')
    bids = [{'seat': s, 'j': j, 'gate': run, 'fees': fees[s['seat']]} for j, s in enumerate(seats)]
    log.write('GATE_START', unit, gate=run, height=h0, observation_id=observation_id(scenario, run))
    log.write('SCHEDULE', unit, increment=increment, increments=increments, increment_rule='MAX_NODE_A_NODE_B',
              ladders=[fees[s['seat']] for s in seats],
              after_g=[s['seat'] for s in seats if plan['roles'][s['seat']] in AFTER_G.get(scenario, ())],
              rule='G_WHEN_RELEASED_IN_TEMPLATE')
    prepared = miner.prepare_block()
    if prepared['height'] != h0 - 1:
        raise invalid('ITEM2_PREPARED_HEIGHT')
    t_build = D.CLOCK()
    rungs = I2.build_ladders(worker, bids, h0, (h0 - 1, prepared['block_hash']), funding, plan['assignment'])
    timing['build_ns'] = D.CLOCK() - t_build
    for bid in bids:
        log.write('GENERATED', unit, seat=bid['seat']['seat'], ladder=bid['fees'],
                  rungs=[{k: v for k, v in r.items() if k != 'hex'} for r in rungs[bid['j']]])
    block = mine4(log, unit, nodes, miner, held, last, timing, prepared=True)
    if block['block_hash'] != prepared['block_hash']:
        raise invalid('ITEM2_PREPARED_HASH')
    blocks = {h0 - 1: block}
    last_rung: dict[str, dict] = {}
    released: list[dict] = []
    t_release = D.CLOCK()
    late = AFTER_G.get(scenario, ())
    # Desktop P3 r4435089959: I2._release raises GateExcluded (REPLACED_RUNG_NOT_IN_MEMPOOL) when a replaced
    # rung k - 1 is not in Node A's or Node B's mempool within 5 s (the censorship stand-in's rung 1). That is
    # the gate's exclusion, recorded as item 2 records it (GATE_END and RUN_END EXCLUDED, exit 2).
    try:
        for j, s in enumerate(seats):
            if plan['roles'][s['seat']] not in late:
                released.append(I2._release(plan, log, unit, nodes, miner, held, s, rungs[j], 0, D.CLOCK(), last_rung))
        wait_released(nodes, released)
        timing['release_ns'] = D.CLOCK() - t_release
        if plan['asymmetric'] is not None:
            log.write('ASYMMETRIC_BID', unit, **asymmetric_record(plan, released))
        standin = next(j for j, s in enumerate(seats) if plan['roles'][s['seat']] == PROJECT_STANDIN)
        stand_rungs = rungs[standin]
        stand_funding = funding[(seats[standin]['wallet'], run)]
        outpoint = (stand_funding['txid'], stand_funding['vout'])
        context = None
        if scenario == 'ITEM4_SELF_DEALING':
            self_txid = rungs[0][0]['txid']
            context = {'kind': 'SELF', 'height': h0, 'self': self_txid}
        elif scenario == 'ITEM4_CENSORSHIP':
            context = {'kind': 'CENSOR', 'first': h0, 'txids': [stand_rungs[0]['txid']], 'outpoints': [list(outpoint)]}
            log.write('CENSOR_WINDOW', unit, first=h0, last=h0 + D.CENSOR_BLOCKS - 1, lifted=h0 + D.CENSOR_BLOCKS,
                      txids=context['txids'], outpoints=context['outpoints'], seat=seats[standin]['seat'])
        block = mine4(log, unit, nodes, miner, held, last, timing, context=context)
        blocks[h0] = block
        misses = I2.release_misses(last_rung, block['template'], block['private_set'])
        extra: dict = {}
        if misses:
            code = 'RELEASE_NOT_IN_TEMPLATE'
            summary = {'gate': run, 'height': h0, 'block_hash': block['block_hash'], 'misses': misses}
            log.write('GATE_END', unit, status='EXCLUDED', code=code,
                      observation_id=observation_id(scenario, run), **summary)
            return {'status': 'EXCLUDED', 'code': code, 'scenario': scenario, 'winner': None,
                    'excluded_gates': [run], 'excluded_observation_ids': [observation_id(scenario, run)], **summary}
        if scenario == 'ITEM4_SELF_DEALING':
            self_check(block, self_txid, {r['txid'] for s, r in last_rung.items() if plan['roles'][s] != 'SELF'})
            log.write('SELF_REGISTER', unit, txid=self_txid, fee=block['order'][0]['fee'], index=0, height=h0,
                      block_hash=block['block_hash'], seat=seats[0]['seat'], policy=plan['miner_policy'])
        elif scenario == 'ITEM4_CENSORSHIP':
            extra['censor'] = censor_run(plan, log, unit, nodes, miner, held, last, timing, blocks, context,
                                         seats[standin], stand_rungs, outpoint, last_rung)
        elif scenario == 'ITEM4_REORG':
            competitor = next(j for j, s in enumerate(seats) if plan['roles'][s['seat']] == 'COMPETITOR')
            extra['reorg'] = reorg_run(plan, log, unit, nodes, miner, held, last, timing, blocks, seats[competitor],
                                       rungs[competitor], stand_rungs[0]['txid'], last_rung, worker, outpoint)
    except I2.GateExcluded as excluded:
        return gate_excluded(log, unit, scenario, run, h0, blocks, excluded)
    replay = replay_chain(worker, log, unit, h0, blocks, 'FINAL', timing)
    by_txid = {r['txid']: plan['roles'][seats[j]['seat']] for j, ladder in rungs.items() for r in ladder}
    born = replay[0]['born']
    if scenario == 'ITEM4_REORG':
        reorg_final_check(born, extra['reorg']['winner'])
    summary = {'gate': run, 'height': h0, 'block_hash': blocks[h0]['block_hash'], 'born': born,
               'winner': by_txid.get(born[0]) if len(born) == 1 else None, 'last_rungs': last_rung,
               'order': [o['txid'] for o in blocks[h0]['order']], 'tip': max(blocks), **extra}
    log.write('GATE_END', unit, status='OBSERVED', observation_id=observation_id(scenario, run), **summary)
    return {'status': 'DONE', 'scenario': scenario, **summary}


def _gate_l0(plan, seed, log, unit, run_unit, nodes, miner, worker, timing, phase, l0) -> dict:
    """D3a-2b-1: `_gate` with the L0 seat in the project seat (built as item 2's `_gate` with `l0`). Block 1 is
    L0's funding; item 2's setup funds the synthetic seats; L0 fixes, charges and signs its set at H0 − 2; after
    G − 1 only rung 0 is released (no t_G, A Q6: `floor` gets [(0, t0)]), by L0's own step 8, and is read back
    from the product and the nodes (`I2._l0_release`); the driver neither prices nor hands off any L0 rung. Then
    block G under the scenario's miner policy, the host's turns (`L0_TURNS`) and the labels' judgement."""
    scenario, run, b, h0 = plan['scenario'], plan['run'], plan['b'], plan['H0']
    t_setup = D.CLOCK()
    held: set[str] = set()
    last = [0]
    chain = C.Chain(worker, h0, log, timing)
    plan['assignment'] = B.assignment(seed, run)
    seats = plan['bidders']['gates'][0]['seats']
    j_l0 = next(j for j, s in enumerate(seats) if plan['roles'][s['seat']] == PROJECT_L0)
    l0_seat = seats[j_l0]
    chain.add(l0.fund(log, run_unit, nodes))   # block 1: L0's funding coinbase (oe.chain_facts, height 1)
    synthetic = [{'gate': run, 'seats': [s for s in seats if s['kind'] != PROJECT_L0]}]
    funding = I2._setup(plan, log, run_unit, nodes, miner, held, last, timing, chain, worker, synthetic)
    timing['setup_ns'] = D.CLOCK() - t_setup
    phase[0] = 'GATE'
    l0_set = l0.start(log, unit, l0_seat, observation_id(scenario, run), b, nodes)
    increment, increments = B.node_increments(nodes)   # D3a-2b-1: the larger of Node A's and Node B's
    fees = {s['seat']: (list(l0_set) if j == j_l0 else plan['fees'][s['seat']]) for j, s in enumerate(seats)}
    bids = [{'seat': s, 'j': j, 'gate': run, 'fees': fees[s['seat']]} for j, s in enumerate(seats) if j != j_l0]
    log.write('GATE_START', unit, gate=run, height=h0, observation_id=observation_id(scenario, run))
    late = AFTER_G.get(scenario, ())   # D3a-2b-2a: the reorg run's competitor is released after G
    log.write('SCHEDULE', unit, increment=increment, increments=increments, increment_rule='MAX_NODE_A_NODE_B',
              ladders=[fees[s['seat']] for s in seats],
              after_g=[s['seat'] for s in seats if plan['roles'][s['seat']] in late],
              rule='G_WHEN_RELEASED_IN_TEMPLATE', l0_seat=l0_seat['seat'], l0_release_ks=[0])
    prepared = miner.prepare_block()
    if prepared['height'] != h0 - 1:
        raise invalid('ITEM2_PREPARED_HEIGHT')
    t_build = D.CLOCK()
    rungs = I2.build_ladders(worker, bids, h0, (h0 - 1, prepared['block_hash']), funding, plan['assignment'])
    timing['build_ns'] = D.CLOCK() - t_build
    for bid in bids:
        log.write('GENERATED', unit, seat=bid['seat']['seat'], ladder=bid['fees'],
                  rungs=[{k: v for k, v in r.items() if k != 'hex'} for r in rungs[bid['j']]])
    ready = l0.ready(log, unit)   # every rung of L0's set signed at H0 − 2; L0 asks for G − 1
    set_txids = [e['txid'] for e in ready['exports']]
    outpoint = (l0.funding['txid'], l0.funding['vout'])
    block = mine4(log, unit, nodes, miner, held, last, timing, prepared=True)
    if block['block_hash'] != prepared['block_hash']:
        raise invalid('ITEM2_PREPARED_HASH')
    blocks = {h0 - 1: block}
    l0.floor(block['block_hash'], [(0, block['t_submit_ns'])])   # rung 0 only: item 4 has no t_G (A Q6)
    last_rung: dict[str, dict] = {}
    released: list[dict] = []
    t_release = D.CLOCK()
    for j, s in enumerate(seats):
        if j != j_l0 and plan['roles'][s['seat']] not in late:
            released.append(I2._release(plan, log, unit, nodes, miner, held, s, rungs[j], 0, D.CLOCK(), last_rung))
    l0_done = I2._l0_release(log, unit, nodes, l0, l0_seat, last_rung)   # what L0 sent, from the product and nodes
    released.extend(l0_done['records'])
    if [r['k'] for r in l0_done['records']] != [0]:
        raise invalid('ITEM4_L0_RELEASED')   # only rung 0 goes out before G
    r0 = l0_done['records'][0]['txid']
    if r0 != set_txids[0]:
        raise invalid('ITEM4_L0_RELEASED')
    wait_released(nodes, released)   # A Q6, L0's rung 0 included
    timing['release_ns'] = D.CLOCK() - t_release
    if plan['asymmetric'] is not None:
        log.write('ASYMMETRIC_BID', unit, **asymmetric_record_l0(plan, released))
    context = None
    if scenario == 'ITEM4_SELF_DEALING':
        self_txid = rungs[0][0]['txid']
        context = {'kind': 'SELF', 'height': h0, 'self': self_txid}
    elif scenario == 'ITEM4_CENSORSHIP':
        # L0's rung 0 by txid and every rung by its funding outpoint (B's D3a-2b-1 brief item 2).
        context = {'kind': 'CENSOR', 'first': h0, 'txids': [r0], 'outpoints': [list(outpoint)]}
        log.write('CENSOR_WINDOW', unit, first=h0, last=h0 + D.CENSOR_BLOCKS - 1, lifted=h0 + D.CENSOR_BLOCKS,
                  txids=context['txids'], outpoints=context['outpoints'], seat=l0_seat['seat'])
    block = mine4(log, unit, nodes, miner, held, last, timing, context=context)
    blocks[h0] = block
    misses = I2.release_misses(last_rung, block['template'], block['private_set'])
    fields = I2.l0_fields(j_l0, seats, released, l0_set)
    if misses:
        code = 'RELEASE_NOT_IN_TEMPLATE'
        summary = {'gate': run, 'height': h0, 'block_hash': block['block_hash'], 'misses': misses,
                   'code_seats': I2.code_seats(code, misses, []), **fields,
                   'l0_budget_counters': l0.last_counters(log, unit)}
        log.write('GATE_END', unit, status='EXCLUDED', code=code, observation_id=observation_id(scenario, run),
                  **summary)
        return {'status': 'EXCLUDED', 'code': code, 'scenario': scenario, 'winner': None,
                'excluded_gates': [run], 'excluded_observation_ids': [observation_id(scenario, run)], **summary}
    extra: dict = {}
    observations: list[dict] = []
    if scenario == 'ITEM4_SELF_DEALING':
        self_check(block, self_txid, {r['txid'] for s, r in last_rung.items() if plan['roles'][s] != 'SELF'})
        log.write('SELF_REGISTER', unit, txid=self_txid, fee=block['order'][0]['fee'], index=0, height=h0,
                  block_hash=block['block_hash'], seat=seats[0]['seat'], policy=plan['miner_policy'],
                  rivals=sorted(r['txid'] for s, r in last_rung.items() if plan['roles'][s] != 'SELF'))
    if scenario == 'ITEM4_REORG' and block_hit(block, set(set_txids), outpoint) != [r0]:
        raise invalid('ITEM4_L0_NOT_IN_G')   # L0's rung 0 alone of its set is in G, the block it wins
    l0_observe(l0, log, unit, nodes, blocks, 'G', h0, observations)
    if scenario == 'ITEM4_CENSORSHIP':
        extra['censor'] = censor_run_l0(plan, log, unit, nodes, miner, held, last, timing, blocks, context,
                                        set_txids, outpoint, l0, observations)
    elif scenario == 'ITEM4_REORG':
        competitor = next(j for j, s in enumerate(seats) if plan['roles'][s['seat']] == 'COMPETITOR')
        extra['reorg'] = reorg_run_l0(plan, log, unit, nodes, miner, held, last, timing, blocks, seats[competitor],
                                      rungs[competitor], set_txids, outpoint, l0, observations, worker, last_rung)
    replay = replay_chain(worker, log, unit, h0, blocks, 'FINAL', timing)
    rows = {row['height']: row for row in replay}
    matched = judge_l0_labels(log, unit, plan, observations, rows, l0.exact_height_miss)
    if scenario == 'ITEM4_REORG':
        if set(replay[0]['born']) & set(set_txids):
            raise invalid('ITEM4_WINNER_STILL_BORN')   # no L0 rung is born on the FINAL chain
        matched &= judge_label_line(log, unit, plan, observations, extra['reorg']['release'], rows)
    by_txid = {r['txid']: plan['roles'][seats[j]['seat']] for j, ladder in rungs.items() for r in ladder}
    by_txid.update({txid: PROJECT_L0 for txid in set_txids})
    born = replay[0]['born']
    summary = {'gate': run, 'height': h0, 'block_hash': blocks[h0]['block_hash'], 'born': born,
               'winner': by_txid.get(born[0]) if len(born) == 1 else None, 'last_rungs': last_rung,
               'order': [o['txid'] for o in blocks[h0]['order']], 'tip': max(blocks), **fields,
               'l0_turns': [{k: o[k] for k in ('turn', 'height', 'block_hash')} for o in observations],
               'l0_exact_height_miss': l0.exact_height_miss,
               'l0_charged_not_released_after_g': I2.l0_held_after_g(fields, l0_set, observations[0]['labels']),
               'l0_budget_counters': observations[-1]['counters'], **extra}
    if not matched:
        raise invalid('ITEM4_LABEL_MISMATCH')
    log.write('GATE_END', unit, status='OBSERVED', observation_id=observation_id(scenario, run), **summary)
    return {'status': 'DONE', 'scenario': scenario, **summary}


def l0_observe(l0, log, unit, nodes, blocks: dict, turn: str, height: int, observations: list[dict],
               phase: str = 'set_observe', release: dict | None = None) -> dict:
    """One host turn after G (`L0Seat.observe_turn`, the set worker's `set_observe`) with Node A and Node B at
    block `height` (ITEM4_L0_OBSERVE_TIP otherwise). ITEM4_L0_OBSERVE logs the turn name, the height, each
    rung's verdict and outcome (`labels`) and the two flags as the worker's `flags` line gives them
    (`parse_flags`: never computed here), and the wallet's counters. D3a-2b-2a: `phase` `set_reorged`, or
    `set_release` with `release` (the `RELEASE_REORG67_TEST_ONLY` phase's arguments and the driver's reads the
    procedure file must match, `L0Seat.release_reorg67`, which checks that file and removes it on every path);
    the worker's `reorg` and `released` lines are logged as returned."""
    tip = blocks[height]['block_hash']
    if any(nodes[role].call('getbestblockhash') != tip for role in ('A', 'B')):
        raise invalid('ITEM4_L0_OBSERVE_TIP')
    if phase == 'set_release':
        got = l0.release_reorg67(log, unit, release['mark'], release['scenario'], release['mode'], nodes,
                                 release['reads'])
    else:
        got = l0.observe_turn(log, unit, phase)
    flags = parse_flags(got['flags'], len(got['labels']))
    obs = {'turn': turn, 'phase': phase, 'height': height, 'block_hash': tip, 'labels': got['labels'],
           'flags': flags, 'counters': got['counters'], 'reorg': got.get('reorg'),
           'released': got.get('released', '-')}
    if phase == 'set_release':
        obs['procedure'] = {'fields': got['procedure'], 'chains': got['chains'], 'mark': got['mark']}
    log.write('ITEM4_L0_OBSERVE', unit, attempt_id=l0.attempt, flags_source='SET_WORKER_FLAGS_LINE', **obs)
    observations.append(obs)
    return obs


def censor_run_l0(plan, log, unit, nodes, miner, held, last, timing, blocks, context, set_txids, outpoint, l0,
                  observations) -> dict:
    """D3a-2b-1: blocks G + 1 … G + 144 under the censor context with the L0 seat (block G and its turn by the
    caller). No L0 rung is released after G (B Q7: the product refuses a release after G). Every block G …
    G + 144 is checked with `censor_check`, its hits from `block_hit`: a transaction of the block (read from
    the block's own bytes, `block_transactions`) is L0's when its txid is one of the set's rungs or when any of
    its inputs spends L0's funding outpoint, whatever its txid (WRD3a2b1 P3-1). While the window lasts L0's
    rung 0 must stay in Node A's and Node B's mempools (ITEM4_L0_CENSORED_LEFT_MEMPOOL); the host turns at
    G + 143 and G + 144 (`L0_TURNS`)."""
    h0 = plan['H0']
    r0 = context['txids'][0]
    txids = set(set_txids)
    hits = {h0: block_hit(blocks[h0], txids, outpoint)}
    code = censor_check(h0, h0, hits[h0])
    if code:
        raise invalid(code)
    checked = [h0]
    l0_in_mempools(nodes, r0)
    turns = {h0 + offset: turn for turn, offset in plan['l0_turns'] if offset}
    for height in range(h0 + 1, h0 + D.CENSOR_BLOCKS + 1):
        block = mine4(log, unit, nodes, miner, held, last, timing, context=context)
        if block['height'] != height:
            raise invalid('ITEM4_HEIGHT')
        blocks[height] = block
        hits[height] = block_hit(block, txids, outpoint)
        code = censor_check(height, h0, hits[height])
        if code:
            raise invalid(code)
        if height < h0 + D.CENSOR_BLOCKS:
            l0_in_mempools(nodes, r0)
            checked.append(height)
        if height in turns:
            l0_observe(l0, log, unit, nodes, blocks, turns[height], height, observations)
    lifted = h0 + D.CENSOR_BLOCKS
    if max(blocks) != lifted or lifted not in hits:
        raise invalid('ITEM4_CENSOR_END')
    code = censor_check(lifted, h0, hits[lifted])
    if code:
        raise invalid(code)
    log.write('CENSOR_MEMPOOL', unit, txid=r0, nodes=['A', 'B'], heights=[checked[0], checked[-1]],
              blocks=len(checked))
    return {'first': h0, 'last': lifted - 1, 'lifted': lifted, 'lifted_txids': hits[lifted],
            'censored_blocks': D.CENSOR_BLOCKS, 'released_rungs': [r0], 'set_txids': sorted(txids),
            'mempool_checked_blocks': len(checked)}


def l0_in_mempools(nodes, txid: str) -> None:
    """L0's censored rung 0 is in Node A's and Node B's mempools (ITEM4_L0_CENSORED_LEFT_MEMPOOL)."""
    if any(txid not in set(nodes[role].call('getrawmempool')) for role in ('A', 'B')):
        raise invalid('ITEM4_L0_CENSORED_LEFT_MEMPOOL')


def gate_excluded(log, unit, scenario: str, run: int, h0: int, blocks: dict, excluded) -> dict:
    """An exclusion raised during a release step (`I2.GateExcluded`, today only REPLACED_RUNG_NOT_IN_MEMPOOL):
    GATE_END EXCLUDED with the original code and detail and `code_seats` (the seat whose rung was missing), as
    item 2 writes it; `block_hash` is block G's when it was mined (a censorship run's rung 1 comes after G),
    else null. The caller writes RUN_END EXCLUDED and raises the code (exit 2)."""
    detail = excluded.detail
    summary = {'gate': run, 'height': h0, 'block_hash': blocks[h0]['block_hash'] if h0 in blocks else None,
               'misses': [], 'code_seats': [detail['replaced_missing']['seat']], **detail}
    log.write('GATE_END', unit, status='EXCLUDED', code=excluded.code,
              observation_id=observation_id(scenario, run), **summary)
    return {'status': 'EXCLUDED', 'code': excluded.code, 'scenario': scenario, 'winner': None,
            'excluded_gates': [run], 'excluded_observation_ids': [observation_id(scenario, run)], **summary}


def wait_released(nodes, released: list[dict], seconds: float = 120.0) -> None:
    """A Q6: block G waits until every released PUBLIC rung is at the miner node (its template is checked
    after: RELEASE_NOT_IN_TEMPLATE)."""
    public = {r['txid'] for r in released if r['path'] == 'PUBLIC' and r['handed_off']}
    try:
        D.wait_until(lambda: public <= set(nodes['miner'].call('getrawmempool')), 'the released rungs at the miner',
                     seconds, POLL)
    except oe.Prerequisite as error:
        if D.node_call_timeout(error):
            raise
        raise oe.Prerequisite('ITEM4_RELEASE_NOT_AT_MINER') from None


def censor_run(plan, log, unit, nodes, miner, held, last, timing, blocks, context, seat, ladder, outpoint,
               last_rung) -> dict:
    """Blocks G + 1 … G + 144 under the censor context (block G is mined by the caller). The stand-in's rung 1
    (a new txid on the same funding outpoint) is released after block G. Each block is checked with
    `censor_check`, its hits from `block_hit` (D3a-2c, as `censor_run_l0`): a transaction of the block, read
    from the block's own bytes, is the stand-in's when its txid is one of the ladder's rungs or when any of its
    inputs spends the stand-in's funding outpoint, whatever its txid. At G + 144 the hits must hold the
    stand-in's last released rung, rung 1, by its txid (D3a-2c pre-PR P3-1: a re-signed spend of the outpoint
    alone is not the lift; ITEM4_CENSOR_NOT_LIFTED)."""
    h0 = plan['H0']
    txids = {r['txid'] for r in ladder}
    hits = {h0: block_hit(blocks[h0], txids, outpoint)}
    code = censor_check(h0, h0, hits[h0])
    if code:
        raise invalid(code)
    I2._release(plan, log, unit, nodes, miner, held, seat, ladder, 1, D.CLOCK(), last_rung)
    wait_released(nodes, [{'txid': ladder[1]['txid'], 'path': 'PUBLIC', 'handed_off': True}])
    for height in range(h0 + 1, h0 + D.CENSOR_BLOCKS + 1):
        block = mine4(log, unit, nodes, miner, held, last, timing, context=context)
        if block['height'] != height:
            raise invalid('ITEM4_HEIGHT')
        blocks[height] = block
        hits[height] = block_hit(block, txids, outpoint)
        code = censor_check(height, h0, hits[height])
        if code:
            raise invalid(code)
    lifted = h0 + D.CENSOR_BLOCKS
    # A 6556082072 P3-1: the run must have reached G + 144 and that block must hold the project's rung,
    # checked again here apart from the loop (a loop that stopped early would otherwise end DONE).
    if max(blocks) != h0 + D.CENSOR_BLOCKS or h0 + D.CENSOR_BLOCKS not in hits:
        raise invalid('ITEM4_CENSOR_END')
    code = censor_check(h0 + D.CENSOR_BLOCKS, h0, hits[h0 + D.CENSOR_BLOCKS])
    if code:
        raise invalid(code)
    if ladder[1]['txid'] not in hits[lifted]:
        raise invalid('ITEM4_CENSOR_NOT_LIFTED')   # pre-PR P3-1: the last released rung itself
    return {'first': h0, 'last': lifted - 1, 'lifted': lifted, 'lifted_txids': hits[lifted],
            'censored_blocks': D.CENSOR_BLOCKS, 'released_rungs': sorted(txids)}


def reorg_run(plan, log, unit, nodes, miner, held, last, timing, blocks, seat, ladder, winner, last_rung,
              worker, outpoint) -> dict:
    """The competitor's rung 0 after G; depth 2 mines G + 1; `invalidateblock` G on the miner node; d + 1
    replacement blocks without the winner (`winner_check`: its txid or any spend of the stand-in's funding
    `outpoint`), waiting as `replacement_waits`."""
    h0, d = plan['H0'], plan['depth']
    I2._release(plan, log, unit, nodes, miner, held, seat, ladder, 0, D.CLOCK(), last_rung)
    wait_released(nodes, [{'txid': ladder[0]['txid'], 'path': 'PUBLIC', 'handed_off': True}])
    if d == 2:
        blocks[h0 + 1] = mine4(log, unit, nodes, miner, held, last, timing)
    replaced = [blocks[h] for h in range(h0, h0 + d)]
    if [b['height'] for b in replaced] != list(range(h0, h0 + d)):
        raise invalid('ITEM4_HEIGHT')
    t_wait = D.CLOCK()
    D.sleep_until(blocks[h0]['t_template_answer_ns'] + TEMPLATE_CACHE_NS)
    waited = D.CLOCK() - t_wait
    timing['template_cache_wait_ns'] = waited
    nodes['miner'].call('invalidateblock', blocks[h0]['block_hash'])
    best = nodes['miner'].call('getbestblockhash')
    if best != blocks[h0 - 1]['block_hash']:
        raise invalid('ITEM4_REORG_TIP')
    context = {'kind': 'REORG', 'drop': [winner]}
    replacement, offered = [], []
    for k, wait in enumerate(replacement_waits(d)):
        block = mine4(log, unit, nodes, miner, held, last, timing, context=context, wait=wait)
        if block['height'] != h0 + k:
            raise invalid('ITEM4_HEIGHT')
        offered.append(winner_check(block, winner, outpoint))
        if k == 0 and ladder[0]['txid'] not in {t['txid'] for t in block['template']['transactions']}:
            raise invalid('ITEM4_TEMPLATE_STALE')   # the competitor released after G must be offered at G'
        replacement.append(block)
    for k, block in enumerate(replacement):
        blocks[h0 + k] = block
    record = {'depth': d, 'invalidated': replaced[0]['block_hash'], 'node': 'miner',
              'replaced': [b['block_hash'] for b in replaced], 'replacement': [b['block_hash'] for b in replacement],
              'winner': winner, 'winner_offered': offered, 'template_cache_wait_ns': waited}
    log.write('REORG', unit, **record)
    # The Core replay of the replaced blocks (G … G + d − 1, the winner's chain): the births at G there.
    record['replaced_born'] = replay_chain(worker, log, unit, h0, {b['height']: b for b in replaced},
                                           'REPLACED', timing)[0]['born']
    if record['replaced_born'] != [winner]:
        raise invalid('ITEM4_REPLACED_NOT_WINNER')   # pre-PR P3-2: the replaced chain's one birth is the winner
    return record


def reorg_block_check_l0(block: dict, set_txids: list[str], outpoint: tuple[str, int]) -> bool:
    """D3a-2b-2a: a replacement block of the L0 reorg run holds no L0 transaction, by txid (any rung of the
    set) or by L0's funding outpoint (any spend of it, whatever its txid: `block_hit` reads the block's own
    bytes), ITEM4_WINNER_READDED otherwise. Returns whether the template offered rung 0 again."""
    if block_hit(block, set(set_txids), outpoint):
        raise invalid('ITEM4_WINNER_READDED')
    return set_txids[0] in {t['txid'] for t in block['template']['transactions']}


def reorg_run_l0(plan, log, unit, nodes, miner, held, last, timing, blocks, seat, ladder, set_txids, outpoint, l0,
                 observations, worker, last_rung) -> dict:
    """D3a-2b-2a: after block G (L0's rung 0 born; the host's G turn by the caller) the competitor's rung 0 is
    released; depth 2 mines G + 1 and the host turns there too; the miner invalidates G and builds the d + 1
    replacement blocks (`reorg_block_check_l0`: no L0 transaction, by txid or by the funding outpoint), the
    last one waited for by all four nodes. Then, on the replacement tip G + d: the `set_reorged` turn (its
    reorg line must be the reorg the driver made: the host's last tip, the replacement's hash there, the
    ancestor G − 1: ITEM4_L0_REORG_SEEN), the `RELEASE_REORG67_TEST_ONLY` phase (the procedure file checked
    against the same reads with `oe.check_reorg_procedure` inside `L0Seat.release_reorg67`, which removes it
    and the release record on every path; pre-PR P3-1: this function's try/finally removes both again around
    the whole RELEASE turn, `l0_observe` included) and the STALE turn. Every block and
    turn is logged with its height and hash."""
    h0, d = plan['H0'], plan['depth']
    if d != depth(plan['run']):
        raise invalid('ITEM4_DEPTH')
    r0 = set_txids[0]
    I2._release(plan, log, unit, nodes, miner, held, seat, ladder, 0, D.CLOCK(), last_rung)
    wait_released(nodes, [{'txid': ladder[0]['txid'], 'path': 'PUBLIC', 'handed_off': True}])
    for k in range(1, d):
        blocks[h0 + k] = mine4(log, unit, nodes, miner, held, last, timing)
        if blocks[h0 + k]['height'] != h0 + k:
            raise invalid('ITEM4_HEIGHT')
        l0_observe(l0, log, unit, nodes, blocks, f'G+{k}', h0 + k, observations)
    replaced = [blocks[h] for h in range(h0, h0 + d)]
    if [b['height'] for b in replaced] != list(range(h0, h0 + d)):
        raise invalid('ITEM4_HEIGHT')
    local = (observations[-1]['height'], observations[-1]['block_hash'])   # the host's tip before the reorg
    if local != (h0 + d - 1, replaced[-1]['block_hash']):
        raise invalid('ITEM4_L0_TURNS')   # the host saw every block the reorg replaces
    t_wait = D.CLOCK()
    D.sleep_until(blocks[h0]['t_template_answer_ns'] + TEMPLATE_CACHE_NS)
    waited = D.CLOCK() - t_wait
    timing['template_cache_wait_ns'] = waited
    nodes['miner'].call('invalidateblock', blocks[h0]['block_hash'])
    if nodes['miner'].call('getbestblockhash') != blocks[h0 - 1]['block_hash']:
        raise invalid('ITEM4_REORG_TIP')
    context = {'kind': 'REORG', 'drop': [r0]}
    replacement, offered = [], []
    for k, wait in enumerate(replacement_waits(d)):
        block = mine4(log, unit, nodes, miner, held, last, timing, context=context, wait=wait)
        if block['height'] != h0 + k:
            raise invalid('ITEM4_HEIGHT')
        offered.append(reorg_block_check_l0(block, set_txids, outpoint))
        if k == 0 and ladder[0]['txid'] not in {t['txid'] for t in block['template']['transactions']}:
            raise invalid('ITEM4_TEMPLATE_STALE')   # the competitor released after G must be offered at G'
        replacement.append(block)
    for k, block in enumerate(replacement):
        blocks[h0 + k] = block
    tip = replacement[-1]
    record = {'depth': d, 'invalidated': replaced[0]['block_hash'], 'node': 'miner',
              'replaced': [{'height': b['height'], 'block_hash': b['block_hash']} for b in replaced],
              'replacement': [{'height': b['height'], 'block_hash': b['block_hash']} for b in replacement],
              'tip': {'height': tip['height'], 'block_hash': tip['block_hash']}, 'winner': r0,
              'winner_offered': offered, 'set_txids': list(set_txids), 'outpoint': list(outpoint),
              'checked_by': ['SET_TXIDS', 'FUNDING_OUTPOINT'], 'template_cache_wait_ns': waited}
    log.write('REORG', unit, **record)
    record['replaced_born'] = replay_chain(worker, log, unit, h0, {b['height']: b for b in replaced},
                                           'REPLACED', timing)[0]['born']
    if record['replaced_born'] != [r0]:
        raise invalid('ITEM4_REPLACED_NOT_WINNER')   # the replaced chain's one birth is L0's rung 0
    at_local = oe.internal(blocks[local[0]]['block_hash'])   # the replacement's block at the host's old height
    ancestor = (h0 - 1, blocks[h0 - 1]['block_hash'])
    seen = l0_observe(l0, log, unit, nodes, blocks, 'REORGED', tip['height'], observations, 'set_reorged')
    expected = {'raised': True, 'local': [local[0], oe.internal(local[1])], 'at_local': at_local,
                'ancestor': [ancestor[0], oe.internal(ancestor[1])]}
    if seen['reorg'] != expected:
        raise invalid('ITEM4_L0_REORG_SEEN')
    try:
        released = l0_observe(l0, log, unit, nodes, blocks, 'RELEASE', tip['height'], observations, 'set_release',
                              {'mark': RELEASE_REORG67_TEST_ONLY, 'scenario': plan['scenario'],
                               'mode': plan['mode'], 'reads': (local, at_local, ancestor)})
    finally:
        l0.remove_release_files()   # #450 runbook section 2 item 5, as oe.LostContext.release
    if released['reorg'] is not None:
        raise invalid('ITEM4_L0_REORG_SEEN')   # the release turn raises nothing (the 1e-2b-2b release rows)
    stale = l0_observe(l0, log, unit, nodes, blocks, 'STALE', tip['height'], observations)
    if stale['reorg'] is not None:
        raise invalid('ITEM4_L0_REORG_SEEN')
    record['release'] = {'turn': 'RELEASE', 'height': tip['height'], 'block_hash': tip['block_hash'],
                         'step': RELEASE_REORG67_TEST_ONLY, 'released': released['released'],
                         'procedure_sha256': released['procedure']['fields'].get('procedure_sha256'),
                         'chains': released['procedure']['chains'], 'local': list(local),
                         'at_local': blocks[local[0]]['block_hash'], 'ancestor': list(ancestor)}   # display order
    log.write('ITEM4_L0_RELEASE', unit, attempt_id=l0.attempt, **record['release'])
    return record


def judge_label_line(log, unit, plan: dict, observations: list[dict], release: dict, rows: dict) -> bool:
    """D3a-2b-2a, A 6557723699 Q4 (나): rung 0's label line, every turn's verdict and outcome in order with
    the release step after the RELEASE turn, against `expected_label_line` (nothing dropped, nothing added).
    One ITEM4_L0_LABEL_LINE line (each step with its height and tip hash); returns whether it matches."""
    tip = plan['H0'] + plan['depth']
    line = []
    for obs in observations:
        line.append({'turn': obs['turn'], 'verdict': obs['labels'][0]['verdict'],
                     'outcome': obs['labels'][0]['outcome']})
        if obs['turn'] == 'RELEASE':
            line.append({'step': release['step'], 'released': release['released']})
    expected = expected_label_line(plan['depth'], plan['H0'], rows[tip]['next_birth'])
    match = line == expected
    steps = [{**step, 'height': obs['height'], 'block_hash': obs['block_hash']} for step, obs in
             zip([x for x in line if 'turn' in x], observations)]
    log.write('ITEM4_L0_LABEL_LINE', unit, line=line, expected=expected, match=match, steps=steps,
              release={k: release[k] for k in ('height', 'block_hash', 'step', 'released')},
              rule='045b 4.3 E9-d with A 6557723699 Q4 (나): '
                   'Done:Born (G) -> Refuse:Locked(Reorg67) -> (release) -> Stale')
    return match


def reorg_final_check(born: list[str], winner: str) -> None:
    """Pre-PR P3-2: after the reorg the FINAL chain must not have the replaced winner born."""
    if winner in born:
        raise invalid('ITEM4_WINNER_STILL_BORN')


def replay_chain(worker, log, unit, h0: int, blocks: dict, chain: str, timing: dict | None = None) -> list[dict]:
    """The Core replay (`BIRTHS`, from H0 with no state) of `blocks` from H0 to the highest height; one
    CORE_REPLAY line per height with `chain` (FINAL or REPLACED)."""
    heights = sorted(h for h in blocks if h >= h0)
    if heights != list(range(h0, h0 + len(heights))) or not heights:
        raise invalid('ITEM4_HEIGHT')
    t0 = D.CLOCK()
    answer = worker.births(h0, [blocks[h]['block_hex'] for h in heights], None, h0)
    if timing is not None:
        timing['birth_ns'] += D.CLOCK() - t0
        timing['birth_calls'] += 1
    for row in answer['rows']:
        log.write('CORE_REPLAY', unit, chain=chain, height=row['height'], born=row['born'],
                  next_birth=row['next_birth'], state_sha256=row['state_sha256'])
    return answer['rows']


if __name__ == '__main__':
    sys.exit(D.EXIT_REFUSAL)   # no CLI: the driver runs ITEM4 (`run --experiment ITEM4_...`)
