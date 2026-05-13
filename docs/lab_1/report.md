# Лабораторная 1
## Архитектура
Проект реализован на фреймворке FastAPI с использованием асинхронного подхода (где необходимо) и синхронных эндпоинтов для работы с БД через SQLModel. Авторизация построена на JWT токенах с хэшированием паролей bcrypt.

## Подключение к БД
файл connection.py
```python
import os
from sqlmodel import SQLModel, Session, create_engine
from dotenv import load_dotenv

load_dotenv()
db_url = os.getenv("DB_ADMIN")
engine = create_engine(db_url, echo=True)

def init_db():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
```

## Модели данных
файл models.py
### Enum-типы
```python
class ParticipantType(Enum):
    programmer = 'programmer'
    designer = 'designer'
    manager = 'manager'
    analyst = 'analyst'
```

### Связующие таблицы
```python
# Связь участник-навык (с уровнем владения)
class ParticipantSkillLink(SQLModel, table=True):
    participant_id: Optional[int] = Field(default=None, foreign_key="participant.id", primary_key=True)
    skill_id: Optional[int] = Field(default=None, foreign_key="skill.id", primary_key=True)
    proficiency_level: Optional[int] = Field(default=None, ge=1, le=10)

# Связь участник-команда (с ролью)
class ParticipantTeamLink(SQLModel, table=True):
    participant_id: Optional[int] = Field(default=None, foreign_key="participant.id", primary_key=True)
    team_id: Optional[int] = Field(default=None, foreign_key="team.id", primary_key=True)
    role: str = Field(default="member")
```

### Основные модели
```python
class Skill(SkillBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    participants: List["Participant"] = Relationship(back_populates="skills", link_model=ParticipantSkillLink)
```
```python
class Team(TeamBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_by: Optional[int] = Field(default=None, foreign_key="user.id")
    creator: Optional["User"] = Relationship(back_populates="teams")
    participants: List["Participant"] = Relationship(back_populates="teams", link_model=ParticipantTeamLink)
    submissions: List["Submission"] = Relationship(back_populates="team")
```
```python
class Participant(ParticipantBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    user: Optional["User"] = Relationship(back_populates="participants")
    skills: List[Skill] = Relationship(back_populates="participants", link_model=ParticipantSkillLink)
    teams: List[Team] = Relationship(back_populates="participants", link_model=ParticipantTeamLink)
    submissions: List["Submission"] = Relationship(back_populates="participant")
```
```python
class User(UserBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    hash_password: str = Field(nullable=False)
    created_at: Optional[str] = Field(default=None)
    updated_at: Optional[str] = Field(default=None)
    participants: List[Participant] = Relationship(back_populates="user")
    teams: List[Team] = Relationship(back_populates="creator")
```
```python
class Task(TaskBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    submissions: List["Submission"] = Relationship(back_populates="task")
```

```python
class Submission(SubmissionBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    task_id: Optional[int] = Field(default=None, foreign_key="task.id")
    team_id: Optional[int] = Field(default=None, foreign_key="team.id")
    participant_id: Optional[int] = Field(default=None, foreign_key="participant.id")
    task: Optional[Task] = Relationship(back_populates="submissions")
    team: Optional[Team] = Relationship(back_populates="submissions")
    participant: Optional[Participant] = Relationship(back_populates="submissions")
```

## Аутентификация и авторизация
### JWT конфигурация

```python
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
```
Данные берутся из .env файла

### Хэширование паролей

```python
def get_password_hash(password: str) -> str:
    """Хэширует пароль."""
    hashed_bytes = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

    import binascii
    return '\\x' + binascii.hexlify(hashed_bytes).decode('utf-8')

```
```python
def verify_password(plain_password: str, hash_password: str) -> bool:
    """Проверяет обычный пароль против хэшированного пароля."""
    # Обработка PostgreSQL hex формата (начинается с \x)
    if hash_password.startswith('\\x'):
        # Конвертируем hex строку в байты
        import binascii
        hex_str = hash_password[2:]  # Убираем префикс \x
        try:
            hashed_bytes = binascii.unhexlify(hex_str)
        except (binascii.Error, ValueError):
            # Если конвертация не удалась, обрабатываем как обычную строку
            hashed_bytes = hash_password.encode('utf-8')
    else:
        # Обычная строка (UTF-8)
        hashed_bytes = hash_password.encode('utf-8')

    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_bytes)
```

### JWT операции

```python
def create_access_token(user: User, expires_delta: Optional[timedelta] = None) -> str:
    """Создает JWT токен доступа."""
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode = {
        "sub": str(user.id),
        "exp": expire
    }
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt
```

```python 
def verify_token(token: str) -> Optional[dict]:
    """Проверяет и декодирует JWT токен."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None
```

## Эндпоинты API

