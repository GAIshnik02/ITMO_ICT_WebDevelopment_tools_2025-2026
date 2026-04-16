from fastapi import FastAPI, Depends, HTTPException, status
from typing_extensions import TypedDict
from sqlmodel import Session, select
from datetime import datetime, timedelta

from models import (
    Participant, ParticipantBase, ParticipantWithSkills,
    Team, TeamBase, TeamWithParticipants,
    Skill, SkillBase,
    Task, TaskBase, TaskWithSubmissions,
    Submission, SubmissionBase, SubmissionWithRelations,
    ParticipantSkillLink, ParticipantTeamLink,
    User, UserCreate, UserResponse, UserUpdate, UserLogin, Token
)
from connection import get_session, init_db
from auth import (
    get_password_hash, verify_password, create_access_token,
    authenticate_user, get_current_user, get_current_active_user,
    get_current_superuser, ACCESS_TOKEN_EXPIRE_MINUTES, check_owner_or_admin
)

app = FastAPI()


@app.on_event("startup")
def on_startup():
    """Инициализация базы данных при запуске"""
    init_db()


@app.get("/", tags=["General"])
def hello():
    return "Система для проведения хакатонов"


@app.post("/register", response_model=UserResponse, tags=["Authentication"])
def register(user: UserCreate, session: Session = Depends(get_session)):
    """Регистрация нового пользователя."""
    # Проверяем, существует ли уже имя пользователя
    existing_user = session.exec(select(User).where(User.username == user.username)).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Имя пользователя уже зарегистрировано"
        )

    # Проверяем, существует ли уже email
    existing_email = session.exec(select(User).where(User.email == user.email)).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email уже зарегистрирован"
        )

    # Создаем нового пользователя
    hash_password = get_password_hash(user.password)
    db_user = User(
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        hash_password=hash_password,
        created_at=datetime.utcnow().isoformat(),
        updated_at=datetime.utcnow().isoformat()
    )

    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user


@app.post("/login", response_model=Token, tags=["Authentication"])
def login(user_data: UserLogin, session: Session = Depends(get_session)):
    """Вход пользователя и возврат JWT токена."""
    user = authenticate_user(session, user_data.username, user_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверное имя пользователя или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        user, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/users/me", response_model=UserResponse, tags=["Users"])
def read_users_me(current_user: User = Depends(get_current_active_user)):
    """Получить информацию о текущем пользователе."""
    return current_user


@app.get("/users", response_model=list[UserResponse], tags=["Users"])
def read_users(
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_superuser)
):
    """Получить список всех пользователей (только для админа)."""
    if current_user.is_superuser:
        return session.exec(select(User)).all()
    else:
        raise HTTPException(status_code=403, detail="У вас нет доступа к этому ресурсу")


@app.put("/users/me", response_model=UserResponse, tags=["Users"])
def update_user_me(
        user_update: UserUpdate,
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_active_user)
):
    """Обновить профиль текущего пользователя."""
    user_data = user_update.model_dump(exclude_unset=True, exclude={"password"})

    # Обрабатываем обновление пароля отдельно
    if user_update.password:
        current_user.hash_password = get_password_hash(user_update.password)

    for key, value in user_data.items():
        setattr(current_user, key, value)

    current_user.updated_at = datetime.utcnow().isoformat()
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return current_user


@app.put("/users/me/password", tags=["Users"])
def change_password(
        old_password: str,
        new_password: str,
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_active_user)
):
    """Изменить пароль пользователя."""
    # Проверяем старый пароль
    if not verify_password(old_password, current_user.hash_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный старый пароль"
        )

    # Обновляем пароль
    current_user.hash_password = get_password_hash(new_password)
    current_user.updated_at = datetime.utcnow().isoformat()
    session.add(current_user)
    session.commit()
    return {"message": "Пароль успешно обновлен"}


@app.get("/participants", response_model=list[Participant], tags=["Participants"])
def participants_list(
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_active_user)
) -> list[Participant]:
    """Получить всех участников (только своих, админ может видеть всех)"""
    if current_user.is_superuser:
        return session.exec(select(Participant)).all()
    else:
        return session.exec(select(Participant).where(Participant.user_id == current_user.id)).all()


