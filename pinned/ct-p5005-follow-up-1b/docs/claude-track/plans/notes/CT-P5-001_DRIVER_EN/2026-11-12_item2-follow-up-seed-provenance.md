# ITEM2 follow-up policy: seed provenance, step 2 (H_s2 named) (2026-11-12)

```text
Status: NO PRODUCTION NETWORK ACTIVE · DO NOT ACTIVATE · Class P NO-GO · DO NOT GENESIS
Generation: D3.5 (Exact D3 Core unchanged)
```

Class T development record only. This is a Claude plan (A, CT-P5-005 owner), not a Founder decision, and it grants
no approval, signing, broadcast or release authority. It is step 2 of A's decision F5 (#258 issuecomment-6820596249)
and of A's request to B (#258 issuecomment-6821207522). `045b:N` is a line of the frozen
`docs/claude-track/plans/CT-P3-045b_PREREGISTRATION_DRAFT_EN.md`, which this unit does not change.

## 1. The policy and P2

- File: `docs/claude-track/preregistration/ARDR_POLICY_V1_CLASS_T_REGTEST_ITEM2_FOLLOW_UP.json`, written by B with
  the seed `PENDING_FREEZE` (B4-81).
- P2 = SHA-256 of those bytes =
  `9067922bf5b80c22b4285af2f7015ea3fd5237711a0b8035d7ac27abad72d0fd` (403 bytes).
- Second writer (A): A built the same file on its own from the request's key list (first policy's serialization:
  sorted keys, compact, ASCII, no trailing newline; ITEM2 only; `p0_rule` `MAX_P0_TWO_RUNGS`; seed
  `PENDING_FREEZE`) and got the same 403 bytes and the same P2. A also re-ran rows 1-4 of B's note section 2 on
  this branch (driver `check-policy`: EXPLORATORY exit 0 with `policy_sha256` P2; CONFIRMATORY `POLICY_PENDING`
  exit 3; a scratch copy with a dummy seed accepted in CONFIRMATORY; the same copy with `CEIL_2_5_B` refused
  `L0_POLICY_P0_RULE` exit 6). Same results. The scratch files were TEST_ONLY, outside the repository.

## 2. H_s2

- **H_s2 = 976,000** (Bitcoin mainnet height). A names it here, in the pull request that adds P2, before that block
  exists. A's estimate of Node A's tip at 2026-11-12 10:30Z was about 975,58x, so 976,000 is a few hundred blocks
  ahead and is expected around 2026-11-15 UTC.
- 045b:1901 named the first policy's H_s as the Node A tip plus 12. FOU-64 lets A choose the follow-up height. A
  chose a height further ahead so that the Founder can read it together with the Node B values for the first
  registration, in one sitting. The order that matters is unchanged: P2 is on `main` before block H_s2 is mined.
- The seed rule is 045b:1901's, unchanged: seed = SHA-256(ASCII `BITAGI_CT_ARDR_SEED_V1` ‖ 0x00 ‖ P2 ‖ H2), where P2
  is the 32 bytes above and H2 is the 32 bytes of the `getblockhash 976000` display hex.

## 3. Next steps (not done here)

1. When Node A's tip is at least 976,002, the Founder reads `getblockhash 976000` and that block's header time on
   Node A and on Node B (FOU-64). The two hashes must be equal; any difference stops the seed step until A
   re-decides.
2. A computes the seed and opens a follow-up pull request that changes only the policy's `seed` value, with the read
   values and the computation in its note. The policy's SHA-256 changes with that commit; the follow-up registration
   that carries ITEM2 pins the policy with the seed.
3. If the header time of block 976,000 is not later than the merge time of the pull request that adds P2, the seed
   step stops until A re-decides.

## 4. Step 3: the reads and the seed (dated addition, 2026-11-16)

- **The reads (FOU-64).** On 2026-11-16 (UTC) the Founder read block 976,000 on Node A (tip 976,037) and on Node B
  (decision file `docs/claude-track/decisions/FD-CT-140_2026-11-16.md`, rows (2) and (3)):
  - `getblockhash 976000` = `00000000000000000000aeb828d7a8e9675a474c1be11d41e78c0d9d7dc1d8d2` on both nodes.
  - header `time` 1794767156 (2026-11-15T18:25:56Z) on both nodes; `mediantime` 1794763268 on both nodes.
  - The two hashes are equal (section 3, step 1 holds). The header time is later than #832's `merged_at`
    1794484717 (section 3, step 3 holds), so P2 was on `main` before block 976,000 was mined.
- **The seed.** seed = SHA-256(ASCII `BITAGI_CT_ARDR_SEED_V1` ‖ 0x00 ‖ P2 ‖ H2) =
  `05282a0387ea78485653e9bb73cba84adf967c0b212b5fbff7e92d54a9d270c7`, with
  P2 = `9067922bf5b80c22b4285af2f7015ea3fd5237711a0b8035d7ac27abad72d0fd` and
  H2 = the block hash above. A computed it twice: with `tools/claude_track_p5005_registration.py seed` (two node
  read files, exit 0) and on its own from the rule. The Reviewer recomputes it without the tool.
- **The policy.** The seed pull request changes only the policy's `seed` value, from `PENDING_FREEZE` to the seed.
  The new file is 453 bytes, SHA-256 `463dd43d7087fd71ab1f4da6c5f050217a77a8ee7f7b53f59680713e2b1eac7e`. Putting
  `PENDING_FREEZE` back gives P2's 403 bytes again.
- **Next.** The follow-up registration 1b pins this policy and this note (B4-82). Its pull request follows this one.
