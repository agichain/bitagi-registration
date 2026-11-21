# P5-002 endurance records, version 1: the private Signet continuity proof, S14 agreement and the collection report (XA13, PR-1, PR-2a, PR-2b)

**2026-11-15, PR-2a and PR-2b 2026-11-16 · Class T · harness before follow-up registration 2 · protocol impact NONE · Claude plan, SELF_REVIEW**

```text
Status: NO PRODUCTION NETWORK ACTIVE · DO NOT ACTIVATE · Class P NO-GO · DO NOT GENESIS
Generation: D3.5 (Exact D3 Core unchanged)
release_authorization NONE. No approval, signing, broadcast or GO authority.
```

V1 is the interface of the P5-002 commands: what the VPS driver writes during one attempt, what the checker computes from it,
and what the hosted report states. The tools, the workflow and the tests are built against this document, not against each
other. Nothing here is a criterion by itself: the criteria are GOV072's and TDS 6.8's, and follow-up registration 2 freezes
these bytes with the tools (section 10). In PR-1 only EXPLORATORY runs; a CONFIRMATORY dispatch is refused at plan. PR-2 edits
this document before that registration; once it is pinned, a change needs a V2 and a new registration. PR-2a (2026-11-16) adds
plan check 9, the S04 citation, and the tag-path TEST_ONLY pilot (section 10). PR-2b (2026-11-16) wires the replay and the
monitor (sections 3, 4.7, 4.8, 8.1): both components are `WIRED`, `NOT_WIRED` is empty, a CONFIRMATORY plan runs the
registration checks, the hosted build job makes the two binaries, and `REGISTERED_PATHS` names fourteen paths.

Sources (line numbers at main `6d3efad6`): A's decisions Q1–Q16 for XA13 (2026-11-15; #258 6893861692; unit note
`docs/claude-track/plans/notes/CT-P5_PHASE_PLAN_KO/2026-11-15_p5002-harness-1.md`); GOV072
(`specs/BITAGI_SEM1_TDS_D3_5_GOV_072_VALIDATION_BUDGET_ADDENDUM_2026-09-18_EN.md` `:16-17`, `:94-98`); TDS 6.8
(`specs/BITAGI_SEM1_TDS_D3_5_FINAL_EN.md` `:866-880`); T-5002 (`docs/tasks/P5-002_PRIVATE_SIGNET_ENDURANCE.md` `:12-15`, `:19`);
045b (`docs/claude-track/plans/CT-P3-045b_PREREGISTRATION_DRAFT_EN.md` `:1033`, `:1851-1856`, `:1870`); BUNDLE
(`docs/claude-track/plans/FD-CT-17_BUNDLE_DRAFT_KO.md` `:331-339`). Pattern: `XD1_EVENT_CHAIN_V3.md` and its tools. PR-2a: the
S04 citation's run and source part as `tools/claude_track_ardr_slices.py` (`s04_run`, `s04_artifact_id`, `s04_job_id`,
`s04_record_from_log`, `s04_record_bytes`, `s04_derive`) and `.github/workflows/claude-track-ardr.yml` read it; the pilot as XD-1's
C2 (`tools/claude_track_xd1_collect.py`, `PILOT_REGISTRATION`, `pilot-registration`). PR-2b: B's fixture
(`crates/bitagi-cli/examples/test_only_signet_store_fixture.rs`, CT-P5-001 fixture-1), `bitagi monitor tick`
(`crates/bitagi-cli/src/monitor_tick.rs`, CT-P5-004-2c-1), the monitor loop `tools/claude_track_monitor.py` and its log
format `docs/claude-track/formats/MONITOR_LOG_V1.md` (CT-P5-004-2c-2); the public fixture credential's recipe as
`tools/claude_track_regtest_store_commands.py` computes it.

Tools: `tools/claude_track_p5002_check.py` (the checker: the only module the other two import, besides
`tools/claude_track_exit.py`), `tools/claude_track_p5002_driver.py` (VPS), `tools/claude_track_p5002_confirm.py` (hosted only),
`.github/workflows/claude-track-p5002.yml`; tests `tests/claude_track/test_p5002_*.py`. Stdlib only. Nothing of ARDR, XD-1,
`tools/common.py` or the Codex policy module is imported. `required_seconds()` reads `docs/policy/ACTIVE_VALIDATION_POLICY.json`
itself, and no Codex ledger file (CR-01: a Claude-track entry's admission does not depend on the Codex ledger,
`docs/claude-track/plans/7A_S06_S07_PLAN_EN.md` section 2); only hosted jobs call it. The tree archive the VPS job unpacks holds
only the driver, the checker, `tools/claude_track_exit.py`, `tools/claude_track_monitor.py` and this document. The checker
imports `tools/claude_track_monitor.py` only inside `monitor_check()` (its `check_log` is the rule a monitor log is read by).

## 1. Scope, labels and the two fixed lines

Scope (b) (A9; 045b `:1851-1856`): one attempt runs two Bitcoin Core nodes on one private Signet, `SIGNET_NODE_A` (key `a`,
Core 31.1) and `SIGNET_NODE_B` (key `b`, Core 30.3), with the replay (B's TEST_ONLY Signet store fixture, labelled
`configuration-unverified synthetic-context replay`, section 4.7) and the watcher (the monitor loop over `bitagi monitor tick`,
section 4.8). It covers S13 (at least 86,400 s of
continuous actual operation) and S14 at genesis, H0 − 1 and H0, plus any reorganization fork point and public report cutoff.
The two nodes are this run's, on one VPS (one failure domain, a stated limit); they are not the Founder's mainnet Node A/B. No
key of any kind exists in the run: the challenge is `51` (OP_TRUE) and no wallet is loaded.

The two fixed lines (ASCII, exact bytes; in `environment.json`, the registration block and the report):

- `SCOPE_B` = `P5-002 scope (b): two private Signet nodes, the replay and the watcher only; no launch host, no REGISTER or BEAT, no Signet H0-1 Rust/Python comparison.`
- `S14_NOT_COVERED` = `S14 heights not covered: every block containing a project REGISTER candidate; accepted REGISTER height; every block containing a project BEAT candidate; accepted BEAT height. Not counted from Regtest CI; open in P5-004 until a later Signet launch run under its own registration.`

| Mode | Labels (sorted) | Bytes that refuse a record of that mode |
|---|---|---|
| CONFIRMATORY | `CLASS_T`, `CONFIRMATORY`, `PRIVATE_SIGNET`, `SCOPE_B`, `TEST_ONLY` | `EXPLORATORY` |
| EXPLORATORY | `CLASS_T`, `CLASS_T_DEVELOPMENT_EVIDENCE_NOT_S13`, `EXPLORATORY`, `PRIVATE_SIGNET`, `SCOPE_B`, `TEST_ONLY`, and `EXPLORATORY_SCALED` when any override was passed (section 2) | `CONFIRMATORY` |

`TRANSFERABILITY`, both modes: `Two nodes on one VPS, an OP_TRUE Signet challenge and scripted blocks do not transfer to the mainnet hosts.`
A record file of an attempt that holds the refusing bytes anywhere, or whose `labels` are not exactly its mode's list, makes
the attempt unreadable (`LABELS_REFUSED`, section 8.1). Nothing a record of one mode can hold (a key, a fixed line, a closed
value) contains the other mode's name.

## 2. Constants

