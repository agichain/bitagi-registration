# SEM-1 campaign fee policy

**FROZEN — CT-P3-045b freeze; values written 2026-11-09 (Claude plan). Hash subject `fee_policy_sha256` of the campaign budget record (045a §4.2); any change is a new file, a new record and a new approval.**

Work item: CT-P3-045b (CR-07). Protocol impact: `NONE`. Class T development;
`release_authorization` NONE. Main draft:
`docs/claude-track/plans/CT-P3-045b_PREREGISTRATION_DRAFT_EN.md` (abbreviations
and labels as there).

At freeze this file loses the DRAFT header, every "filled at freeze" cell gets
its value, and SHA-256 of the exact frozen bytes becomes `fee_policy_sha256` in
the campaign budget record (045a §4.2). CT-P3-042b binds that hash into the
launch artifact (CRD:43); CT-P3-044a-3 uses it after the 045b freeze
(FD-CT-19, B5 §3). This draft grants no fee, signing or broadcast authority
and binds no artifact.

## 1. Scope

- Applies to every project REGISTER rung and BEAT (including BEAT
  replacements) of the SEM-1 campaign, Class T rehearsals and the Class E
  campaign alike. Class T values may differ; they are labelled Class T.
- Fee reserves stay separate from Anchor value (SSoT:1798). The Anchor amount
  is a frozen-subject fact (TDS 8.5 default 10,000 sat, TDS:1043), not a fee.
- No reserve model guarantees inclusion (SSoT:1798). Signet fee results do not
  establish mainnet fee survivability (MBA:273-274).

## 2. Initial feerate (source, TDS 8.10)

The initial feerate `b` is the maximum of (TDS:1137-1144):

| Input | Definition (Claude plan) | Value |
|---|---|---|
| conservative `estimatesmartfee` target | `estimatesmartfee <target> CONSERVATIVE` on Node A and Node B; the larger | target blocks: 2 (REGISTER rung 0), 6 (BEAT); read on both nodes when the value is used. Freeze-time read (Node A, 2026-11-09, tip 975,182): 2,004 sat/kvB at target 2, 689 at target 6 (main draft :1182, A8) |
| recent-block percentile policy | the given percentile of the per-transaction feerates in the last N blocks, both nodes, the larger | percentile 75 of Bitcoin Core's vsize-weighted `getblockstats` `feerate_percentiles` (sat/vB × 1,000; the product's reading, not a count over transactions), N = 6, read when the value is used. Freeze-time read (Node A): 6,000 sat/kvB, from 75th percentiles 2, 1, 3, 5, 2 and 6 sat/vB at 975,177–975,182 (main draft :1182, A8) |
| operator floor | a fixed floor | 1,000 sat/kvB (main draft :1182, A8) |
| configured emergency floor | a fixed floor, always one of the four inputs (TDS 8.10 lists it unconditionally; the reserve code includes it unconditionally, `crates/bitagi-wallet/src/fee_policy.rs:823-830`) | 1,000 sat/kvB, equal to the operator floor (main draft :1182, A8) |

All feerates are integers in sat/kvB, computed with checked `u64`
arithmetic; no floats (AGENTS.md §4).

## 3. REGISTER rungs (pointer)

The REGISTER ladder is the conflict set of 045a §1.3 with the values in the
main draft §1.2-1.3: up to 8 rungs, ratio 1.5 from `b`, each step at least the
045a §1.3 item 5 BIP125 increment using the larger declared
`incrementalrelayfee` of Node A and Node B. Every rung is a separately frozen
and approved subject (FD-CT-01, B1:26).

## 4. Caps

