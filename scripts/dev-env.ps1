$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot

$env:MOSS_ENVIRONMENT = "development"
$env:MOSS_POSTGRES_DSN = "postgresql://moss:moss@localhost:5432/moss"
$env:MOSS_REDIS_DSN = "redis://localhost:6379/0"
$env:MOSS_DUCKDB_PATH = Join-Path $root "data\moss.duckdb"
$env:MOSS_OBJECT_STORE_MODE = "local"
$env:MOSS_LOCAL_ARCHIVE_PATH = Join-Path $root "data\archive"
$env:MOSS_MINIO_ENDPOINT = "localhost:9000"
$env:MOSS_MINIO_ACCESS_KEY = "minioadmin"
$env:MOSS_MINIO_SECRET_KEY = "minioadmin"
$env:MOSS_MINIO_BUCKET = "moss-artifacts"
