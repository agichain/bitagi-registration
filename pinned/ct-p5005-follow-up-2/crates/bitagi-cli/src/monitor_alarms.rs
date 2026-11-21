//! CT-P5-004-2c-1 (B3-04): the pure decision functions of `bitagi monitor
//! tick` (`monitor_tick`). Nothing here reads a node, a store, a file or a
//! clock: each function maps its inputs to a state, so every bound is
//! tested at the bound and at one either side (HC-01, R2:489) on fixture
//! inputs. An alarm holds nothing: no function here gates a step.
//!
//! - The tip age (555-a): [`tip_age`], the launch host's rule
//!   (`bitagi-launch-host/src/freshness.rs`, which this crate does not
//!   depend on) written again with the same constants and the same order
//!   of states; a cell pins the constants to that file's text.
//! - S14 (045b:1854): [`s14_heights`] names the heights both nodes are
//!   compared at, [`s14`] the lag and the heights whose hashes differ.
//! - The Heart bounds (FBO §7.4, :197-208): the W/L window ([`window`]),
//!   AL-1 to AL-6 and READY over a [`HeartPosition`]; AL-7 over
//!   [`BeatCaps`]; AL-8 over a [`FeeCandidate`] (FBO §7.10, :295-297).
//!   Window offsets come from `bitagi_launch::BEAT_WINDOWS` only; the D
//!   bounds are the FBO's draft values (UNMEASURED assumptions).
//! - AL-9 and AL-10 (FBO §7.11, :323-326): [`comparison`], the core's
//!   `ComparisonAlarms::of` over a frontier, or none when no frontier is
//!   known ("not measured", never "no alarm").

use bitagi_launch::{
    BEAT_WINDOWS, BeatChainGap, BeatWindow, ComparisonAlarms, beat_cutover_height, beat_window,
};

/// 555-a: an agreed tip this old or older is `Aging`, a notice only (3 h).
pub(crate) const AGING_SECS: u64 = 10_800;
/// 555-a: an agreed tip this old or older is `Stale` (6 h).
pub(crate) const STALE_SECS: u64 = 21_600;
/// 555-a: an MTP more than this past the host clock is `ClockBehind`.
pub(crate) const CLOCK_AHEAD_SECS: u64 = 300;

/// FBO §7.3: `B_total`, the draft continuity budget in blocks.
pub(crate) const B_TOTAL_BLOCKS: i64 = 784;
/// FBO §7.4: M, the draft operating margin in blocks.
pub(crate) const M_BLOCKS: i64 = 144;
/// FBO §7.4: READY needs D at or above `B_total + M` (draft 928); AL-2 is
/// D below it.
pub(crate) const READY_BOUND_BLOCKS: i64 = B_TOTAL_BLOCKS + M_BLOCKS;
/// FBO §7.4 AL-4: D at or below this (W3 / L3).
pub(crate) const AL4_LATE_D: i64 = 504;
/// FBO §7.4 AL-5: D below this (one 4 h session, 40 blocks, plus the
/// 6-block target).
pub(crate) const AL5_BRINK_D: i64 = 46;
/// FBO §7.4 AL-7: the BEAT replacements left at the TDS 8.10 floor.
#[cfg_attr(
    not(test),
    expect(
        dead_code,
        reason = "no source in this build: cells only (A Q2c-10, Q2c-11)"
    )
)]
pub(crate) const AL7_REPLACEMENT_FLOOR: u64 = 20;

/// The tip age states of 555-a, with its codes.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum TipState {
    Fresh,
    Aging,
    Stale,
    TimesDisagree,
    TimesUnread,
    ClockBehind,
    ClockUnreadable,
}

impl TipState {
    pub(crate) const fn code(self) -> &'static str {
        match self {
            Self::Fresh => "TIP_FRESH",
            Self::Aging => "TIP_AGING",
            Self::Stale => "TIP_STALE",
            Self::TimesDisagree => "TIP_TIMES_DISAGREE",
            Self::TimesUnread => "TIP_TIMES_UNREAD",
            Self::ClockBehind => "TIP_CLOCK_BEHIND",
            Self::ClockUnreadable => "TIP_CLOCK_UNREADABLE",
        }
    }

    /// AL-0 (b) (B's default, A 6894736990 Q2c-5): every state but `Fresh`
    /// and `Aging`. `Aging` is a notice only.
    pub(crate) const fn raises_al0b(self) -> bool {
        !matches!(self, Self::Fresh | Self::Aging)
    }
}

