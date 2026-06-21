from dataclasses import dataclass
from ._where import CanBeValue


@dataclass(frozen=True)
class Param(CanBeValue):
    value: str | int | float | bool | None


def param(value: str | int | float | bool | None) -> Param:
    return Param(value)
