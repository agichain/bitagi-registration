# CT-P5-005 evaluation policy, follow-up registration 2 (P5-002)

**CT-P5-005 follow-up registration 2 (Claude plan). This file becomes registered content when the registration file that carries its SHA-256 (`evaluation_policy_sha256`) merges on `main`; from then on any change is a new file and a new follow-up registration.**

Work item: CT-P5-005 (ROADMAP row 9), work-table row B4-15. Protocol impact: `NONE`. Class T development;
`release_authorization` NONE. Main sources: the frozen 045b,
`docs/claude-track/plans/CT-P3-045b_PREREGISTRATION_DRAFT_EN.md` (`045b:N`, a line of that file as frozen by PR #664
and pinned by this registration), and the P5-002 format document
`docs/claude-track/formats/P5002_ENDURANCE_V1.md` (`FMT:N`), which the registration binds through the P5-002 block
(section 3). "The first policy" is `docs/claude-track/preregistration/CT_P5_005_EVALUATION_POLICY_V1_FIRST.md`
(`EP1:N`); "follow-up 1's policy" is `docs/claude-track/preregistration/CT_P5_005_EVALUATION_POLICY_V1_FOLLOW_UP_1.md`
(`EPF1:N`). `CHK:N` is a line of `tools/claude_track_p5002_check.py`, `T-5002:N` of
`docs/tasks/P5-002_PRIVATE_SIGNET_ENDURANCE.md`, `GOV072:N` of
`specs/BITAGI_SEM1_TDS_D3_5_GOV_072_VALIDATION_BUDGET_ADDENDUM_2026-09-18_EN.md`, `TDS:N` of
`specs/BITAGI_SEM1_TDS_D3_5_FINAL_EN.md`, and `P5:N` of `docs/claude-track/plans/CT-P5_PHASE_PLAN_KO.md` (not pinned).
Line numbers of FMT and CHK are those of the registration commit; this file restates rules and fixes no value that the
format document, the checker or 045b does not already fix.

```text
Status: NO PRODUCTION NETWORK ACTIVE · DO NOT ACTIVATE · Class P NO-GO · DO NOT GENESIS
release_authorization NONE. No Profile approval, signing, broadcast or GO authority.
This file is a Claude plan, not a Founder decision. It makes no Class E or Class P claim.
```

## 1. What the registration is

- The registration is the exact bytes of one file,
  `docs/claude-track/preregistration/CT_P5_005_REGISTRATION_V1_FOLLOW_UP_2.json`. Its identity is the SHA-256 of
  those bytes; nothing is re-serialized before hashing (045b:288-291). That file and this one, whose SHA-256 it
  carries as `evaluation_policy_sha256`, are the evaluation policy of this follow-up registration (045b:289).
- It cites the first registration, `docs/claude-track/preregistration/CT_P5_005_REGISTRATION_V1_FIRST.json`, by
  `prior_registration_sha256`, the SHA-256 of that file's bytes. It keeps the same thresholds, has its own receipts
  and needs one more Founder tag signature (045b:318-321; EP1:43-45).
- This file states rules only. Every SHA-256 is in the registration file (`prior_registration_sha256`,
  `pinned_files`, `p5002.tool_sha256`), which pins this file's own hash. This file carries none of them and no commit
  id. The registration tool refuses a policy that carries the SHA-256 of a pinned file, of the first registration or
  of a P5-002 registered file, or the pinned commit (`EVALUATION_POLICY_CARRIES_PIN`), and a policy that does not
  hold the two fixed lines of section 2 byte for byte as the pinned checker defines them
  (`EVALUATION_POLICY_FIXED_LINES`).
- The registration file is one JSON object of schema `BITAGI_CT_P5_005_REGISTRATION_V1_FOLLOW_UP_2` in canonical
  bytes (sorted keys, two-space indent, ASCII, one LF at the end), at most 64 KiB. Its keys are a closed set:
  `schema`, `release_class`, `prior_registration_sha256`, `evaluation_policy_sha256`, `pinned_files`,
  `registration_key_ed25519_fingerprint`, `schemas` and `p5002`. It has no `experiments`, `ardr_policy_sha256`,
  `xd1`, `node_b` or seed key, and no marker.
