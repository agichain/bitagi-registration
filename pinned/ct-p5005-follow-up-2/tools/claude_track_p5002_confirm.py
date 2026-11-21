"""P5-002 endurance attempts across dispatches: the listing, the next attempt and the report (XA13, PR-1, PR-2a,
PR-2b).

Class T, private Signet, scope (b). Runs only in the hosted jobs of `.github/workflows/claude-track-p5002.yml`
(the plan and report jobs, which hold an `actions: read` token), never on the VPS. The interface is
docs/claude-track/formats/P5002_ENDURANCE_V1.md (sections 3, 7, 8 and 9); the pattern is
`tools/claude_track_xd1_confirm.py`. The checker (`tools/claude_track_p5002_check.py`) is the only module
imported besides the standard library, and only by the names of the document's section 13: every result of an
attempt is the checker's (`attempt_row`, `verdict`, `collection_report`, `observation_list`). This tool reads the
saved Actions API answers, decides which dispatches are counted, and hands the checker each counted attempt's
bytes with the server times of its artifacts and of its observe job.

  pages --dir LISTING
  runs --listing DIR --mode M --registration-sha256 HEX --run-id ID
  downloads --dir RUN_DIR --run-id ID
  continuity --listing DIR --attempts DIR --mode M --registration-sha256 HEX --run-id ID --head-sha SHA
             --attempt N
  report --listing DIR --attempts DIR --mode M --registration-sha256 HEX --run-id ID --head-sha SHA
         --run-attempt N --source-sha256 HEX --output NEW_FILE [--observations NEW_FILE]
  s04-run --dir DIR --s04-run-id ID --commit SHA
  s04-artifact --dir DIR --s04-run-id ID --run-attempt N
  s04-job --dir DIR --s04-run-id ID --run-attempt N

The workflow saves each Actions API answer (GET only) before the tool reads it: the listing of this workflow's
workflow_dispatch runs (`<listing>/runs-<p>.json`, 100 per page) and, per run read, `<attempts>/<run_id>/`
`artifacts.json`, `jobs.json` (attempt 1) and the zips the `downloads` command names (`declaration.zip`,
`marker.zip`, `checkpoint-<k>.zip`, `records.zip`).

* A dispatch's run name is `p5002 <MODE> attempt <N> registration <sha256|none>` (the checker's `TITLE`). The
  CONFIRMATORY dispatches of one registration are this workflow's dispatches with that mode and hash; every
  other run of the workflow must be completed, and one whose name is not that shape is read too and must never
  have started. EXPLORATORY reads its own dispatch only.
* An attempt is counted when its run lists the marker artifact `p5002-started` (uploaded by its observe job
  after sample 0). A run that does not list it is NEVER_STARTED (listed, not counted, its attempt number free
  again) only when it shows no other sign of a start: no checkpoint artifact, no `marker.json` in an unexpired
  `p5002-records` artifact (the driver writes that file last, once sample 0 is taken), and in its attempt-1
  jobs listing no observe job whose step `Upload the marker` succeeded. With such a sign the marker artifact is
  missing although the attempt started (MARKER_MISSING): the run is never taken for one that did not start. An
  expired marker refuses.
* CONFIRMATORY: the listing's `run_number` values from the first dispatch of this registration to this run
  have no gap (RUN_LIST_GAP). The workflow is dispatch-only, so every run of it is in the listing and a deleted
  run leaves a number that no listed run has, whatever the mode of the runs between.
* `continuity` (plan job, before the observe job): the counted attempts, in creation order, are attempts 1..k at
  this commit, k is below MAX_ATTEMPTS, this run's name is its inputs, this attempt is k + 1, and every counted
  attempt still lists its declaration (one that does not can only be UNREADABLE, which makes every later
  verdict INCONCLUSIVE: EARLIER_ATTEMPT_UNREADABLE). An attempt whose records are lost is not refused: the
  report lists it LOST and it counts as an attempt.
* `report` (report job): every counted attempt's declaration, marker, checkpoints and records with each
  artifact's server `created_at` and the observe job's server `started_at`, read by the checker's
  `attempt_row`; an attempt whose records are missing, expired or invalid is listed LOST, and one that cannot
  be read for another cause stays in the report as UNREADABLE with its cause; a refused coverage lists every
  counted dispatch as COMPLETENESS_REFUSED, reads no record, and is named by the report's `coverage` key and on
  the command's line (no stderr line). A never-started run's uploaded records are read for one thing: a
  critical read that disagreed before the marker. CONFIRMATORY gets the checker's verdict and, when an attempt
  is counted and none is unreadable, the observation list. No attempt is erased, and no interval of one attempt
  is added to another's: each row is one attempt's own.
* This run's listing must hold no `p5002-report-attempt-<n>` for n at or above this run attempt
  (REPORT_ARTIFACT_PRESENT: the hosted report job has not uploaded it, so someone else did); the declaration
  artifact must predate the observe job's start, and this run's declaration must name the tree hash the plan
  job passed on (`--source-sha256`), else that attempt is DECLARATION_REFUSED.
* `s04-run`, `s04-artifact`, `s04-job` (PR-2a; the plan job's step "Read the cited S04 run", before `plan`, for a
  dispatch from an attempt tag): which file the step fetches next, as ARDR's three commands of the same names.
  Each reads the answer the step saved last and judges it with the checker's own function of plan check 9
  (`s04_run`, `s04_artifact_id`, `s04_job_id`), so a refusal here is plan check 9's code for that answer; `plan`
  then reads every saved file again in the format document's order.
* A checkpoint artifact that is listed but expired, or whose file is absent from its zip or over its limit, is
  handed to the checker as an empty file, so the server-anchor rule SA5 fails; the same for the marker's file
  and the declaration's is DECLARATION_REFUSED. A zip that is not saved, is not a zip or does not have its
  listed digest refuses the command: the report job is run again, the attempt is not judged on it.

Every command prints one line of canonical JSON on stdout (the document's section 3) and never echoes input
text, a label, a file name or a path. Exit codes: 0 done (a report with PASS, FAIL or OPEN, or a read
EXPLORATORY attempt); 2 validation (a malformed listing or argument, and a report written INCONCLUSIVE with its
cause); 3 unavailable (a missing or unreadable saved answer); 4 internal; 5 security; 6 refusal (optimized
Python among them). No `assert` is a control. Stdlib only; nothing of ARDR or XD-1 and no `tools/common.py` is
imported here (a CONFIRMATORY `report` reads the required seconds through the checker's `required_seconds()`,
in a hosted job; `continuity` reads no policy: the attempt limit is the checker's MAX_ATTEMPTS).
"""
from __future__ import annotations

