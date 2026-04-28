"""Compatibility import for the product-category mapping authority.

The canonical mapping lives under ``backend.app.core_finance.config`` so
formal product-category calculations have a single source of truth.
"""

from __future__ import annotations

from backend.app.core_finance.config.product_category_mapping import (
    DEFAULT_FTP_RATE_PCT,
    DERIVATIVE_PNL_ACCOUNTS,
    FTP_RATE_PCT_BY_REPORT_YEAR,
    INTERMEDIATE_BUSINESS_PNL_ACCOUNTS,
    PRODUCT_CATEGORY_CONFIG,
    build_default_product_category_config,
    build_product_category_config_for_report_date,
    format_account_list,
    resolve_product_category_ftp_rate_pct,
)

__all__ = [
    "DEFAULT_FTP_RATE_PCT",
    "DERIVATIVE_PNL_ACCOUNTS",
    "FTP_RATE_PCT_BY_REPORT_YEAR",
    "INTERMEDIATE_BUSINESS_PNL_ACCOUNTS",
    "PRODUCT_CATEGORY_CONFIG",
    "build_default_product_category_config",
    "build_product_category_config_for_report_date",
    "format_account_list",
    "resolve_product_category_ftp_rate_pct",
]