| Cap | Value |
|---|---|
| `max_feerate_sat_per_kvb` (every rung and every BEAT) | 1,464,000 sat/kvB: max(the top REGISTER rung feerate at the freeze-time `b`, 102,517 sat/kvB; `p_high`, 1,464,000), rounded up to a multiple of 1,000; `p_high` is the peak feerate of the TDS 8.10 prolonged high-fee scenario (section 6), from the 1E Q17 `getblockstats` read (main draft §13; FD-CT-93) (Claude decision, A #258 issuecomment-6545342828, 2026-10-31; main draft :1179, A5) |
| `max_fee_per_candidate_sat` (every rung and every BEAT) | 30,000 sat (FD-CT-102, #258 issuecomment-6581164081). The Founder raises it in a spike with a new budget record (045a §4.2); it never rises on its own. |
| `max_fee_exposure_sat` | 500,000 sat (FD-CT-102, #258 issuecomment-6581164081) |

Why `p_high` is in the feerate cap (same source): a BEAT above the cap is
refused, and if fees stay above it until the Core deadline `A + 2,016`
(section 5), the Heart ends. At a low freeze-time `b` the top rung alone can
sit below that peak (about 35 sat/vB at `b` = 2 sat/vB).

A candidate above any cap is refused at freeze and at release, REGISTER rungs
and BEATs alike; a BEAT is also checked at an offline charge (#279; 045a §2.2
rule 6, §4.3 "candidate over cap"). Caps are never raised by an escalation; a
higher cap is a new budget record with a new Founder approval (045a §4.2).
The wallet takes up a new record only through `clear_budget_stop` on an open
budget stop (main draft §6.3). A budget stop can be raised on purpose first
(`raise_stop`), so a re-pin need not wait for a cap to be used up. The
operating commands for it are not built yet (main draft §11 Q2). *Correction 2026-11-02 (045b freeze draft 1; checklist S6): #583 (merged 2026-10-29) built the host's first pin and re-pin. Section 8.*

## 5. BEAT fees and replacements

- Each BEAT is built when due at the then-current `b` (section 2, BEAT target);
  no presigned BEAT chain (SSoT:1696; main draft §1.7).
- A BEAT replacement is a new frozen subject with a strictly higher fee that
  satisfies the BIP125 increment for its measured vsize, and counts once
  against `max_beat_replacements` when it is released (SSoT:1798). Release
  counts every released BEAT of a slot (one Heart anchor in one context)
  after the first, over the ledger's whole life (045a §2.2 rule 5, #279);
  each slot counts once against `beat_count`. Going over either cap raises
  its stop (`STOP_BEAT_REPLACEMENTS_EXHAUSTED`, `STOP_BEAT_COUNT_EXHAUSTED`),
  which holds every BEAT until a new approved record (045a §4.4). It never changes the successor
  key without explicit revocation of the prior candidates and a re-run successor-control proof (TDS:1133).
- Escalation trigger (Claude plan), always relative to the current Anchor
  height `A` from replay, never to a broadcast time:
  - first BEAT (`A` = the accepted REGISTER height `B`): tip ≥ `B + 144` and
    the first BEAT not included (birth+144 escalation point, MBA:366-367;
    FIRST_BEAT_OPERATIONS window W2);
  - later BEATs: tip ≥ `A + 1,152` (the 1,008-block target plus 144) and the
    BEAT not included;
  - any BEAT: tip ≥ `A + 1,512`, fewer than 504 blocks before the Core
    deadline `last_valid_beat_height = A + 2,016` (B3 §1).
  The emergency floor is always part of `b` (section 2), so escalation does
  not change `b`. Under escalation a replacement may be built each block.
  Its feerate is `max(b, ceil(p × 3 / 2))`, with `b` the then-current
  initial feerate (section 2, BEAT target) and `p` the feerate of the BEAT it
  replaces, both in sat/kvB; its fee is at least that BEAT's fee plus the
  BIP125 increment for its measured vsize (045a §1.3 item 5); and it stays
  within the caps. The ratio 1.5 is the REGISTER ladder's (section 3). Each
  one released uses one unit of `max_beat_replacements`.
- (Claude decision, A #258 issuecomment-6545342828; 2026-10-31) The reserve
  model keeps its linear `Step` ladder for BEAT replacements (rungs
  `b + k × step` for `k` = 1 to `n`,
  `crates/bitagi-wallet/src/fee_policy.rs:1330-1345`); no code change. The
  geometric rule (ratio 1.5, above) is used only when a replacement is built.
  `step = ceil(2 × (max_feerate_sat_per_kvb − b) / (n + 1))` sat/kvB, with
  `n = max_beat_replacements`, so the reserve's replacement total is at least
  `n × ceil(BEAT vsize × max_feerate_sat_per_kvb / 1,000)` sat (vsize in vB,
  the cap in sat/kvB; the cap is a multiple of 1,000, so the ceiling is
  exact), the worst case of all `n` replacements at the feerate cap. The
  other option, a short ladder per BEAT
  event (a CT-P3-009 code change), would need less reserve but a code change
  and is less conservative, so it is not taken. A's check (BEAT vsize about
  263 vB, an estimate; the feerate cap taken as the rounded top REGISTER rung
  at the same `b`): at `b` = 1 / 5 / 10 sat/vB, `step` is 337 / 1,604 /
  3,189 sat/kvB and the reserve 473,937 / 2,261,903 / 4,498,520 sat, against
  worst cases of 473,400 / 2,261,800 / 4,497,300 sat. Each rung's fee rises
  by at least 88 sat, so the `Step` ladder's strictly-increasing condition
  holds. *A decision 2026-11-02 (FD-CT-102 follow-up; #671 note §9 A-1): with the per-candidate cap set, `max_feerate_sat_per_kvb` in `step` is replaced by F_B = min(`max_feerate_sat_per_kvb`, ⌊1,000 × `max_fee_per_candidate_sat` / BEAT vsize⌋), 114,068 sat/kvB at 30,000 sat and 263 vB, so the replacement total is at least n × 30,000 = 3,000,000 sat. Reason: the launch host refuses any candidate above the caps before signing (`crates/bitagi-launch-host/src/checks.rs:518-522`, `crates/bitagi-wallet/src/campaign_budget.rs:229-241`).* *Correction 2026-11-03 (DX-1 wave 1a F22; A #664 issuecomment-6593322614): "the cap is a multiple of 1,000, so the ceiling is exact" holds only for a rate that is one, and no code makes it so. The planner takes any positive integer rate and step (`crates/bitagi-wallet/src/fee_policy.rs:296-304`, `:1330-1347`), rounds each fee up (`:319-329`) and, among rungs, refuses only one past the planning cap or one whose fee does not rise (`:1212-1219`). The multiple of 1,000 is section 1's freeze rule for `max_feerate_sat_per_kvb`; F_B (114,068) is not one. For any rate F in place of the cap, the total is at least n × BEAT vsize × F / 1,000 sat; when F is not a multiple of 1,000 it can fall short of n × ceil(BEAT vsize × F / 1,000) by less than n sat. At the draft values (263 vB, n = 100, F_B) A computed the total for every integer `b` from 1,000 to 114,067 sat/kvB: it is at least 3,000,000 sat each time (least margin 0 sat, at `b` = 13,068). The freeze-time run repeats this with the measured vsize.*

## 6. Reserve (CT-P3-009 PR-2 parameters)

The reserve covers at least the TDS 8.10 floors (TDS:1146-1153); the
preregistered counts here are higher (STATUS §2, CT-P3-009 PR-2 accepts larger
counts and reports them):

| TDS 8.10 category | TDS floor | Preregistered (draft) |
|---|---|---|
| REGISTER gate attempts | 5 | 24 (`max_gate_attempts`) |
| REGISTER replacements | 10 | 168 (24 × 7 rungs after the first) |
| BEATs | 20 | 60 (`beat_count`; Founder, FD-CT-92 row 2 = Q3 (a), decided 2026-10-27, B45:62) |
| BEAT replacements | 20 | 100 (`max_beat_replacements`; Founder, FD-CT-92 row 2, B45:62) |
| two-node broadcast recovery | — | 2 REGISTER and 2 BEAT (the PR-2 minimum) |
| prolonged high-fee incident | one scenario | heights 500,054–504,373 of the Q17 record: the 4,320-block window (30 days at 144 blocks a day) with the highest mean `b_obs`; mean 715,367 sat/kvB, peak 1,464,000 sat/kvB, so its per-occurrence fee path peaks above `b` (main draft :1181, A7; Q17 note §3) |

Reserve size is computed from measured transaction vsize and observed fee
distributions, never a fixed BTC number in this file (TDS:1155). The model is
tested against published historical fee traces and injected broadcast failures
(SSoT:1798) before freeze. *Note 2026-11-02 (045b freeze draft 1; checklist S19): this conflicts with `docs/claude-track/plans/CT-P3-009_BRIEF_EN.md:334` ("P5"; FD-CT-101 S-061, B49:128). Before the freeze A either tests the model on the Q17 record or rewords this sentence to what is true (section 8; main draft §14.Z, B4).* *Done 2026-11-09 (A, freeze): option (a); the Q17 runs and the freeze-time run are cited in main draft §14.21 (B4, :1287).*

## 7. Changes

Any change to this policy after freeze is a new file, a new
`fee_policy_sha256`, a new budget record and a new Founder approval of that
record (045a §4.2). Frozen candidates under the old policy keep their own
approvals and are not reinterpreted, but after a re-pin they cannot be released: the wallet releases only under the pinned record (`release_budget::admit`, `crates/bitagi-wallet/src/release_budget.rs`), and presenting the old record persists `STOP_BUDGET_RECORD_MISMATCH`, which holds every row, BEATs included (first-BEAT operations §4). Refreeze them under the new record (#266).

## 8. Freeze lines (draft, 2026-11-02, Claude plan)

Appended so that every line above keeps its number (main draft §14). `:N` is a line of this file at main `d9322e59`. **[A wording draft]** marks a line whose substance was decided before its wording; A reviewed and finalized that wording on 2026-11-09. What is still open is listed in main draft §14.Z.

- In the draft, no change: the `max_feerate_sat_per_kvb` rule (:53) and the `Step` rule (:101-119), both since #628 (A #258 issuecomment-6545342828).
- (amends :53; checklist S9) The fee observations are the 1E Q17 `getblockstats` read (main draft §13; FD-CT-93), not 044c-1 records. The cap's value waits for that read. *Filled 2026-11-09 (A, freeze): 1,464,000 sat/kvB (main draft :1179, A5).*
- (amends :66-69; checklist S6) #583 (merged 2026-10-29, `37fee9b0`) built the host's first pin and re-pin (`LaunchHost::pin_budget`, `LaunchHost::repin_budget`; first-BEAT operations §4 row 98). A binary command comes with the unit that adds a turn runner (A #258 issuecomment-6470995554, pin Q1).
- **[A wording draft]** (amends sections 4-6; QA S-061, FD-CT-101, B49:128; SSoT:1798) This policy states SSoT:1798's four release values: the BEAT size distribution, as the measured vsize of each BEAT shape the BEAT unit builds (two shapes, each an Anchor and exactly one fee input, key-path signed: 220 vB, weight 878, without change, and 263 vB, weight 1,050, with one P2TR change output; a BEAT carries exactly one fee input; the reserve prices every BEAT at 263 vB, the larger; exact key-path weights of the product shapes, `crates/bitagi-wallet/tests/fee_policy.rs:414-415` and `crates/bitagi-wallet/tests/beat_caps.rs:857-865`, with no real-node BEAT record yet; main draft §14.21); the fee-rate budget, `max_feerate_sat_per_kvb` and `max_fee_per_candidate_sat` 30,000 sat (section 4; FD-CT-102); the maximum replacement-attempt budget, `max_beat_replacements` 100 (section 6; FD-CT-92 row 2); and the reserve-cycle target (main draft §14.17, B3). *A decision 2026-11-02: main draft §14.17 (B3) defines the reserve-cycle target.*
- (amends :136-139; checklist S19; QA S-061, B49:128) "Tested against published historical fee traces … before freeze" conflicts with `docs/claude-track/plans/CT-P3-009_BRIEF_EN.md:334`, which puts that test in P5. Before the freeze A either runs the model on the Q17 record or rewords the sentence to what is true, and puts the chosen line in main draft §10 (main draft §14.Z). The fee-trace identity is the SHA-256 of the Q17 JSON Lines output. *A decision 2026-11-02: main draft §14.17 (B4).* *Settled 2026-11-09 (A, freeze): option (a); main draft §14.21.*
- (amends :33-36; checklist S20) Which written values in section 2 are fixed, and which part is the freeze-time node read, is open (main draft §14.Z). *Settled 2026-11-09 (A, freeze; main draft :1182, A8): targets, percentile, N and both floors are fixed values of this file; the node inputs are read when the value is used; the freeze-time read sets the REGISTER ladder (main draft §14.21).*
- (amends :134) The prolonged high-fee incident period comes from the Q17 record: the 4,320-block window with the highest mean `b_obs` (the Q17 source note of main draft §13, :64-67). Its value is open (main draft §14.Z). *Dated line 2026-11-09 (A, freeze): filled at :134.*
