"""XD-1 collection: the dispatch's plan, its declaration, each slice's T4-2 record and runs (CT-P3-044c-1 1e-4b-2).

Class T EXPLORATORY development evidence on Regtest, not S17-PREP. Sources: B's unit draft #258
issuecomment-6418049931 (sections 2, 6 W1, 8) and A's answer issuecomment-6419729708 (items 5 and 8: A
dispatches each collection); docs/claude-track/plans/CT-P3-044C1_1E_PREP_EN.md section 4.5 (N and slices,
Per-run cap, Checker, Dispatch Q24) and Q11 (slices of at most 10 runs, each at most 330 min, dispatch from main
only). The workflow `.github/workflows/claude-track-xd1.yml` calls it; the record formats are
docs/claude-track/formats/XD1_EVENT_CHAIN_V1.md section 4 (T4-2) and XD1_EVENT_CHAIN_V2.md (declaration, runs).

  plan --n N --github-output FILE
  declare --n N --output FILE
  budget --slice K --n N --spent-seconds S
  t42 --slice K --n N --records DIR --result PASS|FAIL
  collect --slice K --n N --records DIR --node-a BIN --node-b BIN --work-root NEW_DIR

V3, one live-decision session per dispatch (docs/claude-track/formats/XD1_EVENT_CHAIN_V3.md; A's decisions
XA1-XA3, XA7 of 2026-11-10), called by `.github/workflows/claude-track-xd1-confirmatory.yml`:

  plan-v3 --mode M --first-run F --last-run L --expected-head SHA [--registration PATH
          --registration-sha256 HEX] --github-output FILE
  declare-v3 --mode M --first-run F --last-run L [--registration-sha256 HEX] --output FILE
  marker --declaration FILE --output FILE
  t42-v3 --declaration FILE --records DIR --result PASS|FAIL
  budget-v3 --declaration FILE --spent-seconds S
  pilot-registration --pinned-commit SHA --output FILE
  collect-v3 --declaration FILE --records DIR --node-a BIN --node-b BIN --work-root NEW_DIR --console-dir DIR

* `plan` refuses before any job starts unless the run is a workflow_dispatch on refs/heads/main, 1 <= N <=
  MAX_XD1_RUNS, and the slice budget holds (below); it writes `n` and `slices` (the JSON list 1 .. ceil(N/10))
  for the slice matrix.
* `declare` writes the V2 declaration; run_id, run_attempt and head_sha come only from GITHUB_RUN_ID,
  GITHUB_RUN_ATTEMPT and GITHUB_SHA, as the driver's (`claude_track_xd1_driver.run_ids`).
* The slice budget (1E N and slices, Q11): a slice's runs x (`XD1_RUN_CAP` + `XD1_KILL_MARGIN`, with the
  supervisor's 30 s wait for the killed group) must fit the
  collection step's timeout, and the bounded steps before it, the collection step and the upload must fit
  the 330 min slice job. `budget` checks it again with the time the job has spent before collection
  (measured: checkout, Core, build and the T4-2 driver tests), plus the collection step's whole timeout and
  the upload's, against the job's 330 min. The workflow's timeouts are these constants (pinned by
  test_xd1_workflow.py).
* A collection runs once. `plan`, `declare`, `t42` and `collect` refuse a GitHub re-run (GITHUB_RUN_ATTEMPT
  other than 1): a re-run slice would run its declared runs again, and a re-run of all jobs would make a
  second collection under the same run id.
* `t42` writes `t42-slice-<k>.json` once (`BITAGI_CT_XD1_T42_V1`, the head SHA from GITHUB_SHA) before the
  slice's first run.
* `collect` runs exactly the slice's runs, in order, each a new supervisor over one driver run in its own
  work directory: no rerun, no extension, no early stop by result. A supervisor that does not end with 0 (a
  process left, or the run not started) ends the slice: the next run must not start, and the runs after it
  have no record (RECORD_MISSING, T = infinity, never dropped). A run whose supervisor line is unreadable,
  or that left no record without being killed at the cap (any driver exit, a signal such as -11 or an OOM
  kill included), does not end the slice, but fails it once every run has run (B's review WF-3; A #540
  issuecomment-6429217537 F1): such a run was not collected. A run killed at the cap (the supervisor's
  `killed_at_cap`) or that wrote its record (a stop reason included) is a collected run; either way its row
  is in the report.

* `plan-v3` refuses before any job starts unless the run is a workflow_dispatch, attempt 1, at the expected
  head; CONFIRMATORY only at a pinned attempt tag `refs/tags/ct-xd1-c-a<N>` (XA3); EXPLORATORY (the
  live-decision pilot, XA7) on refs/heads/main with no registration, or at such a tag with the TEST_ONLY pilot
  registration PILOT_REGISTRATION (A's C2: the pilot runs the CONFIRMATORY read path); the session is 1 to 5
  consecutive runs (CONFIRMATORY within 1..20, EXPLORATORY from run 1); the session budget holds. A tagged
  dispatch also reads the registration from main (`refs/remotes/origin/main:<path>`, the bytes the receipts
  cover): its SHA-256 must be the input, its `xd1.pinned_commit` this commit, on main's first-parent chain, and
  its `xd1.tool_sha256` must name exactly REGISTERED_PATHS with the SHA-256 of each file of this checkout.
  CONFIRMATORY refuses the pilot file by path (anything under tests/) and by its label.
* `pilot-registration --pinned-commit SHA --output FILE` writes that TEST_ONLY pilot file for a commit on main's
  first-parent chain.
* Pre-flight before the follow-up registration is receipted (verifier N2): A runs `plan-v3` locally for session 1
  at the registration's pinned commit, with `refs/remotes/origin/main` fetched (the registration merged) and the
  dispatch's GITHUB_* values set by hand; see the unit note
  docs/claude-track/plans/notes/CT-P3-044C1_PLAN_EN/2026-11-10_xd1-confirmatory.md section 5. Whether the session is the next one
  after the counted sessions is the hosted `claude_track_xd1_confirm.py continuity` (it reads the Actions
  listing).
* `declare-v3` writes the V3 declaration; `marker` writes the session-start marker (V3 section 3), which the
  slice job uploads before the first run's driver starts: a session with no marker never started (XA1).
* `t42-v3` writes `t42-slice-<first_run>.json`; `collect-v3` runs the session's runs in order, each a
  supervisor over one live-decision driver run, with `collect`'s rules (no rerun, no early stop).

Exit codes: 0 done; 2 refused (event, ref, N, slice, budget, a record that exists, a re-run; in plan and
collect also a missing GITHUB_RUN_ATTEMPT; in V3 also the session, the head, the registration), or a slice
ended by its supervisor or with a failed run; 3 a missing prerequisite (in declare and t42 the GITHUB_* values,
malformed or missing; the records directory; in V3 the declaration, git or main); 4 internal error (an
existing --work-root among them); 5 under -O. Stdlib only; no reference/ code is read here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys

import claude_track_xd1_check as check
import claude_track_xd1_supervisor as supervisor

TOOLS = Path(__file__).resolve().parent
DRIVER = TOOLS / 'claude_track_xd1_driver.py'
SUPERVISOR = TOOLS / 'claude_track_xd1_supervisor.py'

# A killed run lasts this long: the cap, the kill margin and the supervisor's wait for the group to go.
RUN_SLOT_S = supervisor.XD1_RUN_CAP_S + supervisor.XD1_KILL_MARGIN_S + int(supervisor.LEFT_WAIT_S)
SLICE_JOB_MINUTES = 330   # Q11: each slice job at most 330 min (the job's timeout-minutes)
COLLECT_STEP_MINUTES = 170   # the collection step's timeout-minutes: 10 runs x 16.5 min, 5 min to spare
# The steps before the collection with their own timeout-minutes (Core fetch, toolchain, build, T4-2 tests),
# the upload step's timeout, and what the steps without one (checkout, setup) may take.
PREP_STEP_MINUTES = (10, 15, 90, 20)
UPLOAD_MINUTES = 5
SETUP_MARGIN_MINUTES = 15
EVENT, REF = 'workflow_dispatch', 'refs/heads/main'
# V3 (one session per dispatch): the pinned attempt tag (XA3; the VPS guard admits the same pattern), the
# session job's step budget (5 runs x 16.5 min in the collection step) and the files the registration pins.
ATTEMPT_TAG = re.compile(r'refs/tags/ct-xd1-c-a[1-9][0-9]{0,2}')
SESSION_COLLECT_STEP_MINUTES = 90   # 5 runs x 16.5 min, 7.5 min to spare
# The steps before the collection with their own timeout-minutes: the source download, Core fetch, toolchain,
# build, T4-2 tests and the marker upload.
SESSION_PREP_STEP_MINUTES = (10, 10, 15, 90, 20, 5)
REGISTRATION_LIMIT = 1 << 20
REGISTERED_PATHS = (
    'tools/claude_track_xd1_check.py', 'tools/claude_track_xd1_driver.py', 'tools/claude_track_xd1_collect.py',
    'tools/claude_track_xd1_supervisor.py', 'tools/claude_track_xd1_confirm.py', 'tools/claude_track_xd1_decide.py',
    'tools/claude_track_regtest_offline_export.py', 'tools/claude_track_exit.py',
    '.github/workflows/claude-track-xd1-confirmatory.yml', 'docs/claude-track/formats/XD1_EVENT_CHAIN_V3.md',
    'crates/bitagi-launch-host/tests/two_node_launch_accept.rs')
GIT_SECONDS = 60
# C2 (A, 2026-11-10): the EXPLORATORY pilot through the tag path runs the registration read and the tool-hash check
# against this TEST_ONLY file (A commits it on main naming the pilot's commit, with `pilot-registration`).
# CONFIRMATORY refuses it by its path, any path under tests/, and its label, so it can never count.
PILOT_REGISTRATION = 'tests/fixtures/xd1/XD1_PILOT_REGISTRATION_TEST_ONLY.json'
PILOT_LABEL = 'XD1_PILOT_REGISTRATION_TEST_ONLY_NEVER_A_REGISTRATION'
PILOT_NOTE = ('TEST_ONLY. Class T. Exercises the XD-1 registration read for the EXPLORATORY pilot; it is not a '
              'registration, and a CONFIRMATORY dispatch refuses it.')


class Refused(Exception):
    """Exit 2 with this label."""


def runs_of(slice_: int, n: int) -> range:
    """The run indices of slice k (1-based): at most SLICE_RUNS, in order."""
    return range((slice_ - 1) * check.SLICE_RUNS + 1, min(slice_ * check.SLICE_RUNS, n) + 1)


def checked_n(n: int) -> int:
    if type(n) is not int or not 1 <= n <= check.MAX_XD1_RUNS:
        raise Refused('N outside 1..MAX_XD1_RUNS')
    return n


def checked_slice(slice_: int, n: int) -> int:
    if type(slice_) is not int or not 1 <= slice_ <= math.ceil(checked_n(n) / check.SLICE_RUNS):
        raise Refused('slice outside 1..ceil(N/10)')
    return slice_


def static_budget(runs: int = check.SLICE_RUNS) -> None:
    """The configured slice budget, before any job starts."""
    if runs * RUN_SLOT_S > COLLECT_STEP_MINUTES * 60:
        raise Refused('BUDGET: the runs do not fit the collection step')
    if sum(PREP_STEP_MINUTES) + SETUP_MARGIN_MINUTES + COLLECT_STEP_MINUTES + UPLOAD_MINUTES > SLICE_JOB_MINUTES:
        raise Refused('BUDGET: the slice job does not fit 330 min')


def measured_budget(runs: int, spent_seconds: int) -> None:
    """Before collection, with the time the job has spent so far: the collection step is charged its whole
    timeout, so the upload still fits inside the job's 330 min whatever the runs take."""
    static_budget(runs)
    if type(spent_seconds) is not int or spent_seconds < 0:
        raise Refused('BUDGET: spent seconds')
    if spent_seconds + (COLLECT_STEP_MINUTES + UPLOAD_MINUTES) * 60 > SLICE_JOB_MINUTES * 60:
        raise Refused('BUDGET: the spent time, the collection step and the upload do not fit 330 min')


