# MFSTNet — Explained Simply

**Read this if the other documents feel heavy.** Everything here is in plain English with worked
examples. No prior knowledge assumed.

If you want the formal versions afterwards: [README](README.md) for the map,
[PRD](docs/00-planning/PRD.md) for exact numbers, [docs/README](docs/README.md) for everything else.

---

## Contents

1. [What are we building?](#1-what-are-we-building)
2. [Where we started and where we are now](#2-where-we-started-and-where-we-are-now)
3. [The model, explained simply](#3-the-model-explained-simply)
4. [The training data, explained simply](#4-the-training-data-explained-simply)
5. [Numbers right now](#5-numbers-right-now)
6. [Is the paperwork finished?](#6-is-the-paperwork-finished)
7. [What to do this week](#7-what-to-do-this-week)
8. [The thing that should worry you](#8-the-thing-that-should-worry-you)

---

## 1. What are we building?

A traffic light that thinks ahead.

Normal traffic lights work on a timer. Green for 30 seconds, red for 30 seconds, forever — whether
the road is empty or jammed. They were set up once, years ago, and nobody changed them.

We want to do three things instead:

1. **Watch** the intersection with one ordinary camera.
2. **Predict** how crowded each of the four roads will be *one minute from now*.
3. **Decide** the light timing using that prediction.

The important word is **predict**. Most smart traffic systems only react to the jam that has already
formed. Ours tries to see it coming.

### Why a camera and not sensors?

Rich cities bury sensors in the road that count cars. Most Indian intersections do not have them, and
installing them costs a lot. Cameras are already there, or cost a few thousand rupees.

### Why is Indian traffic a hard problem?

Because the vehicles and the behaviour are different:

- Motorcycles squeeze through gaps between cars instead of staying in lanes
- Auto-rickshaws and e-rickshaws exist here and almost nowhere in the datasets everyone else uses
- Cows on the road are normal, not an emergency
- Lane markings are treated as suggestions

A detection model trained in Europe or America has literally never seen an auto-rickshaw. It will
either miss it or call it a car.

### The four pieces

| Piece | Job | Everyday comparison |
|---|---|---|
| **YOLOv8** | Look at a photo, find and count vehicles | Your eyes |
| **MFSTNet** | Look at 5 minutes of video, predict the next minute | Your brain guessing what happens next |
| **PPO agent** | Choose the light timing | Your hand on the switch |
| **SUMO** | A traffic simulator to test in safely | A flight simulator, but for roads |

---

## 2. Where we started and where we are now

The original plan is not wrong. But almost every part of *how* we would carry it out has changed.

| | What we planned at first | What we plan now | Why |
|---|---|---|---|
| **Dataset** | Film 6 public intersections, label 12,000 photos ourselves | Combine existing free datasets + film ~2,000 photos on our own campus | Labelling 12,000 photos takes ~300 hours. And publishing photos of strangers has legal problems |
| **Model** | ResNet-50 + ViT (older version), unlock the model at epoch 30 | ResNet-50 + **DINOv2**, never unlock (use LoRA instead) | Better starting features; unlocking would just memorise |
| **Training data** | *Never explained where it comes from* | Real video, labelled automatically by YOLOv8 | This was a hole big enough to stop the project |
| **Light controller input** | 17 numbers | 16 numbers | One of them could not exist during training |
| **Webster comparison** | Mentioned, never set up | Properly configured, tested across a whole range | We were about to compare against a deliberately weak opponent |
| **Marking scheme** | One overall score | Several scores, including "only the hard cases" | One number can hide the truth |
| **Hardware** | Jetson Nano, ₹12,000–18,000 | A laptop, ₹0 | We have ₹0 |
| **Workload** | Nobody counted | ~1,200 hours of work vs ~715 hours available | We were 1.6× overbooked and did not know |
| **"What's new?"** | "New CNN-ViT fusion" | A much narrower and honest claim | Most of it was already published years ago |

**In one line:** the machine we are building is the same. The way we build, test and describe it has
changed almost completely.

---

## 3. The model, explained simply

### 3.1 What is a "backbone"?

A backbone is a large model that already knows how to look at pictures. It was trained by someone
else on millions of images. We just use it.

> **Example.** You need photographs for a school magazine. You could spend three years learning
> photography. Or you could hire a photographer who is already excellent, and just tell them what to
> shoot. We hire the photographer.

We use **two** backbones because they notice different things:

| Backbone | Notices | Example |
|---|---|---|
| **ResNet-50** (a CNN) | Small local details | "That shape with three wheels is an auto-rickshaw" |
| **DINOv2** (a ViT) | The overall layout of the scene | "The queue stretches from the signal right back to the corner" |

One is good at *what things are*. The other is good at *how the scene is arranged*. Together they see
more than either alone. Proving that is what our experiments are for.

### 3.2 Why "frozen"?

Frozen means we never change the backbone. It stays exactly as we downloaded it.

> **Example.** The photographer you hired is already excellent. You do not send them back to college.
> You just use their photos.

This has one big consequence, and it drives our biggest model decision:

**If we never train the backbone, then the *only* thing it gives us is the quality of what it sees.
So choosing which backbone to use is the single most important model choice we make.**

### 3.3 Change 1 — DINOv2 instead of the older ViT

> **Example.** Two students.
>
> **Student A** studied only to pass one exam: "look at a photo and name the animal." They became very
> good at that, and forgot everything not useful for naming animals.
>
> **Student B** studied photographs generally, without knowing what the exam would be. They had to
> remember much more, because they could not guess what would be asked.
>
> Now give both a **completely new exam about traffic**. Student B does better — not because they are
> cleverer, but because Student A threw away everything that was not about animals.

The old ViT is Student A (trained to sort images into 1000 named categories). DINOv2 is Student B
(trained without labels at all). Since we are giving it a brand-new task and cannot retrain it,
Student B is the better hire.

**Being honest:** we have not tested this on traffic images yet. It is a well-supported general
result, not something we measured. That is exactly why our experiment plan keeps the old ViT as a
comparison — so we find out instead of assuming.

> ⚠️ **One trap.** DINOv2 chops the image into 14-pixel squares, the old one used 16. So it produces
> **257** pieces where the old one gave 197. Any code with "197" written into it will break in a way
> that is hard to spot. Read the number from the config file, never type it.

### 3.4 Change 2 — LoRA instead of "unlocking at epoch 30"

The original plan said: keep the backbone frozen, then unlock it at epoch 30 so it can adjust.

The same document *also* said: unlocking will overfit, keep it frozen. **The plan told itself to do
something it expected to fail.**

**What is overfitting?**

> **Example.** You get 2,000 practice questions before an exam. If you have enough time and pen, you
> can simply memorise all 2,000 answers. You will score 100% on the practice paper and fail the real
> exam, because you learned answers instead of understanding.

Unlocking the backbone gives the model about **26 million adjustable settings** to fit roughly
**2,000 examples**. That is not learning. That is memorising the answer key.

**LoRA** is the middle path. Instead of unlocking all 26 million settings, we add about 0.3% extra —
a small set of adjustments layered on top, with the original left untouched. Enough to adapt to our
traffic, not enough to memorise.

There is a second reason too, explained in §3.6: unlocking would destroy a speed trick worth about
100× to us.

### 3.5 Change 3 — the four-identical-answers bug

**This one was a real bug in the original design, not a preference.** It is also the easiest to
understand, so it is worth reading slowly.

The design said:

1. Take the picture information and **average it all together** into one summary.
2. Feed that summary into a small predictor.
3. Run that predictor **four times** — once each for North, South, East and West.

> **Example.** You take four photos — one of each road. You put all four into a blender and press go.
> Now you have one smoothie.
>
> You look at the smoothie and ask: "How busy is the North road?" You write an answer.
> You look at the **same smoothie** and ask: "How busy is the South road?"
>
> It is the same smoothie. You are using the same rule. **You will give the same answer.** Four times.

That is exactly what the design did. Averaging everything together destroys all information about
*where* things are, and then the same predictor is asked four different questions about the same
blended input. It is guaranteed to produce four identical predictions.

**The fix — "per-lane ROI pooling":** do not blend. Cut the picture into four regions, one per road,
and let each road's prediction look only at its own region.

> Same example, fixed: keep the four photos separate. Look at the North photo to answer about North.
> Now the four answers can differ, because the four questions finally have four different inputs.

**Why this matters beyond the bug:** the model now actually *looks at the right part of the picture*.
When we later claim "the model pays attention to the queue," we can show it is true.

### 3.5b The fusion part — unchanged, but it had a hidden size problem

**First, the good news: the fusion idea is exactly what we always planned.** CNN and ViT look at the
same picture, then each asks the other questions, then a gate decides who to trust. Nothing about
that changed.

> **How the two questions work.**
>
> The CNN asks: *"I can see a three-wheeled shape here — what's the wider situation around it?"*
> The ViT asks: *"I can see a long queue — which exact vehicles make it up?"*
>
> Both questions get answered. Then the **gate** — a single number between 0 and 1 — decides how much
> of each answer to keep. Busy chaotic scene, trust the CNN more. Quiet orderly scene, trust the ViT
> more. The model learns this by itself.

**Now the problem.** When one model asks another a question, it gets back **one answer per question
it asked.**

> **Example.** You send 49 questions, you get 49 answers back. Your friend sends 257 questions, they
> get 257 answers back.
>
> Now try to average the two answer sheets together, line by line. Line 1 with line 1, line 2 with
> line 2… and at line 50 you run out. **One sheet has 49 lines, the other has 257.**

That is exactly our situation:

| Branch | How many pieces it cuts the image into |
|---|---|
| ResNet-50 | 7 × 7 = **49** |
| DINOv2 ViT | 16 × 16 + 1 = **257** |

The gate has to combine them line by line. **49 and 257 do not line up, so the gate simply cannot
run.** The code would crash on the first batch.

This was in the very first version of the plan too — back then it was 49 versus 197. Nobody noticed,
because writing "combine the two" sounds obviously fine until you check the sizes.

**The fix:** make both branches cut the picture into the *same* grid before they start talking. We
shrink the ViT's 16×16 grid down to 7×7 to match the CNN. Now both have 49 pieces, they line up, and
the gate works.

There is a second reason this fix was needed anyway: **ROI pooling** (§3.5) has to look at a
*region* of the picture. You cannot pick out a region from a plain list of 257 numbers — you need a
grid. Aligning the grids gives us that too. One fix, two problems solved.

> **Why 7×7 and not something bigger?** Because attention is expensive. Doubling the grid to 14×14
> makes this step **16 times** slower. Our laptop cannot afford it. The trade-off is that 7×7 is a
> coarse grid — if a road takes up only a small corner of the picture, it might cover just two or
> three squares, which is not much to judge from. So the grid size is a setting we can change, and
> the Week-2 test on real footage will tell us whether 7×7 is enough.

### 3.6 Change 4 — do the hard work once, not 100 times

This is not about the design. It is about speed, and it is the most useful decision in the whole
project.

Training normally works like this: show the model all the data, let it adjust slightly, repeat 100
times. Each repeat is called an **epoch**.

Every epoch, the pictures go through both backbones first. But **the backbones are frozen — they
never change.** So they produce *exactly the same output* every single time.

> **Example.** Your homework has two parts.
>
> Part 1: solve the same 1,920 sums. Same sums, every day.
> Part 2: use those answers to write an essay. The essay changes each day.
>
> You are doing Part 1 a hundred times and getting the identical answers each time. Instead: solve
> them **once**, write the answers on a card, and reuse the card every day.

We do exactly that. Run every picture through the backbones once, save the results, and reuse them.

| | Before | After |
|---|---|---|
| One epoch | Minutes | Seconds |
| Fits in our 6 GB graphics card? | **No** | Yes, comfortably |
| All 8 experiments | **60–90 hours** | A few hours |

The experiments differ only in what happens *after* the backbones — so **one saved card serves all
eight**.

> ⚠️ **The danger.** If you change the backbone, or the image size, or the way images are prepared,
> the saved card is wrong — but everything still runs and produces results that *look* perfectly
> normal. Our code refuses to load a card that does not match, and raises an error rather than a
> warning.

### 3.7 Being blunt: the model is not the impressive part

Our model has about 4.1 million trainable settings. That is small.

And every trick in it was published years ago by other people — combining a CNN and a ViT (2021),
attention flowing both ways (2019), the gate (2022). **We are not inventing these. We are applying
them to a problem nobody applied them to.**

What actually makes the project publishable is the **experiments** — carefully comparing eight
versions of the model to prove which parts genuinely help. Not the model.

The thing that would most improve our results is not a cleverer design. It is **more and better
training data.**

### 3.8 Two gaps found while writing this

**Gap 1 — we forgot the simplest possible comparison.** Our eight experiments all include the
"memory" part (the BiLSTM). So none of them answers the most obvious question a marker will ask:
*does the complicated part help at all?*

We added **Config H**: take the frozen features, average them, feed them to the simplest possible
predictor. No fusion, no memory, no attention. The absolute floor.

> If Config H scores nearly as well as the full model, then all our complexity is pointless — **and
> that is a real finding we report, not hide.**

Costs minutes now that features are cached.

**Gap 2 — we were going to run each experiment once.** Machine learning has randomness in it. Run the
same experiment twice and you get slightly different scores.

The traffic-light half of the project runs 30 times and reports a range. The model half was going to
run **once**. So if one version scored 0.82 and another 0.80, we could not say whether that gap was
real or luck.

Now: **5 runs each, report the average and the range.** Nearly free with caching, and most published
papers do not bother — so this makes us stricter than average, not weaker.

---

## 4. The training data, explained simply

### 4.1 What one training example looks like

The model's task: *look at the last 5 minutes, say how crowded each road will be in 1 minute.*

So one training example is:

- **The question:** 60 photos, taken 5 seconds apart
- **The answer:** how crowded each of the 4 roads actually was, 1 minute after the last photo

### 4.2 A worked example with a clock

This is the part that had a serious bug, so follow the clock carefully.

> Your video starts at **10:00:00**.
>
> Take a photo every 5 seconds:
> `10:00:00 · 10:00:05 · 10:00:10 · …`
>
> You need **60 photos**. The 60th one is at **10:04:55**.
>
> Why 10:04:55 and not 10:05:00? Because between 60 photos there are only **59 gaps**.
> `59 × 5 seconds = 295 seconds = 4 minutes 55 seconds.`
> **This is the mistake almost everyone makes.**
>
> Now the question: *how crowded will it be 1 minute after that last photo?*
> `10:04:55 + 60 seconds = ` **10:05:55**
>
> So one training example needs video from **10:00:00 to 10:05:55** — that is **355 seconds**, just
> under 6 minutes.

### 4.3 The bug this exposed

The original plan said: use **5-minute clips**, and take the answer from **t + 60 seconds**.

Both parts were wrong.

**Wrong thing 1 — the answer was inside the question.**

The 60 photos cover 10:00:00 to 10:04:55. The plan said take the answer at 10:01:00.

But 10:01:00 is *inside* that range. We already have a photo of it.

> **Example.** An exam where the answer is printed at the bottom of the question paper. Every student
> scores 100%. Nobody learned anything. And in the real world — where the future is genuinely unknown
> — the model would be useless.

**Wrong thing 2 — a 5-minute clip gives you nothing.**

> A 5-minute clip runs 10:00:00 to 10:05:00.
> You need to see 10:05:55.
> You never do. So this clip produces **zero** training examples.
>
> And the plan said "skip clips that are too short" — so **every single clip would have been skipped
> and the dataset would have been empty.**

**Both are now fixed:** the answer comes from 355 seconds after the start, and clips must be at least
**6 minutes** long.

### 4.4 How many examples does one video give?

We slide the 6-minute window forward 30 seconds at a time and take a new example each step.

| Video length | Training examples |
|---|---|
| 5 minutes | **0** |
| 6 minutes | 1 |
| 12 minutes | 13 |
| 1 hour | 109 |

**What this means for filming:** do not shoot lots of short clips. Shoot **one long continuous
recording**. A phone that stops and restarts every 2 minutes gives you a fine photo collection and
**zero** usable training examples.

### 4.5 Where the answers come from

We do not label these by hand. That would take forever. Instead:

1. Run YOLOv8 over the video. It counts vehicles in each road, in every frame.
2. Look at the count 355 seconds in.
3. Apply a simple rule:

| Vehicles in that road | Label |
|---|---|
| Under 5 | **LOW** |
| 5 to 15 | **MEDIUM** |
| Over 15 | **HIGH** |

> **Example.** At 10:05:55 the North road has 9 vehicles → **MEDIUM**. South has 22 → **HIGH**. East
> has 2 → **LOW**. West has 7 → **MEDIUM**.
>
> So this example's answer is: `[MEDIUM, HIGH, LOW, MEDIUM]`.

**One refinement.** Counting is jumpy — YOLOv8 might miss a vehicle behind a bus for one frame. So we
smooth over 3 frames and take the **middle** value, not the average.

> **Example.** Three counts: `8, 8, 2` (a bad frame in the middle).
> Average = 6. **Middle value = 8.** The middle value ignores the mistake. The average does not.

### 4.6 Why the split matters so much

We divide our data three ways: **practice** (train), **check** (val), **final exam** (test). The final
exam data must never be seen during learning.

Here is the trap. Two examples starting 30 seconds apart share **54 of their 60 photos** — they are
almost the same thing.

> **Example.** If one goes into practice and the near-identical other goes into the final exam, then
> the exam is 90% questions you already practised. You score brilliantly and have learned nothing.

**So we split by video, never by example.** All examples from one video go to the same place. Our code
checks this and **stops with an error** if it is ever violated — not a warning in a log nobody reads.

### 4.7 Why we check the final exam by hand

Our answers come from YOLOv8. Some of our comparison methods *also* use YOLOv8's counts.

> **Example.** You and your friend both copy from the same wrong textbook. The teacher marks using
> that same textbook. You both score full marks. A student who actually understood the topic, and
> wrote something different, gets marked **wrong**.
>
> That is our situation. The count-based methods share YOLOv8's mistakes, so those mistakes get
> marked correct. Our model looks at pixels instead, so its independent mistakes get marked wrong.
> **The comparison is rigged against us.**

**The fix:** for the final exam only, ~150 examples get counted **by a human**. Two people count 25 of
them independently, so we also learn how much humans disagree with each other.

Practice and check data stay automatic — volume matters more there than perfection.

### 4.8 Being blunt: the data is the weakest part

Three things we do not know, and have not measured:

**1. How much will we have?** We have filmed nothing yet.

**2. How good are the answers?** They come from YOLOv8, which is worst exactly where it matters most.
HIGH means over 15 vehicles — which means vehicles hidden behind each other — which is exactly when
counting fails.

**3. Is the task even learnable?** This is the frightening one.

> **Example.** Suppose you live somewhere the weather never changes. You build a weather predictor.
> Your friend builds one too — theirs just says *"tomorrow is the same as today"*.
>
> Their useless predictor is right 95% of the time. Yours cannot beat it. Not because yours is bad —
> because the question was too easy.

If traffic almost never changes category within 60 seconds, the same thing happens: a predictor that
just says "same as now" wins, and **no model can be told apart from any other**.

**We can find this out in one hour**, with any traffic video, before building anything. It is the
single most valuable hour available to us right now.

---

## 5. Numbers right now

| | |
|---|---|
| Week | 2 of 20 |
| Documents written | 43 |
| Design decisions recorded | 12 |
| Mistakes found and fixed | 15 |
| Working code | 1,339 lines |
| Tests passing | 44 |
| Video filmed | **0** |
| Models trained | **0** |

---

## 6. Is the paperwork finished?

**Yes. More than finished. Stop.**

43 documents is more than most master's theses. And the useful findings are drying up:

| Round of review | What it found |
|---|---|
| 1st | No training data plan existed at all. **Huge** |
| 3rd | The answer was inside the question. **Huge** |
| 4th | Its headline finding turned out to be **wrong** and was withdrawn |
| 5th | Two real improvements — but improvements, not rescues |

**Round 4 producing a wrong answer is the signal.** Thinking without building eventually starts
generating noise instead of insight.

**Should we write more documents before starting?** No. The remaining design documents are scheduled
for Week 5 on purpose. **You design better after you have built something.** The best design document
we have is the one written after actually working through the pipeline in detail.

---

## 7. What to do this week

| # | Do this | Time |
|---|---|---|
| 1 | Give the scope-change request to your guide | 20 min |
| 2 | Install Python 3.11, then `pip install -r requirements.txt` | 30 min |
| 3 | **Run the counting test on any traffic video** | 1 hour |
| 4 | Each person explains their own part to the group | 90 min |
| 5 | Start writing the detector code | Rest of week |

**Item 3 is the most valuable hour of your semester.** It answers two questions that could change the
whole project:

- Does "over 15 vehicles" ever actually happen? If not, one of our three categories is empty.
- Does traffic ever change category in 60 seconds? If not, the task is too easy to be interesting
  (§4.8).

Finding this out now costs an edit to one number. Finding it out in Week 12 costs the experiments.

---

## 8. The thing that should worry you

**You have never run this system. Not one photo detected. Not one model trained. Not one simulation.**

Every mistake found so far was found by *reading*. That was worth doing — some of those mistakes
would have cost weeks.

But the mistakes that actually kill projects are the ones that only appear when code runs. And right
now you have **no evidence that any of this works.** Week 2 of 20.

**Second worry:** 43 documents that nobody on the team has read. They were written quickly, in one
voice. Until your team actually understands them, they are not an asset — they are a false sense of
safety. Everyone will build something slightly different and nobody will notice until Week 17.

That is what item 4 above is for.

---

**Build something this week. Even something small. Even something that fails.**
