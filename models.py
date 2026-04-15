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
    participants: List["Participant"] = Relationship(
        back_populates="teams", link_model=ParticipantTeamLink
    )
    submissions: List["Submission"] = Relationship(back_populates="team")


class Participant(ParticipantBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    skills: List[Skill] = Relationship(
        back_populates="participants", link_model=ParticipantSkillLink
    )
    teams: List[Team] = Relationship(
        back_populates="participants", link_model=ParticipantTeamLink
    )
    submissions: List["Submission"] = Relationship(back_populates="participant")


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