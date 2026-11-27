# Item-4 follow-up policy: the policy bytes and seed provenance, step 2 (H_s3 named) (2026-11-25)

```text
Status: NO PRODUCTION NETWORK ACTIVE · DO NOT ACTIVATE · Class P NO-GO · DO NOT GENESIS
Generation: D3.5 (Exact D3 Core unchanged)
```

Class T development record only. This is a Claude plan (A, CT-P5-005 owner), not a Founder decision, and it grants
no approval, signing, broadcast or release authority. It is step 2 of the seed rule for CT-P5-005 follow-up
registration 3, which carries ARDR item 4 only (A decision #258 issuecomment-7149229274, items 1 and 2). `045b:N` is a
line of the frozen `docs/claude-track/plans/CT-P3-045b_PREREGISTRATION_DRAFT_EN.md`, which this unit does not change.
The model is the ITEM2 follow-up (1b): policy #832 and its note
`docs/claude-track/plans/notes/CT-P5-001_DRIVER_EN/2026-11-12_item2-follow-up-seed-provenance.md`.

## 1. The policy and P3

- File: `docs/claude-track/preregistration/ARDR_POLICY_V1_CLASS_T_REGTEST_ITEM4_FOLLOW_UP.json`, seed
  `PENDING_FREEZE`. Serialization as the first policy and the ITEM2 follow-up policy: sorted keys, compact, ASCII,
  no trailing newline.
- **P3** = SHA-256 of those bytes = `657f920ab8dd0ce87be4ee9c1d3f3a41d4331d3ec5026112018e3dc99ed995f5` (1,378 bytes).
- Contents and sources:

| Key | Value | Source |
|---|---|---|
| `schema` | `BITAGI_CT_ARDR_POLICY_V1` | the first policy, ARDR_RUN_V1 section 3 |
| `bidders` | `[]` | 045b:1901 (the first policy's `bidders`) |
| `counts` | 50 for each of `ITEM4_SELF_DEALING`, `ITEM4_FEE_ASYMMETRY`, `ITEM4_CENSORSHIP`, `ITEM4_REORG` | 045b:1250; `tools/claude_track_ardr_item4.py` `ITEM4_RUNS` |
| `experiments.<E>.miner_policy` | `ITEM4_SELF_FIRST_ZERO_FEE`, `ITEM2_DEFAULT`, `ITEM4_CENSOR_144`, `ITEM4_REORG_REPLACE` (in that order of E) | `tools/claude_track_ardr_driver.py` `ITEM4_MINER` |
| `experiments.<E>.params` | `b` 6,000, `H0` 1,000, `gates_per_run` 1 | 045b:1901 (F10), :1054 |
| `experiments.<E>.l0_seat` | `p0_rule` `MAX_P0_TWO_RUNGS`, `max_gate_attempts` 24, `exact_height_miss` `CONTINUE_WITHIN_LIMITS`, `budget_sha256` `7d0a7a35ffa4df11311955d11e00b8c9c0f0f7df5c6e84c222911d447c7f4dd4`; no `seat` key | FD-CT-133 (the p_0 rule, as in the ITEM2 follow-up policy); 045b:98, :1901; the SHA-256 of `docs/claude-track/preregistration/CAMPAIGN_BUDGET_V1_CLASS_T_REGTEST_L0.json`; `driver.py` `check_l0_seat_shape` (item 4 takes the four keys only) |
| `seed` | `PENDING_FREEZE` | 045b:1901 |

- Two writers. A wrote the file from the key list above. A second, separate computation (A's planning session for
  this registration, from the tools and 045b, before A's own) gave the same 1,378 bytes and the same P3. The Reviewer
  re-derives the bytes when it checks the registration.
- Not in this file: the factor 10 (F15) and item 4's other DRAFT values are constants of the pinned tools; follow-up
  registration 3 fixes them by pinning those tools, and its evaluation policy lists them (045b:1078, :1198).

## 2. H_s3

- **H_s3 = 977,600** (Bitcoin mainnet height). A names it here, in the pull request that adds P3, before that block
  exists.
- A's estimate of Node A's tip at 2026-11-25 02:00Z is about 977,40x–977,47x. The last read height is 976,886 at
  2026-11-21T10:38:35Z (FD-CT-145 (9)), and blocks came at about 156 per day from 976,000 (2026-11-15T18:25:56Z,
  FD-CT-140) to 976,886. So 977,600 is about 130–200 blocks ahead, expected between about 2026-11-25 21:00Z and
  2026-11-26 14:00Z.
- 045b:1901 named the first policy's H_s as the Node A tip plus 12. FOU-64 lets A choose the follow-up height, as A
  did for 1b (976,000, a few hundred blocks ahead). A chose a height far enough ahead that this pull request merges
  well before it, and near enough that the Founder can read it on 2026-11-26. The order that matters is unchanged:
  P3 is on `main` before block H_s3 is mined.
- The seed rule is 045b:1901's, unchanged: seed = SHA-256(ASCII `BITAGI_CT_ARDR_SEED_V1` ‖ 0x00 ‖ P3 ‖ H3), where P3
  is the 32 bytes above and H3 is the 32 bytes of the `getblockhash 977600` display hex.

## 3. Checks run on this branch (TEST_ONLY scratch copies outside the repository)

| Check | Result |
|---|---|
| `tools/claude_track_ardr_driver.py check-policy --mode EXPLORATORY` with this file, each of the four experiments | exit 0, `policy_sha256` P3, the miner policy above |
| The same in CONFIRMATORY with no registration | `REGISTRATION_MISSING`, exit 3 |
| The judge's `parse_item4_policy(…, 'CONFIRMATORY', E)` on this file | `POLICY_PENDING` for each E |
| A copy with a TEST_ONLY dummy seed (`00` × 32): `parse_item4_policy` CONFIRMATORY | accepted for each E, count 50 |
| The same copy: the driver's `load_policy('EXPLORATORY', …, complete=True)` | accepted for each E |
| The dummy copy with `p0_rule` `CEIL_2_5_B`: `parse_item4_policy` CONFIRMATORY | `POLICY_L0_VALUES` |
| `claude_track_ardr_item4.plan_run(E, dummy seed, r, params, 'CONFIRMATORY', l0=True)`, r 0..49 | 50 accepted for self dealing, fee asymmetry and censorship; ITEM4_REORG refused `ITEM4_L0_REORG_CONFIRMATORY` (lifted by B's B1, work table B4-26, before the registration) |

## 4. Next steps (not done here)

1. When Node A's tip is at least 977,602, the Founder reads `getblockhash 977600` and that block's header time on
   Node A and on Node B (FOU-64). The two hashes must be equal; any difference stops the seed step until A
   re-decides.
2. If the header time of block 977,600 is not later than the merge time of the pull request that adds P3, the seed
   step stops until A re-decides.
3. A records the reads in that day's decision file, computes the seed (with the registration tool's `seed` command
   and on its own from the rule) and opens a pull request that changes only the policy's `seed` value, with the read
   values and the computation in a dated section of this note. The Reviewer recomputes the seed without the tool.
4. Follow-up registration 3 pins the policy with the seed, this note, and the tools B1 changes. Its pull request
   follows the seed pull request and B1.

## 5. Step 3: the reads and the seed (dated addition, 2026-11-26)

- **The reads (FOU-64).** On 2026-11-26 (UTC) the Founder read block 977,600 on Node A (tip 977,657) and on Node B
  (tip 977,660) (decision file `docs/claude-track/decisions/FD-CT-154_2026-11-26.md`):
  - `getblockhash 977600` = `0000000000000000000059711cf0fcba3f17a37ea77b7750cc555d3dd22b5f84` on both nodes.
  - header `time` 1795652531 (2026-11-26T00:22:11Z) on both nodes; `mediantime` 1795651149 on both nodes.
  - The two hashes are equal (section 4, step 1 holds). The header time is later than #950's `merged_at`
    1795577599 (2026-11-25T03:33:19Z; section 4, step 2 holds), so P3 was on `main` before block 977,600 was mined.
- **The seed.** seed = SHA-256(ASCII `BITAGI_CT_ARDR_SEED_V1` ‖ 0x00 ‖ P3 ‖ H3) =
  `4fd4a1e59fc195f7ae909a46e2c7a07e863eaa24515746fae44a2bf12a46f166`, with
  P3 = `657f920ab8dd0ce87be4ee9c1d3f3a41d4331d3ec5026112018e3dc99ed995f5` and
  H3 = the block hash above. A computed it twice: with `tools/claude_track_p5005_registration.py seed --scope
  FOLLOW_UP_3` (two node read files, exit 0) and on its own from the rule. The Reviewer recomputes it without the tool.
- **The policy.** The seed pull request changes only the policy's `seed` value, from `PENDING_FREEZE` to the seed.
  The new file is 1,428 bytes, SHA-256 `0e724087845287ab59901069ed1ad9b46a7880badec4f26a8faa0eda92c4e1d3`. Putting `PENDING_FREEZE` back gives P3's 1,378 bytes again.
- **Next.** Follow-up registration 3 pins this policy and this note (section 4, step 4). Its pull request follows this
  one.