@app.get("/participant/{participant_id}", response_model=ParticipantWithSkills, tags=["Participants"])
def participant_get(
        participant_id: int,
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_active_user)
) -> Participant:
    """Получить участника по ID с навыками"""
    participant = session.get(Participant, participant_id)
    if not participant:
        raise HTTPException(status_code=404, detail="Участник не найден")

    if not check_owner_or_admin(current_user, participant.user_id):
        raise HTTPException(status_code=403, detail="Нет доступа к этому ресурсу")

    return participant


@app.post("/participant", tags=["Participants"])
def participant_create(
        participant: ParticipantBase,
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_active_user)
) -> TypedDict('Response', {"status": int, "data": Participant}):
    """Создать нового участника"""
    db_participant = Participant.model_validate(participant)
    db_participant.user_id = current_user.id
    session.add(db_participant)
    session.commit()
    session.refresh(db_participant)
    return {"status": 200, "data": db_participant}


@app.patch("/participant/{participant_id}", tags=["Participants"])
def participant_update(
        participant_id: int,
        participant: ParticipantBase,
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_active_user)
) -> Participant:
    """Частичное обновление участника (только себя)"""
    db_participant = session.get(Participant, participant_id)
    if not db_participant:
        raise HTTPException(status_code=404, detail="Участник не найден")

    if not check_owner_or_admin(current_user, db_participant.user_id):
        raise HTTPException(status_code=403, detail="У вас нет доступа к этому ресурсу")

    participant_data = participant.model_dump(exclude_unset=True)
    for key, value in participant_data.items():
        setattr(db_participant, key, value)

    session.add(db_participant)
    session.commit()
    session.refresh(db_participant)
    return db_participant


@app.delete("/participant/{participant_id}", tags=["Participants"])
def participant_delete(
        participant_id: int,
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_active_user)
):
    """Удалить участника (только себя)"""
    participant = session.get(Participant, participant_id)
    if not participant:
        raise HTTPException(status_code=404, detail="Участник не найден")

    if not check_owner_or_admin(current_user, participant.user_id):
        raise HTTPException(status_code=403, detail="У вас нет доступа к этому ресурсу")

    session.delete(participant)
    session.commit()
    return {"status": 200, "message": "Участник успешно удален"}

@app.get("/teams", response_model=list[Team], tags=["Teams"])
def teams_list(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_active_user)
) -> list[Team]:
    """
    Получить команды:
    - Админ видит все
    - Пользователь видит команды, где он участник ИЛИ которые сам создал
    """
    if current_user.is_superuser:
        return session.exec(select(Team)).all()

    # Получаем участников текущего пользователя
    user_participants = session.exec(
        select(Participant).where(Participant.user_id == current_user.id)
    ).all()
    participant_ids = [p.id for p in user_participants]

    # Находим команды, где есть эти участники
    team_links = session.exec(
        select(ParticipantTeamLink).where(ParticipantTeamLink.participant_id.in_(participant_ids))
    ).all() if participant_ids else []

    team_ids_from_links = [link.team_id for link in team_links]

    # Находим команды, которые создал пользователь
    teams_created = session.exec(
        select(Team).where(Team.created_by == current_user.id)
    ).all()
    team_ids_created = [t.id for t in teams_created]

    # Объединяем ID команд (уникальные)
    all_team_ids = list(set(team_ids_from_links + team_ids_created))

    if not all_team_ids:
        return []

    return session.exec(select(Team).where(Team.id.in_(all_team_ids))).all()


@app.get("/team/{team_id}", response_model=TeamWithParticipants, tags=["Teams"])
def team_get(
    team_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_active_user)
) -> TeamWithParticipants:
    """
    Получить команду по ID:
    - Админ может любую
    - Пользователь может, если он участник ИЛИ создатель
    """
    team = session.get(Team, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Команда не найдена")

    # Если админ - пропускаем
    if current_user.is_superuser:
        _ = team.participants
        return team

    # Проверяем, является ли пользователь участником команды
    user_participants = session.exec(
        select(Participant).where(Participant.user_id == current_user.id)
    ).all()
    participant_ids = [p.id for p in user_participants]

    is_member = False
    if participant_ids:
        link = session.exec(
            select(ParticipantTeamLink).where(
                ParticipantTeamLink.team_id == team_id,
                ParticipantTeamLink.participant_id.in_(participant_ids)
            )
        ).first()
        is_member = link is not None

    # Проверяем, является ли пользователь создателем
    is_creator = team.created_by == current_user.id

    if not is_member and not is_creator:
        raise HTTPException(status_code=403, detail="Нет доступа к этой команде")

    _ = team.participants
    return team


@app.post("/team", tags=["Teams"])
def team_create(
    team: TeamBase,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_active_user)
) -> TypedDict('Response', {"status": int, "data": Team}):
    """Создать новую команду (привязывается к текущему пользователю как создатель)"""
    db_team = Team.model_validate(team)
    db_team.created_by = current_user.id  # ← привязываем создателя
    session.add(db_team)
    session.commit()
    session.refresh(db_team)
    return {"status": 200, "data": db_team}


