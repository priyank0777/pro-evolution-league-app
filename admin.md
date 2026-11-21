# Commissioner Admin Playbook (`admin.md`)

This guide explains every section, toggle, and button on the **Admin Control Center** page — what each control does, when to use it, and what to watch out for during a live 2v2 eFootball League tournament.

---

## Quick Start: The Full Tournament Lifecycle (Order of Operations)

Follow these steps in order from start to finish of a season:

1. **Phase 1 — Registration:** Turn **Registration Phase Open = ON**. Players sign up with their Name and eFootball Username.
2. **Clean Up Users:** Check **Section 5 (User Management)** and delete any duplicate or fake accounts. Make sure you have an **even number of non-admin players (minimum 4)**.
3. **Phase 2 — Partner Preferences:** Turn **Registration Phase Open = OFF** and **Partner Preference Phase Open = ON**. Players log in and rank all other players from `#1` (most preferred) to last.
4. **Phase 3 — Run Matchmaking:** In **Section 2 → Step A**, click **Run Partner Matchmaking & Pair Teams**. This automatically closes Registration & Preferences, pairs all players into 2v2 teams, and opens **Team Setup**.
5. **Phase 4 — Team Setup:** Players visit **My Team** to choose their official Team Name and Team Captain (Leader).
6. **Phase 5 — Generate Fixtures & Go Live:** Turn **Team Setup Phase Open = OFF**, then in **Section 2 → Step B**, choose your **Format Multiplier** (e.g., `2x` Home & Away) and **Matches / Team / Week** (e.g., `2`), and click **Generate Entire Season Fixtures**. The season goes live at Matchweek 1.
7. **Weekly Season Loop (Every Week):**
   - Home teams play and submit scores + player stats.
   - Away teams log in to **Accept** or **Dispute** submitted scores before Friday midnight.
   - Resolve any flagged disputes in **Section 3**.
   - After Friday midnight (or once all matches in the week are finished), run **Check Expired Deadlines** (or **Force 0-0 Unplayed**) and increment **Active Matchweek** (`Set MW`) to the next week.

> **Tip:** Use the **↻ Refresh Admin Panel** button at the top right of the Admin page at any time to pull fresh disputes, scores, and user registrations without reloading the browser.

---

## Section 1: System Phase & Stat Tracking Toggles

Clicking **ON / OFF** next to any toggle takes effect immediately across the entire app and is saved in the database.

### Phase Toggles

| Toggle | What `ON` Does | What `OFF` Does | When to Use |
| :--- | :--- | :--- | :--- |
| **1. Registration Phase Open** | Allows new players to create accounts on the *Player Sign Up* tab. | Blocks new sign-ups and shows a "Registration closed" notice. | Keep `ON` only during sign-ups; turn `OFF` before preferences/matchmaking. |
| **2. Partner Preference Phase Open** | Shows the **Partner Preferences** tab to non-admin players and lets them save partner rankings. | Hides the tab and locks preference rankings. | Turn `ON` after registration closes so everyone can rank partners before matchmaking. |
| **3. Team Setup Phase Open** | Allows paired players on the **My Team** page to edit their Team Name and Team Captain. | Locks Team Name and Captain edits for players (Admin can still view). | Automatically turns `ON` after matchmaking; turn `OFF` once the season starts so teams can't keep renaming themselves mid-season. |
| **4. Live Season Active** | Enables Home teams to submit match scores and stats. | Blocks score submissions (useful if you want to pause the league temporarily). | Automatically turns `ON` when fixtures are generated; turn `OFF` only to freeze/pause the season. |

> **Banner Priority Note:** The top status banner checks phases in order (`Registration` → `Preferences` → `Team Setup` → `Live Season`). Make sure earlier phases are turned `OFF` when the season is live so the banner displays the active Matchweek accurately.

### Stat Tracking Toggles

