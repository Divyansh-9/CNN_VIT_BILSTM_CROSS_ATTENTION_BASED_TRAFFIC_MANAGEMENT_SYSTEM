# Label-quality audit — protocol, fixed before any frame was chosen

Written 2026-10-15. A **pilot** audit: 20 frames from one camera. The frames
are correlated and one frame holds many vehicles, so this estimates the
direction and rough size of detector error. It is not a definitive accuracy
figure. If it shows material error, the sample is expanded before any threshold
or label changes.

## Frames — systematic, not chosen

From the 3,600 samples of the Bellevue NE 8th corpus (15:08–17:08), take
samples `k = r + 180·i` for `i = 0 … 19`, with `r` drawn from `0 … 179` by a
random generator seeded with 2026. That is one frame every 6 minutes, spread
across both hours and across signal phases. No frame is chosen for being a
detector failure or a success. Each frame is decoded at exactly the frame the
detector saw: the corpus's own forward sampling with a stride of 60.

## The lane regions shown

Each pixel is coloured by the lane the corpus would assign it to: the nearest
of the four reviewed centres, within the normalised 0.25 reach. Uncoloured
pixels are unassigned.

| lane | approach | colour |
|---|---|---|
| lane_0 | west | blue |
| lane_1 | north | orange |
| lane_2 | south | green |
| lane_3 | east | magenta |

## Counting rules, fixed before counting

- **Count:** cars, vans, pickups, buses, trucks, motorcycles, and bicycles
  being ridden. Moving, waiting and **parked** vehicles all count: the audit
  measures the detector, and the detector does not know parking.
- **A vehicle belongs to the lane whose colour lies under the centre of its
  body.** A vehicle centred on uncoloured ground is not counted.
- **Partly visible:** count it if it is recognisably a vehicle and its centre
  is in frame. A vehicle hidden behind another is not counted. Do not guess at
  what cannot be seen.
- **Never count** painted road markings (the bicycle-lane symbol included),
  pedestrians, poles, shadows, or a bicycle with no rider.
- **Blind:** the page shows no detector boxes and no detector counts. The
  comparison runs only after every frame is counted and exported.

## Reported

Per lane:

- the mean absolute error, the signed bias (detector − manual), and the share
  of frames where the counts agree exactly;
- **the painted bicycle symbol:** in how many audited frames the detector
  reported a bicycle at the symbol;
- **the far north queue:** the north lane's bias, compared with the other
  lanes'.

Both sets of counts are kept: the manual counts in `audit_manual.json`, the
detector counts in the corpus's `counts.csv`.
