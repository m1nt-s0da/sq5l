from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, cast

SqlLiteral = str | bytes | int | float | bool | None


class CanAggregate:
    def count(self, *, distinct: bool = False) -> FuncCall:
        return FuncCall("count", (cast(CanBeValue, self),), distinct=distinct)

    def avg(self) -> FuncCall:
        return FuncCall("avg", (cast(CanBeValue, self),))

    def sum(self) -> FuncCall:
        return FuncCall("sum", (cast(CanBeValue, self),))

    def min(self) -> FuncCall:
        return FuncCall("min", (cast(CanBeValue, self),))

    def max(self) -> FuncCall:
        return FuncCall("max", (cast(CanBeValue, self),))

    def total(self) -> FuncCall:
        return FuncCall("total", (cast(CanBeValue, self),))

    def group_concat(self, separator: CanBeValue | None = None) -> FuncCall:
        value = cast(CanBeValue, self)
        if separator is None:
            return FuncCall("group_concat", (value,))
        return FuncCall(
            "group_concat", (value, _require_value(separator, "group_concat"))
        )


class CanBeValue(CanAggregate):
    def __invert__(self) -> Op1:
        return Op1("invert", self)

    def __neg__(self) -> Op1:
        return Op1("neg", self)

    def __pos__(self) -> Op1:
        return Op1("pos", self)

    def __add__(self, other: CanBeValue) -> Op2:
        return Op2("add", self, _require_value(other, "add"))

    def __radd__(self, other: SqlLiteral) -> Op2:
        return Op2("add", _require_value(other, "add"), self)

    def __sub__(self, other: CanBeValue) -> Op2:
        return Op2("sub", self, _require_value(other, "sub"))

    def __rsub__(self, other: SqlLiteral) -> Op2:
        return Op2("sub", _require_value(other, "sub"), self)

    def __mul__(self, other: CanBeValue) -> Op2:
        return Op2("mul", self, _require_value(other, "mul"))

    def __rmul__(self, other: SqlLiteral) -> Op2:
        return Op2("mul", _require_value(other, "mul"), self)

    def __floordiv__(self, other: CanBeValue) -> Op2:
        return Op2("div", self, _require_value(other, "div"))

    def __rfloordiv__(self, other: SqlLiteral) -> Op2:
        return Op2("div", _require_value(other, "div"), self)

    def __eq__(self, other: object) -> Any:
        if other is None:
            return Op1("is_null", self)
        return Op2("eq", self, _require_value(other, "eq"))

    def __ne__(self, other: object) -> Any:
        if other is None:
            return Op1("is_not_null", self)
        return Op2("ne", self, _require_value(other, "ne"))

    def __lt__(self, other: CanBeValue) -> Op2:
        return Op2("lt", self, _require_value(other, "lt"))

    def __le__(self, other: CanBeValue) -> Op2:
        return Op2("le", self, _require_value(other, "le"))

    def __gt__(self, other: CanBeValue) -> Op2:
        return Op2("gt", self, _require_value(other, "gt"))

    def __ge__(self, other: CanBeValue) -> Op2:
        return Op2("ge", self, _require_value(other, "ge"))

    def like(self, other: CanBeValue) -> Op2:
        return Op2("like", self, _require_value(other, "like"))

    def is_(self, other: CanBeValue) -> Op2:
        return Op2("is", self, _require_value(other, "is"))

    def in_(self, other: CanBeValue | Any) -> Op2:
        return Op2("in", self, _coerce_in_operand(other))

    def upper(self) -> FuncCall:
        return FuncCall("upper", (self,))

    def lower(self) -> FuncCall:
        return FuncCall("lower", (self,))

    def length(self) -> FuncCall:
        return FuncCall("length", (self,))

    def abs(self) -> FuncCall:
        return FuncCall("abs", (self,))

    def round(self, precision: CanBeValue | None = None) -> FuncCall:
        if precision is None:
            return FuncCall("round", (self,))
        return FuncCall("round", (self, _require_value(precision, "round")))

    def trim(self, chars: CanBeValue | None = None) -> FuncCall:
        if chars is None:
            return FuncCall("trim", (self,))
        return FuncCall("trim", (self, _require_value(chars, "trim")))

    def ltrim(self, chars: CanBeValue | None = None) -> FuncCall:
        if chars is None:
            return FuncCall("ltrim", (self,))
        return FuncCall("ltrim", (self, _require_value(chars, "ltrim")))

    def rtrim(self, chars: CanBeValue | None = None) -> FuncCall:
        if chars is None:
            return FuncCall("rtrim", (self,))
        return FuncCall("rtrim", (self, _require_value(chars, "rtrim")))

    def replace(self, old: CanBeValue, new: CanBeValue) -> FuncCall:
        return FuncCall(
            "replace",
            (self, _require_value(old, "replace"), _require_value(new, "replace")),
        )

    def substr(self, start: CanBeValue, length: CanBeValue | None = None) -> FuncCall:
        if length is None:
            return FuncCall("substr", (self, _require_value(start, "substr")))
        return FuncCall(
            "substr",
            (
                self,
                _require_value(start, "substr"),
                _require_value(length, "substr"),
            ),
        )

    def ifnull(self, fallback: CanBeValue) -> FuncCall:
        return FuncCall("ifnull", (self, _require_value(fallback, "ifnull")))

    def nullif(self, other: CanBeValue) -> FuncCall:
        return FuncCall("nullif", (self, _require_value(other, "nullif")))

    def coalesce(self, *others: CanBeValue) -> FuncCall:
        if not others:
            raise TypeError("coalesce requires at least one fallback value")
        return FuncCall(
            "coalesce", (self, *(_require_value(v, "coalesce") for v in others))
        )

    def as_(self, alias: str) -> AliasedValue:
        return AliasedValue(self, alias)


