from __future__ import annotations

# Keep historical explicit imports usable without collecting these aliases a
# second time during full pytest discovery.
__test__ = False

from tests.test_service_storage_boundaries import (
    test_api_and_service_layers_do_not_call_repository_replace_writers,
    test_api_and_service_layers_do_not_open_repository_task_write_scope,
    test_api_and_service_layers_do_not_open_writable_duckdb_connections,
    test_api_routes_do_not_reference_duckdb_directly,
)
