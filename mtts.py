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


async def generate_voice(text, style, use_svc, debug=None):

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

    emotion_oral = {
        "微笑": "3",
        "担心": "2",
        "笑": "3",
        "思考": "1",
        "开心": "4",
        "生气": "4",
        "脸红": "4",
        "凝视": "2",
        "沉重": "2",
        "憧憬": "3",
        "惊喜": "4",
        "尴尬": "4",
        "意味深长": "3",
        "惊讶": "3",
        "轻松": "4",
        "害羞": "4",
        "急切": "4",
        "得意": "4",
        "不满": "2",
        "严肃": "1",
        "感动": "3",
        "激动": "4",
        "宠爱": "3",
        "眨眼": "3",
        "伤心": "2",
        "厌恶": "2",
        "害怕": "1",
        "可爱": "3"
    }

    emotion_laugh = {
        "微笑": "0",
        "担心": "0",
        "笑": "1",
        "思考": "0",
        "开心": "1",
        "生气": "0",
        "脸红": "0",
        "凝视": "0",
        "沉重": "0",
        "憧憬": "0",
        "惊喜": "0",
        "尴尬": "0",
        "意味深长": "1",
        "惊讶": "0",
        "轻松": "1",
        "害羞": "0",
        "急切": "0",
        "得意": "1",
        "不满": "0",
        "严肃": "0",
        "感动": "0",
        "激动": "0",
        "宠爱": "0",
        "眨眼": "1",
        "伤心": "0",
        "厌恶": "0",
        "害怕": "0",
        "可爱": "0"
    }

    emotion_break = {
        "微笑": "5",
        "担心": "6",
        "笑": "4",
        "思考": "6",
        "开心": "5",
        "生气": "3",
        "脸红": "5",
        "凝视": "6",
        "沉重": "6",
        "憧憬": "5",
        "惊喜": "4",
        "尴尬": "5",
        "意味深长": "6",
        "惊讶": "5",
        "轻松": "5",
        "害羞": "5",
        "急切": "3",
        "得意": "5",
        "不满": "5",
        "严肃": "5",
        "感动": "5",
        "激动": "4",
        "宠爱": "5",
        "眨眼": "5",
        "伤心": "6",
        "厌恶": "5",
        "害怕": "4",
        "可爱": "5"
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
        "spk": "Bob" if use_svc else "嗲嗲的很酥麻",
        "style": emotion_trans[style],
        "temperature": 0.4 if use_svc else 0.55,
        "top_k": 20,
        "top_p": 0.7,
        "format": "wav",
        "prefix": f"[oral_{emotion_oral[style]}][laugh_{emotion_laugh[style]}][break_{emotion_break[style]}]",
        "bs": 8,
        "no_cache": True
    }

    if debug:
        body.update(debug)

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


async def change_voice(timestamp, use_svc, debug=None):

    SOCSVC_URL = load_env('SOCSVC_URL')
    SKIPSVC_URL = load_env('SKIPSVC_URL')
    trg_file = open(f"{os.path.dirname(__file__)}/temp/{timestamp}.wav", "rb")
    data = {}
    files = {"sample": trg_file}
    url = SOCSVC_URL if use_svc else SKIPSVC_URL
    try:
        async with httpx.AsyncClient(proxy=None, timeout=60) as aclient:
            response = await aclient.post(url, data=data, files=files)
            response.raise_for_status()
        content = response.content
        # with open(f"{os.path.dirname(__file__)}/result/{timestamp}.wav", "wb+") as res_f:
        #     res_f.write(content)

    except requests.exceptions.RequestException as e:
        print(f"Request error in SVC status: {e}")

    finally:
        if not debug:
            os.remove(f"{os.path.dirname(__file__)}/temp/{timestamp}.wav")
        pass

    return BytesIO(content)


async def make_mtts(text, style, use_svc=True, debug=None, use_cache=True):
    if use_cache:
        chrs = await wrap_run_in_exc(None, hash_256, (str(int(use_svc)) + '|' + style + '|' + text).encode())
        try:
            with open(f'{os.path.dirname(__file__)}/result/{chrs}.ogg', 'rb') as f:
                voice_bio = BytesIO(f.read())
            print('Cache hit')
        except:
            timestamp = await generate_voice(text, style, use_svc, debug)
            voice_bio = await change_voice(timestamp, use_svc, debug)
            with open(f'{os.path.dirname(__file__)}/result/{chrs}.ogg', 'wb+') as f:
                f.write(voice_bio.getbuffer())
    else:
        timestamp = await generate_voice(text, style, use_svc, debug)
        voice_bio = await change_voice(timestamp, use_svc, debug)
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
            enable_svc = bool(data['conversion'])
        except:
            enable_svc = True
        try:
            target_lang = data['target_lang']
            if not target_lang:
                raise Exception('use default')
            target_lang = 'zh' if target_lang == 'zh' else 'en'
        except:
            target_lang = 'zh'
        try:
            debug = data['debug']
        except:
            debug = None
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
            text_to_gen = re.sub(r'\[.。]{2,}', '.', text_to_gen)
            text_to_gen = re.sub(r'\s+', ' ', text_to_gen)
            pattern_numeric = re.compile(r'[0-9]')
            pattern_content = re.compile(r'[一-龥A-Za-z]')
            pattern_punc_equal_fbreak = re.compile(r"[~!?~！…？]+")
            pattern_punc_equal_hbreak = re.compile(r"[:\"{}\/;'\\[\]·（）—{}《》：“”【】、；‘']+")
            pattern_punc_equal_none = re.compile(r"[`@#$%^&*()_\-+=<>|@#￥%&*\-+=|]+")
            text_to_gen = pattern_punc_equal_fbreak.sub('.', text_to_gen)
            text_to_gen = pattern_punc_equal_hbreak.sub(',', text_to_gen)
            text_to_gen = pattern_punc_equal_none.sub('', text_to_gen)


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
            else:
                filtering_puncs = re.finditer(r'[，。]', text_to_gen)
                for p in filtering_puncs:
                    pos = p.span()[0]
                    cont = p.group()
                    match cont:
                        case '。':
                            new_cont = '.'
                        case _:
                            new_cont = ','
                    text_to_gen = text_to_gen[:pos] + new_cont + text_to_gen[(pos+1):]


            text_to_gen += '[lbreak]'

            print(f'Generating speech--{style_to_att}: {text_to_gen}')
            result = await make_mtts(text_to_gen, style_to_att, enable_svc, debug, cache_strats)
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