def first_attempt(environ) -> None:
    """A collection runs once: a GitHub re-run (attempt 2 or later) of any of its jobs is refused, so no
    declared run is run again and no second collection is made under the same run id."""
    if environ.get('GITHUB_RUN_ATTEMPT') != '1':
        raise Refused('a re-run: GITHUB_RUN_ATTEMPT is not 1')


def plan(n: int, environ) -> dict:
    if environ.get('GITHUB_EVENT_NAME') != EVENT or environ.get('GITHUB_REF') != REF:
        raise Refused('a workflow_dispatch on refs/heads/main only')
    first_attempt(environ)
    checked_n(n)
    for k in range(1, math.ceil(n / check.SLICE_RUNS) + 1):
        static_budget(len(runs_of(k, n)))
    return {'n': n, 'slices': list(range(1, math.ceil(n / check.SLICE_RUNS) + 1))}


class Prerequisite(Exception):
    """Exit 3 with this label."""


def github_ids(environ) -> tuple[int, int, str]:
    run_id, attempt, sha = (environ.get(k, '') for k in ('GITHUB_RUN_ID', 'GITHUB_RUN_ATTEMPT', 'GITHUB_SHA'))
    if not (re.fullmatch(r'[1-9][0-9]{0,18}', run_id) and re.fullmatch(r'[1-9][0-9]{0,9}', attempt)
            and check.HEX40.fullmatch(sha)):
        raise Prerequisite('GITHUB_RUN_ID, GITHUB_RUN_ATTEMPT and GITHUB_SHA')
    return int(run_id), int(attempt), sha


