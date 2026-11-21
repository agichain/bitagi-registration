# MONITOR_LOG_V1: the monitor loop's JSONL log (CT-P5-004-2c-2)

Status: CT-P5-004-2c-2 (B3-04), FD-CT-67. A #258 issuecomment-6894736990 accepted B's defaults for Q2c-7
(JSONL log, this file pinned by follow-up registration 2), Q2c-8 (elapsed times on `utc`, `mono_ns` for order
and gaps only), Q2c-9 (log and stderr, one acknowledgement input stamped at receipt) and Q2c-13 (exit codes).
Class T development tooling, release authorization NONE. The writer is `tools/claude_track_monitor.py run`;
its tests are `tests/claude_track/test_claude_track_monitor.py`; one of them checks that every line kind
(and a STOP line's episodes and refused marks) has exactly the fields section 4 lists, in that order, and one
that section 5's judgement table and class table are the ones the loop uses. The
one-shot tick it calls is CT-P5-004-2c-1's `bitagi monitor tick` (`crates/bitagi-cli/src/monitor_tick.rs`,
request `BITAGI_CT_MONITOR_TICK_REQUEST_V1`, result `BITAGI_CT_MONITOR_TICK_RESULT_V1`).

The loop observes and records. It calls no command but the tick, opens no network connection and holds,
releases or signs nothing: alarms only (FBO :123; P5:650).

## 1. The file

- One run, one file. The path is the `--log` argument; it must be absolute. The file must not exist: it is
  created with `O_CREAT | O_EXCL` (mode 0600), so an existing file or a symbolic link at the path is refused
  with exit 2 and left unchanged. The file is never reopened or rewritten, and no whole line in it is ever
  changed.
- JSON Lines: one compact JSON object per line, ASCII (`ensure_ascii`), each line ended by LF. No floating-point
  number anywhere (AGENTS.md section 4); every number is an integer.
- Append only. Each line is written whole and `fsync`ed before the next action. If a write fails, the only
  change ever made to written bytes is made: the half-written tail past the last whole line is cut off
  (`ftruncate`), then the loop makes one attempt at a STOP line (`LOG_WRITE_FAILED`, exit 4) and ends with exit 4
  whether that attempt worked or not. If that attempt fails too, its half-written part is cut off as well, so the
  file still ends with whole lines, and one stderr line says the log took no STOP line.
- Standard streams: any of fds 0, 1 and 2 that is closed at start is opened on `/dev/null` first, so the log
  (moved to an fd of 3 or more) is never fd 0, 1 or 2. With stderr closed (`2>&-`) stderr lines and refusal text
  go to `/dev/null`: they are written there, so they are not counted as dropped. A stderr line is never written
  while fd 2 is the log file itself (it is dropped and counted, section 4 STOP). If the log cannot be moved off
  its fd, the empty file just created is removed and the start is refused (exit 2, `LOG_CREATE_FAILED`).
- A reader treats a last line without its LF as incomplete (a crash, a full disk, a SIGKILL) and ignores it.
- `seq` counts lines from 0 (START) and grows by 1 a line. The first line is START. STOP, when present, is the
  last line; a log without STOP is from a run that was killed (SIGKILL, power loss) or is still running (`check`
  exits 3 for it, section 9).
- The paths in START are the arguments as given (absolute for `--bitagi` and `--log`). A path under a home
  folder carries its user name into the log; a driver that does not want that gives paths outside any home
  folder.

## 2. Clocks

- `mono_ns`: the loop's `CLOCK_MONOTONIC` reading (`time.clock_gettime_ns`) taken for the line. It never
  decreases from one line to the next. It orders lines and finds gaps; it never measures an elapsed time.
- `utc`: the host's UTC wall clock taken for the line, RFC 3339 `YYYY-MM-DDTHH:MM:SSZ`, whole seconds. Every
  elapsed time in this log (`fault_to_emission_s`, `emission_to_acknowledgment_s`) is a difference of two such
  UTC readings on this host, in whole seconds (FBO :282: "on one clock (the host's UTC wall clock)"). A block
  header's time is never used.
- The tick itself reads the host clock once (`tick.clock.utc`, the observation time; it can be null) and echoes
  the loop's `mono_ns` (`tick.clock.mono_ns`); a result whose echo differs from the request is not used
  (`TICK_OUTPUT_INVALID`).
- Poll: fixed rate on `mono_ns`, `--poll-s` seconds (default 120, A Q2c-5) from one tick's start to the next.
  A tick that ends late is followed at once by the tick that was due; after a wait more than a whole poll long on
  `mono_ns` (a stopped or stalled process) the schedule restarts from the current time, with no catch-up ticks.
  A suspend of the host does not do this: `CLOCK_MONOTONIC` stands still while the host is suspended, so the
  wait goes on after it.
- Suspend: on a TICK line, `suspended_ns` is how much more the host's `CLOCK_BOOTTIME` advanced than its
  `CLOCK_MONOTONIC` since the previous TICK line (the time the host was suspended; never negative), null on the
  first TICK line or where the host has no `CLOCK_BOOTTIME`; `suspend` is true when it is more than 2 s
  (exactly 2 s is not). This is P5-002's `SUSPEND` value (P5002_ENDURANCE_V1, `SUSPEND`: more than 2 s), so a
  P5-002 run and this log name the same suspends (A, #870 6906571571). A suspend also writes a stderr line.
  Where `suspended_ns` is null it counts as 0 (no suspend, and the host time below is `mono_ns` alone). `CLOCK_MONOTONIC` standing still while
  the host is suspended is Linux behaviour; this section is written for Linux hosts.
- Gap: on a TICK line, `since_prev_tick_mono_ns` is this line's `mono_ns` minus the previous TICK line's
  `mono_ns`; the host time between the two TICK lines is that plus `suspended_ns`; when it is more than 2 ×
  `poll_s` × 10^9, `gap` is true. So a suspend that long is a gap as well as a `suspend`.
- Clock step: `utc_drift_s` is this TICK line's `utc` minus the previous TICK line's, in seconds, minus that host
  time in seconds (rounded to the nearest second); `clock_step` is true when its absolute value is more than 5.
  A suspend is not a clock step. A step is shown, not corrected: elapsed times stay on `utc`, as A decided, and a
  reader that finds a step inside an alarm's interval knows that interval crossed it.

## 3. What one poll writes

While the tick runs, the inputs (section 6) are read every 0.5 s, and an ALARM_ACK can come then. After it: one
TICK line; then, when the tick has a checked result and the loop's own alarm `MONITOR_TICK_FAILING` is open,
its ALARM_CLEAR, right after the TICK line and before that tick's other edges; then, from that result, the edges
(section 5) in the tick's alarm order, for each alarm its clears first and then its starts; then one
CRITICAL_HEIGHT per critical height reached for the first time, in the order of the tick's
`critical_heights.reached`.
Inside one alarm, the clears follow the order in which their episodes started, and the starts follow the order
in which each episode key (section 5) first appears in that alarm's `sub_kinds` (for a sub-kind keyed by `kind`
alone, the first entry of that `kind`). A failed tick instead counts towards the loop's own alarm (section 5).
Between ticks the inputs are read every 0.5 s. STOP ends the log.

