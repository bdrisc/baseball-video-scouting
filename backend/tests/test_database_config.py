"""Tests for local and Secrets Manager database configuration."""

import json

from app import database


class FakeSecretsClient:
    """Return a controlled secret without contacting AWS."""

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self.secret_id: str | None = None

    def get_secret_value(self, *, SecretId: str) -> dict[str, str]:
        self.secret_id = SecretId
        return {"SecretString": json.dumps({"DATABASE_URL": self.database_url})}


def test_database_url_uses_local_environment(monkeypatch) -> None:
    monkeypatch.delenv("DB_SECRET_ARN", raising=False)
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://local:password@localhost/baseball_video_scouting",
    )
    database.get_database_url.cache_clear()

    assert database.get_database_url().startswith("postgresql://local:")

    database.get_database_url.cache_clear()


def test_database_url_uses_secrets_manager(monkeypatch) -> None:
    secret_arn = "arn:aws:secretsmanager:us-east-1:123456789012:secret:test"
    expected_url = (
        "postgresql://baseball_app:password@example.neon.tech/"
        "baseball_video_scouting?sslmode=require"
    )
    fake_client = FakeSecretsClient(expected_url)

    def fake_boto_client(service_name: str) -> FakeSecretsClient:
        assert service_name == "secretsmanager"
        return fake_client

    monkeypatch.setenv("DB_SECRET_ARN", secret_arn)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(database.boto3, "client", fake_boto_client)
    database.get_database_url.cache_clear()

    assert database.get_database_url() == expected_url
    assert fake_client.secret_id == secret_arn

    database.get_database_url.cache_clear()
