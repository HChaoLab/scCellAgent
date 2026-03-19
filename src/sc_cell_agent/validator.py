from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Iterable


@dataclass(slots=True)
class ValidationResult:
    ok: bool
    errors: list[str]


class CodeValidator:
    def __init__(self, allowed_imports: set[str], known_variables: set[str]) -> None:
        self.allowed_imports = allowed_imports
        self.known_variables = known_variables

    def validate(self, code: str) -> ValidationResult:
        errors: list[str] = []
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            return ValidationResult(False, [f"SyntaxError: {exc}"])

        assigned_names = self._collect_assigned_names(tree)
        allowed_names = self.known_variables | assigned_names | set(dir(__builtins__))

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root not in self.allowed_imports:
                        errors.append(f"禁止导入未注册库: {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = (node.module or "").split(".")[0]
                if module not in self.allowed_imports:
                    errors.append(f"禁止从未注册库导入: {node.module}")
            elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                if node.id not in allowed_names:
                    errors.append(f"检测到未定义变量或幻觉变量: {node.id}")

        return ValidationResult(not errors, errors)

    @staticmethod
    def _collect_assigned_names(tree: ast.AST) -> set[str]:
        assigned: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                targets: Iterable[ast.AST]
                if isinstance(node, ast.Assign):
                    targets = node.targets
                else:
                    targets = [node.target]
                for target in targets:
                    for name in CodeValidator._flatten_names(target):
                        assigned.add(name)
            elif isinstance(node, ast.FunctionDef):
                assigned.add(node.name)
            elif isinstance(node, ast.ClassDef):
                assigned.add(node.name)
        return assigned

    @staticmethod
    def _flatten_names(node: ast.AST) -> set[str]:
        names: set[str] = set()
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, (ast.Tuple, ast.List)):
            for elt in node.elts:
                names |= CodeValidator._flatten_names(elt)
        return names