@app.patch("/team/{team_id}", tags=["Teams"])
def team_update(
    team_id: int,
    team: TeamBase,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_active_user)
) -> Team:
    """
    Обновить команду:
    - Админ может любую
    - Только создатель команды
    """
    db_team = session.get(Team, team_id)
    if not db_team:
        raise HTTPException(status_code=404, detail="Команда не найдена")

    # Проверка прав
    if not current_user.is_superuser and db_team.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Нет прав на редактирование этой команды")

    team_data = team.model_dump(exclude_unset=True)
    for key, value in team_data.items():
        setattr(db_team, key, value)

    session.add(db_team)
    session.commit()
    session.refresh(db_team)
    return db_team


@app.delete("/team/{team_id}", tags=["Teams"])
def team_delete(
    team_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_active_user)
):
    """
    Удалить команду:
    - Админ может любую
    - Только создатель команды
    """
    team = session.get(Team, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Команда не найдена")

    # Проверка прав
    if not current_user.is_superuser and team.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Нет прав на удаление этой команды")

    session.delete(team)
    session.commit()
    return {"status": 200, "message": "Команда успешно удалена"}


@app.post("/team/{team_id}/participant/{participant_id}", tags=["Relationships"])
def add_participant_to_team(
    team_id: int,
    participant_id: int,
    role: str = "member",
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_active_user)
):
    """
    Добавить участника в команду:
    - Админ может любого
    - Создатель команды может добавлять
    - Сам участник может добавить себя в команду
    """
    team = session.get(Team, team_id)
    participant = session.get(Participant, participant_id)

    if not team or not participant:
        raise HTTPException(status_code=404, detail="Команда или участник не найден")

    # Проверяем права на добавление
    is_creator = team.created_by == current_user.id
    is_self = participant.user_id == current_user.id
    is_superuser = current_user.is_superuser

    if not (is_superuser or is_creator or is_self):
        raise HTTPException(
            status_code=403,
            detail="Нет прав на добавление участников в эту команду"
        )

    # Проверяем, существует ли уже связь
    existing = session.exec(
        select(ParticipantTeamLink).where(
            ParticipantTeamLink.team_id == team_id,
            ParticipantTeamLink.participant_id == participant_id
        )
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="Участник уже в команде")

    # Создаем связь
    link = ParticipantTeamLink(
        team_id=team_id,
        participant_id=participant_id,
        role=role
    )
    session.add(link)
    session.commit()

    return {"status": 200, "message": "Участник успешно добавлен в команду"}


@app.get("/team/{team_id}/participants", response_model=list[Participant], tags=["Relationships"])
def get_team_participants(
    team_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_active_user)
):
    """
    Получить всех участников команды:
    - Админ может любую
    - Создатель команды
    - Участник команды
    """
    team = session.get(Team, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Команда не найдена")

    # Админ может всё
    if current_user.is_superuser:
        return team.participants

    # Проверяем, является ли пользователь участником команды
    user_participants = session.exec(
        select(Participant).where(Participant.user_id == current_user.id)
    ).all()
    participant_ids = [p.id for p in user_participants]

    is_member = False
    if participant_ids:
        link = session.exec(
            select(ParticipantTeamLink).where(
                ParticipantTeamLink.team_id == team_id,
                ParticipantTeamLink.participant_id.in_(participant_ids)
            )
        ).first()
        is_member = link is not None

    # Проверяем, является ли пользователь создателем
    is_creator = team.created_by == current_user.id

    if not is_member and not is_creator:
        raise HTTPException(status_code=403, detail="Нет доступа к этой команде")

    return team.participants


@app.get("/skills", response_model=list[Skill], tags=["Skills"])
def skills_list(
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_active_user)
) -> list[Skill]:
    """Получить все навыки"""
    return session.exec(select(Skill)).all()


