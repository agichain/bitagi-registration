#!/usr/bin/env python3
"""CT-P5-001 D1: the ARDR campaign driver's topology, miner process, seed draw and policy read.

Class T Regtest development evidence only; never mainnet, never S17-PREP, and no ARDR verdict. Sources:
A's unit request #258 issuecomment-6537782009 (Q2, Q3, Q6, Q8, Q9; section 4 row D1), B's acknowledgement
-6537801599 (defaults (a)-(d)) and the 045b draft section 4.6 (`CT-P3-045b_PREREGISTRATION_DRAFT_EN.md`),
which is a draft input, not frozen bytes. The format is `docs/claude-track/formats/ARDR_RUN_V1.md`.

What D1 builds:

- Topology: four fresh Regtest nodes per run, the miner node and the relay node (Bitcoin Core 31.1, the
  `--node-a` binaries), and the `testmempoolaccept` pair Node A (31.1) and Node B (30.3). The node object is
  `claude_track_regtest_offline_export.Node` (as `oe`), started by `RoleNode` with its own whitelist: each
  node's driver user is whitelisted for exactly its role's set (`ROLE_RPCS`), the miner node's second user
  (the miner process's) for exactly `MINER_RPCS`, the cookie for nothing; no other user. A credential
  reaches one node only. The cookie stays in the run's data directory.
- The miner process: a separate process (`miner` subcommand) that holds the miner process's credential
  on the miner node only.
  Per block it takes `getblocktemplate`, adds the private set it holds in memory, orders the union under
  the named miner policy, builds the block itself (coinbase with the BIP34 height and, when a transaction
  has a witness, the witness commitment; merkle root; header; Regtest proof of work) and sends it with
  `submitblock`. Its RPC set is `MINER_RPCS`: no `sendrawtransaction`, no `generateblock`, no
  `generatetodescriptor`. D1 built `ITEM2_DEFAULT`; D2-3a the ITEM1 and POOL variants; D3a-2a the three
  item-4 variants (`item4_filter`, format doc section 23). No name is reserved any more.
- The seed draw (`draw`): 045b 4.6's SHA-256 mapping with rejection sampling, and the draw table's labels.
- The policy read: the policy file's SHA-256 goes into every raw-log line. CONFIRMATORY refuses a PENDING
  value (exit 3), a registration or policy hash that differs (exit 6) and an experiment the registration's
  `experiments` does not list (exit 6, FD-CT-133); EXPLORATORY and PR_SMOKE accept a
  draft policy and mark every line EXPLORATORY.
- The raw log (JSON Lines): one monotonic clock (`time.monotonic_ns`, CLOCK_MONOTONIC, shared by the driver
  and the miner process on one host), every template with the private set, every submitted block's bytes
  and hash, mempool snapshots, unit identifiers. The driver records; A's judge decides.

Exit codes (AGENTS.md section 12): 0 run done, 2 validation failure, 3 missing prerequisite, 4 internal
error, 5 a run secret would enter the log, 6 release-policy refusal (hash binding). Optimized Python (-O) is
refused. Stdlib only. TEST_ONLY material only: every output is P2WSH(OP_TRUE), so no key exists.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).absolute().parent))
import claude_track_regtest_offline_export as oe  # noqa: E402
from common import bounded_regular_bytes, strict_json_bytes  # noqa: E402

EXIT_DONE, EXIT_VALIDATION, EXIT_PREREQUISITE, EXIT_INTERNAL, EXIT_SECURITY, EXIT_REFUSAL = 0, 2, 3, 4, 5, 6
CLOCK = time.monotonic_ns

LOG_SCHEMA = 'BITAGI_CT_ARDR_RAW_V1'
POLICY_SCHEMA = 'BITAGI_CT_ARDR_POLICY_V1'
REGISTRATION_KEY = 'ardr_policy_sha256'   # D1 placeholder for A's P5-005 registration (format doc section 4)
# FD-CT-133 (format doc, the 2026-11-12 addition to section 4): the experiments a registration covers. When the
# registration names them, a CONFIRMATORY run of any other experiment is EXPERIMENT_NOT_REGISTERED (exit 6).
REGISTRATION_EXPERIMENTS_KEY = 'experiments'
MODES = ('CONFIRMATORY', 'EXPLORATORY', 'PR_SMOKE')
LABELS = ['CLASS_T', 'REGTEST', 'TEST_ONLY_OP_TRUE_OUTPUTS', 'CLASS_T_DEVELOPMENT_EVIDENCE_NOT_S17_PREP',
          'DRIVER_RECORD_NOT_VERDICT']
EXPERIMENTS = ('ITEM1', 'ITEM2', 'ITEM3', 'ITEM4_SELF_DEALING', 'ITEM4_FEE_ASYMMETRY', 'ITEM4_CENSORSHIP',
               'ITEM4_REORG', 'POOL')
POLICY_LIMIT = 1024 * 1024
LOG_LIMIT = 256 * 1024 * 1024
# D2-3a round 1 (P3-2): every line but RUN_END must leave this much of LOG_LIMIT free, so a run refused with
# LOG_BOUND can still write its RUN_END FAILED line.
LOG_RESERVE = 1024 * 1024
HEX64 = re.compile(r'[0-9a-f]{64}\Z')
NEEDLE_MIN = 8   # U4: the shortest raw-log needle (a node user's name is 13 or more, the rest 32 to 64 hex)


class Refusal(Exception):
    """A typed outcome: a stable code and its exit code. No input text is echoed."""

    def __init__(self, code: str, exit_code: int):
        super().__init__(code)
        self.code, self.exit_code = code, exit_code


def invalid(code: str) -> Refusal:
    return Refusal(code, EXIT_VALIDATION)


CODE_WORD = re.compile(r'[A-Z][A-Z0-9_]*\Z')


def error_code(kind: str, error: Exception) -> str:
    """`kind` and the leading code words of `error`'s message: never a node's stderr, a path or a name."""
    words = []
    for word in str(error).split()[:3]:
        if not CODE_WORD.match(word):
            break
        words.append(word)
    return ' '.join([kind, *words])


# ---------------------------------------------------------------------------------------------------------
# Seed draw (045b section 4.6). Self-contained: A's judge re-implements it and compares (Q4).

DRAW_TABLE = {
    'ITEM1': (re.compile(r'(OWNER|ANCESTRY|KEY_REUSE)_W(0[0-9]|[12][0-9]|3[0-9])\Z'),
              re.compile(r'WINNER_G(0[0-9][0-9]|1[2-9][0-9])\Z')),   # gates 100-119 have no draw
    'ITEM2': (re.compile(r'BID_FEE_[0-4]\Z'), re.compile(r'PRIVATE_FEE\Z'), re.compile(r'PUBLIC_FEE_[1-4]\Z'),
              re.compile(r'GATE_INTERVAL\Z')),
    'POOL': (re.compile(r'PRODUCER_H(0|[1-9][0-9]*)\Z'),),
    # D3a-2a (A 6551547851 Q5, B 6554438116 Q1-Q2; DRAFT, PENDING_FREEZE, 045b's draw table is A's freeze
    # PR): seats 2-4 of a fee-asymmetry run draw item 2's label form with n = 3b + 1; seat 0 (asymmetric) and
    # seat 1 (the project seat, here its stand-in) draw nothing.
    'ITEM4_FEE_ASYMMETRY': (re.compile(r'BID_FEE_[2-4]\Z'),),
}
# The draw table's fixed ranges, by label prefix (045b 4.6). The ITEM2 fee labels' n depends on b and p, so
# it is the caller's.
DRAW_N = (('OWNER_W', 10), ('ANCESTRY_W', 100), ('KEY_REUSE_W', 100), ('WINNER_G', 40), ('GATE_INTERVAL', 1200),
          ('PRODUCER_H', 100))
U32 = 2**32
U64 = 2**64
GATE_INTERVAL_N = 1200
MAX_DRAW_TRIES = 1 << 20   # a retry happens with probability below 1/2 per try


def draw_label_allowed(e: str, label: str) -> bool:
    return any(pattern.match(label) for pattern in DRAW_TABLE.get(e, ()))


def draw_fixed_n(label: str) -> int | None:
    """The draw table's n for `label`, or None where the table leaves it to b and p (ITEM2 fees)."""
    return next((n for prefix, n in DRAW_N if label.startswith(prefix)), None)


def draw_digest(seed: bytes, e: str, r: int, label: str, k: int) -> bytes:
    """D = SHA-256(seed || e || 0x00 || u32be(r) || label || 0x00 || u32be(k))."""
    return hashlib.sha256(seed + e.encode('ascii') + b'\x00' + r.to_bytes(4, 'big') + label.encode('ascii')
                          + b'\x00' + k.to_bytes(4, 'big')).digest()


