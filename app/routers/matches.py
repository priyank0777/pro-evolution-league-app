from datetime import datetime, timezone
from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.auth import get_current_user, get_system_settings_model, get_user_team
from app.database import get_db
from app.models import Match, MatchStat, MatchStatus, Team, User
from app.schemas import (
    MatchOut,
    MatchSubmitIn,
    MatchVerifyIn,
    PlayerStatOut,
    UserPublicOut,
)
from app.services.scheduler import enforce_expired_match_deadlines

router = APIRouter(prefix="/api/matches", tags=["Matches"])


def serialize_match(db: Session, match: Match, user_team_lookup: Optional[Dict[int, int]] = None) -> MatchOut:
    """Serialize a Match ORM instance with team rosters and individual player stats."""
    home_team = match.home_team
    away_team = match.away_team

    if user_team_lookup is None:
        user_team_lookup = {
            home_team.player1_id: home_team.id,
            home_team.player2_id: home_team.id,
            away_team.player1_id: away_team.id,
            away_team.player2_id: away_team.id,
        }

    home_players = [
        UserPublicOut.model_validate(home_team.player1),
        UserPublicOut.model_validate(home_team.player2),
    ]
    away_players = [
        UserPublicOut.model_validate(away_team.player1),
        UserPublicOut.model_validate(away_team.player2),
    ]

    stats_out: List[PlayerStatOut] = []
    for st in match.player_stats:
        stats_out.append(
            PlayerStatOut(
                id=st.id,
                user_id=st.user_id,
                user_name=st.user.name if st.user else f"User #{st.user_id}",
                efootball_username=st.user.efootball_username if st.user else "",
                team_id=user_team_lookup.get(st.user_id),
                total_points=st.total_points,
                goals=st.goals,
                assists=st.assists,
            )
        )

    return MatchOut(
        id=match.id,
        matchweek=match.matchweek,
        home_team_id=match.home_team_id,
        home_team_name=home_team.name,
        away_team_id=match.away_team_id,
        away_team_name=away_team.name,
        home_score=match.home_score,
        away_score=match.away_score,
        status=match.status,
        deadline=match.deadline,
        submitted_at=match.submitted_at,
        verified_at=match.verified_at,
        home_players=home_players,
        away_players=away_players,
        player_stats=stats_out,
    )


@router.get("", response_model=List[MatchOut])
def list_all_matches(
    matchweek: Optional[int] = Query(default=None),
    status_filter: Optional[MatchStatus] = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
):
    """
    Return the season's fixtures separated or filtered by matchweek.
    Automatically enforces Friday midnight 0-0 auto-draws on expired pending matches.
    """
    enforce_expired_match_deadlines(db)

    query = db.query(Match)
    if matchweek is not None:
        query = query.filter(Match.matchweek == matchweek)
    if status_filter is not None:
        query = query.filter(Match.status == status_filter)

    matches = query.order_by(Match.matchweek.asc(), Match.id.asc()).all()

    teams = db.query(Team).all()
    user_team_lookup: Dict[int, int] = {}
    for t in teams:
        user_team_lookup[t.player1_id] = t.id
        user_team_lookup[t.player2_id] = t.id

    return [serialize_match(db, m, user_team_lookup) for m in matches]


@router.get("/my-current", response_model=List[MatchOut])
def get_my_current_matches(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return the current matchweek's fixtures involving the authenticated user's team,
    plus any unverified (submitted/disputed) fixtures from earlier matchweeks requiring action.
    """
    enforce_expired_match_deadlines(db)
    team = get_user_team(db, current_user.id)
    if not team:
        return []

    sys_settings = get_system_settings_model(db)
    current_mw = sys_settings.current_matchweek

    matches = (
        db.query(Match)
        .filter(
            or_(Match.home_team_id == team.id, Match.away_team_id == team.id),
            or_(
                Match.matchweek == current_mw,
                Match.status.in_([MatchStatus.SUBMITTED, MatchStatus.DISPUTED]),
            ),
        )
        .order_by(Match.matchweek.asc(), Match.id.asc())
        .all()
    )

    return [serialize_match(db, m) for m in matches]


@router.post("/{match_id}/submit", response_model=MatchOut)
def submit_match_score(
    match_id: int,
    payload: MatchSubmitIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Home team submits the match score and individual player stats (Total Points, Goals, Assists).
    Transitions match status from PENDING (or DISPUTED) to SUBMITTED for Away team verification.
    """
    enforce_expired_match_deadlines(db)
    sys_settings = get_system_settings_model(db)
    if not sys_settings.season_live and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Season is not currently live for score submissions.",
        )

    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Match not found."
        )

    user_team = get_user_team(db, current_user.id)
    if not user_team or user_team.id != match.home_team_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only members of the Home team can submit the match score.",
        )

    if match.status not in (MatchStatus.PENDING, MatchStatus.SUBMITTED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot submit score for a match in '{match.status.value}' status.",
        )

    valid_player_ids = {
        match.home_team.player1_id,
        match.home_team.player2_id,
        match.away_team.player1_id,
        match.away_team.player2_id,
    }

    for st in payload.player_stats:
        if st.user_id not in valid_player_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"User ID {st.user_id} is not a participant in this match.",
            )

    match.home_score = payload.home_score
    match.away_score = payload.away_score
    match.status = MatchStatus.SUBMITTED
    match.submitted_at = datetime.now(timezone.utc)

    # Replace any previous temporary stats for this match
    db.query(MatchStat).filter(MatchStat.match_id == match.id).delete()
    db.flush()

    submitted_stat_map = {st.user_id: st for st in payload.player_stats}
    for pid in sorted(valid_player_ids):
        st_in = submitted_stat_map.get(pid)
        db.add(
            MatchStat(
                match_id=match.id,
                user_id=pid,
                total_points=(st_in.total_points if st_in and sys_settings.track_points else 0),
                goals=(st_in.goals if st_in and sys_settings.track_goals else 0),
                assists=(st_in.assists if st_in and sys_settings.track_assists else 0),
            )
        )

    db.commit()
    db.refresh(match)
    return serialize_match(db, match)


@router.post("/{match_id}/verify", response_model=MatchOut)
def verify_match_score(
    match_id: int,
    payload: MatchVerifyIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Away team logs in to either 'accept' or 'dispute' a submitted match score.
    - If accepted: status updates to ACCEPTED and standings/leaderboards immediately reflect the result.
    - If disputed: status updates to DISPUTED and is flagged on the Admin Dashboard.
    """
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Match not found."
        )

    user_team = get_user_team(db, current_user.id)
    if not user_team or user_team.id != match.away_team_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only members of the Away team can verify or dispute this score.",
        )

    if match.status != MatchStatus.SUBMITTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Match must be in 'submitted' status to verify (current: '{match.status.value}').",
        )

    now = datetime.now(timezone.utc)
    if payload.action == "accept":
        match.status = MatchStatus.ACCEPTED
        match.verified_at = now
    else:
        match.status = MatchStatus.DISPUTED
        match.verified_at = now

    db.commit()
    db.refresh(match)
    return serialize_match(db, match)

