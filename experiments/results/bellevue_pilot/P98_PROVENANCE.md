# P98 — provenance and exclusions, recorded before any score

Written 2026-10-15, after the P98 corpus was built and **before the frozen
model was run on it**. Everything below comes from file metadata, the burnt-in
clock, the camera position and the target counts. None of it comes from a
model output. The protocol is
[PREREGISTRATION_P98.md](PREREGISTRATION_P98.md), and it is unchanged.

## Source

The Bellevue traffic-video Drive folder, camera NE 8th St. The licence is
unresolved, so this is internal engineering use only and not publishable (S63).
Eleven files were taken, exactly the hours the protocol names. The ten night
hours (Sun 20:08 – Mon 05:08) were neither downloaded nor used.

Three of the eleven were already in the project owner's export at
`D:\bellevue\…\150th_SE38th\`: Sun 18:08, Mon 09:08 and Mon 13:08. That folder
is named for **another camera**, so camera identity was taken from the
filename and then checked against the image (below), never taken from a folder.
The other eight were downloaded from the source folder.

## Per file

The clock was read by eye from `scripts/clock_sheet.py` at 1 s, at the middle,
and at 2 s before the end. A file is continuous when its clock advances by the
file's own length. All eleven are 1280 × 720 at 29.99 fps.

| file (start) | stratum | frames | min | clock start → middle → end | continuous | samples | windows 60 s / 120 s | blocks 60 s / 120 s |
|---|---|---|---|---|---|---|---|---|
| Sun 18:08:23 | Sunday daylight | 107,972 | 60.0 | 18:08:23 → … → 19:08 | yes | 1800 | 115 / 113 | 6 / 6 |
| Sun 19:08:24 | dawn/dusk | 107,985 | 60.0 | 19:08:24 → 19:38:23 → 20:08:21 | yes | 1800 | 115 / 113 | 6 / 6 |
| Mon 06:08:29 | dawn/dusk | 107,982 | 60.0 | 06:08:30 → 06:38:29 → 07:08:27 | yes | 1800 | 115 / 113 | 6 / 6 |
| Mon 07:08:31 | **primary** | 107,975 | 60.0 | 07:08:31 → … → 08:08 | yes | 1800 | 115 / 113 | 6 / 6 |
| Mon 08:08:31 | **primary** | 107,981 | 60.0 | 08:08:31 → 08:38:30 → 09:08:28 | yes | 1800 | 115 / 113 | 6 / 6 |
| Mon 09:08:30 | **primary** | 107,984 | 60.0 | 09:08:30 → … → 10:08 | yes | 1800 | 115 / 113 | 6 / 6 |
| Mon 10:08:31 | **primary** | 107,970 | 60.0 | 10:08:31 → 10:38:30 → 11:08:28 | yes | 1800 | 115 / 113 | 6 / 6 |
| Mon 11:08:31 | **primary** | 107,973 | 60.0 | 11:08:32 → 11:38:31 → 12:08:29 | yes | 1800 | 115 / 113 | 6 / 6 |
| Mon 12:08:31 | **primary** | 107,974 | 60.0 | 12:08:32 → 12:38:31 → 13:08:29 | yes | 1800 | 115 / 113 | 6 / 6 |
| Mon 13:08:32 | **primary** | **96,275** | **53.5** | 13:08:32 → 13:35:16 → **14:01:59** | yes, **short** | **1605** | **102 / 100** | **6 / 5** |
| Mon 14:08:31 | **primary** | 107,976 | 60.0 | 14:08:32 → 14:38:31 → 15:08:29 | yes, **buffered** | 1800 | **105 / 103** | 6 / 6 |

SHA-256 of every file is in `data/_bellevue/p98_sha256.txt`.

**Primary stratum totals:** 897 windows in 48 blocks at 60 s, and 881 windows
in 47 blocks at 120 s. **No file was excluded for a gap.**

### Mon 13:08 is short in the source, and it is kept

The file ends at 14:01:59, so it is 6 min 33 s short of the hour. The clock
advances by exactly the file's length, so the footage is continuous and stops
early; nothing is missing from inside it. The downloaded source copy is
**byte-identical** to the owner's export (SHA-256 `a6c51c11…f2f6cf`, both
857,731,685 bytes), so the export did not truncate it. The camera recorded
53.5 minutes.

Its windows come from its actual length, with no padding and no window joining
it to 14:08. A file of 1605 samples gives 60 s windows at starts
0, 15, …, 1515, which is 102 windows. Grouped by `start // 300` they form five
full 10-minute blocks of 20 windows and **a sixth block of 2** (starts 1500
and 1515). At 120 s the starts run 0 … 1485, which is 100 windows in **five**
full blocks. That is the expected arithmetic. Every full-length file also ends
in a partial block (15 windows at 60 s, 13 at 120 s). The bootstrap resamples
blocks with their windows, so a 2-window block carries 2 windows' weight and
does not count as a full one.