- `tools/claude_track_p5005_registration.py check --scope FOLLOW_UP_2 --final` recomputes every SHA-256 from the tree
  at the registration commit and refuses any other bytes. Every P5-002 value it compares (the registered paths, the
  constants, the fixed lines, the pilot label, the schema names) is the tree checker's own, imported in a separate
  `python3 -B -I` process. Last, in such a process, it calls the tree's own readers:
  1. the checker's `pilot_registration` at the pinned commit, which requires that commit on `main`'s first-parent
     chain and reads each registered file there; each must equal the tree's, and the block it writes must equal the
     registration's (`P5002_COMMIT_NOT_ON_MAIN`, `P5002_TOOLS_MOVED`, `P5002_READER_REFUSES`);
  2. the checker's `check_registration` (plan checks 7 and 8, FMT:794-799), which must accept the file as a
     CONFIRMATORY registration at the pinned commit, not as the pilot, and return the same block
     (`P5002_READER_REFUSES`);
  3. the ARDR driver's `load_policy` in CONFIRMATORY under the frozen first ARDR policy, which must refuse the file
     for every experiment the driver knows (`ARDR_DRIVER_ACCEPTS_FOLLOW_UP_2`), so this file registers no ARDR
     experiment.
- Each confirmatory observation cites the `registration_sha256` it is evaluated under and carries its start time
  (045b:297-298). For P5-002 the dispatch input, the run name, the declaration, the marker and the report carry it,
  and the plan and report refuse a record bound to another hash (FMT:608, `REGISTRATION_MISMATCH`). The
  observation's start time is the observe job's server `started_at` (FMT:737-740).
- Release class: CLASS_T. P5-002 runs on a private Signet with no key (FMT:45-50; 045b:361-362). Class E freezes stay
  refused until 045b section 10 item 7 holds: CR-20, the time-authentication method, the public channel, and issue
  #110 closed (045b:943-946).

## 2. Scope

- This registration holds P5-002 under scope (b) (045b:1853-1856; P5:612): the rules, commands and tools of the format
  document and its tools, the two fixed lines, and the capture and retention list (045b:1033; EP1:50-51;
  EPF1:70-72). One registered attempt runs two Bitcoin Core nodes on one private Signet (`SIGNET_NODE_A`, Core 31.1;
  `SIGNET_NODE_B`, Core 30.3), the replay (B's TEST_ONLY Signet store fixture, labelled
  `configuration-unverified synthetic-context replay`) and the watcher (the monitor loop over `bitagi monitor tick`)
  (FMT:45-50). It covers S13 and S14 at genesis, H0−1 and H0, plus any reorganization fork point and public report
  cutoff (FMT:465-467).
- The two fixed lines, exactly as the pinned checker defines them (CHK:92-97; FMT:52-56). The registration carries
  them in `p5002.fixed_lines`, and `environment.json` and the report carry them too:

```text
P5-002 scope (b): two private Signet nodes, the replay and the watcher only; no launch host, no REGISTER or BEAT, no Signet H0-1 Rust/Python comparison.
S14 heights not covered: every block containing a project REGISTER candidate; accepted REGISTER height; every block containing a project BEAT candidate; accepted BEAT height. Not counted from Regtest CI; open in P5-004 until a later Signet launch run under its own registration.
```

- The S14 heights not covered are TDS 6.8's project REGISTER and BEAT heights (TDS:873-876; T-5002:19). They are not
  counted from Regtest CI and stay open in P5-004 until a later Signet launch run covers them under its own
  registration (045b:1855, :1870; P5:614; EPF1:215-219). Under FD-CT-112 that run is one short rehearsal, not
  86,400 s (P5:679).
- Transferability, both modes: `Two nodes on one VPS, an OP_TRUE Signet challenge and scripted blocks do not transfer to the mainnet hosts.`
  (FMT:63). The two nodes are this run's, on one VPS (one failure domain); they are not the Founder's mainnet Node
  A/B (FMT:48-49).
