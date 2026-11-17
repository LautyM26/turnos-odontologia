"""Helpers sintéticos de la lista de espera (C-16). Regla dura 14.

Aislamiento entre tests del mismo módulo: cada escenario usa su propio "ahora" (10 días de
separación, así los huecos de otros tests ya pasaron) y una prestación nueva (así las entradas
de otros tests no coinciden).
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from itertools import count
from uuid import uuid4

from app.domain.agenda.models import Prestacion
from app.domain.agenda.turnos import Turno
from app.domain.lista_espera.models import ListaEspera
from app.domain.whatsapp.servicios import procesar_mensaje_entrante
from tests.integration.conftest import paciente_sintetico
from tests.integration.conftest_whatsapp import nuevo_ahora, settings_wa, telefono_unico

_prest = count(1)


@dataclass
class Escenario:
    sf: object
    td: dict
    ahora: datetime
    prest: int
    clinica: str = "a"

    @property
    def c(self) -> int:
        return self.td[self.clinica]

    def paciente(self, telefono: str | None = "auto") -> tuple[int, str | None]:
        tel = telefono_unico() if telefono == "auto" else telefono
        extra = {"telefono": tel} if tel else {"telefono": None, "email": "le@test.test"}
        with self.sf() as s:  # type: ignore[attr-defined]
            p = paciente_sintetico(self.c, **extra)
            s.add(p)
            s.commit()
            return p.id, tel

    def turno(self, horas: float, paciente_id: int, estado: str = "reservado",
              prof: str = "p", sillon: str = "s1") -> int:  # fmt: skip
        inicio = self.ahora + timedelta(hours=horas)
        if self.clinica == "a":
            refs = {"profesional_id": self.td[prof], "sillon_id": self.td[sillon]}
        else:
            refs = {"profesional_id": self.td["prof_b"], "sillon_id": self.td["sillon_b"]}
        with self.sf() as s:  # type: ignore[attr-defined]
            t = Turno(clinica_id=self.c, paciente_id=paciente_id, prestacion_id=self.prest,
                      duracion_min=30, inicio=inicio, fin=inicio + timedelta(minutes=30),
                      estado=estado, **refs)  # fmt: skip
            s.add(t)
            s.commit()
            return t.id

    def hueco(self, horas: float = 20, **kw) -> int:
        """Turno cancelado de un paciente cualquiera: el hueco liberado."""
        pid, _ = self.paciente()
        return self.turno(horas, pid, estado="cancelado", **kw)

    def entrada(self, paciente_id: int, **kw) -> int:
        with self.sf() as s:  # type: ignore[attr-defined]
            e = ListaEspera(clinica_id=self.c, paciente_id=paciente_id, prestacion_id=self.prest,
                            **kw)  # fmt: skip
            s.add(e)
            s.commit()
            return e.id


def escenario(session_factory, td, clinica: str = "a") -> Escenario:  # type: ignore[no-untyped-def]
    with session_factory() as s:
        prest = Prestacion(clinica_id=td[clinica], nombre=f"Prestacion LE {next(_prest)}",
                           duracion_min=30, precio_referencia=Decimal("1000.00"))  # fmt: skip
        s.add(prest)
        s.commit()
        return Escenario(session_factory, td, nuevo_ahora(), prest.id, clinica)


def settings_le(**kw):  # type: ignore[no-untyped-def]
    base = {"lista_espera_oferta_min": 30, "lista_espera_anticipacion_min": 120}
    base.update(kw)
    return settings_wa(**base)


def responder(e: Escenario, telefono: str, texto: str, ahora: datetime, fake,  # type: ignore[no-untyped-def]
              id_externo: str | None = None) -> str:  # fmt: skip
    with e.sf() as s:  # type: ignore[attr-defined]
        return procesar_mensaje_entrante(
            s, e.c, id_externo or f"IN-{uuid4()}", telefono, texto, ahora, fake,
            Decimal("12.50"),
        )  # fmt: skip
