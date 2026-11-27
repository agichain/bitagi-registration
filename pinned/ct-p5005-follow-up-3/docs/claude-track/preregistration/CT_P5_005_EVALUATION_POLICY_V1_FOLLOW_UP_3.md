# CT-P5-005 evaluation policy, follow-up registration 3 (ARDR item 4)

**CT-P5-005 follow-up registration 3 (Claude plan). This file becomes registered content when the registration file that carries its SHA-256 (`evaluation_policy_sha256`) merges on `main`; from then on any change is a new file and a new follow-up registration.**

Work item: CT-P5-005 (ROADMAP row 9). Protocol impact: `NONE`. Class T development;
`release_authorization` NONE. Main source: the frozen 045b,
`docs/claude-track/plans/CT-P3-045b_PREREGISTRATION_DRAFT_EN.md`; `045b:N` is a line of that file as frozen by
PR #664 and pinned by this registration. "The first policy" is
`docs/claude-track/preregistration/CT_P5_005_EVALUATION_POLICY_V1_FIRST.md`. "The decision" is the Founder's
FD-CT-133, `docs/claude-track/decisions/FD-CT-133_2026-11-12.md`. "A's scope decision" is A's post on #258
(issuecomment-7149229274), a Claude decision. "The seed note" is
`docs/claude-track/plans/notes/CT-P5-001_DRIVER_EN/2026-11-25_item4-follow-up-seed-provenance.md`. "The item-4
policy" is `docs/claude-track/preregistration/ARDR_POLICY_V1_CLASS_T_REGTEST_ITEM4_FOLLOW_UP.json`, "the first ARDR
policy" is `docs/claude-track/preregistration/ARDR_POLICY_V1_CLASS_T_REGTEST_FIRST.json`, and "the ITEM2 policy" is
`docs/claude-track/preregistration/ARDR_POLICY_V1_CLASS_T_REGTEST_ITEM2_FOLLOW_UP.json`. "The inventory" is
`docs/claude-track/plans/CT-P5-001_INVENTORY_EN.md`. `<S>` stands for each of the four sub-scenarios: `SELF_DEALING`,
`FEE_ASYMMETRY`, `CENSORSHIP` and `REORG`.

```text
Status: NO PRODUCTION NETWORK ACTIVE · DO NOT ACTIVATE · Class P NO-GO · DO NOT GENESIS
Generation: D3.5 (Exact D3 Core unchanged)
release_authorization NONE. No Profile approval, signing, broadcast or GO authority.
This file is a Claude plan, not a Founder decision. It makes no Class E or Class P claim.
```

## 1. What the registration is

- The registration is the exact bytes of one file,
  `docs/claude-track/preregistration/CT_P5_005_REGISTRATION_V1_FOLLOW_UP_3.json`. Its identity is the SHA-256 of
  those bytes; nothing is re-serialized before hashing (045b:288-291). That file and this one, whose SHA-256 it
  carries as `evaluation_policy_sha256`, are the evaluation policy of this follow-up registration (045b:289).
- It cites the first registration, `docs/claude-track/preregistration/CT_P5_005_REGISTRATION_V1_FIRST.json`, by
  `prior_registration_sha256`, the SHA-256 of that file's bytes (045b:319-320). It has its own receipts and needs
  one more Founder tag signature (045b:318-321). It does not change the first registration or follow-up
  registrations 1, 1b and 2.
- This file states rules only. Every SHA-256 is in the registration file (`prior_registration_sha256`,
  `pinned_files`, `ardr_policy_sha256`, `node_versions` and the `seed` block), which pins this file's own hash.
  This file carries none of them, no block hash, no seed and no commit id. The registration tool refuses a policy
  that carries the SHA-256 of a pinned file or of the first registration (`EVALUATION_POLICY_CARRIES_PIN`).
- The registration file is one JSON object of schema `BITAGI_CT_P5_005_REGISTRATION_V1_FOLLOW_UP_3` in canonical
  bytes (sorted keys, two-space indent, ASCII, one LF at the end), at most 64 KiB. Its keys are a closed set of
  twelve: `schema`, `release_class`, `prior_registration_sha256`, `evaluation_policy_sha256`, `experiments`,
  `ardr_policy_sha256`, `pinned_files`, `registration_key_ed25519_fingerprint`, `node_versions`, `schemas`, `seed`
  and `node_b`. `experiments` is exactly `["ITEM4_SELF_DEALING", "ITEM4_FEE_ASYMMETRY", "ITEM4_CENSORSHIP",
  "ITEM4_REORG"]`, the driver's order, and `ardr_policy_sha256` has exactly one entry, the item-4 policy's SHA-256.
  It has no `d2_2_tool_sha256`, `fee_trace`, `xd1`, `xd1_criteria` or `p5002` key.