/// One tip age judgement: the state and, when both MTPs and the clock were
/// read, the age in seconds.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) struct TipAge {
    pub(crate) state: TipState,
    pub(crate) age_s: Option<u64>,
}

/// 555-a's rule, in its order: either MTP unread, the MTPs differ, the
/// clock unreadable, the MTP more than [`CLOCK_AHEAD_SECS`] past the clock,
/// then the age (clock − MTP, 0 when the MTP is ahead by at most
/// [`CLOCK_AHEAD_SECS`]) against [`STALE_SECS`] and [`AGING_SECS`].
pub(crate) const fn tip_age(mtp: [Option<u64>; 2], clock: Option<u64>) -> TipAge {
    const fn state(state: TipState) -> TipAge {
        TipAge { state, age_s: None }
    }
    let [Some(mtp), Some(other)] = mtp else {
        return state(TipState::TimesUnread);
    };
    if mtp != other {
        return state(TipState::TimesDisagree);
    }
    let Some(now) = clock else {
        return state(TipState::ClockUnreadable);
    };
    if let Some(limit) = now.checked_add(CLOCK_AHEAD_SECS)
        && mtp > limit
    {
        return state(TipState::ClockBehind);
    }
    let age = now.saturating_sub(mtp);
    let state = if age >= STALE_SECS {
        TipState::Stale
    } else if age >= AGING_SECS {
        TipState::Aging
    } else {
        TipState::Fresh
    };
    TipAge {
        state,
        age_s: Some(age),
    }
}

/// Why a height is compared.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum HeightRole {
    Genesis,
    H0Minus1,
    H0,
    LowerTip,
    Critical,
}

impl HeightRole {
    pub(crate) const fn label(self) -> &'static str {
        match self {
            Self::Genesis => "GENESIS",
            Self::H0Minus1 => "H0_MINUS_1",
            Self::H0 => "H0",
            Self::LowerTip => "LOWER_TIP",
            Self::Critical => "CRITICAL",
        }
    }
}

/// S14 (A 6894736990 Q2c-6): the heights both nodes are compared at:
/// genesis, H0 − 1, H0, the lower of the two tips and the caller's critical
/// heights, each only when both nodes reached it (at or below
/// `lower_tip`). Ascending, one entry per height with all its roles.
pub(crate) fn s14_heights(
    h0: u64,
    lower_tip: u64,
    critical: &[u64],
) -> Vec<(u64, Vec<HeightRole>)> {
    let mut named = vec![
        (0, HeightRole::Genesis),
        (h0.saturating_sub(1), HeightRole::H0Minus1),
        (h0, HeightRole::H0),
        (lower_tip, HeightRole::LowerTip),
    ];
    named.extend(
        critical
            .iter()
            .map(|height| (*height, HeightRole::Critical)),
    );
    named.sort_by_key(|(height, _)| *height);
    let mut heights: Vec<(u64, Vec<HeightRole>)> = Vec::new();
    for (height, role) in named {
        if height > lower_tip {
            continue;
        }
        match heights.last_mut() {
            Some((last, roles)) if *last == height => {
                if !roles.contains(&role) {
                    roles.push(role);
                }
            }
            _ => heights.push((height, vec![role])),
        }
    }
    heights
}

/// The S14 reading of one observation.
#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) struct S14 {
    /// `NODES_LAG`: the tip height difference; 0 when the heights agree.
    pub(crate) lag: u64,
    /// `S14_HASH_MISMATCH`: the compared heights whose two hashes differ.
    pub(crate) mismatches: Vec<u64>,
}

/// S14 from the two tip heights and the hashes both nodes gave at each
/// compared height. A height difference alone is `NODES_LAG`, never a
/// mismatch: only a height both nodes reached can have one.
pub(crate) fn s14(tips: [u64; 2], compared: &[(u64, [u8; 32], [u8; 32])]) -> S14 {
    S14 {
        lag: tips[0].abs_diff(tips[1]),
        mismatches: compared
            .iter()
            .filter(|(_, a, b)| a != b)
            .map(|(height, _, _)| *height)
            .collect(),
    }
}

