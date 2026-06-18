"""Ontology Function 注册与调用。"""

from __future__ import annotations

from typing import Any

from app.ontology.functions import FUNCTION_MAP
from app.ontology.registry import ontology_registry


class FunctionRuntime:
    def list_functions(self) -> list[dict]:
        return [
            {
                "name": name,
                "display_name": spec.get("display_name", name),
                "applies_to": spec.get("applies_to", []),
                "inputs": spec.get("inputs", []),
                "disclaimer": spec.get("disclaimer"),
            }
            for name, spec in ontology_registry.functions.items()
        ]

    def invoke(self, name: str, inputs: dict[str, Any]) -> Any:
        spec = ontology_registry.get_function(name)
        if spec is None:
            raise KeyError(f"未知 Function: {name}")
        impl_key = spec.get("implementation", name)
        fn = FUNCTION_MAP.get(name) or FUNCTION_MAP.get(impl_key)
        if fn is None:
            raise NotImplementedError(f"Function 未实现: {name}")
        return fn(**inputs)


function_runtime = FunctionRuntime()
