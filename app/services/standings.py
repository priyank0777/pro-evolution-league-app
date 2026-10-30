from collections import defaultdict
from functools import cmp_to_key
from typing import Dict, List, Set
from sqlalchemy.orm import Session

from app.models import Match, MatchStat, MatchStatus, Team, User
from app.schemas import PlayerLeaderboardRowOut, StandingRowOut

COUNTED_MATCH_STATUSES = {MatchStatus.ACCEPTED, MatchStatus.AUTO_DRAWN}


def calculate_standings(db: Session) -> List[StandingRowOut]:
    """
    Compute the Premier League-style standings table across all official matches
    (ACCEPTED and AUTO_DRAWN).
    Standard Rules:
    - 3 points for Win, 1 point for Draw, 0 points for Loss
    - Tie-breakers:
      1. Points (descending)
      2. Goal Difference (GD, descending)
      3. Head-to-Head (Points, then GD, then GF in matches strictly between the tied teams)
      4. Overall Goals For (GF, descending)
      5. Team Name (ascending)
    """
    teams = db.query(Team).all()
    official_matches = (
        db.query(Match)
        .filter(Match.status.in_(COUNTED_MATCH_STATUSES))
        .all()
    )

    stats: Dict[int, dict] = {}
    for t in teams:
        leader_name = t.leader.name if t.leader else None
        members = [
            f"{t.player1.name} (@{t.player1.efootball_username})",
            f"{t.player2.name} (@{t.player2.efootball_username})",
        ]
        stats[t.id] = {
            "team_id": t.id,
            "team_name": t.name,
            "leader_name": leader_name,
            "members": members,
            "played": 0,
            "won": 0,
            "drawn": 0,
            "lost": 0,
            "goals_for": 0,
            "goals_against": 0,
            "goal_difference": 0,
            "points": 0,
        }

    for m in official_matches:
        if m.home_score is None or m.away_score is None:
            continue
        if m.home_team_id not in stats or m.away_team_id not in stats:
            continue

        h = stats[m.home_team_id]
        a = stats[m.away_team_id]
        hs, as_ = m.home_score, m.away_score

        h["played"] += 1
        a["played"] += 1
        h["goals_for"] += hs
        h["goals_against"] += as_
        a["goals_for"] += as_
        a["goals_against"] += hs

        if hs > as_:
            h["won"] += 1
            h["points"] += 3
            a["lost"] += 1
        elif hs < as_:
            a["won"] += 1
            a["points"] += 3
            h["lost"] += 1
        else:
            h["drawn"] += 1
            a["drawn"] += 1
            h["points"] += 1
            a["points"] += 1

    for row in stats.values():
        row["goal_difference"] = row["goals_for"] - row["goals_against"]

    # Group teams by (points, goal_difference) to compute mini-league Head-to-Head tie-breakers
    buckets: Dict[tuple[int, int], Set[int]] = defaultdict(set)
    for tid, row in stats.items():
        buckets[(row["points"], row["goal_difference"])].add(tid)

    h2h_metrics: Dict[int, tuple[int, int, int]] = {
        tid: (0, 0, 0) for tid in stats
    }

    for tied_group in buckets.values():
        if len(tied_group) <= 1:
            continue
        mini_pts: Dict[int, int] = defaultdict(int)
        mini_gf: Dict[int, int] = defaultdict(int)
        mini_ga: Dict[int, int] = defaultdict(int)

        for m in official_matches:
            if (
                m.home_team_id in tied_group
                and m.away_team_id in tied_group
                and m.home_score is not None
                and m.away_score is not None
            ):
                hs, as_ = m.home_score, m.away_score
                mini_gf[m.home_team_id] += hs
                mini_ga[m.home_team_id] += as_
                mini_gf[m.away_team_id] += as_
                mini_ga[m.away_team_id] += hs
                if hs > as_:
                    mini_pts[m.home_team_id] += 3
                elif hs < as_:
                    mini_pts[m.away_team_id] += 3
                else:
                    mini_pts[m.home_team_id] += 1
                    mini_pts[m.away_team_id] += 1

        for tid in tied_group:
            h2h_metrics[tid] = (
                mini_pts[tid],
                mini_gf[tid] - mini_ga[tid],
                mini_gf[tid],
            )

    def compare_rows(r1: dict, r2: dict) -> int:
        # 1. Points descending
        if r1["points"] != r2["points"]:
            return -1 if r1["points"] > r2["points"] else 1
        # 2. Goal Difference descending
        if r1["goal_difference"] != r2["goal_difference"]:
            return -1 if r1["goal_difference"] > r2["goal_difference"] else 1
        # 3. Head-to-Head among tied group (H2H Points, H2H GD, H2H GF)
        h1 = h2h_metrics[r1["team_id"]]
        h2 = h2h_metrics[r2["team_id"]]
        if h1 != h2:
            return -1 if h1 > h2 else 1
        # 4. Overall Goals For descending
        if r1["goals_for"] != r2["goals_for"]:
            return -1 if r1["goals_for"] > r2["goals_for"] else 1
        # 5. Alphabetical Team Name
        return -1 if r1["team_name"].lower() < r2["team_name"].lower() else 1

    sorted_rows = sorted(stats.values(), key=cmp_to_key(compare_rows))

    return [
        StandingRowOut(
            position=idx,
            **row,
        )
        for idx, row in enumerate(sorted_rows, start=1)
    ]


def calculate_mvp_leaderboard(db: Session) -> List[PlayerLeaderboardRowOut]:
    """
    Aggregate individual human player performances (Total Points, Goals, Assists)
    across all ACCEPTED matches to produce the MVP Leaderboard.
    """
    players = (
        db.query(User)
        .filter(User.is_admin == False)  # noqa: E712
        .order_by(User.id.asc())
        .all()
    )
    teams = db.query(Team).all()
    user_team_map: Dict[int, str] = {}
    for t in teams:
        user_team_map[t.player1_id] = t.name
        user_team_map[t.player2_id] = t.name

    accepted_stats = (
        db.query(MatchStat)
        .join(Match, MatchStat.match_id == Match.id)
        .filter(Match.status == MatchStatus.ACCEPTED)
        .all()
    )

    agg: Dict[int, dict] = {
        p.id: {
            "user_id": p.id,
            "name": p.name,
            "efootball_username": p.efootball_username,
            "team_name": user_team_map.get(p.id),
            "matches_played": 0,
            "total_points": 0,
            "goals": 0,
            "assists": 0,
        }
        for p in players
    }

    for st in accepted_stats:
        if st.user_id in agg:
            entry = agg[st.user_id]
            entry["matches_played"] += 1
            entry["total_points"] += st.total_points
            entry["goals"] += st.goals
            entry["assists"] += st.assists

    rows = list(agg.values())
    rows.sort(
        key=lambda r: (
            -r["total_points"],
            -r["goals"],
            -r["assists"],
            r["name"].lower(),
        )
    )

    result: List[PlayerLeaderboardRowOut] = []
    for idx, r in enumerate(rows, start=1):
        mp = r["matches_played"]
        avg_pts = round(r["total_points"] / mp, 1) if mp > 0 else 0.0
        result.append(
            PlayerLeaderboardRowOut(
                rank=idx,
                avg_points=avg_pts,
                **r,
            )
        )
    return result

