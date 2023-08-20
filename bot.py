import asyncio
import json

from errors.exceptions import EmptyFile, WrongProxyFormat

from urllib.parse import urlparse

from random import choice, randint

from pyrogram import Client
from pyrogram.types import Message, User
from pyrogram.errors import FloodWait, UserChannelsTooMuch

from typing import Union, List
from re import match

from sys import stderr, exit
from os import listdir, stat
from os.path import exists

import aiohttp

from loguru import logger

logger.remove()
logger.add(stderr,
        format="<white>{time:HH:mm:ss}</white> | <level>"
                "{level: <8}</level> | <cyan>"
                "{line}</cyan> - <white>{message}</white>")

bot_token=input("bot token: ")
chat_id=input("ваш telegram id: ")

# sessions = set()

class TelegramSession:
    WORKDIR = "sessions"

    def __init__(self, session_filename, proxy: str = "") -> None:
        self.session_filename: str = session_filename

        self.me: User
        self.client: Client
        self.proxy: Union[None, dict] = self.get_proxy_dict(proxy)

        # asyncio.create_task()

        self.name = ""
        

    async def start(self):
        self.client = Client(name=self.session_filename, workdir=self.WORKDIR, device_model="PC 64bit", proxy=self.proxy) #type: ignore

        async with self.client as app:
            self.me = await app.get_me()

        self.name = f"{self.session_filename}[{self.me.username or self.me.first_name}] | "
    
        # sessions.add(self)
    
    @staticmethod
    async def send_markdown_message(text):
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

        payload = {
            "chat_id": chat_id, 
            "text": text,
            "parse_mode": "Markdown"
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                result = await response.json()
                return result

    async def success(self, message: str):
        logger.success(f"{self.name}{message}")
        
        log = f"success: `{message}`\n\
                ```------------------```\n\
                session: `{self.session_filename}` \n\
                username: @{self.me.username}\n\
                "

        await self.send_markdown_message(text=log)
    
    async def error(self, message: str):
        logger.error(f"{self.name}{message}")
        
        log = f"error: `{message}`\n\
                ```------------------```\n\
                session: `{self.session_filename}` \n\
                username: @{self.me.username}\n\
                "

        await self.send_markdown_message(text=log)
    
    async def info(self, message: str):
        logger.info(f"{self.name}{message}")
        
        log = f"info: `{message}`\n\
                ```------------------```\n\
                session: `{self.session_filename}` \n\
                username: @{self.me.username}\n\
                "

        await self.send_markdown_message(text=log)


    @staticmethod
    def get_proxy_dict(proxy_string: str) -> dict | None:
        if proxy_string is None:
            return None

        if not match(r'^[a-zA-Z]+://[a-zA-Z0-9.-]+:[a-zA-Z0-9.-]+@[a-zA-Z0-9._-]+:[0-9]{1,5}$', proxy_string) \
                and not match(r'^[a-zA-Z]+://[a-zA-Z0-9.-]+:[a-zA-Z0-9.-]$', proxy_string):
            raise WrongProxyFormat(f'The string {proxy_string} does not match the proxy format')

        proxy_type = proxy_string.split(':')[0]
        proxy_host, proxy_port = proxy_string.split('://')[-1].split('@')[0].split(':')
        proxy_username = None
        proxy_password = None

        if '@' in proxy_string:
            proxy_username, proxy_password = proxy_string.split('://')[-1].split('@')[-1].split(':')

        proxy_dict = {
            "scheme": proxy_type,
            "hostname": proxy_host,
            "port": proxy_port,
            "username": proxy_username,
            "password": proxy_password
        }

        return proxy_dict
    
    @staticmethod
    def parse_data_from_file(filename) -> List[str]:
        with open(filename, "r", encoding="utf-8") as f:
            data = f.read().splitlines()

        if not data:
            raise EmptyFile
        
        parsed_url = urlparse(data[0])
        path = parsed_url.path.split('/')

        if len(path) == 4:
            result = [] 
            for link in data:
                path = urlparse(link).path.split('/')
                result.append(f'-100{path[2]}:{path[3]}')
            return result
        
        if len(path) == 1:
            result = []
            for id in data:
                result.append(f'{id}:{-1}')
            return result

        return data

    async def join_chat(self, join_link):
        async with self.client as app:
            while True:
                try:
                    joined_chat = await app.join_chat(chat_id=join_link)

                except FloodWait as error:
                    await self.info(f'FloodWait: {error.value} сек.')
                    await asyncio.sleep(error.value) #type: ignore
 
                except UserChannelsTooMuch:
                    await self.info(f'Количество чатов превышено. Пытаюсь выйти из рандомного чата')
                    chats = []
                    async for dialog in app.get_dialogs():  #type: ignore
                        if dialog.chat.id < 0:
                            chats.append(dialog.chat.id)

                    chat = choice(chats)
                    await app.leave_chat(chat_id=chat)
                    await self.success(f'Успешно вышел из чата/канала {chat}')
                else:
                    await self.success(f'Вступил в чат {joined_chat.title}[{join_link}]')
                    break

    async def leave_chat(self):
        raise NotImplementedError

    async def _search_post_with_button(self, chat_id: str | int, app: Client) -> int:
        async for message in app.get_chat_history(chat_id=chat_id,
                                                            limit=100,
                                                            offset_id=-1): # type: ignore
            if message.reply_markup.inline_keyboard:
                return message.id
            
            return 1
    
    async def click_button(self, chat_id: str | int, message_id: int, button_id=0):
        async with self.client as app:
            if message_id == -1:
                message_id = await self._search_post_with_button(chat_id, app)
            
            message = await app.get_messages(chat_id, message_id)

            if not isinstance(message, Message):
                return await self.error(f"Не удалось получить сообщение с кнопкой")

            while True:
                res = None
                try:
                    res = await message.click(button_id)

                except FloodWait as error:
                    await asyncio.sleep(error.value) #type: ignore

                except TimeoutError:
                    await self.info(f'TimeOut при нажатии кнопки (возможно она была успешно нажата)')
                    break

                except ValueError:
                    break

                else:
                    await self.success(f'Кнопка успешно нажата({button_id}). Полученный ответ: {res.message if res is not None else ""}') #type: ignore
                    break



async def joiner():
    join_chat_target = input('Перетяните .txt, в котором с новой строки указаны '
                                     'username\'s / join link\'s чатов/каналов: ')



    links = TelegramSession.parse_data_from_file(join_chat_target)

    for sess in session_files:
        ts = TelegramSession(sess, proxy=proxies_json.get(sess) if proxies_json else "")
        await ts.start()
        for link in links:
            await ts.join_chat(link)
        
        await asyncio.sleep(randint(min_delay, max_delay))


async def clicker():
    click_chat_target = input('Перетяните .txt, в котором с новой строки указаны '
                                    'ссылки на посты или айди каналов: ')

    links = TelegramSession.parse_data_from_file(click_chat_target)

    for sess in session_files:
        ts = TelegramSession(sess, proxy=proxies_json.get(sess) if proxies_json else "")
        await ts.start()
        for link in links:
            chat_id, message_id = link.split(':')
            await ts.click_button(chat_id, int(message_id))
        
        await asyncio.sleep(randint(min_delay, max_delay))

    

if __name__ == "__main__":
    proxies_json = None
    proxies_list = None

    session_files = [current_file[:-8] for current_file in listdir('sessions')
                     if current_file[-8:] == '.session']

    session_files.remove("example")

    if exists('proxies.json') and stat('proxies.json').st_size > 0:
        with open('proxies.json', 'r', encoding='utf-8-sig') as file:
            try:
                proxies_json = json.load(file)

            except json.JSONDecodeError:
                logger.error('Ошибка при чтении proxies.json файла')
                input('Press Any Key To Exit..')
                exit()

    if not proxies_json:
        logger.info('Не удалось обнаружить ни 1 прокси в `proxies.json`, ищу в `proxies.txt`')

        if exists('proxies.txt') and stat('proxies.txt').st_size > 0:
            with open('proxies.txt', 'r', encoding='utf-8-sig') as file:
                proxies_list = [row.strip() for row in file]

        else:
            logger.info('Не удалось обнаружить ни 1 прокси в `proxies.txt`, работаю без прокси')

    user_action = int(input('\n1. Telegram Mass Joiner\n'
                            '2. Telegram Mass Click Inline Buttons\n'
                            'Выберите ваше действие: '))
    

    delay_range = input("Задержка между аккаунтами(в секундах) в формате: min max(например: 10 120)\n")
    min_delay, max_delay = delay_range.split(' ')

    min_delay = int(min_delay)
    max_delay = int(max_delay)

    match user_action:
        case 1:
            
            asyncio.run(joiner())


        case 2:
            asyncio.run(clicker())

        case _:
            logger.error('Такой функции не обнаружено')
            input('Press Any Key To Exit..')
            exit()