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