## 4. Lines

Types: `str`, `int`, `bool`, `obj` (a JSON object), `list`, `UTC` (a `str` as in section 2); `|null` means the
value can also be null.

### Every line

| Field | Type | Value |
|---|---|---|
| `schema` | str | `BITAGI_CT_MONITOR_LOG_V1` |
| `seq` | int | line number from 0 |
| `mono_ns` | int | section 2 |
| `utc` | UTC | section 2 |
| `kind` | str | `START`, `TICK`, `ALARM_START`, `ALARM_CLEAR`, `ALARM_ACK`, `CRITICAL_HEIGHT` or `STOP` |

The fields below follow these five, in the order listed.

### START

| Field | Type | Value |
|---|---|---|
| `format` | str | `docs/claude-track/formats/MONITOR_LOG_V1.md` |
| `tool_sha256` | str | SHA-256 (lower hex) of `tools/claude_track_monitor.py` as run |
| `bitagi_path` | str | the `--bitagi` argument, an absolute path (a bare name is refused, so the file hashed is the file run) |
| `bitagi_sha256` | str | SHA-256 of that file's bytes at start |
| `request_path` | str | the `--request` argument (the tick request template) |
| `request_sha256` | str | SHA-256 of the template's bytes |
| `log_path` | str | this file's path |
| `poll_s` | int | the poll interval in seconds |
| `tick_timeout_s` | int | a tick still running after this many seconds is killed (`TICK_TIMEOUT`) |
| `max_ticks` | int\|null | the `--max-ticks` argument, or null (run until a signal) |
| `critical_heights` | list | the template's `critical_heights` (int) |
| `ack_input` | str\|obj\|null | `"STDIN"`, `{"file": <path>}` or null |
| `mark_input` | obj\|null | `{"file": <path>}` or null |
| `tick_failing_after` | int | failed ticks in a row that start `MONITOR_TICK_FAILING` (3) |
| `clock` | obj | `{"mono_ns": "CLOCK_MONOTONIC, ORDERING_AND_GAPS_ONLY", "utc": "HOST_UTC_WALL_CLOCK", "suspended_ns": "CLOCK_BOOTTIME MINUS CLOCK_MONOTONIC, SUSPEND_ONLY"}` |
| `release_class` | str | `T` |
| `release_authorization` | str | `NONE` |

The template is not copied into the log; its hash is. Each tick's request is the template with two members
replaced: `mono_ns` (the loop's reading just before the call) and `critical_heights` (those not yet reached).

### TICK

| Field | Type | Value |
|---|---|---|
| `tick_index` | int | tick count from 0 |
| `tick_exit` | int\|null | the tick's exit code; null when no exit was had: `TICK_TIMEOUT`, `TICK_SPAWN_FAILED`, `TICK_KILLED_BY_SIGNAL`, `REQUEST_WRITE_FAILED` (the tick was not run), or `TICK_OUTPUT_TOO_LARGE` or `TICK_OUTPUT_LOST` found while it ran |
| `tick_error` | str\|null | null, or `TICK_REFUSED` (non-zero exit), `TICK_OUTPUT_INVALID` (exit 0 but not exactly one checked result line), `TICK_OUTPUT_TOO_LARGE` (stdout or stderr over 1 MiB: the process group is killed and nothing is parsed), `TICK_OUTPUT_LOST` (the tick's output files or the loop's temporary folder were removed: the process group is killed), `TICK_TIMEOUT`, `TICK_SPAWN_FAILED`, `TICK_KILLED_BY_SIGNAL`, `REQUEST_WRITE_FAILED` (the request could not be written into the temporary folder; the next tick makes a new folder and removes that one) |
| `tick_error_reason` | str\|null | for `TICK_OUTPUT_INVALID`, the check that failed: `ONE_LINE` (not exactly one LF-ended line), `NOT_JSON` (not one strict JSON value, or nested too deeply to read), `SCHEMA`, `MONO_NS_ECHO`, `CLOCK_UTC` (a `clock.utc` that is neither null nor a UTC text as in section 2), `ALARMS`, `ALARM` (an alarm without a valid `id`, a boolean or null `raised`, or `sub_kinds` as section 5 reads them), `CRITICAL_HEIGHTS` or `COUNTDOWN`; else null |
| `request_sha256` | str | SHA-256 of the request bytes this tick was given |
| `request_mono_ns` | int | the request's `mono_ns` |
| `critical_heights_requested` | list | the request's `critical_heights` |
| `tick_utc` | UTC\|null | the tick's `clock.utc` (its observation time), or null |
| `countdown_status` | str\|null | the tick's `countdown.status` (`MEASURED` or `HEART_NOT_CURRENT` from -2c-1), or null |
| `since_prev_tick_mono_ns` | int\|null | section 2; null on the first |
| `suspended_ns` | int\|null | section 2; null on the first or without a boot clock |
| `suspend` | bool | section 2 |
| `gap` | bool | section 2 |
| `utc_drift_s` | int\|null | section 2; null on the first |
| `clock_step` | bool | section 2 |
| `tick` | obj\|null | the tick's result object, parsed and written out again as part of this line (the same members and values in the tick's order; not the tick's bytes), or null when the tick failed |
| `refusal` | obj\|null | the tick's `BITAGI_CLASS_T_REFUSAL_V1` stderr line as an object when its stderr is exactly one such line, else null (other stderr text is never copied) |

A failed tick (any `tick_error`) changes no alarm of the tick, writes a stderr line and counts towards the loop's
alarm; the loop goes on, except after a tick exit 5 or 6, or a tick exit 2 before the first checked tick (section
7). A removed temporary folder is made again, by a new name, before the next tick.

### ALARM_START

| Field | Type | Value |
|---|---|---|
| `alarm_id` | str | the tick's alarm `id` (`AL-0a`, `AL-0b`, `AL-1` … `AL-10`), or the loop's `MONITOR_TICK_FAILING` |
| `sub_kind` | str\|null | the `kind` this episode is about, or null for an alarm raised without sub-kinds (section 5) |
| `episode_key` | obj | the key members of this episode and their values (section 5), for example `{"standing": "SYNCING", "reason_class": null}` or `{"reason": "HEART_NOT_CURRENT"}` (each value a str or null); `{}` for a sub-kind keyed by `kind` alone and for a null sub-kind |
| `name` | str\|null | the tick's alarm `name` (`MONITOR_TICK_FAILING` for the loop's) |
| `sub_kind_entries` | list | the tick's `sub_kinds` entries with this episode key at this tick (for example both `NODE_UNAVAILABLE` entries, node A and node B); empty for a null sub-kind |
| `tick_seq` | int | `seq` of the TICK line that showed it |
| `first_tick` | bool | true when that was the first tick with a checked result |
| `misconfiguration` | str\|null | `NODE_CONTEXT_MISMATCH_ON_FIRST_TICK` for AL-0a's `NODE_CONTEXT_MISMATCH` started on the first tick, else null |
| `clock` | str | `HOST_UTC_WALL_CLOCK` |
| `fault_start_utc` | UTC | section 5 |
| `fault_start_source` | str | `INJECTION_MARK`, `FIRST_TICK_HELD`, `PRESENT_AT_FIRST_TICK`, `PRESENT_WHEN_FIRST_JUDGED` or `FIRST_FAILED_TICK` (section 5) |
| `mark_refused` | str\|null | `MARK_AFTER_EMISSION` when the mark this start took was later than this emission (it is dropped), else null |
| `emission_utc` | UTC | this line's `utc` |
| `fault_to_emission_s` | int | `emission_utc − fault_start_utc`, whole seconds: the first `B_detect` field (FBO :282) |
| `b_detect_sample` | bool | false for `PRESENT_AT_FIRST_TICK` and `PRESENT_WHEN_FIRST_JUDGED` (the fault may have begun before the monitor was judging it) and for a start that took no mark at a TICK where another ALARM_START took one (section 5), else true |

