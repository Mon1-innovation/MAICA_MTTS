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
    global TTS_ADDR, FULL_RESTFUL
    TTS_ADDR = load_env('MTTS_TTS_ADDR')
    FULL_RESTFUL = load_env('MAICA_FULL_RESTFUL')
    if FULL_RESTFUL == '1':
        app.add_url_rule("/legality", methods=['GET'], view_func=ShortConnHandler.as_view("check_legality"))
        app.add_url_rule("/servers", methods=['GET'], view_func=ShortConnHandler.as_view("get_servers", val=False))
        app.add_url_rule("/accessibility", methods=['GET'], view_func=ShortConnHandler.as_view("get_accessibility", val=False))
        app.add_url_rule("/version", methods=['GET'], view_func=ShortConnHandler.as_view("get_version", val=False))
        app.add_url_rule("/workload", methods=['GET'], view_func=ShortConnHandler.as_view("get_workload", val=False))
    else:
        app.add_url_rule("/legality", methods=['GET'], view_func=ShortConnHandler.as_view("check_legality"))
        app.add_url_rule("/servers", methods=['GET'], view_func=ShortConnHandler.as_view("get_servers", val=False))
        app.add_url_rule("/accessibility", methods=['GET'], view_func=ShortConnHandler.as_view("get_accessibility", val=False))
        app.add_url_rule("/version", methods=['GET'], view_func=ShortConnHandler.as_view("get_version", val=False))
        app.add_url_rule("/workload", methods=['GET'], view_func=ShortConnHandler.as_view("get_workload", val=False))
    app.add_url_rule("/<path>", methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'], view_func=ShortConnHandler.as_view("any_unknown", val=False))

app = Quart(import_name=__name__)
app.config['JSON_AS_ASCII'] = False

quart_logger = logging.getLogger('hypercorn.error')
quart_logger.disabled = True

class ShortConnHandler(maica_http.ShortConnHandler):
    """Flask initiates it on every request."""

    auth_pool: DbPoolCoroutine = None
    """Don't forget to implement at first!"""
    maica_pool: DbPoolCoroutine = None
    """Don't forget to implement at first!"""
    mtts_watcher: NvWatcher = None

    async def generate_tts(self):
        """GET"""
        ...
    
    async def get_version(self):
        """GET, val=False"""
        curr_version, legc_version = load_env('MTTS_CURR_VERSION'), load_env('MTTS_VERSION_CONTROL')
        return jsonify({"success": True, "exception": None, "content": {"curr_version": curr_version, "legc_version": legc_version}})

    async def get_workload(self):
        """GET, val=False"""
        content = self.mtts_watcher.get_statics_inside()

        return jsonify({"success": True, "exception": None, "content": content})

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
    config.bind = ['0.0.0.0:7000']

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