@app.post("/skill", tags=["Skills"])
def skill_create(
        skill: SkillBase,
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_superuser)
) -> TypedDict('Response', {"status": int, "data": Skill}):
    """Создать новый навык (Только админы)"""
    db_skill = Skill.model_validate(skill)
    session.add(db_skill)
    session.commit()
    session.refresh(db_skill)
    return {"status": 200, "data": db_skill}


@app.patch("/skill/{skill_id}", tags=["Skills"])
def skill_update(
        skill_id: int,
        skill: SkillBase,
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_superuser)
) -> Skill:
    """Частичное обновление навыка"""

    db_skill = session.get(Skill, skill_id)
    if not db_skill:
        raise HTTPException(status_code=404, detail="Навык не найден")

    skill_data = skill.model_dump(exclude_unset=True)
    for key, value in skill_data.items():
        setattr(db_skill, key, value)

    session.add(db_skill)
    session.commit()
    session.refresh(db_skill)
    return db_skill


@app.delete("/skill/{skill_id}", tags=["Skills"])
def skill_delete(
        skill_id: int,
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_superuser)
):
    """Удалить навык"""
    skill = session.get(Skill, skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Навык не найден")

    session.delete(skill)
    session.commit()
    return {"status": 200, "message": "Навык успешно удален"}


@app.get("/tasks", response_model=list[Task], tags=["Tasks"])
def tasks_list(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_active_user)
) -> list[Task]:
    """Получить все задачи"""
    return session.exec(select(Task)).all()


@app.get("/task/{task_id}", response_model=TaskWithSubmissions, tags=["Tasks"])
def task_get(
    task_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_active_user)
) -> TaskWithSubmissions:
    """Получить задачу по ID с решениями"""
    task = session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    # Триггерим загрузку решений
    _ = task.submissions
    return task


@app.post("/task", tags=["Tasks"])
def task_create(
        task: TaskBase,
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_superuser)
) -> TypedDict('Response', {"status": int, "data": Task}):
    """Создать новую задачу (только админ)"""
    db_task = Task.model_validate(task)
    session.add(db_task)
    session.commit()
    session.refresh(db_task)
    return {"status": 200, "data": db_task}


@app.patch("/task/{task_id}", tags=["Tasks"])
def task_update(
        task_id: int,
        task: TaskBase,
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_superuser)
) -> Task:
    """Частичное обновление задачи"""
    db_task = session.get(Task, task_id)
    if not db_task:
        raise HTTPException(status_code=404, detail="Задача не найдена")

    task_data = task.model_dump(exclude_unset=True)
    for key, value in task_data.items():
        setattr(db_task, key, value)

    session.add(db_task)
    session.commit()
    session.refresh(db_task)
    return db_task


@app.delete("/task/{task_id}", tags=["Tasks"])
def task_delete(
        task_id: int,
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_superuser)
):
    """Удалить задачу"""
    task = session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")

    session.delete(task)
    session.commit()
    return {"status": 200, "message": "Задача успешно удалена"}


@app.get("/submissions", response_model=list[Submission], tags=["Submissions"])
def submissions_list(
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_active_user)
) -> list[Submission]:
    """
    Получить решения:
    - Админ видит все
    - Пользователь видит только решения своих участников
    """
    if current_user.is_superuser:
        return session.exec(select(Submission)).all()

    # Получаем участников текущего пользователя
    user_participants = session.exec(
        select(Participant).where(Participant.user_id == current_user.id)
    ).all()
    participant_ids = [p.id for p in user_participants]

    if not participant_ids:
        return []

    return session.exec(select(Submission).where(Submission.participant_id.in_(participant_ids))).all()


@app.get("/submission/{submission_id}", response_model=SubmissionWithRelations, tags=["Submissions"])
def submission_get(
        submission_id: int,
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_active_user)
) -> SubmissionWithRelations:
    """
    Получить решение по ID:
    - Админ может любое
    - Пользователь может только свои
    """
    submission = session.get(Submission, submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="Решение не найдено")

    # Проверка прав
    if not current_user.is_superuser:
        # Проверяем, принадлежит ли решение участнику текущего пользователя
        if submission.participant_id:
            participant = session.get(Participant, submission.participant_id)
            if not participant or participant.user_id != current_user.id:
                raise HTTPException(status_code=403, detail="Нет доступа к этому решению")
        else:
            raise HTTPException(status_code=403, detail="Нет доступа к этому решению")

    # Триггерим загрузку связей
    _ = submission.task
    _ = submission.team
    _ = submission.participant
    return submission


