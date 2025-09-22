import asyncio
import os
from typing import *
from maica.maica_utils import *

async def create_tables():
    """We suppose MAICA has done basic necessities for us."""

    basic_pool = load_env('DB_ADDR') != "sqlite"
    maica_pool = await ConnUtils.maica_pool()


    maica_tables = [
    ] if basic_pool else [
    ]

    # Notice: These triggers act as 'on update CURRENT_TIMESTAMP', since
    # there is no convenient way for this in SQLite.

    for table in maica_tables:
        print("[mtts-dbs-init] Adding table to MAICA_DB...")
        await maica_pool.query_modify(table)

if __name__ == "__main__":
    asyncio.run(create_tables())