def accept(x: int, n: int) -> int | None:
    """x mod n when x < floor(2^64 / n) * n, else None (retry with k + 1)."""
    return x % n if x < (U64 // n) * n else None


def draw(seed: bytes, e: str, r: int, label: str, n: int) -> tuple[int, int]:
    """The integer uniform in [0, n) for choice `label` of run `r` of experiment `e`, and the k that gave it."""
    if not isinstance(seed, bytes) or len(seed) != 32:
        raise invalid('DRAW_SEED')
    if not draw_label_allowed(e, label):
        raise invalid('DRAW_LABEL')
    if not (type(r) is int and 0 <= r < U32 and type(n) is int and 1 <= n <= U64):
        raise invalid('DRAW_RANGE')
    if draw_fixed_n(label) not in (None, n):
        raise invalid('DRAW_N')
    for k in range(min(MAX_DRAW_TRIES, U32)):
        value = accept(int.from_bytes(draw_digest(seed, e, r, label, k)[:8], 'big'), n)
        if value is not None:
            return value, k
    raise Refusal('DRAW_TRIES', EXIT_INTERNAL)


def gate_interval_seconds(seed: bytes, r: int) -> tuple[int, int]:
    """t_G = GATE_INTERVAL value + 1 seconds (uniform in [1, 1200]), and the k used."""
    value, k = draw(seed, 'ITEM2', r, 'GATE_INTERVAL', GATE_INTERVAL_N)
    return value + 1, k


def whole_seconds(ns: int) -> int:
    """A measured duration in whole seconds, rounded up (045b 4.6)."""
    if ns < 0:
        raise invalid('DURATION_NEGATIVE')
    return -(-ns // 1_000_000_000)


# ---------------------------------------------------------------------------------------------------------
# Policy file and registration (A Q6; format doc section 3).

POLICY_KEYS = {'schema', 'seed', 'counts', 'experiments', 'bidders'}
POLICY_OPTIONAL = {'thresholds'}
# D2-3a builds ITEM1_WINNER_ONLY (the gate filter in `Miner.build_block`) and POOL_50_30_20 (three miner
# processes, a producer tag in each coinbase); both order what they keep by ancestor feerate.
BUILT_POLICIES = ('ITEM2_DEFAULT', 'ITEM1_WINNER_ONLY', 'POOL_50_30_20')
# D2-3a round 1 (P2-1): the campaign experiments run one miner variant each, and no other experiment may name
# those variants. A mismatch is refused in every mode (POLICY_MINER_EXPERIMENT, exit 2).
CAMPAIGN_MINER = {'ITEM1': 'ITEM1_WINNER_ONLY', 'POOL': 'POOL_50_30_20'}
# D3a-2a: the three item-4 miner variants are built (`item4_filter` in `Miner.build_block`, per-block context
# from `claude_track_ardr_item4`); every item-4 experiment runs exactly one policy, and no other experiment
# may name an item-4 variant. Refused like CAMPAIGN_MINER, in every mode (POLICY_MINER_EXPERIMENT, exit 2).
ITEM4_POLICIES = ('ITEM4_SELF_FIRST_ZERO_FEE', 'ITEM4_CENSOR_144', 'ITEM4_REORG_REPLACE')
ITEM4_MINER = {'ITEM4_SELF_DEALING': 'ITEM4_SELF_FIRST_ZERO_FEE', 'ITEM4_CENSORSHIP': 'ITEM4_CENSOR_144',
               'ITEM4_REORG': 'ITEM4_REORG_REPLACE', 'ITEM4_FEE_ASYMMETRY': 'ITEM2_DEFAULT'}
ITEM4_EXPERIMENTS = tuple(ITEM4_MINER)
BUILT_POLICIES += ITEM4_POLICIES
RESERVED_POLICIES: tuple[str, ...] = ()   # D3a-2a built the last reserved names


def pending(value) -> bool:
    """Whether a PENDING marker is left anywhere: a JSON string value that starts with "PENDING"."""
    if isinstance(value, str):
        return value.startswith('PENDING')
    if isinstance(value, dict):
        return any(pending(item) for item in value.values())
    if isinstance(value, list):
        return any(pending(item) for item in value)
    return False


def read_input(path: Path, limit: int) -> bytes:
    resolved = path.absolute()
    try:
        return bounded_regular_bytes(resolved, root=resolved.parent, limit=limit)
    except (OSError, ValueError):
        raise Refusal('INPUT_UNAVAILABLE', EXIT_PREREQUISITE) from None


def parse_json(blob: bytes, code: str) -> dict:
    try:
        value = strict_json_bytes(blob)
    except (ValueError, UnicodeDecodeError, RecursionError):
        raise invalid(code) from None
    if not isinstance(value, dict):
        raise invalid(code)
    return value


def check_policy_shape(policy: dict) -> None:
    """The closed shape (format doc section 3). A PENDING string may stand for any value."""
    keys = set(policy)
    if not POLICY_KEYS <= keys <= POLICY_KEYS | POLICY_OPTIONAL or policy['schema'] != POLICY_SCHEMA:
        raise invalid('POLICY_SHAPE')
    seed = policy['seed']
    if not (pending(seed) or isinstance(seed, str) and HEX64.match(seed)):
        raise invalid('POLICY_SEED')
    for name, block in (('counts', policy['counts']), ('experiments', policy['experiments'])):
        if not isinstance(block, dict) or not set(block) <= set(EXPERIMENTS):
            raise invalid(f'POLICY_{name.upper()}')
    for count in policy['counts'].values():
        if not (pending(count) or type(count) is int and 1 <= count < U32):
            raise invalid('POLICY_COUNTS')
    for name, entry in policy['experiments'].items():
        if not (isinstance(entry, dict) and {'miner_policy'} <= set(entry) <= {'miner_policy', 'params',
                                                                                'method_policy', 'l0_seat'}
                and isinstance(entry['miner_policy'], str)):
            raise invalid('POLICY_EXPERIMENTS')
        if 'l0_seat' in entry:
            check_l0_seat_shape(name, entry['l0_seat'])
        if 'params' in entry:
            check_params(name, entry['params'])
        if 'method_policy' in entry:   # U3 (A Q3): ITEM1's method policy file, named and hashed in the policy
            method = entry['method_policy']
            if not (name == 'ITEM1' and isinstance(method, dict) and set(method) == {'path', 'sha256'}
                    and isinstance(method['path'], str) and isinstance(method['sha256'], str)
                    and (pending(method['sha256']) or HEX64.match(method['sha256']))):
                raise invalid('POLICY_METHOD_POLICY')
        if not pending(entry['miner_policy']) and (
                CAMPAIGN_MINER.get(name, entry['miner_policy']) != entry['miner_policy']
                or name not in CAMPAIGN_MINER and entry['miner_policy'] in CAMPAIGN_MINER.values()):
            raise invalid('POLICY_MINER_EXPERIMENT')
        if not pending(entry['miner_policy']) and (
                ITEM4_MINER.get(name, entry['miner_policy']) != entry['miner_policy']
                or name not in ITEM4_MINER and entry['miner_policy'] in ITEM4_POLICIES):
            raise invalid('POLICY_MINER_EXPERIMENT')   # D3a-2a: the item-4 pin table
    if not (pending(policy['bidders']) or isinstance(policy['bidders'], list)):
        raise invalid('POLICY_BIDDERS')
    if 'thresholds' in policy and not isinstance(policy['thresholds'], dict):
        raise invalid('POLICY_THRESHOLDS')


# D2-3a (A Q6): experiments.<E>.params for the campaigns that D2-3a builds. A PENDING string may stand for any
# value (CONFIRMATORY then refuses it, exit 3). H0 must leave room for the setup blocks and the two funding
# blocks before the first gate; ITEM1 has at most 200 gates (045b 4.6), a pool run at most 200.
CAMPAIGN_EXPERIMENTS = ('ITEM1', 'POOL')
PARAM_KEYS = ('b', 'H0', 'gates_per_run')
MIN_H0 = 106   # SETUP_BLOCKS (103), then the fan-out and owner funding blocks (104, 105)
ITEM2_MIN_H0 = MIN_H0 + 1   # item 2 then prepares G − 1 on its own (Codex r4433308775): H0 ≥ 107
MAX_GATES_PER_RUN = 200
ITEM1_GATES = 200   # 045b 4.6: 200 contested gates in one run, numbered 0-199
# B-FZ-p round 2, Q-pol-4 (A #258 issuecomment-6744913177): early copies of values the judge or 045b binds, so a
# wrong frozen value is refused before any node, not by the judge afterwards. Literal copies: no driver module
# imports the judge (test_ardr_judge `test_no_driver_module_imports_the_judge`).
# (a) The method policy's thresholds are 045b :434's [4, 15] (judge ITEM1_REPORT_THRESHOLDS, METHOD_THRESHOLDS),
#     in every mode, as the judge (the B-FZ-pol note's section 5 patch): METHOD_THRESHOLDS in `_run_campaign`.
ITEM1_REPORT_THRESHOLDS = [4, 15]
# (b) A CONFIRMATORY pool run is one of 50 runs of 4 gates (045b :545; judge POOL_RUNS_GATES, its
#     POLICY_POOL_RUNS / POLICY_POOL_GATES in CONFIRMATORY only): POLICY_POOL_RUNS_GATES in `load_policy`.
POOL_RUNS_GATES = (50, 4)
# (c) 045b F11 (on #664): `b` is a multiple of 250 sat/kvB, so that no ladder is empty at v = 213 vB (section 9 of
#     the format: "the alternative for the freeze"). CONFIRMATORY only (EXPLORATORY keeps off-grid values such as
#     the item-4 self-fee boundary b 1,126 / 1,127): POLICY_B_NOT_MULTIPLE_OF_250 in `load_policy`.
B_MULTIPLE = 250
# DRAFT (PENDING_FREEZE) params for EXPLORATORY and PR_SMOKE runs of a policy without them.
# D2-3b (A Q4): ITEM2 takes params too (b, H0; gates_per_run is 1). Its run is the item-2 run of
# `claude_track_ardr_item2` only when the policy has them; without them it stays D1's smoke.
PARAMS_EXPERIMENTS = CAMPAIGN_EXPERIMENTS + ('ITEM2',)
DRAFT_PARAMS = {'ITEM1': {'b': 3000, 'H0': 110, 'gates_per_run': 200},
                'POOL': {'b': 3000, 'H0': 110, 'gates_per_run': 4}}
# D3a-2a: the item-4 experiments take params of the same shape as ITEM2 (one gate per run, H0 ≥ 107; DRAFT
# H0 1000 as item 2's, A 6551547851 Q2 and B's default Q7). With params, `run` sends them to the item-4 run.
ITEM4_DRAFT_PARAMS = {'b': 3000, 'H0': 1000, 'gates_per_run': 1}
# D3a-2a (A 6554792879 Q1, Q8; FD-CT-133): rung 0 at L0's p_0; self REGISTER 600 sat, the product floor; 213 vB each.
ITEM4_SELF_FEE = 600
ITEM4_VSIZE = 213


def item4_project_p0(b: int) -> int:   # FD-CT-133: the one source, the bidders' (a lazy import: they import this module)
    bidders = __import__('claude_track_ardr_bidders')
    try: return bidders.l0_p0(b, ITEM4_VSIZE)
    except bidders.Refusal as refusal: raise Refusal(refusal.code, refusal.exit_code) from None   # as a script (#823)


def item4_project_fee(b: int) -> int:
    return -(-item4_project_p0(b) * ITEM4_VSIZE // 1000)


# D3a-2b-2b (A #258 issuecomment-6565897037 Q1): the L0 seat's frozen values live in the policy, which the
# registration binds and A's judge reads: `experiments.<E>.l0_seat` for ITEM2 and each item-4 experiment. A
# CONFIRMATORY L0 run needs it (L0_FREEZE_PENDING without it) and must do what it says (ARDR_RUN_V1 section 26).
# A PENDING string may stand for any value. `seat` (ITEM2 only): the PUBLIC seat L0 takes.
L0_SEAT_KEYS = ('p0_rule', 'max_gate_attempts', 'exact_height_miss', 'budget_sha256')
L0_P0_RULE = 'MAX_P0_TWO_RUNGS'   # FD-CT-133 (#807): item 2's `l0_p0`, the bidders' `l0_p0` (was CEIL_2_5_B)
L0_EXACT_HEIGHT_MISS = ('STOP_CAMPAIGN', 'CONTINUE_WITHIN_LIMITS')
# B-FZ-p round 2 (A #258 issuecomment-6744913177): the STOP_CAMPAIGN record (9ea208bd..) is EXPLORATORY only, not
# approved; a CONFIRMATORY run takes A's frozen record only (CONTINUE_WITHIN_LIMITS, 7d0a7a35..). `_run_l0`
# refuses any other `exact_height_miss` before any node (L0_STOP_CAMPAIGN_EXPLORATORY_ONLY, exit 6), and since fix
# round 1 (pre-PR review) `load_policy` does too, so CONFIRMATORY `check-policy` refuses a policy no CONFIRMATORY
# run accepts; the L0 CLI's EXPLORATORY `--policy-l0-seat` still takes either.
L0_CONFIRMATORY_EXACT_HEIGHT_MISS = 'CONTINUE_WITHIN_LIMITS'


def refuse_stop_twin(exact_height_miss: str) -> None:
    """The CONFIRMATORY STOP_CAMPAIGN refusal (B-FZ-p round 2): any `exact_height_miss` other than
    L0_CONFIRMATORY_EXACT_HEIGHT_MISS is L0_STOP_CAMPAIGN_EXPLORATORY_ONLY (exit 6), before any node. One check for
    its three callers: `load_policy` and `_run_l0` in CONFIRMATORY, and (FZ-6 n1, A #759 issuecomment-6749449323)
    the L0 module's Python API runs given a CONFIRMATORY plan (`refuse_confirmatory_outside_driver`)."""
    if exact_height_miss != L0_CONFIRMATORY_EXACT_HEIGHT_MISS:
        raise Refusal('L0_STOP_CAMPAIGN_EXPLORATORY_ONLY', EXIT_REFUSAL)


def check_l0_seat_shape(experiment: str, value) -> None:
    keys = set(L0_SEAT_KEYS) | ({'seat'} if experiment == 'ITEM2' else set())
    if experiment not in ('ITEM2',) + ITEM4_EXPERIMENTS or not (isinstance(value, dict) and set(value) == keys):
        raise invalid('POLICY_L0_SEAT')
    checks = {'p0_rule': lambda v: isinstance(v, str), 'max_gate_attempts': lambda v: type(v) is int and v >= 1,
              'exact_height_miss': lambda v: v in L0_EXACT_HEIGHT_MISS,
              'budget_sha256': lambda v: isinstance(v, str) and HEX64.match(v) is not None,
              'seat': lambda v: type(v) is int and 0 <= v <= 4}
    # B-FZ-a FZ-3 (Desktop r4439901418): a PENDING value stands for the field itself, a string; a container
    # holding one ({"n": "PENDING_FREEZE"}, ["PENDING_FREEZE"]) is no field value (`pending` alone looks inside).
    if not all(isinstance(value[k], str) and pending(value[k]) or checks[k](value[k]) for k in keys):
        raise invalid('POLICY_L0_SEAT')
    # #667 A integration check (F2, MAY): seat 0 is the even runs' private seat (`plan_run` refuses it there), so
    # a frozen seat 0 would refuse half the runs at plan time; refused here, in every mode, before any node.
    if experiment == 'ITEM2' and value['seat'] == 0:
        raise invalid('POLICY_L0_SEAT_PRIVATE')


def check_params(experiment: str, params) -> None:
    if experiment in ITEM4_EXPERIMENTS:
        return check_item4_params(params, experiment)
    if experiment not in PARAMS_EXPERIMENTS:
        raise invalid('POLICY_PARAMS_EXPERIMENT')
    if not (isinstance(params, dict) and set(params) == set(PARAM_KEYS)):
        raise invalid('POLICY_PARAMS')
    bounds = {'b': (1, U32), 'H0': (MIN_H0, U32), 'gates_per_run': (1, MAX_GATES_PER_RUN)}
    for key, (low, high) in bounds.items():
        value = params[key]
        # B-FZ-a fix round 1 (the FZ-3 rule, as `check_l0_seat_shape`): only the field's own PENDING string
        # stands for a value; a container holding one is no field value.
        if not (isinstance(value, str) and pending(value) or type(value) is int and low <= value <= high):
            raise invalid('POLICY_PARAMS')
    if experiment == 'ITEM2' and not pending(params['gates_per_run']) and params['gates_per_run'] != 1:
        raise invalid('POLICY_ITEM2_GATES')   # D2-3b (A Q4): one item-2 run is one contested gate
    if experiment == 'ITEM2' and not pending(params['H0']) and params['H0'] < ITEM2_MIN_H0:
        raise invalid('H0_TOO_LOW')   # Codex r4433308775, A 6549379243: check-policy refuses it too


def check_item4_params(params, experiment: str | None = None) -> None:
    """D3a-2a: `b`, `H0` (≥ ITEM2_MIN_H0) and `gates_per_run` (exactly 1); PENDING may stand for any value.
    ITEM4_SELF_DEALING (A 6554792879 Q8): the static check that the project's rung 0 (L0's p_0, FD-CT-133, at 213 vB)
    pays strictly more than the self REGISTER's product floor, so a feerate order would not put the self
    REGISTER first (ITEM4_SELF_FEE_NOT_BELOW; check-policy and every run, before any node)."""
    if not (isinstance(params, dict) and set(params) == set(PARAM_KEYS)):
        raise invalid('POLICY_PARAMS')
    bounds = {'b': (1, U32), 'H0': (ITEM2_MIN_H0, U32), 'gates_per_run': (1, 1)}
    for key, (low, high) in bounds.items():
        value = params[key]
        # B-FZ-a fix round 1: the FZ-3 rule, as in `check_params`.
        if not (isinstance(value, str) and pending(value) or type(value) is int and low <= value <= high):
            raise invalid('POLICY_ITEM4_PARAMS')
    if experiment == 'ITEM4_SELF_DEALING' and not pending(params['b']) \
            and not item4_project_fee(params['b']) > ITEM4_SELF_FEE:
        raise invalid('ITEM4_SELF_FEE_NOT_BELOW')


def miner_policy(name: str):
    """The ordering function a policy name selects. A reserved name is refused until D2/D3a build it."""
    if name in BUILT_POLICIES:
        return order_ancestor_feerate
    if name in RESERVED_POLICIES:
        raise Refusal('MINER_POLICY_NOT_BUILT', EXIT_PREREQUISITE)
    raise invalid('MINER_POLICY_UNKNOWN')


def load_policy(mode: str, policy_path: Path, experiment: str, registration_path: Path | None = None,
                registration_sha256: str | None = None, complete: bool = False) -> dict:
    """Read the policy (and in CONFIRMATORY the registration) once as bytes and check them in this order:
    registration hash, policy hash bound by the registration (exit 6), the experiment among the registration's
    `experiments` when it has that key (EXPERIMENT_NOT_REGISTERED, exit 6; FD-CT-133), PENDING (exit 3), shape
    (exit 2), the experiment's miner policy. Returns what every log line carries. `complete` (B-FZ-a fix round 1, the L0
    CLI's `--policy-l0-seat`) applies CONFIRMATORY's completeness checks in any mode, through this same code:
    no PENDING anywhere in the policy (POLICY_PENDING) and every experiment counted (POLICY_COUNT_UNSET).
    Q-pol-4 (B-FZ-p round 2): in CONFIRMATORY a POOL run's count and gates are 045b's 50 and 4
    (POLICY_POOL_RUNS_GATES) and the run's `b` is a multiple of 250 (045b F11 on #664,
    POLICY_B_NOT_MULTIPLE_OF_250), so check-policy and every run refuse them before any node. B-FZ-p fix round 1:
    in CONFIRMATORY an `l0_seat` whose `exact_height_miss` is not CONTINUE_WITHIN_LIMITS (the STOP_CAMPAIGN twin,
    EXPLORATORY only) is L0_STOP_CAMPAIGN_EXPLORATORY_ONLY (exit 6), as in `_run_l0`. FZ-6 F1: before that, in
    CONFIRMATORY, an `l0_seat` goes through `confirmatory_l0_seat` as in `_run_l0` (its p_0 rule, attempt count
    and product budget digest; exit 6), so CONFIRMATORY check-policy refuses those values before any node too."""
    if mode not in MODES:
        raise invalid('MODE')
    if experiment not in EXPERIMENTS:
        raise invalid('EXPERIMENT')
    blob = read_input(policy_path, POLICY_LIMIT)
    policy_sha256 = hashlib.sha256(blob).hexdigest()
    registered = None
    if mode == 'CONFIRMATORY':
        if registration_path is None or registration_sha256 is None:
            raise Refusal('REGISTRATION_MISSING', EXIT_PREREQUISITE)
        if not HEX64.match(registration_sha256):
            raise invalid('REGISTRATION_SHA256_ARGUMENT')
        registration = read_input(registration_path, POLICY_LIMIT)
        registered = hashlib.sha256(registration).hexdigest()
        if registered != registration_sha256:
            raise Refusal('REGISTRATION_BYTES_CHANGED', EXIT_REFUSAL)
        document = parse_json(registration, 'REGISTRATION_JSON')
        bound = document.get(REGISTRATION_KEY)
        if not (isinstance(bound, list) and bound and all(isinstance(h, str) and HEX64.match(h) for h in bound)):
            raise invalid('REGISTRATION_SHAPE')
        if policy_sha256 not in bound:
            raise Refusal('POLICY_NOT_REGISTERED', EXIT_REFUSAL)
        if REGISTRATION_EXPERIMENTS_KEY in document:
            # FD-CT-133: the first P5-005 registration lists ITEM1 and POOL; its policy still holds ITEM2, whose
            # CONFIRMATORY runs belong to a follow-up registration. Refused before the policy is parsed, so before
            # any node (a slice's unit stays BEFORE_START). A registration without the key reads as before.
            covered = document[REGISTRATION_EXPERIMENTS_KEY]
            if not (isinstance(covered, list) and covered and all(isinstance(e, str) for e in covered)):
                raise invalid('REGISTRATION_SHAPE')
            if experiment not in covered:
                raise Refusal('EXPERIMENT_NOT_REGISTERED', EXIT_REFUSAL)
    elif registration_path is not None or registration_sha256 is not None:
        raise invalid('REGISTRATION_OUTSIDE_CONFIRMATORY')
    policy = parse_json(blob, 'POLICY_JSON')
    if (mode == 'CONFIRMATORY' or complete) and pending(policy):
        raise Refusal('POLICY_PENDING', EXIT_PREREQUISITE)
    check_policy_shape(policy)
    entry = policy['experiments'].get(experiment)
    if entry is None:
        raise invalid('POLICY_EXPERIMENT_ABSENT')
    if (mode == 'CONFIRMATORY' or complete) and not set(policy['experiments']) <= set(policy['counts']):
        raise Refusal('POLICY_COUNT_UNSET', EXIT_PREREQUISITE)   # 045b 4.6: any count unset is refused
    if mode == 'CONFIRMATORY' and experiment in CAMPAIGN_EXPERIMENTS and 'params' not in entry:
        raise Refusal('POLICY_PARAMS_UNSET', EXIT_PREREQUISITE)
    if mode == 'CONFIRMATORY' and experiment == 'ITEM1' and entry['params']['gates_per_run'] != ITEM1_GATES:
        raise invalid('POLICY_ITEM1_GATES')   # P3-5: a CONFIRMATORY item-1 run is gates 0-199 (045b 4.6)
    if mode == 'CONFIRMATORY' and experiment == 'POOL' \
            and (policy['counts']['POOL'], entry['params']['gates_per_run']) != POOL_RUNS_GATES:
        raise invalid('POLICY_POOL_RUNS_GATES')   # Q-pol-4 (b): 045b :545, as the judge, before any node
    if mode == 'CONFIRMATORY' and 'params' in entry and entry['params']['b'] % B_MULTIPLE:
        raise invalid('POLICY_B_NOT_MULTIPLE_OF_250')   # Q-pol-4 (c): 045b F11 (on #664), before any node
    if mode == 'CONFIRMATORY' and 'l0_seat' in entry:
        # FZ-6 F1 (A #759 issuecomment-6749449323): the run's own L0 value checks, `confirmatory_l0_seat`
        # (L0_POLICY_P0_RULE, L0_POLICY_ATTEMPTS, L0_POLICY_BUDGET_NOT_PRODUCT, exit 6), so CONFIRMATORY check-policy
        # refuses what `_run_l0` refuses, before any node. A lazy import for this check only; the one CONFIRMATORY
        # L0 entry stays `_run_l0`. Run as a script this module is `__main__` and the L0 module raises
        # `claude_track_ardr_driver.Refusal`, so its refusal becomes this module's (as in `run_l0`).
        import claude_track_ardr_l0 as l0
        try:
            l0.confirmatory_l0_seat(experiment, entry['l0_seat'])
        except l0.Refusal as refusal:
            raise Refusal(refusal.code, refusal.exit_code) from None
        # B-FZ-p fix round 1 (pre-PR review): the STOP_CAMPAIGN twin is refused here too, so CONFIRMATORY
        # check-policy refuses a policy no CONFIRMATORY run accepts; `_run_l0` keeps its own check.
        refuse_stop_twin(entry['l0_seat']['exact_height_miss'])
    miner_policy(entry['miner_policy'])
    if pending(policy['seed']):
        seed = None
    else:
        seed = bytes.fromhex(policy['seed'])
    return {
        'mode': mode,
        'evidence_status': 'CONFIRMATORY' if mode == 'CONFIRMATORY' else 'EXPLORATORY',
        'policy_sha256': policy_sha256,
        'registration_sha256': registered,
        'experiment': experiment,
        'miner_policy': entry['miner_policy'],
        'seed': seed,
        'params': entry.get('params'),
        'method_policy': entry.get('method_policy'),
        'l0_seat': entry.get('l0_seat'),
        'registered_hashes': list(bound) if mode == 'CONFIRMATORY' else None,
    }


# ---------------------------------------------------------------------------------------------------------
# Bitcoin serialization (Regtest blocks; stdlib only).

OP_TRUE_SCRIPT = b'\x51'
PAYOUT_SCRIPT = b'\x00\x20' + hashlib.sha256(OP_TRUE_SCRIPT).digest()   # P2WSH(OP_TRUE): no key exists
COINBASE_RESERVE_WEIGHT = 4000   # header, counts and coinbase (Core's default -blockmaxweight reserve)
MAX_TEMPLATE_TXS = 20000


def dsha(data: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def varint(n: int) -> bytes:
    if n < 0xfd:
        return bytes([n])
    if n <= 0xffff:
        return b'\xfd' + n.to_bytes(2, 'little')
    if n <= 0xffffffff:
        return b'\xfe' + n.to_bytes(4, 'little')
    return b'\xff' + n.to_bytes(8, 'little')


class Reader:
    def __init__(self, data: bytes):
        self.data, self.at = data, 0

    def take(self, n: int) -> bytes:
        if n < 0 or self.at + n > len(self.data):
            raise invalid('TX_TRUNCATED')
        chunk = self.data[self.at:self.at + n]
        self.at += n
        return chunk

    def int(self, n: int) -> int:
        return int.from_bytes(self.take(n), 'little')

    def varint(self) -> int:
        first = self.int(1)
        return first if first < 0xfd else self.int({0xfd: 2, 0xfe: 4, 0xff: 8}[first])


class Tx:
    """One parsed transaction: its ids (display hex), inputs, outputs, weight and exact bytes."""

    def __init__(self, raw: bytes):
        reader = Reader(raw)
        version = reader.take(4)
        segwit = raw[4:6] == b'\x00\x01'
        if segwit:
            reader.take(2)
        start_body = reader.at
        inputs = []
        for _ in range(reader.varint()):
            prev = reader.take(32)[::-1].hex()
            vout = reader.int(4)
            reader.take(reader.varint())
            reader.take(4)
            inputs.append((prev, vout))
        outputs = []
        for _ in range(reader.varint()):
            value = reader.int(8)
            outputs.append((value, reader.take(reader.varint())))
        end_body = reader.at
        if segwit:
            for _ in inputs:
                for _ in range(reader.varint()):
                    reader.take(reader.varint())
        locktime = reader.take(4)
        if reader.at != len(raw) or not inputs or not outputs:
            raise invalid('TX_MALFORMED')
        stripped = version + raw[start_body:end_body] + locktime
        self.raw, self.inputs, self.outputs = raw, inputs, outputs
        self.has_witness = segwit
        self.txid = dsha(stripped)[::-1].hex()
        self.wtxid = dsha(raw)[::-1].hex()
        self.weight = len(stripped) * 3 + len(raw)
        self.vsize = (self.weight + 3) // 4


def op_true_spend(prevouts: list[tuple[str, int]], values: list[int]) -> bytes:
    """A TEST_ONLY transaction spending P2WSH(OP_TRUE) outputs into P2WSH(OP_TRUE) outputs (version 2,
    BIP125 signalled). Its witness is the script itself: no signature, no key."""
    body = varint(len(prevouts)) + b''.join(
        bytes.fromhex(txid)[::-1] + vout.to_bytes(4, 'little') + b'\x00' + b'\xfd\xff\xff\xff'
        for txid, vout in prevouts)
    body += varint(len(values)) + b''.join(v.to_bytes(8, 'little') + varint(len(PAYOUT_SCRIPT)) + PAYOUT_SCRIPT
                                           for v in values)
    witness = b''.join(b'\x01\x01' + OP_TRUE_SCRIPT for _ in prevouts)
    return (2).to_bytes(4, 'little') + b'\x00\x01' + body + witness + bytes(4)


def script_number(n: int) -> bytes:
    """`CScript() << n` for a block height (BIP34): OP_0, OP_1..OP_16, or a minimal number push."""
    if n == 0:
        return b'\x00'
    if 1 <= n <= 16:
        return bytes([0x50 + n])
    data = bytearray()
    while n:
        data.append(n & 0xff)
        n >>= 8
    if data[-1] & 0x80:
        data.append(0)
    return bytes([len(data)]) + bytes(data)


def merkle_root(hashes: list[bytes]) -> bytes:
    level = list(hashes)
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        level = [dsha(level[i] + level[i + 1]) for i in range(0, len(level), 2)]
    return level[0]


PRODUCER_TAG = b'BITAGI_ARDR_PRODUCER_'   # D2-3a pool run: this, then one producer letter (A, B or C)
PRODUCERS = ('A', 'B', 'C')


def coinbase(height: int, value: int, witness_root: bytes | None, extranonce: int,
             producer: str | None = None) -> bytes:
    """The coinbase: BIP34 height then an 8-byte extranonce push (then, in a pool run, one push of
    PRODUCER_TAG and the producer letter); one P2WSH(OP_TRUE) payout; and when a transaction has a witness the
    BIP141 commitment output and the 32-byte zero reserved value."""
    script_sig = script_number(height) + b'\x08' + extranonce.to_bytes(8, 'little')
    if producer is not None:
        if producer not in PRODUCERS:
            raise invalid('PRODUCER')
        tag = PRODUCER_TAG + producer.encode('ascii')
        script_sig += bytes([len(tag)]) + tag
    outputs = [value.to_bytes(8, 'little') + varint(len(PAYOUT_SCRIPT)) + PAYOUT_SCRIPT]
    if witness_root is not None:
        commitment = b'\x6a\x24\xaa\x21\xa9\xed' + dsha(witness_root + bytes(32))
        outputs.append(bytes(8) + varint(len(commitment)) + commitment)
    vin = varint(1) + bytes(32) + b'\xff\xff\xff\xff' + varint(len(script_sig)) + script_sig + b'\xff\xff\xff\xff'
    vout = varint(len(outputs)) + b''.join(outputs)
    if witness_root is None:
        return (2).to_bytes(4, 'little') + vin + vout + bytes(4)
    return (2).to_bytes(4, 'little') + b'\x00\x01' + vin + vout + b'\x01\x20' + bytes(32) + bytes(4)


def bits_target(bits: int) -> int:
    exponent, mantissa = bits >> 24, bits & 0x7fffff
    return mantissa << (8 * (exponent - 3)) if exponent > 3 else mantissa >> (8 * (3 - exponent))


def solve_header(version: int, prev: str, root: bytes, time_: int, bits_hex: str) -> bytes:
    """The 80-byte header with the first nonce whose hash meets the target (Regtest: a few tries)."""
    bits = int(bits_hex, 16)
    target = bits_target(bits)
    head = (version.to_bytes(4, 'little', signed=True) + bytes.fromhex(prev)[::-1] + root
            + time_.to_bytes(4, 'little') + bits.to_bytes(4, 'little'))
    for nonce in range(U32):
        header = head + nonce.to_bytes(4, 'little')
        if int.from_bytes(dsha(header), 'little') <= target:
            return header
    raise Refusal('POW_NOT_FOUND', EXIT_INTERNAL)


# ---------------------------------------------------------------------------------------------------------
# Miner policy ITEM2_DEFAULT (045b 4.3 item 2; A Q3): ancestor feerate descending, ties by txid, parents
# before children, cut at the weight cap.

class Entry:
    """One candidate: a template transaction or a private one."""

    def __init__(self, tx: Tx, fee: int, source: str, parents: frozenset):
        self.tx, self.fee, self.source, self.parents = tx, fee, source, parents
        self.txid, self.weight, self.vsize = tx.txid, tx.weight, tx.vsize
        self.spends = frozenset(tx.inputs)


def order_ancestor_feerate(entries: list[Entry], budget: int) -> dict:
    """Select and order `entries` within `budget` weight units.

    Repeat until nothing remains: for every remaining candidate take its package (itself and its remaining
    ancestors); pick the package with the highest feerate (sum of fees over sum of vsizes, compared exactly
    by cross-multiplication), a tie going to the smaller txid (display hex, ascending). A package that spends
    an outpoint a selected transaction already spends, or that another member of it spends, is not selected:
    its conflicting members and their descendants are dropped. A candidate whose parent is not a candidate
    is refused (`MINER_PARENT_MISSING`). A package whose weight would take the block past `budget` ends the selection:
    it and everything still remaining are cut. Otherwise the package is appended parents first, ready members
    by ascending txid."""
    remaining = {entry.txid: entry for entry in entries}
    if len(remaining) != len(entries):
        raise invalid('MINER_DUPLICATE_TXID')
    if any(entry.parents - set(remaining) for entry in entries):
        raise invalid('MINER_PARENT_MISSING')   # a parent in the block must be a candidate
    selected: list[Entry] = []
    spent: set = set()
    dropped: list[str] = []
    used = 0

    def package(txid: str) -> set[str]:
        members, todo = set(), [txid]
        while todo:
            current = todo.pop()
            if current not in members:
                members.add(current)
                todo.extend(p for p in remaining[current].parents if p in remaining)
        return members

    def descendants(roots: set[str]) -> set[str]:
        out = set(roots)
        grew = True
        while grew:
            grew = False
            for txid, entry in remaining.items():
                if txid not in out and entry.parents & out:
                    out.add(txid)
                    grew = True
        return out

    while remaining:
        best = None
        for txid in sorted(remaining):
            members = package(txid)
            fee = sum(remaining[m].fee for m in members)
            vsize = sum(remaining[m].vsize for m in members)
            if best is None or fee * best[2] > best[1] * vsize:
                best = (txid, fee, vsize, members)
        txid, _, _, members = best
        conflicting = {m for m in members if remaining[m].spends & spent
                       or any(remaining[m].spends & remaining[o].spends for o in members if o != m)}
        if conflicting:
            gone = descendants(conflicting)
            dropped.extend(sorted(gone))
            for m in gone:
                del remaining[m]
            continue
        weight = sum(remaining[m].weight for m in members)
        if used + weight > budget:
            break
        placed: list[str] = []
        while len(placed) < len(members):
            ready = sorted(m for m in members if m not in placed
                           and not (remaining[m].parents & members) - set(placed))
            placed.append(ready[0])
        for m in placed:
            selected.append(remaining.pop(m))
            spent |= selected[-1].spends
        used += weight
    return {'selected': selected, 'cut': sorted(remaining), 'dropped': dropped, 'weight': used}


# ---------------------------------------------------------------------------------------------------------
# The miner (runs in its own process; `rpc` is that process's narrowed client or a test stand-in).

MINER_RPCS = frozenset({'getblocktemplate', 'submitblock', 'gettxout'})


class AllowlistRPC:
    """Refuses any method outside `allowed` before the inner client sees it."""

    def __init__(self, inner, allowed: frozenset):
        self.inner, self.allowed = inner, allowed

    def call(self, method: str, *params):
        if method not in self.allowed:
            raise oe.Mismatch(f'RPC_NOT_ALLOWED {method}')
        return self.inner.call(method, *params)


class Miner:
    """Holds the private set in memory and builds every block from the template under one policy."""

    def __init__(self, rpc, policy_name: str, budget: int | None = None, producer: str | None = None):
        self.rpc = AllowlistRPC(rpc, MINER_RPCS)
        self.policy_name = policy_name
        self.order = miner_policy(policy_name)
        self.budget = budget
        if (producer is not None) != (policy_name == 'POOL_50_30_20'):
            raise invalid('PRODUCER')   # a pool miner process tags every block; no other one does
        self.producer = producer
        self.private: dict[str, Tx] = {}
        self.extranonce = 0
        self.prepared: dict | None = None   # D2-3b: a block built by `build_block(submit=False)`, not yet sent

    def add_private(self, raw_hex: str) -> str:
        tx = Tx(bytes.fromhex(raw_hex))
        self.private[tx.txid] = tx
        return tx.txid

    def replace_private(self, raw_hex: str) -> dict:
        """D2-3b: a replacement rung of the private bidder. The new transaction must spend an input of exactly
        one held private transaction (PRIVATE_REPLACE_CONFLICT, exit 2, otherwise; nothing changes); that one
        leaves the private set and the new one is held. Returns the new txid and the replaced one."""
        tx = Tx(bytes.fromhex(raw_hex))
        spent = set(tx.inputs)
        conflicts = sorted(txid for txid, held in self.private.items() if spent & set(held.inputs))
        if len(conflicts) != 1 or tx.txid in self.private:
            raise invalid('PRIVATE_REPLACE_CONFLICT')
        del self.private[conflicts[0]]
        self.private[tx.txid] = tx
        return {'txid': tx.txid, 'replaced': conflicts[0]}

    def private_fee(self, tx: Tx, known: dict[str, Tx]) -> int | None:
        total = 0
        for prev, vout in tx.inputs:
            if prev in known:
                outputs = known[prev].outputs
                if vout >= len(outputs):
                    return None
                total += outputs[vout][0]
                continue
            out = self.rpc.call('gettxout', prev, vout, False)
            if not isinstance(out, dict) or 'value' not in out:
                return None
            total += oe.sats(out['value'])
        fee = total - sum(value for value, _ in tx.outputs)
        return fee if fee >= 0 else None

    def build_block(self, gate: dict | None = None, submit: bool = True, item4: dict | None = None) -> dict:
        """One block from the template and the held private set. `gate` (ITEM1_WINNER_ONLY only, at block
        G): `{"height", "winner", "registers"}`; the gate's other REGISTERs are dropped and the winner must be
        in the block (`gate_filter`). D2-3b: `submit` False builds the block and keeps it (`prepared`)
        without sending it; `submit_prepared` sends it. Item 2 needs block G − 1's hash before its rungs
        exist (the REGISTER is built on G − 1). D3a-2a: `item4` is the item-4 policies' per-block context
        (`item4_filter`); a block without one is ordered by ancestor feerate only."""
        if gate is not None and self.policy_name != 'ITEM1_WINNER_ONLY':
            raise invalid('GATE_CONTEXT_POLICY')
        if item4 is not None and self.policy_name not in ITEM4_POLICIES:
            raise invalid('ITEM4_CONTEXT_POLICY')
        if self.prepared is not None:
            raise invalid('MINER_BLOCK_PREPARED')   # the prepared block is sent first
        t_template = CLOCK()
        template = self.rpc.call('getblocktemplate', {'rules': ['segwit']})
        t_answer = CLOCK()   # D3a-2a: when the answer arrived (item 4's template-cache wait counts from here)
        listed = template['transactions']
        if len(listed) > MAX_TEMPLATE_TXS:
            raise invalid('TEMPLATE_TOO_LARGE')
        template_txs = []
        for item in listed:
            tx = Tx(bytes.fromhex(item['data']))
            if (tx.txid, tx.wtxid) != (item['txid'], item['hash']):
                raise invalid('TEMPLATE_TXID')
            template_txs.append((tx, int(item['fee']), [listed[i - 1]['txid'] for i in item['depends']]))
        known = {tx.txid: tx for tx, _, _ in template_txs}
        if set(self.private) & set(known):
            raise invalid('PRIVATE_IN_TEMPLATE')   # a held private transaction reached a node
        private_snapshot = sorted(self.private)
        private_set = [{'txid': txid, 'hex': self.private[txid].raw.hex()} for txid in private_snapshot]
        entries = [Entry(tx, fee, 'TEMPLATE', frozenset(parents)) for tx, fee, parents in template_txs]
        excluded = set()
        union = dict(known)
        union.update(self.private)
        private_entries = {}
        for txid in private_snapshot:
            tx = self.private[txid]
            fee = self.private_fee(tx, union)
            if fee is None:
                excluded.add(txid)
                continue
            private_entries[txid] = Entry(tx, fee, 'PRIVATE', frozenset(p for p, _ in tx.inputs if p in union))
        grew = True
        while grew:   # a private transaction whose private parent is left out is left out too
            grew = False
            for txid, entry in list(private_entries.items()):
                if entry.parents & excluded:
                    excluded.add(txid)
                    del private_entries[txid]
                    grew = True
        entries.extend(private_entries[txid] for txid in sorted(private_entries))
        gate_dropped: list[str] = []
        if gate is not None:
            entries, gate_dropped = gate_filter(entries, gate, int(template['height']))
        budget = int(template['weightlimit']) - COINBASE_RESERVE_WEIGHT if self.budget is None else self.budget
        first: list[Entry] = []
        item4_record = None
        if item4 is not None:
            entries, first, item4_record = item4_filter(entries, item4, int(template['height']), self.policy_name)
            budget -= sum(e.weight for e in first)
        chosen = self.order(entries, budget)
        selected = first + chosen['selected']   # D3a-2a: the self REGISTER (if any) at index 0
        if gate is not None and gate['winner'] not in {e.txid for e in selected}:
            raise invalid('ITEM1_WINNER_MISSING')
        subsidy = int(template['coinbasevalue']) - sum(fee for _, fee, _ in template_txs)
        value = subsidy + sum(entry.fee for entry in selected)
        witness = any(entry.tx.has_witness for entry in selected)
        witness_root = merkle_root([bytes(32)] + [bytes.fromhex(e.tx.wtxid)[::-1] for e in selected]) \
            if witness else None
        self.extranonce += 1
        cb = coinbase(int(template['height']), value, witness_root, self.extranonce, self.producer)
        cb_tx = Tx(cb)
        root = merkle_root([bytes.fromhex(cb_tx.txid)[::-1]] + [bytes.fromhex(e.txid)[::-1] for e in selected])
        header = solve_header(int(template['version']), template['previousblockhash'], root,
                              int(template['curtime']), template['bits'])
        block = header + varint(1 + len(selected)) + cb + b''.join(e.tx.raw for e in selected)
        block_hash = dsha(header)[::-1].hex()
        extra = {'gate_dropped': gate_dropped} if gate is not None else {}
        if item4_record is not None:
            extra['item4'] = item4_record
        if self.producer is not None:
            extra['producer'] = self.producer
        built = {
            **extra,
            'template': template,
            'private_set': private_set,
            't_template_ns': t_template,
            't_template_answer_ns': t_answer,
            'miner_policy': self.policy_name,
            'height': int(template['height']),
            'block_hex': block.hex(),
            'block_hash': block_hash,
            'coinbase_txid': cb_tx.txid,
            'coinbase_value': value,
            'order': [{'txid': e.txid, 'source': e.source, 'fee': e.fee, 'vsize': e.vsize} for e in selected],
            'cut': chosen['cut'],
            'dropped': chosen['dropped'],
            'private_unresolved': sorted(excluded),
        }
        self.prepared = {'block': built, 'selected': [entry.txid for entry in selected]}
        if not submit:
            return {**built, 't_submit_ns': None, 'submit_result': None, 'prepared': True}
        return self.submit_prepared()

    def submit_prepared(self) -> dict:
        """Send the prepared block (`submitblock`); the held private transactions it holds leave the set."""
        if self.prepared is None:
            raise invalid('MINER_NO_PREPARED_BLOCK')
        prepared, self.prepared = self.prepared, None
        built = prepared['block']
        t_submit = CLOCK()
        result = self.rpc.call('submitblock', built['block_hex'])
        if result is None:
            for txid in prepared['selected']:
                self.private.pop(txid, None)
        return {**built, 't_submit_ns': t_submit, 'submit_result': result}


def gate_filter(entries: list[Entry], gate: dict, height: int) -> tuple[list[Entry], list[str]]:
    """ITEM1_WINNER_ONLY at block G (045b 4.6 `item 1 gate winners`: the winner's REGISTER is the one the
    test miner includes): drop the gate's REGISTERs other than the winner (and anything spending them), keep
    the rest. Refusals (exit 2): a malformed context (GATE_CONTEXT), a block at another height (GATE_HEIGHT),
    a winner not among the gate's REGISTERs (GATE_WINNER_NOT_REGISTER), a winner not a candidate
    (ITEM1_WINNER_MISSING)."""
    if not (isinstance(gate, dict) and set(gate) == {'height', 'winner', 'registers'}
            and type(gate['height']) is int and isinstance(gate['winner'], str) and HEX64.match(gate['winner'])
            and isinstance(gate['registers'], list)
            and all(isinstance(t, str) and HEX64.match(t) for t in gate['registers'])):
        raise invalid('GATE_CONTEXT')
    if gate['height'] != height:
        raise invalid('GATE_HEIGHT')
    if gate['winner'] not in gate['registers']:
        raise invalid('GATE_WINNER_NOT_REGISTER')
    losers = set(gate['registers']) - {gate['winner']}
    gone = {e.txid for e in entries if e.txid in losers}
    grew = True
    while grew:
        grew = False
        for e in entries:
            if e.txid not in gone and e.parents & gone:
                gone.add(e.txid)
                grew = True
    kept = [e for e in entries if e.txid not in gone]
    if gate['winner'] not in {e.txid for e in kept}:
        raise invalid('ITEM1_WINNER_MISSING')
    return kept, sorted(gone)


# D3a-2a: the item-4 policies (045b 4.3 item 4, :541-543). Each block of an item-4 run may carry one context;
# the policy name fixes its kind. Every value is DRAFT / PENDING_FREEZE.
CENSOR_BLOCKS = 144   # 045b :542: project transactions are excluded for 144 consecutive blocks (G … G + 143)
ITEM4_CONTEXT_KIND = {'ITEM4_SELF_FIRST_ZERO_FEE': 'SELF', 'ITEM4_CENSOR_144': 'CENSOR',
                      'ITEM4_REORG_REPLACE': 'REORG'}
ITEM4_CONTEXT_KEYS = {'SELF': {'kind', 'height', 'self'}, 'CENSOR': {'kind', 'first', 'txids', 'outpoints'},
                      'REORG': {'kind', 'drop'}}


def _txids(value) -> bool:
    return isinstance(value, list) and all(isinstance(t, str) and HEX64.match(t) for t in value)


def check_item4_context(context, policy: str) -> str:
    """The context's kind, after its closed shape (ITEM4_CONTEXT) and its policy (ITEM4_CONTEXT_POLICY)."""
    kind = context.get('kind') if isinstance(context, dict) else None
    if kind not in ITEM4_CONTEXT_KEYS or set(context) != ITEM4_CONTEXT_KEYS[kind]:
        raise invalid('ITEM4_CONTEXT')
    if ITEM4_CONTEXT_KIND.get(policy) != kind:
        raise invalid('ITEM4_CONTEXT_POLICY')
    ok = {'SELF': lambda c: type(c['height']) is int and isinstance(c['self'], str) and HEX64.match(c['self']),
          'CENSOR': lambda c: type(c['first']) is int and _txids(c['txids']) and isinstance(c['outpoints'], list)
          and all(isinstance(o, list) and len(o) == 2 and isinstance(o[0], str) and HEX64.match(o[0])
                  and type(o[1]) is int and 0 <= o[1] < U32 for o in c['outpoints']),
          'REORG': lambda c: _txids(c['drop'])}[kind]
    if not ok(context):
        raise invalid('ITEM4_CONTEXT')
    return kind


def with_descendants(entries: list[Entry], roots: set[str]) -> set[str]:
    """`roots` and every candidate that spends one of them, directly or through another."""
    gone = set(roots)
    grew = True
    while grew:
        grew = False
        for e in entries:
            if e.txid not in gone and e.parents & gone:
                gone.add(e.txid)
                grew = True
    return gone


def item4_filter(entries: list[Entry], context: dict, height: int, policy: str
                 ) -> tuple[list[Entry], list[Entry], dict]:
    """One block under an item-4 policy. Returns the candidates left for the ancestor-feerate order, the
    entries placed before them (the self REGISTER) and the block's record (`kind`, `filtered`: txid and
    reason, in candidate order, and the kind's fields).

    - SELF (`ITEM4_SELF_FIRST_ZERO_FEE`, block `height` only, ITEM4_CONTEXT_HEIGHT otherwise): the self
      transaction is placed at index 0 whatever its fee (0 included); it must be a candidate
      (ITEM4_SELF_MISSING) with no parent among the candidates (ITEM4_SELF_PARENT). A candidate spending an
      outpoint the self transaction spends is dropped (SELF_CONFLICT) with its descendants. A candidate
      spending the self transaction's output keeps its place in the order without it as a parent.
    - CENSOR (`ITEM4_CENSOR_144`): in blocks `first` … `first` + CENSOR_BLOCKS − 1 every candidate whose txid is
      listed (TXID) or that spends a listed outpoint (OUTPOINT: a replacement rung has a new txid but spends
      the project's funding output) is dropped, with its descendants (DESCENDANT). Outside the window
      nothing is dropped (`censor_index` null).
    - REORG (`ITEM4_REORG_REPLACE`): every listed txid (the replaced winner: after `invalidateblock` the
      template offers it again) is dropped with its descendants; `offered` lists the listed txids the
      candidates held."""
    kind = check_item4_context(context, policy)
    record: dict = {'kind': kind, 'policy': policy}
    first: list[Entry] = []
    roots: dict[str, str] = {}
    if kind == 'SELF':
        if height != context['height']:
            raise invalid('ITEM4_CONTEXT_HEIGHT')
        own = next((e for e in entries if e.txid == context['self']), None)
        if own is None:
            raise invalid('ITEM4_SELF_MISSING')
        if own.parents:
            raise invalid('ITEM4_SELF_PARENT')
        first = [own]
        roots = {e.txid: 'SELF_CONFLICT' for e in entries if e is not own and e.spends & own.spends}
        record.update({'self_txid': own.txid, 'self_fee': own.fee, 'self_index': 0})
        # Codex P2 r4434970466 (PR #643): own is already in the block at index 0, so a candidate spending its
        # output no longer counts it as a remaining parent (its package is itself and its other ancestors).
        entries = [e if own.txid not in e.parents else Entry(e.tx, e.fee, e.source, e.parents - {own.txid})
                   for e in entries if e is not own]
    elif kind == 'CENSOR':
        index = height - context['first']
        inside = 0 <= index < CENSOR_BLOCKS
        record.update({'censor_index': index if inside else None, 'first': context['first'],
                       'last': context['first'] + CENSOR_BLOCKS - 1})
        if inside:
            listed, outpoints = set(context['txids']), {tuple(o) for o in context['outpoints']}
            for e in entries:
                if e.txid in listed:
                    roots[e.txid] = 'TXID'
                elif e.spends & outpoints:
                    roots[e.txid] = 'OUTPOINT'
    else:
        drop = set(context['drop'])
        roots = {e.txid: 'REPLACED_WINNER' for e in entries if e.txid in drop}
        record['offered'] = sorted(roots)
    gone = with_descendants(entries, set(roots))
    record['filtered'] = [{'txid': e.txid, 'reason': roots.get(e.txid, 'DESCENDANT')}
                          for e in entries if e.txid in gone]
    return [e for e in entries if e.txid not in gone], first, record


def serve(stdin, stdout, miner: Miner) -> None:
    """The miner process's loop: one JSON command per line, one JSON answer per line."""
    for line in stdin:
        command = json.loads(line)
        op = command.get('op')
        try:
            if op == 'private':
                answer = {'txid': miner.add_private(command['hex']), 't_ns': CLOCK()}
            elif op == 'block' and 'item4' in command and 'gate' in command:
                raise invalid('MINER_CONTEXT_BOTH')   # A 6556082072 P3-3
            elif op == 'block' and 'item4' in command:   # D3a-2a: an item-4 policy's block context
                answer = miner.build_block(item4=command['item4'])
            elif op == 'block':
                answer = miner.build_block(command['gate']) if 'gate' in command else miner.build_block()
            elif op == 'prepare':   # D2-3b: build block G - 1 without sending it
                answer = miner.build_block(submit=False)
            elif op == 'submit':
                answer = miner.submit_prepared()
            elif op == 'replace':   # D2-3b: the private bidder's replacement rung
                answer = {**miner.replace_private(command['hex']), 't_ns': CLOCK()}
            elif op == 'stop':
                answer = {'stopped': True}
            else:
                raise invalid('MINER_COMMAND')
        except Refusal as error:
            answer = {'error': error.code, 'exit': error.exit_code}
        except oe.Prerequisite as error:
            answer = {'error': error_code('PREREQUISITE', error), 'exit': EXIT_PREREQUISITE}
        except oe.Mismatch as error:
            answer = {'error': error_code('MISMATCH', error), 'exit': EXIT_VALIDATION}
        stdout.write(json.dumps(answer, default=str) + '\n')
        stdout.flush()
        if op == 'stop':
            return


# ---------------------------------------------------------------------------------------------------------
# Topology (Q3 and A section 4 "nodes"): oe.Node narrowed per role.

# Exactly what the driver's own calls need on each node; the node whitelists its driver user for this set
# and nothing else. `stop` and `getblockchaininfo` are the start and stop path's, and the cookie check's.
# D2-2's READ_RPCS (tools/claude_track_ardr_cluster.py, PR #616): the only set the ITEM1 reader node's cookie
# may get (A #258 -6543158220 Q7). Not imported: D2-2's own allowlist is checked by D2-2.
READER_RPCS = frozenset({'getblockchaininfo', 'getblockhash', 'getblock'})
COMMON_RPCS = frozenset({'getblockchaininfo', 'getnetworkinfo', 'getbestblockhash', 'getrawmempool', 'stop'})
ROLE_RPCS = {
    'miner': COMMON_RPCS,
    'relay': COMMON_RPCS | {'addnode', 'getconnectioncount', 'sendrawtransaction'},
    'A': COMMON_RPCS | {'addnode', 'testmempoolaccept'},
    'B': COMMON_RPCS | {'addnode', 'testmempoolaccept'},
}
# D3a-2a: the ITEM4_REORG topology only (`Topology(reorg=True)`) adds exactly this to the miner node's driver
# user; no other user, node or topology gets it, and nothing gets `reconsiderblock`.
REORG_RPCS = frozenset({'invalidateblock'})
ROLE_VERSIONS = {'miner': 310100, 'relay': 310100, 'A': 310100, 'B': 300300}
STDIN_ARGUMENTS = 64 * 1024
TEXT_RESULTS = frozenset({'submitblock', 'sendrawtransaction'})
P2P_WHITELIST = '-whitelist=in,out,noban@127.0.0.1'   # D2-3b item 2 only (A Q5: loopback noban accepted)


def node_call_timeout(error: Exception) -> bool:
    """U4: a node call past its limit (`oe.Prerequisite('NODE_CALL_TIMEOUT <role>')`, exit 3). A wait that turns
    its own timeout into another code re-raises this one unchanged. A plain oe.Prerequisite, so RUN_END FAILED
    names it `PREREQUISITE NODE_CALL_TIMEOUT <role>`."""
    return isinstance(error, oe.Prerequisite) and str(error).split(' ', 1)[0] == 'NODE_CALL_TIMEOUT'


class RoleNode(oe.Node):
    """oe.Node with its own start and call path: `admin` (the driver's user, or in the miner process the
    miner process's user) may call exactly `rpcs`, and the node whitelists exactly that for it. The miner
    node also has `miner_user`, whitelisted for exactly `MINER_RPCS`. No send user, no fixture read user;
    the cookie is whitelisted to nothing. oe's `ALLOWED_RPCS` is not used, so oe.Node's other callers are
    unchanged."""

    def __init__(self, label: str, bindir: Path, datadir: Path, admin: oe.RunUser, rpcs: frozenset,
                 rpcport: int | None = None, miner_user: oe.RunUser | None = None,
                 extra_miner_users: tuple = (), cookie_rpcs: frozenset = frozenset(), p2p_whitelist: bool = False,
                 port: int | None = None):
        # #682: a topology passes the node's RPC and P2P ports from one `oe.draw_ports`.
        super().__init__(label, bindir, datadir, rpcport or oe.free_port(), None, admin, port=port)
        self.rpcs = frozenset(rpcs)
        self.miner_user = miner_user
        # D2-3a: the pool run's further miner process users (each whitelisted for exactly MINER_RPCS), and
        # the ITEM1 reader node's cookie set (exactly D2-2's READ_RPCS; every other node's stays empty).
        self.extra_miner_users = tuple(extra_miner_users)
        if self.extra_miner_users and miner_user is None:
            raise invalid('MINER_USERS')
        if not frozenset(cookie_rpcs) <= READER_RPCS:
            raise invalid('COOKIE_RPCS')
        self.cookie_rpcs = frozenset(cookie_rpcs)
        # D2-3b (A Q5): item 2's loopback peers get noban both ways, so a released rung is relayed without
        # Core's inv trickle delay. Off for every other topology.
        self.p2p_whitelist = bool(p2p_whitelist)

    def p2p_arguments(self) -> list[str]:
        return [P2P_WHITELIST] if self.p2p_whitelist else []

    def whitelist(self) -> list[str]:
        """The node's rpcauth and rpcwhitelist arguments."""
        users = [(self.admin, self.rpcs)] + ([(self.miner_user, MINER_RPCS)] if self.miner_user else []) \
            + [(user, MINER_RPCS) for user in self.extra_miner_users]
        return (['-rpcauth=' + user.line() for user, _ in users]
                + [f'-rpcwhitelist={user.user}:' + ','.join(sorted(rpcs)) for user, rpcs in users]
                + [f'-rpcwhitelist={oe.COOKIE_USER}:' + ','.join(sorted(self.cookie_rpcs)),
                   '-rpcwhitelistdefault=1'])   # a user without a line gets nothing

    def start(self) -> None:
        for binary in (self.bitcoind, self.cli):
            if not binary.is_file():
                raise oe.Prerequisite(f'NODE_BINARY_MISSING {self.role} {binary.name}')
        self.datadir.mkdir(parents=True, exist_ok=False)
        self.process = subprocess.Popen(
            [str(self.bitcoind), '-regtest', f'-datadir={self.datadir}', f'-port={self.port}',
             f'-rpcport={self.rpcport}', '-bind=127.0.0.1', '-rpcbind=127.0.0.1', '-rpcallowip=127.0.0.1',
             *self.whitelist(), *self.p2p_arguments(), '-disablewallet=1', '-listen=1', '-server=1', '-discover=0', '-dnsseed=0',
             '-fixedseeds=0', '-printtoconsole=0'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # #682: a node that exited instead of coming up is `PORT_COLLISION <role>` (Core's bind failure in its
        # debug log) or `NODE_EXITED <role>`, not the RPC error of whatever answered on its port.
        oe.wait_started(self, self.role)   # `self.call('-rpcwait', '-rpcwaittimeout=120', 'getblockchaininfo')`

    def raw(self, *args: str, cookie: bool = False) -> subprocess.CompletedProcess:
        method = oe.rpc_method(args)
        if method not in self.rpcs:
            raise oe.Mismatch(f'RPC_NOT_ALLOWED {method}')
        base = [str(self.cli), '-regtest', f'-datadir={self.datadir}', f'-rpcport={self.rpcport}']
        # U4 (A #632 6548007197 P3-7): a call past its 300 s limit is a missing prerequisite (exit 3, recorded
        # in RUN_END FAILED), not an internal error; never retried, the limit never extended. The message is
        # code words only: TimeoutExpired's own text holds the command line (the data directory).
        try:
            if cookie:
                return subprocess.run([*base, *args], capture_output=True, text=True, timeout=300, check=False)
            user = [f'-rpcuser={self.admin.user}', '-stdinrpcpass']
            if sum(len(a) for a in args) < STDIN_ARGUMENTS:
                return subprocess.run([*base, *user, *args], input=self.admin.password + '\n',
                                      capture_output=True, text=True, timeout=300, check=False)
            # A long argument (a block's hex) goes on standard input after the password: argv has a limit.
            at = args.index(method)
            return subprocess.run([*base, *user, '-stdin', *args[:at], method],
                                  input=self.admin.password + '\n' + ''.join(a + '\n' for a in args[at + 1:]),
                                  capture_output=True, text=True, timeout=300, check=False)
        except subprocess.TimeoutExpired:
            raise oe.Prerequisite(f'NODE_CALL_TIMEOUT {self.role}') from None

    def rpc(self, method: str, *params):
        """One call with JSON-typed parameters; a bare-string answer is returned as text."""
        args = [p if isinstance(p, str) else json.dumps(p) for p in params]
        if method not in TEXT_RESULTS:
            return self.call(method, *args)
        done = self.raw(method, *args)
        if done.returncode != 0:
            raise oe.Prerequisite(f'RPC_FAILED {self.role} {method} {done.stderr.strip()[:200]}')
        text = done.stdout.strip()
        return text or None

    @property
    def role(self) -> str:
        """The role as a code word for refusals: MINER, RELAY, A, B."""
        return self.label.upper()

    def call(self, *args: str):
        """oe.Node.call with a code-first message (the code and role print; the stderr never does)."""
        done = self.raw(*args)
        if done.returncode != 0:
            raise oe.Prerequisite(f'RPC_FAILED {self.role} {oe.rpc_method(args)} {done.stderr.strip()[:200]}')
        return oe.cli_result(args, done.stdout.strip())

    def cookie_refused(self) -> None:
        """The cookie is refused. On the ITEM1 reader node (cookie set = READ_RPCS) the probe is a method
        outside that set (`getnetworkinfo`), so the driver reads nothing with the cookie: only D2-2's
        subprocess does."""
        method = 'getnetworkinfo' if self.cookie_rpcs else 'getblockchaininfo'
        if method in self.cookie_rpcs:
            raise invalid('COOKIE_PROBE')   # the probe must be refused: the driver reads nothing with the cookie
        done = self.raw(method, cookie=True)
        if done.returncode == 0 or '403' not in done.stderr:
            raise oe.Mismatch(f'COOKIE_NOT_REFUSED {self.role}')


class NodeRPC:
    """`call(method, *params)` on a RoleNode (the shape the miner and the run use)."""

    def __init__(self, node: RoleNode):
        self.node, self.label = node, node.label

    def call(self, method: str, *params):
        return self.node.rpc(method, *params)


class MinerProcess:
    """The miner as its own process: it gets the miner process's credential on the miner node (whitelisted
    there for exactly `MINER_RPCS`) on standard input, and nothing else."""

    def __init__(self, node: RoleNode, policy_name: str, user: oe.RunUser | None = None,
                 producer: str | None = None):
        user = user or node.miner_user
        self.process = subprocess.Popen(
            [sys.executable, str(Path(__file__).absolute()), 'miner'], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
            env={k: v for k, v in os.environ.items() if not k.startswith('PYTHON')})
        self.ask({'bindir': str(node.cli.parent), 'datadir': str(node.datadir), 'rpcport': node.rpcport,
                  'user': user.user, 'password': user.password, 'policy': policy_name, 'producer': producer},
                 answer=False)

    def ask(self, command: dict, answer: bool = True):
        self.process.stdin.write(json.dumps(command) + '\n')
        self.process.stdin.flush()
        if not answer:
            return None
        line = self.process.stdout.readline()
        if not line:
            raise Refusal('MINER_PROCESS_ENDED', EXIT_INTERNAL)
        reply = json.loads(line, parse_float=str)
        if 'error' in reply:   # the miner process's exit code crosses the process boundary unchanged
            code = reply['error'] if isinstance(reply['error'], str) else 'MINER_ANSWER'
            exit_code = reply.get('exit')
            if exit_code not in (EXIT_VALIDATION, EXIT_PREREQUISITE, EXIT_INTERNAL, EXIT_SECURITY, EXIT_REFUSAL):
                exit_code = EXIT_INTERNAL
            raise Refusal(f'MINER {code}', exit_code)
        return reply

    def add_private(self, raw_hex: str) -> str:
        return self.ask({'op': 'private', 'hex': raw_hex})['txid']

    def build_block(self, gate: dict | None = None, item4: dict | None = None) -> dict:
        if gate is not None and item4 is not None:
            raise invalid('MINER_CONTEXT_BOTH')   # A 6556082072 P3-3: one block context, never two
        if item4 is not None:   # D3a-2a: crosses the process boundary as JSON
            return self.ask({'op': 'block', 'item4': item4})
        return self.ask({'op': 'block'} if gate is None else {'op': 'block', 'gate': gate})

    def prepare_block(self) -> dict:
        return self.ask({'op': 'prepare'})

    def submit_prepared(self) -> dict:
        return self.ask({'op': 'submit'})

    def replace_private(self, raw_hex: str) -> dict:
        return self.ask({'op': 'replace', 'hex': raw_hex})

    def stop(self) -> None:
        try:
            self.ask({'op': 'stop'})
            self.process.wait(timeout=30)
        except Exception:  # cleanup only
            self.process.kill()
            self.process.wait(timeout=30)
        for stream in (self.process.stdin, self.process.stdout):
            try:
                stream.close()
            except OSError:   # cleanup only: the process already ended
                pass


def miner_main() -> int:
    """`miner`: the separate miner process. Its first line is its configuration (the credential)."""
    config = json.loads(sys.stdin.readline())
    admin = oe.RunUser(config['user'])
    admin.password = config['password']
    node = RoleNode('miner', Path(config['bindir']), Path(config['datadir']), admin, MINER_RPCS,
                    rpcport=int(config['rpcport']))
    serve(sys.stdin, sys.stdout, Miner(NodeRPC(node), config['policy'], producer=config.get('producer')))
    return EXIT_DONE


class Topology:
    """Four fresh nodes: miner and relay (31.1), the testmempoolaccept pair A (31.1) and B (30.3)."""

    def __init__(self, node_a: Path, node_b: Path, work: Path, pool: bool = False, reader: bool = False,
                 p2p_whitelist: bool = False, reorg: bool = False):
        """`pool` (D2-3a POOL_50_30_20): the miner node gets two more miner process users, one per
        producer. `reader` (D2-3a ITEM1): Node A's cookie gets exactly READER_RPCS. `reorg` (D3a-2a
        ITEM4_REORG): the miner node's driver user gets ROLE_RPCS['miner'] | REORG_RPCS."""
        self.miner_user = oe.RunUser('bitagi-ardr-mine')
        self.pool_users = tuple(oe.RunUser(f'bitagi-ardr-mine-{p.lower()}') for p in PRODUCERS[1:]) if pool else ()
        self.users = {role: oe.RunUser(f'bitagi-ardr-{role}') for role in ('miner', 'relay', 'A', 'B')}
        rpcs = {role: ROLE_RPCS[role] | (REORG_RPCS if reorg and role == 'miner' else frozenset())
                for role in self.users}
        ports = iter(oe.draw_ports(2 * len(self.users)))   # #682: all eight in one draw, distinct
        self.nodes = {role: RoleNode(role, node_b if role == 'B' else node_a, work / role, user, rpcs[role],
                                     rpcport=next(ports), port=next(ports),
                                     miner_user=self.miner_user if role == 'miner' else None,
                                     extra_miner_users=self.pool_users if role == 'miner' else (),
                                     cookie_rpcs=READER_RPCS if reader and role == 'A' else frozenset(),
                                     p2p_whitelist=p2p_whitelist)
                      for role, user in self.users.items()}

    def producer_users(self) -> dict:
        """The pool run's miner process user per producer (A is the miner node's first miner user)."""
        return dict(zip(PRODUCERS, (self.miner_user, *self.pool_users)))

    def needles(self) -> tuple[str, ...]:
        return tuple(n for user in (*self.users.values(), self.miner_user, *self.pool_users)
                     for n in user.needles())

    def start(self) -> None:
        for node in self.nodes.values():
            node.start()
            node.cookie_refused()
        for node in self.nodes.values():
            version = node.call('getnetworkinfo')['version']
            if version != ROLE_VERSIONS[node.label]:
                raise oe.Prerequisite(f'NODE_VERSION {node.role} {version} expected {ROLE_VERSIONS[node.label]}')
        miner, relay = self.nodes['miner'], self.nodes['relay']
        relay.call('addnode', f'127.0.0.1:{miner.port}', 'onetry')
        for role in ('A', 'B'):
            self.nodes[role].call('addnode', f'127.0.0.1:{relay.port}', 'onetry')
        try:
            oe.wait_for(lambda: relay.call('getconnectioncount') >= 3, 'the four nodes to connect')
        except oe.Prerequisite as error:
            if node_call_timeout(error):
                raise
            raise oe.Prerequisite('NODES_NOT_CONNECTED') from None

    def stop(self) -> None:
        for node in reversed(list(self.nodes.values())):
            node.stop()


# ---------------------------------------------------------------------------------------------------------
# Raw log (format doc section 2).

class RawLog:
    """JSON Lines, LF only; every line carries the run header. A line holding a run secret is never written.
    U4: every needle has at least NEEDLE_MIN characters (NEEDLE_TOO_SHORT, exit 2, before the file exists), so
    a short one cannot match nearly every line."""

    def __init__(self, path: Path, header: dict, needles: tuple[str, ...]):
        if any(len(n) < NEEDLE_MIN for n in needles):
            raise invalid('NEEDLE_TOO_SHORT')
        self.header, self.needles, self.seq, self.size = header, needles, 0, 0
        self.stream = path.open('x', encoding='ascii', newline='')

    def write(self, event: str, unit: dict, **fields) -> dict:
        line = {'schema': LOG_SCHEMA, 'seq': self.seq + 1, 't_ns': fields.pop('t_ns', None) or CLOCK(),
                'event': event, **self.header, 'unit': unit, **fields}
        text = json.dumps(line, sort_keys=True, separators=(',', ':'), default=str) + '\n'
        # A needle is looked for both as written and as json.dumps escapes it (backslash, quote, non-ASCII),
        # in keys and values alike; a refused line leaves the file and seq as they were.
        if any(n and (n in text or json.dumps(n)[1:-1] in text) for n in self.needles):
            raise Refusal('SECRET_IN_LOG', EXIT_SECURITY)
        limit = LOG_LIMIT if event == 'RUN_END' else LOG_LIMIT - LOG_RESERVE
        if self.size + len(text) > limit:
            raise invalid('LOG_BOUND')   # the file, seq and size stay as they were
        self.seq += 1
        self.size += len(text)
        self.stream.write(text)
        self.stream.flush()
        return line

    def close(self) -> None:
        self.stream.close()


def log_header(loaded: dict) -> dict:
    """What every raw-log line carries from the policy read: mode, evidence status, the hashes, labels."""
    return {**{k: loaded[k] for k in ('mode', 'evidence_status', 'policy_sha256', 'registration_sha256')},
            'labels': LABELS}


def unit_id(experiment: str, run: int, gate: int | None = None, cohort: int | None = None) -> dict:
    return {'experiment': experiment, 'run': run, 'gate': gate, 'cohort': cohort}


# ---------------------------------------------------------------------------------------------------------
# The D1 run: a PR_SMOKE / EXPLORATORY shape on the real topology (D2 brings the gate campaigns).

SETUP_BLOCKS = 103          # coinbases at heights 1 and 2 mature for the block at height 104
ACCEPT_SECONDS = 120.0      # how long every node has to accept a submitted block
PUBLIC_FEE, PARENT_FEE, CHILD_FEE = 5000, 1000, 20000


def snapshots(log: RawLog, unit: dict, nodes: dict, private: set[str], before_block: bool) -> None:
    """Every node's mempool; before a block no private txid may be in any of them."""
    for role in ('relay', 'miner', 'A', 'B'):
        txids = sorted(nodes[role].call('getrawmempool'))
        log.write('MEMPOOL', unit, node=role, txids=txids, before_block=before_block)
        if before_block and private & set(txids):
            raise oe.Mismatch('PRIVATE_IN_MEMPOOL')


def wait_until(condition, what: str, seconds: float, poll: float) -> None:
    """oe.wait_for with a chosen poll interval (D2-3a campaigns poll at POLL_SECONDS)."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(poll)
    raise oe.Prerequisite(f'timed out waiting for {what}')


def sleep_until(at_ns: int) -> None:
    """Return no earlier than CLOCK() == `at_ns`."""
    while True:
        left = at_ns - CLOCK()
        if left <= 0:
            return
        time.sleep(left / 1e9)


def mine(log: RawLog, unit: dict, nodes: dict, miner, held: set[str], last_ns: list[int],
         gate: dict | None = None, poll: float | None = None, at_ns: int | None = None) -> dict:
    """One block. `held` is the run's set of private txids handed to the miner and not yet in an accepted
    block: the same set object for every block of the run; the txids this block holds leave it. D2-3a:
    `gate` is the ITEM1_WINNER_ONLY context of block G; `poll` (seconds) replaces oe.wait_for's 0.25 s poll
    while waiting for the four nodes (None: oe.wait_for, as D1). D2-3b: `at_ns` (CLOCK) holds the build until
    then, after the snapshots, so the template is taken no earlier than `at_ns` (None: at once, as D1)."""
    snapshots(log, unit, nodes, held, True)
    if at_ns is not None:
        sleep_until(at_ns)
    block = miner.build_block(gate) if gate is not None else miner.build_block()
    log.write('TEMPLATE', unit, t_ns=block['t_template_ns'], template=block['template'],
              private_set=block['private_set'])
    interval = whole_seconds(block['t_submit_ns'] - last_ns[0]) if last_ns[0] else None
    last_ns[0] = block['t_submit_ns']
    log.write('BLOCK', unit, t_ns=block['t_submit_ns'], **{k: block[k] for k in (
        'height', 'block_hex', 'block_hash', 'coinbase_txid', 'coinbase_value', 'miner_policy', 'order', 'cut',
        'dropped', 'private_unresolved', 'submit_result')}, interval_seconds=interval,
              **{k: block[k] for k in ('gate_dropped', 'producer') if k in block})
    if block['submit_result'] is not None:
        raise oe.Mismatch('SUBMITBLOCK_REFUSED')
    def accepted() -> bool:
        return all(node.call('getbestblockhash') == block['block_hash'] for node in nodes.values())

    try:
        if poll is None:
            oe.wait_for(accepted, 'all four nodes to accept the block', ACCEPT_SECONDS)
        else:
            wait_until(accepted, 'all four nodes to accept the block', ACCEPT_SECONDS, poll)
    except oe.Prerequisite as error:
        if node_call_timeout(error):
            raise
        raise oe.Mismatch('BLOCK_NOT_ACCEPTED') from None   # a block a node refuses is a validation failure
    log.write('BLOCK_ACCEPTED', unit, block_hash=block['block_hash'], nodes=sorted(nodes))
    held -= {item['txid'] for item in block['order']}
    return block


def smoke(log: RawLog, experiment: str, run_index: int, seed: bytes | None, nodes: dict, miner) -> dict:
    """Setup blocks from templates; one public transaction through the relay and a private parent and child
    through the miner; mempool snapshots; one block holding all three, accepted by all four nodes."""
    unit = unit_id(experiment, run_index)
    if seed is not None:
        t_gate, k = gate_interval_seconds(seed, run_index)
        log.write('DRAW', unit, e='ITEM2', r=run_index, label='GATE_INTERVAL', k=k, value=t_gate - 1,
                  t_gate_seconds=t_gate, applied=False)
    last = [0]
    coinbases = []
    held: set[str] = set()   # the run's held private set, checked before every block
    for _ in range(SETUP_BLOCKS):
        block = mine(log, unit, nodes, miner, held, last)
        coinbases.append((block['coinbase_txid'], block['coinbase_value']))
    (cb1, v1), (cb2, v2) = coinbases[0], coinbases[1]
    public = op_true_spend([(cb1, 0)], [v1 - PUBLIC_FEE]).hex()
    public_tx = Tx(bytes.fromhex(public))
    for role in ('A', 'B'):
        result = nodes[role].rpc('testmempoolaccept', [public])
        log.write('TESTMEMPOOLACCEPT', unit, node=role, txid=public_tx.txid, result=result)
        if not (isinstance(result, list) and len(result) == 1 and result[0].get('allowed') is True):
            raise oe.Mismatch('TESTMEMPOOLACCEPT_PUBLIC')
    sent = nodes['relay'].rpc('sendrawtransaction', public)
    log.write('PUBLIC_SENT', unit, node='relay', txid=public_tx.txid, hex=public, answer=sent)
    try:
        oe.wait_for(lambda: public_tx.txid in nodes['miner'].call('getrawmempool'), 'the public tx at the miner')
    except oe.Prerequisite as error:
        if node_call_timeout(error):
            raise
        raise oe.Prerequisite('PUBLIC_NOT_AT_MINER') from None
    parent = op_true_spend([(cb2, 0)], [v2 - PARENT_FEE]).hex()
    parent_tx = Tx(bytes.fromhex(parent))
    child = op_true_spend([(parent_tx.txid, 0)], [v2 - PARENT_FEE - CHILD_FEE]).hex()
    private = set()
    for raw in (parent, child):
        txid = miner.add_private(raw)
        private.add(txid)
        held.add(txid)
        log.write('PRIVATE_HANDOFF', unit, txid=txid, hex=raw)
    block = mine(log, unit, nodes, miner, held, last)
    order = [item['txid'] for item in block['order']]
    if sorted(order) != sorted(private | {public_tx.txid}) or held:
        raise oe.Mismatch('SMOKE_BLOCK_CONTENT')
    snapshots(log, unit, nodes, held, False)
    return {'blocks': SETUP_BLOCKS + 1, 'tip': block['block_hash'], 'order': order,
            'public': public_tx.txid, 'private': sorted(private)}


def run(args) -> dict:
    if not args.work.is_absolute():
        # U4: the work path is a raw-log needle; a relative one (`./w` is `w`) would match nearly every line.
        raise invalid('WORK_NOT_ABSOLUTE')
    loaded = load_policy(args.mode, args.policy, args.experiment, args.registration, args.registration_sha256)
    if args.experiment in ITEM4_EXPERIMENTS and loaded['params'] is None \
            and loaded['miner_policy'] in ITEM4_POLICIES:
        # D3a-2a pre-PR P3-1: without params D1's smoke would run under an item-4 policy name and apply no
        # filter. Refused in every mode, before any node or output.
        raise invalid('ITEM4_PARAMS_MISSING')
    if args.mode == 'CONFIRMATORY' and args.started_at is None:
        raise Refusal('STARTED_AT_MISSING', EXIT_PREREQUISITE)
    if args.experiment in CAMPAIGN_EXPERIMENTS:
        return run_campaign(args, loaded)   # D2-3a: ITEM1 and POOL
    if args.method_policy is not None:
        raise invalid('METHOD_POLICY_OUTSIDE_ITEM1')
    if args.mode == 'CONFIRMATORY' and args.experiment in L0_CONFIRMATORY:
        # D3a-2b-2b (A 6557723699 Q5-Q6, corrected by 6557914275): ITEM2 and item 4 CONFIRMATORY run the L0 seat,
        # entered here only (the L0 module's own CLI refuses CONFIRMATORY), after the checks above.
        return run_l0(args, loaded)
    if args.mode == 'CONFIRMATORY':
        # ITEM3 waits for D3.
        raise Refusal('CONFIRMATORY_CAMPAIGN_NOT_BUILT', EXIT_PREREQUISITE)
    if args.experiment == 'ITEM2' and loaded['params'] is not None:
        return run_item2(args, loaded)   # D2-3b: the item-2 run (EXPLORATORY, PR_SMOKE)
    if args.experiment in ITEM4_EXPERIMENTS and loaded['params'] is not None:
        return run_item4(args, loaded)   # D3a-2a: the item-4 run with the stand-in seat (EXPLORATORY, PR_SMOKE)
    started = args.started_at or {'source': 'LOCAL_EXPLORATORY', 'utc': time.strftime(
        '%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    if args.out.exists() or args.work.exists():
        raise Refusal('OUTPUT_EXISTS', EXIT_PREREQUISITE)
    work = oe.private(args.work)
    topology = Topology(args.node_a, args.node_b, work)
    log = RawLog(args.out, log_header(loaded), topology.needles() + (str(work), str(work.resolve())))
    miner = None
    unit = unit_id(args.experiment, args.run_index)
    try:
        log.write('RUN_START', unit, observation_start=started, miner_policy=loaded['miner_policy'],
                  node_versions=ROLE_VERSIONS)
        topology.start()
        miner = MinerProcess(topology.nodes['miner'], loaded['miner_policy'])
        summary = smoke(log, args.experiment, args.run_index, loaded['seed'], topology.nodes, miner)
        log.write('RUN_END', unit, status='DONE', **summary)
        return summary
    finally:
        if miner is not None:
            miner.stop()
        topology.stop()
        log.close()


# U3 (A Q5): the driver's own deadline for an ITEM1 or POOL run. The gate loop must leave the D2-2 share of the
# unit's limit free after its last gate: a node call (the probe, NODE_CALL_SECONDS), the worker's KEYS call (its
# timeout) and D2-2 itself (campaign.CLUSTER_SECONDS); and a margin for the RUN_END line, the teardown of four
# nodes and the miner processes, and the slice's start-up before this process reads its clock. The margin does
# NOT cover a gate already running at the deadline (its worker build is bounded at 1,800 s): unit note.
D2_2_SHARE_SECONDS = {'probe': 300, 'keys': 1800, 'cluster': 3600}
DEADLINE_MARGIN_SECONDS = 900


def run_deadline(unit_seconds: int | None, mode: str, started: tuple[float, int]) -> dict | None:
    """The deadline RUN_START records (fixed before the run): `gate_loop_seconds` = the unit's limit minus the
    D2-2 share and the margin, from this process's start (`started`: wall clock, monotonic ns). CONFIRMATORY needs
    one: without `--unit-seconds` exit 3 `UNIT_SECONDS_MISSING`, too short for the share exit 6
    `UNIT_SECONDS_SHORT`, both before any node. Elsewhere a missing or too short limit records no deadline
    (`null`): a PR smoke unit of 15 minutes is shorter than the share."""
    if unit_seconds is None:
        if mode == 'CONFIRMATORY':
            raise Refusal('UNIT_SECONDS_MISSING', EXIT_PREREQUISITE)
        return None
    if type(unit_seconds) is not int or unit_seconds < 1:
        raise invalid('UNIT_SECONDS')
    share = sum(D2_2_SHARE_SECONDS.values())
    loop = unit_seconds - share - DEADLINE_MARGIN_SECONDS
    if loop <= 0:
        if mode == 'CONFIRMATORY':
            raise Refusal('UNIT_SECONDS_SHORT', EXIT_REFUSAL)
        return None
    return {'unit_seconds': unit_seconds, 'd2_2_share_seconds': share, 'margin_seconds': DEADLINE_MARGIN_SECONDS,
            'gate_loop_seconds': loop, 'clock_ns': started[1] + loop * 10**9,
            'utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(int(started[0]) + loop))}


def run_campaign(args, loaded: dict) -> dict:
    """`_run_campaign` with the imported modules' refusals as this module's: run as a script, this module is
    `__main__`, and the campaign and converter modules raise `claude_track_ardr_driver.Refusal`."""
    import claude_track_ardr_driver as module
    if module is sys.modules.get(__name__):
        return _run_campaign(args, loaded)
    # P3-1: run as a script, build everything (topology, raw log, refusals) with the imported module, so the
    # campaign's RUN_END FAILED path sees one Refusal class; its refusals become this module's.
    try:
        return module._run_campaign(args, loaded)
    except module.Refusal as refusal:
        raise Refusal(refusal.code, refusal.exit_code) from None


def _run_campaign(args, loaded: dict) -> dict:
    """D2-3a: one ITEM1 or POOL run (`claude_track_ardr_campaign`). The params come from the policy's
    `experiments.<E>.params` (DRAFT_PARAMS when an EXPLORATORY or PR_SMOKE policy has none); the seed must be
    set (SEED_PENDING, exit 3). ITEM1 reads the method policy file (`--method-policy`): in CONFIRMATORY it is
    required, its SHA-256 must be in the registration's list (exit 6) and no value may be PENDING (exit 3);
    elsewhere it may be absent (every method value DRAFT). Q-pol-4 (a): in every mode its thresholds (a PENDING
    one: the DRAFT value) must be 045b :434's [4, 15], which the judge binds (METHOD_THRESHOLDS, exit 2)."""
    import claude_track_ardr_campaign as campaign
    import claude_track_ardr_truth as truth
    experiment, mode = args.experiment, args.mode
    if loaded['seed'] is None:
        raise Refusal('SEED_PENDING', EXIT_PREREQUISITE)
    params = loaded['params'] or DRAFT_PARAMS[experiment]
    if pending(params):
        raise Refusal('POLICY_PARAMS_PENDING', EXIT_PREREQUISITE)   # EXPLORATORY too: a run needs numbers
    method = None
    if experiment == 'ITEM1':
        if args.method_policy is None:
            if mode == 'CONFIRMATORY':
                raise Refusal('METHOD_POLICY_MISSING', EXIT_PREREQUISITE)
        else:
            blob = read_input(args.method_policy, POLICY_LIMIT)
            digest, declared = hashlib.sha256(blob).hexdigest(), loaded.get('method_policy')
            # U3 (A Q3-Q4): CONFIRMATORY names the file in the policy (`experiments.ITEM1.method_policy`), and
            # the file given must have that SHA-256 (in any mode when the policy names one) and be registered.
            if mode == 'CONFIRMATORY' and declared is None:
                raise Refusal('METHOD_POLICY_NOT_DECLARED', EXIT_PREREQUISITE)
            if declared is not None and digest != declared['sha256']:
                raise Refusal('METHOD_POLICY_SHA256', EXIT_REFUSAL)
            if mode == 'CONFIRMATORY' and digest not in loaded['registered_hashes']:
                raise Refusal('METHOD_POLICY_NOT_REGISTERED', EXIT_REFUSAL)
            method = truth.parse_method_policy(blob)
            values, _ = truth.method_values(method, mode)   # PENDING in CONFIRMATORY: exit 3, before any node
            if values['thresholds'] != ITEM1_REPORT_THRESHOLDS:
                raise invalid('METHOD_THRESHOLDS')   # Q-pol-4 (a): 045b :434, as the judge (METHOD_THRESHOLDS)
    elif args.method_policy is not None:
        raise invalid('METHOD_POLICY_OUTSIDE_ITEM1')
    cluster_tool = getattr(args, 'cluster_tool', None)
    if cluster_tool is not None and experiment != 'ITEM1':
        raise invalid('CLUSTER_TOOL_OUTSIDE_ITEM1')
    if cluster_tool is not None and mode == 'CONFIRMATORY':
        raise invalid('CLUSTER_TOOL_IN_CONFIRMATORY')   # P3-7: CONFIRMATORY runs the tree's own D2-2
    if experiment == 'ITEM1':
        tool = cluster_tool or campaign.CLUSTER_TOOL
        if not tool.is_file():
            raise Refusal('CLUSTER_TOOL_MISSING', EXIT_PREREQUISITE)   # P2-2: before any node starts
        method_values = truth.method_values(method, mode)[0] if method is not None else truth.DRAFT_METHOD
        truth.check_method_bounds(method_values, params)   # P3-4: D2-2's bounds, before any node starts
    started = args.started_at or {'source': 'LOCAL_EXPLORATORY', 'utc': time.strftime(
        '%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    deadline = run_deadline(getattr(args, 'unit_seconds', None), mode,
                            getattr(args, 'process_start', None) or (time.time(), CLOCK()))
    if args.out.exists() or args.work.exists():
        raise Refusal('OUTPUT_EXISTS', EXIT_PREREQUISITE)
    work = oe.private(args.work)
    topology = Topology(args.node_a, args.node_b, work / 'nodes', pool=experiment == 'POOL',
                        reader=experiment == 'ITEM1')
    log = RawLog(args.out, log_header(loaded), topology.needles() + (str(work), str(work.resolve())))
    try:
        result = campaign.campaign(experiment, params, loaded['seed'], args.run_index, args.node_a, args.node_b,
                                   work, log, topology, os.environ.get('CARGO', 'cargo'),
                                   cluster_tool=cluster_tool, method_policy=method, mode=mode,
                                   observation_start=started, deadline=deadline)
    finally:
        log.close()
    return {k: result[k] for k in ('winners', 'tip', 'timing')} | (
        {'cluster_metrics': result['cluster']['metrics']} if 'cluster' in result else {})


def run_item2(args, loaded: dict) -> dict:
    """D2-3b: one item-2 run (`claude_track_ardr_item2`), EXPLORATORY or PR_SMOKE (D3a-2b-2b: `run` sends
    CONFIRMATORY to `run_l0` before this). Built with the imported driver module, as `run_campaign` (P3-1)."""
    import claude_track_ardr_driver as module
    if module is sys.modules.get(__name__):
        return _run_item2(args, loaded)
    try:
        return module._run_item2(args, loaded)
    except module.Refusal as refusal:
        raise Refusal(refusal.code, refusal.exit_code) from None


def _run_item2(args, loaded: dict) -> dict:
    import claude_track_ardr_item2 as item2
    if loaded['seed'] is None:
        raise Refusal('SEED_PENDING', EXIT_PREREQUISITE)
    if pending(loaded['params']):
        raise Refusal('POLICY_PARAMS_PENDING', EXIT_PREREQUISITE)
    if getattr(args, 'cluster_tool', None) is not None:
        raise invalid('CLUSTER_TOOL_OUTSIDE_ITEM1')
    started = args.started_at or {'source': 'LOCAL_EXPLORATORY', 'utc': time.strftime(
        '%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    plan = item2.plan_run(loaded['seed'], args.run_index, loaded['params'], args.mode)   # before any node
    if args.out.exists() or args.work.exists():
        raise Refusal('OUTPUT_EXISTS', EXIT_PREREQUISITE)
    work = oe.private(args.work)
    topology = Topology(args.node_a, args.node_b, work / 'nodes', p2p_whitelist=True)
    log = RawLog(args.out, log_header(loaded), topology.needles() + (str(work), str(work.resolve())))
    try:
        result = item2.item2_run(plan, loaded['seed'], work, log, topology, os.environ.get('CARGO', 'cargo'),
                                 observation_start=started)
    finally:
        log.close()
    return {k: result[k] for k in ('status', 'gate', 'winner', 'predicted_candidates', 'observed_candidates',
                                   'timing')}


def run_item4(args, loaded: dict) -> dict:
    """D3a-2a: one item-4 run (`claude_track_ardr_item4`) with the stand-in seat, EXPLORATORY or PR_SMOKE
    (D3a-2b-2b: `run` sends CONFIRMATORY to `run_l0`). Built with the imported driver module, as `run_item2`."""
    import claude_track_ardr_driver as module
    if module is sys.modules.get(__name__):
        return _run_item4(args, loaded)
    try:
        return module._run_item4(args, loaded)
    except module.Refusal as refusal:
        raise Refusal(refusal.code, refusal.exit_code) from None


def _run_item4(args, loaded: dict) -> dict:
    import claude_track_ardr_item4 as item4
    if loaded['seed'] is None:
        raise Refusal('SEED_PENDING', EXIT_PREREQUISITE)
    if pending(loaded['params']):
        raise Refusal('POLICY_PARAMS_PENDING', EXIT_PREREQUISITE)
    if getattr(args, 'cluster_tool', None) is not None:
        raise invalid('CLUSTER_TOOL_OUTSIDE_ITEM1')
    started = args.started_at or {'source': 'LOCAL_EXPLORATORY', 'utc': time.strftime(
        '%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    plan = item4.plan_run(args.experiment, loaded['seed'], args.run_index, loaded['params'], args.mode)
    if plan['miner_policy'] != loaded['miner_policy']:
        raise invalid('ITEM4_POLICY_MISMATCH')   # A 6556082072 P3-2: the run's policy is the pinned one
    if args.out.exists() or args.work.exists():
        raise Refusal('OUTPUT_EXISTS', EXIT_PREREQUISITE)
    work = oe.private(args.work)
    topology = Topology(args.node_a, args.node_b, work / 'nodes', p2p_whitelist=True,
                        reorg=args.experiment == 'ITEM4_REORG')
    log = RawLog(args.out, log_header(loaded), topology.needles() + (str(work), str(work.resolve())))
    try:
        result = item4.item4_run(plan, loaded['seed'], work, log, topology, os.environ.get('CARGO', 'cargo'),
                                 observation_start=started)
    finally:
        log.close()
    return {k: result[k] for k in ('status', 'scenario', 'gate', 'winner', 'timing')}


# D3a-2b-2b: the experiments whose CONFIRMATORY run is the L0 seat's (`run_l0`). The Rust workers come from the
# repository's own build directories (the hosted workflow builds them first: ARDR_RUN_V1 section 26); the CLI
# takes no other target.
L0_CONFIRMATORY = ('ITEM2',) + ITEM4_EXPERIMENTS
L0_TARGETS = ('target/offline-build', 'target')


def run_l0(args, loaded: dict) -> dict:
    """D3a-2b-2b: one CONFIRMATORY ITEM2 or item-4 run with the L0 seat, built with the imported driver module
    (as `run_item2`)."""
    import claude_track_ardr_driver as module
    if module is sys.modules.get(__name__):
        return _run_l0(args, loaded)
    try:
        return module._run_l0(args, loaded)
    except module.Refusal as refusal:
        raise Refusal(refusal.code, refusal.exit_code) from None


def _run_l0(args, loaded: dict) -> dict:
    """The L0 module is imported here, lazily (A 6557914275: as item 2 and item 4; the driver is outside XD-1's
    closure). Before any node, output or worker: the params (POLICY_PARAMS_UNSET), the policy's `l0_seat`
    (`confirmatory_l0_seat`: L0_FREEZE_PENDING, exit 3, when absent; its p_0 rule and attempt count must be the
    run's, exit 6), the seed and the plan (CONFIRMATORY: no override, no control row). The run then uses the
    policy's seat (item 2) and `exact_height_miss`, and checks its `budget_sha256` against the product's budget
    record after the charge (L0_POLICY_BUDGET_SHA256); FZ-2's check that the digest is the product's record
    already runs in `confirmatory_l0_seat`, before any node (L0_POLICY_BUDGET_NOT_PRODUCT, exit 6). B-FZ-p round 2:
    CONFIRMATORY takes CONTINUE_WITHIN_LIMITS only; the STOP_CAMPAIGN twin is L0_STOP_CAMPAIGN_EXPLORATORY_ONLY
    (exit 6), right after `confirmatory_l0_seat`, before the plan and any node. Fix round 1 and FZ-6 F1: on the
    CLI path `load_policy` runs `confirmatory_l0_seat` and this STOP check first (so a CONFIRMATORY run with a bad
    `l0_seat` stops there, before ITEM4_PARAMS_MISSING, STARTED_AT_MISSING and this function's
    POLICY_PARAMS_UNSET); both stay here for a `loaded` given to `run_l0` directly."""
    import claude_track_ardr_l0 as l0
    if args.mode != 'CONFIRMATORY' or args.experiment not in L0_CONFIRMATORY:
        raise invalid('L0_RUN_MODE')
    if loaded['params'] is None:
        raise Refusal('POLICY_PARAMS_UNSET', EXIT_PREREQUISITE)
    if getattr(args, 'cluster_tool', None) is not None:
        raise invalid('CLUSTER_TOOL_OUTSIDE_ITEM1')
    frozen = l0.confirmatory_l0_seat(args.experiment, loaded['l0_seat'])   # the policy's, never the constants
    refuse_stop_twin(frozen['exact_height_miss'])   # B-FZ-p round 2: before any node
    if loaded['seed'] is None:
        raise Refusal('SEED_PENDING', EXIT_PREREQUISITE)
    if pending(loaded['params']):
        raise Refusal('POLICY_PARAMS_PENDING', EXIT_PREREQUISITE)
    if args.experiment == 'ITEM2':
        import claude_track_ardr_item2 as item2
        plan = item2.plan_run(loaded['seed'], args.run_index, loaded['params'], args.mode, l0_seat=frozen['seat'])
        go, keys = l0.item2_l0_run, ('status', 'gate', 'winner', 'predicted_candidates', 'observed_candidates',
                                     'l0_seat', 'l0_released_ks', 'l0_charged_not_released')
    else:
        import claude_track_ardr_item4 as item4
        plan = item4.plan_run(args.experiment, loaded['seed'], args.run_index, loaded['params'], args.mode, l0=True)
        if plan['miner_policy'] != loaded['miner_policy']:
            raise invalid('ITEM4_POLICY_MISMATCH')
        go, keys = l0.item4_l0_run, ('status', 'scenario', 'gate', 'winner', 'l0_released_ks',
                                     'l0_charged_not_released')
    if args.out.exists() or args.work.exists():
        raise Refusal('OUTPUT_EXISTS', EXIT_PREREQUISITE)
    offline_target, online_target = (oe.ROOT / name for name in L0_TARGETS)
    result, _ = go(plan, loaded['seed'], args.work, args.out, log_header(loaded), args.node_a, args.node_b,
                   os.environ.get('CARGO', 'cargo'), offline_target, online_target,
                   observation_start=args.started_at, l0_policy=frozen)
    if result.get('status') == 'REFUSED':
        raise Refusal(result['code'], result['exit'])
    return {k: result.get(k) for k in keys}


def started_at(text: str) -> dict:
    if not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z', text):
        raise argparse.ArgumentTypeError('UTC time as YYYY-MM-DDTHH:MM:SSZ')
    return {'source': 'GITHUB_JOB_STARTED_AT', 'utc': text}


def parser() -> argparse.ArgumentParser:
    top = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = top.add_subparsers(dest='command', required=True)
    for name in ('run', 'check-policy'):
        p = sub.add_parser(name)
        p.add_argument('--mode', required=True, choices=MODES)
        p.add_argument('--policy', required=True, type=Path)
        p.add_argument('--experiment', required=True, choices=EXPERIMENTS)
        p.add_argument('--registration', type=Path)
        p.add_argument('--registration-sha256')
        if name == 'run':
            p.add_argument('--run-index', type=int, default=0)
            p.add_argument('--node-a', required=True, type=Path, help='Core 31.1 bin dir (miner, relay, Node A)')
            p.add_argument('--node-b', required=True, type=Path, help='Core 30.3 bin dir (Node B)')
            p.add_argument('--work', required=True, type=Path, help='new directory for the four datadirs')
            p.add_argument('--out', required=True, type=Path, help='new raw-log file')
            p.add_argument('--started-at', type=started_at, help="the GitHub job's started_at (UTC)")
            p.add_argument('--method-policy', type=Path, help='ITEM1: the D2-2 method policy file (D2-3a)')
            p.add_argument('--cluster-tool', type=Path, help='ITEM1: D2-2 (default tools/claude_track_ardr_cluster.py)')
            p.add_argument('--unit-seconds', type=int, help="ITEM1, POOL: the unit's limit (the slice's), for the "
                           'deadline in RUN_START (U3, A Q5); other experiments ignore it')
    d = sub.add_parser('draw')
    d.add_argument('--seed', required=True)
    d.add_argument('--experiment', required=True)
    d.add_argument('--run', type=int, required=True)
    d.add_argument('--label', required=True)
    d.add_argument('--n', type=int, required=True)
    sub.add_parser('miner')
    return top


def main(argv: list[str] | None = None) -> int:
    if not __debug__:
        print(json.dumps({'result': 'FAIL', 'code': 'OPTIMIZED_PYTHON', 'exit': EXIT_REFUSAL}))
        return EXIT_REFUSAL
    process_start = (time.time(), CLOCK())   # U3: the deadline counts from this process's start
    args = parser().parse_args(argv)
    args.process_start = process_start
    if args.command == 'miner':
        return miner_main()
    try:
        try:
            if args.command == 'draw':
                if not HEX64.match(args.seed):
                    raise invalid('DRAW_SEED')
                value, k = draw(bytes.fromhex(args.seed), args.experiment, args.run, args.label, args.n)
                summary = {'value': value, 'k': k}
            elif args.command == 'check-policy':
                loaded = load_policy(args.mode, args.policy, args.experiment, args.registration,
                                     args.registration_sha256)
                summary = {k: loaded[k] for k in ('mode', 'evidence_status', 'policy_sha256',
                                                  'registration_sha256', 'miner_policy')}
            else:
                summary = run(args)
        except Refusal:
            raise
        except oe.Prerequisite as error:   # the message can hold a node's stderr or a path: codes only
            raise Refusal(error_code('PREREQUISITE', error), EXIT_PREREQUISITE) from None
        except oe.Mismatch as error:
            raise Refusal(error_code('MISMATCH', error), EXIT_VALIDATION) from None
    except Refusal as refusal:
        print(json.dumps({'result': 'FAIL', 'code': refusal.code, 'exit': refusal.exit_code}, sort_keys=True))
        return refusal.exit_code
    print(json.dumps({'result': 'DONE', **summary, 'exit': EXIT_DONE}, sort_keys=True))
    return EXIT_DONE


if __name__ == '__main__':
    import claude_track_exit
    claude_track_exit.run(main)
