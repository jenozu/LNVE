"""
database/repository.py — SQLite persistence for the lean LNVE MVP.

Phase 2 adds the fields needed to qualify Google Places prospects:
rating, review count, website URL, Place ID, business status, Maps URL,
and coordinates. Existing databases are migrated in place.
"""

import logging
import sqlite3
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

from config import settings

logger = logging.getLogger(__name__)


_SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS searches (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    search_type         TEXT    NOT NULL,
    location_name       TEXT    NOT NULL,
    latitude            REAL    NOT NULL DEFAULT 0,
    longitude           REAL    NOT NULL DEFAULT 0,
    radius_km           REAL    NOT NULL,
    min_rating          REAL    NOT NULL DEFAULT 0,
    min_reviews         INTEGER NOT NULL DEFAULT 0,
    status              TEXT    NOT NULL DEFAULT 'pending',
    gmaps_status        TEXT    NOT NULL DEFAULT 'pending',
    yellowpages_status  TEXT    NOT NULL DEFAULT 'skipped',
    total_leads         INTEGER NOT NULL DEFAULT 0,
    gmaps_leads         INTEGER NOT NULL DEFAULT 0,
    yellowpages_leads   INTEGER NOT NULL DEFAULT 0,
    market_score        INTEGER,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS leads (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    search_id               INTEGER NOT NULL REFERENCES searches(id),
    place_id                TEXT,
    business_name           TEXT    NOT NULL,
    address                 TEXT,
    phone_number            TEXT,
    rating                  REAL,
    review_count            INTEGER NOT NULL DEFAULT 0,
    website_url             TEXT,
    website_status          TEXT,
    business_status         TEXT,
    google_maps_url         TEXT,
    latitude                REAL,
    longitude               REAL,
    source                  TEXT    NOT NULL DEFAULT 'google_maps',
    email                   TEXT,
    contact_name            TEXT,
    enrichment_source       TEXT,
    enrichment_confidence   INTEGER DEFAULT 0,
    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(search_id, business_name)
);

"""


_SAFE_MIGRATIONS = [
    # Historical lead/enrichment columns.
    "ALTER TABLE leads ADD COLUMN email TEXT",
    "ALTER TABLE leads ADD COLUMN contact_name TEXT",
    "ALTER TABLE leads ADD COLUMN enrichment_source TEXT",
    "ALTER TABLE leads ADD COLUMN enrichment_confidence INTEGER DEFAULT 0",

    # Historical search/source columns.
    "ALTER TABLE searches ADD COLUMN gmaps_status TEXT NOT NULL DEFAULT 'pending'",
    "ALTER TABLE searches ADD COLUMN yellowpages_status TEXT NOT NULL DEFAULT 'skipped'",
    "ALTER TABLE searches ADD COLUMN gmaps_leads INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE searches ADD COLUMN yellowpages_leads INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE searches ADD COLUMN market_score INTEGER",
    "ALTER TABLE searches ADD COLUMN latitude REAL NOT NULL DEFAULT 0",
    "ALTER TABLE searches ADD COLUMN longitude REAL NOT NULL DEFAULT 0",

    # Phase 2 search qualification settings.
    "ALTER TABLE searches ADD COLUMN min_rating REAL NOT NULL DEFAULT 0",
    "ALTER TABLE searches ADD COLUMN min_reviews INTEGER NOT NULL DEFAULT 0",

    # Phase 2 Google Places prospect fields.
    "ALTER TABLE leads ADD COLUMN place_id TEXT",
    "ALTER TABLE leads ADD COLUMN rating REAL",
    "ALTER TABLE leads ADD COLUMN review_count INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE leads ADD COLUMN website_url TEXT",
    "ALTER TABLE leads ADD COLUMN business_status TEXT",
    "ALTER TABLE leads ADD COLUMN google_maps_url TEXT",
    "ALTER TABLE leads ADD COLUMN latitude REAL",
    "ALTER TABLE leads ADD COLUMN longitude REAL",
]


@contextmanager
def _connect(db_path: str):
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=30000")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


class Repository:
    """All SQLite operations used by the active MVP."""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or settings.DATABASE_PATH

    def init(self) -> None:
        """Create a fresh schema or safely migrate an older LNVE database."""
        with _connect(self.db_path) as conn:
            conn.executescript(_SCHEMA_SQL)

            for stmt in _SAFE_MIGRATIONS:
                try:
                    conn.execute(stmt)
                except sqlite3.OperationalError as exc:
                    # Expected when the column already exists.
                    if "duplicate column name" not in str(exc).lower():
                        raise

            # Create indexes only after migrations so older databases that
            # predate these columns can still upgrade cleanly.
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_leads_search ON leads(search_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_leads_email ON leads(email)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_searches_status ON searches(status)"
            )
            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_leads_search_place
                ON leads(search_id, place_id)
                WHERE place_id IS NOT NULL
                """
            )

        logger.info("Database initialised: %s", self.db_path)

    # ── Searches ──────────────────────────────────────────────

    def create_search(
        self,
        search_type: str,
        location_name: str,
        radius_km: float,
        latitude: float = 0.0,
        longitude: float = 0.0,
        min_rating: float = 0.0,
        min_reviews: int = 0,
        gmaps_status: str = "pending",
        yellowpages_status: str = "skipped",
        overall_status: str = "running",
    ) -> int:
        with _connect(self.db_path) as conn:
            cur = conn.execute(
                """
                INSERT INTO searches
                    (search_type, location_name, latitude, longitude,
                     radius_km, min_rating, min_reviews, status,
                     gmaps_status, yellowpages_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    search_type,
                    location_name,
                    latitude,
                    longitude,
                    radius_km,
                    min_rating,
                    min_reviews,
                    overall_status,
                    gmaps_status,
                    yellowpages_status,
                ),
            )
            return cur.lastrowid

    def get_search(self, search_id: int) -> Optional[Dict]:
        with _connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM searches WHERE id = ?", (search_id,)
            ).fetchone()
            return dict(row) if row else None

    def list_searches(self, limit: int = 100) -> List[Dict]:
        with _connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM searches ORDER BY created_at DESC, id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    def update_search_status(
        self,
        search_id: int,
        source: str,
        status: str,
        leads_count: Optional[int] = None,
    ) -> None:
        with _connect(self.db_path) as conn:
            if source == "gmaps":
                conn.execute(
                    "UPDATE searches SET gmaps_status = ? WHERE id = ?",
                    (status, search_id),
                )
                if leads_count is not None:
                    conn.execute(
                        "UPDATE searches SET gmaps_leads = ? WHERE id = ?",
                        (leads_count, search_id),
                    )
            elif source == "yellowpages":
                conn.execute(
                    "UPDATE searches SET yellowpages_status = ? WHERE id = ?",
                    (status, search_id),
                )
                if leads_count is not None:
                    conn.execute(
                        "UPDATE searches SET yellowpages_leads = ? WHERE id = ?",
                        (leads_count, search_id),
                    )
            elif source == "overall":
                conn.execute(
                    "UPDATE searches SET status = ? WHERE id = ?",
                    (status, search_id),
                )

            self._recompute_totals(conn, search_id)

    def recompute_overall_status(self, search_id: int) -> None:
        with _connect(self.db_path) as conn:
            self._recompute_totals(conn, search_id)

    def _recompute_totals(self, conn: sqlite3.Connection, search_id: int) -> None:
        row = conn.execute(
            "SELECT gmaps_status, yellowpages_status FROM searches WHERE id = ?",
            (search_id,),
        ).fetchone()
        if not row:
            return

        gm, yp = row["gmaps_status"], row["yellowpages_status"]
        active = {"running", "pending"}

        if gm in active or yp in active:
            overall = "running"
        elif gm == "cancelled" and yp in {"cancelled", "skipped"}:
            overall = "cancelled"
        elif gm == "failed" and yp in {"failed", "skipped"}:
            overall = "failed"
        else:
            overall = "completed"

        conn.execute(
            """
            UPDATE searches
            SET status = ?,
                total_leads = (
                    SELECT COUNT(*) FROM leads WHERE search_id = ?
                )
            WHERE id = ?
            """,
            (overall, search_id, search_id),
        )

    def cancel_search(self, search_id: int, source: str = "all") -> None:
        with _connect(self.db_path) as conn:
            if source in ("all", "gmaps"):
                conn.execute(
                    """
                    UPDATE searches
                    SET gmaps_status = 'cancelled'
                    WHERE id = ? AND gmaps_status IN ('running', 'pending')
                    """,
                    (search_id,),
                )
            if source in ("all", "yellowpages"):
                conn.execute(
                    """
                    UPDATE searches
                    SET yellowpages_status = 'cancelled'
                    WHERE id = ? AND yellowpages_status IN ('running', 'pending')
                    """,
                    (search_id,),
                )
            self._recompute_totals(conn, search_id)

    def is_cancelled(self, search_id: int, source: str) -> bool:
        col = "gmaps_status" if source == "gmaps" else "yellowpages_status"
        with _connect(self.db_path) as conn:
            row = conn.execute(
                f"SELECT {col} FROM searches WHERE id = ?",
                (search_id,),
            ).fetchone()
            return bool(row and row[0] == "cancelled")

    def save_market_score(self, search_id: int, score: int) -> None:
        """Retained only for backward compatibility with archived modules."""
        with _connect(self.db_path) as conn:
            conn.execute(
                "UPDATE searches SET market_score = ? WHERE id = ?",
                (score, search_id),
            )

    # ── Leads ─────────────────────────────────────────────────

    def insert_lead(
        self,
        search_id: int,
        place_id: Optional[str],
        business_name: str,
        address: str = "",
        phone_number: str = "",
        rating: Optional[float] = None,
        review_count: int = 0,
        website_url: Optional[str] = None,
        business_status: str = "",
        google_maps_url: str = "",
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        source: str = "google_maps",
    ) -> bool:
        """
        Insert one qualified Google prospect.

        Businesses with and without websites are both stored. The existing
        website_status column is retained for compatibility with the old app;
        Phase 3 will use it to split the two prospect pools in the UI.
        """
        website_status = "Has Website" if website_url else "No Website Found"

        with _connect(self.db_path) as conn:
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO leads
                    (
                        search_id, place_id, business_name, address, phone_number,
                        rating, review_count, website_url, website_status,
                        business_status, google_maps_url, latitude, longitude, source
                    )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    search_id,
                    place_id,
                    business_name,
                    address,
                    phone_number,
                    rating,
                    int(review_count or 0),
                    website_url,
                    website_status,
                    business_status,
                    google_maps_url,
                    latitude,
                    longitude,
                    source,
                ),
            )
            return cur.rowcount > 0

    def get_leads_for_search(self, search_id: int) -> List[Dict]:
        with _connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM leads
                WHERE search_id = ?
                ORDER BY review_count DESC, rating DESC, business_name
                """,
                (search_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_recent_leads(self, limit: int = 50) -> List[Dict]:
        with _connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT l.*, s.search_type, s.location_name
                FROM leads l
                JOIN searches s ON l.search_id = s.id
                ORDER BY l.created_at DESC, l.id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Legacy enrichment compatibility ───────────────────────

    def get_leads_pending_enrichment(self, batch_size: int = 50) -> List[Dict]:
        with _connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT id, business_name, address, phone_number
                FROM leads
                WHERE (email IS NULL OR email = '')
                  AND business_name IS NOT NULL
                  AND business_name != 'N/A'
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (batch_size,),
            ).fetchall()
            return [dict(r) for r in rows]

    def update_lead_enrichment(
        self,
        lead_id: int,
        email: str,
        contact_name: str,
        source: str,
        confidence: int,
    ) -> None:
        with _connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE leads
                SET email = ?, contact_name = ?,
                    enrichment_source = ?, enrichment_confidence = ?
                WHERE id = ?
                """,
                (email, contact_name, source, confidence, lead_id),
            )

    def get_all_leads_for_export(self, limit: int = 5000) -> List[Dict]:
        """
        Legacy export shape retained until Phase 4 expands the CSV.
        For now, the all-leads export still returns the immediate no-site pool.
        """
        with _connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT
                    l.business_name, l.address, l.phone_number,
                    COALESCE(l.email, '')                AS email,
                    COALESCE(l.contact_name, '')         AS contact_name,
                    l.source,
                    COALESCE(l.enrichment_source, '')    AS enrichment_source,
                    COALESCE(l.enrichment_confidence, 0) AS enrichment_confidence,
                    l.created_at,
                    s.search_type,
                    s.location_name
                FROM leads l
                JOIN searches s ON l.search_id = s.id
                WHERE l.website_status = 'No Website Found'
                ORDER BY l.created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Legacy analytics compatibility ────────────────────────

    def get_analytics(self) -> Dict[str, Any]:
        with _connect(self.db_path) as conn:
            total_searches = conn.execute(
                "SELECT COUNT(*) FROM searches"
            ).fetchone()[0]
            total_leads = conn.execute(
                "SELECT COUNT(*) FROM leads"
            ).fetchone()[0]
            completed = conn.execute(
                "SELECT COUNT(*) FROM searches WHERE status = 'completed'"
            ).fetchone()[0]
            enriched = conn.execute(
                "SELECT COUNT(*) FROM leads WHERE email IS NOT NULL AND email != ''"
            ).fetchone()[0]

            by_source = conn.execute(
                "SELECT source, COUNT(*) AS count FROM leads GROUP BY source"
            ).fetchall()
            by_type = conn.execute(
                """
                SELECT s.search_type, COUNT(l.id) AS count
                FROM searches s
                LEFT JOIN leads l ON l.search_id = s.id
                GROUP BY s.search_type
                """
            ).fetchall()
            by_date = conn.execute(
                """
                SELECT date(created_at) AS date, COUNT(*) AS count
                FROM searches
                GROUP BY date(created_at)
                ORDER BY date(created_at) DESC
                LIMIT 30
                """
            ).fetchall()

            avg = total_leads / total_searches if total_searches else 0

            return {
                "total_searches": total_searches,
                "total_leads": total_leads,
                "completed_searches": completed,
                "avg_leads_per_search": round(avg, 1),
                "enriched_count": enriched,
                "unenriched_count": total_leads - enriched,
                "by_source": [dict(r) for r in by_source],
                "by_type": [dict(r) for r in by_type],
                "by_date": [dict(r) for r in by_date],
            }
