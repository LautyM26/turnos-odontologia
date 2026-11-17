"""Interpretación de respuestas y chatId -> E.164 (C-15 4.1, D6/D7). Funciones puras."""

import pytest

from app.domain.whatsapp.servicios import interpretar, telefono_de_chat_id


@pytest.mark.parametrize(
    ("texto", "intencion"),
    [
        ("Sí!", "confirmar"),
        ("SI, confirmo", "confirmar"),
        ("1", "confirmar"),
        (" 1. ", "confirmar"),
        ("confirmar", "confirmar"),
        ("Confirmo el turno", "confirmar"),
        ("2", "cancelar"),
        ("NO", "cancelar"),
        ("cancelo", "cancelar"),
        ("Cancelar por favor", "cancelar"),
        ("3", "reprogramar"),
        ("Reprogramar", "reprogramar"),
        ("cambiar", "reprogramar"),
        ("hola, ¿a qué hora era?", "desconocida"),
        ("", "desconocida"),
        ("👍", "desconocida"),
        ("12", "desconocida"),
        ("sino", "desconocida"),
    ],
)
def test_interpretar(texto: str, intencion: str) -> None:
    assert interpretar(texto) == intencion


@pytest.mark.parametrize(
    ("chat", "telefono"),
    [
        ("5491100000001@c.us", "+5491100000001"),
        ("120363000000000001@g.us", None),
        ("123456789012345@lid", None),
        ("abc@c.us", None),
        ("", None),
    ],
)
def test_telefono_de_chat_id(chat: str, telefono: str | None) -> None:
    assert telefono_de_chat_id(chat) == telefono