AL-0a's sub-kinds (-2c-1): `NODE_UNAVAILABLE`, `NODE_CONTEXT_MISMATCH`, `TIP_RACE_NOT_SETTLED`, `NODES_LAG`,
`S14_HASH_MISMATCH`, `STORE_NOT_SYNCED`, `HEART_NAMED_NOT_CURRENT`. AL-0b's (the 555-a tip-age states that raise
it): `TIP_STALE`, `TIP_TIMES_DISAGREE`, `TIP_TIMES_UNREAD`, `TIP_CLOCK_BEHIND`, `TIP_CLOCK_UNREADABLE`. AL-1 to
AL-7 have none. -2c-1 gives each entry the members `kind` and: `node` (`A` or `B`) for `NODE_UNAVAILABLE` and
`NODE_CONTEXT_MISMATCH`; `attempts` for `TIP_RACE_NOT_SETTLED`; `lag` and `behind` for `NODES_LAG`; `heights`
for `S14_HASH_MISMATCH`; `standing` (`SYNCING` or `UNAVAILABLE`) and `reason` (null while `SYNCING`) for
`STORE_NOT_SYNCED`; `reason` for `HEART_NAMED_NOT_CURRENT`. AL-0b's entries have `kind` only.

### ALARM_CLEAR

| Field | Type | Value |
|---|---|---|
| `alarm_id` | str | as in ALARM_START |
| `sub_kind` | str\|null | as in ALARM_START |
| `episode_key` | obj | as in ALARM_START |
| `name` | str\|null | as in ALARM_START |
| `tick_seq` | int | `seq` of the TICK line at which the episode key left the alarm or the alarm turned false (for the loop's alarm, the first checked tick) |
| `start_seq` | int | `seq` of the ALARM_START it ends |

### ALARM_ACK

| Field | Type | Value |
|---|---|---|
| `alarm_id` | str\|null | the line's `alarm_id`, or null for a malformed line |
| `sub_kind` | str\|null | the acknowledged episode's `sub_kind` when accepted, else null |
| `asked_sub_kind` | str\|null | the line's `sub_kind`, or null |
| `asked_start_seq` | int\|null | the line's `start_seq`, or null |
| `start_seq` | int\|null | the ALARM_START it acknowledges when accepted, else null (also for `ALREADY_ACKNOWLEDGED`) |
| `acknowledgment_utc` | UTC | the host UTC when the loop read the line from its input (stamped at receipt) |
| `emission_utc` | UTC\|null | that ALARM_START's `emission_utc` when accepted, else null |
| `emission_to_acknowledgment_s` | int\|null | `acknowledgment_utc − emission_utc`, whole seconds: the second `B_detect` field (FBO :282), or null |
| `channel` | str\|null | the line's `channel`, or null |
| `channel_utc` | UTC\|null | the line's `channel_utc` (the channel's own time), kept as a cross-check only, never used in a field above |
| `clock` | str | `HOST_UTC_WALL_CLOCK` |
| `accepted` | bool | true when it matched an episode not yet acknowledged |
| `refusal` | str\|null | null, or `ACK_MALFORMED`, `START_SEQ_UNKNOWN`, `ALREADY_ACKNOWLEDGED`, `NO_UNACKNOWLEDGED_ALARM` |

A line that is not accepted is still written (it shows the input was received); the text of a malformed line is
never copied.

### CRITICAL_HEIGHT

| Field | Type | Value |
|---|---|---|
| `height` | int | a requested critical height both nodes reached |
| `hash_a_display` | str | Node A's block hash at it (display order) |
| `hash_b_display` | str | Node B's |
| `equal` | bool | whether they are the same (a difference is also AL-0a `S14_HASH_MISMATCH` in the tick) |
| `tick_seq` | int | `seq` of the TICK line |

One line per height, the first time the tick reports it in `critical_heights.reached`; the height is then left
out of every later request (045b :1854, S14 under scope (b)).

### STOP

