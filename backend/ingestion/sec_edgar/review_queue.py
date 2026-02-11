"""Review queue for failed or low-confidence extractions."""

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional
from enum import Enum

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ReviewStatus(str, Enum):
    """Status of a review item."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    MODIFIED = "modified"


class ReviewItem(BaseModel):
    """An item in the review queue."""

    id: Optional[int] = None
    filing_accession: str
    filing_type: str
    company_cik: str
    company_name: Optional[str] = None
    extraction_type: str  # "ownership", "subsidiary", "officer"
    raw_text: str
    attempted_extraction: Optional[dict] = None
    failure_reason: Optional[str] = None
    confidence: Optional[float] = None
    status: ReviewStatus = ReviewStatus.PENDING
    created_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[str] = None
    corrected_data: Optional[dict] = None


class ReviewQueue:
    """SQLite-based queue for human review of failed/low-confidence extractions."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            # Default to a file in the backend directory
            db_path = Path(__file__).parent.parent.parent / "review_queue.db"

        self.db_path = str(db_path)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the SQLite database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS review_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filing_accession TEXT NOT NULL,
                filing_type TEXT NOT NULL,
                company_cik TEXT NOT NULL,
                company_name TEXT,
                extraction_type TEXT NOT NULL,
                raw_text TEXT NOT NULL,
                attempted_extraction TEXT,
                failure_reason TEXT,
                confidence REAL,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reviewed_at TIMESTAMP,
                reviewed_by TEXT,
                corrected_data TEXT
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_status ON review_queue(status)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_company ON review_queue(company_cik)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_filing ON review_queue(filing_accession)
        """)

        conn.commit()
        conn.close()

    def add(self, item: ReviewItem) -> int:
        """Add an item to the review queue."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO review_queue (
                filing_accession, filing_type, company_cik, company_name,
                extraction_type, raw_text, attempted_extraction, failure_reason,
                confidence, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            item.filing_accession,
            item.filing_type,
            item.company_cik,
            item.company_name,
            item.extraction_type,
            item.raw_text[:100000],  # Limit text size
            json.dumps(item.attempted_extraction) if item.attempted_extraction else None,
            item.failure_reason,
            item.confidence,
            item.status.value,
        ))

        item_id = cursor.lastrowid
        conn.commit()
        conn.close()

        logger.info(f"Added review item {item_id} for {item.filing_accession}")
        return item_id

    def add_failed_extraction(
        self,
        filing_accession: str,
        filing_type: str,
        company_cik: str,
        extraction_type: str,
        raw_text: str,
        failure_reason: str,
        company_name: Optional[str] = None,
        attempted_extraction: Optional[dict] = None,
    ) -> int:
        """Convenience method to add a failed extraction."""
        item = ReviewItem(
            filing_accession=filing_accession,
            filing_type=filing_type,
            company_cik=company_cik,
            company_name=company_name,
            extraction_type=extraction_type,
            raw_text=raw_text,
            attempted_extraction=attempted_extraction,
            failure_reason=failure_reason,
            status=ReviewStatus.PENDING,
        )
        return self.add(item)

    def add_low_confidence(
        self,
        filing_accession: str,
        filing_type: str,
        company_cik: str,
        extraction_type: str,
        raw_text: str,
        confidence: float,
        attempted_extraction: dict,
        company_name: Optional[str] = None,
    ) -> int:
        """Convenience method to add a low-confidence extraction."""
        item = ReviewItem(
            filing_accession=filing_accession,
            filing_type=filing_type,
            company_cik=company_cik,
            company_name=company_name,
            extraction_type=extraction_type,
            raw_text=raw_text,
            attempted_extraction=attempted_extraction,
            confidence=confidence,
            failure_reason=f"Low confidence: {confidence:.2f}",
            status=ReviewStatus.PENDING,
        )
        return self.add(item)

    def get_pending(self, limit: int = 100) -> list[ReviewItem]:
        """Get pending review items."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM review_queue
            WHERE status = 'pending'
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))

        items = []
        for row in cursor.fetchall():
            items.append(self._row_to_item(row))

        conn.close()
        return items

    def get_by_id(self, item_id: int) -> Optional[ReviewItem]:
        """Get a review item by ID."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM review_queue WHERE id = ?", (item_id,))
        row = cursor.fetchone()

        conn.close()

        if row:
            return self._row_to_item(row)
        return None

    def get_by_company(self, cik: str, limit: int = 50) -> list[ReviewItem]:
        """Get review items for a specific company."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM review_queue
            WHERE company_cik = ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (cik, limit))

        items = [self._row_to_item(row) for row in cursor.fetchall()]
        conn.close()
        return items

    def approve(
        self,
        item_id: int,
        reviewed_by: str,
        corrected_data: Optional[dict] = None,
    ) -> bool:
        """Approve a review item, optionally with corrections."""
        status = ReviewStatus.MODIFIED if corrected_data else ReviewStatus.APPROVED
        return self._update_status(item_id, status, reviewed_by, corrected_data)

    def reject(self, item_id: int, reviewed_by: str) -> bool:
        """Reject a review item."""
        return self._update_status(item_id, ReviewStatus.REJECTED, reviewed_by)

    def _update_status(
        self,
        item_id: int,
        status: ReviewStatus,
        reviewed_by: str,
        corrected_data: Optional[dict] = None,
    ) -> bool:
        """Update the status of a review item."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE review_queue
            SET status = ?, reviewed_at = ?, reviewed_by = ?, corrected_data = ?
            WHERE id = ?
        """, (
            status.value,
            datetime.utcnow().isoformat(),
            reviewed_by,
            json.dumps(corrected_data) if corrected_data else None,
            item_id,
        ))

        updated = cursor.rowcount > 0
        conn.commit()
        conn.close()

        return updated

    def get_stats(self) -> dict:
        """Get statistics about the review queue."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT status, COUNT(*) as count
            FROM review_queue
            GROUP BY status
        """)

        stats = {row[0]: row[1] for row in cursor.fetchall()}

        cursor.execute("SELECT COUNT(*) FROM review_queue")
        stats["total"] = cursor.fetchone()[0]

        conn.close()
        return stats

    def _row_to_item(self, row: sqlite3.Row) -> ReviewItem:
        """Convert a database row to a ReviewItem."""
        return ReviewItem(
            id=row["id"],
            filing_accession=row["filing_accession"],
            filing_type=row["filing_type"],
            company_cik=row["company_cik"],
            company_name=row["company_name"],
            extraction_type=row["extraction_type"],
            raw_text=row["raw_text"],
            attempted_extraction=json.loads(row["attempted_extraction"]) if row["attempted_extraction"] else None,
            failure_reason=row["failure_reason"],
            confidence=row["confidence"],
            status=ReviewStatus(row["status"]),
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
            reviewed_at=datetime.fromisoformat(row["reviewed_at"]) if row["reviewed_at"] else None,
            reviewed_by=row["reviewed_by"],
            corrected_data=json.loads(row["corrected_data"]) if row["corrected_data"] else None,
        )
