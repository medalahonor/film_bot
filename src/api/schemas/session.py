from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class SessionResponse(BaseModel):
    id: int
    status: str  # status code: collecting | voting | rating | completed
    created_at: datetime
    voting_started_at: Optional[datetime]
    completed_at: Optional[datetime]
    winner_slot1_id: Optional[int]
    winner_slot2_id: Optional[int]
    runoff_slot1_ids: Optional[List[int]]
    runoff_slot2_ids: Optional[List[int]]

    model_config = {"from_attributes": True}
