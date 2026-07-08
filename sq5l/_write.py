from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from ._select import SqlParam


@dataclass(frozen=True)
class Inserted:
    target: Any
    values: Mapping[str, Any] | None = None
    columns: tuple[str, ...] | None = None
    source: Any | None = None
    ignore: bool = False

    def query(self) -> tuple[str, tuple[SqlParam, ...]]:
        from ._query_renderer import _target_table_name, build_query, render_query

        if self.values is not None:
            columns = list(self.values.keys())
            placeholders = ", ".join("?" for _ in columns)
            prefix = "INSERT IGNORE" if self.ignore else "INSERT"
            sql = (
                f"{prefix} INTO {_target_table_name(self.target)} "
                f"({', '.join(columns)}) VALUES ({placeholders});"
            )
            params = tuple(self.values[c] for c in columns)
            return sql, params

        if self.columns is None or self.source is None:
            raise TypeError(
                "insert source and columns are required for INSERT ... SELECT"
            )

        query = build_query(self.source)
        select_sql, params = render_query(query)
        prefix = "INSERT IGNORE" if self.ignore else "INSERT"
        sql = (
            f"{prefix} INTO {_target_table_name(self.target)} "
            f"({', '.join(self.columns)}) {select_sql.rstrip(';')};"
        )
        return sql, tuple(params)


@dataclass(frozen=True)
class Updated:
    source: Any
    mapping: Mapping[str, Any] | None = None
    column: str | None = None
    value_expr: Any | None = None
    pair_exprs: tuple[tuple[Any, Any], ...] = ()

    def query(self) -> tuple[str, tuple[SqlParam, ...]]:
        from ._param import Param
        from ._query_renderer import _context_from_refs, _render_value, build_query
        from ._value import ColumnName

        node = build_query(self.source)
        context = _context_from_refs(node.table_refs)
        params: list[SqlParam] = []

        assignments: list[str] = []
        has_join = bool(node.joins)
        target_ref = node.name

        if self.mapping is not None:
            for key, raw_value in self.mapping.items():
                lhs = f"{target_ref}.{key}" if has_join else key
                rhs_sql = _render_value(Param(raw_value), context, params)
                assignments.append(f"{lhs} = {rhs_sql}")
        elif self.column is not None:
            lhs = f"{target_ref}.{self.column}" if has_join else self.column
            rhs_value = self.value_expr

            if not hasattr(rhs_value, "query") and not isinstance(
                rhs_value, ColumnName
            ):
                rhs_value = Param(rhs_value)

            rhs_sql = _render_value(rhs_value, context, params)
            assignments.append(f"{lhs} = {rhs_sql}")
        else:
            for pair in self.pair_exprs:
                if not isinstance(pair, tuple) or len(pair) != 2:
                    raise TypeError("update lambda must return (left, right)")
                left, right = pair

                if isinstance(left, ColumnName):
                    lhs = left.sql_name
                else:
                    lhs = str(left)

                rhs_sql = _render_value(right, context, params)
                assignments.append(f"{lhs} = {rhs_sql}")

        if not assignments:
            raise TypeError("no update assignments")

        conditions: list[str] = []
        for join in node.joins:
            if join.on is not None:
                conditions.append(_render_value(join.on, context, params))

        for where_expr in node.where_exprs:
            conditions.append(f"({_render_value(where_expr, context, params)})")

        from_clause = ""
        if node.joins:
            join_sources = ", ".join(j.right_source_sql for j in node.joins)
            from_clause = f" FROM {join_sources}"

        where_clause = ""
        if conditions:
            where_clause = f" WHERE {' AND '.join(conditions)}"

        sql = (
            f"UPDATE {node.source_sql} "
            f"SET {', '.join(assignments)}"
            f"{from_clause}{where_clause};"
        )
        return sql, tuple(params)


@dataclass(frozen=True)
class Deleted:
    source: Any

    def query(self) -> tuple[str, tuple[SqlParam, ...]]:
        from ._query_renderer import _context_from_refs, _render_value, build_query

        node = build_query(self.source)
        context = _context_from_refs(node.table_refs)
        params: list[SqlParam] = []

        conditions: list[str] = []
        for join in node.joins:
            if join.on is not None:
                conditions.append(_render_value(join.on, context, params))

        for where_expr in node.where_exprs:
            conditions.append(f"({_render_value(where_expr, context, params)})")

        where_clause = ""
        if conditions:
            where_clause = f" WHERE {' AND '.join(conditions)}"

        sql = f"DELETE FROM {node.source_sql}{where_clause};"
        return sql, tuple(params)


class CanInsert:
    def insert(
        self,
        values_or_columns: Mapping[str, Any] | tuple[str, ...],
        source: Any | None = None,
        *,
        ignore: bool = False,
    ) -> Inserted:
        if isinstance(values_or_columns, Mapping):
            if source is not None:
                raise TypeError("source is not allowed with dict insert")
            return Inserted(self, values=values_or_columns, ignore=ignore)

        if not isinstance(values_or_columns, tuple):
            raise TypeError("insert requires dict values or tuple columns")

        if source is None:
            raise TypeError("insert with columns requires source query")

        return Inserted(self, columns=values_or_columns, source=source, ignore=ignore)


class CanUpdate:
    def update(self, *args: Any) -> Updated:
        if len(args) == 1 and isinstance(args[0], Mapping):
            return Updated(self, mapping=args[0])

        if len(args) == 2 and isinstance(args[0], str):
            value_expr = _resolve_with_source_context(self, args[1])
            return Updated(self, column=args[0], value_expr=value_expr)

        if args and all(callable(x) for x in args):
            pairs = tuple(_resolve_with_source_context(self, expr) for expr in args)
            return Updated(self, pair_exprs=pairs)

        raise TypeError("unsupported update arguments")


class CanDelete:
    def delete(self) -> Deleted:
        return Deleted(self)


def _resolve_with_source_context(source: Any, expr: Any) -> Any:
    if not callable(expr):
        return expr

    from ._value import TableName
    from ._where import call_with_table_context

    table_names = tuple(str(n) for n in getattr(source, "table_names", ()))
    context: dict[str, TableName] = {name: TableName(name) for name in table_names}
    return call_with_table_context(expr, context)
