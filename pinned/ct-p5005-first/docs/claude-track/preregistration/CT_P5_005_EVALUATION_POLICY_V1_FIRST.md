# CT-P5-005 evaluation policy, first registration

**CT-P5-005 first registration (Claude plan). This file becomes registered content when the registration file that carries its SHA-256 (`evaluation_policy_sha256`) merges on `main`; from then on any change is a new file and a follow-up registration.**

Work item: CT-P5-005 (ROADMAP row 9). Protocol impact: `NONE`. Class T development;
`release_authorization` NONE. Main source: the frozen 045b,
`docs/claude-track/plans/CT-P3-045b_PREREGISTRATION_DRAFT_EN.md`; `045b:N` is a line of that file as frozen by
PR #664 and pinned by this registration.

```text
Status: NO PRODUCTION NETWORK ACTIVE · DO NOT ACTIVATE · Class P NO-GO · DO NOT GENESIS
release_authorization NONE. No Profile approval, signing, broadcast or GO authority.
This file is a Claude plan, not a Founder decision. It makes no Class E or Class P claim.
```

## 1. What the registration is

- The registration is the exact bytes of one file,
  `docs/claude-track/preregistration/CT_P5_005_REGISTRATION_V1_FIRST.json`. Its identity is the SHA-256 of those
  bytes; nothing is re-serialized before hashing (045b:288-291). That file and this one, whose SHA-256 it carries as
  `evaluation_policy_sha256`, are the CT-P5-005 evaluation policy (045b:289).
- This file states rules only. Every SHA-256 of a repository file is in the registration file (`pinned_files`,
  `ardr_policy_sha256`, `d2_2_tool_sha256`), which pins this file's own hash. This file carries none of them, so
  the two files do not depend on each other's hashes and a tool or document change before the registration does not
  change this file.
- The registration file is one JSON object of schema `BITAGI_CT_P5_005_REGISTRATION_V1` in canonical bytes (sorted
  keys, two-space indent, ASCII, one LF at the end). `tools/claude_track_p5005_registration.py check --final`
  recomputes every pinned SHA-256 from the tree at the registration commit and refuses any other bytes.
- Each confirmatory observation cites the `registration_sha256` it is evaluated under and carries its start time
  (045b:297-298). Every raw-log line of a CONFIRMATORY ARDR run carries it, and the driver refuses registration
  bytes whose SHA-256 differs from the one given (`REGISTRATION_BYTES_CHANGED`).
- Release class: CLASS_T. Every experiment is Class T Regtest (045b:361-362). Class E freezes stay refused until
  045b section 10 item 7 holds: CR-20, the time-authentication method, the public channel, and issue #110 closed
  (045b:943-946). The receipt identity binds CLASS_T.

## 2. Scope

- This registration holds ARDR items 1 and 2 and the pool run: experiments ITEM1, ITEM2 and POOL of the frozen ARDR
  policy `docs/claude-track/preregistration/ARDR_POLICY_V1_CLASS_T_REGTEST_FIRST.json`, with the ITEM1 method policy
  `docs/claude-track/preregistration/ARDR_METHOD_POLICY_V1_CLASS_T_REGTEST_ITEM1.json` (045b:316-321, :1901). The
  frozen policy lists these three experiments only. Their thresholds are 045b section 4 as amended in section 14;
  045b is their one source, and the method policy's `thresholds` is a copy the tools check (045b:1901).
- Follow-up registrations. Each cites this registration's SHA-256, has its own receipts under 045b section 3.2
  (045b:286-329), and needs one more Founder tag signature (045b:318-321). Each one's receipts precede the first
  confirmatory observation of everything it registers.
- This policy does not fix how the content below is grouped into follow-up registrations, or how many there are. A
  follow-up registration takes the parts that are ready on `main`; a part that is ready does not wait for another.
  The content still to be registered:
  - XD-1 section 5.1's 20 confirmatory runs and criterion (045b:603-615; the metric as amended at :1200);
  - the P5-002 rules and commands under scope (b) (045b:1853-1856), with the (b) scope line and the
    not-covered-heights line (045b:1870) and the P5-002 capture and retention list (045b:1033);
  - the P5-003 pass criteria and the P5-004 judgment rules;
  - the incident V1 verifier for the 045b section 8.2 record (045b:854-896, with the R19-10 additions, :1838). Its
    registration's receipts precede the first confirmatory XD-1 observation and the first confirmatory P5-002
    observation;
  - ARDR items 3 and 4 and ITEM3W (045b:316-321, :1573, :1590), with the same thresholds.

## 3. Pinned content

