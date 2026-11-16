# SEM-1 first-BEAT operations

**FROZEN — CT-P3-045b freeze; values written 2026-11-09 (Claude plan). Hash subject `first_beat_operations_sha256` of the campaign budget record (045a §4.2); any change is a new file, a new record and a new approval.**

Work item: CT-P3-045b (CR-17). Protocol impact: `NONE`. Class T development;
`release_authorization` NONE. Main draft:
`docs/claude-track/plans/CT-P3-045b_PREREGISTRATION_DRAFT_EN.md` (abbreviations
and labels as there).

This section names **roles and time windows only, no identities** (CRD:52).
Who fills each role is recorded outside this file and outside Git where it
would identify a person. At freeze, SHA-256 of the exact frozen bytes becomes
`first_beat_operations_sha256` in the campaign budget record (045a §4.2). This
draft grants no signing or broadcast authority.

## 1. Sources

- (source) Construct the first BEAT only after actual active-chain REGISTER
  acceptance, resolution of its exact current Anchor and at least one
  subsequent block; then complete the exact candidate's human process and
  current execution checks, and execute promptly when separately authorized
  (MBA:361-364).
- (source) Birth+144 is an operational escalation point, not a guaranteed
  service level, Core timeout or exemption from the human interval. The
  campaign MUST specify signer availability, fee policy, escalation and
  recovery in advance. Twelve wall-clock hours are not a fixed number of
  blocks (MBA:366-370).
- (source) An operator MUST keep a signer or a narrowly pre-authorized signing
  mechanism reachable within every heartbeat cycle (SSoT:1696).
- (Founder) FD-CT-01: no fixed wait for each REGISTER/BEAT; the frozen exact
  bundle, human approval, fresh execution checks and **separate** signing and
  broadcast records are required; they may happen in one human session
  (B1:26). FD-CT-05: maintain until block 1,050,000, about every 1,008
  blocks, then by default stop (B3 §1). FD-CT-04: SEM-1 has no supported fast
  per-Heart response to key theft (B2).
- (source) Core deadline: `last_valid_beat_height = current_anchor_height +
  2,016`; first timeout at `+ 2,017` (B3 §1, citing
  `canonical/BITAGI_SSOT_D3_5_FINAL_EN.md:917-920`).

## 2. Roles

One person may hold several roles; each role's acts are separate records
(FD-CT-01). No role is held by Claude for signing or broadcast (AGENTS.md
§10).

| Role | Duty | Must be reachable during |
|---|---|---|
| Monitor | runs the heartbeat monitor (CT-P5-001..004): current Anchor height, blocks left to `last_valid_beat_height`, inclusion status; raises the escalations in section 4 | the whole campaign |
| Constructor | builds and freezes the exact unsigned BEAT (or replacement) under the fee policy | each BEAT window |
| Approver | approves the exact frozen subject (Founder authority) | each BEAT window |
| Signer | operates the offline signer under a human ceremony; records the signing authorization | each BEAT window; a declared backup Signer role covers the same window |
| Broadcaster | runs fresh prebroadcast checks, records the broadcast decision, broadcasts to Node A and Node B | each BEAT window |
| Recovery operator | restores signer, wallet or nodes from the rehearsed backups (TDS 8.11; TDS 7.6) | on escalation *2026-11-04 (Claude plan, §14.19): added duty, on AL-10: start a second comparison container on another host, in the pinned image and under its own leg record; §7.11 also adds the Reference operator role and its availability record; see §7.11.* |

Availability rule (Claude plan): before the REGISTER is broadcast, the
Signer and backup Signer roles each confirm in a dated record that they can
act inside window W1 below. If neither can, the REGISTER broadcast is not
authorized (`ACTION_BLOCK`, 045a §4.4).

## 3. Time windows (blocks; `B` = accepted REGISTER height)

All windows are in block heights from the replayed active chain, never in
wall-clock time (MBA:369-370). For the first BEAT the current Anchor height
is `B`.

| Window | Heights | What happens |
|---|---|---|
| W0 wait | tip = `B` | nothing is built; the REGISTER acceptance and current Anchor are replayed and confirmed on both nodes (TDS 6.8 critical height). The Monitor reads the wallet's open stops and locks, records any that hold the first BEAT (045a §4.4 "Holds"), and escalates them at once (section 4) |
| W1 normal | `B + 1` ≤ tip < `B + 144` | construct, freeze, approve, fresh checks, sign, signed-final checks, Node A/B `testmempoolaccept`, broadcast record, broadcast (MBA:361-364). Target (Claude plan): broadcast by `B + 36` *2026-11-04 (FD-CT-105, BATCH53): at tip ≥ H0 and below the cutover height E (`B + 144`), the sign and the broadcast each wait for a Rust/Python MATCH chain through the tip (WB9); see §7.11.* |
| W2 escalation | `B + 144` ≤ tip < `B + 1,512` and the first BEAT not included | birth+144 escalation (MBA:366-367): Monitor notifies all roles; the fee policy's emergency floor applies; BEAT replacements under the fee policy §5; Recovery operator engaged if any role is unavailable *2026-11-04 (FD-CT-105, BATCH53): `B + 144` is the first BEAT's cutover height E; from here, where the comparison is admitted, a gap in the availability family alone lets the BEAT proceed as `CutoverReplay`, Rust-only and labelled, and a MISMATCH or a divergence-family refusal never cuts over; see §7.11 and 045b §14.19 item 3.* |
| W3 late | `B + 1,512` ≤ tip ≤ `B + 2,016` and not included | last quarter before the Core deadline: replacements may be built each block within the caps; the Founder is told the Heart may time out |
| — | tip ≥ `B + 2,017` with no accepted BEAT | the Heart is TIMEOUT under Core; there is no exception or resurrection (AGENTS.md §4). Record it; no further BEAT is built |

Later BEATs (current Anchor height `A`, the height of the previous accepted
BEAT) have their own windows, aligned with the fee policy §5 triggers:

| Window | Heights | What happens |
|---|---|---|
| L0 wait | `A` ≤ tip < `A + 1,008` | no BEAT is required; the Monitor shows blocks left to `A + 2,016` |
| L1 normal | `A + 1,008` ≤ tip < `A + 1,152` | the operational target interval of 1,008 blocks (B3 §1) is reached: construct, freeze, approve, check, sign, broadcast as in W1. Construction may start earlier (Core has no minimum BEAT interval) *2026-11-04 (FD-CT-105, BATCH53): at tip ≥ H0 and below the cutover height E (`A + 1,152`), the sign and the broadcast each wait for a Rust/Python MATCH chain through the tip (WB9); see §7.11.* |
| L2 escalation | `A + 1,152` ≤ tip < `A + 1,512` and the BEAT not included | as W2: emergency floor, replacements under the fee policy §5 *2026-11-04 (FD-CT-105, BATCH53): `A + 1,152` is a later BEAT's cutover height E; from here, where the comparison is admitted, a gap in the availability family alone lets the BEAT proceed as `CutoverReplay`, Rust-only and labelled, and a MISMATCH or a divergence-family refusal never cuts over; see §7.11 and 045b §14.19 item 3.* |
| L3 late | `A + 1,512` ≤ tip ≤ `A + 2,016` and not included | as W3 |
| — | tip ≥ `A + 2,017` with no accepted BEAT | TIMEOUT under Core, as above |

After block 1,050,000, with no new Founder decision, no BEAT is built
(FD-CT-05 default).

## 4. Escalation and recovery

