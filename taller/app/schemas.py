from pydantic import BaseModel, ConfigDict


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class CandidateBase(BaseModel):
    name: str
    position: str
    stage: str
    notes: str = ""


class CandidateCreate(CandidateBase):
    pass


class CandidateOut(CandidateBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
