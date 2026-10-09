import asyncio
import logging
from typing import ClassVar

from hypercorn.asyncio import serve
from hypercorn.config import Config
from maica import maica_http
from maica.maica_utils import *
from maica.mtools import NvWatcher
from quart import Quart, request, send_file

from mtts.audio.tts_api_v2 import TTSRequestV2

_CONNS_LIST = ['mtts_conn']
_WATCHES_LIST = ["tts"]


# ====================================================== Initiation and registration ======================================================


def pkg_init_mtts_http():
    if int(G.A.FULL_RESTFUL):
        app.add_url_rule("/generate", methods=['GET'], view_func=ShortConnHandler.as_view("generate_tts"))
        app.add_url_rule("/register", methods=['GET', 'POST'], view_func=ShortConnHandler.as_view("download_token", val=False))
        app.add_url_rule("/legality", methods=['GET'], view_func=ShortConnHandler.as_view("check_legality"))
        app.add_url_rule("/servers", methods=['GET'], view_func=ShortConnHandler.as_view("get_servers", val=False))
        app.add_url_rule("/accessibility", methods=['GET'], view_func=ShortConnHandler.as_view("get_accessibility", val=False))
        app.add_url_rule("/version", methods=['GET'], view_func=ShortConnHandler.as_view("get_version", val=False))
        app.add_url_rule("/workload", methods=['GET'], view_func=ShortConnHandler.as_view("get_workload", val=False))
        app.add_url_rule("/defaults", methods=['GET'], view_func=ShortConnHandler.as_view("get_defaults", val=False))
    else:
        app.add_url_rule("/generate", methods=['GET'], view_func=ShortConnHandler.as_view("generate_tts"))
        app.add_url_rule("/register", methods=['GET', 'POST'], view_func=ShortConnHandler.as_view("download_token", val=False))
        app.add_url_rule("/legality", methods=['GET'], view_func=ShortConnHandler.as_view("check_legality"))
        app.add_url_rule("/servers", methods=['GET'], view_func=ShortConnHandler.as_view("get_servers", val=False))
        app.add_url_rule("/accessibility", methods=['GET'], view_func=ShortConnHandler.as_view("get_accessibility", val=False))
        app.add_url_rule("/version", methods=['GET'], view_func=ShortConnHandler.as_view("get_version", val=False))
        app.add_url_rule("/workload", methods=['GET'], view_func=ShortConnHandler.as_view("get_workload", val=False))
        app.add_url_rule("/defaults", methods=['GET'], view_func=ShortConnHandler.as_view("get_defaults", val=False))
    app.add_url_rule("/<path>", methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'], view_func=ShortConnHandler.as_view("any_unknown", val=False))

app = Quart(import_name=__name__)
app.config['JSON_AS_ASCII'] = False
app.config['MAX_CONTENT_LENGTH'] = 1 * 1024 * 1024

quart_logger = logging.getLogger('hypercorn.error')
quart_logger.disabled = True

class ShortConnHandler(maica_http.ShortConnHandler):
    """Flask initiates it on every request."""

    nvwatchers: ClassVar[list[NvWatcher]] = []
    """This is class managed."""

    _gt_m = maica_http.pyd_http_factory(
        model_postfix="gt_m",
        access_token=(str, ...),
        content=(dict, ...),
        __validators__={
            "get_json": maica_http._get_json,
        },
    )
    async def generate_tts(self):
        """GET"""
        query = await self.wrapped_validate(self._gt_m, request.args.to_dict(flat=True))

        # We use fsc here since it was inherited from maica, and used in verification
        # Actual tts options are in content

        tts_request = await TTSRequestV2.async_create(self.fsc, query.content)

        resp_bio = await tts_request.tts()
        file_name = tts_request.file_name

        return await send_file(
            resp_bio,
            as_attachment=True,
            attachment_filename=file_name,
        )

    async def get_version(self):
        """GET, val=False"""
        curr_version, legc_version = G.T.CURR_VERSION, G.T.LEGC_VERSION
        synbrace_capv = G.T.SYNBRACE_CAPV
        return maica_http.jfy_res({"curr_version": curr_version, "legc_version": legc_version, "fe_synbrace_version": synbrace_capv})
    
    async def get_defaults(self):
        """GET, val=False"""
        default_std = TTSRequestV2.StdContent().model_dump()
        default_super = TTSRequestV2.Super().model_dump()
        defaults = default_std | default_super
        
        return maica_http.jfy_res(defaults)

async def prepare_thread(shutdown_trigger=None, **kwargs):

    # Construct csc first
    root_csc_kwargs = {k: kwargs.get(k) for k in _CONNS_LIST}
    root_csc = ConnSocketsContainer(**root_csc_kwargs)
    ShortConnHandler.root_csc = root_csc
            
    # Start watchers
    _watch_start_list = []
    for i in _WATCHES_LIST:
        watcher = await NvWatcher.async_create(i, 'mtts')
        ShortConnHandler.nvwatchers.append(watcher)

        _watch_start_list.append(asyncio.create_task(watcher.wrapped_main_watcher()))

    try:
        config = Config()
        config.bind = [f'{G.T.HTTP_HOST}:{int(G.T.HTTP_PORT)}']
        # Supplying the application-level trigger keeps Hypercorn from
        # replacing the process-wide SIGTERM handler installed by the starter.
        task = asyncio.create_task(
            serve(app, config, shutdown_trigger=shutdown_trigger)
        )

        task_list = [task] + _watch_start_list

        sync_messenger(info='MTTS HTTP server started!', type=MsgType.PRIM_SYS)

        done, pending = await asyncio.wait(task_list, return_when=asyncio.FIRST_COMPLETED)
        for completed in done:
            completed.result()

    except asyncio.CancelledError:
        raise
    except Exception as e:
        sync_messenger(info="Uncaught error happened in mtts: ", code=504, error=e)
        raise

    finally:
        for running_task in [*locals().get('task_list', []), *_watch_start_list]:
            if not running_task.done():
                running_task.cancel()
        await asyncio.gather(
            *locals().get('task_list', []),
            *_watch_start_list,
            return_exceptions=True,
        )
        await asyncio.gather(
            *(watcher.close() for watcher in ShortConnHandler.nvwatchers),
            return_exceptions=True,
        )

        sync_messenger(info='MTTS HTTP server stopped!', type=MsgType.PRIM_SYS)


# ====================================================== Debuggings ======================================================


def run_http(**kwargs):

    asyncio.run(prepare_thread(**kwargs))

if __name__ == '__main__':

    run_http()
