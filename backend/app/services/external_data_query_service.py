"""HTTP-safe series reads: route catalog ``view_name`` / ``std`` tables only (M2b).

Pure query implementations (SQL + parameterized where-clauses, no business
orchestration) now live in
``backend.app.repositories.external_data_catalog_repo`` to keep the read
path in the repository layer. This module re-exports the original public
names so existing call sites and tests keep working unchanged.
"""

from __future__ import annotations

from backend.app.repositories.external_data_catalog_repo import (
    SeriesDataPage,
    SeriesWatermark,
    fetch_series_data_page,
    fetch_series_data_recent,
    fetch_series_watermark,
)

__all__ = [
    "SeriesDataPage",
    "SeriesWatermark",
    "fetch_series_data_page",
    "fetch_series_data_recent",
    "fetch_series_watermark",
]
