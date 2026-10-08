"""DEBUG temporal: estado del logger turnos.auth (se borra tras diagnosticar)."""

import logging


def test_debug_logger_state(caplog) -> None:  # type: ignore[no-untyped-def]
    log = logging.getLogger("turnos.auth")
    print(
        f"\nDISABLED={log.disabled} LEVEL={log.level} "
        f"EFFECTIVE={log.getEffectiveLevel()} HANDLERS={log.handlers} "
        f"ROOT_HANDLERS={logging.getLogger().handlers} "
        f"ROOT_LEVEL={logging.getLogger().level}"
    )
    caplog.set_level(logging.INFO, logger="turnos.auth")
    log.info('{"evento": "debug_probe"}')
    print(f"CAPTURED={[r.message for r in caplog.records]}")
    assert True
