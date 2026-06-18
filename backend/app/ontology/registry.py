"""加载 ontology/registry/*.yaml 注册表。"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

REGISTRY_DIR = Path(__file__).resolve().parents[3] / "ontology" / "registry"


def _load_yaml(name: str) -> dict:
    path = REGISTRY_DIR / name
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


class OntologyRegistry:
    def __init__(self) -> None:
        self._object_types = _load_yaml("object_types.yaml").get("object_types", {})
        self._action_types = _load_yaml("action_types.yaml").get("action_types", {})
        self._functions = _load_yaml("functions.yaml").get("functions", {})
        self._object_sets = _load_yaml("object_sets.yaml").get("object_sets", {})
        self.version = _load_yaml("object_types.yaml").get("version", "1.0.0")

    @property
    def object_types(self) -> dict:
        return self._object_types

    @property
    def action_types(self) -> dict:
        return self._action_types

    @property
    def functions(self) -> dict:
        return self._functions

    @property
    def object_sets(self) -> dict:
        return self._object_sets

    def get_action_type(self, name: str) -> dict | None:
        return self._action_types.get(name)

    def get_function(self, name: str) -> dict | None:
        return self._functions.get(name)

    def get_object_set(self, name: str) -> dict | None:
        return self._object_sets.get(name)

    def list_action_types_summary(self) -> list[dict]:
        return [
            {
                "name": name,
                "display_name": spec.get("display_name", name),
                "target": spec.get("target"),
                "parameters": spec.get("parameters", []),
                "permissions": spec.get("permissions", []),
                "requires_dual_review": spec.get("requires_dual_review", False),
            }
            for name, spec in self._action_types.items()
        ]


@lru_cache(maxsize=1)
def get_registry() -> OntologyRegistry:
    return OntologyRegistry()


ontology_registry = get_registry()