| Trigger | Action |
|---|---|
| W2 or W3 entered | as in the table above |
| Signer unavailable | backup Signer; if both unavailable, Recovery operator restores the signer from the encrypted offline backup (TDS 8.11, rehearsed before Profile freeze) |
| Node A or B unavailable or disagreeing | broadcast blocked (`BLOCK_NODE_UNAVAILABLE_OR_DISAGREEING`, 045a §4.4); restore the node; two-node broadcast recovery (fee policy §6) |
| Reorganization, critical-height disagreement, import/restore failure | broadcast lock and incident record (main draft §8) *2026-11-04 (FD-CT-105, BATCH53): these locks still hold a BEAT past its cutover height E; see §7.11 and 045b §14.19 item 6.* |
| Suspected key compromise | stop official signing (TDS 8.12, TDS:1167-1176); `STOP_SUSPECTED_KEY_COMPROMISE`; disclose that SEM-1 has no supported fast response (FD-CT-04) |
| A stop, block or lock that holds the first BEAT is open at `B` (any 045a §4.4 code except the four REGISTER-cap stops, or any lock) | escalate at `B` and tell the Founder. It clears only by its own 045a §4.4 release condition; for `STOP_EXACT_HEIGHT_MISSED` that is a new approved record, then the first BEAT frozen and approved again under it; for `STOP_BUDGET_RECORD_MISMATCH`, a refreeze under the correct record; for a BEAT-cap stop, a new approved record (`clear_budget_stop`) whose caps exceed the released counts, since under lower caps the next BEAT raises the stop again (#279). Otherwise the Heart is TIMEOUT at `B + 2,017` (#266) *2026-11-04 (Claude plan, §14.19): for a Rust/Python mismatch found at a tip at or above H0, the `STOP_DEFECT_DETECTED` condition also needs a Reviewer record locating the first difference and a new MATCH chain from INITIAL (and public claims reclassified if Rust departed), and the TDS 14.8 case's full replay comparison is that chain; see 045b §14.19 item 5.* |
| `clear_budget_stop` (re-pin to a new record) | never between a BEAT's charge and its broadcast. In the same step, refreeze and reapprove every unreleased candidate of the old record, BEATs included, or stop using it. Never present the superseded record: the wallet then persists `STOP_BUDGET_RECORD_MISMATCH` (`release_budget::admit`, `crates/bitagi-wallet/src/release_budget.rs`), which only refreeze evidence clears (`campaign_stop::may_clear`, `crates/bitagi-wallet/src/campaign_stop.rs`). The host refuses a re-pin while any offline charge is unsettled (`LaunchHost::repin_budget`, `HOST_REPIN_CHARGE_IN_FLIGHT`; FD-CT-92 B item 4). A re-pin the wallet refuses with `BudgetRecordPinnedBefore` is not presented again with the same record: each attempt leaves one reconcile event and a host-file re-bind. After an error or a crash in a pin or re-pin there is no report: read the pin and the stops with `bitagi ledger status`, then present the step again only if they are not as intended |
| A REGISTER-cap stop is open (`STOP_GATE_ATTEMPTS_EXHAUSTED`, `STOP_RELEASED_CANDIDATES_EXHAUSTED`, `STOP_FEE_EXPOSURE_CAP`, `STOP_PRINCIPAL_EXPOSURE_CAP`) | REGISTER releases have ended; BEATs keep the normal windows (045a §4.4 "Holds", #266). Record it |
| A BEAT-cap stop is open (`STOP_BEAT_COUNT_EXHAUSTED`, `STOP_BEAT_REPLACEMENTS_EXHAUSTED`) | Every BEAT release, and every BEAT signing clearance and offline charge, has ended for every Heart. The wallet still releases REGISTER rows (045a §4.4 "Holds", #279), but the launch core refuses a REGISTER candidate while any CAMPAIGN_STOP is open (`crates/bitagi-launch/src/machine.rs`). Escalate at once and tell the Founder: only a new approved record clears it (`clear_budget_stop`), and unless its caps exceed the released counts the next BEAT raises the stop again; otherwise each Heart ends TIMEOUT at its last accepted BEAT height + 2,017 (birth + 2,017 only before its first BEAT; section 1). Blocks then left: at most about 1,008 if the stop opens after routine BEATs start (L1), at most 864 after L2 starts, at most 504 after L3 starts |

## 5. Records per BEAT

Construction (frozen subject hash), approval, signing authorization and
broadcast authorization are four separately identifiable records (FD-CT-01).
They name roles, not people. They contain no key, seed, descriptor, signed
mainnet transaction or credential (AGENTS.md §9); transactions are named by
txid after broadcast.

## 6. Freeze lines (draft, 2026-11-02, Claude plan)

Appended so that every line above keeps its number (main draft §14). **[A wording draft]** marks a row whose substance was decided before its wording; A reviewed and finalized that wording on 2026-11-09. Rows added to the section 4 table:

| Trigger | Action |
|---|---|
| **[A wording draft]** Before the birth, inside the launch window: the ledger reaches the band (`band_reached(·, 1)`), or a band refusal stalls the launch (`BandReorg67`, `BandLastRow`, E-1's `ReadOnly`) | Stop the host and the launch. With the host stopped, rotate the ledger (`ReservationLedger::rotate`) under the pre-init rule: more than `reserve` (1) reservation slots, more than `LOCK_BAND_ROWS` free lock rows and more than `STOP_BAND_ROWS` free stop rows. Then start again. Since 523-a the rotation alone revokes no charged export; a CAMPAIGN_STOP raised after the charge that holds the row still revokes it. After the birth the host rotates on its own (523-b, #581). At the freeze SHA no CLI command rotates a ledger, so the step names the library call (`crates/bitagi-launch-host/src/rotation.rs:696-709`; 523-b's way out (b), A #258 issuecomment-6470995554) |
| Any input path the operator gives the host | Give a regular file, never a symlink. Since B-603 (#604, `26f7b2db`) the host opens outside inputs with `O_NOFOLLOW` and checks the handle, so `load_authority`, `load_sign_base` and `load_export` refuse a symlink they used to follow. `O_NOFOLLOW` covers only the last path component: a parent directory swapped for a symlink is a residual, and the outside-state-tree check still uses the normalized path (A #258 issuecomment-6517012465) |
| Restoring a ledger | Never restore a live ledger in place while a writer is running; restore only after every writer has stopped. This is #584's accepted residual, with no code change: after a replayed reopen the last open wins, and the losing handle poisons itself (A #258 issuecomment-6520126930 Q1) |
| **[A wording draft]** The agreed tip is stale (its MTP 6 hours or more old; 555-a) or the tip monitor raises BEHIND or FORK, and a new BEAT replacement is due | Before building it, check as TDS 14.7 does (TDS:1688-1692): (1) feed Node A and Node B the outside chain: one `addnode` to Node C, or `submitheader` with the headers an explorer shows; (2) read A's and B's `getchaintips`: a `headers-only`, `valid-headers` or `valid-fork` branch whose tip has more `chainwork` (`getblockheader`) than the agreed tip means A and B are behind: fix or rebuild the node; (3) only `invalid` branches, or no change after a feed that reached the node (`submitheader` returned without error, or `getpeerinfo` lists Node C), means the outside source is wrong: record the comparison and go on. If the nodes are sound, build as usual. In W3 and L3 a replacement within the caps is not held for an unfinished check. Re-broadcasting an already signed BEAT is always allowed, and the BEAT approval itself is never held. Reason: in a slow eclipse, W3's replacement each block could use up the campaign caps (`max_beat_replacements` 100, `beat_count` 60); holding replacements on a false alarm would end in TIMEOUT (A #555 issuecomment-6470898517 §4) *2026-11-04 (FD-CT-105, BATCH53): the TDS 14.7 check never holds a re-broadcast, but at tip ≥ H0 and below the cutover height E a re-broadcast at a new tip still waits for the Rust/Python comparison through that tip; see §7.11.* |

- (A #258 issuecomment-6484945777, RV-99) The #555 ruling's "does not reach H0−1" is the monitor's: host check (a) (555-a) does refuse the H0−1 REGISTER Sign and Broadcast once the tip has been stalled 6 hours or more.
- (same) A new BEAT replacement is built after the human check above, outside W3 and L3. The host does not refuse it.
- (A #555 issuecomment-6470898517 §4) The tip monitor only raises alarms: it holds nothing, it is no tie-breaker (TDS:1690), and it is neither a G5-02 trigger nor release evidence. 555-a and the monitor (P5-004-2d) are built after the 045b freeze. The wait registry lists 555-a's hold as W33.

## 7. Budget table: B_*, M, READY, alarm bounds, fault envelope (045b J3; draft 2026-11-02)

Appended so that every line above keeps its number (main draft §14). `:N` is a line of this file. Other files are cited at `1637b151` (branch `claude/a-045b-freeze`) and are re-cited at the freeze SHA. This section answers main draft §14.Z J3 (045b:1209) and the assurance table row "HC-01·HC-03 B_*·M·경보·fault envelope" (AT:191). Everything here is (Claude plan) for A to accept or change.

- **What it is.** R2 §15's continuity budget (R2:510-536), applied to the first BEAT and every later BEAT of this campaign. It defines each `B_*` term, M, the READY test, the alarm bounds, the fault envelope and the recompute trigger. D comes from the countdown (AT:190). This section adds the budget that D is compared with.
- **Freeze.** The section is part of this file's bytes, so it is frozen through `first_beat_operations_sha256` in the budget record (:12-14). The Founder approves it as part of the exact `budget_record_sha256` (F5; 045b:1177 A3). M, the alarm bounds and the human-response assumptions are confirmed there and marked UNMEASURED. No separate question is asked (AT:192, :572-575).
- **UNMEASURED.** No `B_*` term has a measured value in the repository at `1637b151`. The 23 finite EXPLORATORY XD-1 `T` values were read from job logs, not stored as files (B45:240-243). They time the REGISTER pipeline, not a `B_*` term. Every value below is therefore an assumption. R2 asks that a bound which cannot be guaranteed be registered as an assumption (R2:528). Each row names the campaign that measures the term. A measured value replaces an assumption only through 7.6.
- **Posture.** Class T development. Protocol impact NONE. `release_authorization` NONE. NO PRODUCTION NETWORK ACTIVE. The values govern Class E operation only after the freeze and the Founder's approval. This section grants no signing or broadcast authority. It changes no Core height: `last_valid_beat_height = A + 2,016` and the first timeout is `A + 2,017` (:36-38; SSoT:1813).

Abbreviations, added to the main draft's: **R2** = `docs/claude-track/inputs/assurance-handoff-20261026/BITAGI_PreRelease_Assurance_TDS_v20261024_R2.md`; **AT** = `docs/claude-track/plans/ASSURANCE_APPLICATION_TABLE_KO.md`; **P5** = `docs/claude-track/plans/CT-P5_PHASE_PLAN_KO.md`; **V1** = `docs/reporting/BITAGI_HEART_COUNTDOWN_V1.md`; **XD1V2** = `docs/claude-track/formats/XD1_EVENT_CHAIN_V2.md`; **FEE** = `docs/claude-track/preregistration/FEE_POLICY_DRAFT_EN.md`; **REG** = `docs/claude-track/plans/notes/CT-P3-045b_PREREGISTRATION_DRAFT_EN/2026-10-26_wait-registry.md`; **FD17** = `docs/claude-track/plans/FD-CT-17_BUNDLE_DRAFT_KO.md`; **CRF** = `docs/claude-track/plans/CR_FOLLOWUP_PLANS_KO.md`; **B22** = `docs/claude-track/decisions/FD-CT-BATCH22_*.md`.

### 7.1 Deadline and D (source)

- R2:515-516: `H_last = min(h_anchor + 2,016, h_birth + 3,024,000 - 1)` and `D = H_last - H_tip`.
- `H_last` equals countdown V1's `last_timely_beat_height = min(last_valid_beat_height, terminal_height - 1)`, where `last_valid_beat_height = current_anchor_height + 2,016` and `terminal_height = birth_height + 3,024,000` (V1:35-36, :51; AT:190). So `D = last_timely_beat_height - as_of_height`.
- When TIMEOUT comes before MAX_AGE, `D = blocks_to_timeout - 1` (V1:48, :54-58). Alarms use D, not `blocks_to_timeout`. HC-01 tests every bound at zero and at ±1 (R2:489).
- In this campaign the `min` is always `A + 2,016`. Birth is near 1,000,000 (045b:743), so terminal is near 4,024,000, and BEATs stop at 1,050,000 (:85-86). For the first BEAT, `A = B` (:63-64).
- D is recomputed at every tip from the replayed Heart state and is never read from a file (045b:1168). It is also recomputed after a reorg, an accepted BEAT and a node replacement (R2:532).
- READY needs CURRENT verified on both nodes. The countdown refuses `NODES_DISAGREE` and `NODE_UNAVAILABLE` (`crates/bitagi-cli/tests/heart_countdown_command.rs:377`, `:386`), and R2 then shows UNKNOWN, not READY (R2:523, :527). The countdown cannot tell ENDED from NOT_FOUND (`crates/bitagi-cli/src/heart_countdown_command.rs:31-32`). Neither state gets a READY judgement (R2:523).

### 7.2 Hours to blocks (Claude plan)

R2 counts every B and M in blocks. It forbids dividing measured wall time by the 10-minute mean and using the result as an absolute bound (R2:523, :529).

Human and equipment times are therefore assumed in hours and converted to blocks once, on their sum. `blocks(t)` is the smallest `k` with `P[Poisson(6t) <= k] >= 0.999`, for `t` in hours (6 blocks an hour is the 10-minute mean).

This is a one-in-a-thousand allowance for bursts, not an absolute bound. A faster chain is outside the envelope (7.5). HC-03's burst case tests the recomputation (AT:191). Converting each term alone and adding the results would count the burst allowance several times, so the "alone" figures in 7.3 are information only.

### 7.3 Table

| Term | Meaning (R2 names the term; the reading is Claude's) | Value: UNMEASURED assumption, and why | Campaign that measures it | Status |
|---|---|---|---|---|
| `B_detect` | From the start of a fault, or a BEAT that stops progressing, to an alarm reaching the Monitor's human (R2:517; "최대 탐지 … 시간", R2:528; HC-01, R2:489) | 6 h (alone 56 blocks). The Monitor role covers the whole campaign (:48). The Founder runs it on Founder equipment (FD-CT-53, B22:40, :70). 6 h is the tip age the host already treats as stale (555-a, :119). A monitor silent for longer is outside the envelope | CT-P5-004-2c, which adds alarms and W/L classification (P5:73, :319). It merges before P5-002 and is observed during it (P5:220, :325, :344). AT:191 writes it "P5-002 -2c" | UNMEASURED. -2c is not built. P5:344 checks only that alarm output exists, and no campaign records alarm latency yet |
| `B_operator` | From the alarm to a role acting on it: the human response (R2:517; "응답", R2:528; HC-04, R2:492) | 24 h (alone 182). The Signer availability rule asks for action inside W1, which is 144 blocks (:55-58). Under FD-CT-53 one person holds every role, so this is the Founder's own longest absence without a handover (B22:40, :70; 045b:757-758) | XD-1 confirmatory runs record `D1 − D0` as a `B_operator` sample (045b:1099; AT:193, :509). This measures only the decision act, in seconds, with the Founder already at the console. EXPLORATORY runs stamp D0 and D1 back to back (XD1V2:142-145), so the 23 EXPLORATORY runs (045b:1096) hold no sample. No campaign measures the alarm-to-console part, which R2:492 asks for in a real rehearsal | UNMEASURED. Only part of the term has a campaign, and that part's samples never replace the term (7.6 item 1) |
| `B_restore` | Restoring the failed part: rebuilding or replacing a node, restoring the host, or restoring the signer from backup (R2:517; "키 복구", R2:528; DR-03, R2:826) | 72 h (alone 498). Rebuilding a node from scratch is the longest single restore. IBD is estimated at 10–18 h, and 72 h is the figure the node plan already uses for deadline calculation (B45:172, ESTIMATE). A full replay from H0−1 of about 50,000 blocks adds hours (FD17:214, estimate). Restoring the signer from the second encrypted backup in its separate location (TDS:1163-1164) is assumed to fit in the same 72 h. This is the largest term. A spare node kept in sync would cut it to the replay time (FD17:214) | P5-003, Signet node replacement (P5:72, :241-274). The timed mainnet C4 replacement rehearsal before RC (FD17:216). CT-P6-003, signer restore (P5:245-246; CRF:142). Also AT:191, :509 | UNMEASURED. P5-003's pass criteria record no duration (P5:270-274). Signet C1 is not the mainnet C4 path (FD17:207) |
| `B_prepare` | Building, freezing and approving the exact BEAT, and running the fresh checks (R2:517; the W1 steps, :69) | 1 h (alone 15). The machine steps take minutes. Approval happens in the same human session as signing and broadcast (FD-CT-01, :30-33) | AT:191 maps none. Candidates are P5-002 scope (a), a Class T REGISTER and first BEAT on Signet (P5:391), and P5-001 item 3, the project Heart's first BEAT (045b:382) | UNMEASURED. No campaign named |
| `B_sign` | Offline signing with removable media, plus the signing record (R2:517; "오프라인 이동", R2:528; TDS:1161-1162) | 2 h (alone 24). One offline session. The signing method, an in-repo offline signer or an external PSBT signer, is still open (CRF:150) | AT:191 maps none. The candidate is the CT-P6-003 rehearsal of the key ceremony and the first-sign procedure (TDS:1164; CRF:142) | UNMEASURED. No campaign named |
| `B_handoff` | Getting the signed bytes back to the host: import, signed-final checks, Node A/B `testmempoolaccept`, broadcast record and broadcast (R2:518; :69; WB1–WB2, 045b:1166) | 1 h (alone 15). For REGISTER, the same steps after H0−1 have the XD-1 criterion p95 ≤ 420 s (045b:598-613). 1 h is about 8.5 times that | AT:191 maps none. Candidates are XD-1 confirmatory `T`, the REGISTER counterpart (045b:603-613), and P5-002 scope (a) (P5:391) | UNMEASURED. No campaign named |
| `B_include` | From the first broadcast of a valid BEAT to its acceptance in the active chain, replacements included (R2:518). Fees and resends stay inside the approved policy (R2:530; HC-05, R2:493) | 6 blocks plus 2 replacement rounds of 4 h each (8 h in the sum; alone 71 + 6). 6 is the BEAT `estimatesmartfee` target (FEE:33). Each BEAT replacement is its own subject, approved and signed when needed (045b:242-250). A round is therefore one `B_prepare` + `B_sign` + `B_handoff` session. The first round follows a fee rise, since a replacement is built at the then-current `b` (FEE:95). The second covers a rise that continues. Reaching the feerate cap from `b` takes about 7 rounds, or 10–13 (045b:776-779, estimate), and that does not fit (7.5). *Policy wait (Desktop r4440821436, 2026-11-02):* a BEAT broadcast at L1 (`A + 1,008`) cannot be replaced before L2 (`A + 1,152`, FEE:84-94), up to 144 blocks later; the first BEAT waits from W1 to W2 (`B + 144`). The wait ends at a fixed height, not a fixed time after the fault. For a fault at height h, with X blocks from the fault to the broadcast (the hour terms before `B_include`) and R the two rounds, the BEAT is final by max(h + X, L2) + R + 18. The first arm is the `B_total` series below, with R inside the joint 114 h conversion (766). In the second arm X has ended before L2, so the only wall time left is the two rounds' 8 h, converted alone at the same 0.999 quantile (7.2): R = 71, a separate UNMEASURED envelope assumption for this arm. The budget clock starts at the later of the fault and the BEAT's due height, max(h, L1) (max(h, W1) for the first BEAT), because no BEAT is due earlier (AL-1). Counted that way the second arm takes at most (L2 − L1) + R + 18 = 144 + 89 = 233 blocks (232 for the first BEAT), inside 784; against the deadline it needs D at L2 = 864 ≥ 89 (1,872 at W2 for the first BEAT). So the wait adds nothing to `B_total`. *(Desktop r4440886760, 2026-11-02: clock start and R's envelope stated.)* A measured sample records the broadcast height, the first height a replacement was allowed and the inclusion height, and reports the policy wait apart from the inclusion time | P5-001 items 3 and 4: accelerated Regtest with a controlled miner (045b:382-383; AT:191, :194). These test how the host behaves inside the envelope. They do not measure mainnet inclusion | UNMEASURED for mainnet. Tested in Regtest only |
| `B_reorg` | Blocks lost when a reorg disconnects the BEAT before it is final, until it is included again after fresh checks (R2:518, :512; TDS:1663-1669; HC-03, R2:491) | 12 blocks: a reorg up to 6 deep, plus re-inclusion within the 6-block target (FEE:33). Depth 6 is the six-confirmation reporting depth (TDS:1597), which is not finality. Deeper reorgs are outside the envelope. Bursts are covered by 7.2, not here | P5-001 item 4, reorgs 1 and 2 deep (045b:383, :1070). The HC-03 burst case still has to be added to the P5-001 inventory (AT:191) | UNMEASURED. The Regtest tests cover reorgs only up to 2 deep, and the burst case is not yet in the inventory *2026-11-04 (Claude plan, §14.19): the 12 blocks count no TDS 6.7 release time, and step 6 today is one Python run from H0−1, or two with a disconnected side; 045b's R19-17 times it against this term; see 045b §14.19 item 6.* |

**Sum (draft).** Wall time is 6 + 24 + 72 + 1 + 2 + 1 + 8 = 114 h, which converts to 766 blocks (7.2). Adding `B_include`'s 6 blocks and `B_reorg`'s 12 gives **`B_total` = 784**. The per-term "alone" figures would add to 879; they are not used.

R2 defines no other `B_*` term (R2:517-518). R2 §16 adds the wait registry, which is not a B term (R2:560).

### 7.4 M, READY and alarm bounds

**M** (R2:523, :531) is a positive operating margin in blocks. A proposes it from measurement, the worst tested case and operator participation. The Founder confirms it, and it is registered before P5-005.

Draft: **M = 144** (Claude plan; an UNMEASURED assumption, confirmed with the rest at A3). With D ≥ `B_total` + 144, a path that uses its whole budget still ends before the final 144-block band, the point by which SSoT asks for emergency procedures to have begun (SSoT:1818). M does not absorb an assumption that a measurement has exceeded; that case triggers a recompute (7.6). M is never lowered below 144 without the Founder. It is not R2:1234's `M = max(birth)` (I31).

**READY.** R2:519-520, verbatim: `READY_FOR_CONTINUITY only if CURRENT is verified and D > 0 and D >= B_total + M`.

Draft: `B_total + M` = **928** (UNMEASURED: it carries every assumption above). The Monitor shows READY only while all three hold:

- both nodes agree on a fresh tip;
- the Heart is CURRENT;
- D ≥ 928, which means tip ≤ `A + 1,088` (for the first BEAT, `B + 1,088`).

Fit with the windows of sections 3 and 4:

| Point | First BEAT (`A` = `B`) | Later BEAT | D | READY (draft) |
|---|---|---|---|---|
| W1 / L1 starts | `B + 1` | `A + 1,008` | 2,015 / 1,008 | yes / yes, with 80 blocks to spare |
| W1 target | `B + 36` | — | 1,980 | yes |
| W2 / L2 escalation | `B + 144` | `A + 1,152` | 1,872 / 864 | yes / no |
| READY lost | `B + 1,089` | `A + 1,089` | 927 | no |
| W3 / L3 | `B + 1,512` | `A + 1,512` | 504 | no |
| Last timely block | `B + 2,016` | `A + 2,016` | 0 | no |

A routine BEAT needs `B_prepare` + `B_sign` + `B_handoff` = 4 h, which is 40 blocks, plus the 6-block target. That fits inside the 80 blocks between L1 and the READY bound only if the Founder starts on time. A routine BEAT started late raises AL-2. The wall-time sum can grow to 126 h before `B_total + M` passes 1,008. Beyond that, L1 would start NOT READY in every cycle (7.7).

**Alarm bounds** (Claude plan; UNMEASURED, since AL-2, AL-5 and every bound taken from `B_total` or M carry their assumptions). -2c implements them (P5:319). HC-01 tests each one at its bound and at ±1 (R2:489).

| Alarm | Condition | Action |
|---|---|---|
| AL-0 UNKNOWN | (a) The nodes disagree or one is unavailable, or the store is not synced. (b) Node A and Node B agree and the store is synced, but the tip is stale (MTP 6 h or more, 555-a) or the tip monitor raises BEHIND or FORK | Both: no READY (R2:523, :527) until the cause is cleared. (a) The host blocks broadcast while the nodes disagree or one is unavailable (:94; 045a §4.4). Restore the node within `B_restore`, or sync the store. (b) The alarm holds nothing (:123). Run the TDS 14.7 check (:119) before building a new BEAT replacement, as row :119 does; the BEAT itself is built and approved as usual and is never held for the check (:119, "the BEAT approval itself is never held"; Reviewer RV-122 P3). Re-broadcasting an already signed BEAT is always allowed, and in W3 and L3 a replacement within the caps is not held for an unfinished check (:119). READY returns when the check shows the nodes sound, or once they are fixed. The host's own stale-tip refusal covers only the H0−1 REGISTER sign and broadcast (:121). *(Desktop r4440821421, 2026-11-02: split so that a monitor alarm alone never blocks broadcasting.)* *2026-11-04 (FD-CT-105, BATCH53): a third cause, (c): an open Rust/Python MISMATCH or divergence-family refusal makes the public status UNKNOWN after birth (TDS:1655), so no READY until its release, and every BEAT is held (045b §14.19 item 5); and in (b), a re-broadcast at a new tip below the cutover height E still waits for the Rust/Python comparison through that tip; see §7.11.* |
| AL-1 BEAT due | First BEAT: tip ≥ `B + 1` (W1). Later BEATs: tip ≥ `A + 1,008` (L1). In both cases, no accepted BEAT yet | Build the BEAT (:69, :80) |
| AL-2 READY lost | CURRENT verified, no accepted BEAT, and D < `B_total + M` (draft: tip ≥ `A + 1,089`, or `B + 1,089` for the first BEAT) | The Monitor tells every role and the Founder, and the Recovery operator stands by. Under the draft this comes 63 blocks before L2. Fee escalation stays at L2 (FEE:84-94) *2026-11-04 (FD-CT-105, BATCH53): a later BEAT held by the comparison wait WB9 waits until E = `A + 1,152`, 63 blocks after this bound, so AL-2 fires first; see §7.11.* |
| AL-3 W2 / L2 | Tip ≥ `B + 144` / `A + 1,152`, and the BEAT is not included | As :70 and :81; FEE:84-94 |
| AL-4 W3 / L3 | D ≤ 504 | As :71 and :82. The Founder is told the Heart may time out |
| AL-5 brink | D < 46: one 4 h session at the 0.999 quantile (40 blocks), plus the 6-block target | Record that a new BEAT is unlikely to be included in time. Re-broadcasting an already signed BEAT is still allowed (045b:1167) *2026-11-04 (FD-CT-105, BATCH53): AL-5 lies past the cutover height E, so a comparison gap of the availability family alone does not hold it; a MISMATCH or a divergence-family refusal does; see §7.11.* |
| AL-6 no timely block | D ≤ 0 (R2:523) | TIMEOUT is expected at `A + 2,017` (:72, :83). No BEAT is built (WB6, 045b:1166) |
| AL-7 cap headroom | Either 80 or more of the 100 BEAT replacements are released (20 left, the TDS 8.10 floor, TDS:1151), or the remaining `beat_count` is below the slots still needed to stay CURRENT at 1,050,000 (045b:760-762) | The Founder is told to prepare a §6.3 record (045b:790-795). Its S7 receipts (both required witnesses) must be recorded before the stop is reached (045b:1222; WB8, 045b:1166) |

### 7.5 Fault envelope

**Covered.** These faults are covered one at a time, inside `B_total`. For each, the record is R2's sentence: inside the registered fault envelope, a lawful next BEAT was observed within `B_total` (R2:536). The time is counted from the later of the fault and the BEAT's due height (L1 = `A + 1,008`; W1 = `B + 1` for the first BEAT), since no BEAT is due before it (AL-1; 7.3 `B_include`).

- One host process stops or crashes and is restarted (HC-02, R2:490; DR-01, R2:824).
- One node is unavailable or disagrees, or the store is not synced (AL-0 (a)). Broadcast stays blocked until the node is restored or rebuilt within `B_restore`, or the store is synced (:94; TDS:1685-1692). When Node A and Node B agree and the store is synced but the tip is stale (AL-0 (b)), nothing is blocked: the TDS 14.7 check (:119) runs before a new BEAT replacement is built (the BEAT itself is never held for it), an already signed BEAT may be re-broadcast, and W3 and L3 replacements within the caps are not held (see the last bullet). *(Desktop r4440886458, 2026-11-02.)* *2026-11-04 (FD-CT-105, BATCH53): below the cutover height E that re-broadcast still waits for the Rust/Python comparison through the new tip; see §7.11.*
- The signer device is lost, or an offline transfer medium fails (HC-04, R2:492). The Founder uses the backup device or a spare medium, or restores from the second encrypted backup within `B_restore` (:93; TDS:1163-1164).
- The Founder is away for up to 24 h, or the Monitor is silent for up to 6 h.
- Fees rise, or the BEAT is removed from the mempools or outbid there (HC-05, R2:493), and this is met by re-broadcasting the same signed bytes (045b:1167) or by at most two replacement rounds within the caps (FEE §5). *2026-11-04 (FD-CT-105, BATCH53): below the cutover height E the re-broadcast at a new tip first waits for the comparison through that tip, one link while the follower is current from RM v15 (unmeasured bound, 045b §14.19 item 8); if the comparison is also down (two faults at once, not covered by 7.5), the bytes wait until E and then go as `CutoverReplay`; see §7.11.*
- A reorg up to 6 deep disconnects the BEAT, and the BEAT is included again after fresh checks (:95; TDS:1663-1669). *2026-11-04 (Claude plan, §14.19): whether this re-inclusion waits for the TDS 6.7 release, which step 6 today gives only after one or two Python runs from H0−1, is open (045b's R19-17); see 045b §14.19 item 6.*
- Blocks arrive in bursts no larger than the 7.2 quantile.
- A stale-tip or eclipse alarm is settled by the TDS 14.7 check (:119). *2026-11-04 (FD-CT-105, BATCH53): also covered, a Python-side outage, through the BEAT cutover at E; see §7.11.*

A mandatory wait (REG:91) is not a fault. It is registered in the wait registry, not budgeted in `B_total` (R2:560). *2026-11-04 (Claude plan, §14.19): W34, W35 and WB9 (045b §14.19 item 11) are such waits; see §7.11.*

**Not covered.** For these, the record is an alarm, a refusal or an exact ending report, never a continuity claim (R2:536; HC-07, R2:495).

- Two faults at once: for example, a node rebuild together with a signer restore, both nodes lost, or the Founder away while a restore is due.
- The Founder away for more than 24 h, or the Monitor silent for more than 6 h. Under FD-CT-53 there is no second person (B22:40, :70).
- Fees above `max_feerate_sat_per_kvb`, or a rise that needs more than two replacement rounds. A spend that conflicts with the BEAT's inputs needs a project key and falls under key compromise below (HC-05, R2:493).
- A BEAT-cap or replacement-cap stop (:100; WB5, WB8). Every BEAT is blocked until a new record is approved.
- A reorg more than 6 deep, or one that disconnects the current Anchor's own BEAT. The deadline itself then moves, and D is recomputed (R2:532).
- Miners persistently excluding the project's transactions, a permanent network partition, or an eclipse that the TDS 14.7 check does not reveal.
- A suspected or confirmed key compromise, or the loss of all keys. Signing stops (:96). FD-CT-04 provides no fast response (KS-01–06).
- A host or ledger refusal with no exit: W15, a deterministic W16, W17 `AncestryTooLong`, or W27 (REG:66-68, :78). Also a CAMPAIGN_STOP that is open at `B` (:97). *2026-11-04 (Claude plan, §14.19): also not covered, a Rust/Python mismatch stop opened at any height; see §7.11.*
- Events that are not faults: MAX_AGE, which this campaign cannot reach (7.1); the FD-CT-05 end at block 1,050,000, which is an intended TIMEOUT (:85-86); and the ledger's terminal state after the campaign (045b:1169).

### 7.6 Recompute trigger

D is recomputed at every tip (7.1). The table itself (every `B_*`, M, `B_total` and the alarm bounds) is recomputed when any of the following happens. A recompute makes new bytes, so it also makes a new `first_beat_operations_sha256` and a new budget record that the Founder approves (045b:790-795).

1. A campaign in 7.3 records a value above its assumption, or measures an UNMEASURED term for the first time. The value used is the campaign's worst tested case (R2:531). A sample that measures only part of a term never lowers that term, as for `B_detect` (7.9): the term keeps its assumption, and only a part larger than the whole assumption raises it, to at least that part. XD-1's `D1 − D0` is such a part of `B_operator` (the decision act, :158), and an IBD time is such a part of `B_restore` (its node-rebuild share; Reviewer RV-122 P2-2).
2. Node A or Node B changes Core version, host or provider, or is replaced (R2:532; DR-03).
3. The fee regime changes. This covers the `b` inputs, `max_feerate_sat_per_kvb`, `p_high`, or the caps in a new record (FEE:33-36, :53; 045b §6.3). It also covers a market that stays above the cap.
4. A role, a device, the signing method or the single-person arrangement of FD-CT-53 changes, or the Founder's stated absence assumption changes.
5. A reorg more than 6 deep, or a burst beyond 7.2, is observed on the network.
6. A wait that can overlap a BEAT is added or changed (REG:91; WB1–WB8, 045b:1166), or the windows of section 3 or FEE §5 change. *2026-11-04 (Claude plan, §14.19): WB9 (045b §14.19 item 11) fires this item; the recompute is in §7.11.*
7. R2, the SSoT or a Core successor changes the deadline or the READY test.

Whether a recompute that raises no cap needs the S7 receipt is open: S7 covers cap-only changes (045b:1222). *Dated line 2026-11-09 (A, freeze): settled at :283. Any recompute that changes this file's bytes needs the S7 receipt, raising a cap or not; 045b :1222's parenthesis says what a section 6.3 change is and exempts no other byte change, for the reason it gives (the registered hash).*

### 7.7 This fails if

The table fails in either of two cases.

- A covered fault in a Class T rehearsal or in operation ends without a lawful next BEAT within `B_total` (R2:536).
- A measured term pushes `B_total + M` above 1,008, so every routine BEAT starts NOT READY at L1.

In the second case, either the envelope narrows (a term moves under "Not covered" in 7.5) or the routine start moves earlier than `A + 1,008`, which SSoT:1818 allows. M never drops below 144 without the Founder.

### 7.8 Sources

- R2:489, :490, :491, :492, :493, :495, :510-532, :536, :560, :824, :826, :1234.
- V1:35-36, :48, :51, :54-58.
- AT:190, :191, :192, :193, :194, :509, :572-575.
- 045b:242-250, :382-383, :598-613, :743, :757-762, :776-779, :790-795, :1070, :1096, :1099, :1166-1169, :1177, :1209, :1222.
- P5:72, :73, :220, :241-274, :319, :325, :344, :391.
- This file: :12-14, :30-33, :36-38, :48, :55-58, :63-64, :69-72, :80-86, :93-97, :100, :119.
- FEE:33-36, :53, :84-95.
- XD1V2:142-145.
- REG:66-68, :78, :91.
- FD17:207, :214, :216.
- CRF:142, :150.
- B22:40, :70.
- B45:172, :240-243.
- SSoT:1813, :1818.
- TDS:1151, :1161-1164, :1597, :1663-1669, :1685-1692.
- `crates/bitagi-cli/tests/heart_countdown_command.rs:377`, `:386`.
- `crates/bitagi-cli/src/heart_countdown_command.rs:31-32`.

### 7.9 A decisions on this section (2026-11-02)

- **Measuring campaigns with a duration field** (the terms the assurance table did not map). `B_prepare`, `B_sign` and `B_handoff`: the BEAT-path rehearsals record a UTC start and end for each step, and those durations are the first samples: P5-002 scope (a), a Class T REGISTER and first BEAT on Signet with the launch host (P5:391), for all three, and the CT-P6-003 key-ceremony and first-sign rehearsal for `B_sign`. P5-002 signs with a Signet TEST_ONLY key on the VPS (FD-CT-51, P5:218; A #258 issuecomment-6593069825), with no removable-media offline signing path and no human approval time. A step that does not run the offline signing path is a partial sample (7.6 item 1, :241), so P5-002 cannot lower `B_sign` or `B_prepare` (Reviewer RV-127, #664 issuecomment-6593050735; A takes it as P2). Under P5-002 scope (b) only CT-P6-003 remains, for `B_sign`. The Class T OTS rehearsal (045b §14.Z A11) signs and stamps a registration tag: it has no BEAT build, freeze or checks, no removable-media PSBT signing and no import, `testmempoolaccept` or broadcast, so its durations are no sample of these terms (Reviewer RV-122 P2-1). `B_detect`: CT-P5-004-2c records, for each alarm, two elapsed times on one clock (the host's UTC wall clock, never a block header's timestamp, which miners set): fault start to the alarm's emission, where fault start is the injection time for an injected fault and, for a BEAT that stops progressing, the time the host first received the block at which the stall condition held; and emission to the Monitor's human acknowledging it, stamped when the host receives the acknowledgment from the delivery channel, on the same clock (a channel server's own timestamp is kept only as a cross-check). Their sum is the sample, matching the row's definition (to an alarm reaching the Monitor's human). Until the second leg has samples (each test alarm acknowledged by the Monitor), it stays an UNMEASURED assumption and the section 7.6 recompute keeps it; emission time alone never replaces `B_detect`. -2c's acceptance today checks only that alarm output exists (P5:344), so both fields are added in that unit (B). `B_restore`: P5-003 records the restore wall time for each restored part; its pass criteria have no such field today (P5:270-274), so A adds one to P5 §8.4 as a dated line before the rehearsal (12-02). The actual IBD duration of Node A and Node B is a first sample of the node-rebuild share only, never of the whole term (7.6 item 1; the Founder's node logs; asked with the Q17 delivery, not as a new question). *2026-11-04 (Claude plan, §14.19): a P5-002 (a) BEAT sample now includes the Rust/Python comparison link, and on Signet a BEAT is signed only once that comparison is admitted there; without it P5-002 gives no BEAT sample; see §7.11.*
- **Recompute and S7.** Any recompute that changes this file's bytes changes `first_beat_operations_sha256`, hence the budget record, hence the registered hash (P5:116). It follows the S7 rule of 045b §14.15: a follow-up registration whose two required witnesses, the Bitcoin-confirmed OTS proof and the GitHub server time, both precede the first broadcast under the new record. Whether the change raises a cap does not matter. A recompute that leaves the bytes unchanged (D at every tip, 7.1) needs nothing.
- **Replacement in L1 (Part 2 C7)** is not settled here. A settles it with the FEE §5 lines at the freeze (045b §14.Z, with A5–A7). Until then a replacement is built only from L2 on, as FEE §5 reads today. *Settled 2026-11-09 (A, freeze; main draft §14.21): no replacement in L1. A BEAT not included by `A + 1,152` is replaced from L2 on under FEE §5, as FEE §5 reads. Reason: from `A + 1,152` the deadline `A + 2,016` is still 864 blocks away, with a replacement allowed each block, and `max_beat_replacements` (100 for 60 BEATs) is not spent on normal-window variance.*
- **Two rounds against the replacement cap (C8, C10).** Two replacement rounds for each of up to 60 BEATs (120) exceed the 100-replacement cap. The envelope keeps "at most two rounds" for one BEAT, and AL-7 stops the campaign at the cap; the numbers are reconciled with the Founder's Q1 caps (045b §14.Z A1) before the freeze.
- **HC-03 burst case.** A adds it to the P5-001 inventory (about 11-10), with the 7.2 quantile as the expected bound.
- **One person (C9).** Under FD-CT-53 no second person holds a role. The absence rehearsal of R2 §10 pair 8 (045b §14.16) therefore declares the only Signer absent and expects the cap stop and an exact record, not a substitute signer.

### 7.10 Fee-cap alarm and the cap-raise record (FD-CT-102; draft 2026-11-03)

(Claude plan; A #258 issuecomment-6581164081, item 3.) FD-CT-102 sets `max_fee_per_candidate_sat` to 30,000 sat for every REGISTER rung and every BEAT. The cap never rises on its own; in a fee spike the Founder raises it by approving a new budget record. This section says when the Founder is told and what that record holds. It adds alarm AL-8 to the 7.4 table and changes no other row. For the first BEAT, read `A` as `B`, as AL-2 does.

| Alarm | Condition | Action |
|---|---|---|
| AL-8 fee cap | No accepted BEAT yet for this period, and the next BEAT candidate is over the cap: its fee is above `max_fee_per_candidate_sat`. With `v` the measured BEAT vsize, that fee is ⌈`b` × `v` / 1,000⌉ sat for the first build. For a replacement it is the larger of ⌈max(`b`, ⌈`p` × 3 / 2⌉) × `v` / 1,000⌉ and the replaced BEAT's fee plus the BIP125 increment for `v` at `r_inc` (FEE :95-99; `r_inc` as at 045b:134-136, observed on both nodes, not fixed at 1,000). The Monitor may instead take the full fee of the candidate the BEAT unit builds. At the draft 263 vB and 30,000 sat the rate term alone crosses above F_B = 114,068 sat/kvB (FEE :119); the absolute floor can cross first | The Monitor tells the Founder at once: the tip, `A`, the blocks left to `A + 1,512` and to `A + 2,016`, the current `b`, and the fee the BEAT needs. The Founder decides whether to raise the cap with the record below. The alarm holds nothing (as AL-0 (b), :123). Nothing is built above the cap: the launch host refuses such a candidate before signing (row 13, `crates/bitagi-launch-host/src/checks.rs:518-522`; `crates/bitagi-wallet/src/campaign_budget.rs:232-241`). AL-3 to AL-6 run as usual. AL-8 clears when the next candidate is within the cap, at a lower `b` or under a raised cap in force |

- **Bound and tests.** HC-01 tests AL-8 at a fee equal to the cap (no alarm) and one sat above it (alarm), as for the other rows (R2:489). It also tests a replacement whose absolute floor crosses the cap while its rate term does not: 263 vB, `b` = `p` = 2,000 sat/kvB and a replaced fee of 526 sat give a rate term of 789 sat; at `r_inc` = 112,000 sat/kvB the floor is 526 + 29,456 = 29,982 sat (no alarm), and at 113,000 it is 526 + 29,719 = 30,245 sat (alarm) (Desktop P3, #664 r4459613235). -2c implements it with the other alarms (P5:319). Until -2c is merged, the BEAT operator reads the host's row 13 refusal (`checks.rs:43`) as AL-8 and tells the Founder.
- **The cap-raise record.** A raise is a section 6.3 record change (045b:790-795) with the S7 receipt (045b §14.15). A fills in this form, and the Founder approves its exact `budget_record_sha256` (045a §4.2). *Dated line 2026-11-09 (A, freeze): except the case in item 3 that also raises the exposure (note there).*
  1. Prior record: its `budget_record_sha256` and its registration receipts.
  2. Trigger: the AL-8 tip, `A`, `b`, and the fee the BEAT needs.
  3. New `max_fee_per_candidate_sat`. Every other cap and count stays; a raise never lowers a count (045b §14.17 B3). If the new value is above `max_fee_exposure_sat` (500,000 sat), 045a §4.2's "exposure ≥ per-candidate" fails, and the same record raises the exposure too. *Dated line 2026-11-09 (A, freeze; D4 field 12): a raise above 500,000 sat that also raises `max_fee_exposure_sat` changes a value the §4.5 losing-fee threshold uses (`max_fee_exposure_sat / max_gate_attempts`, 045b :500, :1176), so it is not a section 6.3 change: 045b :800-805 governs it (a revision under SSoT:2851). The section 6.3 path covers raises up to 500,000 sat.*
  4. New F_B = min(`max_feerate_sat_per_kvb`, ⌊1,000 × new cap / BEAT vsize⌋) sat/kvB, and the BEAT and REGISTER rates it allows.
  5. Reserve: the planner run at the new F_B (FEE :119; #671 note §9 A-1, A-2), the amount already funded, and the top-up. The top-up is funded before the new cap applies (045b §14.17 B3 note).
  6. Admission bound: the product admits at most 1,000 sat/vB (`checks.rs:523-529`, #426), and B-672 keeps that bound (A's (가), #672 issuecomment-6599534992). For a 263 vB BEAT, a cap above 263,000 sat therefore buys nothing until a B unit under FD-CT-62 raises the bound. That unit is not part of this record.
  7. Deadline: both S7 witnesses, the Bitcoin-confirmed OTS proof and the GitHub server time, are recorded before the first broadcast under the new record; until both are recorded the old cap holds. A plans for both by `A + 1,512` (AL-4).
  8. Reason, and the post on the Q5 channel (045b:790-795).
- **This fails if** a spike outruns the Founder. A raise in force only after `A + 1,089` (AL-2) leaves the BEAT below READY. One in force only after `A + 1,512` leaves at most the 504 blocks of W3/L3 for the build, signing and inclusion. Then the Heart may time out (:72, :83), and nothing restores it (MBA:376-377). The record then says that the cap held. This is the risk the Founder accepted in FD-CT-102.

### 7.11 Rust/Python comparison at tip ≥ H0 (finding #692; FD-CT-105, BATCH53; draft 2026-11-04)

(Claude plan, from A's ruling on finding #692, #692 issuecomment-6625106193 §2-§4, §7 and §13; the rule itself is 045b §14.19. Only the BEAT cutover, the TIMEOUT residual of the Not covered line and the segmented re-replay behind its 1,000-block bound rest on the Founder: the first two on the Founder's answer (가) to Q1 (from E, a gap in the availability family alone lets the BEAT proceed Rust-only, publicly labelled), the third on Q2 「예」, both at 2026-11-04 10:00:15Z, given in the A session; A's receipt #258 issuecomment-6627980792. It is FD-CT-105 text; FD-CT-105 is recorded in record 53, BATCH53 (`decisions/FD-CT-BATCH53_2026-11-05.md`; 045b §14.19, status).) This section adds the Reference operator role to section 2, AL-9 and AL-10 to the 7.4 alarm table (as 7.10 added AL-8), one line to each list of 7.5, and the recompute of 7.6 item 6. It is appended so that no earlier line moves. Ruling §13 put the alarms in section 4; the 7.4 form is used because they have bounds that HC-01 tests. **E** is a BEAT's cutover height (045b §14.19 item 3): `B + 144` for the first BEAT (W2 entry, :70; 1,872 blocks left, :190) and `A + 1,152` for every later BEAT (L2 entry, :81; 864 blocks left). The cutover applies only in W2, W3, L2 and L3, so a short stored `last_valid_beat_height` gives none (045b §14.19 item 3). *2026-11-05 (Claude plan; Reviewer RV-144, #664 issuecomment-6650421190): where a note in this file is marked "FD-CT-105, BATCH53", the record id reaches only the three items above; the MATCH requirement for a rebroadcast below E, WB9 and the authority-report rule are Claude plan (BATCH53 §2.2, §2.3).*

| Role | Duty | Must be reachable during |
|---|---|---|
| Reference operator | runs RM's comparator in the pinned container for each comparison link, or keeps the driver that runs it going, under a leg record; keeps the comparison follower current; acts on AL-9 | from H0 to the end of the campaign |

- **Who holds it.** One person may hold it with other roles (:42). Under FD-CT-53 there is no second person (:287; B22:40). B22:70, a Claude reading of FD-CT-53, places the H0−1 comparison on Founder equipment, checked automatically with the pinned Rust producer and RM's Python comparator; the comparison follower runs the same way (Claude plan). The host never runs Python (`crates/bitagi-launch-host/src/prestate.rs:13-17`). A driver that B builds may start the container and write the leg record, as for step 6 (`docs/claude-track/formats/REORG_STEP6_RECORD_V1.md:898`). Builder code never reads or includes reference code. Independence rests on the separate Builder and RM sessions, the host computing its own side from the nodes, the leg record and the Reviewer's rerun (same file, §11).
- **Availability rule** (Claude plan, in the form of the Signer rule at :55-58): before the REGISTER is broadcast, the Reference operator role confirms in a dated record that it can act from H0 through the first BEAT's E (`B + 144`). If it cannot, the REGISTER broadcast is not authorized (`ACTION_BLOCK`, 045a §4.4). The role stays reachable after that, as the Signer confirms only W1 but is reachable in every BEAT window (:51). The 120 s link bound is a Class T rig criterion (045b §14.19 item 8), not part of this confirmation. No backup role is declared: the Recovery operator's second container (AL-10) adds a second host, not a second person.
- **Follower cadence** (Claude plan; ruling §3). The comparison follower (not the store follower of the wait registry's W18) starts a link at every new agreed block and never waits to fill a batch. After a gap, a catch-up link covers at most 6 blocks. This reads the ruling's "or in batches of at most 6" as a catch-up bound: a follower that waited for 6 blocks would raise AL-9 on every batch. In routine operation from RM v15 the lag stays below 6, so AL-9 means the follower is not keeping up. Before v15 every link replays from H0−1 (045b §14.19 item 2), so the lag grows with tip − H0 and AL-9 can fire in routine operation.

| Alarm | Condition | Action |
|---|---|---|
| AL-9 `COMPARISON_LAG` | From H0, with or without a candidate: the lag is 6 or more. The lag is the agreed tip minus `compared_through_height`, the through height of the last MATCH link that still counts (H0 − 1 before the first link; 045b §14.19 item 2) | The Monitor tells the Reference operator and RM. The comparison follower catches up (at least 5 blocks per 600 s, 045b §14.19 item 8). Repeated availability-family refusals go to RM as a defect lead (045b §14.19 item 4). The alarm holds nothing and is not a stop |
| AL-10 `COMPARISON_LAG` wide | The lag is 36 or more; or tip ≥ E and a BEAT candidate that is not included has no MATCH chain through the current tip, so its next step would be `CutoverReplay`, or the host refusal of 045b §14.19 item 10 where the cutover is not admitted | The Monitor tells every role and the Founder. The Recovery operator starts a second comparison container on another host, in the pinned image and under its own leg record. From E, only a gap in the availability family lets the BEAT proceed as `CutoverReplay`, publicly labelled "Rust-only at broadcast" with its `compared_through` frontier (045b §14.19 item 3). A MISMATCH or a divergence-family refusal never cuts over, and an open reorganization, critical-height or import/restore lock still holds the BEAT (:95; 045b §14.19 item 6). The alarm holds nothing and is not a stop |

- **Bound and tests** (Claude plan; UNMEASURED, like the other bounds). B-692b's decision reports carry `compared_through_height`. BEAT-3b counts the 6 and 36 levels and also records the frontier in each BEAT observation (ruling §8, §9 case C23; A's answer to B's BEAT-3 draft, #258 issuecomment-6629923155, Q8). Until BEAT-3b a dated LATENT row says that no comparison alarm exists yet; the lag is reported as not yet counted, never as 0, and a Class T run on BEAT-3a is not evidence of alarm behaviour. -2c shows and delivers AL-9 and AL-10 with the other alarms (P5:319). HC-01 tests them at zero and ±1 around each bound, as for AL-0 to AL-8 (R2:489; :197): lag 0 and 5 (no AL-9), 6 and 7 (AL-9); 35 (no AL-10), 36 and 37 (AL-10); and, for a BEAT candidate with no MATCH chain through the tip, E − 1 (no AL-10), E and E + 1 (AL-10), each with lag 1, at both the first-BEAT and the later-BEAT E. It also tests a candidate at E whose chain ends one block below the tip (AL-10), one whose chain runs through the tip (no AL-10), and that neither alarm holds anything. BEAT-3b's cells include a mutant that turns an alarm into a stop.
- **READY** (Claude plan). A lag alone does not change READY (R2:519-520; :178-182): the Heart stays CURRENT, but its BEAT's Sign and Broadcast wait below E (WB9, 045b §14.19 item 11). For the first BEAT, E (`B + 144`) comes before AL-2 (`B + 1,089`, draft). For a later BEAT, E (`A + 1,152`) comes 63 blocks after AL-2 (`A + 1,089`, :203; a draft UNMEASURED bound, :197), so a wait that lasts until E passes AL-2 first. An open MISMATCH or divergence-family refusal is different: after birth the public status is UNKNOWN (TDS:1655; 045b §14.19 item 5), so the Monitor shows no READY until its release, as for AL-0 (:201). Before birth TDS 14.3 applies.
- **Re-broadcast at tip ≥ H0** (Claude plan; 045b §14.19 items 2 and 3): broadcasting an already signed BEAT again at a new tip is a broadcast at that tip. Below the cutover height E it waits for a MATCH chain through that tip, which from RM v15 is one comparison link while the follower is current (045b §14.19 items 7 and 8). From E an availability-only gap lets it go as `CutoverReplay`. Bytes a mempool still holds only wait for mining (WB3, 045b:1166) and need no comparison. W2, W3, L2, L3 and AL-5 lie at or past E, so there a comparison gap alone holds no re-broadcast. A MISMATCH or a divergence-family refusal holds it at any height (`STOP_DEFECT_DETECTED`, 045a:661), and so do the locks of :95.
- **Fault envelope** (7.5; Claude plan, UNMEASURED).
  - Covered, one fault at a time, where the comparison is admitted on the network (045b §14.19 item 10): the Python side is unavailable (the availability family, 045b §14.19 item 4). Below E the BEAT waits (WB9); from E it proceeds as `CutoverReplay`. As with the policy wait in 7.3 `B_include`, the wait ends at a fixed height. Counted from max(h, L1) for a fault at height h (max(h, W1) for the first BEAT), it adds at most E − L1 = 144 blocks (E − W1 = 143). Nothing on the BEAT's path is restored, so `B_restore` drops out. The other hour terms, 6 + 24 + 1 + 2 + 1 + 8 = 42 h, convert to 302 blocks (7.2), and `B_include`'s 6 and `B_reorg`'s 12 add 18. The path takes at most 144 + 302 + 18 = 464 blocks (463 for the first BEAT), inside 784, and from E it needs 320 of the 864 blocks left (1,872 are left at `B + 144`). So this wait adds nothing to `B_total`. The record is R2's sentence (R2:536), with the "Rust-only at broadcast" label.
  - Not covered: a Rust/Python MISMATCH, a divergence-family refusal or a TDS 14.8 digest case, at any height (045b §14.19 item 5). Its stop or lock holds every BEAT until its release, which needs a new MATCH chain from INITIAL; the re-replay bound alone is 1,000 blocks (045b §14.19 item 8), more than `B_total`. A lock still open at `A + 2,016` ends the Heart in TIMEOUT at `A + 2,017` (:72, :83), unless a BEAT broadcast before the lock is mined by then. For a real mismatch near the deadline, that is a residual the Founder accepted with FD-CT-105 Q1 as shown then (FD-CT-105, BATCH53). The horizon in 045b §14.19 item 9's precision list, and the case of a mismatch whose cause cannot be fixed, are precision given to the Founder afterwards, not part of that acceptance. Also not covered is the S2 case (045b §14.19 item 6): a reorganization or critical-height lock open while the Python side is down is two faults at once.
- **Waits and the 7.6 recompute.** 045b §14.19 item 11 registers W34 (late H0−1 comparison), W35 (REGISTER replay comparison) and WB9 (BEAT replay comparison below E). They are mandatory waits: registered, not budgeted (:223; R2:560). W34 and W35 end before birth (REG:25) and overlap no BEAT. WB9 can, so 7.6 item 6 (:246) fires. A owes the recompute as this file's author, and these lines are it (Claude plan; UNMEASURED):
  - Routine case, from RM v15 (045b §14.19 item 2), whose STATE links Class E needs: each Sign and each Broadcast waits for one one-block link (p95 ≤ 120 s, 045b §14.19 item 8). That fits inside `B_prepare` (1 h, :160) and `B_handoff` (1 h, :162). A Class T sample before v15 includes an INITIAL link from H0−1. Its link time is recorded apart and is not a sample of `B_prepare` or `B_handoff`; only the rest of the step's time is, under 7.6 item 1. A pre-v15 link over the 120 s bound goes to A and the Founder under 045b §14.19 item 8, not to a recompute.
  - Outage case: the Covered line above, at most 464 blocks.
  - Result: no `B_*` term, M, `B_total` (784), READY bound (928) or AL-0 to AL-8 bound changes; AL-9 and AL-10 are added.
  - This file is not frozen yet, so the recompute is part of the draft bytes that the Founder approves at A3 (:130). The S7 receipt is a follow-up registration that cites the prior registration hash (045b:1222), so it applies only once a record is registered; after that, :283 applies to every recompute that changes these bytes.
  - A measured link time over its bound goes back to A and the Founder (045b §14.19 item 8). If it pushes `B_prepare` or `B_handoff` over its assumption, 7.6 item 1 fires as well.
- **Campaigns and networks** (Claude plan; 045b §14.19 item 10). The gate holds on every network. The comparison runs on Regtest. On Signet it is admitted only after P5 item A9 (a) and the H0−1 Signet unit (P5:391; `docs/claude-track/formats/REORG_STEP6_RECORD_V1.md:1193-1213`); until then the host signs no BEAT there. A P5-002 (a) BEAT on Signet then stops as an explained interruption and gives no sample for 7.9, and `B_prepare` and `B_handoff` keep their assumptions (7.6 item 1). Where the comparison runs, a BEAT sample includes its link time. Before RM v15, a Class T BEAT whose INITIAL-only chain cannot reach its tip because of the 4,096-block limit is treated the same way: no cutover (045b §14.19 item 10). `main` stays refused until 044a-3 (QA-U3).