- `tools/claude_track_p5005_registration.py check --scope FOLLOW_UP_3 --final` recomputes every SHA-256 from the
  tree at the registration commit and refuses any other bytes. The first registration must be in the tree as strict
  JSON with the first registration's schema and no marker word. Last, in a separate `python3 -B -I` process run in
  the tree, it calls the tree's own readers and the tree's item-4 planner:
  1. the ARDR driver's `load_policy` in CONFIRMATORY must take each of the four sub-scenarios under the item-4
     policy, with the registration file's SHA-256, the policy's SHA-256 and seed and the p_0 rule of section 2
     (`DRIVER_REFUSES_REGISTRATION`);
  2. the same call must refuse every other experiment the driver knows, ITEM1, ITEM2, ITEM3 and POOL among them,
     with `EXPERIMENT_NOT_REGISTERED` (`DRIVER_RUNS_UNREGISTERED_EXPERIMENT`); with the registration file, it must
     also refuse each of the four under the first ARDR policy and under the ITEM2 policy with
     `POLICY_NOT_REGISTERED` (`DRIVER_TAKES_UNREGISTERED_POLICY`);
  3. the judge's `parse_registration` must list the item-4 policy, its `registered_experiment` must take the four
     and refuse every other experiment the judge knows, and its `parse_item4_policy` in CONFIRMATORY must accept the
     policy for each of the four with the judge's own run count (`JUDGE_REFUSES_REGISTRATION`,
     `JUDGE_JUDGES_UNREGISTERED_EXPERIMENT`);
  4. the item-4 planner's `plan_run` in CONFIRMATORY with the L0 seat must accept every registered run, `r` = 0 to
     49 of each of the four, with the policy's params and seed (`PLANNER_REFUSES_REGISTERED_RUN`). ITEM4_REORG is
     among them, so the pinned tools take a CONFIRMATORY reorg run with the TEST_ONLY release of section 2.
- Each confirmatory observation cites the `registration_sha256` it is evaluated under and carries its start time
  (045b:297-298). Every raw-log line of a CONFIRMATORY ARDR run carries it, and the driver refuses registration
  bytes whose SHA-256 differs from the one given (`REGISTRATION_BYTES_CHANGED`).
- Release class: CLASS_T. The experiment is Class T Regtest (045b:361-362). Class E freezes stay refused until
  045b section 10 item 7 holds: CR-20, the time-authentication method, the public channel, and issue #110 closed
  (045b:943-946). The receipt identity binds CLASS_T.

## 2. Scope

