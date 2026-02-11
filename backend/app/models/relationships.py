"""Pydantic models for Neo4j relationship types."""

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class OwnershipBase(BaseModel):
    """Base model for OWNS relationship."""

    percentage: Optional[float] = Field(None, ge=0, le=100)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    source: Optional[str] = None
    is_beneficial: bool = Field(True, description="Is beneficial ownership")


class OwnershipCreate(OwnershipBase):
    """Model for creating an ownership relationship."""

    owner_id: str
    owned_id: str


class Ownership(OwnershipBase):
    """Full ownership relationship with entity details."""

    owner_id: str
    owner_name: str
    owner_type: str  # "Company" or "Person"
    owned_id: str
    owned_name: str


class OfficerRelation(BaseModel):
    """Model for OFFICER_OF relationship."""

    person_id: str
    company_id: str
    title: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class DirectorRelation(BaseModel):
    """Model for DIRECTOR_OF relationship."""

    person_id: str
    company_id: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class SameAsRelation(BaseModel):
    """Model for SAME_AS relationship (entity resolution)."""

    entity1_id: str
    entity2_id: str
    confidence: float = Field(..., ge=0, le=1)
    match_method: str = Field(..., description="Method used to determine match")
