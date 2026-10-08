"""Storage local de adjuntos (C-08 8.2): atómico, confinado al root, sin residuos."""

import re

import pytest

from app.infrastructure.storage.adjuntos import (
    ClaveInvalida,
    LocalDirStorage,
    generar_clave,
)


def test_guardar_abrir_roundtrip_bajo_root(tmp_path) -> None:  # type: ignore[no-untyped-def]
    storage = LocalDirStorage(tmp_path / "root")
    clave = generar_clave(3, 9)
    storage.guardar(clave, [b"abc", b"def"])
    with storage.abrir(clave) as fh:
        assert fh.read() == b"abcdef"
    escrito = (tmp_path / "root").joinpath(*clave.split("/"))
    assert escrito.is_file()
    assert escrito.resolve().is_relative_to((tmp_path / "root").resolve())


def test_clave_generada_en_servidor_con_formato_y_unica() -> None:
    a, b = generar_clave(1, 2), generar_clave(1, 2)
    assert a != b
    assert re.fullmatch(r"1/2/[0-9a-f]{32}", a)


@pytest.mark.parametrize("clave", ["../fuera", "1/../../fuera", "/abs/ruta", "a/b/../../../x", ""])
def test_clave_fuera_del_root_se_rechaza(tmp_path, clave) -> None:  # type: ignore[no-untyped-def]
    storage = LocalDirStorage(tmp_path / "root")
    with pytest.raises(ClaveInvalida):
        storage.guardar(clave, [b"x"])
    with pytest.raises(ClaveInvalida):
        storage.abrir(clave)
    assert not (tmp_path / "fuera").exists()


def test_eliminar_borra_y_es_idempotente(tmp_path) -> None:  # type: ignore[no-untyped-def]
    storage = LocalDirStorage(tmp_path / "root")
    clave = generar_clave(1, 1)
    storage.guardar(clave, [b"x"])
    storage.eliminar(clave)
    with pytest.raises(FileNotFoundError):
        storage.abrir(clave)
    storage.eliminar(clave)  # no falla


def test_error_a_mitad_de_escritura_no_deja_residuos(tmp_path) -> None:  # type: ignore[no-untyped-def]
    storage = LocalDirStorage(tmp_path / "root")
    clave = generar_clave(1, 1)

    def chunks():  # type: ignore[no-untyped-def]
        yield b"parcial"
        raise RuntimeError("corte")

    with pytest.raises(RuntimeError):
        storage.guardar(clave, chunks())
    archivos = [p for p in (tmp_path / "root").rglob("*") if p.is_file()]
    assert archivos == []
