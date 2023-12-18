"""
End-to-end API tests for audio.

Can be used to verify a live deployment is functioning as designed.
Run with the `pytest -s` command from this directory.
"""

import pytest


pytestmark = pytest.mark.django_db


def test_audio_detail_without_thumb(client):
    resp = client.get("/v1/audio/44540200-91eb-483d-9e99-38ce86a52fb6/")
    assert resp.status_code == 200
    parsed = resp.json()
    assert parsed["thumbnail"] is None


def test_audio_search_without_thumb(client):
    """The first audio of this search should not have a thumbnail."""
    resp = client.get("/v1/audio/?q=zaus")
    assert resp.status_code == 200
    parsed = resp.json()
    assert parsed["results"][0]["thumbnail"] is None
