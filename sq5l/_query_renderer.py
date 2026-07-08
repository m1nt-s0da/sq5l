from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from ._select import HavingExpr, OrderItem, SelectExpr, SqlParam

if TYPE_CHECKING:
    from ._value import TableName


@dataclass(frozen=True)
class QueryNode:
    name: str
    source_sql: str
    table_refs: tuple[str, ...]
    source_subquery: Any | None = None
    source_alias: str | None = None
    joins: tuple[JoinItem, ...] = ()
    where_expr: Any | None = None
    group_by: tuple[str | Any, ...] = ()
    having: Any | None = None
    order_items: tuple[OrderItem, ...] = ()
    offset: int = 0
    limit: int | None = None
    select_columns: tuple[str | Any, ...] = ()
    select_distinct: bool = False


@dataclass(frozen=True)
class JoinItem:
    kind: str
    right_source_sql: str
    right_ref: str
    on: Any


def build_query(source: Any) -> QueryNode:
    from ._select import Grouped, Ordered, Range, Selected
    from ._table import DerivedTable, TableAs

    where_expr: Any | None = None
    order_items: tuple[OrderItem, ...] = ()
    offset = 0
    limit: int | None = None
    group_by_cols: tuple[str | SelectExpr, ...] = ()
    having_expr: HavingExpr | None = None
    select_columns: tuple[str | SelectExpr, ...] = ()
    select_distinct = False
    join_items_rev: list[JoinItem] = []

    current = source

    while True:
        if isinstance(current, Selected):
            select_columns = current.columns
            select_distinct = current.distinct
            current = current.prev
            continue

        if isinstance(current, Grouped):
            group_by_cols = current.columns
            having_expr = current.having
            current = current.prev
            continue

        if isinstance(current, Ordered):
            order_items = current.items
            current = current.prev
            continue

        if isinstance(current, Range):
            offset = current.offset
            limit = current.limit
            current = current.prev
            continue

        if hasattr(current, "condition") and where_expr is None:
            where_expr = current.condition
            current = current.prev
            continue

        if (
            hasattr(current, "join_kind")
            and hasattr(current, "right")
            and hasattr(current, "on")
        ):
            right = current.right
            if isinstance(right, TableAs):
                right_ref = right.alias
                right_source_sql = f"{right.table.name} AS {right.alias}"
            elif hasattr(right, "name"):
                right_ref = right.name
                right_source_sql = right.name
            else:
                raise TypeError(f"unsupported join source: {type(right)!r}")

            join_items_rev.append(
                JoinItem(
                    kind=current.join_kind,
                    right_source_sql=right_source_sql,
                    right_ref=right_ref,
                    on=current.on,
                )
            )
            current = current.prev
            continue

        if isinstance(current, TableAs):
            base_name = current.table.name
            alias = current.alias
            source_sql = f"{base_name} AS {alias}"
            joins = tuple(reversed(join_items_rev))
            table_refs = (alias, *[j.right_ref for j in joins])
            return QueryNode(
                name=alias,
                source_sql=source_sql,
                table_refs=table_refs,
                joins=joins,
                where_expr=where_expr,
                group_by=group_by_cols,
                having=having_expr,
                order_items=order_items,
                offset=offset,
                limit=limit,
                select_columns=select_columns,
                select_distinct=select_distinct,
            )

        if isinstance(current, DerivedTable):
            alias = current.alias
            joins = tuple(reversed(join_items_rev))
            table_refs = (alias, *[j.right_ref for j in joins])
            return QueryNode(
                name=alias,
                source_sql=alias,
                source_subquery=current.subquery,
                source_alias=alias,
                table_refs=table_refs,
                joins=joins,
                where_expr=where_expr,
                group_by=group_by_cols,
                having=having_expr,
                order_items=order_items,
                offset=offset,
                limit=limit,
                select_columns=select_columns,
                select_distinct=select_distinct,
            )

        if hasattr(current, "name"):
            name = current.name
            source_sql = name
            joins = tuple(reversed(join_items_rev))
            table_refs = (name, *[j.right_ref for j in joins])
            return QueryNode(
                name=name,
                source_sql=source_sql,
                table_refs=table_refs,
                joins=joins,
                where_expr=where_expr,
                group_by=group_by_cols,
                having=having_expr,
                order_items=order_items,
                offset=offset,
                limit=limit,
                select_columns=select_columns,
                select_distinct=select_distinct,
            )

        raise TypeError(f"unsupported query source: {type(current)!r}")


