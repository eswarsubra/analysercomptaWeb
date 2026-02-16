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
            List of dicts with ProductName, Quantity, TotalSales, TVA, TVAAmount
        """
        with get_db() as db:
            results = CoreSalesService.get_product_sales_summary(
                db, date_from, date_to, target_date
            )

        # Calculate TVAAmount from TotalSales (TTC) and TVA rate
        # Formula: TVA_Amount = TTC * TVA_rate / (100 + TVA_rate)
        for row in results:
            total_sales = row.get('TotalSales') or 0
            tva_rate = row.get('TVA') or 0
            if tva_rate > 0 and total_sales > 0:
                row['TVAAmount'] = round(total_sales * tva_rate / (100 + tva_rate), 2)
            else:
                row['TVAAmount'] = 0

        return results
