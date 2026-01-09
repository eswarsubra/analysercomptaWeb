from datetime import date
from dateutil.relativedelta import relativedelta
from typing import Optional

from analysercomptacore.services import BankService as CoreBankService
from app.database import get_db


class BankInstructionService:
    """Service for BankInstruction operations - wraps Core's BankService."""

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
        # Convert date objects to strings for Core
        date_from_str = date_from.strftime('%Y-%m-%d') if date_from else None
        date_to_str = date_to.strftime('%Y-%m-%d') if date_to else None

        with get_db() as db:
            return CoreBankService.get_transactions_by_date_range(
                db,
                date_from=date_from_str,
                date_to=date_to_str,
                libelle_filter=libelle,
                montant_filter=montant,
                filename_filter=filename,
                limit=limit
            )

    @staticmethod
    def get_by_id(transaction_id: int) -> Optional[dict]:
        """Get a transaction by ID."""
        with get_db() as db:
            return CoreBankService.get_transaction_by_id(db, transaction_id)

    @staticmethod
    def get_distinct_filenames() -> list[str]:
        """Get all distinct filenames for filter dropdown."""
        with get_db() as db:
            return CoreBankService.get_distinct_filenames(db)

    @staticmethod
    def get_count(
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        libelle: Optional[str] = None,
        montant: Optional[float] = None,
        filename: Optional[str] = None
    ) -> int:
        """Get count of transactions matching filters."""
        # Convert date objects to strings for Core
        date_from_str = date_from.strftime('%Y-%m-%d') if date_from else None
        date_to_str = date_to.strftime('%Y-%m-%d') if date_to else None

        with get_db() as db:
            return CoreBankService.get_transaction_count(
                db,
                date_from=date_from_str,
                date_to=date_to_str,
                libelle_filter=libelle,
                montant_filter=montant,
                filename_filter=filename
            )

    @staticmethod
    def get_distinct_months_years() -> dict:
        """Get distinct months and years from transactions.

        Returns:
            Dict with 'months' (list of ints 1-12) and 'years' (list of ints)
        """
        with get_db() as db:
            return CoreBankService.get_distinct_months_years(db)

    @staticmethod
    def get_classified_transactions(month: int, year: int) -> list[dict]:
        """Get transactions with Type and Qualifier classification.

        Args:
            month: Month number (1-12)
            year: Year (e.g., 2025)

        Returns:
            List of dicts with columns:
            Type, Qualifier, Libelle, Montant, Date_comptabilisation,
            Date_operation, Date_valeur, TransactionID, Reference
        """
        with get_db() as db:
            return CoreBankService.get_classified_transactions_for_month_year(db, month, year)

    @staticmethod
    def get_monthly_summary(month: int, year: int) -> list[dict]:
        """Get monthly summary of transactions by category.

        Args:
            month: Month number (1-12)
            year: Year (e.g., 2025)

        Returns:
            List of dicts with Type, Name, Montant
        """
        with get_db() as db:
            return CoreBankService.build_monthly_summary(db, month, year)
