"""Pydantic models for Neo4j node types."""

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


# ============================================
# Company Models
# ============================================

class CompanyBase(BaseModel):
    """Base model for Company."""

    name: str = Field(..., min_length=1, max_length=500)
    normalized_name: Optional[str] = None
    cik: Optional[str] = Field(None, pattern=r"^\d{10}$", description="SEC CIK number")
    lei: Optional[str] = Field(None, pattern=r"^[A-Z0-9]{20}$", description="Legal Entity Identifier")
    jurisdiction: Optional[str] = Field(None, max_length=100)
    incorporation_date: Optional[date] = None
    status: Optional[str] = Field(None, max_length=50)


class CompanyCreate(CompanyBase):
    """Model for creating a Company."""

    pass


class CompanyUpdate(BaseModel):
    """Model for updating a Company."""

    name: Optional[str] = Field(None, min_length=1, max_length=500)
    normalized_name: Optional[str] = None
    cik: Optional[str] = Field(None, pattern=r"^\d{10}$")
    lei: Optional[str] = Field(None, pattern=r"^[A-Z0-9]{20}$")
    jurisdiction: Optional[str] = Field(None, max_length=100)
    incorporation_date: Optional[date] = None
    status: Optional[str] = Field(None, max_length=50)


class Company(CompanyBase):
    """Full Company model with ID."""

    id: str


# ============================================
# Person Models
# ============================================

class PersonBase(BaseModel):
    """Base model for Person."""

    name: str = Field(..., min_length=1, max_length=500)
    normalized_name: Optional[str] = None
    is_pep: bool = Field(False, description="Is Politically Exposed Person")
    is_sanctioned: bool = Field(False, description="Is on sanctions list")


class PersonCreate(PersonBase):
    """Model for creating a Person."""

    pass


class PersonUpdate(BaseModel):
    """Model for updating a Person."""

    name: Optional[str] = Field(None, min_length=1, max_length=500)
    normalized_name: Optional[str] = None
    is_pep: Optional[bool] = None
    is_sanctioned: Optional[bool] = None


class Person(PersonBase):
    """Full Person model with ID."""

    id: str


# ============================================
# Address Models
# ============================================

class AddressBase(BaseModel):
    """Base model for Address."""

    full_address: str = Field(..., min_length=1)
    street: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None
    entity_count: int = Field(0, ge=0, description="Number of entities at this address")


class AddressCreate(AddressBase):
    """Model for creating an Address."""

    pass


class Address(AddressBase):
    """Full Address model with ID."""

    id: str


# ============================================
# Filing Models
# ============================================

class FilingBase(BaseModel):
    """Base model for Filing."""

    accession_number: str = Field(..., description="SEC accession number")
    form_type: str = Field(..., description="SEC form type (10-K, 10-Q, etc.)")
    filing_date: date
    source_url: Optional[str] = None


class FilingCreate(FilingBase):
    """Model for creating a Filing."""

    pass


class Filing(FilingBase):
    """Full Filing model with ID."""

    id: str


# ============================================
# Jurisdiction Models
# ============================================

class JurisdictionBase(BaseModel):
    """Base model for Jurisdiction."""

    code: str = Field(..., min_length=2, max_length=10)
    name: str = Field(..., min_length=1)
    country: str
    secrecy_score: Optional[float] = Field(None, ge=0, le=100)
    is_secrecy_jurisdiction: bool = False


class JurisdictionCreate(JurisdictionBase):
    """Model for creating a Jurisdiction."""

    pass


class Jurisdiction(JurisdictionBase):
    """Full Jurisdiction model."""

    pass
