# XD-1 event chain, version 3: live-decision sessions, the collection report and the verdict (XD-1 confirmatory harness)

**2026-11-10 · Class T · CONFIRMATORY harness, before the follow-up registration · protocol impact NONE · Claude plan, SELF_REVIEW; revised the same day after A's non-author review (S1, C1, C2, C3, T1)**

```text
Status: NO PRODUCTION NETWORK ACTIVE · DO NOT ACTIVATE · Class P NO-GO · DO NOT GENESIS
release_authorization NONE. No approval, signing, broadcast or GO authority.
```

V3 is what the XD-1 tools write for a run whose human broadcast decision
the Founder performs live at the VPS console: the 20 CONFIRMATORY runs of
045b section 5.1 and the EXPLORATORY live-decision pilot before them. It is
a successor of `XD1_EVENT_CHAIN_V2.md` ("A producer that cannot write this
shape needs a V3", V2 `:211-212`); V1 and V2 are not edited, and a scripted
EXPLORATORY collection stays V2. Nothing here is a 045b criterion; the
criterion is 045b's and the follow-up registration freezes these bytes
with the tools (section 8).

Sources (line numbers at main `78e6e06c`): A's decisions XA1–XA13 for the
confirmatory harness (A main session 4, 2026-11-10; listed with their
citations in the unit note
`docs/claude-track/plans/notes/CT-P3-044C1_PLAN_EN/2026-11-10_xd1-confirmatory.md`);
045b (`docs/claude-track/plans/CT-P3-045b_PREREGISTRATION_DRAFT_EN.md`)
`:564-569` (nearest rank, whole seconds rounded up), `:577-580`
(re-dispatch of a unit that never started), `:596-619` (metric, runs,
criterion, missing data), `:1090` (expected, observed, INCONCLUSIVE),
`:1098` (environment row), `:1099` (sessions, `B_operator`), `:1100`
(inclusion and replay apart); `tools/ct_preregistration_receipt.py`
`:130-159`, `:275-305` (the observation list).

Tools: `tools/claude_track_xd1_driver.py` (`--decision live`),
`tools/claude_track_xd1_check.py` (V3 sessions, `verdict`,
`observation_list`), `tools/claude_track_xd1_collect.py` (`plan-v3`,
`declare-v3`, `marker`, `t42-v3`, `budget-v3`, `collect-v3`),
`tools/claude_track_xd1_confirm.py` (hosted only: the listing, the next
session, the collection report), `tools/claude_track_xd1_decide.py` (the
Founder's console), `.github/workflows/claude-track-xd1-confirmatory.yml`.
Tests: `tests/claude_track/test_xd1_check_v3.py`,
`test_xd1_live_decision.py`, `test_xd1_collect_v3.py`,
`test_xd1_confirm_tool.py`, `test_xd1_decide_tool.py`,
`test_xd1_confirmatory_workflow.py`.

## 1. What V3 keeps

Everything V2 states holds for V3 unless this document says otherwise: the
read rule and file bounds (V1 §1), the T4-2 record (V1 §4), the event
names, the 28 base events, `MAX_TIMESTAMP_EVENTS` = 35, every structural
check and order edge (V1 §5), V2's three checks, the values and the
deciding value under the metric `045B` (`t_045b_ns` decides; V1 §6, V2
§6), and the exit codes (V1 §8).

A collection is one version: a V3 declaration makes every declared record
V3. A V1 or V2 record in a V3 session is `RECORD_INVALID`, unless its bytes
already refuse the report under section 9.

## 2. Declaration `BITAGI_CT_XD1_DECLARATION_V3` (one session)

One dispatch is one session (XA1): 1 to 5 consecutive runs,
`first_run` … `last_run`. The slice job runs exactly that session.

| Key | Value |
|---|---|
| `format` | `BITAGI_CT_XD1_DECLARATION_V3` |
| `mode` | `CONFIRMATORY` or `EXPLORATORY` |
| `n` | CONFIRMATORY: exactly 20 (`MAX_XD1_RUNS`; 045b `:603-609`). EXPLORATORY: 1 ≤ n ≤ 5, the pilot's own runs |
| `first_run`, `last_run` | 1 ≤ first ≤ last ≤ n, last − first + 1 ≤ `SESSION_RUNS` = 5; EXPLORATORY: first = 1 and last = n |
| `head_sha` | 40 lowercase hex: the dispatched commit (CONFIRMATORY: the registration's pinned commit, XA3) |
| `run_id`, `run_attempt` | the dispatch's ids; `run_attempt` is 1 (a re-run is refused) |
| `registration_sha256` | CONFIRMATORY: 64 lowercase hex, the registration the session is evaluated under. EXPLORATORY: `null` |

The key set is closed. A schema failure refuses the report with
`DECLARATION_INVALID`, a wrong `n` with `DECLARATION_N`, a session outside
these bounds with `DECLARATION_SESSION` (exit 2; no run is read).

The checker reads exactly `run-<i>.json` for i = first … last and the
session's T4-2 record `t42-slice-<first_run>.json`, whose `slice` is
`first_run` (V3 names a session's slice by its first run).

## 3. Session-start marker `BITAGI_CT_XD1_SESSION_MARKER_V3`

The slice job writes it (`collect.py marker`) and uploads it as the
artifact `xd1c-session-started` after the T4-2 step and before the step
that starts the first run's driver. Its keys are `format` and the
declaration's `mode`, `first_run`, `last_run`, `head_sha`, `run_id`,
`run_attempt` and `registration_sha256`, with the declaration's values.

- A dispatch whose run lists no marker artifact is **NEVER_STARTED**: no
  run of its range started, so the range may be dispatched again (045b
  `:577-580`, XA1). It is listed in the collection report and not counted.
- Once the marker exists every run of the range counts. A run with no
  record (cut short, killed at the cap, never reached because the
  supervisor ended the slice) is `RECORD_MISSING`, T = ∞ (045b `:618-619`,
  `:1099`). Where a session ends cannot change which runs count.
- An expired marker artifact refuses (`ARTIFACT_EXPIRED`): it cannot be
  told apart from one never written.

## 4. Run record `BITAGI_CT_XD1_RUN_V3` and the live decision

V2's keys (V2 §3) with these changes and three new keys:

| Key | Value |
|---|---|
| `format` | `BITAGI_CT_XD1_RUN_V3` |
| `labels`, `transferability` | the mode's set and statement (section 9) |
| `mode` | `CONFIRMATORY` or `EXPLORATORY`, the declaration's |
| `registration_sha256` | the declaration's (a record with another value refuses the session: `REGISTRATION_MISMATCH`) |
| `decision` | `BROADCAST`, `REFUSED` or `NONE` |
| `stop_reason` | optional: V2's four, or `DECISION_REFUSED` |

**The decision** (driver `--decision live`; the only decision of
`--mode CONFIRMATORY`; XA2):

1. The second H0 − 1 host process gets a decision FIFO in its environment,
   `BITAGI_E3D3_XD1_DECISION` (the first process never does). The worker
   gate that reads it is M4's (section 10).
2. When the driver stamps that process's `STEP_9_END` line it stamps `D0`
   and starts the decision on its own thread, so the watcher keeps stamping
   lines: a host that did not wait shows attempts before `D1`
   (`D1_LE_EVERY_B`) or no `D1` at all (`BASE_EVENT_MISSING`).
3. It makes the console FIFO `decision.fifo` in the console directory
   (`--console-dir`; the workflow's is `$HOME/xd1-console` of the runner
   account), opens its read end, and then writes the prompt `prompt.json`
   there, whole (written under another name and renamed):
   `{"format": "BITAGI_CT_XD1_DECISION_PROMPT_V1", "run_index", "run_id",
   "txid", "raw_tx_sha256", "display_digest": "<txid[:8]>..<txid[-8:]>",
   "fifo": "decision.fifo", "cap_seconds_left"}`. A leftover prompt or FIFO
   of a killed run is removed first.
4. It waits, until the run's cap (`run_start_ns` + `XD1_RUN_CAP`, 900 s),
   for one line of at most 128 bytes:
   `XD1_DECISION_V1 <run_index> <txid> BROADCAST|REFUSE`. The Founder's
   console (`claude_track_xd1_decide.py`) writes it. The decision time
   counts inside T (045b `:596-602`).
   - **The console** is the root-owned copy the Founder installs once from
     merged main in `/usr/local/lib/bitagi-xd1/` (with
     `claude_track_exit.py`; sha256 compared with A's values), started at
     the VPS console as `runuser -P -u runner01 -- python3 -I
     /usr/local/lib/bitagi-xd1/claude_track_xd1_decide.py`: the runner
     account, on its own pseudo-terminal (`-P`), never a file the runner
     account can write, and the kernel's `dev.tty.legacy_tiocsti` is 0
     (VPS prep 2.4). It refuses to run as root (exit 5) and refuses a
     standard input that is not a terminal (exit 5; `--answer` is for tests
     and needs `--once`). After showing each prompt it discards the input
     already typed (`tcflush`), so a line typed or pasted before the prompt,
     or a second line after a wrong one, never answers a run. It writes the
     line only to a FIFO (opened without following a link, `S_ISFIFO`).
   - **What the directory proves.** The console directory is the runner
     account's: any process of that account could write a line there. The
     line binds the run and the candidate; that the Founder decided rests on
     the registered tree (XA3), the guard and this procedure, not on the
     directory (see the unit note on CR-21 condition 4).
5. A line naming this run and this candidate stamps `D1`.
   - `BROADCAST`: `decision` = `BROADCAST`; the driver writes
     `XD1_ACK_V1 <seq>` to the worker's FIFO and closes it, where `seq` is
     the `STEP_9_END` line's own sequence number in that process's event
     file (17 in today's L0 process; the `xd1::AckLines` grammar,
     `crates/bitagi-launch-host/src/xd1.rs:68-75`).
   - `REFUSE`: `decision` = `REFUSED`, stop reason `DECISION_REFUSED`; the
     worker's FIFO is closed with no line.
6. Anything else gives `decision` = `NONE` and no `D1`, and closes the
   worker's FIFO with no line: a closed console input, a malformed or
   overlong line, another run's line or another candidate's (stop reason
   `DECISION_REFUSED`), or the cap (stop reason `RUN_CAP`). The driver stops
   waiting when the host process ends; a decision cannot reach it after
   that.
7. The prompt and the console FIFO are removed when the decision ends.

A run with any decision but `BROADCAST` has no step 10 lines: T = ∞
(`BASE_EVENT_MISSING`, `STOP_REASON`, `DECISION_NOT_BROADCAST`). The
Founder's absence or delay past the cap is T = ∞, and no run replaces it
(045b `:1099`).

## 5. Checks and the session report

V3 adds one check, after V2's three and before the order edges:
`DECISION_NOT_BROADCAST`, the record's `decision` is not `BROADCAST`.

The checker's report for a V3 declaration is `BITAGI_CT_XD1_REPORT_V3`: V2's
report keys with this `format`, `mode`, the mode's labels and statement, a
`limits` object with `session_runs` = 5, one `slices` entry
`{"slice": first_run, "first_run", "last_run", "t42"}`, and one row per run
of the session. Each row has V2's keys and four more:

- `run_id`: the session's dispatch;
- `decision`: the record's (null when the record is missing, invalid or
  bound to another run);
- `b_operator_ns`: D1 − D0 when D0 and D1 are each stamped once, D0 first,
  whatever the chain (045b `:1099`, every run's `B_operator` sample);
  otherwise null;
- `t_045b_s`: `t_045b_ns` in whole seconds, rounded up (045b `:567-568`),
  for a run that passes; null for T = ∞.

A session report has no percentile and no verdict; those are the
collection's.

## 6. Collection report `BITAGI_CT_XD1_COLLECTION_REPORT_V3` and the verdict

The hosted report job of every dispatch writes it over every counted
session of the registration (CONFIRMATORY) or over its own session
(EXPLORATORY), with `claude_track_xd1_confirm.py report`. Canonical JSON as
V1 §7.

| Key | Value |
|---|---|
| `format`, `mode`, `registration_sha256`, `head_sha`, `labels`, `transferability`, `metric` | as named; `metric` is `045B` |
| `sessions` | per counted session, in creation order: `run_id`, `run_attempt`, `first_run`, `last_run`, `created_at`, `started_at` (its slice job's GitHub server start, XA4), `start_time_utc` (the same in integer seconds), `t42`, `runner_labels`, `state` `COUNTED` |
| `never_started` | per listed dispatch with no marker: `run_id`, `first_run`, `last_run`, `created_at`, `state` `NEVER_STARTED`, `run_name_recognized` |
| `rows` | every counted session's rows (section 5), in run order |
| `verdict` | CONFIRMATORY: below. EXPLORATORY: `null` (no percentile for EXPLORATORY runs, V1 §6) |
| `b_operator_ns` | per run: `run_index`, `b_operator_ns` |
| `inclusion` | per run, apart from the verdict (045b `:1100`): `run_index`, `outcome_a`, `outcome_b`, `included` |
| `replay` | per run: `run_index`, `replay` = `NOT_MEASURED_BY_XD1` (the XD-1 run replays nothing; 045b `:1100` keeps it apart) |
| `environment` | 045b `:1098`: `node_versions` [31.1, 30.3], `host` `SELF_HOSTED_VPS`, `cr21` `FD-CT-92 item 15 (2026-10-27)`, `three_r_l_merged_first` `#545 198424fe`, `t42` (each counted session's), `t42_pass_sha` (`head_sha` when every counted session's T4-2 is `PASS`, else null), `runner_labels` |

**Verdict** (XA8; 045b `:564-569`, `:610-617`, `:1090`):
`{"expected", "observed", "result", "inconclusive_reason"}`.

- Each run's T is `t_045b_s`; a run with T = ∞ (any `infinite_reason`)
  counts as ∞, which sorts after every finite value.
- With exactly 20 counted runs, sorted ascending: p95 is the 19th value and
  p50 the 10th (nearest rank `ceil(q × N / 100)`, no interpolation).
  `result` is `PASS` when p95 ≤ 420 s and `FAIL` when p95 > 420 s; two or
  more ∞ make p95 ∞, a FAIL. One ∞ takes rank 20.
- `expected`: `{"criterion": "P95_T_045B_LE_420_S", "threshold_s": 420,
  "statistic": "P95", "estimator": "NEAREST_RANK", "n": 20, "p95_rank": 19,
  "p50_rank": 10, "rounding": "CEIL_WHOLE_SECONDS", "infinity":
  "SORTS_LAST"}`.
- `observed`: `counted_runs`, `t_s` (each run's seconds in run order, null
  for ∞), `infinite_runs`, `p95_s`, `p95_infinite`, `p50_s`,
  `p50_infinite` (the four null unless the result is PASS or FAIL).
- `INCONCLUSIVE` is a collection value only, never a run's, so a timeout or
  absence is never folded into it: a run's timeout is T = ∞. Its
  `inconclusive_reason` is one of `DECLARATION_REFUSED` (a counted
  session's marker or declaration is not that session's), `REGISTRATION_MISMATCH`,
  `COMPLETENESS_REFUSED` (section 7), `LABELS_REFUSED` (section 9), or
  `FEWER_THAN_20_RUNS` (the state after each session before the last).
  For any cause but the last the report has no rows, keeps the `sessions`
  entries read before the cause, has no observation list, and the tool
  exits 2.
- **Which refusals still write a report** (exactly, as
  `claude_track_xd1_confirm.py report` does): an INCONCLUSIVE report is
  written for `SESSION_GAP`, `SESSION_OVERLAP` and `SESSION_OTHER_COMMIT`
  (as `COMPLETENESS_REFUSED`), an EXPLORATORY pilot whose session never
  started (`COMPLETENESS_REFUSED`), a counted session's slice job missing
  from its jobs listing or without a `started_at` (`COMPLETENESS_REFUSED`),
  a marker or declaration that is not its session's
  (`DECLARATION_REFUSED`), refused labels (`LABELS_REFUSED`) and a record
  of another registration (`REGISTRATION_MISMATCH`). Every other section 7
  refusal writes **no** report and exits 2 or 3, before any session is read
  or while one is unpacked: `OTHER_RUN_IN_PROGRESS`, `THIS_RUN_NOT_LISTED`,
  `RUN_NAME`, `RUN_LIST_TITLE`, `ARTIFACT_EXPIRED`, `ARTIFACT_LISTING`,
  `ARTIFACT_ZIP`, `ARTIFACT_DIGEST`, `JOBS_LISTING`, the listing's own
  shape refusals (`RUN_LIST_SHAPE`, `RUN_LIST_CHANGED`, `RUN_LIST_CAPPED`,
  `RUN_LIST_JSON`, `RUN_LIST_MISSING`) and a missing saved answer. Both are
  fail-closed: no verdict is written without every counted session read.

## 7. Completeness: the dispatch listing (XA1)

Every dispatch of the workflow has the run name
`xd1 <MODE> runs <first_run>-<last_run> registration <sha256|none>`. The
plan and report jobs save this workflow's listing of `workflow_dispatch`
runs (all pages; at most 1,000 runs) and, per run read, its artifact
listing and its attempt-1 jobs listing, with GET requests and the job's
`actions: read` token.

- The CONFIRMATORY dispatches of a registration are its runs named
  `CONFIRMATORY` with that hash. A run whose name has another shape is read
  too and must list no marker (`RUN_LIST_TITLE`). Runs of another
  registration and EXPLORATORY runs are not read, whatever hash an
  EXPLORATORY run's name carries (a pilot through a tag names the TEST_ONLY
  pilot file's hash). Every run of the workflow but the current one must be
  completed (`OTHER_RUN_IN_PROGRESS`).
- **The pilot reads the same listing** (A's C2, so that the pilot meets the
  real API answers before any registered session): an EXPLORATORY dispatch's
  plan and report jobs save the same pages and run `runs` and `continuity`
  over its own dispatch only (its one session must start at run 1), and the
  report reads its own artifact and jobs listings through the same code. Its
  report is labelled EXPLORATORY and never counts.
- The counted sessions, in creation order, must cover exactly 1 … k: each
  run once, in run order, all at the current commit (`SESSION_GAP`,
  `SESSION_OVERLAP`, `SESSION_OTHER_COMMIT`). This is the analogue of the
  ARDR judge's J3 `RUN_LIST_INCOMPLETE`.
- **Plan** (`continuity`, before the slice job): this dispatch's run name
  must be its inputs, and its `first_run` must be k + 1
  (`SESSION_NOT_NEXT`; `ALL_RUNS_COUNTED` after run 20).
- **Report**: each counted session's marker, declaration (bound to its
  run, range, registration and the current commit) and records, read
  through checker V3; each zip's SHA-256 must be its listed digest; only
  the declared member names are read. k = 20 gives PASS or FAIL; k < 20
  gives `FEWER_THAN_20_RUNS`.

## 8. The registration and the observation list

**Registration keys this harness reads** (the follow-up registration adds
them; the plan job reads the file as merged on main,
`refs/remotes/origin/main:<path>`, the bytes the receipts cover):

```json
{"xd1": {"pinned_commit": "<40 hex>", "tool_sha256": {"<path>": "<64 hex>", "...": "..."}}}
```

- The bytes' SHA-256 must be the dispatch input `registration_sha256`
  (`REGISTRATION_SHA256_MISMATCH`).
- `pinned_commit` must be the dispatched commit (`NOT_THE_PINNED_COMMIT`),
  on main's first-parent chain (a commit main pointed at, not a merged
  branch's own commit; `NOT_ON_MAIN`); the dispatch ref must be a pinned
  attempt tag `ct-xd1-c-a<N>` (XA3), which the VPS guard admits only at the
  commit the Founder pinned with `bitagi-runner-pin`.
- `tool_sha256` must name exactly these paths, each with the SHA-256 of
  that file at the dispatched commit (`REGISTRATION_TOOLS`,
  `TOOL_SHA256_MISMATCH`): `tools/claude_track_xd1_check.py`,
  `tools/claude_track_xd1_driver.py`, `tools/claude_track_xd1_collect.py`,
  `tools/claude_track_xd1_supervisor.py`, `tools/claude_track_xd1_confirm.py`,
  `tools/claude_track_xd1_decide.py`,
  `tools/claude_track_regtest_offline_export.py`, `tools/claude_track_exit.py`,
  `.github/workflows/claude-track-xd1-confirmatory.yml`, this document, and
  `crates/bitagi-launch-host/tests/two_node_launch_accept.rs` (the worker
  with M4's gate).
- Other keys of the registration are not read here.

**The TEST_ONLY pilot registration** (A's C2):
`tests/fixtures/xd1/XD1_PILOT_REGISTRATION_TEST_ONLY.json`, with the label
`XD1_PILOT_REGISTRATION_TEST_ONLY_NEVER_A_REGISTRATION` and the same `xd1`
keys. A writes it with `collect.py pilot-registration --pinned-commit
<commit>` (each registered file's hash at that commit, which must be on
main's first-parent chain) and merges it to
main before a pilot dispatched from a `ct-xd1-c-aN` tag at that commit; the
pilot's plan job then runs the whole check above against it (the file must
carry the label). It is never a registration: a CONFIRMATORY dispatch
refuses a registration path that is not canonical (a leading `./`, `..`
or an empty part; `REGISTRATION_PATH`), any path under `tests/` and any
file carrying the label anywhere in its bytes (`REGISTRATION_TEST_ONLY`), the pilot's declaration and records name
no registration, and a CONFIRMATORY report never reads an EXPLORATORY run.
A pilot from main runs no registration check.

**Observation list** (XA9): `BITAGI_CT_OBSERVATION_LIST_V1`, the shape
`tools/ct_preregistration_receipt.py` reads: one entry per counted run, in
run order, `{"observation_id": "OBS-9<run_index:07>", "registration_sha256",
"start_time_utc"}`, the start being its session's slice job `started_at`
(XA4; every per-run time stays the driver's monotonic clock). The prefix 9
keeps the ids apart from ARDR's `OBS-<1..8><run:07>`. The report job writes
it whenever a CONFIRMATORY collection has a counted session and no
INCONCLUSIVE cause but `FEWER_THAN_20_RUNS`, so after each session it lists
every observation made so far.

## 9. Labels (XA5)

| Mode | Labels | Bytes that refuse the whole report |
|---|---|---|
| CONFIRMATORY | `CLASS_T`, `REGTEST`, `TEST_ONLY_PRIVATE_SCALAR_KNOWN`, `CONFIRMATORY`, `DECISION_LIVE_FOUNDER_VPS_CONSOLE`, `S17_PREP_EVIDENCE_CLASS_T` | `EXPLORATORY`, `DECISION_SCRIPTED_TEST_ONLY` |
| EXPLORATORY (the live-decision pilot) | `CLASS_T`, `REGTEST`, `TEST_ONLY_PRIVATE_SCALAR_KNOWN`, `CLASS_T_DEVELOPMENT_EVIDENCE_NOT_S17_PREP`, `EXPLORATORY`, `DECISION_LIVE_FOUNDER_VPS_CONSOLE` | `CONFIRMATORY` |

Transferability statement, both modes: `Small Regtest blocks, a VPS and a
Regtest live decision do not transfer to the mainnet hosts.`

As V1 §3: a declared record that is a readable bounded file and holds the
refusing bytes anywhere, or whose labels (read leniently) are not exactly
the mode's set with the statement, refuses the session report (exit 2); at
collection level that is `LABELS_REFUSED`. So an EXPLORATORY record cannot
be counted as CONFIRMATORY, nor a CONFIRMATORY one as EXPLORATORY, and a
scripted V2 record refuses either.

## 10. What the worker gate (M4) provides

M4 is its own PR (`crates/bitagi-launch-host/tests/two_node_launch_accept.rs`,
a test target; no `crates/*/src` change; FD-CT-62, XA2). The Python tools
rely on exactly this:

- When `BITAGI_E3D3_XD1_DECISION` is set, in the `None =>` arm of
  `Wait::BroadcastAuthorityRequired`, before `launch.broadcast_file(...)`,
  the worker reads that FIFO with `bitagi_launch_host::xd1::AckLines` and
  waits for the ack of `seq`, the sequence number of the `STEP_9_END` line
  it wrote in this process, looping on `TimedOut` (no limit of its own; the
  supervisor's 900 + 60 s bounds the run).
- `Acked`: the authorization file is written, as today. `OtherSequence` or
  `Closed`: no file; the phase ends at the wait and the process ends
  without step 10 lines.
- It writes no new event line, so `EVENT_LINES` and `L0_STEPS` stay as they
  are. Without the variable the worker behaves as today.

The driver opens the write end only when it delivers (a line or none), so
the worker's reader opens the FIFO on its first read, as its ack `Fifo`
does.

## 11. Exit codes

V1 §8 for the checker, with `REGISTRATION_MISMATCH` among the refusals
(exit 2). The driver adds no code: a live-decision run that does not
broadcast writes its record with a stop reason (exit 2). The collect V3
commands, the confirm tool and the console helper document theirs in their
headers (0 done, 2 refused, 3 a missing prerequisite, 4 internal error, 5
under `-O`).

## 12. Not in V3

- The worker gate itself (M4, section 10).
- The follow-up registration's bytes, tool hashes and pinned commit, and
  the criteria restated with frozen citations (the unit note lists them).
- A per-run UTC time (XA4: the session's server start is the observation
  start).
- Any change to the EXPLORATORY workflow `.github/workflows/claude-track-xd1.yml`,
  to V1, V2 or the scripted run.

A producer that cannot write this shape needs a V4. V3 is not edited in
place after A accepts it.
