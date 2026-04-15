from enum import Enum
from typing import Optional
from pydantic import BaseModel, EmailStr


class ParticipantType(Enum):
    programmer = 'programmer'
    designer = 'designer'
    manager = 'manager'
    analyst = 'analyst'


class Team(BaseModel):
    id: int
    name: str
    description: str


class Skill(BaseModel):
    id: int
    name: str
    description: str


class Participant(BaseModel):
    id: int
    type: ParticipantType
    name: str
    email: EmailStr
    phone: Optional[str] = None
    team: Team
    skills: Optional[list[Skill]] = []