- Not in this registration:
  - ARDR items 3 and 4 and ITEM3W. They go to a later follow-up registration when their judgement steps are on `main`;
    a part that is ready does not wait for another (EP1:46-47). The reasons are in the unit note
    `docs/claude-track/plans/notes/CT-P5-005_EN/2026-11-17_follow-up-2.md`, section 2.
  - The content of follow-up registrations 1 and 1b (XD-1, P5-003, P5-004, the incident V1 verifier; ARDR ITEM2).
- Runs before this registration's receipts, the TEST_ONLY tag-path pilot and every EXPLORATORY run included, are
  EXPLORATORY. They inform the design and are not S13 or S14 evidence (FMT:58-62, label
  `CLASS_T_DEVELOPMENT_EVIDENCE_NOT_S13`; FMT:766-777).

## 3. Pinned content

- `pinned_files` is a closed set of eight files, each by path and SHA-256 recomputed from the tree: frozen 045b; the
  workflow `.github/workflows/claude-track-p5002.yml`; the format document; the checker, the VPS driver and the
  hosted tool (`tools/claude_track_p5002_check.py`, `tools/claude_track_p5002_driver.py`,
  `tools/claude_track_p5002_confirm.py`); and the tools modules they import, `tools/claude_track_exit.py` and
  `tools/claude_track_monitor.py` (the checker imports the latter inside `monitor_check`, FMT:39-40). Every tools
  module the three P5-002 tools import must be pinned (`TOOL_CLOSURE_NOT_PINNED`).
- `p5002` is exactly the block of FMT:745-764, `{pinned_commit, tool_sha256, constants, fixed_lines}`:
  - `pinned_commit` is the commit every CONFIRMATORY attempt runs: 40 lowercase hex characters, a commit on `main`'s
    first-parent chain (plan check 6, FMT:793). The Founder's attempt tags `ct-p5002-a<N>` point at it (FMT:83).
  - `tool_sha256` names exactly the checker's `REGISTERED_PATHS` (CHK:186-191; fourteen paths, FMT:752-760): the three
    tools, `tools/claude_track_exit.py`, `docs/policy/ACTIVE_VALIDATION_POLICY.json`, the workflow,
    `tools/claude_track_monitor.py`, `docs/claude-track/formats/MONITOR_LOG_V1.md`, the fixture and the two monitor
    tick sources under `crates/bitagi-cli/`, `Cargo.lock`, `rust-toolchain.toml` and the format document. Each is the
    SHA-256 of the file in the tree and must be the same at the pinned commit. The list must hold the checker, the
    policy file, the workflow and the format document, because the registration reads values from them or this file
    restates their rules (`P5002_REGISTERED_PATHS`).
  - `constants` is the checker's `registered_constants()` over `required_seconds()` (CHK:1077-1080): the fourteen
    unscaled effective constants of FMT:72-95 and the two node pins `node_versions` and `bitcoind_sha256`.
  - `fixed_lines` is `{scope_b, s14_not_covered}`, the two lines of section 2.
- `schemas`: `p5002_report` is the checker's `FORMAT_REPORT`, `BITAGI_CT_P5002_REPORT_V1`; `p5002_observation_list`
  is its `OBSERVATION_SCHEMA`, `BITAGI_CT_OBSERVATION_LIST_V1`. Both are read from the tree's checker.
- `registration_key_ed25519_fingerprint`: the same registration-only key as the first registration (EPF1:101-103),
  in ssh-keygen `SHA256:` form. The public repository's owner and name are not written in this repository
  (045b:1185).
- The file's bytes never hold the checker's TEST_ONLY pilot label (`PILOT_LABEL_IN_REGISTRATION`; FMT:766-777), and
  the checker refuses a registration that does (FMT:794-797, `REGISTRATION_TEST_ONLY`).
- 045b and the format document stay byte for byte as pinned while a judgement under this registration is still to
  come. A change to a registered P5-002 file needs a V2 of the format document and a new registration (FMT:14-15).
  Corrections in that interval go in decision records, not in those files (as EPF1:104-105).

## 4. P5-002 criteria

