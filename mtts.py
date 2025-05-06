if __name__ == '__main__':
    from gevent import monkey
    monkey.patch_all()
from quart import Quart, request, send_file
from quart_cors import cors
from hypercorn.config import Config
from hypercorn.asyncio import serve
import functools
import asyncio
import datetime
import os
import zipfile
from io import BytesIO
import shutil
import requests
import httpx
import json
import time
import datetime
import traceback
import hashlib
import schedule
import re

from loadenv import load_env

async def wrap_run_in_exc(loop, func, *args, **kwargs):
    if not loop:
        loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None, functools.partial(func, *args, **kwargs))
    return result


app = Quart(import_name=__name__)
app = cors(app)


async def generate_voice(text, style):

    CHATTTS_URL = load_env('CHATTTS_URL')
    timestamp = f'{time.time():.21f}'

    # Emotion dict
    emotion_trans = {
        "微笑": "chat",
        "担心": "empathetic",
        "笑": "cheerful",
        "思考": "serious",
        "开心": "cheerful",
        "生气": "angry",
        "脸红": "affectionate",
        "凝视": "chat",
        "沉重": "depressed",
        "憧憬": "hopeful",
        "惊喜": "excited",
        "尴尬": "embarrassed",
        "意味深长": "whispering",
        "惊讶": "fearful",
        "轻松": "calm",
        "害羞": "affectionate",
        "急切": "excited",
        "得意": "envious",
        "不满": "unfriendly",
        "严肃": "serious",
        "感动": "affectionate",
        "激动": "excited",
        "宠爱": "affectionate",
        "眨眼": "cheerful",
        "伤心": "sad",
        "厌恶": "unfriendly",
        "害怕": "terrified",
        "可爱": "affectionate"
    }

    # main infer params
    # body = {
    #     "input": text,
    #     "voice": "严肃女领导",
    #     "response_format": "wav",
    #     "style": emotion_trans[style],
    #     "batch_size": 4,
    #     "top_k": 20,
    #     "top_p": 0.6,
    # }

    body = {
        "text": text,
        "spk": "严肃女领导",
        "style": emotion_trans[style],
        "temperature": 0.3,
        "top_k": 20,
        "top_p": 0.6,
        "format": "wav",
        "prefix": "[oral_1][laugh_0][break_6]",
        "bs": 8,
        "no_cache": True
    }

    try:
        async with httpx.AsyncClient(proxy=None, timeout=60) as aclient:
            response = await aclient.get(CHATTTS_URL, params=body)
            response.raise_for_status()

        content = response.content
        with open(f"{os.path.dirname(__file__)}/temp/{timestamp}.wav", "wb+") as res_f:
            res_f.write(content)
        # with zipfile.ZipFile(BytesIO(response.content), "r") as zip_ref:
        #     # save files for each request in a different folder
        #     dt = datetime.datetime.now()
        #     tgt = f"{os.path.dirname(__file__)}/temp/{timestamp}/"
        #     os.makedirs(tgt, 0o755)
        #     zip_ref.extractall(tgt)

    except requests.exceptions.RequestException as e:
        print(f"Request error in TTS status: {e}")
    
    return timestamp


async def change_voice(timestamp):

    SOCSVC_URL = load_env('SOCSVC_URL')
    trg_file = open(f"{os.path.dirname(__file__)}/temp/{timestamp}.wav", "rb")
    data = {}
    files = {"sample": trg_file}

    try:
        async with httpx.AsyncClient(proxy=None, timeout=60) as aclient:
            response = await aclient.post(SOCSVC_URL, data=data, files=files)
            response.raise_for_status()
        content = response.content
        # with open(f"{os.path.dirname(__file__)}/result/{timestamp}.wav", "wb+") as res_f:
        #     res_f.write(content)

    except requests.exceptions.RequestException as e:
        print(f"Request error in SVC status: {e}")

    finally:
        os.remove(f"{os.path.dirname(__file__)}/temp/{timestamp}.wav")
        pass

    return BytesIO(content)


async def make_mtts(text, style, use_cache=True):
    if use_cache:
        chrs = await wrap_run_in_exc(None, hash_256, (style + text).encode())
        try:
            with open(f'{os.path.dirname(__file__)}/result/{chrs}.ogg', 'rb') as f:
                voice_bio = BytesIO(f.read())
            print('Cache hit')
        except:
            timestamp = await generate_voice(text, style)
            voice_bio = await change_voice(timestamp)
            with open(f'{os.path.dirname(__file__)}/result/{chrs}.ogg', 'wb+') as f:
                f.write(voice_bio.getbuffer())
    else:
        timestamp = await generate_voice(text, style)
        voice_bio = await change_voice(timestamp)
    purge_unused_cache()
    return voice_bio


