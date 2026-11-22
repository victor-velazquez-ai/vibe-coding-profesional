from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, HTTPException, Query, status
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

# Las fechas que pide una reclutadora son días de Austin, no de UTC (issue #6).
ZONA_NEGOCIO = ZoneInfo("America/Chicago")
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
    stage: str | None = Query(default=None),
    created_from: date | None = Query(default=None),
    created_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
    recruiter: Recruiter = Depends(get_current_recruiter),
) -> list[Candidate]:
    query = db.query(Candidate).filter(Candidate.company_id == recruiter.company_id)
    if stage is not None:
        query = query.filter(Candidate.stage == stage)
    if created_from is not None:
        desde = datetime.combine(created_from, time.min, ZONA_NEGOCIO)
        query = query.filter(Candidate.created_at >= desde)
    if created_to is not None:
        # Extremo incluido: todo el día `created_to`, hasta antes de la medianoche siguiente.
        hasta = datetime.combine(created_to + timedelta(days=1), time.min, ZONA_NEGOCIO)
        query = query.filter(Candidate.created_at < hasta)
    return query.all()


@app.get("/candidates/{candidate_id}", response_model=CandidateOut)
def get_candidate(
    candidate_id: int,
    db: Session = Depends(get_db),
    recruiter: Recruiter = Depends(get_current_recruiter),
) -> Candidate:
    candidate = (
        db.query(Candidate)
        .filter(Candidate.id == candidate_id, Candidate.company_id == recruiter.company_id)
        .first()
    )
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidato no encontrado")
    logger.info(
        "candidate_viewed",
        extra={"context": {"candidate_id": candidate.id, "recruiter": recruiter.username}},
    )
    return candidate


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