| Field | Type | Value |
|---|---|---|
| `reason` | str | `MAX_TICKS`, `SIGNAL_SIGTERM`, `SIGNAL_SIGINT`, `SIGNAL_SIGHUP`, `TICK_EXIT`, `LOG_WRITE_FAILED` or `INTERNAL_ERROR` (an unexpected error of the loop) |
| `exit` | int | the loop's exit code (section 7) |
| `tick_exit` | int\|null | the tick's exit for `TICK_EXIT`, else null |
| `ticks` | int | ticks run |
| `failed_ticks` | int | ticks with a `tick_error` |
| `stderr_lines_dropped` | int | stderr lines not written whole within 0.1 s, or at once after a line was dropped (no wait until one is written again), because of a stopped terminal, a pipe nobody reads or a closed stream, or because another writer sharing the pipe filled it (the write itself is cut off after that bound, at least 0.01 s, by a timer; fd 2 is never made non-blocking, since its other writers share it), and dropped; the stop's own stderr line (`STOP <reason> exit=<n>`) is written before the STOP line and counted; any drop makes the stop exit 4 (section 7) |
| `open_alarms` | list | `{"alarm_id", "sub_kind", "episode_key", "start_seq"}` for each episode started and not cleared, in the order they started (no clear is invented) |
| `pending_critical_heights` | list | critical heights never reached |
| `unused_fault_marks` | int | marks accepted that no ALARM_START took |
| `refused_fault_marks` | list | one object per refused mark, in the order refused (below), for the first 256 refused marks only |
| `refused_fault_marks_total` | int | every refused mark, listed or not |
| `input_errors` | obj | for each input given (`ack`, `mark`), how many times it became unreadable |
| `episodes` | list | one object per ALARM_START, in order (below) |

### Episode

| Field | Type | Value |
|---|---|---|
| `alarm_id` | str | the alarm |
| `sub_kind` | str\|null | the sub-kind |
| `episode_key` | obj | as in ALARM_START |
| `start_seq` | int | its ALARM_START |
| `clear_seq` | int\|null | its ALARM_CLEAR, or null |
| `ack_seq` | int\|null | its accepted ALARM_ACK, or null |
| `fault_start_source` | str | as in ALARM_START |
| `fault_to_emission_s` | int | as in ALARM_START |
| `b_detect_sample` | bool | as in ALARM_START |
| `emission_to_acknowledgment_s` | int\|null | as in its ALARM_ACK, or null |
| `b_detect_status` | str | `MEASURED` when it is a sample and was acknowledged, else `UNMEASURED` |

### Refused mark

| Field | Type | Value |
|---|---|---|
| `alarm_id` | str\|null | the mark's `alarm_id`, or null for a malformed mark |
| `sub_kind` | str\|null | the mark's `sub_kind`, or null |
| `fault_start_utc` | UTC\|null | the mark's `fault_start_utc`, or null for a malformed mark |
| `received_utc` | UTC | the host UTC when the loop read the mark |
| `mark_refused` | str | `MARK_MALFORMED`, `MARK_BEFORE_FIRST_TICK`, `MARK_WHILE_OPEN`, `MARK_BEFORE_LAST_CLEAR`, `MARK_UNKNOWN_ALARM`, `MARK_UNKNOWN_SUB_KIND`, `MARK_WHILE_WAITING` or `MARK_AFTER_EMISSION` (section 6) |

## 5. Alarm edges and `B_detect`

- Edges and episodes are per episode key: (`alarm_id`, `sub_kind`, the values of the key members), where `sub_kind`
  is the `kind` of a `sub_kinds` entry of the tick's alarm and the key members are those the judgement table below
  names for its `kind`. A key member is a member of the entry, except `reason_class`, which is the class of the
  entry's `reason` in the class table below. Each key member's value is a string or null: a member missing from the
  entry reads as null, and an entry with a key member (for `reason_class`, a `reason`) of any other type makes the
  tick `TICK_OUTPUT_INVALID` (section 4). When the tick's `raised` is true, each key present that is not open
  starts (the entries with one key are one episode), and each open episode of that alarm whose key is no longer
  present clears, unless its sub-kind is not judged at that tick or a holding entry of its sub-kind keeps it open
  (next bullet). So a new value of a key member is an ALARM_CLEAR of the old episode and then an ALARM_START of the
  new one at the same TICK, as is one sub-kind replaced by another; a new value of any other member (which node is
  `NODE_UNAVAILABLE`, a `NODES_LAG` `lag`, a `STORE_NOT_SYNCED` `reason` of the same class at one `standing`)
  changes nothing. An alarm raised with no sub-kinds (AL-1 to AL-7) has the one key (`alarm_id`, null, none). When
  `raised` is false, every open episode of that alarm clears. `raised` null (status `HEART_NOT_CURRENT` or
  `NOT_MEASURED`, for example AL-0b `NODES_NOT_AGREED` while the nodes disagree) changes nothing: open stays open,
  closed stays closed. An alarm missing from a result is treated as null.
