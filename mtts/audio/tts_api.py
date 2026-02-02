"""
We do not need to consider TTS cache's ownership, that's the main reason why we don't track them with a DB like MVista.
"""
import asyncio
import httpx
import base64
import os
import pydub
import json

from io import BytesIO
from hashlib import md5
from typing import *
from maica.maica_utils import *

class TTSRequest(AsyncCreator):
    """Things what a TTS request has to do, packed up to get roasted."""
    _real_path: str = ''
    _base_path: str = get_inner_path('fs_storage/mtts')

    text = target_lang = ref = ""

    @property
    def default_carriage(self):
        return {
            "text": self.text,                   # str.(required) text to be synthesized
            "text_lang": self.target_lang,              # str.(required) language of the text to be synthesized
            "ref_audio_path": f"mtts/{self.ref}.wav",         # str.(required) reference audio path
            # "aux_ref_audio_paths": [],    # list.(optional) auxiliary reference audio paths for multi-speaker tone fusion
            "prompt_text": G.T.REF_TEXT,            # str.(optional) prompt text for the reference audio
            "prompt_lang": G.T.REF_LANG,            # str.(required) language of the prompt text for the reference audio
            "top_k": 15,                   # int. top k sampling
            "top_p": 1,                   # float. top p sampling
            "temperature": 1,             # float. temperature for sampling
            "text_split_method": "cut2",  # str. text split method, see text_segmentation_method.py for details.
            # "batch_size": 1,              # int. batch size for inference
            # "batch_threshold": 0.75,      # float. threshold for batch splitting.
            # "split_bucket": True,         # bool. whether to split the batch into multiple buckets.
            "speed_factor": 1.0,           # float. control the speed of the synthesized audio.
            # "fragment_interval":0.3,      # float. to control the interval of the audio fragment.
            "seed": 42,                   # int. random seed for reproducibility.
            "parallel_infer": False,       # bool. whether to use parallel inference.
            "repetition_penalty": 1.12,   # float. repetition penalty for T2S model.
            # "sample_steps": 32,           # int. number of sampling steps for VITS model V3.
            # "super_sampling": False,      # bool. whether to use super-sampling for audio when using VITS model V3.
            # "streaming_mode": False,      # bool or int. return audio chunk by chunk.T he available options are: 0,1,2,3 or True/False (0/False: Disabled | 1/True: Best Quality, Slowest response speed (old version streaming_mode) | 2: Medium Quality, Slow response speed | 3: Lower Quality, Faster response speed )
            # "overlap_length": 2,          # int. overlap length of semantic tokens for streaming mode.
            # "min_chunk_length": 16,       # int. The minimum chunk length of semantic tokens for streaming mode. (affects audio chunk size)
        }

    @staticmethod
    def sanitize(params: dict) -> dict:
        unallowed = ('text', 'text_lang', 'ref_audio_path', 'prompt_text', 'prompt_lang', 'streaming_mode')
        return {k: v for k, v in params.items() if not k in unallowed}

    @property
    def file_name(self):
        return os.path.basename(self._real_path)

    def __init__(self, text, emotion='微笑', target_lang: Literal['zh', 'en']='zh', persistence=True, force_gen=False, lossless=False, **kwargs):
        self.url = G.T.TTS_ADDR
        self.text = self.proceed_tts_text(text)
        self.ref = self.emotion_to_ref(emotion)
        self.target_lang = target_lang
        self.persistence = persistence
        self.force_gen = force_gen
        self.lossless = lossless

        self.advanced = self.sanitize(kwargs)
        if self.advanced:
            self.persistence = False
            self.force_gen = True
        
    async def _ainit(self):
        self.identity = await self.calculate_tts_identity()

    @staticmethod
    def proceed_tts_text(text: str):
        """Standardize the text to proceed."""
        text = text.strip()
        text = ReUtils.re_sub_multi_spaces.sub(' ', text)
        text = ReUtils.re_sub_ellipsis.sub('…', text)
        return text

    @staticmethod
    def emotion_to_ref(emotion: str):
        """Simple..."""
        match emotion.strip('[').strip(']').lower():
            # We yet not have a better ref audio

            # case '开心' | 'happy' | '笑' | 'grin' | 'grinning':
            #     ref = 'happy'
            case _:
                ref = 'standard'
        return ref
    
    async def calculate_tts_identity(self):
        text_hash = await wrap_run_in_exc(None, lambda: base64.urlsafe_b64encode(md5(self.text.encode()).digest()).decode("utf-8"))
        identity = f'{self.target_lang}_{self.ref}_{text_hash}'
        self._real_path = os.path.join(self._base_path, f"{identity}.wav")
        return identity

    @Decos.conn_retryer_factory()
    async def _create_tts(self) -> BytesIO:
        """Utilizes the TTS api."""
        if self.advanced:
            sync_messenger(info=f"\nAdvanced params detected:\n{json.dumps(self.advanced, ensure_ascii=False, indent=4)}", type=MsgType.RECV)
            carriage = self.default_carriage | self.advanced
        else:
            carriage = self.default_carriage

        async with httpx.AsyncClient(timeout=int(G.A.OPENAI_TIMEOUT) if G.A.OPENAI_TIMEOUT != '0' else None) as client:
            response = await client.post(self.url, json=carriage)

        if response.status_code < 400:
            wav_content = BytesIO(response.content)
        else:
            raise MaicaResponseError(str(response.json()))
        
        return wav_content
    
    async def get_tts(self):
        """Manages TTS cache. Requires generation if none found."""
        sync_messenger(info=f"TTS handling content: {self.target_lang}, {self.ref}, {self.text}", type=MsgType.PRIM_RECV)
        if os.path.isfile(self._real_path) and not self.force_gen:
            with open(self._real_path, 'rb') as cache_file:
                tts_bio = BytesIO(cache_file.read())
            sync_messenger(info="TTS cache hit", type=MsgType.DEBUG)
        else:
            tts_bio = await self._create_tts()
            if self.persistence:
                with open(self._real_path, 'wb') as cache_file:
                    cache_file.write(tts_bio.getbuffer())
                sync_messenger(info="TTS generated and cached", type=MsgType.DEBUG)
            else:
                sync_messenger(info="TTS generated temporarily", type=MsgType.DEBUG)

        tts_bio.seek(0)

        if not self.lossless:
            tts_bio_wav = tts_bio
            tts_bio = BytesIO()
            sound = pydub.AudioSegment.from_wav(tts_bio_wav)
            sound.export(tts_bio, format="mp3")

        return tts_bio

if __name__ == "__main__":
    import time
    from maica import init
    init()
    async def main():
        ttsr = await TTSRequest.async_create("你好啊! 今天过得怎么样…开心吗?")
        bio = await ttsr._create_tts()
        with open('test.wav', 'wb') as test_file:
            test_file.write(bio.getbuffer())
    time_start = time.time()
    asyncio.run(main())
    print(f"Time consumation: {time.time() - time_start}")