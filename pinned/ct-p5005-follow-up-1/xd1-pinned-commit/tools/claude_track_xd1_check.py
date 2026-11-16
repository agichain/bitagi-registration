"""XD-1 event-chain checker: the per-run XD-1 values from the raw event chains (CT-P3-044c-1 1e-4a, 1e-4b-1).

Class T EXPLORATORY development evidence, not S17-PREP. The checker reads one declaration, exactly the N run
records it declares (`run-<i>.json`, i = 1..N) and one T4-2 record per slice (`t42-slice-<k>.json`), never
a directory listing, and writes one report (format: docs/claude-track/formats/XD1_EVENT_CHAIN_V1.md, or
XD1_EVENT_CHAIN_V2.md for a V2 declaration: the driver's records, with the H0 - 1 hash reads, the H of each
prestate comparison and both nodes' fee and vsize; 1e-4b-1, B #258 issuecomment-6418049931, A -6419729708).

Source: docs/claude-track/plans/CT-P3-044C1_1E_PREP_EN.md section 4.5 (Events, Order, Checker, Per-run cap,
N and slices, Labels) and section 8 T4-1 to T4-7; B's unit draft #258 issuecomment-6204590999 and A's
confirmation issuecomment-6207467677. It is written apart from the host being timed and reads no node.

  check --declaration FILE --records DIR --output FILE

Every declared run has a row. A run whose record is missing, invalid or bound to another run, or whose chain
fails a check, has T = infinity (null values, an `infinite_reason` and its `failed_checks`); it is never dropped.
Q9 is decided (045b :1200): `METRIC` is 045B, so T_045b decides and T_plan and T_bound are still reported;
the UNDECIDED (the largest) and PLAN branches are reachable only through build_report()'s argument (no CLI
flag; A, item 3).

V3 (docs/claude-track/formats/XD1_EVENT_CHAIN_V3.md; the live-decision sessions of the XD-1 confirmatory
harness, A's decisions XA1-XA13 of 2026-11-10): a V3 declaration names one session (`first_run` .. `last_run`,
at most SESSION_RUNS) of a CONFIRMATORY or a live-decision EXPLORATORY collection; the checker reads exactly
that session's run records and its T4-2 record `t42-slice-<first_run>.json`, checks each mode's labels both
ways (XA5), and refuses a record whose `registration_sha256` is not the declaration's. `verdict` (XA8) and
`observation_list` (XA9) are the collection-level functions the hosted report job
(`claude_track_xd1_confirm.py`) calls over every counted session; V1 and V2 behave as before.

Exit codes: 0 written, or the same bytes already there; 2 refused (declaration, labels, registration, output
with other bytes); 3 the declaration file or records directory is missing; 4 internal error or output not
written; 5 under -O. A refusal writes no report. Stdlib only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
from pathlib import Path

FORMAT_DECLARATION = 'BITAGI_CT_XD1_DECLARATION_V1'
FORMAT_RUN = 'BITAGI_CT_XD1_RUN_V1'
FORMAT_T42 = 'BITAGI_CT_XD1_T42_V1'
FORMAT_REPORT = 'BITAGI_CT_XD1_REPORT_V1'
FORMAT_DECLARATION_V2 = 'BITAGI_CT_XD1_DECLARATION_V2'
FORMAT_RUN_V2 = 'BITAGI_CT_XD1_RUN_V2'
FORMAT_REPORT_V2 = 'BITAGI_CT_XD1_REPORT_V2'
VERSIONS = {FORMAT_DECLARATION: 1, FORMAT_DECLARATION_V2: 2}
# V3 (XD1_EVENT_CHAIN_V3.md): one live-decision session of a CONFIRMATORY or EXPLORATORY collection.
FORMAT_DECLARATION_V3 = 'BITAGI_CT_XD1_DECLARATION_V3'
FORMAT_RUN_V3 = 'BITAGI_CT_XD1_RUN_V3'
FORMAT_REPORT_V3 = 'BITAGI_CT_XD1_REPORT_V3'
FORMAT_COLLECTION_V3 = 'BITAGI_CT_XD1_COLLECTION_REPORT_V3'
FORMAT_MARKER_V3 = 'BITAGI_CT_XD1_SESSION_MARKER_V3'
OBSERVATION_SCHEMA = 'BITAGI_CT_OBSERVATION_LIST_V1'   # ct_preregistration_receipt.OBSERVATION_SCHEMA (XA9)

# 1E Q9 is decided (045b :1200, A #664 issuecomment-6738913955; B-FZ-a FZ-5): T_045b decides, S0 to the last
# submission attempt's return on both nodes; T_bound is still reported on every row. Not a CLI flag (A, item 3).
METRIC = '045B'
METRICS = ('UNDECIDED', 'PLAN', '045B')

MAX_XD1_RUNS = 20           # 1E section 4.5 N and slices
SLICE_RUNS = 10             # runs per slice job
MAX_TIMESTAMP_EVENTS = 35   # 28 base events, at most three attempts per node, at most one ACK
MAX_ATTEMPTS = 3
XD1_RUN_CAP_NS = 900 * 10**9
RECORD_LIMIT = 64 * 1024    # bytes per declaration, run record or T4-2 record
SESSION_RUNS = 5            # V3: a session is 1 to 5 consecutive runs (045b :1099; XA1)

REQUIRED_LABELS = ('CLASS_T', 'CLASS_T_DEVELOPMENT_EVIDENCE_NOT_S17_PREP', 'DECISION_SCRIPTED_TEST_ONLY',
                   'EXPLORATORY', 'REGTEST', 'TEST_ONLY_PRIVATE_SCALAR_KNOWN')
FORBIDDEN_LABEL = 'CONFIRMATORY'
TRANSFERABILITY = ('Hosted runners, small Regtest blocks and a scripted decision do not transfer to the '
                   'mainnet hosts.')
# V3 (XA5): each mode's labels, the bytes that refuse a report of that mode (anti-relabel both ways), and one
# transferability statement for both live-decision modes.
MODES_V3 = ('CONFIRMATORY', 'EXPLORATORY')
LABELS_V3 = {
    'CONFIRMATORY': ('CLASS_T', 'CONFIRMATORY', 'DECISION_LIVE_FOUNDER_VPS_CONSOLE', 'REGTEST',
                     'S17_PREP_EVIDENCE_CLASS_T', 'TEST_ONLY_PRIVATE_SCALAR_KNOWN'),
    'EXPLORATORY': ('CLASS_T', 'CLASS_T_DEVELOPMENT_EVIDENCE_NOT_S17_PREP', 'DECISION_LIVE_FOUNDER_VPS_CONSOLE',
                    'EXPLORATORY', 'REGTEST', 'TEST_ONLY_PRIVATE_SCALAR_KNOWN'),
}
FORBIDDEN_V3 = {'CONFIRMATORY': (b'EXPLORATORY', b'DECISION_SCRIPTED_TEST_ONLY'), 'EXPLORATORY': (b'CONFIRMATORY',)}
TRANSFERABILITY_V3 = 'Small Regtest blocks, a VPS and a Regtest live decision do not transfer to the mainnet hosts.'
DECISIONS = ('BROADCAST', 'REFUSED', 'NONE')
# XA8: the criterion (045b :564-569, :610-617): p95 of T_045b <= 420 s by nearest rank over N = 20, each duration
# rounded up to whole seconds, T = infinity sorting last.
CRITERION_S = 420
VERDICT_N = MAX_XD1_RUNS
P95, P50 = 95, 50
INCONCLUSIVE_REASONS = ('DECLARATION_REFUSED', 'REGISTRATION_MISMATCH', 'COMPLETENESS_REFUSED', 'LABELS_REFUSED',
                        'FEWER_THAN_20_RUNS')
OBSERVATION_PREFIX = 9      # XA9: OBS-9<run_index:07>; ARDR uses 1..8 (claude_track_ardr_slices.EXPERIMENTS)
# X10 / 045b :1098: the environment row's fixed parts. NODE_VERSIONS_TEXT is the driver's oe.NODE_VERSIONS.
NODE_VERSIONS_TEXT = ('31.1', '30.3')
ENVIRONMENT_HOST = 'SELF_HOSTED_VPS'
ENVIRONMENT_CR21 = 'FD-CT-92 item 15 (2026-10-27)'
ENVIRONMENT_3R_L = '#545 198424fe'

STEPS = tuple(range(1, 11))
BASE_EVENTS = (('S0', 'S1', 'S2') + tuple(f'STEP_{k}_{edge}' for k in STEPS for edge in ('START', 'END'))
               + ('D0', 'D1', 'O_A', 'O_B', 'I'))
NODES = ('A', 'B')
ATTEMPT = re.compile(r'B_([AB])_([1-9][0-9]?)')
OUTCOMES = ('ACCEPTED', 'REJECTED', 'TIMED_OUT')
STOP_REASONS = ('RUN_CAP', 'COMPARATOR_UNAVAILABLE', 'DRIVER_EXIT')
STOP_REASONS_V2 = STOP_REASONS + ('H0_MINUS_1_CHANGED',)
STOP_REASONS_V3 = STOP_REASONS_V2 + ('DECISION_REFUSED',)
READ_POINTS = ('S1', 'S2', 'RUN_END')   # V2: when the driver reads getblockhash(H0 - 1) on both nodes
MAX_PRESTATE_CALLS = 4
HASH64 = re.compile(r'[0-9a-f]{64}')
T42_RESULTS = ('PASS', 'FAIL')
HEX40 = re.compile(r'[0-9a-f]{40}')

# Chain checks, in report order. Any of them gives T = infinity.
STRUCTURE_CHECKS = ('BASE_EVENT_MISSING', 'EVENT_DUPLICATED', 'ACK_DUPLICATED', 'FIRST_ATTEMPT_MISSING',
                    'ATTEMPT_GAP', 'ATTEMPT_OVER_LIMIT', 'CLOCK_REGRESSION', 'RUN_CAP_EXCEEDED',
                    'EVENT_OUTSIDE_RUN', 'STOP_REASON')
EDGE_CHECKS = ('S0_LE_S1', 'S0_LE_S2', 'S1_LE_I', 'S2_LE_STEP1_START', 'STEP_START_LE_END',
               'STEP_END_LE_NEXT_START', 'D0_LE_D1', 'D1_LE_EVERY_B', 'STEP9_END_LE_D0',
               'STEP10_START_LE_EVERY_B', 'EVERY_O_LE_STEP10_END', 'ATTEMPTS_IN_ORDER', 'ATTEMPT_LE_ITS_O',
               'EVERY_B_LE_I', 'EVERY_O_LE_I', 'S2_LE_ACK', 'ACK_LT_STEP1_START')
CHECKS = STRUCTURE_CHECKS + EDGE_CHECKS
# V2 only: a fact the driver did not read, the two nodes' vsizes differing, H0 - 1 changing within the run.
V2_CHECKS = ('RUN_FACT_UNREAD', 'CANDIDATE_VSIZE_DISAGREES', 'H0_MINUS_1_CHANGED')
CHECKS_V2 = STRUCTURE_CHECKS + V2_CHECKS + EDGE_CHECKS
# V3 only: the run's live decision was not BROADCAST (XA2).
V3_CHECKS = ('DECISION_NOT_BROADCAST',)
CHECKS_V3 = STRUCTURE_CHECKS + V2_CHECKS + V3_CHECKS + EDGE_CHECKS


class Refusal(Exception):
    """No report: `code` is the exit code, `str()` the failure label."""

    def __init__(self, code, label):
        super().__init__(label)
        self.code = code


class Invalid(Exception):
    """One record is unusable: its row has T = infinity with RECORD_INVALID."""


# ------------------------------------------------------------------------------------------- reading ----
def _no_duplicates(pairs):
    keys = [k for k, _ in pairs]
    if len(keys) != len(set(keys)):
        raise Invalid('DUPLICATE_KEY')
    return dict(pairs)


def _no_float(text):
    raise Invalid('FLOAT')


def _no_constant(text):
    raise Invalid('CONSTANT')


def read_bounded(path, limit=RECORD_LIMIT):
    """The bytes of a regular file of at most `limit` bytes, its last component not a link; None if absent.
    Anything else (a link, a directory, a device, too large, unreadable) is Invalid."""
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise Invalid('UNREADABLE') from exc
    if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
        raise Invalid('NOT_A_BOUNDED_FILE')
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, 'O_NONBLOCK', 0))
    except OSError as exc:
        raise Invalid('UNREADABLE') from exc
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise Invalid('NOT_A_BOUNDED_FILE')
        raw = os.read(fd, limit + 1)
    finally:
        os.close(fd)
    if len(raw) > limit:
        raise Invalid('NOT_A_BOUNDED_FILE')
    return raw


def parse(raw):
    """A JSON object with no duplicate key, no float and no NaN or Infinity; anything else is Invalid."""
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=_no_duplicates, parse_float=_no_float,
                           parse_constant=_no_constant)
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise Invalid('JSON') from exc
    if type(value) is not dict:
        raise Invalid('NOT_AN_OBJECT')
    return value


def is_int(value, low=0):
    return type(value) is int and value >= low


def need(condition):
    if not condition:
        raise Invalid('SCHEMA')


# --------------------------------------------------------------------------------------- declaration ----
def read_declaration(path):
    try:
        raw = read_bounded(path)
    except Invalid as exc:
        raise Refusal(2, 'DECLARATION_INVALID') from exc
    if raw is None:
        raise Refusal(3, 'DECLARATION_MISSING')
    try:
        value = parse(raw)
        if value.get('format') == FORMAT_DECLARATION_V3:
            return declaration_v3(value)
        need(set(value) == {'format', 'n', 'head_sha', 'run_id', 'run_attempt'})
        need(value['format'] in VERSIONS and is_int(value['n']))
        need(type(value['head_sha']) is str and HEX40.fullmatch(value['head_sha']))
        need(is_int(value['run_id'], 1) and is_int(value['run_attempt'], 1))
    except Invalid as exc:
        raise Refusal(2, 'DECLARATION_INVALID') from exc
    if not 1 <= value['n'] <= MAX_XD1_RUNS:
        raise Refusal(2, 'DECLARATION_N')
    return value


def declaration_v3(value):
    """A V3 declaration (one session): its closed keys, its mode's registration rule and the session bounds."""
    keys = {'format', 'mode', 'n', 'first_run', 'last_run', 'head_sha', 'run_id', 'run_attempt',
            'registration_sha256'}
    try:
        need(set(value) == keys and value['mode'] in MODES_V3)
        need(all(is_int(value[k], 1) for k in ('n', 'first_run', 'last_run', 'run_id', 'run_attempt')))
        need(type(value['head_sha']) is str and HEX40.fullmatch(value['head_sha']))
        if value['mode'] == 'CONFIRMATORY':
            need(is_hash(value['registration_sha256']))
        else:
            need(value['registration_sha256'] is None)
    except Invalid as exc:
        raise Refusal(2, 'DECLARATION_INVALID') from exc
    # CONFIRMATORY: N is fixed at 20 (045b :603-609); an EXPLORATORY pilot is one session from run 1 (XA7).
    n_ok = value['n'] == MAX_XD1_RUNS if value['mode'] == 'CONFIRMATORY' else value['n'] <= SESSION_RUNS
    if not n_ok:
        raise Refusal(2, 'DECLARATION_N')
    first, last = value['first_run'], value['last_run']
    if not (first <= last <= value['n'] and last - first < SESSION_RUNS) or (
            value['mode'] == 'EXPLORATORY' and (first, last) != (1, value['n'])):
        raise Refusal(2, 'DECLARATION_SESSION')
    return value


