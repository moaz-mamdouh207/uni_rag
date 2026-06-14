from __future__ import annotations
import ast
import asyncio
import logging


from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field


logger = logging.getLogger(__name__)


class CalculateInput(BaseModel):
    expression: str = Field(
        ...,
        min_length=1,
        description=(
            "A mathematical expression to evaluate. "
            "Supports arithmetic, algebra, trig, log, sqrt, and solve(). "
            "For multi-step: 'z = 1/sqrt(2); w = z * 2; [z, w]' (semicolon-separated). "
            "Always use ** for exponentiation, not ^."
        ),
    )


class CalculateOutput(BaseModel):
    expression: str
    result:     str
    success:    bool
    error:      str | None = None


class CalculateTool(BaseTool):
    """Evaluate a mathematical expression using SymPy."""

    name: str = "calculate"
    description: str = (
        "Evaluate a mathematical expression or solve an equation. "
        "Supports arithmetic, algebra, and multi-statement expressions separated by semicolons. "
        "Use solve(equation, variable) syntax for equations."
    )
    args_schema: type[BaseModel] = CalculateInput


    async def _arun(self, expression: str) -> str:
        return await asyncio.to_thread(self._run_calculate, expression)
    

    def _run_calculate(self, expression: str) -> str:
        expression = expression.strip()
        try:
            sympy_ns = self._build_sympy_namespace()
            if expression.startswith("solve("):
                result = self._handle_solve(expression, sympy_ns)
            elif ";" in expression or (
                "=" in expression and not expression.startswith("solve")
            ):
                result = self._handle_multi_statement(expression, sympy_ns)
            else:
                from sympy import sympify
                parsed = sympify(expression, locals=sympy_ns)
                try:
                    result = str(round(float(parsed.evalf()), 6))
                except (AttributeError, TypeError):
                    result = str(parsed)
            return CalculateOutput(expression=expression, result=result, success=True).model_dump_json()
        except Exception as exc:
            logger.warning("calculate: failed for '%s': %s", expression, exc)
            return CalculateOutput(
                expression=expression, result="", success=False, error=str(exc)[:300]
            ).model_dump_json()


    def _build_sympy_namespace(self, ) -> dict:
        import sympy
        ns: dict = {}
        for name in sympy.__all__:
            try:
                ns[name] = getattr(sympy, name)
            except AttributeError:
                pass
        return ns


    def _handle_solve(self, expression: str, sympy_ns: dict) -> str:
        from sympy import sympify, solve

        inner = expression[len("solve("):-1].strip()
        try:
            parsed_args = ast.parse(f"({inner})", mode="eval").body
            if not isinstance(parsed_args, ast.Tuple) or len(parsed_args.elts) != 2:
                raise ValueError("solve() requires exactly two arguments.")
            eq_str = ast.unparse(parsed_args.elts[0])
            var_str = ast.unparse(parsed_args.elts[1])
        except Exception:
            parts = [p.strip() for p in inner.rsplit(",", 1)]
            if len(parts) != 2:
                raise ValueError(f"Could not parse solve() arguments: '{inner}'")
            eq_str, var_str = parts

        eq = sympify(eq_str, locals=sympy_ns)
        var = sympify(var_str, locals=sympy_ns)
        return str(solve(eq, var))


    def _handle_multi_statement(self, expression: str, sympy_ns: dict) -> str:
        from sympy import sympify

        local_ctx: dict = {}
        statements = [s.strip() for s in expression.split(";") if s.strip()]
        if not statements:
            raise ValueError("Empty expression after splitting on semicolons.")

        result = ""
        for i, stmt in enumerate(statements):
            is_last = i == len(statements) - 1
            if "=" in stmt and not stmt.startswith("["):
                exec(stmt, sympy_ns, local_ctx)  # nosec
            elif is_last:
                merged = {**sympy_ns, **local_ctx}
                parsed = sympify(stmt, locals=merged)
                if isinstance(parsed, list):
                    list_vars = [v.strip() for v in stmt.strip("[]").split(",")]
                    evaluated: dict[str, object] = {}
                    for j, sym in enumerate(parsed):
                        key = list_vars[j] if j < len(list_vars) else str(sym)
                        try:
                            evaluated[key] = round(float(sym.evalf()), 6)
                        except (AttributeError, TypeError):
                            evaluated[key] = str(sym)
                    result = str(evaluated)
                else:
                    try:
                        result = str(round(float(parsed.evalf()), 6))
                    except (AttributeError, TypeError):
                        result = str(parsed)
            else:
                exec(stmt, sympy_ns, local_ctx)  # nosec
        return result
    

    def _run(self, **kwargs):
        "Required by langchain"
        raise NotImplementedError("The agent is designed to be used async only")