def write_once(path: Path, value: dict) -> None:
    """A new file, never over another."""
    raw = (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode('ascii')
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    except FileExistsError:
        raise Refused(f'{path.name} exists') from None
    try:
        view = memoryview(raw)
        while view:
            view = view[os.write(fd, view):]
        os.fsync(fd)
    finally:
        os.close(fd)


def declaration(n: int, environ) -> dict:
    run_id, attempt, sha = github_ids(environ)
    first_attempt(environ)
    return {'format': check.FORMAT_DECLARATION_V2, 'n': checked_n(n), 'head_sha': sha, 'run_id': run_id,
            'run_attempt': attempt}


def t42_record(slice_: int, result: str, environ) -> dict:
    sha = github_ids(environ)[2]
    first_attempt(environ)
    if result not in check.T42_RESULTS:
        raise Refused('T4-2 result')
    return {'format': check.FORMAT_T42, 'slice': slice_, 'head_sha': sha, 'result': result}


def collect(slice_: int, n: int, records: Path, node_a: Path, node_b: Path, work_root: Path,
            python: str = sys.executable, driver: Path = DRIVER, supervisor_: Path = SUPERVISOR) -> dict:
    """Runs the slice's runs in order; a supervisor that does not end with 0 ends the slice."""
    checked_slice(slice_, n)
    if not records.is_dir():
        raise Prerequisite('the records directory')
    work_root.mkdir(parents=True, exist_ok=False)
    done, ended = [], None
    for index in runs_of(slice_, n):   # every run of the slice, until a supervisor ends the slice
        work = work_root / f'run-{index}'
        command = [python, '-B', str(supervisor_), 'run', '--work', str(work), '--',
                   python, '-B', str(driver), 'run', '--index', str(index), '--records', str(records),
                   '--node-a', str(node_a), '--node-b', str(node_b), '--work', str(work)]
        got = subprocess.run(command, stdout=subprocess.PIPE, check=False)
        try:
            summary = json.loads(got.stdout)
        except ValueError:
            summary = None
        if type(summary) is not dict:
            summary = {'result': 'UNREADABLE'}
        done.append({'run_index': index, 'supervisor_exit': got.returncode, 'result': summary.get('result'),
                     'driver_exit': summary.get('driver_exit'), 'killed_at_cap': summary.get('killed_at_cap'),
                     'record': (records / f'run-{index}.json').is_file()})
        if got.returncode != 0:
            ended = index   # the next run must not start (supervisor exit 2 or 3)
            break
    failed = [r['run_index'] for r in done
              if r['result'] == 'UNREADABLE' or not (r['record'] or r['killed_at_cap'] is True)]
    return {'slice': slice_, 'n': n, 'runs': done, 'ended_after_run': ended, 'failed_runs': failed,
            'not_run': [i for i in runs_of(slice_, n) if i not in {r['run_index'] for r in done}]}


# ------------------------------------------------------------------------------------ V3: one session ----
def session_n(mode: str, first: int, last: int) -> int:
    """The declared N of a session (CONFIRMATORY 20; an EXPLORATORY pilot its own runs), after the session rules
    of XD1_EVENT_CHAIN_V3.md section 2."""
    if mode not in check.MODES_V3:
        raise Refused('mode')
    if not all(type(x) is int for x in (first, last)) or not 1 <= first <= last or last - first >= check.SESSION_RUNS:
        raise Refused('SESSION: 1 to 5 consecutive runs')
    if mode == 'CONFIRMATORY':
        if last > check.MAX_XD1_RUNS:
            raise Refused('SESSION: runs outside 1..20')
        return check.MAX_XD1_RUNS
    if first != 1:
        raise Refused('SESSION: an EXPLORATORY pilot starts at run 1')
    return last


def session_budget(runs: int) -> None:
    if runs * RUN_SLOT_S > SESSION_COLLECT_STEP_MINUTES * 60:
        raise Refused('BUDGET: the runs do not fit the collection step')
    if (sum(SESSION_PREP_STEP_MINUTES) + SETUP_MARGIN_MINUTES + SESSION_COLLECT_STEP_MINUTES + UPLOAD_MINUTES
            > SLICE_JOB_MINUTES):
        raise Refused('BUDGET: the session job does not fit 330 min')


def session_measured_budget(runs: int, spent_seconds: int) -> None:
    session_budget(runs)
    if type(spent_seconds) is not int or spent_seconds < 0:
        raise Refused('BUDGET: spent seconds')
    if spent_seconds + (SESSION_COLLECT_STEP_MINUTES + UPLOAD_MINUTES) * 60 > SLICE_JOB_MINUTES * 60:
        raise Refused('BUDGET: the spent time, the collection step and the upload do not fit 330 min')


def git(*args: str) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(['git', *args], capture_output=True, timeout=GIT_SECONDS, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise Prerequisite('git') from None


def canonical_path(path: str) -> bool:
    """A canonical relative repository path: `a/b/c`, no leading `/` or `./`, no `.`, `..` or empty part, no
    backslash or colon (verifier N5: `./tests/...` must not pass as a path outside tests/)."""
    parts = path.split('/')
    return bool(path) and '\\' not in path and ':' not in path and all(part not in ('', '.', '..') for part in parts)


def registration_bytes(path: str) -> bytes:
    """The registration as merged on main: the blob `refs/remotes/origin/main:<path>` (a canonical relative path)."""
    if not canonical_path(path):
        raise Refused('REGISTRATION_PATH')
    if git('rev-parse', '--verify', '--quiet', 'refs/remotes/origin/main').returncode != 0:
        raise Prerequisite('refs/remotes/origin/main')
    kind = git('cat-file', '-t', f'refs/remotes/origin/main:{path}')
    if kind.returncode != 0 or kind.stdout.strip() != b'blob':
        raise Refused('REGISTRATION_NOT_ON_MAIN')
    size = git('cat-file', '-s', f'refs/remotes/origin/main:{path}')
    if size.returncode != 0 or int(size.stdout.strip() or b'0') > REGISTRATION_LIMIT:
        raise Refused('REGISTRATION_SIZE')
    blob = git('cat-file', 'blob', f'refs/remotes/origin/main:{path}')
    if blob.returncode != 0:
        raise Prerequisite('the registration blob')
    return blob.stdout


def check_registration(blob: bytes, sha256: str, head: str, root: Path | None = None, pilot: bool = False) -> dict:
    """XA3 and the follow-up registration's XD-1 keys (V3 section 8): the bytes' SHA-256 is the input, the
    pinned commit is this commit, and the registered tool hashes are exactly this checkout's REGISTERED_PATHS.
    `pilot` (the EXPLORATORY pilot through a tag, A's C2 decision of 2026-11-10): the file must carry PILOT_LABEL;
    otherwise (CONFIRMATORY) a file that carries it is refused (REGISTRATION_TEST_ONLY), so it never counts."""
    root = TOOLS.parent if root is None else root
    if hashlib.sha256(blob).hexdigest() != sha256:
        raise Refused('REGISTRATION_SHA256_MISMATCH')
    if (PILOT_LABEL.encode('ascii') in blob) != pilot:
        raise Refused('REGISTRATION_TEST_ONLY' if not pilot else 'PILOT_REGISTRATION_LABEL')
    try:
        value = check.parse(blob)
    except check.Invalid:
        raise Refused('REGISTRATION_JSON') from None
    if pilot and value.get('label') != PILOT_LABEL:
        raise Refused('PILOT_REGISTRATION_LABEL')
    xd1 = value.get('xd1')
    if type(xd1) is not dict or set(xd1) != {'pinned_commit', 'tool_sha256'}:
        raise Refused('REGISTRATION_XD1_MISSING')
    tools = xd1['tool_sha256']
    if type(tools) is not dict or set(tools) != set(REGISTERED_PATHS) or not all(map(check.is_hash, tools.values())):
        raise Refused('REGISTRATION_TOOLS')
    if type(xd1['pinned_commit']) is not str or not check.HEX40.fullmatch(xd1['pinned_commit']):
        raise Refused('REGISTRATION_PINNED_COMMIT')
    if xd1['pinned_commit'] != head:
        raise Refused('NOT_THE_PINNED_COMMIT')
    for path in REGISTERED_PATHS:
        try:
            raw = (root / path).read_bytes()
        except OSError:
            raise Refused(f'REGISTERED_FILE_MISSING {path}') from None
        if hashlib.sha256(raw).hexdigest() != tools[path]:
            raise Refused(f'TOOL_SHA256_MISMATCH {path}')
    return xd1


def on_main_first_parent(head: str) -> bool:
    """Whether `head` is on main's first-parent chain (a commit main pointed at, not one a merge brought in)."""
    done = git('rev-list', '--first-parent', 'refs/remotes/origin/main')
    if done.returncode != 0:
        raise Prerequisite('refs/remotes/origin/main')
    return head.encode('ascii') in done.stdout.split()


def pilot_registration(commit: str) -> dict:
    """A TEST_ONLY pilot registration naming `commit` and the SHA-256 of each REGISTERED_PATHS file at that commit
    (for PILOT_REGISTRATION; it is never a registration and CONFIRMATORY refuses it)."""
    if not check.HEX40.fullmatch(commit):
        raise Refused('PILOT_COMMIT')
    if not on_main_first_parent(commit):   # verifier N7: as plan-v3 would refuse it
        raise Refused('PILOT_COMMIT_NOT_ON_MAIN: the pilot commit is not on main\'s first-parent chain')
    tools = {}
    for path in REGISTERED_PATHS:
        blob = git('cat-file', 'blob', f'{commit}:{path}')
        if blob.returncode != 0:
            raise Refused(f'PILOT_FILE_MISSING {path}')
        tools[path] = hashlib.sha256(blob.stdout).hexdigest()
    return pilot_registration_value(commit, tools)


def pilot_registration_value(commit: str, tools: dict) -> dict:
    return {'label': PILOT_LABEL, 'note': PILOT_NOTE, 'xd1': {'pinned_commit': commit, 'tool_sha256': dict(tools)}}


def plan_v3(mode: str, first: int, last: int, expected_head: str, registration: str | None,
            registration_sha256: str | None, environ, root: Path | None = None) -> dict:
    if environ.get('GITHUB_EVENT_NAME') != EVENT:
        raise Refused('a workflow_dispatch only')
    first_attempt(environ)
    head = environ.get('GITHUB_SHA', '')
    if not check.HEX40.fullmatch(head) or head != expected_head:
        raise Refused('EXPECTED_HEAD: the dispatched commit is not the expected head')
    n = session_n(mode, first, last)
    session_budget(last - first + 1)
    ref = environ.get('GITHUB_REF', '')
    tagged = ATTEMPT_TAG.fullmatch(ref) is not None
    if mode == 'CONFIRMATORY':
        if not tagged:
            raise Refused('a CONFIRMATORY session dispatches from a pinned attempt tag ct-xd1-c-a<N> only')
        if not registration or not check.is_hash(registration_sha256):
            raise Refused('REGISTRATION_INPUTS')
        if not canonical_path(registration):
            raise Refused('REGISTRATION_PATH')
        if registration == PILOT_REGISTRATION or PurePosixPath(registration).parts[0] == 'tests':
            raise Refused('REGISTRATION_TEST_ONLY: a test fixture is never a registration')
    elif tagged:   # the pilot through the tag path (C2): the TEST_ONLY pilot registration only, checked in full
        if registration != PILOT_REGISTRATION or not check.is_hash(registration_sha256):
            raise Refused(f'PILOT_REGISTRATION: an EXPLORATORY pilot from a tag names {PILOT_REGISTRATION}')
    else:
        if ref != REF:
            raise Refused('an EXPLORATORY pilot dispatches from refs/heads/main or a ct-xd1-c-a<N> tag only')
        if registration or registration_sha256:
            raise Refused('EXPLORATORY_INPUTS: no registration from main')
    if tagged:
        if not on_main_first_parent(head):
            raise Refused('NOT_ON_MAIN: the pinned commit is not on main\'s first-parent chain')
        check_registration(registration_bytes(registration), registration_sha256, head, root,
                           pilot=mode == 'EXPLORATORY')
    return {'mode': mode, 'n': n, 'first_run': first, 'last_run': last,
            'registration_sha256': registration_sha256 if mode == 'CONFIRMATORY' else None}


def declaration_v3(mode: str, first: int, last: int, registration_sha256: str | None, environ) -> dict:
    run_id, attempt, sha = github_ids(environ)
    first_attempt(environ)
    n = session_n(mode, first, last)
    if (mode == 'CONFIRMATORY') != (registration_sha256 is not None) or (
            registration_sha256 is not None and not check.is_hash(registration_sha256)):
        raise Refused('REGISTRATION_INPUTS')
    return {'format': check.FORMAT_DECLARATION_V3, 'mode': mode, 'n': n, 'first_run': first, 'last_run': last,
            'head_sha': sha, 'run_id': run_id, 'run_attempt': attempt, 'registration_sha256': registration_sha256}


def read_session(path: Path, environ) -> dict:
    """The plan job's V3 declaration, bound to this run (its ids and head are this job's GITHUB_* values)."""
    try:
        value = check.read_declaration(path)
    except check.Refusal as refusal:
        if refusal.code == 3:
            raise Prerequisite('the declaration') from None
        raise Refused(f'declaration: {refusal}') from None
    if check.version_of(value) != 3:
        raise Refused('declaration: not V3')
    if (value['run_id'], value['run_attempt'], value['head_sha']) != github_ids(environ):
        raise Refused('declaration: another run')
    first_attempt(environ)
    return value


def marker(declaration: dict) -> dict:
    """The session-start marker (V3 section 3): the declaration's session, written before its first run."""
    return {'format': check.FORMAT_MARKER_V3, **{k: declaration[k] for k in (
        'mode', 'first_run', 'last_run', 'head_sha', 'run_id', 'run_attempt', 'registration_sha256')}}


def collect_v3(declaration: dict, records: Path, node_a: Path, node_b: Path, work_root: Path, console: Path,
               python: str = sys.executable, driver: Path = DRIVER, supervisor_: Path = SUPERVISOR) -> dict:
    """The session's runs in order, each a supervisor over one live-decision driver run (collect's rules)."""
    if not records.is_dir():
        raise Prerequisite('the records directory')
    if not console.is_dir():
        raise Prerequisite('the console directory')
    first, last = declaration['first_run'], declaration['last_run']
    extra = ['--mode', declaration['mode'], '--decision', 'live', '--console-dir', str(console)]
    if declaration['registration_sha256'] is not None:
        extra += ['--registration-sha256', declaration['registration_sha256']]
    work_root.mkdir(parents=True, exist_ok=False)
    runs = range(first, last + 1)
    done, ended = [], None
    for index in runs:
        work = work_root / f'run-{index}'
        command = [python, '-B', str(supervisor_), 'run', '--work', str(work), '--',
                   python, '-B', str(driver), 'run', '--index', str(index), '--records', str(records),
                   '--node-a', str(node_a), '--node-b', str(node_b), '--work', str(work), *extra]
        got = subprocess.run(command, stdout=subprocess.PIPE, check=False)
        try:
            summary = json.loads(got.stdout)
        except ValueError:
            summary = None
        if type(summary) is not dict:
            summary = {'result': 'UNREADABLE'}
        done.append({'run_index': index, 'supervisor_exit': got.returncode, 'result': summary.get('result'),
                     'driver_exit': summary.get('driver_exit'), 'killed_at_cap': summary.get('killed_at_cap'),
                     'record': (records / f'run-{index}.json').is_file()})
        if got.returncode != 0:
            ended = index
            break
    failed = [r['run_index'] for r in done
              if r['result'] == 'UNREADABLE' or not (r['record'] or r['killed_at_cap'] is True)]
    return {'first_run': first, 'last_run': last, 'runs': done, 'ended_after_run': ended, 'failed_runs': failed,
            'not_run': [i for i in runs if i not in {r['run_index'] for r in done}]}


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest='mode', required=True)
    plan_ = sub.add_parser('plan')
    plan_.add_argument('--n', type=int, required=True)
    plan_.add_argument('--github-output', type=Path, required=True)
    declare = sub.add_parser('declare')
    declare.add_argument('--n', type=int, required=True)
    declare.add_argument('--output', type=Path, required=True)
    budget = sub.add_parser('budget')
    budget.add_argument('--slice', type=int, required=True)
    budget.add_argument('--n', type=int, required=True)
    budget.add_argument('--spent-seconds', type=int, required=True)
    t42 = sub.add_parser('t42')
    t42.add_argument('--slice', type=int, required=True)
    t42.add_argument('--n', type=int, required=True)
    t42.add_argument('--records', type=Path, required=True)
    t42.add_argument('--result', required=True)
    run = sub.add_parser('collect')
    run.add_argument('--slice', type=int, required=True)
    run.add_argument('--n', type=int, required=True)
    run.add_argument('--records', type=Path, required=True)
    run.add_argument('--node-a', type=Path, required=True)
    run.add_argument('--node-b', type=Path, required=True)
    run.add_argument('--work-root', type=Path, required=True)
    plan3 = sub.add_parser('plan-v3')
    declare3 = sub.add_parser('declare-v3')
    for each in (plan3, declare3):
        each.add_argument('--mode', dest='session_mode', required=True)   # the subcommand is `mode`
        each.add_argument('--first-run', type=int, required=True)
        each.add_argument('--last-run', type=int, required=True)
        each.add_argument('--registration-sha256', default='')
    plan3.add_argument('--registration', default='')
    plan3.add_argument('--expected-head', required=True)
    plan3.add_argument('--github-output', type=Path, required=True)
    declare3.add_argument('--output', type=Path, required=True)
    mark = sub.add_parser('marker')
    mark.add_argument('--declaration', type=Path, required=True)
    mark.add_argument('--output', type=Path, required=True)
    t42v3 = sub.add_parser('t42-v3')
    t42v3.add_argument('--declaration', type=Path, required=True)
    t42v3.add_argument('--records', type=Path, required=True)
    t42v3.add_argument('--result', required=True)
    budget3 = sub.add_parser('budget-v3')
    budget3.add_argument('--declaration', type=Path, required=True)
    budget3.add_argument('--spent-seconds', type=int, required=True)
    pilot = sub.add_parser('pilot-registration')
    pilot.add_argument('--pinned-commit', required=True)
    pilot.add_argument('--output', type=Path, required=True)
    run3 = sub.add_parser('collect-v3')
    run3.add_argument('--declaration', type=Path, required=True)
    run3.add_argument('--records', type=Path, required=True)
    run3.add_argument('--node-a', type=Path, required=True)
    run3.add_argument('--node-b', type=Path, required=True)
    run3.add_argument('--work-root', type=Path, required=True)
    run3.add_argument('--console-dir', type=Path, required=True)
    return p


def main(argv=None) -> int:
    if not __debug__:
        print(json.dumps({'result': 'REFUSED', 'failure': 'OPTIMIZED_PYTHON'}), file=sys.stderr)
        return 5
    a = parser().parse_args(sys.argv[1:] if argv is None else argv)
    try:
        if a.mode == 'plan':
            value = plan(a.n, os.environ)
            with open(a.github_output, 'a', encoding='ascii', newline='') as out:
                out.write(f"n={value['n']}\nslices={json.dumps(value['slices'], separators=(',', ':'))}\n")
        elif a.mode == 'declare':
            value = declaration(a.n, os.environ)
            write_once(a.output, value)
        elif a.mode == 'budget':
            measured_budget(len(runs_of(checked_slice(a.slice, a.n), a.n)), a.spent_seconds)
            value = {'slice': a.slice, 'runs': len(runs_of(a.slice, a.n)), 'spent_seconds': a.spent_seconds}
        elif a.mode == 't42':
            if not a.records.is_dir():
                raise Prerequisite('the records directory')
            value = t42_record(checked_slice(a.slice, a.n), a.result, os.environ)
            write_once(a.records / f't42-slice-{a.slice}.json', value)
        elif a.mode == 'collect':
            first_attempt(os.environ)
            value = collect(a.slice, a.n, a.records.resolve(), a.node_a.resolve(), a.node_b.resolve(),
                            a.work_root.resolve(), driver=DRIVER, supervisor_=SUPERVISOR)
        else:
            value = main_v3(a)
    except Refused as error:
        print(json.dumps({'result': 'REFUSED', 'failure': str(error)}), file=sys.stderr)
        return 2
    except Prerequisite as error:
        print(json.dumps({'result': 'PREREQUISITE', 'failure': str(error)}), file=sys.stderr)
        return 3
    except Exception as error:  # noqa: BLE001 - one bounded internal-error line, no free text
        print(json.dumps({'result': 'FAIL', 'failure': 'INTERNAL:' + type(error).__name__}), file=sys.stderr)
        return 4
    # A record (declare, t42) is printed under its own key: its `result` (PASS or FAIL) never replaces DONE.
    printed = {'record': value} if a.mode in ('declare', 't42', 'declare-v3', 'marker', 't42-v3') else value
    print(json.dumps({'result': 'DONE', 'mode': a.mode, **printed}, sort_keys=True))
    return 2 if a.mode in ('collect', 'collect-v3') and (value['ended_after_run'] is not None
                                                          or value['failed_runs']) else 0


def main_v3(a) -> dict:
    """The V3 subcommands (one session per dispatch)."""
    if a.mode == 'plan-v3':
        value = plan_v3(a.session_mode, a.first_run, a.last_run, a.expected_head, a.registration or None,
                        a.registration_sha256 or None, os.environ)
        with open(a.github_output, 'a', encoding='ascii', newline='') as out:
            out.write(''.join(f'{k}={"" if v is None else v}\n' for k, v in value.items()))
        return value
    if a.mode == 'declare-v3':
        value = declaration_v3(a.session_mode, a.first_run, a.last_run, a.registration_sha256 or None, os.environ)
        write_once(a.output, value)
        return value
    if a.mode == 'pilot-registration':
        value = pilot_registration(a.pinned_commit)
        raw = (json.dumps(value, indent=1, sort_keys=True) + '\n').encode('ascii')
        try:
            fd = os.open(a.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
        except FileExistsError:
            raise Refused(f'{a.output.name} exists') from None
        try:
            os.write(fd, raw)
        finally:
            os.close(fd)
        return {'pinned_commit': a.pinned_commit, 'sha256': hashlib.sha256(raw).hexdigest()}
    declaration = read_session(a.declaration, os.environ)
    if a.mode == 'marker':
        value = marker(declaration)
        write_once(a.output, value)
        return value
    if a.mode == 't42-v3':
        if not a.records.is_dir():
            raise Prerequisite('the records directory')
        if a.result not in check.T42_RESULTS:
            raise Refused('T4-2 result')
        value = {'format': check.FORMAT_T42, 'slice': declaration['first_run'], 'head_sha': declaration['head_sha'],
                 'result': a.result}
        write_once(a.records / f't42-slice-{declaration["first_run"]}.json', value)
        return value
    if a.mode == 'budget-v3':
        runs = declaration['last_run'] - declaration['first_run'] + 1
        session_measured_budget(runs, a.spent_seconds)
        return {'runs': runs, 'spent_seconds': a.spent_seconds}
    return collect_v3(declaration, a.records.resolve(), a.node_a.resolve(), a.node_b.resolve(),
                      a.work_root.resolve(), a.console_dir.resolve())


if __name__ == '__main__':
    import claude_track_exit
    claude_track_exit.run(main)