- The registration file pins, by path and SHA-256 recomputed from the tree:
  - the frozen ARDR policy and the ITEM1 method policy, both in the flat list `ardr_policy_sha256` that the ARDR
    driver and judge read; the list carries the method policy's SHA-256 (045b:1035);
  - the D2-2 cluster tool, also as `d2_2_tool_sha256` (045b:1032);
  - the Class T L0 budget record (the frozen policy's `l0_seat.budget_sha256`, 045b:1898), the Class E budget record,
    the frozen fee policy, the first-BEAT operations and the disposition extract (045b:1891-1899);
  - frozen 045b itself and its companion notes: the wait registry, the D4 crosswalk, and the `b6000fz` request and
    result (045b:992, :1018, :1148, :1902);
  - the CT-P5-001 inventory, whose section 2 is the minimum transition list (045b:1279, dated line);
  - the ARDR tools the runs and judgements use (the driver and every tools module in its, the judge's, the slices
    tool's and the cluster tool's import closure), the campaign and judge workflows, and the three ARDR format
    documents (045b:311-316);
  - the active validation policy file and the GOV072 addendum it binds.
- It also records values that are not repository files: the fee-trace dataset and script values (045b:1162, :1178),
  the Bitcoin Core 31.1 and 30.3 archive and `bitcoind` values as the campaign workflow pins them, the schema names,
  and the seed provenance: `H_s` 975,205, whose block hash Node A read as
  00000000000000000000a4b800a47aae4e800d1e0323de95244cd867968529f4, and the seed rule's inputs (045b:1901).
- 045b and the CT-P5-001 inventory stay byte for byte as pinned from the registration to the first verdict.
  Corrections in that interval go in decision records, not in those files.
- The Class E budget record is pinned for reference only. The ARDR experiments do not use it; the ITEM2 L0 seat uses
  the Class T record. If the 11-15 H0 hold changes H0, a follow-up note records it, and this registration is not
  affected.
- The SSoT:2847 crosswalk of 13 fields and the Class E subset table of SSoT:2849's 23 criteria (045b:1148, condition
  9) are the pinned D4 crosswalk note,
  `docs/claude-track/plans/notes/CT-P3-045b_PREREGISTRATION_DRAFT_EN/2026-11-09_d4-crosswalk.md`. This registration
  carries them by that reference. The verifier-side copy ("The P5-005 verifier carries the same tables", 045b:1148)
  goes with the incident V1 verifier in the follow-up registration that carries it.
- The registration-only key's ED25519 fingerprint (ssh-keygen `SHA256:` form) is in the registration file. The public
  repository's owner and name are not written in this repository (045b:1185).

## 4. Runs and their commands

- The driver commit used for the confirmatory runs and A's judge are on `main` before the registration. A driver
  change after it needs a new registration (045b:311-316); so does a change of the run's start margin (045b:1903).
- From the registration to the verdict, `main` changes only by a merge commit or a squash merge. Otherwise the verdict
  record names that commit (045b:1031).
