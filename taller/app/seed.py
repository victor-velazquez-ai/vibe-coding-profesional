"""Datos de prueba. Se cargan a mano con `poe seed`, nunca al importar la app."""

from sqlalchemy.orm import Session

from app.database import get_sessionmaker
from app.models import Candidate, Company, Recruiter
from app.security import hash_password


def seed_if_empty(db: Session) -> bool:
    """Crea empresas, reclutadores y candidatos de ejemplo.

    Devuelve True si ha insertado algo, False si la base ya tenia datos.
    """
    if db.query(Company).first() is not None:
        return False

    meridian = Company(name="Meridian Logistics")
    northstar = Company(name="Northstar Health")
    db.add_all([meridian, northstar])
    db.flush()

    sofia = Recruiter(
        username="sofia",
        hashed_password=hash_password("sofia1234"),
        company_id=meridian.id,
    )
    marcus = Recruiter(
        username="marcus",
        hashed_password=hash_password("marcus1234"),
        company_id=northstar.id,
    )
    db.add_all([sofia, marcus])

    meridian_candidates = [
        Candidate(
            name="Diana Ortiz",
            position="Coordinadora de flota",
            stage="Entrevista técnica",
            notes="pide 120 mil dólares; tiene otra oferta",
            company_id=meridian.id,
        ),
        Candidate(
            name="Diego Fernández",
            position="Analista de operaciones",
            stage="Preseleccionado",
            notes="Disponible para empezar en dos semanas",
            company_id=meridian.id,
        ),
    ]

    northstar_candidates = [
        Candidate(
            name="Priya Nair",
            position="Enfermera registrada",
            stage="Entrevista con gerente",
            notes="Referida por un empleado actual",
            company_id=northstar.id,
        ),
        Candidate(
            name="Tom Alvarez",
            position="Técnico de laboratorio",
            stage="Oferta enviada",
            notes="Esperando respuesta antes del viernes",
            company_id=northstar.id,
        ),
    ]

    db.add_all(meridian_candidates + northstar_candidates)
    db.commit()
    return True


def main() -> None:
    with get_sessionmaker()() as db:
        inserted = seed_if_empty(db)
    if inserted:
        print("Datos de prueba creados (sofia / marcus).")
    else:
        print("La base ya tenia datos: no se ha tocado nada.")


if __name__ == "__main__":
    main()
