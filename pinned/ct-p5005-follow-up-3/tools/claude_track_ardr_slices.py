#!/usr/bin/env python3
"""CT-P5-001 D4: the ARDR workflow's dispatch plan, slices, collection and re-dispatch check.

Class T Regtest development evidence only; never mainnet, never S17-PREP, and no ARDR verdict. Sources: A's
unit request #258 issuecomment-6537782009 (section 1 S04 rule, Q5, Q6, Q9, section 3 re-dispatch, section 4
row D4) and -6539879887 section 3. The format is `docs/claude-track/formats/ARDR_RUN_V1.md` section 13; the
workflow is `.github/workflows/claude-track-ardr.yml`; the driver is `tools/claude_track_ardr_driver.py` (D1),
called as a black box, one process per unit.

Subcommands:

- `plan`: checks A's dispatch inputs and writes the declaration (`BITAGI_CT_ARDR_DECLARATION_V2`): the
  experiment, the mode, the unit range and its slices, each at most 330 minutes, the observations per unit (an
  ITEM1 or POOL unit is a run of `gates_per_run` gate observations) and ITEM1's method policy (U3).
- `started-at`: this job's server `started_at` from the Actions jobs listing the workflow saved (Q9).
- `slice-begin`: the slice job's first tool step writes the slice record (`BITAGI_CT_ARDR_SLICE_V2`) with every
  unit BEFORE_START, before the Core fetch and the token step, so a setup failure leaves the units re-dispatchable.
- `slice`: requires that record, then reads the policy, this job's server `started_at` (Q9) and, CONFIRMATORY,
  carries the S04 citation the plan job derived (`citation.json` of artifact `ardr-s04`, shape-checked, its run
  id the declaration's; no git or API derivation in the slice, so every S04 refusal happens in plan, section 1
  of A's request); a refusal there leaves every unit BEFORE_START with the refusal's code. It then runs the
  units with the driver and keeps the record current: every unit is BEFORE_START, IN_PROGRESS (written before
  the driver starts), OBSERVED or EXCLUDED.
- `collect`: reads this run's declaration, slice records and jobs listing and writes the collection record
  (`BITAGI_CT_ARDR_COLLECTION_V2`) and, when there is at least one CONFIRMATORY observation, the observation
  list (`BITAGI_CT_OBSERVATION_LIST_V2`) exactly as `tools/ct_preregistration_receipt.py` parses it: one entry
  per started gate of an ITEM1 or POOL run (gate-level id, read from the whole raw log), one per started unit
  of any other experiment (run-level id). EXPLORATORY and PR_SMOKE units are never observations.
- `s04-run-id`, `s04-run`, `s04-artifact`, `s04-job`, `s04-cite`: the S04 citation of a CONFIRMATORY dispatch,
  derived from the server (the `s04_run_id` input): the cited rx02 run as the Actions API lists it, its record
  artifact or, when that is expired or missing, the record job's log; never a committed copy.
- `runs-pages`, `prior-runs`, `artifact-id`, `redispatch`: the re-dispatch rule (CONFIRMATORY only; an
  EXPLORATORY dispatch reads no earlier run). A unit is dispatched once; only a unit that every earlier
  CONFIRMATORY dispatch of the same experiment shows BEFORE_START, whatever its registration, may be
  dispatched again. Only a run that is the current one, or newer and not completed, is skipped (D4-2): a
  completed run of any number is read.
- `recollect-inputs`, `recollect-run`, `recollect-declaration`, `recollect-slices`, `recollect` (D4-2, A #619
  issuecomment-6542865820): the collect-only recovery of a CONFIRMATORY run whose collect job failed. It rebuilds
  that run's collection with collect's own function from that run's declaration, slice artifacts and attempt-1
  jobs listing only, marks it with the original run id and `recollected`, and adds no observation; a later
  re-dispatch check uses it in place of the missing collection.

The tool reads files only; the workflow's one token step per job saves the Actions API answers it reads, so the
tests need no network and no token reaches this process. Exit codes (AGENTS.md section 12): 0 done, 2
validation failure, 3 missing prerequisite, 4 internal error, 6 refusal (S04 citation, re-dispatch, a record
that does not match the run). A refusal prints one JSON line with a fixed `code`. Optimized Python (-O) is
refused. Stdlib only.
"""
from __future__ import annotations

import argparse
import calendar
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import zipfile

sys.dont_write_bytecode = True
TOOLS = Path(__file__).absolute().parent
sys.path.insert(0, str(TOOLS))
from common import bounded_regular_bytes, strict_json_bytes  # noqa: E402

EXIT_DONE, EXIT_VALIDATION, EXIT_PREREQUISITE, EXIT_INTERNAL, EXIT_REFUSAL = 0, 2, 3, 4, 6
EXIT_SECURITY = 5   # a driver refusal for security (SECRET_IN_LOG, D2-2 exit 5): U3 Part C counts these units apart
DRIVER = TOOLS / 'claude_track_ardr_driver.py'
DECLARATION_SCHEMA = 'BITAGI_CT_ARDR_DECLARATION_V2'
DECLARATION_SCHEMA_V1 = 'BITAGI_CT_ARDR_DECLARATION_V1'   # read only as an earlier run's (re-dispatch check)
SLICE_SCHEMA = 'BITAGI_CT_ARDR_SLICE_V2'   # U3 Part C: each unit's driver `exit`
COLLECTION_SCHEMA = 'BITAGI_CT_ARDR_COLLECTION_V2'
COLLECTION_SCHEMAS = ('BITAGI_CT_ARDR_COLLECTION_V1', COLLECTION_SCHEMA)   # an earlier run's, re-dispatch check
OBSERVATION_SCHEMA = 'BITAGI_CT_OBSERVATION_LIST_V2'   # ct_preregistration_receipt.OBSERVATION_SCHEMA_V2
RAW_SCHEMA = 'BITAGI_CT_ARDR_RAW_V1'                   # the driver's LOG_SCHEMA
S04_SCHEMA = 'bitagi.claude_track.s04_record.v2'
# The S04 run a CONFIRMATORY dispatch cites (A's request section 1): a main push run of the rx02 workflow (matched
# on the run's `path`, never its display name), its record job and the artifact that job uploads.
S04_WORKFLOW_PATH = '.github/workflows/claude-track-rx02.yml'
S04_JOB_NAME = 'S04 record v2 (leg set s04-legs-v1, this run only)'
S04_MEMBER = 's04_record_v2.json'
S04_LOG_LIMIT = 16 * 1024 * 1024
S04_SOURCES = ('ARTIFACT', 'JOB_LOG')
S04_CITATION_KEYS = {'record_sha256', 'record_source', 's04_run_id', 's04_run_attempt', 's04_head_sha', 'subjects'}
# A job log line: the runner's timestamp, one space, the printed text.
LOG_LINE = re.compile(rb'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,9})?Z (.*)\Z', re.S)
SHA_LINE = re.compile(rb'([0-9a-f]{64})  \S*/s04_record_v2\.json\Z')
SECONDS_PER_MINUTE = 60
# The driver's EXPERIMENTS, in order; the index is the observation id's first digit.
EXPERIMENTS = ('ITEM1', 'ITEM2', 'ITEM3', 'ITEM4_SELF_DEALING', 'ITEM4_FEE_ASYMMETRY', 'ITEM4_CENSORSHIP',
               'ITEM4_REORG', 'POOL')
DISPATCH_MODES = ('CONFIRMATORY', 'EXPLORATORY')
MODES = DISPATCH_MODES + ('PR_SMOKE',)
STATES = ('BEFORE_START', 'IN_PROGRESS', 'OBSERVED', 'EXCLUDED')
OBSERVATION_STATES = ('IN_PROGRESS', 'OBSERVED', 'EXCLUDED')   # an observation started
SLICE_MINUTES = 330          # A Q5
SETUP_MINUTES = 30           # checkout, Core fetch and the token step, before the first unit
UPLOAD_MINUTES = 15          # kept free at the end for the record upload
MAX_RUN_INDEX = 10**7 - 1    # the observation id holds seven digits of it
# U3 (A Q2-Q3 on #258, 6549827052): the dispatch's observation budget, runs x gates_per_run for ITEM1 and POOL,
# runs for any other experiment. A list entry is at most 157 bytes (a gate id, a 12-digit start time, the year
# 9999) plus a comma, the list frame 61 bytes, so 400 entries are at most 61 + 400 x 157 + 399 = 63,260 bytes,
# under the receipt tool's 64 KiB (65,536) bound (414 would still fit); unit note section 2.
MAX_OBSERVATIONS = 400
GATE_EXPERIMENTS = ('ITEM1', 'POOL')   # the driver's CAMPAIGN_EXPERIMENTS: one observation per gate
MAX_GATES = 200                        # the driver's MAX_GATES_PER_RUN; a gate id holds three digits
DRAFT_GATES = {'ITEM1': 200, 'POOL': 4}   # gates_per_run of the driver's DRAFT_PARAMS (a policy without params)
GATE_STATES = ('OBSERVED', 'EXCLUDED', 'NOT_STARTED')
# U3 (A Q5): the driver's D2_2_SHARE_SECONDS and DEADLINE_MARGIN_SECONDS; a CONFIRMATORY ITEM1 or POOL unit must
# be longer than both, or its driver refuses before RUN_START (UNIT_SECONDS_SHORT); plan refuses it first.
D2_2_SHARE_SECONDS, DEADLINE_MARGIN_SECONDS = 300 + 1800 + 3600, 900   # the driver's (sum of its share; margin)
DEADLINE_RESERVE_SECONDS = D2_2_SHARE_SECONDS + DEADLINE_MARGIN_SECONDS
# B-UM (A #258 6768800772, RV-185 (b)): a CONFIRMATORY ITEM2 unit waits t_G after G - 1, up to the driver's
# GATE_INTERVAL_N (1,200 s; 045b :559), plus its time besides t_G (nodes, the blocks up to G - 1, the L0 seat's
# charge and signing, teardown; measured 21.8-41 s, B-UM note): an allowance of 300 s, so 25 minutes or more.
ITEM2_GATE_SECONDS, ITEM2_OVERHEAD_SECONDS = 1200, 300
ITEM2_UNIT_SECONDS_FLOOR = ITEM2_GATE_SECONDS + ITEM2_OVERHEAD_SECONDS   # 1,500 s
MAX_SLICES = 64
MAX_JOBS = 100               # one page of the jobs or runs listing
# The dispatch runs listing is filtered (event, branch); GitHub's list-workflow-runs returns at most 1,000 runs
# when a filter is used, so it is read in at most 10 pages of 100, and a total of 1,000 or more is refused (the
# oldest runs could be missing from it).
MAX_RUN_PAGES = 10
RUNS_LISTING_CAP = MAX_RUN_PAGES * MAX_JOBS   # 1,000
WORKFLOW_PATH = '.github/workflows/claude-track-ardr.yml'
# The workflow's names the tool matches in the jobs listings (test_ardr_workflow checks them against the file).
PLAN_JOB_NAME = 'ARDR dispatch plan (main only, slice budget, re-dispatch rule)'
DECLARATION_STEP = 'Upload the declaration'
SLICE_JOB = re.compile(r'ARDR slice [1-9][0-9]{0,2}\Z')   # slice_job_name(n) as the jobs listing names it
UNITS_STEP = "Run the slice's units"
# The run name the workflow sets (`run-name`) for a dispatch: its mode and experiment.
RUN_TITLE = re.compile(r'ardr (CONFIRMATORY|EXPLORATORY) ([A-Z0-9_]{1,40})\Z')
# A collect-only recovery dispatch (mode RECOLLECT): `ardr RECOLLECT <experiment> <run id input>`.
RECOLLECT_TITLE = re.compile(r'ardr RECOLLECT ([A-Z0-9_]{1,40})(?: (.*))?\Z', re.S)
JSON_LIMIT = 1024 * 1024
RECEIPT_JSON_LIMIT = 64 * 1024   # ct_preregistration_receipt.JSON_LIMIT
LOG_LIMIT = 256 * 1024 * 1024    # the driver's LOG_LIMIT
ZIP_LIMIT = 1024 * 1024
UTC = re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z\Z')
HEX64 = re.compile(r'[0-9a-f]{64}\Z')
OID = re.compile(r'[0-9a-f]{40}\Z')
CODE_WORD = re.compile(r'[A-Z][A-Z0-9_ ]{0,80}\Z')
DIGITS = re.compile(r'[1-9][0-9]{0,19}\Z')
LABELS = ['CLASS_T', 'REGTEST', 'CLASS_T_DEVELOPMENT_EVIDENCE_NOT_S17_PREP', 'DRIVER_RECORD_NOT_VERDICT']
DECLARATION_ARTIFACT, COLLECTION_ARTIFACT = 'ardr-declaration', 'ardr-collection'
# D4-2 collect-only recovery: the recollection of one CONFIRMATORY run, from that run's own slice artifacts.
RECOLLECTION_SCHEMA = 'BITAGI_CT_ARDR_RECOLLECTION_V1'
RECOLLECTION_ARTIFACT, RECOLLECTION_MEMBER = 'ardr-recollection', 'recollection.json'
SLICE_ARTIFACT = 'ardr-slice-%d'
STRAY_RECORD_TMP = 'slice-record.json.tmp'   # what `replace` leaves when killed between open and rename
# The artifact names a dispatch run of this workflow uploads (D4); a recollected run listing any other is refused.
RUN_ARTIFACT = re.compile(r'ardr-(?:declaration|s04|collection|observations|slice-[1-9][0-9]{0,2})\Z')
SLICE_ZIP_LIMIT = 1024 * 1024 * 1024   # one slice artifact's zip as the API serves it
SLICE_UNPACKED_LIMIT = 4 * 1024 * 1024 * 1024


class Refusal(Exception):
    def __init__(self, code: str, exit_code: int):
        super().__init__(code)
        self.code, self.exit_code = code, exit_code


def need(condition: bool, code: str, exit_code: int = EXIT_VALIDATION) -> None:
    if not condition:
        raise Refusal(code, exit_code)


def evidence_status(mode: str) -> str:
    return 'CONFIRMATORY' if mode == 'CONFIRMATORY' else 'EXPLORATORY'


def dumps(value) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode('ascii')


def read_bytes(path: Path, limit: int, code: str) -> bytes:
    try:
        return bounded_regular_bytes(path.absolute(), root=path.absolute().parent, limit=limit)
    except (OSError, ValueError):
        raise Refusal(code, EXIT_PREREQUISITE) from None


def parse_json(blob: bytes, code: str):
    try:
        return strict_json_bytes(blob)
    except (ValueError, UnicodeDecodeError, RecursionError):
        raise Refusal(code, EXIT_VALIDATION) from None


def read_json(path: Path, code: str, limit: int = JSON_LIMIT) -> dict:
    value = parse_json(read_bytes(path, limit, code + '_UNAVAILABLE'), code + '_JSON')
    need(type(value) is dict, code + '_JSON')
    return value


def write_new(path: Path, data: bytes) -> None:
    """A new file, never an existing one, written whole (create, write, rename)."""
    need(not path.exists(), 'OUTPUT_EXISTS', EXIT_PREREQUISITE)
    replace(path, data)


