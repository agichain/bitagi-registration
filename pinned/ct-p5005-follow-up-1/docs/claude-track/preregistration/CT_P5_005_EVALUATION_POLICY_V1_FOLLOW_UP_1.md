# CT-P5-005 evaluation policy, follow-up registration 1

**CT-P5-005 follow-up registration 1 (Claude plan). This file becomes registered content when the registration file that carries its SHA-256 (`evaluation_policy_sha256`) merges on `main`; from then on any change is a new file and a new follow-up registration.**

Work item: CT-P5-005 (ROADMAP row 9). Protocol impact: `NONE`. Class T development;
`release_authorization` NONE. Main source: the frozen 045b,
`docs/claude-track/plans/CT-P3-045b_PREREGISTRATION_DRAFT_EN.md`; `045b:N` is a line of that file as frozen by
PR #664 and pinned by this registration. "The first policy" is
`docs/claude-track/preregistration/CT_P5_005_EVALUATION_POLICY_V1_FIRST.md`. `P5:N` is a line of
`docs/claude-track/plans/CT-P5_PHASE_PLAN_KO.md`, and `FBO:N` a line of the frozen
`docs/claude-track/preregistration/FIRST_BEAT_OPERATIONS_V1_EN.md`. The phase plan is not pinned. This file restates
each P5-003 criterion and P5-004 rule it takes from there, and the restated text is what registers.

```text
Status: NO PRODUCTION NETWORK ACTIVE · DO NOT ACTIVATE · Class P NO-GO · DO NOT GENESIS
release_authorization NONE. No Profile approval, signing, broadcast or GO authority.
This file is a Claude plan, not a Founder decision. It makes no Class E or Class P claim.
```

## 1. What the registration is

- The registration is the exact bytes of one file,
  `docs/claude-track/preregistration/CT_P5_005_REGISTRATION_V1_FOLLOW_UP_1.json`. Its identity is the SHA-256 of
  those bytes; nothing is re-serialized before hashing (045b:288-291). That file and this one, whose SHA-256 it carries
  as `evaluation_policy_sha256`, are the evaluation policy of this follow-up registration (045b:289).
- It cites the first registration, `docs/claude-track/preregistration/CT_P5_005_REGISTRATION_V1_FIRST.json`, by
  `prior_registration_sha256`, the SHA-256 of that file's bytes (045b:319-320). It has its own receipts and needs one
  more Founder tag signature (045b:318-321).
- This file states rules only. Every SHA-256 is in the registration file (`prior_registration_sha256`,
  `pinned_files`, `xd1.tool_sha256`, `node_versions`), which pins this file's own hash. This file carries none of them
  and no commit id. The registration tool refuses a policy that carries the SHA-256 of a pinned file, of the first
  registration or of an XD-1 registered file (`EVALUATION_POLICY_CARRIES_PIN`).
- The registration file is one JSON object of schema `BITAGI_CT_P5_005_REGISTRATION_V1_FOLLOW_UP_1` in canonical
  bytes (sorted keys, two-space indent, ASCII, one LF at the end), at most 64 KiB. Its keys are a closed set:
  `schema`, `release_class`, `prior_registration_sha256`, `evaluation_policy_sha256`, `pinned_files`,
  `registration_key_ed25519_fingerprint`, `node_versions`, `schemas`, `xd1` and `xd1_criteria`. It has no
  `experiments`, `ardr_policy_sha256`, `node_b` or seed key.
- `tools/claude_track_p5005_registration.py check --scope FOLLOW_UP_1 --final` recomputes every SHA-256 from the tree
  at the registration commit and refuses any other bytes. The first registration must be in the tree as strict JSON
  with the first registration's schema and no marker word. Last, in a separate `python3 -B -I` process run in the
  tree, it calls the tree's own readers:
  1. the XD-1 collect tool's `on_main_first_parent` for the pinned commit against `refs/remotes/origin/main`, and
     each registered XD-1 file at that commit compared with the tree's (`XD1_COMMIT_NOT_ON_MAIN`, `XD1_TOOLS_MOVED`);
  2. the collect tool's `check_registration`, which must accept the file as a CONFIRMATORY registration at the pinned
     commit and read the same `xd1` value (`XD1_READER_REFUSES`);
  3. the ARDR driver's `load_policy` in CONFIRMATORY for ITEM1 under the frozen first ARDR policy, which must refuse
     the file (`ARDR_DRIVER_ACCEPTS_FOLLOW_UP_1`).
