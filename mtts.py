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

from loadenv import load_env

async def wrap_run_in_exc(loop, func, *args, **kwargs):
    if not loop:
        loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None, functools.partial(func, *args, **kwargs))
    return result


app = Quart(import_name=__name__)
app = cors(app)


async def generate_voice(text):

    CHATTTS_URL = load_env('CHATTTS_URL')
    timestamp = f'{time.time():.21f}'

    # main infer params
    body = {
        "text": [text],
        "stream": False,
        "lang": None,
        "skip_refine_text": True,
        "refine_text_only": False,
        "use_decoder": True,
        "audio_seed": 2,
        "text_seed": 42,
        "do_text_normalization": True,
        "do_homophone_replacement": False,
    }

    # refine text params
    params_refine_text = {
        "prompt": "",
        "top_P": 0.7,
        "top_K": 20,
        "temperature": 0.7,
        "repetition_penalty": 1,
        "max_new_token": 384,
        "min_new_token": 0,
        "show_tqdm": True,
        "ensure_non_empty": True,
        "stream_batch": 24,
    }
    body["params_refine_text"] = params_refine_text

    # infer code params
    params_infer_code = {
        "prompt": "[speed_5]",
        "top_P": 0.1,
        "top_K": 20,
        "temperature": 0.3,
        "repetition_penalty": 1.05,
        "max_new_token": 2048,
        "min_new_token": 0,
        "show_tqdm": True,
        "ensure_non_empty": True,
        "stream_batch": True,
        "spk_emb": "蘁淰敕欀摃誌緘義囡胹讵祪萀梂晳癧亇婇嚕儝揇偩贻咆煴淀蠀欐萵貺箚弃胦菍弁夞皥焆喦卢狧乩夏淔莨臃赽奛溕筡誑緶貿捨讖卢瑫嬅哙硚惣蚵刻玏炉跸徱澾登嬖絢烇嫷媓蔢产虜椪眕俟徊吞詸愣備恍珳湉璑訷珽菹訴痙濽圴謗瘾皡憖啤囊偐惏嶩役磅惃碝贬貇行楝薇磉数綊蟊弤夋荄壪攫撧杶岈硯葳赛悫宸岩稼琜串汏僎灡峂蝇筋茹聈柵焵皿綏缊橥爝澺縬樢訣潙许壚朔仑螽穨糼稰礌漖噍脠庭穪栽嚽袿蟢朁睬筸獸蜍荃俜椉狴掠歾泓葁潚蚗刣悬縶執萏淪肬涼覎培煟苇攁蕘瞥覹緌玽忖熒苼偶巴氶壡卝僕聥栘袴瞗匥弯剫堎搒烅芡渢蒺仉濃猿焳觔吼嚾簬伋諿圀晑牣缄澜枡溒甆欌槙螶璭惝賙扣氒嘕質僜乧畭徉蟖裔既流橊卺奪襾耨嬖脡甆槡巢誸倦訐忂匼俵宰凥覡穰捠斋孖瀤謹讗揲害祩歊蠯旸忎継亍憭徿礯蜷絕凵腂凾疼渴痳旑賧槢浃圕畧晖庞捻翺岊澛縃婳哵喳唗趢咊綼倅佹艅丽趔攪懦蟜牢庨蒘薪蜩煐揈羄获话涴婔傊庪蚫曃氻肙瞥响丹粫璯蕷舺捆搞爳瞻僱潜袄恛懝嗀碥嶎椓一奥濇嵊卂燡懼礅護懭爋蚿檠蟔氖謻淫曇乯槙孓僷疶笺慛誏籜扰固嚲幦吲朸罺眅晝噱簭椼嘎坷嬢粆师恢埨伮跭侂庒瞭幕擛裌藩屙径皎蕾猨徲徎俬渰畣瓂嵭璌砟勗睃沭吾嗅端匈椃棒瓁刉觤伎虗貉柨燜緷奦曛綡拷撮箓縳蠺綢臑栳愆蛴聱嫼亞人翢疋貼横査艼妽菪梷薓棆焉彘撙蝳籯嬎谡毮牥狊垦岩刡趄虾葤纵爩媳泟惏撙剗瓕濂届竨跘匊殱幓你侜羯籕匐璾凡樃俋臺虘蝄懇罶悥孆击捪蛖畋屁蠐蟦埙夬俟抗籵惉柌箼瞀庻勨串捅窮氶賰燧捵蕓汐藈噱臷児汱留翷枾昅想慱羆蚅聢珹礦諅坔嚇缤冫窙蟓壡洦啓茖汬嶉賭汯紡屒揁熀蛾数篧哞撌塔妥蓗懘犌富圃胃莧絗喘葔改脧焛摆儭庥挖謪擾緖蓐卼褟萎磗侻恏嫒愗欮樞羻喻厚欫参姿剝堬絊挒暘擋緷貧妖欷牶诬囌揋膝湷觸柗灚烚誵暡讟卒縉乍跊疥褧皏菈吓穭脓呲挿燐藒澬珹嗧茪芝灲吋崩请瀓蜋棦掙沝刴彸褕缥誐喘胤櫂愄娇肥吥匚佯揔舔瑪燣孲珬谱炆夤梑狕祠痸浾薐萂暟葯俴涊怰蕲眞煍嘷趌褖弹硒囑琋焧截嵨蘈卥呬畸痾厾橓槔赒熰毪稵囨瀺綰穧楳囹籽窷俆坵萵澳瘏穉焬睳洲蓴懬膄揳妦悰尯堇翩葾弉忲昦蟝慎摏衃榶硟兡啥焛堵汼殗搩枌狎斳蒞貼敱叏刳梋莯椥刣吿埓仹熖悲嫿嫤哆怔祸嵢狴斻肎唤樵糪禾瓺摏璂跨卶欢刖薁嬼蚨壳栮余育熪跭讘勖亾擕硬悦痕屺櫞袁椤穟帀㴃",
        "manual_seed": 2,
    }
    body["params_infer_code"] = params_infer_code

    try:
        async with httpx.AsyncClient(proxy=None, timeout=60) as aclient:
            response = await aclient.post(CHATTTS_URL, json=body)
            response.raise_for_status()
        with zipfile.ZipFile(BytesIO(response.content), "r") as zip_ref:
            # save files for each request in a different folder
            dt = datetime.datetime.now()
            tgt = f"{os.path.dirname(__file__)}/temp/{timestamp}/"
            os.makedirs(tgt, 0o755)
            zip_ref.extractall(tgt)

    except requests.exceptions.RequestException as e:
        print(f"Request error in TTS status: {e}")
    
    return timestamp


