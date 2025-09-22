import os
import sys
from pathlib import Path
from dotenv import load_dotenv
try:
    from mtts import mtts_http
except Exception:
    current_dir = Path(__file__).parent
    parent_dir = current_dir.parent
    if str(parent_dir) not in sys.path:
        sys.path.insert(0, str(parent_dir))

import asyncio
import argparse
import colorama

import maica
from maica.maica_utils import *
from mtts.mtts_utils import *



colorama.init(autoreset=True)
initialized = False
_silent = False

def printer(*args, **kwargs):
    global _silent
    if not _silent:
        sync_messenger(*args, **kwargs)

def check_params(envdir: str=None, silent=False):
    """This will only run once. Recalling will not take effect, except passing in extra kwargs."""
    global initialized, _silent
    _silent = silent

    def init_parser():
        parser = argparse.ArgumentParser(description="Start MAICA MTTS backend deployment")
        parser.add_argument('-e', '--envdir', help='Include external env file for running deployment, specify every time')
        parser.add_argument('-t', '--templates', choices=['print', 'create'], nargs='?', const='print', help='Print config templates or create them in current directory')
        return parser
    
    parser = init_parser()
    args = parser.parse_args()
    envdir = envdir or args.envdir
    templates = args.templates

    def dest_env(envdir):
        mtts_envdir = envdir or get_inner_path('.env')
        mtts_template_envdir = get_inner_path('env_example')
        maica.init(envdir=mtts_envdir, extra_envdir=[mtts_template_envdir])

    def get_templates():
        with open(get_inner_path('env_example'), 'r', encoding='utf-8') as env_e:
            env_c = env_e.read()
        return env_c
    
    def separate_line(title: str):
        try:
            terminal_width = os.get_terminal_size().columns
        except:
            terminal_width = 40
        line = title.center(terminal_width, '/')
        return line
    
    def print_templates():
        env_c = get_templates()
        print(colorama.Fore.BLUE + separate_line('Begin .env template'))
        print(env_c)
        print(colorama.Fore.BLUE + separate_line('End .env template'))
        exit(0)

    def create_templates():
        env_c = get_templates()
        env_p = os.path.abspath('./.env')
        if os.path.exists(env_p):
            printer(info=f'Config {env_p} already exists, skipping creation...', type=MsgType.WARN)
        else:
            with open(env_p, 'w', encoding='utf-8') as env_f:
                printer(info=f'Generating {env_p}...', type=MsgType.DEBUG)
                env_f.write(env_c)

        printer(info='Creation succeeded, edit them yourself and then start with "mtts -c .env"', type=MsgType.INFO)
        exit(0)

    if not initialized:
        try:
            if templates:
                print_templates() if templates == 'print' else create_templates()
            dest_env(envdir)

            initialized = True
        except Exception as e:
            import traceback
            traceback.print_exc()
            printer(info=f'Error: {str(e)}, quitting...', type=MsgType.ERROR)
            exit(1)

def check_env_init():
    """We run this only if called to serve. No env is basically not a problem for working as module."""
    if load_env('IS_REAL_ENV') == '1':
        return
    else:
        print('''No real env detected, is this workflow?
If it is, at least the imports and grammar are good if you see this.
If not:
    If you're running MTTS for deployment, pass in "--envdir path/to/.env".
    If you're developing with MTTS as dependency, call mtts.init() after import.
Quitting...'''
              )
        quit(0)

async def start_all():...

def full_start():
    check_params()
    check_env_init()
    asyncio.run(start_all())

if __name__ == "__main__":
    full_start()