/// A CURRENT Heart at an agreed, synced tip, from its countdown.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) struct HeartPosition {
    pub(crate) birth_height: u64,
    /// `B` before the first BEAT, `A` after.
    pub(crate) anchor_height: u64,
    pub(crate) last_valid_beat_height: u64,
    pub(crate) last_timely_beat_height: u64,
    pub(crate) tip: u64,
}

impl HeartPosition {
    /// No BEAT accepted yet: the CURRENT Anchor is the birth.
    pub(crate) const fn first(&self) -> bool {
        self.anchor_height == self.birth_height
    }

    /// D = `last_timely_beat_height − as_of` (FBO §7.1), signed; none
    /// outside `i64`.
    pub(crate) fn d(&self) -> Option<i64> {
        let last = i64::try_from(self.last_timely_beat_height).ok()?;
        let tip = i64::try_from(self.tip).ok()?;
        last.checked_sub(tip)
    }
}

/// The table of `BEAT_WINDOWS` for the first BEAT or a later one.
const fn table(first: bool) -> [(BeatWindow, u64); 4] {
    if first {
        BEAT_WINDOWS[0]
    } else {
        BEAT_WINDOWS[1]
    }
}

/// The W/L window class (FBO §3) of the position: `bitagi_launch`'s
/// `beat_window`, first when the anchor is the birth.
pub(crate) const fn window(position: &HeartPosition) -> Option<BeatWindow> {
    beat_window(
        position.first(),
        position.anchor_height,
        position.last_valid_beat_height,
        position.tip,
    )
}

/// The window's label.
pub(crate) const fn window_label(window: BeatWindow) -> &'static str {
    match window {
        BeatWindow::W0Wait => "W0_WAIT",
        BeatWindow::W1Normal => "W1_NORMAL",
        BeatWindow::W2Escalation => "W2_ESCALATION",
        BeatWindow::W3Late => "W3_LATE",
        BeatWindow::L0Wait => "L0_WAIT",
        BeatWindow::L1Normal => "L1_NORMAL",
        BeatWindow::L2Escalation => "L2_ESCALATION",
        BeatWindow::L3Late => "L3_LATE",
        BeatWindow::Timeout => "TIMEOUT",
    }
}

/// AL-1 BEAT due: tip at or above the start of W1 (`B + 1`) or L1
/// (`A + 1,008`), the second row of the table. No accepted BEAT for the
/// period is implied: an accepted BEAT moves the CURRENT Anchor.
pub(crate) const fn al1_beat_due(position: &HeartPosition) -> bool {
    match position
        .anchor_height
        .checked_add(table(position.first())[1].1)
    {
        Some(start) => position.tip >= start,
        None => false,
    }
}

/// AL-2 READY lost: D below `B_total + M`.
pub(crate) const fn al2_ready_lost(d: i64) -> bool {
    d < READY_BOUND_BLOCKS
}

/// AL-3 W2 / L2: tip at or above E, `beat_cutover_height` (`B + 144` /
/// `A + 1,152`).
pub(crate) const fn al3_escalation(position: &HeartPosition) -> bool {
    match beat_cutover_height(position.first(), position.anchor_height) {
        Some(e) => position.tip >= e,
        None => false,
    }
}

/// AL-4 W3 / L3: D at or below 504.
pub(crate) const fn al4_late(d: i64) -> bool {
    d <= AL4_LATE_D
}

/// AL-5 brink: D below 46.
pub(crate) const fn al5_brink(d: i64) -> bool {
    d < AL5_BRINK_D
}

/// AL-6 no timely block: D at or below 0.
pub(crate) const fn al6_no_timely_block(d: i64) -> bool {
    d <= 0
}

/// READY (R2:519-520; FBO §7.4): CURRENT verified on both nodes at an
/// agreed tip that raises no AL-0, and D > 0 and D ≥ `B_total + M`.
pub(crate) const fn ready(current_at_agreed_tip: bool, d: i64) -> bool {
    current_at_agreed_tip && d > 0 && d >= READY_BOUND_BLOCKS
}

/// What AL-7 reads of the campaign's BEAT caps (a ledger read; not in
/// this unit, OFF-10).
#[cfg_attr(
    not(test),
    expect(
        dead_code,
        reason = "no source in this build: cells only (A Q2c-10, Q2c-11)"
    )
)]
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) struct BeatCaps {
    pub(crate) released_replacements: u64,
    pub(crate) max_beat_replacements: u64,
    pub(crate) beat_count_remaining: u64,
    /// The BEAT slots still needed to stay CURRENT at 1,050,000
    /// (045b:760-762), as the caller counts them.
    pub(crate) slots_needed: u64,
}

