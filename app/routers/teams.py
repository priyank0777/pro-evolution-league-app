from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import get_current_user, get_system_settings_model, get_user_team
from app.database import get_db
from app.models import Team, User
from app.schemas import TeamOut, TeamUpdateIn, UserPublicOut

router = APIRouter(prefix="/api/teams", tags=["Teams"])


def serialize_team(team: Team) -> TeamOut:
    """Convert a Team ORM object into TeamOut."""
    return TeamOut(
        id=team.id,
        name=team.name,
        leader_id=team.leader_id,
        leader_name=team.leader.name if team.leader else None,
        player1=UserPublicOut.model_validate(team.player1),
        player2=UserPublicOut.model_validate(team.player2),
    )


@router.get("", response_model=List[TeamOut])
def list_teams(db: Session = Depends(get_db)):
    """Return the Team Directory of all formed 2v2 teams, members, and leaders."""
    teams = db.query(Team).order_by(Team.id.asc()).all()
    return [serialize_team(t) for t in teams]


@router.get("/my-team", response_model=TeamOut)
def get_my_team(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the authenticated player's paired 2v2 team."""
    team = get_user_team(db, current_user.id)
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="You have not been assigned to a team yet.",
        )
    return serialize_team(team)


@router.put("/my-team", response_model=TeamOut)
def update_my_team(
    payload: TeamUpdateIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Allow paired team members to set their Team Name and designate a Team Leader (Captain).
    Permitted when Team Setup phase is open (or before season lock).
    """
    sys_settings = get_system_settings_model(db)
    if not sys_settings.team_setup_open and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Team Setup phase is currently closed by the Administrator.",
        )

    team = get_user_team(db, current_user.id)
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="You are not part of a formed team.",
        )

    if payload.leader_id not in (team.player1_id, team.player2_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Selected Team Leader must be one of the two members of your team.",
        )

    clean_name = payload.name.strip()
    duplicate = (
        db.query(Team)
        .filter(Team.name == clean_name, Team.id != team.id)
        .first()
    )
    if duplicate:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Another team is already using that Team Name.",
        )

    team.name = clean_name
    team.leader_id = payload.leader_id
    db.commit()
    db.refresh(team)
    return serialize_team(team)

