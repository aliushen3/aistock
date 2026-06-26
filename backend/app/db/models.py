from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base

JsonType = JSON().with_variant(JSONB, "postgresql")


class OntSector(Base):
    __tablename__ = "ont_sector"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), default="beta_candidate")
    demand_growth_hint: Mapped[float | None] = mapped_column(Float, nullable=True)
    human_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    terminal_products: Mapped[list] = mapped_column(JsonType, default=list)
    attrs: Mapped[dict] = mapped_column(JsonType, default=dict)


class OntProduct(Base):
    __tablename__ = "ont_product"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    layer: Mapped[str] = mapped_column(String(32))
    sector_id: Mapped[str] = mapped_column(String(64), index=True)
    expansion_cycle_months: Mapped[int] = mapped_column(Integer, default=0)
    cr4_concentration: Mapped[float] = mapped_column(Float, default=0)
    tech_barrier_score: Mapped[float] = mapped_column(Float, default=50)
    supply_demand_score: Mapped[float] = mapped_column(Float, default=50)
    cost_ratio: Mapped[float] = mapped_column(Float, default=0)
    substitution_difficulty: Mapped[str] = mapped_column(String(16), default="medium")
    overseas_dependence: Mapped[str] = mapped_column(String(16), default="low")
    certification_months: Mapped[int] = mapped_column(Integer, default=0)
    bottleneck_status: Mapped[str] = mapped_column(String(32), default="none")
    serenity_niche: Mapped[bool] = mapped_column(Boolean, default=False)
    provenance_ids: Mapped[list] = mapped_column(JsonType, default=list)
    attrs: Mapped[dict] = mapped_column(JsonType, default=dict)


class OntCompany(Base):
    __tablename__ = "ont_company"

    code: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    market_cap_billion: Mapped[float | None] = mapped_column(Float, nullable=True)
    analyst_coverage: Mapped[int | None] = mapped_column(Integer, nullable=True)
    turnover_percentile: Mapped[float | None] = mapped_column(Float, nullable=True)
    gross_margin: Mapped[float | None] = mapped_column(Float, nullable=True)
    market_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pe_percentile: Mapped[float | None] = mapped_column(Float, nullable=True)
    produces: Mapped[list] = mapped_column(JsonType, default=list)
    attrs: Mapped[dict] = mapped_column(JsonType, default=dict)


