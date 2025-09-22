from quart import Quart, request, jsonify, Response
from quart.views import View
import os
import asyncio
import json
import traceback
import time
import colorama
import logging

from hypercorn.config import Config
from hypercorn.asyncio import serve
from typing import *

from maica import maica_http
from maica.maica_ws import NoWsCoroutine, _onliners
from maica.maica_utils import *
from maica.mtools import NvWatcher

def pkg_init_mtts_http():
    global TTS_ADDR, FULL_RESTFUL, known_servers
    TTS_ADDR = load_env('MTTS_TTS_ADDR')
    FULL_RESTFUL = load_env('MTTS_FULL_RESTFUL')
    if FULL_RESTFUL == '1':
        ...
    else:
        ...
    app.add_url_rule("/<path>", methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'], view_func=ShortConnHandler.as_view("any_unknown", val=False))

    try:
        known_servers = json.loads(load_env('MTTS_SERVERS_LIST'))
    except Exception as e:
        sync_messenger(info=f'Loading servers list failed: {str(e)}', type=MsgType.ERROR)
        known_servers = False

app = Quart(import_name=__name__)
app.config['JSON_AS_ASCII'] = False

# quart_logger = logging.getLogger('hypercorn.error')
# quart_logger.disabled = True

workload_cache = {}

class ShortConnHandler(View):
    """Flask initiates it on every request."""

    auth_pool: DbPoolCoroutine = None
    """Don't forget to implement at first!"""
    maica_pool: DbPoolCoroutine = None
    """Don't forget to implement at first!"""
    mtts_watcher: NvWatcher = None

    def __init__(self, val=True):
        if val:
            self.val = True
        else:
            self.val = False

    async def dispatch_request(self, **kwargs):
        try:
            if self.val:
                self.stem_inst = await NoWsCoroutine.async_create(self.auth_pool, self.maica_pool, None)
                self.settings = self.stem_inst.settings
            else:
                self.stem_inst = None
                self.settings = None
            endpoint = request.endpoint
            function_routed = getattr(self, endpoint)
            if function_routed:
                await messenger(info=f'Recieved request on API endpoint {endpoint}', type=MsgType.RECV)
                result = await function_routed()

                if isinstance(result, Response):
                    result_json = await result.get_json()
                    d = {"success": result_json.get('success'), "exception": result_json.get('exception'), "content": ellipsis_str(result_json.get('content'))}
                    await messenger(info=f'Return value: {str(d)}', type=MsgType.SYS)

                return result

        except CommonMaicaException as ce:
            if ce.is_critical:
                traceback.print_exc()
            await messenger(error=ce, no_raise=True)
            return jsonify({"success": False, "exception": str(ce)})

        except Exception as e:
            await messenger(info=f'Handler hit an exception: {str(e)}', type=MsgType.WARN)
            return jsonify({"success": False, "exception": str(e)})

    async def _validate_http(self, raw_data: Union[str, dict], must: list=[]) -> dict:
        data_json = await validate_input(raw_data, 100000, None, must=must)
        if self.val and 'access_token' in must:
            access_token = data_json.get('access_token')
            assert access_token, "access_token not provided"
            login_result = await self.stem_inst.hash_and_login(access_token)
            assert login_result, "Login failed somehow"

        if 'chat_session' in must:
            data_json['chat_session'] = int(data_json['chat_session'])
            assert 0 <= data_json.get('chat_session') < 10, "chat_session out of bound"

        return data_json
    
    check_legality = maica_http.ShortConnHandler.check_legality
    
    get_servers = maica_http.ShortConnHandler.get_servers
    
    async def get_accessibility(self):
        """GET, val=False"""
        accessibility = load_env('MTTS_DEV_STATUS')
        return jsonify({"success": True, "exception": None, "content": accessibility})
    
    async def get_version(self):
        """GET, val=False"""
        curr_version, legc_version = load_env('MTTS_CURR_VERSION'), load_env('MTTS_VERSION_CONTROL')
        return jsonify({"success": True, "exception": None, "content": {"curr_version": curr_version, "legc_version": legc_version}})

    async def get_workload(self):
        """GET, val=False"""
        content = self.mtts_watcher.get_statics_inside()

        return jsonify({"success": True, "exception": None, "content": content})
    
    any_unknown = maica_http.ShortConnHandler.any_unknown

async def prepare_thread(**kwargs):
    auth_created = False; maica_created = False

    if kwargs.get('auth_pool'):
        ShortConnHandler.auth_pool = kwargs.get('auth_pool')
    else:
        ShortConnHandler.auth_pool = await ConnUtils.auth_pool()
        auth_created = True
    if kwargs.get('maica_pool'):
        ShortConnHandler.maica_pool = kwargs.get('maica_pool')
    else:
        ShortConnHandler.maica_pool = await ConnUtils.maica_pool()
        maica_created = True

    ShortConnHandler.mtts_watcher = await NvWatcher.async_create('tts', 'mtts')
    mtts_task = asyncio.create_task(ShortConnHandler.mtts_watcher.wrapped_main_watcher())

    config = Config()
    config.bind = ['0.0.0.0:6000']

    main_task = asyncio.create_task(serve(app, config))
    task_list = [main_task, mtts_task]

    await messenger(info='MTTS HTTP server started!', type=MsgType.PRIM_SYS)

    try:
        await asyncio.wait(task_list, return_when=asyncio.FIRST_COMPLETED)

    except BaseException as be:
        if isinstance(be, Exception):
            error = CommonMaicaError(str(be), '504')
            await messenger(error=error, no_raise=True)
    finally:
        close_list = []
        if auth_created:
            close_list.append(ShortConnHandler.auth_pool.close())
        if maica_created:
            close_list.append(ShortConnHandler.maica_pool.close())

        await asyncio.gather(*close_list, return_exceptions=True)

        # Normally maica_http should be the first one (possibly only one) to
        # respond to the original SIGINT.

        # So its stop msg will be print first, adding \n after ^C to look prettier.

        await messenger(info='\n', type=MsgType.PLAIN)
        await messenger(info='MTTS HTTP server stopped!', type=MsgType.PRIM_SYS)

def run_http(**kwargs):

    asyncio.run(prepare_thread(**kwargs))

if __name__ == '__main__':

    run_http()