def purge_unused_cache():
    schedule.run_pending()


def hash_256(s):
    return hashlib.new('sha256', s).hexdigest()


def first_run_init():
    for d in [f'{os.path.dirname(__file__)}/temp/', f'{os.path.dirname(__file__)}/result/']:
        os.makedirs(d, 0o755, True)


def every_run_init():
    def purge_cache(keep_time=load_env('KEEP_POLICY')):
        if float(keep_time) >= 0:
            for cache_file in os.scandir(f'{os.path.dirname(__file__)}/result'):
                if not cache_file.name.startswith('.') and cache_file.is_file():
                    if ((time.time() - cache_file.stat().st_atime) / 3600) >= float(keep_time):
                        os.remove(cache_file.path)
                        print(f'Removed file {os.path.split(cache_file.path)[1]}')
    purge_cache()
    schedule.every(1).day.at("04:00").do(purge_cache)


@app.route('/generate', methods=["POST"])
async def generation():
    success = True
    exception = ''
    if load_env('LOGIN_VERIFICATION') != 'disabled':
        vfc_enable = True
        VFC_URL = load_env('VFC_URL')
    else:
        vfc_enable = False
    try:
        data = json.loads(await request.data)
        text_to_gen = data['content']
        try:
            style_to_att = data['emotion']
            if not style_to_att:
                raise Exception('use default')
        except:
            style_to_att = '微笑'
        try:
            target_lang = data['target_lang']
            if not target_lang:
                raise Exception('use default')
            target_lang = 'zh' if target_lang == 'zh' else 'en'
        except:
            target_lang = 'zh'
        try:
            cache_strats = bool(data['cache_policy'])
        except:
            cache_strats = True
        if vfc_enable:
            access_token = data['access_token']
            async with httpx.AsyncClient(proxy=None) as aclient:
                response = await aclient.post(VFC_URL, json={"access_token": access_token})
                response.raise_for_status()
            json_r = response.json()
        else:
            json_r = {"success": True}
        if json_r['success']:
            # main logic here

            # pre-filtering first
            text_to_gen = re.sub(r'\.{2,}', '.', text_to_gen)
            text_to_gen = re.sub(r'\s', '', text_to_gen)
            pattern_numeric = re.compile(r'[0-9]')
            pattern_content = re.compile(r'[一-龥A-Za-z]')

            def is_decimal(five_related_cells):
                nonlocal pattern_content, pattern_numeric
                if five_related_cells[2] in ['.', ',']:
                    nums = len(pattern_numeric.findall(five_related_cells)); cnts = len(pattern_content.findall(five_related_cells))
                    if nums>=2 or cnts<=1:
                        return True
                return False

            if target_lang == 'zh':
                filtering_puncs = re.finditer(r'[,.]', text_to_gen)
                for p in filtering_puncs:
                    pos = p.span()[0]
                    cont = p.group()
                    five_relcs = ('  '+text_to_gen+'  ')[(pos):(pos+5)]
                    if is_decimal(five_relcs):
                        pass
                    else:
                        match cont:
                            case '.':
                                new_cont = '。'
                            case _:
                                new_cont = '，'
                        text_to_gen = text_to_gen[:pos] + new_cont + text_to_gen[(pos+1):]

            print(f'Generating speech--{style_to_att}: {text_to_gen}')
            result = await make_mtts(text_to_gen, style_to_att, cache_strats)
            return await send_file(result, as_attachment=True, mimetype="audio/ogg")
        else:
            raise Exception(json_r['exception'])
    except Exception as excepted:
        traceback.print_exc()
        success = False
        return json.dumps({"success": success, "exception": str(excepted)}, ensure_ascii=False)


@app.route('/strategy', methods=["POST"])
async def strats():
    success = True
    exception = ''
    strategy = load_env('LOAD_STRATS')
    return json.dumps({"success": success, "exception": str(exception), "strategy": strategy}, ensure_ascii=False)


def run_http():
    config = Config()
    config.bind = ['0.0.0.0:7000']
    print('MTTS server started!')
    asyncio.run(serve(app, config))

if __name__ == '__main__':
    first_run_init()
    every_run_init()
    run_http()
    #asyncio.run(generate_voice("I love you"))