def version_of(declaration):
    return 3 if declaration['format'] == FORMAT_DECLARATION_V3 else VERSIONS[declaration['format']]


def slice_of(index):
    return (index - 1) // SLICE_RUNS + 1


# ------------------------------------------------------------------------------------------- records ----
def _label_pairs(pairs):
    names = [k for k, _ in pairs]
    if any(names.count(k) > 1 for k in ('labels', 'transferability')):
        raise ValueError('ambiguous labels')
    return dict(pairs)


def labels_refused(raw):
    """Whether a readable record refuses the whole report (A, item 4): CONFIRMATORY anywhere in its bytes, or
    labels that cannot be confirmed as exactly the required set with the transferability statement. The labels
    are read with a lenient parse (floats and other duplicate keys allowed), so a record that fails the strict
    schema only for another reason still has its labels checked; one whose labels cannot be read at all (not
    UTF-8 JSON, not an object, a repeated `labels` key) counts as unlabelled."""
    if FORBIDDEN_LABEL.encode() in raw:
        return True
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=_label_pairs)
    except (UnicodeDecodeError, ValueError, RecursionError):
        return True
    if type(value) is not dict:
        return True
    labels = value.get('labels')
    if type(labels) is not list or not all(type(x) is str for x in labels) or len(labels) != len(set(labels)):
        return True
    return set(labels) != set(REQUIRED_LABELS) or value.get('transferability') != TRANSFERABILITY