/// AL-7 cap headroom: [`AL7_REPLACEMENT_FLOOR`] or fewer BEAT replacements
/// left (80 or more of 100 released), or fewer BEATs left than slots
/// needed.
#[cfg_attr(
    not(test),
    expect(
        dead_code,
        reason = "no source in this build: cells only (A Q2c-10, Q2c-11)"
    )
)]
pub(crate) const fn al7_cap_headroom(caps: &BeatCaps) -> bool {
    caps.released_replacements
        >= caps
            .max_beat_replacements
            .saturating_sub(AL7_REPLACEMENT_FLOOR)
        || caps.beat_count_remaining < caps.slots_needed
}

/// The next BEAT candidate whose fee AL-8 compares with the cap (FBO
/// :295). Rates in sat/kvB, sizes in vB, fees in sat.
#[cfg_attr(
    not(test),
    expect(
        dead_code,
        reason = "no source in this build: cells only (A Q2c-10, Q2c-11)"
    )
)]
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum FeeCandidate {
    /// The first build: ⌈`b` × `v` / 1,000⌉.
    First { rate: u64, vsize: u64 },
    /// A replacement: the larger of ⌈max(`b`, ⌈`p` × 3 / 2⌉) × `v` / 1,000⌉
    /// and the replaced fee plus ⌈`r_inc` × `v` / 1,000⌉ (BIP125).
    Replacement {
        rate: u64,
        replaced_rate: u64,
        replaced_fee: u64,
        incremental_rate: u64,
        vsize: u64,
    },
    /// The full fee of the candidate the BEAT unit built.
    Built { fee: u64 },
}

/// ⌈`rate` × `vsize` / 1,000⌉; none on overflow.
#[cfg_attr(
    not(test),
    expect(
        dead_code,
        reason = "no source in this build: cells only (A Q2c-10, Q2c-11)"
    )
)]
const fn fee_at(rate: u64, vsize: u64) -> Option<u64> {
    match rate.checked_mul(vsize) {
        Some(product) => match product.checked_add(999) {
            Some(sum) => Some(sum / 1_000),
            None => None,
        },
        None => None,
    }
}

/// The candidate's fee; none on overflow.
#[cfg_attr(
    not(test),
    expect(
        dead_code,
        reason = "no source in this build: cells only (A Q2c-10, Q2c-11)"
    )
)]
pub(crate) fn al8_fee(candidate: FeeCandidate) -> Option<u64> {
    match candidate {
        FeeCandidate::First { rate, vsize } => fee_at(rate, vsize),
        FeeCandidate::Replacement {
            rate,
            replaced_rate,
            replaced_fee,
            incremental_rate,
            vsize,
        } => {
            let bumped = replaced_rate.checked_mul(3)?.checked_add(1)? / 2;
            let rate_term = fee_at(rate.max(bumped), vsize)?;
            let floor = replaced_fee.checked_add(fee_at(incremental_rate, vsize)?)?;
            Some(rate_term.max(floor))
        }
        FeeCandidate::Built { fee } => Some(fee),
    }
}

/// AL-8 fee cap: the candidate's fee above `max_fee_per_candidate_sat`;
/// none when the fee overflows (not measured).
#[cfg_attr(
    not(test),
    expect(
        dead_code,
        reason = "no source in this build: cells only (A Q2c-10, Q2c-11)"
    )
)]
pub(crate) fn al8_fee_cap(candidate: FeeCandidate, cap: u64) -> Option<bool> {
    al8_fee(candidate).map(|fee| fee > cap)
}

/// A BEAT candidate of a born Heart, for AL-10's second clause.
#[cfg_attr(
    not(test),
    expect(
        dead_code,
        reason = "no source in this build: cells only (A Q2c-10, Q2c-11)"
    )
)]
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) struct BeatCandidate {
    pub(crate) first: bool,
    pub(crate) anchor_height: u64,
    pub(crate) included: bool,
}

