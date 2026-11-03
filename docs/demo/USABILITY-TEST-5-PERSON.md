# Five-person dashboard test: facilitator sheet

**Purpose:** find out whether someone with no traffic or project background reads the Live page
correctly. Five people can reveal problems. They cannot prove the page works, so report it as a small
formative test, never as statistical validation.

**Who:** five adults outside the project team with no traffic engineering background. Ask each person's
agreement first. Record no names, only P1 to P5.

**Time:** about 15 minutes each. One facilitator, who does not explain or hint.

**Show only the Live page, in Operator view.** Reload it for each person, which returns it to Operator. Do not show Analyze a video or Results: the footage licence and the signal
study are waiting on the guide.

**Rehearse once first.** This sheet has not been run. Confirm that each state below appears, and write
down the exact steps that produced it.

## The four states

Use the fixture runner (D36), so every person sees the same four states in the same order. Before
each person, start it fresh:

```
python scripts/ui_fixture.py --state missing_count
```

Open the address it prints. To move to the next state, type its name into the runner's window and
press Enter: the page stays open and changes within a few seconds. After the fourth state, type `quit`.

| State | Type into the runner | The banner should say |
|---|---|---|
| A. Missing | nothing: it starts here | "Only the congestion level forecast is arriving" |
| B. Normal | `normal` | "Updates are arriving from a recording" |
| C. Stale | `stale_edge` | "No recent updates" |
| D. Server down | `server_down` | "Cannot reach the server" |

The data is made up for testing the page, and the badge says so: `Replay · TEST_FIXTURE_<state>`.
If a state shows something else, record what it showed and continue. That is a finding too.

## What to say

> "This page belongs to a traffic monitoring system. Today's session uses test data rather than a live
> camera. Please describe what you understand from the information displayed on the page. I am testing
> the page, not you. I will ask three questions several times. Say 'I don't know' whenever that is your
> honest answer. I can't help you."

## Three questions, in each state

Start timing when you finish asking. Stop at the person's answer, or at 60 seconds.

1. **Is the system reporting traffic right now?**
2. **Can you trust this information as current?**
3. **Does this system change the traffic lights?**

## Correct answers

| State | Q1 Reporting now? | Q2 Current? | Q3 Changes the lights? |
|---|---|---|---|
| A. Missing | Partly, one forecast only | Only the one arriving | No |
| B. Normal | Yes | Yes | No |
| C. Stale | No | No, it is old | No |
| D. Server down | Cannot tell | No | No, and the page cannot say more |

Mark an answer correct only if the person reaches it from the page. "I don't know" counts as not correct.
Write down the person's own words.

## Record sheet

Copy once per person. **Fill this in only from a real session. Never estimate or complete a blank later.**

Person: ____  Date: ____  Opened the walkthrough? Y / N

| State | Q1 words | OK? | Sec | Q2 words | OK? | Sec | Q3 words | OK? | Sec |
|---|---|---|---|---|---|---|---|---|---|
| A | | | | | | | | | |
| B | | | | | | | | | |
| C | | | | | | | | | |
| D | | | | | | | | | |

After all four states, ask: **"What does HIGH mean on this page?"**

Their words: ______________________________

**Any wrong belief that could matter on a real road, especially "yes, it changes the lights":**
______________________________

## How to report

- Give counts out of five for each state and question, and quote people's words. No percentages.
- Fix only what the test shows is misunderstood. Do not change meanings or numbers to get better answers.
- If anything changes, say the five sessions tested the earlier version.
- Note that testers were chosen by convenience, and name the page's commit and the fixture states used.
