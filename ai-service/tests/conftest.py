from __future__ import annotations

import base64
import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from ai_service.entrypoint.composition_root import build_app
from ai_service.infrastructure.config import Settings


@pytest.fixture
def client() -> TestClient:
    return TestClient(build_app(Settings(embedding_provider="local")))


def make_image_b64(color: tuple[int, int, int], size: int = 32) -> str:
    """A solid-color PNG, base64-encoded — deterministic test fixtures where
    'similar color' should mean 'similar vector'."""
    img = Image.new("RGB", (size, size), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()
