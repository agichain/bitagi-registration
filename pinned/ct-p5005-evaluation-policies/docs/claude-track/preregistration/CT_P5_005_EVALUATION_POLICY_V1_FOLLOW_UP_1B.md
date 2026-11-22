# CT-P5-005 evaluation policy, follow-up registration 1b (ARDR item 2)

**CT-P5-005 follow-up registration 1b (Claude plan). This file becomes registered content when the registration file that carries its SHA-256 (`evaluation_policy_sha256`) merges on `main`; from then on any change is a new file and a new follow-up registration.**

Work item: CT-P5-005 (ROADMAP row 9). Protocol impact: `NONE`. Class T development;
`release_authorization` NONE. Main source: the frozen 045b,
`docs/claude-track/plans/CT-P3-045b_PREREGISTRATION_DRAFT_EN.md`; `045b:N` is a line of that file as frozen by
PR #664 and pinned by this registration. "The first policy" is
`docs/claude-track/preregistration/CT_P5_005_EVALUATION_POLICY_V1_FIRST.md`. "The decision" is the Founder's
FD-CT-133, `docs/claude-track/decisions/FD-CT-133_2026-11-12.md`. "The seed note" is
`docs/claude-track/plans/notes/CT-P5-001_DRIVER_EN/2026-11-12_item2-follow-up-seed-provenance.md`. "The ITEM2
policy" is `docs/claude-track/preregistration/ARDR_POLICY_V1_CLASS_T_REGTEST_ITEM2_FOLLOW_UP.json`, and "the first
ARDR policy" is `docs/claude-track/preregistration/ARDR_POLICY_V1_CLASS_T_REGTEST_FIRST.json`.

```text
Status: NO PRODUCTION NETWORK ACTIVE · DO NOT ACTIVATE · Class P NO-GO · DO NOT GENESIS
Generation: D3.5 (Exact D3 Core unchanged)
release_authorization NONE. No Profile approval, signing, broadcast or GO authority.
This file is a Claude plan, not a Founder decision. It makes no Class E or Class P claim.
```

## 1. What the registration is

- The registration is the exact bytes of one file,
  `docs/claude-track/preregistration/CT_P5_005_REGISTRATION_V1_FOLLOW_UP_1B.json`. Its identity is the SHA-256 of
  those bytes; nothing is re-serialized before hashing (045b:288-291). That file and this one, whose SHA-256 it
  carries as `evaluation_policy_sha256`, are the evaluation policy of this follow-up registration (045b:289).
- It cites the first registration, `docs/claude-track/preregistration/CT_P5_005_REGISTRATION_V1_FIRST.json`, by
  `prior_registration_sha256`, the SHA-256 of that file's bytes (045b:319-320). It has its own receipts and needs
  one more Founder tag signature (045b:318-321). It does not change the first registration or follow-up
  registration 1.
- This file states rules only. Every SHA-256 is in the registration file (`prior_registration_sha256`,
  `pinned_files`, `ardr_policy_sha256`, `node_versions` and the `seed` block), which pins this file's own hash.
  This file carries none of them, no block hash, no seed and no commit id. The registration tool refuses a policy
  that carries the SHA-256 of a pinned file or of the first registration (`EVALUATION_POLICY_CARRIES_PIN`).
- The registration file is one JSON object of schema `BITAGI_CT_P5_005_REGISTRATION_V1_FOLLOW_UP_1B` in canonical
  bytes (sorted keys, two-space indent, ASCII, one LF at the end), at most 64 KiB. Its keys are a closed set of
  twelve: `schema`, `release_class`, `prior_registration_sha256`, `evaluation_policy_sha256`, `experiments`,
  `ardr_policy_sha256`, `pinned_files`, `registration_key_ed25519_fingerprint`, `node_versions`, `schemas`, `seed`
  and `node_b`. `experiments` is exactly `["ITEM2"]`, and `ardr_policy_sha256` has exactly one entry, the ITEM2
  policy's SHA-256. It has no `d2_2_tool_sha256`, `fee_trace`, `xd1` or `xd1_criteria` key.
