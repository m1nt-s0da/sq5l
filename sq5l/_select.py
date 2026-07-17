from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal

from ._value import TableName

OrderDirection = Literal["asc", "desc"]
SelectExpr = Callable[..., object]
HavingExpr = Callable[..., object]
SqlParam = str | int | float | bool | None


@dataclass(frozen=True)
class OrderItem:
    expr: str | object
    direction: OrderDirection


@dataclass(frozen=True)
class Ordered:
    prev: Any
    items: tuple[OrderItem, ...]
    table_names: tuple[str, ...]

    def range(self, *, offset: int = 0, limit: int | None = None) -> Range:
        return Range(self, offset=offset, limit=limit, table_names=self.table_names)

    def group_by(
        self, *columns: str | SelectExpr, having: HavingExpr | None = None
    ) -> Grouped:
        return Grouped(
            self,
            _resolve_columns(columns, self.table_names),
            having=_resolve_expr(having, self.table_names),
            table_names=self.table_names,
        )

    def select(self, *columns: str | SelectExpr, distinct: bool = False) -> Selected:
        return Selected(
            self,
            _resolve_columns(columns, self.table_names),
            distinct=distinct,
            table_names=self.table_names,
        )


@dataclass(frozen=True)
class Range:
    prev: Any
    offset: int = 0
    limit: int | None = None
    table_names: tuple[str, ...] = ()

    def group_by(
        self, *columns: str | SelectExpr, having: HavingExpr | None = None
    ) -> Grouped:
        return Grouped(
            self,
            _resolve_columns(columns, self.table_names),
            having=_resolve_expr(having, self.table_names),
            table_names=self.table_names,
        )

    def select(self, *columns: str | SelectExpr, distinct: bool = False) -> Selected:
        return Selected(
            self,
            _resolve_columns(columns, self.table_names),
            distinct=distinct,
            table_names=self.table_names,
        )


@dataclass(frozen=True)
class Grouped:
    prev: Any
    columns: tuple[str | object, ...]
    having: object | None = None
    table_names: tuple[str, ...] = ()

    def order(self, *items: tuple[str | SelectExpr, OrderDirection]) -> Ordered:
        parsed = tuple(
            OrderItem(
                expr=_resolve_expr(expr, self.table_names),
                direction=direction,
            )
            for expr, direction in items
        )
        return Ordered(self, parsed, table_names=self.table_names)

    def range(self, *, offset: int = 0, limit: int | None = None) -> Range:
        return Range(self, offset=offset, limit=limit, table_names=self.table_names)

    def select(self, *columns: str | SelectExpr, distinct: bool = False) -> Selected:
        return Selected(
            self,
            _resolve_columns(columns, self.table_names),
            distinct=distinct,
            table_names=self.table_names,
        )


@dataclass(frozen=True)
class Selected:
    prev: Any
    columns: tuple[str | object, ...]
    distinct: bool = False
    table_names: tuple[str, ...] = ()

    def query(self) -> tuple[str, tuple[SqlParam, ...]]:
        from ._query_renderer import build_query, render_query

        query = build_query(self)
        sql, params = render_query(query)
        return sql, tuple(params)

    def __contains__(self, item: object) -> bool:
        raise TypeError("subquery membership is only supported inside callbacks")

    def as_(self, alias: str) -> Any:
        from ._table import DerivedTable

        return DerivedTable(self, alias)


class CanOrder:
    def order(self, *items: tuple[str | SelectExpr, OrderDirection]) -> Ordered:
        table_names = _table_names_from_source(self)
        parsed = tuple(
            OrderItem(
                expr=_resolve_expr(expr, table_names),
                direction=direction,
            )
            for expr, direction in items
        )
        return Ordered(self, parsed, table_names=table_names)


class CanRange:
    def range(self, *, offset: int = 0, limit: int | None = None) -> Range:
        return Range(
            self, offset=offset, limit=limit, table_names=_table_names_from_source(self)
        )


class CanGroupBy:
    def group_by(
        self, *columns: str | SelectExpr, having: HavingExpr | None = None
    ) -> Grouped:
        table_names = _table_names_from_source(self)
        return Grouped(
            self,
            _resolve_columns(columns, table_names),
            having=_resolve_expr(having, table_names),
            table_names=table_names,
        )


class CanSelect:
    def select(self, *columns: str | SelectExpr, distinct: bool = False) -> Selected:
        table_names = _table_names_from_source(self)
        return Selected(
            self,
            _resolve_columns(columns, table_names),
            distinct=distinct,
            table_names=table_names,
        )


class CanExists:
    def exists(self) -> Any:
        from ._value import ExistsExpr

        return ExistsExpr(self)


def _table_names_from_source(source: Any) -> tuple[str, ...]:
    names = getattr(source, "table_names", ())
    return tuple(str(n) for n in names)


def _table_context_from_names(table_names: tuple[str, ...]) -> dict[str, TableName]:
    return {name: TableName(name) for name in table_names}


def _resolve_expr(expr: object, table_names: tuple[str, ...]) -> object:
    if expr is None or not callable(expr):
        return expr
    from ._where import call_with_table_context

    return call_with_table_context(expr, _table_context_from_names(table_names))


def _resolve_columns(
    columns: tuple[str | SelectExpr, ...], table_names: tuple[str, ...]
) -> tuple[str | object, ...]:
    return tuple(
        _resolve_expr(c, table_names) if not isinstance(c, str) else c for c in columns
    )