- Judged at this tick. The tick does not judge every sub-kind at every tick: an entry's absence can mean "no fault"
  or "not compared". An entry is unjudged when its members have the values the table's Unjudged value column gives
  and, where its Unjudged only with column lists kinds, its alarm has an entry of one of those kinds at the same
  tick (`any tick`: no such condition). The members in these columns, `reason_class` included, are read as for a
  key member: `reason_class` is the class of the entry's `reason` in the class table below. A sub-kind of a raised
  alarm is judged at a tick when it has an entry that is not unjudged (a judged entry), or when it has no entry and
  no entry of that alarm at that tick is of a kind its Not judged when column lists. Otherwise it is not judged at
  that tick: it is null for that sub-kind, as `raised` null is for an alarm. Every open episode of that alarm and
  sub-kind, whatever its key, stays open (it does not clear), no episode starts for it, and so no mark is taken by
  it (section 6); an unjudged entry is read for nothing else. An alarm whose `raised` is null judges none of its
  sub-kinds at that tick, its null sub-kind (AL-1 to AL-7) included; one whose `raised` is false judges every
  sub-kind of its table rows absent, and its null sub-kind. A kind outside the table counts as judged only at ticks
  where it has an entry: its first start after the first tick is `PRESENT_WHEN_FIRST_JUDGED`, and while its alarm
  is raised without its entry its open episode stays open (it clears when the alarm is false). A judged entry whose
  members have one of the values the Holds other keys column gives starts its own key as usual but keeps every
  other open key of its sub-kind open (it never clears them), and it does not count as judging that sub-kind for
  the first-judged rule below; when the sub-kind also has a judged entry that does not hold, that one decides as
  usual. The other sub-kinds of the alarm are read as usual. When a judged entry and an unjudged entry of one
  sub-kind are present at the same tick (-2c-1 gives no such tick), the judged one wins: the sub-kind is judged
  from the judged entries alone. An alarm raised with only unjudged entries starts nothing, not even a
  null-sub-kind episode, keeps its not-judged sub-kinds' episodes open and clears the open episodes of the
  sub-kinds it judges absent (-2c-1 gives no such tick: its unjudged Heart entry always comes with a
  STORE_NOT_SYNCED entry, and a NODE-class store entry without a node fault is judged). Every row below is read
  from -2c-1 at its branch head 7fb61dff (not merged yet; the loop-read behaviour is that of 78d54756)
  (`al0a_sub_kinds`, `read_store`, `document`, `monitor_alarms::tip_age`): both nodes are read at every tick; the
  tip race, the lag and the S14 heights are compared only when both nodes are READ (`observe_once`), the lag and
  S14 also not while the tips race; the Heart is read only at a SYNCED store (`HEART_NAMED_NOT_CURRENT` `reason`
  `STORE_NOT_SYNCED` otherwise); 555-a decides the tip age in the order times unread, times disagree, clock
  unreadable, clock behind, age, so a later state is not decided when an earlier one holds. For a store
  `UNAVAILABLE` because of a node (class `NODE`) the store's own state was not read; when the same tick shows that
  node fault (a node down, a tip race, a lag or an S14 mismatch: the store judge then fails on it; a node on
  another context: the judge is not run, `read_store`) the node sub-kind carries the tick and the store entry is
  unjudged. Without one, the store judge's own node reads failed while step 1 read both nodes (the judge also asks
  for block counts and headers, in its own session), so the entry is judged: its own (`UNAVAILABLE`, `NODE`)
  episode starts, with its ALARM_START and stderr line, and it holds the store's SYNCING, STORE or WRITER episode
  open. The same happens when a block arrives between step 1 and the judge, so that the judge gives
  `NODES_DISAGREE` or `TIP_RACE_NOT_SETTLED` after its attempts while step 1 saw both nodes agree: a one-tick
  (`UNAVAILABLE`, `NODE`) episode starts, a sample like a `NODES_LAG` on block arrival, and a waiting
  `STORE_NOT_SYNCED` mark is taken by it; the store's own start at a later tick (a SYNCING not open before) is then
  a second sample of that injection. So a Heart failure at a SYNCED store that the store falls behind and catches
  up again, an S14 mismatch across a tick with node B down, or a STORE_DIVERGED episode across a tick with node B
  down, is one episode: no ALARM_CLEAR, no second ALARM_START, and its acknowledgement holds.

  | Sub-kind | Alarm | Key members | Unjudged value | Unjudged only with | Holds other keys | Not judged when |
  |---|---|---|---|---|---|---|
  | `NODE_UNAVAILABLE` | `AL-0a` | none | none | any tick | none | never |
  | `NODE_CONTEXT_MISMATCH` | `AL-0a` | none | none | any tick | none | never |
  | `TIP_RACE_NOT_SETTLED` | `AL-0a` | none | none | any tick | none | `NODE_UNAVAILABLE`, `NODE_CONTEXT_MISMATCH` |
  | `NODES_LAG` | `AL-0a` | none | none | any tick | none | `NODE_UNAVAILABLE`, `NODE_CONTEXT_MISMATCH`, `TIP_RACE_NOT_SETTLED` |
  | `S14_HASH_MISMATCH` | `AL-0a` | none | none | any tick | none | `NODE_UNAVAILABLE`, `NODE_CONTEXT_MISMATCH`, `TIP_RACE_NOT_SETTLED` |
  | `STORE_NOT_SYNCED` | `AL-0a` | `standing`, `reason_class` | `reason_class` = `NODE` | `NODE_UNAVAILABLE`, `NODE_CONTEXT_MISMATCH`, `TIP_RACE_NOT_SETTLED`, `NODES_LAG`, `S14_HASH_MISMATCH` | `reason_class` = `NODE` or `WRITER` | never |
  | `HEART_NAMED_NOT_CURRENT` | `AL-0a` | `reason` | `reason` = `STORE_NOT_SYNCED` | any tick | none | `STORE_NOT_SYNCED` |
  | `TIP_TIMES_UNREAD` | `AL-0b` | none | none | any tick | none | never |
  | `TIP_TIMES_DISAGREE` | `AL-0b` | none | none | any tick | none | `TIP_TIMES_UNREAD` |
  | `TIP_CLOCK_UNREADABLE` | `AL-0b` | none | none | any tick | none | `TIP_TIMES_UNREAD`, `TIP_TIMES_DISAGREE` |
  | `TIP_CLOCK_BEHIND` | `AL-0b` | none | none | any tick | none | `TIP_TIMES_UNREAD`, `TIP_TIMES_DISAGREE`, `TIP_CLOCK_UNREADABLE` |
  | `TIP_STALE` | `AL-0b` | none | none | any tick | none | `TIP_TIMES_UNREAD`, `TIP_TIMES_DISAGREE`, `TIP_CLOCK_UNREADABLE`, `TIP_CLOCK_BEHIND` |
  | any other | any | none | none | any tick | none | without its entry |

  AL-0b is null (`NODES_NOT_AGREED`) whenever AL-0a has a node sub-kind, so its sub-kinds are then not judged as a
  whole (above); AL-1 to AL-7 are null without a CURRENT Heart, AL-8 to AL-10 always. `HEART_NAMED_NOT_CURRENT` is
  keyed by `reason`: at a SYNCED store a Heart that is not CURRENT has `reason` `HEART_NOT_CURRENT` (not in the
  CURRENT index) or `REPLAY_STATE_ERROR` (its state or countdown could not be read), two faults. `STORE_NOT_SYNCED`
  is keyed by `standing` (`SYNCING`, behind and catching up, or `UNAVAILABLE`) and by the class of its `reason`
  (null while `SYNCING`): a store whose own state is at fault (`STORE`), a store another process had open or wrote
  during the read (`WRITER`) and a store whose judge could not read a node (`NODE`, when judged) are different
  faults, so a store in use that then reads diverged clears the `WRITER` episode and starts a `STORE` one. A
  `WRITER` entry, like a judged `NODE` one, holds the store's other open episodes open: that tick did not read the
  store (A's decision 17(a)/20a), so a store in use for a tick does not clear a SYNCING or diverged episode. A
  `reason` changing to another of the same class changes nothing.

  | Reason | Class |
  |---|---|
  | `NODE_UNAVAILABLE` | `NODE` |
  | `NODE_CONTEXT_MISMATCH` | `NODE` |
  | `NODE_GENESIS_MISMATCH` | `NODE` |
  | `NODES_DISAGREE` | `NODE` |
  | `TIP_RACE_NOT_SETTLED` | `NODE` |
  | `STORE_DIVERGED` | `STORE` |
  | `STORE_IN_USE` | `WRITER` |
  | `STORE_WAL_RECOVERY_REQUIRED` | `STORE` |
  | `REPLAY_STATE_ERROR` | `STORE` |
  | `STORE_CHANGED_DURING_READ` | `WRITER` |
  | `STORE_MISSING` | `STORE` |
  | any other | `STORE` |
  | null | null |

- There is no separate id-level line: an alarm id is raised exactly while at least one of its episodes is open, so
  its state is read from the episode lines (an id-level line would always coincide with an episode line). One TICK
  can start more than one episode, and one fault can show as more than one: a fork at which node B is also behind
  gives AL-0a `S14_HASH_MISMATCH` and AL-0a `NODES_LAG` at the same TICK, two episodes. One node going down at a
  SYNCED store gives one, `NODE_UNAVAILABLE`: the store's `STORE_NOT_SYNCED` `UNAVAILABLE` entry (`reason`
  `NODE_UNAVAILABLE`, the judge cannot read that node) is unjudged beside the node sub-kind (above). Each episode
  gets its own ALARM_START, stderr line and `B_detect` fields (FBO :282, "for each alarm"), so a fault that appears
  under an alarm already raised for another reason (an `S14_HASH_MISMATCH` while AL-0a is open for
  `STORE_NOT_SYNCED`) is not hidden.