- This registration holds ARDR item 4 only: the experiments ITEM4_SELF_DEALING, ITEM4_FEE_ASYMMETRY,
  ITEM4_CENSORSHIP and ITEM4_REORG of the item-4 policy, which lists these four and nothing else. Each is 50 runs of
  one gate, `r` = 0 to 49 (045b:524, :1250), with `b` 6,000 and `H0` 1,000 (045b:1901, :1054), its pinned miner
  policy (`ITEM4_SELF_FIRST_ZERO_FEE`, `ITEM2_DEFAULT`, `ITEM4_CENSOR_144` and `ITEM4_REORG_REPLACE`, in the order
  above), and the L0 project bidder in the project seat with 24 attempts, `CONTINUE_WITHIN_LIMITS` and the Class T L0
  budget record (045b:1053, :1068, :1898; item 4's L0 keys come with this policy, :1194). The project seat is S1 in
  self dealing and fee asymmetry and S0 in censorship and reorg (045b:1219).
- Why it is a separate registration. Items 3 and 4 go in a follow-up registration by default (045b:316-321), and the
  first policy leaves the grouping of follow-up registrations open: a part that is ready does not wait for another
  (the first policy, section 2). A's scope decision gives item 4 a registration of its own. The four sub-scenarios
  share one policy and one registration because item 4's outcome reads the four records together and refuses records
  of two policies or two registrations (`RECORD_BINDING`, `docs/claude-track/formats/ARDR_JUDGE_V1.md` section 25).
- **Item 4's DRAFT values are fixed here.** 045b left factor 10 and item 4's other DRAFT values to item 4's own
  follow-up registration (045b:1078, :1079; F15, :1198). They are constants of the pinned tools, and this
  registration fixes them by pinning those tools:
  - the asymmetric bidder pays 10 × the median honest feerate (F15, 045b:541, :1078). The median is the nearest-rank
    p50 of the honest four's rung-0 feerates, from L0's configured `p_0` and the drawn `BID_FEE_2` … `BID_FEE_4`
    (045b:1076, :1078);
  - the self REGISTER pays 600 sat, the product floor, below every honest rung 0 in G; the project's rung-0 fee must
    be above it (045b:1065), so `b` is at least 1,058 under the p_0 rule below (1,127 under 045b's old rule);
  - the project seat's `p_0` is L0's, by the rule below;
  - the censorship and reorg competitor pays 2 × the stand-in's rung-0 fee + 1 at the same vsize (045b:1079);
  - an asymmetric fee above 90,000 sat is refused before any node (`ITEM4_ASYMMETRIC_FEE_CAP`, 045b:1079);
  - the censorship window is G … G + 143, 144 blocks set by G's height, lifted at G + 144 (045b:1079);
  - the reorg depth is 1 for even `r` and 2 for odd `r`; a depth-d run replaces d blocks from G with a chain of
    d + 1 blocks (045b:1070), none of which may hold a txid of the winner's set or any spend of its funding outpoint
    (`ITEM4_WINNER_READDED`, 045b:1079);
  - before it invalidates G, the reorg waits 6 seconds after G's template answer (the planner's template cache
    wait).
- **The L0 p_0 rule.** Under this registration L0's rung-0 feerate `p_0` in every item-4 sub-scenario is the
  largest integer `p_0` with `2b ≤ p_0 ≤ 4b` whose 045b:537 ladder has exactly two rungs, counted at `i` = 0 and
  `v` = 213. Its rule name in the policy, the driver and the judge is `MAX_P0_TWO_RUNGS` (the decision, section 2,
  which fixed the ladder, and A's design under it, section 3; follow-up registration 1b states the same rule for
  ITEM2). For `b` = 6,000 it is 16,000 sat/kvB, and the L0 set is [3,408, 5,112] sat. The project seat's configured
  `p_0`, which the self-dealing fee check and the fee-asymmetry median use, is the same value from the same source.
  This replaces, for item 4 under this registration, the `p_0 = ⌈2.5 × b⌉` of 045b:1053 and :1079 and the `p0_rule`
  `CEIL_2_5_B` of 045b:1053 and :1901. 045b's bytes are not edited.
- **The TEST_ONLY Reorg67 release.** A CONFIRMATORY ITEM4_REORG run with the L0 seat uses the TEST_ONLY release
  `RELEASE_REORG67_TEST_ONLY` (step 6 not performed), with its mark in the raw log; the judge report labels the row
  "release: Class T test step" and says "the release is a Class T test step" (045b:1067, :1068, :1069). The row is
  evidence for item 4's labels after a release, never for the TDS 6.7 release path, which the product does not have
  for this lock (#446, open). When that path merges, the row is run again under a new registration, and the result
  under this registration is not upgraded (045b:1069).
- **Not run.** Every item-4 run logs the cases it does not cover, and they are listed as not run (045b:383, :1066,
  :1067): `Done:Born{late, at_opening: false}` in censorship (the synthetic competitor holds G in every run);
  `ITEM4_SELF_ZERO_FEE_REGISTER` in self dealing (the product signer does not sign a zero-fee REGISTER, so the self
  REGISTER pays the 600-sat floor); and in the L0 runs E7, `Stale{reorged_before_inclusion: true}` and then
  `IncludedNoEffect` (no item-4 miner policy reorgs a released rung out before its inclusion). A case not run is no
  evidence either way.
- **Thresholds.** They are 045b's, unchanged: section 4.3 item 4 (045b:383, with :1065-1070 and :1084), the section
  4.5 rows judged as item 4 (045b:505-506), and the minimum transitions of each sub-scenario that the inventory's
  section 2 lists (045b:1279 and its dated line). 045b is their one source. The changed p_0 rule is a changed design,
  so this is a new policy identity with its reason (045b:483-485); no item-4 result is relabelled.
- Not in this registration:
  - ITEM1 and POOL stay under the first registration and ITEM2 under follow-up registration 1b. The driver refuses
    them under the registration file, and so does the judge.
  - ARDR item 3 and ITEM3W, for a later follow-up registration (the first policy, section 2).
  - Follow-up registration 1's and 2's content (XD-1, P5-003, P5-004, the incident V1 verifier, P5-002).
- Runs before this registration's receipts are EXPLORATORY and are not evidence under it. No item-4 run under any
  other policy or seed is judged under this registration.

## 3. Pinned content

- `pinned_files` is a closed set of 25 files, each by path and SHA-256 recomputed from the tree:
  - the item-4 policy, with its seed;
  - the Class T L0 budget record (each sub-scenario's `l0_seat.budget_sha256`, 045b:1898);
  - the seed note, with the block hash and the seed added (section 6);
  - the decision file;
  - frozen 045b and its `b6000fz` request and result notes, the freeze-time planner run at `b` = 6,000
    (045b:1902);
  - the inventory, whose section 2 is the minimum transition list (045b:1279, dated line);
  - the ARDR tools the runs and the judgement use: the driver, the judge, the slices tool, the item-4 planner and
    every tools module in their import closure, thirteen files (`TOOL_CLOSURE_NOT_PINNED` otherwise);
  - the campaign and judge workflows;
  - the two ARDR format documents for the run and the judgement, `ARDR_RUN_V1.md` and `ARDR_JUDGE_V1.md`. The
    first holds the text of the p_0 rule.
- Twenty-two of these files are also pinned by the first registration, and twenty-two by follow-up registration 1b.
- The registration tool checks the item-4 policy itself: its experiments are exactly the four, each one's L0 budget
  hash is the pinned record's, each one's `p0_rule` is `MAX_P0_TWO_RUNGS` and so is the pinned driver's
  `L0_P0_RULE` (`L0_P0_RULE`), and its bytes with the seed put back to `PENDING_FREEZE` are the bytes fixed before
  the seed block (`POLICY_NOT_P3`, section 6).
- It also records values that are not repository files: the Bitcoin Core 31.1 and 30.3 archive and `bitcoind`
  values as the campaign workflow pins them; five schema names (the policy's, the L0 budget record's, the raw
  log's, the collection's and the observation list's); and the seed provenance (section 6).
- `registration_key_ed25519_fingerprint`: the same registration-only key as the first registration, in ssh-keygen
  `SHA256:` form. The tool takes it from the first registration in the tree and refuses any other
  (`KEY_FINGERPRINT_NOT_PRIOR`). The public repository's owner and name are not written in this repository
  (045b:1185).
- 045b, the inventory, the seed note and the decision file stay byte for byte as pinned from the registration to
  item 4's verdict. Corrections in that interval go in decision records, not in those files. A change to a pinned
  tool, workflow or format document before the verdict needs a new registration (section 10).

## 4. Runs and their commands

- The driver commit used for the confirmatory runs and A's judge are on `main` before the registration. A driver
  change after it needs a new registration (045b:311-316); so does a change of the run's start margin (045b:1903).
- From the registration to the verdict, `main` changes only by a merge commit or a squash merge. Otherwise the
  verdict record names that commit (045b:1031).
- Units: for each sub-scenario, the 50 runs `r` = 0 to 49 of one gate each; the unit is the run (045b:524, :1084).
  ITEM4_REORG's even `r` are depth 1 and its odd `r` depth 2 (045b:1070).
- Dispatch: the campaign workflow `claude-track-ardr` (`.github/workflows/claude-track-ardr.yml`), dispatched by A
  from `main`, first attempt only, one dispatch per sub-scenario, run name `ardr CONFIRMATORY ITEM4_<S>`. Inputs:
  `experiment` ITEM4_<S>, `mode` CONFIRMATORY, the unit range and slice inputs, `policy` the item-4 policy's path,
  `registration` the registration file's path in that commit, `registration_sha256` its SHA-256, and `s04_run_id`.
  Its jobs are `plan` (`tools/claude_track_ardr_slices.py plan`), `slice` (the driver's `run`, one unit at a time,
  with the L0 project seat, after the slice builds the L0 host worker and the offline signer) and `collect`. A
  `RECOLLECT` dispatch is collect-only recovery of one CONFIRMATORY dispatch.
- The unit range is `unit_first` 0 and `unit_last` 49 for each sub-scenario. The slice inputs (`units_per_slice`,
  `unit_minutes`) split the 50 units over slice jobs and change no unit's content. They are part of the run command
  the registration fixes (045b:311-316): A fixes them before the registration and writes them in the registration
  pull request, as for the first registration and follow-up registration 1b. The pinned slices tool's own limits
  bound them.
- Judgement: A's judge `tools/claude_track_ardr_judge.py` in mode CONFIRMATORY with this registration, per
  sub-scenario: per run `item4`, then `experiment --experiment ITEM4_<S>` over every completed dispatch of that
  sub-scenario whose head is on `main`'s first-parent history (045b:1034). The judge workflow
  `claude-track-ardr-judge` (`.github/workflows/claude-track-ardr-judge.yml`) runs these from `main`, first attempt
  only, with `experiment` ITEM4_<S>, `mode` CONFIRMATORY and `registration` the registration file's path; one judge
  dispatch judges one sub-scenario.
- Item 4's outcome: the pinned judge's `item4-outcome --mode CONFIRMATORY` over the four sub-scenarios' `experiment`
  records. It is not in the judge workflow; it is a separate call of the same judge file (`RECORD_TOOL`), and the
  records must share one policy and one registration (`RECORD_BINDING`; `docs/claude-track/formats/ARDR_JUDGE_V1.md`
  sections 25 and 27).

## 5. Receipts and timing

- Receipts are the FD-CT-92 row 1 witnesses (045b:276-285, :322-329): an annotated tag in the separate public
  repository signed with the registration-only SSH key, with a published GitHub release on it, and at least one
  Bitcoin-confirmed OpenTimestamps proof over the signed tag object (045b:307-310). Every required witness must be
  strictly earlier than the first observation, not only the earliest (045b:299-302).
- The first CONFIRMATORY observation of any item-4 sub-scenario starts no earlier than the latest witness time plus
  24 hours plus a 6-hour margin (30 hours). The witness times are the release's `published_at` and each proof's
  block-header time. The receipt check's own rule stays at least 24 hours (045b:309-310, :326-327). Every follow-up
  registration uses the same 30-hour lead (the first policy, section 5).
- A run that starts before the proof's block time is not CONFIRMATORY, whatever the judge's git-time bound says
  (045b:1034).

## 6. The seed and the node reads

- **Rule.** The seed rule is 045b:1901's, unchanged: seed = SHA-256(ASCII `BITAGI_CT_ARDR_SEED_V1` ‖ 0x00 ‖ P3 ‖
  H3). P3 is the 32-byte SHA-256 of the item-4 policy with the seed `PENDING_FREEZE`. H3 is the 32 bytes of the
  `getblockhash` display hex of Bitcoin mainnet height H_s3 = 977,600.
- **Order.** P3 was on `main` and H_s3 was named before block 977,600 existed (the seed note, sections 1 and 2;
  the pull request that added P3 is #950, merged 2026-11-25T03:33:19Z, its GitHub `merged_at`; it reached
  `main` in train #952, whose merge was committed at 03:33:16Z). So the seed cannot be chosen. The seed value is the only change to the item-4 policy after P3.
- **Reads.** When Node A's tip is at least 977,602, the Founder reads `getblockhash 977600` and that block's
  header `time` on Node A and on Node B. The registration records Node A's read in `seed` (`block_hash`,
  `block_header_time`, with `block_height`, `policy_pending_freeze_sha256` and `seed`) and Node B's in `node_b`
  (`getblockhash_977600`, `getblockheader_977600_time`). The time is the integer `time` of the block header, in
  seconds; any other form is refused, never converted.
- **Stop conditions.** The two hashes must be equal, and so must the two times. The header time must be later than
  the merge of the pull request that added P3. If either fails, the seed step stops until A re-decides (the seed
  note, section 4). The registration tool refuses such a file (`NODE_B_SEED_BLOCK_HASH`, `NODE_B_SEED_BLOCK_TIME`,
  `SEED_BLOCK_NOT_AFTER_POLICY`).
- The header time is not an input of the seed.
- The registration tool recomputes the seed from P3 and the recorded block hash, requires the item-4 policy to
  carry that seed, and requires P3, the block hash and the seed to be written in the pinned seed note (`SEED`,
  `SEED_NOT_IN_NOTE`).

## 7. Observation completeness

- The judged set of a sub-scenario is every completed `ardr CONFIRMATORY ITEM4_<S>` dispatch whose head is on
  `main`'s first-parent history. The judge's `experiment` command binds the run list to GitHub's dispatch listing
  (server times): a list that leaves out such a dispatch is refused (`RUN_LIST_INCOMPLETE`), and a listed run that
  is not in the listing as a completed run, or was created before the bound, is refused (`RUN_LIST_DISAGREES`)
  (045b:1034; `docs/claude-track/formats/ARDR_JUDGE_V1.md` section 20).
- This covers item 4 only. Issue #110 stays a condition for Class E (045b:943-946).

## 8. Stopping, exclusion and re-dispatch

- Fixed N of 50 runs per sub-scenario, no early stopping, no extension after seeing results (045b:571-574).
- The unit of a run and of an exclusion is the run (045b:1084). A run whose planned turns are all judged, with no
  plan mismatch, is a judged run whether its labels match or not, and a mismatch is NO-GO evidence (045b:383). A run
  that the driver ends on its own label check (`ITEM4_LABEL_MISMATCH`, or `L0_RELEASE_NOT_REORG67`) is not an
  exclusion: the judge judges its label lines from the raw log. A run that stopped partway is NO-GO evidence when a
  turn it already judged mismatches, and EXCLUDED otherwise (045b:1084).
- A sub-scenario is NOT_ESTABLISHED, and counts as not run (045b:383), when more than 5 of its 50 runs are missing,
  EXCLUDED or otherwise not judged (`TEN_PERCENT_RULE`), when it has no judged run (`NO_JUDGED_GATES`), or when a
  transition the inventory lists for it is reached by no judged run (`TRANSITION_NOT_REACHED`; 045b:1279). Inside a
  sub-scenario a NO-GO comes before NOT_ESTABLISHED (045b:1084).
- Item 4 is NO-GO when a sub-scenario is NO-GO; otherwise NOT_ESTABLISHED when a sub-scenario is NOT_ESTABLISHED or
  has no record (045b:383, "any of the four sub-scenarios not run"); otherwise GO. NOT_ESTABLISHED never gives GO.
- Each unit is dispatched once. Only a unit whose slice record shows it never started may be dispatched again; a
  unit with any recorded observation is judged or excluded, and an exclusion counts under the 10% rule
  (045b:576-580). A run cut off by the runner's limit before collect counts as missing, never as a success
  (045b:1903).

## 9. Values computed before data

These are values computed from the pinned tools before any CONFIRMATORY item-4 observation exists. They are not
thresholds and not criteria. The judge's verdict comes from the collected data and 045b's thresholds only.

- At `b` 6,000 the project seat's configured `p_0` is 16,000 sat/kvB and its rung-0 fee 3,408 sat at 213 vB; L0's
  set is [3,408, 5,112] sat. The censorship and reorg competitor pays 6,817 sat. The self REGISTER pays 600 sat.
- The fee-asymmetry median lies between `b` and `4b`, 6,000 to 24,000 sat/kvB, so the asymmetric fee is 12,780 to
  51,120 sat, and the 90,000-sat cap cannot refuse a run under this registration.
- ITEM4_REORG has 25 runs of depth 1 and 25 of depth 2.

## 10. Scope change

- A changed threshold is a new policy identity with its reason; results under the old one are kept, new
  confirmatory testing is needed, and an old failing run is never relabelled as a pass (045b:483-485).
- A budget record change that only raises BEAT caps is a disclosed operational change; the Founder approves its
  exact hash (045b:790-805). The item-4 runs stay inside the Class T L0 record, so that record is unchanged here.
- A run of ITEM4_REORG with the product's TDS 6.7 release path, once #446 is fixed, is a new registration, and the
  result under this registration is not upgraded (045b:1069).
- Any other change to the registered content (a pinned file, the item-4 policy or its seed, the scope, a driver,
  planner or judge change) is a new registration of the 045b:318-321 shape (045b:311-321).

## 11. What this file does not do

It records no Founder decision, grants no GO and holds no key, secret, credential, public repository name, block
hash, seed or commit id. The receipts, their verification and the judgement are separate records.
