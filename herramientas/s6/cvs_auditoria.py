"""CVs de auditoría para la frontera de pseudonimización (S6 · 6.1). SINTÉTICOS y ficticios.

No son fixtures de los tests: son los CVs que un senior le pasa al pseudonimizador DESPUÉS
de que los tests están en verde, con los formatos que aparecen en CVs reales de EE.UU. y México
(Northstar contrata en Texas y Nueva York; Meridian opera en Dallas y Monterrey).

Cada CV trae sus campos estructurados (lo que la plataforma ya sabe del candidato) y su texto
libre. `pii` es la lista de cadenas que NO pueden llegar al proveedor. Correos en example.com,
teléfonos con 555 / 0000.
"""

CVS = [
    {
        "id": "a01-nombre-invertido",
        "campos": {"nombre": "María José Hernández Garza", "correo": "mj.hernandez@example.com", "telefono": "+1 512 555 0147", "links": ["https://www.linkedin.com/in/mjhernandez"]},
        "texto": "HERNÁNDEZ GARZA, María José\nEnfermera registrada (RN) · Austin, TX\n\nExperiencia\n- 2019–hoy · Enfermera de terapia intensiva en St. Elian Medical Center. Cuidado de 4 a 6 pacientes por turno.\n- 2015–2019 · Enfermera de urgencias en Hospital Ángeles.\n\nLicencia RN de Texas activa. BLS y ACLS vigentes.",
        "pii": ["HERNÁNDEZ GARZA", "María José"],
    },
    {
        "id": "a02-nombre-sin-acentos",
        "campos": {"nombre": "José Ángel Treviño", "correo": "jose.trevino@example.com", "telefono": "+1 214 555 0199", "links": []},
        "texto": "Jose Angel Trevino — Coordinador administrativo\n\nResumen: 8 años en administración hospitalaria, agendas médicas y facturación a aseguradoras.\nReferencias: disponibles a solicitud de Jose Trevino.",
        "pii": ["Jose Angel Trevino", "Jose Trevino"],
    },
    {
        "id": "a03-telefonos-variados",
        "campos": {"nombre": "Daniel Okafor", "correo": "d.okafor@example.com", "telefono": "+1 512 555 0123", "links": []},
        "texto": "Daniel Okafor\nIT Support Specialist\nPhone: (512) 555-0123 · Alt: 512.555.0188 ext. 23\n\n- 2020–present · Help desk lead at Lone Star Clinics: 300 users, Active Directory, Intune.",
        "pii": ["Daniel Okafor", "(512) 555-0123", "512.555.0188"],
    },
    {
        "id": "a04-telefono-mexico",
        "campos": {"nombre": "Ana Lucía Garza", "correo": "analucia.garza@example.com", "telefono": "+52 81 0000 4455", "links": []},
        "texto": "Ana Lucía Garza\nAuxiliar de enfermería · Monterrey, N.L.\nCel. 81 0000 4455 · WhatsApp +52 1 81 0000 4466\n\nExperiencia en hospitalización y curaciones.",
        "pii": ["Ana Lucía Garza", "81 0000 4455", "+52 1 81 0000 4466"],
    },
    {
        "id": "a05-correo-ofuscado",
        "campos": {"nombre": "Priscila Moreno", "correo": "priscila.moreno@example.com", "telefono": "+1 713 555 0110", "links": []},
        "texto": "Priscila Moreno · Medical Billing\nContacto: priscila.moreno [at] example.com o pmoreno(arroba)example.com\n\n- 6 años en facturación médica y codificación CPT/ICD-10.",
        "pii": ["Priscila Moreno", "priscila.moreno [at] example.com", "pmoreno(arroba)example.com"],
    },
    {
        "id": "a06-links-sin-esquema",
        "campos": {"nombre": "Kevin Liu", "correo": "kevin.liu@example.com", "telefono": "+1 646 555 0175", "links": ["https://github.com/kevinliu-dev"]},
        "texto": "Kevin Liu — Systems Analyst\nlinkedin.com/in/kevin-liu-analyst · github.com/kevinliu-dev · kevinliu.dev\n\n- 2018–present · EHR integrations (HL7, FHIR) at Hudson Valley Health.",
        "pii": ["Kevin Liu", "linkedin.com/in/kevin-liu-analyst", "github.com/kevinliu-dev", "kevinliu.dev"],
    },
    {
        "id": "a07-direccion-eeuu",
        "campos": {"nombre": "Rachel Stein", "correo": "rachel.stein@example.com", "telefono": "+1 917 555 0142", "links": []},
        "texto": "Rachel Stein, RN\n4512 Duval St, Apt 3B, Austin, TX 78751\n\nCharge nurse, med-surg, 7 years. Compact license (NLC).",
        "pii": ["Rachel Stein", "4512 Duval St", "Apt 3B"],
    },
    {
        "id": "a08-direccion-mexico",
        "campos": {"nombre": "Luis Fernando Cantú", "correo": "lf.cantu@example.com", "telefono": "+52 81 0000 7788", "links": []},
        "texto": "Luis Fernando Cantú\nAv. Constitución 450 Pte., Col. Centro, C.P. 64000, Monterrey, N.L.\n\nTécnico en sistemas: soporte, redes y altas de usuarios en clínica de 80 camas.",
        "pii": ["Luis Fernando Cantú", "Av. Constitución 450 Pte.", "Col. Centro"],
    },
    {
        "id": "a09-foto",
        "campos": {"nombre": "Sofía Ramírez", "correo": "sofia.ramirez@example.com", "telefono": "+1 210 555 0166", "links": []},
        "texto": "![Foto de Sofía Ramírez](https://example.com/fotos/sofia-ramirez.jpg)\nSofía Ramírez — Recepcionista clínica\n[Foto adjunta: sofia_ramirez_2026.png]\n\n- 4 años en recepción de consultorio, agenda y verificación de seguros.",
        "pii": ["Sofía Ramírez", "https://example.com/fotos/sofia-ramirez.jpg", "sofia_ramirez_2026.png"],
    },
    {
        "id": "a10-nombre-de-pila-en-narrativa",
        "campos": {"nombre": "Patricia Elena Villarreal", "correo": "pevillarreal@example.com", "telefono": "+1 956 555 0133", "links": []},
        "texto": "Perfil profesional\nMe llamo Patricia Villarreal y soy enfermera pediátrica. Mis compañeros me dicen Paty.\n\n- 2016–hoy · Pediatría en Valley Children's Hospital.\n\nCarta de recomendación: \"Patricia es la enfermera más confiable del turno\".",
        "pii": ["Patricia Villarreal", "Patricia"],
    },
]
