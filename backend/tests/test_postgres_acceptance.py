import os

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from asa.bootstrap import build_application
from asa.config import Settings


@pytest.mark.postgres
@pytest.mark.skipif(not os.getenv("ASA_TEST_DATABASE_URL"), reason="ASA_TEST_DATABASE_URL not set")
def test_aapl_is_ingested_persisted_and_queried_from_postgres() -> None:
    database_url = os.environ["ASA_TEST_DATABASE_URL"]
    os.environ["ASA_DATABASE_URL"] = database_url
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM market_observations"))
    client = TestClient(build_application(Settings(database_url=database_url)))

    assert (
        client.post("/api/v1/market/quotes/ingest", json={"symbols": ["AAPL"]}).status_code == 200
    )
    response = client.get("/api/v1/market/quotes/AAPL")

    assert response.status_code == 200
    assert response.json()["provenance"]["selected_provider"] == "deterministic_fake"
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM market_observations")) == 1
