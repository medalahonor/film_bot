"""Session status manager."""
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import SessionStatus


# Status codes
STATUS_COLLECTING = "collecting"
STATUS_VOTING = "voting"
STATUS_RATING = "rating"
STATUS_COMPLETED = "completed"


async def get_status_by_code(db: AsyncSession, code: str) -> Optional[SessionStatus]:
    """Get session status by code.
    
    Args:
        db: Database session
        code: Status code
        
    Returns:
        SessionStatus object or None
    """
    result = await db.execute(
        select(SessionStatus).where(SessionStatus.code == code)
    )
    return result.scalar_one_or_none()


async def init_statuses(db: AsyncSession) -> None:
    """Initialize default session statuses in database.
    
    Args:
        db: Database session
    """
    statuses = [
        {
            "code": STATUS_COLLECTING,
            "name": "Сбор предложений",
            "description": "Участники предлагают фильмы для голосования"
        },
        {
            "code": STATUS_VOTING,
            "name": "Голосование",
            "description": "Идет голосование за предложенные фильмы"
        },
        {
            "code": STATUS_RATING,
            "name": "Выставление рейтингов",
            "description": "Участники оценивают просмотренные фильмы"
        },
        {
            "code": STATUS_COMPLETED,
            "name": "Завершена",
            "description": "Сессия завершена"
        }
    ]
    
    for status_data in statuses:
        # Check if status exists
        existing = await get_status_by_code(db, status_data["code"])
        if not existing:
            status = SessionStatus(
                code=status_data["code"],
                name=status_data["name"],
                description=status_data["description"]
            )
            db.add(status)
    
    await db.commit()
