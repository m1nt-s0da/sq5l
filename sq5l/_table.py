from dataclasses import dataclass
from typing import overload, Callable, Literal, LiteralString, Any
from ._where import CanWhere
from ._select import CanExists, CanGroupBy, CanOrder, CanRange, CanSelect
from ._write import CanInsert


@overload
def table[T: LiteralString](name: T) -> "Table[T]": ...


@overload
def table[T: LiteralString](name: str, *, as_: T) -> "TableAs[T]": ...


@overload
def table(name: str) -> Table: ...


@overload
def table(name: str, *, as_: str) -> TableAs: ...


def table(name: str, *, as_: str | None = None) -> Any:
    if as_ is not None:
        return TableAs(Table(name), as_)
    return Table(name)


@dataclass(frozen=True, init=False)
class TableAs[T: str](
    CanWhere[T], CanOrder, CanRange, CanSelect, CanGroupBy, CanExists, CanInsert
):
    table: Table
    alias: T

    def __init__(self, table: Table, alias: T):
        super().__init__((alias,))
        object.__setattr__(self, "table", table)
        object.__setattr__(self, "alias", alias)

    def inner_join(
        self, other: str | Table | TableAs, *, on: Callable[..., Any]
    ) -> Joined:
        if isinstance(other, str):
            other = Table(other)
        return Joined(self, other, _resolve_join_on(self, other, on), "INNER JOIN")

    def left_join(
        self, other: str | Table | TableAs, *, on: Callable[..., Any]
    ) -> Joined:
        if isinstance(other, str):
            other = Table(other)
        return Joined(self, other, _resolve_join_on(self, other, on), "LEFT JOIN")

    def right_join(
        self, other: str | Table | TableAs, *, on: Callable[..., Any]
    ) -> Joined:
        if isinstance(other, str):
            other = Table(other)
        return Joined(self, other, _resolve_join_on(self, other, on), "RIGHT JOIN")

    def full_join(
        self, other: str | Table | TableAs, *, on: Callable[..., Any]
    ) -> Joined:
        if isinstance(other, str):
            other = Table(other)
        return Joined(self, other, _resolve_join_on(self, other, on), "FULL OUTER JOIN")

    def cross_join(self, other: str | Table | TableAs) -> Joined:
        if isinstance(other, str):
            other = Table(other)
        return Joined(self, other, None, "CROSS JOIN")


@dataclass(frozen=True, init=False)
class Table[T: str](
    CanWhere[T], CanOrder, CanRange, CanSelect, CanGroupBy, CanExists, CanInsert
):
    name: T

    def __init__(self, name: T):
        super().__init__((name,))
        object.__setattr__(self, "name", name)

    @overload
    def as_[U: LiteralString](self, alias: U) -> TableAs[U]: ...
    @overload
    def as_(self, alias: str) -> TableAs: ...

    def as_(self, alias: str) -> TableAs:
        return TableAs(self, alias)

    def inner_join(
        self, other: str | Table | TableAs, *, on: Callable[..., Any]
    ) -> Joined:
        if isinstance(other, str):
            other = Table(other)
        return Joined(self, other, _resolve_join_on(self, other, on), "INNER JOIN")

    def left_join(
        self, other: str | Table | TableAs, *, on: Callable[..., Any]
    ) -> Joined:
        if isinstance(other, str):
            other = Table(other)
        return Joined(self, other, _resolve_join_on(self, other, on), "LEFT JOIN")

    def right_join(
        self, other: str | Table | TableAs, *, on: Callable[..., Any]
    ) -> Joined:
        if isinstance(other, str):
            other = Table(other)
        return Joined(self, other, _resolve_join_on(self, other, on), "RIGHT JOIN")

    def full_join(
        self, other: str | Table | TableAs, *, on: Callable[..., Any]
    ) -> Joined:
        if isinstance(other, str):
            other = Table(other)
        return Joined(self, other, _resolve_join_on(self, other, on), "FULL OUTER JOIN")

    def cross_join(self, other: str | Table | TableAs) -> Joined:
        if isinstance(other, str):
            other = Table(other)
        return Joined(self, other, None, "CROSS JOIN")


@dataclass(frozen=True, init=False)
class Joined(CanWhere[str], CanOrder, CanRange, CanSelect, CanGroupBy, CanExists):
    prev: Any
    right: Table | TableAs
    on: Any
    join_kind: str

    def __init__(self, prev: Any, right: Table | TableAs, on: Any, join_kind: str):
        right_ref = right.alias if isinstance(right, TableAs) else right.name
        prev_names = list(getattr(prev, "table_names", []))
        super().__init__(tuple([*prev_names, right_ref]))
        object.__setattr__(self, "prev", prev)
        object.__setattr__(self, "right", right)
        object.__setattr__(self, "on", on)
        object.__setattr__(self, "join_kind", join_kind)

    def inner_join(
        self, other: str | Table | TableAs, *, on: Callable[..., Any]
    ) -> Joined:
        if isinstance(other, str):
            other = Table(other)
        return Joined(self, other, _resolve_join_on(self, other, on), "INNER JOIN")

    def left_join(
        self, other: str | Table | TableAs, *, on: Callable[..., Any]
    ) -> Joined:
        if isinstance(other, str):
            other = Table(other)
        return Joined(self, other, _resolve_join_on(self, other, on), "LEFT JOIN")

    def right_join(
        self, other: str | Table | TableAs, *, on: Callable[..., Any]
    ) -> Joined:
        if isinstance(other, str):
            other = Table(other)
        return Joined(self, other, _resolve_join_on(self, other, on), "RIGHT JOIN")

    def full_join(
        self, other: str | Table | TableAs, *, on: Callable[..., Any]
    ) -> Joined:
        if isinstance(other, str):
            other = Table(other)
        return Joined(self, other, _resolve_join_on(self, other, on), "FULL OUTER JOIN")

    def cross_join(self, other: str | Table | TableAs) -> Joined:
        if isinstance(other, str):
            other = Table(other)
        return Joined(self, other, None, "CROSS JOIN")


@dataclass(frozen=True, init=False)
class DerivedTable[T: str](
    CanWhere[T], CanOrder, CanRange, CanSelect, CanGroupBy, CanExists
):
    subquery: Any
    alias: T
    name: T

    def __init__(self, subquery: Any, alias: T):
        super().__init__((alias,))
        object.__setattr__(self, "subquery", subquery)
        object.__setattr__(self, "alias", alias)
        object.__setattr__(self, "name", alias)


def _resolve_join_on(prev: Any, right: Table | TableAs, on: Callable[..., Any]) -> Any:
    from ._value import TableName
    from ._where import call_with_table_context

    right_ref = right.alias if isinstance(right, TableAs) else right.name
    prev_names = tuple(str(n) for n in getattr(prev, "table_names", ()))
    context_names = (*prev_names, str(right_ref))
    context: dict[str, TableName] = {name: TableName(name) for name in context_names}
    return call_with_table_context(on, context)
