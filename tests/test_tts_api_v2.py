import asyncio
import json
from io import BytesIO

import pytest

from maica.maica_utils import FullSocketsContainer, G, MaicaInputWarning
from mtts.audio.tts_api_v2 import TTSRequestV2
from mtts.mtts_http import ShortConnHandler


def test_generate_query_decodes_json_content() -> None:
    query = ShortConnHandler._gt_m.model_validate(
        {
            "access_token": "token",
            "content": json.dumps({"text": "hello", "speed": 1.25}),
        }
    )

    assert query.content == {"text": "hello", "speed": 1.25}


def test_tts_request_validates_content_and_hashes_non_strings(monkeypatch) -> None:
    monkeypatch.setattr(G.T, "CENSOR_QUERY", "0")

    async def scenario() -> None:
        content = {"text": "hello", "speed": 1.25, "lossless": True}
        request = await TTSRequestV2.async_create(
            FullSocketsContainer(),
            content,
        )
        assert request.super.speed == 1.25
        assert request.super.lossless is True
        assert request.uq_hash
        assert content["text"] == "hello"

        with pytest.raises(MaicaInputWarning):
            TTSRequestV2(FullSocketsContainer(), {})

    asyncio.run(scenario())


def test_no_cache_skips_cache_lookup(monkeypatch) -> None:
    monkeypatch.setattr(G.T, "CENSOR_QUERY", "0")

    async def scenario() -> None:
        request = await TTSRequestV2.async_create(
            FullSocketsContainer(),
            {"text": "hello", "no_cache": True},
        )

        async def fail_cache_lookup():
            raise AssertionError("cache lookup should be skipped")

        async def generate():
            return BytesIO(b"audio")

        request._get_cache = fail_cache_lookup
        request._gen_and_store = generate

        result = await request.tts()
        assert result.getvalue() == b"audio"

    asyncio.run(scenario())