- Which episode is an injected fault's `B_detect` sample: the one its mark names. The driver gives the mark the
  alarm and sub-kind of the fault it injects (section 6); the ALARM_START that takes the mark is that sample
  (`fault_start_source` `INJECTION_MARK`, or `FIRST_TICK_HELD` with `mark_refused` `MARK_AFTER_EMISSION`). Every
  other ALARM_START at the same TICK (the same `tick_seq`) that takes no mark has `b_detect_sample` false: it is
  the same injection seen by another check, and its `FIRST_TICK_HELD` start would be a second sample of it. At a
  TICK where no start takes a mark, every start is a sample but a `PRESENT_AT_FIRST_TICK` or
  `PRESENT_WHEN_FIRST_JUDGED` one.
- An episode key already present on the first tick starts at the first tick (`first_tick` true). One tick is enough
  to start one, a `NODES_LAG` on block arrival included (-2c-1 For-A 7, B default "the first"). After the first
  tick, a start's `fault_start_source` (when it takes no mark) is decided by the earlier checked ticks: if none of
  them judged its (alarm, sub-kind) (each was not judged, `raised` null, or only a holding entry judged it; a
  failed tick does not count), it is `PRESENT_WHEN_FIRST_JUDGED`, with `b_detect_sample` false and `first_tick`
  false, since the fault may predate the watch: a Heart behind a store that has not been SYNCED since the start, a
  store first read `UNAVAILABLE` because of a node, S14 while node B has been down since the start, AL-1 while no
  Heart has been CURRENT. If any earlier checked tick judged it, even only as absent, it is `FIRST_TICK_HELD`, a
  sample, whatever ticks without judgement came between: S14 judged absent at the first tick, two ticks with node B
  down, then S14 at the fourth tick is `FIRST_TICK_HELD` with the fourth tick's observation time as its fault
  start; the not-judged ticks are left out of `fault_to_emission_s`, as failed ticks are. An accepted mark the
  start takes makes it `INJECTION_MARK`, a sample, in either case.
- Fault start (FBO :282): the injection mark the start took (`INJECTION_MARK`, section 6), else the observation
  time (`tick.clock.utc`) of the tick at which the episode key first held (`FIRST_TICK_HELD`; the TICK line's own
  `utc` if the tick gave no time). On the first tick it is that tick's time and `PRESENT_AT_FIRST_TICK`, with
  `b_detect_sample` false.
- A `FIRST_TICK_HELD` sample is a partial sample (FBO :241): its first leg leaves out the time before the tick
  that held, so it cannot lower `B_detect`.
- `FIRST_TICK_HELD` is later than the host's first receipt of the block at which the condition held by up to one
  poll plus the tick's duration, and by more when the ticks before it failed or did not judge its sub-kind;
  `fault_to_emission_s` then leaves that delay out. A driver that needs the whole leg injects the fault and gives a
  mark.
