"""Filing metadata models for tracking document context during extraction."""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class FilingContext(BaseModel):
    """Context about a filing being processed."""

    # Core identification
    accession_number: str = Field(..., description="SEC EDGAR accession number")
    filing_type: str = Field(..., description="Form type (DEF 14A, 10-K, etc.)")
    filing_date: Optional[date] = Field(None, description="Date filing was submitted")

    # Company info
    company_cik: str = Field(..., description="Company CIK number")
    company_name: Optional[str] = Field(None, description="Company name")

    # URLs
    filing_url: Optional[str] = Field(None, description="URL to full filing")
    document_url: Optional[str] = Field(None, description="URL to specific document")

    # Processing metadata
    processed_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When this filing was processed"
    )

    def build_edgar_url(self) -> str:
        """Build SEC EDGAR URL for this filing."""
        # Convert accession number format: 0000320193-24-000081 -> 000032019324000081
        clean_accession = self.accession_number.replace("-", "")
        return (
            f"https://www.sec.gov/Archives/edgar/data/"
            f"{self.company_cik.lstrip('0')}/{clean_accession}/"
        )

    def build_filing_index_url(self) -> str:
        """Build URL to the filing index page."""
        return (
            f"https://www.sec.gov/cgi-bin/browse-edgar?"
            f"action=getcompany&CIK={self.company_cik}&type={self.filing_type}&"
            f"dateb=&owner=include&count=10"
        )


class DocumentSection(BaseModel):
    """Represents a section within a filing document."""

    name: str = Field(..., description="Section name or heading")
    start_position: int = Field(..., description="Character position where section starts")
    end_position: Optional[int] = Field(None, description="Character position where section ends")
    page_number: Optional[int] = Field(None, description="Approximate page number")

    # Content
    raw_text: Optional[str] = Field(None, description="Raw text content of section")
    html_content: Optional[str] = Field(None, description="HTML content if preserved")


class TableContext(BaseModel):
    """Context about a table being parsed."""

    table_name: Optional[str] = Field(None, description="Name/title of the table")
    section_name: Optional[str] = Field(None, description="Section containing this table")
    table_index: int = Field(default=0, description="Index of table within section")
    row_count: int = Field(default=0, description="Number of rows in table")
    column_count: int = Field(default=0, description="Number of columns")
    page_number: Optional[int] = Field(None, description="Page number if determinable")

    # Headers
    column_headers: list[str] = Field(
        default_factory=list,
        description="Column header names"
    )


class ExtractionContext(BaseModel):
    """Full context during extraction for citation building."""

    filing: FilingContext = Field(..., description="Filing being processed")
    current_section: Optional[DocumentSection] = Field(
        None, description="Current section being parsed"
    )
    current_table: Optional[TableContext] = Field(
        None, description="Current table being parsed"
    )

    def build_citation_base(self) -> dict:
        """Build base citation properties from current context."""
        return {
            "filing_accession": self.filing.accession_number,
            "filing_type": self.filing.filing_type,
            "filing_date": self.filing.filing_date,
            "filing_url": self.filing.document_url or self.filing.build_edgar_url(),
            "section_name": self.current_section.name if self.current_section else None,
            "table_name": self.current_table.table_name if self.current_table else None,
            "page_number": (
                self.current_table.page_number if self.current_table
                else (self.current_section.page_number if self.current_section else None)
            ),
        }
