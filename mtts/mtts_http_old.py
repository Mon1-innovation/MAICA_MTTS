from quart import Quart, request, send_file
from hypercorn.config import Config
from hypercorn.asyncio import serve
import functools
import asyncio
import datetime
import os
from io import BytesIO
import requests
import httpx
import json
import time
import datetime
import traceback
import hashlib
import schedule
import re
from pydub import AudioSegment
import math

from maica.maica_utils import *

































async def process_audio_from_bytes(input_bytesio, volume_ratio=1.0):
    """
    从BytesIO处理音频并返回处理后的BytesIO对象
    参数:
        input_bytesio (BytesIO): 包含WAV音频的BytesIO对象
        volume_ratio (float): 音量放大倍率
    返回:
        BytesIO: 包含转换后OGG音频的BytesIO对象（失败返回None）
    """
    try:
        # 重置指针位置以便读取
        input_bytesio.seek(0)
        
        # 从BytesIO读取WAV音频
        audio = AudioSegment.from_file(
            input_bytesio,
            format="wav"
        )
        
        # 计算增益并调整音量
        gain_db = 20 * math.log10(volume_ratio)
        louder_audio = audio + gain_db
        
        # 准备输出缓冲
        output_buffer = BytesIO()
        
        # 导出到内存中的BytesIO
        louder_audio.export(
            output_buffer,
            format="ogg",
            codec="libvorbis",
            parameters=["-strict", "-2"]
        )
        
        # 重置指针位置以便后续读取
        output_buffer.seek(0)
        return output_buffer
        
    except Exception as e:
        print(f"处理失败: {str(e)}")
        return None


async def wrap_run_in_exc(loop, func, *args, **kwargs):
    if not loop:
        loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None, functools.partial(func, *args, **kwargs))
    return result


app = Quart(import_name=__name__)

async def mtts_v2(text, style, target_lang):
    """
    http://127.0.0.1:9880/tts?text=%E5%85%88%E5%B8%9D%E5%88%9B%E4%B8%9A%E6%9C%AA%E5%8D%8A%E8%80%8C%E4%B8%AD%E9%81%93%E5%B4%A9%E6%AE%82%EF%BC%8C%E4%BB%8A%E5%A4%A9%E4%B8%8B%E4%B8%89%E5%88%86%EF%BC%8C%E7%9B%8A%E5%B7%9E%E7%96%B2%E5%BC%8A%EF%BC%8C%E6%AD%A4%E8%AF%9A%E5%8D%B1%E6%80%A5%E5%AD%98%E4%BA%A1%E4%B9%8B%E7%A7%8B%E4%B9%9F%E3%80%82&text_lang=zh&ref_audio_path=ref/ref.wav&prompt_lang=en&prompt_text=Now,%20I%20actually%20do%20have%20the%20perspective%20of%20the%20other%20Monika,%20too.%20And%20you%20know,%20honestly,%20the%20side%20of%20me%20that%20let%20those%20insults%20get%20to%20me%20is%20kind%20of%20frustrated.&text_split_method=cut5&batch_size=1&media_type=wav&streaming_mode=true
    """
    SOVITS_URL = load_env("SOVITS_URL")
    body = {
        "text": text,                  
        "text_lang": target_lang,             
        "ref_audio_path": "ref/ref.wav",        
        "aux_ref_audio_paths": [],   
        "prompt_text": "Now, I actually do have the perspective of the other Monika, too. And you know, honestly, the side of me that let those insults get to me is kind of frustrated.",           
        "prompt_lang": "en",           
        "top_k": 20,                  
        "top_p": 0.7,                  
        "temperature": 1,            
        "text_split_method": "cut5", 
        "batch_size": 1,             
        "batch_threshold": 0.75,     
        "split_bucket": True,        
        "speed_factor": 1.0,          
        "streaming_mode": False,     
        "seed": 42,                  
        "parallel_infer": True,      
        "repetition_penalty": 1.35,  
        "sample_steps": 8,          
        "super_sampling": False,     
    }
    try:
        async with httpx.AsyncClient(proxy=None, timeout=60) as aclient:
            response = await aclient.get(SOVITS_URL, params=body)
            response.raise_for_status()
        content = response.content
    except requests.exceptions.RequestException as e:
        print(f"Request error in SOVITS status: {e}")
    return BytesIO(content)


async def make_mtts(text, style, target_lang, use_cache=True):
    if use_cache:
        # chrs = await wrap_run_in_exc(None, hash_256, (style + '|' + text).encode())
        chrs = await wrap_run_in_exc(None, hash_256, text.encode())
        try:
            with open(f'{os.path.dirname(__file__)}/result/{chrs}.ogg', 'rb') as f:
                voice_bio = BytesIO(f.read())
            print('Cache hit')
        except:
            voice_bio = await mtts_v2(text, style, target_lang)
            voice_bio = await process_audio_from_bytes(voice_bio, 2)
            with open(f'{os.path.dirname(__file__)}/result/{chrs}.ogg', 'wb+') as f:
                f.write(voice_bio.getbuffer())
    else:
        voice_bio = await mtts_v2(text, style, target_lang)
        voice_bio = await process_audio_from_bytes(voice_bio, 2)
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
            if False:
                pattern_numeric = re.compile(r'[0-9]')
                pattern_content = re.compile(r'[一-龥A-Za-z]')
                pattern_punc_equal_fbreak = re.compile(r"[~!?~！…？]+")
                pattern_punc_equal_hbreak = re.compile(r"[:\"{}\/;'\\[\]·（）—{}《》：“”【】、；‘']+")
                pattern_punc_equal_none = re.compile(r"[`@#$%^&*()_\-+=<>|@#￥%&*\-+=|]+")

                text_to_gen = re.sub(r'\[.。]{2,}', '.', text_to_gen)
                text_to_gen = re.sub(r'\s+', ' ', text_to_gen)
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
            result = await make_mtts(text_to_gen, style_to_att, target_lang, cache_strats)
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