- `tools/claude_track_p5005_registration.py check --scope FOLLOW_UP_1B --final` recomputes every SHA-256 from the
  tree at the registration commit and refuses any other bytes. The first registration must be in the tree as strict
  JSON with the first registration's schema and no marker word. Last, in a separate `python3 -B -I` process run in
  the tree, it calls the tree's own readers:
  1. the ARDR driver's `load_policy` in CONFIRMATORY must take ITEM2 under the ITEM2 policy, with the registration
     file's SHA-256, the policy's SHA-256 and seed and the p_0 rule of section 2 (`DRIVER_REFUSES_REGISTRATION`);
  2. the same call must refuse every other experiment the driver knows, ITEM1 and POOL among them, with
     `EXPERIMENT_NOT_REGISTERED` (`DRIVER_RUNS_UNREGISTERED_EXPERIMENT`), and must refuse the first ARDR policy
     under the registration file with `POLICY_NOT_REGISTERED` (`DRIVER_TAKES_UNREGISTERED_POLICY`);
  3. the judge's `parse_registration` must list the ITEM2 policy, its `registered_experiment` must take ITEM2 and
     refuse every other experiment the judge knows, and its `parse_item2_policy` in CONFIRMATORY must accept the
     policy with the judge's own run count (`JUDGE_REFUSES_REGISTRATION`,
     `JUDGE_JUDGES_UNREGISTERED_EXPERIMENT`).
- Each confirmatory observation cites the `registration_sha256` it is evaluated under and carries its start time
  (045b:297-298). Every raw-log line of a CONFIRMATORY ARDR run carries it, and the driver refuses registration
  bytes whose SHA-256 differs from the one given (`REGISTRATION_BYTES_CHANGED`).
- Release class: CLASS_T. The experiment is Class T Regtest (045b:361-362). Class E freezes stay refused until
  045b section 10 item 7 holds: CR-20, the time-authentication method, the public channel, and issue #110 closed
  (045b:943-946). The receipt identity binds CLASS_T.

## 2. Scope

- This registration holds ARDR item 2 only: experiment ITEM2 of the ITEM2 policy. That policy lists ITEM2 and
  nothing else: 200 runs of one contested gate each, `r` = 0 to 199 (045b:546), `b` 6,000, `H0` 1,000, the miner
  policy `ITEM2_DEFAULT`, and the L0 project bidder in seat 1 with 24 attempts, `CONTINUE_WITHIN_LIMITS` and the
  Class T L0 budget record (045b:1053, :1901).
