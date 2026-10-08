"""Abstracción de storage de adjuntos y backend de directorio local (C-08, D9)."""

import contextlib
import os
import uuid
from collections.abc import Iterable
from pathlib import Path
from typing import BinaryIO, Protocol


class ClaveInvalida(ValueError):
    """La clave resuelve fuera del root del storage."""


class AdjuntoStorage(Protocol):
    """Contrato mínimo; nuevos proveedores (S3, GCS) implementan estos tres métodos."""

    def guardar(self, clave: str, chunks: Iterable[bytes]) -> None: ...

    def abrir(self, clave: str) -> BinaryIO: ...

    def eliminar(self, clave: str) -> None: ...


def generar_clave(clinica_id: int, paciente_id: int) -> str:
    """Clave generada en servidor: ``{clinica}/{paciente}/{uuid4 hex}`` (nunca el nombre)."""
    return f"{clinica_id}/{paciente_id}/{uuid.uuid4().hex}"


class LocalDirStorage:
    """Archivos bajo ``root``; escritura atómica (temporal + ``os.replace``)."""

    def __init__(self, root: Path) -> None:
        self._root = Path(root).resolve()

    def _ruta(self, clave: str) -> Path:
        if not clave or clave.startswith(("/", "\\")):
            raise ClaveInvalida("clave inválida")
        ruta = (self._root / clave).resolve()
        if not ruta.is_relative_to(self._root) or ruta == self._root:
            raise ClaveInvalida("clave fuera del directorio de adjuntos")
        return ruta

    def guardar(self, clave: str, chunks: Iterable[bytes]) -> None:
        destino = self._ruta(clave)
        destino.parent.mkdir(parents=True, exist_ok=True)
        temporal = destino.with_name(f".{destino.name}.{uuid.uuid4().hex}.tmp")
        try:
            with open(temporal, "wb") as fh:
                for chunk in chunks:
                    fh.write(chunk)
            os.replace(temporal, destino)
        except BaseException:
            with contextlib.suppress(FileNotFoundError):
                temporal.unlink()
            raise

    def abrir(self, clave: str) -> BinaryIO:
        return open(self._ruta(clave), "rb")  # noqa: SIM115 - el llamador lo cierra

    def eliminar(self, clave: str) -> None:
        with contextlib.suppress(FileNotFoundError):
            self._ruta(clave).unlink()