def render_query(query: QueryNode) -> tuple[str, list[SqlParam]]:
    return _render_query_internal(query)


def _render_query_internal(
    query: QueryNode,
    *,
    exists_mode: bool = False,
) -> tuple[str, list[SqlParam]]:
    params: list[SqlParam] = []
    context = _context_from_refs(query.table_refs)

    if exists_mode and not query.select_columns:
        select_sql = "1"
    else:
        select_sql = _render_select_list(
            query.select_columns, query.select_distinct, context, params
        )

    if query.source_subquery is not None:
        if query.source_alias is None:
            raise TypeError("derived table alias is required")
        source_sql = f"( {_render_subquery(query.source_subquery, params)} ) AS {query.source_alias}"
    else:
        source_sql = query.source_sql

    parts: list[str] = [f"SELECT {select_sql}", f"FROM {source_sql}"]

    if query.joins:
        for join in query.joins:
            if join.on is None:
                parts.append(f"{join.kind} {join.right_source_sql}")
            else:
                on_sql = _render_value(join.on, context, params)
                parts.append(f"{join.kind} {join.right_source_sql} ON {on_sql}")

    if query.where_expr is not None:
        parts.append(f"WHERE {_render_value(query.where_expr, context, params)}")

    if query.group_by:
        group_sql = ", ".join(
            _render_group_by_item(c, context, params) for c in query.group_by
        )
        parts.append(f"GROUP BY {group_sql}")

    if query.having is not None:
        parts.append(f"HAVING {_render_value(query.having, context, params)}")

    if query.order_items:
        order_sql = ", ".join(
            _render_order_item(i, context, params) for i in query.order_items
        )
        parts.append(f"ORDER BY {order_sql}")

    if query.limit is not None:
        parts.append(f"LIMIT {query.limit} OFFSET {query.offset}")

    return " ".join(parts) + ";", params


def _context_from_refs(table_refs: tuple[str, ...]) -> dict[str, TableName]:
    from ._value import TableName

    return {name: TableName(name) for name in table_refs}


def _target_table_name(target: Any) -> str:
    if hasattr(target, "table") and hasattr(target, "alias"):
        return target.table.name
    if hasattr(target, "name"):
        return target.name
    raise TypeError(f"unsupported target: {type(target)!r}")


def _render_select_list(
    columns: tuple[str | Any, ...],
    distinct: bool,
    context: dict[str, TableName],
    params: list[SqlParam],
) -> str:
    if columns:
        body = ", ".join(_render_select_column(c, context, params) for c in columns)
    else:
        body = "*"
    if distinct:
        return f"DISTINCT {body}"
    return body


def _qualify_column(name: str, table_ref: str) -> str:
    if "." in name:
        return name
    return f"{table_ref}.{name}"


def _render_select_column(
    column: str | Any,
    context: dict[str, TableName],
    params: list[SqlParam],
) -> str:
    from ._value import AliasedValue

    if isinstance(column, str):
        if len(context) != 1:
            raise TypeError("string column selection requires a single table context")
        table_ref = next(iter(context))
        return _qualify_column(column, table_ref)

    value = column
    if isinstance(value, AliasedValue):
        value_sql = _render_value(value.value, context, params)
        return f"{value_sql} AS {value.alias}"
    return _render_value(value, context, params)


