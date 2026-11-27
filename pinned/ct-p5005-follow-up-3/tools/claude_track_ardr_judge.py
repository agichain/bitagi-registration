#!/usr/bin/env python3
"""CT-P5-001 J1-J5 and J4b: A's ARDR judge for item 1, the pool run, item 2 and item 4 (format ARDR_JUDGE_V1).

The judge reads only the raw log (ARDR_RUN_V1 section 2), the frozen policy and method policy, the 045b file
and, when given, the workflow's collection and the registration. It recomputes the seed draws (045b 4.6), the
item-1 plan, the expected clusters and the expected 4- and 15-report lists itself, and compares them with
D2-2's own output carried in the log. It imports no driver module (`claude_track_ardr_*`), no slices collector
and no offline export driver, and no driver imports it (A #258 6537782009 Q4). B may read it but not change it.

J2 replays the final chain from H0 with A's own harness (`crates/bitagi-signer/tests/ardr_judge_replay.rs`: the
product block decoder and `bitagi_core::apply_block_transition`), run as a subprocess with a fixed argv and no
shell; it checks one birth per judged gate at its height G, that birth's txid equal to the REGISTER the judge
found in block G, no other birth inside the judged gates, and G of each next gate equal to the Core's next birth
(`births` REPLAYED). EXPLORATORY with `--no-replay` keeps J1's reading (`births` UNVERIFIED_NO_REPLAY).
CONFIRMATORY needs the replay, the collection and the registration's `d2_2_tool_sha256` (A #258, J2 PR), which
every CLUSTER_TOOL line's `tool_sha256` must equal; a CONFIRMATORY record without the replay exists only when no
gate is judged (`births` NOT_REPLAYED_NO_JUDGED_GATE, outcome NOT_ESTABLISHED). The driver's GATE_END,
CORE_REPLAY and other claims are never used as facts; a disagreement with the bytes is only reported.

J3 adds the pool run (`pool`: block G of each pool gate read from the bytes, its coinbase producer tag against the
judge's own PRODUCER_H<G> draw) and the experiment's judgement across dispatches (`experiment`: the 10% rule over
the registered N, a unit no listed dispatch started counting as missing, and the pool's Herfindahl index over every
judged pool gate; ARDR_JUDGE_V1 sections 19 and 20).

J4a adds item 2 with the L0 project seat (`item2`: the plan recomputed, block G and every released rung read from
the bytes, the Core's one birth at G attributed to a seat by the funding outpoint it spends, never by Anchor key; the
item-2 exclusion codes re-derived; the L0 seat's fees by 045b :537 and its budget record) and `experiment --experiment
ITEM2` (the 10% rule and the E13 stratum over the 200 runs, the private win share, the section 4.5 rows :498-:501;
ARDR_JUDGE_V1 sections 21-23).

J5 adds item 4 (`item4`: one run of ITEM4_SELF_DEALING, ITEM4_FEE_ASYMMETRY, ITEM4_CENSORSHIP or ITEM4_REORG with the L0
seat, its plan recomputed, every block read from the bytes, the host's labels parsed from the set worker's own lines and
judged against 045b :1068 and its 2026-11-05 note, a reorg's replaced branch replayed; a stand-in log in EXPLORATORY
only), `experiment --experiment ITEM4_<S>` (the judged runs, the NO-GO evidence and the 10% rule per sub-scenario, 045b
:1084's note) and `item4-outcome` (item 4 and the section 4.5 rows :505-:506; ARDR_JUDGE_V1 sections 24-26; A's J5
decisions, #258 issuecomment-6656311995).

J4b wires item 2 and the item-4 sub-scenarios into the judge workflow (`artifacts`, `unpack`: their declarations name
no method policy), accepts a listed dispatch that declared nothing only on its attempt-1 jobs listing (`unpack`,
`experiment --undeclared-run`: the plan failed and no other job ran a step; section 16 P3-2), and gives the CONFIRMATORY
dispatch listing its `created` filter (`run-query`, two days before the bound; section 16 P3-8). ARDR_JUDGE_V1
section 27.

045b :1090 (frozen) asks of the judge record the fields `expected` and `observed` and the value INCONCLUSIVE, and that
a fold keeps its cause. Every record that states an outcome carries `verdict` {expected, observed, result,
inconclusive_reason}, made last from the finished outcome by one constant mapping, in every mode; the experiment
record tallies the causes of the gates that are not OBSERVED (`exclusions`) and shows each unit's collection code
(`unit_code`), and a per-run record shows its own (`run_shape.collection_code`). No outcome, state or count changes.
ARDR_JUDGE_V1 section 29.

Decisions implemented: A #258 issuecomment-6557890079, decisions 3, 4, 5, 6, 7, 11, 12 (with A's correction of
decision 12, #258 issuecomment-6558883776: a 0/0 metric is NOT_ESTABLISHED for that metric only, 045b:400-405)
and 13, and A's J1 review rounds (see ARDR_JUDGE_V1 section 16).
Class T Regtest development evidence only. Stdlib only. No key material.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime
import decimal
import errno
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import zipfile

TOOL_PATH = Path(__file__).resolve()
ROOT = TOOL_PATH.parents[1]
PREREG_DEFAULT = ROOT / 'docs' / 'claude-track' / 'plans' / 'CT-P3-045b_PREREGISTRATION_DRAFT_EN.md'

EXIT_DONE = 0
EXIT_VALIDATION = 2
EXIT_PREREQUISITE = 3
EXIT_INTERNAL = 4
EXIT_REFUSAL = 6

JUDGEMENT_SCHEMA = 'BITAGI_CT_ARDR_JUDGEMENT_V1'
RAW_SCHEMA = 'BITAGI_CT_ARDR_RAW_V1'
POLICY_SCHEMA = 'BITAGI_CT_ARDR_POLICY_V1'
METHOD_POLICY_SCHEMA = 'BITAGI_CT_ARDR_METHOD_POLICY_V1'
COLLECTION_SCHEMA = 'BITAGI_CT_ARDR_COLLECTION_V2'
CLUSTER_OUTPUT_SCHEMA = 'BITAGI_CT_ARDR_CLUSTER_V1'
GATES_SCHEMA = 'BITAGI_CT_ARDR_GATES_V1'
CLUSTER_METHOD_SCHEMA = 'BITAGI_CT_ARDR_CLUSTER_METHOD_V1'
CLUSTER_TRUTH_SCHEMA = 'BITAGI_CT_ARDR_CLUSTER_TRUTH_V1'
BIDDERS_SCHEMA = 'BITAGI_CT_ARDR_BIDDERS_V1'

RAW_LABELS = ['CLASS_T', 'REGTEST', 'TEST_ONLY_OP_TRUE_OUTPUTS', 'CLASS_T_DEVELOPMENT_EVIDENCE_NOT_S17_PREP',
              'DRIVER_RECORD_NOT_VERDICT']   # ARV1 section 2
RECORD_LABELS = ['CLASS_T', 'REGTEST', 'JUDGE_RECORD', 'J2_ITEM1_ONLY']
MODES = ('CONFIRMATORY', 'EXPLORATORY', 'PR_SMOKE')
EXPERIMENTS = ('ITEM1', 'ITEM2', 'ITEM3', 'ITEM4_SELF_DEALING', 'ITEM4_FEE_ASYMMETRY', 'ITEM4_CENSORSHIP',
               'ITEM4_REORG', 'POOL')   # ARV1 section 3, in order: ITEM1 is experiment 1 of the observation id
ITEM1_EVENTS = frozenset({
    'RUN_START', 'DRAW', 'MEMPOOL', 'TEMPLATE', 'BLOCK', 'BLOCK_ACCEPTED', 'TESTMEMPOOLACCEPT', 'PUBLIC_SENT',
    'PRIVATE_HANDOFF', 'RUN_END',                                            # section 2
    'FUNDING_SENT', 'LADDER_EMPTY', 'GATE_NO_BID', 'GENERATED', 'CORE_REPLAY',  # section 12
    'BIDDERS', 'GATE_START', 'GATE_END', 'CLUSTER_TOOL', 'PREFIX_START',     # section 16
})
POOL_EVENTS = ITEM1_EVENTS - {'CLUSTER_TOOL', 'PREFIX_START'}   # J3: a pool run runs no D2-2 (ARV1 sections 16, 17)
# J4a: an item-2 log (ARV1 :82-95, sections 12 and 16, section 20 :1652-1670, section 22 :1965-1983).
L0_EVENTS = frozenset({'L0_FUNDING_BLOCK', 'L0_LAUNCH_START', 'L0_SET_CHARGED', 'L0_TURN', 'L0_READY', 'L0_ADMISSION',
                       'L0_BUDGET', 'L0_LAUNCH_END', 'L0_RELAY', 'L0_LABELS', 'L0_BUDGET_COUNTERS', 'L0_RUNG_TEST',
                       'L0_STOP_FAILED'})
ITEM2_EVENTS = POOL_EVENTS | L0_EVENTS | {'SCHEDULE', 'REPLACED_RUNG_MISSING', 'PRIVATE_REPLACE', 'RELEASE',
                                          'RELEASE_MEMPOOLS', 'G_TIMING'}
ITEM2_KEPT = ('MEMPOOL', 'DRAW', 'SCHEDULE', 'RELEASE', 'PUBLIC_SENT', 'PRIVATE_HANDOFF', 'PRIVATE_REPLACE',
              'RELEASE_MEMPOOLS',
              'REPLACED_RUNG_MISSING', 'G_TIMING', 'L0_LAUNCH_START', 'L0_SET_CHARGED', 'L0_READY', 'L0_ADMISSION',
              'L0_BUDGET', 'L0_RELAY', 'L0_LABELS', 'L0_BUDGET_COUNTERS', 'L0_RUNG_TEST')
# J5: an item-4 log (ARV1 sections 22-25). The four sub-scenarios in ARV1 section 3's order (the observation id's e is
# 4, 5, 6 or 7); an item-4 run writes no DRAW, L0_LABELS, RELEASE_MEMPOOLS, G_TIMING or PRIVATE_REPLACE (ARV1 section
# 24: its turns' labels and counters are in ITEM4_L0_OBSERVE); REPLACED_RUNG_MISSING only in a stand-in run.
ITEM4_SCENARIOS = ('ITEM4_SELF_DEALING', 'ITEM4_FEE_ASYMMETRY', 'ITEM4_CENSORSHIP', 'ITEM4_REORG')
ITEM4_L0_EVENTS = frozenset({'ITEM4_L0_OBSERVE', 'ITEM4_LABELS', 'ITEM4_L0_RELEASE', 'ITEM4_L0_LABEL_LINE'})
ITEM4_EVENTS = (POOL_EVENTS - {'DRAW', 'LADDER_EMPTY', 'GATE_NO_BID'}) | (L0_EVENTS - {'L0_LABELS'}) | ITEM4_L0_EVENTS \
    | {'SCHEDULE', 'RELEASE', 'REPLACED_RUNG_MISSING', 'SCENARIO_NOT_RUN', 'ASYMMETRIC_BID', 'MINER_FILTER',
       'SELF_REGISTER', 'CENSOR_WINDOW', 'CENSOR_MEMPOOL', 'REORG'}
ITEM4_KEPT = ITEM2_KEPT + ('L0_TURN', 'BLOCK_ACCEPTED', 'SCENARIO_NOT_RUN', 'ASYMMETRIC_BID', 'SELF_REGISTER',
                           'CENSOR_WINDOW', 'CENSOR_MEMPOOL', 'REORG', 'ITEM4_L0_OBSERVE', 'ITEM4_LABELS',
                           'ITEM4_L0_RELEASE', 'ITEM4_L0_LABEL_LINE')
ENVELOPE = ('schema', 'seq', 't_ns', 'event', 'mode', 'evidence_status', 'policy_sha256', 'registration_sha256',
            'labels', 'unit')
UNIT_KEYS = {'experiment', 'run', 'gate', 'cohort'}
OWN_LABELS_EVENTS = frozenset({'L0_LABELS', 'ITEM4_LABELS', 'ITEM4_L0_OBSERVE'})   # their `labels` is a field (J5)

POLICY_LIMIT = 1 << 20
METHOD_LIMIT = 1 << 20
REGISTRATION_LIMIT = 1 << 20
COLLECTION_LIMIT = 64 << 20
PREREG_LIMIT = 4 << 20
RAW_LIMIT = 256 << 20        # ARV1 section 13: a raw log is read whole once, at most 256 MiB
LINE_LIMIT = 32 << 20        # one line, LF included
RAW_LINES = 4_000_000
BLOCK_LIMIT = 4_000_000      # bytes of one serialized block
SHOWN = 100                  # disagreement entries listed in the record (all are counted)

U32 = 1 << 32
U64 = 1 << 64
HEX64 = re.compile(r'[0-9a-f]{64}\Z')
HEX = re.compile(r'(?:[0-9a-f]{2})*\Z')
CODE_WORD = re.compile(r'[A-Z][A-Z0-9_]*(?: [A-Z0-9_]+)*\Z')

# ARV1 section 18 (EXPLORATORY without params) and section 15 (the method policy's DRAFT values).
DRAFT_PARAMS = {'b': 3000, 'H0': 110, 'gates_per_run': 200}
DRAFT_METHOD = {'floor_height': 1, 'max_depth': 16, 'max_window_blocks': 40000, 'thresholds': [4, 15]}
CANDIDATE_VSIZE = 213        # ARV1 section 9: v, the measured vsize of the product REGISTER
MINER_POLICY = 'ITEM1_WINNER_ONLY'   # ARV1 section 18

# Decision 5 (#258 6557890079): every NO-GO threshold is a judge constant that cites its 045b line; the record
# carries the SHA-256 of the 045b file read. `phrase` must stand on the cited line of that file (run-time check,
# PREREG_CITATION), so a 045b edit that moves or changes a cited line makes the judge refuse until it is updated.
THRESHOLDS = (
    {'name': 'ITEM1_LINK_RECALL_MIN', 'item': 'ITEM1', 'value': {'num': 1, 'den': 1}, 'line': 380,
     'phrase': 'link-based recall or precision below 1.0'},
    {'name': 'ITEM1_LINK_PRECISION_MIN', 'item': 'ITEM1', 'value': {'num': 1, 'den': 1}, 'line': 380,
     'phrase': 'link-based recall or precision below 1.0'},
    {'name': 'ITEM1_REPORT_THRESHOLDS', 'item': 'ITEM1', 'value': [4, 15], 'line': 434,
     'phrase': '4 consecutive gates triggers'},
    {'name': 'ITEM1_GATES', 'item': 'ITEM1', 'value': 200, 'line': 521, 'phrase': '200 contested gates'},
    {'name': 'ITEM1_WALLETS_OWNERS', 'item': 'ITEM1', 'value': [40, 10], 'line': 531,
     'phrase': '40 synthetic wallets, 10 synthetic owners'},
    {'name': 'ITEM1_ANCESTRY_SHARE', 'item': 'ITEM1', 'value': {'num': 30, 'den': 100}, 'line': 553,
     'phrase': 'shares ancestry when the value is below 30'},
    {'name': 'ITEM1_KEY_REUSE_SHARE', 'item': 'ITEM1', 'value': {'num': 30, 'den': 100}, 'line': 554,
     'phrase': 'base Anchor key when the value is below 30'},
    {'name': 'ITEM1_PLANTED_GATES', 'item': 'ITEM1', 'value': [100, 119], 'line': 532,
     'phrase': 'In gates 100 to 119'},
    {'name': 'ITEM1_EXCLUSION_UNIT', 'item': 'ITEM1', 'value': 'GATE', 'line': 546,
     'phrase': 'item 1: a gate inside its one 200-gate run'},
    {'name': 'EXCLUSION_LIMIT', 'item': 'ALL', 'value': {'num': 1, 'den': 10}, 'line': 572,
     'phrase': 'exclusions above 10% of an'},
    {'name': 'ITEM2_PRIVATE_WIN_SHARE_MAX', 'item': 'ITEM2', 'value': {'num': 1, 'den': 2}, 'line': 381,
     'phrase': 'more than 0.5 of contested gates'},
    {'name': 'MINED_LOSING_SHARE_MAX', 'item': 'ITEM2', 'value': {'num': 25, 'den': 100}, 'line': 499,
     'phrase': "more than 25% of the project's attempted gates"},
    {'name': 'POOL_HHI_MAX', 'item': 'POOL', 'value': {'num': 1, 'den': 2}, 'line': 504,
     'phrase': 'Herfindahl index above 0.5'},
    {'name': 'ITEM3_ZERO_BEAT_GATES', 'item': 'ITEM3', 'value': 15, 'line': 435,
     'phrase': 'consecutive gates followed by zero accepted BEAT | 15'},
    # J3 (A #258 6557890079, the J3 row and decisions 6 and 7; ARDR_JUDGE_V1 section 19).
    {'name': 'POOL_RUNS_GATES', 'item': 'POOL', 'value': [50, 4], 'line': 545,
     'phrase': '4 gates per run (50 runs, 200 gates)'},
    {'name': 'POOL_PRODUCER_DRAW', 'item': 'POOL', 'value': {'n': 100, 'A_below': 50, 'B_below': 80}, 'line': 560,
     'phrase': '`n = 100`: producer A below 50, B below 80, else C'},
    {'name': 'POOL_EXCLUSION_UNIT', 'item': 'POOL', 'value': 'GATE', 'line': 546,
     'phrase': 'Pool: a run of 4 gates'},   # decision 6: the line defines the run; the 10% counts its gates
    {'name': 'ITEM1_RUNS', 'item': 'ITEM1', 'value': 1, 'line': 546,
     'phrase': 'item 1: a gate inside its one 200-gate run'},
    {'name': 'FIXED_N', 'item': 'ALL', 'value': 'REGISTERED_N', 'line': 571,
     'phrase': 'Stopping rule: fixed N, no early stopping'},
    {'name': 'DISPATCHED_ONCE', 'item': 'ALL', 'value': 'ONCE', 'line': 577,
     'phrase': 'each unit is dispatched once'},
    # J4a (ARDR_JUDGE_V1 sections 21-23; A's J4a decision 1, 2026-11-02): item 2, the L0 seat and the section 4.5
    # rows on the item-2 campaign. Lines 1050 and above are the 045b freeze draft's (sections 14.4 and 14.15).
    {'name': 'ITEM2_RUNS', 'item': 'ITEM2', 'value': 200, 'line': 546,
     'phrase': 'Item 2: one run is one contested gate, `r` = 0 to 199'},
    {'name': 'ITEM2_EXCLUSION_UNIT', 'item': 'ITEM2', 'value': 'RUN', 'line': 546,
     'phrase': 'Item 2: one run is one contested gate'},
    {'name': 'ITEM2_COMPLETED', 'item': 'ITEM2', 'value': 'OBSERVED', 'line': 1218,
     'phrase': 'A run of item 2 is "completed" when it ends OBSERVED'},
    {'name': 'ITEM2_QUALIFYING', 'item': 'ITEM2', 'value': {'first': 0, 'last': 98, 'step': 2}, 'line': 1218,
     'phrase': 'the first 50 private-present runs, `r` = 0, 2, \u2026, 98'},
    {'name': 'ITEM2_STRATUM_LIMIT', 'item': 'ITEM2', 'value': {'num': 5, 'den': 50}, 'line': 1218,
     'phrase': 'more than 5 of the 50 qualifying runs are missing or EXCLUDED'},
    {'name': 'ITEM2_GATE_INTERVAL', 'item': 'ITEM2', 'value': {'n': 1200, 'plus': 1}, 'line': 559,
     'phrase': '`n = 1,200`: `t_G` = value + 1 seconds'},
    {'name': 'ITEM2_RUNG_SECONDS', 'item': 'ITEM2', 'value': 60, 'line': 537,
     'phrase': 'exactly `60 \u00d7 k` seconds later'},
    {'name': 'ITEM2_LADDER', 'item': 'ITEM2', 'value': {'v': 213, 'last_rung': 7, 'cap_feerate': '4b'}, 'line': 537,
     'phrase': 'or after rung 7, whichever comes first'},
    {'name': 'ITEM2_EXCLUSION_CODES', 'item': 'ITEM2',
     'value': ['RELEASE_NOT_IN_TEMPLATE', 'RELEASE_AFTER_G', 'G_LATE', 'REPLACED_RUNG_NOT_IN_MEMPOOL'], 'line': 1050,
     'phrase': "Item 2's gate codes: `RELEASE_NOT_IN_TEMPLATE`"},
    {'name': 'ITEM2_G_LATE_SECONDS', 'item': 'ITEM2', 'value': 1, 'line': 1050,
     'phrase': "`G_LATE` (block G's template taken 1 s or more after `t0 + t_G`)"},
    {'name': 'ITEM2_WINNER_BY_TXID', 'item': 'ITEM2', 'value': 'TXID', 'line': 1220,
     'phrase': 'winners are read by txid (item2 :638-642)'},
    {'name': 'CANDIDATES_EXACT', 'item': 'ITEM2', 'value': 'OBSERVED_EQUALS_PREDICTED', 'line': 498,
     'phrase': 'in any gate the observed count differs from the predicted count'},
    # 2026-11-10 (A, after the 045b freeze #664 and B-FZ-p #759): the L0 budget values below are the frozen ones (045b
    # A1 :1175 and A2 :1176, FD-CT-102; the Class T record `7d0a7a35..`, section 14.21 :1898-1899). Two names keep
    # their DRAFT: ARDR_JUDGE_V1 :161-163 and its J4a review note (:1232) name them, and every record's `thresholds`
    # lists them by name. Their values, and the :500 threshold's `source`, are the freeze's.
    {'name': 'L0_LOSING_FEE_PER_ATTEMPT_MAX', 'item': 'ITEM2', 'value': {'num': 500000, 'den': 24, 'source': 'FROZEN'},
     'line': 500,
     'phrase': "the project's measured losing fees per attempted gate above "
               "`max_fee_exposure_sat / max_gate_attempts`"},
    {'name': 'L0_LOSING_FEE_DRAFT', 'item': 'ITEM2', 'value': {'num': 500000, 'den': 24}, 'line': 1176,
     'phrase': '20,833 sat per attempt stays (500,000 / 24'},
    {'name': 'L0_MAX_FEE_PER_CANDIDATE_DRAFT', 'item': 'ITEM2', 'value': 30000, 'line': 1175,
     'phrase': '`max_fee_per_candidate_sat` 30,000 sat; `max_fee_exposure_sat` 500,000 and '
               '`max_principal_exposure_sat` 240,000 as drafted'},
    # 2026-11-12 (A, FD-CT-133, finding #807; format doc section 30): the rule is MAX_P0_TWO_RUNGS. Frozen 045b :1053
    # keeps its words; the row still cites them as the value it replaces (`amends`), so a 045b without them is refused.
    {'name': 'L0_P0_RULE', 'item': 'ITEM2', 'value': 'MAX_P0_TWO_RUNGS', 'line': 1053,
     'phrase': '`p_0 = \u23082.5 \u00d7 b\u2309` sat/kvB', 'amends': {'value': 'CEIL_2_5_B', 'by': 'FD-CT-133'}},
    {'name': 'L0_MAX_GATE_ATTEMPTS', 'item': 'ITEM2', 'value': 24, 'line': 1053,
     'phrase': "frozen policy B wrote (B-FZ-pol, `c1baa8db`): `p0_rule` `CEIL_2_5_B`, `max_gate_attempts` 24"},
    {'name': 'L0_FEE_EXACT', 'item': 'ITEM2', 'value': 'F_K_EVERY_RUNG', 'line': 1053,
     'phrase': 'a difference fails the run (`L0_FEE_MISMATCH`)'},
    {'name': 'L0_CHARGED_NOT_RELEASED', 'item': 'ITEM2', 'value': 'NOT_RELEASED', 'line': 1055,
     'phrase': 'the judge does not count them as released rungs'},
    {'name': 'ITEM2_L0_SEAT', 'item': 'ITEM2', 'value': 1, 'line': 1219,
     'phrase': 'The L0 project bidder holds public seat S1 in all 200 item-2 runs'},
    {'name': 'ITEM2_L0_H0', 'item': 'ITEM2', 'value': 1000, 'line': 1054,
     'phrase': 'Every item-2 run and every item-4 run uses H0 = 1000'},
    {'name': 'ROW_NOT_MEASURED', 'item': 'ITEM2', 'value': 'NOT_ESTABLISHED', 'line': 1061,
     'phrase': 'A row the policy cannot attribute is reported NOT_MEASURED'},
    {'name': 'PERCENTILE_NEAREST_RANK', 'item': 'ALL', 'value': 'NEAREST_RANK', 'line': 565,
     'phrase': 'Percentile estimator (every p50 and p95 in this document): nearest rank.'},
    # J5 (ARDR_JUDGE_V1 sections 24-26; A's J5 decisions, #258 issuecomment-6656311995): item 4. Lines 1063-1084 are
    # the freeze draft's section 14.4; the notes dated 2026-11-05 at the end of :1068 and :1084 are A's J5 lines (Q2:
    # the three sub-scenarios' labels; Q1 and Q4: the label-judged runs and the 10% rule per sub-scenario).
    {'name': 'ITEM4_MISLABEL_NOGO', 'item': 'ITEM4', 'value': 'ANY_JUDGED_LABEL_DIFFERS', 'line': 383,
     'phrase': 'any case where the project tooling mislabels a reorg-replaced or lost gate'},
    {'name': 'ITEM4_NOT_RUN', 'item': 'ITEM4', 'value': 'NOT_ESTABLISHED', 'line': 383,
     'phrase': 'any of the four sub-scenarios not run'},
    {'name': 'ITEM4_LABEL_TABLE', 'item': 'ITEM4', 'value': [415, 416, 419], 'line': 410,
     'phrase': "A's judge compares the tooling's labels with this table"},
    {'name': 'ITEM4_LOST_NOT_MINED', 'item': 'ITEM4', 'value': {'outcome': 'Stale', 'opening_block_missed': True},
     'line': 415, 'phrase': '`Stale{target_gate_height: G, …}` with `opening_block_missed` true; not Done'},
    {'name': 'ITEM4_E10S', 'item': 'ITEM4', 'value': 'P0_INCLUDED_NO_EFFECT_IN_G', 'line': 419,
     'phrase': 'P0 is `Done:IncludedNoEffect{G}` in the same block'},
    {'name': 'ITEM4_TURNS', 'item': 'ITEM4', 'line': 1068,
     'value': {'ITEM4_SELF_DEALING': [['G', 0]], 'ITEM4_FEE_ASYMMETRY': [['G', 0]],
               'ITEM4_CENSORSHIP': [['G', 0], ['G+143', 143], ['G+144', 144]]},
     'phrase': 'The planned turns are G for self dealing and fee asymmetry, and G, G + 143 and G + 144 for censorship'},
    {'name': 'ITEM4_LABEL_INCLUDED', 'item': 'ITEM4', 'line': 1068,
     'value': {'verdict': 'Done:IncludedNoEffect@<height>', 'outcome': 'IncludedNoEffect@<height>'},
     'phrase': 'outcome `IncludedNoEffect@<height>`, verdict `Done:IncludedNoEffect@<height>`'},
    {'name': 'ITEM4_LABEL_LOST', 'item': 'ITEM4', 'line': 1068,
     'value': {'verdict': 'Refuse:GateAdvanced', 'outcome': 'Stale@<G>><next birth>'},
     'phrase': 'Rung 0 released and not mined (censorship at G and G + 143): outcome `Stale@G><next birth>`, verdict '
               '`Refuse:GateAdvanced`'},
    {'name': 'ITEM4_LABEL_UNRELEASED', 'item': 'ITEM4', 'line': 1068,
     'value': {'verdict': 'Wait:OfflineSignaturePending', 'outcome': 'Stale@<G>><next birth>'},
     'phrase': 'A rung k ≥ 1, charged and never released: outcome `Stale@G><next birth>`, verdict '
               '`Wait:OfflineSignaturePending`'},
    {'name': 'ITEM4_FLAGS', 'item': 'ITEM4', 'line': 1068,
     'value': {'opening_block_missed': True, 'reorged_before_inclusion': False},
     'phrase': 'Every rung at every turn: `opening_block_missed` true (this is the value :419 leaves to the row '
               'table) and `reorged_before_inclusion` false'},
    {'name': 'ITEM4_NEXT_BIRTH', 'item': 'ITEM4', 'value': 'JUDGE_REPLAY', 'line': 1068,
     'phrase': "The next birth is the judge's own replay at the turn's height"},
    {'name': 'ITEM4_MISLABEL_FIELDS', 'item': 'ITEM4', 'line': 1068,
     'value': ['verdict', 'outcome', 'opening_block_missed', 'reorged_before_inclusion'],
     'phrase': 'Any one of the four that differs is a mislabel under :383'},
    {'name': 'ITEM4_E9D_BORN', 'item': 'ITEM4', 'line': 1068,
     'value': {'verdict': 'Done:Born@<H0>+opening', 'outcome': 'Born@<H0>+opening'},
     'phrase': "The E9-d row's expected label: `Done:Born` (G, and G + 1 at depth 2)"},
    {'name': 'ITEM4_E9D_OTHERS', 'item': 'ITEM4', 'line': 1068,
     'value': {'verdict': 'Done:ProjectBornByOther@<H0>', 'outcome': 'ProjectBornByOther@<H0>'},
     'phrase': 'the other rungs are `Done:ProjectBornByOther@<H0>` at G and G + 1'},
    {'name': 'ITEM4_E9D_LOCKED', 'item': 'ITEM4', 'line': 1068,
     'value': {'verdict': 'Refuse:Locked(Reorg67)', 'outcome': 'Stale@<H0>><next birth>', 'turns': ['REORGED',
                                                                                                  'RELEASE']},
     'phrase': 'The two locked turns pair the verdict `Refuse:Locked(Reorg67)` with the outcome '
               '`Stale@<H0>><next birth>`, and the judge compares both'},
    {'name': 'ITEM4_E9D_STALE', 'item': 'ITEM4', 'line': 1068,
     'value': {'released': 'Refuse:GateAdvanced', 'unreleased': 'Wait:OfflineSignaturePending'},
     'phrase': 'an unreleased rung is `Wait:OfflineSignaturePending` at the STALE turn'},
    {'name': 'ITEM4_E9D_FLAGS', 'item': 'ITEM4', 'line': 1068,
     'value': {'before_tip': {'opening_block_missed': False, 'reorged_before_inclusion': False},
               'from_tip': {'opening_block_missed': True, 'reorged_before_inclusion': False}},
     'phrase': '`opening_block_missed` true from the replacement tip on, `reorged_before_inclusion` false throughout'},
    {'name': 'ITEM4_LABEL_LINE', 'item': 'ITEM4', 'line': 1068,
     'value': {'step': 'RELEASE_REORG67_TEST_ONLY', 'released': 'reason:Reorg67;step6:Some(NotPerformed)',
               'after': 'RELEASE', 'none': '-'},
     'phrase': 'every step is kept in the label line'},
    {'name': 'ITEM4_RELEASE_STEP', 'item': 'ITEM4', 'value': 'RELEASE_REORG67_TEST_ONLY', 'line': 1068,
     'phrase': 'the TEST_ONLY `RELEASE_REORG67_TEST_ONLY` phase, step 6 not performed'},
    {'name': 'ITEM4_MISS', 'item': 'ITEM4', 'value': 'CONTINUE_WITHIN_LIMITS', 'line': 1068,
     'phrase': 'any other value is refused (`ITEM4_L0_MISS`)'},
    {'name': 'ITEM4_RUNS', 'item': 'ITEM4', 'value': 50, 'line': 524,
     'phrase': 'item 4 (each of four sub-scenarios) and the pool-concentration run | 50 runs each'},
    {'name': 'ITEM4_EXCLUSION_UNIT', 'item': 'ITEM4', 'value': 'RUN', 'line': 1084, 'phrase': "item 4's is the run"},
    {'name': 'ITEM4_SUBSCENARIO_LIMIT', 'item': 'ITEM4', 'value': {'num': 5, 'den': 50}, 'line': 1084,
     'phrase': "more than 5 of a sub-scenario's 50 runs missing or EXCLUDED makes that sub-scenario not run (:383), "
               'and so does a sub-scenario with no judged run'},
    {'name': 'ITEM4_LABEL_CHECK_JUDGED', 'item': 'ITEM4', 'value': ['ITEM4_LABEL_MISMATCH', 'L0_RELEASE_NOT_REORG67'],
     'line': 1084,
     'phrase': 'A run that the driver ends on its own label check (`ITEM4_LABEL_MISMATCH`, or '
               '`L0_RELEASE_NOT_REORG67`'},
    {'name': 'ITEM4_LABEL_JUDGED_RUN', 'item': 'ITEM4', 'value': 'JUDGED_MATCH_OR_NOT', 'line': 1084,
     'phrase': 'A run whose planned turns are all judged, with no plan mismatch, is a judged run whether its labels '
               'match or not'},
    {'name': 'ITEM4_PARTIAL_RUN', 'item': 'ITEM4', 'value': 'NOGO_EVIDENCE_ELSE_EXCLUDED', 'line': 1084,
     'phrase': 'A run that stopped partway is NO-GO evidence when a turn it already judged mismatches, and EXCLUDED '
               'otherwise'},
    {'name': 'ITEM4_ORDER', 'item': 'ITEM4', 'value': 'NO_GO_FIRST', 'line': 1084,
     'phrase': 'Inside a sub-scenario a NO-GO comes before NOT_ESTABLISHED'},
    {'name': 'ITEM4_SELF_FEE', 'item': 'ITEM4', 'value': 600, 'line': 1065,
     'phrase': "above the self REGISTER's fee (DRAFT 600 sat"},
    {'name': 'ITEM4_SELF_BELOW_HONEST', 'item': 'ITEM4', 'value': 'STRICTLY_BELOW_EVERY_HONEST_RUNG_0', 'line': 1065,
     'phrase': 'below every honest rung 0 in G'},
    # 2026-11-12 (A, FD-CT-133; section 30): with the new L0 p_0 the floor is b >= 1058 (b 1057's rung 0 is 600 sat).
    {'name': 'ITEM4_SELF_FEE_FLOOR_B', 'item': 'ITEM4', 'value': 1058, 'line': 1065,
     'phrase': 'DRAFT 600 sat, so `b` ≥ 1127', 'amends': {'value': 1127, 'by': 'FD-CT-133'}},
    {'name': 'ITEM4_ASYM_FACTOR', 'item': 'ITEM4', 'value': {'factor': 10, 'source': 'DRAFT'}, 'line': 541,
     'phrase': 'the asymmetric bidder pays 10× the median honest feerate'},
    {'name': 'ITEM4_ASYM_SEATS_MEDIAN', 'item': 'ITEM4', 'line': 1078,
     'value': {'asymmetric': 0, 'l0': 1, 'drawn': [2, 3, 4], 'median': 'NEAREST_RANK_P50'},
     'phrase': 'the asymmetric bidder is public seat 0, L0 is seat 1, and seats 2 to 4 draw'},
    {'name': 'ITEM4_ASYM_DRAW', 'item': 'ITEM4', 'line': 1076,
     'value': {'e': 'ITEM4_FEE_ASYMMETRY', 'labels': ['BID_FEE_2', 'BID_FEE_3', 'BID_FEE_4'], 'n': '3b + 1'},
     'phrase': '| `ITEM4_FEE_ASYMMETRY` | `BID_FEE_2` … `BID_FEE_4` (the seat number) | `n = 3b + 1`'},
    {'name': 'ITEM4_ASYM_FEE_CAP', 'item': 'ITEM4', 'value': 90000, 'line': 1079,
     'phrase': 'an asymmetric fee above 90,000 sat is refused before any node'},
    {'name': 'ITEM4_COMPETITOR_FEE', 'item': 'ITEM4', 'value': {'times': 2, 'plus': 1}, 'line': 1079,
     'phrase': "the censorship and reorg competitor pays 2 × the stand-in's rung-0 fee + 1"},
    {'name': 'ITEM4_CENSOR_WINDOW', 'item': 'ITEM4', 'value': {'first': 0, 'last': 143, 'lifted': 144}, 'line': 1079,
     'phrase': 'the censorship window is G … G + 143 (144 blocks)'},
    {'name': 'ITEM4_WINNER_READDED', 'item': 'ITEM4', 'value': 'TXID_OR_FUNDING_OUTPOINT', 'line': 1079,
     'phrase': "none of the d + 1 replacement blocks may hold a txid of the winner's set or any spend of its funding "
               'outpoint'},
    {'name': 'ITEM4_REORG_DEPTH', 'item': 'ITEM4', 'value': {'even': 1, 'odd': 2}, 'line': 1070,
     'phrase': 'depth 1 for even `r`, depth 2 for odd `r`'},
    {'name': 'ITEM4_REORG_REPLACEMENT', 'item': 'ITEM4', 'value': 'D_PLUS_1_BLOCKS', 'line': 1070,
     'phrase': 'A depth-d run replaces d blocks from G (depth 2 replaces G and G + 1) with a chain of d + 1 blocks'},
    {'name': 'ITEM4_NOT_RUN_LIST', 'item': 'ITEM4', 'line': 1067,
     'value': {'ITEM4_CENSORSHIP': 'DONE_BORN_LATE_NOT_AT_OPENING',
               'ITEM4_SELF_DEALING': 'ITEM4_SELF_ZERO_FEE_REGISTER', 'STANDIN': 'L0_PROJECT_SEAT',
               'L0': 'E7_REORG_BEFORE_INCLUSION'},
     'phrase': 'and the L0 project seat in the stand-in runs (in the L0 runs, E7 takes that place)'},
    {'name': 'ITEM4_E7_NOT_RUN', 'item': 'ITEM4', 'value': 'E7_REORG_BEFORE_INCLUSION', 'line': 1066,
     'phrase': 'E7 is in no item-4 miner policy, so item 4 lists it as not run'},
    {'name': 'ITEM4_RELEASE_CLASS_T_RUN', 'item': 'ITEM4', 'value': 'the release is a Class T test step', 'line': 1067,
     'phrase': 'the judge report says "the release is a Class T test step"'},
    {'name': 'ITEM4_RELEASE_CLASS_T_ROW', 'item': 'ITEM4', 'value': 'release: Class T test step', 'line': 1069,
     'phrase': 'the judge report labels the row "release: Class T test step"'},
    {'name': 'ITEM4_RELEASE_MARK', 'item': 'ITEM4', 'value': 'RELEASE_REORG67_TEST_ONLY', 'line': 1069,
     'phrase': 'uses the TEST_ONLY release, with its mark in the raw log'},
    {'name': 'ITEM4_L0_SEAT', 'item': 'ITEM4', 'line': 1219,
     'value': {'ITEM4_SELF_DEALING': 1, 'ITEM4_FEE_ASYMMETRY': 1, 'ITEM4_CENSORSHIP': 0, 'ITEM4_REORG': 0},
     'phrase': 'S1 in self-dealing and fee asymmetry but S0 in censorship and reorg'},
    {'name': 'ITEM4_WINNER_BY_OUTPOINT', 'item': 'ITEM4', 'value': 'TXID_AND_FUNDING_OUTPOINT', 'line': 1220,
     'phrase': 'in item 4, also by the funding outpoint'},
    {'name': 'ITEM4_H0', 'item': 'ITEM4', 'value': 1000, 'line': 1054,
     'phrase': 'Every item-2 run and every item-4 run uses H0 = 1000'},
    {'name': 'ITEM4_ROW_505', 'item': 'ITEM4', 'value': 'AS_ITEM4', 'line': 505,
     'phrase': 'miner self-dealing scenarios (SSoT:2431) | item 4 | as item 4'},
    {'name': 'ITEM4_ROW_506', 'item': 'ITEM4', 'value': 'AS_ITEM4', 'line': 506,
     'phrase': 'count and outcome of winners replaced by 1-2 block reorgs'},
    {'name': 'ITEM4_MINED_LOSING_REPORTED', 'item': 'ITEM4', 'value': 'REPORTED_NOT_JUDGED', 'line': 536,
     'phrase': "Item 4's four sub-scenarios are all adversarial"},
    {'name': 'ITEM4_LEDGER_C', 'item': 'ITEM4', 'value': 'REPLACED_BRANCH', 'line': 1061,
     'phrase': 'C, disconnected history and recovery (reorg-replaced winners)'},
    # J5b (A's Q1 on #719, 2026-11-10): 045b :1279 (frozen) and its dated line, which names the list (the CT-P5-001
    # inventory section 2) and reads "a J4 item" as item 4's judge stage. The value is the inventory's TR-1 .. TR-6 per
    # item-4 sub-scenario (its scope rule: item 4 per sub-scenario; TR-7 .. TR-9 are item 3's, ITEM3W's and NC-IC08's,
    # J6; E7 not required).
    {'name': 'ITEM4_MIN_TRANSITIONS', 'item': 'ITEM4', 'line': 1279,
     'value': {'ITEM4_SELF_DEALING': ['TR-3', 'TR-4'], 'ITEM4_FEE_ASYMMETRY': ['TR-3'],
               'ITEM4_CENSORSHIP': ['TR-2', 'TR-3'], 'ITEM4_REORG': ['TR-1', 'TR-2', 'TR-5', 'TR-6']},
     'phrase': 'the list is section 2 of `plans/CT-P5-001_INVENTORY_EN.md` (TR-1 to TR-9'},
    {'name': 'ITEM4_MIN_REACH', 'item': 'ITEM4', 'value': 1, 'line': 1279,
     'phrase': 'has a minimum of one reach, checked by the judge from the raw logs'},
    {'name': 'ITEM4_TRANSITION_UNREACHED', 'item': 'ITEM4', 'value': 'NOT_ESTABLISHED', 'line': 1279,
     'phrase': 'A transition that is not reached makes that experiment NOT_ESTABLISHED, never a pass'},
    # J-1090 (ARDR_JUDGE_V1 section 29; A's decisions of 2026-11-11): 045b :1090 (frozen) asks of the judge record the
    # fields `expected` and `observed` and the value INCONCLUSIVE. The value is the one mapping from a finished outcome
    # to `verdict.result`; `verdict_block` reads it and nothing else decides that value.
    {'name': 'VERDICT_MAPPING', 'item': 'ALL', 'line': 1090,
     'value': {'GO': 'PASS', 'NO_GO': 'FAIL', 'NOT_ESTABLISHED': 'INCONCLUSIVE',
               'NOT_A_VERDICT_PER_RUN': 'NOT_A_VERDICT_PER_RUN'},
     'phrase': 'carries `expected` and `observed` fields'},
    # B4-21a (2026-11-25, A; unit note 2026-11-25_b421a-item3w-judge-core.md): the constants of 045b section 14.18
    # (FD-CT-104, frozen by #664, main 317ecbf5), R18-6 tooling 4. Item W_ROWS: the W and review rows' own rules,
    # which item 3's W list (J6) reads too; item ITEM3W: the ninth experiment (:1514-1585), each plant's row of the
    # :1535 table included, whose value is the judge's copy of that row (045b states no fee for T11a and T11b, never
    # opening-block: CHEAP is the W3-3b-3b plan's 600). Only the ITEM3W section's pure functions read them (no command
    # does until B4-21b), so no item-1, item-2 or item-4 outcome changes; every record's `thresholds` lists them.
    {'name': 'W_COST_CAP_SAT', 'item': 'W_ROWS', 'value': 30000, 'line': 1345,
     'phrase': '**Cap 30,000 sat** is `max_fee_per_candidate_sat` (FD-CT-102, :1175). It would be fixed here as its '
               'own constant `W_COST_CAP_SAT`'},
    {'name': 'W_WINDOW_GATES', 'item': 'W_ROWS', 'value': 15, 'line': 1378,
     'phrase': 'W-C fires at the first gate t of a run where gates t−14 … t are all in the run and each has c*_g = '
               '30,000. The sum over that 15-gate window is then 450,000 sat.'},
    {'name': 'W_COST_SUM_SAT', 'item': 'W_ROWS', 'value': 450000, 'line': 1387,
     'phrase': 'W-P fires when E ≥ 450,000 and E > A.'},
    {'name': 'W_P_EDGE', 'item': 'W_ROWS', 'value': 'EDGE_TRIGGERED', 'line': 1388,
     'phrase': 'It is edge-triggered: it reports again only after the condition has been false. Key: '
               '(`LINKAGE_FREE`, `W_P`, height).'},
    {'name': 'V_REF_VB', 'item': 'W_ROWS', 'value': 213, 'line': 1338,
     'phrase': 'V_REF = 213 vB is a constant of this section.'},
    {'name': 'STRONG_LINK_MIN_SAT', 'item': 'W_ROWS', 'value': 30000, 'line': 1351,
     'phrase': "(S) gate h's winning REGISTER directly spends an output of gate g's winning REGISTER R_g (g < h) "
               'worth at least 30,000 sat.'},
    {'name': 'TENURE_OFFSET_BLOCKS', 'item': 'W_ROWS', 'value': 4033, 'line': 1358,
     'phrase': 'Birth i fails tenure when its Heart is ENDED (any cause) at a height ≤ B_i + 4,033.'},
    {'name': 'TENURE_WINDOW_BIRTHS', 'item': 'W_ROWS', 'value': 30, 'line': 1365,
     'phrase': 'The **tenure window** is the non-project births i−29 … i (fewer if fewer exist).'},
    {'name': 'TENURE_FAIL_MIN', 'item': 'W_ROWS', 'value': 15, 'line': 1415,
     'phrase': 'D-T fires when its tenure failures first reach 15. It is edge-triggered.'},
    {'name': 'POP_CHECKPOINT_BLOCKS', 'item': 'W_ROWS', 'value': 2016, 'line': 1418,
     'phrase': 'Checkpoints are at H_k = H0 + 2,016k.'},
    {'name': 'POP_BAND', 'item': 'W_ROWS', 'value': [4033, 10080], 'line': 1419,
     'phrase': 'The cohort is the non-project births with H_k − 10,080 ≤ B ≤ H_k − 4,033, i.e. ages 4,033 to 10,080.'},
    {'name': 'POP_MIN_COHORT', 'item': 'W_ROWS', 'value': 15, 'line': 1420,
     'phrase': 'It is evaluated when the cohort has at least 15 births. A checkpoint whose cohort has fewer than 15 '
               'births is not evaluated and counts as false for the edge trigger.'},
    {'name': 'POP_FLOOR', 'item': 'W_ROWS', 'value': {'num': 1, 'den': 2}, 'line': 1421,
     'phrase': 'It fires when CURRENT × 2 < cohort size. It is edge-triggered over checkpoints.'},
    {'name': 'W_CONFIRMATIONS', 'item': 'W_ROWS', 'value': 6, 'line': 1369,
     'phrase': 'Every row reads the chain at 6 confirmations.'},
    {'name': 'EFFECTIVE_OFFSET', 'item': 'W_ROWS', 'value': 5, 'line': 1369,
     'phrase': 'A report with trigger height h takes effect at height h + 5, or at a later W-DATA deadline'},
    {'name': 'DATA_RESOLUTION_BLOCKS', 'item': 'W_ROWS', 'value': 2016, 'line': 1398,
     'phrase': "Its deadline is 2,016 blocks after the gate's birth height B_g"},
    {'name': 'HISTORY_DEADLINE_BLOCKS', 'item': 'W_ROWS', 'value': 2016, 'line': 1398,
     'phrase': "or, for a birth's ending status, 2,016 blocks after the height at which that status would be "
               'established'},
    {'name': 'W_DATA_LAG_BLOCKS', 'item': 'W_ROWS', 'value': 2016, 'line': 1395,
     'phrase': 'If H_e stays more than 2,016 blocks below the 6-confirmation tip, the namespace withdraws (`W_DATA`).'},
    {'name': 'W_DATA_ADVERSE', 'item': 'W_ROWS', 'line': 1399,
     'value': {'cost': 'W_COST_CAP_SAT', 'control': 'UNKNOWN_IN_EVERY_ADJACENT_RUN', 'ending': 'TENURE_FAILED'},
     'phrase': 'an unresolved winner, package fee, block floor or opening flag gives c*_g = 30,000; an unresolved '
               'winner or link gives unknown control inside every adjacent run (R3); an unresolved ending status '
               'gives tenure failed'},
    {'name': 'HISTORY_ADVERSE', 'item': 'W_ROWS', 'value': {'D_T': 'FAILED', 'D_P': 'NOT_CURRENT'}, 'line': 1444,
     'phrase': 'A D-T birth or D-P cohort member with unresolved history is PENDING. At its W-DATA deadline it '
               'counts as failed (D-T) or as not CURRENT (D-P).'},
    {'name': 'HEART_TIMEOUT_BLOCKS', 'item': 'W_ROWS', 'value': 2017, 'line': 1361,
     'phrase': 'One BEAT at B + 2,016 ends the Heart at B + 4,033 (Core :520-521, :734-735). A same-block BEAT '
               'followed by TIMEOUT ends it at B + 2,017.'},
    {'name': 'OPEN_SPACING_BLOCKS', 'item': 'W_ROWS', 'value': 144, 'line': 1320,
     'phrase': 'Otherwise it is B_prev + 144, with B_prev the latest accepted birth before B_g, project or not.'},
    {'name': 'REPEAT_GATES', 'item': 'W_ROWS', 'value': 15, 'line': 1427,
     'phrase': 'A D-C or D-Z run that continues gets a new review at every further 15 gates (lengths 30, 45, …).'},
    {'name': 'D_T_REPEAT_STEP', 'item': 'W_ROWS', 'value': 30, 'line': 1428,
     'phrase': "it gets a new review each time the window's top index i reaches i_0 + 30, i_0 + 60, …, where i_0 is "
               'the top index at the D-T report (`D_T_REPEAT`)'},
    {'name': 'D_P_REPEAT_STEP', 'item': 'W_ROWS', 'value': 3, 'line': 1429,
     'phrase': 'it gets a new review at every third checkpoint after the first (k_0 + 3, k_0 + 6, …)'},
    {'name': 'ITEM3W_EFFECTIVE_JUDGED', 'item': 'ITEM3W', 'value': True, 'line': 1370,
     'phrase': 'In Class T, effective heights are judged in ITEM3W only.'},
    {'name': 'ITEM3W_COUNTS_JUDGED', 'item': 'ITEM3W', 'line': 1425,
     'value': {'D_T': ['count', 'top_index'], 'W_P': ['e_sat', 'a_sat'], 'D_P': ['count', 'current']},
     'phrase': 'Each linkage-free report also carries its counts: D-T the failures and the top index i; W-P the '
               'values E and A; D-P the cohort size and the CURRENT count. The judge compares them.'},
    {'name': 'ITEM3W_NOGO', 'item': 'ITEM3W', 'line': 1515,
     'value': ['MISSING', 'EXTRA', 'WRONG_TRIGGER', 'WRONG_EFFECTIVE', 'WRONG_COUNTS'],
     'phrase': "NO-GO when the tool's W/D report list differs from the plan's expected list: a report missing, "
               'added, at the wrong trigger, with the wrong effective height or with the wrong counts.'},
    {'name': 'ITEM3W_PAIRING', 'item': 'ITEM3W', 'value': 'wrong_trigger', 'line': 1515,
     'phrase': 'The judge pairs a missing and an extra report as `wrong_trigger`, like `wrong_gate`.'},
    {'name': 'ITEM3W_PLAN_MISMATCH', 'item': 'ITEM3W', 'line': 1516,
     'value': {'result': 'NOT_ESTABLISHED', 'new_fields': ['package_fee', 'birth_height', 'beat_height', 'filler']},
     'phrase': 'A missing log or a `JUDGE_PLAN_MISMATCH:<field>` (new fields `package_fee`, `birth_height`, '
               "`beat_height`, `filler`) makes that run's W/D rows NOT_ESTABLISHED."},
    {'name': 'ITEM3W_ROW_503', 'item': 'ITEM3W', 'value': ['D_C4', 'D_C15', 'D_C_REPEAT', 'W_C'], 'line': 1517,
     'phrase': 'A wrong D-C or W-C report is a NO-GO of the §4.5 repeat-winner row (:503).'},
    {'name': 'ITEM3W_ROW_382', 'item': 'ITEM3W', 'line': 1517,
     'value': ['D_Z15', 'D_Z_REPEAT', 'D_T', 'D_T_REPEAT', 'D_P', 'D_P_REPEAT', 'W_P', 'W_PENDING_DATA', 'W_DATA'],
     'phrase': 'A wrong D-Z15, D-T, D-P, W-P, `W_PENDING_DATA` or `W_DATA` report is a NO-GO of item 3 (:382).'},
    {'name': 'ITEM3W_NOT_ESTABLISHED_ROWS', 'item': 'ITEM3W', 'value': ['382', '503'], 'line': 1518,
     'phrase': 'ITEM3W NOT_ESTABLISHED makes both that row and item 3 NOT_ESTABLISHED.'},
    {'name': 'ITEM3W_ORDER', 'item': 'ITEM3W', 'value': 'NO_GO_FIRST', 'line': 1519,
     'phrase': "Order as item 1 (:1086): a NO-GO found on judged runs comes first, since ITEM3W's NO-GOs are "
               'deterministic.'},
    {'name': 'ITEM3W_NUMS', 'item': 'ITEM3W', 'value': 'NUMS_POINT_OF_THE_LABEL', 'line': 1520,
     'phrase': 'There are no random draws and no private keys. Every Anchor comes from a label '
               '`ITEM3W_<plant>_<role>_<n>` by the NUMS rule'},
    {'name': 'ITEM3W_FORMS', 'item': 'ITEM3W', 'line': 1583,
     'value': {'U': 'OUTPUT_KEY_NO_SCRIPT_PATH', 'L': 'INTERNAL_KEY_ONE_OP_TRUE_LEAF'},
     'phrase': 'An uncontrollable Anchor uses that point as the output key with no script path; every other Anchor '
               'uses it as the internal key with one `OP_TRUE` leaf.'},
    {'name': 'ITEM3W_NUMS_RECOMPUTED', 'item': 'ITEM3W', 'value': 'RECOMPUTED', 'line': 1583,
     'phrase': "B states the hash-to-curve rule and the leaf encoding in ARDR_RUN_V1 before ITEM3W's registration, "
               'and the judge recomputes both.'},
    {'name': 'ITEM3W_FROM_PLAN', 'item': 'ITEM3W', 'value': 'PLAN_NEVER_CHAIN', 'line': 1521,
     'phrase': 'The judge computes every expected list from the plan with the rules above, never from the chain.'},
    {'name': 'ITEM3W_H0_HEND', 'item': 'ITEM3W', 'value': {'H0': 1000, 'H_end': 12000}, 'line': 1523,
     'phrase': 'H0 = 1000 and H_end = 12,000.'},
    {'name': 'ITEM3W_LISTED', 'item': 'ITEM3W', 'value': 'EFFECTIVE_AT_MOST_H_END', 'line': 1523,
     'phrase': 'Reports are listed when their effective height is ≤ H_end.'},
    {'name': 'ITEM3W_PROJECT_GATE', 'item': 'ITEM3W', 'line': 1524,
     'value': {'gate': 0, 'birth': 'H0', 'opening_block': True},
     'phrase': 'Gate 0 is the project: H_P = H0, born in the opening block.'},
    {'name': 'ITEM3W_GATE_SPACING', 'item': 'ITEM3W', 'value': 144, 'line': 1525,
     'phrase': 'Gate j ≥ 1 is born at B_j = H0 + 144j in its opening block (O_1 = H_P + 144), unless stated.'},
    {'name': 'ITEM3W_FLOOR_ZERO', 'item': 'ITEM3W', 'value': 0, 'line': 1526,
     'phrase': 'unless stated (T14 filler). Funding for later gates and every fee input of a BEAT confirm in a block '
               'that is not a B_j. So m_g = 0.'},
    {'name': 'ITEM3W_CHEAP_FEE', 'item': 'ITEM3W', 'value': 600, 'line': 1527,
     'phrase': 'Cheap fee: 600 sat (the product floor).'},
    {'name': 'ITEM3W_CAP_FEE', 'item': 'ITEM3W', 'line': 1528,
     'value': 'max(30000 + ceil(m V), ceil((30000/213 + m) V))',
     'phrase': "Cap fee: F_cap(V, m) = max(30,000 + ⌈m × V⌉, ⌈(30,000/213 + m) × V⌉), with V the package's measured "
               'vsize.'},
    {'name': 'ITEM3W_LINKED', 'item': 'ITEM3W', 'line': 1529,
     'value': {'owner': 'X', 'link_min_sat': 100000, 'ids': ['X', 'L1', 'S1']},
     'phrase': "Each later winner's REGISTER directly spends an output (≥ 100,000 sat) of the previous gate's "
               'winning REGISTER. So item 1 ANCESTRY links (ARDR_CLUSTER_V1 §5: the ancestor set includes the winner '
               'itself) and STRONG_LINK (S) both join every gate. Cluster ids: `X`, `L1`, `S1`.'},
    {'name': 'ITEM3W_UNLINKED', 'item': 'ITEM3W', 'value': {'owner': 'X', 'links': None}, 'line': 1530,
     'phrase': '"Unlinked": owner X in the ownership truth, but a fresh key and fresh funding from the excluded '
               'source per Heart, so there are no links.'},
    {'name': 'ITEM3W_MAINTAINED', 'item': 'ITEM3W', 'value': 1008, 'line': 1532,
     'phrase': '"Maintained": a BEAT every 1,008 blocks after birth, to H_end.'},
    {'name': 'ITEM3W_PLANTS', 'item': 'ITEM3W', 'line': 1535,
     'value': ['T1', 'T2', 'T3', 'T4', 'T5', 'T6A', 'T6B', 'T7', 'T8', 'T9A', 'T9B', 'T10', 'T11A', 'T11B', 'T12',
               'T13A', 'T13B', 'T14A', 'T14B'],
     'phrase': '| Plant | Plan | Expected reports (nothing else) |'},
    {'name': 'ITEM3W_PLANT_T1', 'item': 'ITEM3W', 'line': 1537,
     'value': {'gates': 15, 'funding': 'LINKED', 'fee': 'CHEAP', 'beats': 'MAINTAINED'},
     'phrase': '| T1 cheap linked (ECON-01 path A) | gates 1–15, linked, cheap, maintained | both D_C4@4 (1,576), '
               'both D_C15@15 (3,160) |'},
    {'name': 'ITEM3W_PLANT_T2', 'item': 'ITEM3W', 'line': 1538,
     'value': {'gates': 15, 'funding': 'UNLINKED', 'fee': 'CHEAP', 'beats': [[1, 15, []]], 'form': 'U'},
     'phrase': '| T2 cheap path B (ECON-01) | gates 1–15, unlinked, uncontrollable, cheap | ownership D_C4@4, '
               'D_C15@15; D_Z15@gate 15 (5,177); D_T@5,177 (15 failures, i = 15); D_P@9,064 (k = 4, cohort 15, '
               'CURRENT 0) |'},
    {'name': 'ITEM3W_PLANT_T3', 'item': 'ITEM3W', 'line': 1539,
     'value': {'gates': 15, 'funding': 'LINKED', 'fee': 'CAP', 'cap_m': 0, 'beats': 'MAINTAINED'},
     'phrase': '| T3 paid linked | T1 at F_cap(V, 0) | as T1, plus W_C@15 (3,160; window 1–15) under ownership X and '
               'STRONG_LINK S1 |'},
    {'name': 'ITEM3W_PLANT_T4', 'item': 'ITEM3W', 'line': 1540,
     'value': {'gates': 15, 'funding': 'UNLINKED', 'fee': 'CAP', 'cap_m': 0, 'beats': [[1, 15, [0]]]},
     'phrase': '| T4 paid careful capturer (CORE-01) | gates 1–15, unlinked, F_cap, one same-block BEAT each, then '
               'no BEAT (TIMEOUT at B + 2,017) | ownership D_C4@4, D_C15@15, W_C@15; D_T@5,177; W_P@5,177 (E '
               '450,000, A 0); D_P@9,064 (cohort 15, CURRENT 0) |'},
    {'name': 'ITEM3W_PLANT_T5', 'item': 'ITEM3W', 'line': 1541,
     'value': {'gates': 15, 'funding': 'UNLINKED', 'fee': 'CHEAP', 'beats': [[1, 15, [0]]]},
     'phrase': '| T5 cheap careful capturer | T4 at 600 sat | ownership D_C4@4, D_C15@15; D_T@5,177; D_P@9,064 '
               '(demonstrates residual 2) |'},
    {'name': 'ITEM3W_PLANT_T6A', 'item': 'ITEM3W', 'line': 1542,
     'value': {'gates': 15, 'funding': 'LINKED', 'fee': 'CHEAP', 'beats': 'MAINTAINED', 'decoys': True},
     'phrase': '| T6a / T6b decoys | T1 / T3, plus in each B_j one mined losing REGISTER from an unlinked wallet at '
               '600 sat placed after the winner, plus one unmined decoy'},
    {'name': 'ITEM3W_PLANT_T6B', 'item': 'ITEM3W', 'line': 1542,
     'value': {'gates': 15, 'funding': 'LINKED', 'fee': 'CAP', 'cap_m': 0, 'beats': 'MAINTAINED', 'decoys': True},
     'phrase': '| identical to T1 / T3 |'},
    {'name': 'ITEM3W_PLANT_T7', 'item': 'ITEM3W', 'line': 1543,
     'value': {'gates': 15, 'spacing': 145, 'funding': 'LINKED', 'fee': 'CAP', 'cap_m': 0, 'beats': 'MAINTAINED'},
     'phrase': '| T7 late birth | T3 with each winner held back one block (B_j = H0 + 145j) | both D_C4@4 (1,580), '
               'both D_C15@15 (3,175); no W_C |'},
    {'name': 'ITEM3W_PLANT_T8', 'item': 'ITEM3W', 'line': 1544,
     'value': {'gates': 23, 'funding': 'LINKED', 'fee': 'CAP', 'cap_m': 0, 'below_cap': [8], 'beats': 'MAINTAINED'},
     'phrase': '| T8 window reset | gates 1–23, linked, maintained, F_cap except gate 8 at F_cap − 1 | both D_C4@4, '
               'both D_C15@15; W_C@23 (4,312; window 9–23) under ownership and STRONG_LINK |'},
    {'name': 'ITEM3W_PLANT_T9A', 'item': 'ITEM3W', 'line': 1545,
     'value': {'gates': 15, 'funding': 'LINKED', 'fee': 'CPFP', 'child_block': 0, 'beats': 'MAINTAINED'},
     'phrase': '| T9a in-block CPFP | T3, but each REGISTER pays 600 sat and has two change outputs; a child of '
               'change output 1 in B_j pays F_cap(V_R + V_child, 0) − 600; change output 2 (≥ 100,000 sat) funds the '
               'next gate | as T3 |'},
    {'name': 'ITEM3W_PLANT_T9B', 'item': 'ITEM3W', 'line': 1546,
     'value': {'gates': 15, 'funding': 'LINKED', 'fee': 'CPFP', 'child_block': 1, 'beats': 'MAINTAINED'},
     'phrase': '| T9b | T9a with the child mined in B_j + 1 | as T1 (no W_C) |'},
    {'name': 'ITEM3W_PLANT_T10', 'item': 'ITEM3W', 'line': 1547,
     'value': {'gates': 16, 'funding': 'UNLINKED', 'fee': 'CHEAP',
               'beats': [[1, 14, [2016]], [15, 15, [1, 2017]], [16, 16, [2016, 4032]]]},
     'phrase': '| T10 tenure boundaries | gates 1–16, unlinked, cheap; births 1–14 BEAT once at B + 2,016 (end B + '
               '4,033: fail); birth 15 at B + 1 and B + 2,017 (end B + 4,034: success); birth 16 at B + 2,016 and B '
               '+ 4,032 (success) | ownership D_C4@4, D_C15@15; D_P@9,064 (cohort 16, CURRENT 1); per-birth flags as '
               'planned; no D_T (14 < 15), no D_Z15, no W |'},
    {'name': 'ITEM3W_PLANT_T11A', 'item': 'ITEM3W', 'line': 1548,
     'value': {'gates': 20, 'spacing': 432, 'funding': 'DISTINCT', 'fee': 'CHEAP', 'beats': 'MAINTAINED'},
     'phrase': '| T11a honest thin, long-lived | 20 births by 20 distinct owners at B_j = H0 + 432j (not '
               'opening-block), maintained | none |'},
    {'name': 'ITEM3W_PLANT_T11B', 'item': 'ITEM3W', 'line': 1549,
     'value': {'gates': 30, 'spacing': 288, 'funding': 'DISTINCT', 'fee': 'CHEAP',
               'beats': [[1, 30, [1000, 2000, 3000]]]},
     'phrase': '| T11b honest thin, short-lived | 30 births by 30 distinct owners at B_j = H0 + 288j, BEATs at B + '
               '1,000, B + 2,000 and B + 3,000 while ≤ H_end, then none (end B + 5,017) | D_P@11,080 (k = 5, cohort '
               '20, CURRENT 3); no D_T, no W |'},
    {'name': 'ITEM3W_PLANT_T12', 'item': 'ITEM3W', 'line': 1550,
     'value': {'gates': 15, 'funding': 'LINKED', 'fee': 'BATCH', 'batch': {'fee': 30000, 'min_vsize': 2130},
               'beats': 'MAINTAINED'},
     'phrase': '| T12 batch REGISTER (critique A2) | T1, but each REGISTER is a batch of V ≥ 2,130 vB paying 30,000 '
               'sat absolute (c* ≤ 3,000) | as T1 (no W_C) |'},
    {'name': 'ITEM3W_PLANT_T13A', 'item': 'ITEM3W', 'line': 1551,
     'value': {'gates': 15, 'funding': 'GIFT', 'gift': 29999, 'fee': 'CAP', 'cap_m': 0, 'beats': 'MAINTAINED'},
     'phrase': '| T13a gift link below the bound (critique A3) | gates 1–15 by 15 distinct owners, F_cap, '
               "maintained; winner j's REGISTER pays a 29,999-sat output to owner j+1, whose REGISTER spends it "
               'along with its own fresh funding | link-based L1 D_C4@4, D_C15@15 only |'},
    {'name': 'ITEM3W_PLANT_T13B', 'item': 'ITEM3W', 'line': 1552,
     'value': {'gates': 15, 'funding': 'GIFT', 'gift': 30000, 'fee': 'CAP', 'cap_m': 0, 'beats': 'MAINTAINED'},
     'phrase': '| T13b gift at the bound | T13a with 30,000-sat gifts | as T13a, plus STRONG_LINK S1 W_C@15 |'},
    {'name': 'ITEM3W_PLANT_T14A', 'item': 'ITEM3W', 'line': 1553,
     'value': {'gates': 15, 'funding': 'LINKED', 'fee': 'CAP', 'cap_m': 0, 'filler': {'feerate': 10, 'min_vsize': 1000},
               'beats': 'MAINTAINED'},
     'phrase': '| T14a block floor | T3, plus in each B_j one filler transaction from the excluded source (not '
               'REGISTER-shaped) of about 1,000 vB whose fee is exactly 10 × its measured vsize (m_g = 10); '
               'REGISTERs at F_cap(V, 0) | as T1 (no W_C) |'},
    {'name': 'ITEM3W_PLANT_T14B', 'item': 'ITEM3W', 'line': 1554,
     'value': {'gates': 15, 'funding': 'LINKED', 'fee': 'CAP', 'cap_m': 10,
               'filler': {'feerate': 10, 'min_vsize': 1000}, 'beats': 'MAINTAINED'},
     'phrase': '| T14b | T14a with REGISTERs at F_cap(V, 10) | as T3 |'},
    {'name': 'ITEM3W_RUNS', 'item': 'ITEM3W', 'value': 19, 'line': 1581,
     'phrase': "ITEM3W's count is 19 runs, registered in this section."},
    {'name': 'ITEM3W_ZERO_EXCLUSIONS', 'item': 'ITEM3W', 'value': 0, 'line': 1514,
     'phrase': 'Each plant runs once, as a required inventory case with 0 exclusions'},
    {'name': 'ITEM3W_NO_TEN_PERCENT', 'item': 'ITEM3W', 'value': 'NOT_APPLIED', 'line': 1578,
     'phrase': 'ITEM3W allows 0 exclusions, so the 10% rule does not apply to it.'},
    {'name': 'ITEM3W_TRANSITIONS', 'item': 'ITEM3W', 'line': 1585,
     'value': ['TIMEOUT_AT_B_PLUS_2017', 'TIMEOUT_AT_B_PLUS_4033', 'TIMEOUT_AFTER_SAME_BLOCK_BEAT'],
     'phrase': 'It judges the transitions CURRENT → TIMEOUT at B + 2,017 and at B + 4,033, and a TIMEOUT after a '
               'same-block BEAT.'},
    {'name': 'ITEM3W_W_POLICY', 'item': 'ITEM3W', 'line': 1623,
     'value': {'w_cost_cap_sat': 30000, 'w_window_gates': 15, 'v_ref_vb': 213, 'strong_link_min_value_sat': 30000},
     'phrase': 'New W-policy keys in a schema of their own: `w_cost_cap_sat` 30000, `w_window_gates` 15, `v_ref_vb` '
               '213, `strong_link_min_value_sat` 30000.'},
    {'name': 'ITEM3W_W_POLICY_REFUSED', 'item': 'ITEM3W', 'value': 'A_KEY_THAT_DIFFERS_IS_REFUSED', 'line': 1579,
     'phrase': 'The judge refuses a W policy whose key differs from its constant that cites this section, so the '
               'threshold is still a sentence of this file.'},
    {'name': 'ITEM3W_EXPERIMENT', 'item': 'ITEM3W', 'value': 'ITEM3W', 'line': 1642,
     'phrase': "The judge's `EXPERIMENTS` gains `ITEM3W`. It checks the W policy's shape and the W-row tool's "
               'SHA-256 that the follow-up registration binds, as it checks `d2_2_tool_sha256` for D2-2.'},
    {'name': 'ITEM3_ITEM3W_ROWS', 'item': 'ITEM3', 'value': ['D_Z15', 'D_T', 'D_P', 'W_P', 'W_DATA'], 'line': 382,
     'phrase': "ITEM3W's D-Z15, D-T, D-P, W-P and W-DATA reports are judged under this item"},
    {'name': 'ROW_503_ITEM3W_ROWS', 'item': 'ITEM3W', 'value': ['D_C', 'W_C'], 'line': 503,
     'phrase': "ITEM3W's D-C and W-C reports are judged under this row, with 0 exclusions"},
)


def constant(name: str):
    """One entry of THRESHOLDS: the working constants below read their values from that table only."""
    return next(t['value'] for t in THRESHOLDS if t['name'] == name)


REPORT_THRESHOLDS = list(constant('ITEM1_REPORT_THRESHOLDS'))
EXCLUSION_NUM, EXCLUSION_DEN = constant('EXCLUSION_LIMIT')['num'], constant('EXCLUSION_LIMIT')['den']
ITEM1_GATES = constant('ITEM1_GATES')
LINK_RECALL_MIN = constant('ITEM1_LINK_RECALL_MIN')
LINK_PRECISION_MIN = constant('ITEM1_LINK_PRECISION_MIN')
WALLETS = tuple('W%02d' % i for i in range(constant('ITEM1_WALLETS_OWNERS')[0]))
OWNERS = tuple('O%d' % i for i in range(constant('ITEM1_WALLETS_OWNERS')[1]))
PLANTED = range(constant('ITEM1_PLANTED_GATES')[0], constant('ITEM1_PLANTED_GATES')[1] + 1)
ANCESTRY_SHARE = constant('ITEM1_ANCESTRY_SHARE')     # flag when the draw (n = den) is below num
KEY_REUSE_SHARE = constant('ITEM1_KEY_REUSE_SHARE')
ITEM1_RUNS = constant('ITEM1_RUNS')
POOL_RUNS, POOL_GATES_PER_RUN = constant('POOL_RUNS_GATES')
PRODUCER_DRAW = constant('POOL_PRODUCER_DRAW')
HHI_MAX = constant('POOL_HHI_MAX')
# J3: the pool run (ARV1 sections 17 and 18). Its DRAFT params are ARV1's (b 3,000, H0 110, 4 gates); the producer of
# a block is read from its coinbase (a push of PRODUCER_TAG and one letter), never from a driver line.
POOL_MINER_POLICY = 'POOL_50_30_20'
POOL_DRAFT_PARAMS = {'b': 3000, 'H0': 110, 'gates_per_run': POOL_GATES_PER_RUN}
PRODUCER_TAG = b'BITAGI_ARDR_PRODUCER_'
PRODUCERS = ('A', 'B', 'C')
PRODUCER_LABEL = re.compile(r'PRODUCER_H(0|[1-9][0-9]{0,8})\Z')   # ARV1 section 6: the height without leading zeros
GATES_PER_RUN_MAX = 200      # ARV1 section 18: `gates_per_run` 1 ... 200 for ITEM1 and POOL
PROJECT = object()           # a project gate in a report sequence (none in item 1; CLV1 reading (b))
UNKNOWN = 'UNKNOWN'

GATE_FIELDS = ('height', 'bidders', 'funding', 'block_g', 'winner', 'register_shape', 'fee', 'd2_2_winner',
               'anchor_key', 'replay_birth', 'replay_next_birth', 'replay_other_birth')
RUN_FIELDS = ('params', 'miner_policy', 'bidders_sha256', 'bidders_list', 'funding_layout', 'OWNER_SPLIT',
              'ANCESTRY_ON_CHAIN', 'd2_2_inputs', 'd2_2_method', 'd2_2_truth')

# J2: A's replay worker (ARDR_JUDGE_V1 section 17). One request file in, one answer file out, per call; a request
# holds at most 3 MiB of block hex or 4,096 blocks (one larger block goes alone), as B's campaign chunks its own.
REPLAY_TARGET = 'ardr_judge_replay'
REPLAY_TEST = 'ardr_judge_replay_worker'
REPLAY_REQUEST_ENV = 'BITAGI_ARDR_JUDGE_REPLAY_REQUEST'
REPLAY_ANSWER_ENV = 'BITAGI_ARDR_JUDGE_REPLAY_ANSWER'
REPLAY_REQUEST_HEAD = 'ARDR_JUDGE_REPLAY_REQUEST_V1'
REPLAY_ANSWER_HEAD = 'ARDR_JUDGE_REPLAY_ANSWER_V1'
# J6a (section 31): the V2 request has V1's body; its answer adds each block's Heart events after the block's ROW and
# both counts to END. Kinds and causes are B's EVENTS names (W3-3b-2 note 1.3 and 1.8); each kind's causes ('-' is
# none). Only Stage 0's MAX_AGE and TIMEOUT endings have no tx_index, and only BROKEN has no Anchor.
REPLAY_REQUEST_HEAD_V2 = 'ARDR_JUDGE_REPLAY_REQUEST_V2'
REPLAY_ANSWER_HEAD_V2 = 'ARDR_JUDGE_REPLAY_ANSWER_V2'
EVENT_CAUSES = {'BORN': ('-',), 'BEAT': ('-',), 'BROKEN': ('BROKEN_ONE', 'BROKEN_ALL'),
                'ENDED': ('MAX_AGE', 'TIMEOUT', 'BROKEN')}
STAGE0_CAUSES = ('MAX_AGE', 'TIMEOUT')
EVENT_ANCHOR = re.compile(r'([0-9a-f]{64}):(0|[1-9][0-9]{0,9})\Z')   # <txid>:<vout>, txid in display order
REPLAY_CHUNK_HEX = 3 << 20
REPLAY_CHUNK_BLOCKS = 4096
REPLAY_REQUEST_LIMIT = 12 << 20   # the worker's own bound
REPLAY_ANSWER_LIMIT = 16 << 20
REPLAY_SECONDS = 1800             # one call; the first may compile the worker
DECIMAL = re.compile(r'(?:0|[1-9][0-9]*)\Z')

# J2: the judge workflow's reads (ARDR_JUDGE_V1 section 18).
ARDR_WORKFLOW = '.github/workflows/claude-track-ardr.yml'
DECLARATION_SCHEMA = 'BITAGI_CT_ARDR_DECLARATION_V2'
RUN_ID = re.compile(r'[1-9][0-9]{0,19}\Z')
OID = re.compile(r'[0-9a-f]{40}\Z')
SLICE_ARTIFACT = re.compile(r'ardr-slice-([1-9][0-9]{0,3})\Z')
# At most 20 listed runs. J3 keeps J2's bound: ITEM1 is one unit and POOL 50 units of 4 gates (200 observations, one
# dispatch under the campaign's 400-observation budget), so 20 leaves room for re-dispatching BEFORE_START units; an
# experiment with more completed dispatches than that cannot be listed whole and fails closed (RUN_LIST_INCOMPLETE).
RUN_IDS_MAX = 20
RUN_LIST_PAGE = 100               # J3: the dispatch listing, `per_page=100`
RUN_LIST_CAP = 1000               # GitHub returns at most 1,000 runs for a filtered listing: a capped one is refused
# The campaign's run names (claude-track-ardr.yml `run-name`; the collector's RUN_TITLE and RECOLLECT_TITLE,
# tools/claude_track_ardr_slices.py): a dispatch on main is `ardr <CONFIRMATORY|EXPLORATORY> <experiment>` or
# `ardr RECOLLECT <experiment> <run id>`; any other title means the judge no longer reads the listing as written.
CAMPAIGN_TITLE = re.compile(r'ardr (?:CONFIRMATORY|EXPLORATORY) ([A-Z0-9_]{1,40})\Z')
RECOLLECT_TITLE = re.compile(r'ardr RECOLLECT ([A-Z0-9_]{1,40})(?: (.*))?\Z', re.S)
UTC_TIME = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?(?:Z|[+-]\d{2}:\d{2})\Z')
FETCHED_LIMIT = 64 << 20          # one saved API answer
MAIN_HISTORY_LIMIT = 64 << 20     # `git rev-list --first-parent` of the judge's own main commit, 41 bytes a line
ZIP_LIMIT = 1 << 30               # one artifact zip as downloaded
UNPACKED_LIMIT = 4 << 30          # the members of one zip
SLICE_RECORD_LIMIT = 1 << 20
STRAY_RECORD_TMP = 'slice-record.json.tmp'   # ARV1 section 13 (D4-2): a killed `replace`'s leftover, never read
# J4b (ARDR_JUDGE_V1 section 27): the experiments the judge workflow reads (`artifacts`, `unpack`), each judged per unit
# by its own command (`item1`, `pool`, `item2`, `item4`) and then by `experiment`. ITEM3 has no judge yet (J6).
WORKFLOW_EXPERIMENTS = ('ITEM1', 'POOL', 'ITEM2') + ITEM4_SCENARIOS
# J4b (section 16 P3-2): the campaign workflow's plan job, as the jobs listing names it (claude-track-ardr.yml; the
# collector's PLAN_JOB_NAME, restated since the judge imports no driver module; test_ardr_judge_workflow pins it to the
# file). A dispatch that declared nothing counts as listed only when its attempt-1 jobs listing shows this job failed
# or never ran and no other job ran a step (B's `prior_declaration` rule, ARV1 section 13 D-1, made stricter: any job).
PLAN_JOB_NAME = 'ARDR dispatch plan (main only, slice budget, re-dispatch rule)'
JOBS_PAGE = 100                   # the jobs listing, `per_page=100`: one page holds every job of a dispatch
# J4b (section 16 P3-8): the CONFIRMATORY dispatch listing asks only for runs created on or after the UTC date two days
# before the bound, so GitHub's 1,000-run cap counts those runs alone. Two days: whatever day boundary or time zone the
# server reads the date in, its filter keeps every run created at or after the bound, which the judge then applies
# exactly itself (RUN_LIST_INCOMPLETE, RUN_LIST_DISAGREES).
RUN_LIST_QUERY = 'event=workflow_dispatch&branch=main&per_page=100'
RUN_LIST_MARGIN = datetime.timedelta(days=2)


class Refusal(Exception):
    """A judgement that cannot be made: one JSON line with a fixed code, and its exit code."""

    def __init__(self, code: str, exit_code: int = EXIT_VALIDATION):
        super().__init__(code)
        self.code = code
        self.exit_code = exit_code


def need(condition: bool, code: str, exit_code: int = EXIT_VALIDATION) -> None:
    if not condition:
        raise Refusal(code, exit_code)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii')


def int_in(value, low: int, high: int) -> bool:
    return type(value) is int and low <= value <= high


# ---------------------------------------------------------------------------------------------------------
# Bounded strict input.

def _object(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError('duplicate key')
        out[key] = value
    return out


def _refuse_number(_text):
    raise ValueError('number refused')


def loads(text: str, code: str, floats: bool = False):
    """JSON with no duplicate key and no non-finite constant; a float is refused unless `floats` (the raw log's
    node answers carry BTC amounts), and then it is kept as a Decimal that nothing reads."""
    try:
        return json.loads(text, object_pairs_hook=_object, parse_constant=_refuse_number,
                          parse_float=decimal.Decimal if floats else _refuse_number)
    except (ValueError, RecursionError):
        raise Refusal(code) from None


def open_regular(path: Path, name: str, limit: int):
    """An open binary handle on one regular file (its last component not a symlink) of at most `limit` bytes.
    The open does not block, so a FIFO or a device is refused (`_NOT_REGULAR`) instead of waited on."""
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    except OSError as error:
        if error.errno == errno.ELOOP:
            raise Refusal(f'{name}_NOT_REGULAR') from None
        raise Refusal(f'{name}_UNAVAILABLE', EXIT_PREREQUISITE) from None
    info = os.fstat(fd)   # before fdopen, which raises on a directory (J2: a directory is _NOT_REGULAR, not exit 4)
    if not stat.S_ISREG(info.st_mode):
        os.close(fd)
        raise Refusal(f'{name}_NOT_REGULAR')
    if info.st_size > limit:
        os.close(fd)
        raise Refusal(f'{name}_SIZE')
    return os.fdopen(fd, 'rb')


def read_file(path: Path, name: str, limit: int) -> bytes:
    with open_regular(path, name, limit) as handle:
        data = handle.read(limit + 1)
    need(len(data) <= limit, f'{name}_SIZE')
    return data


def json_document(blob: bytes, name: str) -> dict:
    try:
        text = blob.decode('utf-8')
    except UnicodeDecodeError:
        raise Refusal(f'{name}_JSON') from None
    doc = loads(text, f'{name}_JSON')
    need(type(doc) is dict, f'{name}_JSON')
    return doc


def pending(value) -> bool:
    """A PENDING marker anywhere: a string value that starts with PENDING (ARV1 section 3)."""
    if isinstance(value, str):
        return value.startswith('PENDING')
    if isinstance(value, dict):
        return any(pending(v) for v in value.values())
    if isinstance(value, list):
        return any(pending(v) for v in value)
    return False


# ---------------------------------------------------------------------------------------------------------
# Seed draw (045b 4.6 `randomness`; ARV1 section 6). No 2^20 cap: k runs to 2^32 - 1 (decision 13).

LABEL = re.compile(r'[\x21-\x7e]+\Z')


def draw_digest(seed: bytes, e: str, r: int, label: str, k: int) -> bytes:
    """D = SHA-256(seed || e || 0x00 || u32be(r) || label || 0x00 || u32be(k))."""
    return hashlib.sha256(b''.join((seed, e.encode('ascii'), b'\x00', r.to_bytes(4, 'big'),
                                    label.encode('ascii'), b'\x00', k.to_bytes(4, 'big')))).digest()


def draw(seed: bytes, e: str, r: int, label: str, n: int) -> tuple[int, int]:
    """The integer uniform in [0, n) of choice `label` in run `r` of experiment `e`, and the k that gave it:
    x = the first 8 bytes of D as a big-endian u64, accepted as x mod n only when x < floor(2^64 / n) * n."""
    need(type(seed) is bytes and len(seed) == 32, 'DRAW_SEED', EXIT_INTERNAL)
    need(type(e) is str and type(label) is str and LABEL.match(e) is not None and LABEL.match(label) is not None,
         'DRAW_LABEL', EXIT_INTERNAL)
    need(type(r) is int and 0 <= r < U32 and type(n) is int and 1 <= n <= U64, 'DRAW_RANGE', EXIT_INTERNAL)
    limit = (U64 // n) * n
    for k in range(U32):
        x = int.from_bytes(draw_digest(seed, e, r, label, k)[:8], 'big')
        if x < limit:
            return x % n, k
    raise Refusal('DRAW_EXHAUSTED', EXIT_INTERNAL)


# ---------------------------------------------------------------------------------------------------------
# Policy, method policy, registration and the 045b file.

POLICY_KEYS = {'schema', 'seed', 'counts', 'experiments', 'bidders', 'thresholds'}
POLICY_REQUIRED = {'schema', 'seed', 'counts', 'experiments', 'bidders'}
METHOD_KEYS = {'schema', 'floor_height', 'max_depth', 'max_window_blocks', 'thresholds'}


def policy_head(blob: bytes, mode: str) -> tuple[dict, dict]:
    """A BITAGI_CT_ARDR_POLICY_V1 file's closed key set, PENDING rule, seed and `experiments` map (ARV1 section 3)."""
    doc = json_document(blob, 'POLICY')
    need(set(doc) <= POLICY_KEYS and POLICY_REQUIRED <= set(doc) and doc['schema'] == POLICY_SCHEMA,
         'POLICY_SHAPE')
    if mode == 'CONFIRMATORY':
        need(not pending(doc), 'POLICY_PENDING', EXIT_PREREQUISITE)
    need(not pending(doc['seed']), 'SEED_PENDING', EXIT_PREREQUISITE)
    need(type(doc['seed']) is str and HEX64.match(doc['seed']) is not None, 'POLICY_SEED')
    experiments = doc['experiments']
    need(type(experiments) is dict and all(name in EXPERIMENTS and type(entry) is dict
                                           for name, entry in experiments.items()), 'POLICY_SHAPE')
    return doc, experiments


def policy_params(params, confirmatory: bool, draft: dict, most: int) -> tuple[dict, str]:
    """`experiments.<E>.params` (ARV1 section 18): exactly `b`, `H0` and `gates_per_run`, numbers in range; without
    them a run outside CONFIRMATORY takes the DRAFT params."""
    if params is None:
        need(not confirmatory, 'POLICY_PARAMS_UNSET', EXIT_PREREQUISITE)
        return dict(draft), 'DRAFT'
    need(type(params) is dict and set(params) == {'b', 'H0', 'gates_per_run'}, 'POLICY_PARAMS')
    need(not pending(params), 'POLICY_PARAMS_PENDING', EXIT_PREREQUISITE)
    need(int_in(params['b'], 1, U32 - 1) and int_in(params['H0'], 106, U32 - 1)
         and int_in(params['gates_per_run'], 1, most), 'POLICY_PARAMS')
    return dict(params), 'POLICY'


def parse_policy(blob: bytes, mode: str) -> dict:
    """The ITEM1 part of a BITAGI_CT_ARDR_POLICY_V1 file (ARV1 sections 3 and 18)."""
    doc, experiments = policy_head(blob, mode)
    confirmatory = mode == 'CONFIRMATORY'
    need('ITEM1' in experiments, 'POLICY_ITEM1')
    need(all('method_policy' not in entry for name, entry in experiments.items() if name != 'ITEM1'),
         'POLICY_METHOD_POLICY')
    entry = experiments['ITEM1']
    need(set(entry) <= {'miner_policy', 'params', 'method_policy'} and 'miner_policy' in entry, 'POLICY_ITEM1')
    need(not pending(entry['miner_policy']), 'POLICY_PENDING', EXIT_PREREQUISITE)
    need(entry['miner_policy'] == MINER_POLICY, 'POLICY_MINER_EXPERIMENT')
    counts = doc['counts']
    need(pending(counts) or type(counts) is dict, 'POLICY_SHAPE')
    count = counts.get('ITEM1') if type(counts) is dict else None
    if confirmatory:
        need(int_in(count, 1, U32 - 1), 'POLICY_COUNT_UNSET', EXIT_PREREQUISITE)
    params, source = policy_params(entry.get('params'), confirmatory, DRAFT_PARAMS, ITEM1_GATES)
    if confirmatory:
        need(params['gates_per_run'] == ITEM1_GATES, 'POLICY_ITEM1_GATES')
    method = entry.get('method_policy')
    if method is None:
        need(not confirmatory, 'METHOD_POLICY_NOT_DECLARED', EXIT_PREREQUISITE)
    else:
        need(type(method) is dict and set(method) == {'path', 'sha256'} and type(method['path']) is str
             and type(method['sha256']) is str
             and (pending(method['sha256']) or HEX64.match(method['sha256']) is not None), 'POLICY_METHOD_POLICY')
    return {'sha256': sha256(blob), 'seed': bytes.fromhex(doc['seed']), 'params': params,
            'params_source': source, 'count': count if type(count) is int else None, 'method_policy': method}


def parse_pool_policy(blob: bytes, mode: str) -> dict:
    """J3: the POOL part of a BITAGI_CT_ARDR_POLICY_V1 file (ARV1 sections 3 and 18): the miner policy
    POOL_50_30_20, the params (ARV1's DRAFT b 3,000, H0 110, 4 gates outside CONFIRMATORY), no method policy. A
    CONFIRMATORY policy needs the count, params, and 045b's 50 runs of 4 gates (:545)."""
    doc, experiments = policy_head(blob, mode)
    confirmatory = mode == 'CONFIRMATORY'
    need('POOL' in experiments, 'POLICY_POOL')
    need(all('method_policy' not in entry for name, entry in experiments.items() if name != 'ITEM1'),
         'POLICY_METHOD_POLICY')
    entry = experiments['POOL']
    need(set(entry) <= {'miner_policy', 'params'} and 'miner_policy' in entry, 'POLICY_POOL')
    need(not pending(entry['miner_policy']), 'POLICY_PENDING', EXIT_PREREQUISITE)
    need(entry['miner_policy'] == POOL_MINER_POLICY, 'POLICY_MINER_EXPERIMENT')
    counts = doc['counts']
    need(pending(counts) or type(counts) is dict, 'POLICY_SHAPE')
    count = counts.get('POOL') if type(counts) is dict else None
    if confirmatory:
        need(int_in(count, 1, U32 - 1), 'POLICY_COUNT_UNSET', EXIT_PREREQUISITE)
        need(count == POOL_RUNS, 'POLICY_POOL_RUNS')
    params, source = policy_params(entry.get('params'), confirmatory, POOL_DRAFT_PARAMS, GATES_PER_RUN_MAX)
    if confirmatory:
        need(params['gates_per_run'] == POOL_GATES_PER_RUN, 'POLICY_POOL_GATES')
    return {'sha256': sha256(blob), 'seed': bytes.fromhex(doc['seed']), 'params': params,
            'params_source': source, 'count': count if type(count) is int else None, 'method_policy': None}


def parse_method_policy(blob: bytes, mode: str, declared: dict | None) -> dict:
    """The method policy (ARV1 section 15) bound by the policy's `method_policy` SHA-256 (section 18). Its
    thresholds must be 045b's [4, 15] (ITEM1_REPORT_THRESHOLDS): the expected lists use those constants."""
    doc = json_document(blob, 'METHOD_POLICY')
    need(set(doc) == METHOD_KEYS and doc['schema'] == METHOD_POLICY_SCHEMA, 'METHOD_POLICY_SHAPE')
    digest = sha256(blob)
    if declared is not None and not pending(declared['sha256']):
        need(digest == declared['sha256'], 'METHOD_POLICY_SHA256', EXIT_REFUSAL)
    values, drafted = {}, []
    bounds = {'floor_height': (0, U32 - 1), 'max_depth': (1, 10_000), 'max_window_blocks': (1, 100_000)}
    for key in ('floor_height', 'max_depth', 'max_window_blocks', 'thresholds'):
        value = doc[key]
        if pending(value):
            need(mode != 'CONFIRMATORY', 'METHOD_POLICY_PENDING', EXIT_PREREQUISITE)
            values[key] = DRAFT_METHOD[key]
            drafted.append(key)
        elif key == 'thresholds':
            need(type(value) is list and value and all(int_in(t, 1, 1_000_000) for t in value)
                 and all(a < b for a, b in zip(value, value[1:])), 'METHOD_POLICY_SHAPE')
            values[key] = list(value)
        else:
            need(int_in(value, *bounds[key]), 'METHOD_POLICY_BOUND')
            values[key] = value
    need(values['thresholds'] == REPORT_THRESHOLDS, 'METHOD_THRESHOLDS')
    return {'sha256': digest, 'values': values, 'drafted': drafted,
            'path': declared['path'] if declared is not None else None}


def parse_registration(blob: bytes) -> tuple[dict, list[str]]:
    """The D1 placeholder registration (ARV1 section 4): a JSON object whose `ardr_policy_sha256` is a non-empty
    list of SHA-256 values; other keys are ignored until A's P5-005 format names them."""
    doc = json_document(blob, 'REGISTRATION')
    listed = doc.get('ardr_policy_sha256')
    need(type(listed) is list and listed and all(type(h) is str and HEX64.match(h) for h in listed),
         'REGISTRATION_SHAPE')
    return doc, listed


# FD-CT-133 (section 30): the experiments a registration covers, the driver's `REGISTRATION_EXPERIMENTS_KEY`.
REGISTRATION_EXPERIMENTS_KEY = 'experiments'


def registered_experiment(registration: dict, experiment: str) -> None:
    """FD-CT-133 (section 30), the driver's rule (`load_policy`): a registration that names its experiments covers those
    only, so a CONFIRMATORY judgement of another is EXPERIMENT_NOT_REGISTERED (exit 6). Without the key it reads as
    before; a key that is not a non-empty list of strings is REGISTRATION_SHAPE."""
    if REGISTRATION_EXPERIMENTS_KEY in registration:
        covered = registration[REGISTRATION_EXPERIMENTS_KEY]
        need(type(covered) is list and covered and all(type(e) is str for e in covered), 'REGISTRATION_SHAPE')
        need(experiment in covered, 'EXPERIMENT_NOT_REGISTERED', EXIT_REFUSAL)


def covering_registration(args, experiment: str) -> None:
    """CONFIRMATORY, before the policy is read, as the driver refuses before it parses the policy (so a first
    registration's ITEM2 is EXPERIMENT_NOT_REGISTERED, not a policy code): `registered_experiment` on the registration
    given. None given is left to `registered_log` (REGISTRATION_MISSING, as before), which checks the same rule again
    on the bytes it binds to the raw log."""
    if args.registration is not None:
        registered_experiment(parse_registration(read_file(args.registration, 'REGISTRATION',
                                                           REGISTRATION_LIMIT))[0], experiment)


def registered_d2_2_sha256(registration: dict) -> str | None:
    """J2 (A #258, J2 PR: A's decision on the D2-2 hash): the registration's `d2_2_tool_sha256`, the SHA-256 of the
    bytes of the D2-2 file (the tree's cluster tool, ARV1 section 18 :1496-1499) at the registered commit; every
    CLUSTER_TOOL line's `tool_sha256` must equal it. ARV1 section 4 gains the key at the 045b freeze PR. Absent:
    None (D2_2_TOOL_NOT_REGISTERED); present, it must be 64 lowercase hex (REGISTRATION_D2_2_TOOL)."""
    if 'd2_2_tool_sha256' not in registration:
        return None
    value = registration['d2_2_tool_sha256']
    need(type(value) is str and HEX64.match(value) is not None, 'REGISTRATION_D2_2_TOOL')
    return value


def read_prereg(path: Path) -> dict:
    """The 045b file: its SHA-256, and every constant's phrase on its cited line (decision 5)."""
    blob = read_file(path, 'PREREG', PREREG_LIMIT)
    try:
        lines = blob.decode('utf-8').split('\n')
    except UnicodeDecodeError:
        raise Refusal('PREREG_CITATION', EXIT_REFUSAL) from None
    for entry in THRESHOLDS:
        need(entry['line'] <= len(lines) and entry['phrase'] in lines[entry['line'] - 1], 'PREREG_CITATION',
             EXIT_REFUSAL)
    try:
        shown = str(path.resolve().relative_to(ROOT))
    except ValueError:
        shown = None
    return {'path': shown, 'sha256': sha256(blob)}


def threshold_table() -> list[dict]:
    """The record's `thresholds`; an amended row (section 30) also carries its `amends` {value, by}."""
    return [{'name': t['name'], 'item': t['item'], 'value': t['value'], 'cite': '045b:%d' % t['line'],
             **({'amends': dict(t['amends'])} if 'amends' in t else {})}
            for t in THRESHOLDS]


# ---------------------------------------------------------------------------------------------------------
# J-1090: the requirement verdict beside each outcome, and the cause kept (ARDR_JUDGE_V1 section 29; 045b :1090, frozen;
# A's decisions of 2026-11-11). Every record that states an outcome also carries `verdict` {expected, observed, result,
# inconclusive_reason}, the four keys of the XD-1 collection report. It is a view: it is made last, from the finished
# outcome and the finished figures, in EXPLORATORY and CONFIRMATORY alike, and no state, count or outcome reads it.

VERDICT_RESULT = constant('VERDICT_MAPPING')
EXCLUSION_LIMIT = constant('EXCLUSION_LIMIT')
REPORTS_EQUAL = 'EQUAL_TO_EXPECTED_LISTS'   # decision 3: no report missing, extra or at a wrong gate (`expected`)


def verdict_block(outcome: dict, expected: dict | None = None, observed: dict | None = None) -> dict:
    """`result` is the image of the finished `outcome.result` under VERDICT_RESULT, and of nothing else. The causes are
    that outcome's own `not_established` codes when the result is INCONCLUSIVE, else null (a list: several can hold at
    once). `expected` is the registered criterion and `observed` what the judge measured; a record that states no
    verdict (NOT_A_VERDICT_PER_RUN) has both null."""
    result = VERDICT_RESULT[outcome['result']]
    return {'expected': expected, 'observed': observed, 'result': result,
            'inconclusive_reason': list(outcome['not_established']) if result == 'INCONCLUSIVE' else None}


def item1_criterion() -> dict:
    """Item 1's registered criterion (045b :380, decision 3 and the 10% rule, :572), from the constant table."""
    return {'reports': REPORTS_EQUAL, 'link_recall_min': LINK_RECALL_MIN, 'link_precision_min': LINK_PRECISION_MIN,
            'exclusion_limit': EXCLUSION_LIMIT}


def item1_observed(comparison: dict, counts: dict) -> dict:
    """What the judge measured in one item-1 run. A comparison that was not evaluated leaves the report counts and both
    metrics null, never the expected value; a 0/0 metric keeps its `undefined` fraction."""
    evaluated = comparison['evaluated']
    return {'evaluated': evaluated, 'not_evaluated_reason': comparison['not_evaluated_reason'],
            'reports': {k: len(comparison['reports'][k]) for k in ('missing', 'extra', 'wrong_gate')}
            if evaluated else None,
            'link_recall': comparison['metrics']['link_recall'] if evaluated else None,
            'link_precision': comparison['metrics']['link_precision'] if evaluated else None,
            'gates': counts['gates'], 'missing_or_excluded': counts['missing_or_excluded']}


def collection_code(collection: dict | None) -> str | None:
    """The collection's code of the judged unit, as its text; null without a collection or without a text code. It is
    shown only (`run_shape.collection_code`): a claim like the other collection data, it changes no state and feeds no
    count, and it is the text as given, also when that is no code word. A unit the slice killed at its time limit
    before RUN_END, its last line whole, keeps its UNIT_TIMEOUT here beside the log-derived gate codes. When the kill
    cut the last line the collection itself says RAW_LOG_TRUNCATED (ARV1 section 13), and so does this field."""
    code = collection.get('code') if collection is not None else None
    return code if type(code) is str else None


def exclusion_tally(rows: list) -> dict:
    """The cause of every gate that is not OBSERVED, by code, over the rows `gate_counts` counted (the same list, so the
    tally's sum is `gate_counts.missing_or_excluded`); a gate without a code (null or empty) counts under NONE, as in
    the item-2 and item-4 tallies."""
    tally: dict[str, int] = {}
    for state, code, _ in rows:
        if state != 'OBSERVED':
            tally[code or 'NONE'] = tally.get(code or 'NONE', 0) + 1
    return tally


# ---------------------------------------------------------------------------------------------------------
# The item-1 plan (045b 4.6 rows `item 1 ownership clusters`, `gate winners`, `Anchor keys`; ARV1 9 and 16).

def wallet_draws(seed: bytes, r: int) -> dict:
    """Each wallet's owner, ancestry flag and key-reuse flag, with the draws that gave them."""
    out = {}
    for i, w in enumerate(WALLETS):
        owner, k_owner = draw(seed, 'ITEM1', r, 'OWNER_W%02d' % i, len(OWNERS))
        ancestry, k_ancestry = draw(seed, 'ITEM1', r, 'ANCESTRY_W%02d' % i, ANCESTRY_SHARE['den'])
        reuse, k_reuse = draw(seed, 'ITEM1', r, 'KEY_REUSE_W%02d' % i, KEY_REUSE_SHARE['den'])
        out[w] = {'owner': 'O%d' % owner, 'owner_draw': [owner, k_owner], 'ancestry_draw': [ancestry, k_ancestry],
                  'shares_ancestry': ancestry < ANCESTRY_SHARE['num'], 'key_reuse_draw': [reuse, k_reuse],
                  'reuses_base_key': reuse < KEY_REUSE_SHARE['num']}
    return out


def owners_of(wallets: dict) -> dict[str, list[str]]:
    """Owner -> its wallets in ascending order, for every owner O0-O9 (an owner may have none)."""
    out = {o: [] for o in OWNERS}
    for w in WALLETS:
        out[wallets[w]['owner']].append(w)
    return out


def planted_owner(owners: dict[str, list[str]]) -> str:
    """The owner with the most wallets, the lowest owner index on ties (045b:532; ARV1 section 9)."""
    best = OWNERS[0]
    for o in OWNERS[1:]:
        if len(owners[o]) > len(owners[best]):
            best = o
    return best


def base_label(owners: dict[str, list[str]], owner: str) -> str:
    """The owner's base key: its lowest-indexed wallet's first Heart (045b:533; ARV1 section 9)."""
    return 'SYNTHETIC_%s_ANCHOR_H000' % owners[owner][0]


def item1_winners(seed: bytes, r: int, owners: dict[str, list[str]], planted: str, gates: int) -> list[dict]:
    """Gate 100 + j goes to the planted owner's wallet j mod m (ascending order, no draw); every other gate draws
    WINNER_G<ggg> (n = 40), winner W<value> (045b:532, :555)."""
    rows = []
    mine = owners[planted]
    for g in range(gates):
        if g in PLANTED:
            rows.append({'gate': g, 'wallet': mine[(g - PLANTED.start) % len(mine)], 'source': 'PLANTED',
                         'draw': None})
        else:
            value, k = draw(seed, 'ITEM1', r, 'WINNER_G%03d' % g, len(WALLETS))
            rows.append({'gate': g, 'wallet': WALLETS[value], 'source': 'DRAW', 'draw': [value, k]})
    return rows


def item1_plan(seed: bytes, r: int, gates: int, b: int) -> dict:
    """The whole plan of one ITEM1 run. Heart number h (decision 3): the wallet's earlier wins in this run, in
    gate order, from 0. A wallet that reuses its owner's base key carries it in every gate; any other wallet
    carries SYNTHETIC_<w>_ANCHOR_H<hhh>, so the base wallet's h = 0 gate also carries the base key. Funding: a
    flagged wallet's (wallet, gate) output is in its owner's OWNER transaction, any other in the FAN_OUT."""
    wallets = wallet_draws(seed, r)
    owners = owners_of(wallets)
    planted = planted_owner(owners)
    rows = item1_winners(seed, r, owners, planted, gates)
    hearts: dict[str, int] = {}
    fee = -(-b * CANDIDATE_VSIZE // 1000)
    for row in rows:
        w = row['wallet']
        info = wallets[w]
        h = hearts.get(w, 0)
        hearts[w] = h + 1
        row['owner'] = info['owner']
        row['heart'] = h
        row['anchor_label'] = (base_label(owners, info['owner']) if info['reuses_base_key']
                               else 'SYNTHETIC_%s_ANCHOR_H%03d' % (w, h))
        row['funding'] = 'OWNER ' + info['owner'] if info['shares_ancestry'] else 'FAN_OUT'
    plan = {'run': r, 'gates': gates, 'b': b, 'rung0_fee': fee, 'wallets': wallets, 'owners': owners,
            'planted_owner': planted, 'planted_wallets': len(owners[planted]),
            'base_wallets': {o: ws[0] for o, ws in owners.items() if ws}, 'winners': rows}
    plan['plan_sha256'] = sha256(canonical(plan))
    return plan


class UnionFind:
    def __init__(self, items):
        self.parent = {item: item for item in items}

    def find(self, item):
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, a, b) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)

    def groups(self) -> list[list]:
        out: dict = {}
        for item in self.parent:
            out.setdefault(self.find(item), []).append(item)
        return sorted(sorted(group) for group in out.values())


def gate_link_groups(plan: dict, judged: list[int]) -> list[dict]:
    """The planted on-chain links at gate level (decision 3), over the judged gates. ANCESTRY: every gate won by an
    ancestry-flagged wallet of one owner (they spend that owner's one OWNER transaction; one flagged wallet winning
    twice links its own two gates). ANCHOR_KEY: every gate whose Anchor carries one key label, so all gates of the
    owner's reusing wallets and its base wallet's h = 0 gate. A group needs two gates."""
    rows = {row['gate']: row for row in plan['winners']}
    groups = []
    for owner in OWNERS:
        gates = [g for g in judged
                 if rows[g]['owner'] == owner and plan['wallets'][rows[g]['wallet']]['shares_ancestry']]
        if len(gates) >= 2:
            groups.append({'kind': 'ANCESTRY', 'owner': owner, 'gates': gates})
    by_label: dict[str, list[int]] = {}
    for g in judged:
        by_label.setdefault(rows[g]['anchor_label'], []).append(g)
    for label in sorted(by_label):
        if len(by_label[label]) >= 2:
            groups.append({'kind': 'ANCHOR_KEY', 'owner': rows[by_label[label][0]]['owner'], 'label': label,
                           'gates': by_label[label]})
    return groups


def link_clusters(judged: list[int], groups: list[dict]) -> dict[int, str]:
    """Gate -> link-based cluster id `L<first gate>` of the transitive closure of the groups (CLV1 section 5)."""
    found = UnionFind(judged)
    for group in groups:
        for g in group['gates'][1:]:
            found.union(group['gates'][0], g)
    return {g: 'L%d' % found.find(g) for g in judged}


def pairs_of(groups) -> set[tuple[str, str]]:
    return {(a, b) for group in groups for i, a in enumerate(group) for b in group[i + 1:]}


def planted_pairs(plan: dict, judged: list[int]) -> set[tuple[str, str]]:
    """P_L (CLV1 section 6, 045b:392-396): each planted link group restricted to the winning wallets, then the
    restricted groups closed. Groups of one owner: its flagged winning wallets (ANCESTRY) and the winning wallets
    whose gates carry one key label (ANCHOR_KEY)."""
    rows = {row['gate']: row for row in plan['winners']}
    winners = sorted({rows[g]['wallet'] for g in judged})
    found = UnionFind(winners)
    for group in gate_link_groups(plan, judged):
        wallets = sorted({rows[g]['wallet'] for g in group['gates']})
        for w in wallets[1:]:
            found.union(wallets[0], w)
    return pairs_of(found.groups())


# ---------------------------------------------------------------------------------------------------------
# Raw block and transaction bytes (segwit aware; the txid hashes the non-witness serialization).

class Malformed(Exception):
    pass


class Cursor:
    def __init__(self, data: bytes):
        self.data, self.at = data, 0

    def take(self, n: int) -> bytes:
        if n < 0 or self.at + n > len(self.data):
            raise Malformed('truncated')
        part = self.data[self.at:self.at + n]
        self.at += n
        return part

    def uint(self, n: int) -> int:
        return int.from_bytes(self.take(n), 'little')

    def varint(self) -> int:
        first = self.uint(1)
        if first < 0xfd:
            return first
        size = {0xfd: 2, 0xfe: 4, 0xff: 8}[first]
        value = self.uint(size)
        if value < {2: 0xfd, 4: 0x10000, 8: 0x100000000}[size]:
            raise Malformed('non-canonical varint')
        return value


def dsha(data: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def read_tx(cursor: Cursor) -> dict:
    start = cursor.at
    version = cursor.take(4)
    segwit = cursor.data[cursor.at:cursor.at + 2] == b'\x00\x01'
    if segwit:
        cursor.take(2)
    body = cursor.at
    inputs = []
    for _ in range(cursor.varint()):
        prev = cursor.take(32)
        vout = cursor.uint(4)
        script = cursor.take(cursor.varint())
        cursor.take(4)
        inputs.append({'txid': prev[::-1].hex(), 'vout': vout, 'script': script})
    outputs = []
    for _ in range(cursor.varint()):
        value = cursor.uint(8)
        outputs.append((value, cursor.take(cursor.varint())))
    if not inputs or not outputs:
        raise Malformed('no input or output')
    body_end = cursor.at
    if segwit:
        items = 0
        for _ in inputs:
            for _ in range(cursor.varint()):
                cursor.take(cursor.varint())
                items += 1
        if items == 0:
            raise Malformed('superfluous witness')
    locktime = cursor.take(4)
    stripped = version + cursor.data[body:body_end] + locktime
    size = cursor.at - start
    coinbase = len(inputs) == 1 and inputs[0]['txid'] == '00' * 32 and inputs[0]['vout'] == 0xffffffff
    return {'txid': dsha(stripped)[::-1].hex(), 'inputs': inputs, 'outputs': outputs, 'coinbase': coinbase,
            'weight': len(stripped) * 3 + size}


def parse_tx(raw: bytes) -> dict:
    cursor = Cursor(raw)
    tx = read_tx(cursor)
    if cursor.at != len(raw):
        raise Malformed('trailing bytes')
    return tx


def merkle_root(hashes: list[bytes]) -> bytes:
    level = list(hashes)
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        level = [dsha(level[i] + level[i + 1]) for i in range(0, len(level), 2)]
    return level[0]


def bip34_height(script: bytes) -> int:
    """The height the coinbase scriptSig begins with: OP_1-OP_16, or a minimal positive push of 1-8 bytes."""
    if not script:
        raise Malformed('empty coinbase script')
    op = script[0]
    if 0x51 <= op <= 0x60:
        return op - 0x50
    if not (1 <= op <= 8 and len(script) > op):
        raise Malformed('no BIP34 height')
    data = script[1:1 + op]
    if data[-1] & 0x80 or (data[-1] == 0 and (len(data) == 1 or not data[-2] & 0x80)):
        raise Malformed('BIP34 height not minimal')
    height = int.from_bytes(data, 'little')
    if height <= 16:
        raise Malformed('BIP34 height not minimal')
    return height


def parse_block(raw: bytes) -> dict:
    if not 80 < len(raw) <= BLOCK_LIMIT:
        raise Malformed('block size')
    cursor = Cursor(raw)
    header = cursor.take(80)
    txs = [read_tx(cursor) for _ in range(cursor.varint())]
    if cursor.at != len(raw) or not txs:
        raise Malformed('block shape')
    if not txs[0]['coinbase'] or any(tx['coinbase'] for tx in txs[1:]):
        raise Malformed('coinbase position')
    ids = [bytes.fromhex(tx['txid'])[::-1] for tx in txs]
    if len(set(ids)) != len(ids) or merkle_root(ids) != header[36:68]:
        raise Malformed('merkle root')
    return {'hash': dsha(header)[::-1].hex(), 'prev': header[4:36][::-1].hex(),
            'height': bip34_height(txs[0]['inputs'][0]['script']), 'txs': txs}


def hex_bytes(value, code: str) -> bytes:
    need(type(value) is str and HEX.match(value) is not None, code)
    return bytes.fromhex(value)


def anchor_program(tx: dict) -> str | None:
    """The 32-byte witness program of vout[1] when its script is exactly 0x51 0x20 <32 bytes> (CLV1 section 5)."""
    if len(tx['outputs']) < 2:
        return None
    script = tx['outputs'][1][1]
    return script[2:].hex() if len(script) == 34 and script[:2] == b'\x51\x20' else None


# J3: the pool producer tag (ARV1 section 17, "Reading the tag"; the judge's own reader). The coinbase scriptSig is
# split into its data pushes in order: OP_0 (an empty push), OP_PUSHBYTES_1-75, OP_PUSHDATA1/2/4 with their
# little-endian lengths; any other opcode carries no data and is skipped. A tag is a push of exactly PRODUCER_TAG
# and one letter of PRODUCERS. A push that runs past the script's end makes the script unreadable (None).
PUSHDATA_WIDTH = {0x4c: 1, 0x4d: 2, 0x4e: 4}


def script_tags(script: bytes) -> list[str] | None:
    """The producer letters a coinbase scriptSig carries, in push order; None when a push runs past its end."""
    pushes, at = [], 0
    while at < len(script):
        op = script[at]
        at += 1
        if op > 0x4e:
            continue
        if op in PUSHDATA_WIDTH:
            width = PUSHDATA_WIDTH[op]
            if at + width > len(script):
                return None
            size = int.from_bytes(script[at:at + width], 'little')
            at += width
        else:
            size = op
        if at + size > len(script):
            return None
        pushes.append(script[at:at + size])
        at += size
    return [chr(push[-1]) for push in pushes
            if len(push) == len(PRODUCER_TAG) + 1 and push.startswith(PRODUCER_TAG) and chr(push[-1]) in PRODUCERS]


def coinbase_tags(raw: bytes) -> list[str] | None:
    """The producer tags of a block's coinbase read the way ARV1 section 13's collector reads a pool BLOCK line
    (the header, a transaction count of at least one, the version, an optional segwit marker, exactly one input,
    its scriptSig), without parsing the rest of the block. None when the bytes do not read so: the collector's
    gate then does not rebuild."""
    cursor = Cursor(raw)
    try:
        cursor.take(80)
        if cursor.varint() < 1:
            return None
        cursor.take(4)
        if cursor.data[cursor.at:cursor.at + 2] == b'\x00\x01':
            cursor.take(2)
        if cursor.varint() != 1:
            return None
        cursor.take(36)
        script = cursor.take(cursor.varint())
    except Malformed:
        return None
    return script_tags(script)


# ---------------------------------------------------------------------------------------------------------
# The raw log (one pass, bounded).

def _int(v) -> bool:
    return type(v) is int


def _str(v) -> bool:
    return type(v) is str


def _bool(v) -> bool:
    return type(v) is bool   # real JSON true/false only, never 0, 1 or 0.0


def _ints(v) -> bool:
    return type(v) is list and all(type(x) is int for x in v)


def _opt_int(v) -> bool:
    return v is None or type(v) is int


def _opt_str(v) -> bool:
    return v is None or type(v) is str


def has_float(value) -> bool:
    if isinstance(value, decimal.Decimal):
        return True
    if isinstance(value, dict):
        return any(has_float(v) for v in value.values())
    if isinstance(value, list):
        return any(has_float(v) for v in value)
    return False


# The fields the judge reads, per event, and the refusal code of a wrongly typed or missing one. Any float in
# these lines is refused too; a float is accepted only in the node answers the judge does not read.
FIELDS = {
    'RUN_START': ('RAW_LOG_TYPES', {'gates': _ints}),
    'BIDDERS': ('RAW_LOG_TYPES', {'bidders': lambda v: type(v) is dict, 'bidders_sha256': _str}),
    'BLOCK': ('RAW_LOG_BLOCK', {'height': _int, 'block_hash': _str, 'block_hex': _str}),
    'FUNDING_SENT': ('RAW_LOG_FUNDING', {'txid': _str, 'hex': _str, 'stage': _str,
                                         'outputs': lambda v: type(v) is list and all(
                                             type(o) is list and len(o) == 2 and type(o[0]) is str
                                             and type(o[1]) is int for o in v)}),
    'GATE_START': ('RAW_LOG_GATES', {'gate': _int, 'height': _int, 'wallet': _str, 'observation_id': _str}),
    'GATE_END': ('RAW_LOG_GATES', {'gate': _int, 'height': _int, 'status': _str, 'observation_id': _str,
                                   'winner_txid': _str, 'wallet': _str, 'block_hash': _str, 'next_birth': _int}),
    'CORE_REPLAY': ('RAW_LOG_TYPES', {'height': _int, 'born': lambda v: v is None or (
        type(v) is list and all(type(x) is str for x in v))}),
    'GENERATED': ('RAW_LOG_TYPES', {'ladder': _ints}),
    'CLUSTER_TOOL': ('RAW_LOG_CLUSTER', {'prefix': _bool, 'gates': _ints, 'exit': _int, 'output_bytes': _int,
                                         'output_sha256': _str, 'output': _opt_str,
                                         'tool_sha256': lambda v: type(v) is str and HEX64.match(v) is not None,
                                         'inputs': lambda v: type(v) is dict}),
    'PREFIX_START': ('RAW_LOG_GATES', {'code': _str, 'phase': _str, 'failed_gate': _opt_int, 'gates': _ints}),
}
PHASES = ('GATES', 'POST_GATES', 'CLUSTER', 'END')   # ARV1 section 16, RUN_END FAILED
RUN_END_DONE = {'deadline_reached': _bool, 'gates_not_started': _ints}                  # both optional
RUN_END_FAILED = {'code': _str, 'phase': lambda v: v in PHASES, 'failed_gate': _opt_int, 'cluster_failed': _bool,
                  'cluster_prefix': _str, 'cluster_prefix_reason': _opt_str, 'excluded_gates': _ints}
# J3: the pool lines' own fields (ARV1 sections 13 and 17), checked in a pool log after FIELDS: every BLOCK names its
# `producer`, every DRAW its `label`, `value`, `k` and `producer`, every GATE_END its `producer_tags`.
POOL_FIELDS = {
    'BLOCK': ('RAW_LOG_BLOCK', {'producer': _str}),
    'DRAW': ('RAW_LOG_TYPES', {'label': _str, 'value': _int, 'k': _int, 'producer': _str}),
    'GATE_END': ('RAW_LOG_GATES', {'producer_tags': lambda v: type(v) is list and all(type(t) is str for t in v)}),
}


def _hex64(v) -> bool:
    return type(v) is str and HEX64.match(v) is not None


def _strs(v) -> bool:
    return type(v) is list and all(type(x) is str for x in v)


def _ints_of(*keys):
    return lambda v: type(v) is dict and all(type(v.get(k)) is int for k in keys)


def _rows(**checks):
    """A list of objects, each holding the keys with the given checks."""
    return lambda v: type(v) is list and all(type(x) is dict and all(k in x and c(x[k]) for k, c in checks.items())
                                             for x in v)


def _pools(v) -> bool:
    return type(v) is dict and set(v) == {'relay', 'miner', 'A', 'B'} and all(_strs(x) for x in v.values())


def _l0_fee(v) -> bool:
    return (type(v) is dict and all(type(v.get(k)) is int for k in ('b', 'p0', 'i', 'v', 'k', 'f_k'))
            and _ints_of('A', 'B')(v.get('increments')) and _ints(v.get('ladder')))


def _l0_node(v) -> bool:
    return type(v) is dict and type(v.get('in_mempool')) is bool and type(v.get('fee')) is int \
        and type(v.get('vsize')) is int


# J4a: the item-2 lines' fields the judge reads (ARV1 sections 20 and 22), with the refusal code of a wrongly typed
# or missing one; the third value says whether a float anywhere in the line is refused (False for the node answers
# the judge does not read: a getblocktemplate answer, testmempoolaccept answers).
ITEM2_FIELDS = {
    'RUN_START': ('RAW_LOG_TYPES', {'gates': _ints, 'params': lambda v: type(v) is dict, 'miner_policy': _str,
                                    'bidders_sha256': _str, 'private_present': _bool, 'order_constrained': _bool,
                                    't_gate_seconds': _int, 'rung_seconds': _int, 'release_ks': _ints,
                                    'l0_seat': lambda v: type(v) is int or v == 'PENDING_FREEZE',
                                    'l0_seat_source': _str, 'schedule_source': _str}, True),
    'BIDDERS': ('RAW_LOG_TYPES', {'bidders': lambda v: type(v) is dict, 'bidders_sha256': _str,
                                  'draws': lambda v: type(v) is list and all(type(x) is dict for x in v),
                                  'feerates': lambda v: type(v) is list and all(_opt_int(x) for x in v)}, True),
    'DRAW': ('RAW_LOG_TYPES', {'label': _str, 'value': _int, 'k': _int}, True),
    'BLOCK': FIELDS['BLOCK'] + (True,),
    'FUNDING_SENT': FIELDS['FUNDING_SENT'] + (True,),
    'GATE_START': ('RAW_LOG_GATES', {'gate': _int, 'height': _int, 'observation_id': _str}, True),
    'GATE_END': ('RAW_LOG_GATES', {'gate': _int, 'height': _int, 'status': lambda v: v in ('OBSERVED', 'EXCLUDED'),
                                   'observation_id': _str, 'block_hash': _opt_str, 'born': _strs, 'winner': _opt_str,
                                   'predicted_candidates': _int, 'observed_candidates': _int, 'code_seats': _strs},
                 True),
    'CORE_REPLAY': FIELDS['CORE_REPLAY'] + (True,),
    'GENERATED': FIELDS['GENERATED'] + (True,),
    'SCHEDULE': ('RAW_LOG_ITEM2', {'increment': _int, 'increments': _ints_of('A', 'B'),
                                   'ladders': lambda v: type(v) is list and all(_ints(x) for x in v),
                                   'rounds': _rows(k=_int, offset_seconds=_int, seats=_ints),
                                   'predicted_candidates': _int, 't_gate_seconds': _int, 'rung_seconds': _int,
                                   'l0_seat': _opt_int}, True),
    'RELEASE': ('RAW_LOG_ITEM2', {'seat': _str, 'path': _str, 'k': _int, 'txid': _hex64, 'due_ns': _int,
                                  'sent_ns': _int, 'handed_off': _bool}, True),
    'PUBLIC_SENT': ('RAW_LOG_ITEM2', {'txid': _str, 'hex': _str, 'seat': _str}, True),
    'PRIVATE_HANDOFF': ('RAW_LOG_ITEM2', {'txid': _str, 'hex': _str, 'seat': _str}, True),
    'PRIVATE_REPLACE': ('RAW_LOG_ITEM2', {'txid': _str, 'hex': _str, 'seat': _str, 'replaced': _str}, True),
    'RELEASE_MEMPOOLS': ('RAW_LOG_ITEM2', {'k': _int, 'mempools': _pools}, True),
    'REPLACED_RUNG_MISSING': ('RAW_LOG_ITEM2', {'seat': _str, 'k': _int, 'txid': _str}, False),   # waited_seconds
    'G_TIMING': ('RAW_LOG_ITEM2', {'t0_ns': _int, 'due_ns': _int, 'template_ns': _int, 'lag_ns': _int}, True),
    'TEMPLATE': ('RAW_LOG_ITEM2', {'template': lambda v: type(v) is dict and _rows(txid=_str)(v.get('transactions')),
                                   'private_set': _rows(txid=_str)}, False),
    'L0_FUNDING_BLOCK': ('RAW_LOG_L0', {'height': _int, 'block_hash': _str, 'block_hex': _str,
                                        'funding_script': _str}, True),
    'L0_LAUNCH_START': ('RAW_LOG_L0', {'seat': _str, 'kind': _str, 'attempt': _int, 'attempt_id': _str, 'h0': _int,
                                       'fee': _l0_fee, 'budget_source': _str, 'exact_height_miss': _str}, True),
    'L0_SET_CHARGED': ('RAW_LOG_L0', {'attempt_id': _str, 'budget_sha256': _str, 'fees': _ints,
                                      'rungs': _rows(k=_int, fee_sat=_int, wallet_fee_sat=_int, wallet_vsize=_int,
                                                     txid=_str),
                                      'charge_bases': lambda v: v is None or _rows(absolute_fee_sat=_int)(v)}, True),
    'L0_READY': ('RAW_LOG_L0', {'attempt_id': _str, 'rungs': _rows(k=_int, txid=_str)}, True),
    'L0_ADMISSION': ('RAW_LOG_L0', {'attempt_id': _str, 'k': _int, 'txid': _str,
                                    'nodes': lambda v: type(v) is dict and set(v) == {'A', 'B'}
                                    and all(_l0_node(x) for x in v.values()),
                                    'computed': _ints_of('k', 'f_k'),
                                    'wallet': lambda v: _ints_of('fee_sat', 'vsize')(v)
                                    and _ints_of('absolute_fee_sat')(v.get('charge_base'))}, True),
    'L0_BUDGET': ('RAW_LOG_L0', {'attempt_id': _str, 'threshold_sat_per_attempt': _str,
                                 'product': lambda v: _ints_of('max_gate_attempts', 'max_fee_per_candidate_sat',
                                                               'max_fee_exposure_sat', 'max_principal_exposure_sat')(v)
                                 and type(v.get('exact_height_miss')) is str and type(v.get('budget_sha256')) is str},
                  True),
    'L0_RELAY': ('RAW_LOG_L0', {'txid': _str, 'k': _int, 'at_relay': _bool}, True),
    'L0_LABELS': ('RAW_LOG_L0', {'attempt_id': _str, 'in_g': _opt_int, 'born': _opt_int, 'match': _bool,
                                 'exact_height_miss': _str}, True),
    'MEMPOOL': ('RAW_LOG_ITEM2', {'node': _str, 'txids': _strs}, True),
    'L0_BUDGET_COUNTERS': ('RAW_LOG_L0', {'attempt_id': _str,
                                          'counters': _ints_of('released', 'gate_attempts', 'fee_exposure_sat',
                                                               'principal_exposure_sat')}, True),
    'L0_RUNG_TEST': ('RAW_LOG_L0', {'attempt_id': _str, 'k': _int, 'txid': _str, 'when': _str}, False),
}
ITEM2_PHASES = ('SETUP', 'GATE', 'END')   # ARV1 section 20: RUN_END FAILED's phase in an item-2 run


def _dict(v) -> bool:
    return type(v) is dict


def _dicts(v) -> bool:
    return type(v) is list and all(type(x) is dict for x in v)


def _list(v) -> bool:
    return type(v) is list


# J5: the item-4 lines' fields the judge reads (ARV1 sections 22-25), with the refusal code of a wrongly typed or
# missing one and whether a float anywhere in the line is refused (False for the node answers and claim-only lines
# the judge does not read whole: a getblocktemplate answer, testmempoolaccept answers, the miner's filter record).
ITEM4_FIELDS = {
    'RUN_START': ('RAW_LOG_ITEM4', {'gates': _ints, 'params': _dict, 'miner_policy': _str, 'bidders_sha256': _str,
                                    'scenario': _str, 'depth': _opt_int, 'roles': _dict, 'fees': _dict,
                                    'project_seat': _str, 'self_fee': _opt_int, 'self_fee_rule': _opt_str}, True),
    'BIDDERS': ('RAW_LOG_ITEM4', {'bidders': _dict, 'bidders_sha256': _str, 'draws': _dicts,
                                  'feerates': lambda v: v is None or _ints(v)}, True),
    'SCENARIO_NOT_RUN': ('RAW_LOG_ITEM4', {'not_run': _rows(scenario=_str, case=_str, label=_opt_str, reason=_str)},
                         True),
    'BLOCK': FIELDS['BLOCK'] + (True,),
    'BLOCK_ACCEPTED': ('RAW_LOG_ITEM4', {'block_hash': _str}, True),
    'FUNDING_SENT': FIELDS['FUNDING_SENT'] + (True,),
    'GATE_START': ('RAW_LOG_GATES', {'gate': _int, 'height': _int, 'observation_id': _str}, True),
    'GATE_END': ('RAW_LOG_GATES', {'gate': _int, 'height': _int, 'status': lambda v: v in ('OBSERVED', 'EXCLUDED'),
                                   'observation_id': _str}, True),
    'CORE_REPLAY': ('RAW_LOG_TYPES', {'height': _int, 'next_birth': _int, 'chain': lambda v: v in ('FINAL', 'REPLACED'),
                                      'born': _strs}, True),
    'GENERATED': FIELDS['GENERATED'] + (True,),
    'SCHEDULE': ('RAW_LOG_ITEM4', {'increment': _int, 'increments': _ints_of('A', 'B'),
                                   'ladders': lambda v: type(v) is list and all(_ints(x) for x in v), 'after_g': _strs,
                                   'rule': _str}, True),
    'RELEASE': ('RAW_LOG_ITEM4', {'seat': _str, 'path': _str, 'k': _int, 'txid': _hex64, 'sent_ns': _int,
                                  'handed_off': _bool}, True),
    'PUBLIC_SENT': ('RAW_LOG_ITEM4', {'txid': _str, 'hex': _str, 'seat': _str}, True),
    'PRIVATE_HANDOFF': ('RAW_LOG_ITEM4', {'txid': _str, 'hex': _str, 'seat': _str}, True),
    'REPLACED_RUNG_MISSING': ('RAW_LOG_ITEM4', {'seat': _str, 'k': _int, 'txid': _str}, False),
    'TEMPLATE': ('RAW_LOG_ITEM4', {'template': lambda v: type(v) is dict and _rows(txid=_str)(v.get('transactions')),
                                   'private_set': _rows(txid=_str)}, False),
    'MEMPOOL': ('RAW_LOG_ITEM4', {'node': _str, 'txids': _strs}, True),
    'ASYMMETRIC_BID': ('RAW_LOG_ITEM4', {'seat': _str, 'median': _int, 'factor': _int, 'feerate': _int, 'fee': _int,
                                         'honest_feerates': _ints, 'project_configured_p0': _int, 'project_seat': _str,
                                         'project_sent': _dict}, True),
    'SELF_REGISTER': ('RAW_LOG_ITEM4', {'txid': _str, 'fee': _int, 'index': _int, 'height': _int, 'block_hash': _str,
                                        'seat': _str}, True),
    'CENSOR_WINDOW': ('RAW_LOG_ITEM4', {'first': _int, 'last': _int, 'lifted': _int, 'txids': _strs, 'outpoints': _list,
                                        'seat': _str}, True),
    'CENSOR_MEMPOOL': ('RAW_LOG_ITEM4', {'txid': _str, 'nodes': _strs, 'heights': _ints, 'blocks': _int}, True),
    'REORG': ('RAW_LOG_ITEM4', {'depth': _int, 'invalidated': _str, 'replaced': _list, 'replacement': _list}, True),
    'MINER_FILTER': ('RAW_LOG_ITEM4', {'height': _int, 'block_hash': _str}, False),
    'ITEM4_L0_OBSERVE': ('RAW_LOG_ITEM4', {'attempt_id': _str, 'turn': _str, 'phase': _str, 'height': _int,
                                           'block_hash': _str, 'labels': _rows(verdict=_str, outcome=_str),
                                           'flags': _dicts, 'released': _str}, True),
    'ITEM4_LABELS': ('RAW_LOG_ITEM4', {'turn': _str, 'height': _int, 'labels': _dicts, 'expected': _dicts,
                                       'match': _bool, 'exact_height_miss': _str}, True),
    'ITEM4_L0_RELEASE': ('RAW_LOG_ITEM4', {'attempt_id': _str, 'turn': _str, 'height': _int, 'block_hash': _str,
                                           'step': _str, 'released': _str}, True),
    'ITEM4_L0_LABEL_LINE': ('RAW_LOG_ITEM4', {'line': _dicts, 'expected': _dicts, 'match': _bool}, True),
    'L0_TURN': ('RAW_LOG_L0', {'attempt_id': _str, 'worker': _str,
                               'lines': lambda v: type(v) is dict and all(type(x) is str for x in v.values()),
                               'start_ns': _int, 'end_ns': _int}, True),
    **{event: ITEM2_FIELDS[event] for event in ('L0_FUNDING_BLOCK', 'L0_LAUNCH_START', 'L0_SET_CHARGED', 'L0_READY',
                                                'L0_ADMISSION', 'L0_BUDGET', 'L0_RELAY', 'L0_BUDGET_COUNTERS',
                                                'L0_RUNG_TEST')},
}


def check_item4_fields(obj: dict) -> None:
    """J5: an item-4 line's fields (ITEM4_FIELDS). RUN_END is DONE, EXCLUDED (a code and `excluded_gates`) or FAILED (a
    code, a phase SETUP, GATE or END, `excluded_gates`; ARV1 section 23 `item4_run`)."""
    event = obj['event']
    if event == 'RUN_END':
        status = obj.get('status')
        need(status in ('DONE', 'EXCLUDED', 'FAILED') and not has_float(obj), 'RAW_LOG_GATES')
        if status == 'FAILED':
            need(_str(obj.get('code')) and obj.get('phase') in ITEM2_PHASES and _ints(obj.get('excluded_gates')),
                 'RAW_LOG_GATES')
        elif status == 'EXCLUDED':
            need(code_word(obj.get('code')) is not None and _ints(obj.get('excluded_gates')), 'RAW_LOG_ITEM4')
        return
    if event in ITEM4_FIELDS:
        code, fields, whole = ITEM4_FIELDS[event]
        need(all(k in obj and check(obj[k]) for k, check in fields.items()) and not (whole and has_float(obj)), code)
    if event == 'GATE_END' and obj['status'] == 'EXCLUDED':
        need(code_word(obj.get('code')) is not None, 'RAW_LOG_ITEM4')
    if event == 'RELEASE' and 'sent_by' in obj:   # L0's own release (ARV1 section 22, "What L0 sent")
        need(obj['sent_by'] == L0_SENT_BY and type(obj.get('fee')) is int and type(obj.get('vsize')) is int
             and type(obj.get('attempt_id')) is str, 'RAW_LOG_L0')
    if event == 'L0_LAUNCH_START':
        need(all(type(obj[k]) is str for k in ('budget_sha256',) if k in obj), 'RAW_LOG_L0')


def check_item2_fields(obj: dict) -> None:
    """J4a: an item-2 line's fields (ITEM2_FIELDS). RUN_END is DONE, EXCLUDED (an item-2 gate code, with the code and
    its seats) or FAILED (a code, a phase SETUP, GATE or END, `excluded_gates`)."""
    event = obj['event']
    if event == 'RUN_END':
        status = obj.get('status')
        need(status in ('DONE', 'EXCLUDED', 'FAILED') and not has_float(obj), 'RAW_LOG_GATES')
        if status == 'FAILED':
            need(_str(obj.get('code')) and obj.get('phase') in ITEM2_PHASES and _ints(obj.get('excluded_gates')),
                 'RAW_LOG_GATES')
        elif status == 'EXCLUDED':
            need(code_word(obj.get('code')) is not None and _ints(obj.get('excluded_gates'))
                 and _strs(obj.get('code_seats')), 'RAW_LOG_ITEM2')
        return
    if event in ITEM2_FIELDS:
        code, fields, whole = ITEM2_FIELDS[event]
        need(all(k in obj and check(obj[k]) for k, check in fields.items()) and not (whole and has_float(obj)), code)
    if event == 'GATE_END' and obj['status'] == 'EXCLUDED':
        need(code_word(obj.get('code')) is not None, 'RAW_LOG_ITEM2')
    if event == 'RELEASE' and 'sent_by' in obj:   # L0's own release (ARV1 section 22, "What L0 sent")
        need(obj['sent_by'] == L0_SENT_BY and type(obj.get('fee')) is int and type(obj.get('vsize')) is int
             and type(obj.get('attempt_id')) is str, 'RAW_LOG_L0')
    if event == 'L0_LAUNCH_START':
        need(all(type(obj[k]) is str for k in ('budget_sha256',) if k in obj), 'RAW_LOG_L0')


def check_fields(obj: dict, experiment: str = 'ITEM1') -> None:
    event = obj['event']
    if experiment == 'ITEM2':
        return check_item2_fields(obj)
    if experiment in ITEM4_SCENARIOS:
        return check_item4_fields(obj)
    if event == 'RUN_END':   # ARV1 section 16: DONE or FAILED, with that status's fields
        status = obj.get('status')
        need(status in ('DONE', 'FAILED') and not has_float(obj), 'RAW_LOG_GATES')
        if status == 'DONE':
            need(all(check(obj[k]) for k, check in RUN_END_DONE.items() if k in obj), 'RAW_LOG_GATES')
        else:
            need(all(k in obj and check(obj[k]) for k, check in RUN_END_FAILED.items()), 'RAW_LOG_GATES')
        return
    if event in FIELDS:
        code, fields = FIELDS[event]
        need(not has_float(obj) and all(k in obj and check(obj[k]) for k, check in fields.items()), code)
        if event == 'RUN_START':
            deadline = obj.get('deadline')
            need(deadline is None or (type(deadline) is dict and type(deadline.get('clock_ns')) is int),
                 'RAW_LOG_GATES')
    if experiment == 'POOL' and event in POOL_FIELDS:
        code, fields = POOL_FIELDS[event]
        need(not has_float(obj) and all(k in obj and check(obj[k]) for k, check in fields.items()), code)


def observation_id(r: int, g: int, experiment: str = 'ITEM1') -> str:
    return 'OBS-%d%07d-G%03d' % (EXPERIMENTS.index(experiment) + 1, r, g)


def pool_rebuilt(end: dict, blocks: dict, draws: dict, ended: set) -> bool:
    """J3: ARV1 section 13's rule for a pool gate, from the lines before its GATE_END only (the collection's own
    gate state, decision 11): exactly one BLOCK line with the GATE_END's `block_hash`, at its `height`, named by no
    earlier GATE_END, whose coinbase tags equal the GATE_END's `producer_tags` (`[]` too), and exactly one DRAW
    `PRODUCER_H<height>` line, whose `producer` is the BLOCK's. These lines are driver claims: the rule only
    re-derives the collection's state; the judgement itself reads block G from the bytes (`judge_pool`)."""
    found = blocks.get(end['block_hash']) if end['block_hash'] not in ended else None
    if found is None or len(found) != 1:
        return False
    height, producer, tags = found[0]
    return (height == end['height'] and tags is not None and tags == end['producer_tags']
            and draws.get('PRODUCER_H%d' % height) == [producer])


class Scan:
    """What the judge keeps of one raw log. Every line's envelope is checked; only the lines the item-1
    judgement reads are kept. J3: a pool log (`experiment` POOL) is read the same way, with the pool events, and
    keeps per GATE_END whether the collection's rebuild rule holds (ARV1 section 13, POOL)."""

    def __init__(self, policy_sha256: str, judge_mode: str = 'EXPLORATORY', experiment: str = 'ITEM1'):
        self.policy_sha256 = policy_sha256
        self.judge_mode = judge_mode
        self.experiment = experiment
        self.events = POOL_EVENTS if experiment == 'POOL' else ITEM2_EVENTS if experiment == 'ITEM2' \
            else ITEM4_EVENTS if experiment in ITEM4_SCENARIOS else ITEM1_EVENTS
        # J4a: the item-2 lines the judge reads (J5: and an item-4 log's)
        self.item2: dict[str, list] = {event: [] for event in (ITEM4_KEPT if experiment in ITEM4_SCENARIOS
                                                                else ITEM2_KEPT)}
        self.template = None                     # J4a: the TEMPLATE line since the last BLOCK line
        self.l0_funding: list[dict] = []         # J4a: L0_FUNDING_BLOCK's block 1 (ARV1 section 22)
        self.l0_lines = 0                        # J4a: lines of the L0 seat's events
        self.pool_blocks: dict[str, list] = {}   # J3: claimed block hash -> [(claimed height, producer, tags)]
        self.pool_draws: dict[str, list] = {}    # J3: PRODUCER_H<height> -> [producer], in log order
        self.pool_draw_lines: list[dict] = []
        self.pool_ended: set[str] = set()        # J3: the block hashes earlier GATE_END lines named
        self.pool_rebuilt: dict[int, bool] = {}  # J3: GATE_END seq -> the collection's rebuild rule holds
        self.first = None
        self.envelope = None
        self.run = None
        self.lines = 0
        self.cut = False
        self.run_end = None
        self.l0_stop_after_end = None   # 2026-11-26 (A): the one line taken after RUN_END (`take_after_end`)
        self.bidders = None
        self.blocks = []
        self.rejected_blocks = 0
        self.funding = []
        self.gate_lines = []
        self.cluster_tools = []
        self.prefix_starts = []
        self.core_replay = []
        self.generated = []
        self.after_gate_end = False
        self.t_after_gate_end = None
        self.sha256 = None
        self.bytes = 0

    def take(self, obj: dict, index: int) -> None:
        if self.run_end is not None:   # ARV1 section 13 (:722-724): RAW_LOG_AFTER_END, but for one line (2026-11-26)
            self.take_after_end(obj, index)
            return
        need(all(key in obj for key in ENVELOPE), 'RAW_LOG_ENVELOPE')
        need(obj['schema'] == RAW_SCHEMA, 'RAW_LOG_SCHEMA')
        need(type(obj['seq']) is int and obj['seq'] == index, 'RAW_LOG_SEQ')
        need(type(obj['t_ns']) is int and obj['t_ns'] >= 0, 'RAW_LOG_ENVELOPE')
        event = obj['event']
        need(type(event) is str and event in self.events, 'RAW_LOG_EVENT')
        envelope = (obj['mode'], obj['evidence_status'], obj['policy_sha256'], obj['registration_sha256'])
        unit = obj['unit']
        need(type(unit) is dict and set(unit) == UNIT_KEYS and unit['cohort'] is None
             and (unit['gate'] is None or type(unit['gate']) is int), 'RAW_LOG_UNIT')
        need(unit['experiment'] == self.experiment, 'RAW_LOG_EXPERIMENT')
        if index == 1:
            need(event == 'RUN_START', 'RAW_LOG_START')
            mode = obj['mode']
            need(mode in MODES, 'RAW_LOG_MODE')
            # P2-2 (A, J1 review): a CONFIRMATORY log is never judged in EXPLORATORY mode.
            need(self.judge_mode == 'CONFIRMATORY' or (mode != 'CONFIRMATORY'
                                                        and obj['evidence_status'] != 'CONFIRMATORY'),
                 'LOG_MODE_MISMATCH', EXIT_REFUSAL)
            need(obj['evidence_status'] == ('CONFIRMATORY' if mode == 'CONFIRMATORY' else 'EXPLORATORY'),
                 'RAW_LOG_ENVELOPE')
            need(obj['policy_sha256'] == self.policy_sha256, 'RAW_LOG_POLICY_SHA256', EXIT_REFUSAL)
            registration = obj['registration_sha256']
            need(registration is None if mode != 'CONFIRMATORY'
                 else type(registration) is str and HEX64.match(registration) is not None, 'RAW_LOG_ENVELOPE')
            need(obj['labels'] == RAW_LABELS, 'RAW_LOG_ENVELOPE')
            need(int_in(unit['run'], 0, 9_999_999) and unit['gate'] is None, 'RAW_LOG_UNIT')
            need(self.experiment != 'ITEM2' or unit['run'] < ITEM2_RUN_COUNT, 'RAW_LOG_UNIT')   # J4a: r = 0 ... 199
            need(self.experiment not in ITEM4_SCENARIOS or unit['run'] < ITEM4_RUN_COUNT, 'RAW_LOG_UNIT')   # J5: r < 50
            self.first, self.envelope, self.run = obj, envelope, unit['run']
        else:
            # J5: the driver writes a line's own fields after the header (ARV1 section 2; RawLog.write), so the host
            # labels of L0_LABELS, ITEM4_LABELS and ITEM4_L0_OBSERVE stand in the envelope's `labels` key.
            need(envelope == self.envelope and (obj['labels'] == RAW_LABELS or event in OWN_LABELS_EVENTS),
                 'RAW_LOG_ENVELOPE')
            need(unit['run'] == self.run, 'RAW_LOG_UNIT')
            need(event != 'RUN_START', 'RAW_LOG_DUPLICATE_EVENT')
        check_fields(obj, self.experiment)
        if self.experiment == 'ITEM2' or self.experiment in ITEM4_SCENARIOS:
            if event in self.item2:
                self.item2[event].append(obj)
            self.l0_lines += event in L0_EVENTS or event in ITEM4_L0_EVENTS
            if event == 'TEMPLATE':
                self.template = obj
        if self.after_gate_end:
            self.t_after_gate_end, self.after_gate_end = obj['t_ns'], False
        handler = getattr(self, 'on_' + event, None)
        if handler is not None:
            handler(obj)

    def take_after_end(self, obj: dict, index: int) -> None:
        """A line after RUN_END. ARV1 section 13 (:722-724): none follows it, whatever it holds (RAW_LOG_AFTER_END),
        with one exception (2026-11-26, A): when a run is already failing and the L0 seat's stop then fails, item 2's
        and item 4's cleanup writes L0_STOP_FAILED after RUN_END (`item2_run`, `item4_run`; ARV1 :1670, :1806-1811,
        :1981). That one line is taken when all of these hold, else RAW_LOG_AFTER_END: no line was taken after
        RUN_END yet; the experiment's events hold L0_STOP_FAILED (item 2 and item 4, never ITEM1 or POOL); RUN_END's
        `status` is FAILED or EXCLUDED, not DONE (an excluded gate also fails the run: the `try` path writes RUN_END
        EXCLUDED, then raises its code); the envelope checks of any later line pass (keys, schema, `seq`, `t_ns`, line
        1's mode, evidence status, hashes and labels); the event is L0_STOP_FAILED and its `unit` the run's (gate
        null); `code` is a non-empty string, `failure` is RUN_END's `code`, and the line has no float. It is kept here
        and changes nothing else: every count, kept line and judged field stays what that RUN_END gives (only the raw
        log's own SHA-256, bytes and lines count it, as a line of the file). A stand-in log (no L0 seat) refuses it in
        `item2_l0_binding`."""
        end = self.run_end
        need(self.l0_stop_after_end is None, 'RAW_LOG_AFTER_END')   # at most one
        need('L0_STOP_FAILED' in self.events, 'RAW_LOG_AFTER_END')   # an item-2 or item-4 log
        need(end['status'] in ('FAILED', 'EXCLUDED'), 'RAW_LOG_AFTER_END')   # not DONE
        need(all(key in obj for key in ENVELOPE) and obj['schema'] == RAW_SCHEMA and type(obj['seq']) is int
             and obj['seq'] == index and type(obj['t_ns']) is int and obj['t_ns'] >= 0
             and (obj['mode'], obj['evidence_status'], obj['policy_sha256'], obj['registration_sha256'])
             == self.envelope and obj['labels'] == RAW_LABELS, 'RAW_LOG_AFTER_END')
        need(obj['event'] == 'L0_STOP_FAILED'
             and obj['unit'] == {'experiment': self.experiment, 'run': self.run, 'gate': None, 'cohort': None},
             'RAW_LOG_AFTER_END')
        code = obj.get('code')
        need(type(code) is str and code != '' and obj.get('failure') == end['code'] and not has_float(obj),
             'RAW_LOG_AFTER_END')
        self.l0_stop_after_end = obj

    def on_BIDDERS(self, obj):
        need(self.bidders is None, 'RAW_LOG_DUPLICATE_EVENT')
        self.bidders = obj

    def on_BLOCK(self, obj):
        raw = hex_bytes(obj.get('block_hex'), 'RAW_LOG_BLOCK')
        if self.experiment == 'POOL':   # J3: the collection's index of pool BLOCK lines, rejected ones included
            self.pool_blocks.setdefault(obj['block_hash'], []).append((obj['height'], obj['producer'],
                                                                       coinbase_tags(raw)))
        if obj.get('submit_result') is not None:
            self.rejected_blocks += 1
            return
        try:
            block = parse_block(raw)
        except (Malformed, KeyError):
            raise Refusal('RAW_LOG_BLOCK') from None
        block['seq'] = obj['seq']
        block['raw'] = raw   # J2: the bytes the replay worker is given
        block['claimed_height'] = obj.get('height')
        block['claimed_hash'] = obj.get('block_hash')
        block['t_ns'] = obj['t_ns']                 # J4a: a BLOCK line's t_ns is the submit time (ARV1 :90)
        block['template'], self.template = self.template, None   # J4a: the TEMPLATE line the block was built from
        self.blocks.append(block)

    def on_L0_FUNDING_BLOCK(self, obj):
        """J4a: block 1 of an item-2 run with the L0 seat is L0's funding (ARV1 section 22, `L0_FUNDING_BLOCK`), not a
        BLOCK line; it joins the chain the judge builds."""
        raw = hex_bytes(obj['block_hex'], 'RAW_LOG_L0')
        try:
            block = parse_block(raw)
        except (Malformed, KeyError):
            raise Refusal('RAW_LOG_L0') from None
        block.update(seq=obj['seq'], raw=raw, claimed_height=obj['height'], claimed_hash=obj['block_hash'],
                     t_ns=obj['t_ns'], template=None, funding_script=obj['funding_script'])
        self.l0_funding.append(block)
        self.blocks.append(block)

    def on_FUNDING_SENT(self, obj):
        raw = hex_bytes(obj.get('hex'), 'RAW_LOG_FUNDING')
        try:
            tx = parse_tx(raw)
        except (Malformed, KeyError):
            raise Refusal('RAW_LOG_FUNDING') from None
        self.funding.append({'seq': obj['seq'], 'stage': obj['stage'], 'claimed_txid': obj['txid'],
                             'tx': tx, 'labels': [tuple(o) for o in obj['outputs']]})

    def on_GATE_START(self, obj):
        self.gate_lines.append(obj)

    def on_GATE_END(self, obj):
        self.gate_lines.append(obj)
        self.after_gate_end = True
        if self.experiment == 'POOL':
            self.pool_rebuilt[obj['seq']] = pool_rebuilt(obj, self.pool_blocks, self.pool_draws, self.pool_ended)
            self.pool_ended.add(obj['block_hash'])

    def on_DRAW(self, obj):
        if self.experiment == 'POOL' and PRODUCER_LABEL.match(obj['label']) is not None:   # J3 (ARV1 section 17)
            self.pool_draws.setdefault(obj['label'], []).append(obj['producer'])
            self.pool_draw_lines.append({'seq': obj['seq'], 'label': obj['label'], 'value': obj['value'],
                                         'k': obj['k'], 'producer': obj['producer']})

    def on_CORE_REPLAY(self, obj):
        self.core_replay.append({'height': obj.get('height'), 'born': obj.get('born'), 'seq': obj['seq'],
                                 'next_birth': obj.get('next_birth'), 'state_sha256': obj.get('state_sha256'),
                                 'chain': obj.get('chain')})   # J5: an item-4 line's chain, FINAL or REPLACED

    def on_GENERATED(self, obj):
        self.generated.append({'gate': obj['unit']['gate'], 'ladder': obj.get('ladder'), 'seq': obj['seq']})

    def on_CLUSTER_TOOL(self, obj):
        self.cluster_tools.append(obj)

    def on_PREFIX_START(self, obj):
        self.prefix_starts.append(obj)

    def on_RUN_END(self, obj):
        self.run_end = obj


def parse_line(line: bytes):
    """One raw-log line as a JSON object, or None when it is cut (no LF) or does not parse."""
    if not line.endswith(b'\n'):
        return None
    try:
        text = line[:-1].decode('ascii')
        obj = loads(text, 'RAW_LOG_JSON', floats=True)
    except (UnicodeDecodeError, Refusal):
        return None
    return obj if type(obj) is dict else None


def scan_raw(path: Path, policy_sha256: str, judge_mode: str = 'EXPLORATORY', experiment: str = 'ITEM1') -> Scan:
    """Every line once, in order. A line that does not parse is refused (RAW_LOG_JSON) unless it is the last,
    which is then a cut log (ARV1 section 13: RAW_LOG_TRUNCATED, the unit EXCLUDED)."""
    scan = Scan(policy_sha256, judge_mode, experiment)
    digest = hashlib.sha256()
    with open_regular(path, 'RAW_LOG', RAW_LIMIT) as handle:
        line = handle.readline(LINE_LIMIT + 1)
        while line:
            need(len(line) <= LINE_LIMIT, 'RAW_LOG_LINE_SIZE')
            scan.bytes += len(line)
            need(scan.bytes <= RAW_LIMIT, 'RAW_LOG_SIZE')
            digest.update(line)
            following = handle.readline(LINE_LIMIT + 1)
            obj = parse_line(line)
            if obj is None:
                # ARV1 section 13 (:722-724): no line follows RUN_END, so one there is never a kill's leftover.
                need(scan.run_end is None, 'RAW_LOG_AFTER_END')
                need(not following and scan.lines > 0, 'RAW_LOG_JSON')   # (:630-633) only the last may be cut
                scan.cut = True
                break
            scan.lines += 1
            need(scan.lines <= RAW_LINES, 'RAW_LOG_SIZE')
            scan.take(obj, scan.lines)
            line = following
    need(scan.first is not None, 'RAW_LOG_EMPTY')
    scan.sha256 = digest.hexdigest()
    return scan


# ---------------------------------------------------------------------------------------------------------
# Gate accounting from the log (ARV1 sections 13 and 16; decision 11).

PREFIX_STATUSES = ('OK', 'FAILED', 'NOT_RUN')
PREFIX_NOT_RUN = ('SECRET_IN_LOG', 'LOG_BOUND', 'NO_GATE_DONE', 'NODE_A_DOWN', 'NODE_A_TIMEOUT', 'WORKER_TIMEOUT',
                  'PHASE_CLUSTER', 'PHASE_END', 'NO_CLUSTER', 'NO_OUTCOME')


def code_word(value) -> str | None:
    return value if type(value) is str and CODE_WORD.match(value) else None


def cluster_tool_ok(line: dict, gates: list[int], prefix: bool) -> bool:
    return (line.get('prefix') is prefix and line.get('gates') == gates and line.get('exit') == 0
            and type(line.get('output_bytes')) is int and line['output_bytes'] > 0)


def gate_lines(scan: Scan, n: int) -> tuple[list[int], int | None, list[int], list[int], dict, dict]:
    """The gates 0 .. n - 1 RUN_START must name, the deadline's clock, and the GATE_START and GATE_END lines: each
    names its gate's unit and observation id, starts in gate order once (before the deadline) and ends once with
    `status` OBSERVED after its start."""
    gates = list(range(n))
    first = scan.first
    need(first.get('gates') == gates, 'RAW_LOG_GATES')
    deadline = first.get('deadline')
    need(deadline is None or (type(deadline) is dict and type(deadline.get('clock_ns')) is int), 'RAW_LOG_GATES')
    clock = deadline['clock_ns'] if deadline is not None else None
    started, ended, starts, ends = [], [], {}, {}
    for line in scan.gate_lines:
        g = line.get('gate')
        need(type(g) is int and g in gates and line['unit']['gate'] == g
             and line.get('observation_id') == observation_id(scan.run, g, scan.experiment), 'RAW_LOG_GATES')
        if line['event'] == 'GATE_START':
            need(g not in starts and started == gates[:g], 'RAW_LOG_GATES')
            need(clock is None or line['t_ns'] < clock, 'RAW_LOG_GATES')
            started.append(g)
            starts[g] = line
        else:
            need(g in starts and g not in ends and line.get('status') == 'OBSERVED', 'RAW_LOG_GATES')
            ended.append(g)
            ends[g] = line
    return gates, clock, started, ended, starts, ends


def done_stop(scan: Scan, n: int, gates: list[int], clock: int | None, started: list[int],
              ended: list[int]) -> tuple[bool, int]:
    """RUN_END DONE's deadline facts (ARV1 section 13 "Deadline stop"): `deadline_reached` and `gates_not_started`
    (absent: false and []) name exactly the tail k .. n - 1, k >= 1, every gate before k started and ended; a stop
    needs the deadline and the line right after the last GATE_END stamped at or after its clock."""
    run_end = scan.run_end
    reached = run_end.get('deadline_reached', False)
    left = run_end.get('gates_not_started', [])
    k = n - len(left) if type(left) is list else -1
    need(type(reached) is bool and type(left) is list and reached == bool(left) and k > 0
         and left == gates[k:] and ended == gates[:k] and started == gates[:k], 'RAW_LOG_GATES')
    need(not reached or (clock is not None and type(scan.t_after_gate_end) is int
                         and scan.t_after_gate_end >= clock), 'RAW_LOG_GATES')
    return reached, k


def failed_end(scan: Scan, gates: list[int], ended: list[int], info: dict) -> list[int]:
    """RUN_END FAILED: `excluded_gates` holds every gate without GATE_END, and the prefix outcome is a row of ARV1
    section 16's reason table. Fills `info` with the phase, the death cause, the prefix outcome and g; returns
    `excluded_gates`."""
    run_end = scan.run_end
    listed = run_end.get('excluded_gates')
    need(type(listed) is list and all(type(g) is int and g in gates for g in listed)
         and set(gates) - set(ended) <= set(listed), 'RAW_LOG_GATES')
    status, reason = run_end.get('cluster_prefix'), run_end.get('cluster_prefix_reason')
    need(status in PREFIX_STATUSES and ((status == 'OK' and reason is None)
                                        or (status == 'NOT_RUN' and reason in PREFIX_NOT_RUN)
                                        or (status == 'FAILED' and code_word(reason) is not None)),
         'RAW_LOG_GATES')
    failed = run_end.get('failed_gate')
    info.update(run_end='FAILED', phase=run_end.get('phase'), cause=code_word(run_end.get('code')),
                cluster_prefix=status, cluster_prefix_reason=reason,
                failed_gate=failed if type(failed) is int else None)
    return listed


def gate_states(scan: Scan, n: int, killed: str | None = None) -> dict:
    """Unit and gate states re-derived from the raw log alone. `killed` is the collection's code for a unit the
    slice killed after RUN_END DONE (ARV1 section 13, P3-5), which the log itself cannot show."""
    gates, clock, started, ended, starts, ends = gate_lines(scan, n)
    run_end = scan.run_end
    info = {'unit_state': 'EXCLUDED', 'run_end': None, 'phase': None, 'cause': None, 'failed_gate': None,
            'cluster_prefix': None, 'cluster_prefix_reason': None, 'prefix': False, 'deadline_reached': False,
            'truncated': scan.cut}
    judged, cluster, stop = [], None, None
    observed: set[int] = set()
    code = 'RAW_LOG_TRUNCATED' if scan.cut else 'RUN_END_MISSING'
    if run_end is not None and run_end.get('status') == 'DONE':
        info['run_end'] = 'DONE'
        reached, k = done_stop(scan, n, gates, clock, started, ended)
        info['deadline_reached'] = reached
        stop = k if reached else None
        tools = [t for t in scan.cluster_tools if t.get('prefix') is False]
        need(len(tools) == 1 and len(scan.cluster_tools) == 1 and not scan.prefix_starts
             and cluster_tool_ok(tools[0], gates[:k], False), 'RAW_LOG_CLUSTER')
        if killed is None:
            info['unit_state'] = 'OBSERVED'
            observed, judged, cluster = set(gates[:k]), gates[:k], tools[0]
        else:
            code = killed
    elif run_end is not None and run_end.get('status') == 'FAILED':
        listed = failed_end(scan, gates, ended, info)
        status, failed = info['cluster_prefix'], run_end.get('failed_gate')
        code = info['cause'] or 'RUN_END_FAILED'
        done = gates[:len(ended)]
        tools = [t for t in scan.cluster_tools if t.get('prefix') is True]
        if (status == 'OK' and run_end.get('phase') == 'GATES' and run_end.get('cluster_failed') is False and ended
                and ended == done and len(scan.prefix_starts) == 1 and scan.prefix_starts[0].get('gates') == done
                and len(tools) == 1 and cluster_tool_ok(tools[0], done, True)
                and tools[0]['seq'] > scan.prefix_starts[0]['seq']
                and failed == (len(ended) if len(ended) < n else None)):
            need(not set(listed) & set(ended), 'RAW_LOG_GATES')
            info['prefix'] = True
            observed, judged, cluster = set(ended), done, tools[0]
    elif scan.prefix_starts:   # killed during the prefix: PREFIX_START names the death cause
        start = scan.prefix_starts[-1]
        info['cause'] = code_word(start.get('code'))
        failed = start.get('failed_gate')
        info['failed_gate'] = failed if type(failed) is int else None
        code = info['cause'] or code
    maybe = (max(started) + 1 if started else 0) if scan.cut else None
    out = []
    for g in gates:
        if g in observed:
            out.append({'gate': g, 'state': 'OBSERVED', 'code': 'PREFIX' if info['prefix'] else 'DONE'})
        elif g in starts or g == maybe:
            out.append({'gate': g, 'state': 'EXCLUDED', 'code': code})
        elif stop is not None and g >= stop:
            out.append({'gate': g, 'state': 'NOT_STARTED', 'code': 'DEADLINE_REACHED'})
        else:
            out.append({'gate': g, 'state': 'NOT_STARTED', 'code': code})
    return {'gates': out, 'info': info, 'judged': judged, 'cluster': cluster, 'starts': starts, 'ends': ends}


def pool_gate_states(scan: Scan, n: int, killed: str | None = None) -> dict:
    """J3: a pool run's unit and gate states re-derived from its raw log, as ARV1 section 13 (POOL) and section 16
    ("Which gates count", POOL) give them (decision 11): a run that ends RUN_END DONE (and was not killed after it)
    has its gates 0 .. k - 1 OBSERVED (`DONE`) and a deadline stop's gates NOT_STARTED; in any other run a gate
    with GATE_END that `excluded_gates` does not list is OBSERVED (`REBUILT_FROM_LOG`) when the collection's
    rebuild rule holds for it (`pool_rebuilt`), whatever comes after it; any other started gate is EXCLUDED with
    the death cause, and a gate never started NOT_STARTED. A truncated log so counts to its last whole GATE_END."""
    gates, clock, started, ended, starts, ends = gate_lines(scan, n)
    run_end = scan.run_end
    info = {'unit_state': 'EXCLUDED', 'run_end': None, 'phase': None, 'cause': None, 'failed_gate': None,
            'cluster_prefix': None, 'cluster_prefix_reason': None, 'prefix': False, 'deadline_reached': False,
            'truncated': scan.cut}
    stop, listed, kind = None, [], 'REBUILT_FROM_LOG'
    rebuilt = {g for g in ended if scan.pool_rebuilt.get(ends[g]['seq']) is True}
    code = 'RAW_LOG_TRUNCATED' if scan.cut else 'RUN_END_MISSING'
    if run_end is not None and run_end.get('status') == 'DONE':
        info['run_end'] = 'DONE'
        reached, k = done_stop(scan, n, gates, clock, started, ended)
        info['deadline_reached'] = reached
        stop = k if reached else None
        if killed is None:
            info['unit_state'] = 'OBSERVED'
            rebuilt, kind = set(gates[:k]), 'DONE'
        else:
            code = killed
    elif run_end is not None and run_end.get('status') == 'FAILED':
        listed = failed_end(scan, gates, ended, info)
        code = info['cause'] or 'RUN_END_FAILED'
    observed = sorted(rebuilt - set(listed))
    maybe = (max(started) + 1 if started else 0) if scan.cut else None
    out = []
    for g in gates:
        if g in observed:
            out.append({'gate': g, 'state': 'OBSERVED', 'code': kind})
        elif g in starts or g == maybe:
            out.append({'gate': g, 'state': 'EXCLUDED', 'code': code})
        elif stop is not None and g >= stop:
            out.append({'gate': g, 'state': 'NOT_STARTED', 'code': 'DEADLINE_REACHED'})
        else:
            out.append({'gate': g, 'state': 'NOT_STARTED', 'code': code})
    return {'gates': out, 'info': info, 'judged': observed, 'starts': starts, 'ends': ends}


def gate_counts(gates: list[dict]) -> dict:
    """The 10% rule's input over the run's gates (045b:572, :546; A 6549827052 Q2): missing plus EXCLUDED above a
    tenth of the gates (20 of 200) makes item 1 NOT_ESTABLISHED."""
    count = {s: sum(g['state'] == s for g in gates) for s in ('OBSERVED', 'EXCLUDED', 'NOT_STARTED')}
    lost = count['EXCLUDED'] + count['NOT_STARTED']
    return {'gates': len(gates), 'observed': count['OBSERVED'], 'excluded': count['EXCLUDED'],
            'missing': count['NOT_STARTED'], 'missing_or_excluded': lost,
            'over_10_percent': lost * EXCLUSION_DEN > EXCLUSION_NUM * len(gates)}


# ---------------------------------------------------------------------------------------------------------
# The collection (decision 11: re-derive, refuse on disagreement).

def collection_unit(blob: bytes, run: int, experiment: str = 'ITEM1') -> dict:
    doc = json_document(blob, 'COLLECTION')
    need(doc.get('schema') == COLLECTION_SCHEMA and type(doc.get('units')) is list, 'COLLECTION_SHAPE')
    unit = {'experiment': experiment, 'run': run, 'gate': None, 'cohort': None}
    found = [u for u in doc['units'] if type(u) is dict and u.get('unit') == unit]
    need(len(found) == 1, 'COLLECTION_UNIT')
    entry = found[0]
    need(type(entry.get('gates')) is list and type(entry.get('gate_counts')) is dict
         and entry.get('state') in ('OBSERVED', 'EXCLUDED'), 'COLLECTION_SHAPE')
    return entry


def compare_collection(entry: dict, states: dict) -> None:
    mine = [(g['gate'], g['state']) for g in states['gates']]
    theirs = [(g.get('gate'), g.get('state')) if type(g) is dict else None for g in entry['gates']]
    counts = gate_counts(states['gates'])
    keys = ('gates', 'observed', 'excluded', 'missing', 'missing_or_excluded')
    agree = (mine == theirs and entry['state'] == states['info']['unit_state']
             and all(entry['gate_counts'].get(k) == counts[k] for k in keys)
             and entry['gate_counts'].get('prefix') is states['info']['prefix']
             and entry['gate_counts'].get('deadline_reached') is states['info']['deadline_reached'])
    need(agree, 'COLLECTION_DISAGREES', EXIT_REFUSAL)


# ---------------------------------------------------------------------------------------------------------
# The chain, the funding and the births in block G.

class Claims:
    """Driver claims that disagree with what the judge derived from the bytes: reported, never used."""

    def __init__(self):
        self.items: list[dict] = []
        self.count = 0

    def note(self, event: str, seq, field: str, claimed, derived) -> None:
        self.count += 1
        if len(self.items) < SHOWN:
            self.items.append({'event': event, 'seq': seq, 'field': field, 'claimed': claimed, 'derived': derived})

    def record(self) -> dict:
        return {'count': self.count, 'shown': self.items}


def build_chain(scan: Scan, claims: Claims, strict: bool = True) -> dict:
    """The final chain: from the last accepted BLOCK back by previous-block hash to height 1, each height one more
    than its parent's (BIP34 height from the coinbase). Accepted blocks off that chain are counted. When no gate
    is judged (`strict` false) a log without such a chain gives an empty one instead of a refusal."""
    if not strict:
        try:
            return build_chain(scan, Claims(), True)
        except Refusal:
            return {'blocks': {}, 'where': {}, 'spends': {}, 'tip': None, 'stale': len(scan.blocks)}
    by_hash = {}
    for block in scan.blocks:
        need(block['hash'] not in by_hash, 'RAW_LOG_BLOCK_DUPLICATE')
        by_hash[block['hash']] = block
        if block['claimed_hash'] != block['hash']:
            claims.note('BLOCK', block['seq'], 'block_hash', block['claimed_hash'], block['hash'])
        if block['claimed_height'] != block['height']:
            claims.note('BLOCK', block['seq'], 'height', block['claimed_height'], block['height'])
    need(scan.blocks, 'BLOCK_CHAIN')
    chain = {}
    block = scan.blocks[-1]
    while True:
        need(block['height'] not in chain, 'BLOCK_CHAIN')
        chain[block['height']] = block
        parent = by_hash.get(block['prev'])
        if parent is None:
            break
        need(parent['height'] == block['height'] - 1, 'BLOCK_CHAIN')
        block = parent
    need(block['height'] == 1, 'BLOCK_CHAIN')
    where = {}
    spends = {}
    for height, block in chain.items():
        for tx in block['txs']:
            where[tx['txid']] = height
            for i in tx['inputs']:
                spends.setdefault((i['txid'], i['vout']), []).append((height, tx['txid']))
    return {'blocks': chain, 'where': where, 'spends': spends, 'tip': max(chain), 'stale': len(by_hash) - len(chain)}


def funding_index(scan: Scan, chain: dict, h0: int, n: int, claims: Claims) -> dict:
    """The FUNDING_SENT transactions as bytes (ARV1 sections 9 and 12): `outputs` names [wallet, gate] per output
    in output order. Run-level layout problems: not exactly one FAN_OUT, a transaction not on the chain below H0,
    an OWNER transaction that does not spend the FAN_OUT, a repeated or impossible label, or funding scripts whose
    equality does not follow the wallets (one fee key per wallet)."""
    problems = []
    outpoints, labels, txs = {}, {}, {}
    fan = [f for f in scan.funding if f['stage'] == 'FAN_OUT']
    if len(fan) != 1:
        problems.append('FAN_OUT_COUNT')
    scripts: dict[str, set] = {}
    for f in scan.funding:
        tx = f['tx']
        if f['claimed_txid'] != tx['txid']:
            claims.note('FUNDING_SENT', f['seq'], 'txid', f['claimed_txid'], tx['txid'])
        if f['stage'] not in ('FAN_OUT', 'OWNER'):
            problems.append('FUNDING_STAGE')
        height = chain['where'].get(tx['txid'])
        if height is None or height >= h0:
            problems.append('FUNDING_NOT_MINED')
        if len(f['labels']) > len(tx['outputs']):
            problems.append('FUNDING_OUTPUTS')
        txs[tx['txid']] = f
        for vout, (w, g) in enumerate(f['labels'][:len(tx['outputs'])]):
            if w not in WALLETS or not 0 <= g < n or (w, g) in labels:
                problems.append('FUNDING_LABEL')
                continue
            value, script = tx['outputs'][vout]
            labels[(w, g)] = (tx['txid'], vout)
            outpoints[(tx['txid'], vout)] = {'wallet': w, 'gate': g, 'value': value, 'stage': f['stage']}
            scripts.setdefault(w, set()).add(script)
    if any(len(s) != 1 for s in scripts.values()) or len({next(iter(s)) for s in scripts.values()}) != len(scripts):
        problems.append('FUNDING_SCRIPTS')
    if len(fan) == 1:
        fan_txid = fan[0]['tx']['txid']
        for f in scan.funding:
            if f['stage'] == 'OWNER' and [i['txid'] for i in f['tx']['inputs']] != [fan_txid]:
                problems.append('OWNER_NOT_FROM_FAN_OUT')
    else:
        fan_txid = None
    return {'problems': sorted(set(problems)), 'outpoints': outpoints, 'labels': labels, 'txs': txs,
            'fan_txid': fan_txid}


def funding_membership(plan: dict, row: dict, funding: dict) -> bool:
    """The gate's (planned winner, gate) output is in the transaction the plan puts it in: the FAN_OUT for an
    unflagged wallet, else an OWNER transaction holding only flagged wallets of that wallet's owner."""
    at = funding['labels'].get((row['wallet'], row['gate']))
    if at is None:
        return False
    f = funding['txs'][at[0]]
    if row['funding'] == 'FAN_OUT':
        return f['stage'] == 'FAN_OUT'
    return f['stage'] == 'OWNER' and all(
        w in plan['wallets'] and plan['wallets'][w]['owner'] == row['owner'] and plan['wallets'][w]['shares_ancestry']
        for w, _ in f['labels'])


def owner_split(plan: dict, scan: Scan, funding: dict) -> bool:
    """P1-1 (1), A's J1 review; ARV1 section 9 (:339-340 rejects one owner transaction per gate).
    Each owner's ancestry-flagged (wallet, gate) outputs are all in one OWNER transaction, those transactions are
    exactly the OWNER lines, and there is one per owner with a flagged seat. True when that does not hold."""
    txs_of: dict[str, set] = {}
    for (w, _g), (txid, _vout) in funding['labels'].items():
        if plan['wallets'][w]['shares_ancestry']:
            txs_of.setdefault(plan['wallets'][w]['owner'], set()).add(txid)
    owner_txs = {f['tx']['txid'] for f in scan.funding if f['stage'] == 'OWNER'}
    single = [next(iter(t)) for t in txs_of.values() if len(t) == 1]
    return not (len(single) == len(txs_of) and set(single) == owner_txs and len(owner_txs) == len(txs_of))


def ancestry_on_chain(plan: dict, judged: list[int], births: dict, funding: dict) -> bool:
    """P1-1 (2), A's J1 review; 045b:380 measures the links actually placed on chain. The gate-level ANCESTRY groups
    read from the bytes (births that spend outputs of one funding transaction other than the excluded FAN_OUT) must
    be the plan's groups (over the gates with a birth). True when they differ."""
    on_chain: dict[str, list[int]] = {}
    for g in judged:
        if g in births and births[g]['funding_txid'] != funding['fan_txid']:
            on_chain.setdefault(births[g]['funding_txid'], []).append(g)
    found = sorted(gates for gates in on_chain.values() if len(gates) >= 2)
    planned = [[g for g in group['gates'] if g in births] for group in gate_link_groups(plan, judged)
               if group['kind'] == 'ANCESTRY']
    return found != sorted(gates for gates in planned if len(gates) >= 2)


def find_birth(row: dict, height: int, chain: dict, funding: dict) -> tuple[dict | None, list[str]]:
    """EXPLORATORY birth (no replay): the one transaction in block G that spends a funding output; it must spend
    the planned (wallet, gate) output, with that one input, and that output must be spent nowhere else."""
    block = chain['blocks'].get(height)
    if block is None:
        return None, ['block_g']
    spenders = [tx for tx in block['txs'][1:]
                if any((i['txid'], i['vout']) in funding['outpoints'] for i in tx['inputs'])]
    if len(spenders) != 1:
        return None, ['winner']
    tx = spenders[0]
    planned = funding['labels'].get((row['wallet'], row['gate']))
    used = [(i['txid'], i['vout']) for i in tx['inputs']]
    if planned is None or used != [planned] or [h for h, _ in chain['spends'].get(planned, [])] != [height]:
        return tx, ['winner']
    return tx, []


# ---------------------------------------------------------------------------------------------------------
# J2: the Core replay of the final chain (ARDR_JUDGE_V1 section 17; A #258 6557890079 decision 1).

def replay_argv(replay_bin: Path | None) -> list[str]:
    """The fixed argv of one worker call: the prebuilt test binary the workflow built once, or cargo, which
    builds it on the first call. No shell runs it, and no part of it comes from an input but the binary path."""
    tail = ['--exact', REPLAY_TEST, '--ignored', '--test-threads=1']
    if replay_bin is None:
        return ['cargo', 'test', '--locked', '-q', '-p', 'bitagi-signer', '--test', REPLAY_TARGET, '--', *tail]
    return [str(replay_bin), '-q', *tail]


def run_worker(argv: list[str], request: bytes) -> bytes:
    """One worker call: the request in a new private directory, the answer read back (at most 16 MiB). A worker
    that cannot start, ends non-zero or writes no answer is REPLAY_WORKER_FAILED (exit 3, as ARV1 section 14's
    PREREQUISITE WORKER_FAILED); one that runs past its time is REPLAY_WORKER_TIMEOUT (exit 3, as ARV1's PREREQUISITE
    WORKER_TIMEOUT; section 29: the timeout keeps its own code). Its own output goes to stderr only."""
    with tempfile.TemporaryDirectory(prefix='ardr-judge-replay-') as tmp:
        request_path, answer_path = Path(tmp) / 'request.txt', Path(tmp) / 'answer.txt'
        request_path.write_bytes(request)
        env = {k: v for k, v in os.environ.items() if not k.startswith('BITAGI_ARDR_JUDGE_REPLAY_')}
        env.update({REPLAY_REQUEST_ENV: str(request_path), REPLAY_ANSWER_ENV: str(answer_path)})
        try:
            done = subprocess.run(argv, cwd=ROOT, env=env, stdin=subprocess.DEVNULL, capture_output=True,
                                  timeout=REPLAY_SECONDS, check=False)
        except subprocess.TimeoutExpired:
            raise Refusal('REPLAY_WORKER_TIMEOUT', EXIT_PREREQUISITE) from None
        except (OSError, subprocess.SubprocessError):
            raise Refusal('REPLAY_WORKER_FAILED', EXIT_PREREQUISITE) from None
        if done.returncode != 0:
            sys.stderr.write(done.stderr[-4000:].decode('utf-8', 'replace'))
        need(done.returncode == 0, 'REPLAY_WORKER_FAILED', EXIT_PREREQUISITE)
        try:
            with open(answer_path, 'rb') as handle:
                data = handle.read(REPLAY_ANSWER_LIMIT + 1)
        except OSError:
            raise Refusal('REPLAY_WORKER_FAILED', EXIT_PREREQUISITE) from None
    return data


def replay_request(h0: int, prestate: str | None, blocks: list[dict], events: bool = False) -> bytes:
    """One worker request (section 17); with `events` the V2 head and the same body (J6a, section 31)."""
    lines = [REPLAY_REQUEST_HEAD_V2 if events else REPLAY_REQUEST_HEAD, f'PROFILE\tregtest\t{h0}',
             'PRESTATE\t' + (prestate or '-')]
    lines += [f'BLOCK\t{b["height"]}\t{b["raw"].hex()}' for b in blocks]
    lines.append(f'END\t{len(blocks)}')
    return ('\n'.join(lines) + '\n').encode('ascii')


def parse_answer(data: bytes, blocks: list[dict], events: bool = False) -> dict:
    """The worker's answer, read strictly: one ROW per block sent, in order, at its height, with the hash the
    judge computed, born txids that are transactions of that block, the POSTSTATE of the last block whose SHA-256
    is the last row's, and END. A REFUSED answer is REPLAY_REFUSED (exit 2: the product decoder or the Core
    refused the bytes); any other shape is REPLAY_ANSWER (exit 4: A's own worker answered wrongly).

    J6a (section 31): with `events` the answer must be V2 (its head also on a REFUSED answer): each ROW is followed by
    its block's EVENT lines, read by `answer_events`, END gives both counts, and each row gets its `events`."""
    need(len(data) <= REPLAY_ANSWER_LIMIT and data.endswith(b'\n') and data.isascii() and b'\r' not in data,
         'REPLAY_ANSWER', EXIT_INTERNAL)
    lines = data[:-1].decode('ascii').split('\n')
    need(lines[0] == (REPLAY_ANSWER_HEAD_V2 if events else REPLAY_ANSWER_HEAD), 'REPLAY_ANSWER', EXIT_INTERNAL)
    if len(lines) == 2 and lines[1].startswith('REFUSED\t'):
        code = code_word(lines[1].split('\t', 1)[1])
        need(code is not None, 'REPLAY_ANSWER', EXIT_INTERNAL)
        sys.stderr.write(f'replay worker refused: {code}\n')
        raise Refusal('REPLAY_REFUSED')
    groups = None
    if events:   # the V1 checks below then read the ROW, POSTSTATE and END lines alone
        lines, groups = event_groups(lines)
    need(len(lines) == len(blocks) + 3, 'REPLAY_ANSWER', EXIT_INTERNAL)
    rows = []
    for block, line in zip(blocks, lines[1:-2]):
        f = line.split('\t')
        need(len(f) == 6 and f[0] == 'ROW' and f[1] == str(block['height']) and f[2] == block['hash'], 'REPLAY_ANSWER',
             EXIT_INTERNAL)
        born = [] if f[3] == '-' else f[3].split(',')
        txids = {tx['txid'] for tx in block['txs']}
        need(all(HEX64.match(t) and t in txids for t in born) and len(set(born)) == len(born), 'REPLAY_ANSWER',
             EXIT_INTERNAL)
        need(DECIMAL.match(f[4]) is not None and HEX64.match(f[5]) is not None, 'REPLAY_ANSWER', EXIT_INTERNAL)
        rows.append({'height': block['height'], 'block_hash': f[2], 'born': born, 'next_birth': int(f[4]),
                     'state_sha256': f[5]})
    post = lines[-2].split('\t')
    need(len(post) == 4 and post[0] == 'POSTSTATE' and post[1] == str(blocks[-1]['height'])
         and post[2] == blocks[-1]['hash'] and post[3] and HEX.match(post[3]) is not None
         and sha256(bytes.fromhex(post[3])) == rows[-1]['state_sha256'], 'REPLAY_ANSWER', EXIT_INTERNAL)
    need(lines[-1] == f'END\t{len(blocks)}', 'REPLAY_ANSWER', EXIT_INTERNAL)
    if groups is not None:
        for row, block, group in zip(rows, blocks, groups):
            row['events'] = answer_events(group, row, block)
    return {'rows': rows, 'poststate': post[3]}


def event_groups(lines: list[str]) -> tuple[list[str], list[list[str]]]:
    """A V2 answer's lines (J6a, section 31) split into the V1 shape (head, ROW lines, POSTSTATE, `END <rows>`) and
    the EVENT lines under each ROW. The body is ROW lines, each followed by zero or more EVENT lines; the last line is
    `END <ROW lines> <EVENT lines>`. Else REPLAY_ANSWER (exit 4)."""
    body = lines[1:-2]
    at = [i for i, line in enumerate(body) if line.startswith('ROW\t')]
    events = len(body) - len(at)
    need(len(lines) >= 4 and at[:1] == [0] and all(line.startswith('EVENT\t') for line in body if line[:4] != 'ROW\t')
         and lines[-1] == f'END\t{len(at)}\t{events}', 'REPLAY_ANSWER', EXIT_INTERNAL)
    groups = [body[a + 1:b] for a, b in zip(at, at[1:] + [len(body)])]
    return [lines[0]] + [body[i] for i in at] + [lines[-2], f'END\t{len(at)}'], groups


def answer_events(lines: list[str], row: dict, block: dict) -> list[dict]:
    """One block's EVENT lines of a V2 answer (J6a, section 31), read strictly, as typed events. Each line is
    `EVENT <height> <tx_index|-> <kind> <register txid> <cause|-> <anchor|->`:

    - the height is the row's; the kind is one of EVENT_CAUSES with one of its causes; the register txid is 64
      lowercase hex;
    - the tx_index is `-` exactly for a Stage 0 ending (ENDED with MAX_AGE or TIMEOUT), else a transaction of the block
      that is not its coinbase;
    - the Anchor `<txid>:<vout>` is `-` exactly for BROKEN; BORN's is its own REGISTER's vout 1 (the transaction at its
      tx_index, whose txid is the register txid); BEAT's is the BEAT transaction's vout 1; a Stage 1 ENDED's is an
      outpoint its transaction spends.

    The order is the Core's: the Stage 0 endings first, in ascending CURRENT Anchor (internal byte order, then vout);
    then the transactions in block order, each with one BORN, one BEAT, or a break: its ENDED (BROKEN) rows, then a
    BROKEN row for each of the same Hearts in the same order, all BROKEN_ONE for one Heart or BROKEN_ALL for two or
    more. The BORN Hearts are the row's born txids, in order. Anything else is REPLAY_ANSWER (exit 4)."""
    out = []
    for line in lines:
        f = line.split('\t')
        need(len(f) == 7 and f[0] == 'EVENT' and f[1] == str(row['height']) and f[3] in EVENT_CAUSES
             and HEX64.match(f[4]) is not None and f[5] in EVENT_CAUSES[f[3]], 'REPLAY_ANSWER', EXIT_INTERNAL)
        stage0 = f[3] == 'ENDED' and f[5] in STAGE0_CAUSES
        need((f[2] == '-') if stage0 else (DECIMAL.match(f[2]) is not None and 1 <= int(f[2]) < len(block['txs'])),
             'REPLAY_ANSWER', EXIT_INTERNAL)
        tx = None if stage0 else block['txs'][int(f[2])]
        anchor = EVENT_ANCHOR.match(f[6])
        need((f[6] == '-') if f[3] == 'BROKEN' else (anchor is not None and int(anchor[2]) < 1 << 32),
             'REPLAY_ANSWER', EXIT_INTERNAL)
        anchor = None if anchor is None else (anchor[1], int(anchor[2]))
        if f[3] == 'BORN':
            need(tx['txid'] == f[4] and anchor == (f[4], 1), 'REPLAY_ANSWER', EXIT_INTERNAL)
        elif f[3] == 'BEAT':
            need(anchor == (tx['txid'], 1), 'REPLAY_ANSWER', EXIT_INTERNAL)
        elif f[3] == 'ENDED' and not stage0:
            need(anchor in [(i['txid'], i['vout']) for i in tx['inputs']], 'REPLAY_ANSWER', EXIT_INTERNAL)
        out.append({'height': row['height'], 'tx_index': None if stage0 else int(f[2]), 'kind': f[3],
                    'register_txid': f[4], 'cause': None if f[5] == '-' else f[5],
                    'anchor': None if anchor is None else {'txid': anchor[0], 'vout': anchor[1]}})
    endings = [e for e in out if e['tx_index'] is None]   # Stage 0's
    order = [(bytes.fromhex(e['anchor']['txid'])[::-1], e['anchor']['vout']) for e in endings]
    need(out[:len(endings)] == endings and order == sorted(order) and len(set(order)) == len(order), 'REPLAY_ANSWER',
         EXIT_INTERNAL)
    groups: list[list[dict]] = []
    for e in out[len(endings):]:
        if groups and groups[-1][0]['tx_index'] == e['tx_index']:
            groups[-1].append(e)
        else:
            need(not groups or groups[-1][0]['tx_index'] < e['tx_index'], 'REPLAY_ANSWER', EXIT_INTERNAL)
            groups.append([e])
    for group in groups:
        kinds = [e['kind'] for e in group]
        if kinds in (['BORN'], ['BEAT']):
            continue
        k = len(group) // 2
        hearts = [e['register_txid'] for e in group]
        cause = 'BROKEN_ONE' if k == 1 else 'BROKEN_ALL'
        need(k >= 1 and len(group) == 2 * k and len(set(hearts[:k])) == k and hearts[:k] == hearts[k:]
             and all(e['kind'] == 'ENDED' and e['cause'] == 'BROKEN' for e in group[:k])
             and all(e['kind'] == 'BROKEN' and e['cause'] == cause for e in group[k:]), 'REPLAY_ANSWER', EXIT_INTERNAL)
    need([e['register_txid'] for e in out if e['kind'] == 'BORN'] == row['born'], 'REPLAY_ANSWER', EXIT_INTERNAL)
    return out


def event_fields(event: dict) -> list[str]:
    """An event's first five fields as the worker writes them, `[height, tx_index|-, kind, register txid, cause|-]`:
    B's EVENTS row, and so a HEART_EVENTS row (section 31)."""
    return [str(event['height']), '-' if event['tx_index'] is None else str(event['tx_index']), event['kind'],
            event['register_txid'], event['cause'] or '-']


def chain_events(rows: dict, blocks: list[dict]) -> list[dict]:
    """Every event of a V2 replay from H0 (the empty state as of H0 - 1), in order, checked across the chunks (J6a,
    section 31): a Heart's first row is its BORN, and its CURRENT Anchor is then the BORN's Anchor and after each BEAT
    the BEAT's; each BEAT and break (ENDED BROKEN and BROKEN) spends that Anchor in its transaction; an ENDED names it
    as the final Anchor, at most once per Heart; after its ENDED a Heart has no row but the BROKEN row of the same
    transaction. Anything else is REPLAY_ANSWER (exit 4)."""
    txs = {block['height']: block['txs'] for block in blocks}
    current: dict[str, tuple[str, int]] = {}
    ended: dict[str, tuple[int, int | None]] = {}
    out = []
    for height in sorted(rows):
        for e in rows[height]['events']:
            heart, kind = e['register_txid'], e['kind']
            spent = [] if e['tx_index'] is None else [(i['txid'], i['vout'])
                                                      for i in txs[height][e['tx_index']]['inputs']]
            if heart in ended:
                need(kind == 'BROKEN' and ended[heart] == (height, e['tx_index']), 'REPLAY_ANSWER', EXIT_INTERNAL)
                ended[heart] = (height, -1)   # its one BROKEN row is read
            elif kind == 'BORN':
                need(heart not in current, 'REPLAY_ANSWER', EXIT_INTERNAL)
                current[heart] = (heart, 1)
            else:
                need(heart in current and kind != 'BROKEN', 'REPLAY_ANSWER', EXIT_INTERNAL)
                anchor = current[heart]
                need((e['tx_index'] is None or anchor in spent)
                     and (kind == 'BEAT' or (e['anchor']['txid'], e['anchor']['vout']) == anchor), 'REPLAY_ANSWER',
                     EXIT_INTERNAL)
                if kind == 'BEAT':
                    current[heart] = (e['anchor']['txid'], e['anchor']['vout'])
                else:
                    del current[heart]
                    ended[heart] = (height, e['tx_index'])
            out.append(e)
    return out


def replay_chain(chain: dict, h0: int, argv: list[str], events: bool = False) -> dict:
    """The final chain from H0 to its tip (build_chain: from the last accepted BLOCK back by previous-block hash),
    replayed in chunks; each chunk starts on the poststate of the one before, the first on the empty initial state
    as of H0 - 1 (the worker accepts that only at H0).

    J6a (section 31): with `events` every request is V2; each row then holds its block's `events`, and the result adds
    `answer` V2 and `events`, every event in order (`chain_events`). Without it the requests, rows and result are V1's,
    unchanged: items 1, 2 and 4 and the pool run never ask for events."""
    blocks = [chain['blocks'][h] for h in sorted(chain['blocks']) if h >= h0]
    chunks, size = [], 0
    for block in blocks:
        if not chunks or len(chunks[-1]) == REPLAY_CHUNK_BLOCKS or size + 2 * len(block['raw']) > REPLAY_CHUNK_HEX:
            chunks.append([])
            size = 0
        chunks[-1].append(block)
        size += 2 * len(block['raw'])
    rows, state = {}, None
    for chunk in chunks:
        request = replay_request(h0, state, chunk, events)
        need(len(request) <= REPLAY_REQUEST_LIMIT, 'REPLAY_REQUEST_SIZE')
        answer = parse_answer(run_worker(argv, request), chunk, events)
        rows.update((row['height'], row) for row in answer['rows'])
        state = answer['poststate']
    result = {'rows': rows, 'calls': len(chunks), 'first_height': blocks[0]['height'] if blocks else None,
              'last_height': blocks[-1]['height'] if blocks else None,
              'poststate_sha256': sha256(bytes.fromhex(state)) if state is not None else None}
    if events:
        result.update(answer='V2', events=chain_events(rows, blocks))
    return result


HEART_EVENTS_CHECKS = ('tiling', 'rows', 'poststate', 'state_dep')


def heart_events_check(lines: list[dict], replay: dict, h0: int, claims: Claims) -> list[str]:
    """J6a (section 31; J6 plan section 2.5): the driver's HEART_EVENTS lines (claims: one per B-worker EVENTS answer,
    each with `first`, `last`, `rows` of `[height, tx_index|-, kind, register_txid, cause|-]` as B's worker wrote
    them, `poststate_height`, `poststate_sha256` and `state_dep`) against the judge's own V2 replay (`replay_chain`
    with events; the facts):

    - `tiling`: the lines' `first` ... `last` tile the replay's first height (H0) to its last (the tip), in order, with
      no gap or overlap;
    - `rows`: a line's rows are the judge's events at heights `first` ... `last`, the first five fields of each
      (`event_fields`), in the same order;
    - `poststate`: `poststate_height` is `last` and `poststate_sha256` is the judge's ROW state digest at `last`;
    - `state_dep`: `state_dep` is the Regtest deployment id at H0, hex (`item2_deployment_id`).

    Each difference is a driver claim; the facts are never changed. Returns the checks that differ, in the order
    above. A line whose span is not two ints within the replay is a `tiling` difference only."""
    found: set[str] = set()

    def differs(check: str, seq, field: str, claimed, derived) -> None:
        found.add(check)
        claims.note('HEART_EVENTS', seq, field, claimed, derived)
    at: dict[int, list[list[str]]] = {}
    for e in replay['events']:
        at.setdefault(e['height'], []).append(event_fields(e))
    low, tip, dep = replay['first_height'], replay['last_height'], item2_deployment_id(h0).hex()
    if low is None:   # nothing replayed: no line can tile it
        low, tip = 0, -1
    expect = low
    for line in lines:
        seq, first, last = line.get('seq'), line.get('first'), line.get('last')
        if not (type(first) is int and type(last) is int and low <= first <= last <= tip):
            differs('tiling', seq, 'first_last', [first, last], [expect, None])
            expect = None   # the next line's start cannot be known
            continue
        if expect is not None and first != expect:
            differs('tiling', seq, 'first', first, expect)
        expect = last + 1
        derived = [r for h in range(first, last + 1) for r in at.get(h, [])]
        claimed = line.get('rows')
        if claimed != derived:
            rows = claimed if type(claimed) is list else []
            i = next((k for k, (a, b) in enumerate(zip(rows, derived)) if a != b), min(len(rows), len(derived)))
            differs('rows', seq, 'rows', {'count': len(rows) if type(claimed) is list else claimed, 'at': i,
                                          'row': rows[i] if i < len(rows) else None},
                    {'count': len(derived), 'at': i, 'row': derived[i] if i < len(derived) else None})
        if line.get('poststate_height') != last:
            differs('poststate', seq, 'poststate_height', line.get('poststate_height'), last)
        if line.get('poststate_sha256') != replay['rows'][last]['state_sha256']:
            differs('poststate', seq, 'poststate_sha256', line.get('poststate_sha256'),
                    replay['rows'][last]['state_sha256'])
        if line.get('state_dep') != dep:
            differs('state_dep', seq, 'state_dep', line.get('state_dep'), dep)
    if expect != tip + 1:
        differs('tiling', None, 'last', None if expect is None else expect - 1, tip)
    return [check for check in HEART_EVENTS_CHECKS if check in found]


def replay_fields(states: dict, births: dict, replay: dict, tip: int | None) -> tuple[dict[int, list[str]], list]:
    """Per judged gate (ARDR_JUDGE_V1 section 17): `replay_birth` unless the Core bore exactly one Heart at its
    height G and that Heart is the REGISTER the judge found in block G; `replay_next_birth` unless G is the Core's
    next birth height after the gate before (gate 0: H0, J1's `height`); `replay_other_birth` for a birth at a
    height that is no judged gate's G, from G0 up to the height before the first started gate that is not judged
    (else the tip), charged to the gate whose interval holds it. Returns the fields and the births the replay
    found outside every judged gate's height."""
    judged = states['judged']
    height = {g: states['starts'][g].get('height') for g in judged}
    rows = replay['rows']
    fields: dict[int, list[str]] = {}
    for g in judged:
        row = rows.get(height[g]) if type(height[g]) is int else None
        if row is None or g not in births or row['born'] != [births[g]['txid']]:
            fields.setdefault(g, []).append('replay_birth')
        if g > 0:
            before = rows.get(height[g - 1]) if type(height[g - 1]) is int else None
            if before is None or before['next_birth'] != height[g]:
                fields.setdefault(g, []).append('replay_next_birth')
    gate_heights = sorted((h, g) for g, h in height.items() if type(h) is int)
    later = [line.get('height') for g, line in states['starts'].items() if g not in height]
    later = [h for h in later if type(h) is int]
    end = min(later) - 1 if later else tip
    other = []
    for h in sorted(rows):
        if not rows[h]['born'] or h in {gh for gh, _ in gate_heights}:
            continue
        other.append({'height': h, 'born': rows[h]['born']})
        if judged and end is not None and h <= end:
            owner = max((g for gh, g in gate_heights if gh <= h), default=judged[0])
            fields.setdefault(owner, []).append('replay_other_birth')
    return fields, other


# ---------------------------------------------------------------------------------------------------------
# Expected reports and repeat-winner counts (CLV1 section 5; 045b 4.4).

def runs_of(sequence: list, gates: list[int]) -> list[dict]:
    """R1: per cluster C, every maximal interval of gates each won by C or unknown (None) that holds a gate won by
    C; a project gate or another cluster's gate ends it. R3: every maximal interval of unknown gates, as UNKNOWN."""
    found = []
    clusters = sorted({c for c in sequence if isinstance(c, str)})
    for cluster in clusters:
        i = 0
        while i < len(sequence):
            if sequence[i] != cluster and sequence[i] is not None:
                i += 1
                continue
            j = i
            while j < len(sequence) and (sequence[j] == cluster or sequence[j] is None):
                j += 1
            won = [k for k in range(i, j) if sequence[k] == cluster]
            if won:
                found.append({'cluster': cluster, 'first_gate': gates[i], 'last_gate': gates[j - 1],
                              'length': j - i, 'first_won': gates[won[0]],
                              'unknown_gates': [gates[k] for k in range(i, j) if sequence[k] is None]})
            i = j
    i = 0
    while i < len(sequence):
        if sequence[i] is not None:
            i += 1
            continue
        j = i
        while j < len(sequence) and sequence[j] is None:
            j += 1
        found.append({'cluster': UNKNOWN, 'first_gate': gates[i], 'last_gate': gates[j - 1], 'length': j - i,
                      'first_won': gates[i], 'unknown_gates': gates[i:j]})
        i = j
    return found


def expected_reports(sequence: list, gates: list[int], thresholds: list[int], project=frozenset()) -> dict:
    """One report per run of length >= T: trigger_gate = max(first_gate + T - 1, the run's first gate won by C),
    sorted by (trigger_gate, cluster). `sequence` holds each gate's cluster (None: unknown); a gate in `project`
    is in no run and breaks every run (CLV1 :130-136, reading (b)). Item 1 has no project gate."""
    found = runs_of([PROJECT if g in project else c for c, g in zip(sequence, gates)], gates)
    out = {}
    for t in thresholds:
        rows = [{'cluster': run['cluster'], 'threshold': t, 'trigger_gate': max(run['first_gate'] + t - 1,
                                                                                run['first_won']),
                 'first_gate': run['first_gate'], 'last_gate': run['last_gate'], 'length': run['length'],
                 'unknown_gates': run['unknown_gates']} for run in found if run['length'] >= t]
        out[str(t)] = sorted(rows, key=lambda row: (row['trigger_gate'], row['cluster']))
    return out


def repeat_winner(sequence: list, gates: list[int]) -> dict:
    """045b 4.5 repeat-winner concentration: the top cluster's gates and the longest known-cluster run under R1,
    with every winning gate counted as its cluster's, project gates included (CLV1 :162-165), so `sequence` holds
    the cluster of a project gate too; UNKNOWN runs are not counted."""
    counts: dict[str, int] = {}
    for c in sequence:
        if isinstance(c, str):
            counts[c] = counts.get(c, 0) + 1
    top = max(counts.values(), default=0)
    known = [run['length'] for run in runs_of(sequence, gates) if run['cluster'] != UNKNOWN]
    return {'known_gates': sum(counts.values()), 'unknown_gates': sum(c is None for c in sequence),
            'top_cluster_gates': top, 'top_clusters': sorted(c for c, n in counts.items() if n == top),
            'longest_run': max(known, default=0)}


def fraction(num: int, den: int) -> dict:
    return {'num': num, 'den': den, 'undefined': True} if den == 0 else {'num': num, 'den': den}


# ---------------------------------------------------------------------------------------------------------
# D2-2's output and inputs, read from the CLUSTER_TOOL line.

REPORT_KEYS = {'cluster', 'threshold', 'trigger_gate', 'first_gate', 'last_gate', 'length', 'unknown_gates'}
REPEAT_KEYS = {'known_gates', 'unknown_gates', 'top_cluster_gates', 'top_clusters', 'longest_run'}


def canonical_input(doc) -> str:
    """The SHA-256 of a D2-2 input file as the converter writes it (ARV1 section 15: sorted keys, indent 1, LF)."""
    return sha256((json.dumps(doc, sort_keys=True, indent=1) + '\n').encode('ascii'))


def d2_2_output(line: dict, judged: list[int]) -> tuple[dict | None, str | None]:
    """D2-2's output document, or the reason it is malformed (a tooling defect: its reports cannot be read). The
    line's own SHA-256 and byte count must match the text (else the log is refused)."""
    text = line.get('output')
    need(type(text) is str, 'RAW_LOG_CLUSTER')
    blob = text.encode('ascii', 'strict') if text.isascii() else None
    need(blob is not None and line.get('output_sha256') == sha256(blob) and line.get('output_bytes') == len(blob),
         'RAW_LOG_CLUSTER')
    try:
        doc = loads(text, 'D2_2_JSON')
    except Refusal:
        return None, 'json'
    if type(doc) is not dict or doc.get('schema') != CLUSTER_OUTPUT_SCHEMA:
        return None, 'schema'
    if type(doc.get('incomplete')) is not bool:
        return None, 'incomplete'
    truncated = doc.get('walk_truncated')
    if not (type(truncated) is list and all(type(g) is int and g in judged for g in truncated)):
        return None, 'walk_truncated'
    if doc['incomplete'] is not bool(truncated):   # CLV1 section 7: `incomplete` is "walk_truncated not empty"
        return None, 'incomplete'
    part = doc.get('gates')
    if not (type(part) is dict and type(part.get('unknown')) is list and part.get('project') == []
            and all(type(g) is int and g in judged for g in part['unknown'])):
        return None, 'gates'
    inputs = doc.get('inputs')
    if type(inputs) is not dict or not all(type(inputs.get(k)) is str
                                           for k in ('gates_sha256', 'method_sha256', 'truth_sha256')):
        return None, 'inputs'
    links = doc.get('links')
    if type(links) is not list or not all(
            type(link) is dict and link.get('kind') in ('ANCESTRY', 'ANCHOR_KEY') and type(link.get('gates')) is list
            and len(link['gates']) == 2 and all(type(g) is int and g in judged for g in link['gates'])
            and link['gates'][0] < link['gates'][1] for link in links):
        return None, 'links'
    for name in ('link_based', 'ownership'):
        part = doc.get(name)
        if type(part) is not dict or type(part.get('reports')) is not dict:
            return None, name
        if set(part['reports']) != {str(t) for t in REPORT_THRESHOLDS}:
            return None, name + '_thresholds'
        for t, rows in part['reports'].items():
            if type(rows) is not list or not all(
                    type(row) is dict and set(row) == REPORT_KEYS and type(row['cluster']) is str
                    and all(type(row[f]) is int for f in ('threshold', 'trigger_gate', 'first_gate', 'last_gate',
                                                          'length'))
                    and row['threshold'] == int(t) and type(row['unknown_gates']) is list
                    and all(type(g) is int for g in row['unknown_gates'])   # #648 Codex r4436087755: hashable first
                    and set(row['unknown_gates']) <= set(doc['gates']['unknown']) for row in rows):
                return None, name + '_reports'
        if type(part.get('repeat_winner')) is not dict or set(part['repeat_winner']) != REPEAT_KEYS:
            return None, name + '_repeat_winner'
    return doc, None


def check_d2_2_inputs(line: dict, doc: dict, judged: list[int], plan: dict, births: dict, chain: dict,
                      method: dict, funding: dict) -> tuple[list[str], dict[int, list[str]], dict]:
    """The three documents the driver gave D2-2 (CLUSTER_TOOL `inputs`), bound to D2-2's output by their SHA-256,
    against the judge's own facts. Returns run-level fields, per-gate fields and diagnostics."""
    run, per_gate, notes = [], {}, {}
    inputs = line.get('inputs')
    if not (type(inputs) is dict and set(inputs) == {'cluster_truth', 'gates', 'method'}
            and all(type(v) is dict for v in inputs.values())):
        return ['d2_2_inputs'], per_gate, notes
    bound = (canonical_input(inputs['gates']) == doc['inputs']['gates_sha256']
             and canonical_input(inputs['method']) == doc['inputs']['method_sha256']
             and canonical_input(inputs['cluster_truth']) == doc['inputs']['truth_sha256'])
    if not bound:
        run.append('d2_2_inputs')
    rows = {row['gate']: row for row in plan['winners']}
    gate_rows = inputs['gates'].get('gates')
    if inputs['gates'].get('schema') != GATES_SCHEMA or type(gate_rows) is not list or \
            [r.get('gate') if type(r) is dict else None for r in gate_rows] != judged:
        run.append('d2_2_inputs')
    else:
        for r in gate_rows:
            g = r['gate']
            born = births.get(g)
            block = chain['blocks'].get(born['height']) if born else None
            if not (born and r.get('winner_txid') == born['txid'] and r.get('project') is False
                    and block is not None and r.get('block_hash') == block['hash']):
                per_gate.setdefault(g, []).append('d2_2_winner')
    m = inputs['method']
    values = method['values']
    want = {'schema': CLUSTER_METHOD_SCHEMA,
            'boundary': {'floor_height': values['floor_height'], 'excluded_txids': [funding['fan_txid']]},
            'max_depth': values['max_depth'], 'max_window_blocks': values['max_window_blocks'],
            'thresholds': values['thresholds']}
    if m != want:
        run.append('d2_2_method')
    truth = inputs['cluster_truth']
    told = truth.get('winners')
    owners = {w: plan['wallets'][w]['owner'] for w in WALLETS}
    # A gate whose birth is missing already carries its own field; its truth row is not judged again here.
    if not (truth.get('schema') == CLUSTER_TRUTH_SCHEMA and type(told) is dict and len(told) == len(judged)
            and all(told.get(births[g]['txid']) == rows[g]['wallet'] for g in judged if g in births)
            and truth.get('owners') == owners):
        run.append('d2_2_truth')
    links = truth.get('planted_links')
    if type(links) is list and all(type(l) is dict and type(l.get('wallets')) is list
                                   and all(type(w) is str for w in l['wallets']) for l in links):
        winning = {rows[g]['wallet'] for g in judged}
        found = UnionFind(sorted(winning))
        for l in links:
            members = sorted({w for w in l['wallets'] if w in winning})
            for w in members[1:]:
                found.union(members[0], w)
        notes['truth_planted_pairs_agree'] = pairs_of(found.groups()) == planted_pairs(plan, judged)
    else:
        notes['truth_planted_pairs_agree'] = False
    return sorted(set(run)), per_gate, notes


def report_key(clustering: str, row: dict) -> tuple:
    return (clustering, row['cluster'], row['threshold'], row['trigger_gate'])


def compare_reports(expected: dict, observed: dict) -> dict:
    """Missing, extra and wrong-gate reports on the key (clustering, cluster id, threshold, trigger_gate) (decision
    3); first/last/length, unknown gates and the list order are diagnostics only."""
    exp, obs = [], []
    for clustering in ('link_based', 'ownership'):
        for t in sorted(expected[clustering], key=int):
            exp += [(report_key(clustering, row), row) for row in expected[clustering][t]]
            obs += [(report_key(clustering, row), row) for row in observed[clustering][t]]
    left = [key for key, _ in obs]
    missing = []
    for key, _ in exp:
        if key in left:
            left.remove(key)
        else:
            missing.append(key)
    extra = list(left)
    wrong = []
    for key in list(missing):
        for other in extra:
            if other[:3] == key[:3]:
                wrong.append({'clustering': key[0], 'cluster': key[1], 'threshold': key[2],
                              'expected_trigger_gate': key[3], 'reported_trigger_gate': other[3],
                              'late': other[3] > key[3]})
                missing.remove(key)
                extra.remove(other)
                break
    exp_rows = dict(exp)
    differences = [{'key': list(key), 'expected': {f: exp_rows[key][f] for f in ('first_gate', 'last_gate', 'length',
                                                                                  'unknown_gates')},
                    'reported': {f: row[f] for f in ('first_gate', 'last_gate', 'length', 'unknown_gates')}}
                   for key, row in obs if key in exp_rows
                   and any(row[f] != exp_rows[key][f] for f in ('first_gate', 'last_gate', 'length', 'unknown_gates'))]
    order = all([report_key(c, r) for r in observed[c][t]] == [report_key(c, r) for r in expected[c][t]]
                for c in ('link_based', 'ownership') for t in expected[c])
    return {'missing': [list(k) for k in missing], 'extra': [list(k) for k in extra], 'wrong_gate': wrong,
            'field_differences': differences[:SHOWN], 'order_agrees': order}


def metrics(links: list[dict], wallet_of: dict[int, str], plan: dict, judged: list[int]) -> dict:
    """D: D2-2's links lifted to wallets and closed; P_L: the judge's planted pairs; P_O: same-owner pairs of
    winning wallets (CLV1 section 6, 045b:392-399)."""
    winners = sorted(set(wallet_of.values()))
    detected = UnionFind(winners)
    for link in links:
        detected.union(wallet_of[link['gates'][0]], wallet_of[link['gates'][1]])
    d = pairs_of(detected.groups())
    p_l = planted_pairs(plan, judged)
    by_owner: dict[str, list[str]] = {}
    for w in winners:
        by_owner.setdefault(plan['wallets'][w]['owner'], []).append(w)
    p_o = pairs_of(sorted(by_owner.values()))
    return {'observed_wallets': len(winners), 'detected_pairs': len(d), 'planted_pairs': len(p_l),
            'same_owner_pairs': len(p_o),
            'link_recall': fraction(len(d & p_l), len(p_l)), 'link_precision': fraction(len(d & p_l), len(d)),
            'ownership_recall': fraction(len(d & p_o), len(p_o)),
            'unlinkable_share': fraction(len(p_o - p_l), len(p_o)),
            'missed_planted_pairs': [list(p) for p in sorted(p_l - d)][:SHOWN],
            'false_pairs': [list(p) for p in sorted(d - p_l)][:SHOWN]}


def below(value: dict, minimum: dict) -> bool:
    """A defined fraction below the minimum (exact; a 0/0 value is neither below nor above)."""
    return 'undefined' not in value and value['num'] * minimum['den'] < minimum['num'] * value['den']


# ---------------------------------------------------------------------------------------------------------
# The judgement.

def bidder_seats(scan: Scan) -> dict:
    """The BIDDERS list's seats per gate number (ARV1 section 11), for the gates listed with an int number."""
    bidders = scan.bidders['bidders'] if scan.bidders is not None and type(scan.bidders.get('bidders')) is dict \
        else None
    listed = {}
    if bidders is not None and bidders.get('schema') == BIDDERS_SCHEMA and type(bidders.get('gates')) is list:
        listed = {e['gate']: e.get('seats') for e in bidders['gates']   # a hashable int key only (#648)
                  if type(e) is dict and type(e.get('gate')) is int}
    return listed


def one_public_seat(seats, wallet: str) -> bool:
    """ARV1 sections 16 and 17: one PUBLIC SYNTHETIC seat, held by `wallet`."""
    return (type(seats) is list and len(seats) == 1 and type(seats[0]) is dict
            and set(seats[0]) == {'seat', 'kind', 'wallet', 'path'} and type(seats[0]['seat']) is str
            and seats[0]['kind'] == 'SYNTHETIC' and seats[0]['wallet'] == wallet and seats[0]['path'] == 'PUBLIC')


def check_gates(plan: dict, states: dict, scan: Scan, chain: dict, funding: dict, h0: int,
                claims: Claims) -> tuple[dict[int, list[str]], dict]:
    """Per judged gate, the plan-vs-bytes fields that differ (decision 4), and the births found."""
    rows = {row['gate']: row for row in plan['winners']}
    listed = bidder_seats(scan)
    fields: dict[int, list[str]] = {}
    births: dict[int, dict] = {}
    previous = None
    for g in states['judged']:
        row, start, end = rows[g], states['starts'][g], states['ends'][g]
        bad = []
        height = start.get('height')
        if not (type(height) is int and end.get('height') == height
                and (height == h0 if g == 0 else type(previous) is int and height > previous)):
            bad.append('height')
        if previous is not None and g > 0 and states['ends'][g - 1].get('next_birth') != height:
            claims.note('GATE_END', states['ends'][g - 1]['seq'], 'next_birth',
                        states['ends'][g - 1].get('next_birth'), height)
        previous = height if type(height) is int else previous
        if not one_public_seat(listed.get(g), row['wallet']):
            bad.append('bidders')   # ARV1 section 16: one PUBLIC SYNTHETIC seat per gate, the gate's winner
        if not funding_membership(plan, row, funding):
            bad.append('funding')
        tx, found = find_birth(row, height, chain, funding) if type(height) is int else (None, ['block_g'])
        bad += found
        if tx is not None and not found:
            births[g] = {'txid': tx['txid'], 'height': height, 'anchor': anchor_program(tx),
                         'funding_txid': tx['inputs'][0]['txid']}
            if births[g]['anchor'] is None:
                bad.append('register_shape')
            spent = funding['outpoints'][(tx['inputs'][0]['txid'], tx['inputs'][0]['vout'])]
            if spent['value'] - sum(v for v, _ in tx['outputs']) != plan['rung0_fee']:
                bad.append('fee')
            block = chain['blocks'][height]
            if end.get('winner_txid') != tx['txid']:
                claims.note('GATE_END', end['seq'], 'winner_txid', end.get('winner_txid'), tx['txid'])
            if end.get('block_hash') != block['hash']:
                claims.note('GATE_END', end['seq'], 'block_hash', end.get('block_hash'), block['hash'])
        if end.get('wallet') != row['wallet']:
            claims.note('GATE_END', end['seq'], 'wallet', end.get('wallet'), row['wallet'])
        if bad:
            fields[g] = bad
    # Anchor-key equality structure: gates with one planned label share one vout[1] program, others differ.
    by_label: dict[str, set] = {}
    for g, born in births.items():
        if born['anchor'] is not None:
            by_label.setdefault(rows[g]['anchor_label'], set()).add(born['anchor'])
    owner_of_key: dict[str, list[str]] = {}
    for label, keys in by_label.items():
        for key in keys:
            owner_of_key.setdefault(key, []).append(label)
    for g, born in births.items():
        label = rows[g]['anchor_label']
        if born['anchor'] is not None and (len(by_label[label]) != 1 or len(owner_of_key[born['anchor']]) != 1):
            fields.setdefault(g, []).append('anchor_key')
    return fields, births


def check_run(plan: dict, policy: dict, scan: Scan, funding: dict) -> list[str]:
    """Run-level plan-vs-log fields (decision 4)."""
    out = log_run_fields(policy, scan, MINER_POLICY, plan['gates'])
    if funding['problems']:
        out.append('funding_layout')
    return out


def log_run_fields(policy: dict, scan: Scan, miner_policy: str, n: int) -> list[str]:
    """The run fields RUN_START and BIDDERS carry: the params, the miner policy, the bidder list's SHA-256 and its
    gates 0 .. n - 1 in list order (ARV1 sections 11 and 16)."""
    out = []
    first = scan.first
    if first.get('params') != policy['params']:
        out.append('params')
    if first.get('miner_policy') != miner_policy:
        out.append('miner_policy')
    bidders = scan.bidders
    if not (bidders is not None and type(bidders.get('bidders')) is dict
            and bidders.get('bidders_sha256') == sha256(canonical(bidders['bidders']))
            and first.get('bidders_sha256') == bidders.get('bidders_sha256')):
        out.append('bidders_sha256')
    listed = bidders.get('bidders') if bidders is not None else None
    if not (type(listed) is dict and set(listed) == {'schema', 'gates'} and listed['schema'] == BIDDERS_SCHEMA
            and type(listed['gates']) is list
            and [e.get('gate') if type(e) is dict else None for e in listed['gates']] == list(range(n))):
        out.append('bidders_list')   # ARV1 section 11: consecutive gates in list order, here 0 .. n - 1
    return out


def core_replay_claims(scan: Scan, states: dict, births: dict, replay: dict | None, claims: Claims) -> None:
    """The driver's CORE_REPLAY lines as claims: with the replay, against A's replay of the same bytes (J2); without
    it, `born` against the births found in block G."""
    gate_heights = {line.get('height') for line in states['starts'].values()}
    for item in scan.core_replay:
        if replay is not None:   # J2: the driver's own replay lines against A's replay of the same bytes
            row = replay['rows'].get(item['height'])
            for field in ('born', 'next_birth', 'state_sha256') if row is not None else ():
                if item[field] != row[field]:
                    claims.note('CORE_REPLAY', item['seq'], field, item[field], row[field])
            continue
        born = item['born']
        expect = [b['txid'] for b in births.values() if b['height'] == item['height']]
        if type(born) is list and (expect or item['height'] not in gate_heights) and born != expect:
            claims.note('CORE_REPLAY', item['seq'], 'born', born, expect)


def replay_summary(replay: dict | None, replay_other: list) -> dict | None:
    """The record's `replay` (section 13): null unless the chain was replayed."""
    if replay is None:
        return None
    born = [{'height': h, 'txid': t} for h in sorted(replay['rows']) for t in replay['rows'][h]['born']]
    return {'first_height': replay['first_height'], 'last_height': replay['last_height'],
            'rows': len(replay['rows']), 'calls': replay['calls'], 'poststate_sha256': replay['poststate_sha256'],
            'birth_count': len(born), 'births': born[:SHOWN], 'outside_judged_gates': replay_other[:SHOWN]}


def judge_item1(policy: dict, method: dict, scan: Scan, prereg: dict, collection: dict | None, mode: str,
                replay_with: list[str] | None = None, d2_2_registered: str | None = None) -> dict:
    """The item-1 judgement. `replay_with` is the worker argv (None: --no-replay, EXPLORATORY only)."""
    n = policy['params']['gates_per_run']
    h0 = policy['params']['H0']
    claims = Claims()
    killed = None
    if collection is not None and collection['state'] == 'EXCLUDED' and scan.run_end is not None \
            and scan.run_end.get('status') == 'DONE' and not scan.cut:
        killed = code_word(collection.get('code')) or 'UNIT_TIMEOUT'
    states = gate_states(scan, n, killed)
    if collection is not None:
        compare_collection(collection, states)
    plan = item1_plan(policy['seed'], scan.run, n, policy['params']['b'])
    judged = states['judged']
    gates = states['gates']
    rows = {row['gate']: row for row in plan['winners']}
    chain = build_chain(scan, claims, strict=bool(judged))
    funding = funding_index(scan, chain, h0, n, claims)
    run_fields = check_run(plan, policy, scan, funding)
    gate_fields, births = check_gates(plan, states, scan, chain, funding, h0, claims)
    replay, replay_other = None, []
    if replay_with is not None and judged:
        replay = replay_chain(chain, h0, replay_with)
        extra, replay_other = replay_fields(states, births, replay, chain['tip'])
        for g, fields in extra.items():
            gate_fields.setdefault(g, []).extend(fields)
    if owner_split(plan, scan, funding):
        run_fields.append('OWNER_SPLIT')
    if judged and ancestry_on_chain(plan, judged, births, funding):
        run_fields.append('ANCESTRY_ON_CHAIN')
    core_replay_claims(scan, states, births, replay, claims)
    for item in scan.generated:
        if item['gate'] in rows and item['ladder'] != [plan['rung0_fee']]:
            claims.note('GENERATED', item['seq'], 'ladder', item['ladder'], [plan['rung0_fee']])
    nogo, not_established, run_codes = [], [], []
    comparison = {'evaluated': False, 'not_evaluated_reason': None}
    expected = None
    doc, malformed = (None, None)
    if states['cluster'] is not None:
        doc, malformed = d2_2_output(states['cluster'], judged)
    if doc is not None:
        d_run, d_gate, notes = check_d2_2_inputs(states['cluster'], doc, judged, plan, births, chain, method, funding)
        run_fields += d_run
        for g, fields in d_gate.items():
            gate_fields.setdefault(g, []).extend(fields)
        comparison['diagnostics'] = notes
        if doc['incomplete'] is True:
            run_codes.append('D2_2_INCOMPLETE')
        # CLV1 section 3 (:71-72): a gate D2-2 lists as unknown had no known winner; CLV1:146-148: a Class T
        # campaign plants none, so one is a logging gap and the run counts as an exclusion.
        if doc['gates']['unknown']:
            run_codes.append('D2_2_UNKNOWN_GATES')
        if any(row['cluster'] == UNKNOWN for part in ('link_based', 'ownership')
               for rows_t in doc[part]['reports'].values() for row in rows_t):
            run_codes.append('D2_2_UNKNOWN_REPORT')
    run_fields = [f for f in RUN_FIELDS if f in run_fields]
    for g in list(gate_fields) + (judged if run_fields else []):   # run fields first, then the gate's own in order
        gate_fields[g] = run_fields + [f for f in GATE_FIELDS if f in gate_fields.get(g, [])]
    mismatched = sorted(g for g in judged if gate_fields.get(g))
    if judged:
        groups = gate_link_groups(plan, judged)
        link_of = link_clusters(judged, groups)
        owner_seq = [rows[g]['owner'] for g in judged]
        link_seq = [link_of[g] for g in judged]
        members: dict[str, list[int]] = {}
        for g in judged:
            members.setdefault(link_of[g], []).append(g)
        expected = {'link_groups': groups,
                    'link_clusters': [{'id': c, 'gates': gs} for c, gs in sorted(members.items(),
                                                                                key=lambda item: item[1][0])],
                    'reports': {'link_based': expected_reports(link_seq, judged, REPORT_THRESHOLDS),
                                'ownership': expected_reports(owner_seq, judged, REPORT_THRESHOLDS)},
                    'repeat_winner': {'link_based': repeat_winner(link_seq, judged),
                                      'ownership': repeat_winner(owner_seq, judged)},
                    'planted_pairs': [list(p) for p in sorted(planted_pairs(plan, judged))][:SHOWN]}
    if states['cluster'] is not None and doc is None:
        if mismatched:
            comparison['not_evaluated_reason'] = 'JUDGE_PLAN_MISMATCH'
            not_established.append('COMPARISON_NOT_EVALUATED:JUDGE_PLAN_MISMATCH')
        else:
            nogo.append('D2_2_OUTPUT_MALFORMED:' + malformed)
    elif doc is not None and not run_codes and mismatched:
        comparison['not_evaluated_reason'] = 'JUDGE_PLAN_MISMATCH'
        not_established.append('COMPARISON_NOT_EVALUATED:JUDGE_PLAN_MISMATCH')
    elif doc is not None and not run_codes:
        wallet_of = {g: rows[g]['wallet'] for g in judged}
        measured = metrics(doc['links'], wallet_of, plan, judged)
        comparison['metrics'] = measured
        comparison['evaluated'] = True
        comparison['reports'] = compare_reports(expected['reports'],
                                                {part: doc[part]['reports'] for part in ('link_based', 'ownership')})
        comparison['repeat_winner'] = {
            part: {'judge': expected['repeat_winner'][part], 'd2_2': doc[part]['repeat_winner'],
                   'agree': expected['repeat_winner'][part] == doc[part]['repeat_winner']}
            for part in ('link_based', 'ownership')}
        d2 = doc.get('metrics')
        comparison['diagnostics']['d2_2_metrics_agree'] = type(d2) is dict and all(
            d2.get(k) == measured[k] for k in ('link_recall', 'link_precision', 'ownership_recall', 'unlinkable_share'))
        reports = comparison['reports']
        if reports['missing']:
            nogo.append('REPORT_MISSING')
        if reports['extra']:
            nogo.append('REPORT_EXTRA')
        if reports['wrong_gate']:
            nogo.append('REPORT_WRONG_GATE')
        # 045b:400-405 and A's #258 correction of decision 12: a 0/0 metric is neither 1 nor 0, so that metric
        # alone is NOT_ESTABLISHED for the run. It excludes no gate and stops neither the report comparison nor
        # the other metric; a defined value below 1 is NO-GO (045b:380).
        status = {}
        for name, code, minimum in (('link_recall', 'LINK_RECALL_BELOW_1', LINK_RECALL_MIN),
                                    ('link_precision', 'LINK_PRECISION_BELOW_1', LINK_PRECISION_MIN)):
            if 'undefined' in measured[name]:
                status[name] = 'NOT_ESTABLISHED'
                not_established.append('METRIC_UNDEFINED:' + name)
            elif below(measured[name], minimum):
                status[name] = 'BELOW_1'
                nogo.append(code)
            else:
                status[name] = 'MET'
        comparison['metric_status'] = status
    if run_codes:
        comparison['evaluated'] = False
        comparison['not_evaluated_reason'] = run_codes[0]
        not_established += ['RUN_EXCLUDED:' + c for c in run_codes]
    for entry in gates:
        g = entry['gate']
        row = rows[g]
        replayed = replay['rows'].get(births[g]['height']) if replay is not None and g in births else None
        entry.update(observation_id=observation_id(scan.run, g), wallet=row['wallet'],
                     born_txid=births[g]['txid'] if g in births else None,
                     height=births[g]['height'] if g in births else None,
                     next_birth=replayed['next_birth'] if replayed is not None else None,
                     mismatches=gate_fields.get(g, []))
        if entry['state'] == 'OBSERVED' and gate_fields.get(g):
            entry.update(state='EXCLUDED', code='JUDGE_PLAN_MISMATCH:' + gate_fields[g][0])
        elif entry['state'] == 'OBSERVED' and run_codes:
            entry.update(state='EXCLUDED', code=run_codes[0])
    counts = gate_counts(gates)
    if counts['over_10_percent']:
        not_established.append('TEN_PERCENT_RULE')
    if not judged:
        not_established.append('NO_JUDGED_GATES')
    result = 'NO_GO' if nogo else 'NOT_ESTABLISHED' if not_established else 'GO'
    labels = list(RECORD_LABELS) + (['EXPLORATORY_NOT_A_VERDICT'] if mode != 'CONFIRMATORY' else [])
    if replay_with is None:
        births_label = 'UNVERIFIED_NO_REPLAY'
    else:
        births_label = 'REPLAYED' if replay is not None else 'NOT_REPLAYED_NO_JUDGED_GATE'
    replay_record = replay_summary(replay, replay_other)
    outcome = {'result': result, 'nogo': nogo, 'not_established': sorted(set(not_established))}
    return {
        'schema': JUDGEMENT_SCHEMA, 'labels': labels, 'item': 'ITEM1', 'mode': mode,
        'evidence_status': 'CONFIRMATORY' if mode == 'CONFIRMATORY' else 'EXPLORATORY',
        'log_mode': scan.first['mode'], 'log_evidence_status': scan.first['evidence_status'],
        'births': births_label, 'replay': replay_record,
        'judge': {'unit': 'J2', 'tool_sha256': sha256(TOOL_PATH.read_bytes())},
        'inputs': {'policy_sha256': policy['sha256'], 'method_policy_sha256': method['sha256'],
                   'method_policy_path': method['path'], 'method_drafted': method['drafted'],
                   'raw_log_sha256': scan.sha256, 'raw_log_bytes': scan.bytes, 'raw_log_lines': scan.lines,
                   'collection_given': collection is not None, 'prereg_045b': prereg,
                   'd2_2_tool_sha256': states['cluster']['tool_sha256'] if states['cluster'] is not None else None,
                   'd2_2_tool_registered_sha256': d2_2_registered,
                   'registration_sha256': scan.first['registration_sha256']},
        'thresholds': threshold_table(),
        'unit': {'experiment': 'ITEM1', 'run': scan.run, 'registered_runs': policy['count']},
        'params': dict(policy['params'], source=policy['params_source']),
        'plan': {'plan_sha256': plan['plan_sha256'], 'planted_owner': plan['planted_owner'],
                 'planted_wallets': plan['planted_wallets'], 'base_wallets': plan['base_wallets'],
                 'rung0_fee': plan['rung0_fee'], 'wallets': plan['wallets'],
                 'winners': [{k: row[k] for k in ('gate', 'wallet', 'source', 'draw', 'heart', 'anchor_label',
                                                  'funding')} for row in plan['winners']]},
        'run_shape': dict(states['info'], judged_gates=len(judged), chain_tip=chain['tip'],
                          stale_blocks=chain['stale'], rejected_blocks=scan.rejected_blocks,
                          funding_problems=funding['problems'], run_mismatches=run_fields,
                          collection_code=collection_code(collection)),
        'gates': gates, 'gate_counts': counts,
        'expected': expected, 'comparison': comparison, 'driver_claims': claims.record(),
        'outcome': outcome,
        'verdict': verdict_block(outcome, item1_criterion(), item1_observed(comparison, counts)),
    }


# ---------------------------------------------------------------------------------------------------------
# The command.

def registered_log(args, policy: dict, method_blob: bytes | None, experiment: str) -> dict:
    """CONFIRMATORY: the binding checks of ARV1 sections 3, 15 and 18 (the method policy's only when there is one,
    ITEM1), with the registration's coverage of the experiment (section 30); then (J2) the replay (REPLAY_NOT_BUILT
    with --no-replay) and the collection (COLLECTION_REQUIRED). Returns the registration."""
    need(args.registration is not None, 'REGISTRATION_MISSING', EXIT_PREREQUISITE)
    reg_blob = read_file(args.registration, 'REGISTRATION', REGISTRATION_LIMIT)
    registration, listed = parse_registration(reg_blob)
    registered_experiment(registration, experiment)
    need(policy['sha256'] in listed, 'POLICY_NOT_REGISTERED', EXIT_REFUSAL)
    if method_blob is not None:
        need(sha256(method_blob) in listed, 'METHOD_POLICY_NOT_REGISTERED', EXIT_REFUSAL)
    with open_regular(args.raw, 'RAW_LOG', RAW_LIMIT) as handle:
        first = parse_line(handle.readline(LINE_LIMIT + 1))
    need(first is not None, 'RAW_LOG_JSON')
    need(first.get('evidence_status') == 'CONFIRMATORY', 'RAW_LOG_NOT_CONFIRMATORY', EXIT_REFUSAL)
    need(first.get('policy_sha256') == policy['sha256'], 'RAW_LOG_POLICY_SHA256', EXIT_REFUSAL)
    need(first.get('registration_sha256') == sha256(reg_blob), 'REGISTRATION_BYTES_CHANGED', EXIT_REFUSAL)
    need(not args.no_replay, 'REPLAY_NOT_BUILT', EXIT_PREREQUISITE)
    need(args.collection is not None, 'COLLECTION_REQUIRED', EXIT_PREREQUISITE)
    return registration


def confirmatory_binding(args, policy: dict, method_blob: bytes) -> str:
    """ITEM1 CONFIRMATORY: `registered_log`, then the registration's D2-2 file hash (D2_2_TOOL_NOT_REGISTERED,
    REGISTRATION_D2_2_TOOL). Returns that hash."""
    registration = registered_log(args, policy, method_blob, 'ITEM1')
    registered = registered_d2_2_sha256(registration)
    need(registered is not None, 'D2_2_TOOL_NOT_REGISTERED', EXIT_PREREQUISITE)
    return registered


def item1(args) -> dict:
    mode = args.mode
    if mode == 'EXPLORATORY':
        need(args.registration is None, 'EXPLORATORY_REGISTRATION')
    need(not (args.no_replay and args.replay_bin is not None), 'REPLAY_OPTIONS')
    prereg = read_prereg(args.prereg)
    if mode == 'CONFIRMATORY':
        covering_registration(args, 'ITEM1')
    policy_blob = read_file(args.policy, 'POLICY', POLICY_LIMIT)
    policy = parse_policy(policy_blob, mode)
    method_blob = read_file(args.method_policy, 'METHOD_POLICY', METHOD_LIMIT)
    method = parse_method_policy(method_blob, mode, policy['method_policy'])
    registered = confirmatory_binding(args, policy, method_blob) if mode == 'CONFIRMATORY' else None
    # The workflow path (section 18): the D2-2 file's bytes at the judged run's own commit.
    at_commit = sha256(read_file(args.d2_2_tool_at_commit, 'D2_2_FILE', PREREG_LIMIT)) \
        if args.d2_2_tool_at_commit is not None else None
    collection_blob = read_file(args.collection, 'COLLECTION', COLLECTION_LIMIT) if args.collection else None
    scan = scan_raw(args.raw, policy['sha256'], mode)
    if mode == 'CONFIRMATORY':   # J2: every D2-2 run in the log is the registered file
        need(all(line['tool_sha256'] == registered for line in scan.cluster_tools), 'D2_2_TOOL_SHA256',
             EXIT_REFUSAL)
    if at_commit is not None:    # and, in any mode, the file at the run's commit: the D2-2 code that actually ran
        need(all(line['tool_sha256'] == at_commit for line in scan.cluster_tools), 'D2_2_TOOL_NOT_AT_RUN_COMMIT',
             EXIT_REFUSAL)
    collection = collection_unit(collection_blob, scan.run) if collection_blob is not None else None
    record = judge_item1(policy, method, scan, prereg, collection, mode,
                         None if args.no_replay else replay_argv(args.replay_bin), registered)
    record['inputs']['d2_2_tool_at_run_commit_sha256'] = at_commit
    if collection_blob is not None:
        record['inputs']['collection_sha256'] = sha256(collection_blob)
    return record


# ---------------------------------------------------------------------------------------------------------
# J3: the pool run (ARDR_JUDGE_V1 section 19; 045b :504, :545, :560; ARV1 sections 13, 16 and 17). The judge reads
# each pool gate's block G from the bytes: the block at the gate height G on the final chain, the one REGISTER
# there spending the seat's funding output, and the producer tag in its coinbase, checked against the judge's own
# PRODUCER_H<G> draw. The Herfindahl index is the experiment's (`experiment`); per run it is description only.

POOL_GATE_FIELDS = ('height', 'bidders', 'block_g', 'winner', 'fee', 'producer', 'replay_birth', 'replay_next_birth',
                    'replay_other_birth')
POOL_RUN_FIELDS = ('params', 'miner_policy', 'bidders_sha256', 'bidders_list')
POOL_RECORD_LABELS = ['CLASS_T', 'REGTEST', 'JUDGE_RECORD', 'J3_POOL_RUN']
PRODUCER_MISSING = 'PRODUCER_MISSING'   # 045b :504, :545: block G without exactly one tag, excluded and counted
POOL_RUN_RESULT = 'NOT_A_VERDICT_PER_RUN'   # 045b :545: per-run values are descriptive only and not judged


def pool_wallet(g: int) -> str:
    """The pool seat's wallet: W<gate mod 40> (ARV1 section 17, DEFAULT)."""
    return WALLETS[g % len(WALLETS)]


def drawn_producer(seed: bytes, r: int, height: int) -> dict:
    """The producer of block `height` in pool run r: the draw PRODUCER_H<height> (n = 100), A below 50, B below
    80, else C (045b :560; ARV1 section 6)."""
    value, k = draw(seed, 'POOL', r, 'PRODUCER_H%d' % height, PRODUCER_DRAW['n'])
    letter = 'A' if value < PRODUCER_DRAW['A_below'] else 'B' if value < PRODUCER_DRAW['B_below'] else 'C'
    return {'producer': letter, 'value': value, 'k': k}


def herfindahl(counts: dict) -> dict:
    """The Herfindahl index of the producer counts as an exact fraction: the sum of n_p^2 over N^2 (0/0 undefined)."""
    total = sum(counts.values())
    return fraction(sum(n * n for n in counts.values()), total * total)


def above_hhi_max(index: dict) -> bool:
    """045b :504: a Herfindahl index above 1/2 (strictly); an undefined one is not above."""
    return 'undefined' not in index and index['num'] * HHI_MAX['den'] > HHI_MAX['num'] * index['den']


def check_pool_gates(policy: dict, states: dict, scan: Scan, chain: dict, funding: dict,
                     claims: Claims) -> tuple[dict[int, list[str]], dict, dict]:
    """Per judged pool gate, the plan-vs-bytes fields that differ (decision 4), the births found and what block G
    holds. `height`: G0 = H0, each later G above the gate before's; `bidders`: one PUBLIC SYNTHETIC seat W<g mod
    40>; `block_g`, `winner`: as item 1 (section 7), for the seat's (wallet, gate) funding output; `fee`: rung 0
    at feerate b; `producer`: block G's one tag is not the drawn producer of G."""
    seed, h0 = policy['seed'], policy['params']['H0']
    fee = -(-policy['params']['b'] * CANDIDATE_VSIZE // 1000)
    listed = bidder_seats(scan)
    fields: dict[int, list[str]] = {}
    births: dict[int, dict] = {}
    found: dict[int, dict] = {}
    for g in states['judged']:
        start, end, wallet = states['starts'][g], states['ends'][g], pool_wallet(g)
        before = states['starts'][g - 1].get('height') if g > 0 else None   # gate g - 1 started before g
        bad = []
        height = start.get('height')
        if not (type(height) is int and end.get('height') == height
                and (height == h0 if g == 0 else type(before) is int and height > before)):
            bad.append('height')
        if not one_public_seat(listed.get(g), wallet):
            bad.append('bidders')
        tx, missed = find_birth({'wallet': wallet, 'gate': g}, height, chain, funding) if type(height) is int \
            else (None, ['block_g'])
        bad += missed
        block = chain['blocks'].get(height) if type(height) is int else None
        tags = script_tags(block['txs'][0]['inputs'][0]['script']) if block is not None else None
        drawn = drawn_producer(seed, scan.run, height) if block is not None else None
        if tx is not None and not missed:
            births[g] = {'txid': tx['txid'], 'height': height}
            spent = funding['outpoints'][(tx['inputs'][0]['txid'], tx['inputs'][0]['vout'])]
            if spent['value'] - sum(v for v, _ in tx['outputs']) != fee:
                bad.append('fee')
            if end.get('winner_txid') != tx['txid']:
                claims.note('GATE_END', end['seq'], 'winner_txid', end.get('winner_txid'), tx['txid'])
        if tags is not None and len(tags) == 1 and tags[0] != drawn['producer']:
            bad.append('producer')
        if block is not None:
            if end.get('block_hash') != block['hash']:
                claims.note('GATE_END', end['seq'], 'block_hash', end.get('block_hash'), block['hash'])
            if end.get('producer_tags') != tags:
                claims.note('GATE_END', end['seq'], 'producer_tags', end.get('producer_tags'), tags)
        if end.get('wallet') != wallet:
            claims.note('GATE_END', end['seq'], 'wallet', end.get('wallet'), wallet)
        found[g] = {'height': height if block is not None else None,
                    'block_hash': block['hash'] if block is not None else None, 'tags': tags, 'drawn': drawn}
        if bad:
            fields[g] = bad
    return fields, births, found


def pool_replay_fields(states: dict, births: dict, replay: dict) -> tuple[dict[int, list[str]], list]:
    """The replay's gate fields for the judged pool gates, whose set need not be a prefix (a pool gate counts by
    itself, ARV1 section 16): `replay_birth` and `replay_next_birth` as section 17 (gate g's G against the Core's
    next birth after block G of gate g - 1, which started before it); `replay_other_birth` for a birth at a height
    that is no started gate's G, charged to the judged gate whose interval [G, the next started gate's G) holds it.
    Returns the fields and the births outside every judged gate's height."""
    judged = states['judged']
    height = {g: line.get('height') for g, line in states['starts'].items()}
    rows = replay['rows']
    fields: dict[int, list[str]] = {}
    for g in judged:
        row = rows.get(height[g]) if type(height[g]) is int else None
        if row is None or g not in births or row['born'] != [births[g]['txid']]:
            fields.setdefault(g, []).append('replay_birth')
        if g > 0:
            before = rows.get(height[g - 1]) if type(height[g - 1]) is int else None
            if before is None or before['next_birth'] != height[g]:
                fields.setdefault(g, []).append('replay_next_birth')
    started = sorted((h, g) for g, h in height.items() if type(h) is int)
    judged_heights = {height[g] for g in judged if type(height[g]) is int}
    other = []
    for h in sorted(rows):
        if not rows[h]['born'] or h in judged_heights:
            continue
        other.append({'height': h, 'born': rows[h]['born']})
        # The started gate whose interval holds h (a gate that is not judged, at its own G, holds its own birth).
        owner = max((pair for pair in started if pair[0] <= h), default=None)
        if owner is not None and owner[1] in judged:
            fields.setdefault(owner[1], []).append('replay_other_birth')
    return fields, other


def judge_pool(policy: dict, scan: Scan, prereg: dict, collection: dict | None, mode: str,
               replay_with: list[str] | None = None) -> dict:
    """One pool run's judgement record (section 19). Per gate: the collection's state re-derived (decision 11), then
    a judged gate whose bytes differ from the plan is EXCLUDED JUDGE_PLAN_MISMATCH:<field> (decision 4), and one
    whose block G does not carry exactly one producer tag is EXCLUDED PRODUCER_MISSING (045b :504, :545); both
    count under the 10% rule. The run's producer counts and Herfindahl index are description only."""
    n, h0 = policy['params']['gates_per_run'], policy['params']['H0']
    claims = Claims()
    killed = None
    if collection is not None and collection['state'] == 'EXCLUDED' and scan.run_end is not None \
            and scan.run_end.get('status') == 'DONE' and not scan.cut:
        killed = code_word(collection.get('code')) or 'UNIT_TIMEOUT'
    states = pool_gate_states(scan, n, killed)
    if collection is not None:
        compare_collection(collection, states)
    judged = states['judged']
    chain = build_chain(scan, claims, strict=bool(judged))
    funding = funding_index(scan, chain, h0, n, claims)
    run_fields = log_run_fields(policy, scan, POOL_MINER_POLICY, n)
    gate_fields, births, found = check_pool_gates(policy, states, scan, chain, funding, claims)
    replay, replay_other = None, []
    if replay_with is not None and judged:
        replay = replay_chain(chain, h0, replay_with)
        extra, replay_other = pool_replay_fields(states, births, replay)
        for g, more in extra.items():
            gate_fields.setdefault(g, []).extend(more)
    core_replay_claims(scan, states, births, replay, claims)
    fee = -(-policy['params']['b'] * CANDIDATE_VSIZE // 1000)
    for item in scan.generated:
        if item['gate'] in range(n) and item['ladder'] != [fee]:
            claims.note('GENERATED', item['seq'], 'ladder', item['ladder'], [fee])
    for line in scan.pool_draw_lines:   # the driver's PRODUCER_H draws against the judge's own
        mine = drawn_producer(policy['seed'], scan.run, int(line['label'][len('PRODUCER_H'):]))
        for field in ('value', 'k', 'producer'):
            if line[field] != mine[field]:
                claims.note('DRAW', line['seq'], field, line[field], mine[field])
    run_fields = [f for f in POOL_RUN_FIELDS if f in run_fields]
    for g in list(gate_fields) + (judged if run_fields else []):   # run fields first, then the gate's own in order
        gate_fields[g] = run_fields + [f for f in POOL_GATE_FIELDS if f in gate_fields.get(g, [])]
    gates = states['gates']
    counts = {p: 0 for p in PRODUCERS}
    for entry in gates:
        g = entry['gate']
        seen = found.get(g, {})
        replayed = replay['rows'].get(births[g]['height']) if replay is not None and g in births else None
        entry.update(observation_id=observation_id(scan.run, g, 'POOL'), wallet=pool_wallet(g),
                     height=seen.get('height'), block_hash=seen.get('block_hash'),
                     born_txid=births[g]['txid'] if g in births else None,
                     next_birth=replayed['next_birth'] if replayed is not None else None,
                     producer_tags=seen.get('tags'), drawn_producer=seen.get('drawn'), producer=None,
                     mismatches=gate_fields.get(g, []))
        if entry['state'] != 'OBSERVED':
            continue
        if gate_fields.get(g):
            entry.update(state='EXCLUDED', code='JUDGE_PLAN_MISMATCH:' + gate_fields[g][0])
        elif seen.get('tags') is None or len(seen['tags']) != 1:
            entry.update(state='EXCLUDED', code=PRODUCER_MISSING)
        else:
            entry['producer'] = seen['tags'][0]
            counts[entry['producer']] += 1
    labels = list(POOL_RECORD_LABELS) + (['EXPLORATORY_NOT_A_VERDICT'] if mode != 'CONFIRMATORY' else [])
    if replay_with is None:
        births_label = 'UNVERIFIED_NO_REPLAY'
    else:
        births_label = 'REPLAYED' if replay is not None else 'NOT_REPLAYED_NO_JUDGED_GATE'
    outcome = {'result': POOL_RUN_RESULT, 'nogo': [], 'not_established': []}
    return {
        'schema': JUDGEMENT_SCHEMA, 'labels': labels, 'item': 'POOL', 'mode': mode,
        'evidence_status': 'CONFIRMATORY' if mode == 'CONFIRMATORY' else 'EXPLORATORY',
        'log_mode': scan.first['mode'], 'log_evidence_status': scan.first['evidence_status'],
        'births': births_label, 'replay': replay_summary(replay, replay_other),
        'judge': {'unit': 'J3', 'tool_sha256': sha256(TOOL_PATH.read_bytes())},
        'inputs': {'policy_sha256': policy['sha256'], 'raw_log_sha256': scan.sha256, 'raw_log_bytes': scan.bytes,
                   'raw_log_lines': scan.lines, 'collection_given': collection is not None, 'prereg_045b': prereg,
                   'registration_sha256': scan.first['registration_sha256']},
        'thresholds': threshold_table(),
        'unit': {'experiment': 'POOL', 'run': scan.run, 'registered_runs': policy['count']},
        'params': dict(policy['params'], source=policy['params_source']),
        'plan': {'rung0_fee': fee, 'seats': [{'gate': g, 'wallet': pool_wallet(g)} for g in range(n)]},
        'run_shape': dict(states['info'], judged_gates=len(judged), chain_tip=chain['tip'],
                          stale_blocks=chain['stale'], rejected_blocks=scan.rejected_blocks,
                          funding_problems=funding['problems'], run_mismatches=run_fields,
                          collection_code=collection_code(collection)),
        'gates': gates, 'gate_counts': gate_counts(gates),
        'producers': {'counts': counts, 'gates': sum(counts.values()), 'herfindahl': herfindahl(counts),
                      'scope': 'RUN_DESCRIPTION_NOT_JUDGED'},
        'driver_claims': claims.record(),
        'outcome': outcome,
        'verdict': verdict_block(outcome),
    }


def pool(args) -> dict:
    """The `pool` command: one POOL run's raw log, bound as `item1` binds an ITEM1 log (no method policy, no D2-2)."""
    mode = args.mode
    if mode == 'EXPLORATORY':
        need(args.registration is None, 'EXPLORATORY_REGISTRATION')
    need(not (args.no_replay and args.replay_bin is not None), 'REPLAY_OPTIONS')
    prereg = read_prereg(args.prereg)
    if mode == 'CONFIRMATORY':
        covering_registration(args, 'POOL')
    policy = parse_pool_policy(read_file(args.policy, 'POLICY', POLICY_LIMIT), mode)
    if mode == 'CONFIRMATORY':
        registered_log(args, policy, None, 'POOL')
    collection_blob = read_file(args.collection, 'COLLECTION', COLLECTION_LIMIT) if args.collection else None
    scan = scan_raw(args.raw, policy['sha256'], mode, 'POOL')
    collection = collection_unit(collection_blob, scan.run, 'POOL') if collection_blob is not None else None
    record = judge_pool(policy, scan, prereg, collection, mode,
                        None if args.no_replay else replay_argv(args.replay_bin))
    if collection_blob is not None:
        record['inputs']['collection_sha256'] = sha256(collection_blob)
    return record


# ---------------------------------------------------------------------------------------------------------
# J4a: one item-2 run, with or without the L0 project seat (ARDR_JUDGE_V1 section 21; 045b :381, :535-540, :546,
# :556-559, :1050-1055, :1218-1220; ARV1 sections 20, 22 and 26). One run is one contested gate at G = H0. The
# judge recomputes the plan (fee draws, t_G, the rung numbers released, every ladder by :537 with i the larger of
# Node A's and Node B's increment as logged), reads block G and every released rung from the bytes, attributes the
# Core's one birth at G to a seat by the funding outpoint it spends (never by Anchor key, F9), re-derives the
# item-2 exclusion codes, and checks the L0 seat's fees, attempt and budget record. Per run it is description only
# (NOT_A_VERDICT_PER_RUN); `experiment --experiment ITEM2` judges item 2 and the section 4.5 rows (section 22).

ITEM2_MINER_POLICY = 'ITEM2_DEFAULT'   # ARV1 section 7
ITEM2_SEATS = 5                        # 045b :535: 5 bidders per gate, bidder 0 private when present
ITEM2_MIN_H0 = 107                     # ARV1 section 20: the setup and funding blocks, then G - 1 on its own
ITEM2_RUN_COUNT = constant('ITEM2_RUNS')
ITEM2_QUALIFYING = constant('ITEM2_QUALIFYING')
ITEM2_STRATUM = constant('ITEM2_STRATUM_LIMIT')
ITEM2_INTERVAL = constant('ITEM2_GATE_INTERVAL')
ITEM2_RUNG_SECONDS = constant('ITEM2_RUNG_SECONDS')
ITEM2_LAST_RUNG = constant('ITEM2_LADDER')['last_rung']
ITEM2_CODES = tuple(constant('ITEM2_EXCLUSION_CODES'))
ITEM2_G_LATE_NS = constant('ITEM2_G_LATE_SECONDS') * 1_000_000_000
ITEM2_PRIVATE_WIN_MAX = constant('ITEM2_PRIVATE_WIN_SHARE_MAX')
MINED_LOSING_MAX = constant('MINED_LOSING_SHARE_MAX')
LOSING_FEE_MAX = constant('L0_LOSING_FEE_PER_ATTEMPT_MAX')
L0_P0_RULE = constant('L0_P0_RULE')
L0_MAX_GATE_ATTEMPTS = constant('L0_MAX_GATE_ATTEMPTS')
L0_MAX_FEE_PER_CANDIDATE = constant('L0_MAX_FEE_PER_CANDIDATE_DRAFT')
L0_SEAT_REGISTERED = constant('ITEM2_L0_SEAT')
L0_H0 = constant('ITEM2_L0_H0')
L0_MAX_SET_RUNGS = ITEM2_LAST_RUNG + 1          # rungs 0 ... 7 (the wallet's `max_rungs_per_conflict_set` 8)
L0_KIND, L0_WALLET, L0_SENT_BY = 'L0_PROJECT', 'L0', 'L0_STEP8'
L0_SEAT_KEYS = {'p0_rule', 'max_gate_attempts', 'exact_height_miss', 'budget_sha256', 'seat'}
EXACT_HEIGHT_MISS = ('STOP_CAMPAIGN', 'CONTINUE_WITHIN_LIMITS')
L0_DRAFT_MISS = 'CONTINUE_WITHIN_LIMITS'        # the L0 module's DRAFT / EXPLORATORY value (045b :103; :1899's too)
# 2026-11-10 (A): the frozen ITEM2 key's `exact_height_miss` (045b :1053's dated line, section 14.21 :1899, :1901);
# a CONFIRMATORY run takes no other (the driver's L0_STOP_CAMPAIGN_EXPLORATORY_ONLY, ARV1 section 26).
L0_CONFIRMATORY_MISS = L0_DRAFT_MISS
# The SHA-256 of the budget record the product's set charge writes, per `exact_height_miss` (ARV1 section 26
# :2557-2558, the L0 module's PRODUCT_BUDGET_SHA256, restated): CONTINUE_WITHIN_LIMITS is A's frozen Class T L0
# record, the frozen key's `budget_sha256` (045b section 14.21 :1898, :1901); STOP_CAMPAIGN is its one-field twin,
# EXPLORATORY only. `--policy-l0-seat` refuses any other digest before any node (L0_POLICY_BUDGET_NOT_PRODUCT).
L0_PRODUCT_BUDGET_SHA256 = {
    'CONTINUE_WITHIN_LIMITS': '7d0a7a35ffa4df11311955d11e00b8c9c0f0f7df5c6e84c222911d447c7f4dd4',
    'STOP_CAMPAIGN': '9ea208bd6e9bc19ab60b07469497887e6b4ce9aa270efb752247b1d3b13a26d0',
}
# The L0 module's budget record (ARV1 section 22 "Budget"), restated: an L0_LAUNCH_START with `budget_source`
# BUDGET_DRAFT names it as `budget_draft`, and L0_BUDGET.product carries its four fields. 2026-11-10 (A): B-FZ-p
# (#759) made it four fields of A's frozen Class T record (045b section 14.21 :1898-1899, `7d0a7a35..`), with the
# L0 module's status FROZEN_TEST_ONLY; the name stays, as the L0 module's BUDGET_DRAFT (the `budget_source` value).
L0_BUDGET_DRAFT = {'status': 'FROZEN_TEST_ONLY', 'max_fee_per_candidate_sat': L0_MAX_FEE_PER_CANDIDATE,
                   'max_fee_exposure_sat': LOSING_FEE_MAX['num'], 'max_principal_exposure_sat': 240_000,
                   'max_gate_attempts': L0_MAX_GATE_ATTEMPTS,
                   'fee_row_threshold_sat_per_attempt': '%d/%d' % (LOSING_FEE_MAX['num'], LOSING_FEE_MAX['den'])}
L0_BUDGET_FIELDS = ('max_gate_attempts', 'max_fee_per_candidate_sat', 'max_fee_exposure_sat',
                    'max_principal_exposure_sat')
ITEM2_FIELD_ORDER = ('params', 'miner_policy', 'bidders_sha256', 'bidders', 'fee_draws', 'schedule', 'ladder',
                     'height', 'block_g', 'rung_bytes', 'private_exposure', 'presence', 'timing', 'release',
                     'l0_fee', 'l0_budget', 'l0_attempt', 'replay_birth', 'replay_other_birth')
MEMPOOL_LOG_INCOMPLETE = 'MEMPOOL_LOG_INCOMPLETE'   # 045b :498: a gate without a complete mempool log is excluded
ITEM2_RECORD_LABELS = ['CLASS_T', 'REGTEST', 'JUDGE_RECORD', 'J4A_ITEM2_RUN']
ITEM2_CONDITIONS = ('ORDER_CONSTRAINED', 'PRIVATE_UNCONSTRAINED', 'PUBLIC_ONLY')
# J4c, finding #788 (section 28): why a refused rung is undecided for :501, the `why` of its entry. REPLACES_UNKNOWN:
# the rung meets item 5 and the node's `replaces_in_mempool` is not a bool. ITEM5_UNKNOWN: the judge cannot establish
# item 5 for the rung (the node's `replaces_in_mempool` true or not a bool).
RUNG_UNDECIDED_WHY = ('REPLACES_UNKNOWN', 'ITEM5_UNKNOWN')
L0_RUNG_WHEN = ('BEFORE_RELEASE', 'CHARGED_NOT_RELEASED_BEFORE_G')   # ARV1 section 22: L0_RUNG_TEST's `when`
SEAT_NAME = re.compile(r'S[0-4]\Z')
# The REGISTER form (Desktop r4443064942): output 0 the exact REGISTER carrier of the run's deployment and gate height
# (crates/bitagi-wire/src/lib.rs `construct_register_carrier`: 0x6a 0x30, PROTOCOL_MAGIC `BITAGI`, format 0x01, action
# `R`, the deployment id, the target gate height u64 big-endian), value 0, and output 1 an Anchor script (0x51 0x20,
# 34 bytes, `is_anchor_script`). The deployment id is the `BITAGI/deployment` tagged hash of the Regtest Profile
# (`BITAGI` 0x01 || genesis || rules_hash || u64be(H0)), as tools/verify_launch_namespace_ct.py computes it; the replay
# worker builds the same Profile (section 17). Restated here, with a test against that tool.
REGTEST_GENESIS = bytes.fromhex('0f9188f13cb7b2c71f2a335e3a4fc328bf5beb436012afca590b1a11466e2206')[::-1]
RULES_HASH = bytes.fromhex('a9a26978e97871ad9a5fc89efe2a517ba42a858d95291731014ba9b9355581ed')
DEPLOYMENT_TAG = b'BITAGI/deployment'
PROFILE_PREFIX = b'BITAGI\x01'
REGISTER_PREFIX = b'\x6a\x30BITAGI\x01R'


def ceil_div(a: int, b: int) -> int:
    return -(-a // b)


def item2_ladder(p0: int, b: int, i: int, v: int = CANDIDATE_VSIZE) -> list[int]:
    """045b :537, the rung fees of one bidder: f_0 = ceil(p_0 v / 1000); r_k = ceil(p_0 3^k / 2^k); f_k = max(ceil(r_k
    v / 1000), f_(k-1) + max(1, ceil(i v / 1000))). The ladder ends before the first rung with f_k x 1000 > 4b x v, or
    after rung 7 (an empty ladder when rung 0 is past the cap)."""
    fees: list[int] = []
    step = max(1, ceil_div(i * v, 1000))
    for k in range(ITEM2_LAST_RUNG + 1):
        fee = ceil_div(ceil_div(p0 * 3 ** k, 2 ** k) * v, 1000)
        if fees:
            fee = max(fee, fees[-1] + step)
        if fee * 1000 > 4 * b * v:
            break
        fees.append(fee)
    return fees


def l0_p0(b: int) -> int:
    """The L0 seat's rung-0 feerate (FD-CT-133, `MAX_P0_TWO_RUNGS`; section 30; it replaces 045b :1053's ceil(2.5 b)):
    the largest integer p_0 >= 2b whose :537 ladder at i = 0 (v = 213) has two rungs. From 2b up r_2 >= 4.5b, so no
    rung 2 fits, and f_1 never falls as p_0 rises: the last p_0 whose f_1 x 1000 <= 4b x v. The judge's own search
    over its own `item2_ladder`; none from 2b is L0_P0_NO_TWO_RUNGS (b 1-3)."""
    need(type(b) is int and b >= 1, 'L0_P0_INPUT')
    low, high = 2 * b, 4 * b   # f_0 at 4b is the cap fee or more, so f_1 is past it: 4b never has two rungs
    need(len(item2_ladder(low, b, 0)) == 2, 'L0_P0_NO_TWO_RUNGS')
    while high - low > 1:   # invariant: two rungs at low, fewer at high
        mid = (low + high) // 2
        low, high = (mid, high) if len(item2_ladder(mid, b, 0)) == 2 else (low, mid)
    return low


def item2_deployment_id(h0: int) -> bytes:
    """The Regtest deployment id at H0: SHA-256(t || t || Profile), t = SHA-256(`BITAGI/deployment`)."""
    tag = hashlib.sha256(DEPLOYMENT_TAG).digest()
    return hashlib.sha256(tag + tag + PROFILE_PREFIX + REGTEST_GENESIS + RULES_HASH + h0.to_bytes(8, 'big')).digest()


def register_form(tx: dict, h0: int, gate: int) -> bool:
    """A candidate of block G has the REGISTER form: output 0 the exact carrier for the run's deployment and target
    height G, value 0; output 1 an Anchor script."""
    outputs = tx['outputs']
    carrier = REGISTER_PREFIX + item2_deployment_id(h0) + gate.to_bytes(8, 'big')
    return (len(outputs) >= 2 and outputs[0] == (0, carrier) and len(outputs[1][1]) == 34
            and outputs[1][1][:2] == b'\x51\x20')


def item2_qualifying(r: int) -> bool:
    """045b :1218 (E13): the qualifying sample is fixed by run index, r = 0, 2, ..., 98."""
    q = ITEM2_QUALIFYING
    return q['first'] <= r <= q['last'] and (r - q['first']) % q['step'] == 0


def item2_condition(r: int) -> str:
    """045b :546: even r private present (r = 0 ... 98 the order-constrained runs), odd r five public seats."""
    if item2_qualifying(r):
        return 'ORDER_CONSTRAINED'
    return 'PRIVATE_UNCONSTRAINED' if r % 2 == 0 else 'PUBLIC_ONLY'


def item2_observation_id(r: int) -> str:
    """The item-2 unit is the run (one gate): `OBS-2<r:07>` (ARV1 section 20)."""
    return 'OBS-%d%07d' % (EXPERIMENTS.index('ITEM2') + 1, r)


def item2_plan(seed: bytes, r: int, b: int, l0: int | None) -> dict:
    """The run's seats, fee draws and GATE_INTERVAL draw (045b :535, :546, :556-559; ARV1 section 20): seats S0-S4
    with wallets W00-W04, S0 PRIVATE on even r; the L0 seat (section 22) is L0_PROJECT / L0 / PUBLIC and draws no fee
    (045b :1052). Order-constrained: PRIVATE_FEE (n = b + 1), then PUBLIC_FEE_j (n = 4b - p + 1) from the private p;
    otherwise BID_FEE_j (n = 3b + 1). Each label is drawn on its own, so the L0 seat leaves the others unchanged."""
    condition = item2_condition(r)
    present = r % 2 == 0
    seats = [{'seat': f'S{j}', 'kind': 'SYNTHETIC', 'wallet': 'W%02d' % j,
              'path': 'PRIVATE' if present and j == 0 else 'PUBLIC'} for j in range(ITEM2_SEATS)]
    if l0 is not None:
        seats[l0] = {'seat': f'S{l0}', 'kind': L0_KIND, 'wallet': L0_WALLET, 'path': 'PUBLIC'}
    draws: list[dict] = []

    def one(label: str, n: int, base: int) -> int:
        value, k = draw(seed, 'ITEM2', r, label, n)
        draws.append({'label': label, 'n': n, 'k': k, 'value': value, 'feerate': base + value})
        return base + value

    if condition == 'ORDER_CONSTRAINED':
        private = one('PRIVATE_FEE', b + 1, b)
        rates = [private] + [None if j == l0 else one(f'PUBLIC_FEE_{j}', 4 * b - private + 1, private)
                             for j in range(1, ITEM2_SEATS)]
    else:
        rates = [None if j == l0 else one(f'BID_FEE_{j}', 3 * b + 1, b) for j in range(ITEM2_SEATS)]
    value, k = draw(seed, 'ITEM2', r, 'GATE_INTERVAL', ITEM2_INTERVAL['n'])
    # The order constraint (045b :540) is a property of the draws, never a selection by results (E13): every public
    # p_0 at least the private p, and L0's p_0 (FD-CT-133, section 30) at least 2b, at least the private p.
    order = condition != 'ORDER_CONSTRAINED' or all(p >= rates[0] for p in rates[1:] if p is not None) and (
        l0 is None or l0_p0(b) >= rates[0])
    return {'condition': condition, 'qualifying': condition == 'ORDER_CONSTRAINED', 'private_present': present,
            'bidders': {'schema': BIDDERS_SCHEMA, 'gates': [{'gate': r, 'seats': seats}]}, 'seats': seats,
            'feerates': rates, 'draws': draws, 'order_holds': order,
            'gate_interval': {'value': value, 'k': k, 't_gate_seconds': value + ITEM2_INTERVAL['plus']}}


def item2_schedule(plan: dict, first: dict, sched: dict | None, b: int, l0: int | None) -> tuple[dict, list[str]]:
    """t_G, the rung numbers released (k with rung_seconds x k < t_G, at most rung 7), i (the larger of SCHEDULE's two
    increments), every ladder (045b :537; the L0 seat at FD-CT-133's p_0), the release rounds and the predicted
    count (045b :537: the rungs released strictly before t_G, summed over bidders). Returns it and the fields whose
    log values differ: `schedule`, `ladder` (a synthetic seat's) and `l0_fee` (the L0 seat's ladder)."""
    bad = []
    if first['schedule_source'] == 'DRAFT_OVERRIDE':   # EXPLORATORY only (the CONFIRMATORY refusal comes first)
        t_gate, rung = first['t_gate_seconds'], first['rung_seconds']
        if not (t_gate >= 1 and rung >= 1):
            bad.append('schedule')
            t_gate, rung = plan['gate_interval']['t_gate_seconds'], ITEM2_RUNG_SECONDS
    else:
        t_gate, rung = plan['gate_interval']['t_gate_seconds'], ITEM2_RUNG_SECONDS
    ks = [k for k in range(ITEM2_LAST_RUNG + 1) if rung * k < t_gate]
    if (first['t_gate_seconds'], first['rung_seconds'], first['release_ks']) != (t_gate, rung, ks):
        bad.append('schedule')
    increments = sched['increments'] if sched is not None else {'A': 0, 'B': 0}
    i = max(increments['A'], increments['B'])
    ladders = [item2_ladder(l0_p0(b) if j == l0 else plan['feerates'][j], b, i) for j in range(ITEM2_SEATS)]
    rounds = []
    for k in ks:
        seats = [j for j in range(ITEM2_SEATS) if k < len(ladders[j])]
        if seats:
            rounds.append({'k': k, 'offset_seconds': rung * k, 'seats': seats})
    predicted = sum(len(step['seats']) for step in rounds)
    if sched is None:
        bad.append('schedule')
    else:
        if (sched['increment'], sched['rounds'], sched['t_gate_seconds'], sched['rung_seconds'], sched['l0_seat']) \
                != (i, rounds, t_gate, rung, l0) or len(sched['ladders']) != ITEM2_SEATS:
            bad.append('schedule')
        logged = sched['ladders'] + [None] * ITEM2_SEATS
        if any(logged[j] != ladders[j] for j in range(ITEM2_SEATS) if j != l0):
            bad.append('ladder')
        if l0 is not None and logged[l0] != ladders[l0]:
            bad.append('l0_fee')
    return {'t_gate_seconds': t_gate, 'rung_seconds': rung, 'release_ks': ks, 'increments': increments, 'i': i,
            'ladders': ladders, 'rounds': rounds, 'predicted': predicted}, bad


def check_l0_seat_shape(value) -> None:
    """`experiments.ITEM2.l0_seat` (ARV1 section 26): exactly `p0_rule`, `max_gate_attempts`, `exact_height_miss`,
    `budget_sha256` and `seat`, each a PENDING string or a value of its kind (POLICY_L0_SEAT); seat 0 is the even
    runs' private seat (POLICY_L0_SEAT_PRIVATE)."""
    checks = {'p0_rule': _str, 'max_gate_attempts': lambda v: type(v) is int and v >= 1,
              'exact_height_miss': lambda v: v in EXACT_HEIGHT_MISS, 'budget_sha256': _hex64,
              'seat': lambda v: int_in(v, 0, ITEM2_SEATS - 1)}
    need(type(value) is dict and set(value) == L0_SEAT_KEYS
         and all(pending(value[k]) or checks[k](value[k]) for k in L0_SEAT_KEYS), 'POLICY_L0_SEAT')
    need(value['seat'] != 0, 'POLICY_L0_SEAT_PRIVATE')


def parse_item2_policy(blob: bytes, mode: str) -> dict:
    """J4a: the ITEM2 part of a BITAGI_CT_ARDR_POLICY_V1 file (ARV1 sections 3, 18, 20 and 26): the miner policy
    ITEM2_DEFAULT, the params in any mode (without them the driver runs D1's smoke, which has no gate), one gate per
    run, H0 at least 107, and the `l0_seat` key. CONFIRMATORY needs the count and the key, with 045b's seat 1, p_0
    rule MAX_P0_TWO_RUNGS (FD-CT-133) and 24 attempts (:1053, :1219), and H0 1000 (:1054); a keyed policy too.
    2026-11-10 (A, after the freeze): the CONFIRMATORY key's other two values are the frozen ones too,
    CONTINUE_WITHIN_LIMITS and the frozen record's digest (:1053's dated line, section 14.21 :1898-1901;
    POLICY_L0_VALUES). `complete`: no PENDING value anywhere and every experiment counted, as the L0 CLI's
    `--policy-l0-seat` loads a policy (`l0_seat_of`), each count an int 1 .. U32-1 and every `counts` key an
    experiment (`check_policy_shape` POLICY_COUNTS). 2026-11-10 (A, J5b): CONFIRMATORY requires it
    (POLICY_COUNT_UNSET), as the driver's `load_policy` does."""
    doc, experiments = policy_head(blob, mode)
    confirmatory = mode == 'CONFIRMATORY'
    need('ITEM2' in experiments, 'POLICY_ITEM2')
    need(all('method_policy' not in entry for name, entry in experiments.items() if name != 'ITEM1'),
         'POLICY_METHOD_POLICY')
    entry = experiments['ITEM2']
    need(set(entry) <= {'miner_policy', 'params', 'l0_seat'} and 'miner_policy' in entry, 'POLICY_ITEM2')
    need(not pending(entry['miner_policy']), 'POLICY_PENDING', EXIT_PREREQUISITE)
    need(entry['miner_policy'] == ITEM2_MINER_POLICY, 'POLICY_MINER_EXPERIMENT')
    counts = doc['counts']
    need(pending(counts) or type(counts) is dict, 'POLICY_SHAPE')
    count = counts.get('ITEM2') if type(counts) is dict else None
    # 2026-11-10 (A, Desktop P3 on #669): each count must also be the producer's value, an int 1 .. U32-1
    # (`check_policy_shape` POLICY_COUNTS), not only present: a null or 0 count is no `--policy-l0-seat` policy.
    # 2026-11-10 (A, J5b verification round): nor is a `counts` key that is not an experiment, POLICY_COUNTS's other
    # half (`set(counts) <= set(EXPERIMENTS)`, refused in every mode before any node).
    complete = (not pending(doc) and type(counts) is dict and set(experiments) <= set(counts) <= set(EXPERIMENTS)
                and all(int_in(value, 1, U32 - 1) for value in counts.values()))
    if confirmatory:
        need(int_in(count, 1, U32 - 1), 'POLICY_COUNT_UNSET', EXIT_PREREQUISITE)
        # 2026-11-10 (A, J5b; A's Q3 on #719): CONFIRMATORY takes only a complete policy, as the driver's `load_policy`
        # does (no PENDING anywhere, POLICY_PENDING, already refused by `policy_head`; every experiment counted,
        # POLICY_COUNT_UNSET, exit 3). A count that is not an int 1 .. U32-1, or a `counts` key that is not an
        # experiment, is the driver's POLICY_COUNTS (exit 2), a code the judge has not: the judge's own code for that
        # count of its own experiment is POLICY_COUNT_UNSET.
        need(complete, 'POLICY_COUNT_UNSET', EXIT_PREREQUISITE)
    params, source = policy_params(entry.get('params'), True, {}, GATES_PER_RUN_MAX)
    need(params['gates_per_run'] == 1, 'POLICY_ITEM2_GATES')
    need(params['H0'] >= ITEM2_MIN_H0, 'POLICY_ITEM2_H0')
    seat = entry.get('l0_seat')
    if seat is not None:
        check_l0_seat_shape(seat)
    if confirmatory:
        need(seat is not None, 'L0_FREEZE_PENDING', EXIT_PREREQUISITE)
        need(seat['seat'] == L0_SEAT_REGISTERED and seat['p0_rule'] == L0_P0_RULE
             and seat['max_gate_attempts'] == L0_MAX_GATE_ATTEMPTS and seat['exact_height_miss'] == L0_CONFIRMATORY_MISS
             and seat['budget_sha256'] == L0_PRODUCT_BUDGET_SHA256[L0_CONFIRMATORY_MISS], 'POLICY_L0_VALUES')
    if confirmatory or (seat is not None and not pending(seat)):
        need(params['H0'] == L0_H0, 'POLICY_ITEM2_H0')
    return {'sha256': sha256(blob), 'seed': bytes.fromhex(doc['seed']), 'params': params, 'params_source': source,
            'count': count if type(count) is int else None, 'method_policy': None, 'l0_seat': seat,
            'complete': complete}


def item2_unit_state(scan: Scan, r: int, killed: str | None) -> dict:
    """The unit's state re-derived from the log as the collection derives it (ARV1 section 13; decision 11): OBSERVED
    iff RUN_END DONE after GATE_END OBSERVED (and the collection does not say the unit was killed after it); EXCLUDED
    with RUN_END EXCLUDED's item-2 code, RUN_END FAILED's code (phase SETUP, GATE or END), or RUN_END_MISSING /
    RAW_LOG_TRUNCATED. One GATE_START and at most one GATE_END, both of gate r with the run's observation id."""
    obs = item2_observation_id(r)
    need(scan.first['gates'] == [r], 'RAW_LOG_GATES')
    starts = [line for line in scan.gate_lines if line['event'] == 'GATE_START']
    ends = [line for line in scan.gate_lines if line['event'] == 'GATE_END']
    need(all(line['gate'] == r and line['unit']['gate'] == r and line['observation_id'] == obs
             for line in scan.gate_lines), 'RAW_LOG_GATES')
    need(len(starts) <= 1 and len(ends) <= 1 and (not ends or (starts and ends[0]['seq'] > starts[0]['seq'])),
         'RAW_LOG_GATES')
    start, end = (starts or [None])[0], (ends or [None])[0]
    run_end = scan.run_end
    info = {'unit_state': 'EXCLUDED', 'code': 'RAW_LOG_TRUNCATED' if scan.cut else 'RUN_END_MISSING',
            'run_end': None, 'phase': None, 'truncated': scan.cut, 'killed': killed is not None,
            'code_seats': [], 'start': start, 'end': end}
    if run_end is not None:
        status = run_end['status']
        info['run_end'] = status
        need(status == 'DONE' or run_end['excluded_gates'] == [r], 'RAW_LOG_GATES')
        if status == 'DONE':
            need(end is not None and end['status'] == 'OBSERVED', 'RAW_LOG_GATES')
            if killed is None:
                info.update(unit_state='OBSERVED', code='DONE')
            else:
                info['code'] = killed
        elif status == 'EXCLUDED':
            need(end is not None and end['status'] == 'EXCLUDED' and end['code'] == run_end['code'], 'RAW_LOG_ITEM2')
            info.update(code=run_end['code'], code_seats=list(end['code_seats']))
        else:
            info.update(code=code_word(run_end['code']) or 'RUN_END_FAILED', phase=run_end['phase'])
    return info


def l0_policy_valued(scan: Scan, mode: str) -> bool:
    """Whether the L0 seat ran on the policy's `l0_seat` values: in CONFIRMATORY (REGISTERED_POLICY), and outside it
    when RUN_START's `l0_seat_source` is POLICY_VALUE (2026-11-10, B-FZ-a #756: the L0 CLI's `--policy-l0-seat`, the
    045b F3 command :1224; ARV1 section 26, "Where the values came from, in the log", :2563-2571, and section 22
    :1766-1768). J5: an item-4 RUN_START has no `l0_seat_source` (its key has no seat, ARV1 section 26), so an item-4
    log says it on L0_LAUNCH_START's `budget_source` alone (the L0 module's `budget_fields`)."""
    if mode == 'CONFIRMATORY':
        return True
    if scan.experiment in ITEM4_SCENARIOS:
        return any(launch['budget_source'] == 'POLICY_VALUE' for launch in scan.item2['L0_LAUNCH_START'])
    return scan.first['l0_seat_source'] == 'POLICY_VALUE'


def l0_seat_of(first: dict, policy: dict, mode: str) -> int | None:
    """The L0 seat from RUN_START (ARV1 sections 22 and 26; 045b :1219): CONFIRMATORY the policy's seat, with
    `l0_seat_source` REGISTERED_POLICY (RAW_LOG_L0_SEAT, RAW_LOG_L0_SOURCE, exit 6); EXPLORATORY a seat 1-4 with
    DRAFT_PARAMETER, or none (PENDING_FREEZE) with PENDING_FREEZE (A's J4a decision 6). 2026-11-10 (B-FZ-a): or,
    outside CONFIRMATORY, POLICY_VALUE: the judged policy holds an `l0_seat` with no PENDING value
    (RAW_LOG_L0_SOURCE otherwise) and the log's seat is that key's seat (RAW_LOG_L0_SEAT), both exit 6. A policy the
    L0 CLI's `--policy-l0-seat` refuses before any node is no source of POLICY_VALUE either (RAW_LOG_L0_SOURCE): one
    not complete (`load_policy(complete=True)`: a PENDING value anywhere, an experiment not counted), or a key whose
    `p0_rule` is not MAX_P0_TWO_RUNGS, `max_gate_attempts` not 24, or `budget_sha256` not the product's
    record for its `exact_height_miss` (`confirmatory_l0_seat`; ARV1 section 26 :2557-2558)."""
    seat, source = first['l0_seat'], first['l0_seat_source']
    if mode == 'CONFIRMATORY':
        need(seat == policy['l0_seat']['seat'], 'RAW_LOG_L0_SEAT', EXIT_REFUSAL)
        need(source == 'REGISTERED_POLICY', 'RAW_LOG_L0_SOURCE', EXIT_REFUSAL)
        return seat
    need(seat == 'PENDING_FREEZE' or int_in(seat, 1, ITEM2_SEATS - 1), 'RAW_LOG_L0')
    if source == 'POLICY_VALUE':
        key = policy['l0_seat']
        # `complete` covers the key: no PENDING value anywhere in the policy, the key's five included.
        need(seat != 'PENDING_FREEZE' and key is not None and policy['complete'], 'RAW_LOG_L0_SOURCE', EXIT_REFUSAL)
        need(key['p0_rule'] == L0_P0_RULE and key['max_gate_attempts'] == L0_MAX_GATE_ATTEMPTS
             and key['budget_sha256'] == L0_PRODUCT_BUDGET_SHA256[key['exact_height_miss']],
             'RAW_LOG_L0_SOURCE', EXIT_REFUSAL)
        need(seat == key['seat'], 'RAW_LOG_L0_SEAT', EXIT_REFUSAL)
        return seat
    need(source == ('PENDING_FREEZE' if seat == 'PENDING_FREEZE' else 'DRAFT_PARAMETER'), 'RAW_LOG_L0_SOURCE',
         EXIT_REFUSAL)
    return None if seat == 'PENDING_FREEZE' else seat


def item2_l0_binding(scan: Scan, policy: dict, mode: str, l0: int | None, h0: int) -> None:
    """The L0 lines' own binding refusals: none without the seat (RAW_LOG_L0), H0 1000 with it (RAW_LOG_L0; ARV1
    section 22), at most one L0_LAUNCH_START, L0_SET_CHARGED, L0_READY and L0_BUDGET and one funding block
    (RAW_LOG_DUPLICATE_EVENT), `budget_source` the mode's (RAW_LOG_L0_SOURCE: REGISTERED_POLICY with `budget_sha256`
    in CONFIRMATORY, else BUDGET_DRAFT with `budget_draft`; #667 P3-1), and in CONFIRMATORY every logged
    `budget_sha256` the policy's (L0_BUDGET_SHA256). 2026-11-10 (B-FZ-a): a run outside CONFIRMATORY whose RUN_START
    says POLICY_VALUE has `budget_source` POLICY_VALUE with `budget_sha256` (and no `budget_draft`), and every
    logged `budget_sha256` the policy's, as in CONFIRMATORY; the two labels go together (RAW_LOG_L0_SOURCE).
    L0_BUDGET's `policy_compare` (ARV1 section 26 :2570-2571): EQUAL with `policy_budget_sha256` in a run on the
    policy's values (CONFIRMATORY or POLICY_VALUE), that digest the policy's like every other (L0_BUDGET_SHA256);
    NO_POLICY_VALUE without `policy_budget_sha256` otherwise, or absent there (an EXPLORATORY log written before
    B-FZ-a); anything else RAW_LOG_L0_SOURCE. 2026-11-26 (A): without the seat, also no L0_STOP_FAILED after RUN_END
    (`Scan.take_after_end` takes it for the L0 seat's cleanup only; RAW_LOG_AFTER_END)."""
    lines = scan.item2
    if l0 is None:
        need(scan.l0_lines == 0, 'RAW_LOG_L0')
        need(scan.l0_stop_after_end is None, 'RAW_LOG_AFTER_END')
        return
    need(h0 == L0_H0, 'RAW_LOG_L0')
    need(all(len(lines[e]) <= 1 for e in ('L0_LAUNCH_START', 'L0_SET_CHARGED', 'L0_READY', 'L0_BUDGET'))
         and len(scan.l0_funding) <= 1, 'RAW_LOG_DUPLICATE_EVENT')
    valued = l0_policy_valued(scan, mode)
    label = 'REGISTERED_POLICY' if mode == 'CONFIRMATORY' else 'POLICY_VALUE'
    for launch in lines['L0_LAUNCH_START']:
        source = launch['budget_source']
        if valued:
            need(source == label and 'budget_sha256' in launch and 'budget_draft' not in launch,
                 'RAW_LOG_L0_SOURCE', EXIT_REFUSAL)
        else:
            need(source == 'BUDGET_DRAFT' and 'budget_draft' in launch and 'budget_sha256' not in launch,
                 'RAW_LOG_L0_SOURCE', EXIT_REFUSAL)
    for budget in lines['L0_BUDGET']:
        if valued:
            need(budget.get('policy_compare') == 'EQUAL' and 'policy_budget_sha256' in budget,
                 'RAW_LOG_L0_SOURCE', EXIT_REFUSAL)
        else:
            need(budget.get('policy_compare', 'NO_POLICY_VALUE') == 'NO_POLICY_VALUE'
                 and 'policy_budget_sha256' not in budget, 'RAW_LOG_L0_SOURCE', EXIT_REFUSAL)
    if valued:
        logged = [x['budget_sha256'] for x in lines['L0_LAUNCH_START'] + lines['L0_SET_CHARGED']]
        logged += [x['product']['budget_sha256'] for x in lines['L0_BUDGET']]
        logged += [x['policy_budget_sha256'] for x in lines['L0_BUDGET']]
        need(all(d == policy['l0_seat']['budget_sha256'] for d in logged), 'L0_BUDGET_SHA256', EXIT_REFUSAL)


def item2_funding(scan: Scan, chain: dict, h0: int, plan: dict, l0: int | None, claims: Claims) -> dict:
    """Each seat's funding outpoint from the bytes. Synthetic seats: FUNDING_SENT `outputs` names [wallet, r] per
    output in output order (ARV1 section 12; the item-1 layout F9 keeps); L0: the one output of block 1's coinbase
    paying L0_FUNDING_BLOCK's `funding_script` (ARV1 section 22). Layout problems are reported, never an exclusion
    (A's J4a decision 7): not exactly one FAN_OUT, a transaction not on the chain below H0, an OWNER transaction
    not spending the FAN_OUT, a label outside the run's synthetic seats or repeated, a seat without a label, scripts
    whose equality does not follow the wallets, and the L0 funding block or output missing."""
    r = scan.run
    problems = []
    wanted = {(s['wallet'], r): j for j, s in enumerate(plan['seats']) if s['kind'] != L0_KIND}   # J5: C00 too
    by_seat: dict[int, dict] = {}
    fan = [f for f in scan.funding if f['stage'] == 'FAN_OUT']
    if len(fan) != 1:
        problems.append('FAN_OUT_COUNT')
    scripts: dict[str, bytes] = {}
    for f in scan.funding:
        tx = f['tx']
        if f['claimed_txid'] != tx['txid']:
            claims.note('FUNDING_SENT', f['seq'], 'txid', f['claimed_txid'], tx['txid'])
        if f['stage'] not in ('FAN_OUT', 'OWNER'):
            problems.append('FUNDING_STAGE')
        height = chain['where'].get(tx['txid'])
        if height is None or height >= h0:
            problems.append('FUNDING_NOT_MINED')
        if len(f['labels']) > len(tx['outputs']):
            problems.append('FUNDING_OUTPUTS')
        if f['stage'] == 'OWNER' and len(fan) == 1 and [i['txid'] for i in tx['inputs']] != [fan[0]['tx']['txid']]:
            problems.append('OWNER_NOT_FROM_FAN_OUT')
        for vout, label in enumerate(f['labels'][:len(tx['outputs'])]):
            j = wanted.get(label)
            if j is None or j in by_seat:
                problems.append('FUNDING_LABEL')
                continue
            value, script = tx['outputs'][vout]
            by_seat[j] = {'txid': tx['txid'], 'vout': vout, 'value': value}
            scripts[label[0]] = script
    if len(set(scripts.values())) != len(scripts):
        problems.append('FUNDING_SCRIPTS')
    if set(by_seat) != set(wanted.values()):
        problems.append('FUNDING_MISSING')
    if l0 is not None:
        block = chain['blocks'].get(1)
        if len(scan.l0_funding) != 1 or block is None or block is not scan.l0_funding[0]:
            problems.append('L0_FUNDING_BLOCK')
        else:
            script = bytes.fromhex(block['funding_script']) if HEX.match(block['funding_script']) else None
            paid = [(vout, value) for vout, (value, s) in enumerate(block['txs'][0]['outputs']) if s == script]
            if len(paid) != 1:
                problems.append('L0_FUNDING_OUTPUT')
            else:
                by_seat[l0] = {'txid': block['txs'][0]['txid'], 'vout': paid[0][0], 'value': paid[0][1]}
    return {'problems': sorted(set(problems)), 'by_seat': by_seat,
            'by_outpoint': {(f['txid'], f['vout']): j for j, f in by_seat.items()}}


def tx_fee_vsize(tx: dict, value: int) -> tuple[int, int]:
    """A one-input candidate's fee (the funding output's value less its outputs) and vsize (ceil(weight / 4))."""
    return value - sum(v for v, _ in tx['outputs']), ceil_div(tx['weight'], 4)


def item2_releases(scan: Scan, plan: dict, schedule: dict, funding: dict, l0: int | None,
                   floor_seq: int | None = None) -> tuple[list, dict, set]:
    """Every RELEASE line (ARV1 sections 20 and 22) with the bytes handed off: PUBLIC_SENT for a public rung,
    PRIVATE_HANDOFF (rung 0) or PRIVATE_REPLACE (k >= 1) for the private one; L0's rungs (`sent_by` L0_STEP8) carry
    no bytes. A synthetic rung handed off must have its bytes, spend exactly its seat's funding output, pay its
    ladder's f_k at vsize 213, (PRIVATE_REPLACE) replace the seat's rung before, and stand in its step's window: after
    the previous step's RELEASE lines and relay snapshot (step 0: after block G - 1's BLOCK line, `floor_seq`) and
    before its own RELEASE (`rung_bytes`; Desktop r4445653922, r4446892062). Returns the releases, the bytes by txid
    and the fields."""
    lines = scan.item2
    bad = set()
    # The driver writes step k's hand-offs only after step k - 1's RELEASE lines and relay snapshot (L0's own lines,
    # written after every step, are not a step's).
    first_l0 = min((line['seq'] for line in lines['RELEASE'] if line.get('sent_by') == L0_SENT_BY), default=None)
    steps = [(line['seq'], line['k']) for line in lines['RELEASE'] if line.get('sent_by') != L0_SENT_BY]
    steps += [(line['seq'], line['k']) for line in lines['RELEASE_MEMPOOLS'] if first_l0 is None
              or line['seq'] < first_l0]

    def lower(k: int) -> int:
        return max([seq for seq, kk in steps if kk < k] + [floor_seq or 0])
    handed: dict[str, dict] = {}
    for event in ('PUBLIC_SENT', 'PRIVATE_HANDOFF', 'PRIVATE_REPLACE'):
        for line in lines[event]:
            try:
                tx = parse_tx(hex_bytes(line['hex'], 'RAW_LOG_ITEM2'))
            except (Malformed, KeyError):
                raise Refusal('RAW_LOG_ITEM2') from None
            if tx['txid'] != line['txid'] or tx['txid'] in handed:
                bad.add('rung_bytes')
            handed[tx['txid']] = {'event': event, 'seat': line['seat'], 'tx': tx, 'seq': line['seq'],
                                  'replaced': line.get('replaced')}
    releases, last_private, paired = [], None, set()
    for line in lines['RELEASE']:
        need(SEAT_NAME.match(line['seat']) is not None, 'RAW_LOG_ITEM2')
        j = int(line['seat'][1:])
        is_l0 = line.get('sent_by') == L0_SENT_BY
        need(is_l0 == (j == l0), 'RAW_LOG_L0')   # only the L0 seat releases through L0, and only through L0
        seat = plan['seats'][j]
        if line['path'] != seat['path']:
            bad.add('schedule')
        rel = {'j': j, 'seat': line['seat'], 'path': seat['path'], 'kind': seat['kind'], 'k': line['k'],
               'txid': line['txid'], 'seq': line['seq'], 'sent_ns': line['sent_ns'], 'due_ns': line['due_ns'],
               'handed_off': line['handed_off'],
               'l0': is_l0, 'fee': line.get('fee'), 'vsize': line.get('vsize'), 'attempt_id': line.get('attempt_id')}
        releases.append(rel)
        if is_l0 or not rel['handed_off']:
            continue
        want = 'PUBLIC_SENT' if seat['path'] == 'PUBLIC' else 'PRIVATE_HANDOFF' if rel['k'] == 0 else 'PRIVATE_REPLACE'
        got = handed.get(rel['txid'])
        ladder = schedule['ladders'][j]
        outpoint = funding['by_seat'].get(j)
        # Desktop r4445653922: the driver writes the hand-off, then the RELEASE, then the step's snapshot; a hand-off
        # line after its RELEASE (so after the snapshot that may show it) does not attest the release: rung_bytes.
        if got is None or got['event'] != want or got['seat'] != rel['seat'] or outpoint is None \
                or got['seq'] > rel['seq'] or got['seq'] < lower(rel['k']) \
                or [(i['txid'], i['vout']) for i in got['tx']['inputs']] != [(outpoint['txid'], outpoint['vout'])] \
                or not 0 <= rel['k'] < len(ladder) \
                or tx_fee_vsize(got['tx'], outpoint['value']) != (ladder[rel['k']], CANDIDATE_VSIZE) \
                or (want == 'PRIVATE_REPLACE' and got['replaced'] != last_private):
            bad.add('rung_bytes')
        else:
            paired.add(rel['txid'])
        if seat['path'] == 'PRIVATE':
            last_private = rel['txid']
    # Desktop r4448008178: only a hand-off line that is a RELEASE's validated hand-off starts or ends a hold or counts
    # as taken. The driver writes every hand-off right before its RELEASE (item2 `_release`; B.hand_off is called
    # there only), so a line no RELEASE pairs with is rung_bytes, and it is dropped from the hand-offs returned.
    if set(handed) - paired:
        bad.add('rung_bytes')
    return releases, {txid: h for txid, h in handed.items() if txid in paired}, bad


def item2_observed(scan: Scan, releases: list, handed: dict) -> tuple[set, int]:
    """045b :498, the distinct candidates seen in the gate: a public synthetic rung handed off whose txid is in the
    relay's mempool in a RELEASE_MEMPOOLS line after its RELEASE; a private rung the miner process took (its
    PRIVATE_HANDOFF or PRIVATE_REPLACE); an L0 rung handed off with L0_RELAY `at_relay` true or in a relay list taken
    at or after its `sent_ns` (by the lines' `t_ns`, one clock: L0 writes its RELEASE lines after the driver's own
    release steps, so a later step's relay list precedes them in the log). Returns the txids seen and the private
    ones' count."""
    relay = [(line['seq'], line['t_ns'], set(line['mempools']['relay'])) for line in scan.item2['RELEASE_MEMPOOLS']]
    l0_relay = {line['txid'] for line in scan.item2['L0_RELAY'] if line['at_relay']}
    seen, private = set(), set()
    for rel in releases:
        if not rel['handed_off']:
            continue
        if rel['l0']:
            later = any(t_ns >= rel['sent_ns'] and rel['txid'] in pool for _, t_ns, pool in relay)
        else:
            later = any(seq > rel['seq'] and rel['txid'] in pool for seq, _, pool in relay)
        if rel['path'] == 'PRIVATE':
            if rel['txid'] in handed:
                seen.add(rel['txid'])
                private.add(rel['txid'])
        elif later or (rel['l0'] and rel['txid'] in l0_relay):
            seen.add(rel['txid'])
    return seen, len(private)


def item2_private_exposed(scan: Scan, handed: dict) -> bool:
    """Desktop r4443056837: a private rung is held from its hand-off to the miner process (PRIVATE_HANDOFF, or
    PRIVATE_REPLACE) until a PRIVATE_REPLACE replaces it or a block holds it. The driver stops the run when a held
    private txid is in any node's mempool (`PRIVATE_IN_MEMPOOL`, ARV1 :99-103 and section 20, RUN_END FAILED; it never
    writes that snapshot), so a log that shows one in a `RELEASE_MEMPOOLS` list or a `MEMPOOL` line inside its hold is
    not the run the driver says it is (field `private_exposure`)."""
    snapshots = [(line['seq'], {t for pool in line['mempools'].values() for t in pool})
                 for line in scan.item2['RELEASE_MEMPOOLS']]
    snapshots += [(line['seq'], set(line['txids'])) for line in scan.item2['MEMPOOL']]
    replaced = {h['replaced']: h['seq'] for h in handed.values() if h['event'] == 'PRIVATE_REPLACE'}
    for txid, h in handed.items():
        if h['event'] == 'PUBLIC_SENT':
            continue
        mined = [b['seq'] for b in scan.blocks if any(tx['txid'] == txid for tx in b['txs'])]
        ends = ([replaced[txid]] if txid in replaced else []) + mined
        end = min(ends) if ends else None
        if any(h['seq'] < seq and (end is None or seq < end) and txid in pool for seq, pool in snapshots):
            return True
    return False


def item2_mempool_complete(scan: Scan, schedule: dict, releases: list) -> bool:
    """045b :498's complete mempool log (ARV1 section 20 step 4), matched by position: each release step k has its own
    RELEASE_MEMPOOLS line with that k after step k's synthetic RELEASE lines (and after the step before's line) and
    before any later step's RELEASE line and L0's first RELEASE; with L0 rungs released, one more line, of L0's
    last k, after L0's last RELEASE. A line is matched once, so L0's line never stands for a step's (P2-2)."""
    pools = [(line['seq'], line['k']) for line in scan.item2['RELEASE_MEMPOOLS']]
    synthetic = [rel for rel in releases if not rel['l0']]
    mine = [rel for rel in releases if rel['l0']]
    first_l0 = min((rel['seq'] for rel in mine), default=None)
    used: set[int] = set()
    previous = 0
    for step in schedule['rounds']:
        k = step['k']
        after = max([previous] + [rel['seq'] for rel in synthetic if rel['k'] == k])
        before = min([rel['seq'] for rel in synthetic if rel['k'] > k] + ([first_l0] if mine else []),
                     default=None)
        found = [seq for seq, kk in pools if kk == k and seq > after and (before is None or seq < before)
                 and seq not in used]
        if not found:
            return False
        used.add(found[0])
        previous = found[0]
    if mine:
        last = max(mine, key=lambda rel: rel['seq'])
        if not [seq for seq, kk in pools if kk == last['k'] and seq > last['seq'] and seq not in used]:
            return False
    return True


def item2_presence(scan: Scan, chain: dict, h0: int, schedule: dict, releases: list) -> dict:
    """The item-2 exclusion code re-derived from the log (045b :1050, :538; ARV1 section 20), one per gate in this
    order: RELEASE_NOT_IN_TEMPLATE (a seat's last released rung not in TEMPLATE(G)'s transactions, or the private
    rung not in its private set), RELEASE_AFTER_G (a release with `sent_ns` at or after t0 + t_G, t0 the submit time
    of block G - 1), G_LATE (TEMPLATE(G) taken 1 s or more after t0 + t_G); without block G,
    REPLACED_RUNG_NOT_IN_MEMPOOL when REPLACED_RUNG_MISSING is logged. `presence` / `timing` when TEMPLATE(G) or
    block G - 1 is not there to read; `timing` too when TEMPLATE(G) was taken before t0 + t_G (block G early: the
    run did not wait the frozen interval, 045b :537-538, Codex r4442135911). `release` when a rung k >= 1 is logged
    due at another time than t0 + 60 k, or sent before it; the released (seat, k) pairs are only reported."""
    out = {'code': None, 'seats': [], 'fields': [], 't0_ns': None, 'due_ns': None, 'template_ns': None,
           'lag_ns': None, 'misses': [], 'late': [], 'last_released': {}, 'release_pairs': None}
    block, before = chain['blocks'].get(h0), chain['blocks'].get(h0 - 1)
    # A decision 2026-11-02 (J4a round 2, P3-2 split): the released (seat, k) pairs against the plan's rounds are
    # reported, never an exclusion field: a release defect is :498's NO-GO (045b :498, FD-CT-92 row 8), reached
    # through the observed-against-predicted count only.
    pairs = sorted((rel['j'], rel['k']) for rel in releases)
    planned = sorted((j, step['k']) for step in schedule['rounds'] for j in step['seats'])
    counted = {pair: pairs.count(pair) for pair in set(pairs)}
    out['release_pairs'] = {
        'planned': [[f'S{j}', k] for j, k in planned], 'released': [[f'S{j}', k] for j, k in pairs],
        'missing': [[f'S{j}', k] for j, k in planned if (j, k) not in counted],
        'extra': [[f'S{j}', k] for j, k in sorted(counted) if (j, k) not in planned],
        'repeated': [[f'S{j}', k] for j, k in sorted(counted) if counted[(j, k)] > 1],
        'agree': pairs == planned}
    # P3-2 and Desktop r4443056830: a rung k >= 1 is due, and is not sent before, t0 + k x the rung spacing.
    for rel in releases if before is not None else []:
        due_k = before['t_ns'] + schedule['rung_seconds'] * rel['k'] * 1_000_000_000
        if rel['k'] >= 1 and (rel['due_ns'] != due_k or rel['sent_ns'] < due_k):
            out['fields'].append('release')
            break
    last: dict[int, dict] = {}
    for rel in releases:
        last[rel['j']] = rel
    out['last_released'] = {f'S{j}': {'k': rel['k'], 'txid': rel['txid'], 'path': rel['path']}
                            for j, rel in sorted(last.items())}
    if block is None:
        missing = scan.item2['REPLACED_RUNG_MISSING']
        if missing:
            out.update(code='REPLACED_RUNG_NOT_IN_MEMPOOL', seats=sorted({line['seat'] for line in missing}))
        return out
    template = block['template']
    if template is None:
        out['fields'].append('presence')
    if before is None:
        out['fields'].append('timing')
    if template is None or before is None:   # Codex r4445199350: only missing inputs stop the code's derivation;
        return out                           # a `release` mismatch keeps the gate codes, which take precedence
    t0 = before['t_ns']
    due = t0 + schedule['t_gate_seconds'] * 1_000_000_000
    listed = {item['txid'] for item in template['template']['transactions']}
    private = {item['txid'] for item in template['private_set']}
    misses = sorted(j for j, rel in last.items() if rel['txid'] not in (private if rel['path'] == 'PRIVATE'
                                                                        else listed))
    late = sorted({rel['j'] for rel in releases if rel['sent_ns'] >= due})
    lag = template['t_ns'] - due
    if lag < 0:
        out['fields'].append('timing')
    out.update(t0_ns=t0, due_ns=due, template_ns=template['t_ns'], lag_ns=lag, misses=[f'S{j}' for j in misses],
               late=[f'S{j}' for j in late])
    if misses:
        out.update(code='RELEASE_NOT_IN_TEMPLATE', seats=out['misses'])
    elif late:
        out.update(code='RELEASE_AFTER_G', seats=out['late'])
    elif lag >= ITEM2_G_LATE_NS:
        out.update(code='G_LATE')
    return out


def item2_l0(scan: Scan, policy: dict, mode: str, r: int, b: int, l0: int, schedule: dict, releases: list,
             candidates: list, observation: str | None = None) -> tuple[set, dict]:
    """The L0 seat's checks (045b :536-537, :1053-1055; ARV1 sections 22 and 26). `l0_fee`: the judge's ladder at p_0
    = l0_p0(b), i the larger increment and v 213 (at most 8 rungs, each at most the frozen 30,000 sat, 045b :1175)
    must equal L0_LAUNCH_START's `fee` (and its increments SCHEDULE's), L0_SET_CHARGED's fees, every rung's wallet row
    and charge base, each released rung's L0_ADMISSION (computed f_k, wallet row, charge base, both nodes' fee and
    vsize) and RELEASE, and the L0 rung read from block G's bytes. `l0_attempt`: the launch's seat, kind, attempt 1,
    attempt id `L0ATT-OBS-2<r:07>-01` and H0, L0_READY's one txid per rung, each release a charged rung of that
    attempt. `l0_budget`: the module's record in `budget_draft` (a BUDGET_DRAFT run) and L0_BUDGET.product's four
    fields, one budget digest, `exact_height_miss` the policy's (in CONFIRMATORY and in a POLICY_VALUE run,
    `l0_policy_valued`; else CONTINUE_WITHIN_LIMITS) in L0_LAUNCH_START, L0_BUDGET and L0_LABELS, and the wallet's
    `gate_attempts` at most 24. Returns the fields and the L0 facts reported."""
    lines = scan.item2
    bad = set()
    ladder = schedule['ladders'][l0]
    expected_attempt = 'L0ATT-%s-01' % (observation or item2_observation_id(r))   # J5: an item-4 run's own
    valued = l0_policy_valued(scan, mode)
    miss = policy['l0_seat']['exact_height_miss'] if valued else L0_DRAFT_MISS
    if not ladder or len(ladder) > L0_MAX_SET_RUNGS or max(ladder) > L0_MAX_FEE_PER_CANDIDATE:
        bad.add('l0_fee')
    launch = (lines['L0_LAUNCH_START'] or [None])[0]
    if launch is None:
        bad.add('l0_attempt')
    else:
        if (launch['seat'], launch['kind'], launch['attempt'], launch['attempt_id'], launch['h0']) != (
                f'S{l0}', L0_KIND, 1, expected_attempt, L0_H0):
            bad.add('l0_attempt')
        fee = launch['fee']
        if (fee['b'], fee['p0'], fee['i'], fee['v'], fee['k'], fee['ladder'], fee['f_k']) != (
                b, l0_p0(b), schedule['i'], CANDIDATE_VSIZE, 0, ladder, (ladder or [None])[0]) \
                or fee['increments'] != schedule['increments']:
            bad.add('l0_fee')
        if launch['exact_height_miss'] != miss or (not valued and launch.get('budget_draft') != L0_BUDGET_DRAFT):
            bad.add('l0_budget')
    charged = (lines['L0_SET_CHARGED'] or [None])[0]
    if charged is None or charged['attempt_id'] != expected_attempt:
        bad.add('l0_attempt')
    if charged is None or charged['fees'] != ladder or len(charged['rungs']) != len(ladder) \
            or charged['charge_bases'] is None or len(charged['charge_bases']) != len(ladder) \
            or any((row['k'], row['fee_sat'], row['wallet_fee_sat'], row['wallet_vsize'], base['absolute_fee_sat'])
                   != (k, ladder[k], ladder[k], CANDIDATE_VSIZE, ladder[k])
                   for k, (row, base) in enumerate(zip(charged['rungs'], charged['charge_bases']))):
        bad.add('l0_fee')
    ready = (lines['L0_READY'] or [None])[0]
    signed = {row['k']: row['txid'] for row in ready['rungs']} if ready is not None else {}
    if ready is None or ready['attempt_id'] != expected_attempt or sorted(signed) != list(range(len(ladder))) \
            or len(ready['rungs']) != len(ladder):
        bad.add('l0_attempt')
    # Desktop r4443056821: one txid per rung k from the charge to the signed set (and on to its release, below).
    if charged is None or {row['k']: row['txid'] for row in charged['rungs']} != signed:
        bad.add('l0_attempt')
    # Desktop r4445659421: every L0 row of the run names the attempt judged (the driver writes `self.attempt`).
    if any(line['attempt_id'] != expected_attempt for line in lines['L0_ADMISSION']):
        bad.add('l0_attempt')
    if any(line['attempt_id'] != expected_attempt for line in lines['L0_BUDGET']):
        bad.add('l0_attempt')
    if any(line['attempt_id'] != expected_attempt for line in lines['L0_LABELS'] + lines['L0_BUDGET_COUNTERS']):
        bad.add('l0_attempt')
    mine = [rel for rel in releases if rel['l0']]
    admissions: dict[int, list] = {}
    for line in lines['L0_ADMISSION']:
        admissions.setdefault(line['k'], []).append(line)
    if [rel['k'] for rel in mine] != list(range(len(mine))):
        bad.add('l0_attempt')   # L0 releases rungs 0, 1, ... of its set in order (ARV1 section 22, L0_SCHEDULE)
    if sorted(admissions) != sorted(rel['k'] for rel in mine) or any(len(v) != 1 for v in admissions.values()):
        bad.add('l0_fee')       # one L0_ADMISSION per released rung
    for rel in mine:
        k = rel['k']
        if signed.get(k) != rel['txid'] or rel['attempt_id'] != expected_attempt:
            bad.add('l0_attempt')
        f_k = ladder[k] if 0 <= k < len(ladder) else None
        if (rel['fee'], rel['vsize']) != (f_k, CANDIDATE_VSIZE):
            bad.add('l0_fee')
        for adm in admissions.get(k, []):
            if adm['txid'] != rel['txid'] or (adm['computed']['k'], adm['computed']['f_k']) != (k, f_k) \
                    or (adm['wallet']['fee_sat'], adm['wallet']['vsize'],
                        adm['wallet']['charge_base']['absolute_fee_sat']) != (f_k, CANDIDATE_VSIZE, f_k) \
                    or any((node['in_mempool'], node['fee'], node['vsize']) != (True, f_k, CANDIDATE_VSIZE)
                           for node in adm['nodes'].values()):
                bad.add('l0_fee')
    in_g = [c for c in candidates if c['j'] == l0]
    for c in in_g:
        if c['k'] is None or not 0 <= c['k'] < len(ladder) or (c['fee'], c['vsize']) != (ladder[c['k']],
                                                                                         CANDIDATE_VSIZE):
            bad.add('l0_fee')
    budget = (lines['L0_BUDGET'] or [None])[0]
    if budget is None or any(budget['product'][f] != L0_BUDGET_DRAFT[f] for f in L0_BUDGET_FIELDS) \
            or budget['product']['exact_height_miss'] != miss \
            or (charged is not None and budget['product']['budget_sha256'] != charged['budget_sha256']) \
            or budget['threshold_sat_per_attempt'] != L0_BUDGET_DRAFT['fee_row_threshold_sat_per_attempt']:
        bad.add('l0_budget')
    if any(line['exact_height_miss'] != miss for line in lines['L0_LABELS']):
        bad.add('l0_budget')
    counters = [line['counters'] for line in lines['L0_BUDGET_COUNTERS']]
    if counters and counters[-1]['gate_attempts'] > L0_MAX_GATE_ATTEMPTS:
        bad.add('l0_budget')
    released = {rel['k'] for rel in mine}
    held = [k for k in range(len(ladder)) if k not in released]
    labels = lines['L0_LABELS'][-1] if lines['L0_LABELS'] else None
    tests = []
    # Desktop r4446892881: a rung test of another attempt is l0_attempt and never enters the refusal count (:501).
    foreign = [line for line in lines['L0_RUNG_TEST'] if line['attempt_id'] != expected_attempt]
    if foreign:
        bad.add('l0_attempt')
    # Desktop r4448015560: the attempt's rung tests are one per charged rung k >= 1 (ARV1 section 22, L0_RUNG_TEST),
    # each with that rung's charged txid; a duplicate, a k outside the set or another txid is l0_attempt, and only
    # the first valid row of each k enters :501's refusal count.
    own = [line for line in lines['L0_RUNG_TEST'] if line['attempt_id'] == expected_attempt]
    ks = [line['k'] for line in own]
    charged_txids = {row['k']: row['txid'] for row in charged['rungs']} if charged is not None else {}
    if len(set(ks)) != len(ks):
        bad.add('l0_attempt')
    if set(ks) != set(range(1, len(ladder))):
        bad.add('l0_attempt')
    if any(line['txid'] != charged_txids.get(line['k']) for line in own):
        bad.add('l0_attempt')
    # Finding #788: a rung test's `when` is one of ARV1's two values. (New for item 2 only: item 4 already takes
    # CHARGED_NOT_RELEASED_BEFORE_G alone, section 24.)
    if any(line['when'] not in L0_RUNG_WHEN for line in own):
        bad.add('l0_attempt')
    # Finding #788: every charged row of a rung, so that two rows of one rung read the same in either order.
    charged_rows: dict[int, list] = {}
    for row in (charged['rungs'] if charged is not None else []):
        charged_rows.setdefault(row['k'], []).append(row)
    # J4c (section 28; 045b :501): 045a section 1.3 item 5 for rung k, read from the judge's ladder, the launch and the
    # charge, never from `l0_fee`'s absence (a FAILED attempt has no RELEASE lines, so `l0_fee` is set in every run with
    # a step-8 refusal). The step is item2_ladder's: max(1, ceil(i v / 1000)).
    step = max(1, ceil_div(schedule['i'] * CANDIDATE_VSIZE, 1000))
    fee5 = launch is not None and launch['fee']['ladder'] == ladder \
        and launch['fee']['increments'] == schedule['increments'] and charged is not None and charged['fees'] == ladder

    # Finding #788: two questions, kept apart, for a counted rung k (1 <= k < len(ladder)). None: the judge cannot
    # establish item 5. Item 5 compares f_k with f_(k-1), so both rungs need exactly one charged row with the judge's
    # fee and vsize; the launch and the charge must carry the judge's ladder; and rung k-1 needs exactly one
    # L0_ADMISSION in which each node's reported fee is the ladder's (the driver writes the released rungs'
    # admissions before a rung test, also in a failed attempt). Otherwise whether item 5 is met on the judge's
    # values: True, or False when the step is not reached (never on item2_ladder's own ladder, built with this step
    # at the same i and v; the comparison restates it).
    def item5(k: int) -> bool | None:
        for j in (k - 1, k):
            rows = charged_rows.get(j, [])
            if len(rows) != 1 or (rows[0]['wallet_fee_sat'], rows[0]['wallet_vsize']) != (ladder[j], CANDIDATE_VSIZE):
                return None
        before = admissions.get(k - 1, [])
        if not fee5 or len(before) != 1 or any(node['fee'] != ladder[k - 1] for node in before[0]['nodes'].values()):
            return None
        return ladder[k] - ladder[k - 1] >= step
    refusals, undecided, measured, unresolved = [], [], 0, 0
    counted: set[int] = set()
    for line in lines['L0_RUNG_TEST']:
        # ARV1 gives `nodes` as the two answers or null (an untested rung); a line without the key is neither, and
        # reads as a tested line with no answer (finding #788).
        k, when, nodes = line['k'], line['when'], line.get('nodes', {})
        allowed = {role: (nodes[role].get('allowed') if type(nodes) is dict and type(nodes.get(role)) is dict
                          and type(nodes[role].get('allowed')) is bool else None) for role in ('A', 'B')}
        replaces = {role: (nodes[role].get('replaces_in_mempool') if type(nodes) is dict
                           and type(nodes.get(role)) is dict and type(nodes[role].get('replaces_in_mempool')) is bool
                           else None) for role in ('A', 'B')}
        # The counting rule (section 21): the first row of each rung k >= 1 of the judge's ladder, of the judged
        # attempt, whose txid is a charged txid of that rung (finding #788: any charged row of k, not the last).
        is_counted = line['attempt_id'] == expected_attempt and k not in counted and 1 <= k < len(ladder) \
            and any(row['txid'] == line['txid'] for row in charged_rows.get(k, []))
        # Finding #788, fail closed: a node's answer is open when the line was tested (`nodes` not null), the node
        # did not answer `allowed` true and its `replaces_in_mempool` is not false (a node without the predecessor
        # refused no replacement).
        open_roles = [role for role in ('A', 'B')
                      if nodes is not None and allowed[role] is not True and replaces[role] is not False]
        if is_counted:
            counted.add(k)
            tests.append({'k': k, 'when': when, 'allowed': allowed})
            # A's decision on J4c: a counted BEFORE_RELEASE test with a node's answer measures :501 (an untested
            # rung, `nodes` null, is no refusal evidence: neither NO-GO nor undecided, and not a measurement).
            measured += when == 'BEFORE_RELEASE' and any(a is not None for a in allowed.values())
        # :501's NO-GO: a refusal before the rung's release, with the rung it replaces in that node's mempool (L0-501's
        # `replaces_in_mempool`), of a rung that meets item 5. A refusal whose field is missing cannot be told apart.
        if is_counted and when == 'BEFORE_RELEASE':
            met = item5(k)
            roles = [role for role in ('A', 'B') if allowed[role] is False and replaces[role] is True]
            unknown = [role for role in ('A', 'B') if allowed[role] is False and replaces[role] is None]
            if met and roles:
                refusals.append({'k': k, 'roles': roles})
            if met and unknown:
                undecided.append({'k': k, 'roles': unknown, 'why': 'REPLACES_UNKNOWN'})
            # Finding #788: a refusal of a rung whose item 5 the judge cannot establish is undecided too, with the
            # predecessor in that node's mempool or with the field missing (two unknowns must not read as healthy). It
            # was dropped, and the row could read GO with the refusal on record. `why` names the cause of each entry
            # (RUNG_UNDECIDED_WHY). As before, a rung whose item 5 is established and not met stays out of both lists,
            # and so does a refusal with `replaces_in_mempool` false (that node had nothing to replace).
            either = [role for role in ('A', 'B') if role in roles + unknown]
            if met is None and either:
                undecided.append({'k': k, 'roles': either, 'why': 'ITEM5_UNKNOWN'})
            # Finding #788: a node answer without a bool `allowed` is not an acceptance; the line is unresolved.
            unresolved += any(allowed[role] is None for role in open_roles)
        # Finding #788: a line that is not counted, or whose `when` is not BEFORE_RELEASE, is unresolved when a
        # node's answer on it is open: the judge cannot say that no replacement was refused. One exception, as
        # before: a counted CHARGED_NOT_RELEASED_BEFORE_G line of a rung without a RELEASE line, in an attempt that
        # has L0 RELEASE lines, tests no replacement the attempt made. Without any L0 RELEASE line (a FAILED
        # attempt) the judge cannot tell a held rung from a released one, and a line it does not count it cannot
        # tie to a rung at all.
        elif not is_counted or when != 'CHARGED_NOT_RELEASED_BEFORE_G' or k in released or not released:
            unresolved += bool(open_roles)
    facts = {'seat': f'S{l0}', 'attempt_id': launch['attempt_id'] if launch is not None else None,
             'p0': l0_p0(b), 'i': schedule['i'], 'ladder': ladder, 'released_ks': sorted(released),
             'charged_not_released': {'count': len(held), 'fee_sum_sat': sum(ladder[k] for k in held), 'ks': held},
             'in_g_ks': [c['k'] for c in in_g], 'budget_product': budget['product'] if budget is not None else None,
             'budget_counters': counters[-1] if counters else None,
             'labels': None if labels is None else {'in_g': labels['in_g'], 'born': labels['born'],
                                                    'match': labels['match'], 'scope': 'REPORTED_NOT_JUDGED'},
             'rung_tests': tests,
             'rung_tests_refused': sum(a is False for t in tests for a in t['allowed'].values()),
             'replacements': sum(rel['k'] >= 1 and rel['handed_off'] and any(
                 all(node['in_mempool'] for node in adm['nodes'].values()) for adm in admissions.get(rel['k'], []))
                 for rel in mine)}
    if observation is None:   # J4c: ITEM2 only; an item-4 run's facts are as before (it has no BEFORE_RELEASE test)
        facts.update(rung_refusals_501=refusals, rung_refusals_501_undecided=undecided,
                     rung_tests_before_release=measured, rung_tests_unresolved=unresolved)
    return bad, facts


def item2_replay_fields(replay: dict, h0: int, candidates: list) -> tuple[list[str], dict | None, list]:
    """The Core's births on the replayed chain (section 17): exactly one at G, a candidate of block G (`replay_birth`,
    also for zero births with candidates in G), and none at another height (`replay_other_birth`)."""
    bad, winner = [], None
    row = replay['rows'].get(h0)
    born = row['born'] if row is not None else []
    found = [c for c in candidates if c['txid'] in born]
    if len(born) == 1 and len(found) == 1:
        winner = found[0]
    else:
        bad.append('replay_birth')
    other = [{'height': h, 'born': replay['rows'][h]['born']} for h in sorted(replay['rows'])
             if h != h0 and replay['rows'][h]['born']]
    if other:
        bad.append('replay_other_birth')
    return bad, winner, other


def judge_item2(policy: dict, scan: Scan, prereg: dict, collection: dict | None, mode: str,
                replay_with: list[str] | None = None) -> dict:
    """One item-2 run's record (section 21). The unit's state is re-derived as the collection's (decision 11); a run
    the driver ended OBSERVED becomes EXCLUDED with the item-2 code the judge re-derives, else JUDGE_PLAN_MISMATCH:
    <field> (decision 4), else MEMPOOL_LOG_INCOMPLETE (045b :498); a driver code the judge does not reproduce stays
    and is a driver claim. The run's facts (winner, candidates, the section 4.5 counts) are description only."""
    r = scan.run
    params = policy['params']
    b, h0 = params['b'], params['H0']
    first = scan.first
    claims = Claims()
    killed = None
    if collection is not None and collection['state'] == 'EXCLUDED' and scan.run_end is not None \
            and scan.run_end.get('status') == 'DONE' and not scan.cut:
        killed = code_word(collection.get('code')) or 'UNIT_TIMEOUT'
    state = item2_unit_state(scan, r, killed)
    if collection is not None:
        need(collection['state'] == state['unit_state'], 'COLLECTION_DISAGREES', EXIT_REFUSAL)
    judged = state['unit_state'] == 'OBSERVED'
    l0 = l0_seat_of(first, policy, mode)
    item2_l0_binding(scan, policy, mode, l0, h0)
    plan = item2_plan(policy['seed'], r, b, l0)
    lines = scan.item2
    need(len(lines['SCHEDULE']) <= 1, 'RAW_LOG_DUPLICATE_EVENT')
    need(first['schedule_source'] in ('GATE_INTERVAL_DRAW', 'DRAFT_OVERRIDE'), 'RAW_LOG_ITEM2')
    fields: set[str] = set()
    if first['params'] != params:
        fields.add('params')
    if first['miner_policy'] != ITEM2_MINER_POLICY:
        fields.add('miner_policy')
    bidders = scan.bidders
    if not (bidders is not None and bidders['bidders_sha256'] == sha256(canonical(bidders['bidders']))
            and first['bidders_sha256'] == bidders['bidders_sha256']):
        fields.add('bidders_sha256')
    if bidders is None or bidders['bidders'] != plan['bidders'] \
            or (first['private_present'], first['order_constrained']) != (plan['private_present'],
                                                                          plan['qualifying']):
        fields.add('bidders')
    keys = ('label', 'n', 'k', 'value', 'feerate')
    if bidders is None or bidders['feerates'] != plan['feerates'] \
            or [{k: d.get(k) for k in keys} for d in bidders['draws']] != plan['draws']:
        fields.add('fee_draws')
    for line in lines['DRAW']:
        if line['label'] == 'GATE_INTERVAL':
            for field in ('value', 'k'):
                if line[field] != plan['gate_interval'][field]:
                    claims.note('DRAW', line['seq'], field, line[field], plan['gate_interval'][field])
    sched = (lines['SCHEDULE'] or [None])[0]
    schedule, bad = item2_schedule(plan, first, sched, b, l0)
    fields.update(bad)
    if sched is not None and sched['predicted_candidates'] != schedule['predicted']:
        claims.note('SCHEDULE', sched['seq'], 'predicted_candidates', sched['predicted_candidates'],
                    schedule['predicted'])
    chain = build_chain(scan, claims, strict=judged)
    funding = item2_funding(scan, chain, h0, plan, l0, claims)
    start, end = state['start'], state['end']
    if start is not None and (start['height'] != h0 or (end is not None and end['height'] != h0)):
        fields.add('height')
    g_minus_1 = chain['blocks'].get(h0 - 1)
    releases, handed, bad = item2_releases(scan, plan, schedule, funding, l0,
                                           g_minus_1['seq'] if g_minus_1 is not None else None)
    fields.update(bad)
    seen, private_seen = item2_observed(scan, releases, handed)
    if item2_private_exposed(scan, handed):
        fields.add('private_exposure')
    presence = item2_presence(scan, chain, h0, schedule, releases)
    fields.update(presence['fields'])
    mempool_complete = item2_mempool_complete(scan, schedule, releases)
    block = chain['blocks'].get(h0) if start is not None else None
    if judged and block is None:
        fields.add('block_g')
    by_txid = {(rel['j'], rel['txid']): rel['k'] for rel in releases}
    candidates = []
    for position, tx in enumerate(block['txs'][1:] if block is not None else [], 1):
        used = [(i['txid'], i['vout']) for i in tx['inputs']]
        seats = [funding['by_outpoint'][o] for o in used if o in funding['by_outpoint']]
        if not seats:
            continue
        j = seats[0]
        fee, vsize = tx_fee_vsize(tx, funding['by_seat'][j]['value'])
        k = by_txid.get((j, tx['txid']))
        register = register_form(tx, h0, h0)
        if len(used) != 1 or k is None or any(c['j'] == j for c in candidates) or not register:
            fields.add('rung_bytes')   # one input, a released rung of the seat, one per seat, the REGISTER form
        seat = plan['seats'][j]
        candidates.append({'j': j, 'seat': seat['seat'], 'path': seat['path'], 'kind': seat['kind'], 'k': k,
                           'txid': tx['txid'], 'position': position, 'weight': tx['weight'], 'vsize': vsize,
                           'fee': fee, 'register': register})
    if block is not None and not candidates:
        fields.add('block_g')
    # P1-1 (J4a check): a rung a seat released (or L0 charged) that block G holds must be that seat's candidate, read
    # through the seat's funding outpoint; else it is mined but unattributed, which would hide a mined losing rung.
    owner = {rel['txid']: rel['j'] for rel in releases}
    owner.update({row['txid']: l0 for line in lines['L0_READY'] for row in line['rungs']} if l0 is not None else {})
    attributed = {(c['txid'], c['j']) for c in candidates}
    in_g = [tx['txid'] for tx in block['txs'][1:]] if block is not None else []
    if any(txid in owner and (txid, owner[txid]) not in attributed for txid in in_g):
        fields.add('rung_bytes')
    if l0 is not None and any(p.startswith('L0_FUNDING') for p in funding['problems']) \
            and any(owner.get(txid) == l0 for txid in in_g):
        fields.add('l0_attempt')   # its rung is in G, and attribution needs the L0 funding outpoint
    replay, replay_other, winner = None, [], None
    if replay_with is not None and block is not None:
        replay = replay_chain(chain, h0, replay_with)
        bad, winner, replay_other = item2_replay_fields(replay, h0, candidates)
        fields.update(bad)
    elif block is not None and candidates:
        winner = candidates[0]   # 045b :421-423: the first candidate in G's order (no replay: unverified)
    l0_facts = None
    if l0 is not None:
        bad, l0_facts = item2_l0(scan, policy, mode, r, b, l0, schedule, releases, candidates)
        fields.update(bad)
    ordered = [f for f in ITEM2_FIELD_ORDER if f in fields]
    unit_state, code, source, code_seats = state['unit_state'], state['code'], 'LOG', state['code_seats']
    if judged and presence['code'] is not None:
        unit_state, code, source, code_seats = 'EXCLUDED', presence['code'], 'JUDGE', presence['seats']
    elif judged and ordered:
        unit_state, code, source, code_seats = 'EXCLUDED', 'JUDGE_PLAN_MISMATCH:' + ordered[0], 'JUDGE', []
    elif judged and not mempool_complete:
        unit_state, code, source, code_seats = 'EXCLUDED', MEMPOOL_LOG_INCOMPLETE, 'JUDGE', []
    elif not judged and presence['code'] == code:
        code_seats = presence['seats']
    elif not judged and code in ITEM2_CODES:
        claims.note('GATE_END', end['seq'] if end is not None else None, 'code', code, presence['code'])
    # A's decision (J4a review, 2026-11-02): an item-2 exclusion code of the driver the judge does not re-derive is
    # flagged; in the qualifying stratum it makes :381 NOT_ESTABLISHED (section 22).
    reproduced = not (source == 'LOG' and code in ITEM2_CODES and presence['code'] != code)
    born = [winner['txid']] if winner is not None else []
    unverified = []
    if end is not None and replay is None:   # no Core replay: GATE_END's birth claims stand unverified, not compared
        unverified = [{'field': 'born', 'claimed': end['born']}, {'field': 'winner', 'claimed': end['winner']}]
    if end is not None:
        compared = [('predicted_candidates', end['predicted_candidates'], schedule['predicted']),
                    ('observed_candidates', end['observed_candidates'], len(seen)),
                    ('block_hash', end['block_hash'], block['hash'] if block else None)]
        if replay is not None:
            compared += [('born', end['born'], born), ('winner', end['winner'], winner['seat'] if winner else None)]
        for field, claimed, derived in compared:
            if claimed != derived:
                claims.note('GATE_END', end['seq'], field, claimed, derived)
    core_replay_claims(scan, {'starts': {0: start} if start is not None else {}},   # without the replay, unverified
                       {0: {'txid': winner['txid'], 'height': h0}} if winner is not None and replay is not None else {},
                       replay, claims)
    # Desktop r4443064942: only a candidate of the REGISTER form counts as a mined REGISTER (:499, :500).
    losing = [c for c in candidates if c['register'] and (winner is None or c['txid'] != winner['txid'])]
    replacements = sum(rel['handed_off'] and rel['k'] >= 1 for rel in releases if not rel['l0'])
    l0_row = None
    if l0_facts is not None:
        l0_in_g = [c for c in candidates if c['j'] == l0]
        l0_lost = [c for c in l0_in_g if c['register'] and (winner is None or c['txid'] != winner['txid'])]
        l0_row = {'attempted': bool(lines['L0_LAUNCH_START']), 'in_g': bool(l0_in_g),
                  'born': winner is not None and winner['j'] == l0, 'mined_losing': bool(l0_lost),
                  'losing_fee_sat': sum(c['fee'] for c in l0_lost),
                  'losing_weight_wu': sum(c['weight'] for c in l0_lost)}
        replacements += l0_facts['replacements']
    handed_off = sum(rel['handed_off'] for rel in releases)
    winner_row = {k: winner[k] for k in ('seat', 'path', 'kind', 'txid')} if winner is not None else None
    observation = {
        'observation_id': item2_observation_id(r), 'state': unit_state, 'code': code, 'code_source': source,
        'code_reproduced': reproduced, 'mempool_log_complete': mempool_complete,
        'code_seats': code_seats, 'condition': plan['condition'], 'qualifying': plan['qualifying'], 'l0_seat': l0,
        'winner': winner_row, 'predicted_candidates': schedule['predicted'], 'observed_candidates': len(seen),
        'private_observed': private_seen, 'candidates_in_g': sum(c['register'] for c in candidates),
        'mined_losing': len(losing),
        'losing_weight_wu': sum(c['weight'] for c in losing), 'losing_fee_sat': sum(c['fee'] for c in losing),
        'l0': l0_row,
        'traffic': {'handed_off': handed_off, 'replacements': replacements, 'cancellations': 0,
                    'l0_replacements': l0_facts['replacements'] if l0_facts is not None else 0,
                    'l0_rung_tests_refused': l0_facts['rung_tests_refused'] if l0_facts is not None else 0,
                    'rung_refusals_501': l0_facts['rung_refusals_501'] if l0_facts is not None else [],
                    'rung_refusals_501_undecided': l0_facts['rung_refusals_501_undecided']
                    if l0_facts is not None else [],
                    'rung_tests_before_release': l0_facts['rung_tests_before_release'] if l0_facts is not None else 0,
                    'rung_tests_unresolved': l0_facts['rung_tests_unresolved'] if l0_facts is not None else 0},
        'mismatches': ordered}
    labels = list(ITEM2_RECORD_LABELS) + (['EXPLORATORY_NOT_A_VERDICT'] if mode != 'CONFIRMATORY' else [])
    if replay_with is None:
        births_label = 'UNVERIFIED_NO_REPLAY'
    else:
        births_label = 'REPLAYED' if replay is not None else 'NOT_REPLAYED_NO_JUDGED_GATE'
    outcome = {'result': POOL_RUN_RESULT, 'nogo': [], 'not_established': []}
    return {
        'schema': JUDGEMENT_SCHEMA, 'labels': labels, 'item': 'ITEM2', 'mode': mode,
        'evidence_status': 'CONFIRMATORY' if mode == 'CONFIRMATORY' else 'EXPLORATORY',
        'log_mode': first['mode'], 'log_evidence_status': first['evidence_status'],
        'births': births_label, 'replay': replay_summary(replay, replay_other),
        'judge': {'unit': 'J4A', 'tool_sha256': sha256(TOOL_PATH.read_bytes())},
        'inputs': {'policy_sha256': policy['sha256'], 'raw_log_sha256': scan.sha256, 'raw_log_bytes': scan.bytes,
                   'raw_log_lines': scan.lines, 'collection_given': collection is not None, 'prereg_045b': prereg,
                   'registration_sha256': first['registration_sha256']},
        'thresholds': threshold_table(),
        'unit': {'experiment': 'ITEM2', 'run': r, 'registered_runs': policy['count']},
        'params': dict(params, source=policy['params_source']),
        'plan': {'condition': plan['condition'], 'qualifying': plan['qualifying'], 'order_holds': plan['order_holds'],
                 'l0_seat': l0, 'l0_seat_source': first['l0_seat_source'], 'bidders': plan['bidders'],
                 'feerates': plan['feerates'], 'draws': plan['draws'], 'gate_interval': plan['gate_interval'],
                 'schedule_source': first['schedule_source'], 't_gate_seconds': schedule['t_gate_seconds'],
                 'rung_seconds': schedule['rung_seconds'], 'release_ks': schedule['release_ks'],
                 'increments': schedule['increments'], 'i': schedule['i'], 'ladders': schedule['ladders'],
                 'rounds': schedule['rounds'], 'predicted_candidates': schedule['predicted']},
        'run_shape': {'unit_state': state['unit_state'], 'code': state['code'], 'run_end': state['run_end'],
                      'phase': state['phase'], 'truncated': state['truncated'], 'killed': state['killed'],
                      'chain_tip': chain['tip'], 'stale_blocks': chain['stale'],
                      'rejected_blocks': scan.rejected_blocks,
                      'funding_problems': funding['problems'], 'collection_code': collection_code(collection)},
        'gate': {'height': h0 if block is not None else None, 'block_hash': block['hash'] if block else None,
                 'judge_code': presence['code'], 'judge_code_seats': presence['seats'],
                 'timing': {k: presence[k] for k in ('t0_ns', 'due_ns', 'template_ns', 'lag_ns')},
                 'misses': presence['misses'], 'late': presence['late'], 'last_released': presence['last_released'],
                 'released': [{k: rel[k] for k in ('seat', 'path', 'kind', 'k', 'txid', 'handed_off')}
                              for rel in releases][:SHOWN],
                 'observed_txids': sorted(seen)[:SHOWN], 'mempool_log_complete': mempool_complete,
                 'release_pairs': presence['release_pairs'],
                 'candidates_in_g': [{k: c[k] for k in ('seat', 'path', 'kind', 'k', 'txid', 'position', 'weight',
                                                         'vsize', 'fee', 'register')} for c in candidates],
                 'winner': winner_row, 'winner_source': 'REPLAY' if replay is not None else 'FIRST_IN_BLOCK_ORDER',
                 'unverified_claims': unverified,
                 'l0': l0_facts},
        'observation': observation,
        'driver_claims': claims.record(),
        'outcome': outcome,
        'verdict': verdict_block(outcome),
    }


def item2(args) -> dict:
    """The `item2` command: one ITEM2 run's raw log, bound as `pool` binds a POOL log (no method policy, no D2-2); in
    CONFIRMATORY also the policy's `l0_seat` (L0_FREEZE_PENDING without it), the log's seat and sources, no schedule
    override (RAW_LOG_SCHEDULE_OVERRIDE) and the registered budget digest (L0_BUDGET_SHA256). An EXPLORATORY log
    labelled POLICY_VALUE (B-FZ-a) is bound to the given policy's `l0_seat` the same way (`l0_seat_of`)."""
    mode = args.mode
    if mode == 'EXPLORATORY':
        need(args.registration is None, 'EXPLORATORY_REGISTRATION')
    need(not (args.no_replay and args.replay_bin is not None), 'REPLAY_OPTIONS')
    prereg = read_prereg(args.prereg)
    if mode == 'CONFIRMATORY':
        covering_registration(args, 'ITEM2')
    policy = parse_item2_policy(read_file(args.policy, 'POLICY', POLICY_LIMIT), mode)
    if mode == 'CONFIRMATORY':
        registered_log(args, policy, None, 'ITEM2')
    collection_blob = read_file(args.collection, 'COLLECTION', COLLECTION_LIMIT) if args.collection else None
    scan = scan_raw(args.raw, policy['sha256'], mode, 'ITEM2')
    need(mode != 'CONFIRMATORY' or scan.first['schedule_source'] != 'DRAFT_OVERRIDE', 'RAW_LOG_SCHEDULE_OVERRIDE',
         EXIT_REFUSAL)
    collection = run_collection_unit(collection_blob, scan.run, 'ITEM2') if collection_blob is not None else None
    record = judge_item2(policy, scan, prereg, collection, mode,
                         None if args.no_replay else replay_argv(args.replay_bin))
    if collection_blob is not None:
        record['inputs']['collection_sha256'] = sha256(collection_blob)
    return record


def run_collection_unit(blob: bytes, run: int, experiment: str) -> dict:
    """J4a: the collection's entry of a run-level unit (ARV1 section 13: `gates` null): OBSERVED or EXCLUDED, with a
    code."""
    doc = json_document(blob, 'COLLECTION')
    need(doc.get('schema') == COLLECTION_SCHEMA and type(doc.get('units')) is list, 'COLLECTION_SHAPE')
    unit = {'experiment': experiment, 'run': run, 'gate': None, 'cohort': None}
    found = [u for u in doc['units'] if type(u) is dict and u.get('unit') == unit]
    need(len(found) == 1, 'COLLECTION_UNIT')
    entry = found[0]
    need(entry.get('gates') is None and entry.get('state') in ('OBSERVED', 'EXCLUDED')
         and _code(entry.get('code')), 'COLLECTION_SHAPE')
    return entry


def nearest_rank(values: list[int], q: int) -> int | None:
    """045b :565-569: pq of N sorted values is the value at 1-based rank ceil(q N / 100), no interpolation."""
    ordered = sorted(values)
    return ordered[ceil_div(q * len(ordered), 100) - 1] if ordered else None


def above(value: dict, limit: dict) -> bool:
    """A defined fraction strictly above the limit (exact)."""
    return 'undefined' not in value and value['num'] * limit['den'] > limit['num'] * value['den']


def item2_rows(units: list[tuple[int, str, str | None, dict | None]], count: int) -> dict:
    """J4a, section 22: item 2 (045b :381, E13 :1218) and the section 4.5 rows :498-:501 over the registered runs.
    `units` holds, per run r < N, its state (OBSERVED, EXCLUDED, NOT_STARTED), its code and its record's observation
    (None without a record). Statistics use OBSERVED runs only."""
    observed = [(r, obs) for r, s, _, obs in units if s == 'OBSERVED']
    lost = sum(s != 'OBSERVED' for _, s, _, _ in units)
    ten = lost * EXCLUSION_DEN > EXCLUSION_NUM * count
    stratum_units = [(r, s) for r, s, _, _ in units if item2_qualifying(r)]
    stratum_lost = sum(s != 'OBSERVED' for _, s in stratum_units)
    stratum = stratum_lost * ITEM2_STRATUM['den'] > ITEM2_STRATUM['num'] * len(stratum_units)
    # A's clarification (2026-11-02) of J4a decision 2: the E13 stratum gates only :381, the statistic over the
    # qualifying sample (045b :1218 amends :381 and :540); :499 and :500 are over the attempted gates, gated by the
    # 10% rule and their own "not reported" (NOT_MEASURED).
    ten_rule = ['TEN_PERCENT_RULE'] if ten else []
    gating = ten_rule + (['QUALIFYING_STRATUM_RULE'] if stratum else [])

    def row(nogo: list[str], not_established: list[str], defect: bool) -> dict:
        if defect:   # A's J4a decision 2: a defect row is NO_GO first, as item 1 (section 12)
            result = 'NO_GO' if nogo else 'NOT_ESTABLISHED' if not_established else 'GO'
        else:        # a statistic row: NOT_ESTABLISHED first, as POOL (section 20)
            result = 'NOT_ESTABLISHED' if not_established else 'NO_GO' if nogo else 'GO'
        return {'result': result, 'nogo': nogo, 'not_established': not_established}

    # 045b :381 and :1218: the private win share over the OBSERVED qualifying runs, NO_GO above 1/2 (strictly).
    qualifying = [obs for r, obs in observed if item2_qualifying(r)]
    private = sum(obs['winner'] is not None and obs['winner']['path'] == 'PRIVATE'
                  and obs['winner']['kind'] == 'SYNTHETIC' for obs in qualifying)
    share = fraction(private, len(qualifying))
    # A's decision (J4a review, 2026-11-02): a driver item-2 exclusion the judge does not re-derive is counted by
    # condition; one in the qualifying stratum makes :381 NOT_ESTABLISHED whatever the stratum count.
    unreproduced = {c: 0 for c in ITEM2_CONDITIONS}
    for r, _, _, obs in units:
        if obs is not None and not obs['code_reproduced']:
            unreproduced[item2_condition(r)] += 1
    win_row = row(['ITEM2_PRIVATE_WIN_SHARE_ABOVE_MAX'] if above(share, ITEM2_PRIVATE_WIN_MAX) else [],
                  gating + ([] if qualifying else ['NO_JUDGED_GATES'])
                  + (['DRIVER_EXCLUSION_UNREPRODUCED'] if unreproduced['ORDER_CONSTRAINED'] else []), False)
    by_path = {c: {'runs': 0, 'PRIVATE': 0, 'PUBLIC': 0, 'L0': 0, 'NONE': 0} for c in ITEM2_CONDITIONS}
    flow = {'private': 0, 'all': 0}
    for r, obs in observed:
        part = by_path[item2_condition(r)]
        part['runs'] += 1
        w = obs['winner']
        part['NONE' if w is None else 'L0' if w['kind'] == L0_KIND else w['path']] += 1
        if r % 2 == 0:
            flow['private'] += obs['private_observed']
            flow['all'] += obs['observed_candidates']
    exclusions = {'by_condition': {c: {'excluded': 0, 'missing': 0} for c in ITEM2_CONDITIONS}, 'by_code': {},
                  'by_seat': {}, 'l0_seat': {'runs': 0, 'by_code': {}}}
    for r, s, code, obs in units:
        if s == 'OBSERVED':
            continue
        exclusions['by_condition'][item2_condition(r)]['excluded' if s == 'EXCLUDED' else 'missing'] += 1
        code = code or 'NONE'
        exclusions['by_code'][code] = exclusions['by_code'].get(code, 0) + 1
        for seat in (obs['code_seats'] if obs is not None else []):
            exclusions['by_seat'][seat] = exclusions['by_seat'].get(seat, 0) + 1
        if obs is not None and obs['l0_seat'] is not None and 'S%d' % obs['l0_seat'] in obs['code_seats']:
            exclusions['l0_seat']['runs'] += 1   # 045b :1050: the L0 seat's exclusions on a line of their own
            exclusions['l0_seat']['by_code'][code] = exclusions['l0_seat']['by_code'].get(code, 0) + 1
    # :498 (Ledger B): observed against predicted in every OBSERVED gate; a defect row.
    seen = [obs['observed_candidates'] for _, obs in observed]
    # A decision 2026-11-02 (J4a round 2, P3-2 split): a run EXCLUDED only by release timing (`release` its one
    # mismatch) whose mempool log is complete still reaches the count comparison, so the timing exclusion cannot
    # hide a release defect. Every other exclusion leaves the gate out (045b :498, :538).
    timing_only = [(r, obs) for r, s, c, obs in units if s == 'EXCLUDED' and obs is not None
                   and c == 'JUDGE_PLAN_MISMATCH:release' and obs['mismatches'] == ['release']
                   and obs['mempool_log_complete']]
    compared = sorted(observed + timing_only, key=lambda pair: pair[0])
    differ = [r for r, obs in compared if obs['observed_candidates'] != obs['predicted_candidates']]
    candidates_row = dict(row(['CANDIDATES_DIFFER'] if differ else [],
                              ten_rule + ([] if observed else ['NO_JUDGED_GATES']), True),
                          gates=len(observed), compared=len(compared),
                          release_timing_excluded_compared=[r for r, _ in timing_only][:SHOWN],
                          differ=differ[:SHOWN], differ_count=len(differ),
                          observed={'mean': fraction(sum(seen), len(seen)), 'p95': nearest_rank(seen, 95),
                                    'max': max(seen, default=None)},
                          predicted={'mean': fraction(sum(obs['predicted_candidates'] for _, obs in observed),
                                                      len(observed))},
                          release_not_in_template_left_out=sum(s == 'EXCLUDED' and c == 'RELEASE_NOT_IN_TEMPLATE'
                                                               for _, s, c, _ in units))
    # :499 and :500 (Ledger A): the project's attempted gates are the OBSERVED runs with an L0 attempt (A's J4a
    # decision 3); the figure over every started run with one is reported beside it.
    attempted = [obs for _, obs in observed if obs['l0'] is not None and obs['l0']['attempted']]
    started = [obs for _, _, _, obs in units if obs is not None and obs['l0'] is not None and obs['l0']['attempted']]
    measured = [] if attempted else ['NOT_MEASURED']
    project = fraction(sum(obs['l0']['mined_losing'] for obs in attempted), len(attempted))
    in_g = sum(obs['candidates_in_g'] for _, obs in observed)
    losing = sum(obs['mined_losing'] for _, obs in observed)
    mined_row = dict(row(['MINED_LOSING_SHARE_ABOVE_MAX'] if attempted and above(project, MINED_LOSING_MAX) else [],
                         ten_rule + measured, False),
                     mined_registers=in_g, mined_losing=losing, mined_losing_share=fraction(losing, in_g),
                     project_attempted_gates=len(attempted), project_share=project,
                     project_share_all_started=fraction(sum(obs['l0']['mined_losing'] for obs in started),
                                                        len(started)))
    fee_sum = sum(obs['l0']['losing_fee_sat'] for obs in attempted)
    per_attempt = fraction(fee_sum, len(attempted))
    fee_row = dict(row(['LOSING_FEE_PER_ATTEMPT_ABOVE_MAX'] if attempted and above(per_attempt, LOSING_FEE_MAX) else [],
                       ten_rule + measured, False),
                   losing_weight_wu=sum(obs['losing_weight_wu'] for _, obs in observed),
                   losing_fee_sat=sum(obs['losing_fee_sat'] for _, obs in observed),
                   per_gate_weight_wu=fraction(sum(obs['losing_weight_wu'] for _, obs in observed), len(observed)),
                   per_gate_fee_sat=fraction(sum(obs['losing_fee_sat'] for _, obs in observed), len(observed)),
                   project_losing_fee_sat=fee_sum, project_fee_per_attempt=per_attempt,
                   project_fee_per_attempt_all_started=fraction(sum(obs['l0']['losing_fee_sat'] for obs in started),
                                                                len(started)),
                   threshold=LOSING_FEE_MAX)
    # :501 (Ledger B): J4c (section 28) judges its NO-GO, a defect row: a project rung refused by Node A or B before
    # its release with the rung it replaces in that node's mempool, meeting item 5, in any run with a record (FAILED
    # and EXCLUDED included: a step-8 refusal ends the attempt FAILED). The other figures stay reported.
    replaced = sum(obs['traffic']['replacements'] for _, obs in observed)
    handed = sum(obs['traffic']['handed_off'] for _, obs in observed)
    refused = [dict(x, run=r) for r, _, _, obs in units if obs is not None
               for x in obs['traffic']['rung_refusals_501']]
    # Finding #788: the undecided rungs are of two kinds, told apart by the entry's `why`, each with its own code and
    # its own list in the row: a refusal whose `replaces_in_mempool` is missing on a rung that meets item 5
    # (REPLACES_UNKNOWN), and a refusal of a rung whose item 5 the judge could not establish (ITEM5_UNKNOWN). The
    # second list is the complement of the first, so no entry can fall between the two.
    undecided = [dict(x, run=r) for r, _, _, obs in units if obs is not None
                 for x in obs['traffic']['rung_refusals_501_undecided']]
    unknown = [x for x in undecided if x['why'] == 'REPLACES_UNKNOWN']
    item5_unknown = [x for x in undecided if x['why'] != 'REPLACES_UNKNOWN']
    # A's decision on J4c (045b :489-492): no counted BEFORE_RELEASE test in any record leaves :501 unmeasured, as
    # :499's NOT_MEASURED.
    tested = sum(obs['traffic']['rung_tests_before_release'] for _, _, _, obs in units if obs is not None)
    # Finding #788: rung-test lines the judge could not resolve (not counted, mislabelled, or a node answer without a
    # bool `allowed`), over every unit with a record.
    unresolved = sum(obs['traffic']['rung_tests_unresolved'] for _, _, _, obs in units if obs is not None)
    traffic_row = dict(row(['PROJECT_REPLACEMENT_REFUSED'] if refused else [],
                           ten_rule + (['RUNG_TEST_REPLACES_UNKNOWN'] if unknown else [])
                           + (['RUNG_TEST_ITEM5_UNKNOWN'] if item5_unknown else [])
                           + (['RUNG_TEST_UNRESOLVED'] if unresolved else [])
                           + ([] if tested else ['NOT_MEASURED']), True),
                       project_rung_tests_before_release=tested,
                       replacements=replaced,
                       cancellations=0, per_gate=fraction(replaced, len(observed)),
                       share_of_candidate_traffic=fraction(replaced, handed),
                       project_replacements=sum(obs['traffic']['l0_replacements'] for _, obs in observed),
                       project_rung_tests_refused_all_started=sum(obs['traffic']['l0_rung_tests_refused']
                                                                  for _, _, _, obs in units if obs is not None),
                       project_replacements_refused=refused[:SHOWN], project_replacements_refused_count=len(refused),
                       rung_tests_replaces_unknown=unknown[:SHOWN], rung_tests_replaces_unknown_count=len(unknown),
                       rung_tests_item5_unknown=item5_unknown[:SHOWN],
                       rung_tests_item5_unknown_count=len(item5_unknown),
                       rung_tests_unresolved_count=unresolved)
    rows = {'381': dict(win_row, qualifying_observed=len(qualifying), private_wins=private,
                        private_win_share=share, threshold=ITEM2_PRIVATE_WIN_MAX),
            '498': candidates_row, '499': mined_row, '500': fee_row, '501': traffic_row}
    # Section 29 (045b :1090): each finished row's requirement verdict, its criterion from the constant table beside
    # the figure the row already holds. A figure the judge did not measure is null or an `undefined` fraction, never
    # the criterion's value: no gate compared (:498), no attempted gate (:499, :500), no counted rung test (:501).
    views = {'381': ({'private_win_share_max': ITEM2_PRIVATE_WIN_MAX, 'stratum_limit': ITEM2_STRATUM},
                     {'private_win_share': share, 'qualifying_observed': len(qualifying)}),
             '498': ({'candidates': constant('CANDIDATES_EXACT')},
                     {'compared': len(compared), 'differ_count': len(differ) if compared else None}),
             '499': ({'project_share_max': MINED_LOSING_MAX},
                     {'project_share': project, 'project_attempted_gates': len(attempted)}),
             '500': ({'project_fee_per_attempt_max': LOSING_FEE_MAX}, {'project_fee_per_attempt': per_attempt}),
             '501': ({'project_replacements_refused': 0},   # 045b :501: any refused project replacement is the defect
                     {'project_replacements_refused': len(refused) if tested or refused else None,
                      'rung_tests_before_release': tested, 'undecided': len(undecided), 'unresolved': unresolved})}
    for key, (criterion, figures) in views.items():
        rows[key]['verdict'] = verdict_block(rows[key], dict(criterion, exclusion_limit=EXCLUSION_LIMIT), figures)
    return {'stratum': {'runs': len(stratum_units), 'missing_or_excluded': stratum_lost, 'limit': ITEM2_STRATUM,
                        'over_limit': stratum},
            'missing_or_excluded': lost, 'over_10_percent': ten,
            'rows': rows,
            'win_share_by_path': by_path, 'driver_exclusions_unreproduced': unreproduced,
            'private_order_flow_share': dict(fraction(flow['private'], flow['all']), scope='REPORTED_NOT_JUDGED'),
            'exclusions': exclusions}


# ---------------------------------------------------------------------------------------------------------
# J5: one item-4 run (ARDR_JUDGE_V1 section 24; A's J5 decisions, #258 issuecomment-6656311995). ITEM4_SELF_DEALING,
# ITEM4_FEE_ASYMMETRY, ITEM4_CENSORSHIP or ITEM4_REORG with the L0 project seat (ARV1 sections 23-26), or in
# EXPLORATORY with the stand-in (labels NOT_APPLICABLE_STANDIN, A's Q7): the plan recomputed, every block and rung read
# from the bytes, the host's labels parsed from the set worker's own lines (`L0_TURN`) and judged against 045b :1068 and
# its 2026-11-05 note, and a reorg run's replaced branch replayed beside the final chain.

ITEM4_RUN_COUNT = constant('ITEM4_RUNS')
ITEM4_MINER_POLICIES = {'ITEM4_SELF_DEALING': 'ITEM4_SELF_FIRST_ZERO_FEE', 'ITEM4_FEE_ASYMMETRY': ITEM2_MINER_POLICY,
                        'ITEM4_CENSORSHIP': 'ITEM4_CENSOR_144', 'ITEM4_REORG': 'ITEM4_REORG_REPLACE'}   # ARV1 sec. 23
ITEM4_STANDIN = 'PROJECT_STANDIN'      # ARV1 section 23: the synthetic stand-in project seat (W01)
# A's Q3: the role a scenario is built to let win; a birth of any other seat's rung is the driver's defect (`winner`).
ITEM4_ADVERSARY = {'ITEM4_SELF_DEALING': 'SELF', 'ITEM4_FEE_ASYMMETRY': 'ASYMMETRIC', 'ITEM4_CENSORSHIP': 'COMPETITOR',
                   'ITEM4_REORG': 'COMPETITOR'}
ITEM4_SELF_FEE = constant('ITEM4_SELF_FEE')
ITEM4_FACTOR = constant('ITEM4_ASYM_FACTOR')
ITEM4_DRAW = constant('ITEM4_ASYM_DRAW')
ITEM4_ASYM_SEATS = constant('ITEM4_ASYM_SEATS_MEDIAN')
ITEM4_FEE_CAP = constant('ITEM4_ASYM_FEE_CAP')
ITEM4_COMPETITOR = constant('ITEM4_COMPETITOR_FEE')
ITEM4_WINDOW = constant('ITEM4_CENSOR_WINDOW')
ITEM4_DEPTHS = constant('ITEM4_REORG_DEPTH')
ITEM4_PROJECT_SEAT = constant('ITEM4_L0_SEAT')
ITEM4_L0_H0 = constant('ITEM4_H0')
ITEM4_LIMIT = constant('ITEM4_SUBSCENARIO_LIMIT')
ITEM4_LABEL_CHECKS = tuple(constant('ITEM4_LABEL_CHECK_JUDGED'))
ITEM4_MISS_VALUE = constant('ITEM4_MISS')
ITEM4_LINE = constant('ITEM4_LABEL_LINE')
ITEM4_MARK = constant('ITEM4_RELEASE_MARK')
ITEM4_NOT_RUN_CASES = constant('ITEM4_NOT_RUN_LIST')
ITEM4_JUDGED_FIELDS = tuple(constant('ITEM4_MISLABEL_FIELDS'))
ITEM4_PLAN_TURNS = constant('ITEM4_TURNS')
ITEM4_INCLUDED = constant('ITEM4_LABEL_INCLUDED')
ITEM4_LOST = constant('ITEM4_LABEL_LOST')
ITEM4_UNRELEASED = constant('ITEM4_LABEL_UNRELEASED')
ITEM4_LABEL_FLAGS = constant('ITEM4_FLAGS')
ITEM4_BORN = constant('ITEM4_E9D_BORN')
ITEM4_BORN_OTHER = constant('ITEM4_E9D_OTHERS')
ITEM4_LOCKED = constant('ITEM4_E9D_LOCKED')
ITEM4_STALE_TURN = constant('ITEM4_E9D_STALE')
ITEM4_E9D_FLAGS = constant('ITEM4_E9D_FLAGS')
ITEM4_L0_SEAT_KEYS = L0_SEAT_KEYS - {'seat'}   # ARV1 section 26: `seat` is ITEM2's only
ITEM4_SET_WORKER = 'launch_set_worker'          # ARV1 section 22: the set worker; its observing phases (section 25)
ITEM4_OBSERVING = ('set_observe', 'set_reorged', 'set_release')
ITEM4_TIP_TURNS = (('REORGED', 'set_reorged'), ('RELEASE', 'set_release'), ('STALE', 'set_observe'))   # ARV1 sec. 25
ITEM4_RECORD_LABELS = ['CLASS_T', 'REGTEST', 'JUDGE_RECORD', 'J5_ITEM4_RUN']
NOT_APPLICABLE_STANDIN = 'NOT_APPLICABLE_STANDIN'
ITEM4_FIELD_ORDER = ('params', 'miner_policy', 'bidders_sha256', 'bidders', 'fee_draws', 'fees', 'asymmetric',
                     'not_run', 'schedule', 'height', 'block_g', 'presence', 'rung_bytes', 'release',
                     'private_exposure', 'self_first', 'censor_window', 'censor_mempool', 'reorg_depth',
                     'reorg_replaced', 'reorg_readded', 'reorg_offered', 'reorg_seen', 'l0_turns', 'l0_fee',
                     'l0_budget', 'l0_attempt', 'replay_birth', 'replay_replaced', 'replay_other_birth', 'winner')
# A driver exclusion code (ARV1 sections 23-25) and the judge's fields that reproduce it from the bytes (plan D10).
ITEM4_DRIVER_CODES = {'ITEM4_CENSOR_LEAK': ('censor_window',), 'ITEM4_CENSOR_NOT_LIFTED': ('censor_window',),
                      'ITEM4_CENSOR_END': ('censor_window',), 'ITEM4_WINNER_READDED': ('reorg_readded',),
                      'ITEM4_SELF_NOT_FIRST': ('self_first',), 'ITEM4_SELF_FEE_NOT_LOWEST': ('self_first',),
                      'ITEM4_TEMPLATE_STALE': ('reorg_offered',), 'ITEM4_REPLACED_NOT_WINNER': ('replay_replaced',),
                      'ITEM4_WINNER_STILL_BORN': ('replay_birth', 'replay_other_birth', 'winner'),
                      'ITEM4_L0_CENSORED_LEFT_MEMPOOL': ('censor_mempool',), 'ITEM4_L0_NOT_IN_G': ('reorg_replaced',),
                      'ITEM4_L0_REORG_SEEN': ('reorg_seen',), 'L0_REORG_LINE': ('reorg_seen',)}
ITEM4_TRANSITIONS = ('DONE_BORN', 'PROJECT_BORN_BY_OTHER', 'STALE_OPENING_MISSED', 'INCLUDED_NO_EFFECT', 'REORG67_LOCK',
                     'REORG67_RELEASE_CLASS_T', 'GATE_ADVANCED', 'OFFLINE_SIGNATURE_PENDING')   # A's Q13: reported
# J5b: the minimum transitions (045b :1279; inventory section 2): each sub-scenario's TR ids and the reach they need.
ITEM4_MIN_TRANSITIONS = constant('ITEM4_MIN_TRANSITIONS')
ITEM4_MIN_REACH = constant('ITEM4_MIN_REACH')


def item4_observation_id(scenario: str, r: int) -> str:
    """The item-4 unit is the run: `OBS-<e><r:07>`, e = 4 ... 7 in ARV1 section 3's order (ARV1 section 23)."""
    return 'OBS-%d%07d' % (EXPERIMENTS.index(scenario) + 1, r)


def item4_depth(r: int) -> int:
    """045b :1070: depth 1 for even r, depth 2 for odd r."""
    return ITEM4_DEPTHS['even'] if r % 2 == 0 else ITEM4_DEPTHS['odd']


def item4_turn_plan(scenario: str, r: int) -> list[dict]:
    """The host turns a run takes (045b :1068 and its note; ARV1 sections 24-25): G for self dealing and fee asymmetry;
    G, G + 143 and G + 144 for censorship; for a reorg run G (and G + 1 at depth 2) on the replaced branch, then
    REORGED, RELEASE and STALE at the replacement tip G + d."""
    if scenario == 'ITEM4_REORG':
        d = item4_depth(r)
        turns = [{'turn': 'G' if k == 0 else f'G+{k}', 'offset': k, 'phase': 'set_observe', 'branch': 'REPLACED'}
                 for k in range(d)]
        return turns + [{'turn': name, 'offset': d, 'phase': phase, 'branch': 'FINAL'}
                        for name, phase in ITEM4_TIP_TURNS]
    return [{'turn': name, 'offset': offset, 'phase': 'set_observe', 'branch': 'FINAL'}
            for name, offset in ITEM4_PLAN_TURNS[scenario]]


def item4_plan(seed: bytes, scenario: str, r: int, b: int, l0: bool) -> dict:
    """The run's seats, roles, fixed fees or draws, depth, turns and not-run list (045b :1065-1079, :1219; ARV1 section
    23 and 24). The project seat (S1 in self dealing and fee asymmetry, S0 in censorship and reorg) is the L0 seat
    (`L0_PROJECT` / `L0` / PUBLIC) or the stand-in (SYNTHETIC W01 PUBLIC). Its configured p_0 is l0_p0(b) (045b
    :1053, :1079), its rung 0 f_0 = ceil(p_0 x 213 / 1000). Self dealing: S0 the PRIVATE `SELF` seat at 600 sat. Fee
    asymmetry: S0 `ASYMMETRIC`, S2-S4 `HONEST` drawing `BID_FEE_j` (n = 3b + 1, feerate b + value); the median is the
    nearest-rank p50 of [p_0, the three draws]; S0 pays one rung of ceil(10 x median x 213 / 1000) sat. Censorship and
    reorg: S1 `COMPETITOR` (C00) at 2 f_0 + 1, released after G in the reorg run."""
    p = ITEM4_PROJECT_SEAT[scenario]
    project = ({'kind': L0_KIND, 'wallet': L0_WALLET, 'path': 'PUBLIC', 'role': L0_KIND} if l0
               else {'kind': 'SYNTHETIC', 'wallet': 'W01', 'path': 'PUBLIC', 'role': ITEM4_STANDIN})
    if scenario == 'ITEM4_SELF_DEALING':
        others = [{'kind': 'SYNTHETIC', 'wallet': 'W00', 'path': 'PRIVATE', 'role': 'SELF'}]
    elif scenario == 'ITEM4_FEE_ASYMMETRY':
        others = [{'kind': 'SYNTHETIC', 'wallet': 'W%02d' % ITEM4_ASYM_SEATS['asymmetric'], 'path': 'PUBLIC',
                   'role': 'ASYMMETRIC'}] + [{'kind': 'SYNTHETIC', 'wallet': 'W%02d' % j, 'path': 'PUBLIC',
                                              'role': 'HONEST'} for j in ITEM4_ASYM_SEATS['drawn']]
    else:
        others = [{'kind': 'COMPETITOR', 'wallet': 'C00', 'path': 'PUBLIC', 'role': 'COMPETITOR'}]
    rows = others[:p] + [project] + others[p:]
    seats = [dict(row, seat=f'S{j}') for j, row in enumerate(rows)]
    roles = {s['seat']: s['role'] for s in seats}
    bidders = {'schema': BIDDERS_SCHEMA, 'gates': [{'gate': r, 'seats': [
        {k: s[k] for k in ('seat', 'kind', 'wallet', 'path')} for s in seats]}]}
    p0 = l0_p0(b)
    f0 = ceil_div(p0 * CANDIDATE_VSIZE, 1000)
    fees: dict[str, list[int] | None] = {}
    draws: list[dict] = []
    rates, asym = None, None
    if scenario == 'ITEM4_FEE_ASYMMETRY':
        rates = [p0]
        for label in ITEM4_DRAW['labels']:
            value, k = draw(seed, ITEM4_DRAW['e'], r, label, 3 * b + 1)
            draws.append({'e': ITEM4_DRAW['e'], 'r': r, 'label': label, 'n': 3 * b + 1, 'k': k, 'value': value,
                          'feerate': b + value})
            rates.append(b + value)
        median = nearest_rank(rates, 50)
        feerate = ITEM4_FACTOR['factor'] * median
        fee = ceil_div(feerate * CANDIDATE_VSIZE, 1000)
        asym = {'median': median, 'factor': ITEM4_FACTOR['factor'], 'feerate': feerate, 'fee': fee,
                'honest_feerates': list(rates), 'factor_source': ITEM4_FACTOR['source'],
                'cap_exceeded': fee > ITEM4_FEE_CAP}
        for j, s in enumerate(seats):
            role = s['role']
            fees[s['seat']] = ([fee] if role == 'ASYMMETRIC' else None if role == L0_KIND
                               else item2_ladder(rates[0] if j == p else rates[j - 1], b, 0)[:1])
    else:
        for s in seats:
            fees[s['seat']] = {'SELF': [ITEM4_SELF_FEE], 'COMPETITOR': [ITEM4_COMPETITOR['times'] * f0
                                                                         + ITEM4_COMPETITOR['plus']],
                               ITEM4_STANDIN: [f0], L0_KIND: None}[s['role']]
    not_run = []
    for name in ('ITEM4_CENSORSHIP', 'ITEM4_SELF_DEALING'):
        if scenario == name:
            not_run.append([name, ITEM4_NOT_RUN_CASES[name]])
    not_run.append(['*', ITEM4_NOT_RUN_CASES['L0' if l0 else 'STANDIN']])
    return {'scenario': scenario, 'run': r, 'project': p, 'l0': l0, 'seats': seats, 'roles': roles,
            'bidders': bidders, 'p0': p0, 'f0': f0, 'fees': fees, 'draws': draws, 'feerates': rates,
            'asymmetric': asym, 'depth': item4_depth(r) if scenario == 'ITEM4_REORG' else None,
            'after_g': [s['seat'] for s in seats if scenario == 'ITEM4_REORG' and s['role'] == 'COMPETITOR'],
            'turns': item4_turn_plan(scenario, r) if l0 else [], 'not_run': not_run}


def check_item4_l0_seat_shape(value) -> None:
    """`experiments.ITEM4_<S>.l0_seat` (ARV1 section 26): exactly `p0_rule`, `max_gate_attempts`, `exact_height_miss`
    and `budget_sha256` (no `seat`), each a PENDING string or a value of its kind (POLICY_L0_SEAT)."""
    checks = {'p0_rule': _str, 'max_gate_attempts': lambda v: type(v) is int and v >= 1,
              'exact_height_miss': lambda v: v in EXACT_HEIGHT_MISS, 'budget_sha256': _hex64}
    need(type(value) is dict and set(value) == ITEM4_L0_SEAT_KEYS
         and all(pending(value[k]) or checks[k](value[k]) for k in ITEM4_L0_SEAT_KEYS), 'POLICY_L0_SEAT')


def parse_item4_policy(blob: bytes, mode: str, experiment: str) -> dict:
    """J5: one item-4 experiment's part of a BITAGI_CT_ARDR_POLICY_V1 file (ARV1 sections 3, 18, 23 and 26): the pinned
    miner policy, params in every mode (POLICY_PARAMS_UNSET), one gate per run (POLICY_ITEM4_GATES), H0 at least 107
    (POLICY_ITEM4_H0), and for ITEM4_SELF_DEALING a project rung 0 above the 600-sat self fee (b >= 1058, 045b :1065;
    POLICY_ITEM4_SELF_FEE). `l0_seat` has the item-4 shape. CONFIRMATORY needs the count and the key
    (L0_FREEZE_PENDING) with `MAX_P0_TWO_RUNGS`, 24 attempts and CONTINUE_WITHIN_LIMITS (045b :1053, :1068;
    POLICY_L0_VALUES); a CONFIRMATORY policy, or one with a non-PENDING key, needs H0 1000 (045b :1054).
    2026-11-10 (A, after the freeze): the CONFIRMATORY key's `budget_sha256` is the frozen Class T L0 record's too,
    `7d0a7a35…` (045b section 14.21 :1898, the record for the ARDR L0 seat; the driver refuses any other before any
    node, `confirmatory_l0_seat`, ARV1 section 26 :2557-2558), as item 2's. `complete` as item 2's (`l0_seat_of`):
    no PENDING value anywhere, every experiment counted, each count an int 1 .. U32-1 and every `counts` key an
    experiment; CONFIRMATORY requires it (J5b, as item 2's)."""
    doc, experiments = policy_head(blob, mode)
    confirmatory = mode == 'CONFIRMATORY'
    need(experiment in ITEM4_SCENARIOS and experiment in experiments, 'POLICY_ITEM4')
    need(all('method_policy' not in entry for name, entry in experiments.items() if name != 'ITEM1'),
         'POLICY_METHOD_POLICY')
    entry = experiments[experiment]
    need(set(entry) <= {'miner_policy', 'params', 'l0_seat'} and 'miner_policy' in entry, 'POLICY_ITEM4')
    need(not pending(entry['miner_policy']), 'POLICY_PENDING', EXIT_PREREQUISITE)
    need(entry['miner_policy'] == ITEM4_MINER_POLICIES[experiment], 'POLICY_MINER_EXPERIMENT')
    counts = doc['counts']
    need(pending(counts) or type(counts) is dict, 'POLICY_SHAPE')
    count = counts.get(experiment) if type(counts) is dict else None
    # 2026-11-10 (A, Desktop P3 on #669, as `parse_item2_policy`): each count an int 1 .. U32-1 (POLICY_COUNTS);
    # J5b verification round: and every `counts` key an experiment (POLICY_COUNTS's other half).
    complete = (not pending(doc) and type(counts) is dict and set(experiments) <= set(counts) <= set(EXPERIMENTS)
                and all(int_in(value, 1, U32 - 1) for value in counts.values()))
    if confirmatory:
        need(int_in(count, 1, U32 - 1), 'POLICY_COUNT_UNSET', EXIT_PREREQUISITE)
        need(complete, 'POLICY_COUNT_UNSET', EXIT_PREREQUISITE)   # 2026-11-10 (A, J5b): as `parse_item2_policy`
    params, source = policy_params(entry.get('params'), True, {}, GATES_PER_RUN_MAX)
    need(params['gates_per_run'] == 1, 'POLICY_ITEM4_GATES')
    need(params['H0'] >= ITEM2_MIN_H0, 'POLICY_ITEM4_H0')
    if experiment == 'ITEM4_SELF_DEALING':
        need(ceil_div(l0_p0(params['b']) * CANDIDATE_VSIZE, 1000) > ITEM4_SELF_FEE, 'POLICY_ITEM4_SELF_FEE')
    seat = entry.get('l0_seat')
    if seat is not None:
        check_item4_l0_seat_shape(seat)
    if confirmatory:
        need(seat is not None, 'L0_FREEZE_PENDING', EXIT_PREREQUISITE)
        # 2026-11-10 (A, J5b; A's Q4 on #719): the digest pin is the frozen Class T record's (`7d0a7a35…`, 045b
        # section 14.21 :1898; L0_PRODUCT_BUDGET_SHA256). Item 4 registers in the follow-up registration (045b
        # :317-320): if that policy names another budget record, this pin moves with it; nothing changes here before.
        need(seat['p0_rule'] == L0_P0_RULE and seat['max_gate_attempts'] == L0_MAX_GATE_ATTEMPTS
             and seat['exact_height_miss'] == ITEM4_MISS_VALUE
             and seat['budget_sha256'] == L0_PRODUCT_BUDGET_SHA256[ITEM4_MISS_VALUE], 'POLICY_L0_VALUES')
    if confirmatory or (seat is not None and not pending(seat)):
        need(params['H0'] == ITEM4_L0_H0, 'POLICY_ITEM4_H0')
    return {'sha256': sha256(blob), 'seed': bytes.fromhex(doc['seed']), 'params': params, 'params_source': source,
            'count': count if type(count) is int else None, 'method_policy': None, 'l0_seat': seat,
            'experiment': experiment, 'complete': complete}


def item4_unit_state(scan: Scan, scenario: str, r: int, killed: str | None) -> dict:
    """The unit's state re-derived from the log as the collection derives it (ARV1 section 13; decision 11), as
    `item2_unit_state` with the item-4 observation id: OBSERVED iff RUN_END DONE after GATE_END OBSERVED (and no kill
    the collection reports); EXCLUDED with RUN_END EXCLUDED's code, RUN_END FAILED's code (phase SETUP, GATE or END), or
    RUN_END_MISSING / RAW_LOG_TRUNCATED. The label judgement is kept apart (A's Q1, 045b :1084's note)."""
    obs = item4_observation_id(scenario, r)
    need(scan.first['gates'] == [r], 'RAW_LOG_GATES')
    starts = [line for line in scan.gate_lines if line['event'] == 'GATE_START']
    ends = [line for line in scan.gate_lines if line['event'] == 'GATE_END']
    need(all(line['gate'] == r and line['unit']['gate'] == r and line['observation_id'] == obs
             for line in scan.gate_lines), 'RAW_LOG_GATES')
    need(len(starts) <= 1 and len(ends) <= 1 and (not ends or (starts and ends[0]['seq'] > starts[0]['seq'])),
         'RAW_LOG_GATES')
    start, end = (starts or [None])[0], (ends or [None])[0]
    run_end = scan.run_end
    info = {'unit_state': 'EXCLUDED', 'code': 'RAW_LOG_TRUNCATED' if scan.cut else 'RUN_END_MISSING',
            'run_end': None, 'phase': None, 'truncated': scan.cut, 'killed': killed is not None,
            'code_seats': [], 'start': start, 'end': end}
    if run_end is not None:
        status = run_end['status']
        info['run_end'] = status
        need(status == 'DONE' or run_end['excluded_gates'] == [r], 'RAW_LOG_GATES')
        if status == 'DONE':
            need(end is not None and end['status'] == 'OBSERVED', 'RAW_LOG_GATES')
            if killed is None:
                info.update(unit_state='OBSERVED', code='DONE')
            else:
                info['code'] = killed
        elif status == 'EXCLUDED':
            need(end is not None and end['status'] == 'EXCLUDED' and end['code'] == run_end['code'], 'RAW_LOG_ITEM4')
            info.update(code=run_end['code'], code_seats=list(end['code_seats']) if _strs(end.get('code_seats'))
                        else [])
        else:
            info.update(code=code_word(run_end['code']) or 'RUN_END_FAILED', phase=run_end['phase'])
    return info


def item4_binding(scan: Scan, policy: dict, mode: str, scenario: str, h0: int) -> bool:
    """The item-4 lines' own binding refusals. Returns whether the project seat is the L0 seat. `RUN_START.scenario`
    is the log's experiment and `project_seat` `L0_PROJECT` or `PROJECT_STANDIN` (RAW_LOG_ITEM4); a CONFIRMATORY
    stand-in log is RAW_LOG_ITEM4_STANDIN (exit 6; ARV1 :2077-2078, A's Q7). The L0 lines bind as item 2's
    (`item2_l0_binding`: none in a stand-in log, H0 1000, the budget source and digest); REPLACED_RUNG_MISSING only in a
    stand-in log; one line of each item-4 singleton (RAW_LOG_DUPLICATE_EVENT), and a scenario's own lines only in its
    log (RAW_LOG_ITEM4). A release step outside ITEM4_REORG, and in a CONFIRMATORY reorg log a release turn the driver
    accepted (or an ITEM4_L0_RELEASE line) without the TEST_ONLY mark (`ITEM4_L0_OBSERVE.procedure.mark` and
    `ITEM4_L0_RELEASE.step` both RELEASE_REORG67_TEST_ONLY; 045b :1069, A's Q10), is RAW_LOG_RELEASE_MARK (exit 6).
    2026-11-10 (A, after B-FZ-a): an L0 log outside CONFIRMATORY whose L0_LAUNCH_START says POLICY_VALUE
    (`l0_policy_valued`) ran on the policy's key, so the key is one the L0 run takes, as item 2's (`l0_seat_of`): the
    policy complete, the key present, `p0_rule` MAX_P0_TWO_RUNGS, 24 attempts, `budget_sha256` the product's record for
    its `exact_height_miss` (`confirmatory_l0_seat`; ARV1 section 26 :2557-2558), else RAW_LOG_L0_SOURCE (exit 6)."""
    first, lines = scan.first, scan.item2
    need(first['scenario'] == scenario, 'RAW_LOG_ITEM4')
    need(first['project_seat'] in (L0_KIND, ITEM4_STANDIN), 'RAW_LOG_ITEM4')
    l0 = first['project_seat'] == L0_KIND
    if mode == 'CONFIRMATORY':
        need(l0, 'RAW_LOG_ITEM4_STANDIN', EXIT_REFUSAL)
    elif l0 and l0_policy_valued(scan, mode):
        key = policy['l0_seat']
        need(key is not None and policy['complete'], 'RAW_LOG_L0_SOURCE', EXIT_REFUSAL)
        need(key['p0_rule'] == L0_P0_RULE and key['max_gate_attempts'] == L0_MAX_GATE_ATTEMPTS
             and key['budget_sha256'] == L0_PRODUCT_BUDGET_SHA256[key['exact_height_miss']],
             'RAW_LOG_L0_SOURCE', EXIT_REFUSAL)
    item2_l0_binding(scan, policy, mode, ITEM4_PROJECT_SEAT[scenario] if l0 else None, h0)
    need(not (l0 and lines['REPLACED_RUNG_MISSING']), 'RAW_LOG_ITEM4')
    need(all(len(lines[e]) <= 1 for e in ('SCHEDULE', 'SCENARIO_NOT_RUN', 'ASYMMETRIC_BID', 'SELF_REGISTER',
                                          'CENSOR_WINDOW', 'CENSOR_MEMPOOL', 'REORG', 'ITEM4_L0_RELEASE',
                                          'ITEM4_L0_LABEL_LINE')), 'RAW_LOG_DUPLICATE_EVENT')
    owners = {'ASYMMETRIC_BID': 'ITEM4_FEE_ASYMMETRY', 'SELF_REGISTER': 'ITEM4_SELF_DEALING',
              'CENSOR_WINDOW': 'ITEM4_CENSORSHIP', 'CENSOR_MEMPOOL': 'ITEM4_CENSORSHIP', 'REORG': 'ITEM4_REORG',
              'ITEM4_L0_LABEL_LINE': 'ITEM4_REORG'}
    need(all(not lines[event] or scenario == owner for event, owner in owners.items()), 'RAW_LOG_ITEM4')
    release_turns = [t for t in lines['L0_TURN'] if t['worker'] == ITEM4_SET_WORKER
                     and t['lines'].get('phase') == 'set_release']
    need(scenario == 'ITEM4_REORG' or not (release_turns or lines['ITEM4_L0_RELEASE']), 'RAW_LOG_RELEASE_MARK',
         EXIT_REFUSAL)
    return l0


def item4_release_mark(scan: Scan, plan: dict, turns: list, mode: str, done: bool) -> str | None:
    """045b :1069, A's Q10 and A's decision on the J5 check (P2-1): a CONFIRMATORY ITEM4_REORG run's TEST_ONLY release
    carries its mark in the raw log. The release turn is found by its position in the planned turns (never by the
    phase an `ITEM4_L0_OBSERVE` claims). Every mark present is RELEASE_REORG67_TEST_ONLY. When the run went past the
    release turn (a later turn, or RUN_END DONE), the release turn's `ITEM4_L0_OBSERVE.procedure.mark` is there; when
    it went past the STALE turn's checks (RUN_END DONE, or an `ITEM4_L0_LABEL_LINE`: ARV1 section 25 writes
    `ITEM4_L0_RELEASE` after the STALE turn and its checks, and the label line after it), so is the one
    `ITEM4_L0_RELEASE.step`. A run stopped inside the release turn (`L0_RELEASE_NOT_REORG67`) has no mark yet. Else
    RAW_LOG_RELEASE_MARK (exit 6). Returns the mark state recorded (None outside CONFIRMATORY ITEM4_REORG)."""
    if mode != 'CONFIRMATORY' or plan['scenario'] != 'ITEM4_REORG':
        return None
    at = [t['turn'] for t in plan['turns']].index(ITEM4_LINE['after'])
    release = turns[at] if at < len(turns) else None
    observe = release['observe'] if release is not None else None
    marks = [o['procedure'].get('mark') if type(o.get('procedure')) is dict else None
             for o in scan.item2['ITEM4_L0_OBSERVE'] if 'procedure' in o or o is observe]
    steps = [x['step'] for x in scan.item2['ITEM4_L0_RELEASE']]
    need(all(mark == ITEM4_MARK for mark in marks + steps), 'RAW_LOG_RELEASE_MARK', EXIT_REFUSAL)
    past_release = done or len(turns) > at + 1
    past_stale = done or bool(scan.item2['ITEM4_L0_LABEL_LINE'])
    need(not past_release or (observe is not None and type(observe.get('procedure')) is dict
                              and observe['procedure'].get('mark') == ITEM4_MARK), 'RAW_LOG_RELEASE_MARK', EXIT_REFUSAL)
    need(not past_stale or steps == [ITEM4_MARK], 'RAW_LOG_RELEASE_MARK', EXIT_REFUSAL)
    return 'MARKED' if past_release or past_stale or marks or steps else 'STOPPED_BEFORE_THE_MARK'


def item4_schedule(plan: dict, sched: dict | None, b: int) -> tuple[dict, set]:
    """i (the larger of SCHEDULE's two increments) and every seat's ladder: the L0 seat's by 045b :537 at FD-CT-133's
    l0_p0(b), v 213 (`l0_fee`); a censorship stand-in's first two rungs of it (ARV1 section 23); every other seat's
    the plan's one rung (`fees`). `schedule` when SCHEDULE is missing or its `increment`, rule, `after_g` (the reorg
    run's competitor), ladder count, `l0_seat` or `l0_release_ks` ([0]: item 4 has no t_G) is not the judge's."""
    bad = set()
    increments = sched['increments'] if sched is not None else {'A': 0, 'B': 0}
    i = max(increments['A'], increments['B'])
    ladders = []
    for s in plan['seats']:
        if s['role'] == L0_KIND:
            ladders.append(item2_ladder(plan['p0'], b, i))
        elif s['role'] == ITEM4_STANDIN and plan['scenario'] == 'ITEM4_CENSORSHIP':
            ladders.append(item2_ladder(plan['p0'], b, i)[:2])
        else:
            ladders.append(list(plan['fees'][s['seat']]))
    p, l0 = plan['project'], plan['l0']
    if sched is None:
        bad.add('schedule')
    else:
        if (sched['increment'], sched.get('increment_rule'), sched['rule'], sched['after_g'], len(sched['ladders'])) \
                != (i, 'MAX_NODE_A_NODE_B', 'G_WHEN_RELEASED_IN_TEMPLATE', plan['after_g'], len(ladders)):
            bad.add('schedule')
        if (sched.get('l0_seat'), sched.get('l0_release_ks')) != ((f'S{p}', [0]) if l0 else (None, None)):
            bad.add('schedule')
        logged = sched['ladders'] + [None] * len(ladders)
        for j, ladder in enumerate(ladders):
            if logged[j] != ladder:
                bad.add('l0_fee' if l0 and j == p else 'fees')
    if any(not ladder for ladder in ladders) or (not l0 and plan['scenario'] == 'ITEM4_CENSORSHIP'
                                                and len(ladders[p]) != 2):
        bad.add('schedule')
    return {'increments': increments, 'i': i, 'ladders': ladders}, bad


def item4_releases(scan: Scan, plan: dict, ladders: list, funding: dict, floor_seq: int | None,
                   g_seq: int | None, whole: bool = False) -> tuple[list, dict, set]:
    """Every RELEASE line with the bytes handed off (PUBLIC_SENT for a public rung, PRIVATE_HANDOFF for the self seat's
    rung 0); L0's rungs (`sent_by` L0_STEP8) carry no bytes. A synthetic or competitor rung handed off must have its
    hand-off line between block G − 1's BLOCK line (`floor_seq`) and its RELEASE, spend exactly its seat's funding
    output with one input, and pay its ladder's f_k at vsize 213 (`rung_bytes`; another fee: `fees`); a hand-off no
    RELEASE pairs with is `rung_bytes`. `release`: a path other than its seat's, a release before block G − 1, a
    before-G release after block G or an after-G one (the reorg run's competitor, the censorship stand-in's rung 1)
    before it, a (seat, k) twice or one the plan does not release (in a whole run, `whole`: also one it does not
    get)."""
    lines = scan.item2
    bad = set()
    handed: dict[str, dict] = {}
    for event in ('PUBLIC_SENT', 'PRIVATE_HANDOFF'):
        for line in lines[event]:
            try:
                tx = parse_tx(hex_bytes(line['hex'], 'RAW_LOG_ITEM4'))
            except (Malformed, KeyError):
                raise Refusal('RAW_LOG_ITEM4') from None
            if tx['txid'] != line['txid'] or tx['txid'] in handed:
                bad.add('rung_bytes')
            handed[tx['txid']] = {'event': event, 'seat': line['seat'], 'tx': tx, 'seq': line['seq']}
    p, l0, scenario = plan['project'], plan['l0'], plan['scenario']
    releases, paired = [], set()
    for line in lines['RELEASE']:
        need(SEAT_NAME.match(line['seat']) is not None and int(line['seat'][1:]) < len(plan['seats']), 'RAW_LOG_ITEM4')
        j = int(line['seat'][1:])
        is_l0 = line.get('sent_by') == L0_SENT_BY
        need(is_l0 == (l0 and j == p), 'RAW_LOG_L0')   # only the L0 seat releases through L0, and only through L0
        seat = plan['seats'][j]
        after = seat['seat'] in plan['after_g'] or (not l0 and scenario == 'ITEM4_CENSORSHIP' and j == p
                                                   and line['k'] == 1)
        rel = {'j': j, 'seat': line['seat'], 'role': seat['role'], 'path': seat['path'], 'kind': seat['kind'],
               'k': line['k'], 'txid': line['txid'], 'seq': line['seq'], 'sent_ns': line['sent_ns'],
               'handed_off': line['handed_off'], 'l0': is_l0, 'fee': line.get('fee'), 'vsize': line.get('vsize'),
               'attempt_id': line.get('attempt_id'), 'after_g': after}
        releases.append(rel)
        if line['path'] != seat['path'] or floor_seq is None or line['seq'] < floor_seq \
                or (g_seq is not None and (line['seq'] > g_seq) != after) or (g_seq is None and after):
            bad.add('release')
        if is_l0 or not rel['handed_off']:
            continue
        want = 'PUBLIC_SENT' if seat['path'] == 'PUBLIC' else 'PRIVATE_HANDOFF'
        got = handed.get(rel['txid'])
        outpoint = funding['by_seat'].get(j)
        ladder = ladders[j]
        if got is None or got['event'] != want or got['seat'] != rel['seat'] or outpoint is None \
                or got['seq'] > rel['seq'] or floor_seq is None or got['seq'] < floor_seq \
                or (want == 'PRIVATE_HANDOFF' and rel['k'] != 0) \
                or [(i['txid'], i['vout']) for i in got['tx']['inputs']] != [(outpoint['txid'], outpoint['vout'])] \
                or not 0 <= rel['k'] < len(ladder) or ceil_div(got['tx']['weight'], 4) != CANDIDATE_VSIZE:
            bad.add('rung_bytes')
            continue
        paired.add(rel['txid'])
        if tx_fee_vsize(got['tx'], outpoint['value'])[0] != ladder[rel['k']]:
            bad.add('fees')
    if set(handed) - paired:
        bad.add('rung_bytes')
    planned = sorted([(j, 0) for j, s in enumerate(plan['seats']) if s['seat'] not in plan['after_g']]
                     + [(j, 0) for j, s in enumerate(plan['seats']) if s['seat'] in plan['after_g']]
                     + ([(p, 1)] if not l0 and scenario == 'ITEM4_CENSORSHIP' else []))
    got_pairs = sorted((rel['j'], rel['k']) for rel in releases)
    if len(set(got_pairs)) != len(got_pairs) or not set(got_pairs) <= set(planned) \
            or (whole and got_pairs != planned):
        bad.add('release')
    return releases, {txid: h for txid, h in handed.items() if txid in paired}, bad


def item4_branches(scan: Scan, chain: dict, h0: int, depth: int | None) -> dict:
    """FINAL is `build_chain`'s chain (from the last accepted BLOCK back). `g_first` is the first block the log wrote at
    H0 on FINAL's G − 1: block G as the run mined it. In a reorg run the original branch is `g_first` and its
    descendants up to H0 + d − 1 by previous-block hash, in log order; `replaced` holds those not on FINAL (none
    before the reorg); `other_stale` every other accepted block on neither."""
    final = chain['blocks']
    parent = final.get(h0 - 1)
    g_first = next((block for block in scan.blocks if parent is not None and block['height'] == h0
                    and block['prev'] == parent['hash']), None)
    orig = {}
    if g_first is not None:
        orig[h0] = g_first
        for k in range(1, depth or 1):
            nxt = next((block for block in scan.blocks if block['height'] == h0 + k
                        and block['prev'] == orig[h0 + k - 1]['hash']), None)
            if nxt is None:
                break
            orig[h0 + k] = nxt
    if depth is None:
        orig = {}
    on_final = {id(block) for block in final.values()}
    replaced = {h: block for h, block in orig.items() if id(block) not in on_final}
    kept = on_final | {id(block) for block in orig.values()}
    other = [block for block in scan.blocks if id(block) not in kept]
    branch = {h: block for h, block in final.items() if h < h0}
    branch.update(orig)
    return {'final': final, 'g_first': g_first, 'orig': branch, 'replaced': replaced, 'other_stale': other}


def item4_hits(block: dict, txids: set, outpoint: tuple | None) -> list[str]:
    """A block's project transactions, read from its bytes (045b :1079, :1220): a txid of the project's set or any
    spend of its funding outpoint, whatever its txid."""
    return [tx['txid'] for tx in block['txs'][1:] if tx['txid'] in txids
            or (outpoint is not None and any((i['txid'], i['vout']) == outpoint for i in tx['inputs']))]


def item4_candidates(block: dict, funding: dict, k_of: dict, plan: dict, h0: int) -> tuple[list, bool]:
    """A block's transactions that spend a seat's funding outpoint (045b :1220: attributed by the outpoint, never by
    Anchor key), with fee, vsize and weight from the bytes. The second value is true when one has more than one input,
    is not a known rung of its seat, is a second one of its seat or is not of the REGISTER form for target H0."""
    out, bad = [], False
    for position, tx in enumerate(block['txs'][1:], 1):
        used = [(i['txid'], i['vout']) for i in tx['inputs']]
        seats = [funding['by_outpoint'][o] for o in used if o in funding['by_outpoint']]
        if not seats:
            continue
        j = seats[0]
        fee, vsize = tx_fee_vsize(tx, funding['by_seat'][j]['value'])
        k = k_of.get((j, tx['txid']))
        register = register_form(tx, h0, h0)
        if len(used) != 1 or k is None or any(c['j'] == j for c in out) or not register:
            bad = True
        seat = plan['seats'][j]
        out.append({'j': j, 'seat': seat['seat'], 'role': seat['role'], 'kind': seat['kind'], 'path': seat['path'],
                    'k': k, 'txid': tx['txid'], 'position': position, 'weight': tx['weight'], 'vsize': vsize,
                    'fee': fee, 'register': register, 'height': block['height']})
    return out, bad


def item4_parse_labels(text, n: int) -> list[tuple[str, str]] | None:
    """The set worker's raw `labels` line, read by rung name: `r<j>=<verdict>/<outcome>` for every rung of the set once
    (ARV1 section 22, host `set_verdict`). None when it is not that form."""
    out: dict[int, tuple[str, str]] = {}
    for item in text.split(';') if type(text) is str and text else []:
        name, _, value = item.partition('=')
        verdict, _, outcome = value.partition('/')
        if not (name.startswith('r') and DECIMAL.match(name[1:]) and verdict and outcome):
            return None
        j = int(name[1:])
        if j in out or j >= n:
            return None
        out[j] = (verdict, outcome)
    return [out[j] for j in range(n)] if sorted(out) == list(range(n)) else None


def item4_parse_flags(text, n: int) -> list[dict] | None:
    """The set worker's raw `flags` line, read by rung name: `r<j>=opening_block_missed:<true|false>,
    reorged_before_inclusion:<true|false>` for every rung once (ARV1 section 24, host `set_flags`). None otherwise."""
    names = list(ITEM4_LABEL_FLAGS)
    out: dict[int, dict] = {}
    for item in text.split(';') if type(text) is str and text else []:
        name, _, value = item.partition('=')
        parts = value.split(',')
        if not (name.startswith('r') and DECIMAL.match(name[1:]) and [x.partition(':')[0] for x in parts] == names
                and all(x.partition(':')[2] in ('true', 'false') for x in parts)):
            return None
        j = int(name[1:])
        if j in out or j >= n:
            return None
        out[j] = {x.partition(':')[0]: x.partition(':')[2] == 'true' for x in parts}
    return [out[j] for j in range(n)] if sorted(out) == list(range(n)) else None


def item4_fill(template: dict, h0: int, height: int | None = None, next_birth: int | None = None) -> dict:
    """A label constant with its placeholders filled: `<height>` (the inclusion height), `<G>` and `<H0>` (H0) and
    `<next birth>` (the replay's next birth). This is the host's rendering (ARV1 sections 24-25), the one 045b :1068's
    note writes (`Stale@G><next birth>`, `IncludedNoEffect@<height>`)."""
    out = {}
    for key in ('verdict', 'outcome'):
        text = template[key].replace('<G>', str(h0)).replace('<H0>', str(h0))
        if height is not None:
            text = text.replace('<height>', str(height))
        if next_birth is not None:
            text = text.replace('<next birth>', str(next_birth))
        out[key] = text
    return out


def item4_expected(scenario: str, planned: dict, h: int, h0: int, branch: dict, rows: dict, set_txids: list,
                   released: set) -> list[dict] | None:
    """Every rung's expected label at one turn (045b :415, :416, :419, :1068 and its 2026-11-05 note), the case chosen
    from the bytes (A's Q3): on the turn's branch up to its height, a rung the replay found born is `Done:Born` and the
    set's other rungs `Done:ProjectBornByOther` (flags false: before the replacement tip); otherwise a rung a block
    holds is `IncludedNoEffect@<its height>`; otherwise the rung is `Stale@<H0>><next birth>`, its verdict
    `Refuse:Locked(Reorg67)` at the two locked turns, `Refuse:GateAdvanced` when released, else
    `Wait:OfflineSignaturePending`. Every rung not born has `opening_block_missed` true and `reorged_before_inclusion`
    false. The next birth is the replay's at the turn's height on its branch. None when a replay row is missing."""
    if any(rows.get(x) is None for x in range(h0, h + 1)) or any(branch.get(x) is None for x in range(h0, h + 1)):
        return None
    next_birth = rows[h]['next_birth']
    included: dict[int, int] = {}
    born: set[int] = set()
    for x in range(h0, h + 1):
        ids = {tx['txid'] for tx in branch[x]['txs'][1:]}
        for k, txid in enumerate(set_txids):
            if txid in ids and k not in included:
                included[k] = x
            if txid in rows[x]['born']:
                born.add(k)
    reorg = scenario == 'ITEM4_REORG'
    out = []
    for k in range(len(set_txids)):
        if born:
            label = item4_fill(ITEM4_BORN if k in born else ITEM4_BORN_OTHER, h0)
            flags = ITEM4_E9D_FLAGS['before_tip']
        elif k in included:
            label = item4_fill(ITEM4_INCLUDED, h0, height=included[k])
            flags = ITEM4_LABEL_FLAGS
        else:
            flags = ITEM4_E9D_FLAGS['from_tip'] if reorg else ITEM4_LABEL_FLAGS
            if reorg and planned['turn'] in ITEM4_LOCKED['turns']:
                label = item4_fill(ITEM4_LOCKED, h0, next_birth=next_birth)
            elif reorg:
                label = item4_fill(ITEM4_LOST, h0, next_birth=next_birth)
                label['verdict'] = ITEM4_STALE_TURN['released' if k in released else 'unreleased']
            else:
                label = item4_fill(ITEM4_LOST if k in released else ITEM4_UNRELEASED, h0, next_birth=next_birth)
        out.append(dict(label, **flags))
    return out


def item4_turns(scan: Scan) -> list[dict]:
    """The host turns as the raw log shows them: each `launch_set_worker` `L0_TURN` of an observing phase whose run
    ended the turn (`prestate_receipt` `-`), in log order, with the tip the host saw (the last accepted block the log
    wrote before it). The j-th `ITEM4_L0_OBSERVE` (the driver's own copy, a claim) pairs with the j-th turn and stands
    between it and the next (RAW_LOG_ITEM4 otherwise)."""
    out = []
    for line in scan.item2['L0_TURN']:
        lines = line['lines']
        if line['worker'] != ITEM4_SET_WORKER or lines.get('phase') not in ITEM4_OBSERVING \
                or lines.get('prestate_receipt') != '-':
            continue
        tip = None
        for block in scan.blocks:
            if block['seq'] < line['seq']:
                tip = block
        out.append({'seq': line['seq'], 'phase': lines['phase'], 'attempt_id': line['attempt_id'],
                    'start_ns': line['start_ns'], 'lines': lines, 'tip': tip, 'observe': None})
    observes = scan.item2['ITEM4_L0_OBSERVE']
    need(len(observes) <= len(out), 'RAW_LOG_ITEM4')
    for j, obs in enumerate(observes):
        need(out[j]['seq'] < obs['seq'] and (j + 1 == len(out) or obs['seq'] < out[j + 1]['seq']), 'RAW_LOG_ITEM4')
        out[j]['observe'] = obs
    return out


ITEM4_COUNTERS = ('released', 'gate_attempts', 'fee_exposure_sat', 'principal_exposure_sat')   # ARV1 section 22
# The set worker's `reorg` and `released` line forms (ARV1 section 25, host `set_reorg`; `-` when none).
ITEM4_REORG_LINE = re.compile(r'raised:(true|false);local:(0|[1-9][0-9]*):[0-9a-f]{64};at_local:([0-9a-f]{64}|below);'
                              r'ancestor:(-|(0|[1-9][0-9]*):[0-9a-f]{64})\Z')
ITEM4_RELEASED_LINE = re.compile(r'reason:[^;=]+;step6:[^;=]+\Z')
# Driver codes of a label-line host line not in its form (ARV1 sections 22-25): reproduced by a mislabel the judge
# finds. `L0_REORG_LINE` is reproduced by plan field `reorg_seen` (ITEM4_DRIVER_CODES).
ITEM4_HOST_FORM_CODES = ('ITEM4_L0_FLAGS', 'L0_LABELS')


def item4_counters(text) -> dict | None:
    """The set worker's raw `budget_counters` line (`released=…;gate_attempts=…;fee_exposure_sat=…;
    principal_exposure_sat=…`, the wallet's own counters; ARV1 section 22), or None when it is not that form."""
    parts = text.split(';') if type(text) is str else []
    if [x.partition('=')[0] for x in parts] != list(ITEM4_COUNTERS) or not all(
            DECIMAL.match(x.partition('=')[2]) for x in parts):
        return None
    return {x.partition('=')[0]: int(x.partition('=')[2]) for x in parts}


def item4_internal(block_hash: str) -> str:
    """A block hash in internal byte order (the host's `reorg` line, ARV1 section 25)."""
    return bytes.fromhex(block_hash)[::-1].hex()


def item4_core_rows(scan: Scan, chain_name: str) -> dict:
    """`--no-replay` (EXPLORATORY, A's Q14): the driver's CORE_REPLAY rows of one chain, unverified claims."""
    return {line['height']: {'born': line['born'], 'next_birth': line['next_birth']} for line in scan.core_replay
            if line['chain'] == chain_name}


def item4_ledger(cands: list, born: set) -> dict:
    """Mined REGISTERs (the REGISTER form) that created no Heart: count, weight and fee (045b :499-500, reported)."""
    lost = [c for c in cands if c['register'] and c['txid'] not in born]
    return {'count': len(lost), 'weight_wu': sum(c['weight'] for c in lost), 'fee_sat': sum(c['fee'] for c in lost)}


def item4_min_transitions(scenario: str, plan: dict, h0: int, by_turn: dict, turns: list, lines: dict, fields: set,
                          facts: dict, g_final: dict | None, orig: dict, replayed: tuple[bool, bool],
                          release_class: dict | None, winner: dict | None) -> list[str]:
    """J5b (045b :1279 and its dated line; the CT-P5-001 inventory section 2): the minimum transitions this run reaches,
    each only in the sub-scenario and at the planned turn the inventory lists it, from the raw-log evidence it names.
    A rung counts when its turn is judged and the host's raw label (the set worker's `L0_TURN` lines, the labels
    `ITEM4_L0_OBSERVE` copies) matches the label the judge derives from the block bytes and its own replay, so a reach
    needs the judge's replay (`replayed`: FINAL, the replaced branch); with `--no-replay` the run reaches none. The run
    reports them only; the experiment counts the reach per sub-scenario over its label-judged runs (section 25)."""
    final_replayed, replaced_replayed = replayed
    if not final_replayed:
        return []
    out: set[str] = set()
    names = {t['offset']: t['turn'] for t in plan['turns'] if t['branch'] == 'FINAL'}

    def rung0(name: str | None, shows) -> bool:   # the planned turn judged, rung 0 matching and showing the transition
        entry = by_turn.get(name)
        x = entry['rungs'][0] if entry is not None and entry['rungs'] else None
        return x is not None and x['match'] and shows(x['observed'])

    def stale(o: dict) -> bool:   # `Stale@<H0>><next birth>` with `opening_block_missed` true
        return o['outcome'].startswith('Stale@') and o['opening_block_missed'] is True

    def included(height: int):   # `IncludedNoEffect@<height>`; the height is where the bytes hold P0's rung 0
        text = item4_fill(ITEM4_INCLUDED, h0, height=height)['outcome']
        return lambda o: o['outcome'] == text

    def locked(name: str) -> bool:   # every rung `Refuse:Locked(Reorg67)`, each matching
        entry = by_turn.get(name)
        return entry is not None and bool(entry['rungs']) and all(
            x['match'] and x['observed']['verdict'] == ITEM4_LOCKED['verdict'] for x in entry['rungs'])
    if scenario in ('ITEM4_SELF_DEALING', 'ITEM4_FEE_ASYMMETRY') and rung0(names.get(0), included(h0)):
        out.add('TR-3')
    if scenario == 'ITEM4_SELF_DEALING' and 'TR-3' in out:
        # TR-4 (E10-s): TR-3's line, block G's own order (the self REGISTER first, from the bytes) and SELF_REGISTER's
        # index 0, height and block hash as the bytes give them. J5b verification round: and the competitor born in G,
        # the judge's replay bearing exactly the self REGISTER there (`winner`; no plan field `replay_birth`), as TR-1
        # needs its replay.
        register = lines['SELF_REGISTER']
        if facts['self']['first_in_g'] and winner is not None and winner['txid'] == facts['self']['txid'] \
                and register and (register[0]['index'], register[0]['height'],
                                  register[0]['block_hash']) == (0, h0, g_final['hash']):
            out.add('TR-4')
    if scenario == 'ITEM4_CENSORSHIP':
        if rung0(names.get(0), stale) or rung0(names.get(ITEM4_WINDOW['last']), stale):
            out.add('TR-2')
        if rung0(names.get(ITEM4_WINDOW['lifted']), included(h0 + ITEM4_WINDOW['lifted'])):
            out.add('TR-3')
    if scenario == 'ITEM4_REORG':
        # TR-1: rung 0 `Done:Born@<H0>+opening` at G, and the judge's replay of the replaced branch gives exactly that
        # birth (plan field `replay_replaced`).
        born = item4_fill(ITEM4_BORN, h0)['verdict']
        if 'replay_replaced' not in fields and rung0('G', lambda o: o['verdict'] == born):
            out.add('TR-1')
        if rung0('STALE', stale):
            out.add('TR-2')
        # TR-5: both locked turns, both branches replayed, the REORGED turn's raw `reorg` line the reorg the bytes show
        # (plan field `reorg_seen`), and REORG's depth and invalidated block the judge's.
        reorg = lines['REORG']
        if replaced_replayed and 'reorg_seen' not in fields and all(locked(name) for name in ITEM4_LOCKED['turns']) \
                and reorg and orig.get(h0) is not None \
                and (reorg[0]['depth'], reorg[0]['invalidated']) == (plan['depth'], orig[h0]['hash']):
            out.add('TR-5')
        # TR-6: the Class T release (the RELEASE turn's raw `released` line, `release_class`; ITEM4_L0_RELEASE's step,
        # released, procedure_sha256 and chains; the release turn's ITEM4_L0_OBSERVE `procedure.mark`), then Stale.
        step = lines['ITEM4_L0_RELEASE']
        if release_class is not None:   # the RELEASE turn is judged, so it is the planned turn at its position
            observe = turns[[t['turn'] for t in plan['turns']].index(ITEM4_LINE['after'])]['observe']
            procedure = observe.get('procedure') if observe is not None else None
            if type(procedure) is dict and procedure.get('mark') == ITEM4_MARK and step \
                    and (step[0]['step'], step[0]['released']) == (ITEM4_LINE['step'], ITEM4_LINE['released']) \
                    and type(step[0].get('procedure_sha256')) is str and type(step[0].get('chains')) is dict \
                    and rung0('STALE', lambda o: o['outcome'].startswith('Stale@')):
                out.add('TR-6')
    return [tr for tr in ITEM4_MIN_TRANSITIONS[scenario] if tr in out]


def judge_item4(policy: dict, scan: Scan, prereg: dict, collection: dict | None, mode: str,
                replay_with: list[str] | None = None) -> dict:
    """One item-4 run's record (section 24). The unit's state is the collection's (decision 11); the labels are judged
    apart from it (A's Q1, 045b :1084's note): a run whose planned turns are all judged with no plan mismatch is
    label-judged, matching or not; a mismatch on a judged turn of a run with no plan mismatch is NO-GO evidence, also
    when the run stopped partway. A run the driver ended OBSERVED becomes EXCLUDED with the re-derived exclusion code,
    else `JUDGE_PLAN_MISMATCH:<field>` (decision 4)."""
    scenario, r = scan.experiment, scan.run
    params = policy['params']
    b, h0 = params['b'], params['H0']
    first, lines = scan.first, scan.item2
    claims = Claims()
    killed = None
    if collection is not None and collection['state'] == 'EXCLUDED' and scan.run_end is not None \
            and scan.run_end.get('status') == 'DONE' and not scan.cut:
        killed = code_word(collection.get('code')) or 'UNIT_TIMEOUT'
    state = item4_unit_state(scan, scenario, r, killed)
    if collection is not None:
        need(collection['state'] == state['unit_state'], 'COLLECTION_DISAGREES', EXIT_REFUSAL)
    l0 = item4_binding(scan, policy, mode, scenario, h0)
    plan = item4_plan(policy['seed'], scenario, r, b, l0)
    p = plan['project']
    done = state['run_end'] == 'DONE'
    turns = item4_turns(scan) if l0 else []
    release_mark = item4_release_mark(scan, plan, turns, mode, done)
    # Check P3-3: a run whose planned turns are all present wrote every line, so its absence checks apply as a DONE
    # run's do (reading 3 spares only a run that stopped partway).
    whole = done or (l0 and bool(plan['turns']) and len(turns) >= len(plan['turns']))
    fields: set[str] = set()
    # Run fields (RUN_START, BIDDERS, SCENARIO_NOT_RUN).
    if first['params'] != params:
        fields.add('params')
    if first['miner_policy'] != ITEM4_MINER_POLICIES[scenario]:
        fields.add('miner_policy')
    bidders = scan.bidders
    if not (bidders is not None and bidders['bidders_sha256'] == sha256(canonical(bidders['bidders']))
            and first['bidders_sha256'] == bidders['bidders_sha256']):
        fields.add('bidders_sha256')
    if bidders is None or bidders['bidders'] != plan['bidders'] or first['roles'] != plan['roles']:
        fields.add('bidders')
    keys = ('e', 'r', 'label', 'n', 'k', 'value', 'feerate')
    if bidders is None or bidders['feerates'] != plan['feerates'] \
            or [{k: d.get(k) for k in keys} for d in bidders['draws']] != plan['draws']:
        fields.add('fee_draws')
    self_fee = (ITEM4_SELF_FEE, 'PRODUCT_FLOOR_ZERO_FEE_NEEDS_SRC') if scenario == 'ITEM4_SELF_DEALING' \
        else (None, None)
    if first['fees'] != plan['fees'] or (first['self_fee'], first['self_fee_rule']) != self_fee \
            or (plan['asymmetric'] is not None and plan['asymmetric']['cap_exceeded']):
        fields.add('fees')
    if first['depth'] != plan['depth']:
        fields.add('reorg_depth')
    listed = lines['SCENARIO_NOT_RUN'][0]['not_run'] if lines['SCENARIO_NOT_RUN'] else None
    if listed is None or [[n['scenario'], n['case']] for n in listed] != plan['not_run']:
        fields.add('not_run')
    sched = (lines['SCHEDULE'] or [None])[0]
    schedule, bad = item4_schedule(plan, sched, b)
    fields.update(bad)
    # Bytes, chains, attribution.
    chain = build_chain(scan, claims, strict=state['unit_state'] == 'OBSERVED')
    funding = item2_funding(scan, chain, h0, plan, p if l0 else None, claims)
    branches = item4_branches(scan, chain, h0, plan['depth'])
    final, g_first, orig = branches['final'], branches['g_first'], branches['orig']
    reorged = bool(branches['replaced'])
    start, end = state['start'], state['end']
    if start is not None and (start['height'] != h0 or (end is not None and end['height'] != h0)):
        fields.add('height')
    g_minus_1 = final.get(h0 - 1)
    releases, handed, bad = item4_releases(scan, plan, schedule['ladders'], funding,
                                           g_minus_1['seq'] if g_minus_1 is not None else None,
                                           g_first['seq'] if g_first is not None else None, whole)
    fields.update(bad)
    l0_ready = (lines['L0_READY'] or [None])[0]
    set_txids = [row['txid'] for row in sorted(l0_ready['rungs'], key=lambda row: row['k'])] if l0_ready else None
    k_of = {(rel['j'], rel['txid']): rel['k'] for rel in releases}
    if l0 and set_txids is not None:
        k_of.update({(p, txid): k for k, txid in enumerate(set_txids)})
    standin_txids = [rel['txid'] for rel in releases if rel['j'] == p and not l0]
    project_txids = set(set_txids or []) if l0 else set(standin_txids)
    outpoint = (funding['by_seat'][p]['txid'], funding['by_seat'][p]['vout']) if p in funding['by_seat'] else None
    project_rung0 = (set_txids[0] if set_txids else None) if l0 else (standin_txids[0] if standin_txids else None)
    project_last = project_rung0 if l0 else (standin_txids[-1] if standin_txids else None)
    # Every block from H0 on (both branches): candidates, each a known rung of its seat in the REGISTER form.
    blocks_from_g = {id(block): block for h, block in list(final.items()) + list(orig.items()) if h >= h0}
    cands: dict[int, list] = {}
    for key, block in blocks_from_g.items():
        cands[key], bad_c = item4_candidates(block, funding, k_of, plan, h0)
        if bad_c:
            fields.add('rung_bytes')
        owner = {txid: j for (j, txid) in k_of}
        attributed = {(c['txid'], c['j']) for c in cands[key]}
        if any(tx['txid'] in owner and (tx['txid'], owner[tx['txid']]) not in attributed for tx in block['txs'][1:]):
            fields.add('rung_bytes')   # a known rung in a block, not read through its seat's funding outpoint
    g_final = final.get(h0)
    cands_g = cands.get(id(g_final), []) if g_final is not None else []
    if whole and g_final is None:
        fields.add('block_g')
    if g_final is not None and not cands_g:
        fields.add('block_g')
    # The exclusion code re-derived (045b :571-574; ARV1 section 23): RELEASE_NOT_IN_TEMPLATE against block G's
    # template as the run mined it, then (stand-in) REPLACED_RUNG_NOT_IN_MEMPOOL.
    presence = {'code': None, 'seats': [], 'misses': [], 'last_released': {}}
    last: dict[int, dict] = {}
    for rel in releases:
        if g_first is not None and rel['seq'] < g_first['seq']:
            last[rel['j']] = rel
    presence['last_released'] = {f'S{j}': {'k': rel['k'], 'txid': rel['txid'], 'path': rel['path']}
                                 for j, rel in sorted(last.items())}
    if g_first is not None:
        template = g_first['template']
        if template is None:
            fields.add('presence')
        else:
            listed_t = {item['txid'] for item in template['template']['transactions']}
            private = {item['txid'] for item in template['private_set']}
            misses = sorted(j for j, rel in last.items() if rel['txid'] not in (private if rel['path'] == 'PRIVATE'
                                                                                else listed_t))
            presence['misses'] = [f'S{j}' for j in misses]
            if misses:
                presence.update(code='RELEASE_NOT_IN_TEMPLATE', seats=presence['misses'])
    if presence['code'] is None and lines['REPLACED_RUNG_MISSING']:
        presence.update(code='REPLACED_RUNG_NOT_IN_MEMPOOL',
                        seats=sorted({line['seat'] for line in lines['REPLACED_RUNG_MISSING']}))
    # The replay: FINAL from H0, and in a reorg run the original branch from H0 (its second request).
    replay, replay_orig = None, None
    if replay_with is not None and g_final is not None:
        replay = replay_chain(chain, h0, replay_with)
        if reorged:
            replay_orig = replay_chain({'blocks': orig}, h0, replay_with)
    if replay is not None:
        rows_final = replay['rows']
        rows_orig = replay_orig['rows'] if replay_orig is not None else rows_final
    else:
        rows_final = item4_core_rows(scan, 'FINAL')
        rows_orig = item4_core_rows(scan, 'REPLACED') if reorged else rows_final
    final_checked = scenario != 'ITEM4_REORG' or reorged   # a reorg run before its reorg: FINAL is still G's branch
    winner, other_births = None, []
    if replay is not None and final_checked:
        row = rows_final.get(h0)
        born = row['born'] if row is not None else []
        found = [c for c in cands_g if c['txid'] in born]
        if len(born) == 1 and len(found) == 1:
            winner = found[0]
        else:
            fields.add('replay_birth')
        other_births = [{'height': h, 'born': rows_final[h]['born']} for h in sorted(rows_final)
                        if h != h0 and rows_final[h]['born']]
        if other_births:
            fields.add('replay_other_birth')
    elif final_checked and cands_g:
        winner = cands_g[0]   # 045b :421-423: the first candidate in G's order (no replay: unverified)
    if winner is not None and winner['role'] != ITEM4_ADVERSARY[scenario]:
        fields.add('winner')   # A's Q3: a project win (or another seat's) is the driver's defect, never a mislabel
    if replay_orig is not None or (replay is not None and scenario == 'ITEM4_REORG'):
        births = [(h, txid) for h in sorted(rows_orig) for txid in rows_orig[h]['born']]
        if births != [(h0, project_rung0)]:
            fields.add('replay_replaced')
    # Scenario mechanics, read from the bytes.
    def hits(block: dict) -> list[str]:
        return item4_hits(block, project_txids, outpoint)
    facts: dict = {}
    if scenario == 'ITEM4_SELF_DEALING' and g_final is not None:
        self_rel = next((rel for rel in releases if rel['j'] == 0 and rel['k'] == 0 and rel['handed_off']), None)
        self_txid = self_rel['txid'] if self_rel is not None else None
        own = next((c for c in cands_g if c['j'] == 0), None)
        rivals = [rel for j, rel in last.items() if j != 0]
        in_g = {c['txid']: c for c in cands_g}
        first_tx = g_final['txs'][1]['txid'] if len(g_final['txs']) > 1 else None
        if self_txid is None or first_tx != self_txid or own is None or own['txid'] != self_txid:
            fields.add('self_first')
        else:
            if own['fee'] != ITEM4_SELF_FEE:
                fields.add('fees')
            for rel in rivals:
                rival = in_g.get(rel['txid'])
                if rival is None or not own['fee'] * rival['vsize'] < rival['fee'] * own['vsize']:
                    fields.add('self_first')   # strictly below every other released rung's feerate (045b :1065)
        if self_txid is not None and self_txid in handed:
            since = handed[self_txid]['seq']
            if any(since < m['seq'] < g_final['seq'] and self_txid in m['txids'] for m in lines['MEMPOOL']):
                fields.add('private_exposure')
        facts['self'] = {'txid': self_txid, 'first_in_g': first_tx == self_txid and self_txid is not None,
                         'fee': own['fee'] if own is not None else None,
                         'rivals': sorted(rel['txid'] for rel in rivals)}
        for line in lines['SELF_REGISTER']:
            for field, derived in (('txid', self_txid), ('fee', own['fee'] if own else None), ('index', 0),
                                   ('height', h0), ('block_hash', g_final['hash']), ('seat', 'S0')):
                if line[field] != derived:
                    claims.note('SELF_REGISTER', line['seq'], field, line[field], derived)
    if scenario == 'ITEM4_FEE_ASYMMETRY':
        asym = plan['asymmetric']
        bid = (lines['ASYMMETRIC_BID'] or [None])[0]
        project_c = next((c for c in cands_g if c['j'] == p), None)
        if bid is None:
            if whole:
                fields.add('asymmetric')
        else:
            want = {'seat': 'S0', 'median': asym['median'], 'factor': asym['factor'], 'feerate': asym['feerate'],
                    'fee': asym['fee'], 'honest_feerates': asym['honest_feerates'],
                    'project_configured_p0': plan['p0'], 'project_seat': f'S{p}'}
            if any(bid[k] != v for k, v in want.items()):
                fields.add('asymmetric')
            sent = bid['project_sent']
            if l0:
                if bid.get('project_p0_sources') != {'item4_project_p0': plan['p0'], 'l0_p0': plan['p0']} \
                        or (sent.get('k'), sent.get('source'), sent.get('fee_source')) != (0, 'L0_ADMISSION',
                                                                                           'NODE_MEMPOOL_ENTRY'):
                    fields.add('asymmetric')
                if project_c is None or (sent.get('fee'), sent.get('vsize'), sent.get('txid')) != (
                        project_c['fee'], project_c['vsize'], project_c['txid']):
                    fields.add('l0_fee')   # what L0 sent against its rung 0 read from block G's bytes
            elif (sent.get('fee'), sent.get('txid')) != (plan['f0'], project_rung0):
                fields.add('asymmetric')
        facts['asymmetric'] = dict(asym, logged=None if bid is None else {k: bid[k] for k in (
            'median', 'factor', 'feerate', 'fee')})
    if scenario == 'ITEM4_CENSORSHIP':
        lifted = h0 + ITEM4_WINDOW['lifted']
        leaks = {h: hits(final[h]) for h in range(h0 + ITEM4_WINDOW['first'], h0 + ITEM4_WINDOW['last'] + 1)
                 if h in final and hits(final[h])}
        if leaks or (chain['tip'] is not None and chain['tip'] > lifted) or (whole and chain['tip'] != lifted):
            fields.add('censor_window')
        lift = final.get(lifted)
        if lift is not None and project_last not in {tx['txid'] for tx in lift['txs'][1:]}:
            fields.add('censor_window')   # G + 144 holds the project's last released rung (045b :1068's note)
        if any(rel['l0'] and g_first is not None and rel['seq'] > g_first['seq'] for rel in releases):
            fields.add('release')         # L0 releases nothing after G (ARV1 section 24)
        missing_mempool = []
        if l0:
            for h in range(h0 + 1, lifted + 1):
                block = final.get(h)
                if block is None:
                    continue
                before = max((x['seq'] for x in scan.blocks if x['seq'] < block['seq']), default=0)
                snap = [m for m in lines['MEMPOOL'] if before < m['seq'] < block['seq']]
                for node in ('A', 'B'):
                    mine = [m for m in snap if m['node'] == node]
                    if not mine or any(project_rung0 not in m['txids'] for m in mine):
                        missing_mempool.append([h, node])
            if missing_mempool:
                fields.add('censor_mempool')   # L0's rung 0 in Node A's and Node B's mempool before each block
        facts['censor'] = {'first': h0 + ITEM4_WINDOW['first'], 'last': h0 + ITEM4_WINDOW['last'], 'lifted': lifted,
                           'leaks': [{'height': h, 'txids': t} for h, t in sorted(leaks.items())][:SHOWN],
                           'lift_holds_last_rung': lift is not None and project_last in {
                               tx['txid'] for tx in lift['txs'][1:]},
                           'mempool_missing': missing_mempool[:SHOWN], 'tip': chain['tip']}
        for line in lines['CENSOR_WINDOW']:
            for field, derived in (('first', h0), ('last', lifted - 1), ('lifted', lifted), ('seat', f'S{p}')):
                if line[field] != derived:
                    claims.note('CENSOR_WINDOW', line['seq'], field, line[field], derived)
        for line in lines['CENSOR_MEMPOOL']:
            if line['txid'] != project_rung0:
                claims.note('CENSOR_MEMPOOL', line['seq'], 'txid', line['txid'], project_rung0)
    reorg_facts = None
    if scenario == 'ITEM4_REORG':
        d = plan['depth']
        rg = orig.get(h0)
        if rg is not None and hits(rg) != ([project_rung0] if project_rung0 else []):
            fields.add('reorg_replaced')   # the replaced G holds the project's rung 0 alone of its set
        competitor = next((rel for rel in releases if plan['seats'][rel['j']]['role'] == 'COMPETITOR'), None)
        readded = []
        if whole or reorged:
            if sorted(branches['replaced']) != list(range(h0, h0 + d)) or branches['other_stale'] \
                    or chain['tip'] != h0 + d:
                fields.add('reorg_replaced')
            readded = [{'height': h, 'txids': hits(final[h])} for h in range(h0, h0 + d + 1)
                       if h in final and hits(final[h])]
            if readded:
                fields.add('reorg_readded')
            template = g_final['template'] if g_final is not None else None
            offered = {item['txid'] for item in template['template']['transactions']} if template else set()
            if competitor is None or competitor['txid'] not in offered:
                fields.add('reorg_offered')
        reorg_facts = {'depth': d, 'reorged': reorged,
                       'replaced': [{'height': h, 'block_hash': blk['hash']}
                                    for h, blk in sorted(branches['replaced'].items())],
                       'replacement': [{'height': h, 'block_hash': final[h]['hash']}
                                       for h in range(h0, h0 + d + 1) if h in final] if reorged else [],
                       'readded': readded, 'replaced_births': [t for h in sorted(rows_orig)
                                                               for t in rows_orig[h]['born']],
                       'final_births': [t for h in sorted(rows_final) for t in rows_final[h]['born']]
                       if reorged else []}
        for line in lines['REORG']:
            for field, derived in (('depth', d), ('invalidated', rg['hash'] if rg else None)):
                if line[field] != derived:
                    claims.note('REORG', line['seq'], field, line[field], derived)
    # L0's own checks (J4a's, with this run's observation and its rung 0 read from the block that holds it).
    l0_facts = None
    if l0:
        holder = orig.get(h0) if scenario == 'ITEM4_REORG' else final.get(
            h0 + ITEM4_WINDOW['lifted'] if scenario == 'ITEM4_CENSORSHIP' else h0)
        l0_cands = [c for c in cands.get(id(holder), []) if c['j'] == p] if holder is not None else []
        bad, l0_facts = item2_l0(scan, policy, mode, r, b, p, schedule, releases, l0_cands,
                                 item4_observation_id(scenario, r))
        fields.update(bad)
        expected_attempt = 'L0ATT-%s-01' % item4_observation_id(scenario, r)
        mine = [rel['k'] for rel in releases if rel['l0']]
        if mine != ([0] if mine or whole else []):
            fields.add('l0_attempt')   # item 4 releases L0's rung 0 only (no t_G; ARV1 section 24)
        if any(line['attempt_id'] == expected_attempt and line['when'] != 'CHARGED_NOT_RELEASED_BEFORE_G'
               for line in lines['L0_RUNG_TEST']):
            fields.add('l0_attempt')
        if any(line['attempt_id'] != expected_attempt for line in lines['ITEM4_L0_OBSERVE'] + lines['L0_TURN']
               + lines['ITEM4_L0_RELEASE']):
            fields.add('l0_attempt')
        miss = policy['l0_seat']['exact_height_miss'] if l0_policy_valued(scan, mode) else L0_DRAFT_MISS
        if miss != ITEM4_MISS_VALUE or any(line['exact_height_miss'] != miss for line in lines['ITEM4_LABELS']):
            fields.add('l0_budget')   # 045b :1068: only CONTINUE_WITHIN_LIMITS has expected labels
        # The wallet's counters after the last turn (an item-4 run writes them in its turns, ARV1 section 24): at most
        # 24 gate attempts (045b :1053).
        counted = item4_counters(turns[-1]['lines'].get('budget_counters')) if turns else None
        if turns and (counted is None or counted['gate_attempts'] > L0_MAX_GATE_ATTEMPTS):
            fields.add('l0_budget')
        l0_facts['turn_counters'] = counted
    # The host's labels (045b :1068 and its note), from the set worker's own lines.
    n = len(set_txids) if set_txids is not None else len(schedule['ladders'][p])
    released_ks = {rel['k'] for rel in releases if rel['l0']}
    accepted = lines['BLOCK_ACCEPTED']
    entries = []
    for i, want in enumerate(plan['turns']):
        t = turns[i] if i < len(turns) else None
        height = h0 + want['offset']
        entry = {'turn': want['turn'], 'phase': want['phase'], 'height': height, 'branch': want['branch'],
                 'block_hash': None, 'source': 'RAW_WORKER_LINES', 'judged': False, 'reason': None, 'rungs': [],
                 'released': None, 'match': None, 'malformed': []}
        entries.append(entry)
        if t is None:
            entry['reason'] = 'NOT_REACHED'
            continue
        branch = final if want['branch'] == 'FINAL' else orig
        block = branch.get(height)
        seen = t['tip'] is not None and any(a['block_hash'] == t['tip']['hash']
                                            and t['tip']['seq'] < a['seq'] < t['seq'] and a['t_ns'] <= t['start_ns']
                                            for a in accepted)
        if block is None or t['tip'] is not block or t['phase'] != want['phase'] or not seen:
            fields.add('l0_turns')
            entry['reason'] = 'NOT_THE_PLANNED_TURN'
            continue
        entry['block_hash'] = block['hash']
        raw = t['lines']
        # A's decisions on the J5 check (P2-2) and re-check (P2): the stage completed (`done` yes) and a host line it
        # must print is absent: no raw evidence, the turn is not judged. A line of 045b's label line that is present
        # but not in its form is a mislabel (045b :383, :1068's note: the host printed a wrong-form label), so the turn
        # is judged and does not match: `labels` and `flags` in every sub-scenario, `released` in ITEM4_REORG only
        # (:1068 names it there). The `reorg` line is not part of 045b's label line (A's Q9): a malformed one is a
        # wrong one, plan field `reorg_seen`, in every sub-scenario.
        needed = ('labels', 'flags') + (('reorg', 'released') if scenario == 'ITEM4_REORG' else ())
        if raw.get('done') != 'yes' or any(name not in raw for name in needed):
            entry['reason'] = 'RAW_LINE_ABSENT'
            continue
        labels = item4_parse_labels(raw['labels'], n)
        flags = item4_parse_flags(raw['flags'], n)
        malformed = [name for name, got in (('labels', labels), ('flags', flags)) if got is None]
        if scenario == 'ITEM4_REORG' and raw['released'] != '-' and ITEM4_RELEASED_LINE.match(raw['released']) is None:
            malformed.append('released')
        reorg_formed = raw.get('reorg', '-') == '-' or ITEM4_REORG_LINE.match(raw['reorg']) is not None
        if not reorg_formed:
            fields.add('reorg_seen')
        # the driver accepted the turn (its ITEM4_L0_OBSERVE), so it parsed these lines: the log contradicts itself
        need(t['observe'] is None or not {'labels', 'flags'} & set(malformed), 'RAW_LOG_ITEM4_LABELS')
        if scenario == 'ITEM4_REORG' and reorg_formed:
            line = raw['reorg']
            if want['turn'] == 'REORGED':
                tip_hash = orig[h0 + plan['depth'] - 1]['hash'] if h0 + plan['depth'] - 1 in orig else None
                at_local = final.get(h0 + plan['depth'] - 1)
                ancestor = final.get(h0 - 1)
                expect = None if tip_hash is None or at_local is None or ancestor is None else (
                    f'raised:true;local:{h0 + plan["depth"] - 1}:{item4_internal(tip_hash)};'
                    f'at_local:{item4_internal(at_local["hash"])};ancestor:{h0 - 1}:{item4_internal(ancestor["hash"])}')
                if line != expect:
                    fields.add('reorg_seen')   # A's Q9: the host saw the driver's reorg (a plan field)
            elif want['turn'] in ('RELEASE', 'STALE') and line != '-':
                fields.add('reorg_seen')
        expected = item4_expected(scenario, want, height, h0, branch, rows_final if want['branch'] == 'FINAL'
                                  else rows_orig, set_txids, released_ks) if set_txids is not None else None
        if expected is None and not malformed:
            entry['reason'] = 'NEXT_BIRTH_UNKNOWN'
            continue
        rungs = []
        for k, exp in enumerate(expected or []):
            obs = {'verdict': labels[k][0] if labels else None, 'outcome': labels[k][1] if labels else None,
                   **(flags[k] if flags else dict.fromkeys(ITEM4_LABEL_FLAGS))}
            differs = [f for f in ITEM4_JUDGED_FIELDS if obs[f] != exp[f]]
            rungs.append({'k': k, 'observed': obs, 'expected': exp, 'match': not differs, 'differs': differs})
        released = raw.get('released')
        released_ok = True
        if scenario == 'ITEM4_REORG':   # the label line's release step (045b :1068): after RELEASE only
            released_want = ITEM4_LINE['released'] if want['turn'] == ITEM4_LINE['after'] else ITEM4_LINE['none']
            released_ok = released == released_want
            entry['released'] = {'observed': released, 'expected': released_want, 'match': released_ok}
        entry.update(judged=True, rungs=rungs, malformed=malformed, reason='RAW_LINE_MALFORMED' if malformed else None,
                     match=not malformed and released_ok and all(x['match'] for x in rungs))
        observe = t['observe']
        if observe is not None:
            for field, claimed, derived in (
                    ('turn', observe['turn'], want['turn']), ('height', observe['height'], height),
                    ('block_hash', observe['block_hash'], block['hash']), ('phase', observe['phase'], t['phase']),
                    ('labels', observe['labels'], [{'verdict': v, 'outcome': o} for v, o in labels]),
                    ('flags', observe['flags'], flags), ('released', observe['released'], released)):
                if claimed != derived:
                    claims.note('ITEM4_L0_OBSERVE', observe['seq'], field, claimed, derived)
    if len(turns) > len(plan['turns']) or (done and l0 and len(turns) < len(plan['turns'])):
        fields.add('l0_turns')
    judged_turns = [e for e in entries if e['judged']]
    complete = l0 and bool(plan['turns']) and len(judged_turns) == len(plan['turns'])
    label_mismatch = any(not e['match'] for e in judged_turns)
    mismatch_turns = [e['turn'] for e in judged_turns if not e['match']]
    # The driver's label claims (ITEM4_LABELS, ITEM4_L0_LABEL_LINE): a disagreement is the driver's defect, reported.
    disagreements = []
    by_turn = {e['turn']: e for e in judged_turns}
    for line in lines['ITEM4_LABELS']:
        e = by_turn.get(line['turn'])
        if e is None:
            continue
        mine = [x['expected'] for x in e['rungs']]
        if line['expected'] != mine:
            claims.note('ITEM4_LABELS', line['seq'], 'expected', line['expected'], mine)
        rung_match = all(x['match'] for x in e['rungs']) and not e['malformed']
        if line['match'] != rung_match:
            claims.note('ITEM4_LABELS', line['seq'], 'match', line['match'], rung_match)
            disagreements.append({'turn': line['turn'], 'driver_match': line['match'], 'judge_match': rung_match})
    line_record = None
    if scenario == 'ITEM4_REORG' and l0:
        observed_line, expected_line = [], []
        for e in judged_turns:
            rung0 = e['rungs'][0] if e['rungs'] else {'observed': {}, 'expected': {}}
            observed_line.append({'turn': e['turn'], 'verdict': rung0['observed'].get('verdict'),
                                  'outcome': rung0['observed'].get('outcome')})
            expected_line.append({'turn': e['turn'], 'verdict': rung0['expected'].get('verdict'),
                                  'outcome': rung0['expected'].get('outcome')})
            if e['released']['observed'] != ITEM4_LINE['none'] or e['turn'] == ITEM4_LINE['after']:
                observed_line.append({'step': ITEM4_LINE['step'] if e['turn'] == ITEM4_LINE['after'] else None,
                                      'released': e['released']['observed']})
            if e['turn'] == ITEM4_LINE['after']:
                expected_line.append({'step': ITEM4_LINE['step'], 'released': ITEM4_LINE['released']})
        line_record = {'observed': observed_line, 'expected': expected_line, 'match': observed_line == expected_line,
                       'complete': complete}
        for line in lines['ITEM4_L0_LABEL_LINE']:
            if complete and line['match'] != line_record['match']:
                claims.note('ITEM4_L0_LABEL_LINE', line['seq'], 'match', line['match'], line_record['match'])
        tip = final.get(h0 + plan['depth'])
        release_turn = by_turn.get(ITEM4_LINE['after'])
        for line in lines['ITEM4_L0_RELEASE']:
            for field, derived in (('step', ITEM4_LINE['step']), ('height', h0 + plan['depth']),
                                   ('block_hash', tip['hash'] if tip else None),
                                   ('released', release_turn['released']['observed'] if release_turn else None)):
                if line[field] != derived:
                    claims.note('ITEM4_L0_RELEASE', line['seq'], field, line[field], derived)
    # Classification (A's Q1 and 045b :1084's note): the unit state stays the collection's; the labels apart.
    ordered = [f for f in ITEM4_FIELD_ORDER if f in fields]
    unit_state, code, source, code_seats = state['unit_state'], state['code'], 'LOG', state['code_seats']
    if unit_state == 'OBSERVED' and presence['code'] is not None:
        unit_state, code, source, code_seats = 'EXCLUDED', presence['code'], 'JUDGE', presence['seats']
    elif unit_state == 'OBSERVED' and ordered:
        unit_state, code, source, code_seats = 'EXCLUDED', 'JUDGE_PLAN_MISMATCH:' + ordered[0], 'JUDGE', []
    clean = l0 and not ordered and presence['code'] is None
    label_judged = clean and complete
    nogo_evidence = clean and label_mismatch
    reproduced = True
    if source == 'LOG' and state['run_end'] in ('EXCLUDED', 'FAILED'):
        if code in ('RELEASE_NOT_IN_TEMPLATE', 'REPLACED_RUNG_NOT_IN_MEMPOOL'):
            reproduced = presence['code'] == code
        elif code in ITEM4_DRIVER_CODES:
            reproduced = any(f in fields for f in ITEM4_DRIVER_CODES[code])
        elif code in ITEM4_LABEL_CHECKS or code in ITEM4_HOST_FORM_CODES:
            reproduced = label_mismatch
    if not reproduced:
        claims.note('RUN_END', scan.run_end['seq'], 'code', code, presence['code'] if presence['code'] else ordered)
    driver_check = None
    if state['run_end'] == 'FAILED' and state['code'] in ITEM4_LABEL_CHECKS:
        driver_check = {'code': state['code'], 'reproduced': label_mismatch}
    # Reported facts.
    born_final = ({t for h in rows_final for t in rows_final[h]['born']} if replay is not None
                  else {winner['txid']} if winner is not None else set())
    born_orig = {t for h in rows_orig for t in rows_orig[h]['born']}
    ledger_a = [c for h, blk in sorted(final.items()) if h >= h0 for c in cands.get(id(blk), [])]
    ledger_c = [c for h, blk in sorted(branches['replaced'].items()) for c in cands.get(id(blk), [])]
    mined_losing = {'A': item4_ledger(ledger_a, born_final), 'C': item4_ledger(ledger_c, born_orig),
                    'l0_A': item4_ledger([c for c in ledger_a if c['j'] == p and l0], born_final),
                    'l0_C': item4_ledger([c for c in ledger_c if c['j'] == p and l0], born_orig)}
    stale_turn = by_turn.get('STALE')
    replaced_winner = None
    if scenario == 'ITEM4_REORG' and reorg_facts is not None:
        replaced_winner = {'depth': plan['depth'],
                           'replaced': bool(reorged and project_rung0 in born_orig and project_rung0 not in born_final),
                           'end_state': None if stale_turn is None or not stale_turn['rungs']
                           or stale_turn['malformed'] else {
                               k: stale_turn['rungs'][0]['observed'][k] for k in ('verdict', 'outcome')},
                           'label_line_match': line_record['match'] if line_record is not None else None}
    release_turn = by_turn.get(ITEM4_LINE['after']) if scenario == 'ITEM4_REORG' else None
    release_class = None
    if release_turn is not None and release_turn['released']['match']:
        release_class = {'step': ITEM4_LINE['step'], 'released': release_turn['released']['observed'],
                         'class': 'CLASS_T_TEST_STEP', 'label': constant('ITEM4_RELEASE_CLASS_T_RUN')}
    reached = set()
    for e in judged_turns:
        for x in e['rungs']:
            obs = {k: (v if v is not None else '') for k, v in x['observed'].items()}
            reached |= {name for name, hit in (
                ('DONE_BORN', obs['verdict'].startswith('Done:Born@')),
                ('PROJECT_BORN_BY_OTHER', obs['verdict'].startswith('Done:ProjectBornByOther@')),
                ('STALE_OPENING_MISSED', obs['outcome'].startswith('Stale@') and obs['opening_block_missed']),
                ('INCLUDED_NO_EFFECT', obs['outcome'].startswith('IncludedNoEffect@')),
                ('REORG67_LOCK', obs['verdict'] == ITEM4_LOCKED['verdict']),
                ('GATE_ADVANCED', obs['verdict'] == ITEM4_LOST['verdict']),
                ('OFFLINE_SIGNATURE_PENDING', obs['verdict'] == ITEM4_UNRELEASED['verdict'])) if hit}
    if release_class is not None:
        reached.add('REORG67_RELEASE_CLASS_T')
    min_reached = item4_min_transitions(scenario, plan, h0, by_turn, turns, lines, fields, facts, g_final, orig,
                                        (replay is not None, replay_orig is not None), release_class, winner)
    if end is not None:
        derived_born = sorted(born_final) if replay is not None else None
        for field, claimed, derived in (('block_hash', end.get('block_hash'), g_final['hash'] if g_final else None),
                                        ('born', end.get('born'), derived_born),
                                        ('winner', end.get('winner'), winner['role'] if winner else None)):
            if end['status'] == 'OBSERVED' and claimed != derived and (derived is not None or field == 'block_hash'):
                claims.note('GATE_END', end['seq'], field, claimed, derived)
    if replay is not None:
        for item in scan.core_replay:
            rows = rows_final if item['chain'] == 'FINAL' else rows_orig if reorged else {}
            row = rows.get(item['height'])
            for field in ('born', 'next_birth', 'state_sha256') if row is not None else ():
                if item[field] != row[field]:
                    claims.note('CORE_REPLAY', item['seq'], field, item[field], row[field])
    winner_row = {k: winner[k] for k in ('seat', 'role', 'kind', 'txid')} if winner is not None else None
    observation = {
        'observation_id': item4_observation_id(scenario, r), 'scenario': scenario, 'state': unit_state, 'code': code,
        'code_source': source, 'code_reproduced': reproduced, 'code_seats': code_seats, 'depth': plan['depth'],
        'project_seat': L0_KIND if l0 else ITEM4_STANDIN, 'labels': 'JUDGED' if l0 else NOT_APPLICABLE_STANDIN,
        'label_judged': label_judged, 'label_mismatch': label_mismatch, 'nogo_evidence': nogo_evidence,
        'complete': complete, 'judged_turns': len(judged_turns), 'planned_turns': len(plan['turns']),
        'mismatch_turns': mismatch_turns, 'driver_label_check': driver_check,
        'driver_label_disagreements': disagreements[:SHOWN],
        'project_born': None if not final_checked else bool(winner is not None and winner['j'] == p),
        'winner': winner_row, 'mined_losing': mined_losing, 'replaced_winner': replaced_winner,
        'release_class': release_class, 'not_run': [case for _, case in plan['not_run']],
        'transitions': [name for name in ITEM4_TRANSITIONS if name in reached], 'min_transitions': min_reached,
        'mismatches': ordered}
    labels = list(ITEM4_RECORD_LABELS) + (['EXPLORATORY_NOT_A_VERDICT'] if mode != 'CONFIRMATORY' else [])
    if replay_with is None:
        births_label = 'UNVERIFIED_NO_REPLAY'
    else:
        births_label = 'REPLAYED' if replay is not None else 'NOT_REPLAYED_NO_JUDGED_GATE'
    outcome = {'result': POOL_RUN_RESULT, 'nogo': [], 'not_established': []}
    return {
        'schema': JUDGEMENT_SCHEMA, 'labels': labels, 'item': scenario, 'mode': mode,
        'evidence_status': 'CONFIRMATORY' if mode == 'CONFIRMATORY' else 'EXPLORATORY',
        'log_mode': first['mode'], 'log_evidence_status': first['evidence_status'],
        'births': births_label, 'replay': replay_summary(replay, other_births),
        'replay_replaced': replay_summary(replay_orig, []),
        'judge': {'unit': 'J5', 'tool_sha256': sha256(TOOL_PATH.read_bytes())},
        'inputs': {'policy_sha256': policy['sha256'], 'raw_log_sha256': scan.sha256, 'raw_log_bytes': scan.bytes,
                   'raw_log_lines': scan.lines, 'collection_given': collection is not None, 'prereg_045b': prereg,
                   'registration_sha256': first['registration_sha256']},
        'thresholds': threshold_table(),
        'unit': {'experiment': scenario, 'run': r, 'registered_runs': policy['count']},
        'params': dict(params, source=policy['params_source']),
        'plan': {'scenario': scenario, 'run': r, 'depth': plan['depth'], 'project_seat': f'S{p}',
                 'project_kind': L0_KIND if l0 else ITEM4_STANDIN, 'seats': plan['seats'], 'bidders': plan['bidders'],
                 'fees': plan['fees'], 'p0': plan['p0'], 'f0': plan['f0'], 'draws': plan['draws'],
                 'feerates': plan['feerates'], 'asymmetric': plan['asymmetric'], 'after_g': plan['after_g'],
                 'increments': schedule['increments'], 'i': schedule['i'], 'ladders': schedule['ladders'],
                 'released_ks': [0] if l0 else None, 'turns': plan['turns'], 'not_run': plan['not_run'],
                 'censor_window': [h0 + ITEM4_WINDOW['first'], h0 + ITEM4_WINDOW['last']]
                 if scenario == 'ITEM4_CENSORSHIP' else None},
        'run_shape': {'unit_state': state['unit_state'], 'code': state['code'], 'run_end': state['run_end'],
                      'phase': state['phase'], 'truncated': state['truncated'], 'killed': state['killed'],
                      'chain_tip': chain['tip'], 'stale_blocks': chain['stale'],
                      'replaced_branch': sorted(branches['replaced']), 'other_stale': len(branches['other_stale']),
                      'rejected_blocks': scan.rejected_blocks, 'funding_problems': funding['problems'],
                      'collection_code': collection_code(collection)},
        'gate': {'height': h0 if g_final is not None else None, 'block_hash': g_final['hash'] if g_final else None,
                 'judge_code': presence['code'], 'judge_code_seats': presence['seats'], 'misses': presence['misses'],
                 'last_released': presence['last_released'],
                 'released': [{k: rel[k] for k in ('seat', 'role', 'kind', 'k', 'txid', 'handed_off', 'after_g')}
                              for rel in releases][:SHOWN],
                 'candidates_in_g': [{k: c[k] for k in ('seat', 'role', 'kind', 'k', 'txid', 'position', 'weight',
                                                         'vsize', 'fee', 'register')} for c in cands_g],
                 'winner': winner_row, 'winner_source': 'REPLAY' if replay is not None else 'FIRST_IN_BLOCK_ORDER',
                 'scenario': facts, 'reorg': reorg_facts, 'l0': l0_facts},
        'labels_judged': {'source': 'RAW_WORKER_LINES' if l0 else NOT_APPLICABLE_STANDIN,
                          'next_birth_source': 'REPLAY' if replay is not None else 'CORE_REPLAY_UNVERIFIED'
                          if replay_with is None else 'CORE_REPLAY_UNVERIFIED_NOT_REPLAYED',
                          'turns': entries, 'label_line': line_record, 'release': release_class,
                          'release_mark': release_mark,
                          'judged_turns': len(judged_turns), 'complete': complete},
        'observation': observation,
        'driver_claims': claims.record(),
        'outcome': outcome,
        'verdict': verdict_block(outcome),
    }


def raw_log_experiment(path: Path) -> str:
    """The item-4 experiment a raw log names on its first line (A's Q6: `item4` reads the scenario from the log)."""
    with open_regular(path, 'RAW_LOG', RAW_LIMIT) as handle:
        first = parse_line(handle.readline(LINE_LIMIT + 1))
    need(first is not None, 'RAW_LOG_JSON')
    unit = first.get('unit')
    need(type(unit) is dict and unit.get('experiment') in ITEM4_SCENARIOS, 'RAW_LOG_EXPERIMENT')
    return unit['experiment']


def item4(args) -> dict:
    """The `item4` command: one item-4 run's raw log, bound as `item2` binds an ITEM2 log (no method policy, no D2-2);
    the scenario is the log's experiment. CONFIRMATORY also needs the policy's `l0_seat` (L0_FREEZE_PENDING), the L0
    seat in the log (RAW_LOG_ITEM4_STANDIN), the registered budget digest and, for a reorg run, the release mark."""
    mode = args.mode
    if mode == 'EXPLORATORY':
        need(args.registration is None, 'EXPLORATORY_REGISTRATION')
    need(not (args.no_replay and args.replay_bin is not None), 'REPLAY_OPTIONS')
    prereg = read_prereg(args.prereg)
    scenario = raw_log_experiment(args.raw)
    if mode == 'CONFIRMATORY':
        covering_registration(args, scenario)
    policy = parse_item4_policy(read_file(args.policy, 'POLICY', POLICY_LIMIT), mode, scenario)
    if mode == 'CONFIRMATORY':
        registered_log(args, policy, None, scenario)
    collection_blob = read_file(args.collection, 'COLLECTION', COLLECTION_LIMIT) if args.collection else None
    scan = scan_raw(args.raw, policy['sha256'], mode, scenario)
    collection = run_collection_unit(collection_blob, scan.run, scenario) if collection_blob is not None else None
    record = judge_item4(policy, scan, prereg, collection, mode,
                         None if args.no_replay else replay_argv(args.replay_bin))
    if collection_blob is not None:
        record['inputs']['collection_sha256'] = sha256(collection_blob)
    return record


# ---------------------------------------------------------------------------------------------------------
# J3: the 10% rule across dispatches (ARDR_JUDGE_V1 section 20; 045b :571-572, :576-580; decisions 6 and 7). One
# experiment's judgement over the collections of every listed dispatch and the judge's own record of each unit
# with a raw log. The denominator is the registered N runs times the gates per run; a unit no listed dispatch
# started (absent, or BEFORE_START everywhere) is missing; a unit started in two dispatches is refused.

EXPERIMENT_SCHEMA = 'BITAGI_CT_ARDR_EXPERIMENT_JUDGEMENT_V1'
EXPERIMENT_LABELS = ['CLASS_T', 'REGTEST', 'JUDGE_RECORD', 'J3_EXPERIMENT']
RECORD_LIMIT = 16 << 20          # one judgement record (a 200-gate ITEM1 record is about 96 KB)
REGISTERED_GATES_MAX = 100_000   # N x gates per run judged at once (045b: 200 gates for ITEM1 and for POOL)
UNIT_STATES = ('BEFORE_START', 'OBSERVED', 'EXCLUDED')
GATE_STATES = ('OBSERVED', 'EXCLUDED', 'NOT_STARTED')
RUN_RESULTS = {'ITEM1': ('GO', 'NO_GO', 'NOT_ESTABLISHED'), 'POOL': (POOL_RUN_RESULT,), 'ITEM2': (POOL_RUN_RESULT,),
               **{name: (POOL_RUN_RESULT,) for name in ITEM4_SCENARIOS}}
RUN_LEVEL = ('ITEM2',) + ITEM4_SCENARIOS   # J4a, J5: a unit of one observation, the run (ARV1 section 13: `gates` null)


def _code(value) -> bool:
    return value is None or type(value) is str


def _texts(value) -> bool:
    return type(value) is list and all(type(x) is str for x in value)


def experiment_collection(blob: bytes, experiment: str, gates: int, mode: str) -> dict:
    """One dispatch's collection (ARV1 section 13, V2), read strictly before any set or map is built from it: the
    experiment, the mode, the run, and per unit its state and, unless BEFORE_START, one row per gate."""
    doc = json_document(blob, 'COLLECTION')
    run, units = doc.get('run'), doc.get('units')
    need(doc.get('schema') == COLLECTION_SCHEMA and doc.get('experiment') == experiment and type(run) is dict
         and type(units) is list and type(run.get('run_id')) in (str, int)
         and RUN_ID.match(str(run['run_id'])) is not None
         and (doc.get('registration_sha256') is None or (type(doc['registration_sha256']) is str
                                                         and HEX64.match(doc['registration_sha256']) is not None)),
         'COLLECTION_SHAPE')
    need(doc.get('mode') == mode, 'COLLECTION_MODE', EXIT_REFUSAL)
    out: dict[int, dict] = {}
    for item in units:
        unit = item.get('unit') if type(item) is dict else None
        need(type(unit) is dict and set(unit) == UNIT_KEYS and unit['experiment'] == experiment
             and int_in(unit['run'], 0, 9_999_999) and unit['gate'] is None and unit['cohort'] is None
             and type(item.get('state')) is str and item['state'] in UNIT_STATES and _code(item.get('code')),
             'COLLECTION_SHAPE')
        rows = item.get('gates')
        if experiment in RUN_LEVEL:   # J4a: a run-level unit has no gate rows; its state is its one row's
            need(rows is None, 'COLLECTION_SHAPE')
            rows = None if item['state'] == 'BEFORE_START' else [{'state': item['state'], 'code': item.get('code')}]
        elif item['state'] == 'BEFORE_START':
            need(rows is None, 'COLLECTION_SHAPE')
        else:
            need(type(rows) is list and len(rows) == gates
                 and all(type(x) is dict and type(x.get('gate')) is int and x['gate'] == i
                         and type(x.get('state')) is str and x['state'] in GATE_STATES and _code(x.get('code'))
                         for i, x in enumerate(rows)), 'COLLECTION_SHAPE')
        need(unit['run'] not in out, 'COLLECTION_SHAPE')
        # J5: an item-4 unit's driver exit, always present (ARV1 section 13: null before its driver ran, so an integer
        # means the slice record names a raw log; A's re-check P3-3).
        driver_exit = item.get('exit', '')
        # Finding #788: an ITEM2 unit too (RUN_LEVEL), since `experiment` reads its `exit` for RECORD_MISSING.
        need(experiment not in RUN_LEVEL or driver_exit is None or type(driver_exit) is int, 'COLLECTION_SHAPE')
        out[unit['run']] = {'state': item['state'], 'code': item.get('code'), 'exit': item.get('exit'),
                            'gates': [(x['state'], x.get('code'), None) for x in rows] if rows is not None else None}
    return {'run_id': str(run['run_id']), 'sha256': sha256(blob), 'registration_sha256': doc.get('registration_sha256'),
            'units': out}


def item2_observation_ok(obs) -> bool:
    """J4a: an `item2` record's `observation` (section 21), every field the experiment reads."""
    def count(v):
        return type(v) is int and v >= 0
    if type(obs) is not dict or obs.get('state') not in ('OBSERVED', 'EXCLUDED') or not _code(obs.get('code')) \
            or type(obs.get('observation_id')) is not str:
        return False
    winner, l0, traffic = obs.get('winner'), obs.get('l0'), obs.get('traffic')
    return (_texts(obs.get('code_seats')) and type(obs.get('code_reproduced')) is bool
            and type(obs.get('mempool_log_complete')) is bool and _texts(obs.get('mismatches'))
            and (obs.get('l0_seat') is None or int_in(obs['l0_seat'], 1, ITEM2_SEATS - 1))
            and all(count(obs.get(k)) for k in ('predicted_candidates', 'observed_candidates', 'private_observed',
                                                'candidates_in_g', 'mined_losing', 'losing_weight_wu',
                                                'losing_fee_sat'))
            and (winner is None or (type(winner) is dict and winner.get('path') in ('PRIVATE', 'PUBLIC')
                                    and winner.get('kind') in ('SYNTHETIC', L0_KIND)))
            and (l0 is None or (type(l0) is dict and all(type(l0.get(k)) is bool for k in ('attempted', 'mined_losing'))
                                and count(l0.get('losing_fee_sat'))))
            and type(traffic) is dict and all(count(traffic.get(k)) for k in ('handed_off', 'replacements',
                                                                              'l0_replacements',
                                                                              'l0_rung_tests_refused'))
            and rung_refusals_ok(traffic.get('rung_refusals_501'))
            and rung_refusals_ok(traffic.get('rung_refusals_501_undecided'), undecided=True)
            and count(traffic.get('rung_tests_before_release')) and count(traffic.get('rung_tests_unresolved')))


def rung_refusals_ok(value, undecided: bool = False) -> bool:
    """J4c (section 28): an observation's :501 rung list, each entry a rung k >= 1 once with the node roles (A, B; at
    least one, in that order) its line names. Finding #788: an entry of the undecided list also says `why`, one of
    RUNG_UNDECIDED_WHY; an entry of the NO-GO list has no `why`."""
    keys = {'k', 'roles', 'why'} if undecided else {'k', 'roles'}
    return type(value) is list and all(
        type(x) is dict and set(x) == keys and type(x['k']) is int and 1 <= x['k'] <= ITEM2_LAST_RUNG
        and x['roles'] in (['A'], ['B'], ['A', 'B'])
        and (not undecided or (type(x['why']) is str and x['why'] in RUNG_UNDECIDED_WHY)) for x in value) \
        and len({x['k'] for x in value}) == len(value)


def experiment_record(blob: bytes, experiment: str, gates: int) -> dict:
    """One per-unit judgement record of this judge (`item1`, `pool` or J4a's `item2`), read strictly: its unit, its
    gate rows (a pool OBSERVED gate names its producer; an item-2 run has its one `observation` row instead), its
    outcome and its inputs."""
    doc = json_document(blob, 'RECORD')
    unit, inputs, judge, rows, outcome = (doc.get(k) for k in ('unit', 'inputs', 'judge', 'gates', 'outcome'))
    if experiment in RUN_LEVEL:
        obs = doc.get('observation')
        item4 = experiment in ITEM4_SCENARIOS
        need(item4_observation_ok(obs, experiment) if item4 else item2_observation_ok(obs), 'RECORD_SHAPE')
        # Desktop r4446911576: the observation is its unit's run (`OBS-2<run:07>`; J5: `OBS-<e><run:07>`), so a copy of
        # another run's record with only `unit.run` changed is refused.
        need(type(unit) is dict and int_in(unit.get('run'), 0, (ITEM4_RUN_COUNT if item4 else ITEM2_RUN_COUNT) - 1)
             and obs['observation_id'] == (item4_observation_id(experiment, unit['run']) if item4
                                           else item2_observation_id(unit['run'])), 'RECORD_SHAPE')
        rows = [{'gate': 0, 'state': obs['state'], 'code': obs['code'], 'observation': obs}]
    need(doc.get('schema') == JUDGEMENT_SCHEMA and doc.get('item') == experiment and type(doc.get('mode')) is str
         and type(unit) is dict and unit.get('experiment') == experiment and int_in(unit.get('run'), 0, 9_999_999)
         and type(inputs) is dict and type(judge) is dict and type(judge.get('tool_sha256')) is str
         and HEX64.match(judge['tool_sha256']) is not None and type(outcome) is dict
         and type(outcome.get('result')) is str and outcome['result'] in RUN_RESULTS[experiment]
         and _texts(outcome.get('nogo')) and _texts(outcome.get('not_established'))
         and type(rows) is list and len(rows) == gates
         and all(type(x) is dict and type(x.get('gate')) is int and x['gate'] == i and type(x.get('state')) is str
                 and x['state'] in GATE_STATES and _code(x.get('code'))
                 and (experiment != 'POOL' or x['state'] != 'OBSERVED'
                      or (type(x.get('producer')) is str and x['producer'] in PRODUCERS))
                 for i, x in enumerate(rows)), 'RECORD_SHAPE')
    # Section 29 (045b :1090): the record carries its `verdict`, and that says what its `outcome` says. Whether it does
    # is only noted here (`verdict_agrees`): `experiment` refuses a record that does not as its last record check, so a
    # record another judge file made, or one bound to other inputs, keeps the refusal it had before this check.
    verdict = doc.get('verdict')
    return {'run': unit['run'], 'sha256': sha256(blob), 'mode': doc['mode'], 'tool_sha256': judge.get('tool_sha256'),
            'policy_sha256': inputs.get('policy_sha256'), 'collection_sha256': inputs.get('collection_sha256'),
            'registration_sha256': inputs.get('registration_sha256'),
            'verdict_agrees': type(verdict) is dict and verdict.get('result') == VERDICT_RESULT[outcome['result']],
            'gates': [(x['state'], x.get('code'), x.get('observation', x.get('producer'))) for x in rows],
            'outcome': {'result': outcome['result'], 'nogo': list(outcome['nogo']),
                        'not_established': list(outcome['not_established'])}}


def follows(collection_rows: list, record_rows: list) -> bool:
    """A record's gate states follow the collection's: the same state, or a collection OBSERVED gate the judge
    EXCLUDED (decision 4 and the run and missing-data exclusions)."""
    return all(mine == theirs or (theirs == 'OBSERVED' and mine == 'EXCLUDED')
               for (theirs, _, _), (mine, _, _) in zip(collection_rows, record_rows))


def experiment(args) -> dict:
    """The `experiment` command (section 20): the 10% rule over the registered N across every listed dispatch,
    and, for POOL, the Herfindahl index over the block-G producers of every judged pool gate."""
    name, mode = args.experiment, args.mode
    if mode == 'EXPLORATORY':
        need(args.registration is None, 'EXPLORATORY_REGISTRATION')
    prereg = read_prereg(args.prereg)
    if mode == 'CONFIRMATORY':
        covering_registration(args, name)
    policy_blob = read_file(args.policy, 'POLICY', POLICY_LIMIT)
    if name in ITEM4_SCENARIOS:   # J5: one item-4 sub-scenario (section 25)
        policy = parse_item4_policy(policy_blob, mode, name)
    else:
        policy = {'ITEM1': parse_policy, 'POOL': parse_pool_policy, 'ITEM2': parse_item2_policy}[name](policy_blob,
                                                                                                        mode)
    registration = None
    if mode == 'CONFIRMATORY':
        need(args.registration is not None, 'REGISTRATION_MISSING', EXIT_PREREQUISITE)
        reg_blob = read_file(args.registration, 'REGISTRATION', REGISTRATION_LIMIT)
        covered, listed = parse_registration(reg_blob)
        registered_experiment(covered, name)   # section 30, again on the bytes the collections bind
        need(policy['sha256'] in listed, 'POLICY_NOT_REGISTERED', EXIT_REFUSAL)
        registration = sha256(reg_blob)
        need(name != 'ITEM1' or policy['count'] == ITEM1_RUNS, 'POLICY_ITEM1_RUNS')   # 045b :546
        need(name != 'ITEM2' or policy['count'] == ITEM2_RUN_COUNT, 'POLICY_ITEM2_RUNS')   # J4a: 045b :546
        need(name not in ITEM4_SCENARIOS or policy['count'] == ITEM4_RUN_COUNT, 'POLICY_ITEM4_RUNS')   # J5: :524
    k = policy['params']['gates_per_run']
    need(len(args.collection) + len(args.undeclared_run) <= RUN_IDS_MAX, 'RUN_IDS')
    collections = [experiment_collection(read_file(p, 'COLLECTION', COLLECTION_LIMIT), name, k, mode)
                   for p in args.collection]
    need(len({c['run_id'] for c in collections}) == len(collections), 'COLLECTION_DUPLICATE')
    need(all(c['registration_sha256'] == registration for c in collections), 'COLLECTION_REGISTRATION',
         EXIT_REFUSAL)
    # J4b (section 16 P3-2): a listed dispatch that declared nothing, re-checked here from its saved answers; it adds
    # no unit and counts only as listed (its units are those of no dispatch: missing, decision 7). It needs the listing.
    need(not args.undeclared_run or (args.runs_listing is not None and args.main_history is not None),
         'RUN_LIST_REQUIRED', EXIT_PREREQUISITE)
    undeclared = [undeclared_run(folder, mode, name, args.main_history) for folder in args.undeclared_run]
    given = [c['run_id'] for c in collections] + [u['run_id'] for u in undeclared]
    need(len(set(given)) == len(given), 'COLLECTION_DUPLICATE')   # one run given twice, by collection or not
    run_list = run_list_check(args, name, mode, given)   # P2-1: every dispatch listed
    tool = sha256(TOOL_PATH.read_bytes())
    records = [experiment_record(read_file(p, 'RECORD', RECORD_LIMIT), name, k) for p in args.record]
    for rec in records:
        need(rec['tool_sha256'] == tool, 'RECORD_TOOL', EXIT_REFUSAL)
        need(rec['mode'] == mode and rec['policy_sha256'] == policy['sha256']
             and rec['registration_sha256'] == registration, 'RECORD_BINDING', EXIT_REFUSAL)
    started: dict[int, tuple[dict, dict]] = {}
    listed_runs: set[int] = set()
    for c in collections:
        for r, entry in c['units'].items():
            listed_runs.add(r)
            if entry['state'] != 'BEFORE_START':
                need(r not in started, 'UNIT_DISPATCHED_TWICE', EXIT_REFUSAL)   # 045b :577-580
                started[r] = (c, entry)
    count, source = policy['count'], 'POLICY'
    if count is None:   # EXPLORATORY without a registered count: the listed units, from 0
        count, source = (max(listed_runs) + 1 if listed_runs else 0), 'UNITS_LISTED'
    need(count * k <= REGISTERED_GATES_MAX, 'REGISTERED_N_SIZE')
    need(all(r < count for r in started), 'UNIT_NOT_REGISTERED', EXIT_REFUSAL)   # 045b :571: fixed N
    by_run: dict[int, dict] = {}
    for rec in records:
        need(rec['run'] not in by_run, 'RECORD_DUPLICATE')
        by_run[rec['run']] = rec
        need(rec['run'] in started and started[rec['run']][0]['sha256'] == rec['collection_sha256'],
             'RECORD_BINDING', EXIT_REFUSAL)
    units, every, runs = [], [], []
    for r in range(count):
        if r not in started:
            state = 'BEFORE_START' if r in listed_runs else 'NOT_DISPATCHED'   # decision 7: missing
            rows, dispatch, rec = [('NOT_STARTED', state, None)] * k, None, None
        else:
            c, entry = started[r]
            rec, state, dispatch = by_run.get(r), entry['state'], c['run_id']
            if rec is None:   # no raw log judged: only a unit with no OBSERVED gate may stand on its collection
                need(all(s != 'OBSERVED' for s, _, _ in entry['gates']), 'RECORD_MISSING', EXIT_PREREQUISITE)
                # J5 (A's decision on the J5 check, P1-1; 045b :1084's note): an item-4 run the driver ended on its own
                # label check is judged from its raw log, never an exclusion, and so is any run whose driver ran (its
                # exit is in the collection: the raw log exists; decision 11). Without its record the judge refuses.
                need(name not in ITEM4_SCENARIOS or (entry['code'] not in ITEM4_LABEL_CHECKS and entry['exit'] is None),
                     'RECORD_MISSING', EXIT_PREREQUISITE)
                # Finding #788 (A's decision): the same for an ITEM2 run whose driver ran (its `exit` is in the
                # collection, so the slice holds its raw log; ARV1 section 13). A FAILED attempt's rung tests reach
                # :501 only through its record, so the unit does not stand on the collection's word.
                need(name != 'ITEM2' or entry['exit'] is None, 'RECORD_MISSING', EXIT_PREREQUISITE)
                rows = entry['gates']
            else:
                need(follows(entry['gates'], rec['gates']), 'RECORD_DISAGREES', EXIT_REFUSAL)
                rows = rec['gates']
        every += rows
        runs.append((r, rows[0][0], rows[0][1], rows[0][2] if rec is not None else None))   # J4a: a run-level unit
        units.append({'run': r, 'dispatch_run_id': dispatch, 'unit_state': state,
                      'source': 'RECORD' if rec is not None else 'COLLECTION' if dispatch is not None else 'NONE',
                      'observed': sum(s == 'OBSERVED' for s, _, _ in rows),
                      'excluded': sum(s == 'EXCLUDED' for s, _, _ in rows),
                      'missing': sum(s == 'NOT_STARTED' for s, _, _ in rows),
                      'result': rec['outcome']['result'] if rec is not None else None,
                      # Section 29: the collection's code of the unit (UNIT_TIMEOUT, SLICE_RECORD_MISSING, ...), from
                      # the dispatch that started it; null for a unit no listed dispatch started (the code of a
                      # BEFORE_START listing stays in its collection) or whose collection gives none. Shown only: no
                      # count and no state reads it.
                      'unit_code': started[r][1]['code'] if r in started else None})
    # Section 29 (045b :1090), the read-back check: every record given carries its `verdict`, the mapping of its
    # `outcome`. It is the last record check, after RECORD_TOOL, RECORD_BINDING, RECORD_DUPLICATE, RECORD_MISSING and
    # RECORD_DISAGREES above, so each of those refuses exactly what it refused before this check existed.
    need(all(rec['verdict_agrees'] for rec in records), 'RECORD_SHAPE')
    counts = gate_counts([{'state': s} for s, _, _ in every])
    nogo, not_established = [], []
    if counts['over_10_percent']:
        not_established.append('TEN_PERCENT_RULE')
    if counts['observed'] == 0:
        not_established.append('NO_JUDGED_GATES')
    pool_part, item2_part, item4_part = None, None, None
    if name in ITEM4_SCENARIOS:   # J5 (section 25): the sub-scenario's own rule, per sub-scenario (045b :1084's note)
        item4_part = item4_rows(runs, count, name)
        own = item4_part['outcome']
        result, nogo, not_established = own['result'], list(own['nogo']), list(own['not_established'])
    elif name == 'ITEM2':   # J4a (section 22): item 2's outcome is the :381 row's; each 4.5 row carries its own
        item2_part = item2_rows(runs, count)
        own = item2_part['rows']['381']
        result, nogo, not_established = own['result'], list(own['nogo']), list(own['not_established'])
    elif name == 'POOL':
        produced = {p: sum(s == 'OBSERVED' and x == p for s, _, x in every) for p in PRODUCERS}
        index = herfindahl(produced)
        pool_part = {'counts': produced, 'gates': sum(produced.values()), 'herfindahl': index,
                     'herfindahl_max': HHI_MAX, 'above_max': above_hhi_max(index)}
        if pool_part['above_max']:
            nogo.append('POOL_HHI_ABOVE_MAX')
        # 045b :571-572: exclusions above 10% make the experiment NOT_ESTABLISHED; the index is a statistic of the
        # judged gates, so it gives NO_GO only when the experiment is established (section 20).
        result = 'NOT_ESTABLISHED' if not_established else 'NO_GO' if nogo else 'GO'
    else:
        for rec in records:   # ITEM1: each run's own outcome; its per-run 10% is replaced by the experiment's
            nogo += rec['outcome']['nogo']
            not_established += [c for c in rec['outcome']['not_established'] if c != 'TEN_PERCENT_RULE']
        result = 'NO_GO' if nogo else 'NOT_ESTABLISHED' if not_established else 'GO'   # section 12's order
    labels = (['CLASS_T', 'REGTEST', 'JUDGE_RECORD', 'J4A_ITEM2_EXPERIMENT'] if name == 'ITEM2'
              else list(ITEM4_EXPERIMENT_LABELS) if name in ITEM4_SCENARIOS
              else list(EXPERIMENT_LABELS)) + (['EXPLORATORY_NOT_A_VERDICT'] if mode != 'CONFIRMATORY' else [])
    outcome = {'result': result, 'nogo': sorted(set(nogo)), 'not_established': sorted(set(not_established))}
    # Section 29 (045b :1090): the requirement verdict of the finished outcome, and for ITEM1 and POOL the cause of
    # every gate that is not OBSERVED, tallied from `every`, the rows `gate_counts` counted (ITEM2 and item 4 have
    # their own tallies, `item2.exclusions` and `item4.exclusions`). Item 2's verdict is the :381 row's, as `outcome`
    # is: the row's criterion, figures and result, with the record's own (sorted) `not_established` list as reasons.
    exclusions = None
    if name in ITEM4_SCENARIOS:
        criterion, figures = item4_view(item4_part)
    elif name == 'ITEM2':
        criterion, figures = (item2_part['rows']['381']['verdict'][side] for side in ('expected', 'observed'))
    else:
        exclusions = {'by_code': exclusion_tally(every)}
        figures = {'gates': counts['gates'], 'missing_or_excluded': counts['missing_or_excluded']}
        if name == 'POOL':
            criterion = {'herfindahl_max': HHI_MAX, 'exclusion_limit': EXCLUSION_LIMIT}
            figures.update(herfindahl=pool_part['herfindahl'], judged_gates=pool_part['gates'])
        else:
            criterion = dict(item1_criterion(), runs=count)
            figures.update(run_results=[{'run': u['run'], 'result': u['result']} for u in units])
    return {
        'schema': EXPERIMENT_SCHEMA, 'labels': labels, 'experiment': name, 'mode': mode,
        'evidence_status': 'CONFIRMATORY' if mode == 'CONFIRMATORY' else 'EXPLORATORY',
        'judge': {'unit': 'J4A' if name == 'ITEM2' else 'J5' if name in ITEM4_SCENARIOS else 'J3', 'tool_sha256': tool},
        'inputs': {'policy_sha256': policy['sha256'], 'prereg_045b': prereg, 'registration_sha256': registration,
                   'run_list': run_list,
                   'collections': sorted(({'run_id': c['run_id'], 'sha256': c['sha256']} for c in collections),
                                         key=lambda c: int(c['run_id'])),
                   'undeclared_runs': sorted(undeclared, key=lambda u: int(u['run_id'])),
                   'records': sorted(({'run': rec['run'], 'sha256': rec['sha256']} for rec in records),
                                     key=lambda rec: rec['run'])},
        'thresholds': threshold_table(),
        'registered': {'runs': count, 'source': source, 'gates_per_run': k, 'gates': count * k,
                       'params_source': policy['params_source']},
        'units': units, 'pool': pool_part, 'item2': item2_part, 'item4': item4_part,
        # J5 (check P3-2): an item-4 experiment's counts are its `item4` block's; J3's generic gate counts would count a
        # label-judged FAILED run as excluded, so they are left out there.
        'gate_counts': None if name in ITEM4_SCENARIOS else counts,
        'exclusions': exclusions,
        'outcome': outcome,
        'verdict': verdict_block(outcome, criterion, figures),
    }


def item4_rows(units: list[tuple[int, str, str | None, dict | None]], count: int, scenario: str) -> dict:
    """J5, section 25: one item-4 sub-scenario over its registered runs (045b :383, :524, :1084 and its note). `units`
    holds, per run r < N, its state, code and record observation (None without a record). A label-judged run is a
    judged run, matching or not; a mismatch on a judged turn of a run with no plan mismatch (label-judged or stopped
    partway) is NO-GO evidence (`ITEM4_MISLABEL`). Every other run counts as missing or excluded: more than 5 of 50 (the
    same share of another N) makes the sub-scenario not run (`TEN_PERCENT_RULE`), and so does no judged run
    (`NO_JUDGED_GATES`). J5b (045b :1279): so does a transition of the inventory's list for the sub-scenario that no
    label-judged run reaches (`TRANSITION_NOT_REACHED`). NO_GO comes before NOT_ESTABLISHED (A's Q5, 045b :1084's
    note)."""
    judged = [(r, obs) for r, _, _, obs in units if obs is not None and obs['label_judged']]
    evidence = [(r, obs) for r, _, _, obs in units if obs is not None and obs['nogo_evidence']]
    partial = [r for r, obs in evidence if not obs['label_judged']]
    lost = count - len(judged) - len(partial)
    over = lost * ITEM4_LIMIT['den'] > ITEM4_LIMIT['num'] * count
    nogo = ['ITEM4_MISLABEL'] if evidence else []
    not_established = (['TEN_PERCENT_RULE'] if over else []) + ([] if judged else ['NO_JUDGED_GATES'])
    # J5b (045b :1279 and its dated line; inventory section 2): each transition the sub-scenario lists needs at least
    # one reach over its label-judged runs, counted per sub-scenario (a run reports its own, `min_transitions`); one not
    # reached makes the sub-scenario NOT_ESTABLISHED, after any NO-GO (the inventory's order, :1084's note).
    required = ITEM4_MIN_TRANSITIONS[scenario]
    reach = {tr: sum(tr in obs['min_transitions'] for _, obs in judged) for tr in required}
    unreached = [tr for tr in required if reach[tr] < ITEM4_MIN_REACH]
    if unreached:
        not_established.append('TRANSITION_NOT_REACHED')
    result = 'NO_GO' if nogo else 'NOT_ESTABLISHED' if not_established else 'GO'
    started = [obs for _, _, _, obs in units if obs is not None]
    ledger = {name: {'count': 0, 'weight_wu': 0, 'fee_sat': 0} for name in ('A', 'C', 'l0_A', 'l0_C')}
    for _, obs in judged:
        for name, part in ledger.items():
            for key in part:
                part[key] += obs['mined_losing'][name][key]
    replaced: dict[str, dict] = {}
    for _, obs in judged:
        w = obs['replaced_winner']
        if w is not None:
            part = replaced.setdefault(str(w['depth']), {'runs': 0, 'replaced': 0, 'end_states': {}})
            part['runs'] += 1
            part['replaced'] += w['replaced']
            end = w['end_state']['outcome'].split('@', 1)[0] if w['end_state'] is not None else 'NONE'
            part['end_states'][end] = part['end_states'].get(end, 0) + 1
    transitions = {name: sum(name in obs['transitions'] for _, obs in judged) for name in ITEM4_TRANSITIONS}
    exclusions: dict[str, int] = {}
    counted = {r for r, _ in judged} | set(partial)
    for r, state, code, obs in units:
        if r not in counted:
            key = code or 'NONE'
            exclusions[key] = exclusions.get(key, 0) + 1
    release = any(obs['release_class'] is not None for _, obs in judged)
    return {'scenario': scenario, 'runs': count, 'judged': len(judged), 'nogo_evidence_runs': [r for r, _ in evidence],
            'nogo_evidence_partial_runs': partial, 'missing_or_excluded': lost, 'limit': ITEM4_LIMIT,
            'over_10_percent': over,
            'label_mismatch_runs': [r for r, obs in judged if obs['label_mismatch']],
            'label_judged_failed_runs': [r for r, obs in judged if obs['driver_label_check'] is not None],
            'win_rate': {'judged': fraction(sum(bool(obs['project_born']) for _, obs in judged), len(judged)),
                         'started': fraction(sum(bool(obs['project_born']) for obs in started), len(started)),
                         'scope': 'REPORTED_NOT_JUDGED'},
            'mined_losing': dict(ledger, scope='REPORTED_NOT_JUDGED'),
            'replaced_winners': replaced if scenario == 'ITEM4_REORG' else None,
            'release_label': constant('ITEM4_RELEASE_CLASS_T_ROW') if release else None,
            'not_run': sorted({case for obs in started for case in obs['not_run']}),
            'transitions': transitions,
            'min_transitions': {'required': list(required), 'reach': reach, 'min_reach': ITEM4_MIN_REACH,
                                'unreached': unreached, 'source': 'CT-P5-001 inventory section 2 (045b :1279)'},
            'driver_exclusions_unreproduced': sorted(r for r, _, _, obs in units
                                                     if obs is not None and not obs['code_reproduced']),
            'driver_label_disagreements': sorted(r for r, _, _, obs in units if obs is not None
                                                 and (obs['driver_label_disagreements']
                                                      or (obs['driver_label_check'] is not None
                                                          and not obs['driver_label_check']['reproduced']))),
            'standin_runs': sum(obs['project_seat'] == ITEM4_STANDIN for obs in started),
            'exclusions': exclusions,
            'outcome': {'result': result, 'nogo': nogo, 'not_established': not_established}}


def item4_view(part: dict) -> tuple[dict, dict]:
    """Section 29 (045b :1090): one sub-scenario's criterion (045b :383, :1084's note, :1279) and what `item4_rows`
    counted, for the record's `verdict`. `matching_runs` is null with no label-judged run, and `differing_runs` when no
    run is label-judged and none carries NO-GO evidence: null, never 0."""
    judged, differing = part['judged'], len(part['nogo_evidence_runs'])
    return ({'mislabel_nogo': constant('ITEM4_MISLABEL_NOGO'), 'subscenario_limit': ITEM4_LIMIT,
             'min_transitions': list(part['min_transitions']['required']), 'min_reach': ITEM4_MIN_REACH},
            {'judged_runs': judged, 'matching_runs': judged - len(part['label_mismatch_runs']) if judged else None,
             'differing_runs': differing if judged or differing else None,
             'missing_or_excluded': part['missing_or_excluded'],
             'unreached_transitions': list(part['min_transitions']['unreached'])})


def item4_observation_ok(obs, experiment: str) -> bool:
    """J5: an `item4` record's `observation` (section 24), every field the experiment reads."""
    def ledger(v):
        return type(v) is dict and all(type(v.get(k)) is int and v[k] >= 0 for k in ('count', 'weight_wu', 'fee_sat'))
    if type(obs) is not dict or obs.get('state') not in ('OBSERVED', 'EXCLUDED') or not _code(obs.get('code')) \
            or type(obs.get('observation_id')) is not str or obs.get('scenario') != experiment:
        return False
    winner, check, mined = obs.get('replaced_winner'), obs.get('driver_label_check'), obs.get('mined_losing')
    end = winner.get('end_state') if type(winner) is dict else None
    return (all(type(obs.get(k)) is bool for k in ('code_reproduced', 'label_judged', 'label_mismatch',
                                                    'nogo_evidence'))
            and not (obs['nogo_evidence'] and not obs['label_mismatch'])
            and not (obs['label_judged'] and obs['project_seat'] != L0_KIND)
            and not ((obs['label_judged'] or obs['nogo_evidence']) and obs.get('mismatches') != [])
            and obs.get('project_born') in (None, True, False) and obs.get('project_seat') in (L0_KIND, ITEM4_STANDIN)
            and _texts(obs.get('transitions')) and _texts(obs.get('not_run')) and _texts(obs.get('mismatches'))
            and _texts(obs.get('min_transitions'))
            and len(set(obs['min_transitions'])) == len(obs['min_transitions'])
            and set(obs['min_transitions']) <= set(ITEM4_MIN_TRANSITIONS[experiment])
            and type(obs.get('driver_label_disagreements')) is list
            and (check is None or (type(check) is dict and type(check.get('reproduced')) is bool))
            and type(mined) is dict and all(ledger(mined.get(k)) for k in ('A', 'C', 'l0_A', 'l0_C'))
            and (winner is None or (type(winner) is dict and type(winner.get('depth')) is int
                                    and type(winner.get('replaced')) is bool
                                    and (end is None or (type(end) is dict and type(end.get('outcome')) is str))))
            and (obs.get('release_class') is None or type(obs['release_class']) is dict))


ITEM4_OUTCOME_SCHEMA = 'BITAGI_CT_ARDR_ITEM4_JUDGEMENT_V1'
ITEM4_OUTCOME_LABELS = ['CLASS_T', 'REGTEST', 'JUDGE_RECORD', 'J5_ITEM4_OUTCOME']
ITEM4_EXPERIMENT_LABELS = ['CLASS_T', 'REGTEST', 'JUDGE_RECORD', 'J5_ITEM4_EXPERIMENT']


def item4_experiment_record(blob: bytes) -> dict:
    """One `experiment --experiment ITEM4_<S>` record of this judge, read strictly (RECORD_SHAPE): its experiment, mode,
    tool, bindings, `item4` block and outcome."""
    doc = json_document(blob, 'RECORD')
    judge, inputs, part, outcome = (doc.get(k) for k in ('judge', 'inputs', 'item4', 'outcome'))
    need(doc.get('schema') == EXPERIMENT_SCHEMA and doc.get('experiment') in ITEM4_SCENARIOS
         and type(doc.get('labels')) is list and 'J5_ITEM4_EXPERIMENT' in doc['labels']
         and type(doc.get('mode')) is str and type(judge) is dict and type(judge.get('tool_sha256')) is str
         and type(inputs) is dict and type(inputs.get('prereg_045b')) is dict
         and type(part) is dict and part.get('scenario') == doc['experiment']
         and type(part.get('replaced_winners')) in (dict, type(None)) and type(part.get('mined_losing')) is dict
         and type(outcome) is dict and outcome.get('result') in ('GO', 'NO_GO', 'NOT_ESTABLISHED')
         and _texts(outcome.get('nogo')) and _texts(outcome.get('not_established')), 'RECORD_SHAPE')
    # Check P3-1: the result agrees with its lists (NO_GO with a NO-GO code; NOT_ESTABLISHED with none and a reason;
    # GO with neither), and NO-GO evidence runs mean NO_GO.
    result, nogo, not_established = outcome['result'], outcome['nogo'], outcome['not_established']
    evidence = part.get('nogo_evidence_runs')
    need((bool(nogo) == (result == 'NO_GO')) and (result != 'NOT_ESTABLISHED' or bool(not_established))
         and (result != 'GO' or not not_established) and type(evidence) is list
         and (not evidence or result == 'NO_GO'), 'RECORD_SHAPE')
    return {'experiment': doc['experiment'], 'sha256': sha256(blob), 'mode': doc['mode'],
            'tool_sha256': judge['tool_sha256'], 'policy_sha256': inputs.get('policy_sha256'),
            'registration_sha256': inputs.get('registration_sha256'),
            'prereg_sha256': inputs['prereg_045b'].get('sha256'), 'item4': part,
            'outcome': {'result': outcome['result'], 'nogo': list(outcome['nogo']),
                        'not_established': list(outcome['not_established'])}}


def item4_outcome(args) -> dict:
    """The `item4-outcome` command (section 25; A's Q6): item 4's outcome from up to four sub-scenario records, which
    share this judge's file, the mode, the policy, the registration and the 045b file read now (RECORD_TOOL,
    RECORD_BINDING). Two records of one sub-scenario are ITEM4_RECORD_DUPLICATE. Item 4 is NO_GO when a sub-scenario
    is NO_GO; else NOT_ESTABLISHED when one is NOT_ESTABLISHED or has no record ("not run", 045b :383); else GO. The
    section 4.5 rows :505 and :506 take item 4's outcome; :499 and :500 are reported only (045b :536)."""
    prereg = read_prereg(args.prereg)
    tool = sha256(TOOL_PATH.read_bytes())
    records = [item4_experiment_record(read_file(path, 'RECORD', RECORD_LIMIT)) for path in args.record]
    by: dict[str, dict] = {}
    for rec in records:
        need(rec['experiment'] not in by, 'ITEM4_RECORD_DUPLICATE')
        by[rec['experiment']] = rec
        need(rec['tool_sha256'] == tool, 'RECORD_TOOL', EXIT_REFUSAL)
        need(rec['mode'] == args.mode and rec['prereg_sha256'] == prereg['sha256'], 'RECORD_BINDING', EXIT_REFUSAL)
    need(len({(rec['policy_sha256'], rec['registration_sha256']) for rec in records}) <= 1, 'RECORD_BINDING',
         EXIT_REFUSAL)
    scenarios, nogo, not_established = {}, [], []
    for name in ITEM4_SCENARIOS:
        rec = by.get(name)
        if rec is None:
            scenarios[name] = {'present': False, 'result': None, 'nogo': [], 'not_established': ['NOT_RUN']}
            not_established.append(f'NOT_RUN:{name}')
            continue
        own = rec['outcome']
        scenarios[name] = dict(own, present=True, sha256=rec['sha256'])
        if own['result'] == 'NO_GO':
            nogo += [f'{code}:{name}' for code in own['nogo']]
        elif own['result'] == 'NOT_ESTABLISHED':
            not_established += [f'{code}:{name}' for code in own['not_established']]
    result = 'NO_GO' if nogo else 'NOT_ESTABLISHED' if not_established else 'GO'
    item_outcome = {'result': result, 'nogo': nogo, 'not_established': not_established}
    # Section 29 (045b :1090): item 4's requirement verdict, which the rows :505 and :506 take with its outcome. A
    # sub-scenario without a record is observed as null (not run), never as GO.
    verdict = verdict_block(item_outcome, {'mislabel_nogo': constant('ITEM4_MISLABEL_NOGO'),
                                           'sub_scenarios': list(ITEM4_SCENARIOS)},
                            {'sub_scenarios': {name: scenarios[name]['result'] for name in ITEM4_SCENARIOS}})
    reorg = by.get('ITEM4_REORG')
    mined = {name: by[name]['item4']['mined_losing'] for name in by}
    labels = list(ITEM4_OUTCOME_LABELS) + (['EXPLORATORY_NOT_A_VERDICT'] if args.mode != 'CONFIRMATORY' else [])
    first = records[0] if records else None
    return {
        'schema': ITEM4_OUTCOME_SCHEMA, 'labels': labels, 'item': 'ITEM4', 'mode': args.mode,
        'evidence_status': 'CONFIRMATORY' if args.mode == 'CONFIRMATORY' else 'EXPLORATORY',
        'judge': {'unit': 'J5', 'tool_sha256': tool},
        'inputs': {'prereg_045b': prereg, 'records': {name: by[name]['sha256'] for name in sorted(by)},
                   'policy_sha256': first['policy_sha256'] if first else None,
                   'registration_sha256': first['registration_sha256'] if first else None},
        'thresholds': threshold_table(),
        'scenarios': scenarios,
        'rows': {'505': dict(item_outcome, source='ITEM4', verdict=verdict),
                 '506': dict(item_outcome, source='ITEM4', verdict=verdict,
                             replaced_winners=reorg['item4']['replaced_winners'] if reorg else None,
                             release_label=reorg['item4'].get('release_label') if reorg else None),
                 '499': {'result': 'REPORTED_NOT_JUDGED', 'mined_losing': mined},
                 '500': {'result': 'REPORTED_NOT_JUDGED', 'mined_losing': mined}},
        'outcome': item_outcome,
        'verdict': verdict,
    }


# ---------------------------------------------------------------------------------------------------------
# B4-21a: the pure core of the ITEM3W judge (045b section 14.18, frozen by #664; R18-6 tooling 4 and R18-8). No command
# calls it yet: B4-21b wires it into `item3w`, `experiment --experiment ITEM3W` and `item3-outcome`, and J6b calls the
# shared part (QJ6-20: the W-row output parser, the W policy check, the tool binding and the generator), so no item-1,
# item-2 or item-4 path reads it. The rules are 045b's, read as the W-row tool reads them where 045b admits two
# readings (A accepted them, #258 issuecomment-6768250495: :1399 literal and R-a reading 1; R-b to R-e as B's defaults;
# the W3-1 table). The unit note `2026-11-25_b421a-item3w-judge-core.md` lists each reading with its line. The
# generator computes every expected list from a plan spec (045b :1521); it never reads the W-row tool or B's modules.

W_CAP = constant('W_COST_CAP_SAT')
W_WINDOW = constant('W_WINDOW_GATES')
W_SUM = constant('W_COST_SUM_SAT')
W_V_REF = constant('V_REF_VB')
W_LINK_BOUND = constant('STRONG_LINK_MIN_SAT')
W_TENURE = constant('TENURE_OFFSET_BLOCKS')
W_TENURE_WINDOW = constant('TENURE_WINDOW_BIRTHS')
W_TENURE_FAILS = constant('TENURE_FAIL_MIN')
W_CHECKPOINT = constant('POP_CHECKPOINT_BLOCKS')
W_BAND_LOW, W_BAND_HIGH = constant('POP_BAND')
W_COHORT_MIN = constant('POP_MIN_COHORT')
W_POP_FLOOR = constant('POP_FLOOR')
W_EFFECTIVE = constant('EFFECTIVE_OFFSET')
W_GATE_DEADLINE = constant('DATA_RESOLUTION_BLOCKS')
# 045b :1398, :1444 and the W3-2 reading (note 2026-11-04_item3w-w32.md :182): an unresolved history has one deadline,
# 2,016 blocks after the height B + 4,033 at which its tenure status would be established.
W_HISTORY_DEADLINE = W_TENURE + constant('HISTORY_DEADLINE_BLOCKS')
W_LAG = constant('W_DATA_LAG_BLOCKS')
W_TIMEOUT = constant('HEART_TIMEOUT_BLOCKS')
W_OPEN_SPACING = constant('OPEN_SPACING_BLOCKS')
W_REPEAT_GATES = constant('REPEAT_GATES')
W_D_T_STEP = constant('D_T_REPEAT_STEP')
W_D_P_STEP = constant('D_P_REPEAT_STEP')
W_ZERO_BEAT_RUN = constant('ITEM3_ZERO_BEAT_GATES')   # 045b :1412: D-Z15 is :435's 15-count, unchanged in counting
W_POLICY_SCHEMA = 'BITAGI_CT_ARDR_W_POLICY_V1'       # ARDR_WROWS_V1 section 4
W_POLICY_VALUES = constant('ITEM3W_W_POLICY')
W_FIELDS = ('winner', 'package_fee', 'block_floor', 'opening', 'link')   # 045b :1396; ARDR_WROWS_V1 section 2's order
W_COST_FIELDS = frozenset({'winner', 'package_fee', 'block_floor', 'opening'})   # adverse c* = the cap (:1399)
W_LINK_FIELDS = frozenset({'winner', 'link'})   # adverse: unknown control inside every adjacent run (:1399)
W_GATE_KEYED = frozenset({'D_C4', 'D_C15', 'D_C_REPEAT', 'W_C', 'D_Z15', 'D_Z_REPEAT'})   # the rest: by height
LINKAGE_FREE = 'LINKAGE_FREE'
ZERO_BEAT = 'ZERO_BEAT'
SPEC_KEYS = {'h0', 'first_effective', 'h_e', 'tip', 'gates'}
SPEC_GATE_KEYS = {'gate', 'project', 'birth', 'owner', 'link', 'key', 'spends', 'package', 'others', 'unresolved',
                  'beats'}


def _spec(condition: bool, what: str) -> None:
    """A plan spec that breaks its own shape is the judge's own error (exit 4 through `run`), never a refusal code."""
    if not condition:
        raise ValueError('ITEM3W plan spec: ' + what)


def ceil_fraction(value: Fraction) -> int:
    return -(-value.numerator // value.denominator)


def w_floor(others: list[dict]) -> Fraction:
    """m_g (045b :1330-1332): the smallest own feerate r_i such that the other transactions with r <= r_i hold at least
    half the other transactions' vsize (2 x held >= total), exact; 0 when there is none."""
    rates = sorted((Fraction(o['fee'], o['vsize']), o['vsize']) for o in others)
    total, held = sum(vsize for _, vsize in rates), 0
    for rate, vsize in rates:
        held += vsize
        if 2 * held >= total:
            return rate
    return Fraction(0)


def w_counted_cost(opening: bool, fee: int, vsize: int, floor: Fraction) -> int:
    """c*_g (045b :1335-1337): 0 unless opening-block; else max(0, floor(min(cap; F - m V; V_REF (F / V - m)))) in exact
    rationals, floored once at the end."""
    if not opening:
        return 0
    value = min(Fraction(W_CAP), fee - floor * vsize, W_V_REF * (Fraction(fee, vsize) - floor))
    return max(0, value.numerator // value.denominator)


def w_cap_fee(vsize: int, floor) -> int:
    """F_cap(V, m) = max(30,000 + ceil(m V), ceil((30,000 / 213 + m) V)) (045b :1528), exact."""
    m = Fraction(floor)
    return max(W_CAP + ceil_fraction(m * vsize), ceil_fraction((Fraction(W_CAP, W_V_REF) + m) * vsize))


def wrows_check_spec(spec: dict) -> None:
    """The plan spec `wrows_expected` reads (the unit note, section 2): heights `h0` (the D-P checkpoints' H0),
    `first_effective` (first_effective_height), `h_e` (H_e, evaluated at 6 confirmations) and `tip` (the 6-confirmation
    tip), and every accepted birth at or after first_effective_height in birth order, numbered consecutively: `gate`,
    `project`, `birth` (B_g), `owner` (ownership truth), `link` (its item-1 link group: equal names are one ANCESTRY
    group), `key` (its Anchor key: equal keys are a (K) link), `spends` ({gate, value, winner}: outputs of gate g's
    package it spends directly, `winner` when the output is R_g's own), `package` ({fee, vsize} of pkg_g, or None for a
    project gate whose package is not measured), `others` (the other transactions' {fee, vsize}), `unresolved` (the
    W-DATA (ii) fields), `beats` (the accepted BEAT heights, or None for an unresolved history) and, optionally, `end`
    ({height, cause}; else Core's TIMEOUT 2,017 blocks after the last anchor)."""
    _spec(type(spec) is dict and set(spec) == SPEC_KEYS, 'keys')
    _spec(all(type(spec[k]) is int and spec[k] >= 0 for k in SPEC_KEYS - {'gates'}), 'heights')
    _spec(spec['tip'] >= spec['h_e'], 'the tip below H_e')
    gates = spec['gates']
    _spec(type(gates) is list and len(gates) > 0, 'no gate')
    for at, g in enumerate(gates):
        _spec(type(g) is dict and SPEC_GATE_KEYS <= set(g) <= SPEC_GATE_KEYS | {'end'}, 'gate keys')
        _spec(type(g['gate']) is int and (at == 0 or g['gate'] == gates[at - 1]['gate'] + 1), 'gates not consecutive')
        _spec(type(g['birth']) is int and g['birth'] <= spec['h_e'], 'a birth above H_e')
        opened = spec['first_effective'] if at == 0 else gates[at - 1]['birth'] + W_OPEN_SPACING
        _spec(g['birth'] >= opened, 'a birth before its opening height')
        unresolved = g['unresolved']
        _spec(type(unresolved) is list and set(unresolved) <= set(W_FIELDS) and len(set(unresolved)) == len(unresolved),
              'unresolved fields')
        _spec(not (g['project'] and unresolved), 'an unresolved project gate')
        _spec(g['package'] is not None or g['project'] or 'winner' in unresolved, 'a gate without a package')
        _spec(g['others'] is not None or 'block_floor' in unresolved, 'a gate without its other transactions')
        _spec(g['beats'] is not None or not g['project'], "the project's unresolved history")
        _spec(all(set(s) == {'gate', 'value', 'winner'} for s in g['spends']), 'spends')


def wrows_gate_values(spec: dict) -> list[dict]:
    """Per gate (045b :1318-1339, :1396-1399): O_g recomputed (first_effective_height for the first, else B_prev + 144,
    the project counted), the opening flag, F_g, V_g, m_g and c*_g, with W-DATA (ii)'s adverse values (P3 literal: an
    unresolved winner, package fee, block floor or opening gives c* = cap; an unresolved winner or link is unknown
    control) and the deadline B_g + 2,016 of a gate with an unresolved field."""
    values, before = [], None
    for g in spec['gates']:
        unresolved = set(g['unresolved'])
        opened = spec['first_effective'] if before is None else before + W_OPEN_SPACING
        opening = None if 'opening' in unresolved else g['birth'] == opened
        package = g['package'] if 'winner' not in unresolved else None
        fee = None if package is None or 'package_fee' in unresolved else package['fee']
        vsize = None if package is None else package['vsize']
        floor = None if 'block_floor' in unresolved else w_floor(g['others'])
        adverse = bool(unresolved & W_COST_FIELDS)
        if adverse:
            cost = W_CAP
        elif fee is None:
            cost = None   # a project gate without its measured package: in no window, sum or cohort (045b :1371)
        else:
            cost = w_counted_cost(opening, fee, vsize, floor)
        values.append({'gate': g['gate'], 'project': g['project'], 'birth_height': g['birth'], 'open_height': opened,
                       'opening_block': opening, 'package_fee_sat': fee, 'package_vsize_vb': vsize,
                       'block_floor': None if floor is None else {'num': floor.numerator, 'den': floor.denominator},
                       'counted_cost_sat': cost, 'cost_adverse': adverse, 'winner_unknown': 'winner' in unresolved,
                       'unknown_control': bool(unresolved & W_LINK_FIELDS),
                       'unresolved': [f for f in W_FIELDS if f in unresolved],
                       'deadline_height': g['birth'] + W_GATE_DEADLINE if unresolved else None})
        before = g['birth']
    return values


def wrows_strong_link(spec: dict) -> dict[int, str]:
    """STRONG_LINK (045b :1349-1357), over the gates that are not unknown control: (K) equal Anchor keys; (S) gate h
    directly spends an output of R_g itself (g < h, never of another pkg_g transaction) worth at least 30,000 sat. Links
    join transitively; the id is S and the first gate. W3-1 readings: an unknown-control gate takes part in no link, not
    even through another gate's resolved spend of it; the project's gate is an element (it breaks every run)."""
    known = [g for g in spec['gates'] if not set(g['unresolved']) & W_LINK_FIELDS]
    ids = {g['gate'] for g in known}
    found = UnionFind(sorted(ids))
    holders: dict = {}
    for g in known:
        holders.setdefault(g['key'], []).append(g['gate'])
    for same in holders.values():
        for gate in same[1:]:
            found.union(same[0], gate)
    for g in known:
        for spend in g['spends']:
            if (spend['winner'] and spend['gate'] in ids and spend['gate'] < g['gate']
                    and spend['value'] >= W_LINK_BOUND):
                found.union(spend['gate'], g['gate'])
    return {gate: 'S%d' % group[0] for group in found.groups() for gate in group}


def wrows_sequences(spec: dict, strong: dict[int, str]) -> dict[str, list]:
    """Each clustering's cluster per gate: None for an unknown gate (unresolved winner; under STRONG_LINK also an
    unresolved link) and PROJECT for the project's gate, which breaks every run (045b :1371, reading (b)). Ownership is
    the plan's owner; link-based is D2-2's id L and the first known gate of the link group (ARDR_CLUSTER_V1 section
    5)."""
    first: dict = {}
    for g in spec['gates']:
        if 'winner' not in g['unresolved']:
            first.setdefault(g['link'], g['gate'])
    out: dict[str, list] = {'OWNERSHIP': [], 'LINK_BASED': [], 'STRONG_LINK': []}
    for g in spec['gates']:
        unknown = 'winner' in g['unresolved']
        out['OWNERSHIP'].append(PROJECT if g['project'] else None if unknown else g['owner'])
        out['LINK_BASED'].append(PROJECT if g['project'] else None if unknown else 'L%d' % first[g['link']])
        out['STRONG_LINK'].append(PROJECT if g['project'] else strong.get(g['gate']))
    return out


def _w_row(kind: str, clustering: str, cluster, trigger_gate, trigger_height: int, deadline, count: int,
           effective: int | None = None, **extra) -> dict:
    """One W or D row (ARDR_WROWS_V1 sections 5 and 9): its effective height is max(trigger height + 5, deadline) (045b
    :1369, :1401) unless given (W_DATA)."""
    if effective is None:
        effective = trigger_height + W_EFFECTIVE if deadline is None else max(trigger_height + W_EFFECTIVE, deadline)
    return {'row': kind, 'clustering': clustering, 'cluster': cluster, 'trigger_gate': trigger_gate,
            'trigger_height': trigger_height, 'effective_height': effective, 'deadline_height': deadline,
            'count': count, **extra}


def wrows_w_c_rows(values: list[dict], clustering: str, sequence: list, unknown) -> list[dict]:
    """W-C (045b :1375-1384): at the first gate t of a run where gates t - 14 ... t are all in the run, each at c* =
    cap, and C has won a gate of the run at or before t (W3-1: D2-2's trigger rule; an UNKNOWN run counts from its first
    gate, and it gives W_C too). One report per run, trigger height B_t, the window's first gate and its 450,000-sat
    sum; the deadline is the latest among the window's gates with an adverse c* or unknown in this clustering."""
    numbers = [v['gate'] for v in values]
    base = numbers[0]
    rows = []
    for run in runs_of(sequence, numbers):
        for t in range(max(run['first_gate'] + W_WINDOW - 1, run['first_won']), run['last_gate'] + 1):
            span = values[t - W_WINDOW + 1 - base:t + 1 - base]
            if all(v['counted_cost_sat'] == W_CAP for v in span):
                used = [v['deadline_height'] for v in span if v['cost_adverse'] or unknown(v)]
                rows.append(_w_row('W_C', clustering, run['cluster'], t, values[t - base]['birth_height'],
                                   max(used, default=None), W_WINDOW, window_first_gate=t - W_WINDOW + 1,
                                   window_sum_sat=W_CAP * W_WINDOW, first_gate=run['first_gate'],
                                   last_gate=run['last_gate']))
                break
    return rows


def _unknown_deadline(report: dict, at: dict, upto: int) -> int | None:
    """The latest deadline among a report's unknown gates at or before gate `upto` (W3-1 reading of :1398, :1401)."""
    return max((at[g]['deadline_height'] for g in report['unknown_gates'] if g <= upto), default=None)


def wrows_d_c_rows(values: list[dict], clustering: str, sequence: list) -> list[dict]:
    """D-C4 and D-C15 (045b :1407-1411): D2-2's expected 4- and 15-reports (section 10 of the format doc; R1, R3,
    reading (b)) with trigger height B_t; the deadline is the latest among the run's unknown gates at or before the
    trigger. D_C_REPEAT (:1427): a 15-run of length 15 + 15m gets a review at gate max(first + 15 + 15m - 1, the
    15-report's trigger), m >= 1 (W3-1: the max matters only for a run that starts with 30 or more unknown gates)."""
    numbers = [v['gate'] for v in values]
    at = {v['gate']: v for v in values}
    expected = expected_reports(sequence, numbers, REPORT_THRESHOLDS)
    rows = []
    for t in REPORT_THRESHOLDS:
        for report in expected[str(t)]:
            extra = {'first_gate': report['first_gate'], 'last_gate': report['last_gate'], 'length': report['length']}
            trigger = report['trigger_gate']
            rows.append(_w_row('D_C%d' % t, clustering, report['cluster'], trigger, at[trigger]['birth_height'],
                               _unknown_deadline(report, at, trigger), t, **extra))
            if t != W_REPEAT_GATES:
                continue
            count = t + W_REPEAT_GATES
            while count <= report['length']:
                gate = max(report['first_gate'] + count - 1, trigger)
                rows.append(_w_row('D_C_REPEAT', clustering, report['cluster'], gate, at[gate]['birth_height'],
                                   _unknown_deadline(report, at, gate), count, **extra))
                count += W_REPEAT_GATES
    return rows


def wrows_history(g: dict, h_e: int) -> tuple[list[int], int | None, str | None]:
    """A resolved history as at H_e: the BEAT heights at or below H_e, and the end height and cause when the Heart is
    ENDED at or below H_e (else None, None). Without a stated end it is Core's TIMEOUT 2,017 blocks after the last
    anchor (045b :1360-1362): the birth, then each BEAT, each at most 2,016 after the one before; BEATs in one block
    bank no time. A stated end ({height, cause}, e.g. BROKEN) lies in [last BEAT, last BEAT + 2,017]."""
    beats = g['beats']
    _spec(type(beats) is list and all(type(b) is int for b in beats) and beats == sorted(beats), 'BEAT heights')
    last = g['birth']
    for beat in beats:
        _spec(last <= beat < last + W_TIMEOUT, 'a BEAT before its birth or after its Heart ended')
        last = beat
    end = g.get('end')
    if end is None:
        height, cause = last + W_TIMEOUT, 'TIMEOUT'
    else:
        height, cause = end['height'], end['cause']
        _spec(type(height) is int and last <= height <= last + W_TIMEOUT, 'an end outside its last anchor + 2,017')
    seen = [b for b in beats if b <= h_e]
    return (seen, height, cause) if height <= h_e else (seen, None, None)


def wrows_birth(g: dict, value: dict, h_e: int) -> dict:
    """One birth's tenure and zero-BEAT status (045b :1358-1363, :1441-1444; ARDR_WROWS_V1 section 9). Tenure fails when
    the Heart is ENDED at or below B + 4,033; it is established at the end if it failed, else at B + 4,033. Zero-BEAT:
    no accepted BEAT, established at the end (also a non-TIMEOUT end before B + 2,017). W3-2 readings: an unresolved
    history is PENDING until its one deadline B + 4,033 + 2,016, then failed, not CURRENT and zero-BEAT (its D-Z trigger
    height B + 2,017); an unresolved c* counts the cap with the deadline B + 2,016, in E or A as its tenure falls (R-a
    reading 1)."""
    b = g['birth']
    if g['beats'] is None:
        deadline = b + W_HISTORY_DEADLINE
        beats, end, cause = None, None, None
        failed, established, zero, zero_at, zero_trigger = True, deadline, True, deadline, b + W_TIMEOUT
    else:
        deadline = None
        beats, end, cause = wrows_history(g, h_e)
        failed = end is not None and end <= b + W_TENURE
        established = end if failed else b + W_TENURE
        zero = not beats
        zero_at = end if zero else beats[0]
        zero_trigger = zero_at
    return {'gate': g['gate'], 'project': g['project'], 'birth_height': b,
            'counted_cost_sat': value['counted_cost_sat'], 'beat_heights': beats, 'end_height': end, 'end_cause': cause,
            'unresolved': (['cost'] if value['cost_adverse'] else []) + (['history'] if g['beats'] is None else []),
            'tenure_failed': failed, 'established_height': established,
            'tenure_status': 'PENDING' if established > h_e else 'FAILED' if failed else 'SUCCEEDED',
            'zero_beat': zero, 'zero_beat_height': zero_at, 'zero_beat_trigger_height': zero_trigger,
            'cost_deadline_height': b + W_GATE_DEADLINE if value['cost_adverse'] else None,
            'history_deadline_height': deadline}


def w_current_at(birth: dict, height: int) -> bool:
    """CURRENT at a height: not ENDED at or below it; an unresolved history never is (045b :1444)."""
    return birth['history_deadline_height'] is None and (birth['end_height'] is None or birth['end_height'] > height)


def wrows_d_z_rows(statuses: list[dict], h_e: int) -> list[dict]:
    """D-Z15 and D_Z_REPEAT (045b :1412, :1427; :435 and R3): runs of consecutive births established zero-BEAT at or
    below H_e (the project breaks a run); a row at the 15th birth and every further 15th, keyed by that gate, its
    trigger height the latest establishment in the run, its deadline the latest history deadline (R-b: an unresolved
    history counts only from its deadline and breaks the run before it)."""
    rows, run = [], []
    for s in statuses + [None]:
        if (s is not None and not s['project'] and s['zero_beat'] and s['zero_beat_height'] is not None
                and s['zero_beat_height'] <= h_e):
            run.append(s)
            n = len(run)
            if n == W_ZERO_BEAT_RUN or (n > W_ZERO_BEAT_RUN and (n - W_ZERO_BEAT_RUN) % W_REPEAT_GATES == 0):
                deadline = max((x['history_deadline_height'] for x in run
                                if x['history_deadline_height'] is not None), default=None)
                kind = 'D_Z15' if n == W_ZERO_BEAT_RUN else 'D_Z_REPEAT'
                rows.append(_w_row(kind, LINKAGE_FREE, ZERO_BEAT, s['gate'],
                                   max(x['zero_beat_trigger_height'] for x in run), deadline, n,
                                   first_gate=run[0]['gate']))
            continue
        run = []
    return rows


def wrows_prefix(births: list[dict], h_e: int) -> list[tuple[int, int]]:
    """(height, i) at each height at or below H_e where the established prefix's top index i changes (045b :1364-1367):
    i is the highest non-project index whose births 1 ... i are all established; one not yet established holds i."""
    events, highest = [], None
    for index, birth in enumerate(births, start=1):
        if birth['established_height'] > h_e:
            break
        highest = birth['established_height'] if highest is None else max(highest, birth['established_height'])
        if events and events[-1][0] == highest:
            events[-1] = (highest, index)
        else:
            events.append((highest, index))
    return events


def wrows_tenure_rows(births: list[dict], h_e: int) -> list[dict]:
    """D-T, D_T_REPEAT and W-P over the tenure window, births i - 29 ... i of the established prefix (045b :1385-1391,
    :1413-1417, :1428), at each height where i changes. D-T: failures reach 15, edge-triggered, with its repeats at the
    first height where i >= i_0 + 30m (R-c: a jump past two steps gives two). W-P: E >= 450,000 and E > A over the
    window's c*, edge-triggered; its deadline is the latest c* deadline in the window."""
    rows, d_t, w_p, i_0, step = [], False, False, None, 1
    for height, top in wrows_prefix(births, h_e):
        window = births[max(0, top - W_TENURE_WINDOW):top]
        failures = sum(1 for s in window if s['tenure_failed'])
        if failures >= W_TENURE_FAILS:
            if not d_t:
                d_t, i_0, step = True, top, 1
                rows.append(_w_row('D_T', LINKAGE_FREE, None, None, height, None, failures, top_index=top))
            while top >= i_0 + W_D_T_STEP * step:
                rows.append(_w_row('D_T_REPEAT', LINKAGE_FREE, None, None, height, None, failures, top_index=top))
                step += 1
        else:
            d_t = False
        e = sum(s['counted_cost_sat'] for s in window if s['tenure_failed'])
        a = sum(s['counted_cost_sat'] for s in window if not s['tenure_failed'])
        if e >= W_SUM and e > a:
            if not w_p:
                w_p = True
                deadline = max((s['cost_deadline_height'] for s in window if s['cost_deadline_height'] is not None),
                               default=None)
                rows.append(_w_row('W_P', LINKAGE_FREE, None, None, height, deadline, len(window), e_sat=e, a_sat=a,
                                   top_index=top))
        else:
            w_p = False
    return rows


def wrows_d_p_rows(births: list[dict], h0: int, h_e: int) -> list[dict]:
    """D-P and D_P_REPEAT (045b :1418-1421, :1429): at H_k = H0 + 2,016k <= H_e, the cohort is the births with H_k -
    10,080 <= B <= H_k - 4,033; with at least 15 it fires when CURRENT x 2 < size, edge-triggered (a checkpoint not
    evaluated counts as false), and repeats at k_0 + 3m while it holds. Its deadline is the cohort's latest history
    deadline."""
    rows, on, k_0, k = [], False, None, 1
    while h0 + W_CHECKPOINT * k <= h_e:
        h_k = h0 + W_CHECKPOINT * k
        cohort = [s for s in births if h_k - W_BAND_HIGH <= s['birth_height'] <= h_k - W_BAND_LOW]
        current = sum(1 for s in cohort if w_current_at(s, h_k))
        if len(cohort) >= W_COHORT_MIN and current * W_POP_FLOOR['den'] < W_POP_FLOOR['num'] * len(cohort):
            deadline = max((s['history_deadline_height'] for s in cohort if s['history_deadline_height'] is not None),
                           default=None)
            if not on:
                on, k_0 = True, k
                rows.append(_w_row('D_P', LINKAGE_FREE, None, None, h_k, deadline, len(cohort), current=current,
                                   checkpoint=k))
            elif (k - k_0) % W_D_P_STEP == 0:
                rows.append(_w_row('D_P_REPEAT', LINKAGE_FREE, None, None, h_k, deadline, len(cohort), current=current,
                                   checkpoint=k))
        else:
            on = False
        k += 1
    return rows


def wrows_data(spec: dict, values: list[dict], statuses: list[dict]) -> tuple[dict, list[dict]]:
    """W-DATA (045b :1392-1405). (i) W_DATA when the tip is more than 2,016 above H_e: one row at H_e + 2,017, effective
    there and read against the tip (R-d). (ii) `W_PENDING_DATA` while H_e is below the tip or a gate is named; a gate
    with an unresolved field is named from B_g + 5 until its latest deadline (fixture (i): gate 10 from 2,445 to 4,456),
    its fields the gate's then the birth's (cost, history)."""
    h_e, lag = spec['h_e'], spec['tip'] - spec['h_e']
    pending = []
    for value, status in zip(values, statuses):
        deadlines = [d for d in (value['deadline_height'], status['cost_deadline_height'],
                                 status['history_deadline_height']) if d is not None]
        if deadlines:
            pending.append({'gate': value['gate'], 'fields': value['unresolved'] + status['unresolved'],
                            'from_height': value['birth_height'] + W_EFFECTIVE, 'deadline_height': max(deadlines)})
    named = [p['gate'] for p in pending if p['from_height'] <= h_e < p['deadline_height']]
    rows = []
    if lag > W_LAG:
        trigger = h_e + W_LAG + 1
        rows.append(_w_row('W_DATA', LINKAGE_FREE, None, None, trigger, None, lag, effective=trigger))
    return ({'state': 'W_PENDING_DATA' if lag > 0 or named else 'NONE', 'lag_blocks': lag, 'pending_gates': named,
             'pending_data': pending}, rows)


def w_row_order(row: dict) -> tuple:
    return (row['trigger_height'], row['row'], row['clustering'], row['cluster'] or '',
            -1 if row['trigger_gate'] is None else row['trigger_gate'])


def wrows_expected(spec: dict) -> dict:
    """Every W and D row the plan spec gives (045b section 14.18, computed from the plan, never from the chain, :1521):
    W_C under STRONG_LINK and ownership; D_C4, D_C15 and D_C_REPEAT under link-based and ownership; D_Z15, D_Z_REPEAT,
    D_T, D_T_REPEAT, W_P, D_P, D_P_REPEAT and W_DATA linkage-free; the `W_PENDING_DATA` status. A row is listed when its
    effective height is at or below the height it is read at (H_e; W_DATA the tip, R-d); the others are
    `not_yet_effective` (045b :1523). Shared with J6b (QJ6-20)."""
    wrows_check_spec(spec)
    h_e = spec['h_e']
    values = wrows_gate_values(spec)
    strong = wrows_strong_link(spec)
    sequences = wrows_sequences(spec, strong)
    rows = (wrows_w_c_rows(values, 'STRONG_LINK', sequences['STRONG_LINK'], lambda v: v['unknown_control'])
            + wrows_w_c_rows(values, 'OWNERSHIP', sequences['OWNERSHIP'], lambda v: v['winner_unknown'])
            + wrows_d_c_rows(values, 'LINK_BASED', sequences['LINK_BASED'])
            + wrows_d_c_rows(values, 'OWNERSHIP', sequences['OWNERSHIP']))
    statuses = [wrows_birth(g, v, h_e) for g, v in zip(spec['gates'], values)]
    births = [s for s in statuses if not s['project']]
    data, w_data = wrows_data(spec, values, statuses)
    rows += (wrows_d_z_rows(statuses, h_e) + wrows_tenure_rows(births, h_e) + wrows_d_p_rows(births, spec['h0'], h_e)
             + w_data)
    listed, later = [], []
    for row in rows:
        (listed if row['effective_height'] <= (spec['tip'] if row['row'] == 'W_DATA' else h_e) else later).append(row)
    events = wrows_prefix(births, h_e)
    top = events[-1][1] if events else 0
    window = births[max(0, top - W_TENURE_WINDOW):top]
    return {'gates': values, 'strong_link': strong, 'births': statuses,
            'established_prefix': {'top_index': top,
                                   'window_first_index': max(1, top - W_TENURE_WINDOW + 1) if top else 0,
                                   'failures': sum(1 for s in window if s['tenure_failed'])},
            'data': data, 'listed': sorted(listed, key=w_row_order),
            'not_yet_effective': sorted(later, key=w_row_order)}


# The plan of each plant (045b :1523-1554), from the THRESHOLDS rows above. Constants 045b does not state are kept here
# with their source, as ITEM4_REORG_LINE is: the project's owner and Anchor (the D2-2 truth's PROJECT; the L0 seat's
# TEST_ONLY key, not a NUMS label, W3-3b-3a section 1.2), and the run order (run r is the r-th plant, QW3B-4).
ITEM3W_PLANTS = tuple(constant('ITEM3W_PLANTS'))
ITEM3W_H0 = constant('ITEM3W_H0_HEND')['H0']
ITEM3W_H_END = constant('ITEM3W_H0_HEND')['H_end']
ITEM3W_SPACING = constant('ITEM3W_GATE_SPACING')
ITEM3W_CHEAP = constant('ITEM3W_CHEAP_FEE')
ITEM3W_MAINTAIN = constant('ITEM3W_MAINTAINED')
ITEM3W_LINK_SAT = constant('ITEM3W_LINKED')['link_min_sat']
ITEM3W_PROJECT_OWNER = 'PROJECT'


def item3w_package(row: dict, j: int, size: dict) -> tuple[dict, list[dict]]:
    """Gate j's pkg_g {fee, vsize} and other transactions under the plant's fee rule at the measured vsizes `size` (045b
    :1526-1528, :1537-1554; QB-13): cheap 600; F_cap(V, m) (T8's below-cap gates one less); T9's REGISTER 600 with its
    child's F_cap(V_R + V_child, 0) - 600, in pkg_g only when mined in B_j; T12's batch 30,000 absolute; T14's filler at
    exactly 10 x its vsize, every other B_j with no other transaction (m_g = 0)."""
    v, rule = size['R'], row['fee']
    if rule == 'CHEAP':
        package = {'fee': ITEM3W_CHEAP, 'vsize': v}
    elif rule == 'CAP':
        package = {'fee': w_cap_fee(v, row['cap_m']) - (1 if j in row.get('below_cap', ()) else 0), 'vsize': v}
    elif rule == 'CPFP':
        child = size['CHILD']
        child_fee = w_cap_fee(v + child, 0) - ITEM3W_CHEAP
        package = ({'fee': ITEM3W_CHEAP + child_fee, 'vsize': v + child} if row['child_block'] == 0
                   else {'fee': ITEM3W_CHEAP, 'vsize': v})
    else:
        _spec(rule == 'BATCH', 'a fee rule')
        package = {'fee': row['batch']['fee'], 'vsize': v}
    others = []
    if 'filler' in row:
        others = [{'fee': row['filler']['feerate'] * size['FILLER'], 'vsize': size['FILLER']}]
    return package, others


def item3w_beats(row: dict, j: int, birth: int) -> list[int]:
    """Heart j's planned BEAT heights at or below H_end: maintained every 1,008 blocks after birth (045b :1532), else
    the plant row's offsets for j's gate range (T2 none; T4, T5 one in B_j; T10; T11b)."""
    if row['beats'] == 'MAINTAINED':
        return list(range(birth + ITEM3W_MAINTAIN, ITEM3W_H_END + 1, ITEM3W_MAINTAIN))
    for first, last, offsets in row['beats']:
        if first <= j <= last:
            return [birth + offset for offset in offsets if birth + offset <= ITEM3W_H_END]
    raise ValueError('ITEM3W plan spec: no BEAT rule for a gate')


def item3w_plant_spec(plant: str, measured: dict, project: dict | None = None) -> dict:
    """One plant of the 045b section 14.18 table as a plan spec (`wrows_expected`), from the plan alone and the vsizes
    measured from the bytes: `measured[j]` holds gate j's {R} (its REGISTER) and {CHILD} (T9) or {FILLER} (T14);
    `project` is gate 0's {fee, vsize} or None. The project's gate is in no window, sum or cohort and breaks every run
    (:1371), and its later liveness is not judged (:1524), so no row reads its BEATs: the spec gives it none (B4-21b
    reads the replay's). Common plan (:1523-1532): H0 = first_effective_height = 1,000, H_e = the
    6-confirmation tip = H_end = 12,000, gate j born at H0 + spacing x j. Linked: owner X, one link group, R_j spends
    R_{j-1}'s change of at least 100,000 sat (T9: change output 2); gift (T13): owner j, one link group (the gift is
    D2-2 ancestry), R_j spends R_{j-1}'s gift; unlinked: owner X, no link; distinct: owner j, no link. Every Anchor key
    is the gate's own label (QW-5), so no (K) link."""
    row = constant('ITEM3W_PLANT_' + plant)
    n, spacing, funding = row['gates'], row.get('spacing', ITEM3W_SPACING), row['funding']
    gates = [{'gate': 0, 'project': True, 'birth': ITEM3W_H0, 'owner': ITEM3W_PROJECT_OWNER, 'link': 'PROJECT',
              'key': 'PROJECT', 'spends': [], 'package': project, 'others': [], 'unresolved': [], 'beats': []}]
    for j in range(1, n + 1):
        birth = ITEM3W_H0 + spacing * j
        package, others = item3w_package(row, j, measured[j])
        spends = []
        if j > 1 and funding in ('LINKED', 'GIFT'):
            spends = [{'gate': j - 1, 'value': ITEM3W_LINK_SAT if funding == 'LINKED' else row['gift'], 'winner': True}]
        gates.append({'gate': j, 'project': False, 'birth': birth,
                      'owner': 'X' if funding in ('LINKED', 'UNLINKED') else 'O%d' % j,
                      'link': 'CHAIN' if funding in ('LINKED', 'GIFT') else 'G%d' % j,
                      'key': item3w_label(plant, 'G', j, 0), 'spends': spends, 'package': package, 'others': others,
                      'unresolved': [], 'beats': item3w_beats(row, j, birth)})
    return {'h0': ITEM3W_H0, 'first_effective': ITEM3W_H0, 'h_e': ITEM3W_H_END, 'tip': ITEM3W_H_END, 'gates': gates}


# R18-8 (045b :1520, :1531, :1583, :1661): every ITEM3W Anchor is the NUMS point of its label, recomputed here with the
# judge's own affine secp256k1 over integers (stdlib: no EC library). The rule is B's W3-3b-3a note section 1, which
# W3-3b-4 copies into ARDR_RUN_V1: the tag, the label grammar, the counter (no cap below 2^32, 045b :1045's
# precedent), BIP340 lift_x with even y, form U for T2's G<j>_0 and form L (one OP_TRUE leaf at version 0xc0)
# otherwise. ITEM3's capture Anchors (J6, QD3-5) take `nums_point` with their own tag.
SECP_P = 2**256 - 2**32 - 977
SECP_N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
SECP_G = (0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798,
          0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8)
ITEM3W_NUMS_TAG = b'BITAGI_CT_ITEM3W_NUMS_V1'
TAP_LEAF_VERSION = 0xc0
ITEM3W_LABEL = re.compile(r'ITEM3W_(%s)_([GLU])([1-9][0-9]{0,5})_(0|[1-9][0-9]{0,5})\Z' % '|'.join(ITEM3W_PLANTS))


def secp_add(a, b):
    """Affine secp256k1 point addition (None is the point at infinity), doubling when a = b (BIP340's reference)."""
    if a is None:
        return b
    if b is None:
        return a
    if a[0] == b[0] and a[1] != b[1]:
        return None
    if a == b:
        slope = 3 * a[0] * a[0] * pow(2 * a[1], -1, SECP_P) % SECP_P
    else:
        slope = (b[1] - a[1]) * pow(b[0] - a[0], -1, SECP_P) % SECP_P
    x = (slope * slope - a[0] - b[0]) % SECP_P
    return x, (slope * (a[0] - x) - a[1]) % SECP_P


def secp_mul(k: int, point):
    """k * point by double-and-add."""
    result = None
    for i in range(k.bit_length() - 1, -1, -1):
        result = secp_add(result, result)
        if (k >> i) & 1:
            result = secp_add(result, point)
    return result


def lift_x(x: int):
    """BIP340 lift_x: the point with x-coordinate x and even y, or None (x >= p, or x^3 + 7 not a square mod p)."""
    if not 0 <= x < SECP_P:
        return None
    c = (pow(x, 3, SECP_P) + 7) % SECP_P
    y = pow(c, (SECP_P + 1) // 4, SECP_P)
    if y * y % SECP_P != c:
        return None
    return x, y if y % 2 == 0 else SECP_P - y


def tagged_hash(tag: str, message: bytes) -> bytes:
    """BIP340's TH(tag, msg) = SHA-256(SHA-256(tag) || SHA-256(tag) || msg), the tag in ASCII."""
    digest = hashlib.sha256(tag.encode('ascii')).digest()
    return hashlib.sha256(digest + digest + message).digest()


TAP_OP_TRUE_LEAF = tagged_hash('TapLeaf', bytes([TAP_LEAF_VERSION, 1, 0x51]))   # the one leaf is the merkle root


def nums_point(tag: bytes, label: str):
    """(k, P): the first counter k whose SHA-256(tag || 0x00 || label || 0x00 || u32be(k)), read big-endian, is the x of
    a point (lift_x, even y); None only past 2^32 counters (no cap below that, 045b :1045's precedent)."""
    head = tag + b'\x00' + label.encode('ascii') + b'\x00'
    for k in range(U32):
        point = lift_x(int.from_bytes(hashlib.sha256(head + k.to_bytes(4, 'big')).digest(), 'big'))
        if point is not None:
            return k, point
    return None


def item3w_label(plant: str, kind: str, j: int, n: int) -> str:
    """The label `ITEM3W_<plant>_<kind><j>_<n>` (045b :1520; W3-3b-3a section 1.2): kind G for gate j's Heart, L and U
    for its mined and unmined decoy; n 0 for the REGISTER Anchor, m for the m-th BEAT's new Anchor."""
    return 'ITEM3W_%s_%s%d_%d' % (plant, kind, j, n)


def item3w_parse_label(label) -> tuple[str, str, int, int] | None:
    match = ITEM3W_LABEL.match(label) if type(label) is str and label.isascii() else None
    return None if match is None else (match[1], match[2], int(match[3]), int(match[4]))


def item3w_anchor(label: str) -> dict | None:
    """The Anchor a label names (R18-8). Form U, T2's G<j>_0 (045b :1531, :1583: uncontrollable): the NUMS point P is
    the output key, no script path. Form L, every other label: P is the internal key of one OP_TRUE leaf, h =
    TH(TapLeaf, c0 01 51), t = TH(TapTweak, x(P) || h), Q = P + tG, scriptPubKey 0x51 0x20 || x(Q), control block (0xc0
    | y(Q) mod 2) || x(P), spent by exactly the witness [0x51, control]. None for a string that is not a label and for
    the BIP341 failures no label reaches (t >= N, Q at infinity)."""
    fields = item3w_parse_label(label)
    found = None if fields is None else nums_point(ITEM3W_NUMS_TAG, label)
    if found is None:
        return None
    k, point = found
    internal = point[0].to_bytes(32, 'big')
    anchor = {'label': label, 'k': k, 'internal_key': internal.hex()}
    if (fields[0], fields[1], fields[3]) == ('T2', 'G', 0):
        return dict(anchor, form='U', output_key=internal.hex(), parity=None, script_pubkey='5120' + internal.hex(),
                    control_block=None, witness=None)
    tweak = int.from_bytes(tagged_hash('TapTweak', internal + TAP_OP_TRUE_LEAF), 'big')
    q = secp_add(point, secp_mul(tweak, SECP_G)) if tweak < SECP_N else None
    if q is None:
        return None
    output = q[0].to_bytes(32, 'big')
    control = bytes([TAP_LEAF_VERSION | q[1] % 2]) + internal
    return dict(anchor, form='L', output_key=output.hex(), parity=q[1] % 2, script_pubkey='5120' + output.hex(),
                control_block=control.hex(), witness=['51', control.hex()])


# The W-row tool's output (ARDR_WROWS_V1 sections 6 and 10), read strictly: a part that does not follow the format is
# `WrowsMalformed`, which the caller turns into the outcome WROWS_OUTPUT_MALFORMED:<part> (NO-GO in both ITEM3W rows,
# QB-10, as J1's D2_2_OUTPUT_MALFORMED; AJV1 :392, :428-429). It is not a refusal and raises no code.
WROWS_SCHEMA = 'BITAGI_CT_ARDR_WROWS_V1'
WROWS_LABELS = ['TOOL_RECORD_NOT_VERDICT', 'NO_NODE_READ']
WROWS_KEYS = {'schema', 'labels', 'inputs', 'w_policy', 'first_effective_height', 'evaluated_height', 'd2_2_incomplete',
              'gates', 'strong_link', 'd_reports', 'w_reports', 'repeat_reviews', 'not_yet_effective'}
WROWS_INPUTS = ('wgates_sha256', 'd2_2_sha256', 'w_policy_sha256')
WROWS_ROW_KEYS = ('row', 'clustering', 'cluster', 'trigger_gate', 'trigger_height', 'effective_height',
                  'deadline_height', 'count')
WROWS_ROW_EXTRA = {'D_C4': ('first_gate', 'last_gate', 'length'), 'D_C15': ('first_gate', 'last_gate', 'length'),
                   'D_C_REPEAT': ('first_gate', 'last_gate', 'length'),
                   'W_C': ('window_first_gate', 'window_sum_sat', 'first_gate', 'last_gate'),
                   'D_Z15': ('first_gate',), 'D_Z_REPEAT': ('first_gate',), 'D_T': ('top_index',),
                   'D_T_REPEAT': ('top_index',), 'D_P': ('current', 'checkpoint'),
                   'D_P_REPEAT': ('current', 'checkpoint'), 'W_P': ('e_sat', 'a_sat', 'top_index'), 'W_DATA': ()}
WROWS_CLUSTERINGS = {'D_C4': ('LINK_BASED', 'OWNERSHIP'), 'D_C15': ('LINK_BASED', 'OWNERSHIP'),
                     'D_C_REPEAT': ('LINK_BASED', 'OWNERSHIP'), 'W_C': ('STRONG_LINK', 'OWNERSHIP')}
WROWS_PLACES = {
    'd_reports': ('D_C4', 'D_C15'), 'w_reports': ('W_C',), 'repeat_reviews': ('D_C_REPEAT',),
    'not_yet_effective': ('D_C4', 'D_C15', 'D_C_REPEAT', 'W_C'),
    'linkage_free.d_reports': ('D_Z15', 'D_T', 'D_P'), 'linkage_free.w_reports': ('W_P', 'W_DATA'),
    'linkage_free.repeat_reviews': ('D_Z_REPEAT', 'D_T_REPEAT', 'D_P_REPEAT'),
    'linkage_free.not_yet_effective': ('D_Z15', 'D_T', 'D_P', 'W_P', 'D_Z_REPEAT', 'D_T_REPEAT', 'D_P_REPEAT'),
}
WROWS_GATE_KEYS = {'gate', 'project', 'birth_height', 'open_height', 'opening_block', 'winner_txid', 'package_fee_sat',
                   'package_vsize_vb', 'block_floor', 'counted_cost_sat', 'unresolved', 'deadline_height',
                   'strong_link_cluster'}
WROWS_LF_KEYS = {'h0', 'evaluated_height', 'tip_height', 'births', 'established_prefix', 'data', 'd_reports',
                 'w_reports', 'repeat_reviews', 'not_yet_effective'}
WROWS_BIRTH_KEYS = {'gate', 'project', 'birth_height', 'open_height', 'opening_block', 'counted_cost_sat',
                    'beat_heights', 'end_height', 'end_cause', 'unresolved', 'tenure_failed', 'established_height',
                    'tenure_status', 'zero_beat', 'zero_beat_height', 'zero_beat_trigger_height',
                    'cost_deadline_height', 'history_deadline_height'}


class WrowsMalformed(Exception):
    """A W-row output that does not follow its format; `part` names the first part that fails."""

    def __init__(self, part: str):
        super().__init__(part)
        self.part = part


def _shape(condition: bool, part: str) -> None:
    if not condition:
        raise WrowsMalformed(part)


def _nat(value) -> bool:
    return type(value) is int and value >= 0


def _opt_nat(value) -> bool:
    return value is None or _nat(value)


def _nats(value) -> bool:
    return type(value) is list and all(_nat(v) for v in value)


def wrows_row(row, place: str) -> None:
    """One row of a W-row output list: a row kind that list holds, exactly its keys, its clustering and cluster (a
    cluster row's id; ZERO_BEAT for D-Z; null for the other linkage-free rows), a trigger gate exactly for a gate-keyed
    row, and non-negative integers (a deadline may be null)."""
    _shape(type(row) is dict and row.get('row') in WROWS_PLACES[place], place)
    kind = row['row']
    _shape(set(row) == set(WROWS_ROW_KEYS + WROWS_ROW_EXTRA[kind]), place)
    if kind in WROWS_CLUSTERINGS:
        _shape(row['clustering'] in WROWS_CLUSTERINGS[kind] and type(row['cluster']) is str and row['cluster'] != '',
               place)
    else:
        _shape(row['clustering'] == LINKAGE_FREE and row['cluster'] == (ZERO_BEAT if kind in W_GATE_KEYED else None),
               place)
    _shape(_nat(row['trigger_gate']) if kind in W_GATE_KEYED else row['trigger_gate'] is None, place)
    _shape(all(_nat(row[k]) for k in ('trigger_height', 'effective_height', 'count') + WROWS_ROW_EXTRA[kind])
           and _opt_nat(row['deadline_height']), place)


def wrows_gates_part(doc: dict) -> None:
    gates = doc['gates']
    _shape(type(gates) is list and len(gates) > 0, 'gates')
    for g in gates:
        _shape(type(g) is dict and set(g) == WROWS_GATE_KEYS and _nat(g['gate']) and type(g['project']) is bool
               and all(_nat(g[k]) for k in ('birth_height', 'open_height', 'counted_cost_sat'))
               and g['opening_block'] in (None, True, False)
               and (g['winner_txid'] is None or (type(g['winner_txid']) is str and HEX64.match(g['winner_txid'])))
               and all(_opt_nat(g[k]) for k in ('package_fee_sat', 'package_vsize_vb', 'deadline_height'))
               and (g['block_floor'] is None or (type(g['block_floor']) is dict
                                                 and set(g['block_floor']) == {'num', 'den'}
                                                 and _nat(g['block_floor']['num']) and _nat(g['block_floor']['den'])
                                                 and g['block_floor']['den'] > 0))
               and type(g['unresolved']) is list and all(f in W_FIELDS for f in g['unresolved'])
               and (g['strong_link_cluster'] is None or type(g['strong_link_cluster']) is str), 'gates')
    strong = doc['strong_link']
    _shape(type(strong) is dict and set(strong) == {'links', 'clusters'} and type(strong['links']) is list
           and type(strong['clusters']) is list, 'strong_link')
    for link in strong['links']:
        _shape(type(link) is dict and set(link) == {'kind', 'gates', 'via'} and link['kind'] in ('K', 'S')
               and _nats(link['gates']) and len(link['gates']) == 2 and type(link['via']) is str, 'strong_link')
    for cluster in strong['clusters']:
        _shape(type(cluster) is dict and set(cluster) == {'id', 'gates', 'project'} and type(cluster['id']) is str
               and _nats(cluster['gates']) and type(cluster['project']) is bool, 'strong_link')


def wrows_linkage_free_part(part) -> None:
    _shape(type(part) is dict and set(part) == WROWS_LF_KEYS
           and all(_nat(part[k]) for k in ('h0', 'evaluated_height', 'tip_height')), 'linkage_free')
    births = part['births']
    _shape(type(births) is list and len(births) > 0, 'linkage_free.births')
    for b in births:
        _shape(type(b) is dict and set(b) == WROWS_BIRTH_KEYS and _nat(b['gate'])
               and all(type(b[k]) is bool for k in ('project', 'tenure_failed', 'zero_beat'))
               and _nat(b['birth_height']) and _opt_nat(b['counted_cost_sat'])
               and (b['beat_heights'] is None or _nats(b['beat_heights']))
               and all(_opt_nat(b[k]) for k in ('open_height', 'end_height', 'established_height', 'zero_beat_height',
                                                'zero_beat_trigger_height', 'cost_deadline_height',
                                                'history_deadline_height'))
               and b['opening_block'] in (None, True, False) and (b['end_cause'] is None or type(b['end_cause']) is str)
               and type(b['unresolved']) is list and all(f in ('cost', 'history') for f in b['unresolved'])
               and b['tenure_status'] in ('FAILED', 'SUCCEEDED', 'PENDING'), 'linkage_free.births')
    prefix = part['established_prefix']
    _shape(type(prefix) is dict and set(prefix) == {'top_index', 'window_first_index', 'failures'}
           and all(_nat(v) for v in prefix.values()), 'linkage_free.established_prefix')
    data = part['data']
    _shape(type(data) is dict and set(data) == {'state', 'lag_blocks', 'pending_gates', 'pending_data'}
           and data['state'] in ('W_PENDING_DATA', 'NONE') and _nat(data['lag_blocks']) and _nats(data['pending_gates'])
           and type(data['pending_data']) is list, 'linkage_free.data')
    for item in data['pending_data']:
        _shape(type(item) is dict and set(item) == {'gate', 'fields', 'from_height', 'deadline_height'}
               and all(_nat(item[k]) for k in ('gate', 'from_height', 'deadline_height'))
               and type(item['fields']) is list and all(type(f) is str for f in item['fields']), 'linkage_free.data')


def wrows_parse(text, births: bool = True) -> dict:
    """The W-row tool's output text (ARDR_WROWS_V1 sections 6 and 10), checked strictly and fail closed: canonical ASCII
    JSON ending in one LF (sorted keys, `,` and `:`, as the tool writes it), exactly section 6's keys (with
    `linkage_free` and `inputs.wbirths_sha256` exactly when `births`: ITEM3W always gives births), the schema and
    labels, the SHA-256 inputs, the four W policy values as integers, and each list's rows (`wrows_row`). Raises
    WrowsMalformed(part); returns the document."""
    _shape(type(text) is str and text.isascii(), 'encoding')
    try:
        doc = json.loads(text, object_pairs_hook=_object, parse_constant=_refuse_number, parse_float=_refuse_number)
        _shape(type(doc) is dict, 'json')
        again = canonical(doc).decode('ascii') + '\n'
    except (ValueError, RecursionError):
        raise WrowsMalformed('json') from None
    _shape(text == again, 'encoding')
    _shape(set(doc) == WROWS_KEYS | ({'linkage_free'} if births else set()), 'keys')
    _shape(doc['schema'] == WROWS_SCHEMA, 'schema')
    _shape(doc['labels'] == WROWS_LABELS, 'labels')
    inputs = doc['inputs']
    names = WROWS_INPUTS + (('wbirths_sha256',) if births else ())
    _shape(type(inputs) is dict and set(inputs) == set(names)
           and all(type(v) is str and HEX64.match(v) for v in inputs.values()), 'inputs')
    _shape(type(doc['w_policy']) is dict and set(doc['w_policy']) == set(W_POLICY_VALUES)
           and all(type(v) is int for v in doc['w_policy'].values()), 'w_policy')
    _shape(_nat(doc['first_effective_height']) and _nat(doc['evaluated_height']), 'heights')
    _shape(type(doc['d2_2_incomplete']) is bool, 'd2_2_incomplete')
    wrows_gates_part(doc)
    for place in ('d_reports', 'w_reports', 'repeat_reviews', 'not_yet_effective'):
        _shape(type(doc[place]) is list, place)
        for row in doc[place]:
            wrows_row(row, place)
    if births:
        wrows_linkage_free_part(doc['linkage_free'])
        for name in ('d_reports', 'w_reports', 'repeat_reviews', 'not_yet_effective'):
            place = 'linkage_free.' + name
            _shape(type(doc['linkage_free'][name]) is list, place)
            for row in doc['linkage_free'][name]:
                wrows_row(row, place)
    return doc


def wrows_observed(doc: dict) -> dict:
    """A parsed output as the comparison reads it: every listed row, every row not yet effective, and the status."""
    part = doc.get('linkage_free', {})
    lists = ('d_reports', 'w_reports', 'repeat_reviews')
    return {'listed': [r for name in lists for r in doc[name] + part.get(name, [])],
            'not_yet_effective': doc['not_yet_effective'] + part.get('not_yet_effective', []),
            'data': part.get('data')}


def wrows_w_policy_problem(doc) -> str | None:
    """The W policy file's object (ARDR_WROWS_V1 section 4) against 045b :1623 and :1579 (:1044's note): exactly the
    schema and the four keys, each an integer equal to its constant citing section 14.18. Returns 'schema' for the
    object, its key set or schema, else the first key whose value differs, else None. Pure: B4-21b and J6b refuse from
    it with their own code."""
    if type(doc) is not dict or set(doc) != {'schema'} | set(W_POLICY_VALUES) or doc['schema'] != W_POLICY_SCHEMA:
        return 'schema'
    for key in W_POLICY_VALUES:
        if type(doc[key]) is not int or doc[key] != W_POLICY_VALUES[key]:
            return key
    return None


def wrows_binding(doc: dict, files: dict) -> list[str]:
    """The output bound to the input files the driver logged (ARDR_WROWS_V1 section 6 `inputs`): each file's SHA-256 is
    the output's, a births file exactly when the output names one, and the output's `w_policy` is the frozen W policy's
    four values. `files` maps wgates, d2_2, w_policy and wbirths to bytes (wbirths may be absent). Returns the names
    that fail, in that order (empty when bound): B4-21b's plan field `wrows_binding`."""
    failed = []
    for name, key in (('wgates', 'wgates_sha256'), ('d2_2', 'd2_2_sha256'), ('w_policy', 'w_policy_sha256'),
                      ('wbirths', 'wbirths_sha256')):
        blob, stated = files.get(name), doc['inputs'].get(key)
        if (blob is None) != (stated is None) or (blob is not None and sha256(blob) != stated):
            failed.append(name)
    if doc['w_policy'] != W_POLICY_VALUES:
        failed.append('w_policy_values')
    return failed


# The comparison (045b :1515, :1425, :1370; QB-5 as A took it): rows are matched on their key, (row, clustering,
# cluster, trigger gate) for the gate-keyed rows and (row, clustering, cluster, trigger height) for the rest (:1379,
# :1388, :1415, :1421, :1431); then the trigger height, the effective height and the counts are compared. A missing and
# an extra row of one (row, clustering, cluster) pair as `wrong_trigger`, like J1's `wrong_gate` (`late` when the
# reported trigger is later). Rows are multisets (R-c: two D_T_REPEAT rows may share a key). `not_yet_effective` and the
# other fields are diagnostics. Each difference is NO-GO in the row its family maps to (:1517; QB-10 for the repeats).
ITEM3W_COUNTS = {'D_C4': ('count',), 'D_C15': ('count',), 'D_C_REPEAT': ('count',),
                 'W_C': ('count', 'window_first_gate', 'window_sum_sat'),
                 'D_Z15': ('count', 'first_gate'), 'D_Z_REPEAT': ('count', 'first_gate'),
                 'D_T': ('count', 'top_index'), 'D_T_REPEAT': ('count', 'top_index'),
                 'D_P': ('count', 'current', 'checkpoint'), 'D_P_REPEAT': ('count', 'current', 'checkpoint'),
                 'W_P': ('count', 'e_sat', 'a_sat', 'top_index'), 'W_DATA': ('count',)}
ITEM3W_ROW_OF = {**{kind: '503' for kind in constant('ITEM3W_ROW_503')},
                 **{kind: '382' for kind in constant('ITEM3W_ROW_382')}}


def item3w_key(row: dict) -> tuple:
    trigger = row['trigger_gate'] if row['row'] in W_GATE_KEYED else row['trigger_height']
    return (row['row'], row['clustering'], row['cluster'], trigger)


def _key_order(key: list) -> tuple:
    return (key[0], key[1], key[2] or '', key[3])


def _compared(row: dict) -> tuple:
    return (row['trigger_height'], row['effective_height']) + tuple(row[f] for f in ITEM3W_COUNTS[row['row']])


def _trigger(row: dict) -> dict:
    return {'trigger_gate': row['trigger_gate'], 'trigger_height': row['trigger_height']}


def item3w_compare(expected: dict, observed: dict) -> dict:
    """The W-row tool's lists (`wrows_observed`) against the generator's (`wrows_expected`)."""
    left = [(item3w_key(r), r) for r in observed['listed']]
    pairs, missing = [], []
    for row in expected['listed']:
        key = item3w_key(row)
        same = [i for i, (k, _) in enumerate(left) if k == key]
        if not same:
            missing.append(row)
            continue
        exact = [i for i in same if _compared(left[i][1]) == _compared(row)]
        pairs.append((row, left.pop((exact or same)[0])[1]))
    extra = [r for _, r in left]
    wrong_trigger = []
    for row in list(missing):
        for other in extra:
            if item3w_key(other)[:3] == item3w_key(row)[:3]:
                late = ((other['trigger_gate'], other['trigger_height']) > (row['trigger_gate'], row['trigger_height'])
                        if row['row'] in W_GATE_KEYED else other['trigger_height'] > row['trigger_height'])
                wrong_trigger.append({'row': row['row'], 'clustering': row['clustering'], 'cluster': row['cluster'],
                                      'expected': _trigger(row), 'reported': _trigger(other), 'late': late})
                missing.remove(row)
                extra.remove(other)
                break
    wrong_effective, wrong_counts, notes = [], [], []
    for row, other in pairs:
        key = list(item3w_key(row))
        if other['trigger_height'] != row['trigger_height']:
            wrong_trigger.append({'row': row['row'], 'clustering': row['clustering'], 'cluster': row['cluster'],
                                  'expected': _trigger(row), 'reported': _trigger(other),
                                  'late': other['trigger_height'] > row['trigger_height']})
        if other['effective_height'] != row['effective_height']:
            wrong_effective.append({'key': key, 'expected': row['effective_height'],
                                    'reported': other['effective_height']})
        differ = [f for f in ITEM3W_COUNTS[row['row']] if other[f] != row[f]]
        if differ:
            wrong_counts.append({'key': key, 'expected': {f: row[f] for f in differ},
                                 'reported': {f: other[f] for f in differ}})
        rest = [f for f in sorted(set(row) - {'trigger_height', 'effective_height'} - set(ITEM3W_COUNTS[row['row']]))
                if other.get(f) != row[f]]
        if rest:
            notes.append({'key': key, 'expected': {f: row[f] for f in rest},
                          'reported': {f: other.get(f) for f in rest}})
    status = {f: expected['data'][f] for f in ('state', 'pending_gates')}
    told = {f: observed['data'][f] for f in ('state', 'pending_gates')} if observed['data'] is not None else None
    later_expected = sorted((list(item3w_key(r)) for r in expected['not_yet_effective']), key=_key_order)
    later_observed = sorted((list(item3w_key(r)) for r in observed['not_yet_effective']), key=_key_order)
    return {'missing': [list(item3w_key(r)) for r in missing], 'extra': [list(item3w_key(r)) for r in extra],
            'wrong_trigger': wrong_trigger, 'wrong_effective': wrong_effective, 'wrong_counts': wrong_counts,
            'pending_data': None if told == status else {'expected': status, 'reported': told},
            'diagnostics': {'field_differences': notes[:SHOWN],
                            'not_yet_effective_agrees': later_expected == later_observed,
                            'not_yet_effective': {'expected': later_expected[:SHOWN],
                                                  'reported': later_observed[:SHOWN]}}}


def item3w_causes(comparison: dict) -> list[tuple[str, str]]:
    """(row, cause) for each difference: ITEM3W_REPORT_<MISSING|EXTRA|WRONG_TRIGGER|WRONG_EFFECTIVE|WRONG_COUNTS>:<row>
    (045b :1515), and ITEM3W_PENDING_DATA for the status."""
    found = [(key[0], 'ITEM3W_REPORT_MISSING:' + key[0]) for key in comparison['missing']]
    found += [(key[0], 'ITEM3W_REPORT_EXTRA:' + key[0]) for key in comparison['extra']]
    found += [(w['row'], 'ITEM3W_REPORT_WRONG_TRIGGER:' + w['row']) for w in comparison['wrong_trigger']]
    found += [(w['key'][0], 'ITEM3W_REPORT_WRONG_EFFECTIVE:' + w['key'][0]) for w in comparison['wrong_effective']]
    found += [(w['key'][0], 'ITEM3W_REPORT_WRONG_COUNTS:' + w['key'][0]) for w in comparison['wrong_counts']]
    if comparison['pending_data'] is not None:
        found.append(('W_PENDING_DATA', 'ITEM3W_PENDING_DATA'))
    return found


def item3w_rows(comparison: dict | None = None, plan_fields=(), malformed: str | None = None) -> dict:
    """One run's two rows (045b :1516-1517): `382` (item 3) and `503` (the section 4.5 repeat-winner row), each an
    outcome {result, nogo, not_established}. A plan field leaves the comparison not evaluated: both NOT_ESTABLISHED
    (:1516, :1578; QB-6 as A ruled: the W-row inputs that differ from the judge's classification are such a field, as in
    J1 and J6). Else a malformed output is NO-GO in both (QB-10). Else each difference is NO-GO in the row its family
    maps to (:1517); a row with none is GO for this run."""
    if plan_fields:
        return {row: {'result': 'NOT_ESTABLISHED', 'nogo': [],
                      'not_established': ['COMPARISON_NOT_EVALUATED:JUDGE_PLAN_MISMATCH']} for row in ('382', '503')}
    if malformed is not None:
        return {row: {'result': 'NO_GO', 'nogo': ['WROWS_OUTPUT_MALFORMED:' + malformed], 'not_established': []}
                for row in ('382', '503')}
    _spec(comparison is not None, 'a run with no comparison')
    causes = item3w_causes(comparison)
    out = {}
    for row in ('382', '503'):
        nogo = sorted({cause for kind, cause in causes if ITEM3W_ROW_OF[kind] == row})
        out[row] = {'result': 'NO_GO' if nogo else 'GO', 'nogo': nogo, 'not_established': []}
    return out


# ---------------------------------------------------------------------------------------------------------
# J3: the run list is every dispatch of the experiment (A's decision on the J3 check, P2-1; ARDR_JUDGE_V1 section 20).
# The workflow saves the claude-track-ardr.yml workflow_dispatch runs on main, every page, in its one GET-only token
# step; `experiment` refuses when a completed run of the experiment (its run-name `ardr <mode> <experiment>`, its head
# on the judge's first-parent main history, created at or after the bound) is not one of the listed runs.

def instant(value) -> datetime.datetime | None:
    """An ISO 8601 time with its offset (`...Z` or `...+hh:mm`), as an aware datetime; None for anything else."""
    if type(value) is not str or UTC_TIME.match(value) is None:
        return None
    try:
        return datetime.datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return None


def cli_run_query(args) -> dict:
    """J4b (section 16 P3-8): `run-query --mode M [--listed-after TIME]`, the query of the dispatch listing the token
    step saves: claude-track-ardr.yml's workflow_dispatch runs on main, 100 a page, and with a bound (CONFIRMATORY
    requires it, RUN_LIST_REQUIRED) only the runs created on or after the UTC date two days before it
    (`created=>=YYYY-MM-DD`, URL-encoded), so the 1,000-run cap (RUN_LIST_CAPPED) counts the runs near the campaign,
    not every dispatch of any experiment since the workflow began. The filter is a margin only: `experiment` applies
    the exact bound to the saved runs (section 20)."""
    if args.mode == 'CONFIRMATORY':
        need(args.listed_after is not None, 'RUN_LIST_REQUIRED', EXIT_PREREQUISITE)
    query = RUN_LIST_QUERY
    if args.listed_after is not None:
        bound = instant(args.listed_after)
        need(bound is not None, 'RUN_LIST_BOUND')
        try:
            day = (bound - RUN_LIST_MARGIN).astimezone(datetime.timezone.utc).date().isoformat()
        except OverflowError:   # a bound in the first two days of year 1 has no date two days before it
            raise Refusal('RUN_LIST_BOUND') from None
        query += '&created=%3E%3D' + day
    return {'query': query}


def cli_run_pages(args) -> dict:
    """`run-pages --dir D`: how many pages of 100 the saved listing has, from its first page (`D/runs-1.json`). A
    total of 1,000 or more is refused (RUN_LIST_CAPPED, exit 3): GitHub never lists the older runs then."""
    total = fetched(args.dir / 'runs-1.json').get('total_count')
    need(type(total) is int and total >= 0, 'RUN_LIST_SHAPE')
    need(total < RUN_LIST_CAP, 'RUN_LIST_CAPPED', EXIT_PREREQUISITE)
    return {'pages': max(1, -(-total // RUN_LIST_PAGE))}


def run_listing(folder: Path) -> list[dict]:
    """Every saved page (`runs-<p>.json`): one total on every page, every page but the last full, no run twice
    (RUN_LIST_CHANGED, exit 3: the listing moved while it was read), and every run's fields typed before any set is
    built from them (RUN_LIST_SHAPE, #655)."""
    pages = cli_run_pages(argparse.Namespace(dir=folder))['pages']
    total = fetched(folder / 'runs-1.json')['total_count']
    runs = []
    for page in range(1, pages + 1):
        doc = fetched(folder / f'runs-{page}.json')
        items = doc.get('workflow_runs')
        need(doc.get('total_count') == total and type(items) is list
             and len(items) == (RUN_LIST_PAGE if page < pages else total - RUN_LIST_PAGE * (pages - 1)),
             'RUN_LIST_CHANGED', EXIT_PREREQUISITE)
        runs += items
    need(all(type(x) is dict and type(x.get('id')) is int and x['id'] > 0
             and all(type(x.get(k)) is str for k in ('display_title', 'status', 'event', 'path', 'head_branch',
                                                     'head_sha'))
             and instant(x.get('created_at')) is not None for x in runs), 'RUN_LIST_SHAPE')
    need(len({x['id'] for x in runs}) == len(runs), 'RUN_LIST_CHANGED', EXIT_PREREQUISITE)
    return runs


def run_list_check(args, name: str, mode: str, listed: list[str]) -> dict | None:
    """The run list against the saved listing (section 20). A run of the experiment is a `workflow_dispatch` run of
    claude-track-ardr.yml on main named `ardr <mode> <experiment>` whose head is on the judge's first-parent main
    history (a tag `main` elsewhere is not one). Each listed run must be such a run and completed
    (RUN_LIST_DISAGREES); every such run created at or after the bound, completed or not, must be listed
    (RUN_LIST_INCOMPLETE). The bound is `--listed-after` (CONFIRMATORY, required: the earliest committer time among
    the commits that changed the presence of the registration's bytes; any offset, compared as a time),
    else the first listed run's creation. With `--listed-after` a listed run created before the bound is refused
    too (RUN_LIST_DISAGREES; the re-check's P2-A): the judged runs are then exactly the experiment's runs at or after
    the bound, and a bound set too late refuses instead of selecting. Every dispatch on main of the workflow must
    carry one of the campaign's run names (RUN_LIST_TITLE; P3-4). Returns the record's `inputs.run_list` (None when
    not checked)."""
    given = args.runs_listing is not None
    if mode == 'CONFIRMATORY':
        need(given and args.main_history is not None and args.listed_after is not None, 'RUN_LIST_REQUIRED',
             EXIT_PREREQUISITE)
    if not given:   # P3-6: a bound or a history without the listing it belongs to
        need(args.listed_after is None and args.main_history is None, 'RUN_LIST_REQUIRED', EXIT_PREREQUISITE)
        return None
    need(args.main_history is not None, 'RUN_LIST_REQUIRED', EXIT_PREREQUISITE)
    bound = instant(args.listed_after) if args.listed_after is not None else None
    need(args.listed_after is None or bound is not None, 'RUN_LIST_BOUND')
    runs = run_listing(args.runs_listing)
    history = main_history(args.main_history)
    dispatched = [x for x in runs
                  if x['event'] == 'workflow_dispatch' and x['path'] == ARDR_WORKFLOW and x['head_branch'] == 'main']
    for x in dispatched:
        named = CAMPAIGN_TITLE.match(x['display_title']) or RECOLLECT_TITLE.match(x['display_title'])
        need(named is not None and named.group(1) in EXPERIMENTS, 'RUN_LIST_TITLE', EXIT_REFUSAL)
    title = f'ardr {mode} {name}'
    ours = {str(x['id']): x for x in dispatched if x['display_title'] == title and x['head_sha'] in history}
    need(all(i in ours and ours[i]['status'] == 'completed' for i in listed), 'RUN_LIST_DISAGREES', EXIT_REFUSAL)
    need(bound is None or all(instant(ours[i]['created_at']) >= bound for i in listed), 'RUN_LIST_DISAGREES',
         EXIT_REFUSAL)
    source = 'LISTED_AFTER'
    if bound is None:
        bound, source = min(instant(ours[i]['created_at']) for i in listed), 'FIRST_LISTED_RUN'
    missing = sorted((int(i) for i, x in ours.items() if i not in listed and instant(x['created_at']) >= bound))
    if missing:
        sys.stderr.write('RUN_LIST_INCOMPLETE runs %s\n' % ','.join(map(str, missing[:SHOWN])))
    need(not missing, 'RUN_LIST_INCOMPLETE', EXIT_REFUSAL)
    return {'listing_runs': len(runs), 'experiment_runs': len(ours), 'bound': bound.isoformat(), 'bound_source': source,
            'checked_runs': sorted(int(i) for i in listed)}


# ---------------------------------------------------------------------------------------------------------
# J2: the judge workflow's reads (ARDR_JUDGE_V1 section 18). The workflow saves each Actions API answer and each
# artifact zip with GET requests only; these commands check each answer before the next request, then unpack the
# zips and bind every raw log to the collection: collection -> slice_record_sha256 -> slice record ->
# raw_log_sha256 -> raw-<run>.jsonl.

def fetched(path: Path) -> dict:
    return json_document(read_file(path, 'FETCHED', FETCHED_LIMIT), 'FETCHED')


def cli_run_ids(args) -> dict:
    ids = args.run_ids.split(',')
    need(0 < len(ids) <= RUN_IDS_MAX and all(RUN_ID.match(i) for i in ids) and len(set(ids)) == len(ids), 'RUN_IDS')
    return {'runs': ids}


def main_history(path: Path) -> set[str]:
    """The workflow's `git rev-list --first-parent "$GITHUB_SHA"` (the judge's own commit, which the workflow ran
    only from refs/heads/main): one 40-hex commit per line, LF-terminated, at least one."""
    blob = read_file(path, 'MAIN_HISTORY', MAIN_HISTORY_LIMIT)
    lines = blob.split(b'\n')
    need(len(lines) >= 2 and lines[-1] == b'' and all(OID.match(line.decode('ascii', 'replace'))
                                                      for line in lines[:-1]), 'MAIN_HISTORY_SHAPE')
    return {line.decode('ascii') for line in lines[:-1]}


def checked_listing(args) -> tuple[str, list[tuple[str, int, str | None]] | None]:
    """The saved run (`run.json`) must be a first-attempt, completed workflow_dispatch run of claude-track-ardr.yml on
    main named `ardr <mode> <experiment>` (its run-name; the experiment is ITEM1 unless J3's `--experiment`); the saved
    listing (`artifacts.json`, one page of at most 100) must name its declaration and collection once each, every slice
    artifact at most once, none expired and all of this run. Returns the run's head commit and (file stem, artifact id,
    listed `sha256:` digest or None).

    J4b (section 16 P3-2): a run whose listing names no declaration, no collection and no slice artifact declared
    nothing; it returns None for the downloads, and its attempt-1 jobs listing decides (`nothing_dispatched`). Such a
    run may be a later attempt in CONFIRMATORY only, where the campaign's plan refuses every attempt but the first
    (RUN_ATTEMPT_NOT_FIRST, before its declaration upload), so no later attempt can observe; in EXPLORATORY it must be
    the first attempt (a later one could plan and observe, and only a deleted declaration would hide it).

    A run's `head_branch` `main` is not proof that it ran main's commit: a dispatch on a tag named `main` lists the
    same way (as B's slices collector notes for recollections, in `prior_recollection`'s paragraph on a tag named
    `main`). So the run's `head_sha` must also be on the first-parent history of the judge's own commit
    (`--main-history`, ancestor or equal; RUN_NOT_ON_MAIN_HISTORY, exit 6), as the collector's S04 rule binds its
    run (`S04_NOT_ON_SLICE_HISTORY`, in `s04_run`). This binds the run to main only while main takes changes by
    merge commit alone: a fast-forward push or a rebase merge (GitHub's rebase merge, which main's ruleset allows
    today, adds each rewritten commit to main's first-parent line) puts commits main never pointed at on its
    first-parent history, so a tag `main` on one of them would pass. A tag ruleset refusing `refs/tags/main` (a
    repository setting, the Founder's) closes that gap."""
    need(RUN_ID.match(args.run_id) is not None, 'RUN_IDS')
    run = fetched(args.dir / 'run.json')
    attempt = run.get('run_attempt')
    need(str(run.get('id')) == args.run_id and run.get('path') == ARDR_WORKFLOW
         and run.get('event') == 'workflow_dispatch' and run.get('head_branch') == 'main'
         and run.get('status') == 'completed' and type(attempt) is int and attempt >= 1
         and run.get('display_title') == f'ardr {args.mode} {args.experiment}'
         and type(run.get('head_sha')) is str and OID.match(run['head_sha']) is not None, 'RUN_NOT_JUDGEABLE',
         EXIT_REFUSAL)
    need(run['head_sha'] in main_history(args.main_history), 'RUN_NOT_ON_MAIN_HISTORY', EXIT_REFUSAL)
    listing = fetched(args.dir / 'artifacts.json')
    artifacts = listing.get('artifacts')
    need(type(artifacts) is list and listing.get('total_count') == len(artifacts) and len(artifacts) < 100,
         'ARTIFACT_LISTING', EXIT_PREREQUISITE)
    found: dict[str, int] = {}
    for item in artifacts:
        need(type(item) is dict and type(item.get('name')) is str and type(item.get('id')) is int
             and item['id'] > 0 and item.get('expired') is False and type(item.get('workflow_run')) is dict
             and str(item['workflow_run'].get('id')) == args.run_id, 'ARTIFACT_LISTING', EXIT_PREREQUISITE)
        name, digest = item['name'], item.get('digest')
        need(digest is None or (type(digest) is str and digest.startswith('sha256:')
                                and HEX64.match(digest[7:]) is not None), 'ARTIFACT_LISTING', EXIT_PREREQUISITE)
        if name in ('ardr-declaration', 'ardr-collection') or SLICE_ARTIFACT.match(name):
            need(name not in found, 'ARTIFACT_LISTING', EXIT_PREREQUISITE)
            found[name] = (item['id'], digest[7:] if digest is not None else None)
    if not found:   # J4b: declared nothing; the attempt-1 jobs listing decides (a later attempt in CONFIRMATORY only)
        need(attempt == 1 or args.mode == 'CONFIRMATORY', 'RUN_NOT_JUDGEABLE', EXIT_REFUSAL)
        return run['head_sha'], None
    need(attempt == 1, 'RUN_NOT_JUDGEABLE', EXIT_REFUSAL)
    need('ardr-declaration' in found and 'ardr-collection' in found, 'RUN_COLLECTION_MISSING', EXIT_PREREQUISITE)
    slices = sorted((int(SLICE_ARTIFACT.match(n).group(1)), v) for n, v in found.items() if SLICE_ARTIFACT.match(n))
    out = [('declaration', *found['ardr-declaration']), ('collection', *found['ardr-collection'])]
    return run['head_sha'], out + [(f'slice-{n}', *v) for n, v in slices]


def step_ran(step: dict) -> bool:
    """A step may have run unless the jobs listing shows it not started (`queued`, `pending`, `waiting`) or
    `completed` `skipped`; any other status or conclusion counts as ran (fail closed; the collector's `step_ran`)."""
    status = step.get('status')
    return not (status in ('queued', 'pending', 'waiting')
                or (status == 'completed' and step.get('conclusion') == 'skipped'))


def nothing_dispatched(path: Path, run_id: str) -> str:
    """J4b (section 16 P3-2; B's `prior_declaration` rule, ARV1 section 13 D-1): the attempt-1 jobs listing
    (`jobs.json`, the token step's `GET actions/runs/<id>/attempts/1/jobs?per_page=100`) of a run that declared
    nothing shows that it dispatched nothing: the plan job is not listed or completed without success, and no other
    job ran a step (a step that may have run, `step_ran`). A unit runs only inside a slice job, which needs the plan;
    the collect job runs only after a successful plan; so every other job of such a run is skipped or never started.
    The rule is the collector's, made stricter: it reads every job, not only the slice jobs, and a job's steps whatever
    its `started_at`. The listing must be one page of every job (`total_count`), each of this run's attempt 1, each
    name once, with its steps (RUN_JOBS_LISTING, exit 3, as ARTIFACT_LISTING). A plan that succeeded (or is not done),
    or a job that ran a step, is RUN_COLLECTION_MISSING (exit 3): the run may have observed and is read only from its
    collection, as before J4b. Returns the listing's SHA-256."""
    blob = read_file(path, 'FETCHED', FETCHED_LIMIT)
    listing = json_document(blob, 'FETCHED')
    jobs = listing.get('jobs')
    need(type(jobs) is list and listing.get('total_count') == len(jobs) and len(jobs) <= JOBS_PAGE, 'RUN_JOBS_LISTING',
         EXIT_PREREQUISITE)
    names: set[str] = set()
    for job in jobs:
        need(type(job) is dict and type(job.get('name')) is str and job['name'] not in names
             and type(job.get('run_id')) is int and str(job['run_id']) == run_id and job.get('run_attempt') == 1
             and type(job.get('steps')) is list and all(type(step) is dict for step in job['steps']),
             'RUN_JOBS_LISTING', EXIT_PREREQUISITE)
        names.add(job['name'])
    plans = [job for job in jobs if job['name'] == PLAN_JOB_NAME]
    plan_failed = not plans or (plans[0].get('status') == 'completed'
                                and plans[0].get('conclusion') not in (None, 'success'))
    others_ran = any(step_ran(step) for job in jobs if job['name'] != PLAN_JOB_NAME for step in job['steps'])
    need(plan_failed and not others_ran, 'RUN_COLLECTION_MISSING', EXIT_PREREQUISITE)
    return sha256(blob)


def undeclared_run(folder: Path, mode: str, experiment: str, history: Path) -> dict:
    """J4b (section 16 P3-2): `experiment --undeclared-run D` re-checks one listed dispatch that declared nothing from
    the answers the token step saved in D (`run.json`, `artifacts.json`, `jobs.json`): `artifacts`' run checks, a
    listing with no declaration, collection or slice artifact (a run that declared something is given by its
    collection, RUN_DECLARED), and an attempt-1 jobs listing that shows it dispatched nothing (`nothing_dispatched`).
    Returns its run id and the three files' SHA-256 for the record."""
    run_id = fetched(folder / 'run.json').get('id')
    need(type(run_id) is int and RUN_ID.match(str(run_id)) is not None, 'RUN_NOT_JUDGEABLE', EXIT_REFUSAL)
    _, items = checked_listing(argparse.Namespace(dir=folder, run_id=str(run_id), mode=mode, experiment=experiment,
                                                  main_history=history))
    need(items is None, 'RUN_DECLARED')
    jobs = nothing_dispatched(folder / 'jobs.json', str(run_id))
    return {'run_id': str(run_id), 'run_sha256': sha256(read_file(folder / 'run.json', 'FETCHED', FETCHED_LIMIT)),
            'artifacts_sha256': sha256(read_file(folder / 'artifacts.json', 'FETCHED', FETCHED_LIMIT)),
            'jobs_sha256': jobs}


def cli_artifacts(args) -> dict:
    """The downloads of one checked run, `<file stem>:<artifact id>` (the zip is saved as `<file stem>.zip`). J4b: a
    run that declared nothing has none (`declared` false); the token step then saves its attempt-1 jobs listing."""
    head, items = checked_listing(args)
    return {'run_id': args.run_id, 'head_sha': head, 'declared': items is not None,
            'downloads': [f'{stem}:{i}' for stem, i, _ in items or []]}


def zip_digest(path: Path, digest: str | None) -> None:
    """A downloaded zip's SHA-256 must be the digest the server listed for it (when it lists one)."""
    if digest is not None and path.is_file():
        hasher = hashlib.sha256()
        with open(path, 'rb') as handle:
            for block in iter(lambda: handle.read(1 << 20), b''):
                hasher.update(block)
        need(hasher.hexdigest() == digest, 'ARTIFACT_DIGEST', EXIT_REFUSAL)


def zip_members(path: Path, allowed: dict[str, int]) -> zipfile.ZipFile:
    """One downloaded artifact zip whose members are all in `allowed` (name: byte limit), each once."""
    need(path.is_file() and not path.is_symlink(), 'ARTIFACT_MISSING', EXIT_PREREQUISITE)
    need(path.stat().st_size <= ZIP_LIMIT, 'ARTIFACT_ZIP')
    try:
        archive = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError):
        raise Refusal('ARTIFACT_ZIP') from None
    infos = [i for i in archive.infolist() if i.filename != STRAY_RECORD_TMP]
    names = [i.filename for i in archive.infolist()]
    ok = (len(set(names)) == len(names) and all(i.filename in allowed and i.file_size <= allowed[i.filename]
                                                for i in infos)
          and sum(i.file_size for i in infos) <= UNPACKED_LIMIT)
    if not ok:
        archive.close()
    need(ok, 'ARTIFACT_ZIP')
    return archive


def zip_read(archive: zipfile.ZipFile, name: str, limit: int, target: Path | None = None) -> tuple[bytes, str]:
    """A member's bytes (or, with `target`, written to that new file) and their SHA-256, read in bounded steps."""
    digest, size, parts = hashlib.sha256(), 0, []
    try:
        sink = open(target, 'xb') if target is not None else contextlib.nullcontext()   # entered (closed) below
        with sink as out, archive.open(name) as source:
            for block in iter(lambda: source.read(1 << 20), b''):
                size += len(block)
                need(size <= limit, 'ARTIFACT_ZIP')
                digest.update(block)
                if out is None:
                    parts.append(block)
                else:
                    out.write(block)
    except (KeyError, zipfile.BadZipFile, OSError):
        raise Refusal('ARTIFACT_ZIP') from None
    return b''.join(parts), digest.hexdigest()


def cli_unpack(args) -> dict:
    """The run's zips into `--out` (a new directory): `declaration.json`, `collection.json` and, for each slice
    whose units the collection binds to a slice record (`slice_record_sha256`), every raw log that record names,
    checked against its `raw_log_sha256`. Returns what the judge needs per run: the commit, the policy and method
    policy paths, and the run indexes with a raw log.

    J4b: ITEM2 and the item-4 experiments are read as POOL is (their declarations name no method policy, ARV1 section
    13); a run that declared nothing (`checked_listing`) is accepted only on its attempt-1 jobs listing
    (`nothing_dispatched`, `jobs.json` in `--dir`): the new empty directory O, `declared` false, no policy, no unit."""
    head_sha, items = checked_listing(args)
    if items is None:   # J4b (section 16 P3-2): no declaration, collection or slice; it must have dispatched nothing
        nothing_dispatched(args.dir / 'jobs.json', args.run_id)
        try:
            args.out.mkdir(mode=0o700, parents=True, exist_ok=False)
        except OSError:
            raise Refusal('OUTPUT_EXISTS', EXIT_PREREQUISITE) from None
        return {'run_id': args.run_id, 'commit': head_sha, 'declared': False, 'policy_path': None,
                'method_policy_path': None, 'units': []}
    head = {'head_sha': head_sha}
    for stem, _id, digest in items:
        zip_digest(args.dir / f'{stem}.zip', digest)
    with zip_members(args.dir / 'declaration.zip', {'declaration.json': POLICY_LIMIT}) as archive:
        blob, _ = zip_read(archive, 'declaration.json', POLICY_LIMIT)
    declaration = json_document(blob, 'FETCHED')
    run, slices, method = declaration.get('run'), declaration.get('slices'), declaration.get('method_policy')
    need(declaration.get('schema') == DECLARATION_SCHEMA and declaration.get('experiment') == args.experiment
         and declaration.get('mode') == args.mode and type(run) is dict and str(run.get('run_id')) == args.run_id
         and str(run.get('run_attempt')) == '1' and run.get('commit') == head['head_sha']
         and type(declaration.get('policy_path')) is str
         and (method is None or (type(method) is dict and type(method.get('path')) is str))
         and type(slices) is list and all(type(x) is dict and int_in(x.get('slice'), 1, 9999)
                                          and int_in(x.get('first'), 0, 9_999_999)
                                          and int_in(x.get('last'), x['first'], 9_999_999) for x in slices),
         'RUN_DECLARATION', EXIT_REFUSAL)
    # ITEM1 declares its method policy (required in CONFIRMATORY); J3: a POOL declaration names none (ARV1 13); J4b:
    # nor does an ITEM2 or item-4 one (the collector's `check_declaration`: a method policy is ITEM1's only).
    need(method is None if args.experiment != 'ITEM1' else args.mode == 'EXPLORATORY' or method is not None,
         'RUN_DECLARATION', EXIT_REFUSAL)
    with zip_members(args.dir / 'collection.zip', {'collection.json': COLLECTION_LIMIT}) as archive:
        blob_c, _ = zip_read(archive, 'collection.json', COLLECTION_LIMIT)
    collection = json_document(blob_c, 'FETCHED')
    # #655: each unit's `slice_record_sha256` is null or 64 lowercase hex before any set is built from it.
    need(collection.get('schema') == COLLECTION_SCHEMA and type(collection.get('units')) is list
         and all(type(u) is dict and (u.get('slice_record_sha256') is None
                                      or (type(u['slice_record_sha256']) is str
                                          and HEX64.match(u['slice_record_sha256']) is not None))
                 for u in collection['units']), 'COLLECTION_SHAPE')
    # P3-4 (J3 check): the collection's own run is this dispatch's (run id, attempt 1, the run's head), as the
    # declaration's is; a collection of another run is a binding refusal.
    named = collection.get('run')
    need(type(named) is dict and str(named.get('run_id')) == args.run_id and str(named.get('run_attempt')) == '1'
         and named.get('commit') == head['head_sha'], 'COLLECTION_RUN', EXIT_REFUSAL)
    try:
        args.out.mkdir(mode=0o700, parents=True, exist_ok=False)
    except OSError:
        raise Refusal('OUTPUT_EXISTS', EXIT_PREREQUISITE) from None
    (args.out / 'declaration.json').write_bytes(blob)
    (args.out / 'collection.json').write_bytes(blob_c)
    units = []
    for spec in slices:
        digests = {u.get('slice_record_sha256') for u in collection['units'] if u.get('slice') == spec['slice']}
        digests.discard(None)
        if not digests:   # no slice record was collected for this slice: no raw log to judge from it
            continue
        need(len(digests) == 1, 'SLICE_RECORD_SHA256', EXIT_REFUSAL)
        runs = range(spec['first'], spec['last'] + 1)
        allowed = {'slice-record.json': SLICE_RECORD_LIMIT}
        allowed.update((f'raw-{r}.jsonl', RAW_LIMIT) for r in runs)
        with zip_members(args.dir / f'slice-{spec["slice"]}.zip', allowed) as archive:
            record_blob, digest = zip_read(archive, 'slice-record.json', SLICE_RECORD_LIMIT)
            need(digest in digests, 'SLICE_RECORD_SHA256', EXIT_REFUSAL)
            record = json_document(record_blob, 'FETCHED')
            entries = record.get('units')
            need(type(entries) is list and all(type(e) is dict and type(e.get('unit')) is dict for e in entries)
                 and [e['unit'].get('run') for e in entries] == list(runs), 'SLICE_RECORD_SHA256', EXIT_REFUSAL)
            names = {i.filename for i in archive.infolist()}
            for entry in entries:
                expected = entry.get('raw_log_sha256')
                if expected is None:
                    continue
                name = f'raw-{entry["unit"]["run"]}.jsonl'
                need(entry.get('raw_log') == name and name in names, 'RAW_LOG_MISSING', EXIT_PREREQUISITE)
                _, digest = zip_read(archive, name, RAW_LIMIT, args.out / name)
                need(digest == expected, 'RAW_LOG_SHA256', EXIT_REFUSAL)
                units.append(entry['unit']['run'])
    return {'run_id': args.run_id, 'commit': head['head_sha'], 'declared': True,
            'policy_path': declaration['policy_path'],
            'method_policy_path': method['path'] if method is not None else None, 'units': sorted(units)}


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="A's ARDR judge (CT-P5-001 J1-J5: item 1, the pool run, the 10% rule "
                                            'across dispatches, item 2 and the section 4.5 rows, item 4). Prints one '
                                            'judgement record.')
    sub = p.add_subparsers(dest='command', required=True)
    one = sub.add_parser('item1', help='judge one ITEM1 run from its raw log')
    one.add_argument('--policy', type=Path, required=True)
    one.add_argument('--method-policy', type=Path, required=True)
    one.add_argument('--raw', type=Path, required=True)
    one.add_argument('--collection', type=Path)
    one.add_argument('--registration', type=Path)
    one.add_argument('--prereg', type=Path, default=PREREG_DEFAULT, help='the 045b file (default: the tree copy)')
    one.add_argument('--mode', choices=('EXPLORATORY', 'CONFIRMATORY'), required=True)
    one.add_argument('--no-replay', action='store_true',
                     help='EXPLORATORY only: judge without the Core replay (births UNVERIFIED_NO_REPLAY)')
    one.add_argument('--replay-bin', type=Path,
                     help='the prebuilt ardr_judge_replay test binary (default: cargo builds and runs it)')
    one.add_argument('--d2-2-tool-at-commit', type=Path,
                     help="the D2-2 file's bytes at the judged run's commit (the workflow's `git show`)")
    one_pool = sub.add_parser('pool', help='J3: judge one POOL run from its raw log (per-run description)')
    one_pool.add_argument('--policy', type=Path, required=True)
    one_pool.add_argument('--raw', type=Path, required=True)
    one_pool.add_argument('--collection', type=Path)
    one_pool.add_argument('--registration', type=Path)
    one_pool.add_argument('--prereg', type=Path, default=PREREG_DEFAULT, help='the 045b file (default: the tree copy)')
    one_pool.add_argument('--mode', choices=('EXPLORATORY', 'CONFIRMATORY'), required=True)
    one_pool.add_argument('--no-replay', action='store_true',
                          help='EXPLORATORY only: judge without the Core replay (births UNVERIFIED_NO_REPLAY)')
    one_pool.add_argument('--replay-bin', type=Path,
                          help='the prebuilt ardr_judge_replay test binary (default: cargo builds and runs it)')
    one_item2 = sub.add_parser('item2', help='J4a: judge one ITEM2 run from its raw log (per-run description)')
    one_item2.add_argument('--policy', type=Path, required=True)
    one_item2.add_argument('--raw', type=Path, required=True)
    one_item2.add_argument('--collection', type=Path)
    one_item2.add_argument('--registration', type=Path)
    one_item2.add_argument('--prereg', type=Path, default=PREREG_DEFAULT, help='the 045b file (default: the tree copy)')
    one_item2.add_argument('--mode', choices=('EXPLORATORY', 'CONFIRMATORY'), required=True)
    one_item2.add_argument('--no-replay', action='store_true',
                           help='EXPLORATORY only: judge without the Core replay (births UNVERIFIED_NO_REPLAY)')
    one_item2.add_argument('--replay-bin', type=Path,
                           help='the prebuilt ardr_judge_replay test binary (default: cargo builds and runs it)')
    one_item4 = sub.add_parser('item4', help='J5: judge one item-4 run from its raw log (per-run description)')
    one_item4.add_argument('--policy', type=Path, required=True)
    one_item4.add_argument('--raw', type=Path, required=True)
    one_item4.add_argument('--collection', type=Path)
    one_item4.add_argument('--registration', type=Path)
    one_item4.add_argument('--prereg', type=Path, default=PREREG_DEFAULT, help='the 045b file (default: the tree copy)')
    one_item4.add_argument('--mode', choices=('EXPLORATORY', 'CONFIRMATORY'), required=True)
    one_item4.add_argument('--no-replay', action='store_true',
                           help='EXPLORATORY only: judge without the Core replay (births UNVERIFIED_NO_REPLAY)')
    one_item4.add_argument('--replay-bin', type=Path,
                           help='the prebuilt ardr_judge_replay test binary (default: cargo builds and runs it)')
    whole = sub.add_parser('experiment', help='J3: the 10%% rule across dispatches (and the pool index); J4a: item 2 '
                                              'and the section 4.5 rows; J5: one item-4 sub-scenario')
    whole.add_argument('--experiment', choices=('ITEM1', 'POOL', 'ITEM2') + ITEM4_SCENARIOS, required=True)
    whole.add_argument('--policy', type=Path, required=True)
    whole.add_argument('--mode', choices=('EXPLORATORY', 'CONFIRMATORY'), required=True)
    whole.add_argument('--registration', type=Path)
    whole.add_argument('--prereg', type=Path, default=PREREG_DEFAULT, help='the 045b file (default: the tree copy)')
    whole.add_argument('--collection', type=Path, action='append', required=True,
                       help='one listed dispatch run\'s collection (repeat per run)')
    whole.add_argument('--record', type=Path, action='append', default=[],
                       help='this judge\'s record of one unit with a raw log (repeat per unit)')
    whole.add_argument('--runs-listing', type=Path,
                       help='the saved claude-track-ardr dispatch listing (runs-<page>.json); CONFIRMATORY needs it')
    whole.add_argument('--main-history', type=Path,
                       help='`git rev-list --first-parent` of the judge\'s own main commit, one per line')
    whole.add_argument('--listed-after', help='ISO time: every run of the experiment created at or after it must be '
                                              'listed, and a listed run created before it is refused (CONFIRMATORY: '
                                              'the earliest committer time of the registration\'s bytes)')
    whole.add_argument('--undeclared-run', type=Path, action='append', default=[],
                       help='J4b: the saved run.json, artifacts.json and jobs.json of one listed dispatch that '
                            'declared nothing (repeat per run; needs --runs-listing)')
    outcome = sub.add_parser('item4-outcome', help="J5: item 4's outcome from the four sub-scenario records")
    outcome.add_argument('--mode', choices=('EXPLORATORY', 'CONFIRMATORY'), required=True)
    outcome.add_argument('--record', type=Path, action='append', default=[],
                         help="one `experiment --experiment ITEM4_<S>` record (repeat, at most one per sub-scenario)")
    outcome.add_argument('--prereg', type=Path, default=PREREG_DEFAULT, help='the 045b file (default: the tree copy)')
    pages = sub.add_parser('run-pages', help='workflow: the number of pages of the saved dispatch listing')
    pages.add_argument('--dir', type=Path, required=True)
    query = sub.add_parser('run-query', help="workflow (J4b): the dispatch listing's query (CONFIRMATORY: created on "
                                             'or after two days before the bound)')
    query.add_argument('--mode', choices=('EXPLORATORY', 'CONFIRMATORY'), required=True)
    query.add_argument('--listed-after', help='ISO time: the bound (CONFIRMATORY requires it)')
    ids = sub.add_parser('run-ids', help='workflow: check the comma-separated run ids')
    ids.add_argument('--run-ids', required=True)
    for name, text in (('artifacts', 'workflow: check a saved run and its artifact listing; name the downloads'),
                       ('unpack', 'workflow: unpack and bind the downloaded zips of one run')):
        one_run = sub.add_parser(name, help=text)
        one_run.add_argument('--dir', type=Path, required=True)
        one_run.add_argument('--run-id', required=True)
        one_run.add_argument('--mode', choices=('EXPLORATORY', 'CONFIRMATORY'), required=True)
        one_run.add_argument('--experiment', choices=WORKFLOW_EXPERIMENTS, default='ITEM1',
                             help='J3, J4b: the experiment the run dispatched (default ITEM1)')
        one_run.add_argument('--main-history', type=Path, required=True,
                             help='`git rev-list --first-parent` of the judge\'s own main commit, one per line')
        if name == 'unpack':
            one_run.add_argument('--out', type=Path, required=True)
    return p


def lf_stdout() -> None:
    """The record and the refusal line end in one LF on every platform (section 2; #650, Desktop P3). A text
    stdout that would turn '\\n' into the platform's line end (CRLF on native Windows) is set to write it
    unchanged. The text layer stays, so a failed write still ends with exit 4 (claude_track_exit)."""
    reconfigure = getattr(sys.stdout, 'reconfigure', None)
    if reconfigure is not None:
        reconfigure(newline='\n')


def main(argv: list[str] | None = None) -> int:
    lf_stdout()
    if sys.flags.optimize or not __debug__:
        print(json.dumps({'code': 'OPTIMIZED_PYTHON', 'exit': EXIT_REFUSAL, 'result': 'FAIL'}, sort_keys=True))
        return EXIT_REFUSAL
    args = parser().parse_args(argv)
    command = {'item1': item1, 'pool': pool, 'item2': item2, 'item4': item4, 'experiment': experiment,
               'item4-outcome': item4_outcome, 'run-pages': cli_run_pages, 'run-query': cli_run_query,
               'run-ids': cli_run_ids,
               'artifacts': cli_artifacts, 'unpack': cli_unpack}
    try:
        record = command[args.command](args)
    except Refusal as refusal:
        print(json.dumps({'code': refusal.code, 'exit': refusal.exit_code, 'result': 'FAIL'}, sort_keys=True))
        return refusal.exit_code
    sys.stdout.write(canonical(record).decode('ascii') + '\n')
    return EXIT_DONE


if __name__ == '__main__':
    import claude_track_exit
    claude_track_exit.run(main)
