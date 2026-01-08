from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from typing import Optional
from sqlalchemy import func
from app.database import get_db
from app.models import BankInstruction


class BankInstructionService:
    """Service for BankInstruction operations - read-only transaction viewing."""

    @staticmethod
    def get_default_date_range() -> tuple[date, date]:
        """Get default date range: first and last day of previous month."""
        today = date.today()
        first_of_current_month = today.replace(day=1)
        last_of_previous_month = first_of_current_month - relativedelta(days=1)
        first_of_previous_month = last_of_previous_month.replace(day=1)
        return first_of_previous_month, last_of_previous_month

    @staticmethod
    def get_all(
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        libelle: Optional[str] = None,
        montant: Optional[float] = None,
        filename: Optional[str] = None,
        limit: int = 500
    ) -> list[dict]:
        """Get transactions with optional filters.

        Args:
            date_from: Start date for Date de comptabilisation filter
            date_to: End date for Date de comptabilisation filter
            libelle: Text search in Libelle field (case-insensitive)
            montant: Filter by exact Montant value
            filename: Filter by filename (case-insensitive contains)
            limit: Maximum number of records to return (default 500)

        Returns:
            List of transaction dictionaries
        """
        with get_db() as db:
            query = db.query(BankInstruction)

            # Date range filter
            if date_from:
                query = query.filter(BankInstruction.Date_de_comptabilisation >= date_from)
            if date_to:
                # Include the entire end date
                query = query.filter(BankInstruction.Date_de_comptabilisation <= date_to)

            # Libelle text search
            if libelle:
                query = query.filter(BankInstruction.Libelle.ilike(f'%{libelle}%'))

            # Montant filter
            if montant is not None:
                query = query.filter(BankInstruction.Montant == montant)

            # Filename filter
            if filename:
                query = query.filter(BankInstruction.filename.ilike(f'%{filename}%'))

            # Order by date descending and limit
            results = query.order_by(
                BankInstruction.Date_de_comptabilisation.desc(),
                BankInstruction.TransactionID.desc()
            ).limit(limit).all()

            return [row.to_dict() for row in results]

    @staticmethod
    def get_by_id(transaction_id: int) -> Optional[dict]:
        """Get a transaction by ID."""
        with get_db() as db:
            transaction = db.query(BankInstruction).filter(
                BankInstruction.TransactionID == transaction_id
            ).first()
            return transaction.to_dict() if transaction else None

    @staticmethod
    def get_distinct_filenames() -> list[str]:
        """Get all distinct filenames for filter dropdown."""
        with get_db() as db:
            filenames = db.query(BankInstruction.filename).distinct().filter(
                BankInstruction.filename.isnot(None)
            ).order_by(BankInstruction.filename).all()
            return [f[0] for f in filenames if f[0]]

    @staticmethod
    def get_count(
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        libelle: Optional[str] = None,
        montant: Optional[float] = None,
        filename: Optional[str] = None
    ) -> int:
        """Get count of transactions matching filters."""
        with get_db() as db:
            query = db.query(func.count(BankInstruction.TransactionID))

            if date_from:
                query = query.filter(BankInstruction.Date_de_comptabilisation >= date_from)
            if date_to:
                query = query.filter(BankInstruction.Date_de_comptabilisation <= date_to)
            if libelle:
                query = query.filter(BankInstruction.Libelle.ilike(f'%{libelle}%'))
            if montant is not None:
                query = query.filter(BankInstruction.Montant == montant)
            if filename:
                query = query.filter(BankInstruction.filename.ilike(f'%{filename}%'))

            return query.scalar()
