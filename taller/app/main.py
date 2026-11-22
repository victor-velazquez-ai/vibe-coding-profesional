from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.database import Base, SessionLocal, engine, get_db
from app.deps import get_current_recruiter
from app.models import Candidate, Recruiter
from app.schemas import CandidateCreate, CandidateOut, Token
from app.security import create_access_token, verify_password
from app.seed import seed_if_empty


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_if_empty(db)
    finally:
        db.close()
    yield


app = FastAPI(title="Recruiting API", lifespan=lifespan)


@app.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    recruiter = db.query(Recruiter).filter(Recruiter.username == form_data.username).first()
    if recruiter is None or not verify_password(form_data.password, recruiter.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(subject=recruiter.username)
    return Token(access_token=access_token)


@app.get("/candidates", response_model=list[CandidateOut])
def list_candidates(
    db: Session = Depends(get_db),
    recruiter: Recruiter = Depends(get_current_recruiter),
):
    return (
        db.query(Candidate)
        .filter(Candidate.company_id == recruiter.company_id)
        .all()
    )


@app.post("/candidates", response_model=CandidateOut, status_code=status.HTTP_201_CREATED)
def create_candidate(
    candidate_in: CandidateCreate,
    db: Session = Depends(get_db),
    recruiter: Recruiter = Depends(get_current_recruiter),
):
    candidate = Candidate(**candidate_in.model_dump(), company_id=recruiter.company_id)
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return candidate
