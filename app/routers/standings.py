from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import get_system_settings_model
from app.database import get_db
from app.schemas import (
    PlayerLeaderboardRowOut,
    StandingRowOut,
    SystemSettingsOut,
)
from app.services.scheduler import enforce_expired_match_deadlines
from app.services.standings import calculate_mvp_leaderboard, calculate_standings

router = APIRouter(prefix="/api", tags=["Standings & Public State"])


@router.get("/settings/public", response_model=SystemSettingsOut)
def get_public_system_settings(db: Session = Depends(get_db)):
    """Return global phase toggles and stat tracking settings for the frontend SPA."""
    return get_system_settings_model(db)


@router.get("/standings", response_model=List[StandingRowOut])
def get_league_standings(db: Session = Depends(get_db)):
    """
    Return the Premier League-style standings table (Played, Won, Drawn, Lost,
    GF, GA, GD, Points) with GD and Head-to-Head tie-breakers.
    """
    enforce_expired_match_deadlines(db)
    return calculate_standings(db)


@router.get("/stats/leaderboard", response_model=List[PlayerLeaderboardRowOut])
def get_player_mvp_leaderboard(db: Session = Depends(get_db)):
    """
    Return the individual human player MVP leaderboard tracking Total Points,
    Goals, Assists, Matches Played, and Average Points.
    """
    return calculate_mvp_leaderboard(db)

