"""Mobile Scan Service - manages scan sessions with token-based access for phone uploads."""
import uuid
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


class MobileScanService:
    """In-memory session store for mobile receipt scanning.

    Each session is identified by a UUID4 token and holds a list of scanned
    receipts that accumulate as the phone uploads images.  Sessions expire
    after SESSION_EXPIRY_SECONDS and are cleaned up lazily.
    """

    _sessions: dict[str, dict] = {}
    SESSION_EXPIRY_SECONDS = 900  # 15 minutes

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    @classmethod
    def create_session(cls) -> str:
        """Create a new scan session and return its token."""
        cls._cleanup_expired()
        token = uuid.uuid4().hex
        cls._sessions[token] = {
            'created_at': datetime.utcnow(),
            'receipts': [],
        }
        logger.info(f"Mobile scan session created: {token[:8]}...")
        return token

    @classmethod
    def validate_session(cls, token: str) -> Optional[dict]:
        """Return session data if the token is valid and not expired, else None."""
        session = cls._sessions.get(token)
        if not session:
            return None
        if cls._is_expired(session):
            cls._sessions.pop(token, None)
            return None
        return session

    @classmethod
    def invalidate(cls, token: str) -> None:
        """Remove a session entirely (cancel / cleanup)."""
        removed = cls._sessions.pop(token, None)
        if removed:
            logger.info(f"Mobile scan session invalidated: {token[:8]}...")

    # ------------------------------------------------------------------
    # Receipt management
    # ------------------------------------------------------------------

    @classmethod
    def add_receipt(
        cls,
        token: str,
        receipt_id: str,
        status: str = 'processing',
        ocr_result: Optional[dict] = None,
        error: Optional[str] = None,
    ) -> None:
        """Append a receipt entry to the session's receipts list."""
        session = cls.validate_session(token)
        if not session:
            raise ValueError('Invalid or expired session')
        session['receipts'].append({
            'id': receipt_id,
            'status': status,
            'ocr_result': ocr_result,
            'error': error,
        })

    @classmethod
    def update_receipt(
        cls,
        token: str,
        receipt_id: str,
        status: str,
        ocr_result: Optional[dict] = None,
        error: Optional[str] = None,
    ) -> None:
        """Update an existing receipt entry in the session."""
        session = cls.validate_session(token)
        if not session:
            return
        for receipt in session['receipts']:
            if receipt['id'] == receipt_id:
                receipt['status'] = status
                if ocr_result is not None:
                    receipt['ocr_result'] = ocr_result
                if error is not None:
                    receipt['error'] = error
                break

    @classmethod
    def get_receipts(cls, token: str) -> list[dict]:
        """Return all receipts for this session (desktop polls this)."""
        session = cls.validate_session(token)
        if not session:
            return []
        return list(session['receipts'])

    @classmethod
    def get_receipt_count(cls, token: str) -> int:
        """Return count of receipts in the session."""
        session = cls.validate_session(token)
        if not session:
            return 0
        return len(session['receipts'])

    @classmethod
    def remove_receipt(cls, token: str, receipt_id: str) -> None:
        """Remove a receipt from the queue (after user matched it)."""
        session = cls.validate_session(token)
        if not session:
            return
        session['receipts'] = [
            r for r in session['receipts'] if r['id'] != receipt_id
        ]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @classmethod
    def _is_expired(cls, session: dict) -> bool:
        cutoff = datetime.utcnow() - timedelta(seconds=cls.SESSION_EXPIRY_SECONDS)
        return session['created_at'] < cutoff

    @classmethod
    def _cleanup_expired(cls) -> None:
        """Purge sessions older than SESSION_EXPIRY_SECONDS."""
        expired = [
            t for t, s in cls._sessions.items() if cls._is_expired(s)
        ]
        for t in expired:
            cls._sessions.pop(t, None)
        if expired:
            logger.info(f"Cleaned up {len(expired)} expired mobile scan session(s)")