- Each confirmatory observation cites the `registration_sha256` it is evaluated under and carries its start time
  (045b:297-298). For XD-1 the dispatch input, the run name, the session declaration, each run record and the
  observation list carry it, and the XD-1 checker refuses a run record bound to another hash.
- Release class: CLASS_T. XD-1 runs on Regtest and P5-003 on the private Signet; both are Class T (045b:361-362).
  Class E freezes stay refused until 045b section 10 item 7 holds: CR-20, the time-authentication method, the public
  channel, and issue #110 closed (045b:943-946).

## 2. Scope

- This registration holds:
  - XD-1 section 5.1's 20 confirmatory runs and criterion (045b:603-616; the metric as amended at :1200), with the
    session rule (045b:1099) and XD-1 observation completeness (sections 4 and 9 here);
  - the P5-003 pass criteria (section 5);
  - the P5-004 judgment rules (section 6);
  - the incident V1 verifier for the 045b section 8.2 record (045b:854-896, with the R19-10 additions, :1838)
    (section 7).
- It registers no ARDR experiment. The registration tool requires the ARDR driver to refuse this file (section 1).
- This file does not register ITEM2. Under FD-CT-133 ITEM2 is out of the first registration, and it registers with
  its fixed L0 ladder, its policy, its judge inputs and a new seed in a later follow-up registration
  (`docs/claude-track/decisions/FD-CT-133_2026-11-12.md:60`). Whether that is this follow-up registration or a
  separate follow-up registration 1b is decided by A at the ITEM2 seed PR, under A's decision F1 (#258
  issuecomment-6820596249).
- Still for later follow-up registrations: the P5-002 rules, commands and capture and retention list, and ARDR items
  3 and 4 and ITEM3W (the first policy, section 2; 045b:1033, :1573, :1590). A part that is ready does not wait for
  another (the first policy, section 2).
- Runs before this registration's receipts, the XD-1 live-decision pilot included, are EXPLORATORY. They inform the
  design and are not S17-PREP evidence (045b:607-609).

## 3. Pinned content

- `pinned_files` is a closed set of six files, each by path and SHA-256 recomputed from the tree:
  - frozen 045b;
  - the D4 crosswalk note,
    `docs/claude-track/plans/notes/CT-P3-045b_PREREGISTRATION_DRAFT_EN/2026-11-09_d4-crosswalk.md` (045b:1148);
  - the incident format document `docs/claude-track/formats/BROADCAST_LOCK_INCIDENT_V1.md`;
  - the incident verifier `tools/claude_track_incident_v1.py`, with `tools/common.py` and
    `tools/claude_track_exit.py`. Every tools module the verifier imports must be pinned
    (`TOOL_CLOSURE_NOT_PINNED`).
- `xd1` is exactly `{pinned_commit, tool_sha256}`:
  - `pinned_commit` is the commit every XD-1 session runs. It is 40 lowercase hex characters and a commit on
    `main`'s first-parent chain: a merge commit `main` pointed at, not a commit of a merged branch. It holds the
    XD-1 confirmatory harness and the worker gate.
  - `tool_sha256` names exactly the XD-1 collect tool's `REGISTERED_PATHS`, each with the SHA-256 of that file in
    the tree. These are eleven files: the six XD-1 tools (check, driver, collect, supervisor, confirm, decide),
    `tools/claude_track_regtest_offline_export.py`, `tools/claude_track_exit.py`, the confirmatory workflow, the
    V3 format document and the worker test file. Each must be the same at the pinned commit. The list must hold the
    checker, collect and the workflow, because the registration reads values from their bytes
    (`XD1_REGISTERED_PATHS`).