@dataclass(frozen=True, eq=False)
class Op2(CanBeValue):
    op: Literal[
        "add",
        "sub",
        "mul",
        "div",
        "and",
        "or",
        "eq",
        "ne",
        "lt",
        "le",
        "gt",
        "ge",
        "like",
        "is",
        "in",
    ]
    left: CanBeValue
    right: Any


@dataclass(frozen=True, eq=False)
class Op1(CanBeValue):
    op: Literal["invert", "neg", "pos", "is_null", "is_not_null"]
    operand: CanBeValue


@dataclass(frozen=True, eq=False)
class FuncCall(CanBeValue):
    name: Literal[
        "upper",
        "lower",
        "length",
        "abs",
        "round",
        "trim",
        "ltrim",
        "rtrim",
        "replace",
        "substr",
        "ifnull",
        "nullif",
        "coalesce",
        "count",
        "avg",
        "sum",
        "min",
        "max",
        "total",
        "group_concat",
    ]
    args: tuple[CanBeValue, ...]
    distinct: bool = False


@dataclass(frozen=True)
class AliasedValue:
    value: CanBeValue
    alias: str

    def __eq__(self, other: object) -> bool:
        raise TypeError("AliasedValue is only allowed as a select lambda return value")

    def __ne__(self, other: object) -> bool:
        raise TypeError("AliasedValue is only allowed as a select lambda return value")


@dataclass(frozen=True, eq=False)
class ScalarSubquery(CanBeValue):
    source: Any


@dataclass(frozen=True)
class ValueList:
    values: tuple[CanBeValue, ...]


@dataclass(frozen=True, eq=False)
class ExistsExpr(CanBeValue):
    source: Any


class Asterisk(CanBeValue):
    pass


asterisk = Asterisk()


@dataclass(frozen=True, eq=False)
class ColumnName(CanBeValue):
    table_name: str
    column_name: str

    @property
    def sql_name(self) -> str:
        return f"{self.table_name}.{self.column_name}"


@dataclass(frozen=True)
class TableName:
    table_name: str

    def __getattr__(self, column_name: str) -> ColumnName:
        return ColumnName(self.table_name, column_name)


def _require_value(other: object, op: str) -> CanBeValue:
    from ._param import Param

    if isinstance(other, CanBeValue):
        return other
    if isinstance(other, (str, bytes, int, float, bool)) or other is None:
        return Param(other)
    raise TypeError(f"{op} expects a SQL value expression or literal")


def _coerce_in_operand(other: object) -> CanBeValue | ValueList | ScalarSubquery:
    if isinstance(other, CanBeValue):
        return other
    if isinstance(other, (list, tuple, set, frozenset, range)):
        return ValueList(tuple(_require_value(value, "in") for value in other))
    return ScalarSubquery(other)