@app.post("/submission", tags=["Submissions"])
def submission_create(
        submission: SubmissionBase,
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_active_user)
) -> TypedDict('Response', {"status": int, "data": Submission}):
    """
    Создать новое решение:
    - Админ может для любого участника
    - Пользователь может только для своих участников
    """
    # Проверяем, что participant_id принадлежит текущему пользователю (или админ)
    if submission.participant_id:
        participant = session.get(Participant, submission.participant_id)
        if not participant:
            raise HTTPException(status_code=404, detail="Участник не найден")
        if not current_user.is_superuser and participant.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Нельзя создать решение для чужого участника")
    else:
        raise HTTPException(status_code=400, detail="Не указан участник (participant_id)")

    db_submission = Submission.model_validate(submission)
    session.add(db_submission)
    session.commit()
    session.refresh(db_submission)
    return {"status": 200, "data": db_submission}


@app.delete("/submission/{submission_id}", tags=["Submissions"])
def submission_delete(
        submission_id: int,
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_active_user)
):
    """
    Удалить решение:
    - Админ может любое
    - Пользователь может только свои
    """
    submission = session.get(Submission, submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="Решение не найдено")

    # Проверка прав
    if not current_user.is_superuser:
        if submission.participant_id:
            participant = session.get(Participant, submission.participant_id)
            if not participant or participant.user_id != current_user.id:
                raise HTTPException(status_code=403, detail="Нет доступа к этому решению")
        else:
            raise HTTPException(status_code=403, detail="Нет доступа к этому решению")

    session.delete(submission)
    session.commit()
    return {"status": 200, "message": "Решение успешно удалено"}


@app.post("/participant/{participant_id}/skill/{skill_id}", tags=["Relationships"])
def add_skill_to_participant(
        participant_id: int,
        skill_id: int,
        proficiency_level: int = 1,
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_active_user)
):
    """Добавить навык участнику (многие-ко-многим)"""
    participant = session.get(Participant, participant_id)
    skill = session.get(Skill, skill_id)

    if not participant or not skill:
        raise HTTPException(status_code=404, detail="Участник или навык не найден")

    # Проверяем, существует ли уже связь
    existing = session.exec(
        select(ParticipantSkillLink).where(
            ParticipantSkillLink.participant_id == participant_id,
            ParticipantSkillLink.skill_id == skill_id
        )
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="Навык уже добавлен участнику")

    # Создаем связь
    link = ParticipantSkillLink(
        participant_id=participant_id,
        skill_id=skill_id,
        proficiency_level=proficiency_level
    )
    session.add(link)
    session.commit()

    return {"status": 200, "message": "Навык успешно добавлен участнику"}


@app.post("/team/{team_id}/participant/{participant_id}", tags=["Relationships"])
def add_participant_to_team(
        team_id: int,
        participant_id: int,
        role: str = "member",
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_active_user)
):
    """Добавить участника в команду (многие-ко-многим)"""
    team = session.get(Team, team_id)
    participant = session.get(Participant, participant_id)

    if not team or not participant:
        raise HTTPException(status_code=404, detail="Команда или участник не найден")

    # Проверяем, существует ли уже связь
    existing = session.exec(
        select(ParticipantTeamLink).where(
            ParticipantTeamLink.team_id == team_id,
            ParticipantTeamLink.participant_id == participant_id
        )
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="Участник уже в команде")

    # Создаем связь
    link = ParticipantTeamLink(
        team_id=team_id,
        participant_id=participant_id,
        role=role
    )
    session.add(link)
    session.commit()

    return {"status": 200, "message": "Участник успешно добавлен в команду"}


@app.get("/participant/{participant_id}/teams", response_model=list[Team], tags=["Relationships"])
def get_participant_teams(
        participant_id: int,
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_active_user)
):
    """Получить все команды участника"""
    participant = session.get(Participant, participant_id)
    if not participant:
        raise HTTPException(status_code=404, detail="Участник не найден")
    return participant.teams


@app.get("/team/{team_id}/participants", response_model=list[Participant], tags=["Relationships"])
def get_team_participants(
        team_id: int,
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_active_user)
):
    """Получить всех участников команды"""
    team = session.get(Team, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Команда не найдена")
    return team.participants


@app.get("/task/{task_id}/submissions", response_model=list[Submission], tags=["Relationships"])
def get_task_submissions(
        task_id: int,
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_active_user)
):
    """Получить все решения задачи"""
    task = session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    return task.submissions