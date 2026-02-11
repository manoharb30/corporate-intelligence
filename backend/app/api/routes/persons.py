"""Person-related API endpoints."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.models import (
    Person,
    PersonCreate,
    PersonUpdate,
    PaginatedResponse,
    Company,
)
from app.services.person_service import PersonService

router = APIRouter()


@router.get("", response_model=PaginatedResponse[Person])
async def list_persons(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    is_pep: Optional[bool] = None,
    is_sanctioned: Optional[bool] = None,
) -> PaginatedResponse[Person]:
    """List persons with optional filtering."""
    return await PersonService.list_persons(
        page=page,
        page_size=page_size,
        is_pep=is_pep,
        is_sanctioned=is_sanctioned,
    )


@router.get("/search")
async def search_persons(
    q: str = Query(..., min_length=2),
    limit: int = Query(10, ge=1, le=50),
) -> list[Person]:
    """Search persons by name."""
    return await PersonService.search_by_name(q, limit)


@router.get("/pep", response_model=list[Person])
async def list_peps(
    limit: int = Query(50, ge=1, le=200),
) -> list[Person]:
    """List all Politically Exposed Persons."""
    return await PersonService.list_peps(limit)


@router.get("/sanctioned", response_model=list[Person])
async def list_sanctioned(
    limit: int = Query(50, ge=1, le=200),
) -> list[Person]:
    """List all sanctioned persons."""
    return await PersonService.list_sanctioned(limit)


@router.get("/{person_id}", response_model=Person)
async def get_person(person_id: str) -> Person:
    """Get a person by ID."""
    person = await PersonService.get_by_id(person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    return person


@router.get("/{person_id}/companies", response_model=list[Company])
async def get_person_companies(person_id: str) -> list[Company]:
    """Get companies associated with a person (owned, officer, director)."""
    return await PersonService.get_associated_companies(person_id)


@router.post("", response_model=Person, status_code=201)
async def create_person(person: PersonCreate) -> Person:
    """Create a new person."""
    return await PersonService.create(person)


@router.patch("/{person_id}", response_model=Person)
async def update_person(person_id: str, person: PersonUpdate) -> Person:
    """Update a person."""
    updated = await PersonService.update(person_id, person)
    if not updated:
        raise HTTPException(status_code=404, detail="Person not found")
    return updated


@router.delete("/{person_id}", status_code=204)
async def delete_person(person_id: str) -> None:
    """Delete a person."""
    deleted = await PersonService.delete(person_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Person not found")
