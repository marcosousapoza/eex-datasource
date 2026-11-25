"""Portable SQLAlchemy schema for EEX data and ingestion provenance."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

JSON_VALUE = JSON().with_variant(JSONB, "postgresql")
MONEY = Numeric(24, 9)


class Base(DeclarativeBase):
    pass


class SyncRun(Base):
    __tablename__ = "sync_run"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job: Mapped[str] = mapped_column(String(80), index=True)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE)
    status: Mapped[str] = mapped_column(String(20), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetched_count: Mapped[int] = mapped_column(Integer, default=0)
    record_count: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)


class SyncState(Base):
    __tablename__ = "sync_state"

    state_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    job: Mapped[str] = mapped_column(String(80), index=True)
    scope: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE)
    watermark: Mapped[str | None] = mapped_column(String(64))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("sync_run.id", ondelete="SET NULL")
    )


class SyncLease(Base):
    __tablename__ = "sync_lease"

    lease_key: Mapped[str] = mapped_column(String(80), primary_key=True)
    owner: Mapped[str] = mapped_column(String(120))
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ArchiveObject(Base):
    __tablename__ = "archive_object"

    content_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    relative_path: Mapped[str | None] = mapped_column(String(300), unique=True)
    media_type: Mapped[str] = mapped_column(String(80), default="application/json")
    compressed_size: Mapped[int] = mapped_column(BigInteger)
    uncompressed_size: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    evicted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ApiFetch(Base):
    __tablename__ = "api_fetch"
    __table_args__ = (Index("ix_api_fetch_request_time", "request_hash", "fetched_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str | None] = mapped_column(
        ForeignKey("sync_run.id", ondelete="SET NULL"), index=True
    )
    request_hash: Mapped[str] = mapped_column(String(64), index=True)
    content_hash: Mapped[str] = mapped_column(
        ForeignKey("archive_object.content_hash"), index=True
    )
    path: Mapped[str] = mapped_column(String(500), index=True)
    query: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE)
    url: Mapped[str] = mapped_column(String(1200))
    status_code: Mapped[int] = mapped_column(Integer)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    record_count: Mapped[int] = mapped_column(Integer)
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False)


class MarketInstrument(Base):
    __tablename__ = "market_instrument"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    instrument_key: Mapped[str] = mapped_column(String(64), unique=True)
    market: Mapped[str] = mapped_column(String(20), index=True)
    instrument_isin: Mapped[str | None] = mapped_column(String(20), index=True)
    product_isin: Mapped[str | None] = mapped_column(String(20))
    commodity: Mapped[str | None] = mapped_column(String(40), index=True)
    area: Mapped[str | None] = mapped_column(String(40), index=True)
    shortcode: Mapped[str | None] = mapped_column(String(40), index=True)
    maturity: Mapped[str | None] = mapped_column(String(40), index=True)
    long_name: Mapped[str | None] = mapped_column(String(300))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE)


class InstrumentSnapshot(Base):
    __tablename__ = "instrument_snapshot"
    __table_args__ = (
        UniqueConstraint("instrument_id", "business_date", "record_hash"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    instrument_id: Mapped[str] = mapped_column(
        ForeignKey("market_instrument.id"), index=True
    )
    business_date: Mapped[date] = mapped_column(Date, index=True)
    record_hash: Mapped[str] = mapped_column(String(64), index=True)
    source_fetch_id: Mapped[str | None] = mapped_column(
        ForeignKey("api_fetch.id", ondelete="SET NULL")
    )
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE)


class MarketTrade(Base):
    __tablename__ = "market_trade"
    __table_args__ = (
        UniqueConstraint("market", "record_hash"),
        Index("ix_trade_lookup", "market", "business_date", "shortcode"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    market: Mapped[str] = mapped_column(String(20))
    source_key: Mapped[str] = mapped_column(String(300), index=True)
    record_hash: Mapped[str] = mapped_column(String(64))
    business_date: Mapped[date | None] = mapped_column(Date, index=True)
    event_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    commodity: Mapped[str | None] = mapped_column(String(40))
    area: Mapped[str | None] = mapped_column(String(40))
    shortcode: Mapped[str | None] = mapped_column(String(40))
    maturity: Mapped[str | None] = mapped_column(String(40))
    trade_id: Mapped[str | None] = mapped_column(String(80))
    group_id: Mapped[str | None] = mapped_column(String(80))
    version: Mapped[str | None] = mapped_column(String(20))
    update_action: Mapped[str | None] = mapped_column(String(30))
    price: Mapped[Decimal | None] = mapped_column(MONEY)
    size: Mapped[Decimal | None] = mapped_column(MONEY)
    volume: Mapped[Decimal | None] = mapped_column(MONEY)
    source_fetch_id: Mapped[str | None] = mapped_column(
        ForeignKey("api_fetch.id", ondelete="SET NULL")
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE)


class TopOfBook(Base):
    __tablename__ = "top_of_book"
    __table_args__ = (UniqueConstraint("market", "record_hash"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    market: Mapped[str] = mapped_column(String(20), index=True)
    record_hash: Mapped[str] = mapped_column(String(64))
    business_date: Mapped[date | None] = mapped_column(Date, index=True)
    event_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    commodity: Mapped[str | None] = mapped_column(String(40))
    area: Mapped[str | None] = mapped_column(String(40))
    shortcode: Mapped[str | None] = mapped_column(String(40), index=True)
    maturity: Mapped[str | None] = mapped_column(String(40))
    bid_price: Mapped[Decimal | None] = mapped_column(MONEY)
    bid_size: Mapped[Decimal | None] = mapped_column(MONEY)
    ask_price: Mapped[Decimal | None] = mapped_column(MONEY)
    ask_size: Mapped[Decimal | None] = mapped_column(MONEY)
    source_fetch_id: Mapped[str | None] = mapped_column(
        ForeignKey("api_fetch.id", ondelete="SET NULL")
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE)


class MarketStatistic(Base):
    __tablename__ = "market_statistic"
    __table_args__ = (UniqueConstraint("market", "record_hash"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    market: Mapped[str] = mapped_column(String(20), index=True)
    record_hash: Mapped[str] = mapped_column(String(64))
    business_date: Mapped[date | None] = mapped_column(Date, index=True)
    commodity: Mapped[str | None] = mapped_column(String(40))
    area: Mapped[str | None] = mapped_column(String(40))
    shortcode: Mapped[str | None] = mapped_column(String(40), index=True)
    maturity: Mapped[str | None] = mapped_column(String(40))
    open_price: Mapped[Decimal | None] = mapped_column(MONEY)
    high_price: Mapped[Decimal | None] = mapped_column(MONEY)
    low_price: Mapped[Decimal | None] = mapped_column(MONEY)
    last_price: Mapped[Decimal | None] = mapped_column(MONEY)
    trade_count: Mapped[int | None] = mapped_column(Integer)
    total_size: Mapped[Decimal | None] = mapped_column(MONEY)
    total_volume: Mapped[Decimal | None] = mapped_column(MONEY)
    source_fetch_id: Mapped[str | None] = mapped_column(
        ForeignKey("api_fetch.id", ondelete="SET NULL")
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE)


class Settlement(Base):
    __tablename__ = "settlement"
    __table_args__ = (UniqueConstraint("market", "record_hash"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    market: Mapped[str] = mapped_column(String(20), index=True)
    record_hash: Mapped[str] = mapped_column(String(64))
    business_date: Mapped[date | None] = mapped_column(Date, index=True)
    event_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    commodity: Mapped[str | None] = mapped_column(String(40))
    area: Mapped[str | None] = mapped_column(String(40))
    shortcode: Mapped[str | None] = mapped_column(String(40), index=True)
    maturity: Mapped[str | None] = mapped_column(String(40))
    price: Mapped[Decimal | None] = mapped_column(MONEY)
    update_action: Mapped[str | None] = mapped_column(String(30))
    source_fetch_id: Mapped[str | None] = mapped_column(
        ForeignKey("api_fetch.id", ondelete="SET NULL")
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE)


class Auction(Base):
    __tablename__ = "auction"

    auction_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    auction_date: Mapped[date] = mapped_column(Date, index=True)
    commodity: Mapped[str | None] = mapped_column(String(40))
    area: Mapped[str | None] = mapped_column(String(40))
    shortcode: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[str | None] = mapped_column(String(20))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE)
    record_hash: Mapped[str] = mapped_column(String(64))
    source_fetch_id: Mapped[str | None] = mapped_column(
        ForeignKey("api_fetch.id", ondelete="SET NULL")
    )


class AuctionResult(Base):
    __tablename__ = "auction_result"
    __table_args__ = (UniqueConstraint("auction_id", "record_hash"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    auction_id: Mapped[int] = mapped_column(
        ForeignKey("auction.auction_id"), index=True
    )
    record_hash: Mapped[str] = mapped_column(String(64))
    event_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    price: Mapped[Decimal | None] = mapped_column(MONEY)
    traded_volume: Mapped[Decimal | None] = mapped_column(MONEY)
    total_revenue: Mapped[Decimal | None] = mapped_column(MONEY)
    source_fetch_id: Mapped[str | None] = mapped_column(
        ForeignKey("api_fetch.id", ondelete="SET NULL")
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE)


class AuctionRevenue(Base):
    __tablename__ = "auction_revenue"
    __table_args__ = (UniqueConstraint("auction_id", "record_hash"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    auction_id: Mapped[int] = mapped_column(
        ForeignKey("auction.auction_id"), index=True
    )
    record_hash: Mapped[str] = mapped_column(String(64))
    auctioneer_name: Mapped[str | None] = mapped_column(String(300))
    volume: Mapped[Decimal | None] = mapped_column(MONEY)
    revenue: Mapped[Decimal | None] = mapped_column(MONEY)
    source_fetch_id: Mapped[str | None] = mapped_column(
        ForeignKey("api_fetch.id", ondelete="SET NULL")
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE)


class IndexDefinition(Base):
    __tablename__ = "index_definition"
    __table_args__ = (UniqueConstraint("commodity", "area", "index_code"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    commodity: Mapped[str] = mapped_column(String(40), index=True)
    area: Mapped[str] = mapped_column(String(40), index=True)
    index_code: Mapped[str] = mapped_column(String(80), index=True)
    long_name: Mapped[str | None] = mapped_column(String(300))
    unit: Mapped[str | None] = mapped_column(String(30))
    currency: Mapped[str | None] = mapped_column(String(10))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE)


class IndexObservation(Base):
    __tablename__ = "index_observation"
    __table_args__ = (UniqueConstraint("definition_id", "record_hash"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    definition_id: Mapped[str] = mapped_column(
        ForeignKey("index_definition.id"), index=True
    )
    trade_date: Mapped[date] = mapped_column(Date, index=True)
    event_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    record_hash: Mapped[str] = mapped_column(String(64))
    price: Mapped[Decimal | None] = mapped_column(MONEY)
    volume: Mapped[Decimal | None] = mapped_column(MONEY)
    update_action: Mapped[str | None] = mapped_column(String(30))
    source_fetch_id: Mapped[str | None] = mapped_column(
        ForeignKey("api_fetch.id", ondelete="SET NULL")
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE)


class TransparencyCompany(Base):
    __tablename__ = "transparency_company"

    company_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    name: Mapped[str | None] = mapped_column(String(400))
    country: Mapped[str | None] = mapped_column(String(4), index=True)
    ace: Mapped[str | None] = mapped_column(String(40))
    modified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE)


class TransparencyFacility(Base):
    __tablename__ = "transparency_facility"

    facility_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    company_id: Mapped[str | None] = mapped_column(
        ForeignKey("transparency_company.company_id"), index=True
    )
    name: Mapped[str | None] = mapped_column(String(400))
    area: Mapped[str | None] = mapped_column(String(4), index=True)
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    modified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE)


class TransparencyUnit(Base):
    __tablename__ = "transparency_unit"

    unit_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    facility_id: Mapped[str | None] = mapped_column(
        ForeignKey("transparency_facility.facility_id"), index=True
    )
    name: Mapped[str | None] = mapped_column(String(400))
    commodity: Mapped[str | None] = mapped_column(String(20))
    facility_type: Mapped[str | None] = mapped_column(String(30))
    fuel_type: Mapped[str | None] = mapped_column(String(100))
    eic: Mapped[str | None] = mapped_column(String(40), index=True)
    modified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE)


class TransparencyCapacity(Base):
    __tablename__ = "transparency_capacity"
    __table_args__ = (UniqueConstraint("unit_id", "record_hash"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    unit_id: Mapped[str] = mapped_column(
        ForeignKey("transparency_unit.unit_id"), index=True
    )
    record_hash: Mapped[str] = mapped_column(String(64))
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    modified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    installed: Mapped[Decimal | None] = mapped_column(MONEY)
    working: Mapped[Decimal | None] = mapped_column(MONEY)
    unit_measure: Mapped[str | None] = mapped_column(String(30))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE)


class TransparencyReferenceSnapshot(Base):
    __tablename__ = "transparency_reference_snapshot"
    __table_args__ = (
        UniqueConstraint("entity_type", "entity_id", "validity_date", "record_hash"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(20), index=True)
    entity_id: Mapped[str] = mapped_column(String(120), index=True)
    validity_date: Mapped[date] = mapped_column(Date, index=True)
    record_hash: Mapped[str] = mapped_column(String(64))
    source_fetch_id: Mapped[str | None] = mapped_column(
        ForeignKey("api_fetch.id", ondelete="SET NULL")
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE)


class UmmThread(Base):
    __tablename__ = "umm_thread"

    thread_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    kind: Mapped[str] = mapped_column(String(20), index=True)
    commodity: Mapped[str | None] = mapped_column(String(20), index=True)
    area: Mapped[str | None] = mapped_column(String(4), index=True)
    latest_message_id: Mapped[str] = mapped_column(String(120))
    latest_modified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    status: Mapped[str | None] = mapped_column(String(30))


class UmmRevision(Base):
    __tablename__ = "umm_revision"

    message_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    thread_id: Mapped[str] = mapped_column(
        ForeignKey("umm_thread.thread_id"), index=True
    )
    version: Mapped[str | None] = mapped_column(String(10))
    modified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    event_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    event_stop: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    record_hash: Mapped[str] = mapped_column(String(64))
    source_fetch_id: Mapped[str | None] = mapped_column(
        ForeignKey("api_fetch.id", ondelete="SET NULL")
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE)


class UmmCapacityInterval(Base):
    __tablename__ = "umm_capacity_interval"
    __table_args__ = (
        UniqueConstraint("message_id", "interval_start", "interval_stop"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    message_id: Mapped[str] = mapped_column(
        ForeignKey("umm_revision.message_id"), index=True
    )
    interval_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    interval_stop: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    available: Mapped[Decimal | None] = mapped_column(MONEY)
    unavailable: Mapped[Decimal | None] = mapped_column(MONEY)


class TransparencySeries(Base):
    __tablename__ = "transparency_series"
    __table_args__ = (
        UniqueConstraint("source", "commodity", "area", "symbol", "series_key"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source: Mapped[str] = mapped_column(String(20))
    commodity: Mapped[str] = mapped_column(String(20), index=True)
    area: Mapped[str] = mapped_column(String(4), index=True)
    symbol: Mapped[str] = mapped_column(String(100), index=True)
    series_key: Mapped[str] = mapped_column(String(64))
    facility_type: Mapped[str | None] = mapped_column(String(30))
    fuel_type: Mapped[str | None] = mapped_column(String(100))
    unit_id: Mapped[str | None] = mapped_column(String(120))
    resolution: Mapped[str | None] = mapped_column(String(30))
    unit_measure: Mapped[str | None] = mapped_column(String(30))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE)


class TransparencySeriesPoint(Base):
    __tablename__ = "transparency_series_point"
    __table_args__ = (UniqueConstraint("series_id", "timestamp", "modified_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    series_id: Mapped[str] = mapped_column(
        ForeignKey("transparency_series.id"), index=True
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    value: Mapped[Decimal] = mapped_column(MONEY)
    source_fetch_id: Mapped[str | None] = mapped_column(
        ForeignKey("api_fetch.id", ondelete="SET NULL")
    )
