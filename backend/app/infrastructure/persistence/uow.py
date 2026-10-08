"""Unit of work: commit/rollback per request (C-02, D6)."""

from types import TracebackType
from typing import Self

from sqlalchemy.orm import Session


class UnitOfWork:
    """Context manager binding one request to one session lifecycle."""

    def __init__(self, session: Session) -> None:
        self._session = session

    @property
    def session(self) -> Session:
        """Expose the underlying session for repositories."""
        return self._session

    def commit(self) -> None:
        """Persist pending changes."""
        self._session.commit()

    def rollback(self) -> None:
        """Discard pending changes."""
        self._session.rollback()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if exc_type is not None:
            self.rollback()
        else:
            self.commit()