def _render_group_by_item(
    column: str | Any,
    context: dict[str, TableName],
    params: list[SqlParam],
) -> str:
    if isinstance(column, str):
        if len(context) != 1:
            raise TypeError("string group_by column requires a single table context")
        table_ref = next(iter(context))
        return _qualify_column(column, table_ref)

    return _render_value(column, context, params)


def _render_order_item(
    item: OrderItem,
    context: dict[str, TableName],
    params: list[SqlParam],
) -> str:
    if isinstance(item.expr, str):
        if len(context) != 1:
            raise TypeError("string order column requires a single table context")
        table_ref = next(iter(context))
        expr_sql = _qualify_column(item.expr, table_ref)
    else:
        expr_sql = _render_value(item.expr, context, params)

    return f"{expr_sql} {item.direction.upper()}"


def _render_subquery(
    source: Any,
    params: list[SqlParam],
    *,
    exists_mode: bool = False,
) -> str:
    query = build_query(source)
    sub_sql, sub_params = _render_query_internal(query, exists_mode=exists_mode)
    params.extend(sub_params)
    return sub_sql.rstrip(";")


def _render_value(
    value: Any,
    context: dict[str, TableName],
    params: list[SqlParam],
) -> str:
    from ._param import Param
    from ._value import (
        AliasedValue,
        Asterisk,
        ColumnName,
        ExistsExpr,
        FuncCall,
        Op1,
        Op2,
        ScalarSubquery,
    )

    if isinstance(value, Param):
        params.append(value.value)
        return "?"

    if isinstance(value, bool):
        return "1" if value else "0"

    if isinstance(value, (int, float)):
        return str(value)

    if isinstance(value, str):
        escaped = value.replace("'", "''")
        return f"'{escaped}'"

    if isinstance(value, ColumnName):
        return value.sql_name

    if isinstance(value, Asterisk):
        return "*"

    if isinstance(value, AliasedValue):
        raise TypeError("AliasedValue is only allowed as a select lambda return value")

    if isinstance(value, ExistsExpr):
        return f"EXISTS ( {_render_subquery(value.source, params, exists_mode=True)} )"

    if isinstance(value, ScalarSubquery):
        return f"( {_render_subquery(value.source, params)} )"

    if isinstance(value, FuncCall):
        if value.name == "count" and value.distinct:
            if len(value.args) != 1:
                raise ValueError("count(distinct=True) requires one argument")
            arg_sql = _render_value(value.args[0], context, params)
            return f"COUNT(DISTINCT {arg_sql})"

        args_sql = ", ".join(_render_value(arg, context, params) for arg in value.args)
        return f"{value.name.upper()}({args_sql})"

    if isinstance(value, Op1):
        operand_sql = _render_value(value.operand, context, params)
        if value.op == "invert":
            return f"NOT ({operand_sql})"
        if value.op == "neg":
            return f"(-{operand_sql})"
        if value.op == "pos":
            return f"(+{operand_sql})"
        if value.op == "is_null":
            return f"{operand_sql} IS NULL"
        if value.op == "is_not_null":
            return f"{operand_sql} IS NOT NULL"
        raise ValueError(f"unsupported op1: {value.op}")

    if isinstance(value, Op2):
        left_sql = _render_value(value.left, context, params)
        right_sql = _render_value(value.right, context, params)
        op_map = {
            "add": "+",
            "sub": "-",
            "mul": "*",
            "div": "/",
            "and": "AND",
            "or": "OR",
            "eq": "=",
            "ne": "!=",
            "lt": "<",
            "le": "<=",
            "gt": ">",
            "ge": ">=",
            "like": "LIKE",
            "is": "IS",
            "in": "IN",
        }
        sql_op = op_map[value.op]
        return f"({left_sql} {sql_op} {right_sql})"

    if hasattr(value, "query"):
        return f"( {_render_subquery(value, params)} )"

    raise TypeError(f"unsupported value node: {type(value)!r}")