The criteria are GOV072's and TDS 6.8's; the format document states how they are computed and is not a criterion by
itself (FMT:12-13). The pinned checker computes every result below; `p5002.tool_sha256` binds its bytes.

- **S13.** At least 86,400 s of qualifying continuous actual operation on the registered private Signet context
  (GOV072:16-17; `required_seconds` as the checker reads it from the policy file, FMT:72). Replayed, accelerated or
  backdated time is not endurance; a reset or an unexplained gap restarts the interval (GOV072:94-98;
  T-5002:13-14, :19).
  - Good samples, breaks and the qualifying interval: FMT:410-435. Every break restarts the count from zero, and an
    explanation changes nothing (FMT:447). An interval never spans two attempts or two records directories; there
    is no inherited partial interval and no stitching (FMT:431-435).
  - Gaps: `SAMPLE_GAP` above `gap_seconds` (180 s; exactly 180 s is not a gap), `FAILED_SAMPLE`, `SUSPEND` above
    `clock_step_record_seconds` of suspended time (FMT:419-423).
  - Clock steps: a step above `clock_step_gap_seconds` (60 s) breaks; a step from 2 s to 60 s is listed and breaks
    nothing; the cumulative clock rule breaks an interval whose wall clock drifts more than 60 s from its opening
    offset (FMT:422, :436-441).
  - Live evidence: no new block seen on both nodes for more than `live_window_seconds` (1,800 s) breaks
    (`NO_LIVE_BLOCK`; FMT:442-446; GOV072:97-98).
  - Server anchors: the hosted report ties the longest interval to GitHub server times through the marker and the
    checkpoint artifacts (SA1 to SA7, FMT:492-515). S13 is `PASS` only when the identity checks are empty, the
    longest interval is at least `required_seconds` (86,400 s exactly passes; 86,399 s or 86,400 s less 1 ns fails)
    and the anchors pass (FMT:456-457, :547-549).
- **S14.** No Node A/B block-hash disagreement at the covered critical heights (TDS:866-880; FMT:463-490).
  - `FAIL` when any critical read disagrees, the monitor's CRITICAL_HEIGHT lines included: an automatic broadcast
    lock and NO-GO, final whatever a later attempt shows (FMT:470; TDS:880; FMT:553-555).
  - `PASS` when there is no disagreement and each of genesis, H0−1 and H0 has exactly one first and one final read,
    the final read shows the first read's hash, genesis is the environment's, H0's block is the producer's, and no
    fork point lies at or under H0 (FMT:471-474).
  - `INCOMPLETE` otherwise; `missing` names what was not recorded (FMT:475-486).
  - Challenge check: both nodes report the challenge `51` at start, in every good sample and at the end; a `FAIL`
    makes the attempt's S13 `FAIL` (FMT:487-490; T-5002:14).
- **Components.** The replay and the monitor checks must both pass in the passing attempt (FMT:557-589; FMT:648-649).
  The monitor's countdown and alarm output during P5-002 is the P5-004 monitor row (P5:344; EPF1:227).
- **Verdict** (CONFIRMATORY; FMT:635-655): the first rule that holds decides.
  1. Any S14 disagreement (a read attempt's S14 `FAIL`, a lost attempt's checkpoint count, a never-started dispatch's
     records): `FAIL`, `NO_GO_S14_DISAGREEMENT`, final.
  2. An unreadable attempt, or a coverage that is not `OK`: `INCONCLUSIVE`, with the cause kept.
  3. A read attempt with S13, S14 and both component checks `PASS`: `PASS`; `lost_attempts` is reported beside it.
  4. `max_attempts` attempts counted: `FAIL`, `ATTEMPTS_EXHAUSTED`.
  5. Otherwise `OPEN`.

## 5. Attempts

- At most `max_attempts` = 3 counted attempts under this registration (FMT:81; CHK:143). A counted attempt is a run
  that lists the marker artifact (FMT:693-702).