def replace(path: Path, data: bytes) -> None:
    """Write a whole output (create, write, fsync, rename). A tool that cannot write its output exits 4
    (AGENTS.md section 12), not 3: the partial `.tmp` is removed and `path` keeps what it held before."""
    tmp = path.with_name(path.name + '.tmp')
    try:
        with open(tmp, 'xb') as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except OSError:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise Refusal('OUTPUT_WRITE_FAILED', EXIT_INTERNAL) from None


def epoch(utc: str) -> int:
    need(type(utc) is str and UTC.match(utc) is not None, 'STARTED_AT')
    try:
        return calendar.timegm(time.strptime(utc, '%Y-%m-%dT%H:%M:%SZ'))
    except ValueError:
        raise Refusal('STARTED_AT', EXIT_VALIDATION) from None


def unit_id(experiment: str, run: int) -> dict:
    """The driver's unit identifier (ARDR_RUN_V1 section 5); gate and cohort come with D2-3/D3."""
    return {'cohort': None, 'experiment': experiment, 'gate': None, 'run': run}


def observation_id(experiment: str, run: int) -> str:
    """One id per unit, so lists of different dispatches of one registration never collide."""
    return 'OBS-%d%07d' % (EXPERIMENTS.index(experiment) + 1, run)


def gate_observation_id(experiment: str, run: int, gate: int) -> str:
    """One id per gate of an ITEM1 or POOL run: the campaign's `gate_observation_id` (`OBS-<e><run:07>-G<g:03>`),
    which each GATE_START and GATE_END line carries."""
    return observation_id(experiment, run) + '-G%03d' % gate


# ---------------------------------------------------------------------------------------------------------- plan

def slices_of(first: int, last: int, per_slice: int) -> list[dict]:
    return [{'slice': i + 1, 'first': start, 'last': min(start + per_slice - 1, last)}
            for i, start in enumerate(range(first, last + 1, per_slice))]


def policy_entry(blob: bytes, experiment: str) -> dict:
    """The policy's `experiments.<experiment>` object (the driver checks the rest of the policy)."""
    value = parse_json(blob, 'POLICY_JSON')
    entries = value.get('experiments') if type(value) is dict else None
    need(type(entries) is dict and type(entries.get(experiment)) is dict, 'POLICY_JSON')
    return entries[experiment]


def observations_per_unit(entry: dict, experiment: str, mode: str) -> int:
    """An ITEM1 or POOL unit holds `params.gates_per_run` observations (the driver's DRAFT_PARAMS when an
    EXPLORATORY policy has no params); any other unit one."""
    if experiment not in GATE_EXPERIMENTS:
        return 1
    params = entry.get('params')
    if params is None:
        need(mode != 'CONFIRMATORY', 'POLICY_GATES_UNSET', EXIT_PREREQUISITE)
        return DRAFT_GATES[experiment]
    need(type(params) is dict, 'POLICY_GATES')   # U3 pre-PR P3-6(a): `params: 3` is not a gate count
    gates = params.get('gates_per_run')
    need(not (type(gates) is str and gates.startswith('PENDING')), 'POLICY_GATES_PENDING', EXIT_PREREQUISITE)
    need(type(gates) is int and 1 <= gates <= MAX_GATES, 'POLICY_GATES')
    return gates


def declared_method_policy(entry: dict, experiment: str, mode: str) -> dict | None:
    """A Q3: ITEM1's method policy is named in the policy, `experiments.ITEM1.method_policy {path, sha256}`, so
    the registered policy hash binds it; a CONFIRMATORY ITEM1 needs it (exit 3 `METHOD_POLICY_UNDECLARED`)."""
    value = entry.get('method_policy')
    if value is None:
        need(not (experiment == 'ITEM1' and mode == 'CONFIRMATORY'), 'METHOD_POLICY_UNDECLARED', EXIT_PREREQUISITE)
        return None
    need(experiment == 'ITEM1' and type(value) is dict and set(value) == {'path', 'sha256'}
         and type(value['path']) is str and type(value['sha256']) is str and HEX64.match(value['sha256']) is not None,
         'METHOD_POLICY_DECLARATION')
    return {'path': value['path'], 'sha256': value['sha256']}


def plan(args) -> dict:
    need(args.experiment in EXPERIMENTS, 'EXPERIMENT')
    need(args.mode in DISPATCH_MODES, 'MODE')
    need(0 <= args.unit_first <= args.unit_last <= MAX_RUN_INDEX, 'UNIT_RANGE')
    units = args.unit_last - args.unit_first + 1
    need(units <= MAX_OBSERVATIONS, 'OBSERVATION_BUDGET', EXIT_REFUSAL)   # every unit is one observation or more
    need(1 <= args.unit_minutes <= SLICE_MINUTES and 1 <= args.units_per_slice <= MAX_OBSERVATIONS, 'SLICE_SHAPE')
    # A slice is planned to fit 330 minutes with its setup and upload (Q5); the slice also stops early.
    need(SETUP_MINUTES + args.units_per_slice * args.unit_minutes + UPLOAD_MINUTES <= SLICE_MINUTES,
         'SLICE_BUDGET', EXIT_REFUSAL)
    slices = slices_of(args.unit_first, args.unit_last, args.units_per_slice)
    need(len(slices) <= MAX_SLICES, 'SLICE_COUNT')
    registration = args.registration_sha256 or None
    if args.mode == 'CONFIRMATORY':
        need(registration is not None and HEX64.match(registration) is not None, 'REGISTRATION_SHA256',
             EXIT_PREREQUISITE)
        need(bool(args.registration) and bool(args.s04_run_id), 'CONFIRMATORY_INPUTS', EXIT_PREREQUISITE)
        need(DIGITS.match(args.s04_run_id) is not None, 'S04_RUN_ID_INPUT')
        s04_run_id, s04_input = args.s04_run_id, 'CITED'
    else:
        need(registration is None and not args.registration, 'EXPLORATORY_INPUTS')
        # An EXPLORATORY dispatch cites no S04 run; a given run id is ignored and the declaration says so.
        s04_run_id, s04_input = None, ('IGNORED_EXPLORATORY' if args.s04_run_id else 'NOT_GIVEN')
    need(DIGITS.match(args.run_id) is not None and DIGITS.match(args.run_attempt) is not None, 'RUN_FIELDS')
    # A second attempt of a CONFIRMATORY dispatch would dispatch its units again (section 3 of A's request).
    need(args.mode != 'CONFIRMATORY' or args.run_attempt == '1', 'RUN_ATTEMPT_NOT_FIRST', EXIT_REFUSAL)
    need(OID.match(args.commit) is not None, 'RUN_FIELDS')
    # D-2: the policy and registration are files of the dispatched commit, checked here rather than in every slice.
    commit_file(args.policy)
    if args.registration:
        commit_file(args.registration)
    per_unit, method = 1, None
    if args.experiment in GATE_EXPERIMENTS:   # U3: the gates per run and the method policy, from the policy
        entry = policy_entry(read_bytes(Path(args.policy), JSON_LIMIT, 'POLICY_UNAVAILABLE'), args.experiment)
        per_unit = observations_per_unit(entry, args.experiment, args.mode)
        method = declared_method_policy(entry, args.experiment, args.mode)
        if method is not None:   # a file of the commit with the policy's SHA-256 (A Q3)
            commit_file(method['path'])
            blob = read_bytes(Path(method['path']), JSON_LIMIT, 'METHOD_POLICY_UNAVAILABLE')
            need(hashlib.sha256(blob).hexdigest() == method['sha256'], 'METHOD_POLICY_SHA256', EXIT_REFUSAL)
    need(units * per_unit <= MAX_OBSERVATIONS, 'OBSERVATION_BUDGET', EXIT_REFUSAL)
    need(not (args.mode == 'CONFIRMATORY' and args.experiment in GATE_EXPERIMENTS)
         or args.unit_minutes * SECONDS_PER_MINUTE > DEADLINE_RESERVE_SECONDS, 'UNIT_MINUTES_SHORT', EXIT_REFUSAL)
    # B-UM: a CONFIRMATORY ITEM2 unit shorter than t_G's bound and the overhead allowance is refused (A 6768800772).
    need(not (args.mode == 'CONFIRMATORY' and args.experiment == 'ITEM2')
         or args.unit_minutes * SECONDS_PER_MINUTE >= ITEM2_UNIT_SECONDS_FLOOR, 'UNIT_MINUTES_SHORT', EXIT_REFUSAL)
    declaration = {
        'schema': DECLARATION_SCHEMA, 'experiment': args.experiment, 'mode': args.mode,
        'evidence_status': evidence_status(args.mode), 'units': {'first': args.unit_first, 'last': args.unit_last},
        'units_per_slice': args.units_per_slice, 'unit_minutes': args.unit_minutes, 'slices': slices,
        'policy_path': args.policy, 'registration_path': args.registration or None,
        'registration_sha256': registration, 's04_run_id': s04_run_id, 's04_run_id_input': s04_input,
        'run': {'run_id': args.run_id, 'run_attempt': args.run_attempt, 'commit': args.commit},
        'observations_per_unit': per_unit, 'method_policy': method, 'labels': LABELS}
    write_new(args.out, dumps(declaration))
    if args.github_output is not None:
        try:   # an output this tool cannot write is exit 4 (AGENTS.md section 12), like replace()
            with open(args.github_output, 'a', encoding='ascii', newline='') as handle:
                handle.write('slices=%s\n' % json.dumps([s['slice'] for s in slices], separators=(',', ':')))
        except OSError:
            raise Refusal('OUTPUT_WRITE_FAILED', EXIT_INTERNAL) from None
    return {'slices': len(slices), 'units': units, 'observations': units * per_unit}


def check_declaration(value: dict, prior: bool = False) -> dict:
    """The declaration's shape. `prior`: an earlier run's declaration for the re-dispatch check, which may be
    V1 (written before U3, without `observations_per_unit` and `method_policy`; only its units are read)."""
    keys = {'schema', 'experiment', 'mode', 'evidence_status', 'units', 'units_per_slice', 'unit_minutes',
            'slices', 'policy_path', 'registration_path', 'registration_sha256', 's04_run_id', 's04_run_id_input',
            'run', 'labels'}
    v1 = prior and set(value) == keys and value.get('schema') == DECLARATION_SCHEMA_V1
    keys |= {'observations_per_unit', 'method_policy'}
    need(v1 or (set(value) == keys and value['schema'] == DECLARATION_SCHEMA), 'DECLARATION_SHAPE')
    need(value['experiment'] in EXPERIMENTS and value['mode'] in DISPATCH_MODES
         and value['evidence_status'] == evidence_status(value['mode']), 'DECLARATION_SHAPE')
    units, per = value['units'], value['units_per_slice']
    need(type(units) is dict and set(units) == {'first', 'last'} and type(per) is int and per >= 1
         and all(type(units[k]) is int for k in units) and 0 <= units['first'] <= units['last'] <= MAX_RUN_INDEX
         and units['last'] - units['first'] < MAX_OBSERVATIONS, 'DECLARATION_SHAPE')
    if not v1:
        per_unit, method = value['observations_per_unit'], value['method_policy']
        gated = value['experiment'] in GATE_EXPERIMENTS
        need(type(per_unit) is int and (1 <= per_unit <= MAX_GATES if gated else per_unit == 1)
             and (units['last'] - units['first'] + 1) * per_unit <= MAX_OBSERVATIONS, 'DECLARATION_SHAPE')
        need((method is None and not (value['experiment'] == 'ITEM1' and value['mode'] == 'CONFIRMATORY'))
             or (value['experiment'] == 'ITEM1' and type(method) is dict and set(method) == {'path', 'sha256'}
                 and type(method['path']) is str and HEX64.match(str(method['sha256'])) is not None),
             'DECLARATION_SHAPE')
    need(value['slices'] == slices_of(units['first'], units['last'], per), 'DECLARATION_SLICES')
    reg = value['registration_sha256']
    need((reg is not None and HEX64.match(reg) is not None) == (value['mode'] == 'CONFIRMATORY'),
         'DECLARATION_SHAPE')
    s04 = value['s04_run_id']
    need((value['s04_run_id_input'] == 'CITED' and type(s04) is str and DIGITS.match(s04) is not None)
         if value['mode'] == 'CONFIRMATORY' else
         (s04 is None and value['s04_run_id_input'] in ('IGNORED_EXPLORATORY', 'NOT_GIVEN')), 'DECLARATION_SHAPE')
    run = value['run']
    need(type(run) is dict and set(run) == {'run_id', 'run_attempt', 'commit'}
         and DIGITS.match(str(run['run_id'])) is not None and DIGITS.match(str(run['run_attempt'])) is not None
         and OID.match(str(run['commit'])) is not None,
         'DECLARATION_SHAPE')
    return value


def read_declaration(path: Path) -> dict:
    return check_declaration(read_json(path, 'DECLARATION'))


def commit_file(path: str) -> None:
    """A relative path without `..` naming a file (blob) of the checkout's HEAD (`HEAD:<path>`, from the repository
    root, where the workflow runs the tool); else exit 3 `INPUT_PATH_NOT_IN_COMMIT`."""
    parts = Path(path).parts
    need(bool(path) and not Path(path).is_absolute() and '..' not in parts and '\\' not in path,
         'INPUT_PATH_NOT_IN_COMMIT', EXIT_PREREQUISITE)
    done = git_run(['cat-file', '-t', f'HEAD:{path}'], 60)
    need(done.returncode == 0 and done.stdout.strip() == 'blob', 'INPUT_PATH_NOT_IN_COMMIT', EXIT_PREREQUISITE)


# ------------------------------------------------------------------------------------------------- jobs listing

def jobs_of(path: Path, run_id: str, run_attempt: str) -> dict[str, dict]:
    """The Actions jobs listing of one run attempt, by job name (each name once)."""
    listing = read_json(path, 'JOBS')
    jobs = listing.get('jobs')
    need(type(jobs) is list and listing.get('total_count') == len(jobs) and len(jobs) <= MAX_JOBS, 'JOBS_LISTING')
    by_name: dict[str, dict] = {}
    for job in jobs:
        need(type(job) is dict and type(job.get('name')) is str, 'JOBS_LISTING')
        need(str(job.get('run_id')) == run_id and str(job.get('run_attempt')) == run_attempt, 'JOBS_RUN',
             EXIT_REFUSAL)
        need(job['name'] not in by_name, 'JOBS_DUPLICATE_NAME')
        by_name[job['name']] = job
    return by_name


def slice_job_name(number: int) -> str:
    return 'ARDR slice %d' % number   # the workflow's slice job name; the listing is matched on it


def started_at(args) -> dict:
    job = jobs_of(args.jobs, args.run_id, args.run_attempt).get(args.job_name)
    need(job is not None, 'JOB_NOT_LISTED', EXIT_REFUSAL)
    utc = job.get('started_at')
    epoch(utc)
    return {'started_at': utc}


# ---------------------------------------------------------------------------------------------------- S04 rule

def git_run(args: list[str], seconds: int) -> subprocess.CompletedProcess:
    """One git call. A git that does not answer in time is a missing prerequisite (exit 3 `GIT_TIMEOUT`, U4
    LATENT), not an internal error: the call is not repeated and no state is read from it."""
    try:
        return subprocess.run(['git', *args], capture_output=True, text=True, timeout=seconds, check=False)
    except subprocess.TimeoutExpired:
        raise Refusal('GIT_TIMEOUT', EXIT_PREREQUISITE) from None


