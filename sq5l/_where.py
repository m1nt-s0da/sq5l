from __future__ import annotations

import ast
import inspect
from dataclasses import dataclass
from inspect import Parameter, signature
import linecache
from typing import Any, Callable, Protocol, overload

from ._select import CanExists, CanGroupBy, CanOrder, CanRange, CanSelect
from ._value import CanBeValue, TableName
from ._write import CanDelete, CanUpdate


@dataclass(frozen=True)
class Where(CanOrder, CanRange, CanSelect, CanGroupBy, CanExists, CanUpdate, CanDelete):
    prev: Any
    condition: CanBeValue
    table_names: tuple[str, ...]

    def where(self, condition: Callable[..., CanBeValue]) -> Where:
        # Keep this implementation local to Where.
        # Sharing via CanWhere on this dataclass can couple constructor/field behavior,
        # while Where(self, condition, table_names) must stay stable for chain building.
        table_name_objects: dict[str, TableName] = {
            str(name): TableName(str(name)) for name in self.table_names
        }
        return Where(
            self,
            call_with_table_context(condition, table_name_objects),
            tuple(str(name) for name in self.table_names),
        )


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
    if not callable(func):
        return func

    sig = signature(func)
    params = sig.parameters
    kwargs: dict[str, TableName] = {}

    if any(p.kind == Parameter.VAR_KEYWORD for p in params.values()):
        kwargs = dict(context)
    else:
        for name, p in params.items():
            if p.kind not in (Parameter.POSITIONAL_OR_KEYWORD, Parameter.KEYWORD_ONLY):
                continue
            if name in context:
                kwargs[name] = context[name]
                continue
            if p.default is Parameter.empty:
                raise TypeError(f"missing table argument '{name}'")

    try:
        callback = _compile_callback_expression(func)
    except OSError, SyntaxError, TypeError, ValueError:
        return func(**kwargs)

    return callback(**kwargs)


def _compile_callback_expression(func: Any) -> Callable[..., Any]:
    source_path = inspect.getsourcefile(func) or inspect.getfile(func)
    if source_path is None:
        raise OSError("callback source file is unavailable")

    source = "".join(linecache.getlines(source_path))
    if not source:
        raise OSError("callback source text is unavailable")

    tree = ast.parse(source, filename=source_path)

    target = _find_callback_node(tree, func)
    target = _CallbackAstTransformer().visit(target)
    ast.fix_missing_locations(target)

    if isinstance(target, ast.Lambda):
        expression = ast.Expression(body=target)
        ast.fix_missing_locations(expression)
        code = compile(
            expression, inspect.getsourcefile(func) or "<sq5l callback>", "eval"
        )
        namespace = dict(func.__globals__)
        namespace.update(_callback_helpers())
        closure_vars = inspect.getclosurevars(func)
        namespace.update(closure_vars.globals)
        namespace.update(closure_vars.nonlocals)
        return eval(code, namespace, {})

    if isinstance(target, ast.FunctionDef):
        module = ast.Module(body=[target], type_ignores=[])
        ast.fix_missing_locations(module)
        namespace = dict(func.__globals__)
        namespace.update(_callback_helpers())
        closure_vars = inspect.getclosurevars(func)
        namespace.update(closure_vars.globals)
        namespace.update(closure_vars.nonlocals)
        exec(
            compile(module, inspect.getsourcefile(func) or "<sq5l callback>", "exec"),
            namespace,
        )
        return namespace[target.name]

    raise TypeError(f"unsupported callback node: {type(target)!r}")


def _find_callback_node(tree: ast.AST, func: Any) -> ast.AST:
    original_signature = _code_signature(func.__code__)

    if func.__name__ == "<lambda>":
        candidates = [node for node in ast.walk(tree) if isinstance(node, ast.Lambda)]
    else:
        candidates = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == func.__name__
        ]

    if not candidates:
        raise TypeError("callback source did not contain a supported expression")

    exact_matches: list[ast.AST] = []
    for node in candidates:
        try:
            candidate = _build_candidate_callable(node)
        except Exception:
            continue
        if _code_signature(candidate.__code__) == original_signature:
            exact_matches.append(node)

    signature_params = signature(func).parameters
    expected_names = tuple(
        name
        for name, param in signature_params.items()
        if param.kind
        in (
            Parameter.POSITIONAL_ONLY,
            Parameter.POSITIONAL_OR_KEYWORD,
            Parameter.KEYWORD_ONLY,
        )
    )
    target_line = getattr(func.__code__, "co_firstlineno", 1)

    def candidate_names(node: ast.AST) -> tuple[str, ...]:
        if isinstance(node, ast.Lambda):
            args = node.args
        elif isinstance(node, ast.FunctionDef):
            args = node.args
        else:
            return ()
        return tuple(
            arg.arg for arg in (*args.posonlyargs, *args.args, *args.kwonlyargs)
        )

    def score(node: ast.AST) -> tuple[int, int, int]:
        line = getattr(node, "lineno", target_line)
        end_line = getattr(node, "end_lineno", line)
        candidate_name_score = 0 if candidate_names(node) == expected_names else 1
        location_score = 0 if line <= target_line <= end_line else 1
        return (candidate_name_score, location_score, abs(target_line - line))

    if exact_matches:
        return min(exact_matches, key=score)

    return min(candidates, key=score)


