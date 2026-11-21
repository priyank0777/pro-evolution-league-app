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
    matches_per_week: int = 1,
    start_friday_deadline: Optional[datetime] = None,
) -> List[Match]:
    """
    Generate the entire season's fixtures using the Circle Method (Berger tables).
    - multiplier = 1: single round-robin (every team plays every other team once)
    - multiplier = 2: double round-robin (home & away)
    - multiplier = k: k passes, flipping home/away on each subsequent cycle.
    - matches_per_week = m: groups m Berger rounds into each matchweek so every
      team plays m matches per week (with the same Friday deadline).
    """
    if matches_per_week < 1:
        raise ValueError("matches_per_week must be at least 1.")

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
    global_round_idx = 0

    for cycle in range(multiplier):
        flip_home_away = cycle % 2 == 1
        for round_pairings in base_cycle_rounds:
            current_mw = (global_round_idx // matches_per_week) + 1
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
            global_round_idx += 1

    db.commit()
    for m in created_matches:
        db.refresh(m)

    return created_matches


def reschedule_remaining_fixtures(
    db: Session,
    matches_per_week: int,
    current_matchweek: int = 1,
) -> dict:
    """
    Repack all remaining unplayed future matchweeks so that each team plays
    `matches_per_week` matches per week for the rest of the tournament.
    - Past matchweeks (< current_matchweek) are never modified.
    - Any matchweek >= current_matchweek that already has a non-PENDING match
      (SUBMITTED, ACCEPTED, DISPUTED, AUTO_DRAWN) is preserved intact; rescheduling
      begins from the next matchweek after the latest active/completed matchweek.
    """
    if matches_per_week < 1:
        raise ValueError("matches_per_week must be at least 1.")

    all_matches = (
        db.query(Match)
        .order_by(Match.matchweek.asc(), Match.id.asc())
        .all()
    )
    if not all_matches:
        return {
            "rescheduled_matches": 0,
            "start_matchweek": current_matchweek,
            "total_matchweeks": 0,
        }

    non_pending_at_or_after = [
        m for m in all_matches
        if m.matchweek >= current_matchweek and m.status != MatchStatus.PENDING
    ]
    if non_pending_at_or_after:
        start_mw = max(m.matchweek for m in non_pending_at_or_after) + 1
    else:
        start_mw = current_matchweek

    remaining_matches = [m for m in all_matches if m.matchweek >= start_mw]
    if not remaining_matches:
        return {
            "rescheduled_matches": 0,
            "start_matchweek": start_mw,
            "total_matchweeks": max(m.matchweek for m in all_matches),
        }

    # Determine the Friday deadline anchor for `start_mw`
    anchor_deadline: Optional[datetime] = None
    for m in remaining_matches:
        if m.matchweek == start_mw and m.deadline is not None:
            anchor_deadline = m.deadline
            break

    if anchor_deadline is None:
        earlier_with_deadline = [
            m for m in all_matches
            if m.matchweek < start_mw and m.deadline is not None
        ]
        if earlier_with_deadline:
            last_prev = max(earlier_with_deadline, key=lambda m: m.matchweek)
            anchor_deadline = last_prev.deadline + timedelta(
                days=7 * (start_mw - last_prev.matchweek)
            )
        else:
            anchor_deadline = compute_next_friday_midnight()

    # Reconstruct individual Berger rounds (each team plays at most once per round)
    rounds: List[List[Match]] = []
    round_teams: List[set[int]] = []

    for m in remaining_matches:
        placed = False
        for idx, used in enumerate(round_teams):
            if m.home_team_id not in used and m.away_team_id not in used:
                rounds[idx].append(m)
                used.add(m.home_team_id)
                used.add(m.away_team_id)
                placed = True
                break
        if not placed:
            rounds.append([m])
            round_teams.append({m.home_team_id, m.away_team_id})

    # Reassign matchweeks & deadlines according to the new matches_per_week
    for r_idx, r_matches in enumerate(rounds):
        week_offset = r_idx // matches_per_week
        new_mw = start_mw + week_offset
        new_deadline = anchor_deadline + timedelta(days=7 * week_offset)
        for m in r_matches:
            m.matchweek = new_mw
            m.deadline = new_deadline

    db.commit()
    total_mws = max(m.matchweek for m in all_matches)
    return {
        "rescheduled_matches": len(remaining_matches),
        "start_matchweek": start_mw,
        "total_matchweeks": total_mws,
    }


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