| Toggle | What It Controls |
| :--- | :--- |
| **Track Player Total Points (1000s)** | Enables/disables the individual match points field on score submission, match cards, and the MVP Leaderboard. |
| **Track Player Goals** | Enables/disables individual player goals on score submission, match cards, and the MVP Leaderboard. |
| **Track Player Assists** | Enables/disables individual player assists on score submission, match cards, and the MVP Leaderboard. |

- **When to set these:** Set them **before Matchweek 1 begins** so every match records the same stat categories. If you turn a stat `OFF`, new submissions will store `0` for that stat and hide its column on the MVP Leaderboard.

---

## Section 2: Tournament Engine & Matchweek Controls

### Step A: 2v2 Matchmaking Algorithm
- **What it does:** Pairs all non-admin registered players into 2v2 teams using their mutual preference rankings (Irving's Stable Roommates algorithm, with automatic fallback to Minimum-Weight Blossom Matching so it always finds the fairest global pairing).
- **Requirements:**
  - At least **4 non-admin players**.
  - Must be an **even number** of non-admin players (the badge shows `Even ✓` or `Odd ⚠️`).
- **Automatic side effects:**
  - **Deletes all existing teams and matches** before creating the new teams.
  - Automatically sets `Registration = OFF`, `Preferences = OFF`, and `Team Setup = ON`.
- **When to use:** Once at the end of Phase 2 (after players have finished ranking partners).
- **Warning:** **Never click this after a season has started** unless you intentionally want to wipe all teams, fixtures, and scores and restart from scratch.

---

### Step B: Season Fixture Generator
- **Controls:**
  - **Format Multiplier (`1x` – `4x`):** How many times every team plays every other team (`1x` = Single Round-Robin, `2x` = Home & Away, `3x` = Triple, `4x` = Quadruple). Home/Away flips automatically on each cycle.
  - **Matches / Team / Week (`1` – `10`):** How many matches each team is scheduled to play per week (e.g., `2` = every team plays 2 matches every week until changed).
- **What it does:**
  - **Deletes all existing matches and player stats**, then generates a fresh full-season schedule with Friday 23:59:59 UTC deadlines spaced 7 days apart.
  - Sets `Active Matchweek = 1` and `Live Season = ON`, and saves both the Multiplier and Matches/Week settings.
- **When to use:** Once at the start of the season, right after teams have finished naming themselves in Phase 4.
- **Warning:** **Do not click this mid-season** — it wipes all played matches and stats. To change the weekly pace mid-season without losing data, use **Step C → Set Pace** instead.

---

### Step C: Weekly Cycle & Friday Auto-Draws

#### 1. Active Matchweek (`Set MW`)
- **What it does:** Controls which matchweek is shown as "Current Week" on the phase banner, All Fixtures, and on players' **Dashboard (`My Active Matchweek Fixtures`)**.
- **When to use:** At the start of each new week (e.g., after Friday midnight or once the current week's games finish), change `1` → `2` → `3` and click **Set MW**.

#### 2. Matches Per Team Per Week (`Set Pace`)
- **What it does:** Updates the tournament's weekly pace (`1`–`10` matches per team per week) and **automatically reschedules all remaining unplayed matchweeks** without deleting any data.
- **How mid-season changes work:**
  - **Completed matchweeks** (before Active Matchweek) are **never touched**.
  - **In-progress matchweeks** (any week that already has at least one `Submitted`, `Accepted`, `Disputed`, or `Auto-Drawn` match) are **kept intact** so teams aren't disrupted mid-week.
  - **All remaining unplayed matchweeks** are repacked to the new pace with updated Friday deadlines.
  - **Example:** You start the tournament at `2` matches/week. After Matchweek 1 is done, you set `Active Matchweek = 2` and change `Matches Per Team Per Week` to `1` and click **Set Pace**. Matchweek 1 keeps its 2 matches per team, and Matchweek 2 onward becomes 1 match per team per week for the rest of the tournament (until you change it again).
- **Persistence:** Saved in the database, so it survives server restarts and Render sleep/wake cycles.

#### 3. Check Expired Deadlines
- **What it does:** Scans all `Pending` matches whose Friday midnight deadline has already passed and converts them to **`0 - 0` Auto-Drawn** (1 point each).
- **Note:** This also runs automatically every 5 minutes in the background and whenever fixtures/standings are loaded. Use this button if you want to trigger a manual check immediately.

#### 4. Force 0-0 Unplayed in MW X
- **What it does:** Immediately assigns `0 - 0` **Auto-Drawn** to all remaining `Pending` matches up to Matchweek `X`, **even if the Friday deadline hasn't passed yet**.
- **When to use:** When you want to manually close out a matchweek early (for example, if both teams agreed they can't play or missed your custom cutoff) before advancing to the next matchweek.

---

## Section 3: Flagged Match Disputes

- **How matches arrive here:** After a Home team submits a score (`Submitted`), the Away team clicks **Dispute Result (Flag Admin)** if the score or individual player stats are wrong.
- **What happens while a match is `Disputed`:**
  - Neither team can edit or accept it.
  - It does **not** count in the League Standings or MVP Leaderboard.
- **How to resolve a dispute:**
  1. Check proof of the real result (e.g., end-of-match screenshots from the teams).
  2. Click **Resolve & Override Score** on the disputed match.
  3. Enter the verified Home Score, Away Score, and all 4 players' stats.
  4. Make sure **Match Status** is set to **Accepted (Official Final Result)** and click **Save Match Result**.
  5. The match disappears from the Disputes queue and immediately updates the Standings and MVP Leaderboard.

---

## Section 4: Retroactive Match & Player Stat Override

- **What it does:** Lets the Admin edit **any match from any matchweek** at any time — including fixing typos in already-accepted matches, overturning an Auto-Draw if teams played late with permission, or manually entering scores if a Home team couldn't submit.
- **Filter:** Use the Matchweek dropdown on the right to narrow down to a specific week.
- **Match Statuses Explained:**

| Status | Counts in Standings? | Counts in MVP Leaderboard? | Meaning & When to Use |
| :--- | :---: | :---: | :--- |
| **Accepted** | Yes | Yes | Official final result. Use this when finalizing or correcting a played match. |
| **Submitted** | No | No | Score entered by Home team, waiting for Away team to Accept or Dispute. |
| **Disputed** | No | No | Flagged for Admin review; appears in Section 3. |
| **Auto-Drawn** | Yes (`0-0`, 1 pt each) | No | Unplayed match that expired past the Friday deadline. |
| **Pending** | No | No | Unplayed match; Home team can submit a score. *(Note: Overriding a match back to Pending currently keeps whatever numbers are in the score boxes visually until the Home team submits a new score, though it will not count in Standings.)* |

---

## Section 5: Registered Players & User Management

- **What it does:** Lists every registered account (Admins and Players), their eFootball username, role, and assigned team.
- **Delete button:** Permanently deletes a player account. (Admin accounts are protected and cannot be deleted.)
- **When to use:** **Before running matchmaking** (during Phase 1 or Phase 2) to remove duplicate sign-ups, test accounts, or players who dropped out before teams are formed.
- **Important Warning:** **Do not delete a player who is already assigned to a team during a live season.** Deleting a paired player will cascade-delete their team and all of that team's matches from the database.

---

## Admin Do's & Don'ts Checklist

- **DO** verify an even number of players in Section 5 before running matchmaking.
- **DO** turn off `Registration`, `Preferences`, and `Team Setup` once the season is live.
- **DO** use **Step C → Set Pace** to change matches per week mid-season (never Step B).
- **DO** use **↻ Refresh Admin Panel** to check for newly submitted scores or disputes without losing your place.
- **DON'T** click *Run Partner Matchmaking* or *Generate Entire Season Fixtures* after Matchweek 1 has started unless you want a full season reset.
- **DON'T** delete a user who already belongs to an active team.

