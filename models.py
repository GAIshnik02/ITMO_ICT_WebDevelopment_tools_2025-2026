from datetime import datetime
from enum import Enum
from typing import List, Optional
from sqlmodel import SQLModel, Field, Relationship
from pydantic import EmailStr

class ParticipantType(Enum):
    programmer = 'programmer'
    designer = 'designer'
    manager = 'manager'
    analyst = 'analyst'

#M:M между участником и навыком
class ParticipantSkillLink(SQLModel, table=True):
    participant_id: Optional[int] = Field(
        default=None, foreign_key="participant.id", primary_key=True
    )
    skill_id: Optional[int] = Field(
        default=None, foreign_key="skill.id", primary_key=True
    )
    proficiency_level: Optional[int] = Field(
        default=None, ge=1, le=10
    )

#M:M между участником и командой
class ParticipantTeamLink(SQLModel, table=True):
    participant_id: Optional[int] = Field(
        default=None, foreign_key="participant.id", primary_key=True
    )
    team_id: Optional[int] = Field(
        default=None, foreign_key="team.id", primary_key=True
    )
    role: str = Field(default="member")

#Модели для Post запросов
class SkillBase(SQLModel):
    name: str
    description: Optional[str] = ""

class TeamBase(SQLModel):
    name: str
    description: Optional[str] = ""

class UserBase(SQLModel):
    username: str
    email: EmailStr
    full_name: Optional[str] = None
    is_active: Optional[bool] = True
    is_superuser: Optional[bool] = False


class ParticipantBase(SQLModel):
    name: str
    email: EmailStr
    phone: Optional[str] = None
    type: ParticipantType


class TaskBase(SQLModel):
    title: str
    description: str
    requirements: str
    evaluation_criteria: str
    is_active: bool = True

class SubmissionBase(SQLModel):
    title: str
    description: str
    repository_url: Optional[str] = ""
    demo_url: Optional[str] = ""


# Базовые таблицы
class Skill(SkillBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    participants: List["Participant"] = Relationship(
        back_populates="skills", link_model=ParticipantSkillLink
    )

class Team(TeamBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_by: Optional[int] = Field(default=None, foreign_key="user.id")
    creator: Optional["User"] = Relationship(back_populates="teams")

    participants: List["Participant"] = Relationship(
        back_populates="teams", link_model=ParticipantTeamLink
    )
    submissions: List["Submission"] = Relationship(back_populates="team")


class Participant(ParticipantBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    user: Optional["User"] = Relationship(back_populates="participants")

    skills: List[Skill] = Relationship(
        back_populates="participants", link_model=ParticipantSkillLink
    )
    teams: List[Team] = Relationship(
        back_populates="participants", link_model=ParticipantTeamLink
    )
    submissions: List["Submission"] = Relationship(back_populates="participant")


class User(UserBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    hash_password: str = Field(nullable=False)
    created_at: Optional[str] = Field(default=None)
    updated_at: Optional[str] = Field(default=None)
    participants: List[Participant] = Relationship(back_populates="user")
    teams: List[Team] = Relationship(back_populates="creator")


class Task(TaskBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    submissions: List["Submission"] = Relationship(back_populates="task")


class Submission(SubmissionBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    task_id: Optional[int] = Field(default=None, foreign_key="task.id")
    team_id: Optional[int] = Field(default=None, foreign_key="team.id")
    participant_id: Optional[int] = Field(default=None, foreign_key="participant.id")

    task: Optional[Task] = Relationship(back_populates="submissions")
    team: Optional[Team] = Relationship(back_populates="submissions")
    participant: Optional[Participant] = Relationship(back_populates="submissions")

# Response
class ParticipantWithSkills(ParticipantBase):
    id: int
    skills: List[Skill] = []


class ParticipantWithTeams(ParticipantBase):
    id: int
    teams: List[Team] = []


class TeamWithParticipants(TeamBase):
    id: int
    participants: List[Participant] = []


class TaskWithSubmissions(TaskBase):
    id: int
    submissions: List[Submission] = []


class SubmissionWithRelations(SubmissionBase):
    id: int
    task: Optional[Task] = None
    team: Optional[Team] = None
    participant: Optional[Participant] = None


class UserResponse(UserBase):
    id: int
    created_at: Optional[datetime] = datetime.now()
    updated_at: Optional[datetime] = datetime.now()


class UserCreate(SQLModel):
    username: str
    email: EmailStr
    password: str
    full_name: Optional[str] = None


class UserUpdate(SQLModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None


class UserLogin(SQLModel):
    username: str
    password: str


class Token(SQLModel):
    access_token: str
    token_type: str


class TokenData(SQLModel):
    username: Optional[str] = None