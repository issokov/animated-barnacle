import asyncio
import aiohttp
import base64
import time
import rsa
import os
import json
import uuid

from yarl import URL
from http.cookies import SimpleCookie


class InvalidCredentials(Exception):
    pass


class CaptchaRequired(Exception):
    pass


class LoginExecutor:

    def __init__(self, username: str, password: str, session: aiohttp.ClientSession) -> None:
        self.username = username
        self.password = password
        self.one_time_code = ''
        self.session = session

    async def login(self) -> aiohttp.ClientSession:
        login_response = await self._send_login_request()
        await self._check_for_captcha(login_response)
        login_response = await self._enter_steam_guard_if_necessary(login_response)
        await self._assert_valid_credentials(login_response)
        json_response = await login_response.json()
        await self._perform_redirects(json_response)
        self.set_sessionid_cookies()
        return self.session

    async def _send_login_request(self) -> aiohttp.ClientResponse:
        rsa_params = await self._fetch_rsa_params()
        encrypted_password = self._encrypt_password(rsa_params)
        rsa_timestamp = rsa_params['rsa_timestamp']
        request_data = self._prepare_login_request_data(encrypted_password, rsa_timestamp)
        response = await self.session.post('https://store.steampowered.com/login/dologin', data=request_data)
        return response

    def set_sessionid_cookies(self):
        cookies = self.session.cookie_jar.filter_cookies(URL('https://help.steampowered.com'))
        sessionid = cookies.get('sessionid')
        community_cookie = SimpleCookie(f"sessionid={sessionid}; Domain={'steamcommunity.com'}")
        store_cookie = SimpleCookie(f"sessionid={sessionid}; Domain={'store.steampowered.com'}")
        self.session.cookie_jar.update_cookies(community_cookie, URL('steamcommunity.com'))
        self.session.cookie_jar.update_cookies(store_cookie, URL('store.steampowered.com'))

    async def _fetch_rsa_params(self, current_number_of_repetitions: int = 0) -> dict:
        maximal_number_of_repetitions = 5
        response = await self.session.post('https://store.steampowered.com/login/getrsakey/',
                                           data={'username': self.username})
        key_response = await response.json()
        try:
            rsa_mod = int(key_response['publickey_mod'], 16)
            rsa_exp = int(key_response['publickey_exp'], 16)
            rsa_timestamp = key_response['timestamp']
            return {'rsa_key': rsa.PublicKey(rsa_mod, rsa_exp),
                    'rsa_timestamp': rsa_timestamp}
        except KeyError:
            if current_number_of_repetitions < maximal_number_of_repetitions:
                return await self._fetch_rsa_params(current_number_of_repetitions + 1)
            else:
                raise ValueError('Could not obtain rsa-key')

    def _encrypt_password(self, rsa_params: dict) -> str:
        return base64.b64encode(rsa.encrypt(self.password.encode('utf-8'), rsa_params['rsa_key'])).decode('utf-8')

    def _prepare_login_request_data(self, encrypted_password: str, rsa_timestamp: str) -> dict:
        return {
            'password': encrypted_password,
            'username': self.username,
            'twofactorcode': self.one_time_code,
            'emailauth': '',
            'loginfriendlyname': '',
            'captchagid': '-1',
            'captcha_text': '',
            'emailsteamid': '',
            'rsatimestamp': rsa_timestamp,
            'remember_login': 'true',
            'donotcache': str(int(time.time() * 1000))
        }

    @staticmethod
    async def _check_for_captcha(login_response: aiohttp.ClientResponse) -> None:
        json_ = await login_response.json()
        if json_.get('captcha_needed', False):
            raise CaptchaRequired('Captcha required')

    async def _enter_steam_guard_if_necessary(self, login_response: aiohttp.ClientResponse) -> aiohttp.ClientResponse:
        json_ = await login_response.json()
        if json_['requires_twofactor']:
            self.one_time_code = input('Please put there your steam guard one time code: ')
            return await self._send_login_request()
        return login_response

    @staticmethod
    async def _assert_valid_credentials(login_response: aiohttp.ClientResponse) -> None:
        json_ = await login_response.json()
        if not json_['success']:
            raise InvalidCredentials(json_['message'])

    async def _perform_redirects(self, response_dict: dict) -> None:
        parameters = response_dict.get('transfer_parameters')
        if parameters is None:
            raise Exception('Cannot perform redirects after login, no parameters fetched')
        for url in response_dict['transfer_urls']:
            await self.session.post(url, data=parameters)


class SteamSession:
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
        self.session = aiohttp.ClientSession()
        self.cookies = None

    async def try_init_cookies(self):
        if os.path.exists(self.cookies_path):
            print("Cookies found.")
            self.session._cookie_jar.load(self.cookies_path)
        if await self.is_session_alive():
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

    async def get(self, url):
        """
        returns result, error_string
        """
        if self.requests_counter < self.requests_threshold:
            self.requests_counter += 1
            response = await self.session.get(url)
            return response, None if response.status == 200 else None, response.reason
        else:
            return None, 'Requests threshold reached.'

    async def is_session_alive(self):
        async with self.session.get('https://steamcommunity.com/my/home/') as resp:
            return self.username in await resp.text()

    async def aio_destructor(self):
        self.save_cookies()
        await self.session.close()
        await asyncio.sleep(0.250)


async def main():
    ss = SteamSession('/home/issokov/Desktop/credentials.txt')
    await ss.try_init_cookies()
    print(await ss.is_session_alive())
    await ss.aio_destructor()


if __name__ == '__main__':
    asyncio.run(main())