async def change_voice(timestamp):

    SOCSVC_URL = load_env('SOCSVC_URL')
    trg_file = open(f"{os.path.dirname(__file__)}/temp/{timestamp}/res.wav", "rb")
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
        shutil.rmtree(f"temp/{timestamp}/")

    return BytesIO(content)


async def make_mtts(text, use_cache=True):
    if use_cache:
        chrs = await wrap_run_in_exc(None, hash_256, text.encode())
        try:
            with open(f'{os.path.dirname(__file__)}/result/{chrs}.wav', 'rb') as f:
                voice_bio = BytesIO(f.read())
            print('Cache hit')
        except:
            timestamp = await generate_voice(text)
            voice_bio = await change_voice(timestamp)
            with open(f'{os.path.dirname(__file__)}/result/{chrs}.wav', 'wb+') as f:
                f.write(voice_bio.getbuffer())
    else:
        timestamp = await generate_voice(text)
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
        for cache_file in os.scandir(f'{os.path.dirname(__file__)}/result'):
            if not cache_file.name.startswith('.') and cache_file.is_file():
                if ((time.time() - cache_file.stat().st_atime) / 3600) >= float(keep_time):
                    os.remove(cache_file.path)
                    print(f'Removed file {os.path.split(cache_file.path)[1]}')
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
            print(f'Generating speech: {text_to_gen}')
            result = await make_mtts(text_to_gen, cache_strats)
            return await send_file(result, as_attachment=True, mimetype="audio/wav")
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