def labels_refused_v3(raw, mode):
    """V3 (XA5): the record refuses the whole report when its bytes hold another mode's label (CONFIRMATORY in an
    EXPLORATORY session; EXPLORATORY or DECISION_SCRIPTED_TEST_ONLY in a CONFIRMATORY one), or its labels cannot
    be confirmed as exactly the mode's set with the V3 transferability statement (read as V1 section 3 reads
    them)."""
    if any(word in raw for word in FORBIDDEN_V3[mode]):
        return True
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=_label_pairs)
    except (UnicodeDecodeError, ValueError, RecursionError):
        return True
    if type(value) is not dict:
        return True
    labels = value.get('labels')
    if type(labels) is not list or not all(type(x) is str for x in labels) or len(labels) != len(set(labels)):
        return True
    return set(labels) != set(LABELS_V3[mode]) or value.get('transferability') != TRANSFERABILITY_V3


def per_node(value, check):
    """{"A": v, "B": v}, each v None (V2: not read) or passing `check`."""
    return type(value) is dict and set(value) == set(NODES) and all(v is None or check(v) for v in value.values())


def is_hash(value):
    return type(value) is str and HASH64.fullmatch(value) is not None


def validate_run(value, version=1):
    """A run record's closed schema; Invalid if anything is outside it."""
    keys = {'format', 'run_index', 'run_id', 'run_attempt', 'head_sha', 'labels', 'transferability',
            'incrementalfee_sat_per_kvb', 'candidate_vsize', 'events', 'run_start_ns', 'run_end_ns'}
    if version >= 2:
        keys |= {'h0_minus_1_height', 'h0_minus_1_reads', 'prestate_calls'}
    if version == 3:
        keys |= {'mode', 'registration_sha256', 'decision'}
    need(set(value) in (keys, keys | {'stop_reason'}))
    need(value['format'] == {1: FORMAT_RUN, 2: FORMAT_RUN_V2, 3: FORMAT_RUN_V3}[version])
    if version == 3:
        need(value['mode'] in MODES_V3 and value['decision'] in DECISIONS)
        need(value['registration_sha256'] is None or is_hash(value['registration_sha256']))
    need(is_int(value['run_index'], 1) and is_int(value['run_id'], 1) and is_int(value['run_attempt'], 1))
    need(type(value['head_sha']) is str and HEX40.fullmatch(value['head_sha']))
    fee = value['incrementalfee_sat_per_kvb']
    if version == 1:
        need(type(fee) is dict and set(fee) == set(NODES) and all(is_int(fee[n]) for n in NODES))
        need(is_int(value['candidate_vsize'], 1))
    else:
        need(per_node(fee, is_int) and per_node(value['candidate_vsize'], lambda v: is_int(v, 1)))
        need(is_int(value['h0_minus_1_height'], 1))
        reads = value['h0_minus_1_reads']
        need(type(reads) is list and len(reads) == len(READ_POINTS))
        for at, read in zip(READ_POINTS, reads):
            need(type(read) is dict and set(read) == {'at', *NODES} and read['at'] == at)
            need(per_node({n: read[n] for n in NODES}, is_hash))
        calls = value['prestate_calls']
        need(type(calls) is list and len(calls) <= MAX_PRESTATE_CALLS)
        for call in calls:
            need(type(call) is dict and set(call) == {'height', 'hash'})
            need(is_int(call['height'], 1) and is_hash(call['hash']))
    need(type(value['run_start_ns']) is int and type(value['run_end_ns']) is int)
    need(value.get('stop_reason', STOP_REASONS[0]) in {1: STOP_REASONS, 2: STOP_REASONS_V2, 3: STOP_REASONS_V3}[version])
    events = value['events']
    need(type(events) is list and len(events) <= MAX_TIMESTAMP_EVENTS)
    for item in events:
        need(type(item) is dict and type(item.get('event')) is str and type(item.get('t_ns')) is int)
        name = item['event']
        need(name in BASE_EVENTS or name == 'ACK' or ATTEMPT.fullmatch(name))
        if name == 'I':
            need(set(item) == {'event', 't_ns', 'included'} and type(item['included']) is bool)
        elif name in ('O_A', 'O_B'):
            need(set(item) == {'event', 't_ns', 'outcome'} and item['outcome'] in OUTCOMES)
        else:
            need(set(item) == {'event', 't_ns'})