def git(*args: str) -> str:
    done = git_run(list(args), 120)
    need(done.returncode == 0, 'GIT', EXIT_PREREQUISITE)
    return done.stdout


def s04_refuse(condition: bool, code: str) -> None:
    need(condition, code, EXIT_REFUSAL)


def s04_run(folder: Path, run_id: str, commit: str) -> dict:
    """The cited run as the Actions API answered (`run.json`, saved by the plan job): a completed, successful push
    run of the rx02 workflow on main whose head is on the slice commit's first-parent history (ancestor or
    equal), so the record was judged on a commit the slice commit descends from."""
    run = read_json(folder / 'run.json', 'S04_RUN')
    s04_refuse(DIGITS.match(run_id) is not None and str(run.get('id')) == run_id, 'S04_RUN_ID')
    s04_refuse(run.get('path') == S04_WORKFLOW_PATH, 'S04_RUN_WORKFLOW')
    s04_refuse(run.get('event') == 'push', 'S04_RUN_EVENT')
    s04_refuse(run.get('head_branch') == 'main', 'S04_RUN_BRANCH')
    s04_refuse(run.get('status') == 'completed' and run.get('conclusion') == 'success', 'S04_RUN_NOT_SUCCESS')
    attempt = run.get('run_attempt')
    s04_refuse(type(attempt) is int and 1 <= attempt <= 999, 'S04_RUN_ATTEMPT')
    head = run.get('head_sha')
    s04_refuse(type(head) is str and OID.match(head) is not None, 'S04_RUN_HEAD')
    s04_refuse(head in git('rev-list', '--first-parent', commit).split(), 'S04_NOT_ON_SLICE_HISTORY')
    return {'run_attempt': str(attempt), 'head_sha': head, 'artifact': 's04-record-v2-%s-%d' % (run_id, attempt)}


def s04_artifact_id(folder: Path, run_id: str, attempt: str) -> str | None:
    """The record artifact (`artifacts.json`, listed by its exact name): its id when it is listed once and not
    expired, else None (the job log is read instead). More than one listed is refused."""
    name = 's04-record-v2-%s-%s' % (run_id, attempt)
    listing = read_json(folder / 'artifacts.json', 'S04_ARTIFACTS')
    items = listing.get('artifacts')
    s04_refuse(type(items) is list and listing.get('total_count') == len(items) and len(items) <= MAX_JOBS,
               'S04_ARTIFACT_LISTING')
    named = [item for item in items if type(item) is dict and item.get('name') == name]
    s04_refuse(len(named) == len(items) and len(named) <= 1, 'S04_ARTIFACT_LISTING')
    if not named or named[0].get('expired') is not False:
        return None
    s04_refuse(DIGITS.match(str(named[0].get('id'))) is not None, 'S04_ARTIFACT_LISTING')
    return str(named[0]['id'])


def s04_job_id(folder: Path, run_id: str, attempt: str) -> str:
    """The record job of the cited run attempt (`jobs.json`), by its exact name, listed once."""
    jobs = jobs_of(folder / 'jobs.json', run_id, attempt)
    job = jobs.get(S04_JOB_NAME)
    s04_refuse(job is not None and DIGITS.match(str(job.get('id'))) is not None, 'S04_JOB_NOT_LISTED')
    return str(job['id'])


def zip_single(path: Path, member: str, code: str, exit_code: int) -> bytes:
    """The one member of a bounded zip, by exact name; any other shape is refused."""
    need(path.stat().st_size <= ZIP_LIMIT, code + '_SIZE', exit_code)
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            need(len(infos) == 1 and infos[0].filename == member and infos[0].file_size <= JSON_LIMIT,
                 code + '_ZIP', exit_code)
            with archive.open(infos[0]) as handle:
                blob = handle.read(JSON_LIMIT + 1)
    except zipfile.BadZipFile:
        raise Refusal(code + '_ZIP', exit_code) from None
    need(len(blob) <= JSON_LIMIT, code + '_ZIP', exit_code)
    return blob


def s04_record_from_log(blob: bytes) -> bytes:
    """The record bytes the record job printed (`cat` of the one-line record), checked against the `sha256sum`
    line the same step printed right after it. Exactly one printed record line."""
    lines = [line[:-1] if line.endswith(b'\r') else line for line in blob.split(b'\n')]
    texts = [match.group(1) if match else None for match in map(LOG_LINE.match, lines)]
    found = []
    for index, text in enumerate(texts):
        if text is None or not text.startswith(b'{'):
            continue
        try:
            value = strict_json_bytes(text)
        except (ValueError, UnicodeDecodeError, RecursionError):
            continue
        if type(value) is dict and value.get('schema') == S04_SCHEMA:
            found.append(index)
    s04_refuse(len(found) <= 1, 'S04_JOB_LOG_AMBIGUOUS')
    need(len(found) == 1, 'S04_RECORD_MISSING', EXIT_PREREQUISITE)
    raw = texts[found[0]] + b'\n'
    after = texts[found[0] + 1] if found[0] + 1 < len(texts) else None
    sha = SHA_LINE.match(after) if after is not None else None
    need(sha is not None and sha.group(1).decode('ascii') == hashlib.sha256(raw).hexdigest(), 'S04_RECORD_MISSING',
         EXIT_PREREQUISITE)
    return raw


def s04_record_bytes(folder: Path, run_id: str, attempt: str) -> tuple[bytes, str]:
    """The artifact wins: when it is listed and not expired its zip is the record and the log is not read (a
    missing zip then is exit 3, never a fallback). Only an artifact that is not listed or expired falls back to
    the record job's log."""
    if s04_artifact_id(folder, run_id, attempt) is not None:
        need((folder / 'record.zip').is_file(), 'S04_RECORD_MISSING', EXIT_PREREQUISITE)
        return zip_single(folder / 'record.zip', S04_MEMBER, 'S04_ARTIFACT', EXIT_REFUSAL), 'ARTIFACT'
    s04_job_id(folder, run_id, attempt)
    blob = read_bytes(folder / 'job.log', S04_LOG_LIMIT, 'S04_RECORD_MISSING')
    return s04_record_from_log(blob), 'JOB_LOG'


def s04_derive(folder: Path, run_id: str, commit: str) -> dict:
    """Section 1 of A's request, from the files the plan job saved (no network here): the cited run, its record
    (artifact, else job log), the record's verdict and commit, and every subject's object id at the slice commit
    (`git rev-parse`; no subject's bytes are read)."""
    run = s04_run(folder, run_id, commit)
    raw, source = s04_record_bytes(folder, run_id, run['run_attempt'])
    try:
        record = strict_json_bytes(raw)
    except (ValueError, UnicodeDecodeError, RecursionError):
        raise Refusal('S04_RECORD_JSON', EXIT_REFUSAL) from None
    s04_refuse(type(record) is dict and record.get('schema') == S04_SCHEMA, 'S04_RECORD_SCHEMA')
    s04_refuse(record.get('s04') == 'PASS_CLASS_T', 'S04_NOT_PASS')
    s04_refuse(record.get('commit') == run['head_sha'], 'S04_RECORD_COMMIT')
    fields = record.get('run')
    s04_refuse(type(fields) is dict and fields.get('event') == 'push' and fields.get('ref') == 'refs/heads/main'
               and fields.get('run_id') == run_id and fields.get('run_attempt') == run['run_attempt']
               and fields.get('commit') == run['head_sha'], 'S04_RECORD_RUN')
    oids = record.get('subject_oids')
    s04_refuse(type(oids) is dict and 0 < len(oids) <= 4096, 'S04_RECORD_SCHEMA')
    for subject, oid in sorted(oids.items()):
        s04_refuse(OID.match(str(oid)) is not None, 'S04_RECORD_SCHEMA')
        done = git_run(['rev-parse', '--verify', '--quiet', f'{commit}:{subject}'], 60)
        s04_refuse(done.returncode == 0 and done.stdout.strip() == oid, 'S04_SUBJECTS_CHANGED')
    return {'record_sha256': hashlib.sha256(raw).hexdigest(), 'record_source': source, 's04_run_id': run_id,
            's04_run_attempt': run['run_attempt'], 's04_head_sha': run['head_sha'], 'subjects': len(oids)}


def s04_cli_run_id(args) -> dict:
    return {'run_id': read_declaration(args.declaration)['s04_run_id']}


def s04_cli_run(args) -> dict:
    return s04_run(args.dir, args.s04_run_id, args.commit)


def s04_cli_artifact(args) -> dict:
    return {'id': s04_artifact_id(args.dir, args.s04_run_id, args.run_attempt)}


def s04_cli_job(args) -> dict:
    return {'id': s04_job_id(args.dir, args.s04_run_id, args.run_attempt)}


def s04_cite(args) -> dict:
    """The plan job's citation, written for the slice jobs next to the files it was derived from."""
    declaration = read_declaration(args.declaration)
    if declaration['mode'] != 'CONFIRMATORY':
        return {'s04': 'NOT_CITED_' + declaration['mode']}
    citation = s04_derive(args.dir, declaration['s04_run_id'], declaration['run']['commit'])
    write_new(args.dir / 'citation.json', dumps(citation))
    return {'s04': citation['record_source'], 'record_sha256': citation['record_sha256']}


def check_citation(value, declaration: dict) -> dict:
    """A citation's shape (`s04-cite` writes it), naming the S04 run the declaration names."""
    need(type(value) is dict and set(value) == S04_CITATION_KEYS and value['record_source'] in S04_SOURCES
         and HEX64.match(str(value['record_sha256'])) is not None and OID.match(str(value['s04_head_sha'])) is not None
         and type(value['s04_run_attempt']) is str and DIGITS.match(value['s04_run_attempt']) is not None
         and type(value['subjects']) is int and value['subjects'] > 0, 'S04_CITATION_SHAPE')
    need(value['s04_run_id'] == declaration['s04_run_id'], 'S04_CITATION_RUN', EXIT_REFUSAL)
    return value


def s04_slice_citation(folder: Path | None, declaration: dict) -> dict:
    """A slice carries the citation the plan job derived (`citation.json` of artifact `ardr-s04`), checked for
    shape and run id only: no git or API derivation here, so no S04 refusal can happen after a slice job
    started."""
    need(folder is not None, 'S04_CITATION_UNAVAILABLE', EXIT_PREREQUISITE)
    return check_citation(read_json(folder / 'citation.json', 'S04_CITATION'), declaration)


# -------------------------------------------------------------------------------------------------------- slice