- A failed attempt (S13 `FAIL`, S14 `INCOMPLETE` or a component check that is not `PASS`) is kept and reported, counts
  toward the three, and leaves the verdict `OPEN` until a later attempt passes or the attempts are exhausted
  (FMT:650-655). A retry is dispatched only after A records the investigated cause (FMT:651; T-5002:15). No attempt
  is erased (FMT:619; T-5002:15).
- A `LOST` attempt (records missing, expired or invalid) fails S13, counts as one of the three, and its S14 after its
  last checkpoint is not known; a pass beside it names it (FMT:591-600, :656-666).
- An S14 disagreement ends the registration with `FAIL` (rule 1). It is not retried into a PASS.
- A CONFIRMATORY dispatch runs from an attempt tag at the pinned commit, first run attempt only, with no override of
  any constant (FMT:83, :102-103, :780-792); its run name carries this registration's SHA-256 (FMT:681-692).

## 6. Capture and retention list

045b:1033 asks the registration to carry a P5-002 capture and retention list before P5-002 observes, because
wall-clock data not logged inside the window cannot be rebuilt. The report's `capture_list` (FMT:628-631;
CHK:2324-2327) states each item:

| 045b:1033 item | `capture_list` field | State under scope (b) | Why |
|---|---|---|---|
| tx hex with attempt ids | `tx_hex` | `NOT_APPLICABLE_SCOPE_B` | Scope (b) makes no project transaction and no REGISTER or BEAT; `txs.jsonl` holds one line with zero rows and the fields it would have (FMT:359-362; A Q7) |
| broadcast, first-seen and inclusion times | `tx_times` | `NOT_APPLICABLE_SCOPE_B` | as above; the same file names `broadcast_realtime_ns`, `first_seen_realtime_ns`, `inclusion_realtime_ns` |
| reserve snapshots | `reserve_snapshots` | `NOT_APPLICABLE_SCOPE_B` | no reserve exists under (b); `reserve_snapshots.jsonl` holds one line with zero rows (FMT:359-362) |
| (block timing, not in 045b:1033) | `block_times` | `RECORDED` | `blocks.jsonl` (FMT:306-322) |
| outage intervals | `outage_intervals` | `RECORDED` | the breaks and intervals from the raw samples (FMT:407-462; section 4 here) |
| monitor and CT-P5-004-2c alarm logs | `monitor_logs` | `RECORDED` | `monitor/monitor.jsonl` and `monitor/request.json` (FMT:396-406) |
| fleet-scale items | `fleet_scale` | `NOT_MEASURED` | 045b:1033 states it; `final.json` carries it (FMT:356) |

- No synthetic row is written for an item that does not apply (FMT:361-362).
- Retention: the raw evidence stays in GitHub Actions artifacts for their retention period, with a summary in A's
  record (FMT:915-916). The collection report and the observation list are identified by the SHA-256 lines the
  hosted report job prints, not by an artifact name (FMT:890-897). A longer retention, or a copy outside Actions, is
  A's to decide (FMT:916); this file sets no other retention rule.

## 7. Observation completeness (#110) for P5-002

- The judged set is every counted attempt of this registration's CONFIRMATORY dispatches. The P5-002 tools bind it to
  GitHub's listing of the workflow's dispatches (server times), as FMT:668-733 states.
- The plan and report jobs read every page of the listing (fewer than 1,000 runs) and every run named CONFIRMATORY
  with this registration, and every run whose name has another shape; every other run must be completed
  (FMT:670-680).
- No run number is missing between the first CONFIRMATORY dispatch of this registration and the reporting run
  (`RUN_LIST_GAP`, FMT:681-692).
- An attempt counts when its run lists the marker; a run without it is never started only when nothing else shows a
  start, else `MARKER_MISSING` (FMT:693-702). The counted attempts are attempts 1 to k at the pinned commit, in
  creation order (`ATTEMPT_OTHER_COMMIT`, `ATTEMPT_GAP`, `ATTEMPT_OVERLAP`, FMT:703-710).
- A never-started dispatch's critical reads still count for S14 when its records are readable (FMT:716-722).
- A completeness refusal makes the collection `INCONCLUSIVE` (`COMPLETENESS_REFUSED`, or the coverage code), never
  `FAIL` (FMT:646-647, :711-715). An `UNREADABLE` attempt keeps the verdict `INCONCLUSIVE` in every later report of
  this registration, and no further attempt is dispatched for it (FMT:662-666).