/// AL-9 and AL-10 at `tip` from the comparison frontier's through height:
/// the core's `ComparisonAlarms::of` with the lag tip − through and, for a
/// BEAT candidate, E from `beat_cutover_height` and a chain through the tip
/// when the frontier is the tip. None (not measured, never "no alarm")
/// without a frontier or with a frontier above the tip.
#[cfg_attr(
    not(test),
    expect(
        dead_code,
        reason = "no source in this build: cells only (A Q2c-10, Q2c-11)"
    )
)]
pub(crate) fn comparison(
    tip: u64,
    through_height: Option<u64>,
    beat: Option<BeatCandidate>,
) -> Option<ComparisonAlarms> {
    let through = through_height?;
    let lag = tip.checked_sub(through)?;
    let gap = beat.map(|beat| BeatChainGap {
        cutover_height: beat_cutover_height(beat.first, beat.anchor_height),
        included: beat.included,
        chain_through_tip: through == tip,
    });
    Some(ComparisonAlarms::of(lag, tip, gap))
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The constant `name`'s value in the launch host's 555-a source, read
    /// at run time.
    fn launch_host_constant(source: &str, name: &str) -> u64 {
        let prefix = format!("pub const {name}: u64 = ");
        let line = source
            .lines()
            .find_map(|line| line.trim().strip_prefix(prefix.as_str()))
            .unwrap_or_else(|| panic!("{name} is not in freshness.rs"));
        line.trim_end_matches(';').replace('_', "").parse().unwrap()
    }

    /// Q2c-5: the tip age constants equal `freshness.rs:36-41`.
    #[test]
    fn tip_age_constants_equal_the_launch_host_rule() {
        let path = concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../bitagi-launch-host/src/freshness.rs"
        );
        let source = std::fs::read_to_string(path).unwrap();
        assert_eq!(launch_host_constant(&source, "AGING_SECS"), AGING_SECS);
        assert_eq!(launch_host_constant(&source, "STALE_SECS"), STALE_SECS);
        assert_eq!(
            launch_host_constant(&source, "CLOCK_AHEAD_SECS"),
            CLOCK_AHEAD_SECS
        );
        assert_eq!(
            (AGING_SECS, STALE_SECS, CLOCK_AHEAD_SECS),
            (10_800, 21_600, 300)
        );
    }

    const NOW: u64 = 1_794_748_080;

    fn aged(age: u64) -> TipAge {
        tip_age([Some(NOW - age), Some(NOW - age)], Some(NOW))
    }

    #[test]
    fn tip_age_10800_is_aging_and_10799_fresh() {
        assert_eq!(aged(10_799).state, TipState::Fresh);
        assert_eq!(aged(10_800).state, TipState::Aging);
        assert_eq!(aged(10_801).state, TipState::Aging);
        assert_eq!(aged(10_800).age_s, Some(10_800));
    }

    #[test]
    fn tip_age_21600_is_stale_and_21599_aging() {
        assert_eq!(aged(21_599).state, TipState::Aging);
        assert_eq!(aged(21_600).state, TipState::Stale);
        assert_eq!(aged(21_601).state, TipState::Stale);
    }

    #[test]
    fn mtp_300_ahead_is_fresh_301_is_clock_behind() {
        let ahead = |by: u64| tip_age([Some(NOW + by), Some(NOW + by)], Some(NOW));
        assert_eq!(ahead(299).state, TipState::Fresh);
        assert_eq!(
            ahead(300),
            TipAge {
                state: TipState::Fresh,
                age_s: Some(0)
            }
        );
        assert_eq!(ahead(301).state, TipState::ClockBehind);
        assert_eq!(ahead(301).age_s, None);
        // A clock within 300 s of u64::MAX has no MTP past it.
        assert_eq!(
            tip_age([Some(u64::MAX), Some(u64::MAX)], Some(u64::MAX - 1)).state,
            TipState::Fresh
        );
    }

    #[test]
    fn node_mtps_differ_is_times_disagree_and_one_unread_is_times_unread() {
        assert_eq!(
            tip_age([Some(NOW), Some(NOW - 1)], Some(NOW)).state,
            TipState::TimesDisagree
        );
        assert_eq!(
            tip_age([Some(NOW), None], Some(NOW)).state,
            TipState::TimesUnread
        );
        assert_eq!(
            tip_age([None, Some(NOW)], Some(NOW)).state,
            TipState::TimesUnread
        );
        // 555-a's order: unread before disagree before the clock.
        assert_eq!(tip_age([None, None], None).state, TipState::TimesUnread);
        assert_eq!(
            tip_age([Some(1), Some(2)], None).state,
            TipState::TimesDisagree
        );
        assert_eq!(
            tip_age([Some(1), Some(1)], None).state,
            TipState::ClockUnreadable
        );
    }

    #[test]
    fn al0b_is_every_state_but_fresh_and_aging() {
        let raised = [
            TipState::Fresh,
            TipState::Aging,
            TipState::Stale,
            TipState::TimesDisagree,
            TipState::TimesUnread,
            TipState::ClockBehind,
            TipState::ClockUnreadable,
        ]
        .map(TipState::raises_al0b);
        assert_eq!(raised, [false, false, true, true, true, true, true]);
    }

    #[test]
    fn s14_heights_are_genesis_h0_minus_1_h0_the_lower_tip_and_critical_ones_reached() {
        let heights = s14_heights(1_000, 1_005, &[1_002, 1_006]);
        let listed: Vec<u64> = heights.iter().map(|(height, _)| *height).collect();
        assert_eq!(listed, [0, 999, 1_000, 1_002, 1_005]);
        assert_eq!(heights[1].1, [HeightRole::H0Minus1]);
        assert_eq!(heights[4].1, [HeightRole::LowerTip]);
        // Below H0 only genesis and the tip are reached; a tip at H0 − 1
        // carries both roles.
        let early = s14_heights(1_000, 999, &[999]);
        assert_eq!(
            early,
            [
                (0, vec![HeightRole::Genesis]),
                (
                    999,
                    vec![
                        HeightRole::H0Minus1,
                        HeightRole::LowerTip,
                        HeightRole::Critical
                    ]
                ),
            ]
        );
    }

    #[test]
    fn s14_mismatch_at_h0_minus_1_with_equal_tips() {
        let same = [7; 32];
        let reading = s14(
            [1_005, 1_005],
            &[
                (0, same, same),
                (999, [1; 32], [2; 32]),
                (1_005, same, same),
            ],
        );
        assert_eq!(reading.lag, 0);
        assert_eq!(reading.mismatches, [999]);
    }

    #[test]
    fn one_block_behind_is_lag_not_s14() {
        let same = [7; 32];
        let reading = s14([1_005, 1_004], &[(0, same, same), (1_004, same, same)]);
        assert_eq!(
            reading,
            S14 {
                lag: 1,
                mismatches: vec![]
            }
        );
        assert_eq!(s14([1_004, 1_005], &[]).lag, 1);
    }

    const BIRTH: u64 = 1_000_000;

    /// A position of a Heart born at [`BIRTH`] with its CURRENT Anchor at
    /// `anchor`, at `tip`, with D's deadline at anchor + 2,016.
    fn at(anchor: u64, tip: u64) -> HeartPosition {
        HeartPosition {
            birth_height: BIRTH,
            anchor_height: anchor,
            last_valid_beat_height: anchor + 2_016,
            last_timely_beat_height: anchor + 2_016,
            tip,
        }
    }

    const A: u64 = BIRTH + 1_100;

    #[test]
    fn first_beat_window_is_w_and_a_later_one_l() {
        assert!(at(BIRTH, BIRTH).first());
        assert!(!at(A, A).first());
        let label = |anchor, tip| window(&at(anchor, tip)).map(window_label);
        assert_eq!(label(BIRTH, BIRTH), Some("W0_WAIT"));
        assert_eq!(label(BIRTH, BIRTH + 1), Some("W1_NORMAL"));
        assert_eq!(label(BIRTH, BIRTH + 144), Some("W2_ESCALATION"));
        assert_eq!(label(BIRTH, BIRTH + 1_512), Some("W3_LATE"));
        assert_eq!(label(BIRTH, BIRTH + 2_017), Some("TIMEOUT"));
        assert_eq!(label(A, A + 1_007), Some("L0_WAIT"));
        assert_eq!(label(A, A + 1_008), Some("L1_NORMAL"));
        assert_eq!(label(A, A + 1_152), Some("L2_ESCALATION"));
        assert_eq!(label(A, A + 1_512), Some("L3_LATE"));
        assert_eq!(label(A, A + 2_016), Some("L3_LATE"));
        assert_eq!(label(A, A - 1), None);
    }

    #[test]
    fn al1_is_due_at_b_plus_1_and_a_plus_1008() {
        assert!(!al1_beat_due(&at(BIRTH, BIRTH)));
        assert!(al1_beat_due(&at(BIRTH, BIRTH + 1)));
        assert!(!al1_beat_due(&at(A, A + 1_007)));
        assert!(al1_beat_due(&at(A, A + 1_008)));
        assert!(al1_beat_due(&at(A, A + 1_009)));
    }

    #[test]
    fn al2_ready_lost_at_d_927_not_at_928_or_929() {
        assert_eq!(READY_BOUND_BLOCKS, 928);
        assert!(al2_ready_lost(927));
        assert!(!al2_ready_lost(928));
        assert!(!al2_ready_lost(929));
    }

    #[test]
    fn al3_at_b_plus_144_and_a_plus_1152() {
        assert!(!al3_escalation(&at(BIRTH, BIRTH + 143)));
        assert!(al3_escalation(&at(BIRTH, BIRTH + 144)));
        assert!(al3_escalation(&at(BIRTH, BIRTH + 145)));
        assert!(!al3_escalation(&at(A, A + 1_151)));
        assert!(al3_escalation(&at(A, A + 1_152)));
        assert!(al3_escalation(&at(A, A + 1_153)));
    }

    #[test]
    fn al4_late_at_d_504_and_505_is_not() {
        assert!(al4_late(503));
        assert!(al4_late(504));
        assert!(!al4_late(505));
    }

    #[test]
    fn al5_brink_at_d_45_not_at_46_or_47() {
        assert!(al5_brink(45));
        assert!(!al5_brink(46));
        assert!(!al5_brink(47));
    }

    #[test]
    fn al6_at_d_minus_1_and_0_not_at_1() {
        assert!(al6_no_timely_block(-1));
        assert!(al6_no_timely_block(0));
        assert!(!al6_no_timely_block(1));
    }

    #[test]
    fn d_is_last_timely_minus_tip_and_ready_needs_928_at_an_agreed_tip() {
        assert_eq!(at(A, A + 1_088).d(), Some(928));
        assert_eq!(at(A, A + 1_089).d(), Some(927));
        assert_eq!(at(A, A + 2_017).d(), Some(-1));
        assert!(ready(true, 928));
        assert!(ready(true, 929));
        assert!(!ready(true, 927));
        assert!(!ready(false, 2_015));
        assert_eq!(
            HeartPosition {
                tip: u64::MAX,
                ..at(A, A)
            }
            .d(),
            None
        );
    }

    fn caps(released: u64, remaining: u64, needed: u64) -> BeatCaps {
        BeatCaps {
            released_replacements: released,
            max_beat_replacements: 100,
            beat_count_remaining: remaining,
            slots_needed: needed,
        }
    }

    #[test]
    fn eighty_released_alarms_and_seventy_nine_does_not() {
        assert!(!al7_cap_headroom(&caps(79, 40, 30)));
        assert!(al7_cap_headroom(&caps(80, 40, 30)));
        // The remaining beat_count against the slots needed.
        assert!(!al7_cap_headroom(&caps(0, 30, 30)));
        assert!(al7_cap_headroom(&caps(0, 29, 30)));
    }

    #[test]
    fn fee_equal_to_cap_no_alarm_and_one_sat_above_alarms() {
        // FBO :295: at 263 vB the rate term alone crosses above F_B =
        // 114,068 sat/kvB.
        let first = |rate| FeeCandidate::First { rate, vsize: 263 };
        assert_eq!(al8_fee(first(114_068)), Some(30_000));
        assert_eq!(al8_fee_cap(first(114_068), 30_000), Some(false));
        assert_eq!(al8_fee(first(114_069)), Some(30_001));
        assert_eq!(al8_fee_cap(first(114_069), 30_000), Some(true));
        assert_eq!(
            al8_fee_cap(FeeCandidate::Built { fee: 30_000 }, 30_000),
            Some(false)
        );
        assert_eq!(
            al8_fee_cap(FeeCandidate::Built { fee: 30_001 }, 30_000),
            Some(true)
        );
    }

    #[test]
    fn replacement_floor_29982_no_alarm_and_30245_alarms() {
        // FBO :297: 263 vB, b = p = 2,000 sat/kvB, a replaced fee of 526
        // sat: a rate term of 789 sat, and the BIP125 floor crosses first.
        let replacement = |incremental_rate| FeeCandidate::Replacement {
            rate: 2_000,
            replaced_rate: 2_000,
            replaced_fee: 526,
            incremental_rate,
            vsize: 263,
        };
        assert_eq!(fee_at(3_000, 263), Some(789));
        assert_eq!(al8_fee(replacement(112_000)), Some(29_982));
        assert_eq!(al8_fee_cap(replacement(112_000), 30_000), Some(false));
        assert_eq!(al8_fee(replacement(113_000)), Some(30_245));
        assert_eq!(al8_fee_cap(replacement(113_000), 30_000), Some(true));
        // The rate term wins when it is larger: ⌈1,001 × 3 / 2⌉ = 1,502.
        let rate_term = FeeCandidate::Replacement {
            rate: 1_000,
            replaced_rate: 1_001,
            replaced_fee: 0,
            incremental_rate: 1_000,
            vsize: 1_000,
        };
        assert_eq!(al8_fee(rate_term), Some(1_502));
    }

    #[test]
    fn a_fee_that_overflows_is_not_measured() {
        // 2^63 × 2 overflows u64 (it would wrap to 0).
        let first = FeeCandidate::First {
            rate: 1 << 63,
            vsize: 2,
        };
        assert_eq!(al8_fee_cap(first, 30_000), None);
    }

    const TIP: u64 = 2_000;

    fn lagged(lag: u64) -> ComparisonAlarms {
        comparison(TIP, Some(TIP - lag), None).unwrap()
    }

    #[test]
    fn al9_at_lag_6_and_7_not_at_0_or_5() {
        assert!(!lagged(0).al9);
        assert!(!lagged(5).al9);
        assert!(lagged(6).al9);
        assert!(lagged(7).al9);
    }

    #[test]
    fn al10_at_lag_36_and_37_not_at_35() {
        assert!(!lagged(35).al10());
        assert!(lagged(36).al10());
        assert!(lagged(37).al10());
        assert!(lagged(35).al9);
    }

    /// FBO :326: a candidate with no MATCH chain through the tip, lag 1, at
    /// E − 1 (no AL-10), E and E + 1 (AL-10), for both kinds of E.
    #[test]
    fn al10_from_e_at_both_e_with_lag_1() {
        for (first, anchor, e) in [(true, BIRTH, BIRTH + 144), (false, A, A + 1_152)] {
            let beat = BeatCandidate {
                first,
                anchor_height: anchor,
                included: false,
            };
            let at = |tip: u64| comparison(tip, Some(tip - 1), Some(beat)).unwrap();
            assert!(!at(e - 1).al10(), "E - 1, first {first}");
            assert!(at(e).al10(), "E, first {first}");
            assert!(at(e + 1).al10(), "E + 1, first {first}");
            assert!(!at(e).al10_lag && !at(e).al9);
            // An included candidate raises nothing at E.
            let included = BeatCandidate {
                included: true,
                ..beat
            };
            assert!(!comparison(e, Some(e - 1), Some(included)).unwrap().al10());
        }
    }

    #[test]
    fn al10_at_e_with_a_chain_one_below_the_tip_and_none_through_it() {
        let beat = BeatCandidate {
            first: false,
            anchor_height: A,
            included: false,
        };
        let e = A + 1_152;
        assert!(comparison(e, Some(e - 1), Some(beat)).unwrap().al10());
        assert!(!comparison(e, Some(e), Some(beat)).unwrap().al10());
    }

    #[test]
    fn missing_frontier_is_not_measured() {
        assert_eq!(comparison(TIP, None, None), None);
        assert_eq!(comparison(TIP, Some(TIP + 1), None), None);
        assert!(comparison(TIP, Some(TIP), None).is_some());
    }

    /// M5 of the launch core (no window literal): this module takes every
    /// window offset from `BEAT_WINDOWS` and `beat_cutover_height`; its
    /// code outside the tests names none of them. Read at run time.
    #[test]
    fn no_window_literal_outside_the_tests() {
        let source = std::fs::read_to_string(concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/src/monitor_alarms.rs"
        ))
        .unwrap();
        let code = source.split("#[cfg(test)]").next().unwrap();
        for literal in [
            "1_008", "1008", "1_152", "1152", "1_512", "1512", "2_016", "2016",
        ] {
            assert!(!code.contains(literal), "window literal {literal}");
        }
        assert!(code.contains("BEAT_WINDOWS[0]") && code.contains("beat_cutover_height("));
    }
}