- `node_versions`: the Bitcoin Core 31.1 and 30.3 archive and `bitcoind` values, as the XD-1 confirmatory
  workflow's `fetch` lines pin them.
- `schemas`: `incident_record` is the incident verifier's `SCHEMA`, `BITAGI_CT_BROADCAST_LOCK_INCIDENT_V1`;
  `xd1_observation_list` is the XD-1 checker's `OBSERVATION_SCHEMA`, `BITAGI_CT_OBSERVATION_LIST_V1`. Both are read
  from the sources.
- `registration_key_ed25519_fingerprint`: the same registration-only key as the first registration (A's decision
  F3), in ssh-keygen `SHA256:` form. The public repository's owner and name are not written in this repository
  (045b:1185).
- 045b and the D4 crosswalk note stay byte for byte as pinned while a judgement under this registration is still to
  come. Corrections in that interval go in decision records, not in those files (as the first policy, section 3).
- P5-003 and P5-004 have no pinned tool. This file restates their criteria and rules, and that text is their
  registered form.

## 4. XD-1 runs and criterion

- **Runs.** Exactly 20 confirmatory runs, `run_index` 1 to 20 in order, in the 044c-1 two-node Regtest. In each run
  the Founder types the broadcast decision live at the VPS console (045b:603-604; the Founder and the VPS: FD-CT-51;
  the live decision: `docs/claude-track/plans/notes/CT-P3-044C1_PLAN_EN/2026-11-10_xd1-confirmatory.md:32`). Fixed
  N, no early stopping and no extension (045b:605-607).
- **Sessions.** One dispatch is one session of 1 to 5 consecutive runs. A session ends only between two runs, and the
  next session starts at the next `run_index`. No run is repeated, skipped or replaced (045b:1099, dated line). The
  registered split is 1, 5, 5, 5 and 4 runs (FD-CT-134). The XD-1 tools enforce the session size and the next-session
  rule; they do not read the split. Where a session ends cannot change which runs count (045b:1099, dated line).
- **Cap.** Each run has a 900-second cap (`XD1_RUN_CAP`). A run that passes the cap, for example through the
  Founder's absence or delay, counts `T = ∞` and is not repeated (045b:1099).
- **Metric.** `T_045b`: from S0 to the last submission attempt's return on both nodes (045b:598-602, as decided at
  :1200). `T_bound` is still reported for every run and never replaces it. Each duration is whole seconds, rounded
  up (045b:565-569).
- **Criterion.** The p95 of `T` is at most 420 s, by nearest rank over the 20 runs: the 19th of the 20 sorted values,
  with `T = ∞` sorting last (045b:565-569, :610-613).
- **Missing data.** A run without a complete timestamp chain counts `T = ∞`, a failure, and is never excluded
  (045b:618-619).
- **Verdict.** PASS when the 19th value is at most 420 s. FAIL when it is above 420 s, an infinite 19th value
  included. INCONCLUSIVE only at collection level, with its cause kept and never folded into FAIL: a refused
  declaration, a registration mismatch, a refused completeness, refused labels, or fewer than 20 counted runs
  (045b:1090).
- **Failure.** A p95 above 420 s re-raises A-1 (XD-1) to MAJOR and goes to the Founder (045b:614-615). The Class E
  notice states the single-interval structure and the success probability `exp(-p50 / 600)` either way
  (045b:615-616). The criterion covers `T`, the H0−1 path, only (045b:617).
- **Reported apart.** Each run's `D1 − D0` as a `B_operator` sample (045b:1099). Inclusion and replay, per run, never
  merged into success (045b:1100). One environment row: the node versions, the T4-2 PASS SHA of the collection head,
  the VPS and CR-21 disposition, and 3r-L merged first (045b:1098).