import argparse
import calendar
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import sys
import time
import zipfile
import zlib

import claude_track_p5002_check as check

TOOL = 'p5002_confirm'
RUN_LIST_PAGE, RUN_LIST_CAP = 100, 1000
ARTIFACT_PAGE = 100            # one page of a run's artifact listing; a run of this workflow lists far fewer
UTC = re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z')
HEX40 = re.compile(r'[0-9a-f]{40}')
HEX64 = re.compile(r'[0-9a-f]{64}')
CHECKPOINT_NAME = re.compile(re.escape(check.ARTIFACTS['checkpoint']) + r'([1-9][0-9]?)')
# The hosted report job's own artifact (`p5002-report-attempt-<run_attempt>`): no other job may upload that name.
REPORT_PREFIX = 'p5002-report-attempt-'
REPORT_NAME = re.compile(re.escape(REPORT_PREFIX) + r'([1-9][0-9]{0,2})')
# The artifacts read, by stem: the zip of stem S is saved as `<S>.zip` and holds the member `<S>.json`, except
# the records zip, which holds the checker's MEMBERS and its MONITOR_FILES (PR-2b).
STEMS = {check.ARTIFACTS['declaration']: 'declaration', check.ARTIFACTS['marker']: 'marker',
         check.ARTIFACTS['records']: 'records'}
RUN_FIELDS = ('display_title', 'status', 'event', 'path', 'head_sha', 'created_at')
MARKER_FILE = 'marker.json'    # the member of p5002-records that `start` writes last (S8)
EXPLORATORY_ATTEMPTS = 1       # an EXPLORATORY dispatch is its own collection: attempt 1 only


def need(condition, code) -> None:
    if not condition:
        raise check.Refusal(code)


# ---------------------------------------------------------------------------------------------- files ----
def _read(path, limit):
    """The bytes of a regular file that is not a link, at most `limit` + 1 of them; None when absent.
    PATH_NOT_REGULAR for a link or anything that is not a regular file."""
    try:
        info = os.lstat(path)
    except (FileNotFoundError, NotADirectoryError):
        return None
    if not stat.S_ISREG(info.st_mode):
        raise check.Refusal('PATH_NOT_REGULAR')
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, 'O_NONBLOCK', 0))
    except (FileNotFoundError, NotADirectoryError):
        return None
    except OSError:
        raise check.Refusal('PATH_NOT_REGULAR') from None
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise check.Refusal('PATH_NOT_REGULAR')
        chunks, size = [], 0
        while size <= limit:
            chunk = os.read(fd, min(1 << 20, limit + 1 - size))
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
    finally:
        os.close(fd)
    return b''.join(chunks)


def _free(path) -> None:
    """Nothing is at `path`: OUTPUT_EXISTS for a regular file there, PATH_NOT_REGULAR for a link or anything
    else."""
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return
    raise check.Refusal('OUTPUT_EXISTS' if stat.S_ISREG(info.st_mode) else 'PATH_NOT_REGULAR')


def write_new(path, raw: bytes) -> None:
    """A new file, never over another and never through a link."""
    _free(path)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    except FileExistsError:
        raise check.Refusal('OUTPUT_EXISTS') from None
    try:
        try:
            view = memoryview(raw)
            while view:
                view = view[os.write(fd, view):]
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError:
        try:   # no partial output is left behind
            os.unlink(path)
        except OSError:
            pass
        raise


def _pairs(pairs):
    keys = [key for key, _ in pairs]
    if len(keys) != len(set(keys)):
        raise ValueError('duplicate key')
    return dict(pairs)


def _no_constant(text):
    raise ValueError('constant')


def fetched(path, missing: str, malformed: str) -> dict:
    """A saved API answer: a regular file of at most FETCHED_LIMIT bytes holding one JSON object with no
    duplicate key. `missing` when it is absent or over the limit, `malformed` when it is not that object."""
    raw = _read(path, check.FETCHED_LIMIT)
    need(raw is not None and len(raw) <= check.FETCHED_LIMIT, missing)
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=_pairs, parse_constant=_no_constant)
    except (UnicodeDecodeError, ValueError, RecursionError):
        raise check.Refusal(malformed) from None
    need(type(value) is dict, malformed)
    return value