### Mon 14:08 carries the protocol's buffer

The file ends at 15:08:29, and P97's training data begins at 15:08:32. As the
protocol requires, a window is dropped if its inputs or its target reach the
last 149 samples. That leaves starts up to 1560 at 60 s (105 windows) and up
to 1530 at 120 s (103 windows).

## Same camera, same view: checked rather than assumed

The lanes are frozen, so a moved camera would be counted through the wrong
regions. A whole-frame thumbnail similarity cannot detect this here. Against
P97's footage it ranges from 0.22 to 0.80 on a camera that has not moved,
because a tall building's shadow sweeps the junction through the day, and the
07:08 and 08:08 files carry heavy low-sun glare. P97's own two hours score 0.86
against each other.

`scripts/camera_offset.py` measures the movement directly. It registers static
structure (ORB on contrast-equalised frames, clock masked, RANSAC homography)
at 5 points in each file against 3 points in the P97 reference. It reports the
displacement of the three lane centres as a fraction of frame width
(`p98_camera_offset.json`):

| file | pairs registered | median shift | max shift |
|---|---|---|---|
| P97's 15:08 (control) | 15/15 | 0.0005 | 0.0009 |
| Sun 18:08 | 13/15 | 0.0017 | 0.0127 |
| Sun 19:08 | 9/15 | 0.0016 | 0.0028 |
| Mon 06:08 | 9/15 | 0.0028 | 0.0037 |
| Mon 07:08 | 15/15 | 0.0026 | 0.0078 |
| Mon 08:08 | 15/15 | 0.0063 | 0.3901 |
| Mon 09:08 | 15/15 | 0.0018 | 0.0057 |
| Mon 10:08 | 12/15 | 0.0023 | 0.0072 |
| Mon 11:08 | 15/15 | 0.0025 | 0.0059 |
| Mon 12:08 | 11/15 | 0.0022 | 0.1840 |
| Mon 13:08 | 10/15 | 0.0021 | 0.0080 |
| Mon 14:08 | 15/15 | 0.0006 | 0.0050 |

Every median is at most 0.0063 of frame width, which is 8 px at 1280. The lane
radius is 0.25.

The two large maxima, at 08:08 and 12:08, were each checked with a red/green
overlay against the reference: 08:08 at 08:11, 08:38 and 08:53, and 12:08 at
12:38, 12:53 and 13:05. Crosswalk bars, stop lines, kerbs and building edges
coincide in every overlay. Only vehicles, shadows and glare separate. **Those
two maxima are registration failures under glare and shadow, not movement.**
The camera is fixed across all eleven files, and the frozen lanes apply
unchanged.

## How the corpus was built

`scripts/p98_build.py` builds each file on its own. It reads the detector,
operating point, step, window geometry and thresholds from P97's corpus
manifest, and the three lanes from P97's reviewed lane file. It writes a copy
of that lane file for each P98 file, unchanged apart from the clip key
(`data/_bellevue/lanes_p98/`).

`build_corpus.py` gained `--split-mode none` for this. Its temporal mode
divides one recording into train, validation and test splits, and it
correctly refuses a single hour as too short for three. P98 trains nothing and
reads no split. The evaluator builds its own windows from `counts.csv`, file
by file.

## Class support (targets only)

Decisions are windows × 3 lanes. A class with **fewer than 10** decisions is
flagged ⚑, and its F1 is not interpreted.

| | LOW | MEDIUM | HIGH |
|---|---|---|---|
| **primary, 60 s** | 129 | 1860 | 702 |
| west / north / east | 38 / 67 / 24 | 713 / 402 / 745 | 146 / 428 / 128 |
| dawn/dusk, 60 s | 203 | 444 | 43 |
| Sunday daylight, 60 s | 8 ⚑ | 240 | 97 |
| primary, 120 s | 75 | 1948 | 620 |
| west / north / east, 120 s | 21 / 52 / **2 ⚑** | 776 / 342 / 830 | 84 / 487 / 49 |

Per lane, outside the primary stratum, further cells fall under 10: dawn/dusk
west HIGH (3 at 60 s, 0 at 120 s) and east HIGH (5 at 120 s), and Sunday
daylight LOW on every lane. The protocol scores no per-lane comparison on
those strata.

## Observed, not acted on

- **Glare:** the 07:08 and 08:08 files carry heavy low-sun glare across the
  junction. P96 audited the detector in daylight but not under this glare. The
  protocol makes no exclusion for it, and none is made. If the result is
  examined per hour afterwards, that is exploratory and labelled as such.
- **Traffic mix:** the primary stratum is busier than P97's hours. North is
  HIGH in 428 of 897 windows. P96 measured that the detector undercounts more
  when traffic is busy (14% / 27% / 41%).