- **Labels.** A CONFIRMATORY record carries `CLASS_T`, `CONFIRMATORY`, `DECISION_LIVE_FOUNDER_VPS_CONSOLE`,
  `REGTEST`, `S17_PREP_EVIDENCE_CLASS_T` and `TEST_ONLY_PRIVATE_SCALAR_KNOWN`. The checker refuses relabelling in
  either direction (045b:584-589).
- **`xd1_criteria`.** The registration records `runs` 20, `first_run` 1, `last_run` 20, `sessions`
  `[1, 5, 5, 5, 4]`, `cap_seconds` 900, `p95_rank` 19, `p95_max_seconds` 420 and `missing_run` `INFINITY`, integers
  only. The registration tool checks them against the tree's XD-1 checker constants (`MAX_XD1_RUNS`,
  `XD1_RUN_CAP_NS`, `SESSION_RUNS`, `CRITERION_S`, `P95`, read from its source without running it), with the rank as
  the integer ceiling of `P95 × runs / 100`, and then against these exact values (`XD1_CRITERIA_*`). The pinned
  checker computes the verdict; `xd1.tool_sha256` binds its bytes.
- **Dispatch.** A dispatches `claude-track-xd1-confirmatory` (`.github/workflows/claude-track-xd1-confirmatory.yml`),
  first attempt only, from a pinned attempt tag `ct-xd1-c-a<N>` on the pinned commit. Inputs: `mode` CONFIRMATORY,
  `first_run`, `last_run`, `expected_head` the pinned commit, `registration` this registration file's path on `main`,
  and `registration_sha256` its SHA-256. Run name: `xd1 CONFIRMATORY runs <first>-<last> registration <sha256>`.
  The workflow's exclusive job refuses while a 7a, VPS checks or other XD-1 run waits or runs.
- **Plan job** (`tools/claude_track_xd1_collect.py plan-v3`). It refuses unless the run is a workflow dispatch,
  attempt 1, at the expected head, from a pinned attempt tag, with a session of 1 to 5 consecutive runs within 1 to
  20 that fits the session budget. It reads the registration as merged on `main` (`refs/remotes/origin/main:<path>`,
  the bytes the receipts cover). Its SHA-256 must be the input. `xd1.pinned_commit` must be the dispatched commit
  (`NOT_THE_PINNED_COMMIT`) and on `main`'s first-parent chain (`NOT_ON_MAIN`). `xd1.tool_sha256` must name exactly
  the registered files, each with the checkout's SHA-256 (`REGISTRATION_TOOLS`, `TOOL_SHA256_MISMATCH`). A path under
  `tests/` is refused, and so is a file that carries the collect tool's pilot label anywhere in its bytes
  (`REGISTRATION_TEST_ONLY`). Then `tools/claude_track_xd1_confirm.py continuity` checks that the session is the next
  one (section 9).
- **Report job.** `tools/claude_track_xd1_confirm.py report` writes the collection report V3 with the verdict and
  the observation list (section 9).
- **Pre-flight.** After the registration merges, and before the Founder's tag and the receipts, A runs session 1's
  `plan-v3` locally at the pinned commit with `main` fetched. A expects exit 0 and the registration's SHA-256 in the
  output. Any refusal there is one the first session would give after the receipts, when fixing it costs a new
  registration.

## 5. P5-003 pass criteria

- P5-003 is the node-replacement rehearsal on the private Signet by the C4 path: the new node replays from H0−1
  (FD-CT-112; P5:663). It runs after P5-002 ends (P5:257). A runs it on the VPS, and a non-author Reviewer verifies
  the record (P5:252). These criteria replace the four of the phase plan's section 8.4 (P5:274, :668).
