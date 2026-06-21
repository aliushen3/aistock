"""OWL 一致性校验 — 对照 ontology/aistock.owl 逻辑约束。"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

OWL_PATH = Path(__file__).resolve().parents[3] / "ontology" / "aistock.owl"

VALID_LAYERS = {"terminal", "mid", "material", "consumable"}
VALID_BOTTLENECK = {"none", "bottleneck_hint", "bottleneck_confirmed"}
VALID_SUBSTITUTION = {"low", "medium", "high"}
VALID_OVERSEAS = {"low", "medium", "high"}


def validate_product(product: dict) -> list[dict]:
    """规则版 OWL 对齐检查（无需运行时推理机）。"""
    issues = []
    pid = product.get("id", "?")

    if product.get("layer") not in VALID_LAYERS:
        issues.append(
            {"level": "error", "entity": pid, "rule": "Product.layer", "message": "无效产品层级"}
        )

    bs = product.get("bottleneck_status", "none")
    if bs not in VALID_BOTTLENECK:
        issues.append(
            {"level": "error", "entity": pid, "rule": "BottleneckHint.status", "message": f"无效瓶颈状态 {bs}"}
        )
    if bs == "bottleneck_confirmed" and bs == "bottleneck_hint":
        pass
    if product.get("serenity_niche") and product.get("layer") == "terminal":
        issues.append(
            {
                "level": "warning",
                "entity": pid,
                "rule": "SerenityNiche.layer",
                "message": "终端产品通常不应标记为 Serenity 小众环节",
            }
        )

    if product.get("substitution_difficulty") not in VALID_SUBSTITUTION:
        issues.append({"level": "warning", "entity": pid, "rule": "substitution", "message": "替代难度枚举无效"})
    if product.get("overseas_dependence") not in VALID_OVERSEAS:
        issues.append({"level": "warning", "entity": pid, "rule": "overseas", "message": "海外依赖枚举无效"})

    if product.get("expansion_cycle_months", 0) < 0:
        issues.append({"level": "error", "entity": pid, "rule": "expansion_cycle", "message": "扩产周期不能为负"})

    return issues


def validate_sector_graph(store, sector_id: str) -> dict:
    """校验赛道图谱一致性。"""
    products = store.list_products(sector_id)
    all_issues = []
    for p in products:
        all_issues.extend(validate_product(p))

    prod_ids = {p["id"] for p in products}
    for rel in store.relations:
        if rel.get("type") != "UPSTREAM_OF":
            continue
        if rel["source"] not in prod_ids or rel["target"] not in prod_ids:
            continue
        if rel["source"] == rel["target"]:
            all_issues.append(
                {
                    "level": "error",
                    "entity": rel["source"],
                    "rule": "UPSTREAM_OF",
                    "message": "上游关系不能自环",
                }
            )

    errors = [i for i in all_issues if i["level"] == "error"]
    warnings = [i for i in all_issues if i["level"] == "warning"]
    return {
        "sector_id": sector_id,
        "valid": len(errors) == 0,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "issues": all_issues,
        "owl_path": str(OWL_PATH),
        "validator": "rule_owl_v1",
    }


def validate_with_owlready(sector_id: str, store) -> dict | None:
    """可选 owlready2 深度校验。"""
    try:
        from owlready2 import get_ontology, sync_reasoner_pellet

        onto = get_ontology(f"file://{OWL_PATH.as_posix()}").load()
        sync_reasoner_pellet(infer_property_values=True, infer_data_property_values=True)
        return {"sector_id": sector_id, "owlready": "ok", "classes": len(list(onto.classes()))}
    except Exception as e:
        logger.info("owlready2 不可用，使用规则校验: %s", e)
        return None
