from dataclasses import dataclass
from ._value import CanBeValue


@dataclass(frozen=True)
class Param(CanBeValue):
    value: str | bytes | int | float | bool | None