def read_t42(directory, k, head_sha):
    """The slice's T4-2 state: PASS only for a valid record of this slice at this head SHA."""
    try:
        raw = read_bounded(directory / f't42-slice-{k}.json')
        if raw is None:
            return 'MISSING'
        value = parse(raw)
        need(set(value) == {'format', 'slice', 'head_sha', 'result'} and value['format'] == FORMAT_T42)
        need(is_int(value['slice'], 1) and type(value['head_sha']) is str and HEX40.fullmatch(value['head_sha']))
        need(value['result'] in T42_RESULTS)
    except Invalid:
        return 'INVALID'
    if value['slice'] != k:
        return 'OTHER_SLICE'
    if value['head_sha'] != head_sha:
        return 'OTHER_SHA'
    return value['result']


# --------------------------------------------------------------------------------------------- chain ----
def v2_checks(record):
    """V2: RUN_FACT_UNREAD when a fee, a vsize or an H0 - 1 read is null or no comparison's H is recorded;
    CANDIDATE_VSIZE_DISAGREES when the nodes decode other vsizes; H0_MINUS_1_CHANGED when the six reads and
    every comparison's H are not one hash, or a comparison ran at another height (A, Q3)."""
    failed = set()
    reads = [read[n] for read in record['h0_minus_1_reads'] for n in NODES]
    facts = list(record['incrementalfee_sat_per_kvb'].values()) + list(record['candidate_vsize'].values()) + reads
    if None in facts or not record['prestate_calls']:
        failed.add('RUN_FACT_UNREAD')
    vsize = record['candidate_vsize']
    if None not in vsize.values() and vsize['A'] != vsize['B']:
        failed.add('CANDIDATE_VSIZE_DISAGREES')
    hashes = {h for h in reads if h is not None} | {call['hash'] for call in record['prestate_calls']}
    if len(hashes) > 1 or any(call['height'] != record['h0_minus_1_height'] for call in record['prestate_calls']):
        failed.add('H0_MINUS_1_CHANGED')
    return failed


