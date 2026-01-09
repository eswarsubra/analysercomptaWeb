"""Sales Service - wraps Core's SalesService for web operations."""
from datetime import date
from typing import Optional

from analysercomptacore.services import SalesService as CoreSalesService
from app.database import get_db


class SalesService:
    """Service for Sales operations - wraps Core's SalesService."""

    @staticmethod
    def get_payments_for_date_range(
        date_from: date,
        date_to: date
    ) -> list[dict]:
        """Get sales payments within a date range.

        Args:
            date_from: Start date (inclusive)
            date_to: End date (inclusive)

        Returns:
            List of payment dicts
        """
        with get_db() as db:
            return CoreSalesService.get_payments_for_date_range(db, date_from, date_to)

    @staticmethod
    def get_product_sales_summary(
        date_from: date,
        date_to: date,
        target_date: Optional[date] = None
    ) -> list[dict]:
        """Get aggregated product sales summary.

        Args:
            date_from: Start date for period
            date_to: End date for period
            target_date: If provided, filter to this specific date only

        Returns:
            List of dicts with ProductName, Quantity, TotalSales
        """
        with get_db() as db:
            return CoreSalesService.get_product_sales_summary(
                db, date_from, date_to, target_date
            )
