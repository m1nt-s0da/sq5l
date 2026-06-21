from __future__ import annotations

from dataclasses import dataclass
from inspect import Parameter, signature
from typing import Any, Callable, Protocol, overload

from ._select import CanExists, CanGroupBy, CanOrder, CanRange, CanSelect
from ._value import CanBeValue, TableName
from ._write import CanUpdate


@dataclass(frozen=True)
class Where(CanOrder, CanRange, CanSelect, CanGroupBy, CanExists, CanUpdate):
    prev: Any
    condition: CanBeValue
    table_names: tuple[str, ...]


class WhereCondition[TableNames: str](Protocol):
    def __call__(self, **kwargs: TableName) -> CanBeValue: ...


@dataclass(frozen=True)
class CanWhere[TableNames: str]:
    table_names: tuple[TableNames, ...]

    @overload
    def where(self, condition: Callable[[TableName], CanBeValue]) -> Where: ...

    @overload
    def where(self, condition: WhereCondition[TableNames]) -> Where: ...

    def where(self, condition: Callable[..., CanBeValue]) -> Where:
        table_name_objects: dict[str, TableName] = {
            str(name): TableName(str(name)) for name in self.table_names
        }
        return Where(
            self,
            call_with_table_context(condition, table_name_objects),
            tuple(str(name) for name in self.table_names),
        )


def call_with_table_context(func: Any, context: dict[str, TableName]) -> Any:
    sig = signature(func)
    params = sig.parameters

    if any(p.kind == Parameter.VAR_KEYWORD for p in params.values()):
        return func(**context)

    kwargs: dict[str, TableName] = {}
    for name, p in params.items():
        if p.kind not in (Parameter.POSITIONAL_OR_KEYWORD, Parameter.KEYWORD_ONLY):
            continue
        if name in context:
            kwargs[name] = context[name]
            continue
        if p.default is Parameter.empty:
            raise TypeError(f"missing table argument '{name}'")

    return func(**kwargs)
