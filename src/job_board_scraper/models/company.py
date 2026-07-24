"""Company model.

Re-exports from the SQLAlchemy company model for backwards compatibility.
"""

from job_board_scraper.models.db_company import AdapterType, Company

__all__ = ["AdapterType", "Company"]
