"""
The MTTS v2 inference allows usage of standard openai api (speech), so we adopt it.
"""

import asyncio
import base64
import json
import os
from typing import *
from hashlib import md5
from io import BytesIO
from typing import Any

import aiofiles
import aiofiles.os
from maica.maica_utils import *
from maica.mtools import has_censored
from pydantic import BaseModel, Field, model_validator

_base_path: str = get_inner_path('fs_storage/mtts')

class TTSRequestV2(AsyncCreator):
    """The carrier of a V2 tts request."""
    class EssContent(BaseModel):
        raw_text: str

        @model_validator(mode="before")
        @classmethod
        def text_to_rt(cls, data: Any):
            if isinstance(data, dict):
                data = data.copy()
                if "text" in data:
                    data["raw_text"] = data.pop("text")

            return data

    class StdContent(BaseModel):
        emotion: Optional[str] = None
        persistent: bool = True

    class Super(BaseModel):
        no_cache: bool = False
        lossless: bool = False
        speed: float = Field(
            ge=0.25,
            le=4.0,
            default=1.0,
        )

        @property
        def modified(self):
            return self != type(self).model_validate({})

    @staticmethod
    async def hash_unique(*essentials):
        """Create unique hash according to all given essentials."""
        id_string = "|".join(str(item) for item in essentials)
        uq_hash = await asyncio.to_thread(lambda: base64.urlsafe_b64encode(md5(id_string.encode()).digest()).decode("utf-8"))
        return uq_hash

    @property
    def file_name(self):
        if not getattr(self, "uq_hash", None):
            raise CommonMaicaError("TTS identity used before assignment")
        return self.uq_hash + (".wav" if self.super.lossless else ".mp3")

    @property
    def real_path(self):
        return os.path.join(_base_path, self.file_name)

    def __init__(
            self,
            fsc: FullSocketsContainer,
            # This content is a dict including text, not text itself
            content: dict,
        ):
        try:
            ess_content = self.EssContent.model_validate(content)
            std_content = self.StdContent.model_validate(content)
            super_content = self.Super.model_validate(content)
        except Exception as exc:
            raise MaicaInputWarning(f"Query parsing failed: {exc}") from exc

        self.fsc = fsc

        self.text = self.proceed_tts_text(ess_content.raw_text)
        self.emo_prompt = self.emotion_mapping(std_content.emotion)
        self.persistent = std_content.persistent

        self.super = super_content

    async def _ainit(self):
        # We don't want to actually cache requests with active supers, but we impl it anyway
        essentials = [self.emo_prompt, self.text]
        if self.super.modified:
            super_ess = list(self.super.model_dump().values())
            essentials.extend(super_ess)
        self.uq_hash = await self.hash_unique(*essentials)

        if G.T.CENSOR_QUERY != '0':
            tolerance = int(G.T.CENSOR_QUERY)
            query_censor = await has_censored(self.text)
            if len(query_censor) >= tolerance:
                sync_messenger(info=f"Query has censored words: {query_censor}", type=MsgType.DEBUG)
                raise MaicaInputWarning("Input query has censored words or phrases", "403", "maica_input_query_censored")

            elif len(query_censor):
                sync_messenger(info=f"Input query has censored words or phrases but ignored: {query_censor}", type=MsgType.DEBUG)


    @staticmethod
    def proceed_tts_text(text: str):
        """Standardize the text to proceed."""
        text = text.strip()
        text = ReUtils.re_sub_multi_spaces.sub(' ', text)
        text = ReUtils.re_sub_ellipsis.sub('…', text)

        if not text or text.isspace():
            raise MaicaInputWarning("TTS text is blank")

        return text

    @staticmethod
    def emotion_mapping(emotion: Optional[str]):
        """Map emotion to generation prompt."""

        # This normally does not perform well, so mute for now
        return ""

    async def _generate_speech(self) -> BytesIO:
        conn = self.fsc.mtts_conn
        if not conn:
            raise MaicaInputError("TTS connection is not provided with fsc")

        if self.super.modified:
            sync_messenger(info=f"\nModified tts super params detected:\n{json.dumps(self.super.model_dump(), ensure_ascii=False, indent=4)}", type=MsgType.RECV)

        speech_args = {
            "input": self.text,
            # According to docs, VoxCPM does not utilize the voice param
            "voice": G.T.PREC_CHR or "default",
            "response_format": "wav" if self.super.lossless else "mp3",
            "speed": self.super.speed,

            "extra_body": {
                "ref_audio": G.T.REF_PATH if not G.T.PREC_CHR else None,
                "ref_text": G.T.REF_TEXT if not G.T.PREC_CHR else None,
                "instructions": self.emo_prompt,
            }
        }

        resp = await conn.make_speech(**speech_args)
        return BytesIO(resp.content)

    async def _gen_and_store(self) -> BytesIO:
        resp_bio = await self._generate_speech()

        # Uncomment & comment below to allow caching super-tweaked results
        # if False:
        if self.super.modified:
            sync_messenger(info="TTS result not cached due to modified super params", type=MsgType.DEBUG)

        else:
            if self.persistent:
                async with aiofiles.open(self.real_path, 'wb') as cache_file:
                    await cache_file.write(resp_bio.getbuffer())
                sync_messenger(info="TTS generated and cached", type=MsgType.DEBUG)
            else:
                sync_messenger(info="TTS generated temporarily", type=MsgType.DEBUG)

        return resp_bio

    async def _get_cache(self) -> Optional[BytesIO]:
        resp = None

        file_exists = await aiofiles.os.path.isfile(self.real_path)
        if file_exists:
            async with aiofiles.open(self.real_path, 'rb') as cache_file:
                resp = BytesIO(await cache_file.read())

        return resp


    async def tts(self):
        resp_bio = None if self.super.no_cache else await self._get_cache()

        if not resp_bio:
            resp_bio = await self._gen_and_store()
        return resp_bio
