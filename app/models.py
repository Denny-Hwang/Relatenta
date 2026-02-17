from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, ForeignKey, Float, Text, UniqueConstraint, JSON
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from datetime import datetime
from .db import Base

class Author(Base):
    __tablename__ = "authors"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    normalized_name: Mapped[str] = mapped_column(String, index=True)
    display_name: Mapped[str] = mapped_column(String, index=True)
    orcid: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    aliases = relationship("AuthorAlias", back_populates="author", cascade="all, delete-orphan")
    work_links = relationship("WorkAuthor", back_populates="author", cascade="all, delete-orphan")

class AuthorAlias(Base):
    __tablename__ = "author_aliases"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("authors.id", ondelete="CASCADE"))
    raw_name: Mapped[str] = mapped_column(String)
    source: Mapped[str] = mapped_column(String, default="manual")
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    author = relationship("Author", back_populates="aliases")

class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, index=True)
    country_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    city: Mapped[str | None] = mapped_column(String, nullable=True)

class Venue(Base):
    __tablename__ = "venues"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, index=True)
    type: Mapped[str | None] = mapped_column(String, nullable=True)  # journal, conference
    issn: Mapped[str | None] = mapped_column(String, nullable=True)
    publisher: Mapped[str | None] = mapped_column(String, nullable=True)

class Work(Base):
    __tablename__ = "works"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    doi: Mapped[str | None] = mapped_column(String, index=True)
    source_uid: Mapped[str | None] = mapped_column(String, index=True)  # OpenAlex ID, etc
    title: Mapped[str] = mapped_column(Text)
    abstract: Mapped[str | None] = mapped_column(Text, nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, index=True)
    venue_id: Mapped[int | None] = mapped_column(ForeignKey("venues.id"), nullable=True)
    url: Mapped[str | None] = mapped_column(String, nullable=True)
    type: Mapped[str | None] = mapped_column(String, nullable=True)
    language: Mapped[str | None] = mapped_column(String, nullable=True)
    source: Mapped[str | None] = mapped_column(String, default="OpenAlex")
    raw_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    venue = relationship("Venue")
    authors = relationship("WorkAuthor", back_populates="work", cascade="all, delete-orphan")
    affiliations = relationship("WorkAffiliation", back_populates="work", cascade="all, delete-orphan")
    keywords = relationship("WorkKeyword", back_populates="work", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("doi", name="uq_works_doi"),
        UniqueConstraint("source_uid", "source", name="uq_works_sourceid"),
    )

class WorkAuthor(Base):
    __tablename__ = "work_authors"
    work_id: Mapped[int] = mapped_column(ForeignKey("works.id", ondelete="CASCADE"), primary_key=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("authors.id", ondelete="CASCADE"), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    corresponding: Mapped[bool] = mapped_column(Boolean, default=False)

    work = relationship("Work", back_populates="authors")
    author = relationship("Author", back_populates="work_links")

class WorkAffiliation(Base):
    __tablename__ = "work_affiliations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    work_id: Mapped[int] = mapped_column(ForeignKey("works.id", ondelete="CASCADE"))
    author_id: Mapped[int | None] = mapped_column(ForeignKey("authors.id"), nullable=True)
    org_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), nullable=True)
    org_label_raw: Mapped[str | None] = mapped_column(String, nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    country_code: Mapped[str | None] = mapped_column(String(2), nullable=True)

    work = relationship("Work", back_populates="affiliations")
    organization = relationship("Organization")

class Keyword(Base):
    __tablename__ = "keywords"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    term_norm: Mapped[str] = mapped_column(String, index=True, unique=True)
    term_display: Mapped[str] = mapped_column(String)
    vocabulary: Mapped[str | None] = mapped_column(String, nullable=True)

class WorkKeyword(Base):
    __tablename__ = "work_keywords"
    work_id: Mapped[int] = mapped_column(ForeignKey("works.id", ondelete="CASCADE"), primary_key=True)
    keyword_id: Mapped[int] = mapped_column(ForeignKey("keywords.id", ondelete="CASCADE"), primary_key=True)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    extractor: Mapped[str | None] = mapped_column(String, nullable=True)

    work = relationship("Work", back_populates="keywords")
    keyword = relationship("Keyword")

class CoauthorEdge(Base):
    __tablename__ = "coauthor_edges"
    a_id: Mapped[int] = mapped_column(ForeignKey("authors.id", ondelete="CASCADE"), primary_key=True)
    b_id: Mapped[int] = mapped_column(ForeignKey("authors.id", ondelete="CASCADE"), primary_key=True)
    weight: Mapped[float] = mapped_column(Float, default=0.0)
    evidence_count: Mapped[int] = mapped_column(Integer, default=0)
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class OrgEdge(Base):
    __tablename__ = "org_edges"
    org1_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True)
    org2_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True)
    weight: Mapped[float] = mapped_column(Float, default=0.0)
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class NationEdge(Base):
    __tablename__ = "nation_edges"
    n1: Mapped[str] = mapped_column(String(2), primary_key=True)
    n2: Mapped[str] = mapped_column(String(2), primary_key=True)
    weight: Mapped[float] = mapped_column(Float, default=0.0)
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class MergeLog(Base):
    __tablename__ = "merges"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String)  # 'author' etc
    kept_id: Mapped[str] = mapped_column(String)
    removed_id: Mapped[str] = mapped_column(String)
    reason: Mapped[str | None] = mapped_column(String, nullable=True)
    user: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)