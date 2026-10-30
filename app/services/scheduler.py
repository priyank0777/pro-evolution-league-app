from datetime import datetime, timedelta, timezone
from typing import List, Optional
from sqlalchemy.orm import Session

from app.models import Match, MatchStat, MatchStatus, Team


def compute_next_friday_midnight(reference_dt: Optional[datetime] = None) -> datetime:
    """
    Calculate the upcoming Friday 23:59:59 UTC deadline for Matchweek 1.
    A matchweek runs Friday to Friday (inclusive).
    """
    now = reference_dt or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    # weekday(): Monday=0 ... Friday=4, Saturday=5, Sunday=6
    days_until_friday = (4 - now.weekday()) % 7
    if days_until_friday == 0:
        # If generated on a Friday, Matchweek 1 runs from today until next Friday midnight
        days_until_friday = 7

    first_friday = (now + timedelta(days=days_until_friday)).replace(
        hour=23, minute=59, second=59, microsecond=0
    )
    return first_friday


def generate_round_robin_fixtures(
    db: Session,
    multiplier: int = 2,
    start_friday_deadline: Optional[datetime] = None,
) -> List[Match]:
    """
    Generate the entire season's fixtures using the Circle Method (Berger tables).
    - multiplier = 1: single round-robin (every team plays every other team once)
    - multiplier = 2: double round-robin (home & away)
    - multiplier = k: k passes, flipping home/away on each subsequent cycle.
    """
    teams = db.query(Team).order_by(Team.id.asc()).all()
    if len(teams) < 2:
        raise ValueError("At least 2 teams are required to generate tournament fixtures.")

    # Clear existing matches and match stats before generating a fresh season
    db.query(MatchStat).delete()
    db.query(Match).delete()
    db.flush()

    team_ids: List[Optional[int]] = [t.id for t in teams]
    if len(team_ids) % 2 != 0:
        team_ids.append(None)  # Dummy BYE slot if an odd number of teams exists

    n = len(team_ids)
    rounds_per_cycle = n - 1
    half = n // 2

    base_cycle_rounds: List[List[tuple[int, int]]] = []
    rotation = list(team_ids)

    for round_idx in range(rounds_per_cycle):
        round_pairings: List[tuple[int, int]] = []
        for i in range(half):
            t1 = rotation[i]
            t2 = rotation[n - 1 - i]
            if t1 is not None and t2 is not None:
                # Alternate home/away for the fixed pivot team and even/odd indices
                if (i == 0 and round_idx % 2 == 1) or (i > 0 and (i + round_idx) % 2 == 1):
                    round_pairings.append((t2, t1))
                else:
                    round_pairings.append((t1, t2))
        base_cycle_rounds.append(round_pairings)

        # Rotate all elements except the first fixed pivot element
        rotation = [rotation[0]] + [rotation[-1]] + rotation[1:-1]

    mw1_deadline = start_friday_deadline or compute_next_friday_midnight()
    created_matches: List[Match] = []
    current_mw = 1

    for cycle in range(multiplier):
        flip_home_away = cycle % 2 == 1
        for round_pairings in base_cycle_rounds:
            mw_deadline = mw1_deadline + timedelta(days=7 * (current_mw - 1))
            for home_id, away_id in round_pairings:
                actual_home = away_id if flip_home_away else home_id
                actual_away = home_id if flip_home_away else away_id
                match = Match(
                    matchweek=current_mw,
                    home_team_id=actual_home,
                    away_team_id=actual_away,
                    home_score=None,
                    away_score=None,
                    status=MatchStatus.PENDING,
                    deadline=mw_deadline,
                )
                db.add(match)
                created_matches.append(match)
            current_mw += 1

    db.commit()
    for m in created_matches:
        db.refresh(m)

    return created_matches


def enforce_expired_match_deadlines(
    db: Session,
    up_to_matchweek: Optional[int] = None,
    force_all_pending_in_matchweek: bool = False,
) -> int:
    """
    Assign a 0-0 draw (status = AUTO_DRAWN) to unplayed (PENDING) matches:
    - Automatically when their Friday midnight deadline has passed, OR
    - Immediately for a specified matchweek when triggered by the Admin.
    Returns the number of matches converted to AUTO_DRAWN.
    """
    now = datetime.now(timezone.utc)
    query = db.query(Match).filter(Match.status == MatchStatus.PENDING)

    if up_to_matchweek is not None:
        query = query.filter(Match.matchweek <= up_to_matchweek)

    pending_matches = query.all()
    auto_drawn_count = 0

    for match in pending_matches:
        deadline = match.deadline
        if deadline is not None and deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)

        is_expired = deadline is not None and now > deadline
        if force_all_pending_in_matchweek or is_expired:
            match.home_score = 0
            match.away_score = 0
            match.status = MatchStatus.AUTO_DRAWN
            match.verified_at = now
            auto_drawn_count += 1

    if auto_drawn_count > 0:
        db.commit()

    return auto_drawn_count