## Общие эндпоинты

| Метод | Эндпоинт | Описание | Доступ | Request Body | Response |
|-------|----------|----------|--------|--------------|----------|
| GET | / | Приветствие | Публичный | - | "Система для проведения хакатонов" |

## Аутентификация

| Метод | Эндпоинт | Описание | Доступ | Request Body | Response |
|-------|----------|----------|--------|--------------|----------|
| POST | /register | Регистрация пользователя | Публичный | username, email, password, full_name | UserResponse |
| POST | /login | Вход в систему | Публичный | username, password | Token (access_token, token_type) |

## Пользователи

| Метод | Эндпоинт | Описание | Доступ | Request Body | Response |
|-------|----------|----------|--------|--------------|----------|
| GET | /users/me | Текущий пользователь | Авторизованные | - | UserResponse |
| GET | /users | Список всех пользователей | Суперпользователь | - | list[UserResponse] |
| PUT | /users/me | Обновление профиля | Авторизованные | UserUpdate | UserResponse |
| PUT | /users/me/password | Смена пароля | Авторизованные | old_password, new_password | message |

## Участники (Participants)

| Метод | Эндпоинт | Описание | Доступ | Request Body | Response |
|-------|----------|----------|--------|--------------|----------|
| GET | /participants | Список участников | Авторизованные | - | list[Participant] |
| GET | /participant/{id} | Участник по ID | Владелец/Админ | - | ParticipantWithSkills |
| POST | /participant | Создание участника | Авторизованные | ParticipantBase | status + Participant |
| PATCH | /participant/{id} | Обновление участника | Владелец/Админ | ParticipantBase | Participant |
| DELETE | /participant/{id} | Удаление участника | Владелец/Админ | - | status + message |

## Команды (Teams)

| Метод | Эндпоинт | Описание | Доступ | Request Body | Response |
|-------|----------|----------|--------|--------------|----------|
| GET | /teams | Список команд | Авторизованные | - | list[Team] |
| GET | /team/{id} | Команда по ID | Админ/Создатель/Участник | - | TeamWithParticipants |
| POST | /team | Создание команды | Авторизованные | TeamBase | status + Team |
| PATCH | /team/{id} | Обновление команды | Админ/Создатель | TeamBase | Team |
| DELETE | /team/{id} | Удаление команды | Админ/Создатель | - | status + message |

## Задачи (Tasks)

| Метод | Эндпоинт | Описание | Доступ | Request Body | Response |
|-------|----------|----------|--------|--------------|----------|
| GET | /tasks | Список задач | Авторизованные | - | list[Task] |
| GET | /task/{id} | Задача по ID | Авторизованные | - | TaskWithSubmissions |
| POST | /task | Создание задачи | Суперпользователь | TaskBase | status + Task |
| PATCH | /task/{id} | Обновление задачи | Суперпользователь | TaskBase | Task |
| DELETE | /task/{id} | Удаление задачи | Суперпользователь | - | status + message |

## Решения (Submissions)

| Метод | Эндпоинт | Описание | Доступ | Request Body | Response |
|-------|----------|----------|--------|--------------|----------|
| GET | /submissions | Список решений | Админ (все) / Пользователь (свои) | - | list[Submission] |
| GET | /submission/{id} | Решение по ID | Админ/Владелец | - | SubmissionWithRelations |
| POST | /submission | Создание решения | Админ/Владелец | SubmissionBase | status + Submission |
| DELETE | /submission/{id} | Удаление решения | Админ/Владелец | - | status + message |

## Навыки (Skills)

| Метод | Эндпоинт | Описание | Доступ | Request Body | Response |
|-------|----------|----------|--------|--------------|----------|
| GET | /skills | Список навыков | Авторизованные | - | list[Skill] |
| POST | /skill | Создание навыка | Суперпользователь | SkillBase | status + Skill |
| PATCH | /skill/{id} | Обновление навыка | Суперпользователь | SkillBase | Skill |
| DELETE | /skill/{id} | Удаление навыка | Суперпользователь | - | status + message |

## Связи (Relationships)

| Метод | Эндпоинт | Описание | Доступ | Параметры | Response |
|-------|----------|----------|--------|-----------|----------|
| POST | /participant/{pid}/skill/{sid} | Добавить навык участнику | Авторизованные | proficiency_level (1-10) | status + message |
| POST | /team/{tid}/participant/{pid} | Добавить участника в команду | Админ/Создатель/Участник | role (default=member) | status + message |
| GET | /participant/{pid}/teams | Команды участника | Авторизованные | - | list[Team] |
| GET | /team/{tid}/participants | Участники команды | Админ/Создатель/Участник | - | list[Participant] |
| GET | /task/{tid}/submissions | Решения задачи | Авторизованные | - | list[Submission] |