def chain_checks(record, version=1):
    """(failed checks in CHECKS order, the time of each event present exactly once)."""
    events = record['events']
    names = [e['event'] for e in events]
    counts = {}
    for name in names:
        counts[name] = counts.get(name, 0) + 1
    t = {e['event']: e['t_ns'] for e in events if counts[e['event']] == 1}
    position = {e['event']: i for i, e in enumerate(events) if counts[e['event']] == 1}
    failed = set()
    if any(name not in counts for name in BASE_EVENTS):
        failed.add('BASE_EVENT_MISSING')
    if any(c > 1 for name, c in counts.items() if name != 'ACK'):
        failed.add('EVENT_DUPLICATED')
    if counts.get('ACK', 0) > 1:
        failed.add('ACK_DUPLICATED')
    attempts = {}
    for name in counts:
        match = ATTEMPT.fullmatch(name)
        if match:
            attempts.setdefault(match.group(1), []).append(int(match.group(2)))
    for node in NODES:
        numbers = sorted(attempts.get(node, []))
        if 1 not in numbers:
            failed.add('FIRST_ATTEMPT_MISSING')
        if numbers and numbers != list(range(numbers[0], numbers[0] + len(numbers))):
            failed.add('ATTEMPT_GAP')
        if any(i > MAX_ATTEMPTS for i in numbers):
            failed.add('ATTEMPT_OVER_LIMIT')
    times = [e['t_ns'] for e in events]
    if any(b < a for a, b in zip(times, times[1:])):
        failed.add('CLOCK_REGRESSION')
    start, end = record['run_start_ns'], record['run_end_ns']
    if end - start > XD1_RUN_CAP_NS or end < start:
        failed.add('RUN_CAP_EXCEEDED')
    if any(not start <= x <= end for x in times):
        failed.add('EVENT_OUTSIDE_RUN')
    if 'stop_reason' in record:
        failed.add('STOP_REASON')
    failed.update(edge_failures(t, position, attempts))
    if version >= 2:
        failed.update(v2_checks(record))
    if version == 3 and record['decision'] != 'BROADCAST':
        failed.add('DECISION_NOT_BROADCAST')
    return [c for c in {1: CHECKS, 2: CHECKS_V2, 3: CHECKS_V3}[version] if c in failed], t


def edge_failures(t, position, attempts):
    """Every edge of 1E section 4.5 Order whose events are present exactly once; each failed edge once."""
    failed = set()

    def edge(name, a, b, strict=False):
        # Every edge is a stamping order, so on equal times the list order is the evidence: a must come first
        # (#381 Codex r4290902278: B_A_2 listed before B_A_1 at one timestamp).
        if a in t and b in t and not (t[a] < t[b] or (not strict and t[a] == t[b] and position[a] < position[b])):
            failed.add(name)

    edge('S0_LE_S1', 'S0', 'S1')
    edge('S0_LE_S2', 'S0', 'S2')
    edge('S1_LE_I', 'S1', 'I')
    edge('S2_LE_STEP1_START', 'S2', 'STEP_1_START')
    for k in STEPS:
        edge('STEP_START_LE_END', f'STEP_{k}_START', f'STEP_{k}_END')
        if k < STEPS[-1]:
            edge('STEP_END_LE_NEXT_START', f'STEP_{k}_END', f'STEP_{k + 1}_START')
    edge('D0_LE_D1', 'D0', 'D1')
    edge('STEP9_END_LE_D0', 'STEP_9_END', 'D0')
    for node in NODES:
        names = [f'B_{node}_{i}' for i in sorted(attempts.get(node, []))]
        for b in names:
            edge('D1_LE_EVERY_B', 'D1', b)
            edge('STEP10_START_LE_EVERY_B', 'STEP_10_START', b)
            edge('ATTEMPT_LE_ITS_O', b, f'O_{node}')
            edge('EVERY_B_LE_I', b, 'I')
        for a, b in zip(names, names[1:]):
            edge('ATTEMPTS_IN_ORDER', a, b)
        edge('EVERY_O_LE_STEP10_END', f'O_{node}', 'STEP_10_END')
        edge('EVERY_O_LE_I', f'O_{node}', 'I')
    edge('S2_LE_ACK', 'S2', 'ACK')
    edge('ACK_LT_STEP1_START', 'ACK', 'STEP_1_START', strict=True)
    return failed


def last_attempt(t, node):
    return max((int(ATTEMPT.fullmatch(n).group(2)), x) for n, x in t.items()
               if ATTEMPT.fullmatch(n) and n[2] == node)[1]


def values(t):
    """T_plan, T_045b, T_bound, S2 - S0 and D1 - D0 of a chain that passed every check (1E section 4.5 Checker)."""
    outcome = max(t['O_A'], t['O_B'])
    return dict(t_plan_ns=outcome - t['S2'],
                t_045b_ns=max(last_attempt(t, 'A'), last_attempt(t, 'B')) - t['S0'],
                t_bound_ns=outcome - t['S0'], s2_minus_s0_ns=t['S2'] - t['S0'], d1_minus_d0_ns=t['D1'] - t['D0'])


