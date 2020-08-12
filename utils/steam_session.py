import asyncio
import aiohttp
import os
import json
import uuid

from utils.login_executor import LoginExecutor

from abc import ABC, abstractmethod


class ABCSteamSession(ABC):

    @abstractmethod
    def get_account_preferences(self):
        pass

    @abstractmethod
    async def is_alive(self) -> bool:
        pass

    @abstractmethod
    async def get(self, url, timeout=5) -> aiohttp.ClientResponse:
        pass


class ThresholdReached(Exception):
    pass


class SteamSession(ABCSteamSession):
    def __init__(self, credentials_json_path: str):
        """
        format of credentials:
            {"username": nickname, "password": password, "path_to_cookies": path_to_cookies or ''}
        """
        self.credentials_json_path = credentials_json_path
        self.credentials = json.load(open(credentials_json_path, "r"))
        self.username = self.credentials['username']
        self.password = self.credentials['password']
        self.cookies_path = self.credentials.get('path_to_cookies', None)
        self.requests_counter = 0
        self.requests_threshold = 99000
        self.session = None
        self.cookies = None

    async def init_session(self):
        self.session = aiohttp.ClientSession()
        if os.path.exists(self.cookies_path):
            print("Cookies found.")
            self.session._cookie_jar.load(self.cookies_path)
        if await self.is_alive():
            print('Session is alive. Login is not required')
        else:
            print('Cookies are invalid. Please, login.')
            self.session = await LoginExecutor(self.username, self.password, self.session).login()
            self.save_cookies()

    def save_cookies(self):
        if not os.path.exists(self.cookies_path):
            self.cookies_path = f"{str(uuid.uuid4())}.cookie"
        self.session._cookie_jar.save(self.cookies_path)
        self.credentials['path_to_cookies'] = self.cookies_path
        json.dump(self.credentials, open(self.credentials_json_path, 'w'))
        print(f'Cookie for user {self.username} saved in {self.cookies_path}')

    async def get(self, url, timeout=5):
        if not self.session:
            await self.init_session()
        if self.requests_counter < self.requests_threshold:
            self.requests_counter += 1
            response = await self.session.get(url, timeout=timeout)
            return response
        else:
            raise ThresholdReached(f'Requests threshold({self.requests_threshold}) reached.')

    def get_account_preferences(self):
        # TODO dump to credentials or make it auto-filled
        return {
            "country": "RU",
            "language": "russian",
            "currency": "5",
            "price_suffix": 'pуб.',
            "two_factor": "0",
            "norender": "1",
        }

    async def is_alive(self):
        async with self.session.get('https://steamcommunity.com/my/home/') as resp:
            return self.username in await resp.text()

    async def aio_destructor(self):
        self.save_cookies()
        await self.session.close()
        self.session = None
        await asyncio.sleep(0.250)
