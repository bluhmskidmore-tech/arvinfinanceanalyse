from tests.helpers import load_module


def test_network_backed_repositories_report_unreachable_endpoints_as_not_ok():
    postgres_module = load_module("backend.app.repositories.postgres_repo", "backend/app/repositories/postgres_repo.py")
    redis_module = load_module("backend.app.repositories.redis_repo", "backend/app/repositories/redis_repo.py")
    object_store_module = load_module("backend.app.repositories.object_store_repo", "backend/app/repositories/object_store_repo.py")

    postgres_repo = postgres_module.PostgresRepository("postgresql://u:p@127.0.0.1:1/db")
    redis_repo = redis_module.RedisRepository("redis://127.0.0.1:1/0")
    object_store_repo = object_store_module.ObjectStoreRepository(
        endpoint="127.0.0.1:1",
        access_key="minioadmin",
        secret_key="minioadmin",
        bucket="moss-artifacts",
    )

    assert postgres_repo.healthcheck()["ok"] is False
    assert redis_repo.healthcheck()["ok"] is False
    assert object_store_repo.healthcheck()["ok"] is False