- Why it is a separate registration. The decision took ITEM2 out of the first registration (finding #807): the
  frozen design's L0 ladder stopped below the fee cap. The ladder is fixed for a reason that does not depend on any
  seed, the design is fixed first, and the seed comes from a block mined after it (the decision, section 2, (1) to
  (4); the first policy, section 11).
- **The L0 p_0 rule.** Under this registration L0's rung-0 feerate `p_0` is the largest integer `p_0` with
  `2b ≤ p_0 ≤ 4b` whose 045b:537 ladder has exactly two rungs, counted at `i` = 0 and `v` = 213. Its rule name in
  the policy, the driver and the judge is `MAX_P0_TWO_RUNGS`. For `b` = 6,000 it is 16,000 sat/kvB, and the L0 set
  is [3,408, 5,112] sat: rung 1 is the cap fee. This replaces, for ITEM2 under this registration, the
  `p_0 = ⌈2.5 × b⌉` of 045b:1053 and the `p0_rule` `CEIL_2_5_B` of 045b:1053 and :1901, whose set was
  [3,195, 4,793] sat. 045b's bytes are not edited. Nothing else of the ladder changes: the 045b:537 formula, the
  cap `4b`, the rule that a rung above the cap is left out, and the release schedule are the same for every seat.
- **Thresholds.** They are 045b's, unchanged: section 4.3 item 2 (045b:381, with E13 at :1218) and the section 4.5
  rows measured on the item-2 campaign (045b:498-502), among them the 25% of 045b:499 (FD-CT-92 row 8; the
  decision, section 2, (6)). 045b is their one source. The changed p_0 rule is a changed design, so this is a new
  policy identity with its reason (045b:483-485); no result under the old design is relabelled.
- Not in this registration:
  - ITEM1 and POOL: they stay under the first registration. The driver refuses them under the registration file.
  - Follow-up registration 1's content (XD-1, P5-003, P5-004, the incident V1 verifier).
  - Still for later follow-up registrations: the P5-002 rules, commands and capture and retention list, and ARDR
    items 3 and 4 and ITEM3W (the first policy, section 2). A part that is ready does not wait for another.
- Runs before this registration's receipts are EXPLORATORY and are not evidence under it. No ITEM2 run under the
  first ARDR policy, with the old ladder or the first seed, is judged under this registration.

## 3. Pinned content

- `pinned_files` is a closed set of 24 files, each by path and SHA-256 recomputed from the tree:
  - the ITEM2 policy, with its seed;
  - the Class T L0 budget record (the ITEM2 policy's `l0_seat.budget_sha256`, 045b:1898);
  - the seed note, with the block hash and the seed added (section 6);
  - the decision file;
  - frozen 045b and its `b6000fz` request and result notes, the freeze-time planner run at `b` = 6,000
    (045b:1902);
  - the ARDR tools the runs and the judgement use: the driver, the judge, the slices tool and every tools module
    in their import closure, thirteen files (`TOOL_CLOSURE_NOT_PINNED` otherwise);
  - the campaign and judge workflows;
  - the two ARDR format documents for the run and the judgement, `ARDR_RUN_V1.md` and `ARDR_JUDGE_V1.md`. The
    first holds the text of the p_0 rule.
- Twenty-one of these files are also pinned by the first registration.
- The registration tool checks the ITEM2 policy itself: its experiments are exactly ITEM2, its L0 budget hash is
  the pinned record's, its `p0_rule` is `MAX_P0_TWO_RUNGS` and so is the pinned driver's `L0_P0_RULE`
  (`L0_P0_RULE`), and its bytes with the seed put back to `PENDING_FREEZE` are the bytes fixed before the seed
  block (`POLICY_NOT_P2`, section 6).
- It also records values that are not repository files: the Bitcoin Core 31.1 and 30.3 archive and `bitcoind`
  values as the campaign workflow pins them; five schema names (the policy's, the L0 budget record's, the raw
  log's, the collection's and the observation list's); and the seed provenance (section 6).
- `registration_key_ed25519_fingerprint`: the same registration-only key as the first registration, in ssh-keygen
  `SHA256:` form. The tool takes it from the first registration in the tree and refuses any other
  (`KEY_FINGERPRINT_NOT_PRIOR`). The public repository's owner and name are not written in this repository
  (045b:1185).
- 045b, the seed note and the decision file stay byte for byte as pinned from the registration to the ITEM2
  verdict. Corrections in that interval go in decision records, not in those files. A change to a pinned tool,
  workflow or format document before the verdict needs a new registration (section 10).

## 4. Runs and their commands

- The driver commit used for the confirmatory runs and A's judge are on `main` before the registration. A driver
  change after it needs a new registration (045b:311-316); so does a change of the run's start margin (045b:1903).
- From the registration to the verdict, `main` changes only by a merge commit or a squash merge. Otherwise the
  verdict record names that commit (045b:1031).
- Units: the 200 runs `r` = 0 to 199 of one gate each. Even `r` is private present; `r` = 0, 2, …, 98 are the 50
  order-constrained runs (045b:546, :1218).
- Dispatch: the campaign workflow `claude-track-ardr` (`.github/workflows/claude-track-ardr.yml`), dispatched by A
  from `main`, first attempt only, run name `ardr CONFIRMATORY ITEM2`. Inputs: `experiment` ITEM2, `mode`
  CONFIRMATORY, the unit range and slice inputs, `policy` the ITEM2 policy's path, `registration` this
  registration file's path in that commit, `registration_sha256` its SHA-256, and `s04_run_id`. Its jobs are
  `plan` (`tools/claude_track_ardr_slices.py plan`), `slice` (the driver's `run`, one unit at a time, with the L0
  project seat) and `collect`. A `RECOLLECT` dispatch is collect-only recovery of one CONFIRMATORY dispatch.
- The unit range is `unit_first` 0 and `unit_last` 199. The slice inputs (`units_per_slice`, `unit_minutes`) split
  the 200 units over slice jobs and change no unit's content. They are part of the run command the registration
  fixes (045b:311-316): A fixes them before the registration and writes them in the registration pull request, as
  for the first registration. The pinned slices tool's own limits bound them.
- Judgement: A's judge `tools/claude_track_ardr_judge.py` in mode CONFIRMATORY with this registration: per run
  `item2`, then `experiment --experiment ITEM2` over every completed dispatch of the experiment whose head is on
  `main`'s first-parent history (045b:1034). The judge workflow `claude-track-ardr-judge`
  (`.github/workflows/claude-track-ardr-judge.yml`) runs these from `main`, first attempt only, with `experiment`
  ITEM2, `mode` CONFIRMATORY and `registration` the registration file's path.

## 5. Receipts and timing

- Receipts are the FD-CT-92 row 1 witnesses (045b:276-285, :322-329): an annotated tag in the separate public
  repository signed with the registration-only SSH key, with a published GitHub release on it, and at least one
  Bitcoin-confirmed OpenTimestamps proof over the signed tag object (045b:307-310). Every required witness must be
  strictly earlier than the first observation, not only the earliest (045b:299-302).
- The first CONFIRMATORY ITEM2 observation starts no earlier than the latest witness time plus 24 hours plus a
  6-hour margin (30 hours). The witness times are the release's `published_at` and each proof's block-header time.
  The receipt check's own rule stays at least 24 hours (045b:309-310, :326-327). Every follow-up registration uses
  the same 30-hour lead (the first policy, section 5).
- A run that starts before the proof's block time is not CONFIRMATORY, whatever the judge's git-time bound says
  (045b:1034).

## 6. The seed and the node reads

- **Rule.** The seed rule is 045b:1901's, unchanged: seed = SHA-256(ASCII `BITAGI_CT_ARDR_SEED_V1` ‖ 0x00 ‖ P2 ‖
  H2). P2 is the 32-byte SHA-256 of the ITEM2 policy with the seed `PENDING_FREEZE`. H2 is the 32 bytes of the
  `getblockhash` display hex of Bitcoin mainnet height H_s2 = 976,000.
- **Order.** P2 was on `main` and H_s2 was named before block 976,000 existed (the seed note, sections 1 and 2;
  the pull request that added P2 is #832, merged 2026-11-12T11:58:37Z). So the seed cannot be chosen. The seed
  value is the only change to the ITEM2 policy after P2.
- **Reads.** When Node A's tip is at least 976,002, the Founder reads `getblockhash 976000` and that block's
  header `time` on Node A and on Node B. The registration records Node A's read in `seed` (`block_hash`,
  `block_header_time`, with `block_height`, `policy_pending_freeze_sha256` and `seed`) and Node B's in `node_b`
  (`getblockhash_976000`, `getblockheader_976000_time`). The time is the integer `time` of the block header, in
  seconds; any other form is refused, never converted.
- **Stop conditions.** The two hashes must be equal, and so must the two times. The header time must be later than
  the merge of the pull request that added P2. If either fails, the seed step stops until A re-decides (the seed
  note, section 3). The registration tool refuses such a file (`NODE_B_SEED_BLOCK_HASH`, `NODE_B_SEED_BLOCK_TIME`,
  `SEED_BLOCK_NOT_AFTER_POLICY`).
- The header time is not an input of the seed.
- The registration tool recomputes the seed from P2 and the recorded block hash, requires the ITEM2 policy to
  carry that seed, and requires P2, the block hash and the seed to be written in the pinned seed note (`SEED`,
  `SEED_NOT_IN_NOTE`).

## 7. Observation completeness

- The judged set is every completed `ardr CONFIRMATORY ITEM2` dispatch whose head is on `main`'s first-parent
  history. The judge's `experiment` command binds the run list to GitHub's dispatch listing (server times): a list
  that leaves out such a dispatch is refused (`RUN_LIST_INCOMPLETE`), and a listed run that is not in the listing
  as a completed run, or was created before the bound, is refused (`RUN_LIST_DISAGREES`) (045b:1034;
  `docs/claude-track/formats/ARDR_JUDGE_V1.md` section 20).
- This covers ITEM2 only. Issue #110 stays a condition for Class E (045b:943-946).

## 8. Stopping, exclusion and re-dispatch

- Fixed N of 200, no early stopping, no extension after seeing results (045b:571-574).
- A run is completed when it ends OBSERVED. Missing and EXCLUDED runs are counted and reported. Item 2's gate
  exclusion codes `RELEASE_NOT_IN_TEMPLATE`, `RELEASE_AFTER_G`, `G_LATE` and `REPLACED_RUNG_NOT_IN_MEMPOOL` count
  as exclusions (045b:381, correction of 2026-11-02).
- Item 2 is NOT_ESTABLISHED when more than 10% of its 200 runs are missing or EXCLUDED, that is 21 or more. The
  045b:381 statistic is NOT_ESTABLISHED when more than 5 of the 50 qualifying runs are missing or EXCLUDED. The
  qualifying sample is fixed by run index, never chosen by results, and its statistic uses its OBSERVED runs
  (E13, 045b:1218).
- For a statistic, NOT_ESTABLISHED comes before NO-GO; neither gives GO (045b:1218).
- Each unit is dispatched once. Only a unit whose slice record shows it never started may be dispatched again; a
  unit with any recorded observation ends as PASS, FAIL or an exclusion, and an exclusion counts under the 10%
  rule (045b:576-580). A gate cut off by the runner's limit before collect counts as missing, never as a success
  (045b:1903).

## 9. Model statements made before data

These are statements of a model, made before any CONFIRMATORY ITEM2 observation exists. They are not thresholds
and not criteria. The judge's verdict comes from the collected data and 045b's thresholds only. A difference
between data and model is reported and changes no verdict.

- **Model.** The tree's own draw functions, gate interval, release schedule and 045b:537 ladder, with `b` 6,000,
  `v` 213 and `i` 100, L0 in seat 1. Block G holds each seat's last released rung, and the gate goes to the highest
  fee. An equal top is decided by txid in the runs, which the model does not know, so each figure is given as a
  range over both ways of deciding it where the two differ.
- **Seeds.** 2,000 fresh seeds, seed_s = SHA-256(ASCII `BITAGI_CT_807_L0FIX_FRESH_SEEDS_V1` ‖ 0x00 ‖ u32be(s)),
  s = 0 to 1,999. The first registration's seed was not used to choose the design, and no figure here uses it or
  this registration's seed.
- **L0 losing share (the 045b:499 row).** The share of a seed's 200 runs in which another seat's last released
  rung pays more than L0's:

| Ladder | Mean | Median | 5th percentile | 95th percentile | Maximum | Seeds above 25% |
|---|---|---|---|---|---|---|
| fixed, [3,408, 5,112] sat | 4.5% to 4.8% | 4.5% | 2.0% to 2.5% | 7.0% to 7.5% | 10.0% to 10.5% | none |
| old, [3,195, 4,793] sat | 59.9% to 60.0% | 60.0% | 54.0% | 65.5% | 71.0% | all |

- **Power of the 045b:381 rule.** The probability that the private bidder wins more than 25 of the 50
  order-constrained runs, when an order bias is planted in the miner. FAIR: no bias. TIE: the private candidate
  wins every equal top. BONUS k: the private candidate is ordered as if it paid k times its fee. FIRST: the
  private candidate is always first. Each cell is the mean private share and the power:

| Bias | Old ladder | Fixed ladder |
|---|---|---|
| FAIR | 0.116 / 0.000 | 0.000 / 0.000 |
| TIE | 0.116 / 0.000 | 0.001 / 0.000 |
| BONUS 1.10 | 0.342 / 0.008 to 0.009 | 0.236 / 0.000 |
| BONUS 1.20 | 0.483 / 0.350 | 0.423 / 0.107 to 0.108 |
| BONUS 1.25 | 0.535 / 0.637 | 0.476 / 0.316 |
| BONUS 1.30 | 0.628 / 0.958 | 0.524 / 0.583 |
| BONUS 1.35 | 0.737 / 1.000 | 0.594 / 0.892 |
| BONUS 1.40 | 0.844 / 1.000 | 0.704 / 0.997 |
| BONUS 1.50 | 0.911 / 1.000 | 0.904 / 1.000 |
| FIRST | 1.000 / 1.000 | 1.000 / 1.000 |

- **What the model says.** Without a bias the rule gives no false NO-GO under either ladder. A large bias (FIRST,
  k of 1.4 or more) is caught under both. The fixed ladder lowers the power only for k between about 1.15 and
  1.35. A bias that acts only on an equal top is not caught under either ladder, since equal tops are rare. The
  0.5 limit of 045b:381 is the Founder's (FD-CT-92 row 8) and is not changed.
- **What the model does not cover.** A node whose template timing differs from the schedule, for example frequent
  `RELEASE_NOT_IN_TEMPLATE`; and a bias that acts on inclusion or timing instead of order.
- **The registered seed.** After this registration merges and before the first CONFIRMATORY ITEM2 dispatch, A posts
  on finding #807 the model's figures for the registered seed: the runs whose `t_G` is shorter than L0's rung-0
  release, their count among the 50 qualifying runs, and the L0 losing count. They too are a model's statements,
  not criteria.
- The old design's prediction, 129 of 200 runs lost under the first seed (64.5%), stays on finding #807 as it was
  published and is not rewritten (the decision, section 2, (5)).

## 10. Scope change

- A changed threshold is a new policy identity with its reason; results under the old one are kept, new
  confirmatory testing is needed, and an old failing run is never relabelled as a pass (045b:483-485).
- A budget record change that only raises BEAT caps is a disclosed operational change; the Founder approves its
  exact hash (045b:790-805). The fixed ladder stays inside the Class T L0 record, so that record is unchanged here.
- Any other change to the registered content (a pinned file, the ITEM2 policy or its seed, the scope, a driver or
  judge change) is a new registration of the 045b:318-321 shape (045b:311-321).

## 11. What this file does not do

It records no Founder decision, grants no GO and holds no key, secret, credential, public repository name, block
hash, seed or commit id. The receipts, their verification and the judgement are separate records.
