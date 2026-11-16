"""XD-1 confirmatory sessions across dispatches: the listing, the next session and the collection report (V3).

Class T Regtest. Runs only in the hosted jobs of `.github/workflows/claude-track-xd1-confirmatory.yml` (the plan
and report jobs, which hold an `actions: read` token), never on the VPS. Sources: A's decisions XA1, XA3, XA4,
XA8 and XA9 (2026-11-10); docs/claude-track/formats/XD1_EVENT_CHAIN_V3.md sections 3, 6 and 7; 045b
(docs/claude-track/plans/CT-P3-045b_PREREGISTRATION_DRAFT_EN.md) :564-619, :1090, :1098-1100. The pattern of the
listing check is the ARDR judge's J3 RUN_LIST_INCOMPLETE; nothing of ARDR or tools/common.py is imported (XA11).

  pages --dir LISTING
  runs --listing DIR --mode M --registration-sha256 HEX --run-id ID
  downloads --dir RUN_DIR --run-id ID
  continuity --listing DIR --sessions DIR --mode M --registration-sha256 HEX --run-id ID --head-sha SHA
             --first-run F --last-run L
  report --mode M --registration-sha256 HEX --listing DIR --sessions DIR --run-id ID --head-sha SHA
         --output FILE [--observations FILE]

The workflow saves each Actions API answer (GET only) before the tool reads it: the listing of this workflow's
workflow_dispatch runs (`runs-<p>.json`), and per run `artifacts.json`, `jobs.json` (attempt 1) and the zips the
`downloads` command names (`<stem>.zip`).

* A dispatch's run name is `xd1 <MODE> runs <first>-<last> registration <sha256|none>`. The CONFIRMATORY
  dispatches of one registration are this workflow's dispatches with that mode and hash; every other run of the
  workflow must be completed, and one whose name is not that shape is read too and must never have started.
* A session is counted when its run lists the session-start marker artifact (written by its slice job before
  its first run, XA1); one that does not is NEVER_STARTED: listed, not counted, its range free again. An
  expired marker refuses (it cannot be told from one never written).
* `continuity` (plan job, before the session's slice job): the counted sessions, in creation order, cover
  exactly 1..k with no gap or overlap, all at this commit, and this dispatch's first run is k + 1.
* `report` (report job): every counted session's marker, declaration and records (checker V3,
  `claude_track_xd1_check.session_rows`), its slice job's server `started_at` (XA4), the completeness rule
  above, and then the verdict (XA8: PASS or FAIL over exactly runs 1..20; INCONCLUSIVE, the cause kept, for a
  refused declaration, a registration mismatch, a refused completeness, refused labels, or fewer than 20 counted
  runs) and the observation list (XA9). An EXPLORATORY pilot reads the same listing and reports its own dispatch
  only (A's C2: the pilot exercises these reads), with no verdict and no observation list; it never counts.

Exit codes: 0 done (a report with PASS, FAIL or FEWER_THAN_20_RUNS); 2 refused (a run list, a session that is
not the next, a collection report written INCONCLUSIVE for any other cause); 3 a missing or malformed API answer
or input; 4 internal error; 5 under -O. Stdlib only.
"""
from __future__ import annotations

import argparse
import calendar
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
import time
import zipfile

import claude_track_xd1_check as check

WORKFLOW_PATH = '.github/workflows/claude-track-xd1-confirmatory.yml'
SLICE_JOB_NAME = 'XD-1 session slice (VPS)'   # the workflow's slice job name; the jobs listing is matched on it
TITLE = re.compile(r'xd1 (CONFIRMATORY|EXPLORATORY) runs ([1-9][0-9]?)-([1-9][0-9]?) registration ([0-9a-f]{64}|none)')
ARTIFACTS = {'marker': 'xd1c-session-started', 'declaration': 'xd1c-declaration', 'records': 'xd1c-session-records'}
RUN_LIST_PAGE, RUN_LIST_CAP = 100, 1000
FETCHED_LIMIT = 4 << 20
ZIP_LIMIT = 4 << 20
MEMBER_LIMIT = check.RECORD_LIMIT
UTC = re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z')
HEX64 = re.compile(r'[0-9a-f]{64}')
EXIT_REFUSAL, EXIT_PREREQUISITE = 2, 3