- The criteria (1 to 6, 8 and 9: P5:669-676; 7: FBO:282):
  1. The new node replays from an empty state at H0−1 and catches up with the old node's tip. It uses no state or file
     of the old node as a trusted input.
  2. After the catch-up, the two nodes' critical-height records are the same (P5:670, citing TDS:868-878).
  3. After the catch-up, the new node's state is the same as the old node's. The comparison is verify-only, and
     import writing stays refused. It compares `state_digest` and `as_of_block_hash_display` from `replay status`
     on both nodes at the same `as_of_height`, both reads `STORE_SYNCED`. A difference at the same height is FAIL.
     Two reads at different heights are not a comparison; they are read again. This replaces P5:671's byte
     equality with the old node's checkpoint export, because `export-state` refuses without a stored checkpoint
     row (`NO_CHECKPOINT_AT_HEIGHT`) and no product caller writes one (finding #796; A's B3-03 decision).
  4. The new node is on the same Signet as the old node. Two Signets can share a genesis, and a block hash does not
     authenticate the challenge. The product cannot check this itself today, so the operator compares the two
     nodes' Signet challenge settings and writes a manual record. A difference is FAIL (P5:672). The record has,
     for each node (OLD and NEW): the Bitcoin Core version, `chain` (it must be `signet`), the `signetchallenge`
     value in hex, where it was set (configuration file or command line), and the block hash at H0−1 (recorded,
     not compared). Then `challenge_equal` (`EQUAL` or `DIFFERENT`) and the result. Only that one setting is
     copied, never a whole configuration file, which can hold RPC credentials.
  5. A mismatch is FAIL. The rehearsal is not run again to turn it into a PASS (P5:673).
  6. The record gives the elapsed time and the number of blocks replayed (P5:674). One clock: the new node host's
     UTC wall clock, never a block-header time. Start: the replay command starts on an empty store at H0−1. End:
     the first `replay status` on the new node that reads `STORE_SYNCED` with `as_of_height` equal to the old
     node's `as_of_height` read at the same time. Durations are whole seconds, rounded up. Blocks replayed: the end
     `as_of_height` − (H0−1). The rehearsal is one timed replay.
  7. The record gives the wall time to restore each restored part, a `B_restore` sample (FBO:282). A part never
     lowers the term; only a part larger than the whole assumption raises it (FBO:241). The parts are
     `NODE_REBUILD`, `REPLAY` and `CHECKS`, each with its UTC start, UTC end and elapsed whole seconds. Host and
     signer restore are not part of P5-003.
  8. No real key and no mainnet credential is used (P5:675; AGENTS.md section 9).
  9. Authenticated transfer and the suspected-exposure path (replacement after a key is revoked) are outside this
     rehearsal. The record writes them as not covered (P5:676).
- The rehearsal record cites this registration's SHA-256 and carries its start time (045b:297-298).
- The C4 replay time A measures before the rehearsal is EXPLORATORY, by criterion 6's method, three timed replays.
  It serves the FD-CT-112 condition for asking the Founder again (P5:677) and is not evidence of this rehearsal.
  It does not gate this registration.
- A failed attempt and its raw data are kept (P5:347).

## 6. P5-004 judgment rules

- A writes the P5 exit record, and a non-author Reviewer verifies it (P5:333). It comes after P5-003 (P5:223).
- Each row's PASS condition (P5:338-344):
  - **S13.** A continuous qualifying interval of at least 86,400 s in the preregistered private Signet context. Its
    measurement rules are P5-002's, in the follow-up registration that carries P5-002.
  - **S14.** No Node A/B block-hash mismatch at the critical heights; the height list is TDS 6.8 (TDS:1316,
    :868-878). The project REGISTER and BEAT heights that P5-002 scope (b) does not cover are recorded as open,
    until a later Signet launch run, under its own registration, covers them (045b:1870; P5:614, :679). The row is
    PASS over the covered heights only, and it lists the open heights by name. An open height does not make the row
    not PASS, and the row never claims it.
  - **ARDR items 1–4 and the nine measurements.** Each has one of ESTABLISHED, NOT_ESTABLISHED or NO-GO, under the
    registration that carries it. Items 5 and 7 are Founder statements and belong to CT-P7-001.
  - **XD-1.** Section 4's verdict is PASS: the p95 of the 20 confirmatory runs is at most 420 s. Above it, A-1
    (XD-1) is re-raised to MAJOR and goes to the Founder.
  - **P5-003.** Section 5's criteria pass.
  - **G5-02.** Every opened incident has a valid version 2. An incident without one is recorded as still open. The
    check is section 7's `check-set`, once for each deployment's record set.
  - **Monitor.** Countdown and alarm output exist during P5-002 (the phase plan's section 10).
- The value is `P5_COMPLETE` or `P5_INCOMPLETE`. A row that is not PASS makes it `P5_INCOMPLETE`, with the reason for
  each row (P5:346). An XD-1 INCONCLUSIVE is not a PASS.
- Each row cites the registration under which its evidence was evaluated (045b:297-298).
- Failed attempts and raw data are not deleted. A FAIL is never written as a PASS (P5:347).
- The record holds no secret. A transaction is named by its txid only (P5:348; 045b:850-852).

## 7. Incident V1 verifier

- The registered verifier is `tools/claude_track_incident_v1.py` as it is on `main` at the registration commit,
  with its format document and import closure (section 3). It checks records of schema
  `BITAGI_CT_BROADCAST_LOCK_INCIDENT_V1`: 045b section 8.2 (045b:847-896) with its dated notes, section 14.8
  (:1128-1134) and section 14.19 item 5 (:1739-1743). It accepts the R19-10 additions:
  `RUST_PYTHON_MISMATCH_TIP_GE_H0`, `REFERENCE_DIVERGENCE_REFUSAL` and the two new release rows (045b:1838).
- `check-record FILE` checks one record. `check-set DIR` checks one deployment's record set: the record rules, then
  the set rules (045b:886-896). Each incident is OPEN or RELEASED. While any incident is OPEN, `broadcast_allowed` is
  false and the code is `INCIDENT_OPEN` (exit 6).
- The verifier cannot check whether a digest is the evidence its member names, whether `affected_txids` is
  complete, whether the heights fit each other, or whether every lock was recorded. The record set is supplied by
  the caller (the format document, section 5).
- Freeze condition 9 says the P5-005 verifier carries the SSoT:2847 crosswalk of 13 fields and the Class E subset
  table of SSoT:2849's 23 criteria (045b:1148). The pinned D4 crosswalk note holds them. The verifier's
  `crosswalk --note PATH` command checks a note's two tables against the verifier's own copy. A runs it on the
  pinned note at the registration commit before the registration; the registration tool does not run it. If the
  verifier on `main` does not carry the tables by then, the verifier goes to the next follow-up registration (A's
  decision F7, #258 issuecomment-6820596249).
- Every broadcast lock during P5 is recorded in this format (P5:142), and P5-004's G5-02 row reads this verifier
  (section 6).
- A change to the verifier, its format document or a module of its import closure is a new registration before a
  registered judgement uses it, as for a driver change (045b:311-316).

## 8. Receipts and timing

- Receipts are the FD-CT-92 row 1 witnesses (045b:276-285, :322-329): an annotated tag in the separate public
  repository signed with the registration-only SSH key, with a published GitHub release on it, and at least one
  Bitcoin-confirmed OpenTimestamps proof over the signed tag object (045b:307-310). Every required witness must be
  strictly earlier than the first observation, not only the earliest (045b:299-302).
- This registration's receipts precede the first CONFIRMATORY XD-1 observation and the start of the P5-003
  rehearsal. Because this registration carries the incident verifier, they also precede the first CONFIRMATORY
  P5-002 observation (the first policy, section 2).
- Each of these starts no earlier than the latest witness time plus 24 hours plus a 6-hour margin (30 hours). The
  witness times are the release's `published_at` and each proof's block-header time. The receipt check's own rule
  stays at least 24 hours (045b:309-310, :326-327). Every follow-up registration uses the same 30-hour lead (the
  first policy, section 5; #258 issuecomment-6798644052 item 1).
- An XD-1 observation's start time is its session's slice job `started_at`, the server time the report job reads.
  A session that starts before the proof's block time is not CONFIRMATORY, as 045b:1034 states for ARDR runs.

## 9. Observation completeness for XD-1

- The judged set is every counted session of this registration's CONFIRMATORY dispatches. The XD-1 tools bind it
  to GitHub's listing of the workflow's dispatches (server times), as follows.
- The plan and report jobs read every page of the listing. It must hold fewer than 1,000 runs (`RUN_LIST_CAPPED`),
  and pages that change while they are read are refused (`RUN_LIST_CHANGED`). They read every CONFIRMATORY dispatch
  whose run name carries this registration's SHA-256, and every run whose name has another shape. Every run but the
  current one must be completed (`OTHER_RUN_IN_PROGRESS`).
- A session counts when its run lists the session-start marker artifact, which the slice job uploads before the
  first run starts. A session without it never started: it is listed, not counted, and its range is free again. A
  run whose name has another shape must list no marker (`RUN_LIST_TITLE`). An expired marker is refused
  (`ARTIFACT_EXPIRED`), since it cannot be told from one never written.
- The counted sessions, in creation order, must cover exactly runs 1 to k, each run once, all at the pinned commit
  (`SESSION_GAP`, `SESSION_OVERLAP`, `SESSION_OTHER_COMMIT`). Before a session runs, the plan job requires its first
  run to be k + 1 (`SESSION_NOT_NEXT`; `ALL_RUNS_COUNTED` after run 20).
- The report job reads each counted session's marker, declaration and records through the checker. Each artifact's
  SHA-256 must equal its listed digest where the listing gives one (`ARTIFACT_DIGEST`). A completeness refusal makes
  the collection INCONCLUSIVE (`COMPLETENESS_REFUSED`), never FAIL. 20 counted runs give PASS or FAIL; fewer give
  `FEWER_THAN_20_RUNS`.
- The observation list has schema `BITAGI_CT_OBSERVATION_LIST_V1`: one entry per counted run, in run order, with
  the id `OBS-9` followed by the run index in seven digits, `registration_sha256` and `start_time_utc` (section 8).
  The report job writes it for a CONFIRMATORY collection with a counted session and no INCONCLUSIVE cause other than
  `FEWER_THAN_20_RUNS`. The receipt check reads this list. Its result stays
  `STRUCTURE_PASS_OBSERVATIONS_UNVERIFIED`, and issue #110 stays a condition for Class E (045b:943-946).
- P5-003: every attempt of the rehearsal is recorded, and none is deleted (P5:347, :673). P5-002 completeness goes
  with the follow-up registration that registers P5-002.

## 10. Stopping, exclusion and re-dispatch

- XD-1: fixed N of 20, no early stopping and no extension after seeing results (045b:571-574, :605-607). XD-1 has
  no exclusions: the 10% exclusion rule applies to the ARDR rows only (045b:1089), and a missing run counts
  `T = ∞` (045b:618-619).
- A session that never started may be dispatched again for the same range. Once its marker exists, every run of the
  session counts, and a run with no record is `T = ∞`. A GitHub re-run is refused (attempt 1 only). No run is
  repeated, skipped or replaced (045b:1099).
- P5-003: a mismatch is FAIL and is not run again into a PASS (P5:673). An attempt that stops before any criterion
  is compared (for example a lost host or a setup error) may be run again. Its record is kept, says why it stopped,
  and is cited by the next attempt. An attempt that reaches a comparison is final (as 045b:576-580 for a unit with
  a recorded observation).

## 11. Scope change

- A changed criterion or threshold is a new policy identity with its reason. Results under the old one are kept, new
  confirmatory testing is needed, and an old failing run is never relabelled as a pass (045b:483-485).
- Any other change to the registered content is a new registration of the 045b:318-321 shape (045b:311-321). That
  covers a pinned file, an XD-1 registered file, the pinned commit, a P5-003 criterion, a P5-004 rule and the scope.
  The XD-1 plan job refuses a dispatch whose checkout differs from the registered hashes.
- If ITEM2 registers in a separate follow-up registration 1b, that registration does not change this one.

## 12. What this file does not do

It records no Founder decision, grants no GO and holds no key, secret, credential, public repository name or commit
id. The receipts, their verification, the verdicts and the P5 exit record are separate records.