def epoch(utc):
    """A server time `YYYY-MM-DDThh:mm:ssZ` in whole seconds; None when it is not that text."""
    if type(utc) is not str or UTC.fullmatch(utc) is None:
        return None
    try:
        return calendar.timegm(time.strptime(utc, '%Y-%m-%dT%H:%M:%SZ'))
    except ValueError:
        return None


# -------------------------------------------------------------------------------------------- listing ----
def pages(folder: Path) -> int:
    total = fetched(folder / 'runs-1.json', 'RUN_LIST_MISSING', 'RUN_LIST_JSON').get('total_count')
    need(type(total) is int and total >= 0, 'RUN_LIST_SHAPE')
    need(total < RUN_LIST_CAP, 'RUN_LIST_CAPPED')
    return max(1, -(-total // RUN_LIST_PAGE))


def listing(folder: Path) -> list[dict]:
    """Every saved page: one total, every page but the last full, no run twice, each run's fields typed, each
    run a workflow_dispatch of this workflow with its own `run_number`."""
    count = pages(folder)
    total = fetched(folder / 'runs-1.json', 'RUN_LIST_MISSING', 'RUN_LIST_JSON')['total_count']
    runs = []
    for page in range(1, count + 1):
        doc = fetched(folder / f'runs-{page}.json', 'RUN_LIST_MISSING', 'RUN_LIST_JSON')
        items = doc.get('workflow_runs')
        need(type(doc.get('total_count')) is int and doc['total_count'] == total and type(items) is list
             and len(items) == (RUN_LIST_PAGE if page < count else total - RUN_LIST_PAGE * (count - 1)),
             'RUN_LIST_CHANGED')
        runs += items
    need(all(type(run) is dict and type(run.get('id')) is int and run['id'] > 0
             and type(run.get('run_number')) is int and run['run_number'] > 0
             and all(type(run.get(key)) is str for key in RUN_FIELDS)
             and UTC.fullmatch(run['created_at']) is not None and HEX40.fullmatch(run['head_sha']) is not None
             for run in runs), 'RUN_LIST_SHAPE')
    need(len({run['id'] for run in runs}) == len(runs), 'RUN_LIST_CHANGED')
    need(all(run['path'] == check.WORKFLOW_PATH and run['event'] == 'workflow_dispatch' for run in runs)
         and len({run['run_number'] for run in runs}) == len(runs), 'RUN_LIST_SHAPE')
    return runs


def dispatch(run: dict) -> dict:
    """A listed run as a dispatch: its id, its run name's mode, attempt and registration (all None when the name
    is not a run name of this workflow), its creation time, head, status and run number."""
    out = {'run_id': run['id'], 'created_at': run['created_at'], 'head_sha': run['head_sha'],
           'status': run['status'], 'run_number': run['run_number'], 'mode': None, 'attempt': None,
           'registration_sha256': None}
    title = check.TITLE.fullmatch(run['display_title'])
    if title is not None:
        out.update(mode=title.group(1), attempt=int(title.group(2)),
                   registration_sha256=None if title.group(3) == 'none' else title.group(3))
    return out


def all_completed(runs: list[dict], run_id: int) -> bool:
    """Every run of the workflow but this one has completed."""
    return all(run['id'] == run_id or run['status'] == 'completed' for run in runs)


def selected(runs: list[dict], mode: str, registration: str | None, run_id: int, complete: bool = True) -> list[dict]:
    """The dispatches the tool reads, in creation order: CONFIRMATORY, those of this registration and every run
    whose name is not a run name (each must never have started); EXPLORATORY, this run only. Every other run of
    the workflow must have completed (OTHER_RUN_IN_PROGRESS), unless `complete` is false: the `runs` command
    only names the runs to save, and `report` writes that code as the report's `coverage`."""
    out = []
    need(not complete or all_completed(runs, run_id), 'OTHER_RUN_IN_PROGRESS')
    for run in sorted(runs, key=lambda item: (item['created_at'], item['id'])):
        d = dispatch(run)
        if mode == 'EXPLORATORY':
            if d['run_id'] == run_id:
                out.append(d)
        elif d['mode'] is None or (d['mode'] == 'CONFIRMATORY' and d['registration_sha256'] == registration):
            out.append(d)
    need(any(d['run_id'] == run_id for d in out), 'THIS_RUN_NOT_LISTED')
    return out


def run_list_gap(runs: list[dict], registration: str | None, run_id: int) -> bool:
    """Section 8.3, CONFIRMATORY: some `run_number` from the first listed CONFIRMATORY dispatch of this
    registration to this run is the number of no listed run. Every run of the workflow has a number of one
    sequence, whatever its mode, registration or name, so a run that was deleted inside that range leaves its
    number unlisted. False when the listing names no such dispatch or this run lies before the first."""
    listed = {run['run_number'] for run in runs}
    named = [d['run_number'] for d in map(dispatch, runs)
             if d['mode'] == 'CONFIRMATORY' and d['registration_sha256'] == registration]
    this = [run['run_number'] for run in runs if run['id'] == run_id]
    return bool(named and this) and any(number not in listed for number in range(min(named), this[0] + 1))


def artifacts_of(folder: Path, run_id: int) -> dict:
    """{stem: {'id', 'digest', 'created', 'expired'}} of this harness's artifacts in one run's saved listing (one
    page): `declaration`, `marker`, `records`, `checkpoint-<k>` for k in 1..MAX_CHECKPOINTS and `report-<n>` (the
    report job's own, which no command reads). `created` is the artifact's server `created_at` in seconds. An
    artifact named twice, a checkpoint name outside that range and an item without its fields are
    ARTIFACT_LISTING; an expired marker is ARTIFACT_EXPIRED; another expired artifact stays, marked."""
    doc = fetched(folder / 'artifacts.json', 'INPUT_MISSING', 'ARTIFACT_LISTING')
    items = doc.get('artifacts')
    need(type(items) is list and type(doc.get('total_count')) is int and doc['total_count'] == len(items)
         and len(items) < ARTIFACT_PAGE, 'ARTIFACT_LISTING')
    found = {}
    for item in items:
        need(type(item) is dict and type(item.get('name')) is str and type(item.get('id')) is int and item['id'] > 0
             and type(item.get('expired')) is bool and type(item.get('workflow_run')) is dict
             and type(item['workflow_run'].get('id')) is int and item['workflow_run']['id'] == run_id,
             'ARTIFACT_LISTING')
        digest, created = item.get('digest'), epoch(item.get('created_at'))
        need(digest is None or (type(digest) is str and digest.startswith('sha256:')
                                and HEX64.fullmatch(digest[7:]) is not None), 'ARTIFACT_LISTING')
        need(created is not None and created >= 1, 'ARTIFACT_LISTING')
        stem = STEMS.get(item['name'])
        if stem is None and item['name'].startswith(check.ARTIFACTS['checkpoint']):
            numbered = CHECKPOINT_NAME.fullmatch(item['name'])
            need(numbered is not None and int(numbered.group(1)) <= check.MAX_CHECKPOINTS, 'ARTIFACT_LISTING')
            stem = 'checkpoint-' + numbered.group(1)
        if stem is None and REPORT_NAME.fullmatch(item['name']) is not None:
            stem = 'report-' + REPORT_NAME.fullmatch(item['name']).group(1)
        if stem is None:
            continue
        need(stem not in found, 'ARTIFACT_LISTING')
        need(stem != 'marker' or not item['expired'], 'ARTIFACT_EXPIRED')
        found[stem] = {'id': item['id'], 'digest': digest[7:] if digest else None, 'created': created,
                       'expired': item['expired']}
    return found


def counted(found: dict) -> bool:
    return 'marker' in found


def report_numbers(found: dict) -> list[int]:
    return sorted(int(stem.split('-')[1]) for stem in found if stem.startswith('report-'))


def marker_step_succeeded(folder: Path, run_id: int) -> bool:
    """The run's saved attempt-1 jobs listing shows the observe job's step `Upload the marker` concluded
    `success`. JOBS_LISTING when that job is listed without its steps."""
    doc = fetched(folder / 'jobs.json', 'INPUT_MISSING', 'JOBS_LISTING')
    items = doc.get('jobs')
    need(type(items) is list and type(doc.get('total_count')) is int and doc['total_count'] == len(items),
         'JOBS_LISTING')
    for job in items:
        if type(job) is dict and job.get('name') == check.OBSERVE_JOB_NAME and job.get('run_id') == run_id:
            steps = job.get('steps')
            need(type(steps) is list and all(type(step) is dict for step in steps), 'JOBS_LISTING')
            if any(step.get('name') == check.MARKER_STEP_NAME and step.get('conclusion') == 'success'
                   for step in steps):
                return True
    return False


def records_hold_marker(found: dict, folder: Path) -> bool:
    """The run's unexpired `p5002-records` artifact holds `marker.json`. The driver writes that file last (S8,
    after sample 0), so such records show an attempt that started; records without it are a `start` that did
    not reach the marker. A records artifact that is not listed or is expired shows nothing."""
    item = found.get('records')
    return item is not None and not item['expired'] and MARKER_FILE in zip_names(folder / 'records.zip',
                                                                                item['digest'])


def started_without_marker(found: dict, folder: Path, run_id: int) -> bool:
    """A run that lists no marker but did start (section 8.3): it lists a checkpoint artifact (the workflow
    uploads one only after the marker's upload succeeded), its records hold `marker.json`, or its jobs listing
    shows that the marker's upload succeeded. Its marker artifact is missing; it is never read as a dispatch
    that did not start."""
    return not counted(found) and (bool(_checkpoints(found)) or records_hold_marker(found, folder)
                                   or marker_step_succeeded(folder, run_id))


def _checkpoints(found: dict) -> list[int]:
    return sorted(int(stem.split('-')[1]) for stem in found if stem.startswith('checkpoint-'))


def stems(found: dict) -> list[str]:
    """The stems of one run's artifacts in reading order: declaration, marker, the checkpoints by index, records."""
    order = ['declaration', 'marker'] + [f'checkpoint-{k}' for k in _checkpoints(found)] + ['records']
    return [stem for stem in order if stem in found]


def coverage(attempts: list[dict], head_sha: str) -> int:
    """Section 8.3: the counted attempts, in creation order, are attempts 1, 2, ..., k at one commit; returns k.
    ATTEMPT_OTHER_COMMIT, ATTEMPT_GAP and ATTEMPT_OVERLAP refuse."""
    nxt = 1
    for d in attempts:
        need(d['head_sha'] == head_sha, 'ATTEMPT_OTHER_COMMIT')
        need(d['attempt'] <= nxt, 'ATTEMPT_GAP')
        need(d['attempt'] == nxt, 'ATTEMPT_OVERLAP')
        nxt += 1
    return nxt - 1


def classified(attempts_dir: Path, chosen: list[dict], skip: int | None = None) -> tuple[list, list, str | None]:
    """(the dispatches that started, those that never started, the first refusal or None), each list in
    creation order and each dispatch with its artifacts. A dispatch started when its run lists the marker, or
    lists none but shows another sign of a start (MARKER_MISSING); a run whose name is not a run name of this
    workflow must not have started (RUN_LIST_TITLE). The refusal is the first in the order RUN_LIST_TITLE,
    MARKER_MISSING."""
    started, never, codes = [], [], set()
    for d in chosen:
        if d['run_id'] == skip:
            continue
        folder = attempts_dir / str(d['run_id'])
        found = artifacts_of(folder, d['run_id'])
        erased = started_without_marker(found, folder, d['run_id'])
        if counted(found) or erased:
            if d['mode'] is None:
                codes.add('RUN_LIST_TITLE')
            if erased:
                codes.add('MARKER_MISSING')
            started.append({**d, 'artifacts': found})
        else:
            never.append({**d, 'artifacts': found})
    return started, never, next((code for code in ('RUN_LIST_TITLE', 'MARKER_MISSING') if code in codes), None)


def counted_dispatches(attempts_dir: Path, chosen: list[dict], skip: int | None = None) -> list[dict]:
    """The chosen dispatches that started, in creation order, each with its artifacts. RUN_LIST_TITLE and
    MARKER_MISSING refuse."""
    started, _, refusal = classified(attempts_dir, chosen, skip)
    need(refusal is None, refusal or 'MARKER_MISSING')
    return started


def continuity(runs: list[dict], attempts_dir: Path, registration: str | None, run_id: int, head_sha: str,
               attempt: int, mode: str, max_attempts: int) -> dict:
    """Plan job: this dispatch is the next attempt (section 8.3). Its run name is its inputs (RUN_NAME); a
    CONFIRMATORY listing has no run number missing up to this run (RUN_LIST_GAP); the counted attempts before
    it are 1..k at this commit; k is below `max_attempts` (ATTEMPTS_EXHAUSTED); this attempt is k + 1
    (ATTEMPT_NOT_NEXT); each counted attempt still lists its declaration (EARLIER_ATTEMPT_UNREADABLE: with one
    that cannot be read no later attempt can change the verdict). An attempt whose records are missing or
    expired is not refused here: the report lists it LOST, and it is one of the k. EXPLORATORY reads its own
    dispatch only, so its attempt is 1."""
    chosen = selected(runs, mode, registration, run_id)
    this = next(d for d in chosen if d['run_id'] == run_id)
    need((this['mode'], this['attempt'], this['registration_sha256']) == (mode, attempt, registration), 'RUN_NAME')
    need(mode != 'CONFIRMATORY' or not run_list_gap(runs, registration, run_id), 'RUN_LIST_GAP')
    done = counted_dispatches(attempts_dir, chosen, skip=run_id)
    k = coverage(done, head_sha)
    need(k < max_attempts, 'ATTEMPTS_EXHAUSTED')
    need(attempt == k + 1, 'ATTEMPT_NOT_NEXT')
    need(all('declaration' in d['artifacts'] and not d['artifacts']['declaration']['expired'] for d in done),
         'EARLIER_ATTEMPT_UNREADABLE')
    done_ids = {d['run_id'] for d in done}
    return {'counted_attempts': [d['run_id'] for d in done], 'next_attempt': k + 1,
            'never_started': [d['run_id'] for d in chosen if d['run_id'] != run_id and d['run_id'] not in done_ids]}


# --------------------------------------------------------------------------------------------- unpack ----
def _saved_zip(path: Path, digest: str | None) -> bytes:
    """The bytes of one saved zip: it is saved (INPUT_MISSING), within ZIP_LIMIT (ARTIFACT_ZIP), and its SHA-256
    is the listed digest (ARTIFACT_DIGEST)."""
    raw = _read(path, check.ZIP_LIMIT)
    need(raw is not None, 'INPUT_MISSING')
    need(len(raw) <= check.ZIP_LIMIT, 'ARTIFACT_ZIP')
    need(digest is None or hashlib.sha256(raw).hexdigest() == digest, 'ARTIFACT_DIGEST')
    return raw


def zip_names(path: Path, digest: str | None) -> set[str]:
    """The member names of one saved zip, checked as zip_members checks it; no member is read."""
    raw = _saved_zip(path, digest)
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            names = archive.namelist()
    except (zipfile.BadZipFile, zipfile.LargeZipFile, zlib.error, OSError, EOFError, NotImplementedError,
            RuntimeError, ValueError):
        raise check.Refusal('ARTIFACT_ZIP') from None
    need(len(names) == len(set(names)), 'ARTIFACT_ZIP')
    return set(names)


def zip_members(path: Path, wanted: dict[str, int], digest: str | None) -> dict[str, bytes]:
    """The wanted members of one saved zip (name: byte limit); other members are not read. The zip is saved
    (INPUT_MISSING), within ZIP_LIMIT and a zip with no member name twice (ARTIFACT_ZIP), and its SHA-256 is the
    listed digest (ARTIFACT_DIGEST). A wanted member that is absent or over its limit is not returned."""
    raw = _saved_zip(path, digest)
    out = {}
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            need(len(names) == len(set(names)), 'ARTIFACT_ZIP')
            for info in infos:
                limit = wanted.get(info.filename)
                if limit is None or info.file_size > limit:
                    continue
                with archive.open(info) as member:
                    data = member.read(limit + 1)
                if len(data) <= limit:
                    out[info.filename] = data
    except (zipfile.BadZipFile, zipfile.LargeZipFile, zlib.error, OSError, EOFError, NotImplementedError,
            RuntimeError, ValueError):
        raise check.Refusal('ARTIFACT_ZIP') from None
    return out


def observe_job(folder: Path, run_id: int) -> tuple[int | None, list[str]]:
    """(the observe job's server `started_at` in seconds, its runner labels) from the run's saved attempt-1 jobs
    listing; (None, []) when that job is not listed exactly once for this run's attempt 1, and a None start when
    it has no `started_at`."""
    doc = fetched(folder / 'jobs.json', 'INPUT_MISSING', 'JOBS_LISTING')
    items = doc.get('jobs')
    need(type(items) is list and type(doc.get('total_count')) is int and doc['total_count'] == len(items),
         'JOBS_LISTING')
    named = [job for job in items if type(job) is dict and job.get('name') == check.OBSERVE_JOB_NAME]
    if len(named) != 1 or named[0].get('run_id') != run_id or named[0].get('run_attempt') != 1:
        return None, []
    labels = named[0].get('labels') if type(named[0].get('labels')) is list else []
    labels = [label for label in labels if type(label) is str and 1 <= len(label) <= 128]
    return epoch(named[0].get('started_at')), sorted(labels)


def attempt_of(d: dict, folder: Path, head_sha: str, source_sha256: str | None = None) -> tuple[dict, dict | None]:
    """One counted attempt: (its entry of the report's `attempts`, its declaration's constants or None). The
    entry is the checker's attempt row (read, or LOST when its records are missing, expired or invalid), or
    UNREADABLE with the checker's cause. The declaration artifact is the plan job's: one created after the
    observe job started, or (with `source_sha256`, this run's plan output) one that names another tree, is
    DECLARATION_REFUSED when the checker names no earlier cause."""
    found = d['artifacts']

    def member(stem):
        item = found.get(stem)
        if item is None or item['expired']:
            return b''
        name = stem + '.json'
        return zip_members(folder / f'{stem}.zip', {name: check.SMALL_LIMIT}, item['digest']).get(name, b'')

    declaration_raw = member('declaration')
    anchors = {0: (member('marker'), found['marker']['created'])}
    for k in _checkpoints(found):
        anchors[k] = (member(f'checkpoint-{k}'), found[f'checkpoint-{k}']['created'])
    members = {}
    records = found.get('records')
    if records is not None and not records['expired']:
        # the eleven members and the monitor's two files (PR-2b), each within its limit: a `.jsonl` file
        # LINES_LIMIT (the monitor log included), a `.json` file SMALL_LIMIT; one over it is not handed on
        wanted = {name: check.LINES_LIMIT if name.endswith('.jsonl') else check.SMALL_LIMIT
                  for name in check.MEMBERS + check.MONITOR_FILES}
        members = zip_members(folder / 'records.zip', wanted, records['digest'])
    started, labels = observe_job(folder, d['run_id'])
    listed = {'run_id': d['run_id'], 'created_at': d['created_at'], 'head_sha': head_sha, 'mode': d['mode'],
              'attempt': d['attempt'], 'registration_sha256': d['registration_sha256'], 'runner_labels': labels}
    try:
        row = check.attempt_row(declaration_raw, members, listed, {'job_started_at': started, 'anchors': anchors})
    except check.Unreadable as unreadable:
        return unreadable_entry(d, unreadable.cause), None
    # the row exists, so the declaration is one canonical line of its schema and the observe job has a start
    declaration = json.loads(declaration_raw.decode('ascii'))
    if found['declaration']['created'] > started or (
            source_sha256 is not None and declaration['source_sha256'] != source_sha256):
        return unreadable_entry(d, 'DECLARATION_REFUSED'), None
    return row, declaration['constants']


def unreadable_entry(d: dict, cause: str) -> dict:
    return {'attempt': d['attempt'], 'run_id': d['run_id'], 'state': 'UNREADABLE', 'cause': cause}


def early_disagreements(d: dict, folder: Path) -> int | None:
    """Section 8.3: the critical reads with `agree` false in a never-started dispatch's uploaded records (`start`
    reads height 0 and H0 - 1 before the marker); None when it uploaded no records or no readable
    critical_heights.jsonl."""
    records = d['artifacts'].get('records')
    if records is None or records['expired']:
        return None
    name = 'critical_heights.jsonl'
    raw = zip_members(folder / 'records.zip', {name: check.LINES_LIMIT}, records['digest']).get(name)
    return None if raw is None else check.critical_disagreements(raw)


def report(mode: str, registration: str | None, attempts_dir: Path, run_id: int, head_sha: str,
           runs: list[dict], run_attempt: int | None = None,
           source_sha256: str | None = None) -> tuple[bytes, bytes | None, str | None]:
    """(the collection report, the observation list or None, the INCONCLUSIVE cause or None). The cause is None
    for a CONFIRMATORY verdict of PASS, FAIL or OPEN and for a read EXPLORATORY attempt; an EXPLORATORY attempt
    that is LOST gives EVIDENCE_MISSING. `run_attempt` is this run's attempt (the report job may be run again)
    and `source_sha256` the plan job's tree hash."""
    chosen = selected(runs, mode, registration, run_id, complete=False)
    need(mode == 'CONFIRMATORY' or next(d for d in chosen if d['run_id'] == run_id)['mode'] == 'EXPLORATORY',
         'RUN_NAME')
    if run_attempt is not None:     # the report job of this run attempt has not uploaded its artifact yet
        mine = artifacts_of(attempts_dir / str(run_id), run_id)
        need(all(n < run_attempt for n in report_numbers(mine)), 'REPORT_ARTIFACT_PRESENT')
    done, idle, refused = classified(attempts_dir, chosen)
    confirmatory = mode == 'CONFIRMATORY'
    constants = check.registered_constants(check.required_seconds()) if confirmatory else None
    limit = check.MAX_ATTEMPTS if confirmatory else EXPLORATORY_ATTEMPTS
    # the coverage of section 8.3: OTHER_RUN_IN_PROGRESS first, then a missing run number, then classified()'s
    # code, then coverage()'s
    if not all_completed(runs, run_id):
        refused = 'OTHER_RUN_IN_PROGRESS'
    elif confirmatory and run_list_gap(runs, registration, run_id):
        refused = 'RUN_LIST_GAP'
    if refused is None:
        try:
            need(coverage(done, head_sha) <= limit, 'ATTEMPTS_EXHAUSTED')
        except check.Refusal as refusal:
            refused = refusal.code
    never = [{'run_id': d['run_id'], 'attempt': d['attempt'], 'created_at': d['created_at'],
              'state': 'NEVER_STARTED', 'run_name_recognized': d['mode'] is not None,
              's14_disagreements': None if refused else early_disagreements(d, attempts_dir / str(d['run_id']))}
             for d in idle]
    if refused is not None:     # no record is read: every dispatch that started is listed with the one cause
        attempts = [unreadable_entry(d, 'COMPLETENESS_REFUSED') for d in done]
    else:
        attempts = []
        for d in done:
            entry, declared = attempt_of(d, attempts_dir / str(d['run_id']), head_sha,
                                         source_sha256 if d['run_id'] == run_id else None)
            attempts.append(entry)
            if not confirmatory:
                constants = declared
    unreadable = [entry['cause'] for entry in attempts if entry['state'] == 'UNREADABLE']
    observations = None
    if confirmatory:
        result = check.verdict(attempts, constants, never, refused or check.COVERAGE_OK)
        cause = result['reason'] if result['result'] == 'INCONCLUSIVE' else None
        if attempts and not unreadable and refused is None:
            observations = check.observation_list({row['attempt']: row['start_time_utc'] for row in attempts},
                                                  registration)
    else:
        result = None
        # an EXPLORATORY attempt that is LOST was not read: the line names the records, the row says LOST
        lost = any(entry['state'] == 'LOST' for entry in attempts)
        cause = (unreadable[0] if unreadable else 'EVIDENCE_MISSING' if lost
                 else None if attempts and refused is None else 'COMPLETENESS_REFUSED')
    raw = check.collection_report(mode, registration, head_sha, attempts, never, result, constants,
                                  refused or check.COVERAGE_OK)
    return raw, observations, cause


# ------------------------------------------------------------------------------------------- commands ----
def _digits(text: str) -> int:
    if re.fullmatch(r'[0-9]{1,18}', text) is None:
        raise argparse.ArgumentTypeError('an integer')
    return int(text)


def _optional_text(text: str):
    return None if text == '' else text


def parser():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest='command', required=True)
    q = sub.add_parser('pages')
    q.add_argument('--dir', required=True)
    q = sub.add_parser('downloads')
    q.add_argument('--dir', required=True)
    q.add_argument('--run-id', required=True, type=_digits)
    for name in ('s04-run', 's04-artifact', 's04-job'):
        q = sub.add_parser(name)
        q.add_argument('--dir', required=True)
        q.add_argument('--s04-run-id', required=True, type=_digits)
        if name == 's04-run':
            q.add_argument('--commit', required=True)
        else:
            q.add_argument('--run-attempt', required=True, type=_digits)
    for name in ('runs', 'continuity', 'report'):
        q = sub.add_parser(name)
        q.add_argument('--listing', required=True)
        q.add_argument('--mode', required=True)
        q.add_argument('--registration-sha256', type=_optional_text)
        q.add_argument('--run-id', required=True, type=_digits)
        if name == 'runs':
            continue
        q.add_argument('--attempts', required=True)
        q.add_argument('--head-sha', required=True)
        if name == 'continuity':
            q.add_argument('--attempt', required=True, type=_digits)
        else:
            q.add_argument('--run-attempt', required=True, type=_digits)
            q.add_argument('--source-sha256', required=True)
            q.add_argument('--output', required=True)
            q.add_argument('--observations', type=_optional_text)
    return p


def _inputs(args) -> None:
    """The arguments of runs, continuity and report: a mode, a run id, and a registration hash exactly when the
    mode is CONFIRMATORY (CONTINUITY_INPUTS); a 40-hex head (HEAD_SHA)."""
    registration = args.registration_sha256
    need(args.mode in check.MODES and args.run_id >= 1
         and (registration is not None and HEX64.fullmatch(registration) is not None
              if args.mode == 'CONFIRMATORY' else registration is None), 'CONTINUITY_INPUTS')
    if args.command != 'runs':
        need(HEX40.fullmatch(args.head_sha) is not None, 'HEAD_SHA')


def _pages_command(args) -> dict:
    return {'pages': pages(Path(args.dir))}


def _downloads_command(args) -> dict:
    need(args.run_id >= 1, 'CONTINUITY_INPUTS')
    found = artifacts_of(Path(args.dir), args.run_id)
    # a run without the marker holds one thing the report may read: the critical reads made before the marker
    names = stems(found) if counted(found) else ['records'] if 'records' in found else []
    names = [stem for stem in names if not found[stem]['expired']]
    return {'counted': counted(found), 'downloads': [f'{stem}:{found[stem]["id"]}' for stem in names]}


def _runs_command(args) -> dict:
    _inputs(args)
    # the runs to save; whether every other run has completed is `continuity`'s and `report`'s to judge
    chosen = selected(listing(Path(args.listing)), args.mode, args.registration_sha256, args.run_id, complete=False)
    return {'runs': [d['run_id'] for d in chosen]}


def _continuity_command(args) -> dict:
    _inputs(args)
    need(1 <= args.attempt <= 999, 'CONTINUITY_INPUTS')
    runs = listing(Path(args.listing))
    limit = check.MAX_ATTEMPTS if args.mode == 'CONFIRMATORY' else EXPLORATORY_ATTEMPTS
    return continuity(runs, Path(args.attempts), args.registration_sha256, args.run_id, args.head_sha,
                      args.attempt, args.mode, limit)


def _report_command(args) -> tuple[dict, str | None]:
    _inputs(args)
    need(1 <= args.run_attempt <= 999 and HEX64.fullmatch(args.source_sha256) is not None, 'CONTINUITY_INPUTS')
    for path in (args.output, args.observations):
        if path is not None:
            _free(path)
    raw, observations, cause = report(args.mode, args.registration_sha256, Path(args.attempts), args.run_id,
                                      args.head_sha, listing(Path(args.listing)), args.run_attempt,
                                      args.source_sha256)
    write_new(args.output, raw)
    written = None
    if observations is not None and args.observations is not None:
        write_new(args.observations, observations)
        written = hashlib.sha256(observations).hexdigest()
    parsed = json.loads(raw)
    return {'verdict': (parsed['verdict'] or {}).get('result'), 'attempts': len(parsed['attempts']),
            'coverage': parsed['coverage'], 'sha256': hashlib.sha256(raw).hexdigest(),
            'observations_sha256': written}, cause


def _s04_inputs(args) -> None:
    """The arguments of the three S04 commands: a positive run id, a run attempt 1..999, a 40-hex commit
    (S04_RUN_ID, S04_RUN_ATTEMPT, HEAD_SHA)."""
    need(args.s04_run_id >= 1, 'S04_RUN_ID')
    if args.command == 's04-run':
        need(HEX40.fullmatch(args.commit) is not None, 'HEAD_SHA')
    else:
        need(1 <= args.run_attempt <= 999, 'S04_RUN_ATTEMPT')


def _s04_run_command(args) -> dict:
    _s04_inputs(args)
    return {'run_attempt': check.s04_run(Path(args.dir), args.s04_run_id, args.commit)['run_attempt']}


def _s04_artifact_command(args) -> dict:
    _s04_inputs(args)
    return {'id': check.s04_artifact_id(Path(args.dir), args.s04_run_id, args.run_attempt)}


def _s04_job_command(args) -> dict:
    _s04_inputs(args)
    return {'id': check.s04_job_id(Path(args.dir), args.s04_run_id, args.run_attempt)}


COMMANDS = {'pages': _pages_command, 'runs': _runs_command, 'downloads': _downloads_command,
            'continuity': _continuity_command, 'report': _report_command, 's04-run': _s04_run_command,
            's04-artifact': _s04_artifact_command, 's04-job': _s04_job_command}


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)

    def emit(command, result, exit_code, code=None, **keys) -> int:
        sys.stdout.write(check.output_line(TOOL, command, result, exit_code, code, **keys).decode('ascii'))
        return exit_code

    if not __debug__:   # before anything else, argparse included
        return emit(argv[0] if argv and argv[0] in COMMANDS else None, 'REFUSED', check.EXIT_REFUSAL,
                    'OPTIMIZED_PYTHON')
    args = parser().parse_args(argv)
    cause = None
    try:
        keys = COMMANDS[args.command](args)
        if args.command == 'report':
            keys, cause = keys
    except check.Refusal as refusal:
        return emit(args.command, 'REFUSED', refusal.exit_code, refusal.code)
    except Exception:   # noqa: BLE001 - one closed line; no text of the failure is printed
        return emit(args.command, 'INTERNAL', check.EXIT_INTERNAL, 'INTERNAL_ERROR')
    if cause is not None:   # the report is written; the line names the cause and the report's coverage
        return emit(args.command, 'INCONCLUSIVE', check.EXIT_VALIDATION, cause, coverage=keys['coverage'])
    return emit(args.command, 'DONE', check.EXIT_OK, **keys)


if __name__ == '__main__':
    import claude_track_exit
    claude_track_exit.run(main)