def file_sha256(path: Path) -> str:
    digest, size = hashlib.sha256(), 0
    with open(path, 'rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            size += len(block)
            need(size <= LOG_LIMIT, 'RAW_LOG_SIZE')
            digest.update(block)
    return digest.hexdigest()


def parse_line(line: bytes):
    """One raw-log line as a JSON object, or None when it does not parse (a line cut by a kill)."""
    try:
        value = strict_json_bytes(line)
    except (ValueError, UnicodeDecodeError, RecursionError):
        return None
    return value if type(value) is dict else None


GATE_EVENTS = ('GATE_START', 'GATE_END')
# U3 Part C: the U2 lines collect reads, by event, in the same one pass (never the whole log in memory).
CLUSTER_KEYS = ('seq', 'prefix', 'gates', 'exit', 'output_bytes')   # what a CLUSTER_TOOL line keeps (not truth)
PRODUCER_LABEL = re.compile(r'PRODUCER_H(0|[1-9][0-9]{0,8})\Z')


def block_producer_tags(block_hex) -> list | None:
    """The producer tags of a pool BLOCK line's coinbase, read from its `block_hex` by the campaign's own reader
    (`coinbase_producers`, imported only when a pool block is met), or None when the bytes do not parse."""
    import claude_track_ardr_campaign as campaign   # noqa: PLC0415 - only a pool log needs it
    try:
        return campaign.coinbase_producers(block_hex) if type(block_hex) is str else None
    except Exception:   # noqa: BLE001 - bytes that do not parse rebuild nothing (the gate is EXCLUDED)
        return None


class RawScan:
    """One pass over a whole raw log (U3, A's 256 MiB bound): its SHA-256, its first and last lines (None when
    it does not parse), whether any line between them does not parse, and the gate lines and RUN_END line an
    ITEM1 or POOL run's gate states are read from. The size is checked before the first byte is read and again
    while reading (a file that grows), so at most LOG_LIMIT bytes are ever read: exit 2 `RAW_LOG_SIZE`."""

    def __init__(self, path: Path):
        need(path.is_file() and not path.is_symlink() and path.stat().st_size <= LOG_LIMIT, 'RAW_LOG_SIZE')
        digest, size, count = hashlib.sha256(), 0, 0
        self.first = self.last = self.before_last = None
        self.cut_inside = False   # a line that does not parse and is not the last one
        self.gate_lines: list[dict] = []
        # U3 Part C: PREFIX_START lines, CLUSTER_TOOL lines (CLUSTER_KEYS only) and, per pool GATE_END (by its
        # seq), whether the gate's judgement inputs rebuild from the lines before it (A Q6).
        self.prefix_starts: list[dict] = []
        self.cluster_tools: list[dict] = []
        self.pool_rebuilt: dict[int, bool] = {}
        blocks: dict[str, list] = {}   # pool block hash -> [(height, producer, tags)], tags read from block_hex
        draws: dict[str, list] = {}    # PRODUCER_H<height> -> [producer]
        ended_hashes: set = set()      # the block hashes earlier pool GATE_END lines named (one per gate)
        # U3 pre-PR P3-1: a line after the first RUN_END (a second RUN_END included), or a `seq` that does not
        # run 1, 2, ... over the lines, is a log the driver does not write (collect: exit 6 `RAW_LOG_GATES`).
        # #713: so is a pool GATE_END (with `producer_tags`) whose `seq` is not an integer or whose `block_hash`
        # is not a string, or a pool BLOCK (with `producer`) whose `block_hash` is not a string: refused here,
        # exit 6 `RAW_LOG_GATES`, since those values are used as dict keys and set elements below.
        # P3-3: the `t_ns` of the line right after the last GATE_END (the deadline stop is read from it).
        self.after_end, self.seq_ok, self.t_after_gate_end = False, True, None
        ended = after = False
        with open(path, 'rb') as handle:
            for line in handle:
                size += len(line)
                need(size <= LOG_LIMIT, 'RAW_LOG_SIZE')
                digest.update(line)
                text = line.rstrip(b'\n')
                if not text:
                    continue
                row = parse_line(text)
                if count and self.last is None:
                    self.cut_inside = True
                self.after_end = self.after_end or ended
                if row is not None and row.get('seq') != count + 1:
                    self.seq_ok = False
                event = row.get('event') if row is not None else None
                ended = ended or event == 'RUN_END'
                if after:
                    self.t_after_gate_end, after = (row or {}).get('t_ns'), False
                if event in GATE_EVENTS:
                    self.gate_lines.append(row)
                    after = event == 'GATE_END'
                    if event == 'GATE_END' and 'producer_tags' in row:
                        # #713: `seq` keys a dict and `block_hash` joins a set here, so a list or object value
                        # (a log the driver does not write) is refused by name, never a TypeError.
                        need(type(row.get('seq')) is int, 'RAW_LOG_GATES', EXIT_REFUSAL)
                        need(type(row.get('block_hash')) is str, 'RAW_LOG_GATES', EXIT_REFUSAL)
                        self.pool_rebuilt[row['seq']] = pool_gate_rebuilt(row, blocks, draws, ended_hashes)
                        ended_hashes.add(row['block_hash'])
                elif event == 'PREFIX_START':
                    self.prefix_starts.append(row)
                elif event == 'CLUSTER_TOOL':
                    self.cluster_tools.append({k: row.get(k) for k in CLUSTER_KEYS})
                elif event == 'BLOCK' and 'producer' in row:
                    need(type(row.get('block_hash')) is str, 'RAW_LOG_GATES', EXIT_REFUSAL)   # #713: a dict key
                    blocks.setdefault(row['block_hash'], []).append(
                        (row.get('height'), row.get('producer'), block_producer_tags(row.get('block_hex'))))
                elif event == 'DRAW' and type(row.get('label')) is str and PRODUCER_LABEL.match(row['label']):
                    draws.setdefault(row['label'], []).append(row.get('producer'))
                self.before_last, self.last = self.last, row
                if not count:
                    self.first = row
                count += 1
        self.sha256 = digest.hexdigest()
        self.written = count > 0


def pool_gate_rebuilt(end: dict, blocks: dict, draws: dict, ended_hashes: set) -> bool:
    """A pool gate's judgement inputs rebuild from the log lines before its GATE_END alone (A Q6; section 16
    POOL): exactly one BLOCK line with the GATE_END's `block_hash`, at the GATE_END's `height` (block G of this
    gate) and named by no earlier GATE_END of the run (U3 pre-PR P3-2), whose coinbase producer tags (read
    from its `block_hex`) equal the GATE_END's `producer_tags`, and exactly one DRAW `PRODUCER_H<height>` line
    for that height whose `producer` is the BLOCK's."""
    tags = end.get('producer_tags')
    if not (type(tags) is list and all(type(t) is str for t in tags)):
        return False
    block_hash = end.get('block_hash')
    found = blocks.get(block_hash) if type(block_hash) is str and block_hash not in ended_hashes else None
    if not found or len(found) != 1:
        return False
    height, producer, rebuilt = found[0]
    if not (type(height) is int and height == end.get('height')):
        return False
    drawn = draws.get(f'PRODUCER_H{height}')
    return rebuilt is not None and rebuilt == tags and drawn is not None and drawn == [producer]


def raw_log_bounds(path: Path) -> tuple[dict | None, dict | None, bool]:
    """The raw log's first and last lines and whether it holds any byte. (None, None, False) when the driver wrote
    nothing; a line that does not parse is None (the caller decides whether that is a truncation)."""
    if not path.exists():
        return None, None, False
    scan = RawScan(path)
    return scan.first, scan.last, scan.written


def unit_state(code: int, out: dict | None, first: dict | None, last: dict | None, expect: dict,
               written: bool = True) -> tuple[str, str]:
    """BEFORE_START when the driver wrote no line (it refused before RUN_START); OBSERVED when the log runs
    RUN_START .. RUN_END DONE and the driver ended 0; EXCLUDED for every other started unit. A log cut by a kill
    (UNIT_TIMEOUT with any line that does not parse, or a parsed first line and a last line that does not) is
    EXCLUDED `RAW_LOG_TRUNCATED`: the unit may have been observed."""
    timeout = (out or {}).get('code') == 'UNIT_TIMEOUT'
    if not written:
        return 'BEFORE_START', (out or {}).get('code') or 'NO_RAW_LOG'
    if first is None:
        need(timeout, 'RAW_LOG_JSON')
        return 'EXCLUDED', 'RAW_LOG_TRUNCATED'
    need(first.get('schema') == RAW_SCHEMA and first.get('event') == 'RUN_START' and first.get('seq') == 1,
         'RAW_LOG_START')
    for key, value in expect.items():
        need(first.get(key) == value, 'RAW_LOG_' + key.upper(), EXIT_REFUSAL)
    if last is None:
        return 'EXCLUDED', 'RAW_LOG_TRUNCATED'
    done = code == 0 and last.get('event') == 'RUN_END' and last.get('status') == 'DONE'
    return ('OBSERVED', 'DONE') if done else ('EXCLUDED', (out or {}).get('code') or 'RUN_NOT_DONE')


def driver_code(stdout: str) -> dict | None:
    lines = stdout.strip().splitlines()
    try:
        value = json.loads(lines[-1]) if lines else None
    except ValueError:
        return None
    if type(value) is not dict:
        return None
    code = value.get('code')
    return {'code': code if type(code) is str and CODE_WORD.match(code) else None}


def run_unit(command: list[str], seconds: int) -> tuple[int, dict | None]:
    """The driver in its own process group; at the unit's limit the whole group (the driver, its nodes and its
    miner process) is killed. The driver's stderr is not kept (it can hold a node's message or a path)."""
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                               start_new_session=True)
    try:
        stdout, _ = process.communicate(timeout=seconds)
        return process.returncode, driver_code(stdout)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, 9)
        process.communicate()
        return EXIT_INTERNAL, {'code': 'UNIT_TIMEOUT'}


def begin_record(declaration: dict, number: int, mode: str, commit: str) -> dict:
    """The slice record before anything ran: every unit BEFORE_START, no policy hash, citation or start time yet."""
    # The slice runs the declared mode; PR_SMOKE is the pull-request job's EXPLORATORY slice.
    need(mode == declaration['mode'] or (mode == 'PR_SMOKE' and declaration['mode'] == 'EXPLORATORY'), 'SLICE_MODE')
    spec = [s for s in declaration['slices'] if s['slice'] == number]
    need(len(spec) == 1, 'SLICE_NUMBER')
    # A checkout of another commit writes no record; the collector reads the skipped units step (BEFORE_START).
    need(commit == declaration['run']['commit'], 'SLICE_COMMIT', EXIT_REFUSAL)
    experiment = declaration['experiment']
    return {
        'schema': SLICE_SCHEMA, 'mode': mode, 'evidence_status': evidence_status(mode), 'experiment': experiment,
        'slice': number, 'job_name': slice_job_name(number), 'slice_commit': commit, 'run': declaration['run'],
        'policy_sha256': None, 'registration_sha256': declaration['registration_sha256'], 's04': None,
        'started_at': None, 'labels': LABELS,
        'units': [{'unit': unit_id(experiment, r), 'state': 'BEFORE_START', 'code': None, 'exit': None,
                   'raw_log': None, 'raw_log_sha256': None} for r in range(spec[0]['first'], spec[0]['last'] + 1)]}


def slice_begin(args) -> dict:
    """The slice job's first tool step, before the Core fetch and the token step (ARDR_RUN_V1 section 13)."""
    declaration = read_declaration(args.declaration)
    record = begin_record(declaration, args.slice, args.mode, git('rev-parse', 'HEAD').strip())
    try:   # an existing directory is exit 3 like an existing output; one that cannot be made is exit 4
        args.out_dir.mkdir(mode=0o700, parents=False, exist_ok=False)
    except FileExistsError:
        raise Refusal('OUTPUT_EXISTS', EXIT_PREREQUISITE) from None
    except OSError:
        raise Refusal('OUTPUT_WRITE_FAILED', EXIT_INTERNAL) from None
    write_new(args.out_dir / 'slice-record.json', dumps(record))
    return {'slice': args.slice, 'units': len(record['units']), 'states': [u['state'] for u in record['units']]}


