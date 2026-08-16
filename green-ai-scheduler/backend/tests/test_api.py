import asyncio

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.api.main import create_app


@pytest_asyncio.fixture
async def client(tmp_path, monkeypatch):
    db_path = tmp_path / "api_test.db"
    ckpt = tmp_path / "ckpt"
    ckpt.mkdir()
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.setenv("CHECKPOINT_DIR", str(ckpt))
    monkeypatch.setenv("TICK_INTERVAL_SECONDS", "3600")
    app = create_app()
    transport = ASGITransport(app=app, lifespan="on")
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
