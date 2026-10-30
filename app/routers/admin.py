from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth import (
    get_admin_user,
    get_system_settings_model,
    serialize_user,
    update_system_setting,
)
from app.database import get_db
from app.models import Match, MatchStat, MatchStatus, Team, User
from app.routers.matches import serialize_match
from app.routers.teams import serialize_team
from app.schemas import (
    AdminMatchOverrideIn,
    GenerateFixturesIn,
    MatchOut,
    SystemSettingsOut,
    SystemSettingsUpdateIn,
    UserOut,
)
from app.services.matchmaking import run_partner_matchmaking
from app.services.scheduler import (
    enforce_expired_match_deadlines,
    generate_round_robin_fixtures,
)

router = APIRouter(prefix="/api/admin", tags=["Admin Controls"])


@router.get("/settings", response_model=SystemSettingsOut)
def admin_get_settings(
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    """Retrieve all system settings for the Admin Dashboard."""
    return get_system_settings_model(db)


@router.put("/settings", response_model=SystemSettingsOut)
def admin_update_settings(
    payload: SystemSettingsUpdateIn,
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    """Update system phase toggles, stat tracking switches, and matchweek settings."""
    updates = payload.model_dump(exclude_none=True)
    for key, val in updates.items():
        if isinstance(val, bool):
            update_system_setting(db, key, "true" if val else "false")
        else:
            update_system_setting(db, key, str(val))
    db.commit()
    return get_system_settings_model(db)


@router.get("/users", response_model=List[UserOut])
def admin_list_users(
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    """List all registered users (both players and admins) for user management."""
    users = db.query(User).order_by(User.is_admin.desc(), User.id.asc()).all()
    return [serialize_user(db, u) for u in users]


@router.delete("/users/{user_id}", status_code=status.HTTP_200_OK)
def admin_delete_user(
    user_id: int,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    """Allow Admin to delete duplicate or erroneous user accounts."""
    if user_id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own active Admin account.",
        )

    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    db.delete(target)
    db.commit()
    return {"detail": f"Deleted user '{target.name}' (@{target.efootball_username})."}


@router.post("/matchmaking/run")
def admin_trigger_matchmaking(
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    """
    Execute the Stable Roommate / Minimum-Weight Matching algorithm to pair all
    non-admin players into 2v2 teams based on mutual preference rankings.
    Automatically closes registration & preferences and opens the Team Setup phase.
    """
    try:
        teams, algorithm_used = run_partner_matchmaking(db)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    update_system_setting(db, "registration_open", "false")
    update_system_setting(db, "preferences_open", "false")
    update_system_setting(db, "team_setup_open", "true")
    db.commit()

    return {
        "detail": f"Successfully paired {len(teams) * 2} players into {len(teams)} teams using {algorithm_used}.",
        "algorithm": algorithm_used,
        "teams": [serialize_team(t) for t in teams],
        "settings": get_system_settings_model(db),
    }


@router.post("/fixtures/generate")
def admin_generate_season_fixtures(
    payload: GenerateFixturesIn,
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    """
    Generate the entire season's round-robin fixtures using the configured multiplier
    (1 = single round-robin, 2 = home & away double round-robin, etc.).
    Automatically activates the Live Season at Matchweek 1.
    """
    sys_settings = get_system_settings_model(db)
    multiplier = (
        payload.round_robin_multiplier
        if payload.round_robin_multiplier is not None
        else sys_settings.round_robin_multiplier
    )

    start_friday: Optional[datetime] = None
    if payload.start_friday_iso:
        try:
            start_friday = datetime.fromisoformat(
                payload.start_friday_iso.replace("Z", "+00:00")
            )
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid ISO datetime format for start_friday_iso.",
            )

    try:
        matches = generate_round_robin_fixtures(
            db, multiplier=multiplier, start_friday_deadline=start_friday
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    update_system_setting(db, "round_robin_multiplier", str(multiplier))
    update_system_setting(db, "current_matchweek", "1")
    update_system_setting(db, "season_live", "true")
    db.commit()

    max_mw = max((m.matchweek for m in matches), default=1)
    return {
        "detail": f"Generated {len(matches)} fixtures across {max_mw} matchweeks (Multiplier: {multiplier}x).",
        "total_matches": len(matches),
        "total_matchweeks": max_mw,
        "settings": get_system_settings_model(db),
    }


@router.post("/matches/auto-draw")
def admin_process_auto_draws(
    matchweek: Optional[int] = Query(default=None),
    force_matchweek: bool = Query(default=False),
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    """
    Enforce Friday midnight deadlines (assigning 0-0 AUTO_DRAWN to unplayed matches).
    If `force_matchweek=true` and `matchweek` is provided, immediately assigns 0-0
    draws to all remaining unplayed matches in that matchweek.
    """
    count = enforce_expired_match_deadlines(
        db,
        up_to_matchweek=matchweek,
        force_all_pending_in_matchweek=force_matchweek,
    )
    return {
        "detail": f"Assigned 0-0 auto-draw to {count} unplayed match(es).",
        "auto_drawn_count": count,
    }


@router.get("/disputes", response_model=List[MatchOut])
def admin_list_disputed_matches(
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    """Return all matches currently flagged as DISPUTED (or SUBMITTED awaiting review)."""
    matches = (
        db.query(Match)
        .filter(Match.status == MatchStatus.DISPUTED)
        .order_by(Match.matchweek.asc(), Match.id.asc())
        .all()
    )
    return [serialize_match(db, m) for m in matches]


@router.put("/matches/{match_id}/override", response_model=MatchOut)
def admin_override_match(
    match_id: int,
    payload: AdminMatchOverrideIn,
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    """
    Retroactively edit any match score, status, or individual player statistics
    at any time, even after the matchweek has concluded.
    """
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Match not found.",
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

    now = datetime.now(timezone.utc)
    match.home_score = payload.home_score
    match.away_score = payload.away_score
    match.status = payload.status
    match.verified_at = now
    if match.submitted_at is None:
        match.submitted_at = now

    # Replace match stats if provided or ensure all 4 players have stat rows
    db.query(MatchStat).filter(MatchStat.match_id == match.id).delete()
    db.flush()

    stat_map = {st.user_id: st for st in payload.player_stats}
    for pid in sorted(valid_player_ids):
        st_in = stat_map.get(pid)
        db.add(
            MatchStat(
                match_id=match.id,
                user_id=pid,
                total_points=st_in.total_points if st_in else 0,
                goals=st_in.goals if st_in else 0,
                assists=st_in.assists if st_in else 0,
            )
        )

    db.commit()
    db.refresh(match)
    return serialize_match(db, match)