def slice_start(args, mode: str, declaration: dict) -> dict:
    """The slice's start time: this job's server `started_at` (Q9), from `--jobs` or `--started-at`; a slice
    outside a dispatch (the PR smoke, a local run) may use the local clock, never a CONFIRMATORY one."""
    if args.jobs is not None:
        run = declaration['run']
        utc = started_at(argparse.Namespace(jobs=args.jobs, run_id=str(run['run_id']),
                                            run_attempt=str(run['run_attempt']),
                                            job_name=slice_job_name(args.slice)))['started_at']
        need(args.started_at is None or args.started_at == utc, 'STARTED_AT', EXIT_REFUSAL)
        return {'source': 'GITHUB_JOB_STARTED_AT', 'utc': utc}
    if args.started_at is not None:
        epoch(args.started_at)
        return {'source': 'GITHUB_JOB_STARTED_AT', 'utc': args.started_at}
    need(mode != 'CONFIRMATORY', 'STARTED_AT_MISSING', EXIT_PREREQUISITE)
    return {'source': 'LOCAL_EXPLORATORY', 'utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}


def check_method_policy(declaration: dict, policy: bytes) -> None:
    """U3 (A Q3): before any unit starts, the policy's ITEM1 or POOL entry still names the declared gates per run
    and method policy, and the method policy file at that path still has the declared SHA-256; else exit 6
    `OBSERVATIONS_PER_UNIT_CHANGED` / `METHOD_POLICY_CHANGED` and every unit stays BEFORE_START."""
    experiment, mode, declared = declaration['experiment'], declaration['mode'], declaration['method_policy']
    if experiment in GATE_EXPERIMENTS:
        entry = policy_entry(policy, experiment)
        need(observations_per_unit(entry, experiment, mode) == declaration['observations_per_unit'],
             'OBSERVATIONS_PER_UNIT_CHANGED', EXIT_REFUSAL)
        need(declared_method_policy(entry, experiment, mode) == declared, 'METHOD_POLICY_CHANGED', EXIT_REFUSAL)
    if declared is not None:
        blob = read_bytes(Path(declared['path']), JSON_LIMIT, 'METHOD_POLICY_UNAVAILABLE')
        need(hashlib.sha256(blob).hexdigest() == declared['sha256'], 'METHOD_POLICY_CHANGED', EXIT_REFUSAL)


def slice_run(args) -> dict:
    """One slice: the record `slice-begin` wrote; then the work root (absolute), the policy and the method policy
    (U3), the start time and the S04 citation (CONFIRMATORY), a refusal of which leaves every unit BEFORE_START;
    then each unit under the driver."""
    clock = time.monotonic()
    declaration = read_declaration(args.declaration)
    mode = args.mode
    commit = git('rev-parse', 'HEAD').strip()
    record = begin_record(declaration, args.slice, mode, commit)
    path = args.out_dir / 'slice-record.json'
    begun = read_bytes(path, JSON_LIMIT, 'SLICE_RECORD_NOT_BEGUN')
    need(begun == dumps(record), 'SLICE_RECORD_NOT_BEGUN', EXIT_REFUSAL)
    try:
        # U4 LATENT: the root of every unit's `--work` is absolute, checked before it is made (the driver's needle
        # is the work path as given).
        need(args.work_root.is_absolute(), 'WORK_ROOT_NOT_ABSOLUTE')
        policy = read_bytes(Path(declaration['policy_path']), JSON_LIMIT, 'POLICY_UNAVAILABLE')
        check_method_policy(declaration, policy)
        start = slice_start(args, mode, declaration)
        citation = s04_slice_citation(args.s04_dir, declaration) if mode == 'CONFIRMATORY' else None
    except Refusal as refusal:
        for entry in record['units']:   # nothing ran: every unit stays BEFORE_START and says why
            entry['code'] = refusal.code
        replace(path, dumps(record))
        raise
    experiment, registration = declaration['experiment'], declaration['registration_sha256']
    record.update(policy_sha256=hashlib.sha256(policy).hexdigest(), s04=citation, started_at=start)
    replace(path, dumps(record))
    args.work_root.mkdir(mode=0o700, parents=False, exist_ok=False)   # each unit's driver makes its own dir in it
    budget = (SLICE_MINUTES - UPLOAD_MINUTES) * 60 - args.spent_seconds
    stop = None
    for entry in record['units']:
        run = entry['unit']['run']
        if time.monotonic() - clock + declaration['unit_minutes'] * SECONDS_PER_MINUTE > budget:
            stop = 'SLICE_BUDGET_LEFT_UNITS_BEFORE_START'
            break
        log = args.out_dir / f'raw-{run}.jsonl'
        entry.update(state='IN_PROGRESS', raw_log=log.name)
        replace(path, dumps(record))
        command = [sys.executable, str(DRIVER), 'run', '--mode', mode, '--policy', declaration['policy_path'],
                   '--experiment', experiment, '--run-index', str(run), '--node-a', str(args.node_a),
                   '--node-b', str(args.node_b), '--work', str(args.work_root / f'unit-{run}'), '--out', str(log)]
        # U3 (A Q5): the unit's limit, from which the driver fixes its gate-loop deadline in RUN_START.
        command += ['--unit-seconds', str(declaration['unit_minutes'] * SECONDS_PER_MINUTE)]
        if declaration['method_policy'] is not None:   # U3 (A Q3): the declared file, re-hashed above
            command += ['--method-policy', declaration['method_policy']['path']]
        if mode == 'CONFIRMATORY':
            command += ['--started-at', start['utc'], '--registration', declaration['registration_path'],
                        '--registration-sha256', registration]
        elif start['source'] == 'GITHUB_JOB_STARTED_AT':
            command += ['--started-at', start['utc']]
        code, out = run_unit(command, declaration['unit_minutes'] * SECONDS_PER_MINUTE)
        scan = RawScan(log) if log.exists() else None
        first, last, written = (scan.first, scan.last, scan.written) if scan is not None else (None, None, False)
        expect = {'mode': mode, 'evidence_status': evidence_status(mode), 'policy_sha256': record['policy_sha256'],
                  'registration_sha256': registration if mode == 'CONFIRMATORY' else None,
                  'unit': entry['unit']}
        state, unit_code = unit_state(code, out, first, last, expect, written)
        entry.update(state=state, code=unit_code, exit=code,
                     raw_log=log.name if written else None,
                     raw_log_sha256=scan.sha256 if written else None)
        replace(path, dumps(record))
        if state == 'BEFORE_START':   # the driver refused before any observation: nothing later can start either
            return {'slice': args.slice, 'stopped': unit_code, 'exit': code if code in (2, 3, 5, 6) else EXIT_INTERNAL,
                    'states': [u['state'] for u in record['units']]}
    return {'slice': args.slice, 'stopped': stop, 'exit': 0, 'states': [u['state'] for u in record['units']]}


def check_slice_record(value: dict) -> dict:
    """The record's shape. A record whose units are all BEFORE_START may lack the policy hash, the start time and
    the citation (the slice stopped before them); a record with a started unit has all three."""
    keys = {'schema', 'mode', 'evidence_status', 'experiment', 'slice', 'job_name', 'slice_commit', 'run',
            'policy_sha256', 'registration_sha256', 's04', 'started_at', 'labels', 'units'}
    need(set(value) == keys and value['schema'] == SLICE_SCHEMA and value['mode'] in MODES
         and value['evidence_status'] == evidence_status(value['mode']), 'SLICE_RECORD_SHAPE')
    need(type(value['units']) is list and 0 < len(value['units']) <= MAX_OBSERVATIONS, 'SLICE_RECORD_SHAPE')
    for entry in value['units']:
        need(type(entry) is dict and set(entry) == {'unit', 'state', 'code', 'exit', 'raw_log', 'raw_log_sha256'}
             and entry['state'] in STATES and type(entry['unit']) is dict
             and (entry['exit'] is None or type(entry['exit']) is int)
             # #713 round 2: `code` keys the collect summary's `exit_5` table: null or a code word, as slice writes
             and (entry['code'] is None or (type(entry['code']) is str and CODE_WORD.match(entry['code']) is not None)),
             'SLICE_RECORD_SHAPE')
    started = any(entry['state'] != 'BEFORE_START' for entry in value['units'])
    start, s04 = value['started_at'], value['s04']
    if start is not None or started:
        need(type(start) is dict and set(start) == {'source', 'utc'}
             and start['source'] in ('GITHUB_JOB_STARTED_AT', 'LOCAL_EXPLORATORY'), 'SLICE_RECORD_SHAPE')
        epoch(start['utc'])
    need(type(value['policy_sha256']) is str or (value['policy_sha256'] is None and not started),
         'SLICE_RECORD_SHAPE')
    if value['mode'] == 'CONFIRMATORY':
        need(HEX64.match(str(value['registration_sha256'])) is not None, 'SLICE_RECORD_SHAPE')
        need(start is None or start['source'] == 'GITHUB_JOB_STARTED_AT', 'SLICE_RECORD_SHAPE')
        if s04 is not None or started:
            need(type(s04) is dict and set(s04) == S04_CITATION_KEYS and s04['record_source'] in S04_SOURCES
                 and HEX64.match(str(s04['record_sha256'])) is not None
                 and OID.match(str(s04['s04_head_sha'])) is not None, 'SLICE_RECORD_SHAPE')
    else:
        need(s04 is None, 'SLICE_RECORD_SHAPE')
    return value


# ------------------------------------------------------------------------------------------------------ collect

def check_raw_log(folder: Path, entry: dict) -> RawScan | None:
    """A unit's raw log as the slice artifact holds it: none for BEFORE_START; for OBSERVED and EXCLUDED the file
    `raw-<run>.jsonl` with the recorded SHA-256, read whole once (at most 256 MiB, U3); an OBSERVED unit's log
    runs RUN_START (this unit) .. RUN_END DONE. An IN_PROGRESS unit (the job was lost while its driver ran) is
    EXCLUDED whatever its log holds, and its log is not read. Returns the scan of a log that was read."""
    name = 'raw-%d.jsonl' % entry['unit']['run']
    if entry['state'] == 'BEFORE_START':
        need(entry['raw_log'] is None and entry['raw_log_sha256'] is None, 'SLICE_RECORD_RAW_LOG', EXIT_REFUSAL)
        return None
    need(entry['raw_log'] == name, 'SLICE_RECORD_RAW_LOG', EXIT_REFUSAL)
    if entry['state'] == 'IN_PROGRESS':
        return None
    path = folder / name
    need(path.is_file() and not path.is_symlink(), 'RAW_LOG_MISSING', EXIT_PREREQUISITE)
    scan = RawScan(path)
    need(entry['raw_log_sha256'] == scan.sha256, 'RAW_LOG_SHA256', EXIT_REFUSAL)
    if entry['state'] == 'OBSERVED':
        first, last = scan.first, scan.last
        need(first is not None and last is not None and first.get('schema') == RAW_SCHEMA
             and first.get('event') == 'RUN_START' and first.get('seq') == 1 and first.get('unit') == entry['unit']
             and last.get('event') == 'RUN_END' and last.get('status') == 'DONE', 'RAW_LOG_NOT_DONE', EXIT_REFUSAL)
    return scan


def gate_entry(gate: int, state: str, code: str | None) -> dict:
    return {'gate': gate, 'state': state, 'code': code, 'observation_id': None}


# U3 Part C: RUN_END FAILED's prefix outcome (campaign `PREFIX_STATUSES`, section 16's reason table). A NOT_RUN
# reason outside this set is a log the format does not describe: exit 6 `RAW_LOG_GATES`. Every NOT_RUN and
# FAILED outcome excludes every started gate of an ITEM1 run; only OK keeps the prefix's gates.
PREFIX_STATUSES = ('OK', 'FAILED', 'NOT_RUN')
PREFIX_NOT_RUN_REASONS = ('SECRET_IN_LOG', 'LOG_BOUND', 'NO_GATE_DONE', 'NODE_A_DOWN', 'NODE_A_TIMEOUT',
                          'WORKER_TIMEOUT', 'PHASE_CLUSTER', 'PHASE_END', 'NO_CLUSTER', 'NO_OUTCOME')
DEADLINE_CODE = 'DEADLINE_REACHED'   # a gate a run stopped by its deadline did not start (A Q5: missing)


def code_word(value) -> str | None:
    return value if type(value) is str and CODE_WORD.match(value) else None


def check_prefix_outcome(run_end: dict) -> tuple[str, str | None]:
    """RUN_END FAILED's `cluster_prefix` and `cluster_prefix_reason` as section 16 lists them, else exit 6."""
    status, reason = run_end.get('cluster_prefix'), run_end.get('cluster_prefix_reason')
    need(status in PREFIX_STATUSES and ((status == 'OK' and reason is None)
                                        or (status == 'NOT_RUN' and reason in PREFIX_NOT_RUN_REASONS)
                                        or (status == 'FAILED' and code_word(reason) is not None)),
         'RAW_LOG_GATES', EXIT_REFUSAL)
    return status, reason


def prefix_gate_observed(experiment: str, run_end: dict | None, scan: RawScan, ended: list[int], total: int) -> bool:
    """U3 Part C (A Q2): whether the gates of an ITEM1 run that failed with every `GATE_END` line in `ended`
    count as OBSERVED: RUN_END FAILED phase GATES with `cluster_prefix` OK, `cluster_failed` false, and one
    PREFIX_START and one prefix CLUSTER_TOOL (`prefix` true, exit 0, output written) after it, both naming
    exactly the gates 0..g-1 that reached GATE_END, and `failed_gate` g (null when every one of the `total`
    gates reached it). Anything else (no RUN_END, a prefix FAILED or NOT_RUN, a
    phase after GATES): no gate of the run counts. POOL gates are read per gate (`pool_rebuilt`)."""
    if experiment != 'ITEM1' or run_end is None or run_end.get('status') != 'FAILED' or not ended:
        return False
    if not (run_end.get('cluster_prefix') == 'OK' and run_end.get('phase') == 'GATES'
            and run_end.get('cluster_failed') is False):
        return False
    done = list(range(len(ended)))
    tools = [t for t in scan.cluster_tools if t['prefix'] is True]
    return (ended == done and len(scan.prefix_starts) == 1 and scan.prefix_starts[0].get('gates') == done
            and len(tools) == 1 and tools[0]['gates'] == done and tools[0]['exit'] == 0
            and type(tools[0]['output_bytes']) is int and tools[0]['output_bytes'] > 0
            and type(tools[0]['seq']) is int and tools[0]['seq'] > scan.prefix_starts[0].get('seq', 0)
            and run_end.get('failed_gate') == (len(ended) if len(ended) < total else None))


def gate_counts(gates: list[dict], info: dict) -> dict:
    """A run's gate counts (U3 Part C, A Q2): OBSERVED, EXCLUDED, missing (NOT_STARTED), the death cause and g,
    the prefix outcome, `prefix` (gates counted from a failed run's prefix D2-2), the deadline, and the 10%
    rule's input (missing + EXCLUDED, flagged when above a tenth of the run's gates: 20 of 200). The collection
    reports; the judge makes the NOT_ESTABLISHED call."""
    count = {s: sum(g['state'] == s for g in gates) for s in GATE_STATES}
    lost = count['EXCLUDED'] + count['NOT_STARTED']
    return {'gates': len(gates), 'observed': count['OBSERVED'], 'excluded': count['EXCLUDED'],
            'missing': count['NOT_STARTED'], 'missing_or_excluded': lost, 'over_10_percent': lost * 10 > len(gates),
            **info}


def check_deadline(deadline, unit_seconds: int, confirmatory: bool) -> None:
    """RUN_START's `deadline` (U3 pre-PR P3-3): the driver's for this declaration's unit limit (`unit_seconds`
    = unit_minutes x 60, the share 5,700, the margin 900, the gate loop the rest, an integer `clock_ns`), or null
    only outside CONFIRMATORY; else exit 6 `RAW_LOG_GATES`."""
    if deadline is None:
        need(not confirmatory, 'RAW_LOG_GATES', EXIT_REFUSAL)
        return
    need(type(deadline) is dict and deadline.get('unit_seconds') == unit_seconds
         and deadline.get('d2_2_share_seconds') == D2_2_SHARE_SECONDS
         and deadline.get('margin_seconds') == DEADLINE_MARGIN_SECONDS
         and deadline.get('gate_loop_seconds') == unit_seconds - DEADLINE_RESERVE_SECONDS
         and type(deadline.get('clock_ns')) is int, 'RAW_LOG_GATES', EXIT_REFUSAL)


def deadline_stop(scan: RawScan, run_end: dict, gates: list[int], ended: list[int], started: set) -> tuple[bool, int]:
    """RUN_END DONE's deadline facts (A Q5): `deadline_reached` and `gates_not_started` (absent: false, []) must be
    the tail k..end of the gates, k >= 1, with every gate before k started and ended and none after; a stop
    needs RUN_START's deadline and the line right after the last GATE_END stamped at or after its `clock_ns`
    (P3-3). Returns (reached, k); else exit 6 `RAW_LOG_GATES`."""
    reached = run_end.get('deadline_reached', False)
    left = run_end.get('gates_not_started', [])
    k = len(gates) - len(left) if type(left) is list else -1
    deadline = scan.first.get('deadline')
    need(reached in (True, False) and type(left) is list and reached == bool(left) and 0 < k
         and left == gates[k:] and ended == gates[:k] and started == set(gates[:k])
         and (not reached or (type(deadline) is dict and type(scan.t_after_gate_end) is int
                              and scan.t_after_gate_end >= deadline['clock_ns'])), 'RAW_LOG_GATES', EXIT_REFUSAL)
    return reached, k


def unit_gates(experiment: str, run: int, per_unit: int, state: str, code: str | None,
               scan: RawScan | None, unit_seconds: int | None = None,
               confirmatory: bool = False) -> tuple[list[dict] | None, dict | None]:
    """The gate states of one ITEM1 or POOL unit (U3) and its gate counts, from its whole raw log: (None, None)
    for a BEFORE_START unit (no observation); every gate EXCLUDED with the unit's code when no log was read
    (IN_PROGRESS, a lost slice) or its first line was cut. Else RUN_START's `gates` must be the declared
    0..per_unit-1 and every GATE_START and GATE_END line must name its gate's unit and id (exit 6
    `RAW_LOG_GATES`). An OBSERVED unit has every gate's GATE_END and every gate OBSERVED, except the gates a run
    stopped by its deadline did not start (RUN_END DONE `deadline_reached`, `gates_not_started`; RUN_START must
    carry a deadline): NOT_STARTED `DEADLINE_REACHED`. In an EXCLUDED unit a gate that started (GATE_START), or
    may have started (the gate after the last GATE_START when the last line was cut by a kill), is EXCLUDED and
    any other gate NOT_STARTED, with the death cause: RUN_END FAILED's `code`, else PREFIX_START's `code`, else
    the unit's (never the slice's exit when the log names one). RUN_END FAILED's `excluded_gates` must hold every
    gate without GATE_END, and its prefix outcome must be one section 16 lists. Part C (A Q2, Q6): the gates
    that reached GATE_END count as OBSERVED in an ITEM1 run whose prefix D2-2 judged them
    (`prefix_gate_observed`), and in a POOL run each gate not in `excluded_gates` whose judgement inputs rebuild
    from the lines before its GATE_END (`pool_rebuilt`; a truncated log so counts to its last whole GATE_END).
    A line that does not parse before the last one is exit 2 `RAW_LOG_JSON`."""
    if state == 'BEFORE_START':
        return None, None
    gates = list(range(per_unit))
    info = {'cause': None, 'failed_gate': None, 'cluster_prefix': None, 'cluster_prefix_reason': None,
            'prefix': False, 'deadline_reached': False}
    if scan is None or scan.first is None:
        out = [gate_entry(g, 'EXCLUDED', code) for g in gates]
        return out, gate_counts(out, info)
    need(not scan.cut_inside, 'RAW_LOG_JSON')
    need(scan.first.get('gates') == gates and not scan.after_end and scan.seq_ok, 'RAW_LOG_GATES', EXIT_REFUSAL)
    check_deadline(scan.first.get('deadline'), unit_seconds, confirmatory)
    clock = (scan.first.get('deadline') or {}).get('clock_ns')
    started, ended, ends = set(), [], {}
    for line in scan.gate_lines:
        g = line.get('gate')
        need(type(g) is int and g in gates and line.get('observation_id') == gate_observation_id(experiment, run, g)
             and line.get('unit') == {'cohort': None, 'experiment': experiment, 'gate': g, 'run': run},
             'RAW_LOG_GATES', EXIT_REFUSAL)
        if line['event'] == 'GATE_START':
            need(g not in started and set(started) == set(range(g)), 'RAW_LOG_GATES', EXIT_REFUSAL)   # in order
            # P3-3: with a deadline, every gate started before it (GATE_START carries the clock reading checked)
            need(clock is None or (type(line.get('t_ns')) is int and line['t_ns'] < clock), 'RAW_LOG_GATES',
                 EXIT_REFUSAL)
            started.add(g)
        else:
            need(g in started and g not in ends and line.get('status') == 'OBSERVED', 'RAW_LOG_GATES', EXIT_REFUSAL)
            ended.append(g)
            ends[g] = line
    last = scan.last
    run_end = last if last is not None and last.get('event') == 'RUN_END' else None
    if state == 'OBSERVED':
        reached, k = deadline_stop(scan, run_end, gates, ended, started)
        out = [gate_entry(g, 'OBSERVED', 'DONE') if g < k else gate_entry(g, 'NOT_STARTED', DEADLINE_CODE)
               for g in gates]
        return out, gate_counts(out, dict(info, deadline_reached=reached))
    excluded, stopped_at = set(), None
    if run_end is not None and run_end.get('status') == 'DONE':
        # P3-5: RUN_END DONE in an EXCLUDED unit (the slice killed the driver in teardown, UNIT_TIMEOUT): the
        # states stay EXCLUDED; the deadline facts are read, so the gates it never started say DEADLINE_REACHED.
        reached, k = deadline_stop(scan, run_end, gates, ended, started)
        info['deadline_reached'] = reached
        stopped_at = k if reached else None
    elif run_end is not None and run_end.get('status') == 'FAILED':
        listed = run_end.get('excluded_gates')
        need(type(listed) is list and all(type(g) is int and g in gates for g in listed)
             and set(gates) - set(ended) <= set(listed), 'RAW_LOG_GATES', EXIT_REFUSAL)
        excluded = set(listed)
        status, reason = check_prefix_outcome(run_end)
        info.update(cause=code_word(run_end.get('code')), cluster_prefix=status, cluster_prefix_reason=reason,
                    failed_gate=run_end.get('failed_gate') if type(run_end.get('failed_gate')) is int else None)
    elif run_end is None and scan.prefix_starts:   # killed during the prefix: PREFIX_START names the cause
        start = scan.prefix_starts[-1]
        info.update(cause=code_word(start.get('code')),
                    failed_gate=start.get('failed_gate') if type(start.get('failed_gate')) is int else None)
    code = info['cause'] or code
    observed = set()
    if prefix_gate_observed(experiment, run_end, scan, ended, len(gates)):
        observed = set(ended)
        info['prefix'] = True
    elif experiment == 'POOL':
        observed = {g for g in ended if g not in excluded and scan.pool_rebuilt.get(ends[g].get('seq')) is True}
    maybe = (max(started) + 1 if started else 0) if last is None else None   # cut by the kill
    out = []
    for g in gates:
        if g in observed:
            out.append(gate_entry(g, 'OBSERVED', 'PREFIX' if info['prefix'] else 'REBUILT_FROM_LOG'))
        elif g in started or g == maybe:
            out.append(gate_entry(g, 'EXCLUDED', code))
        else:
            out.append(gate_entry(g, 'NOT_STARTED', DEADLINE_CODE if stopped_at is not None and g >= stopped_at
                                  else code))
    return out, gate_counts(out, info)


def job_steps(job: dict) -> list:
    steps = job.get('steps')
    need(type(steps) is list and all(type(step) is dict for step in steps), 'JOBS_LISTING')
    return steps


def step_ran(step: dict) -> bool:
    """A step may have run unless the server lists it as not started (queued, pending, waiting) or `completed`
    `skipped`; any other status or conclusion (cancelled, failure, unknown) counts as ran (fail closed)."""
    status = step.get('status')
    return not (status in ('queued', 'pending', 'waiting')
                or (status == 'completed' and step.get('conclusion') == 'skipped'))


def job_ran(job: dict | None) -> bool:
    """A job ran a step: it is listed with a started_at and at least one step that may have run. A hosted job that
    was queued and then cancelled can list a started_at with no step."""
    return job is not None and job.get('started_at') is not None and any(map(step_ran, job_steps(job)))


def units_step_skipped(job: dict) -> bool:
    """The server says the slice job's units step never ran (`skipped`): no unit of it started."""
    steps = job_steps(job)
    named = [step for step in steps if step.get('name') == UNITS_STEP]
    need(len(named) <= 1, 'JOBS_LISTING')
    return len(named) == 1 and named[0].get('status') == 'completed' and named[0].get('conclusion') == 'skipped'


def collection_of(declaration_path: Path, records: Path, jobs_path: Path | None) -> tuple[dict, bytes | None]:
    """The collection of one dispatch run and its observation list (or None), from the run's own records only: the
    declaration the plan job wrote, the slice records and raw logs the slice jobs wrote, and the server's jobs
    listing of that run attempt. `collect` writes them; `recollect` (D4-2) derives them the same way from the
    same run's artifacts."""
    declaration = read_declaration(declaration_path)
    run = declaration['run']
    jobs = jobs_of(jobs_path, str(run['run_id']), str(run['run_attempt'])) if jobs_path is not None else None
    experiment, registration = declaration['experiment'], declaration['registration_sha256']
    gated, per_unit = experiment in GATE_EXPERIMENTS, declaration['observations_per_unit']
    units, missing = [], []
    for spec in declaration['slices']:
        name = slice_job_name(spec['slice'])
        job = jobs.get(name) if jobs is not None else None
        folder = records / f'ardr-slice-{spec["slice"]}'
        path = folder / 'slice-record.json'
        expected = [unit_id(experiment, r) for r in range(spec['first'], spec['last'] + 1)]
        if not path.exists():
            # A slice that never started, or whose units step the server lists as skipped, dispatched nothing; one
            # lost after its units step began, before its upload, is all excluded: the units may have been observed.
            need(jobs is not None or declaration['mode'] != 'CONFIRMATORY', 'JOBS_LISTING_MISSING', EXIT_PREREQUISITE)
            code = 'SLICE_RECORD_MISSING'
            if not job_ran(job):   # never started, or listed with a started_at and no step that ran (P3-g)
                code = 'SLICE_NOT_STARTED'
            elif units_step_skipped(job):
                code = 'SLICE_UNITS_NOT_RUN'
            lost = code == 'SLICE_RECORD_MISSING'
            missing.append(spec['slice'])
            for unit in expected:
                state = 'EXCLUDED' if lost else 'BEFORE_START'
                gates, counts = unit_gates(experiment, unit['run'], per_unit, state, code, None) if gated \
                    else (None, None)
                units.append({'unit': unit, 'slice': spec['slice'], 'state': state, 'code': code, 'exit': None,
                              'started_at': job['started_at'] if lost else None, 'slice_record_sha256': None,
                              'gates': gates, 'gate_counts': counts})
            continue
        raw = read_bytes(path, JSON_LIMIT, 'SLICE_RECORD_UNAVAILABLE')
        record = parse_json(raw, 'SLICE_RECORD_JSON')
        need(type(record) is dict, 'SLICE_RECORD_JSON')
        check_slice_record(record)
        need(record['slice'] == spec['slice'] and record['job_name'] == name and record['run'] == run
             and record['experiment'] == experiment and record['slice_commit'] == run['commit'], 'SLICE_RECORD_RUN',
             EXIT_REFUSAL)
        need([u['unit'] for u in record['units']] == expected, 'SLICE_RECORD_UNITS', EXIT_REFUSAL)
        confirmatory = record['mode'] == 'CONFIRMATORY'
        need(confirmatory == (declaration['mode'] == 'CONFIRMATORY'), 'SLICE_RECORD_MODE', EXIT_REFUSAL)
        started = any(u['state'] != 'BEFORE_START' for u in record['units'])
        if confirmatory:
            need(record['registration_sha256'] == registration, 'SLICE_RECORD_REGISTRATION', EXIT_REFUSAL)
            if record['s04'] is not None or started:
                need(record['s04']['s04_run_id'] == declaration['s04_run_id'], 'SLICE_RECORD_S04', EXIT_REFUSAL)
            if started:
                # Q9: the observation starts at the job's server started_at, read here from the server again.
                need(jobs is not None, 'JOBS_LISTING_MISSING', EXIT_PREREQUISITE)
                need(job is not None and job.get('started_at') == record['started_at']['utc'],
                     'STARTED_AT_NOT_SERVER', EXIT_REFUSAL)
        scans = [check_raw_log(folder, entry) for entry in record['units']]
        digest = hashlib.sha256(raw).hexdigest()
        for entry, scan in zip(record['units'], scans):
            state = 'EXCLUDED' if entry['state'] == 'IN_PROGRESS' else entry['state']
            code = 'RUN_INTERRUPTED' if entry['state'] == 'IN_PROGRESS' else entry['code']
            gates, counts = unit_gates(experiment, entry['unit']['run'], per_unit, state, code, scan,
                                       declaration['unit_minutes'] * SECONDS_PER_MINUTE,
                                       declaration['mode'] == 'CONFIRMATORY') if gated else (None, None)
            units.append({'unit': entry['unit'], 'slice': spec['slice'], 'state': state, 'code': code,
                          'exit': entry['exit'],
                          'started_at': record['started_at']['utc'] if state != 'BEFORE_START' else None,
                          'slice_record_sha256': digest, 'gates': gates, 'gate_counts': counts})
    observations = []
    for entry in units:
        entry['observation_id'] = None
        # EXPLORATORY and PR_SMOKE units are never observations. An ITEM1 or POOL gate is one when it started
        # or may have started (OBSERVED or EXCLUDED); any other unit when it started (A #634: one form per list).
        if declaration['mode'] != 'CONFIRMATORY' or entry['state'] not in OBSERVATION_STATES:
            continue
        if not gated:
            entry['observation_id'] = observation_id(experiment, entry['unit']['run'])
            ids = [entry['observation_id']]
        else:
            ids = []
            for gate in entry['gates']:
                if gate['state'] != 'NOT_STARTED':
                    gate['observation_id'] = gate_observation_id(experiment, entry['unit']['run'], gate['gate'])
                    ids.append(gate['observation_id'])
        observations += [{'observation_id': i, 'registration_sha256': registration,
                          'start_time_utc': epoch(entry['started_at'])} for i in ids]
    blob = dumps({'schema': OBSERVATION_SCHEMA, 'observations': observations}) if observations else None
    # Checked before anything is written: a list the receipt tool cannot read leaves no collection either.
    need(blob is None or len(blob) <= RECEIPT_JSON_LIMIT, 'OBSERVATIONS_OVERSIZED')
    collection = {'schema': COLLECTION_SCHEMA, 'declaration_sha256': hashlib.sha256(
                      read_bytes(declaration_path, JSON_LIMIT, 'DECLARATION_UNAVAILABLE')).hexdigest(),
                  'experiment': experiment, 'mode': declaration['mode'],
                  'evidence_status': declaration['evidence_status'], 'registration_sha256': registration,
                  'run': run, 'jobs_listing': 'ACTIONS_API_THIS_RUN_ATTEMPT' if jobs is not None else None,
                  'missing_slice_records': missing, 'units': units, 'labels': LABELS,
                  # #110: derived from this run's own records in the workflow; not yet bound to an authenticated
                  # append-only collection log.
                  'observation_completeness': 'WORKFLOW_DERIVED_NOT_AUTHENTICATED_LOG'}
    return collection, blob


def collection_summary(collection: dict, blob: bytes | None) -> dict:
    """The collect step's summary line. U3 Part C: `ten_percent_rule` is A Q2's input over every gate of a
    started unit (missing + EXCLUDED, `over_10_percent` above a tenth: 20 of 200 gates), reported for the
    judge, who makes the NOT_ESTABLISHED call; `exit_5` lists the units whose driver ended exit 5 by code and
    count (A #638 check 6552915714 For-A 3), kept apart from the other EXCLUDED units."""
    units = collection['units']
    gates = [g for u in units for g in (u['gates'] or ())]
    lost = sum(g['state'] != 'OBSERVED' for g in gates)
    exit_5: dict = {}
    for u in units:
        if u['exit'] == EXIT_SECURITY:
            exit_5[u['code']] = exit_5.get(u['code'], 0) + 1
    return {'units': len(units), 'observations': len(strict_json_bytes(blob)['observations']) if blob else 0,
            'missing_slice_records': collection['missing_slice_records'],
            'states': {s: sum(u['state'] == s for u in units) for s in STATES if s != 'IN_PROGRESS'},
            'gate_states': {s: sum(g['state'] == s for g in gates) for s in GATE_STATES},
            'ten_percent_rule': {'gates': len(gates), 'missing_or_excluded': lost,
                                 'over_10_percent': lost * 10 > len(gates)},
            'exit_5': {'units': sum(exit_5.values()), 'codes': dict(sorted(exit_5.items(), key=lambda kv: str(kv[0])))}}


def collect(args) -> dict:
    collection, blob = collection_of(args.declaration, args.records, args.jobs)
    summary = collection_summary(collection, blob)   # #713 round 2: before any output, so a refusal writes none
    write_new(args.out_collection, dumps(collection))
    if blob is not None:
        write_new(args.out_observations, blob)
    return summary


# -------------------------------------------------------------------------------------------------- re-dispatch

def runs_pages(args) -> dict:
    """How many pages of 100 the dispatch runs listing has, from its first page (`runs-1.json`). A filtered listing
    holds at most 1,000 runs, so a total of 1,000 or more is exit 3 `RUNS_LISTING_CAPPED`: the oldest runs may be
    missing and are never dropped silently."""
    first = read_json(args.runs_dir / 'runs-1.json', 'RUNS')
    total = first.get('total_count')
    need(type(total) is int and total >= 0, 'RUNS_LISTING', EXIT_PREREQUISITE)
    need(total < RUNS_LISTING_CAP, 'RUNS_LISTING_CAPPED', EXIT_PREREQUISITE)
    pages = max(1, -(-total // MAX_JOBS))   # at most MAX_RUN_PAGES, since total < MAX_RUN_PAGES x 100
    return {'pages': pages}


def read_runs(folder: Path) -> list:
    """Every page the workflow saved (`runs-<p>.json`): each page says the same total, every page but the last is
    full, and no run is listed twice; a listing that changed between pages is exit 3 (dispatch again)."""
    pages = runs_pages(argparse.Namespace(runs_dir=folder))['pages']
    runs, total = [], read_json(folder / 'runs-1.json', 'RUNS')['total_count']
    for page in range(1, pages + 1):
        listing = read_json(folder / f'runs-{page}.json', 'RUNS')
        items = listing.get('workflow_runs')
        need(type(items) is list and listing.get('total_count') == total
             and len(items) == (MAX_JOBS if page < pages else total - MAX_JOBS * (pages - 1)),
             'RUNS_LISTING_CHANGED', EXIT_PREREQUISITE)
        runs += items
    ids = [str(item.get('id')) if type(item) is dict else None for item in runs]
    need(len(set(ids)) == len(ids), 'RUNS_LISTING_CHANGED', EXIT_PREREQUISITE)
    return runs


def chosen_runs(planned: dict, folder: Path, current_id: str, current_number: int) -> tuple[list, list]:
    """The CONFIRMATORY dispatch runs of the planned experiment whose artifacts the plan job must read, and the
    RECOLLECT runs of the experiment that recollected one of them, as (run id, recollected run id, server
    `head_sha`) triples (a RECOLLECT run's `head_sha` must be a commit id, exit 3 `RUNS_LISTING`). A run is
    chosen by its server `display_title`, the workflow's `run-name`: `ardr <mode> <experiment>`, or
    `ardr RECOLLECT <experiment> <run id>` for a collect-only recovery; a run on another branch is skipped (its
    first step refuses and it uploads nothing), and so is a RECOLLECT run whose run id is not digits (its first
    tool step refuses that input, before its upload).

    Order (D4-2, Desktop r4431587744): GitHub's concurrency group does not promise that dispatches start in
    `run_number` order. A listed run is skipped only when it is the current run (its id) or when it is NEWER
    (`run_number` above the current run's) AND not `completed`: a newer dispatch the group holds pending behind
    the current run holds no observation yet, and refusing it would abort the current plan whenever the next
    dispatch is submitted (#619 review). Every `completed` run, whatever its number, is read exactly as a
    preceding run is: a newer run the group admitted first may have observed a unit. Any other chosen run that is
    not `completed` (an older one, or a synthetic one with the current number) is refused as in progress (its
    collection does not exist yet). `run_number` counts up by one per run of this workflow and does not change
    between attempts (a CONFIRMATORY plan refuses any attempt but the first); `created_at` has one-second
    resolution and `id` is not documented as ordered."""
    need(current_number >= 1, 'RUN_FIELDS')
    ids, again = [], []
    for item in read_runs(folder):
        need(type(item) is dict and DIGITS.match(str(item.get('id'))) is not None
             and type(item.get('run_number')) is int and item['run_number'] >= 1
             and item.get('event') == 'workflow_dispatch' and item.get('path') == WORKFLOW_PATH, 'RUNS_LISTING',
             EXIT_PREREQUISITE)
        completed = item.get('status') == 'completed'
        if (str(item['id']) == current_id or (item['run_number'] > current_number and not completed)
                or item.get('head_branch') != 'main'):
            continue   # the current run, a newer unfinished dispatch, another branch
        text = str(item.get('display_title'))
        recollect = RECOLLECT_TITLE.match(text)
        if recollect is not None:
            need(recollect.group(1) in EXPERIMENTS, 'RUNS_TITLE', EXIT_PREREQUISITE)
            target = recollect.group(2)
            if recollect.group(1) != planned['experiment'] or target is None or DIGITS.match(target) is None:
                continue   # another experiment, or a run id its recollect job refuses before any upload
            need(completed, 'PRIOR_RUN_IN_PROGRESS', EXIT_PREREQUISITE)
            need(type(item.get('head_sha')) is str and OID.match(item['head_sha']) is not None, 'RUNS_LISTING',
                 EXIT_PREREQUISITE)
            again.append((str(item['id']), target, item['head_sha']))
            continue
        title = RUN_TITLE.match(text)
        need(title is not None and title.group(2) in EXPERIMENTS, 'RUNS_TITLE', EXIT_PREREQUISITE)
        if (title.group(1), title.group(2)) != ('CONFIRMATORY', planned['experiment']):
            continue
        need(completed, 'PRIOR_RUN_IN_PROGRESS', EXIT_PREREQUISITE)
        ids.append(str(item['id']))
    again = [pair for pair in again if pair[1] in ids]   # a recollection matters only for a chosen run
    return sorted(ids, key=int), sorted(again, key=lambda pair: int(pair[0]))


def prior_runs(args) -> dict:
    """`chosen_runs` for the workflow: the CONFIRMATORY runs whose jobs, declaration and collection it saves, and
    the RECOLLECT runs whose recollection it saves (none for an EXPLORATORY dispatch)."""
    planned = read_declaration(args.declaration)
    if planned['mode'] != 'CONFIRMATORY':
        return {'runs': [], 'recollections': []}
    ids, again = chosen_runs(planned, args.runs_dir, args.current_run_id, args.current_run_number)
    return {'runs': ids, 'recollections': [run_id for run_id, _, _ in again]}


def artifact_id(args) -> dict:
    """The one artifact of the listing (exact name), or none; an expired one is refused (it cannot be read)."""
    listing = read_json(args.listing, 'ARTIFACTS')
    items = listing.get('artifacts')
    need(type(items) is list and len(items) <= 1 and listing.get('total_count') == len(items), 'ARTIFACTS_LISTING')
    if not items:
        return {'id': None}
    need(items[0].get('name') == args.name and DIGITS.match(str(items[0].get('id'))) is not None, 'ARTIFACTS_LISTING')
    need(items[0].get('expired') is False, 'PRIOR_ARTIFACT_EXPIRED', EXIT_PREREQUISITE)
    return {'id': str(items[0]['id'])}


def zip_member(path: Path, member: str, code: str) -> dict:
    value = parse_json(zip_single(path, member, code, EXIT_VALIDATION), code + '_JSON')
    need(type(value) is dict, code + '_JSON')
    return value


def prior_declaration(folder: Path, run_id: str) -> dict | None:
    """An earlier run's declaration, or None when the server says it dispatched nothing (B default D-1 for A):
    its attempt-1 plan job is not listed or completed without success, AND every attempt-1 `ARDR slice <n>` job is
    absent or ran no step (units are observed only inside slice jobs, and a slice job needs plan). This covers a
    plan that refused (whatever its upload step shows) and a queued run the concurrency group cancelled before any
    job started. A missing artifact alone never hides a run: a plan that succeeded, a slice job that ran a step,
    or a collection without a readable declaration is exit 3 `PRIOR_DECLARATION_MISSING`."""
    decl_zip, coll_zip = folder / f'{run_id}-declaration.zip', folder / f'{run_id}-collection.zip'
    if decl_zip.exists():
        declared = check_declaration(zip_member(decl_zip, 'declaration.json', 'PRIOR_DECLARATION'), prior=True)
        need(str(declared['run']['run_id']) == run_id, 'PRIOR_DECLARATION_RUN', EXIT_REFUSAL)
        return declared
    jobs = jobs_of(folder / f'{run_id}-jobs.json', run_id, '1')
    plan_job = jobs.get(PLAN_JOB_NAME)
    plan_failed = plan_job is None or (plan_job.get('status') == 'completed'
                                       and plan_job.get('conclusion') not in (None, 'success'))
    slice_ran = any(job_ran(job) for name, job in jobs.items() if SLICE_JOB.match(name))
    need(plan_failed and not slice_ran and not coll_zip.exists(), 'PRIOR_DECLARATION_MISSING', EXIT_PREREQUISITE)
    return None


def check_recollection(value: dict) -> dict:
    """A recollection's shape (`recollect` writes it); returns its collection, whose digest it carries. The
    original run and the RECOLLECT run are attempt 1, the labels are LABELS and every slice artifact id is digits,
    as recollect writes them; `recollect_run.tool_sha256` is informational and not checked."""
    keys = {'schema', 'recollected', 'recollected_from', 'recollect_run', 'collection', 'collection_sha256',
            'slice_artifacts', 'labels'}
    need(set(value) == keys and value['schema'] == RECOLLECTION_SCHEMA and value['recollected'] is True,
         'PRIOR_RECOLLECTION_SHAPE', EXIT_REFUSAL)
    origin, by, collection = value['recollected_from'], value['recollect_run'], value['collection']
    need(type(origin) is dict and set(origin) == {'run_id', 'run_attempt'} and type(by) is dict
         and set(by) == {'run_id', 'run_attempt', 'commit', 'tool_sha256'} and type(collection) is dict
         and type(collection.get('run')) is dict and str(collection['run'].get('run_id')) == str(origin['run_id'])
         and value['collection_sha256'] == hashlib.sha256(dumps(collection)).hexdigest(),
         'PRIOR_RECOLLECTION_SHAPE', EXIT_REFUSAL)
    arts = value['slice_artifacts']
    need(origin['run_attempt'] == '1' and by['run_attempt'] == '1' and value['labels'] == LABELS
         and type(arts) is list
         and all(type(a) is dict and set(a) == {'slice', 'artifact_id'} and type(a['slice']) is int
                 and type(a['artifact_id']) is str and DIGITS.match(a['artifact_id']) is not None for a in arts),
         'PRIOR_RECOLLECTION_SHAPE', EXIT_REFUSAL)
    return collection


def prior_recollection(folder: Path, run_id: str, recollect_runs: list[tuple[str, str]], commit: str,
                       declaration_sha256: str) -> dict:
    """The collection a collect-only recovery rebuilt for `run_id`, which has a declaration and no collection; a
    RECOLLECT run without the artifact refused and recollected nothing. Two recollections of one run must agree.
    None at all is exit 3 `PRIOR_COLLECTION_MISSING` (fail closed, as before D4-2).

    A run's `head_branch` `main` is not proof that it ran `main`'s workflow: a dispatch on a tag named `main` lists
    the same way and may run a changed workflow that writes any self-consistent recollection (B pre-PR review,
    P2-1). So each recollection's `recollect_run.commit` must be its RECOLLECT run's server `head_sha` (exit 6
    `PRIOR_RECOLLECTION_COMMIT`) and on the first-parent history of the dispatched commit `commit` (exit 6
    `PRIOR_RECOLLECTION_NOT_ON_HISTORY`), whose workflow refuses any ref but `refs/heads/main`. This binds a
    recollection to `main` only while `main` takes changes by merge commit or squash merge alone (B delta review,
    P3-A; corrected by W653q, finding #654): a fast-forward push or a rebase merge (GitHub's rebase merge, which
    main's ruleset 24579265 allows today beside merge and squash, adds each rewritten commit to main's
    first-parent line) puts commits main never pointed at on its first-parent history, so a tag `main` on one of
    them would pass. A tag ruleset refusing `refs/tags/main`, or a main ruleset allowing merge and squash only
    (repository settings, the Founder's), closes that gap. Its collection must name `run_id`'s declaration
    bytes as the plan saved them (exit 6
    `PRIOR_RECOLLECTION_DECLARATION`)."""
    found, history = None, None
    for again, head_sha in recollect_runs:
        path = folder / f'{again}-recollection.zip'
        if not path.exists():
            continue
        value = zip_member(path, RECOLLECTION_MEMBER, 'PRIOR_RECOLLECTION')
        collection = check_recollection(value)
        need(str(value['recollect_run']['run_id']) == again and str(value['recollected_from']['run_id']) == run_id,
             'PRIOR_RECOLLECTION_RUN', EXIT_REFUSAL)
        need(value['recollect_run']['commit'] == head_sha, 'PRIOR_RECOLLECTION_COMMIT', EXIT_REFUSAL)
        if history is None:
            history = set(git('rev-list', '--first-parent', commit).split())
        need(head_sha in history, 'PRIOR_RECOLLECTION_NOT_ON_HISTORY', EXIT_REFUSAL)
        need(collection.get('declaration_sha256') == declaration_sha256, 'PRIOR_RECOLLECTION_DECLARATION',
             EXIT_REFUSAL)
        need(found is None or found == collection, 'PRIOR_RECOLLECTION_CONFLICT', EXIT_REFUSAL)
        found = collection
    need(found is not None, 'PRIOR_COLLECTION_MISSING', EXIT_PREREQUISITE)
    return found


def redispatch(args) -> dict:
    """A planned CONFIRMATORY unit is refused when any earlier CONFIRMATORY dispatch of the same experiment, under
    any registration, did not leave it BEFORE_START (section 3 of A's request names no registration scope): a
    unit with any observation ends PASS, FAIL or excluded, and an exclusion counts toward the 10 % rule."""
    planned = read_declaration(args.declaration)
    if planned['mode'] != 'CONFIRMATORY':
        return {'checked_runs': 0, 'refused_units': []}
    runs, again = chosen_runs(planned, args.runs_dir, args.current_run_id, args.current_run_number)
    want = {(planned['experiment'], r) for r in range(planned['units']['first'], planned['units']['last'] + 1)}
    used = set()
    for run_id in runs:
        declared = prior_declaration(args.prior_dir, run_id)
        if declared is None:
            continue   # the server says this dispatch's plan refused: it declared and dispatched nothing
        # Its run name said CONFIRMATORY and this experiment; its declaration must say the same.
        need((declared['mode'], declared['experiment']) == ('CONFIRMATORY', planned['experiment']),
             'PRIOR_DECLARATION_TITLE', EXIT_REFUSAL)
        coll_zip = args.prior_dir / f'{run_id}-collection.zip'
        if coll_zip.exists():
            collection = zip_member(coll_zip, 'collection.json', 'PRIOR_COLLECTION')
        else:   # D4-2: a collect-only recovery of this run stands in for its missing collection
            blob = zip_single(args.prior_dir / f'{run_id}-declaration.zip', 'declaration.json', 'PRIOR_DECLARATION',
                              EXIT_VALIDATION)
            collection = prior_recollection(args.prior_dir, run_id,
                                            [(r, head) for r, target, head in again if target == run_id],
                                            planned['run']['commit'], hashlib.sha256(blob).hexdigest())
        need(collection.get('schema') in COLLECTION_SCHEMAS and collection.get('run') == declared['run']
             and type(collection.get('units')) is list, 'PRIOR_COLLECTION_SHAPE', EXIT_REFUSAL)
        listed = set()
        for entry in collection['units']:
            need(type(entry) is dict and type(entry.get('unit')) is dict and entry.get('state') in STATES,
                 'PRIOR_COLLECTION_SHAPE', EXIT_REFUSAL)
            key = (entry['unit'].get('experiment'), entry['unit'].get('run'))
            listed.add(key)
            if entry['state'] != 'BEFORE_START':
                used.add(key)
        declared_units = {(declared['experiment'], r)
                          for r in range(declared['units']['first'], declared['units']['last'] + 1)}
        need(listed == declared_units, 'PRIOR_COLLECTION_UNITS', EXIT_REFUSAL)
    refused = sorted(r for e, r in want & used)
    need(not refused, 'REDISPATCH_OBSERVED_UNIT', EXIT_REFUSAL)
    return {'checked_runs': len(runs), 'refused_units': []}


# ------------------------------------------------------------------------------------ collect-only recovery (D4-2)

def recollect_inputs(args) -> dict:
    """The recollect job's first tool step: the dispatch's experiment and `recollect_run_id` input (digits)."""
    need(args.experiment in EXPERIMENTS, 'EXPERIMENT')
    need(DIGITS.match(args.recollect_run_id) is not None, 'RECOLLECT_RUN_ID_INPUT')
    return {'experiment': args.experiment, 'recollect_run_id': args.recollect_run_id}


def recollect_run(folder: Path, run_id: str, experiment: str) -> dict:
    """The original run as the Actions API lists it (`run.json`): this workflow's CONFIRMATORY dispatch of the
    experiment on main, and completed (its slice and collect jobs ended). `head_branch` `main` alone does not bind
    it to main: `recollect` also requires its head on main's first-parent history (`recollect_on_history`)."""
    recollect_inputs(argparse.Namespace(experiment=experiment, recollect_run_id=run_id))
    run = read_json(folder / 'run.json', 'RECOLLECT_RUN')
    need(str(run.get('id')) == run_id, 'RECOLLECT_RUN_ID', EXIT_REFUSAL)
    need(run.get('path') == WORKFLOW_PATH, 'RECOLLECT_RUN_WORKFLOW', EXIT_REFUSAL)
    need(run.get('event') == 'workflow_dispatch', 'RECOLLECT_RUN_EVENT', EXIT_REFUSAL)
    need(run.get('head_branch') == 'main', 'RECOLLECT_RUN_BRANCH', EXIT_REFUSAL)
    need(run.get('display_title') == f'ardr CONFIRMATORY {experiment}', 'RECOLLECT_RUN_TITLE', EXIT_REFUSAL)
    need(run.get('status') == 'completed', 'RECOLLECT_RUN_NOT_COMPLETED', EXIT_PREREQUISITE)
    return run


def recollect_listing(folder: Path, run_id: str) -> dict[str, dict]:
    """The original run's artifact listing (`artifacts.json`, one page of 100), by name: every item is that run's
    (`workflow_run.id`), each name once, and only D4's names (`RUN_ARTIFACT`). A listed collection, expired or not, means there is nothing to recover."""
    listing = read_json(folder / 'artifacts.json', 'RECOLLECT_ARTIFACTS')
    items = listing.get('artifacts')
    need(type(items) is list and listing.get('total_count') == len(items) and len(items) <= MAX_JOBS,
         'RECOLLECT_ARTIFACT_LISTING', EXIT_REFUSAL)
    by_name: dict[str, dict] = {}
    for item in items:
        need(type(item) is dict and type(item.get('name')) is str and item['name'] not in by_name
             and RUN_ARTIFACT.match(item['name']) is not None
             and DIGITS.match(str(item.get('id'))) is not None and type(item.get('expired')) is bool,
             'RECOLLECT_ARTIFACT_LISTING', EXIT_REFUSAL)
        source = item.get('workflow_run')
        need(type(source) is dict and str(source.get('id')) == run_id, 'RECOLLECT_ARTIFACT_RUN', EXIT_REFUSAL)
        by_name[item['name']] = item
    need(COLLECTION_ARTIFACT not in by_name, 'RECOLLECT_COLLECTION_EXISTS', EXIT_REFUSAL)
    return by_name


def recollect_artifact(item: dict | None) -> str | None:
    if item is None:
        return None
    need(item['expired'] is False, 'RECOLLECT_ARTIFACT_EXPIRED', EXIT_PREREQUISITE)
    return str(item['id'])


def recollect_declaration_id(listed: dict[str, dict]) -> str:
    art = recollect_artifact(listed.get(DECLARATION_ARTIFACT))
    need(art is not None, 'RECOLLECT_DECLARATION_MISSING', EXIT_PREREQUISITE)
    return art


def recollect_declaration(folder: Path, run_id: str, experiment: str, run: dict,
                          listed: dict[str, dict]) -> tuple[dict, bytes]:
    """The original run's declaration (artifact `ardr-declaration`, listed and not expired, saved as
    `declaration.zip`): CONFIRMATORY, of the experiment, attempt 1 of that run at its head commit."""
    recollect_declaration_id(listed)
    path = folder / 'declaration.zip'
    need(path.is_file() and not path.is_symlink(), 'RECOLLECT_DECLARATION_MISSING', EXIT_PREREQUISITE)
    blob = zip_single(path, 'declaration.json', 'RECOLLECT_DECLARATION', EXIT_VALIDATION)
    value = parse_json(blob, 'RECOLLECT_DECLARATION_JSON')
    need(type(value) is dict, 'RECOLLECT_DECLARATION_JSON')
    declared = check_declaration(value)
    need(declared['mode'] == 'CONFIRMATORY', 'RECOLLECT_NOT_CONFIRMATORY', EXIT_REFUSAL)
    need(declared['experiment'] == experiment, 'RECOLLECT_EXPERIMENT', EXIT_REFUSAL)
    need(str(declared['run']['run_id']) == run_id and str(declared['run']['run_attempt']) == '1'
         and declared['run']['commit'] == run.get('head_sha'), 'RECOLLECT_DECLARATION_RUN', EXIT_REFUSAL)
    return declared, blob


def recollect_slice_ids(listed: dict[str, dict], declared: dict) -> list[tuple[int, str]]:
    """The declared slices whose artifact the original run lists (an unlisted one is a missing slice record, read
    as collect reads it); an expired one is exit 3 (its units may have been observed)."""
    found = []
    for spec in declared['slices']:
        art = recollect_artifact(listed.get(SLICE_ARTIFACT % spec['slice']))
        if art is not None:
            found.append((spec['slice'], art))
    return found


def recollect_on_history(run: dict, commit: str) -> None:
    """The original run's server `head_sha` must be a commit id on the first-parent history of the RECOLLECT
    dispatch commit `commit` (`github.sha`, the checked-out HEAD), whose workflow refuses any ref but
    `refs/heads/main` (exit 6 `RECOLLECT_RUN_NOT_ON_HISTORY`; W653q, A #258 6561758412, finding #654). A run's
    `head_branch` `main` is not proof that it ran `main`'s workflow: a dispatch on a tag named `main` lists the same
    way and may run a changed workflow, without the `refs/heads/main` checks, that uploads a declaration and slices.
    This is `prior_recollection`'s rule and carries its caveat: it binds the run to `main` only while `main` takes
    changes by merge commit or squash merge alone. A fast-forward push or a rebase merge (GitHub's rebase merge,
    which main's ruleset 24579265 allows today beside merge and squash, adds each rewritten commit to main's
    first-parent line) puts commits main never pointed at on its first-parent history, so a tag `main` on one of
    them would pass. A tag ruleset refusing `refs/tags/main`, or a main ruleset allowing merge and squash only
    (repository settings, the Founder's), closes that gap."""
    head = run.get('head_sha')
    need(type(head) is str and OID.match(head) is not None
         and head in git('rev-list', '--first-parent', commit).split(), 'RECOLLECT_RUN_NOT_ON_HISTORY', EXIT_REFUSAL)


def recollect_checked(args) -> tuple[dict, dict[str, dict]]:
    run = recollect_run(args.dir, args.recollect_run_id, args.experiment)
    listed = recollect_listing(args.dir, args.recollect_run_id)
    return run, listed


def recollect_cli_run(args) -> dict:
    run = recollect_run(args.dir, args.recollect_run_id, args.experiment)
    return {'run_id': str(run['id']), 'head_sha': run.get('head_sha')}


def recollect_cli_declaration(args) -> dict:
    _, listed = recollect_checked(args)
    return {'id': recollect_declaration_id(listed)}


def recollect_cli_slices(args) -> dict:
    run, listed = recollect_checked(args)
    declared, _ = recollect_declaration(args.dir, args.recollect_run_id, args.experiment, run, listed)
    return {'downloads': ['%d:%s' % pair for pair in recollect_slice_ids(listed, declared)]}


def extract_slice(path: Path, folder: Path, spec: dict) -> None:
    """One slice artifact's zip into `folder`, as the collect job's download would lay it out: members
    `slice-record.json` and `raw-<run>.jsonl` of the slice's runs only, each within its bound. A member
    `slice-record.json.tmp` (a slice job killed inside `replace`, between its open and its rename, whose
    `always()` upload kept it) is skipped, never extracted: collect's download would hold it and collect never
    reads it (B pre-PR review, P3-2)."""
    need(path.is_file() and not path.is_symlink(), 'RECOLLECT_SLICE_MISSING', EXIT_PREREQUISITE)
    need(path.stat().st_size <= SLICE_ZIP_LIMIT, 'RECOLLECT_SLICE_ZIP', EXIT_REFUSAL)
    allowed = {'slice-record.json': JSON_LIMIT}
    allowed.update(('raw-%d.jsonl' % r, LOG_LIMIT) for r in range(spec['first'], spec['last'] + 1))
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            infos = [info for info in infos if info.filename != STRAY_RECORD_TMP]
            need(len(set(names)) == len(names) and all(info.filename in allowed for info in infos)
                 and all(info.file_size <= allowed[info.filename] for info in infos)
                 and sum(info.file_size for info in infos) <= SLICE_UNPACKED_LIMIT, 'RECOLLECT_SLICE_ZIP',
                 EXIT_REFUSAL)
            folder.mkdir(mode=0o700, parents=False, exist_ok=False)
            for info in infos:
                size = 0
                with archive.open(info) as source, open(folder / info.filename, 'xb') as target:
                    for block in iter(lambda: source.read(1 << 20), b''):
                        size += len(block)
                        need(size <= allowed[info.filename], 'RECOLLECT_SLICE_ZIP', EXIT_REFUSAL)
                        target.write(block)
    except zipfile.BadZipFile:
        raise Refusal('RECOLLECT_SLICE_ZIP', EXIT_REFUSAL) from None


def recollect(args) -> dict:
    """D4-2 collect-only recovery (A #619 6542865820): the collection of the original CONFIRMATORY run, rebuilt by
    the collection function `collect` uses from THAT run's declaration, slice artifacts and attempt-1 jobs listing
    only, wrapped in a recollection that names the original run and says `recollected`. It adds no observation:
    every unit state comes from the slice records exactly as collect derives it."""
    need(DIGITS.match(args.run_id) is not None and DIGITS.match(args.run_attempt) is not None
         and OID.match(args.commit) is not None, 'RUN_FIELDS')
    need(args.run_attempt == '1', 'RUN_ATTEMPT_NOT_FIRST', EXIT_REFUSAL)
    run, listed = recollect_checked(args)
    recollect_on_history(run, args.commit)
    declared, blob = recollect_declaration(args.dir, args.recollect_run_id, args.experiment, run, listed)
    found = recollect_slice_ids(listed, declared)
    try:   # an existing directory is exit 3 like an existing output; one that cannot be made is exit 4
        args.out_dir.mkdir(mode=0o700, parents=False, exist_ok=False)
        (args.out_dir / 'records').mkdir(mode=0o700)
    except FileExistsError:
        raise Refusal('OUTPUT_EXISTS', EXIT_PREREQUISITE) from None
    except OSError:
        raise Refusal('OUTPUT_WRITE_FAILED', EXIT_INTERNAL) from None
    write_new(args.out_dir / 'declaration.json', blob)
    specs = {spec['slice']: spec for spec in declared['slices']}
    for number, _ in found:
        extract_slice(args.dir / f'slice-{number}.zip', args.out_dir / 'records' / f'ardr-slice-{number}',
                      specs[number])
    collection, observations = collection_of(args.out_dir / 'declaration.json', args.out_dir / 'records',
                                             args.dir / 'jobs.json')
    value = {'schema': RECOLLECTION_SCHEMA, 'recollected': True,
             'recollected_from': {'run_id': args.recollect_run_id, 'run_attempt': '1'},
             'recollect_run': {'run_id': args.run_id, 'run_attempt': args.run_attempt, 'commit': args.commit,
                               'tool_sha256': file_sha256(Path(__file__).absolute())},
             'collection': collection, 'collection_sha256': hashlib.sha256(dumps(collection)).hexdigest(),
             'slice_artifacts': [{'slice': number, 'artifact_id': art} for number, art in found], 'labels': LABELS}
    summary = collection_summary(collection, observations)   # #713 round 2: before the recollection is written
    write_new(args.out_dir / RECOLLECTION_MEMBER, dumps(value))
    if observations is not None:
        write_new(args.out_dir / 'observations.json', observations)
    return dict(summary, recollected_from=args.recollect_run_id)


# --------------------------------------------------------------------------------------------------------- main

def parser() -> argparse.ArgumentParser:
    top = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = top.add_subparsers(dest='command', required=True)
    p = sub.add_parser('plan')
    p.add_argument('--experiment', required=True)
    p.add_argument('--mode', required=True)
    p.add_argument('--unit-first', type=int, required=True)
    p.add_argument('--unit-last', type=int, required=True)
    p.add_argument('--units-per-slice', type=int, required=True)
    p.add_argument('--unit-minutes', type=int, required=True)
    p.add_argument('--policy', required=True)
    p.add_argument('--registration', default='')
    p.add_argument('--registration-sha256', default='')
    p.add_argument('--s04-run-id', default='')
    p.add_argument('--run-id', required=True)
    p.add_argument('--run-attempt', required=True)
    p.add_argument('--commit', required=True)
    p.add_argument('--out', required=True, type=Path)
    p.add_argument('--github-output', type=Path)
    s = sub.add_parser('started-at')
    s.add_argument('--jobs', required=True, type=Path)
    s.add_argument('--run-id', required=True)
    s.add_argument('--run-attempt', required=True)
    s.add_argument('--job-name', required=True)
    b = sub.add_parser('slice-begin')
    b.add_argument('--declaration', required=True, type=Path)
    b.add_argument('--slice', required=True, type=int)
    b.add_argument('--mode', required=True)
    b.add_argument('--out-dir', required=True, type=Path)
    r = sub.add_parser('slice')
    r.add_argument('--declaration', required=True, type=Path)
    r.add_argument('--slice', required=True, type=int)
    r.add_argument('--mode', required=True)
    r.add_argument('--jobs', type=Path)
    r.add_argument('--started-at')
    r.add_argument('--spent-seconds', type=int, default=0)
    r.add_argument('--node-a', required=True, type=Path)
    r.add_argument('--node-b', required=True, type=Path)
    r.add_argument('--work-root', required=True, type=Path)
    r.add_argument('--out-dir', required=True, type=Path)
    r.add_argument('--s04-dir', type=Path)
    c = sub.add_parser('collect')
    c.add_argument('--declaration', required=True, type=Path)
    c.add_argument('--records', required=True, type=Path)
    c.add_argument('--jobs', type=Path)
    c.add_argument('--out-collection', required=True, type=Path)
    c.add_argument('--out-observations', required=True, type=Path)
    rp = sub.add_parser('runs-pages')
    rp.add_argument('--runs-dir', required=True, type=Path)
    pr = sub.add_parser('prior-runs')
    pr.add_argument('--declaration', required=True, type=Path)
    pr.add_argument('--runs-dir', required=True, type=Path)
    pr.add_argument('--current-run-id', required=True)
    pr.add_argument('--current-run-number', required=True, type=int)
    a = sub.add_parser('artifact-id')
    a.add_argument('--listing', required=True, type=Path)
    a.add_argument('--name', required=True, choices=(DECLARATION_ARTIFACT, COLLECTION_ARTIFACT,
                                                             RECOLLECTION_ARTIFACT))
    d = sub.add_parser('redispatch')
    d.add_argument('--declaration', required=True, type=Path)
    d.add_argument('--runs-dir', required=True, type=Path)
    d.add_argument('--current-run-id', required=True)
    d.add_argument('--current-run-number', required=True, type=int)
    d.add_argument('--prior-dir', required=True, type=Path)
    e = sub.add_parser('s04-run-id')
    e.add_argument('--declaration', required=True, type=Path)
    for name in ('s04-run', 's04-artifact', 's04-job'):
        q = sub.add_parser(name)
        q.add_argument('--dir', required=True, type=Path)
        q.add_argument('--s04-run-id', required=True)
        if name == 's04-run':
            q.add_argument('--commit', required=True)
        else:
            q.add_argument('--run-attempt', required=True)
    k = sub.add_parser('s04-cite')
    k.add_argument('--declaration', required=True, type=Path)
    k.add_argument('--dir', required=True, type=Path)
    i = sub.add_parser('recollect-inputs')
    i.add_argument('--experiment', required=True)
    i.add_argument('--recollect-run-id', required=True)
    for name in ('recollect-run', 'recollect-declaration', 'recollect-slices', 'recollect'):
        q = sub.add_parser(name)
        q.add_argument('--dir', required=True, type=Path)
        q.add_argument('--experiment', required=True)
        q.add_argument('--recollect-run-id', required=True)
        if name == 'recollect':
            q.add_argument('--run-id', required=True)
            q.add_argument('--run-attempt', required=True)
            q.add_argument('--commit', required=True)
            q.add_argument('--out-dir', required=True, type=Path)
    return top


COMMANDS = {'plan': plan, 'started-at': started_at, 'slice-begin': slice_begin, 'slice': slice_run,
            'collect': collect, 'runs-pages': runs_pages, 'prior-runs': prior_runs, 'artifact-id': artifact_id, 'redispatch': redispatch,
            's04-run-id': s04_cli_run_id, 's04-run': s04_cli_run, 's04-artifact': s04_cli_artifact,
            's04-job': s04_cli_job, 's04-cite': s04_cite, 'recollect-inputs': recollect_inputs,
            'recollect-run': recollect_cli_run, 'recollect-declaration': recollect_cli_declaration,
            'recollect-slices': recollect_cli_slices, 'recollect': recollect}


def main(argv: list[str] | None = None) -> int:
    if not __debug__:
        print(json.dumps({'result': 'FAIL', 'code': 'OPTIMIZED_PYTHON', 'exit': EXIT_REFUSAL}))
        return EXIT_REFUSAL
    args = parser().parse_args(argv)
    try:
        summary = COMMANDS[args.command](args)
    except Refusal as refusal:
        print(json.dumps({'result': 'FAIL', 'code': refusal.code, 'exit': refusal.exit_code}, sort_keys=True))
        return refusal.exit_code
    except (OSError, zipfile.BadZipFile):
        print(json.dumps({'result': 'FAIL', 'code': 'IO_ERROR', 'exit': EXIT_PREREQUISITE}, sort_keys=True))
        return EXIT_PREREQUISITE
    code = summary.pop('exit', EXIT_DONE)
    print(json.dumps({'result': 'DONE' if code == 0 else 'FAIL', **summary, 'exit': code}, sort_keys=True))
    return code


if __name__ == '__main__':
    import claude_track_exit
    claude_track_exit.run(main)
