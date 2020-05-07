import argparse
import asyncio
import json
import os
import pathlib
import sys

import aiofiles
import httpx
import tqdm
import yaml

MIRAI_DIR = '/app'
VERSION_FILE = os.path.join(MIRAI_DIR, 'versions.json')
PLUGIN_DIR = os.path.join(MIRAI_DIR, 'plugins')
CONTENT_DIR = os.path.join(MIRAI_DIR, 'content')
CONFIG_DIR = os.path.join(PLUGIN_DIR, 'MiraiAPIHTTP')
CONFIG_FILE = os.path.join(CONFIG_DIR, 'setting.yml')


def strtobool(s):
    return s.lower() in {'1', 'true', 'yes', 'on'}


def makedirs(dir, mode=0o755, exist_ok=True):
    os.makedirs(dir, mode=mode, exist_ok=exist_ok)


def is_first_start():
    return not os.path.exists(CONTENT_DIR)


def getenv(key: str, default=None):
    return os.getenv(('mirai_http_' + key).upper(), default)


async def gen_conf():
    conf = {}
    conf['port'] = getenv('port', 8080)
    conf['authKey'] = getenv('authkey', 'PLEASE_REPLACE_IT')
    if getenv('use_report', True):
        conf['report'] = {}
        conf['report']['enable'] = True
        conf['report']['groupMessage'] = {'report': True}
        conf['report']['friendMessage'] = {'report': True}
        conf['report']['tempMessage'] = {'report': True}
        conf['report']['eventMessage'] = {'report': True}
        conf['report']['destinations'] = [
            getenv('report_url', 'http://172.17.0.1:5000/')
        ]
    makedirs('plugins/MiraiAPIHTTP')
    async with aiofiles.open(CONFIG_FILE, 'w') as f:
        await f.write(yaml.dump(conf))


async def fetch(url, name):
    if pathlib.Path(name).exists():
        tqdm.tqdm.write(f'{name} already exists.')
        return True
    async with httpx.AsyncClient() as client:
        async with client.stream('GET', url, timeout=None) as stream:
            try:
                stream.raise_for_status()
            except:
                code = stream.status_code
                tqdm.tqdm.write(
                    f'Failed to fetch {name}, status code: {code}.',
                    sys.stderr)
                tqdm.tqdm.write('Plz check your version number.', sys.stderr)
                return False
            length = int(stream.headers.get('content-length'))
            bar = tqdm.tqdm(None, name, length, unit='B', unit_scale=True)
            async with aiofiles.open(name, 'wb') as f:
                async for chuck in stream.aiter_bytes():
                    bar.update(len(chuck))
                    if chuck:
                        await f.write(chuck)
    return True


async def fetch_wrapper(version):
    return await fetch(
        'https://github.com/mamoe/mirai-console/releases/download/' \
        f'wrapper-{version}/mirai-console-wrapper-{version}.jar',
        os.path.join(MIRAI_DIR, f'mirai-console-wrapper-{version}.jar'))


async def fetch_console(version):
    return await fetch(
        f'https://raw.githubusercontent.com/mamoe/mirai-repo/master/shadow/mirai-console/mirai-console-{version}.jar',
        os.path.join(CONTENT_DIR, f'mirai-console-{version}.jar'))

async def fetch_core(version):
    return await fetch(
        f'https://raw.githubusercontent.com/mamoe/mirai-repo/master/shadow/mirai-core-qqandroid/mirai-core-qqandroid-{version}.jar',
        os.path.join(CONTENT_DIR, f'mirai-core-qqandroid-jvm-{version}.jar'))


async def fetch_plugin(plugin, version):
    return await fetch(
        f'https://raw.githubusercontent.com/mamoe/mirai-plugins/master/{plugin}/{plugin}-{version}.jar',
        os.path.join(PLUGIN_DIR, f'{plugin}-{version}.jar'))


async def init():
    makedirs(CONTENT_DIR)
    makedirs(PLUGIN_DIR)

    async with aiofiles.open(VERSION_FILE) as f:
        content = await f.read()
        VER = json.loads(content)

    coros = [
        fetch_wrapper(VER['wrapper']),
        fetch_console(VER['console']),
        fetch_core(VER['core-qqandroid']),
        fetch_plugin('mirai-api-http', VER['mirai-api-http'])
    ]
    res = await asyncio.gather(*coros)
    if not all(res):
        sys.exit(1)


if __name__ == '__main__':
    if is_first_start():
        asyncio.run(init())
    asyncio.run(gen_conf())