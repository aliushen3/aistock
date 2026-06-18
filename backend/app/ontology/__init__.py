"""Palantir Ontology 风格语义层运行时（自建，不依赖商业产品）。"""

from app.ontology.action_executor import action_executor
from app.ontology.function_runtime import function_runtime
from app.ontology.registry import ontology_registry

__all__ = ["ontology_registry", "action_executor", "function_runtime"]