- The observation list has schema `BITAGI_CT_OBSERVATION_LIST_V1`: one entry per counted attempt, in attempt order,
  with the id `OBS-0` followed by the attempt number in seven digits, `registration_sha256` and `start_time_utc`
  (FMT:735-741). The receipt check reads it. Its result stays `STRUCTURE_PASS_OBSERVATIONS_UNVERIFIED`, and issue
  #110 stays a condition for Class E (045b:943-946).
- What hosted verification cannot see is FMT:864-897 (the report's `hosted_limits`); this registration claims none of
  it.

## 8. Receipts and timing

- Receipts are the FD-CT-92 row 1 witnesses (045b:276-285, :322-329): an annotated tag in the separate public
  repository signed with the registration-only SSH key, with a published GitHub release on it, and at least one
  Bitcoin-confirmed OpenTimestamps proof over the signed tag object (045b:307-310). Every required witness must be
  strictly earlier than the first observation, not only the earliest (045b:299-302).
- This registration's receipts precede the first CONFIRMATORY P5-002 observation (EP1:43-45). The receipts of the
  registration that carries the incident V1 verifier (follow-up registration 1) also precede it (EP1:53-55;
  EPF1:264-266).
- The first CONFIRMATORY P5-002 observation starts no earlier than the latest witness time of this registration plus
  24 hours plus a 6-hour margin (30 hours). The witness times are the release's `published_at` and each proof's
  block-header time. The receipt check's own rule stays at least 24 hours (045b:309-310, :326-327). Every follow-up
  registration uses this 30-hour lead (EP1:115-118; EPF1:267-270).
- A P5-002 observation's start time is its observe job's server `started_at` (FMT:737-740). An attempt whose observe
  job starts before the proof's block time is not CONFIRMATORY evidence (as 045b:1034 states for ARDR runs), and an
  observation list whose first observation is not strictly later than every witness is refused by the receipt
  check (045b:299-306).

## 9. Stopping, exclusion and re-dispatch

- Each attempt stops by the daemon's stopping rule only: `STOP_RULE` when the interval holding the last sample reaches
  `required_seconds` + `stop_margin_seconds`, or `DEADLINE` at `checkpoints` × `checkpoint_seconds`. A break never
  stops it (FMT:458-462). There is no early stop after seeing a result and no extension past the deadline.
- There are no exclusions: every counted attempt is in the report, read, lost or unreadable (FMT:619; T-5002:15).
  The 10% exclusion rule applies to the ARDR rows only (045b:571-574).
- A dispatch that never started may be dispatched again; its attempt number is free again (FMT:693-702). A GitHub
  re-run is refused (first run attempt only, FMT:780-781). Once an attempt is counted it is never repeated or
  replaced; the next attempt is k + 1 (`ATTEMPT_NOT_NEXT`, FMT:703-710).

## 10. Scope change

- A changed criterion or threshold is a new policy identity with its reason. Results under the old one are kept, new
  confirmatory testing is needed, and an old failing attempt is never relabelled as a pass (045b:483-485).
- Any other change to the registered content is a new registration of the 045b:318-321 shape (045b:311-321). That
  covers a pinned file, a P5-002 registered file, the pinned commit, the constants, the fixed lines and the scope.
  The P5-002 plan job refuses a dispatch whose checkout differs from the registered hashes (FMT:798-799,
  `TOOL_SHA256_MISMATCH`).
- A later follow-up registration that carries ARDR items 3 and 4 or ITEM3W does not change this one.

## 11. What this file does not do

It records no Founder decision, grants no GO and holds no key, secret, credential, public repository name or commit
id. It makes no Class E or Class P claim and covers no mainnet host: the private Signet result does not transfer to
the mainnet hosts (section 2). It registers no launch host, REGISTER or BEAT, and it closes no S14 height that section
2 lists as not covered. The receipts, their verification, the attempts, the report and the P5 exit record are separate
records.
