from fastapi import FastAPI
from typing_extensions import TypedDict

from models import Participant
from mock import temp_bd

app = FastAPI()


@app.get('/')
def hello():
    return 'Hackathon Management System API'


@app.get("/participants")
def participants_list() -> list[Participant]:
    return temp_bd


@app.get("/participant/{participant_id}")
def participant_get(participant_id: int) -> list[Participant]:
    return [participant for participant in temp_bd if participant.get("id") == participant_id]


@app.post("/participant")
def participant_create(participant: Participant) -> TypedDict('Response', {"status": int, "data": Participant}):
    participant_to_append = participant.model_dump()
    temp_bd.append(participant_to_append)
    return {"status": 200, "data": participant}


@app.delete("/participant/delete/{participant_id}")
def participant_delete(participant_id: int):
    for i, participant in enumerate(temp_bd):
        if participant.get("id") == participant_id:
            temp_bd.pop(i)
            break
    return {"status": 201, "message": "deleted"}


@app.put("/participant/{participant_id}")
def participant_update(participant_id: int, participant: Participant) -> list[Participant]:
    for part in temp_bd:
        if part.get("id") == participant_id:
            participant_to_append = participant.model_dump()
            temp_bd.remove(part)
            temp_bd.append(participant_to_append)
    return temp_bd