"""Parse raw Cricsheet IPL JSON files into one ball-by-ball table.

Run from the repo root:
    python src/parse_matches.py

Reads : data/raw/ipl/*.json
Writes: data/processed/ball_by_ball.csv

One row per delivery. The match state (runs, wickets, balls) is recorded
AFTER that delivery. `batting_team_won` is the label: 1 if the team batting
in that innings went on to win the match, else 0.
"""
import json
from collections import Counter
from pathlib import Path

import pandas as pd

RAW_DIR = Path("data/raw/ipl")
OUT_FILE = Path("data/processed/ball_by_ball.csv")

# Wicket "kinds" that are not real dismissals
NOT_A_DISMISSAL = {"retired hurt", "retired not out"}


def parse_match(path):
    """Return (rows, skip_reason). rows = list of dicts, one per delivery."""
    with open(path, encoding="utf-8") as f:
        match = json.load(f)

    info = match["info"]
    winner = info.get("outcome", {}).get("winner")
    if winner is None:
        return [], "no winner (no result / tie)"

    date = info["dates"][0]
    rows = []

    for innings_no, innings in enumerate(match["innings"], start=1):
        if innings.get("super_over"):
            continue  # super overs are a different situation, skip them

        batting_team = innings["team"]
        bowling_team = next(t for t in info["teams"] if t != batting_team)
        target = innings.get("target", {})  # only the chasing side has this

        runs = wickets = legal_balls = 0
        for over in innings["overs"]:
            for ball_in_over, d in enumerate(over["deliveries"], start=1):
                extras = d.get("extras", {})
                is_legal = not ("wides" in extras or "noballs" in extras)

                runs += d["runs"]["total"]
                wickets += sum(
                    1 for w in d.get("wickets", [])
                    if w["kind"] not in NOT_A_DISMISSAL
                )
                legal_balls += int(is_legal)

                rows.append({
                    "match_id": path.stem,
                    "date": date,
                    "year": int(date[:4]),
                    "venue": info.get("venue"),
                    "city": info.get("city"),
                    "innings": innings_no,
                    "batting_team": batting_team,
                    "bowling_team": bowling_team,
                    "over": over["over"],
                    "ball_in_over": ball_in_over,
                    "is_legal": int(is_legal),
                    "runs_on_ball": d["runs"]["total"],
                    "runs_so_far": runs,
                    "wickets_so_far": wickets,
                    "legal_balls_bowled": legal_balls,
                    "target_runs": target.get("runs"),
                    "target_overs": target.get("overs"),
                    "winner": winner,
                    "batting_team_won": int(batting_team == winner),
                })
    return rows, None


def main():
    files = sorted(RAW_DIR.glob("*.json"))
    all_rows, skipped = [], Counter()

    for path in files:
        rows, reason = parse_match(path)
        if reason:
            skipped[reason] += 1
        all_rows.extend(rows)

    df = pd.DataFrame(all_rows).sort_values(
        ["date", "match_id", "innings", "legal_balls_bowled"], kind="stable"
    )
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_FILE, index=False)

    print(f"JSON files read : {len(files)}")
    print(f"Matches kept    : {df['match_id'].nunique()}")
    print(f"Skipped         : {dict(skipped)}")
    print(f"Rows written    : {len(df)} -> {OUT_FILE}")


if __name__ == "__main__":
    main()
