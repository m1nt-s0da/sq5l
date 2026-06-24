from dataclasses import dataclass
from ._where import CanBeValue


@dataclass(frozen=True)
class Param(CanBeValue):
    value: str | bytes | int | float | bool | None


def param(value: str | bytes | int | float | bool | None) -> Param:
    return Param(value)