class Refusal(Exception):
    def __init__(self, label, code=EXIT_REFUSAL):
        super().__init__(label)
        self.code = code


def need(condition, label, code=EXIT_PREREQUISITE):
    if not condition:
        raise Refusal(label, code)


def _pairs(pairs):
    keys = [k for k, _ in pairs]
    if len(keys) != len(set(keys)):
        raise ValueError('duplicate key')
    return dict(pairs)


def fetched(path: Path, what: str) -> dict:
    """A saved API answer: a regular file of at most FETCHED_LIMIT bytes, one JSON object, no duplicate key."""
    need(path.is_file() and not path.is_symlink() and path.stat().st_size <= FETCHED_LIMIT, f'{what}_MISSING')
    try:
        value = json.loads(path.read_bytes().decode('utf-8'), object_pairs_hook=_pairs)
    except (UnicodeDecodeError, ValueError, RecursionError):
        raise Refusal(f'{what}_JSON') from None
    need(type(value) is dict, f'{what}_JSON')
    return value


def epoch(utc) -> int:
    need(type(utc) is str and UTC.fullmatch(utc) is not None, 'STARTED_AT')
    return calendar.timegm(time.strptime(utc, '%Y-%m-%dT%H:%M:%SZ'))


# ------------------------------------------------------------------------------------------------ listing ----
def pages(folder: Path) -> int:
    total = fetched(folder / 'runs-1.json', 'RUN_LIST').get('total_count')
    need(type(total) is int and total >= 0, 'RUN_LIST_SHAPE')
    need(total < RUN_LIST_CAP, 'RUN_LIST_CAPPED')
    return max(1, -(-total // RUN_LIST_PAGE))


def listing(folder: Path) -> list[dict]:
    """Every saved page: one total, every page but the last full, no run twice, each run's fields typed."""
    count = pages(folder)
    total = fetched(folder / 'runs-1.json', 'RUN_LIST')['total_count']
    runs = []
    for page in range(1, count + 1):
        doc = fetched(folder / f'runs-{page}.json', 'RUN_LIST')
        items = doc.get('workflow_runs')
        need(doc.get('total_count') == total and type(items) is list
             and len(items) == (RUN_LIST_PAGE if page < count else total - RUN_LIST_PAGE * (count - 1)),
             'RUN_LIST_CHANGED')
        runs += items
    need(all(type(x) is dict and type(x.get('id')) is int and x['id'] > 0
             and all(type(x.get(k)) is str for k in ('display_title', 'status', 'event', 'path', 'head_sha',
                                                     'created_at'))
             and UTC.fullmatch(x['created_at']) is not None for x in runs), 'RUN_LIST_SHAPE')
    need(len({x['id'] for x in runs}) == len(runs), 'RUN_LIST_CHANGED')
    need(all(x['path'] == WORKFLOW_PATH and x['event'] == 'workflow_dispatch' for x in runs), 'RUN_LIST_SHAPE')
    return runs


def dispatch(run: dict) -> dict:
    """A listed run as a dispatch: its id, its run name's mode, range and registration (None when the name is not
    a run name of this workflow), its creation time and head."""
    title = TITLE.fullmatch(run['display_title'])
    out = {'run_id': run['id'], 'created_at': run['created_at'], 'head_sha': run['head_sha'],
           'status': run['status'], 'mode': None, 'first_run': None, 'last_run': None, 'registration_sha256': None}
    if title is not None and int(title.group(2)) <= int(title.group(3)):
        out.update(mode=title.group(1), first_run=int(title.group(2)), last_run=int(title.group(3)),
                   registration_sha256=None if title.group(4) == 'none' else title.group(4))
    return out


def selected(runs: list[dict], mode: str, registration: str | None, run_id: int) -> list[dict]:
    """The dispatches the tool reads, in creation order: CONFIRMATORY, those of this registration and every run
    whose name is not a run name (each must never have started); EXPLORATORY, this run only. Every other run of
    the workflow must have completed (OTHER_RUN_IN_PROGRESS)."""
    out = []
    for run in sorted(runs, key=lambda x: (x['created_at'], x['id'])):
        d = dispatch(run)
        need(d['run_id'] == run_id or d['status'] == 'completed', 'OTHER_RUN_IN_PROGRESS', EXIT_REFUSAL)
        if mode == 'EXPLORATORY':
            if d['run_id'] == run_id:
                out.append(d)
        elif d['mode'] is None or (d['mode'] == 'CONFIRMATORY' and d['registration_sha256'] == registration):
            out.append(d)
    need(any(d['run_id'] == run_id for d in out), 'THIS_RUN_NOT_LISTED')
    return out


def artifacts_of(folder: Path, run_id: int) -> dict:
    """{stem: (artifact id, digest or None)} of this harness's artifacts in one run's saved listing (one page of
    fewer than 100); an expired one refuses."""
    doc = fetched(folder / 'artifacts.json', 'ARTIFACT_LISTING')
    items = doc.get('artifacts')
    need(type(items) is list and doc.get('total_count') == len(items) and len(items) < 100, 'ARTIFACT_LISTING')
    names = {v: k for k, v in ARTIFACTS.items()}
    found = {}
    for item in items:
        need(type(item) is dict and type(item.get('name')) is str and type(item.get('id')) is int and item['id'] > 0
             and type(item.get('expired')) is bool and type(item.get('workflow_run')) is dict
             and item['workflow_run'].get('id') == run_id, 'ARTIFACT_LISTING')
        digest = item.get('digest')
        need(digest is None or (type(digest) is str and digest.startswith('sha256:')
                                and HEX64.fullmatch(digest[7:]) is not None), 'ARTIFACT_LISTING')
        stem = names.get(item['name'])
        if stem is None:
            continue
        need(stem not in found, 'ARTIFACT_LISTING')
        need(not item['expired'], 'ARTIFACT_EXPIRED', EXIT_REFUSAL)
        found[stem] = (item['id'], digest[7:] if digest else None)
    return found


def counted(found: dict) -> bool:
    return 'marker' in found


def coverage(sessions: list[dict], head_sha: str) -> int:
    """XA1: the counted sessions, in creation order, cover exactly 1..k (each run once, in run order) at one
    commit; returns k. SESSION_OTHER_COMMIT, SESSION_GAP, SESSION_OVERLAP refuse (exit 2)."""
    nxt = 1
    for s in sessions:
        need(s['head_sha'] == head_sha, 'SESSION_OTHER_COMMIT', EXIT_REFUSAL)
        need(s['first_run'] <= nxt, 'SESSION_GAP', EXIT_REFUSAL)
        need(s['first_run'] == nxt, 'SESSION_OVERLAP', EXIT_REFUSAL)
        nxt = s['last_run'] + 1
    need(nxt - 1 <= check.MAX_XD1_RUNS, 'SESSION_OVERLAP', EXIT_REFUSAL)
    return nxt - 1


def counted_dispatches(sessions_dir: Path, chosen: list[dict], skip: int | None = None) -> list[dict]:
    """The chosen dispatches whose run lists the marker, in creation order; a run whose name is not a run name of
    this workflow must not list one (RUN_LIST_TITLE)."""
    out = []
    for d in chosen:
        if d['run_id'] == skip:
            continue
        found = artifacts_of(sessions_dir / str(d['run_id']), d['run_id'])
        if counted(found):
            need(d['mode'] is not None, 'RUN_LIST_TITLE', EXIT_REFUSAL)
            out.append({**d, 'artifacts': found})
    return out


def continuity(runs: list[dict], sessions_dir: Path, registration: str | None, run_id: int, head_sha: str,
               first: int, last: int, mode: str = 'CONFIRMATORY') -> dict:
    """Plan job: this dispatch's session is the next one (XA1, 045b :1099). EXPLORATORY (the pilot, A's C2): the
    same reads over the pilot's own dispatch, whose only session must start at run 1."""
    chosen = selected(runs, mode, registration, run_id)
    this = next(d for d in chosen if d['run_id'] == run_id)
    need((this['mode'], this['first_run'], this['last_run']) == (mode, first, last), 'RUN_NAME', EXIT_REFUSAL)
    done = counted_dispatches(sessions_dir, chosen, skip=run_id)
    k = coverage(done, head_sha)
    need(k < check.MAX_XD1_RUNS, 'ALL_RUNS_COUNTED', EXIT_REFUSAL)
    need(first == k + 1, 'SESSION_NOT_NEXT', EXIT_REFUSAL)
    return {'counted_sessions': [d['run_id'] for d in done], 'counted_runs': k, 'next_first_run': k + 1,
            'never_started': [d['run_id'] for d in chosen if d['run_id'] != run_id
                              and d['run_id'] not in {x['run_id'] for x in done}]}


# ------------------------------------------------------------------------------------------------- unpack ----
def zip_members(path: Path, wanted: dict[str, int], digest: str | None) -> dict[str, bytes]:
    """The wanted members of one downloaded zip (name: byte limit), each at most once; other members are not
    read (the checker never lists a directory either). The zip's SHA-256 must be the listed digest."""
    need(path.is_file() and not path.is_symlink() and path.stat().st_size <= ZIP_LIMIT, 'ARTIFACT_ZIP')
    raw = path.read_bytes()
    need(digest is None or hashlib.sha256(raw).hexdigest() == digest, 'ARTIFACT_DIGEST', EXIT_REFUSAL)
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            names = [i.filename for i in infos]
            need(len(names) == len(set(names)), 'ARTIFACT_ZIP')
            out = {}
            for info in infos:
                if info.filename in wanted:
                    need(info.file_size <= wanted[info.filename], 'ARTIFACT_ZIP')
                    with archive.open(info) as member:
                        data = member.read(wanted[info.filename] + 1)
                    need(len(data) <= wanted[info.filename], 'ARTIFACT_ZIP')
                    out[info.filename] = data
    except (zipfile.BadZipFile, OSError, EOFError):
        raise Refusal('ARTIFACT_ZIP') from None
    return out


def write_new(path: Path, raw: bytes) -> None:
    """A new file, never over another (OUTPUT_EXISTS, exit 3)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(path, 'xb') as out:
            out.write(raw)
    except FileExistsError:
        raise Refusal('OUTPUT_EXISTS', EXIT_PREREQUISITE) from None


class Inconclusive(Exception):
    """The collection is INCONCLUSIVE with this cause (XA8); the report is still written."""

    def __init__(self, reason, detail):
        super().__init__(reason)
        self.reason, self.detail = reason, detail


def session_of(d: dict, folder: Path, work: Path, registration: str | None,
               head_sha: str) -> tuple[dict, list[dict], int]:
    """One counted session: (its sessions entry, its rows, its start in UTC seconds). Inconclusive for a marker or
    declaration that is not this session's (DECLARATION_REFUSED), refused labels (LABELS_REFUSED), a record of
    another registration (REGISTRATION_MISMATCH), or no slice job start (COMPLETENESS_REFUSED)."""
    found = d['artifacts']
    got = {}
    for stem, member in (('marker', 'marker.json'), ('declaration', 'declaration.json')):
        if stem in found:
            got.update(zip_members(folder / f'{stem}.zip', {member: MEMBER_LIMIT}, found[stem][1]))
    try:
        marker = check.parse(got['marker.json'])
        raw = got['declaration.json']
    except (KeyError, check.Invalid):
        raise Inconclusive('DECLARATION_REFUSED', f'run {d["run_id"]}: marker or declaration') from None
    write_new(work / 'declaration.json', raw)
    try:
        declaration = check.read_declaration(work / 'declaration.json')
    except check.Refusal:
        raise Inconclusive('DECLARATION_REFUSED', f'run {d["run_id"]}: declaration') from None
    bound = {'run_id': d['run_id'], 'run_attempt': 1, 'head_sha': head_sha, 'mode': d['mode'],
             'first_run': d['first_run'], 'last_run': d['last_run'], 'registration_sha256': registration}
    if check.version_of(declaration) != 3 or any(declaration[k] != v for k, v in bound.items()):
        raise Inconclusive('DECLARATION_REFUSED', f'run {d["run_id"]}: declaration binding')
    if marker != {'format': check.FORMAT_MARKER_V3, **bound}:
        raise Inconclusive('DECLARATION_REFUSED', f'run {d["run_id"]}: marker binding')
    records = work / 'records'
    records.mkdir()
    if 'records' in found:   # a session whose records never uploaded has every run RECORD_MISSING
        first = d['first_run']
        wanted = {f'records/run-{i}.json': MEMBER_LIMIT for i in range(first, d['last_run'] + 1)}
        wanted[f'records/t42-slice-{first}.json'] = MEMBER_LIMIT
        for name, data in zip_members(folder / 'records.zip', wanted, found['records'][1]).items():
            write_new(work / name, data)
    try:
        entry, rows = check.session_rows(declaration, records)
    except check.Refusal as refusal:
        reason = 'REGISTRATION_MISMATCH' if str(refusal).startswith('REGISTRATION_MISMATCH') else 'LABELS_REFUSED'
        raise Inconclusive(reason, f'run {d["run_id"]}: {refusal}') from None
    jobs = fetched(folder / 'jobs.json', 'JOBS')
    items = jobs.get('jobs')
    need(type(items) is list and jobs.get('total_count') == len(items), 'JOBS_LISTING')
    named = [j for j in items if type(j) is dict and j.get('name') == SLICE_JOB_NAME]
    if len(named) != 1 or named[0].get('run_id') != d['run_id'] or named[0].get('run_attempt') != 1:
        raise Inconclusive('COMPLETENESS_REFUSED', f'run {d["run_id"]}: slice job not listed')
    utc = named[0].get('started_at')
    try:
        start = epoch(utc)
    except Refusal:
        raise Inconclusive('COMPLETENESS_REFUSED', f'run {d["run_id"]}: slice job started_at') from None
    labels = named[0].get('labels')
    labels = sorted(x for x in labels if type(x) is str) if type(labels) is list else []
    entry = {'run_id': d['run_id'], 'run_attempt': 1, 'first_run': d['first_run'], 'last_run': d['last_run'],
             'created_at': d['created_at'], 'started_at': utc, 'start_time_utc': start, 't42': entry['t42'],
             'runner_labels': labels, 'state': 'COUNTED'}
    return entry, rows, start


def report(mode: str, registration: str | None, sessions_dir: Path, run_id: int, head_sha: str,
           runs: list[dict] | None) -> tuple[bytes, bytes | None, int]:
    """(collection report, observation list or None, exit code). Both modes read the dispatch listing (an
    EXPLORATORY pilot's own dispatch only, A's C2) and the artifact listings."""
    need(runs is not None, 'RUN_LIST_REQUIRED')
    if mode == 'EXPLORATORY':
        need(registration is None, 'EXPLORATORY_REGISTRATION', EXIT_REFUSAL)
    else:
        need(registration is not None and HEX64.fullmatch(registration) is not None, 'REGISTRATION_SHA256')
    chosen = selected(runs, mode, registration, run_id)
    need(mode == 'CONFIRMATORY' or next(d for d in chosen if d['run_id'] == run_id)['mode'] == 'EXPLORATORY',
         'RUN_NAME', EXIT_REFUSAL)
    done = counted_dispatches(sessions_dir, chosen)
    done_ids = {d['run_id'] for d in done}
    never = [{'run_id': d['run_id'], 'first_run': d['first_run'], 'last_run': d['last_run'],
              'created_at': d['created_at'], 'state': 'NEVER_STARTED', 'run_name_recognized': d['mode'] is not None}
             for d in chosen if d['run_id'] not in done_ids]
    sessions, rows, starts, observations = [], [], {}, None
    unpacked = tempfile.TemporaryDirectory(prefix='xd1-confirm-')   # the zips' members, read once, then gone
    try:
        try:
            coverage(done, head_sha)
        except Refusal as refusal:
            raise Inconclusive('COMPLETENESS_REFUSED', str(refusal)) from None
        if mode == 'EXPLORATORY' and not done:
            raise Inconclusive('COMPLETENESS_REFUSED', 'the pilot session never started')
        for d in done:
            entry, session_rows_, start = session_of(d, sessions_dir / str(d['run_id']),
                                                     Path(unpacked.name) / str(d['run_id']), registration, head_sha)
            sessions.append(entry)
            rows += session_rows_
            starts.update({r['run_index']: start for r in session_rows_})
        values = [r['t_045b_s'] if r['infinite_reason'] is None else None for r in rows]
        result = check.verdict(values) if mode == 'CONFIRMATORY' else None
        code = 0
        if mode == 'CONFIRMATORY' and starts:
            observations = check.observation_list(starts, registration)
    except Inconclusive as why:
        result = check.inconclusive(why.reason) if mode == 'CONFIRMATORY' else None
        sys.stderr.write(json.dumps({'inconclusive': why.reason, 'detail': why.detail}) + '\n')
        code, rows = EXIT_REFUSAL, []
    finally:
        unpacked.cleanup()
    raw = check.collection_report(mode, registration, head_sha, sessions, never, rows, result)
    return raw, observations, code


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest='command', required=True)
    pg = sub.add_parser('pages')
    pg.add_argument('--dir', type=Path, required=True)
    rn = sub.add_parser('runs')
    dl = sub.add_parser('downloads')
    dl.add_argument('--dir', type=Path, required=True)
    dl.add_argument('--run-id', type=int, required=True)
    ct = sub.add_parser('continuity')
    rp = sub.add_parser('report')
    for each in (rn, ct, rp):
        each.add_argument('--mode', choices=check.MODES_V3, required=True)
        each.add_argument('--registration-sha256', default='')
        each.add_argument('--run-id', type=int, required=True)
    for each in (rn, ct):
        each.add_argument('--listing', type=Path, required=True)
    rp.add_argument('--listing', type=Path, required=True)
    for each in (ct, rp):
        each.add_argument('--sessions', type=Path, required=True)
        each.add_argument('--head-sha', required=True)
    ct.add_argument('--first-run', type=int, required=True)
    ct.add_argument('--last-run', type=int, required=True)
    rp.add_argument('--output', type=Path, required=True)
    rp.add_argument('--observations', type=Path)
    return p


def main(argv=None) -> int:
    if not __debug__:
        print(json.dumps({'result': 'REFUSED', 'failure': 'OPTIMIZED_PYTHON'}), file=sys.stderr)
        return 5
    a = parser().parse_args(sys.argv[1:] if argv is None else argv)
    code = 0
    try:
        if a.command == 'pages':
            value = {'pages': pages(a.dir)}
        elif a.command == 'downloads':
            found = artifacts_of(a.dir, a.run_id)
            value = {'run_id': a.run_id, 'counted': counted(found),
                     'downloads': [f'{stem}:{found[stem][0]}' for stem in ARTIFACTS if stem in found]}
        else:
            registration = a.registration_sha256 or None
            need(check.HEX40.fullmatch(getattr(a, 'head_sha', None) or '0' * 40) is not None, 'HEAD_SHA')
            if a.command == 'runs':
                chosen = selected(listing(a.listing), a.mode, registration, a.run_id)
                value = {'runs': [d['run_id'] for d in chosen]}
            elif a.command == 'continuity':
                need((registration is not None and HEX64.fullmatch(registration) is not None)
                     == (a.mode == 'CONFIRMATORY'), 'CONTINUITY_INPUTS')
                value = continuity(listing(a.listing), a.sessions, registration, a.run_id, a.head_sha,
                                   a.first_run, a.last_run, a.mode)
            else:
                need(a.listing is not None, 'RUN_LIST_REQUIRED')
                raw, observations, code = report(a.mode, registration, a.sessions, a.run_id, a.head_sha,
                                                 listing(a.listing))
                write_new(a.output, raw)
                if observations is not None:
                    need(a.observations is not None, 'OBSERVATIONS_PATH')
                    write_new(a.observations, observations)
                parsed = json.loads(raw)
                value = {'verdict': (parsed['verdict'] or {}).get('result'), 'rows': len(parsed['rows']),
                         'sha256': hashlib.sha256(raw).hexdigest(),
                         'observations_sha256': hashlib.sha256(observations).hexdigest() if observations else None}
    except Refusal as refusal:
        print(json.dumps({'result': 'REFUSED', 'failure': str(refusal)}), file=sys.stderr)
        return refusal.code
    except Exception as exc:  # noqa: BLE001 - one bounded internal-error line, no free text
        print(json.dumps({'result': 'FAIL', 'failure': 'INTERNAL:' + type(exc).__name__}), file=sys.stderr)
        return 4
    print(json.dumps({'result': 'DONE' if code == 0 else 'INCONCLUSIVE', 'command': a.command, **value},
                     sort_keys=True))
    return code


if __name__ == '__main__':
    import claude_track_exit
    claude_track_exit.run(main)