- The loop's own alarm: `TICK_FAILING_AFTER` (3) failed ticks in a row (each with a `tick_error`, of one kind or
  mixed: a refusal, invalid or too large output, a timeout, a killed tick, a spawn or request write failure) start
  `MONITOR_TICK_FAILING` (sub-kind null) at the third; its fault start is the first failed tick of that run of
  failed ticks in a row (`FIRST_FAILED_TICK`, that TICK line's `utc`); the next tick with a checked result clears
  it. It is acknowledged like any other alarm.
- Emission: the ALARM_START line itself (`emission_utc` = its `utc`); a one-line copy goes to stderr.
- Acknowledgement: stamped when the loop reads the line (`acknowledgment_utc`), on the host clock; the channel's
  time (`channel_utc`) is a cross-check only. The inputs are read every 0.5 s while the loop waits and while a
  tick runs. Without a backlog the stamp is at most about 0.5 s plus one log write after the line reached the
  input. Under a backlog (more than 64 ack lines in one read, section 6) a line that reaches the input waits there
  until the lines read before it are taken, 64 every 0.5 s: at most 1,024 reads of the inputs, about 512 s, for
  a full 64 KiB read of 1-byte lines. The stamp is the time of the read, also for a line taken later from the
  backlog, and a line can only acknowledge an episode whose ALARM_START was already in the log when it was read
  (else `START_SEQ_UNKNOWN` or `NO_UNACKNOWLEDGED_ALARM`): it is judged as of its read. Until an episode is
  acknowledged its second field is null and it is `UNMEASURED`; emission time alone never replaces `B_detect`
  (FBO :282).
- `B_detect` sample for one episode = `fault_to_emission_s + emission_to_acknowledgment_s` when
  `b_detect_status` is `MEASURED`.

## 6. Inputs

Both are read from where the last read ended, a complete LF-ended line at a time, at most 4,096 bytes a line. An
input file must be a regular file: one that exists at start and is not (a FIFO, a device, a folder) is refused with
exit 2 (`ACK_FILE_NOT_REGULAR`, `MARK_FILE_NOT_REGULAR`), and one that becomes so later is unreadable
(`NOT_A_REGULAR_FILE`) and never opened in a way that blocks. One read of an input (a file or stdin) takes at most
64 KiB, and an input is read again only when every line of its last read has been taken. Every mark line is taken
at its read, so it is judged by the loop's state at that read. While the loop runs, at most 64 ack lines are taken
per read of the inputs and the rest wait, in order, in the backlog, so a flood of acknowledgements never holds the
loop; each keeps the time and the log position of its read (`acknowledgment_utc`), so it is judged as of its read
(section 5). At a stop (any STOP reason but a log write failure or `INTERNAL_ERROR`), an input with no lines
waiting is read once more, then every line already read is taken before STOP and written as an ALARM_ACK or a
refused mark (section 7 gives the bound); bytes not yet read stay in the input. A partial line (read, its LF not
yet read) is dropped at the stop and not recorded: for a file its bytes stay in the file, for stdin they are gone.
`--ack-stdin` is refused with exit 2 when stdin is a terminal (`ACK_STDIN_IS_A_TERMINAL`: a background loop reading
it would be stopped). Identifiers (`alarm_id`, `sub_kind`, `channel`) must match their pattern as a whole string,
so a trailing LF or other character makes the line malformed. A longer line is refused once as malformed
(`ACK_MALFORMED` or `MARK_MALFORMED`), as soon as more than 4,096 of its bytes have been read without an LF; every
byte up to and including its LF, over any number of reads, belongs to that refused line and is dropped, and the
next line starts after that LF (a file and stdin alike). A time member (`channel_utc`, `fault_start_utc`) must be a
real UTC time as in section 2: an impossible calendar value (month 13, day 32, hour 24, 30 February) makes the line
malformed. Lines already in a file when the loop starts (up to its size at START) count as read right after START,
before the first tick, however many reads they take: a mark among them is refused `MARK_BEFORE_FIRST_TICK` and an
acknowledgement matches nothing. A read never takes bytes from both sides of that size. A file that does not exist
yet has no lines. An input that cannot be read (a folder, no permission, a read error on stdin) does not stop the
loop: it has no lines while it stays so, a stderr line says so when it becomes unreadable and when it becomes
readable again, and STOP's `input_errors` counts the times it became unreadable. Monitoring goes on because an
alarm still reaches the log and stderr without the input; only acknowledgements (or marks) are lost while it lasts.

- Acknowledgement (`--ack-file <path>`, appended to by the channel or a person, or `--ack-stdin`): one JSON
  object a line, members `alarm_id` (required), `sub_kind`, `start_seq` (an ALARM_START `seq`), `channel` (1 to
  64 of `A-Z a-z 0-9 _ . : -`), `channel_utc` (RFC 3339 Z). No other member. Without `start_seq` it acknowledges
  the latest unacknowledged episode of that alarm, and when `sub_kind` is given the latest of that sub-kind only
  (whatever its key members); with `start_seq` and `sub_kind`, an episode of another sub-kind is
  `START_SEQ_UNKNOWN`. An episode can be acknowledged after it cleared, once.
- Injection mark (`--mark-file <path>`, written by a driver): one JSON object a line, `alarm_id` and
  `fault_start_utc` (RFC 3339 Z), and `sub_kind` when it is for one sub-kind (needed when the alarm is already open
  for another one, and to name the sample when one fault starts more than one episode, section 5). A mark names an
  alarm and a sub-kind, never key members; a sub-kind not judged at a tick (section 5) starts nothing, so it never
  takes a mark, which waits for the next start of that sub-kind at a tick that judges it. A mark is accepted only
  if it was read after the first tick with a checked result, while no episode it matches (that alarm, or that alarm
  and sub-kind, whatever its key members) is open, and its `fault_start_utc` is not before the last clear of an
  episode it matches (so a clear of another sub-kind of that alarm does not refuse it); it then waits for the next
  ALARM_START it matches, and while it waits another mark is refused `MARK_WHILE_WAITING` when either of the two
  could be taken by a start the other could take (the same alarm, and the same sub-kind or no sub-kind on either
  one), so a mark left over from one injection never becomes the fault start of a later one. Otherwise it is
  refused: `MARK_BEFORE_FIRST_TICK`, `MARK_UNKNOWN_ALARM` (an `alarm_id` no checked tick has reported; so the
  loop's own alarm `MONITOR_TICK_FAILING`, which no tick reports, takes no marks),
  `MARK_UNKNOWN_SUB_KIND` (a `sub_kind` outside its alarm's rows of the section 5 table), `MARK_WHILE_OPEN`,
  `MARK_BEFORE_LAST_CLEAR`, or `MARK_MALFORMED`, so at most one mark waits per table sub-kind of an alarm, or one
  for an alarm without sub-kinds; a waiting mark whose time is later than the emission of the start that takes it
  is refused `MARK_AFTER_EMISSION`. Each refusal is counted in STOP's `refused_fault_marks_total`; the first 256 of
  a run are also listed in `refused_fault_marks` and each writes a stderr line, the rest neither (a flood of bad
  marks never fills STOP or stderr). Marks are not lines of their own: the ALARM_START that takes one shows it.

## 7. Exit codes and stops

| Exit | When | Last line |
|---|---|---|
| 0 | `--max-ticks` reached, or SIGTERM, SIGINT or SIGHUP, with every stderr line written | STOP `MAX_TICKS` / `SIGNAL_*` |
| 2 | bad arguments: log path not absolute, log already there or not creatable, `--bitagi` not absolute or not an executable file, template unreadable, not strict JSON, wrong `schema` or bad `critical_heights`, an ack or mark file that is not a regular file (`ACK_FILE_NOT_REGULAR`, `MARK_FILE_NOT_REGULAR`) or cannot be inspected (`ACK_FILE_UNREADABLE`, `MARK_FILE_UNREADABLE`), `--ack-stdin` with a terminal on stdin (`ACK_STDIN_IS_A_TERMINAL`), the temporary folder not creatable (`WORK_FOLDER_FAILED`), a bad option value | none (no log is created, or the existing one is untouched) |
| 2 | the tick exited 2 (an invalid request) before the first tick with a checked result, with every stderr line written | STOP `TICK_EXIT` with `tick_exit` 2 |
| 5, 6 | the tick exited 5 (credential material) or 6 (mainnet, refused before any node), at any tick, with every stderr line written | STOP `TICK_EXIT` with that `tick_exit` |
| 4 | a log write failed (after one attempt at a STOP line); an unexpected error of the loop; any stop of the loop (exit 0, 2, 5 or 6 above) after a stderr line could not be written (AGENTS.md section 12) | STOP `LOG_WRITE_FAILED` or `INTERNAL_ERROR` when that attempt worked (else a stderr line says the log took none); STOP with `exit` 4 and `stderr_lines_dropped` above 0, its `reason` and `tick_exit` unchanged (a tick's 2, 5 or 6 stays in `tick_exit`) |
| 5 | optimized Python (`-O`) | none |

A tick exit 2 after a checked tick is a failed tick and the loop goes on (A's decision 8): -2c-1 also exits 2 for
store file states it meets while it runs (`STORE_UNREADABLE`, `STORE_TOO_LARGE`, `INPUT_NOT_A_REGULAR_FILE`,
`STORE_CONTEXT_MISMATCH`, `FIRST_EFFECTIVE_HEIGHT_MISMATCH`) and for `LOOPBACK_SESSION`, and a state of the store
must not turn the monitor off; three in a row start `MONITOR_TICK_FAILING`. The STOP line's `exit` is always the
loop's exit; a stderr line that is not written never blocks the loop (it is dropped and counted).

A stop signal takes effect within `tick_timeout_s`: one that arrives while a tick runs takes effect when that tick
ends, and one that arrives just before a tick starts still gets that one tick. Then every input line already read
is taken and written (section 6). The bound on that work: one read of each input, at most 64 KiB, plus a partial
line of at most 4,096 bytes, so at most 65,536 ack lines and 65,536 mark lines. Each ack line is one ALARM_ACK line
of at most 600 bytes beyond the bytes of its input line (about 430 for a malformed one: 421 to 428 measured, as
`seq`, `mono_ns` and the times grow), written without its own fsync (STOP's covers them): at most about 40 MB. A
mark line writes no log line, at most one of the 256 entries in STOP and at most one stderr line, and no stderr
line is waited on after one was dropped. On the builder's host the worst case measured about 3 s (65,472 ALARM_ACK
lines, 28 MB, `Stops.test_a_stop_after_a_flood_is_bounded`). Then the STOP line follows, and the loop's temporary
folder (the tick request and the tick's output files) is removed. SIGKILL cannot be handled: the log then ends
without STOP (possibly with an incomplete last line) and the temporary folder `claude-track-monitor-*` is left in
the temporary directory (`TMPDIR`).

Any other tick outcome (exit 3 or 4, a timeout, invalid, too large or lost output) is a TICK line with its
`tick_error` and the loop goes on (A Q2c-13: a tick's exit is 0 whenever there is an observation, whatever the
alarms).

## 8. `HEART_NOT_CURRENT`, `NOT_MEASURED` and `heart.failure`

Without a Heart (P5-002 scope (b)) the tick gives AL-1 to AL-7, the countdown, READY and the W/L window as
`HEART_NOT_CURRENT` with `heart.failure` false, and AL-8 to AL-10 as `NOT_MEASURED` (A Q2c-1, Q2c-2). They
appear in each TICK line's `tick` object, and `countdown_status` repeats the countdown's. They are never an edge.
A TICK line with `countdown_status` `HEART_NOT_CURRENT` counts as countdown output for FU1 :227 ("Countdown and
alarm output exist during P5-002"; A Q2c-13: A writes this reading into follow-up registration 2 and the P5-004
record).

In this document a failure is a failed tick: a TICK with a `tick_error` (section 4), the only failure the loop
counts, towards `MONITOR_TICK_FAILING` (section 5). The tick's `heart.failure` is never one, and the loop never
reads it; it stays inside the TICK's `tick`. The tick sets it true whenever a Heart is named and is not CURRENT,
also while the store is not SYNCED (`tick.store.standing` `SYNCING` or `UNAVAILABLE`; then `tick.heart.reason` and
the AL-0a `HEART_NAMED_NOT_CURRENT` entry's `reason` are `STORE_NOT_SYNCED`). On such a tick it is not a monitor
failure (A, -2c-1 pre-check item 8): the Heart is not judged while the store is behind, and in the log the Heart
sub-kind is not judged at that tick (section 5): it starts, clears and takes nothing. A Heart that is named and not
CURRENT at a SYNCED store is `heart.failure` true with `tick.store.standing` `SYNCED`; in the log it is an AL-0a
`HEART_NAMED_NOT_CURRENT` episode keyed by its `reason` (never `STORE_NOT_SYNCED`). It starts at the first SYNCED
tick that shows it (`PRESENT_WHEN_FIRST_JUDGED`, not a sample, when the store had not been SYNCED since the watch
began), stays open across ticks whose store falls behind again, and clears when a SYNCED tick no longer shows it,
at a new `reason`, or when AL-0a turns false.

## 9. Reading a log

`tools/claude_track_monitor.py check --log <path>` reads a log and prints one JSON line: `valid`, `errors`
(order, schema, `seq`, `mono_ns` order, UTC text, START first, START and STOP placement), `lines`,
`incomplete_last_line`, `kinds` (count of each), `ticks`, `gaps_at_seq`, `clock_steps_at_seq`,
`utc_backwards_at_seq`, `suspends_at_seq`, `alarm_starts` (`seq`, `alarm_id`, `sub_kind`), `last_line` (`seq`,
`kind`, `utc` of the last whole line) and `stopped` / `stop`. Exit 0 for a well-formed log that ends with STOP, 3
for a well-formed log without STOP (the loop was killed or still runs; `last_line.utc` says when it last wrote),
2 otherwise. It recomputes gaps, suspends and clock steps from the TICK lines' `mono_ns`, `suspended_ns` and `utc`
with the rules of section 2. A malformed line is never an exception: it is reported in `errors` (the first 8)
with exit 2. Each line's `mono_ns` must be an integer not less than the last integer `mono_ns` before it; a line
that is not JSON (or nests too deeply to read) or has the wrong `schema` or `kind` ends the reading there; gaps
and clock steps are computed only for a log without errors.
