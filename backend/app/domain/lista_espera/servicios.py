"""Lista de espera con relleno automático (C-16, RN-AG-06, Flujo 4).

Hueco liberado = turno ``cancelado`` (no sobreturno) que empieza con la anticipación mínima y
cuyo horario sigue libre (D1). Cada hueco se ofrece a una entrada por vez (D3); la oferta vence
y rota. Aceptar = claim de estado + ``crear_turno`` (D6): una sola reasignación por oferta.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, distinct, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from app.domain.agenda.models import Prestacion, Profesional, SillonRecurso
from app.domain.agenda.servicio import CatalogoError, Conflicto, NoEncontrado, ReferenciaInvalida
from app.domain.agenda.turnos import (
    Turno,
    crear_turno,
    horario_libre,
    transicionar_turno,
)
from app.domain.core.models import Clinica
from app.domain.lista_espera.models import ESTADOS_ACTIVOS, ListaEspera, OfertaListaEspera
from app.domain.pacientes.models import Paciente
from app.domain.whatsapp.models import MensajeWhatsApp
from app.domain.whatsapp.servicios import (
    despachar,
    enviar_texto_base,
    renderizar,
    renderizar_texto,
    variables_horario,
)
from app.infrastructure.persistence.repository import BaseRepository
from app.infrastructure.settings import Settings
from app.infrastructure.whatsapp.puerto import Mensajeria, NoConfigurado

UNIQUE_VIOLATION = "23505"
_TURNO_ADELANTABLE = ("reservado", "confirmado")


# --- Entradas (D2, D8) -----------------------------------------------------------------------


def _validar_preferencias(session: Session, clinica_id: int, datos: dict[str, Any]) -> None:
    if datos.get("profesional_id") is not None and (
        BaseRepository(session, Profesional, clinica_id).get(datos["profesional_id"]) is None
    ):
        raise ReferenciaInvalida("profesional_id inexistente, inactivo o de otra clinica")
    if datos.get("sillon_id") is not None and (
        BaseRepository(session, SillonRecurso, clinica_id).get(datos["sillon_id"]) is None
    ):
        raise ReferenciaInvalida("sillon_id inexistente, inactivo o de otra clinica")


def crear_entrada(
    session: Session, clinica_id: int, datos: dict[str, Any], ahora: datetime
) -> ListaEspera:
    """Anota al paciente; referencias inválidas o ajenas -> 422, entrada activa repetida -> 409."""
    if BaseRepository(session, Paciente, clinica_id).get(datos["paciente_id"]) is None:
        raise ReferenciaInvalida("paciente_id inexistente, inactivo o de otra clinica")
    if BaseRepository(session, Prestacion, clinica_id).get(datos["prestacion_id"]) is None:
        raise ReferenciaInvalida("prestacion_id inexistente, inactiva o de otra clinica")
    _validar_preferencias(session, clinica_id, datos)
    turno_id = datos.get("turno_a_adelantar_id")
    if turno_id is not None:
        turno = BaseRepository(session, Turno, clinica_id).get(turno_id)
        if (
            turno is None or turno.paciente_id != datos["paciente_id"]
            or turno.estado not in _TURNO_ADELANTABLE or turno.inicio <= ahora
        ):  # fmt: skip
            raise ReferenciaInvalida("turno_a_adelantar_id debe ser un turno futuro del paciente")
    entrada = ListaEspera(clinica_id=clinica_id, **datos)
    session.add(entrada)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        if getattr(exc.orig, "sqlstate", None) == UNIQUE_VIOLATION:
            raise Conflicto("El paciente ya está en la lista para esa prestación") from exc
        raise
    session.refresh(entrada)
    return entrada


def obtener_entrada(session: Session, clinica_id: int, entrada_id: int) -> ListaEspera:
    entrada = BaseRepository(session, ListaEspera, clinica_id).get(entrada_id)
    if entrada is None:
        raise NoEncontrado("No encontrado")
    return entrada


def listar_activas(
    session: Session, clinica_id: int, prestacion_id: int | None
) -> list[ListaEspera]:
    """Cola activa: prioridad descendente y, a igual prioridad, la más antigua primero."""
    stmt = select(ListaEspera).where(
        ListaEspera.clinica_id == clinica_id, ListaEspera.estado.in_(ESTADOS_ACTIVOS)
    )
    if prestacion_id is not None:
        stmt = stmt.where(ListaEspera.prestacion_id == prestacion_id)
    orden = (ListaEspera.prioridad.desc(), ListaEspera.created_at, ListaEspera.id)
    return list(session.scalars(stmt.order_by(*orden)))


def editar_entrada(
    session: Session, clinica_id: int, entrada_id: int, cambios: dict[str, Any]
) -> ListaEspera:
    entrada = obtener_entrada(session, clinica_id, entrada_id)
    if entrada.estado not in ESTADOS_ACTIVOS:
        raise NoEncontrado("No encontrado")
    _validar_preferencias(session, clinica_id, cambios)
    for campo, valor in cambios.items():
        setattr(entrada, campo, valor)
    session.commit()
    session.refresh(entrada)
    return entrada


def dar_de_baja(session: Session, clinica_id: int, entrada_id: int) -> None:
    """La entrada sale de la cola y su oferta pendiente (si la hay) queda anulada."""
    entrada = obtener_entrada(session, clinica_id, entrada_id)
    if entrada.estado not in ESTADOS_ACTIVOS:
        raise NoEncontrado("No encontrado")
    session.execute(
        update(OfertaListaEspera)
        .where(OfertaListaEspera.clinica_id == clinica_id,
               OfertaListaEspera.lista_espera_id == entrada_id,
               OfertaListaEspera.estado == "pendiente")
        .values(estado="anulada")
    )  # fmt: skip
    entrada.estado = "salido"
    session.commit()


# --- Huecos y candidatos (D1, D3) ------------------------------------------------------------


def _ofertas_pendientes_mismo_horario(hueco: Any) -> Any:
    return select(OfertaListaEspera.id).where(
        OfertaListaEspera.clinica_id == hueco.clinica_id,
        OfertaListaEspera.profesional_id == hueco.profesional_id,
        OfertaListaEspera.inicio == hueco.inicio,
        OfertaListaEspera.estado == "pendiente",
    )


def es_hueco_liberado(session: Session, turno: Turno, ahora: datetime, anticipacion: int) -> bool:
    """Cancelado, no sobreturno, con anticipación, sin oferta en curso y con el horario libre."""
    return (
        turno.estado == "cancelado" and turno.is_active and not turno.es_sobreturno
        and turno.inicio >= ahora + timedelta(minutes=anticipacion)
        and session.scalars(_ofertas_pendientes_mismo_horario(turno).limit(1)).first() is None
        and horario_libre(session, turno.clinica_id, turno.inicio, turno.fin,
                          turno.profesional_id, turno.sillon_id)
    )  # fmt: skip


def huecos_liberados(session: Session, ahora: datetime, anticipacion: int) -> list[Turno]:
    """Huecos de todas las clínicas, por inicio; un horario repetido se ofrece una sola vez."""
    pendiente = (
        select(OfertaListaEspera.id)
        .where(OfertaListaEspera.clinica_id == Turno.clinica_id,
               OfertaListaEspera.profesional_id == Turno.profesional_id,
               OfertaListaEspera.inicio == Turno.inicio,
               OfertaListaEspera.estado == "pendiente")
    )  # fmt: skip
    candidatos = session.scalars(
        select(Turno)
        .where(Turno.estado == "cancelado", Turno.is_active.is_(True),
               Turno.es_sobreturno.is_(False),
               Turno.inicio >= ahora + timedelta(minutes=anticipacion), ~pendiente.exists())
        .order_by(Turno.inicio, Turno.id)
    ).all()  # fmt: skip
    vistos: set[tuple[int, int, datetime]] = set()
    huecos = []
    for t in candidatos:
        clave = (t.clinica_id, t.profesional_id, t.inicio)
        if clave in vistos:
            continue
        vistos.add(clave)
        if horario_libre(session, t.clinica_id, t.inicio, t.fin, t.profesional_id, t.sillon_id):
            huecos.append(t)
    return huecos


def _filtro_candidato(hueco: Turno) -> list[Any]:
    adelantar = aliased(Turno)
    ya_ofrecido = select(OfertaListaEspera.id).where(
        OfertaListaEspera.clinica_id == ListaEspera.clinica_id,
        OfertaListaEspera.lista_espera_id == ListaEspera.id,
        OfertaListaEspera.turno_liberado_id == hueco.id,
    )
    turno_posterior = select(adelantar.id).where(
        adelantar.clinica_id == ListaEspera.clinica_id,
        adelantar.id == ListaEspera.turno_a_adelantar_id,
        adelantar.is_active.is_(True), adelantar.estado.in_(_TURNO_ADELANTABLE),
        adelantar.inicio > hueco.inicio,
    )  # fmt: skip
    return [
        ListaEspera.clinica_id == hueco.clinica_id,
        ListaEspera.prestacion_id == hueco.prestacion_id,
        or_(ListaEspera.profesional_id.is_(None),
            ListaEspera.profesional_id == hueco.profesional_id),
        or_(ListaEspera.sillon_id.is_(None), ListaEspera.sillon_id == hueco.sillon_id),
        ListaEspera.paciente_id != hueco.paciente_id,
        Paciente.is_active.is_(True), Paciente.telefono.is_not(None),
        ~ya_ofrecido.exists(),
        or_(ListaEspera.turno_a_adelantar_id.is_(None), turno_posterior.exists()),
    ]  # fmt: skip


def _join_paciente(stmt: Any) -> Any:
    return stmt.join(
        Paciente,
        and_(Paciente.clinica_id == ListaEspera.clinica_id, Paciente.id == ListaEspera.paciente_id),
    )


def elegir_candidato(session: Session, hueco: Turno) -> ListaEspera | None:
    """La entrada en cola que coincide, de mayor prioridad y más antigua (D3)."""
    stmt = _join_paciente(select(ListaEspera)).where(
        ListaEspera.estado == "en_cola", *_filtro_candidato(hueco)
    )
    orden = (ListaEspera.prioridad.desc(), ListaEspera.created_at, ListaEspera.id)
    return session.scalars(stmt.order_by(*orden).limit(1)).first()


def entrada_puede_recibir(session: Session, entrada: ListaEspera, hueco: Turno) -> bool:
    stmt = _join_paciente(select(ListaEspera.id)).where(
        ListaEspera.id == entrada.id, *_filtro_candidato(hueco)
    )
    return session.scalars(stmt).first() is not None


# --- Oferta (D4) -----------------------------------------------------------------------------


def ofertar(
    session: Session, mensajeria: Mensajeria | NoConfigurado, settings: Settings,
    entrada: ListaEspera, hueco: Turno, ahora: datetime,
) -> tuple[OfertaListaEspera | None, bool]:  # fmt: skip
    """Crea la oferta (UNIQUE como claim) y envía ``oferta_hueco``.

    Devuelve ``(oferta, enviada)``; ``(None, True)`` si otro proceso ganó el hueco o la entrada.
    Si el envío falla, la oferta queda ``anulada`` y la entrada vuelve a la cola.
    """
    paciente = session.get(Paciente, entrada.paciente_id)
    assert paciente is not None and paciente.telefono is not None
    texto = renderizar_texto(
        session, "oferta_hueco",
        variables_horario(session, hueco.clinica_id, entrada.paciente_id, hueco.profesional_id,
                          hueco.inicio),
    )  # fmt: skip
    oferta = OfertaListaEspera(
        clinica_id=hueco.clinica_id, lista_espera_id=entrada.id, turno_liberado_id=hueco.id,
        inicio=hueco.inicio, fin=hueco.fin, profesional_id=hueco.profesional_id,
        sillon_id=hueco.sillon_id, prestacion_id=hueco.prestacion_id, estado="pendiente",
        expira_at=ahora + timedelta(minutes=settings.lista_espera_oferta_min),
    )  # fmt: skip
    msg = MensajeWhatsApp(
        clinica_id=hueco.clinica_id, paciente_id=entrada.paciente_id, plantilla="oferta_hueco",
        direccion="saliente", telefono=paciente.telefono, estado="pendiente", texto=texto,
    )  # fmt: skip
    session.add_all([oferta, msg])
    entrada.estado = "ofertado"
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        if getattr(exc.orig, "sqlstate", None) == UNIQUE_VIOLATION:
            return None, True
        raise
    oferta.mensaje_id = msg.id
    session.commit()
    if despachar(session, mensajeria, msg, settings.ars_precio_mensaje):
        return oferta, True
    oferta.estado, entrada.estado = "anulada", "en_cola"
    session.commit()
    return oferta, False


def vencer_ofertas(session: Session, ahora: datetime) -> int:
    """Ofertas pendientes vencidas -> ``expirada``; sus entradas vuelven a la cola."""
    entradas = session.scalars(
        update(OfertaListaEspera)
        .where(OfertaListaEspera.estado == "pendiente", OfertaListaEspera.expira_at <= ahora)
        .values(estado="expirada")
        .returning(OfertaListaEspera.lista_espera_id)
    ).all()
    if entradas:
        session.execute(
            update(ListaEspera)
            .where(ListaEspera.id.in_(entradas), ListaEspera.estado == "ofertado")
            .values(estado="en_cola")
        )
    session.commit()
    return len(entradas)


def ofertar_manual(
    session: Session, mensajeria: Mensajeria | NoConfigurado, settings: Settings,
    clinica_id: int, entrada_id: int, turno_liberado_id: int, ahora: datetime,
) -> OfertaListaEspera:  # fmt: skip
    """Recepción elige a quién ofrecer un hueco puntual (D7); respeta coincidencia y reglas."""
    entrada = obtener_entrada(session, clinica_id, entrada_id)
    hueco = BaseRepository(session, Turno, clinica_id).get(turno_liberado_id)
    if hueco is None or entrada.estado != "en_cola":
        raise ReferenciaInvalida("La entrada no está en cola o el hueco no existe")
    pendiente = session.scalars(_ofertas_pendientes_mismo_horario(hueco).limit(1)).first()
    if pendiente is not None:
        raise Conflicto("El hueco ya tiene una oferta en curso")
    anticipacion = settings.lista_espera_anticipacion_min
    if not es_hueco_liberado(session, hueco, ahora, anticipacion):
        raise ReferenciaInvalida("El turno no es un hueco liberado ofrecible")
    if not entrada_puede_recibir(session, entrada, hueco):
        raise ReferenciaInvalida("La entrada no coincide con el hueco")
    oferta, enviada = ofertar(session, mensajeria, settings, entrada, hueco, ahora)
    if oferta is None:
        raise Conflicto("El hueco ya tiene una oferta en curso")
    if not enviada:
        raise CanalNoDisponible("No se pudo enviar la oferta por WhatsApp")
    return oferta


class CanalNoDisponible(CatalogoError):
    status_code = 502


# --- Respuestas (D6) -------------------------------------------------------------------------


def _no_disponible(
    session: Session, mensajeria: Mensajeria | NoConfigurado, oferta: OfertaListaEspera,
    entrada: ListaEspera, telefono: str, precio: Decimal,
) -> str:  # fmt: skip
    texto = renderizar_texto(
        session, "oferta_no_disponible",
        variables_horario(session, oferta.clinica_id, entrada.paciente_id, oferta.profesional_id,
                          oferta.inicio),
    )  # fmt: skip
    enviar_texto_base(session, mensajeria, oferta.clinica_id, "oferta_no_disponible", texto,
                      entrada.paciente_id, telefono, precio)  # fmt: skip
    return "oferta_no_disponible"


def aceptar_oferta(
    session: Session, clinica_id: int, oferta_id: int, telefono: str, ahora: datetime,
    mensajeria: Mensajeria | NoConfigurado, precio: Decimal,
) -> str:  # fmt: skip
    """Claim ``pendiente -> aceptada`` y después ``crear_turno`` (D6).

    ``crear_turno`` hace commit adentro, así que un lock de fila no sobreviviría: el claim de
    estado garantiza una sola reasignación aunque lleguen aceptaciones simultáneas.
    """
    gano = session.execute(
        update(OfertaListaEspera)
        .where(OfertaListaEspera.clinica_id == clinica_id, OfertaListaEspera.id == oferta_id,
               OfertaListaEspera.estado == "pendiente", OfertaListaEspera.expira_at > ahora)
        .values(estado="aceptada", respondida_at=ahora)
        .returning(OfertaListaEspera.id)
    ).first()  # fmt: skip
    session.commit()
    oferta = session.get(OfertaListaEspera, oferta_id, populate_existing=True)
    assert oferta is not None
    entrada = session.get(ListaEspera, oferta.lista_espera_id)
    assert entrada is not None
    if gano is None:
        if oferta.estado == "aceptada":
            return "sin_efecto"  # aceptación repetida: ya se reasignó
        if oferta.estado == "pendiente":  # vencida, el job todavía no pasó
            oferta.estado = "expirada"
            if entrada.estado == "ofertado":
                entrada.estado = "en_cola"
            session.commit()
        return _no_disponible(session, mensajeria, oferta, entrada, telefono, precio)
    datos = {"profesional_id": oferta.profesional_id, "sillon_id": oferta.sillon_id,
             "paciente_id": entrada.paciente_id, "prestacion_id": oferta.prestacion_id,
             "inicio": oferta.inicio}  # fmt: skip
    try:
        turno = crear_turno(session, clinica_id, datos, ahora=ahora, origen="lista_espera")
    except CatalogoError:  # 409 (hueco tomado en el medio) o 422 (referencias que cambiaron)
        session.rollback()
        oferta.estado, oferta.respondida_at = "anulada", ahora
        entrada.estado = "en_cola"
        session.commit()
        return _no_disponible(session, mensajeria, oferta, entrada, telefono, precio)
    oferta.turno_creado_id = turno.id
    entrada.estado = "aceptado"
    session.commit()
    if entrada.turno_a_adelantar_id is not None:
        try:
            transicionar_turno(
                session, clinica_id, entrada.turno_a_adelantar_id, "cancelado", actor_id=None,
                motivo="adelantado por lista de espera", ahora=ahora,
                actor_tipo="paciente_whatsapp",
            )  # fmt: skip
        except CatalogoError:  # ya no es cancelable (asistido, cancelado): nada que liberar
            session.rollback()
    texto = renderizar(session, clinica_id, "oferta_aceptada", turno.id)
    enviar_texto_base(session, mensajeria, clinica_id, "oferta_aceptada", texto,
                      entrada.paciente_id, telefono, precio, turno_id=turno.id)  # fmt: skip
    return "oferta_aceptada"


def rechazar_oferta(session: Session, clinica_id: int, oferta_id: int, ahora: datetime) -> str:
    """``pendiente -> rechazada``; la entrada vuelve a la cola, sin respuesta automática."""
    entrada_id = session.scalar(
        update(OfertaListaEspera)
        .where(OfertaListaEspera.clinica_id == clinica_id, OfertaListaEspera.id == oferta_id,
               OfertaListaEspera.estado == "pendiente")
        .values(estado="rechazada", respondida_at=ahora)
        .returning(OfertaListaEspera.lista_espera_id)
    )  # fmt: skip
    if entrada_id is not None:
        session.execute(
            update(ListaEspera)
            .where(ListaEspera.id == entrada_id, ListaEspera.estado == "ofertado")
            .values(estado="en_cola")
        )
    session.commit()
    return "oferta_rechazada" if entrada_id is not None else "sin_efecto"


def responder_oferta(
    session: Session, clinica_id: int, oferta_id: int, intencion: str, telefono: str,
    ahora: datetime, mensajeria: Mensajeria | NoConfigurado, precio: Decimal,
) -> str:  # fmt: skip
    if intencion == "confirmar":
        return aceptar_oferta(session, clinica_id, oferta_id, telefono, ahora, mensajeria, precio)
    return rechazar_oferta(session, clinica_id, oferta_id, ahora)


# --- Bandeja y métricas (D8) -----------------------------------------------------------------


def bandeja(
    session: Session, clinica_id: int, limit: int
) -> list[tuple[OfertaListaEspera, int, str]]:
    """Ofertas recientes: ``(oferta, paciente_id, nombre del paciente)``."""
    filas = session.execute(
        select(OfertaListaEspera, ListaEspera.paciente_id,
               func.concat_ws(" ", Paciente.nombre, Paciente.apellido))
        .join(ListaEspera, (ListaEspera.clinica_id == OfertaListaEspera.clinica_id)
              & (ListaEspera.id == OfertaListaEspera.lista_espera_id))
        .join(Paciente, (Paciente.clinica_id == ListaEspera.clinica_id)
              & (Paciente.id == ListaEspera.paciente_id))
        .where(OfertaListaEspera.clinica_id == clinica_id)
        .order_by(OfertaListaEspera.created_at.desc(), OfertaListaEspera.id.desc())
        .limit(limit)
    ).all()  # fmt: skip
    return [(o, pid, nombre) for o, pid, nombre in filas]


def metricas(session: Session, clinica_id: int, desde: date, hasta: date) -> dict[str, int]:
    """Huecos liberados (cancelados, no sobreturno) por fecha local del hueco; recuperados = con
    oferta aceptada que creó turno; perdidos = el resto."""
    dia = func.date(func.timezone(Clinica.zona_horaria, Turno.inicio))
    base = (
        select(Turno.id)
        .join(Clinica, Clinica.id == Turno.clinica_id)
        .where(Turno.clinica_id == clinica_id, Turno.estado == "cancelado",
               Turno.is_active.is_(True), Turno.es_sobreturno.is_(False),
               dia.between(desde, hasta))
    ).subquery()  # fmt: skip
    liberados = session.scalar(select(func.count()).select_from(base)) or 0
    recuperados = session.scalar(
        select(func.count(distinct(OfertaListaEspera.turno_liberado_id))).where(
            OfertaListaEspera.clinica_id == clinica_id,
            OfertaListaEspera.turno_liberado_id.in_(select(base.c.id)),
            OfertaListaEspera.turno_creado_id.is_not(None),
        )
    ) or 0
    return {"liberados": liberados, "recuperados": recuperados,
            "perdidos": liberados - recuperados}  # fmt: skip

