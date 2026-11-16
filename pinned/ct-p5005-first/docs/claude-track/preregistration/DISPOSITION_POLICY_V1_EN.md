## 3. R3 Part III §10 disposition policy (draft)

SSoT:1863 requires a published disposition policy for ended Anchors and for
non-winning or abandoned candidates, defining: branch depth and uncertainty
assumptions, quarantine and review conditions, exact evidence to release a
reservation, descendant handling, cancellation attempts, and the accepted
residual risk of already released transactions. RT-8 asks that CPFP children,
cancellations and sweeps get approval and timing classes or be declared
unsupported (`docs/claude-track/audit/2026-10-02_protocol_purpose_audit/FINDINGS.json` id `RT-8`). IMPL-OPS-3 recommends publishing the
policy before the first candidate freeze "even if the policy is 'retain
forever, accepted residual'" (`FINDINGS.json` id `IMPL-OPS-3`).

This draft is a Claude plan. CT-P3-045b freezes it, its hash goes into the
budget record (section 4), CT-P3-044b enforces it in the ledgers, and the
Founder decides residual-risk acceptance (FD-CT-13, B2:102-109).

### 3.1 Policy: retain everything in SEM-1 (Claude plan)

| §10 element | SEM-1 draft |
|---|---|
| Scope | Non-winning, stale, abandoned and replaced REGISTER candidates and rungs; their `vout[1]` and change outputs; their descendants; ended Anchors. |
| Release of a reservation | **None in SEM-1.** No evidence releases a reservation: not a stale-gate label, a losing label, a cached ending, a confirmation count or elapsed time (SSoT:1702, :1867; MBA:353-355). Releasing any reservation requires a versioned successor of this policy and a Founder decision. |
| Branch depth / uncertainty assumptions | No depth is treated as final (SSoT:1704). Because nothing is released, the policy needs no depth threshold. Every branch change triggers reclassification of every released record (`reclassify`, SSoT:1867). Reorg testing depth follows FD-CT-02 / GOV072 (S07), which is evidence about the implementation, not a disposal threshold. |
| Quarantine / review conditions | A released record whose branch classification changes is quarantined by `reclassify` and stays released. Review is triggered by: any branch change touching a released record; inclusion of any rung; gate advance past a set's target; H0+144 and birth+144 (operational review triggers, MBA:348-349, :366-367). Review never authorizes a spend. |
| Descendant handling | Children of a replaced or invalidated parent become `ChildInvalid` and keep protection (today's code, `reservations.rs:2326-2327`). Released descendants keep their exposure records. Conflict-set siblings follow 1.4; an unconfirmed rung has no descendants (1.3 item 9). |
| Cancellation attempts | **Not supported in SEM-1.** The only real cancellation is spending a rung's input in a conflicting transaction (B1:49). The signer offers no generic send (`FINDINGS.json` RT-8 key evidence, inherited P3-006), and no cancellation workflow is declared (SSoT:1806 leaves cancellation to its own declared workflow). Stale candidates are handled by **replacement** (Option B, FD-CT-18, 3.4): a retry for the next gate reuses the inputs of an unmined stale set under the 3.4 conditions, and uses fresh fee inputs only where conditions 1 or 4 exclude reuse. The SSoT:1750 SHOULD counts as followed for a stale set only after a recorded replacement broadcast attempt (3.4 condition 3). *Historical:* the first draft used fresh inputs for every retry and attempted neither cancellation nor replacement (Option A); it was PROPOSED and the Founder did not choose it. |
| Sweeps (ended Anchors, losing `vout[1]`, ordinary cleanup) | **Not supported in SEM-1.** No sweep candidate is constructed or signed. Ended Anchors stay unswept. SSoT:1892 requires refusing a historical-Anchor sweep without replay-confirmed ending; SEM-1 goes further and supports no sweep at all. |
| CPFP | Declared unsupported in CT-P3-046b (ROADMAP row 6, RT-8). Not decided here. |
| Accepted residual risk of released transactions | See 3.2. Acceptance is the Founder's (FD-CT-13). Until accepted, the budget record cannot be Class E (section 4.3). |
| Reporting (SSoT:1869-1874, SHOULD) | CURRENT Anchor count and value; ENDED unswept count and value; estimated sweep cost; economically unsweepable residue; plus the section 2 counters. The report owner is CT-P3-046b or CT-P7-004 (Claude plan; not decided here). |

### 3.2 Residual risk of released transactions (draft text for the Founder)

Every released rung remains a valid Bitcoin transaction until one of its
inputs is spent elsewhere. Under the retain policy:

1. **Fee loss.** Any released rung, even long after its gate moved, can be
   mined. It then pays its fee and, if its gate is no longer open on that
   branch, creates no Heart (SSoT:1741). Per set the loss is at most the
   highest released rung fee; in total at most `fee_exposure_sat`.
2. **Locked principal.** A mined losing rung leaves its `vout[1]` Anchor amount
   under reservation, unswept, for the life of SEM-1. At most
   `principal_exposure_sat` can be locked this way.
3. **Branch-dependent winner.** A rung that lost on one branch can win on
   another where its gate is still open (SSoT:1752, :1865). It then creates a
   project Heart whose Anchor the wallet must track and BEAT. The four REGISTER-cap stops (`STOP_GATE_ATTEMPTS_EXHAUSTED`, `STOP_RELEASED_CANDIDATES_EXHAUSTED`, `STOP_FEE_EXPOSURE_CAP`, `STOP_PRINCIPAL_EXPOSURE_CAP`) do not hold that BEAT (4.4, "Holds"; #266). Every other open stop or block, and any open lock, holds it until its own release condition, including `STOP_EXACT_HEIGHT_MISSED` when the record says `STOP_CAMPAIGN` (#254 decision 2) and the two BEAT-cap stops (`STOP_BEAT_COUNT_EXHAUSTED`, `STOP_BEAT_REPLACEMENTS_EXHAUSTED`, #279), which hold every BEAT of every Heart until a new approved record. Without that release the Heart ends TIMEOUT at birth + 2,017 (SSoT:1100-1105) and is not restored (MBA:376-377). Stops are ledger-wide (the `stops` table has no scope column; `crates/bitagi-wallet/src/reservations.rs:152` at main `92565d34`). Because sets are
   REGISTER-only and spend zero CURRENT Anchors (TDS:1036), a released rung
   cannot break an existing Heart.
4. **No revocation.** No local act (deleting records, withdrawing approval, an
   RBF attempt) revokes a released rung (SSoT:1704; MBA:243-245).
5. **Inputs per retry (Option B, 3.4).** A retry reuses the inputs of an unmined
   stale set where conditions 1 and 4 allow. It reserves fresh fee inputs when a
   stale rung was mined or the cross-set floor would exceed
   `max_fee_per_candidate_sat`. Only those fresh-input retries grow the
   fee-wallet balance tied up with `gate_attempts`. The counted exposure does
   not shrink either way (2.2).

The fee and principal at risk are bounded before release by the FD-CT-13
caps in the budget record (`max_fee_exposure_sat`,
`max_principal_exposure_sat`). These caps count REGISTER rows only (2.2 rule 5). BEAT fees are outside them: each BEAT is bounded by its own approval and the per-candidate fee and feerate caps, and all BEATs by 045b's BEAT budget (045b Q3), which release enforces since #279 (`beat_count` and `max_beat_replacements`, 2.2 rules 5 and 6; the `release_budget` module doc, `crates/bitagi-wallet/src/release_budget.rs`). The Anchor amount defaults to 10,000 sats in
TDS 8.5 (TDS:1043); the exact value is a frozen-subject fact.

### 3.3 Options not chosen (Claude plan)

- *Option A: fresh inputs for every retry, no cancellation or replacement of a
  stale candidate.* Not chosen: the Founder chose Option B on 2026-10-04
  (FD-CT-18, 3.4). It stays in the 3.4 table only as the rejected
  alternative. (Before that decision this bullet listed Option B as the
  alternative put to the Founder.)
- *An explicit cancellation transaction class.* Not chosen for SEM-1: it is a
  new signer workflow (no generic send exists) with its own approval and
  timing class (RT-8). It would reduce 3.2-1 and 3.2-2 only after the
  cancellation confirms on every branch, which no depth guarantees
  (SSoT:1867).

### 3.4 Stale-candidate replacement: Option B (decided, FD-CT-18)

*Decided 2026-10-04:* the Founder chose **Option B** (FD-CT-18,
`../decisions/FD-CT-BATCH5_2026-10-04.md` §1). The Option B conditions below
now apply (Claude plan). CT-P3-044b enforces them in a new PR; until then the
ledger keeps refusing a cross-gate input reuse with `PendingFounderDecision`.
The deviation analysis and the option table below are the record of the
question as it was put (historical). Option A is the rejected alternative.
The Option B conditions after the table are the active rule.

*Historical (the open question):* **Is it a deviation?** Yes. SSoT:1750: "After any accepted birth advances the
gate, the wallet MUST treat an unmined candidate for the prior target as stale
and SHOULD attempt safe cancellation or replacement." The SHOULD is met by
either a cancellation or a replacement. Under 3.1 as drafted, SEM-1 does
neither:

- no cancellation transaction exists (3.1, RT-8);
- a replacement of a stale set would have to spend its inputs, but a retry
  for the next gate uses **fresh** fee inputs (3.1), and today's ledger
  refuses a cross-gate overlap (`same_replacement` compares the gate,
  `reservations.rs:1671`). A replacement for the *same* gate is meaningless
  once that gate has advanced.

So this part of the draft was not adopted as a Claude plan. It was
**PROPOSED** and needed a Founder decision before CT-P3-044b enforced the
disposition policy (decided: Option B, FD-CT-18). The rest of section 3 (no reservation release, no sweep, the
retain-and-reclassify rules) does not depend on it.

| | Option A: no cancellation or replacement (as drafted) | Option B: next gate's set reuses the stale set's inputs |
|---|---|---|
| SSoT:1750 SHOULD | not followed; disclosed in the CT-P7-004 notice | followed by replacement only when the next set's broadcast rung is an *effective* replacement (conditions below); once it is mined, every stale rung is invalid on that branch |
| Reason | simplest ledger; no cross-gate relation; a stale REGISTER spends no CURRENT Anchor, so it cannot break a Heart (3.2-3) | removes most of 3.2-1/2 for the stale set once the new set confirms |
| Residual risk | each stale released set stays mineable: up to its max rung fee and its `vout[1]` principal (3.2), and on a branch where its gate is still open it can still win (SSoT:1752) | until the new set confirms, the stale set is still mineable; on a reorg either can win on its own branch; no depth makes this final (SSoT:1867) |
| Cost | none now | a new 044b ledger relation (cross-gate conflict between sets of one lineage), new refusals and tests; the new set's fee inputs are fixed by the old set |
| Budget effect | `fee_exposure_sat` and `principal_exposure_sat` sum over all sets | unchanged as a bound (counting is conservative and never decremented, 2.2); the actual risk is lower |

**Option B conditions (Claude plan; active since FD-CT-18).** Reusing the
inputs alone is not an effective replacement: the 1.3 fee ladder binds rungs
within one set, so the next set's first rung could pay less than a stale rung
already in a mempool and be rejected. Under Option B:

1. Only the inputs of a stale set **none of whose rungs is included** on the
   evaluated branch can be reused; if a stale rung was mined, its inputs are
   spent and the next set uses fresh inputs for that set.
2. **Cross-set fee floor.** Every rung of the next set must pay at least
   `F_stale + max(1, ceil(r_inc × v_new / 1000))`, where `F_stale` is the
   highest fee among the stale set's **released** rungs and `v_new` the next
   set's vsize, and its feerate must exceed that stale rung's feerate
   (compared exactly by cross-multiplication, since `v_new` may differ).
   This applies across every stale set whose inputs are reused.
   **A stale set with no released rung** has no cross-set floor: no signed
   rung of it left the signer, so nothing in a mempool needs replacing, and
   the next set needs only its own 1.3 ladder. Once its inputs are reused,
   none of its held (signed, unreleased) rungs may be released. It adds
   nothing to `fee_exposure_sat` or `principal_exposure_sat` (2.2: those sum
   over sets with a released rung); it still counts in
   `reserved_conflict_sets` (Codex review of `016c3c7`).
3. Current Node A/B `testmempoolaccept` acceptance of the next set's rung
   against their current mempools is a **prerequisite** only: it reports
   whether the transaction would be accepted and adds nothing to a mempool
   (OVL:169-175 orders signed-final admission before the separate broadcast
   authorization and broadcast). The SHOULD counts as followed for a given
   stale set only after an **actual replacement broadcast attempt** is
   recorded: the separate human broadcast authorization, the broadcast, and
   its outcome (the exposure ledger's broadcast-attempt observation,
   `exposure.rs:1584-1604`). Withheld authorization or a failed or rejected
   broadcast is no attempt or a failed attempt; the stale set stays mineable.
   In every case the stale set keeps its full counted exposure (2.2 rule 3).
4. The cross-set floor counts against `max_fee_per_candidate_sat`; if the
   floor would exceed it, the next set cannot reuse the inputs.

CT-P3-044b ships this retry-input rule (conditions 1–4) in a new PR, with
the refusals and tests in section 6 item 12. Until that PR merges, the ledger
refuses a cross-gate input reuse with `PendingFounderDecision`. (Before
FD-CT-18 this paragraph said 044b must not ship either option's retry-input
rule as final.)
