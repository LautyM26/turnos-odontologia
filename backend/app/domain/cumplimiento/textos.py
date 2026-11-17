"""Textos de consentimiento versionados (C-18, D2).

Cada texto es un borrador con marcadores ``[A completar ...]`` y debe validarse con asesoría
legal (SU-08 / PA-04). Cambiar un texto exige subir su versión: el test de snapshot lo fuerza.
Los documentos ya generados guardan su propia copia, así que no cambian.
"""

AVISO = "Texto base a validar con asesoría legal"

TIPOS = ("tratamiento_general", "extraccion", "endodoncia", "implante", "anestesia")


def _texto(titulo: str, cuerpo: str) -> str:
    return (
        f"{AVISO}\n\nConsentimiento informado: {titulo}\n\n{cuerpo}\n\n"
        "He recibido información clara sobre el procedimiento, sus riesgos y las alternativas, "
        "y pude hacer preguntas. Entiendo que puedo revocar este consentimiento antes del "
        "procedimiento. Responsable del tratamiento: [A completar: responsable y contacto]."
    )


#: tipo -> (version, texto)
CATALOGO: dict[str, tuple[str, str]] = {
    "tratamiento_general": (
        "1.0",
        _texto(
            "tratamiento odontológico general",
            "Autorizo al profesional a realizar el diagnóstico y los tratamientos odontológicos "
            "acordados en la consulta [A completar: detalle del plan de tratamiento].",
        ),
    ),
    "extraccion": (
        "1.0",
        _texto(
            "extracción dental",
            "Autorizo la extracción de la pieza dental indicada [A completar: pieza FDI]. "
            "Riesgos habituales: dolor, inflamación, sangrado y, en casos poco frecuentes, "
            "infección o lesión de estructuras vecinas.",
        ),
    ),
    "endodoncia": (
        "1.0",
        _texto(
            "tratamiento de conducto (endodoncia)",
            "Autorizo el tratamiento de conducto de la pieza indicada [A completar: pieza FDI]. "
            "Riesgos habituales: molestias posteriores, necesidad de retratamiento y, en casos "
            "poco frecuentes, fractura de instrumental o de la pieza.",
        ),
    ),
    "implante": (
        "1.0",
        _texto(
            "implante dental",
            "Autorizo la colocación de un implante dental [A completar: zona y plan]. "
            "Riesgos habituales: inflamación, infección, falta de integración del implante y "
            "necesidad de procedimientos adicionales.",
        ),
    ),
    "anestesia": (
        "1.0",
        _texto(
            "anestesia local",
            "Autorizo la aplicación de anestesia local. Informé mis alergias y medicación "
            "habitual. Riesgos habituales: adormecimiento prolongado, hematoma y, en casos poco "
            "frecuentes, reacción alérgica.",
        ),
    ),
}
