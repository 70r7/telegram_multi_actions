import asyncio
import json

from errors.exceptions import EmptyFile, WrongProxyFormat

from urllib.parse import urlparse

from random import choice, randint

from pyrogram.raw.types.messages.bot_callback_answer import BotCallbackAnswer
from pyrogram.client import Client
from pyrogram.types import Message, User
from pyrogram.errors import FloodWait, UserChannelsTooMuch, UserAlreadyParticipant

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


settings = {}

if exists("settings.json") and stat('proxies.json').st_size > 0:
    with open("settings.json", "r", encoding='utf-8-sig') as f:
        settings = json.load(f)


delay_range = settings.get("delay") or input("Задержка между аккаунтами(в секундах) в формате: min max(например: 10 120)\n")
min_delay, max_delay = delay_range.split(' ')

min_delay = int(min_delay)
max_delay = int(max_delay)

bot_token=settings.get("bot_token") or input("bot token: ")
chat_id=settings.get("user_id") or input("ваш telegram id: ")

# sessions = set()


async def http_get(url: str, referer: str):
    headers = {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "ru,en;q=0.9,en-GB;q=0.8,en-US;q=0.7",
        "Referer": referer,
        "Sec-Ch-Ua": '"Not/A)Brand";v="99", "Microsoft Edge";v="115", "Chromium";v="115", "Microsoft Edge WebView2";v="115"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36 Edg/115.0.1901.203"
    }
    proxy = None

    if settings:
        proxy_data = settings.get("mobile_proxy")

        if proxy_data:
            ip = proxy_data['ip']
            if proxy_data["change_url"]:
                async with aiohttp.ClientSession() as sess:
                    async with sess.get(proxy_data["change_url"]) as resp:
                        print(await resp.text())
                    # if proxy_data["get_ip"]:
                    #     async with sess.get(proxy_data["get_ip"]) as resp:
                    #         ip = await resp.text()
                    #         print(ip)
            proxy = f"{proxy_data['type']}://{proxy_data['login']}:{proxy_data['password']}@{ip}"
    # print(proxy)
    async with aiohttp.ClientSession() as sess:
        async with sess.get(url, headers=headers, proxy=proxy) as resp:
            return await resp.text()

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

        for _ in range(5):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, json=payload) as response:
                        result = await response.json()
                        return result
            except:
                await asyncio.sleep(5)
                

    async def success(self, message: str):
        logger.success(f"{self.name}{message}")
        
        log = f"""success:\n {message}
```------------------```
session: `{self.session_filename}`
username: @{self.me.username}
"""

        await self.send_markdown_message(text=log)
    
    async def error(self, message: str):
        logger.error(f"{self.name}{message}")
        
        log = f"""error:\n {message}
```------------------```
session: `{self.session_filename}`
username: @{self.me.username}
"""

        await self.send_markdown_message(text=log)
    
    async def info(self, message: str):
        logger.info(f"{self.name}{message}")
        
        log = f"""info:\n {message}
```------------------```
session: `{self.session_filename}`
username: @{self.me.username}
"""

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
        
        result = []
        for element in data:
            parsed_url = urlparse(element)
            path = parsed_url.path.split('/')

            if len(path) == 4:
                if path[2].isdigit():
                    result.append(f'-100{path[2]}:{path[3]}')
                else:
                    result.append(f'{path[1]}:{path[2]}')
                continue
            
            if len(path) == 3:
                result.append(f'{path[1]}:{path[2]}')
                continue

            
            if len(path) == 1:
                result.append(f'{element}:{-1}')
                continue
            
            if len(path) == 2:
                result.append(f"@{path[1]}" if not path[1].startswith("+") else element)
                continue

            result.append(element)

        return result

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
                    await self.success(f'Успешно вышел из чата/канала `{chat}`')

                except UserAlreadyParticipant:
                    await self.error(f"Не удалось вступить в {join_link}. Я уже состою в этом чате")
                    break
                else:
                    await self.success(f'Вступил в чат `{joined_chat.title}` `[`{join_link}`]`')
                    break

    async def leave_chat(self):
        raise NotImplementedError
    

    async def start_ref_bot(self, url):
        parsed_url = urlparse(res)
        query = parsed_url.query.split('=')
        async with self.client as app:
            res = await app.send_message(chat_id=parsed_url.path.split('/')[1], text=f"/{query[0]} {' '.join(query[1:])}")

        await self.success(f"Активировал реф бота")

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
            # print(message)

            if not isinstance(message, Message):
                return await self.error(f"Не удалось получить сообщение с кнопкой")

            while True:
                res = None
                try:
                    res = await message.click(button_id)
                    print(res)
                    if isinstance(res, str) and res.startswith("https://t.me"):
                        parsed_url = urlparse(res)
                        query = parsed_url.query.split('=')
                        if "BlessMeBot" in res:
                            logger.info(f"Найден RandomGodBot")
                            start_param = parsed_url.query.split("&")[0].replace("startapp=", "")

                            try:
                                res = await http_get(f"https://randomgodbot.com/api/lottery/requestCaptcha.php?userId={self.me.id}&startParam={start_param}", f"https://randomgodbot.com/api/lottery/?tgWebAppStartParam={start_param}")
                            except Exception as e:
                                res = str(e)
                                await self.error(f"Не удалось вступить в розыгрыш в RandomGodBot, {e}")

                        else:
                            res = await app.send_message(chat_id=parsed_url.path.split('/')[1], text=f"/{query[0]} {' '.join(query[1:])}")

                except FloodWait as error:
                    await asyncio.sleep(error.value) #type: ignore

                except TimeoutError:
                    await self.info(f'TimeOut при нажатии кнопки (возможно она была успешно нажата)')
                    break

                except ValueError:
                    break

                else:
                    await self.success(f'Кнопка успешно нажата({button_id}). Полученный ответ: ``` {res.message if isinstance(res, BotCallbackAnswer) else res}```') #type: ignore
                    break



async def send_end_message():
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    payload = {
        "chat_id": chat_id, 
        "text": "Закончил работу",
        "parse_mode": "Markdown"
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as response:
            result = await response.json()
            return result

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

    await send_end_message()


async def clicker():
    click_chat_target = input('Перетяните .txt, в котором с новой строки указаны '
                                    'ссылки на посты или айди каналов: ')

    links = TelegramSession.parse_data_from_file(click_chat_target)
    # print(links)
    for sess in session_files:
        ts = TelegramSession(sess, proxy=proxies_json.get(sess) if proxies_json else "")
        await ts.start()
        for link in links:
            chat_id, message_id = link.split(':')
            await ts.click_button(chat_id, int(message_id))
        
        await asyncio.sleep(randint(min_delay, max_delay))

    await send_end_message()

async def ref_clicker():
    click_chat_target = input('Перетяните .txt, в котором с новой строки указаны '
                                'ссылки на посты или айди каналов: ')

    with open(click_chat_target, "r", encoding="utf-8") as f:
        links = f.read().splitlines()

    for sess in session_files:
        ts = TelegramSession(sess, proxy=proxies_json.get(sess) if proxies_json else "")
        await ts.start()
        for link in links:
            await ts.start_ref_bot(link)

        await asyncio.sleep(randint(min_delay, max_delay))
    
    await send_end_message()

    

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
                            '3. Telegram Send Start Command With Referral Link\n'
                            'Выберите ваше действие: '))
    

    match user_action:
        case 1:
            
            asyncio.run(joiner())


        case 2:
            asyncio.run(clicker())
        
        case 3:
            asyncio.run(ref_clicker())

        case _:
            logger.error('Такой функции не обнаружено')
            input('Press Any Key To Exit..')
            exit()