| Name | Value | Source |
|---|---|---|
| `required_seconds` | 86,400: `required_seconds()` returns `signet.continuous_seconds` of `docs/policy/ACTIVE_VALIDATION_POLICY.json` (`POLICY_PATH`), read as a regular file that is not a link, at most `SMALL_LIMIT` bytes, of SHA-256 `POLICY_SHA256` (`e3068586…7a07`, the pin GOV072's own reader holds), UTF-8 JSON with no duplicate key, whose `signet` object is exactly `POLICY_SIGNET` (the continuous seconds and four flags, each true); any failure is `POLICY_UNAVAILABLE`. No Codex ledger module or file (`BACKLOG.json`, `REQUIREMENTS.json`) is read (CR-01). The literal is written once, in `POLICY_SIGNET`, and in no other P5-002 tool. The hosted plan job writes it into the declaration and the VPS reads it there | GOV072 `:16-17`; A Q4; CR-01 |
| `sample_seconds`, `gap_seconds` | 60; 180 = 3 × `sample_seconds` | A Q4 |
| `clock_step_record_seconds`, `clock_step_gap_seconds` | 2; 60 (never scaled) | A Q4 |
| `block_seconds`, `live_window_seconds` | 600; 1,800 = 3 × `block_seconds` | A Q3, Q4 |
| `stop_margin_seconds` | 600 = 10 × `sample_seconds` | A Q4 |
| `checkpoint_seconds`, `checkpoints` | 3,600; 26 = ceil((`required_seconds` + `stop_margin_seconds`) / `checkpoint_seconds`) + 1, never above `MAX_CHECKPOINTS` = 26 | A Q4 |
| `anchor_slack_seconds` | 300 (never scaled) | this document |
| `h0` | 200. Heights 1..199 are mined before sample 0 in chunks of `PREMINE_CHUNK` = 25, producers alternating from `a` (1–25 `a`, 26–50 `b`, …, 176–199 `b`) | A Q3 |
| `signet_challenge_hex` | `51`; blocks by `generatetodescriptor 1 "raw(51)" <tries>` | A Q2 |
| `max_attempts` | 3 | A Q5 |
| `NODE_VERSIONS`, `BITCOIND_SHA256` | `a`: 310100, `986e63b3c8770f08d0059820ad3dd085d1ab9e1bea23946c243f858a06888a08`; `b`: 300300, `30d4fa871a5447be1f57f195c3fd021c6fa44f920693aa4650e61769326edca8` (`getnetworkinfo`'s `version`; the archives and hashes of `claude-track-xd1-confirmatory.yml` `:293-294`) | A Q16 |
| `ATTEMPT_TAG` | `refs/tags/ct-p5002-a[1-9][0-9]{0,2}` (the Founder creates it; its number need not be the attempt's). A CONFIRMATORY dispatch runs from such a tag, and so may the EXPLORATORY TEST_ONLY pilot (section 10) | A names |
| `PORTS` | `a`: P2P 38433, RPC 38432; `b`: P2P 38443, RPC 38442 (loopback only) | this document |
| `RPC_SECONDS`, `MAX_OBSERVATION_SECONDS` | 20; 96,000 | this document |
| Step budgets (minutes) | observe job 1,760; `start` 70; each `checkpoint` 75; `finish` 25. The job's limit is 60 minutes above the caps on the longest path (downloads, Python and Core 35, the binaries' download among them; `start` 70; the 26 slots 1,560; `finish` 25; the records upload 10: 1,700), which covers the marker and checkpoint uploads and the last checkpoint's wait, so the records are uploaded before it: no step is expected to run after a job-level timeout. Inside `start` the driver waits at most READY 120 + PREMINE 3,000 + REPLAY 330 + MONITOR_START 60 + DAEMON_START 120 = 3,630 s; inside `finish` about F1 340 + F1m 90 + F1r 330 + F2 160 + F3 90 s. The hosted build job's 30 minutes are outside the observe job | A decision 2; PR-2 decision 14 |
| Component constants | the monitor polls every `MONITOR_POLL_SECONDS` = 120 s with `MONITOR_TICK_TIMEOUT_SECONDS` = 60 s; its checked TICK lines lie at most `MONITOR_SPAN_SECONDS` = 300 s apart over the longest interval (2 polls and a timeout). The replay follows once every `sample_seconds`; a fixture run is given `REPLAY_SECONDS` = 330 s (the driver's; its own replay session is bounded at 300 s). Harness constants bound by the tool hashes, not registration constants (PR-2 decision 10) | PR-2 decisions 6, 7, 10 |
| Read limits | `SMALL_LIMIT` 64 KiB (each `.json`), `LINES_LIMIT` 16 MiB (each `.jsonl`), `ZIP_LIMIT` 256 MiB (the records zip), `FETCHED_LIMIT` 4 MiB (a saved API answer) | this document |
| `MAX_SAMPLES` | 16,000: the most samples a plan may take by its deadline, so that `samples.jsonl` (about 940 bytes a line) stays within `LINES_LIMIT`. The registered constants take at most 1,561 | this document |

The **effective constants** are the fourteen keys `required_seconds`, `sample_seconds`, `gap_seconds`, `clock_step_record_seconds`,
`clock_step_gap_seconds`, `block_seconds`, `live_window_seconds`, `stop_margin_seconds`, `checkpoint_seconds`, `checkpoints`,
`anchor_slack_seconds`, `h0`, `signet_challenge_hex`, `max_attempts`: integers, except the challenge. The declaration's
`constants` holds exactly them, and sections 5–8 read only that object.

**EXPLORATORY scaling rule.** An EXPLORATORY dispatch may pass any of `duration_seconds` (60..96,000; it replaces
`required_seconds`), `sample_seconds` (2..60), `block_seconds` (10..600, at least `sample_seconds`) and `checkpoint_seconds`
(30..3,700, at least `sample_seconds`). `gap_seconds`, `live_window_seconds`, `stop_margin_seconds` and `checkpoints` follow by
the formulas above; `checkpoints` must stay ≤ 26, `checkpoints` × `checkpoint_seconds` ≤ `MAX_OBSERVATION_SECONDS`, and
`checkpoints` × `checkpoint_seconds` ≤ `MAX_SAMPLES` × `sample_seconds` (`OVERRIDE_RANGE`: with the default checkpoints a
`sample_seconds` below 6 is refused). With any override present, even one equal to the registered value, the declaration's `scaling` is
`EXPLORATORY_SCALED` and that label is added; otherwise `scaling` is `REGISTERED_CONSTANTS`. A CONFIRMATORY plan refuses any
override (`OVERRIDE_REFUSED`).

## 3. Commands

Every command refuses optimized Python first (`OPTIMIZED_PYTHON`), uses no `assert` as a control, ends through
`claude_track_exit.run(main)`, and prints exactly one line on stdout: canonical JSON (section 4) with the keys `command`, `exit`,
`result` (`DONE`, `REFUSED`, `INCONCLUSIVE` or `INTERNAL`), `tool` (`p5002_check`, `p5002_driver`, `p5002_confirm`), `code` (a
code of section 10; absent on `DONE`) and, on `DONE`, the keys in the table; the `report` command's `INCONCLUSIVE` line also
carries `coverage`. Values are closed codes, integers, booleans and hex
digests: never input text, a label, a file name or a path. An argument error is argparse's (exit 2, usage on stderr). An
optional argument given as the empty string is absent. Exit codes: 0 done, 2 validation, 3 unavailable, 4 internal, 5 security,
6 refusal.

| Tool and command line | What it does | `DONE` keys |
|---|---|---|
| check `plan --mode M --attempt N --expected-head SHA --source-sha256 HEX --bin-sha256 HEX --bitagi-sha256 HEX --fixture-sha256 HEX --declaration NEW_FILE [--registration PATH --registration-sha256 HEX --s04-run-id ID] [--s04-dir DIR] [--duration-seconds D] [--sample-seconds S] [--block-seconds B] [--checkpoint-seconds C]` | Hosted plan job, after the tree is archived and, for a dispatch from an attempt tag, the cited S04 run is read into `--s04-dir` (read only by such a dispatch): the plan checks (section 10) on the `GITHUB_*` environment, then `declaration.json`. The three binary hashes are the hosted build job's outputs (its tar, `bitagi`, the fixture) | `attempt`, `mode`, `scaling`, `checkpoints`, `declaration_sha256` |
| check `attempt --records DIR --output NEW_FILE` | One records directory read locally (its own `declaration.json` is the declaration; no listing, no server anchors): writes the attempt row of section 8.1 with `anchors.result` `NOT_CHECKED` | `s13`, `s14`, `longest_interval_seconds`, `disagreements`, `row_sha256` |
| check `pilot-registration --commit SHA --output NEW_FILE` | For A, by hand: the TEST_ONLY pilot file of section 10 for a commit on main's first-parent chain, one canonical line. A commits it on main as `PILOT_REGISTRATION` after that commit, tags the commit and dispatches the EXPLORATORY pilot from the tag | `registration_sha256` |
| driver `start --declaration FILE --source-sha256 HEX --node-a BIN_DIR --node-b BIN_DIR --bin-dir DIR --records NEW_DIR --work NEW_DIR` | Steps S1–S8 below | `samples` (1), `head_sha256`, `premine_blocks`, `marker_sha256` |
| driver `checkpoint --records DIR --work DIR --index K [--github-output FILE]` | Waits until slot K is due (`t0` + K × `checkpoint_seconds`) or the daemon has ended, whichever is first; for K = `checkpoints` it then waits for the daemon to end, at most 3 × `sample_seconds`. Writes `checkpoint-K.json` once (a second call: `OUTPUT_EXISTS`). `checkpoints` < K ≤ 26 writes nothing. `--github-output` gets `scheduled=true` or `scheduled=false` | `index`, `scheduled`, `daemon_state`, `seq`, `head_sha256` (the last three null when not scheduled) |
| driver `finish --records DIR --work DIR` | Steps F1–F5 below; the workflow runs it with `if: always()` | `stop_reason`, `samples`, `head_sha256`, `leftover_processes`, `final_sha256` |
| driver `daemon --records DIR --work DIR` | Internal (only `start` spawns it): the sampler and the block producer (sections 4.3, 4.4) until the stopping rule (section 5) | `stop_reason`, `samples` |
| confirm `pages --dir LISTING`; `runs --listing DIR --mode M --registration-sha256 HEX --run-id ID`; `downloads --dir RUN_DIR --run-id ID` | As `claude_track_xd1_confirm.py`: the listing's page count; the run ids to read (section 8.3; `runs` names them whether or not another run is still in progress: `continuity` and `report` judge that); from a run's saved `artifacts.json`, whether it lists the marker and which zips to save (every unexpired one of a run with the marker; of a run without it only `records`) | `pages`; `runs`; `counted`, `downloads` (`<stem>:<artifact id>`) |
| confirm `continuity --listing DIR --attempts DIR --mode M --registration-sha256 HEX --run-id ID --head-sha SHA --attempt N` | Plan job: this dispatch is the next attempt (section 8.3). It reads each earlier run's saved `artifacts.json` and, for a run without the marker, its `jobs.json` and its saved `records.zip` when it lists an unexpired one | `counted_attempts`, `never_started` (lists of run ids), `next_attempt` (integer) |
| confirm `s04-run --dir DIR --s04-run-id ID --commit SHA`; `s04-artifact --dir DIR --s04-run-id ID --run-attempt N`; `s04-job --dir DIR --s04-run-id ID --run-attempt N` | Plan job, the step "Read the cited S04 run" (section 10, check 9): which file it fetches next, as ARDR's commands of the same names. Each judges the answer saved last with the checker's own function (`s04_run`: the run, `--commit` being `GITHUB_SHA`; `s04_artifact_id`; `s04_job_id`) and refuses with that check's code | `run_attempt`; `id` (the artifact's, or null when it is not listed or has expired); `id` (the record job's) |
| confirm `report --listing DIR --attempts DIR --mode M --registration-sha256 HEX --run-id ID --head-sha SHA --run-attempt N --source-sha256 HEX --output NEW_FILE [--observations NEW_FILE]` | Report job: the collection report and, CONFIRMATORY, the observation list. `--run-attempt` is `GITHUB_RUN_ATTEMPT` and `--source-sha256` the plan job's tree hash (section 8.3). Exit 0 for `PASS`, `FAIL`, `OPEN` and for a read EXPLORATORY attempt; otherwise exit 2, `result` `INCONCLUSIVE`, the cause as `code` (`EVIDENCE_MISSING` for an EXPLORATORY attempt that is `LOST`, section 8.1), the report still written. Both lines carry `coverage`, the report's own key (section 8.2): `OK`, or the code that refused the coverage. Nothing is written on stderr | `verdict` (the result, or null), `attempts`, `coverage`, `sha256`, `observations_sha256` |

**`start`**, in order. A refusal before S8 leaves no marker, so the attempt never started.

- S1. Read the declaration (section 4.1). Its `run_id`, `head_sha` and `run_attempt` must be `GITHUB_RUN_ID`, `GITHUB_SHA` and
  `GITHUB_RUN_ATTEMPT` = 1 (`DECLARATION_OTHER_RUN`), and `--source-sha256` its `source_sha256` (`SOURCE_MISMATCH`). Create the
  records and work directories new (`OUTPUT_EXISTS`).
- S1b (PR-2b). `--bin-dir` holds `bitagi` and `test_only_signet_store_fixture`, each a regular file that is not a link and is
  executable (`TOOL_BINARY_MISSING`), each of the declaration's `binaries` SHA-256 (`BINARY_MISMATCH`). Both are copied into
  `<work>/bin/` and hashed again there, so every path a log names lies in the work directory.
- S2. Hash both `bitcoind` files. Start each node in its own new session, datadir `<work>/node-<x>`, with exactly `-signet
  -signetchallenge=51 -datadir=<dir> -server=1 -listen=1 -bind=127.0.0.1:<p2p> -rpcbind=127.0.0.1 -rpcallowip=127.0.0.1
  -rpcport=<rpc> -rpcauth=<auth> -connect=127.0.0.1:<other p2p> -dnsseed=0 -fixedseeds=0 -discover=0 -listenonion=0
  -disablewallet=1 -printtoconsole=0` (the driver's `NODE_ARGS`; the checker does not compare `args`, so a change the local
  smoke forces is made there and in this line together). `<auth>` is the RPC auth line of the public Class T fixture user of
  `crates/bitagi-bitcoin/src/rpc_credentials.rs` (`bitagi-class-t`), computed from the public recipe with a fresh salt per
  node per attempt (PR-2 decision 1: B's fixture and `bitagi monitor tick` authenticate only as that user); no secret exists,
  and `environment.json` writes the argument as `-rpcauth=<CLASS_T_PUBLIC_FIXTURE>`, never the salted line. Every RPC of the
  driver goes through that node's own `bitcoin-cli -signet -datadir=<dir> -rpcport=<rpc> -rpcclienttimeout=20`: cookie
  authentication is `bitcoin-cli`'s, and the tools never open, read, copy or print a cookie file. No node is ever restarted.
- S3. Within 120 s both nodes answer and each reports at least one peer (`NODE_NOT_READY`, `PEERS_NOT_CONNECTED`).
  `getblockchaininfo` on both: `chain` = `main` refuses with `MAINNET_REFUSED`; any `chain` but `signet`, or a `signet_challenge`
  that is absent or not `51`, refuses with `UNSUPPORTED_SIGNET_CONTEXT`.
- S4, S5. Critical read `GENESIS` / `FIRST` (section 4.5). Pre-mine heights 1..199 (section 2): each block by its producer, then
  seen on the other node within 60 s (`PREMINE_FAILED`), one `blocks.jsonl` row each. Critical read `H0_MINUS_1` / `FIRST`.
  A read of S4 or S5 whose two hashes differ is written like any other disagreement (its row with `agree` false and its
  incident file) and `start` does not refuse for it. When `start` still reaches S8 the attempt is counted and its S14 is
  `FAIL`. When `start` ends before S8 for another reason (two nodes on different chains do not relay, so the pre-mine
  fails), the records still hold the row and the report reads it (section 8.3).
- S5r (PR-2b). When the `H0_MINUS_1` / `FIRST` read agrees, build the replay store: `<work>/bin/test_only_signet_store_fixture
  <work>/replay <h0> <that read's hash> <genesis> 51 38432 38442`, at most 330 s. Exit 0 with one BUILD line of section 4.7
  whose `genesis_hash_display`, `signet_challenge_hex`, `first_effective_height`, `as_of_height` (`h0` − 1) and
  `as_of_block_hash_display` are these, and whose `store_path` is the real path of `<work>/replay/store.sqlite3`, is `BUILT`.
  Any other outcome writes `replay_build.json` with that result and then refuses (`REPLAY_BUILD_FAILED`). When the read
  disagrees nothing is built (`NOT_BUILT_S14_DISAGREEMENT`), no monitor is started (its request names the build's deployment
  id) and `start` goes on, as S4 and S5 do.
- S6. Write `environment.json`, `components.json`, `txs.jsonl`, `reserve_snapshots.jsonl`, and the declaration's exact bytes as
  `declaration.json`.
- S6m (PR-2b). With a built store: write `monitor/request.json` (`monitor_request()`, section 4.8) in the work directory and
  in the records, and spawn in a new session `python3 -B tools/claude_track_monitor.py run --bitagi <work>/bin/bitagi --request
  <work>/monitor/request.json --log <work>/monitor/monitor.jsonl --poll-s 120 --tick-timeout-s 60` (no acknowledgement or mark
  input), its output and error output to `<work>/monitor/monitor.out` and `monitor.err`, `TMPDIR=<work>/monitor/tmp`. Wait at
  most 60 s for its log's START line (`MONITOR_NOT_STARTED`, also when the loop is gone before it).
- S7, S8. Spawn `daemon` in a new session and wait at most 120 s for sample 0 (`DAEMON_NOT_STARTED`). Write `marker.json`
  (section 4.6); the workflow uploads it as `p5002-started` in its next step.

**`finish`**: F1 stop the daemon if it still runs (the stop reason is then `FINISH`; a daemon gone without a stop reason is
`DAEMON_DEAD`; a follow in flight is awaited, at most 340 s). F1m (PR-2b) SIGTERM to the monitor's leader (it ends a running
tick and writes STOP `SIGNAL_SIGTERM`, exit 0), at most 90 s for it, then its session is killed. F1r (PR-2b) with a built
store, one last follow, its row `read` `FINAL` (no block follows once the daemon stopped). F2 for the nodes that still answer:
critical reads `GENESIS`, `H0_MINUS_1`, `H0` / `FINAL` and each `signet_challenge`. F3 stop both nodes (RPC `stop`, then the
session's process group is killed) and count the processes left in the four sessions, and (PR-2 decision 13) every live
process whose executable (`/proc/<pid>/exe`) is `<work>/bin/bitagi` or `<work>/bin/test_only_signet_store_fixture` in no
session of the four: a tick a killed monitor left behind runs in a session of its own. F4 copy each `debug.log` to
`node-logs/node-<x>.log` unless it holds a credential word (then it is withheld), under the same rule the daemon's own output
and error output `<work>/daemon.out` and `<work>/daemon.err` to `node-logs/daemon.out` and `node-logs/daemon.err`, each cut to
its last 64 KiB (the daemon's closing line, and a dead daemon's traceback: the work directory is never uploaded; A decision 7),
and the monitor's log whole to `monitor/monitor.jsonl` (never cut, so its START and STOP both survive; not copied above
`LINES_LIMIT`: `TOO_LARGE`) and its error output's last 64 KiB to `monitor/monitor.err`. A credential word is `rpcpassword` or
`__cookie__` anywhere, or `rpcauth` anywhere except as the exact bytes `rpcauth=****` followed by `\n` (Core's own redacted
line for the command-line `-rpcauth`, PR-2 decision 1) or inside the exact bytes `Using rpcauth authentication.` followed by `\n` (Core 30.3 and 31.1 write it when `-rpcauth` is given; seen in the 11-18 scaled pilot). While copying, every occurrence of the work directory's absolute path
is written as `<work>` and every occurrence of the runner user's home directory as `<home>`, in every copied file alike (the
work directory first, since it may lie under the home directory); the credential scan reads the file as it is. F5 write
`final.json`. Exit 0, or after F5 `CREDENTIAL_MATERIAL` (a withheld file, the monitor's two included; it comes first) or
`LEFTOVER_PROCESS`. A second `finish` refuses with `OUTPUT_EXISTS`.

**Workflow contract** (`claude-track-p5002.yml`; `workflow_dispatch` only; `permissions: {}`; run name `p5002 <MODE> attempt <N>
registration <sha256|none>`, N without a leading zero, the hash for CONFIRMATORY and none for every EXPLORATORY dispatch, the pilot
from an attempt tag included (its declaration names no registration); inputs `mode`, `attempt`, `expected_head`, `registration`,
`registration_sha256`, `s04_run_id`, `duration_seconds`, `sample_seconds`, `block_seconds`, `checkpoint_seconds`). Five jobs:

- `P5-002 exclusive (hosted)`: no run of the 7a, VPS checks, XD-1 confirmatory or this workflow waits or runs.
- `P5-002 build (hosted)` (PR-2b, PR-2 decision 2; `contents: read`, 30 minutes, after `exclusive`): checkout of the
  dispatched commit without persisted credentials, the pinned toolchain (`rustup show active-toolchain || rustup toolchain
  install`), then under `env -i` with the 7a list of kept variables `cargo build --locked -p bitagi-cli --bin bitagi --example
  test_only_signet_store_fixture` (dev profile without debug information, the cargo home and the checkout remapped); the two
  files packed into `p5002-bin.tar` (fixed order, owner and time) and uploaded as `p5002-bin` (3 days); the tar's SHA-256
  and each file's are the job's outputs. It succeeds only once B's fixture and `bitagi monitor tick` are on the dispatched
  commit. The binaries are made here, never on the VPS (no Rust there).
- `P5-002 plan (hosted)` (after `exclusive` and `build`): archive exactly `tools/claude_track_p5002_driver.py`,
  `tools/claude_track_p5002_check.py`, `tools/claude_track_exit.py`, `tools/claude_track_monitor.py` and this document (A
  decision 6, the monitor loop added by PR-2b; the plan job still hashes every `REGISTERED_PATHS` file of its own checkout);
  for a dispatch from an attempt tag (`if: startsWith(github.ref, 'refs/tags/ct-p5002-a')`), the step "Read
  the cited S04 run": with the S04 run id input empty it reads nothing (`plan` then refuses), else GET requests only, ARDR's
  sequence: the run into `run.json`, `s04-run`, its artifact listing filtered by `s04-record-v2-<run id>-<attempt>` into
  `artifacts.json`, `s04-artifact`, then the artifact's zip into `record.zip` or, with no id, the attempt's jobs listing into
  `jobs.json`, `s04-job`, and that job's log into `job.log`, all under `target/p5002/s04`; `plan` with `--s04-dir
  target/p5002/s04` and the build job's three hashes (never inputs; its `required_seconds()` reads the policy file of
  section 2 from this checkout, no Codex ledger file);
  save the listing, each earlier run's artifact and attempt-1 jobs listings and, of an earlier run without the marker, the
  records zip `downloads` names; `continuity` (the registration hash is passed for CONFIRMATORY only); upload
  `p5002-declaration` (90 days) and `p5002-source` (3 days). Its output `bin_sha256` passes the build job's tar hash on.
- `P5-002 observe (VPS)` (label `bitagi-ct7a-vps`, no token): the identity step (from an attempt tag CONFIRMATORY or EXPLORATORY,
  from main EXPLORATORY); the tree after its SHA-256; the declaration; `p5002-bin`, unpacked into `$RUNNER_TEMP/p5002-bin/bin`
  only after the tar's SHA-256 is the plan job's `bin_sha256`;
  Python; Core 31.1 and 30.3; `start` (with `--bin-dir`); upload `p5002-started` = `marker.json`; for K = 1..26 `checkpoint` and, when scheduled,
  upload `p5002-checkpoint-<K>` = `checkpoint-<K>.json` (a failed upload fails the job); then, both with `if: always()`,
  `finish` and the upload of the records directory as `p5002-records`.
- `P5-002 report (hosted)` (`if: always()` and the plan succeeded): save the listings and zips; `report` (the registration hash
  passed for CONFIRMATORY only; CONFIRMATORY: the registered constants through `required_seconds()`, the policy file of section
  2); print each file
  with its SHA-256 and upload `report.json` and `observations.json` as `p5002-report-attempt-<run_attempt>`, replacing any
  artifact of that name (`overwrite: true`). The printed SHA-256 lines are the two files' identity (section 11).

## 4. Records

**Canonical serialization.** `json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True)` as ASCII bytes:
objects, lists, strings, integers, booleans and null only (never a float). A **line** is that text plus one `\n`. Every `.json`
record is one line; every `.jsonl` record is zero or more lines and nothing else. Reading is strict: no duplicate key, no float,
no NaN or Infinity, the closed key set, `type(x) is int` for integers (0 ≤ x < 2^63), lower-case hex of the stated length, a
bounded regular file that is not a link. Known answer: the line `{"prev_sha256":"<64 zeros>","seq":0}` has `line_sha256`
`abc46256fe3f63509d41a94dae502666134eeec413e5d4aec20cc856d36f9b6b`.

Clocks, read in this order: `monotonic_ns` = `time.monotonic_ns()`, `boottime_ns` = `time.clock_gettime_ns(time.CLOCK_BOOTTIME)`,
`realtime_ns` = `time.time_ns()`. `t0` is sample 0's `monotonic_ns`. The records directory holds `declaration.json`,
`environment.json`, `marker.json`, `samples.jsonl`, `blocks.jsonl`, `critical_heights.jsonl`, `components.json`,
`replay_build.json`, `replay.jsonl`, `txs.jsonl`, `reserve_snapshots.jsonl`, `checkpoint-<k>.json`, `final.json`, `incidents/`,
`node-logs/` and `monitor/` (`request.json`, `monitor.jsonl`, `monitor.err`). The work directory is never uploaded: it holds the
two data directories (with each node's cookie file while it runs), `bin/` (the two binaries), `replay/` (the fixture's store),
`monitor/` (the request, the log, the loop's output and error output, its temporary folder) and the driver's own `state.json`
(the leaders of the four sessions: two nodes, the daemon, the monitor), `daemon-stop.json`, `daemon.out` and `daemon.err`
(`finish` copies the last two to `node-logs/`).

### 4.1 `declaration.json` (`BITAGI_CT_P5002_DECLARATION_V1`; written by `plan`)

| Key | Type and value |
|---|---|
| `format`, `mode`, `attempt` | the name above; `CONFIRMATORY` or `EXPLORATORY`; integer, CONFIRMATORY 1..3, EXPLORATORY 1 |
| `head_sha`, `ref`, `run_id`, `run_attempt` | `GITHUB_SHA` (40 hex); `GITHUB_REF`: CONFIRMATORY an `ATTEMPT_TAG` ref, EXPLORATORY `refs/heads/main` or, for the TEST_ONLY pilot, an `ATTEMPT_TAG` ref; integers, `run_attempt` 1 |
| `registration_sha256` | CONFIRMATORY: 64 hex. EXPLORATORY: null, the pilot included (its TEST_ONLY file is not a registration; XD-1 C2) |
| `s04_run_id`, `s04_citation` | A cited declaration (its `ref` is an attempt tag: CONFIRMATORY, or the pilot): a positive integer, and plan check 9's result `{"record_sha256"` (64 hex, of the record's bytes)`, "record_source"` (`ARTIFACT` or `JOB_LOG`)`, "s04_run_attempt"` (1..999)`, "s04_head_sha"` (40 hex, the cited run's head)`, "subjects"` (1..4,096, the record's subject count)`}`. Otherwise (EXPLORATORY from main): null and null |
| `source_sha256` | 64 hex: the SHA-256 of the tree archive the plan job uploads |
| `binaries` | (PR-2b) `{"archive_sha256", "bitagi_sha256", "fixture_sha256"}`, 64 hex each: the hosted build job's `p5002-bin.tar`, `bitagi` and `test_only_signet_store_fixture` (`BINARIES_SHA256` when one is absent or malformed) |
| `scaling`, `constants`, `labels` | `REGISTERED_CONSTANTS` (always, for CONFIRMATORY) or `EXPLORATORY_SCALED`; the effective constants, which satisfy section 2's formulas and bounds; the mode's list (section 1) |

### 4.2 `environment.json` (`BITAGI_CT_P5002_ENVIRONMENT_V1`; written by `start`)

| Key | Type and value |
|---|---|
| `format`, `mode`, `attempt`, `head_sha`, `run_id` | the name; the declaration's values |
| `source_sha256` | the value the VPS job checked (`--source-sha256`) |
| `nodes` | `{"a": N, "b": N}`, N = `{"name"` (`SIGNET_NODE_A`, `SIGNET_NODE_B`)`, "version"` (`getnetworkinfo`'s integer)`, "bitcoind_sha256", "args"` (the list of S2, the work directory written as `<work>` and the RPC auth line as `<CLASS_T_PUBLIC_FIXTURE>`)`, "p2p_port", "rpc_port"}` |
| `binaries` | (PR-2b) `{"bitagi", "fixture"}`: the SHA-256 of each binary as S1b computed it in `<work>/bin/` |
| `signet_challenge_hex`, `genesis_hash`, `h0` | `51`; `getblockhash 0`, equal on both nodes; 200 |
| `boot_id`, `clock` | `/proc/sys/kernel/random/boot_id` (36 characters); `{"source"` (the kernel's current clocksource, 0..32 characters: empty when it could not be read, and then the identity check `ENVIRONMENT_CLOCK` fails, section 8.1)`, "ntp_synchronized"` (boolean, or null when not readable)`}` |
| `host` | `{"nproc", "mem_total_kb", "disk_free_kb"` (integers)`, "kernel", "python"` (at most 64 characters)`, "runner_name"` (`RUNNER_NAME` or `""`)`}` |
| `start_monotonic_ns`, `start_realtime_ns` | when `start` began |
| `labels`, `transferability`, `scope_b`, `s14_not_covered` | section 1 |

### 4.3 `samples.jsonl` (the hash chain; written by the daemon's sampler only)

`prev_sha256` of line n is the SHA-256 (64 hex) of line n − 1's exact bytes without its `\n`; line 0 has 64 zeros. The **chain
head** of a file is the SHA-256 of its last line without the `\n` (64 zeros when empty). The sampler takes a sample, then sleeps
until `sample_seconds` after that sample's own `monotonic_ns`; it never back-fills a missed sample and never rewrites a line.
Each line is one `os.write` on an append-only descriptor.

| Key | Type and value |
|---|---|
| `seq`, `prev_sha256` | integer, the line's index from 0; 64 hex |
| `monotonic_ns`, `boottime_ns`, `realtime_ns` | integers, read before this sample's RPCs |
| `boot_id`, `sampler_pid` | as section 4.2; the daemon's pid |
| `nodes` | `{"a": N, "b": N}`, N = `{"ok", "pid", "uptime", "chain", "blocks", "bestblockhash", "mediantime", "signet_challenge", "genesis_hash", "connections", "networkactive", "mempool_size"}` |

N: `ok` is true when every read of that node answered within `RPC_SECONDS`, and then no value is null; when `ok` is false every
other value is null. `pid` is the integer in the node's pid file (`<datadir>/signet/bitcoind.pid`); `uptime` is RPC `uptime`;
`chain`, `blocks`, `bestblockhash`, `mediantime`, `signet_challenge` are `getblockchaininfo`'s; `genesis_hash` is
`getblockhash 0`; `connections` and `networkactive` are `getnetworkinfo`'s; `mempool_size` is `getmempoolinfo`'s `size`.

**Tip replacement.** For a node `ok` in this sample, against that node's part of its last `ok` sample (the one before, or an
earlier one when failed samples lie between): when its height dropped or `getblockhash <previous blocks>` is not its previous
`bestblockhash`, the sampler walks `getblockheader` from the previous tip by `previousblockhash` to the first header with
`confirmations` ≥ 1 and writes a `FORK_POINT` critical read at that height (section 4.5) with this sample's `seq` and that
node. When a read of the walk gets no answer, or the fork height is found and the `FORK_POINT` read writes no row (a node did
not answer it), that node's part of this sample is written not `ok` (a failed sample), the tip compared stays the one before
the replacement, and the same comparison is made again at the next sample: a fork point is not dropped. A replacement
between `start`'s reads and sample 0 has no sample to detect it; section 6's comparison of the `FIRST` and `FINAL` reads
sees one that reached a critical height.

### 4.4 `blocks.jsonl` (written by `start`, then by the daemon's producer)

Inside the observation, block n (n = 0, 1, …; height `h0` + n) is due at `t0` + (n + 1) × `block_seconds`, produced by `a` when
n is even and by `b` when odd, late rather than skipped, one at a time. The producer runs apart from the sampler (a slow block
never delays a sample) and repeats `generatetodescriptor`, each call's tries sized to return within `RPC_SECONDS`, until one
block hash returns (the driver's `GENERATE_TRIES`, 4,000,000: the local smoke measured 16 calls a block at 1,000,000 tries and
1.9 at 4,000,000, on a host of about 4,000,000 tries a second, which fits a block template stamped with its second, so that a
call repeated within that second tries the same nonces again). `GENERATE_TRIES` is a harness constant, not a
criterion: no result of sections 5 to 8 reads it. H0 is block 0: the first block inside the observation (A Q3).

| Key | Type and value |
|---|---|
| `n`, `phase` | integer, the line's index from 0; `PREMINE` (heights 1..199) or `INTERVAL` |
| `height`, `hash`, `producer`, `tries` | integer; 64 hex; `a` or `b`; integer ≥ 1, the `generatetodescriptor` calls made for this block |
| `produced_monotonic_ns`, `produced_realtime_ns` | when the producer's call returned the hash |
| `seen_other_monotonic_ns`, `seen_other_realtime_ns` | when the other node first reported that hash at that height (polled each second), or null |

### 4.5 `critical_heights.jsonl` (one writer at a time: `start`, then the daemon, then `finish`)

| Key | Type and value |
|---|---|
| `n`, `kind` | integer, the line's index from 0; `GENESIS` (height 0), `H0_MINUS_1` (`h0` − 1), `H0` (`h0`) or `FORK_POINT` |
| `read` | `FIRST` or `FINAL` for the first three kinds; `EVENT` for `FORK_POINT` |
| `height`, `hash_a`, `hash_b`, `agree` | integer; `getblockhash <height>` on each node (64 hex; a row is written only when both answered); boolean, `hash_a` = `hash_b` |
| `seq`, `node` | `FORK_POINT`: the detecting sample's `seq` and its node (`a` or `b`). Otherwise null and null |
| `monotonic_ns`, `realtime_ns` | when the second hash was read |

`GENESIS` and `H0_MINUS_1` / `FIRST` are `start`'s (S4, S5); `H0` / `FIRST` is the daemon's, once block 0 is on both nodes; the
three `FINAL` rows are `finish`'s (F2). No public report cutoff falls inside the run.

### 4.6 The other records

- `marker.json` (`BITAGI_CT_P5002_MARKER_V1`, anchor 0): `format`; the declaration's `mode`, `attempt`, `head_sha`, `run_id`,
  `run_attempt`, `registration_sha256`; `seq` (0); `head_sha256` (the chain head after sample 0); `monotonic_ns`, `realtime_ns`
  (when written).
- `checkpoint-<k>.json` (`BITAGI_CT_P5002_CHECKPOINT_V1`, anchor k, 1 ≤ k ≤ `checkpoints`): `format`, `run_id`, `attempt`,
  `index` (k), `due_monotonic_ns` (`t0` + k × `checkpoint_seconds` × 10^9), `monotonic_ns`, `realtime_ns` (when written), `seq`
  and `head_sha256` (the last complete sample line then), `daemon_state` (`RUNNING`, `STOPPED` or `DEAD`), `stop_reason`
  (`STOP_RULE` or `DEADLINE` when `STOPPED`, else null), `blocks` and `critical_reads` (line counts), `s14_disagreements` (rows
  with `agree` false), `current_interval_seconds` (the VPS's own `intervals()` result; informational).
- `final.json` (`BITAGI_CT_P5002_FINAL_V1`): `format`, `run_id`, `attempt`, `stop_reason` (`STOP_RULE`, `DEADLINE`, `FINISH` or
  `DAEMON_DEAD`), `samples`, `head_sha256`, `monotonic_ns`, `realtime_ns`, `challenge_final` (`{"a", "b"}`: each node's
  `signet_challenge` at F2, or null), `nodes_stopped` (`{"a", "b"}` booleans: no process of that node's session is left
  when F3 ends), `leftover_processes` (integer), `node_logs` (`{"a", "b"}`: `COPIED`, `WITHHELD_CREDENTIAL_SCAN` or
  `MISSING`), `daemon_logs` (`{"out", "err"}`, the same three states for `daemon.out` and `daemon.err`: `COPIED` also for an
  empty file, `MISSING` when the file is not there), `monitor` (PR-2b: `{"log", "err", "exit", "stop_reason"}`: the monitor
  log's state, one of the three or `TOO_LARGE`; `monitor.err`'s state, one of the three; the loop's exit and its STOP line's
  `reason` (a reason of `MONITOR_LOG_V1` section 4), read from the log's last line, or null and null without a STOP line),
  `replay_store_sha256` (PR-2b: `{"profile", "store"}`, the SHA-256 of `<work>/replay/profile.bin` and `store.sqlite3` after
  F1r, each null when absent; informational, the store is not uploaded), `vps_summary` (`{"longest_interval_seconds", "breaks",
  "s14_disagreements"}`; informational, the report recomputes), `fleet_scale` (`NOT_MEASURED`).
- `components.json` (`BITAGI_CT_P5002_COMPONENTS_V1`): `{"components": {"monitor": S, "replay": S}, "format"}`, S =
  `NOT_WIRED_PENDING_UNIT` or `WIRED`. Since PR-2b both are `WIRED` (the checker's `NOT_WIRED` is empty).
- `txs.jsonl` and `reserve_snapshots.jsonl`: exactly one line each, `{"fields", "file", "format", "rows", "state"}` with `format`
  `BITAGI_CT_P5002_SCOPE_FILE_V1`, `rows` 0, `state` `NOT_APPLICABLE_SCOPE_B`, `file` the file's name, and `fields`
  `["attempt_id", "tx_hex", "broadcast_realtime_ns", "first_seen_realtime_ns", "inclusion_realtime_ns"]` or `["realtime_ns",
  "reserve_snapshot"]`. Under (b) no transaction is made and no reserve exists (045b `:1033`; A Q7); no synthetic row is written.
- `incidents/s14-disagreement-<n>.json` (`BITAGI_CT_P5002_S14_DISAGREEMENT_V1`), one per critical read whose `agree` is false:
  `{"format", "run_id", "attempt", "row"` (that row)`, "effect": "BROADCAST_LOCK_NO_GO"}`. The observation continues. The report
  recounts from the rows and does not read this folder (section 12), nor `node-logs/` (F4's copies), nor `monitor/monitor.err`.

### 4.7 The replay: `replay_build.json` and `replay.jsonl` (PR-2b; members)

The fixture's two summary lines (`fixture_line()`): exactly one LF-ended line of strict UTF-8 JSON on stdout, exit 0. BUILD has
exactly the keys `BUILD_KEYS` (`fixture` `TEST_ONLY_PRIVATE_SIGNET_STORE_FIXTURE`, `mode` `BUILD`, `network` `PRIVATE_SIGNET`,
`node_settings_verification` `UNAVAILABLE`, `genesis_hash_display`, `signet_challenge_hex`, `substrate_context_hash`,
`deployment_id_internal`, `profile_sha256`, `first_effective_height`, `as_of_height`, `as_of_block_hash_display`, `store_path`);
FOLLOW exactly `FOLLOW_KEYS` (`fixture`, `mode` `FOLLOW`, `replay_kind` `SYNTHETIC_CONTEXT_UNVERIFIED_SETTINGS`, `replay_label`
B's Korean constant, `network`, `node_settings_verification`, `substrate_context_hash`, `deployment_id_internal`, `sync_kind`
(`ALREADY_CURRENT`, `EXTENDED`, `REORGANIZED`), `ancestor_height`, `disconnected_blocks`, `connected_blocks`,
`replay_floor_reanchored`, `final_height`, `final_hash_display`, `final_state_digest`). Anything else on exit 0 is
`OUTPUT_INVALID`. A refusal is exit 2 with one stderr line `test_only_signet_store_fixture: [node A: |node B: ]CODE: ...`;
`fixture_refusal()` reads its code (`FIXTURE_REFUSALS`, `OTHER` for a line without one, as an `RpcSession` error) and node;
the text is never copied. B keeps exit 2 for a transient `FOLLOW_REFUSED` (two tips differ), so it is a row, not a stop.

`replay_build.json` (`BITAGI_CT_P5002_REPLAY_BUILD_V1`; written by `start`, S5r): `{"format", "run_id", "attempt", "result"`
(`BUILT`, `NOT_BUILT_S14_DISAGREEMENT`, and for a refused `start` `REFUSED`, `TIMEOUT`, `SPAWN_FAILED` or `OUTPUT_INVALID`)`,
"exit"` (integer, or null when nothing ran or the run gave none)`, "refusal"` (`REFUSED`: the code; else null)`,
"started_monotonic_ns", "ended_monotonic_ns"` (null when nothing ran)`, "line"` (`BUILT`: the BUILD object without
`store_path`, which the driver checks and does not record; else null)`, "label"` (`configuration-unverified synthetic-context
replay`)`}`.

`replay.jsonl` (the daemon's replayer, then `finish`'s F1r; one writer at a time): one line per follow, `{"n", "read"` (`POLL`,
or `FINAL` for F1r's, the last line)`, "started_monotonic_ns", "started_realtime_ns", "ended_monotonic_ns", "exit", "result"`
(`FOLLOWED`, `REFUSED`, `TIMEOUT`, `SPAWN_FAILED`, `OUTPUT_INVALID`)`, "refusal", "refusal_node"` (`A`, `B` or null)`, "line"`
(`FOLLOWED`: the FOLLOW object; else null)`}`. The replayer starts one follow (`<work>/bin/test_only_signet_store_fixture
--follow <work>/replay <h0> <genesis> 51 38432 38442`, at most 330 s) at sample 0 and then every `sample_seconds` from the
previous follow's start, one at a time, never delaying a sample; no follow starts after the stop and one in flight is awaited.
The fixture applies blocks only when both nodes name one tip. Without a built store the file stays empty.

### 4.8 The monitor: `monitor/request.json` and `monitor/monitor.jsonl` (PR-2b; not members)

`monitor/request.json` (written by `start`, S6m; canonical): `monitor_request()` = `{"schema":
"BITAGI_CT_MONITOR_TICK_REQUEST_V1", "context_mode": "CLASS_T_LOOPBACK_SETTINGS_UNVERIFIED", "substrate": {"network":
"PRIVATE_SIGNET", "genesis_hash_display": <environment genesis_hash>, "signet_challenge_hex": "51"}, "deployment_id_internal":
<the BUILD line's>, "store_path": null, "loopback_ports": [38432, 38442], "heart_ref": null, "first_effective_height": <h0>,
"critical_heights": [0, <h0 − 1>, <h0>], "mono_ns": 0}`: -2c-1's P5-002 shape, no store and no Heart (PR-2 decision 5).
`monitor/monitor.jsonl` is the loop's `MONITOR_LOG_V1` log, copied whole by F4 with the `<work>` and `<home>` marks. They are not
members of section 8.1: a missing or withheld monitor log is a monitor check `FAIL`, not a lost attempt, because a separate
process writes it. The `LABELS_REFUSED` scan covers both files.

## 5. Continuity

Inputs: the samples in `seq` order, the `FORK_POINT` rows, the effective constants and `environment.json`'s `genesis_hash`.
Durations are compared in nanoseconds (the constant × 10^9).

- **Good sample.** Both nodes `ok`, and for both `chain` = `signet`, `signet_challenge` = `signet_challenge_hex` and
  `genesis_hash` = the environment's.
- **Breaks.** At sample s with predecessor p (the line before it; sample 0 has none), each kind that holds is recorded at
  s.`seq`, in this order (`BREAK_KINDS`):

| Kind | Holds when |
|---|---|
| `FAILED_SAMPLE` | a node of s is not `ok` (a failed sample is a gap) |
| `CONTEXT` | both nodes of s are `ok` and s is not good (a reset: the genesis or the reported challenge changed) |
| `SAMPLE_GAP` | s.`monotonic_ns` − p.`monotonic_ns` > `gap_seconds`. Exactly 180 s is not a gap; 180 s and 1 ns is |
| `CLOCK_STEP` | step = \|(s.`realtime_ns` − p.`realtime_ns`) − (s.`monotonic_ns` − p.`monotonic_ns`)\| > `clock_step_gap_seconds`. Exactly 60 s is not a gap. A step from `clock_step_record_seconds` (2 s, inclusive) up to 60 s is listed in `clock_steps` and breaks nothing |
| `SUSPEND` | (s.`boottime_ns` − p.`boottime_ns`) − (s.`monotonic_ns` − p.`monotonic_ns`) > `clock_step_record_seconds`: the boot-time clock counts the time the machine was suspended and the monotonic clock does not. Exactly 2 s is not a break; 2 s and 1 ns is. A difference below zero is not this kind |
| `NODE_UPTIME`, `NODE_PID` | for a node `ok` in p and s: `uptime` decreased; `pid` differs (resets) |
| `HEIGHT_DROP` | for a node `ok` in p and s: `blocks` decreased and no `FORK_POINT` row has this `seq` and node (a reset) |
| `BOOT_ID`, `SAMPLER_RESTART` | `boot_id` differs; `sampler_pid` differs or s.`monotonic_ns` ≤ p.`monotonic_ns` (resets) |
| `CLOCK_DRIFT` | the cumulative clock rule below |
| `NO_LIVE_BLOCK` | the live-evidence rule below |

- **Qualifying interval.** Walk the samples in order. A sample that is not good, or that has a break of any kind but
  `CLOCK_DRIFT` and `NO_LIVE_BLOCK`, ends the open interval; that interval's last sample is p. A good sample then opens a new interval when none
  is open, and otherwise extends the open one. The length is `monotonic_ns`(last) − `monotonic_ns`(first); one sample alone has
  length 0. An interval never spans two attempts or two records directories: the chain starts at 64 zeros in a directory `start`
  created, and sample 0 is this attempt's own, taken inside the observe job seconds before the marker that commits it (no
  inherited partial interval, no stitching).
- **Cumulative clock rule.** An open interval keeps `offset_ns` = `realtime_ns` − `monotonic_ns` of its opening sample. For
  each later sample t of the interval, first: when \|(t.`realtime_ns` − t.`monotonic_ns`) − `offset_ns`\| >
  `clock_step_gap_seconds`, `CLOCK_DRIFT` is recorded at t, the interval ends at t's predecessor and t opens a new one.
  Exactly 60 s is not a break. So wall-clock steps that each stay within 60 s cannot add up past 60 s inside one interval
  (five steps of 59 s break at the second); a wall clock that swings back and forth within 60 s of where it stood breaks
  nothing.
- **Live-evidence rule** (GOV072 `:97-98`). An open interval keeps `witness_ns` and `witness_height`, set when it opens to the
  opening sample's `monotonic_ns` and the lower of its two `blocks`. For each later sample t of the interval, after the
  cumulative clock rule: when t.`monotonic_ns` − `witness_ns` > `live_window_seconds`, `NO_LIVE_BLOCK` is recorded at t, the
  interval ends at t's predecessor and t opens a new one. Exactly 1,800 s is not a break. Otherwise, when both nodes of t report one `bestblockhash`
  and `blocks` > `witness_height`, t is a block witness and both values become t's.
- **No admissible outage.** Every break restarts the count from zero; an explanation changes nothing.
- **Suspends and pauses.** `boottime_ns` is judged: a guest suspend stops the monotonic clock while the boot-time clock
  runs on, so a suspend of more than 2 s between two samples is a `SUSPEND` break at the later one, whatever the wall
  clock shows (this replaces A decision 11, under which the value was only recorded). A pause of the whole virtual
  machine stops every guest clock, so no sample rule sees it by itself: it shows as `CLOCK_STEP` or `CLOCK_DRIFT` only
  once the time daemon moves the wall clock by more than 60 s, and otherwise through the server anchors, as
  `SA7_SAMPLE_TIE` when the pauses between the anchors that bracket the longest interval add up to more than
  `gap_seconds` + `anchor_slack_seconds` (480 s) of server time. Pauses below that sum are not seen (section 11, item 4).
  The report's two `margins` (section 8.1) show how close a run came to the 60 s and to the 480 s.
- **S13 continuity** is met when the longest interval (the earliest on a tie) has length ≥ `required_seconds`: 86,400 s exactly
  passes; 86,399 s, or 86,400 s less 1 ns, fails.
- **Stopping rule** (the daemon, after each sample, with the same `intervals()`). `STOP_RULE`: the interval holding the last
  sample has length ≥ `required_seconds` + `stop_margin_seconds` (87,000 s). `DEADLINE`: the monotonic clock is at or past `t0` +
  `checkpoints` × `checkpoint_seconds` (93,600 s), checked before each sample. After either, no sample is taken and no block is
  produced. Nothing else stops the daemon by itself: a break never does.

## 6. S14 and the challenge check

Covered (TDS 6.8 `:870-878` under scope (b)): height 0, H0 − 1, H0, every reorganization fork point the sampler detects (section
4.3; none is expected with one producer at a time), and public report cutoffs (none inside the run: `report_cutoffs` is
`NONE_IN_RUN`). Not covered: the line `S14_NOT_COVERED`.

- `disagreements` is the number of `critical_heights.jsonl` rows with `agree` false, over every read.
- `FAIL` when `disagreements` ≥ 1: an automatic broadcast lock and NO-GO (TDS `:880`), whatever a later attempt shows.
- `PASS` when `disagreements` = 0, each of `GENESIS`, `H0_MINUS_1`, `H0` has exactly one `FIRST` row and exactly one `FINAL`
  row at its height, each `FINAL` row shows the hash of its `FIRST` row, every `GENESIS` row shows `environment.json`'s
  `genesis_hash`, `blocks.jsonl` holds exactly one row of height `h0` and its `hash` is the `H0` / `FIRST` read's, and no
  `FORK_POINT` row has a height at or under `h0`.
- `INCOMPLETE` otherwise: no disagreement was read, but the agreement the gate asks for is not recorded. `missing` lists
  `<kind>:<read>` for a read that is not there exactly once at its height, `<kind>:REPLACED` when the `FIRST` and `FINAL` rows
  of a kind both agree and name different blocks (the chain was rewritten at or below that critical height between the two
  reads, with or without a recorded fork point), `GENESIS:NOT_ENVIRONMENT` when an agreeing `GENESIS` row names another
  hash than the environment's, `H0:NOT_PRODUCED_BLOCK` when the `H0` / `FIRST` read is there once, agrees, and
  `blocks.jsonl` has no row, two rows or another `hash` at height `h0` (the block both nodes showed at H0 is not the one
  the producer recorded), and `FORK_POINT:AT_OR_UNDER_H0` when a `FORK_POINT` row has a height at or under `h0` (the
  chain was rewritten down to a critical height; a fork point exactly at `h0` leaves block `h0` in place and is listed
  all the same). A rewrite that replaces the block at a critical height after its `FIRST` read therefore never leaves
  S14 `PASS`, whether the sampler saw it or not. The `H0` check is part of `s14_table` (it gets the rows of
  `blocks.jsonl`), not an identity check. Whether such a rewrite is also a break of S13 is not decided here: a height
  drop with its `FORK_POINT` row breaks nothing in section 5.
- **Challenge check** (the CT-P3-044a binding; T-5002 `:14`, "unsupported Signet context"). `start` refuses unless both nodes
  report `signet_challenge` = `51` (S3); every good sample carries it for both nodes; `final.json`'s `challenge_final` is `51` for
  both. `s14.challenge` is `PASS` when the last holds and no `CONTEXT` break exists, else `FAIL`; a `FAIL` makes the attempt's
  S13 `FAIL` (identity check `CHALLENGE`). Genesis equality alone proves nothing: every Signet shares one genesis block.

## 7. Server anchors (hosted report only)

Anchor 0 is `marker.json` in the artifact `p5002-started`; anchor k is `checkpoint-<k>.json` in `p5002-checkpoint-<k>`.
`anchor_time(k)` is that artifact's `created_at` in the run's artifact listing (GitHub server time, whole seconds);
`anchor.realtime_s` is the file's `realtime_ns` // 10^9; `anchor.monotonic_ns` and `anchor.realtime_ns` are the file's own
values; (i, j) are the first and last `seq` of the longest interval. Each rule that fails is listed in
`s13.anchors.failed`:

| Rule | Check |
|---|---|
| `SA1_JOB_ORDER` | the observe job's `started_at` ≤ `anchor_time(0)` |
| `SA2_CLOCK_TIE` | for every anchor: \|`anchor.realtime_s` − `anchor_time(k)`\| ≤ `anchor_slack_seconds` |
| `SA3_PREFIX` | for every anchor: line `seq` of the final `samples.jsonl` has `line_sha256` = its `head_sha256`; `seq` never decreases with k; anchor 0 has `seq` 0; each file's `run_id`, `attempt` and (checkpoints) `index` are its own |
| `SA4_SPACING` | for k ≥ 1: 0 ≤ `anchor_time(k)` − `anchor_time(k − 1)` ≤ `checkpoint_seconds` + `anchor_slack_seconds` (an anchor is never created before the one it follows) |
| `SA5_ALL_PRESENT` | anchors 0..`checkpoints` are all listed, each once, none expired, each file valid |
| `SA6_SPAN` | with a = the last anchor whose `seq` ≤ i and b = the first anchor whose `seq` ≥ j (both must exist): `anchor_time(b)` − `anchor_time(a)` ≥ `required_seconds`. `server_span_seconds` is that difference, or null |
| `SA7_SAMPLE_TIE` | with s(k) = line `seq` of anchor k in the final `samples.jsonl` (an anchor whose `seq` is no line is SA3's) and T = `gap_seconds` + `anchor_slack_seconds`: (1) the observe job's `started_at` − `anchor_slack_seconds` ≤ s(0).`realtime_ns` // 10^9 ≤ `anchor_time(0)` + `anchor_slack_seconds` (a file with no sample fails this part); (2) for anchor 0 and every checkpoint whose `daemon_state` is `RUNNING`: 0 ≤ `anchor.monotonic_ns` − s(k).`monotonic_ns` ≤ T and \|`anchor.realtime_ns` − s(k).`realtime_ns`\| ≤ T (in ns); (3) a checkpoint whose `daemon_state` is `STOPPED` or `DEAD` has the `seq` of the last line; (4) for every anchor k with a < k ≤ b (SA6's a and b): \|(s(k).`monotonic_ns` − s(a).`monotonic_ns`) // 10^9 − (`anchor_time(k)` − `anchor_time(a)`)\| ≤ T |

SA7 ties the samples' own clocks to server time: a checkpoint of a running sampler commits a sample at most T old on both
clocks (so a head that commits nothing new, or a chain whose clocks were shifted, fails), sample 0 lies inside the observe
job (no inherited or backdated chain), and between the bracketing anchors the committed samples' monotonic time follows
server time within T (SA6 alone bounds the interval from above only). An honest checkpoint's head is at most one sample
period and one slow sample old. A duplicate harness artifact name in a run's listing, or a checkpoint artifact name outside
1..26, is not an anchor failure: it stays `ARTIFACT_LISTING` (exit 3, no report; A decision 4).

## 8. Report `BITAGI_CT_P5002_REPORT_V1`

### 8.1 Attempt row

`{"attempt", "run_id", "run_attempt", "created_at", "started_at", "start_time_utc", "runner_labels", "state", "scaling",
"stop_reason", "samples_partial_last_line", "s13", "s14", "components", "component_checks", "blocks"}`, `state` = `COUNTED`. `started_at` is the
observe job's server start (the attempt-1 jobs listing) and `start_time_utc` the same in integer seconds; the four listing
values are null for `attempt`. `samples_partial_last_line` is true when `samples.jsonl` holds bytes after its last newline
(one line a killed writer left unfinished, which the read dropped), else false.

- `s13`: `{"result", "reason", "required_seconds", "samples", "intervals", "longest", "breaks", "clock_steps", "identity",
  "anchors", "margins"}`. `longest` is `{"first_seq", "last_seq", "monotonic_ns", "seconds", "ended_by"}` or null (`seconds` =
  `monotonic_ns` // 10^9; `ended_by` the first break kind that ended it, or null); `intervals` is their count; `breaks` is
  `[{"seq", "kind"}]` and `clock_steps` `[{"seq", "step_ns"}]`, each cut to its first 1,000; `identity` lists the failed identity
  checks; `anchors` is `{"result"` (`PASS`, `FAIL` or `NOT_CHECKED`)`, "failed", "server_span_seconds", "present"` (the anchor
  indices listed)`}`.
- `s13.margins`: `{"clock_drift_max_ns", "anchor_skew_max_seconds"}`, two observed numbers that no result reads (they show
  how close a run came to a bound). `clock_drift_max_ns` is the largest \|(t.`realtime_ns` − t.`monotonic_ns`) −
  `offset_ns`\| over the samples t of the longest interval, `offset_ns` being that interval's opening sample's (the
  quantity of section 5's cumulative clock rule, whose bound is `clock_step_gap_seconds`); null when there is no interval.
  `anchor_skew_max_seconds` is the largest value part (4) of `SA7_SAMPLE_TIE` compared with T (section 7); null when the
  anchors are not checked or that part compared nothing.
- **Identity checks** (T-5002 `:14`): `ENVIRONMENT_BINDING` (`mode`, `attempt`, `head_sha`, `run_id` are the declaration's),
  `ENVIRONMENT_SOURCE` (`source_sha256`), `ENVIRONMENT_BINARY` (each node's `version` and `bitcoind_sha256` are section 2's),
  `ENVIRONMENT_BINARIES` (PR-2b: `binaries` is `{"bitagi", "fixture"}` of the declaration's `bitagi_sha256` and
  `fixture_sha256`), `ENVIRONMENT_CONTEXT` (`signet_challenge_hex`, `h0`, the two fixed lines, `transferability`), `ENVIRONMENT_CLOCK`
  (`clock.source` is not empty, sample 0's `boot_id` is the environment's and, for a CONFIRMATORY attempt,
  `clock.ntp_synchronized` is true; an EXPLORATORY attempt records that value and is not refused for it),
  `RECORDS_DECLARATION` (the records'
  `declaration.json` has the bytes of the `p5002-declaration` artifact), `CHALLENGE` (section 6).
- **S13** `result` is `PASS` when `identity` is empty, the continuity of section 5 is met and `anchors.result` is `PASS`.
  Otherwise it is `FAIL`, and `reason` is the first of `IDENTITY`, `INTERVAL_SHORT`, `SERVER_ANCHOR`,
  `SERVER_ANCHOR_NOT_CHECKED` that applies.
- `s14`: `{"result", "reads", "disagreements", "monitor_disagreements", "covered", "fork_points", "missing",
  "report_cutoffs", "challenge", "not_covered"}`. `covered` is `[{"kind", "height", "first_agree", "final_agree"}]` (null for
  a missing read), `fork_points` is `[{"height", "agree", "seq", "node"}]`, `missing` is section 6's list, `not_covered` is
  the fixed line. `monitor_disagreements` (PR-2 decision 4) counts the monitor log's CRITICAL_HEIGHT lines whose `equal` is
  not true; they are added to `disagreements`, and one or more makes `result` `FAIL` (a final NO-GO, as a critical read's).
- `components`: the record's object. `blocks`: `{"premine", "interval", "first_height", "last_height", "alternation_ok"}`
  (informational; no result reads it).
- `component_checks` (PR-2b, PR-2 decision 3): `{"monitor": M, "replay": R}`, each with `result` (`PASS`, `FAIL`, or
  `NOT_JUDGED` when the store was not built because the `H0_MINUS_1` / `FIRST` read disagreed: S14 is `FAIL` then) and `failed`
  (the codes that fail, in the order below), plus counts that no result reads. With the longest interval's first and last
  sample `monotonic_ns` [t_first, t_last] (no interval: the two window checks are not judged, and S13 is `FAIL`):

| Replay code (`replay_check()`) | Fails when |
|---|---|
| `REPLAY_BUILD` | `replay_build.json` is not `BUILT`, or its line names another `fixture`, `mode`, `network`, `node_settings_verification`, genesis (the environment's), challenge (`signet_challenge_hex`), `first_effective_height` (`h0`), `as_of_height` (`h0` − 1) or `as_of_block_hash_display` (the one agreeing `H0_MINUS_1` / `FIRST` read's hash) |
| `REPLAY_LABEL` | a `FOLLOWED` line's `fixture`, `mode`, `replay_kind`, `replay_label`, `network` or `node_settings_verification` is not the fixed value of section 4.7 |
| `REPLAY_CONTEXT` | a `FOLLOWED` line's `substrate_context_hash` or `deployment_id_internal` is not the build line's |
| `REPLAY_LAG` | an `INTERVAL` row of `blocks.jsonl` seen on both nodes at `seen_other_monotonic_ns` = s, t_first ≤ s and t_last − s > `live_window_seconds`, has no `FOLLOWED` row that ended at most `live_window_seconds` after s and whose `final_height` is at least its height (GOV072's live-evidence rule for the replay; exactly `live_window_seconds` passes) |
| `REPLAY_FINAL` | the last row of `blocks.jsonl` was seen on both nodes and the `FINAL` row is not one `FOLLOWED` row at that row's height and hash |
| `REPLAY_CONSISTENT` | two `FOLLOWED` rows name one `final_hash_display` with two `final_state_digest` values |

  Reported (`replay_check()`): `build`, `rows`, `results` (each result's count), `reorganized` (`sync_kind` `REORGANIZED`),
  `reanchored` (`replay_floor_reanchored` true; PR-2 decision 8: a rewrite at or under H0 already leaves S14 `INCOMPLETE`),
  `final_height`.

| Monitor code (`monitor_check()`) | Fails when |
|---|---|
| `MONITOR_LOG` | `final.json`'s `monitor.log` is not `COPIED`, or the log is over `LINES_LIMIT`, or the monitor tool's own `check_log()` gives `valid` false. Then nothing else is read |
| `MONITOR_STOP` | the last line is not STOP with `reason` `SIGNAL_SIGTERM` and `exit` 0 (the loop ran until `finish` stopped it) |
| `MONITOR_START` | START's `format` is not `docs/claude-track/formats/MONITOR_LOG_V1.md`, its `tool_sha256` not the SHA-256 of `tools/claude_track_monitor.py` in the reading checkout, its `bitagi_sha256` not the declaration's `bitagi_sha256`, its `bitagi_path`, `request_path`, `log_path` not `<work>/bin/bitagi`, `<work>/monitor/request.json`, `<work>/monitor/monitor.jsonl`, or its `poll_s` 120, `tick_timeout_s` 60, `max_ticks`, `ack_input`, `mark_input` null are not so |
| `MONITOR_REQUEST` | `monitor/request.json` is absent, is not the line of `monitor_request()` of this attempt (the environment's genesis, the build line's deployment id, `h0`), or its SHA-256 is not START's `request_sha256` |
| `MONITOR_SPAN` | with P = [t_first, each checked TICK's `mono_ns` inside [t_first, t_last], t_last], two consecutive values of P lie more than 300 s apart (a checked TICK has `tick_error` null; exactly 300 s passes) |
| `MONITOR_ALARM_OUTPUT` | no TICK is checked, or a checked TICK's `tick.alarms` ids are not exactly the twelve `AL-0a`, `AL-0b`, `AL-1` … `AL-10` |
| `MONITOR_COUNTDOWN_OUTPUT` | no TICK is checked, or a checked TICK's `countdown_status` is not `HEART_NOT_CURRENT` or `MEASURED` (PR-2 decision 5: without a Heart it is `HEART_NOT_CURRENT`, which counts as countdown output) |
| `MONITOR_CRITICAL_HEIGHTS` | the log does not hold exactly one CRITICAL_HEIGHT line for each of 0, `h0` − 1 and `h0` and no other, or a line's `hash_a_display` is not the hash of the one `FIRST` read of that kind |

  Reported (`monitor_check()`): `lines`, `ticks`, `checked_ticks`, `failed_ticks`, `alarm_starts` (count per `alarm_id`),
  `gaps_at_seq`, `suspends_at_seq`, `clock_steps_at_seq` (`check_log`'s, each cut to its first 1,000), `open_alarms` (STOP's
  count), `unequal` (the CRITICAL_HEIGHT lines added to S14, above). This is P5:344 ("감시기: P5-002 동안 countdown과 경보 출력이
  있다"), which FBO :157 reads as alarm output existing; `B_detect` is not measured (no acknowledgement, no injected fault).

**A lost attempt.** In the hosted report a counted attempt whose declaration and marker are valid and whose records are
missing, expired or invalid (the conditions of `EVIDENCE_MISSING` below) is not unreadable: its row is `{"attempt",
"run_id", "run_attempt", "created_at", "started_at", "start_time_utc", "runner_labels", "state": "LOST", "scaling", "s13":
{"result": "FAIL", "reason": "RECORDS_LOST", "required_seconds"}, "s14": {"result": "UNKNOWN"}, "checkpoints_read",
"checkpoint_s14_disagreements"}`. `checkpoints_read` lists the indices k (1..26) whose `p5002-checkpoint-<k>` artifact
holds a valid `checkpoint-<k>.json` (one canonical line of section 4.6's schema; its `run_id`, `attempt` and `index` are
not compared here, so that no count is passed over), and `checkpoint_s14_disagreements` is the largest
`s14_disagreements` over those files (null when there is none). The earlier causes of the table (`DECLARATION_REFUSED`, `REGISTRATION_MISMATCH`,
`LABELS_REFUSED`) and the later ones (`COMPLETENESS_REFUSED`; `COMPONENTS_NOT_WIRED` while the checker's `NOT_WIRED` is
not empty) come first: an attempt is `LOST` only when its records are the one thing missing.

A counted attempt that cannot be read is `{"attempt", "run_id", "state": "UNREADABLE", "cause"}` (`attempt` is null for a
run whose name is not a run name of this workflow); the causes are closed:

| Cause | When |
|---|---|
| `DECLARATION_REFUSED` | the declaration or marker artifact is missing or invalid, or is not this run's (`run_id`, `run_attempt` 1, `head_sha`, `mode`, `attempt`); CONFIRMATORY: its `constants` are not the registered ones. When no other cause holds: the declaration artifact's `created_at` is later than the observe job's `started_at` (the plan job uploads it before that job starts), or, for the run the report job belongs to, its `source_sha256` is not `--source-sha256` |
| `REGISTRATION_MISMATCH` | the declaration or the marker names another `registration_sha256` than the dispatch |
| `LABELS_REFUSED` | section 1, over the declaration, the marker, every checkpoint, the eleven members and the monitor's two files |
| `EVIDENCE_MISSING` | Never a cause in the hosted report: there the attempt is `LOST` (above), and the code is the `report` line's for an EXPLORATORY attempt that is `LOST`. For `attempt` (a local read, which names it `RECORD_INVALID`) and as the condition of `LOST`: the `p5002-records` artifact is missing or expired, or one of its eleven members (the records list of section 4 without the marker, the checkpoints, the three folders and the monitor's files) is missing, over its limit, not canonical, or fails its schema or the hash chain; or `final.json`'s `run_id` and `attempt` are not the declaration's, or its `samples` and `head_sha256` do not describe the `samples.jsonl` read. Bytes after the last newline of `samples.jsonl`, `blocks.jsonl` or `critical_heights.jsonl` (a line a killed writer left unfinished) are not a line and are not read, as on the VPS |
| `COMPLETENESS_REFUSED` | the observe job is not in the attempt-1 jobs listing or has no `started_at`; an EXPLORATORY dispatch that never started; a refused coverage (section 8.3: every dispatch that started is then listed with this cause, no record is read, and the report's `coverage` names the code) |
| `COMPONENTS_NOT_WIRED` | CONFIRMATORY and a component is not `WIRED` |

### 8.2 Collection report and verdict

`{"format", "mode", "registration_sha256", "head_sha", "labels", "transferability", "scope_b", "s14_not_covered", "constants",
"attempts", "never_started", "verdict", "coverage", "capture_list", "environment", "hosted_limits"}`, canonical JSON.

- `attempts`: every counted attempt in attempt order, read, lost or unreadable (T-5002 `:15`: no attempt is erased). `never_started`:
  `[{"run_id", "attempt", "created_at", "state": "NEVER_STARTED", "run_name_recognized", "s14_disagreements"}]`;
  `s14_disagreements` is the number of critical reads with `agree` false in that run's uploaded records (section 8.3), or
  null when it uploaded none, when they hold no readable `critical_heights.jsonl`, or when the coverage is refused.
- `coverage` (A decision 5): `OK`, or the code that refused the coverage of section 8.3: `OTHER_RUN_IN_PROGRESS`,
  `RUN_LIST_GAP`, `RUN_LIST_TITLE`, `MARKER_MISSING`, `ATTEMPT_OTHER_COMMIT`, `ATTEMPT_GAP`, `ATTEMPT_OVERLAP` or
  `ATTEMPTS_EXHAUSTED` (the checker's `COVERAGE_CODES`; the first that holds, in section 8.3's order). The reason a coverage was refused is read from
  the report itself.
- `constants`: `registered_constants()` (CONFIRMATORY) or the declaration's (EXPLORATORY; null when unreadable).
- `capture_list` (045b `:1033`): `{"tx_hex": "NOT_APPLICABLE_SCOPE_B", "tx_times": "NOT_APPLICABLE_SCOPE_B", "reserve_snapshots":
  "NOT_APPLICABLE_SCOPE_B", "block_times": "RECORDED", "outage_intervals": "RECORDED", "monitor_logs": "RECORDED",
  "fleet_scale": "NOT_MEASURED"}` (`monitor_logs` is `NOT_WIRED_PENDING_UNIT` while the checker's `NOT_WIRED` names the monitor:
  never since PR-2b).
- `environment`: `{"host": "SELF_HOSTED_VPS", "cr21": "FD-CT-92 item 15 (2026-10-27)", "node_versions", "same_host_nodes": true,
  "runner_labels"}`. `hosted_limits`: section 11's list.

`verdict` is null for EXPLORATORY. CONFIRMATORY: `{"expected", "observed", "result", "reason"}`, with `expected` = `{"s13":
"LONGEST_QUALIFYING_INTERVAL_GE_REQUIRED_SECONDS", "required_seconds", "s14": "CRITICAL_HEIGHT_DISAGREEMENTS_EQ_0",
"components": "ALL_WIRED_AND_CHECKED", "max_attempts", "stitching": "NONE_EACH_ATTEMPT_ALONE"}` and `observed` =
`{"counted_attempts", "s13", "s14"` (each attempt's result in order: `FAIL` and `UNKNOWN` for a lost one, null for an
unreadable one)`, "components"` (each attempt's `{"monitor", "replay"}` component check results in order, null for a lost or
unreadable one)`, "s14_disagreements", "passing_attempt", "lost_attempts"` (the attempt numbers whose state is `LOST`)`}`. The
first rule that holds decides:

1. A read attempt has S14 `FAIL`, or a `LOST` attempt has `checkpoint_s14_disagreements` ≥ 1, or a never-started
   dispatch has `s14_disagreements` ≥ 1: `FAIL`, reason `NO_GO_S14_DISAGREEMENT`. It is final (A Q5).
   `observed.s14_disagreements` counts all three.
2. An attempt is unreadable, or `coverage` is not `OK`: `INCONCLUSIVE`, reason the first unreadable attempt's cause
   (`COMPLETENESS_REFUSED` for a refused coverage with no counted dispatch).
3. A read attempt has S13 `PASS`, S14 `PASS` and both component checks `PASS` (PR-2 decision 3): `PASS`, `passing_attempt`
   the first such, reason null. `observed.lost_attempts` names every lost attempt beside it.
4. `max_attempts` attempts are counted: `FAIL`, reason `ATTEMPTS_EXHAUSTED`. A `LOST` attempt is counted.
5. Otherwise `OPEN`: a retry comes only after A records the investigated cause (A Q5; T-5002 `:15`). The reason is
   `COMPONENT_CHECK_FAILED` when a read attempt has S13 `PASS` and S14 `PASS` and a component check that is not `PASS`
   (the attempt counts toward `max_attempts`), else `S14_INCOMPLETE` when a read attempt has S13 `PASS` and S14
   `INCOMPLETE` (S13 was met; the agreement was not recorded), else `S13_NOT_YET_PASSED`.

**What a lost attempt leaves open.** A lost records artifact (a host reboot, a dead runner, a job timeout, a failed
upload) does not end the registration: the attempt is `LOST`, it fails S13, it counts as one of the `max_attempts`, and a
later attempt can still pass. Its S14 is not known after its last checkpoint: the critical reads made after the last
file of `checkpoints_read` (the three `FINAL` reads among them), and every read when no checkpoint was uploaded, are in
no record the report has. A disagreement a checkpoint did count is final (rule 1); one made after the last checkpoint
is not seen, and a `PASS` under rule 3 says so by naming the attempt in `lost_attempts`. So A records the investigated
cause of a lost attempt before a retry is dispatched (T-5002 `:15`); `continuity` does not refuse that retry. Rule 2
stays strict for every other cause: an attempt that is `UNREADABLE` makes the verdict `INCONCLUSIVE` in every later
report of that registration, and `continuity` refuses a retry after an attempt it can see to be unreadable
(`EARLIER_ATTEMPT_UNREADABLE`, section 8.3), so that no further 26-hour attempt is spent on a verdict that can no
longer change.

### 8.3 Completeness: the dispatch listing

As XD-1 V3 section 7, with attempts for sessions. The plan and report jobs save this workflow's `workflow_dispatch` listing
(`<listing>/runs-<p>.json`, 100 per page, fewer than 1,000 runs) and, per run read, `<attempts>/<run_id>/artifacts.json`,
`jobs.json` (attempt 1) and the zips `downloads` names (`declaration.zip`, `marker.zip`, `checkpoint-<k>.zip`, `records.zip`),
with GET requests only. Each zip's SHA-256 must be its listed digest (`ARTIFACT_DIGEST`); only the named members are read.
A listing item whose `digest` is null is read with no digest check, as XD-1's tool reads it (whether the API lists a digest
for every artifact of this workflow is not known before the first pilot). The plan job saves `artifacts.json` and
`jobs.json` of each earlier run and one zip only: the `records.zip` of an earlier run without the marker.

- CONFIRMATORY reads the runs named CONFIRMATORY with this registration, and every run whose name is not a run name of this
  workflow (it must not have started: `RUN_LIST_TITLE`). EXPLORATORY reads its own run only. Every other run of the workflow
  must be completed (`OTHER_RUN_IN_PROGRESS`).
- **No run number is missing** (CONFIRMATORY; `RUN_LIST_GAP`). Each listed run carries its `run_number` (a positive
  integer, no two alike: `RUN_LIST_SHAPE`). Let f be the lowest `run_number` among the listed runs named CONFIRMATORY
  with this registration and c the `run_number` of the run the command belongs to. Every integer from f to c must be
  the `run_number` of a listed run, whatever that run's mode, registration or name. The workflow has one trigger,
  `workflow_dispatch`, and GitHub numbers the runs of one workflow in one sequence, so an EXPLORATORY run, a run of
  another registration and a run with another name each fill their own number, and a run that was deleted inside the
  range leaves a number that no listed run has. A second attempt of the same run keeps its number. The rule holds
  when the listing names no such run or c is below f. It is not applied to an EXPLORATORY command, which reads its own
  run only. A run of this workflow file started by another event (possible only from a branch that changed the trigger)
  would take a number and be in no dispatch listing: it reads as a gap. The refusal does not lift: while a
  registration is open, deleting any run of this workflow inside the range, a refused or EXPLORATORY one included,
  refuses the coverage of that registration in every later report.
- An attempt is **counted** when its run lists `p5002-started`. A run that does not list it is `NEVER_STARTED` (listed, not
  counted, its attempt number free again) only when nothing else shows a start: it lists no `p5002-checkpoint-<k>` artifact
  (the workflow uploads one only after the marker's upload succeeded), its `p5002-records` artifact, when it lists an
  unexpired one, holds no member `marker.json` (`start` writes that file last, at S8, so records that hold it are an
  attempt the driver started), and its attempt-1 jobs listing shows no step `Upload the marker` of the observe job that
  concluded `success` (the checker's `MARKER_STEP_NAME`). With any of the three signs the marker artifact is missing
  although the attempt started (it was deleted, or its upload failed after `start` had ended): `MARKER_MISSING`. The run
  stays a dispatch that started and its attempt number is not free. A `p5002-records` artifact alone is not such a
  sign: the records upload runs always, so a `start` that ended before S8 leaves records too, and those are read as
  the last item of this list says. An expired marker refuses the command (`ARTIFACT_EXPIRED`).
- The counted attempts, in creation order, must be attempts 1, 2, …, k at this commit (`ATTEMPT_OTHER_COMMIT`, `ATTEMPT_GAP`,
  `ATTEMPT_OVERLAP`). `continuity` also needs this run's name to be its inputs (`RUN_NAME`), k < `max_attempts`
  (`ATTEMPTS_EXHAUSTED`), this attempt = k + 1 (`ATTEMPT_NOT_NEXT`), and every counted attempt to list an unexpired
  `p5002-declaration` (`EARLIER_ATTEMPT_UNREADABLE`: section 8.2's rule 2; the plan job saves no zip of a counted run, so
  this is the one unreadable cause `continuity` can see). A counted attempt without an unexpired `p5002-records` is not
  refused: it is `LOST` in the report and is one of the k. `continuity` refuses with the first code that holds, in the
  order `OTHER_RUN_IN_PROGRESS`, `RUN_NAME`, `RUN_LIST_GAP`, `RUN_LIST_TITLE`, `MARKER_MISSING`, the three of this item,
  `ATTEMPTS_EXHAUSTED`, `ATTEMPT_NOT_NEXT`, `EARLIER_ATTEMPT_UNREADABLE`.
- `report` refuses none of the eight coverage codes: it writes the report with `coverage` set to the first that holds
  (`OTHER_RUN_IN_PROGRESS`, `RUN_LIST_GAP`, `RUN_LIST_TITLE`, `MARKER_MISSING`, then the three of the item above in
  creation order, then `ATTEMPTS_EXHAUSTED` for more counted attempts than `max_attempts`), every dispatch that started
  listed `COMPLETENESS_REFUSED`, and no record read: the one thing looked at is whether a run without the marker holds
  `marker.json` in its records, which decides whether it started.
- A dispatch that never started may still have read a critical height: `start` reads height 0 and H0 − 1 before the
  marker, and the records upload runs always. When a never-started run lists an unexpired `p5002-records`, `report` reads
  that zip's `critical_heights.jsonl` (complete lines, section 4.5's schema) and counts its rows with `agree` false as that
  entry's `s14_disagreements`; a disagreement there is as final as one of a counted attempt (section 8.2, rule 1). Nothing
  else of such a run is read. Under a refused coverage that file is not read either (the count is null), so the verdict
  is `INCONCLUSIVE` until the coverage is clean; a never-started run whose records artifact is missing or expired adds
  nothing to the verdict.
- **What a deleted run still hides.** A run that was deleted whole is in no listing. Inside the range of the run number
  rule its number is missed (`RUN_LIST_GAP`). Outside it nothing shows. That is a run deleted before the first listed
  CONFIRMATORY run of the registration (that first run itself, when it was the one deleted: the range then begins at
  the next), and a run deleted together with every run after it: the range of a report made for an earlier run ends
  before the deleted numbers, and a later dispatch shows the gap only if GitHub does not give a freed number to the
  next run, which was not verified. An EXPLORATORY command reads its own run only, so no run number is compared
  for it (section 11, item 7).
- The report artifact is the hosted report job's own. `report` refuses (`REPORT_ARTIFACT_PRESENT`) when this run's listing
  already holds a `p5002-report-attempt-<n>` with n ≥ `--run-attempt`: no report job of this run attempt or a later one has
  uploaded yet, so another holder of the job's runtime token did. The report job's upload replaces an artifact of its own
  name.

## 9. Observation list

`BITAGI_CT_OBSERVATION_LIST_V1`, the shape `tools/ct_preregistration_receipt.py` reads: one entry per counted attempt, in attempt
order, `{"observation_id": "OBS-0<attempt:07>", "registration_sha256", "start_time_utc"}` (attempt 1 is `OBS-00000001`), the
start being the observe job's server `started_at` in integer seconds (A Q8). The prefix 0 keeps the ids apart from ARDR's 1..8
and XD-1's 9. `report` writes it for CONFIRMATORY whenever an attempt is counted, none is unreadable and `coverage` is `OK`,
so after each attempt it lists every observation made so far; a `LOST` attempt is counted and has its entry. The receipt check's result stays `STRUCTURE_PASS_OBSERVATIONS_UNVERIFIED`.

## 10. The registration block, the plan checks and the refusal codes

The plan job reads the registration as merged on main (`refs/remotes/origin/main:<path>`, at most 1 MiB):

```json
{"p5002": {"pinned_commit": "<40 hex>", "tool_sha256": {"<path>": "<64 hex>"},
           "constants": {"<name>": "<value>"}, "fixed_lines": {"scope_b": "<line>", "s14_not_covered": "<line>"}}}
```

The block's key set is closed, and other keys of the registration are not read here. `tool_sha256` names exactly
`REGISTERED_PATHS` (fourteen paths since PR-2b, PR-2 decision 9; seven before), in this order: the three tools,
`tools/claude_track_exit.py`, `docs/policy/ACTIVE_VALIDATION_POLICY.json` (the file `required_seconds()` reads),
`.github/workflows/claude-track-p5002.yml`, `tools/claude_track_monitor.py` (it runs on the VPS and its START line hashes
itself), `docs/claude-track/formats/MONITOR_LOG_V1.md` (its format, pinned by follow-up registration 2),
`crates/bitagi-cli/examples/test_only_signet_store_fixture.rs`, `crates/bitagi-cli/src/monitor_tick.rs`,
`crates/bitagi-cli/src/monitor_alarms.rs` (the two binaries' entry points), `Cargo.lock`, `rust-toolchain.toml` (the
dependency versions and the compiler) and this document. Everything else the binaries contain is fixed by plan check 7 (the
head is the pinned commit) and by the S04 citation; each file's hash is a readable redundancy. Until B's fixture and the
-2c-1 tick are on main, the three `crates/` files are absent and a registered plan refuses `REGISTERED_FILE_MISSING`. No
module of the Codex ledger is registered, because none is imported (CR-01). `constants` equals
`registered_constants()`: the unscaled effective constants plus `node_versions` and `bitcoind_sha256` (each `{"a", "b"}`).
`fixed_lines` equals section 1's two lines.

**The tag-path TEST_ONLY pilot** (PR-2a; XD-1's C2). An EXPLORATORY dispatch from an attempt tag is the pilot: its
registration input is exactly `PILOT_REGISTRATION` = `tests/fixtures/p5002/P5002_PILOT_REGISTRATION_TEST_ONLY.json`, with that
file's SHA-256 and an S04 run id. The file is `{"label": PILOT_LABEL, "note": PILOT_NOTE, "p5002": <the block above>}`, with
`PILOT_LABEL` = `P5002_PILOT_REGISTRATION_TEST_ONLY_NEVER_A_REGISTRATION`; `pilot-registration --commit SHA` writes it (section
3), and A commits it on main after that commit, then tags the commit. The pilot runs checks 6 to 9 in full against it (main's
first-parent chain, the file as merged on main, the pinned commit, the tool hashes, the constants, the fixed lines, the S04
citation), so the read path a registered attempt takes is exercised on GitHub before the first counted attempt. Overrides
are allowed (`EXPLORATORY_SCALED`). The pilot is labelled and recorded EXPLORATORY: its declaration names no registration, its
run name says `registration none`, and its records count for nothing. A CONFIRMATORY plan refuses the file by its path
(`REGISTRATION_TEST_ONLY`, check 5, as any path under `tests/`) and any registration that holds `PILOT_LABEL` (check 7). Since
PR-2b the pilot hashes the fourteen paths, as a registered attempt does.

**Plan checks**, in this order; the first that fails refuses:

1. `EVENT`, `RERUN`, `GITHUB_IDS`, `EXPECTED_HEAD`: a `workflow_dispatch`, `GITHUB_RUN_ATTEMPT` = 1, well-formed `GITHUB_RUN_ID`
   and `GITHUB_SHA`, `GITHUB_SHA` = `--expected-head`.
2. `MODE`, `ATTEMPT_RANGE` (section 4.1), `SOURCE_SHA256`, `BINARIES_SHA256` (PR-2b: the build job's three hashes, each 64
   hex), `POLICY_UNAVAILABLE` (`required_seconds()`: the policy file of section 2, read with no Codex ledger file).
3. EXPLORATORY: `REF` (`GITHUB_REF` is `refs/heads/main` or an `ATTEMPT_TAG` ref). From main: `EXPLORATORY_INPUTS` (a
   registration, its hash or an S04 run id was passed), `OVERRIDE_RANGE`, then step 10. From an attempt tag (the TEST_ONLY
   pilot): `PILOT_REGISTRATION` (the registration is not exactly `PILOT_REGISTRATION`, or its hash or the S04 run id is
   missing or malformed), `OVERRIDE_RANGE`, then steps 6 to 10.
4. CONFIRMATORY: `OVERRIDE_REFUSED`; then `COMPONENTS_NOT_WIRED` while `NOT_WIRED` is not empty (empty since PR-2b: the code
   stays, dormant); then `S04_CITATION_NOT_WIRED` while `PLAN_CHECKS_NOT_WIRED` is not empty (empty since PR-2a: the code stays,
   dormant).
5. `REF` (`ATTEMPT_TAG`), `REGISTRATION_INPUTS`, `REGISTRATION_PATH` (canonical, as XD-1 V3 section 8),
   `REGISTRATION_TEST_ONLY` (any path under `tests/`, `PILOT_REGISTRATION` among them).
6. `MAIN_UNAVAILABLE`, `NOT_ON_MAIN` (the head is on main's first-parent chain).
7. `REGISTRATION_NOT_ON_MAIN`, `REGISTRATION_SIZE`, `REGISTRATION_SHA256_MISMATCH`; then the pilot's label: CONFIRMATORY
   `REGISTRATION_TEST_ONLY` when the bytes hold `PILOT_LABEL`, the pilot `PILOT_REGISTRATION_LABEL` when they do not;
   `REGISTRATION_JSON`; the pilot `PILOT_REGISTRATION_LABEL` when its `label` is not `PILOT_LABEL`; `REGISTRATION_P5002` (the
   block), `NOT_THE_PINNED_COMMIT`.
8. `REGISTERED_FILE_MISSING`, `TOOL_SHA256_MISMATCH` (each file of this checkout), `REGISTRATION_CONSTANTS`,
   `REGISTRATION_FIXED_LINES`.
9. The S04 citation (PR-2a; STEP-48; A's Q10 and Q15: the rule of `tools/claude_track_ardr_slices.py` copied, no ARDR module
   and no `tools/common.py` imported), from the files the step "Read the cited S04 run" saved in `--s04-dir`; no request is
   made here. `S04_INPUT_MISSING` (no `--s04-dir`, or `run.json` absent or over `FETCHED_LIMIT`). The run, from `run.json`:
   `S04_RUN_ID` (its `id` is not the input, or the file is not a JSON object), `S04_RUN_WORKFLOW` (its `path` is not
   `.github/workflows/claude-track-rx02.yml`; the display name is never read), `S04_RUN_EVENT` (not `push`), `S04_RUN_BRANCH`
   (`head_branch` not `main`), `S04_RUN_NOT_SUCCESS` (not `completed` with the conclusion `success`), `S04_RUN_ATTEMPT` (not an
   integer 1..999), `S04_RUN_HEAD` (not 40 hex), `S04_NOT_ON_PINNED_HISTORY` (the run's head is not on the pinned commit's
   first-parent history, ancestor or equal: `git rev-list --first-parent <head>`). The record's source: `artifacts.json` (absent:
   `S04_INPUT_MISSING`), the run's artifact listing filtered by the name `s04-record-v2-<run id>-<attempt>`:
   `S04_ARTIFACT_LISTING` when it is not one page of that name only, lists it twice, or gives a listed, unexpired artifact no
   positive integer id. The artifact wins: when it is listed and its `expired` is false, `record.zip` is the record
   (`S04_RECORD_MISSING` when that zip was not saved, never a fallback; `S04_ARTIFACT_ZIP` when the zip is over 1 MiB, not a zip,
   or holds anything but the one member `s04_record_v2.json` of at most 1 MiB) and no log is read. Only an artifact that is not
   listed or has expired falls back to the record job: `jobs.json` (absent: `S04_INPUT_MISSING`), that run attempt's jobs
   listing, in which every job is of that run attempt and named once and the job
   `S04 record v2 (leg set s04-legs-v1, this run only)` is listed with a positive integer id (`S04_JOB_NOT_LISTED`); then
   `job.log`, at most 16 MiB, in which exactly one line printed after the runner's timestamp is a JSON object of the record's
   schema (`S04_JOB_LOG_AMBIGUOUS` for two or more) and the next printed line is its `sha256sum` line naming
   `s04_record_v2.json` with the SHA-256 of that line and its newline (`S04_RECORD_MISSING` for no record, no such hash line, or
   no `job.log`). Then the record, by `s04_citation`: `S04_RECORD_JSON` (not UTF-8 JSON with no duplicate key),
   `S04_RECORD_SCHEMA` (no object of `bitagi.claude_track.s04_record.v2`, or `subject_oids` not 1..4,096 subjects of 40 hex),
   `S04_NOT_PASS` (`s04` is not `PASS_CLASS_T`), `S04_RECORD_COMMIT` (its `commit` is not the run's head), `S04_RECORD_RUN` (its
   `run` is not that push of `refs/heads/main`, run id, run attempt and commit), `S04_SUBJECTS_CHANGED` (a subject's object
   id is not the pinned commit's, `git rev-parse --verify --quiet <head>:<path>`; no subject's bytes are read). The
   declaration's `s04_citation` is the result (section 4.1). On GitHub the step's three confirm commands make the run, listing
   and job parts of this check on each answer before the next request, so a refusal of those parts can show there first.
10. The declaration is written (`OUTPUT_EXISTS`).

**Refusal codes** (closed; `REFUSALS` maps each to its exit code):

| Exit | Tool | Codes |
|---|---|---|
| 6 | all | `OPTIMIZED_PYTHON` |
| 6 | `plan` | `EVENT`, `RERUN`, `EXPECTED_HEAD`, `REF`, `OVERRIDE_REFUSED`, `COMPONENTS_NOT_WIRED`, `S04_CITATION_NOT_WIRED`, `REGISTRATION_TEST_ONLY`, `NOT_ON_MAIN`, `REGISTRATION_SHA256_MISMATCH`, `NOT_THE_PINNED_COMMIT`, `TOOL_SHA256_MISMATCH`, `REGISTRATION_CONSTANTS`, `REGISTRATION_FIXED_LINES` |
| 6 | `plan` (PR-2a), `pilot-registration` | `PILOT_REGISTRATION`, `PILOT_REGISTRATION_LABEL`, `S04_RUN_ID`, `S04_RUN_WORKFLOW`, `S04_RUN_EVENT`, `S04_RUN_BRANCH`, `S04_RUN_NOT_SUCCESS`, `S04_RUN_ATTEMPT`, `S04_RUN_HEAD`, `S04_NOT_ON_PINNED_HISTORY`, `S04_ARTIFACT_LISTING`, `S04_ARTIFACT_ZIP`, `S04_JOB_NOT_LISTED`, `S04_JOB_LOG_AMBIGUOUS`, `S04_RECORD_JSON`, `S04_RECORD_SCHEMA`, `S04_NOT_PASS`, `S04_RECORD_COMMIT`, `S04_RECORD_RUN`, `S04_SUBJECTS_CHANGED` |
| 6 | driver | `DECLARATION_OTHER_RUN`, `SOURCE_MISMATCH`, `UNSUPPORTED_SIGNET_CONTEXT`, `BINARY_MISMATCH` |
| 6 | confirm | `OTHER_RUN_IN_PROGRESS`, `RUN_NAME`, `RUN_LIST_GAP`, `RUN_LIST_TITLE`, `MARKER_MISSING`, `ATTEMPT_GAP`, `ATTEMPT_OVERLAP`, `ATTEMPT_OTHER_COMMIT`, `ATTEMPT_NOT_NEXT`, `ATTEMPTS_EXHAUSTED`, `EARLIER_ATTEMPT_UNREADABLE`, `ARTIFACT_EXPIRED`, `ARTIFACT_DIGEST`, `REPORT_ARTIFACT_PRESENT` |
| 5 | driver | `MAINNET_REFUSED`, `CREDENTIAL_MATERIAL` |
| 5 | all | `PATH_NOT_REGULAR` (an input or output path is a link or not a regular file) |
| 4 | all | `INTERNAL_ERROR` (`result` `INTERNAL`) |
| 3 | `plan` | `GITHUB_IDS`, `MAIN_UNAVAILABLE`, `GIT_UNAVAILABLE`, `REGISTERED_FILE_MISSING`, `POLICY_UNAVAILABLE`, `S04_RECORD_MISSING`, `S04_INPUT_MISSING` |
| 3 | `attempt`, driver | `DECLARATION_MISSING`, `RECORDS_MISSING`, `NODE_BINARY_MISSING`, `NODE_NOT_READY`, `PEERS_NOT_CONNECTED`, `PREMINE_FAILED`, `DAEMON_NOT_STARTED`, `DAEMON_STATE_MISSING` |
| 3 | driver (PR-2b) | `TOOL_BINARY_MISSING`, `REPLAY_BUILD_FAILED`, `MONITOR_NOT_STARTED` |
| 3 | confirm | `RUN_LIST_MISSING`, `RUN_LIST_JSON`, `THIS_RUN_NOT_LISTED`, `ARTIFACT_LISTING`, `ARTIFACT_ZIP`, `JOBS_LISTING`, `INPUT_MISSING` |
| 2 | `plan` | `MODE`, `ATTEMPT_RANGE`, `SOURCE_SHA256`, `EXPLORATORY_INPUTS`, `OVERRIDE_RANGE`, `REGISTRATION_INPUTS`, `REGISTRATION_PATH`, `REGISTRATION_NOT_ON_MAIN`, `REGISTRATION_SIZE`, `REGISTRATION_JSON`, `REGISTRATION_P5002`, `BINARIES_SHA256` |
| 2 | `attempt`, driver | `DECLARATION_INVALID`, `RECORD_INVALID`, `CHECKPOINT_INDEX` (K outside 1..26), `LEFTOVER_PROCESS` |
| 2 | confirm | `RUN_LIST_SHAPE`, `RUN_LIST_CHANGED`, `RUN_LIST_CAPPED`, `HEAD_SHA`, `CONTINUITY_INPUTS`, and the six causes of section 8.1 (`result` `INCONCLUSIVE`) |
| 2 | all | `OUTPUT_EXISTS` |

The confirm tool's `RUN_LIST_*`, `THIS_RUN_NOT_LISTED`, `ARTIFACT_LISTING`, `ARTIFACT_ZIP` and `JOBS_LISTING` mean what they mean
in `claude_track_xd1_confirm.py`. `INPUT_MISSING` is a saved file that is absent; `HEAD_SHA` and `CONTINUITY_INPUTS` are
malformed arguments; `GIT_UNAVAILABLE` is git failing; `RECORDS_MISSING`, `NODE_BINARY_MISSING` and `DAEMON_STATE_MISSING` are
an absent records directory, node binary and daemon state; `RECORD_INVALID` is a record that fails section 4.
`TOOL_BINARY_MISSING` and `BINARY_MISMATCH` are S1b's (a binary absent, a link or not executable; another SHA-256),
`REPLAY_BUILD_FAILED` is S5r's and `MONITOR_NOT_STARTED` S6m's; `CREDENTIAL_MATERIAL` also stands for a withheld monitor log or
`monitor.err`. A follow the fixture refuses is a row of `replay.jsonl`, never a refusal.
`COMPONENTS_NOT_WIRED` stands in two rows: `REFUSALS` holds the plan's exit 6, and a line whose `result` is `INCONCLUSIVE`
exits 2 for each of the six causes. The eight coverage codes are refusals of `continuity` only; `report` writes them as
`coverage` (section 8.3). `CONTINUITY_INPUTS` also covers `report`'s `--run-attempt` and `--source-sha256`. The three S04
commands of confirm refuse with the codes of plan check 9 their function raises (and `S04_INPUT_MISSING`, `GIT_UNAVAILABLE`,
`PATH_NOT_REGULAR`), and with `S04_RUN_ID`, `S04_RUN_ATTEMPT` or `HEAD_SHA` for a malformed argument. `pilot-registration`
refuses with `PILOT_REGISTRATION` (a commit that is not 40 hex), `MAIN_UNAVAILABLE`, `NOT_ON_MAIN`, `REGISTERED_FILE_MISSING`
(a registered path that is no file at that commit), `GIT_UNAVAILABLE`, `POLICY_UNAVAILABLE` and `OUTPUT_EXISTS`.

## 11. What hosted verification cannot see (CR-21 condition 4)

`HOSTED_LIMITS`, the report's `hosted_limits` list (exact strings):

1. `The final verification runs in the hosted report job of claude-track-p5002.yml, never on the VPS.`
2. `It checks: the dispatched commit and, for a registered attempt, the registration and tag binding; the tree hash named by the plan job; the sample hash chain; the continuity rules recomputed from the raw samples; the S14 recount from the raw reads; labels; every counted attempt; the replay rows and the monitor log against the run's own reads; and the server times of the marker and the checkpoint artifacts.`
3. `It can see: a job whose marker and checkpoints span less than the required seconds of GitHub server time; a missing, late or reordered checkpoint; a record that does not extend the checkpointed chain heads; a checkpoint whose committed sample is stale; sample clocks that do not follow server time from anchor to anchor; a VPS clock more than 300 s from server time at an anchor.`
4. `It cannot see whether node answers, block hashes, uptime values, process ids, monotonic clock values, replay outputs and monitor logs are real: a hostile VPS holding the job's runtime token could upload a self-consistent fabricated record at the right server times, and the samples between two checkpoints are committed only by the later one.`
5. `It cannot see whether the Signet blocks were made on the VPS by the two stated binaries, whether the VPS unpacked the tree it reports, or whether the VPS ran the binaries the hosted build job made.`
6. `Start and end are bound to GitHub job server times and to the registration receipts.`
7. `It cannot see a dispatch whose run was deleted, except that for a registered collection a run number missing between the first dispatch of the registration and the reporting run refuses the coverage. A run deleted before that first dispatch, or deleted together with every later run, leaves no gap: it is neither counted nor reported.`
8. `It cannot know S14 for an attempt whose records are lost: the attempt is reported LOST with the largest disagreement count of its valid checkpoint files, and its critical reads after its last checkpoint are not known. A retry follows only after A records the investigated cause.`
9. `Under a refused coverage it reads no record, a never-started run included, so the verdict is INCONCLUSIVE until the coverage is clean. A never-started run whose records artifact is missing or expired adds nothing to the verdict.`
10. `The replay is a configuration-unverified synthetic-context replay of blocks with no project transaction, and the monitor's B_detect is not measured: no acknowledgement and no injected fault.`

Items 4 and 5 are the tentative list of FD-CT-92 item 15 ("86,400 s continuous observation, Signet blocks made on the VPS";
BUNDLE `:336-339`). Replay and watcher outputs joined item 4 in PR-2b, and item 5 says the hosted report cannot see that the
VPS ran the hosted-built binaries; whether they fall inside that list is A's question to the Founder (STEP-11), not this
document's. Item 10 (PR-2b) is what the two components do not cover.

What the anchors bind, in short (section 7): each checkpoint of a running sampler commits a sample at most 480 s old on the
VPS's own clocks, those clocks are within 300 s of server time at the anchor, and between the bracketing anchors the
committed samples' monotonic time follows server time within 480 s. So a chain cannot be re-dated, replayed from an earlier
run or left uncommitted until the end; a whole-machine pause is bounded by 480 s over the longest interval, not excluded;
and each hour's samples can still be invented during that hour (item 4).

**The report's identity.** The observe job's runtime token can upload artifacts of this run under any name, and the hosted
report job cannot stop it from doing so before the report exists. So the collection report and the observation list are
identified by the two SHA-256 lines the hosted report job prints in its log (`sha256sum`, before each file's text), not by
an artifact name: a file fetched from `p5002-report-attempt-<n>` is compared with that line before it is used, in A's
record and before `tools/ct_preregistration_receipt.py` reads an observation list. The tool refuses when such an artifact
exists before the report job uploads (`REPORT_ARTIFACT_PRESENT`), the upload replaces an artifact of its own name, and a
declaration artifact that was replaced after the plan job is refused (section 8.1, `DECLARATION_REFUSED`); whether the
runtime token can delete an artifact was not tested.

## 12. Deferred to PR-2 or later

- Done in PR-2b (2026-11-16): the replay (B's TEST_ONLY Signet store fixture with `--follow`, labelled
  "configuration-unverified synthetic-context replay"; sections 3, 4.7, 8.1) and the monitor (the -2c tick and loop,
  `MONITOR_LOG_V1`, the `monitor/` folder; sections 3, 4.8, 8.1): their record files and checks; both components `WIRED`;
  `NOT_WIRED` emptied; `capture_list.monitor_logs` `RECORDED`; the hosted build job; the RPC auth line and F4's rule;
  `REGISTERED_PATHS` fourteen.
- Done in PR-2a (2026-11-16): the S04 citation as plan check 9 (section 10; `PLAN_CHECKS_NOT_WIRED` emptied, the declaration's
  `s04_citation`), and the TEST_ONLY pilot through the tag path (section 10; `pilot-registration`). The pilot file itself is
  A's, committed on main for a pilot commit; this document does not hold it.
- Not covered by the components (section 11, item 10): `B_detect` (no acknowledgement input, no injected fault, no mark: every
  episode is `UNMEASURED`); AL-1 to AL-7 `HEART_NOT_CURRENT` and AL-8 to AL-10 `NOT_MEASURED` under scope (b); the tick reads no
  replay store; the replay's node settings are unverified, its blocks carry no project transaction and the store itself is not
  uploaded (its SHA-256 is). A tick orphaned by a killed monitor is counted only by its executable's path.
- A `BROADCAST_LOCK_INCIDENT_V1` record for an S14 disagreement, written by A from `incidents/` and checked with
  `tools/claude_track_incident_v1.py` (that format refuses height 0, so a genesis disagreement needs A's decision).
- Later units: the `FOLLOW_UP_2` scope of `tools/claude_track_p5005_registration.py` and its evaluation policy. The raw
  evidence stays in Actions artifacts (90 days) with a summary in A's record (A Q13); a longer retention is A's to decide.

## 13. Module API (`tools/claude_track_p5002_check.py`)

The driver and the hosted tool use exactly these names; nothing else of the checker is an interface. `required` is
`required_seconds()`'s value in a hosted job and the declaration's `constants["required_seconds"]` on the VPS: only `plan`
and the hosted `report` call `required_seconds()` (`report` for CONFIRMATORY, also through `attempt_row` when `listed` is
given). `continuity` and `report` take the attempt limit from `MAX_ATTEMPTS`, not from the policy (A decision 1). A failed
check raises `Refusal` with the code shown.

```python
# constants (values in sections 1, 2, 4, 8, 10, 11)
FORMAT_DECLARATION, FORMAT_ENVIRONMENT, FORMAT_MARKER, FORMAT_CHECKPOINT, FORMAT_FINAL, FORMAT_COMPONENTS, FORMAT_SCOPE_FILE
FORMAT_DISAGREEMENT, FORMAT_REPORT, OBSERVATION_SCHEMA, OBSERVATION_PREFIX                           # prefix 0
MODES; LABELS: dict[str, tuple[str, ...]]; SCALED_LABEL; FORBIDDEN: dict[str, tuple[bytes, ...]]
TRANSFERABILITY; SCOPE_B; S14_NOT_COVERED; HOSTED_LIMITS: tuple[str, ...]; ZERO_HASH                 # '0' * 64
NODES = ('a', 'b'); NODE_NAMES; NODE_VERSIONS; BITCOIND_SHA256; PORTS; PREMINE_CHUNK; RPC_SECONDS
COMPONENTS = ('monitor', 'replay'); NOT_WIRED; NOT_WIRED_STATE; WIRED_STATE   # NOT_WIRED: () since PR-2b
PLAN_CHECKS_NOT_WIRED                                                          # () since PR-2a
ATTEMPT_TAG; TITLE                     # re.Pattern: the tag ref; the run name, groups (mode, attempt, registration)
REGISTERED_PATHS; WORKFLOW_PATH; OBSERVE_JOB_NAME; MARKER_STEP_NAME    # 'P5-002 observe (VPS)'; 'Upload the marker'
POLICY_PATH; POLICY_SHA256; POLICY_SIGNET  # section 2: the policy file required_seconds() reads, its pin, its `signet`
PILOT_REGISTRATION; PILOT_LABEL            # section 10: the tag-path TEST_ONLY pilot's file and the label it carries
S04_WORKFLOW_PATH; S04_JOB_NAME; S04_SOURCES   # section 10, check 9: the cited run's workflow, its record job, the sources
ARTIFACTS: dict[str, str]  # stem -> name: declaration, source, binaries ('p5002-bin'), marker ('p5002-started'),
                           # checkpoint (the prefix), records
MEMBERS: tuple[str, ...]   # the eleven members of p5002-records the report reads
MONITOR_FILES              # ('monitor/request.json', 'monitor/monitor.jsonl'): read, not members (section 4.8)
BINARY_NAMES               # {'bitagi': 'bitagi', 'fixture': 'test_only_signet_store_fixture'} (S1b, the build job)
FORMAT_REPLAY_BUILD; REPLAY_LABEL          # section 4.7: replay_build.json's format and its fixed label
MONITOR_POLL_SECONDS; MONITOR_TICK_TIMEOUT_SECONDS; MONITOR_STOPS    # 120; 60; the STOP reasons of MONITOR_LOG_V1
SMALL_LIMIT; LINES_LIMIT; ZIP_LIMIT; FETCHED_LIMIT; MAX_OBSERVATION_SECONDS; MAX_CHECKPOINTS; BREAK_KINDS; UNREADABLE_CAUSES
MAX_ATTEMPTS = 3; MAX_SAMPLES; COVERAGE_OK = 'OK'; COVERAGE_CODES: tuple[str, ...]      # section 8.2's `coverage`
EXIT_OK, EXIT_VALIDATION, EXIT_UNAVAILABLE, EXIT_INTERNAL, EXIT_SECURITY, EXIT_REFUSAL = 0, 2, 3, 4, 5, 6
REFUSALS: dict[str, int]

class Refusal(Exception):        # Refusal(code); .code, .exit_code = REFUSALS[code]
class Unreadable(Exception):     # Unreadable(cause); .cause in UNREADABLE_CAUSES

def output_line(tool: str, command: str, result: str, exit_code: int, code: str | None = None, **keys) -> bytes  # section 3;
    # keys on DONE, and `coverage` alone on an INCONCLUSIVE line
def required_seconds(root: Path | None = None) -> int     # POLICY_UNAVAILABLE; reads POLICY_PATH of root only (section 2)
def effective_constants(overrides: dict[str, int] | None, required: int) -> dict       # OVERRIDE_RANGE
def registered_constants(required: int) -> dict
def labels_for(mode: str, scaled: bool) -> list[str]
def canonical(value) -> bytes                                      # no newline
def line(value: dict) -> bytes                                     # canonical(value) + b'\n'
def line_sha256(raw_line: bytes) -> str                            # one line, with or without its b'\n'
def chain_head(raw: bytes) -> str                                  # a whole samples.jsonl; ZERO_HASH when empty
def validate_record(name: str, value) -> None      # name: a member, 'marker.json' or 'checkpoint.json'; value: the parsed
    # object, or the list of rows of blocks.jsonl / critical_heights.jsonl; RECORD_INVALID
def validate_sample(value: dict, seq: int, prev_sha256: str) -> None                   # RECORD_INVALID
def read_samples(raw: bytes) -> list[dict]                         # every line validated and chained; RECORD_INVALID
def read_declaration(path: Path) -> dict                           # DECLARATION_MISSING, DECLARATION_INVALID
def intervals(samples: list[dict], fork_rows: list[dict], constants: dict, genesis_hash: str) -> dict
    # {'intervals': [{'first_seq', 'last_seq', 'monotonic_ns', 'ended_by'}], 'breaks': [{'seq', 'kind'}],
    #  'clock_steps': [{'seq', 'step_ns'}], 'longest': interval | None, 'current': interval | None}
    # 'current' is the interval holding the last sample: the stopping rule reads it
def s14_table(rows: list[dict], h0: int, genesis_hash: str | None = None, blocks: list[dict] | None = None) -> dict
    # section 8.1's 's14' without 'challenge' and 'not_covered'; genesis_hash: the environment's; blocks: the rows of
    # blocks.jsonl, for the H0 check (section 6); a value left None is not compared
def critical_disagreements(raw: bytes) -> int | None   # a critical_heights.jsonl's rows with agree false; None: not one
def check_registration(blob: bytes, sha256: str, head: str, required: int, root: Path | None = None,
                       pilot: bool = False) -> dict                # checks 7 and 8; pilot: the TEST_ONLY pilot's file
def plan(mode: str, attempt: int, expected_head: str, source_sha256: str, registration: str | None,
         registration_sha256: str | None, s04_run_id: int | None, overrides: dict[str, int] | None, environ,
         root: Path | None = None, s04_dir: Path | None = None, binaries: dict | None = None) -> dict
    # the declaration; section 10's order; binaries: {'archive_sha256', 'bitagi_sha256', 'fixture_sha256'}
def s04_run(folder: Path, run_id: int, head: str, root: Path | None = None) -> dict
    # check 9, the cited run from folder/run.json: {'run_attempt', 'head_sha'}
def s04_artifact_id(folder: Path, run_id: int, run_attempt: int) -> int | None    # folder/artifacts.json
def s04_job_id(folder: Path, run_id: int, run_attempt: int) -> int               # folder/jobs.json
def s04_cite(folder: Path, run_id: int, head: str, root: Path | None = None) -> dict    # check 9: the s04_citation
def pilot_registration(commit: str, required: int, root: Path | None = None) -> dict   # the pilot file's value
def marker(declaration: dict, head_sha256: str, monotonic_ns: int, realtime_ns: int) -> dict
def components() -> dict                                           # components.json's value
def scope_file(name: str) -> bytes                                 # the one line of txs.jsonl or reserve_snapshots.jsonl
def disagreement(run_id: int, attempt: int, row: dict) -> dict     # an incidents/ file's value
def fixture_line(raw: bytes, mode: str) -> dict | None      # section 4.7: the BUILD or FOLLOW line, or None
def fixture_refusal(raw: bytes) -> tuple[str, str | None]   # section 4.7: (the stderr line's code or OTHER, its node)
def monitor_request(genesis_hash: str, signet_challenge_hex: str, deployment_id_internal: str, h0: int) -> dict
    # section 4.8: monitor/request.json's value
def replay_check(build: dict, rows: list[dict], blocks: list[dict], critical: list[dict], genesis_hash: str,
                 constants: dict, window: tuple[int, int] | None) -> dict             # section 8.1, the replay codes
def monitor_check(log_raw: bytes | None, request_raw: bytes | None, final: dict, declaration: dict,
                  environment: dict, build: dict, critical: list[dict], window: tuple[int, int] | None) -> dict
    # section 8.1, the monitor codes; imports tools/claude_track_monitor.py (its check_log) when called
def attempt_row(declaration_raw: bytes, members: dict[str, bytes], listed: dict | None, server: dict | None) -> dict
    # members: name -> bytes of each of MEMBERS and MONITOR_FILES found. listed: {'run_id', 'created_at', 'head_sha', 'mode', 'attempt',
    # 'registration_sha256', 'runner_labels'}. server: {'job_started_at': int, 'anchors': {k: (file bytes, created_at in
    # seconds)}}. Both None for the attempt command (anchors NOT_CHECKED). Section 8.1's row: COUNTED, or with
    # `server` LOST when the records are missing or invalid (without it that is EVIDENCE_MISSING); raises Unreadable
def verdict(attempts: list[dict], constants: dict, never_started: list[dict] | None = None,
            coverage: str = COVERAGE_OK) -> dict           # section 8.2, over read rows, LOST rows and UNREADABLE entries
def collection_report(mode: str, registration_sha256: str | None, head_sha: str, attempts: list[dict],
                      never_started: list[dict], result: dict | None, constants: dict | None,
                      coverage: str = COVERAGE_OK) -> bytes
def observation_list(starts: dict[int, int], registration_sha256: str) -> bytes       # attempt -> start_time_utc
```