class OntLinkUpstream(Base):
    __tablename__ = "ont_link_upstream"
    __table_args__ = (UniqueConstraint("source_id", "target_id", name="uq_upstream"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(String(64), index=True)
    target_id: Mapped[str] = mapped_column(String(64), index=True)


class OntLinkProduces(Base):
    __tablename__ = "ont_link_produces"
    __table_args__ = (UniqueConstraint("company_code", "product_id", name="uq_produces"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_code: Mapped[str] = mapped_column(String(16), index=True)
    product_id: Mapped[str] = mapped_column(String(64), index=True)


class OntEvidence(Base):
    __tablename__ = "ont_evidence"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    source_type: Mapped[str] = mapped_column(String(32))
    source_ref: Mapped[str] = mapped_column(Text)
    excerpt: Mapped[str] = mapped_column(Text)


class OntCandidateEntry(Base):
    __tablename__ = "ont_candidate_entry"

    entry_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    sector_id: Mapped[str] = mapped_column(String(64), index=True)
    mode: Mapped[str] = mapped_column(String(32))
    stock_code: Mapped[str] = mapped_column(String(16), index=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    operator: Mapped[str | None] = mapped_column(String(64), nullable=True)
    priority: Mapped[str | None] = mapped_column(String(8), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class OntResearchReport(Base):
    __tablename__ = "ont_research_report"

    report_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    status: Mapped[str] = mapped_column(String(16), default="draft")
    sector_id: Mapped[str] = mapped_column(String(64), index=True)
    mode: Mapped[str] = mapped_column(String(32))
    generated_by: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JsonType, default=dict)
    review: Mapped[dict | None] = mapped_column(JsonType, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class OntAuditLog(Base):
    __tablename__ = "ont_audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    operator: Mapped[str] = mapped_column(String(64))
    target: Mapped[str] = mapped_column(String(128), index=True)
    detail: Mapped[dict] = mapped_column(JsonType, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class OntKnowledgeAssertion(Base):
    __tablename__ = "ont_knowledge_assertion"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subject_type: Mapped[str] = mapped_column(String(32))
    subject_id: Mapped[str] = mapped_column(String(64), index=True)
    predicate: Mapped[str] = mapped_column(String(64))
    object_value: Mapped[str] = mapped_column(String(128))
    evidence_refs: Mapped[list] = mapped_column(JsonType, default=list)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    operator: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class OntSectorMetric(Base):
    __tablename__ = "ont_sector_metric"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sector_id: Mapped[str] = mapped_column(String(64), index=True)
    product_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    metric_key: Mapped[str] = mapped_column(String(64), index=True)
    period: Mapped[str] = mapped_column(String(16))
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(32), default="")
    attrs: Mapped[dict] = mapped_column(JsonType, default=dict)


    attrs: Mapped[dict] = mapped_column(JsonType, default=dict)


# --- ODS 原始/标准数据层（阶段 A）---


class OdsIndustryMetric(Base):
    __tablename__ = "ods_industry_metric"
    __table_args__ = (
        UniqueConstraint("sector_id", "product_id", "metric_key", "period", "source", name="uq_ods_metric"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sector_id: Mapped[str] = mapped_column(String(64), index=True)
    product_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    metric_key: Mapped[str] = mapped_column(String(64), index=True)
    period: Mapped[str] = mapped_column(String(16))
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(32), default="")
    source: Mapped[str] = mapped_column(String(32), default="mock")
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class OdsResearchReport(Base):
    __tablename__ = "ods_research_report"

    report_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(256))
    sector_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(64), default="upload")
    storage_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    char_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="indexed")
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class OdsMarketDaily(Base):
    __tablename__ = "ods_market_daily"
    __table_args__ = (UniqueConstraint("stock_code", "trade_date", name="uq_ods_market_daily"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stock_code: Mapped[str] = mapped_column(String(16), index=True)
    trade_date: Mapped[str] = mapped_column(String(16), index=True)
    close_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    market_cap_billion: Mapped[float | None] = mapped_column(Float, nullable=True)
    pe_percentile: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="mock")
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class OdsAnnouncement(Base):
    __tablename__ = "ods_announcement"

    ann_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    stock_code: Mapped[str] = mapped_column(String(16), index=True)
    title: Mapped[str] = mapped_column(String(512))
    ann_date: Mapped[str] = mapped_column(String(16), index=True)
    category: Mapped[str] = mapped_column(String(64), default="general")
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    storage_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="mock")
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class OdsFinancialStatement(Base):
    __tablename__ = "ods_financial_statement"
    __table_args__ = (
        UniqueConstraint("stock_code", "end_date", "source", name="uq_ods_financial"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stock_code: Mapped[str] = mapped_column(String(16), index=True)
    end_date: Mapped[str] = mapped_column(String(16), index=True)
    ann_date: Mapped[str | None] = mapped_column(String(16), nullable=True)
    revenue: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_profit: Mapped[float | None] = mapped_column(Float, nullable=True)
    gross_margin: Mapped[float | None] = mapped_column(Float, nullable=True)
    roe: Mapped[float | None] = mapped_column(Float, nullable=True)
    eps: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="mock")
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class OdsExternalReport(Base):
    __tablename__ = "ods_external_report"
    __table_args__ = (
        UniqueConstraint("report_key", name="uq_ods_external_report"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_key: Mapped[str] = mapped_column(String(128), index=True)
    stock_code: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(512))
    org_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    rating: Mapped[str | None] = mapped_column(String(64), nullable=True)
    report_date: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="em")
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class OntPendingReview(Base):
    __tablename__ = "ont_pending_review"

    pending_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    action_type: Mapped[str] = mapped_column(String(64), index=True)
    target_type: Mapped[str] = mapped_column(String(64))
    target_id: Mapped[str] = mapped_column(String(128), index=True)
    params: Mapped[dict] = mapped_column(JsonType, default=dict)
    first_operator: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class OntSectorRecommendation(Base):
    __tablename__ = "ont_sector_recommendation"

    rec_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    sector_name: Mapped[str] = mapped_column(String(128))
    sector_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    is_new: Mapped[bool] = mapped_column(Boolean, default=True)
    beta_score: Mapped[float] = mapped_column(Float, default=0.0)
    demand_growth_hint: Mapped[float | None] = mapped_column(Float, nullable=True)
    signals: Mapped[dict] = mapped_column(JsonType, default=dict)
    rationale: Mapped[str] = mapped_column(Text)
    terminal_products: Mapped[list] = mapped_column(JsonType, default=list)
    evidence_refs: Mapped[list] = mapped_column(JsonType, default=list)
    risks: Mapped[list] = mapped_column(JsonType, default=list)
    next_actions: Mapped[list] = mapped_column(JsonType, default=list)
    status: Mapped[str] = mapped_column(String(16), default="proposed")
    focus: Mapped[str | None] = mapped_column(String(256), nullable=True)
    agent_mode: Mapped[str] = mapped_column(String(32), default="rule")
    operator: Mapped[str] = mapped_column(String(64), default="system")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class OntBottleneckRecommendation(Base):
    __tablename__ = "ont_bottleneck_recommendation"

    rec_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    sector_id: Mapped[str] = mapped_column(String(64), index=True)
    product_id: Mapped[str] = mapped_column(String(64), index=True)
    product_name: Mapped[str] = mapped_column(String(128))
    hint_score: Mapped[float] = mapped_column(Float, default=0.0)
    hint_level: Mapped[str] = mapped_column(String(32), default="none")
    hit_rules: Mapped[list] = mapped_column(JsonType, default=list)
    rationale: Mapped[str] = mapped_column(Text, default="")
    evidence_refs: Mapped[list] = mapped_column(JsonType, default=list)
    status: Mapped[str] = mapped_column(String(16), default="proposed")
    agent_mode: Mapped[str] = mapped_column(String(32), default="rule_v1")
    operator: Mapped[str] = mapped_column(String(64), default="system")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class OntSerenityRecommendation(Base):
    __tablename__ = "ont_serenity_recommendation"

    rec_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    sector_id: Mapped[str] = mapped_column(String(64), index=True)
    path_id: Mapped[str] = mapped_column(String(64), index=True)
    niche_product_id: Mapped[str] = mapped_column(String(64), index=True)
    niche_product_name: Mapped[str] = mapped_column(String(128))
    serenity_hint: Mapped[float] = mapped_column(Float, default=0.0)
    hop_count: Mapped[int] = mapped_column(Integer, default=0)
    node_names: Mapped[list] = mapped_column(JsonType, default=list)
    companies: Mapped[list] = mapped_column(JsonType, default=list)
    rationale: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(16), default="proposed")
    agent_mode: Mapped[str] = mapped_column(String(32), default="trace_v1")
    operator: Mapped[str] = mapped_column(String(64), default="system")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class OntUploadedDocument(Base):
    __tablename__ = "ont_uploaded_document"

    doc_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    sector_id: Mapped[str] = mapped_column(String(64), index=True)
    source_ref: Mapped[str] = mapped_column(Text)
    filename: Mapped[str] = mapped_column(String(256))
    content_type: Mapped[str] = mapped_column(String(128), default="application/octet-stream")
    storage_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    char_count: Mapped[int] = mapped_column(Integer, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="indexed")
    operator: Mapped[str] = mapped_column(String(64), default="analyst")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class OntKnowledgeDraft(Base):
    __tablename__ = "ont_knowledge_draft"

    draft_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    sector_id: Mapped[str] = mapped_column(String(64), index=True)
    source_type: Mapped[str] = mapped_column(String(32))
    source_ref: Mapped[str] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text)
    extracted: Mapped[dict] = mapped_column(JsonType, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="draft")
    operator: Mapped[str] = mapped_column(String(64), default="system")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class OntHintOutcome(Base):
    """提示分人工裁决 outcome 回溯（F4 校准闭环）。"""

    __tablename__ = "ont_hint_outcome"

    outcome_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    product_id: Mapped[str] = mapped_column(String(64), index=True)
    sector_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    hint_score: Mapped[float] = mapped_column(Float, default=0.0)
    hint_level: Mapped[str] = mapped_column(String(32), default="none")
    weight_version: Mapped[str] = mapped_column(String(32), default="unknown")
    weights_snapshot: Mapped[dict] = mapped_column(JsonType, default=dict)
    action_type: Mapped[str] = mapped_column(String(64))
    verdict: Mapped[str] = mapped_column(String(32))
    outcome_status: Mapped[str] = mapped_column(String(32), default="pending")
    operator: Mapped[str] = mapped_column(String(64), default="analyst")
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class OntBearCase(Base):
    """看空论点（反证一等对象，v3.0 主线一）。"""

    __tablename__ = "ont_bear_case"

    bear_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    sector_id: Mapped[str] = mapped_column(String(64), index=True)
    candidate_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    stock_code: Mapped[str] = mapped_column(String(16), index=True)
    risk: Mapped[str] = mapped_column(Text)
    dimension: Mapped[str] = mapped_column(String(32))
    severity: Mapped[str] = mapped_column(String(16), default="medium")
    probability: Mapped[str] = mapped_column(String(16), default="medium")
    what_would_confirm: Mapped[str] = mapped_column(Text, default="")
    citations: Mapped[list] = mapped_column(JsonType, default=list)
    rebuttal: Mapped[str | None] = mapped_column(Text, nullable=True)
    rebuttal_status: Mapped[str] = mapped_column(String(16), default="unrebutted")
    operator: Mapped[str | None] = mapped_column(String(64), nullable=True)
    agent_mode: Mapped[str] = mapped_column(String(32), default="rule_v1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