def decide(v, metric, ack_ok, t42_pass):
    """(deciding value, its name). UNDECIDED: the largest; 045B: T_045b; PLAN: T_plan only with a valid ACK and
    a T4-2 pass of the run's own slice at the run's head SHA, else T_bound."""
    if metric == '045B':
        return v['t_045b_ns'], 'T_045B'
    if metric == 'PLAN':
        if ack_ok and t42_pass:
            return v['t_plan_ns'], 'T_PLAN'
        return v['t_bound_ns'], 'T_BOUND'
    named = (('T_BOUND', v['t_bound_ns']), ('T_PLAN', v['t_plan_ns']), ('T_045B', v['t_045b_ns']))
    best = max(x for _, x in named)
    return best, next(name for name, x in named if x == best)


# -------------------------------------------------------------------------------------------- report ----
def empty_row(index, reason, failed, version=1, declaration=None):
    row = dict(run_index=index, slice=slice_of(index) if version < 3 else declaration['first_run'],
               infinite_reason=reason, failed_checks=failed,
               decision_ns=None, decided_by=None, t_plan_ns=None, t_045b_ns=None, t_bound_ns=None,
               s2_minus_s0_ns=None, d1_minus_d0_ns=None, ack_present=None, incrementalfee_sat_per_kvb=None,
               r_inc_sat_per_kvb=None, candidate_vsize=None, outcome_a=None, outcome_b=None, included=None,
               stop_reason=None)
    if version >= 2:
        row.update(candidate_vsize_by_node=None, h0_minus_1_hash=None, t_s2_to_last_b_ns=None)
    if version == 3:   # the session's run id, the live decision, D1 - D0 as a B_operator sample, T in whole seconds
        row.update(run_id=declaration['run_id'], decision=None, b_operator_ns=None, t_045b_s=None)
    return row


def b_operator(record):
    """D1 - D0 of a record whose D0 and D1 are each stamped once, D0 first (045b :1099: every run's B_operator
    sample, whatever its chain); else None."""
    stamps = [e for e in record['events'] if e['event'] in ('D0', 'D1')]
    if [e['event'] for e in stamps] != ['D0', 'D1'] or stamps[1]['t_ns'] < stamps[0]['t_ns']:
        return None
    return stamps[1]['t_ns'] - stamps[0]['t_ns']


def ceil_seconds(value_ns):
    """XA8 (045b :567-568): a duration in whole seconds, rounded up."""
    return -(-value_ns // 10**9)


def run_row(index, record, declaration, t42_state, metric, version=1):
    if (record['run_index'], record['run_id'], record['run_attempt'], record['head_sha']) != (
            index, declaration['run_id'], declaration['run_attempt'], declaration['head_sha']):
        return empty_row(index, 'RUN_BINDING_MISMATCH', ['RUN_BINDING_MISMATCH'], version, declaration)
    failed, t = chain_checks(record, version)
    row = empty_row(index, 'CHAIN_FAILED' if failed else None, failed, version, declaration)
    if version == 3:
        row.update(decision=record['decision'], b_operator_ns=b_operator(record))
    fee = record['incrementalfee_sat_per_kvb']
    by_name = {e['event']: e for e in record['events']}
    row.update(incrementalfee_sat_per_kvb=dict(fee), ack_present='ACK' in t,
               outcome_a=by_name.get('O_A', {}).get('outcome'), outcome_b=by_name.get('O_B', {}).get('outcome'),
               included=by_name.get('I', {}).get('included'), stop_reason=record.get('stop_reason'))
    if version == 1:
        row.update(r_inc_sat_per_kvb=max(fee['A'], fee['B']), candidate_vsize=record['candidate_vsize'])
    else:   # V2 and V3
        # A node's fact may be unread (null); a value is reported only from both nodes, the vsize only agreed.
        vsize = record['candidate_vsize']
        reads = {read[n] for read in record['h0_minus_1_reads'] for n in NODES}
        agreed = reads.pop() if len(reads) == 1 and 'H0_MINUS_1_CHANGED' not in failed else None
        row.update(r_inc_sat_per_kvb=None if None in fee.values() else max(fee['A'], fee['B']),
                   candidate_vsize=vsize['A'] if None not in vsize.values() and vsize['A'] == vsize['B'] else None,
                   candidate_vsize_by_node=dict(vsize), h0_minus_1_hash=agreed)
    if failed:
        return row
    v = values(t)
    decision, by = decide(v, metric, 'ACK' in t, t42_state == 'PASS')
    row.update(v, decision_ns=decision, decided_by=by)
    if version >= 2:   # the fourth start-stop pair (Q9: both starts, both stops): S2 to the last attempt
        row['t_s2_to_last_b_ns'] = max(last_attempt(t, 'A'), last_attempt(t, 'B')) - t['S2']
    if version == 3:
        row['t_045b_s'] = ceil_seconds(v['t_045b_ns'])
    return row


def build_report(declaration_path, records_dir, metric=METRIC):
    """The report bytes, or Refusal. Reads only the declared names."""
    if metric not in METRICS:
        raise Refusal(4, 'METRIC')
    declaration = read_declaration(Path(declaration_path))
    version = version_of(declaration)
    directory = Path(records_dir)
    if not directory.is_dir():
        raise Refusal(3, 'RECORDS_MISSING')
    if version == 3:
        return session_report(declaration, directory, metric)
    n, head = declaration['n'], declaration['head_sha']
    loaded = {}
    for index in range(1, n + 1):
        try:
            raw = read_bounded(directory / f'run-{index}.json')
        except Invalid:
            loaded[index] = 'RECORD_INVALID'
            continue
        if raw is None:
            loaded[index] = 'RECORD_MISSING'
            continue
        if labels_refused(raw):
            raise Refusal(2, f'LABELS run-{index}.json')
        try:
            value = parse(raw)
            validate_run(value, version)
        except Invalid:
            loaded[index] = 'RECORD_INVALID'
            continue
        loaded[index] = value
    slices = []
    for k in range(1, slice_of(n) + 1):
        first = (k - 1) * SLICE_RUNS + 1
        slices.append(dict(slice=k, first_run=first, last_run=min(k * SLICE_RUNS, n), t42=read_t42(directory, k, head)))
    rows = []
    for index in range(1, n + 1):
        record = loaded[index]
        if type(record) is str:
            rows.append(empty_row(index, record, [record], version))
        else:
            rows.append(run_row(index, record, declaration, slices[slice_of(index) - 1]['t42'], metric, version))
    report = dict(format=FORMAT_REPORT if version == 1 else FORMAT_REPORT_V2, declaration=declaration, labels=list(REQUIRED_LABELS),
                  transferability=TRANSFERABILITY, metric=metric,
                  limits=dict(max_xd1_runs=MAX_XD1_RUNS, max_timestamp_events=MAX_TIMESTAMP_EVENTS,
                              xd1_run_cap_ns=XD1_RUN_CAP_NS, record_limit_bytes=RECORD_LIMIT),
                  slices=slices, rows=rows)
    return (json.dumps(report, sort_keys=True, separators=(',', ':'), ensure_ascii=True) + '\n').encode()


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True) + '\n').encode()