- Dispatch: the campaign workflow `claude-track-ardr` (`.github/workflows/claude-track-ardr.yml`), dispatched by A
  from `main`, first attempt only, run name `ardr CONFIRMATORY <experiment>`. Inputs: `experiment` (ITEM1, ITEM2 or
  POOL), `mode` CONFIRMATORY, the unit range and slice inputs, `policy` the frozen policy's path, `registration` this
  registration file's path in that commit, `registration_sha256` its SHA-256, and `s04_run_id`. Its jobs are `plan`
  (`tools/claude_track_ardr_slices.py plan`), `slice` (the driver's `run`, one unit at a time) and `collect`. A
  `RECOLLECT` dispatch is collect-only recovery of one CONFIRMATORY dispatch. Units, from the frozen policy's `counts`
  and `gates_per_run`: ITEM1 is one run of 200 gates, ITEM2 200 runs of one gate, POOL 50 runs of 4 gates.
- Judgement: A's judge `tools/claude_track_ardr_judge.py` in mode CONFIRMATORY with this registration: per run
  `item1`, `item2` or `pool`; per experiment `experiment --experiment ITEM1|ITEM2|POOL` over every completed dispatch
  of the experiment whose head is on `main`'s first-parent history (045b:1034). The judge workflow
  `claude-track-ardr-judge` (`.github/workflows/claude-track-ardr-judge.yml`) runs these from `main`, first attempt
  only, for the experiments its `experiment` input offers.

## 5. Receipts and timing

- Receipts are the FD-CT-92 row 1 witnesses (045b:276-285, :322-329): an annotated tag in the separate public
  repository signed with the registration-only SSH key, with a published GitHub release on it, and at least one
  Bitcoin-confirmed OpenTimestamps proof over the signed tag object (045b:307-310). Every required witness must be
  strictly earlier than the first observation, not only the earliest (045b:299-302).
- The first CONFIRMATORY observation starts no earlier than the latest witness time plus 24 hours plus a 6-hour
  margin (30 hours). The witness times are the release's `published_at` and each proof's block-header time. The
  receipt check's own rule stays at least 24 hours (045b:309-310, :326-327); the margin is this policy's, since a
  header time can run ahead of wall time.
- A run that starts before the proof's block time is not CONFIRMATORY, whatever the judge's git-time bound says
  (045b:1034).

## 6. Node B confirmation

- Before the registration the Founder reads Node B, and the registration file's `node_b` block records the read. A
  fee is an integer in the unit its key names (sat/kvB).
- `incrementalrelayfee` must equal Node A's 100 sat/kvB. A larger or different value stops the registration until A
  re-decides (the strictest of 045b:1182, :1183 and :1874).
- `getblockhash 975205` must equal 00000000000000000000a4b800a47aae4e800d1e0323de95244cd867968529f4, the seed block
  hash (045b:1901). Any difference stops the registration.
- `estimatesmartfee 2 CONSERVATIVE` and `estimatesmartfee 6 CONSERVATIVE` are recorded in sat/kvB and not compared.
- A fee given in another unit (a sat/vB value, bitcoind's BTC/kvB decimal, a fraction or a string) is refused, never
  converted (045b:1241, pair 7).

## 7. Observation completeness for the ARDR runs

- The judged set of an experiment is every completed `ardr CONFIRMATORY <experiment>` dispatch whose head is on
  `main`'s first-parent history. The judge's `experiment` command binds the run list to GitHub's dispatch listing
  (server times): a list that leaves out such a dispatch is refused (`RUN_LIST_INCOMPLETE`), and a listed run that is
  not in the listing as a completed run, or was created before the bound, is refused (`RUN_LIST_DISAGREES`)
  (045b:1034; `docs/claude-track/formats/ARDR_JUDGE_V1.md` section 20).
- This covers the scope of section 2 only. Observation completeness for XD-1 and P5-002 goes with the follow-up
  registration that registers each. Issue #110 stays a condition for Class E (045b:943-946).

## 8. Stopping, exclusion and re-dispatch

- Fixed N, no early stopping, no extension after seeing results. Excluded runs are counted and reported; exclusions
  above 10% of an experiment's runs make it NOT_ESTABLISHED (045b:571-574).
- The unit of a run and of an exclusion is 045b:546 as amended: an item-1 job that dies at gate `g` (045b:1083); the
  pool's outcome order (045b:1086); item 2's completed runs and its qualifying sample of 50 order-constrained runs
  fixed by run index (E13, 045b:1218).
- Each unit is dispatched once. Only a unit whose slice record shows it never started may be dispatched again; a unit
  with any recorded observation ends as PASS, FAIL or an exclusion, and an exclusion counts under the 10% rule
  (045b:576-580). A gate cut off by the runner's limit before collect counts as missing, never as a success
  (045b:1903).

## 9. Scope change

- A changed threshold is a new policy identity with its reason; results under the old one are kept, new confirmatory
  testing is needed, and an old failing run is never relabelled as a pass (045b:483-485).
- A budget record change that only raises BEAT caps is a disclosed operational change; the Founder approves its exact
  hash (045b:790-805). It needs its own receipt as a follow-up registration, with both witnesses strictly before the
  first broadcast under the new record (S7, 045b:1222).
- Any other change to the registered content (a pinned file, the scope, a driver change) is a new registration of
  the 045b:318-321 shape (045b:311-321).

## 10. What this file does not do

It records no Founder decision, grants no GO and holds no key, secret, credential or public repository name. The
receipts, their verification and the judgements are separate records.

## 11. Dated addition, 2026-11-12 (FD-CT-133)

- The Founder's decision FD-CT-133 (2026-11-12T00:06:51Z, finding #807;
  `docs/claude-track/decisions/FD-CT-133_2026-11-12.md`) takes ITEM2 out of this first registration. This
  registration holds ITEM1 and POOL only.
- Every mention of ITEM2 above, and of three experiments, applies to the follow-up registration that carries ITEM2
  with the fixed L0 ladder and a new seed: section 2's scope and dispatch inputs, and section 4's per-experiment lines.
- Under this registration the driver refuses an ITEM2 run (`EXPERIMENT_NOT_REGISTERED`). The registration tool refuses
  a first registration that lists ITEM2 (`ITEM2_IN_FIRST_REGISTRATION`).
- The frozen ARDR policy still lists ITEM2, and its bytes and hash are checked as before.
- The lines above are not edited.
