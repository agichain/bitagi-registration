# GOV072 — SEM1 prospective validation budget successor

Artifact: BITAGI_SEM1_GOV072_VALIDATION_BUDGET_2026_09_18_V1.
Authority: explicitly requested Founder amendment to prospective SEM1 TDS
validation quantities. Local adoption is PREPARED_LOCAL_ONLY pending verified
shared integration. This publication does not report any campaign execution,
endurance, readiness, gate PASS, release authorization or mainnet authority.

## 1. Exact supersession and preserved sources

This addendum replaces only the prospective SEM1 quantities for TDS section10
gates S07/S08/S13, section11's P5 endurance schedule and scoped section11.4
quantity prohibition, section17's Signet-risk mitigation period and AppendixB's
reorg/crash command counts. Sections9.2,19 and20.1 remain unchanged. S07 requires exactly
1,000 distinct randomized reorganization histories; S08 exactly1,000 distinct
executed crash-injection points; S13 private Signet requires at least86,400
seconds of qualifying continuous actual operation under the preregistered rules.
The Founder requested one day or less; this implementation chooses one complete
24-hour interval, the upper boundary of that request. No shorter observation is
silently authorized by this choice. The source statement and this interpretation
are recorded separately in the adoption intent.

This scoped successor also replaces GOV070's issued prospective reorg/crash
quantities and GOV071's retention of actual30-day private Signet, including its
derived REQ-MBL-ASSURANCE prohibition against a shorter interval. That prohibition
now rejects any interval shorter than86,400 qualifying continuous actual seconds.
The Founder's explicit prospective revision supersedes TDS section11.4's
prohibition on reducing reorg/crash evidence only for these approved quantities.
It also supersedes GOV061's retained100k/10k/10k and30-day quantities only as
100k/1k/1k and86,400 seconds, and the30-day private Signet retention in item4 of
`BITAGI_SEM1_R3_A2_COMPATIBILITY_2026-09-07_EN.md`. No observation-driven
relaxation or other prohibition is relaxed. GOV059/GOV061's other workflow
rules, GOV071 launch semantics and every unmentioned requirement remain in
force. Original documents, hashes, requirement maps, execution receipts,
failed trials and original10000-case preparation remain immutable history.

The sealed TDS SHA256 is257bd0790ca717dcb4fa04770c1f65af75a25e04f86cab8958a1269bf07a5ab1.
The predecessor D requirements SHA256 is a53bd83655ac240b4bf0572baa0454b05a33a7ab5d97a1f0711bea4178b7c1bf.
The GOV071 launch addendum SHA256 is1ee3e50854417f4b354df53a83f5aac32ad9cad2f87d4df5aac76e7c2c815d34.
R3-A2 remains77c928388be10f1383d40cea7bfb77ca5116f2d5976edfbc6a3ec39dd241b45f.
Core and corpus identities and Bitcoin validation semantics are unchanged.

## 2. Reorganization campaign

Retain the existing seed0x0000000000040005, SplitMix64 definition, actual
rollback/replacement versus independent complete replay from effective height,
canonical-byte/digest equality and context isolation. Count exactly1,000 distinct
preregistered histories. Minimum typed coverage is:

| Category | Minimum |
|---|---:|
| depth1 | 100 |
| depth2 through6 | 200 |
| depth7 through144 | 200 |
| depth145 through288 | 100 |
| birth on replaced branch | 50 |
| BEAT on replaced branch | 50 |
| ending on replaced branch | 20 |
| different gate with empty CURRENT | 10 |
| replacement branch differs | 1,000 |
| checkpoint roundtrip | 100 |

Retain at least128 independently source-derived known-answer histories and
maximum depth288. Freeze the successor's complete ordered ID/input/coverage
inventory before any counted run; merely truncating the original ordered10000
recipes is forbidden. Preparation controls and negative wrong-context cases do
not count. Original prepared inputs and controls may be cited only under their
original identities and applicable scope; no historical execution is relabeled.
Retain43200s total,120s per history,512MiB driver and8GiB output limits. Current
source-bound measurement and all existing readiness controls remain mandatory.

## 3. Crash campaign

Retain seed0x0000000000040006 and the existing SplitMix64 definition. Count
exactly1,000 distinct actual context/input/injection-boundary observations.
Each of the seven declared abstract boundaries has at least100 executed points:
before begin; after candidate validation before write; after state write before
undo; after undo before metadata; after metadata before commit; after commit
before publication; after publication before acknowledgement.

Before collection, preregister an exhaustive source-derived map from every
abstract boundary to its actual concrete hook(s), including every additional
separate implementation hook. Every distinct concrete hook must execute at least
once. Missing hooks, combining distinct sites to hide gaps, or an absent map
make readiness unavailable. If complete coverage cannot fit within1,000 points,
the campaign is NOT_READY until an explicitly authorized successor resolves it;
do not drop hooks or silently increase the denominator. Retain128 independent
known-answer points, observed termination and reopened authoritative/derived
old-or-new state verification. A missed injection, no restart or log-only hook
does not count. Retain86400s total,120s per point,512MiB driver and8GiB output.

## 4. Private Signet observation

Use actual continuous elapsed time of at least86,400 seconds in the named
private Signet substrate context. Freeze start/end, cohort, coverage, missing-data,
outage and restart rules before collection. A reset or unexplained gap restarts
the qualifying interval. Replayed history, synthetic/accelerated time, backdating
or simply waiting without complete live evidence is not endurance. Preserve all
other exit conditions, actual node/context checks, fee/reorg/crash observations,
reporting and admission-risk ownership. P5-005/P3-045 prepare the rules; P5-002
owns the actual observation and P5-004 owns closure. Adoption is not S13/S14 PASS.

## 5. Historical and operational boundaries

Completed100,000 forward comparisons,200,000 calls,512 KAT and S06 evidence stay
unchanged. The smaller future denominator does not negate their results and does
not mean equal statistical assurance: this is an explicit reduction in prospective
sample size and endurance horizon. No original failure or incomplete preparation
is removed or promoted. Current consumers must bind this exact policy identity;
historical consumers continue validating their original exact requirements.

Class P's separate R3-A2 Part VII section5 requirements of180 days and26,208
qualifying heights remain unchanged. Mainnet's minimum43,200-second human
deliberation, Profile approval, separate signing/broadcast ceremony, launch H0,
runtime execution gates and source authentication remain unchanged. No product,
reference model, key, node configuration or consensus behavior is amended.

## 6. Adoption and implementation boundary

P4-040 records the actual Founder instruction, exact source/policy/requirements
hashes, compatibility checks and finite consumer changes at0128c2214690ad894c581269b252a442ad246ab2.
The existing P4-039 owner paused at that atomic checkpoint. Local policy is
prepared and usable for implementation consistency checks; counted execution is
not authorized by this registry. Shared activation requires separately verified
integration and applicable existing authorization/CI. P4-038/P4-039 remain
incomplete and P4-005/P4-006/P5 remain subject to their actual readiness and
task-start gates. Rollback preserves all original artifacts and uses a separate
successor after shared adoption rather than rewriting published history.
