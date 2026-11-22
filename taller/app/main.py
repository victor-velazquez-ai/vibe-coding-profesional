from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_recruiter
from app.logging_config import configure_logging, get_logger
from app.middleware import RequestIdMiddleware
from app.models import Candidate, Recruiter
from app.schemas import CandidateCreate, CandidateOut, Token
from app.security import create_access_token, verify_password

configure_logging()
logger = get_logger("app.api")

# El esquema de la base lo gestiona Alembic (`poe migrate`), no `create_all`.
# Los datos de prueba se cargan con `poe seed`.
app = FastAPI(title="Recruiting API")
app.add_middleware(RequestIdMiddleware)


@app.post("/login", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> Token:
    recruiter = db.query(Recruiter).filter(Recruiter.username == form_data.username).first()
    if recruiter is None or not verify_password(form_data.password, recruiter.hashed_password):
        logger.warning("login_failed", extra={"context": {"username": form_data.username}})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(subject=recruiter.username)
    logger.info("login_succeeded", extra={"context": {"username": recruiter.username}})
    return Token(access_token=access_token)


@app.get("/candidates", response_model=list[CandidateOut])
def list_candidates(
    db: Session = Depends(get_db),
    recruiter: Recruiter = Depends(get_current_recruiter),
) -> list[Candidate]:
    return db.query(Candidate).filter(Candidate.company_id == recruiter.company_id).all()


@app.post("/candidates", response_model=CandidateOut, status_code=status.HTTP_201_CREATED)
def create_candidate(
    candidate_in: CandidateCreate,
    db: Session = Depends(get_db),
    recruiter: Recruiter = Depends(get_current_recruiter),
) -> Candidate:
    candidate = Candidate(**candidate_in.model_dump(), company_id=recruiter.company_id)
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    logger.info(
        "candidate_created",
        extra={"context": {"candidate_id": candidate.id, "company_id": candidate.company_id}},
    )
    return candidate