def session_rows(declaration, directory, metric=METRIC):
    """V3: (the session's slice entry, its rows) from exactly its declared names; Refusal for the labels of either
    mode (XA5) or a record evaluated under another registration (REGISTRATION_MISMATCH)."""
    mode, first, last = declaration['mode'], declaration['first_run'], declaration['last_run']
    loaded = {}
    for index in range(first, last + 1):
        try:
            raw = read_bounded(directory / f'run-{index}.json')
        except Invalid:
            loaded[index] = 'RECORD_INVALID'
            continue
        if raw is None:
            loaded[index] = 'RECORD_MISSING'
            continue
        if labels_refused_v3(raw, mode):
            raise Refusal(2, f'LABELS run-{index}.json')
        try:
            value = parse(raw)
            validate_run(value, 3)
        except Invalid:
            loaded[index] = 'RECORD_INVALID'
            continue
        if value['registration_sha256'] != declaration['registration_sha256']:
            raise Refusal(2, f'REGISTRATION_MISMATCH run-{index}.json')
        loaded[index] = value
    entry = dict(slice=first, first_run=first, last_run=last, t42=read_t42(directory, first, declaration['head_sha']))
    rows = []
    for index in range(first, last + 1):
        record = loaded[index]
        if type(record) is str:
            rows.append(empty_row(index, record, [record], 3, declaration))
        else:
            rows.append(run_row(index, record, declaration, entry['t42'], metric, 3))
    return entry, rows


def session_report(declaration, directory, metric=METRIC):
    """The V3 report of one session (XD1_EVENT_CHAIN_V3.md section 5): no percentile; the verdict is the
    collection's."""
    entry, rows = session_rows(declaration, directory, metric)
    mode = declaration['mode']
    report = dict(format=FORMAT_REPORT_V3, mode=mode, declaration=declaration, labels=list(LABELS_V3[mode]),
                  transferability=TRANSFERABILITY_V3, metric=metric,
                  limits=dict(max_xd1_runs=MAX_XD1_RUNS, session_runs=SESSION_RUNS,
                              max_timestamp_events=MAX_TIMESTAMP_EVENTS, xd1_run_cap_ns=XD1_RUN_CAP_NS,
                              record_limit_bytes=RECORD_LIMIT),
                  slices=[entry], rows=rows)
    return canonical(report)


