# Usability Evaluation Kit

Use this kit to test the system with real nurses (3 to 5 participants is enough for a formative study).
It gives you task scripts, a record sheet, and the System Usability Scale (SUS) questionnaire.
Enter the answers in `data/sus_responses.csv` and run `python -m scripts.sus_score` to get the results for Chapter Five.

**Ethics:** use only the synthetic scenarios below. Do not enter any real patient information.
Tell participants the session is voluntary, that the system is being tested and not them, and that their answers are anonymous (use codes P1, P2, and so on).

---

## 1. Before the session

1. Start the server: `uvicorn app.main:app --reload --port 8081`.
2. Create a nurse account for each participant (Users page, or `python -m scripts.create_user`).
3. Give the participant a 2-minute introduction: what telephone triage is, and that the questions run from most to least serious.
4. Do not show them how to use the screens. Watching where they hesitate is the point.

## 2. Tasks

Read each scenario aloud as if you are the caller. Note the time taken, whether the task was completed, any errors, and the final disposition.

| Task | Scenario read to the participant | Expected result |
|---|---|---|
| T1 | Sign in, then start a new consultation for a 58-year-old man with chest pain. He agrees to the call being recorded. | Reaches question 1 of the Chest Pain protocol |
| T2 | (Continue) "The pain is heavy and has lasted about 20 minutes. I'm sweating." Answer the questions from what the caller says. | **Emergency** at question 3 |
| T3 | New call: mother of a 3-year-old with fever since yesterday. The child is playing and drinking, but is breathing fast. Not tested for malaria. Answer one question wrongly on purpose, then use Back to correct it. | **Urgent** at question 7 |
| T4 | New call: 30-year-old woman with chest-wall pain after carrying heavy bags. The system will say Routine. Override it to Urgent, because she sounds very anxious and lives alone. | Saved as **Urgent**, overridden, with a reason |
| T5 | Find the consultation from task T2 and open its full record. | Record of the Emergency call opened |

## 3. Record sheet (one per participant)

Participant code: ______   Role: ______   Years of nursing: ______   Date: ______

| Task | Completed (Y/N) | Time (seconds) | Errors | Disposition shown | Notes |
|---|---|---|---|---|---|
| T1 | | | | | |
| T2 | | | | | |
| T3 | | | | | |
| T4 | | | | | |
| T5 | | | | | |

## 4. System Usability Scale (SUS)

Ask the participant to answer straight after the tasks. Each item is scored 1 (strongly disagree) to 5 (strongly agree).

| # | Statement | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|---|
| 1 | I think that I would like to use this system frequently. | | | | | |
| 2 | I found the system unnecessarily complex. | | | | | |
| 3 | I thought the system was easy to use. | | | | | |
| 4 | I think that I would need the support of a technical person to be able to use this system. | | | | | |
| 5 | I found the various functions in this system were well integrated. | | | | | |
| 6 | I thought there was too much inconsistency in this system. | | | | | |
| 7 | I would imagine that most people would learn to use this system very quickly. | | | | | |
| 8 | I found the system very cumbersome to use. | | | | | |
| 9 | I felt very confident using the system. | | | | | |
| 10 | I needed to learn a lot of things before I could get going with this system. | | | | | |

The SUS was developed by John Brooke (1996) and is free to use.

**Two open questions**

1. What did you find most useful?
2. What would you change?

## 5. Scoring

Enter one row per participant in `data/sus_responses.csv`, then run:

```powershell
python -m scripts.sus_score
```

The script converts each participant's answers to a score from 0 to 100, and reports the mean, the range, and a plain-language rating. A score of 68 is the commonly cited average; above 80 is considered excellent.
