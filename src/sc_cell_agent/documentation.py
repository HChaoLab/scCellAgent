from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class ToolDocEntry:
    package: str
    symbols: list[str]
    description: str


class ToolDocumentation:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("# Tool Documentation\n\n", encoding="utf-8")

    def has_package(self, package: str) -> bool:
        content = self.path.read_text(encoding="utf-8")
        return f"## {package}" in content

    def append_entry(self, entry: ToolDocEntry) -> None:
        if self.has_package(entry.package):
            return
        section = "\n".join(
            [
                f"## {entry.package}",
                "",
                f"- symbols: {', '.join(entry.symbols)}",
                f"- description: {entry.description}",
                "",
            ]
        )
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(section)

    def ensure_entries(self, entries: list[ToolDocEntry]) -> list[str]:
        missing: list[str] = []
        for entry in entries:
            if not self.has_package(entry.package):
                missing.append(entry.package)
                self.append_entry(entry)
        return missing

    def as_text(self) -> str:
        return self.path.read_text(encoding="utf-8")