# ------------------------------------------------------------------------------- collection (V3, XA8, XA9) ----
def nearest_rank(q, n):
    """045b :564-569: the 1-based rank ceil(q * n / 100), no interpolation (p95 of 20 is the 19th, p50 the 10th)."""
    return -(-q * n // 100)


def verdict(values_s):
    """XA8: the verdict over the counted runs' T in whole seconds, None for T = infinity, in run order. Exactly
    VERDICT_N values give PASS (p95 <= CRITERION_S) or FAIL (p95 > CRITERION_S, an infinite p95 included); any
    other count is INCONCLUSIVE (FEWER_THAN_20_RUNS) with no percentile. Infinity sorts last."""
    if not all(v is None or is_int(v) for v in values_s):
        raise ValueError('values')
    expected = dict(criterion='P95_T_045B_LE_420_S', threshold_s=CRITERION_S, statistic='P95',
                    estimator='NEAREST_RANK', n=VERDICT_N, p95_rank=nearest_rank(P95, VERDICT_N),
                    p50_rank=nearest_rank(P50, VERDICT_N), rounding='CEIL_WHOLE_SECONDS',
                    infinity='SORTS_LAST')
    observed = dict(counted_runs=len(values_s), t_s=list(values_s),
                    infinite_runs=[i + 1 for i, v in enumerate(values_s) if v is None],
                    p95_s=None, p95_infinite=None, p50_s=None, p50_infinite=None)
    if len(values_s) != VERDICT_N:
        return dict(expected=expected, observed=observed, result='INCONCLUSIVE',
                    inconclusive_reason='FEWER_THAN_20_RUNS')
    ordered = sorted(values_s, key=lambda v: (v is None, v or 0))
    p95, p50 = ordered[nearest_rank(P95, VERDICT_N) - 1], ordered[nearest_rank(P50, VERDICT_N) - 1]
    observed.update(p95_s=p95, p95_infinite=p95 is None, p50_s=p50, p50_infinite=p50 is None)
    result = 'PASS' if p95 is not None and p95 <= CRITERION_S else 'FAIL'
    return dict(expected=expected, observed=observed, result=result, inconclusive_reason=None)


def inconclusive(reason):
    """A collection-level INCONCLUSIVE (XA8): the cause kept, no percentile, never folded into FAIL."""
    if reason not in INCONCLUSIVE_REASONS:
        raise ValueError('reason')
    value = verdict([])
    value['inconclusive_reason'] = reason
    return value


def observation_id(run_index):
    """XA9: OBS-9<run_index:07>, the 8-digit id ct_preregistration_receipt reads, apart from ARDR's 1..8."""
    if not is_int(run_index, 1) or run_index > MAX_XD1_RUNS:
        raise ValueError('run_index')
    return 'OBS-%d%07d' % (OBSERVATION_PREFIX, run_index)


def observation_list(run_starts, registration_sha256):
    """XA9: the observation list in ct_preregistration_receipt's V1 shape, one entry per counted run, in run order;
    `run_starts` maps run_index to its session's slice job `started_at` (integer UTC seconds, XA4)."""
    if not is_hash(registration_sha256) or not run_starts:
        raise ValueError('observation list')
    items = []
    for index in sorted(run_starts):
        start = run_starts[index]
        if not is_int(start, 1) or start > 2**53 - 1:
            raise ValueError('start_time_utc')
        items.append(dict(observation_id=observation_id(index), registration_sha256=registration_sha256,
                          start_time_utc=start))
    return canonical(dict(schema=OBSERVATION_SCHEMA, observations=items))


def collection_report(mode, registration_sha256, head_sha, sessions, never_started, rows, result):
    """The collection report V3 (XD1_EVENT_CHAIN_V3.md section 6): every counted session's rows in run order, the
    verdict (`result`, from verdict() or inconclusive()), each run's B_operator sample, inclusion and replay apart
    (045b :1100), and the environment row (045b :1098)."""
    t42 = [s['t42'] for s in sessions]
    environment = dict(node_versions=list(NODE_VERSIONS_TEXT), host=ENVIRONMENT_HOST, cr21=ENVIRONMENT_CR21,
                       three_r_l_merged_first=ENVIRONMENT_3R_L, t42=t42,
                       t42_pass_sha=head_sha if t42 and all(x == 'PASS' for x in t42) else None,
                       runner_labels=sorted({label for s in sessions for label in s.get('runner_labels', [])}))
    report = dict(format=FORMAT_COLLECTION_V3, mode=mode, registration_sha256=registration_sha256, head_sha=head_sha,
                  labels=list(LABELS_V3[mode]), transferability=TRANSFERABILITY_V3, metric=METRIC,
                  sessions=sessions, never_started=never_started, rows=rows, verdict=result,
                  b_operator_ns=[dict(run_index=r['run_index'], b_operator_ns=r['b_operator_ns']) for r in rows],
                  inclusion=[dict(run_index=r['run_index'], outcome_a=r['outcome_a'], outcome_b=r['outcome_b'],
                                  included=r['included']) for r in rows],
                  replay=[dict(run_index=r['run_index'], replay='NOT_MEASURED_BY_XD1') for r in rows],
                  environment=environment)
    return canonical(report)


def publish(path, raw):
    """'WRITTEN', or 'SAME' when the same bytes are already there; other bytes or another file type refuse (2)."""
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        info = None
    except OSError as exc:
        raise Refusal(4, 'OUTPUT_UNREADABLE') from exc
    if info is not None:
        if not stat.S_ISREG(info.st_mode):
            raise Refusal(2, 'OUTPUT_EXISTS')
        try:
            same = read_bounded(path, len(raw)) == raw
        except Invalid:
            same = False
        if not same:
            raise Refusal(2, 'OUTPUT_EXISTS')
        return 'SAME'
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    except OSError as exc:
        raise Refusal(4, 'OUTPUT_WRITE') from exc
    try:
        try:
            view = memoryview(raw)
            while view:
                view = view[os.write(fd, view):]
        finally:
            os.close(fd)
    except OSError as exc:
        try:   # no partial report is left behind: a rerun then writes it, not OUTPUT_EXISTS
            os.unlink(path)
        except OSError:
            pass
        raise Refusal(4, 'OUTPUT_WRITE') from exc
    return 'WRITTEN'


def parser():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest='mode', required=True)
    check = sub.add_parser('check')
    check.add_argument('--declaration', required=True)
    check.add_argument('--records', required=True)
    check.add_argument('--output', required=True)
    return p


def main(argv=None):
    if not __debug__:
        print(json.dumps(dict(result='REFUSED', failure='OPTIMIZED_PYTHON')), file=sys.stderr)
        return 5
    try:
        a = parser().parse_args(sys.argv[1:] if argv is None else argv)
        raw = build_report(a.declaration, a.records)
        state = publish(a.output, raw)
    except Refusal as exc:
        print(json.dumps(dict(result='REFUSED', failure=str(exc))), file=sys.stderr)
        return exc.code
    except Exception as exc:  # noqa: BLE001 - one bounded internal-error line, no free text
        print(json.dumps(dict(result='FAIL', failure='INTERNAL:' + type(exc).__name__)), file=sys.stderr)
        return 4
    rows = json.loads(raw)['rows']
    print(json.dumps(dict(result=state, rows=len(rows), sha256=hashlib.sha256(raw).hexdigest())))
    return 0


if __name__ == '__main__':
    import claude_track_exit
    claude_track_exit.run(main)