def _build_candidate_callable(node: ast.AST) -> Callable[..., Any]:
    if isinstance(node, ast.Lambda):
        expression = ast.Expression(body=node)
        ast.fix_missing_locations(expression)
        return eval(compile(expression, "<sq5l callback>", "eval"), {})

    if isinstance(node, ast.FunctionDef):
        module = ast.Module(body=[node], type_ignores=[])
        ast.fix_missing_locations(module)
        namespace: dict[str, Any] = {}
        exec(compile(module, "<sq5l callback>", "exec"), namespace)
        return namespace[node.name]

    raise TypeError(f"unsupported callback node: {type(node)!r}")


def _code_signature(code: Any) -> tuple[Any, ...]:
    arg_count = code.co_argcount + code.co_posonlyargcount + code.co_kwonlyargcount
    return (
        code.co_code,
        tuple(_normalize_constant(constant) for constant in code.co_consts),
        code.co_names,
        code.co_varnames[:arg_count],
        code.co_argcount,
        code.co_posonlyargcount,
        code.co_kwonlyargcount,
        code.co_freevars,
        code.co_cellvars,
    )


def _normalize_constant(value: Any) -> Any:
    if isinstance(value, type((lambda: None).__code__)):
        return ("code", _code_signature(value))
    if isinstance(value, tuple):
        return tuple(_normalize_constant(item) for item in value)
    if isinstance(value, list):
        return [*(_normalize_constant(item) for item in value)]
    return value


def _callback_helpers() -> dict[str, Callable[..., Any]]:
    return {
        "_sq5l_and": _sq5l_and,
        "_sq5l_or": _sq5l_or,
    }


def _sq5l_and(left: CanBeValue, right: CanBeValue) -> CanBeValue:
    from ._value import Op2

    return Op2("and", left, right)


def _sq5l_or(left: CanBeValue, right: CanBeValue) -> CanBeValue:
    from ._value import Op2

    return Op2("or", left, right)


class _CallbackAstTransformer(ast.NodeTransformer):
    def visit_BoolOp(self, node: ast.BoolOp) -> ast.AST:
        node = self.generic_visit(node)
        assert isinstance(node, ast.BoolOp)

        if len(node.values) == 1:
            return node.values[0]

        helper_name = "_sq5l_and" if isinstance(node.op, ast.And) else "_sq5l_or"
        expression = node.values[0]
        for value in node.values[1:]:
            expression = ast.Call(
                func=ast.Name(id=helper_name, ctx=ast.Load()),
                args=[expression, value],
                keywords=[],
            )
        return ast.copy_location(expression, node)

    def visit_UnaryOp(self, node: ast.UnaryOp) -> ast.AST:
        node = self.generic_visit(node)
        assert isinstance(node, ast.UnaryOp)

        if isinstance(node.op, ast.Not):
            return ast.copy_location(
                ast.UnaryOp(op=ast.Invert(), operand=node.operand), node
            )
        return node

    def visit_Compare(self, node: ast.Compare) -> ast.AST:
        node = self.generic_visit(node)
        assert isinstance(node, ast.Compare)

        if len(node.ops) == 1:
            return node

        pieces: list[ast.AST] = []
        left = node.left
        for operator, right in zip(node.ops, node.comparators):
            pieces.append(ast.Compare(left=left, ops=[operator], comparators=[right]))
            left = right

        expression = pieces[0]
        for piece in pieces[1:]:
            expression = ast.Call(
                func=ast.Name(id="_sq5l_and", ctx=ast.Load()),
                args=[expression, piece],
                keywords=[],
            )
        return ast.copy_location(expression, node)
