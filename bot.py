import os
import sys
import time
import json
import random

from loguru import logger

import requests
import argparse
from datetime import datetime
from colorama import *
from urllib.parse import parse_qs
from base64 import b64decode
from concurrent.futures import ThreadPoolExecutor, as_completed

red = Fore.LIGHTRED_EX
white = Fore.LIGHTWHITE_EX
green = Fore.LIGHTGREEN_EX
yellow = Fore.LIGHTYELLOW_EX
blue = Fore.LIGHTBLUE_EX
reset = Style.RESET_ALL
black = Fore.LIGHTBLACK_EX
magenta = Fore.LIGHTMAGENTA_EX


def countdown(t):
    while t:
        minutes, seconds = divmod(t, 60)
        hours, minutes = divmod(minutes, 60)
        hours = str(hours).zfill(2)
        minutes = str(minutes).zfill(2)
        seconds = str(seconds).zfill(2)
        print(f"{white}waiting until {hours}:{minutes}:{seconds} ", flush=True, end="\r")
        t -= 1
        time.sleep(1)
    print("                          ", flush=True, end="\r")


class BlumBot:
    def __init__(self, init_data, proxy=None):
        self.base_headers = {
            "accept": "application/json, text/plain, */*",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0",
            "content-type": "application/json",
            "origin": "https://telegram.blum.codes",
            "x-requested-with": "org.telegram.messenger",
            "sec-fetch-site": "same-site",
            "sec-fetch-mode": "cors",
            "sec-fetch-dest": "empty",
            "referer": "https://telegram.blum.codes/",
            "accept-encoding": "gzip, deflate",
            "accept-language": "en,en-US;q=0.9",
        }

        self.headers = self.base_headers.copy()
        self.ses = requests.Session()
        self.init_data = init_data
        self.proxy = proxy
        self.balance = 0
        self.print_ipinfo()

        if self.proxy:
            self.set_proxy()

        parsed_init_data = self.parse_init_data(self.init_data)
        self.user_info = json.loads(parsed_init_data.get("user", '{}'))
        self.userid = self.user_info["id"]
        self.access_token = self.get_access_token()
        self.headers["Authorization"] = f"Bearer {self.access_token}"

        logger.info(f"{green}login as : {white}{self.user_info.get('username')}, userid: {self.userid}")

    def renew_access_token(self):
        headers = self.base_headers.copy()
        data = json.dumps(
            {
                "query": self.init_data,
                # "referralToken": "8KRxh44e4M"
            },
        )
        headers["Content-Length"] = str(len(data))
        url = "https://user-domain.blum.codes/api/v1/auth/provider/PROVIDER_TELEGRAM_MINI_APP"
        res = self.make_request(url, headers, data)
        token = res.json().get("token")
        if token is None:
            logger.info(f"{red}'token' is not found in response, check you data !!")
            return ''

        self.access_token = token.get("access")
        self.save_local_token()

        logger.info(f"{green}success get access token ")
        self.headers["Authorization"] = f"Bearer {self.access_token}"
        return self.access_token

    def validate_task(self, task):
        answers = {
            "What are Telegram Mini Apps?": "CRYPTOBLUM",
            "Navigating Crypto": "HEYBLUM",
            "Secure your Crypto!": "BEST PROJECT EVER",
            "Forks Explained": "GO GET",
            "Say No to Rug Pull!": "SUPERBLUM",
            "How to Analyze Crypto?": "VALUE",
            "$2.5M+ DOGS Airdrop": "Happydogs",
            "What Are AMMs?": "Cryptosmart",
            "Liquidity Pools Guide": "Blumersss"
        }

        if task.get("validationType") != "KEYWORD":
            logger.info(f'unsupported verify task {task}')
            return

        task_id = task.get("id", None)
        validate_url = f"https://earn-domain.blum.codes/api/v1/tasks/{task_id}/validate"
        question = task.get("title")
        ans = answers.get(question, None)
        if ans:
            res = self.make_request(validate_url, self.headers, {"keyword": ans})
            status = res.json().get("status")
            logger.info(f"success validate task {question}, task status: {status}")
            return status

        logger.error(f"unknow question: {question}")
        return None

    def claim_task_reward(self, task):
        task_id = task.get("id")
        task_title = task.get("title")
        claim_task_url = f"https://earn-domain.blum.codes/api/v1/tasks/{task_id}/claim"
        status = self.make_request(claim_task_url, self.headers, "").json().get("status")
        logger.info(f"claim task: {task_title} reward, status: {status}")
        return status

    def start_task(self, task):
        start_task_url = f"https://earn-domain.blum.codes/api/v1/tasks/{task.get('id')}/start"
        resp = self.make_request(start_task_url, self.headers, "").json()
        status = resp.get("status")
        if resp.get("status"):
            logger.info(f'started task: {task.get("title")}, status: {status}')
        else:
            logger.warning(f'started task: {task.get("title")} error, resp: {resp}')
        return status if status else task.get('status')

    def solve(self, task: dict):
        ignore_tasks = [
            "39391eb2-f031-4954-bd8a-e7aecbb1f192",  # wallet connect
            "d3716390-ce5b-4c26-b82e-e45ea7eba258",  # invite task
            "f382ec3f-089d-46de-b921-b92adfd3327a",  # invite task
            "220ee7b1-cca4-4af8-838a-2001cb42b813",  # invite task
            "5ecf9c15-d477-420b-badf-058537489524",  # invite task
            "c4e04f2e-bbf5-4e31-917b-8bfa7c4aa3aa",  # invite task
        ]
        task_id = task.get("id")
        task_status = task.get("status")
        if task_id in ignore_tasks:
            return

        if task_status == "NOT_STARTED" and task.get("type") == "PROGRESS_TARGET":
            return

        if task_status == "NOT_STARTED":
            task_status = self.start_task(task)
            countdown(random.randint(1, 3))

        if task_status == "STARTED":
            task_status = self.claim_task_reward(task)

        if task_status == "READY_FOR_VERIFY":
            task_status = self.validate_task(task)
            countdown(random.randint(1, 3))

        if task_status == "READY_FOR_CLAIM":
            task_status = self.claim_task_reward(task)

        if task_status == "FINISHED":
            task_title = task.get("title") or task_id
            logger.info(f"already complete task: {task_title} !")

    def solve_task(self):
        url_task = "https://earn-domain.blum.codes/api/v1/tasks"

        res = self.make_request(url_task, self.headers)

        for tasks in res.json():
            if isinstance(tasks, str):
                logger.error(f"failed get task list !")
                return

            for k in list(tasks.keys()):
                if k != "tasks" and k != "subSections":
                    continue
                for t in tasks.get(k):
                    if isinstance(t, dict):
                        if t.get("title") == "New":
                            continue

                        subtasks = t.get("subTasks")
                        if subtasks:
                            for task in subtasks:
                                self.solve(task)
                            self.solve(t)
                            continue
                    for task in t.get("tasks", []):
                        self.solve(task)

    def set_proxy(self, proxy=None):
        if proxy is not None:
            self.ses.proxies.update({"http": proxy, "https": proxy})

    def claim_farming(self):
        url = "https://game-domain.blum.codes/api/v1/farming/claim"
        res = self.make_request(url, self.headers, "")
        balance = res.json().get("availableBalance", 0)
        logger.info(f"{green}balance after claim : {white}{balance}")
        return

    def get_end_farming_time(self, only_show_balance=False):
        url = "https://game-domain.blum.codes/api/v1/user/balance"

        end_farming = 0

        while True:
            res = self.make_request(url, self.headers)
            self.balance = res.json().get("availableBalance", 0)
            logger.info(f"{green}balance: {white}{self.balance}")
            if only_show_balance:
                return
            timestamp = res.json().get("timestamp")
            if timestamp is None:
                countdown(3)
                continue
            timestamp = round(timestamp / 1000)
            if "farming" not in res.json().keys():
                return False, "not_started"

            end_farming = res.json().get("farming", {}).get("endTime")
            if end_farming is None:
                countdown(3)
                continue
            break

        end_farming = round(end_farming / 1000)
        if timestamp > end_farming:
            logger.info(f"{green}now is time to claim farming !")
            return True, end_farming

        logger.info(f"{yellow}not time to claim farming !")
        end_date = datetime.fromtimestamp(end_farming)
        logger.info(f"{green}end farming : {white}{end_date}")
        return False, end_farming

    def get_balance(self):
        url = "https://game-domain.blum.codes/api/v1/user/balance"
        res = self.make_request(url, self.headers)
        self.balance = res.json().get("availableBalance", 0)
        logger.info(f"{green}balance: {white}{self.balance}")
        return self.balance

    def start_farming(self):
        url = "https://game-domain.blum.codes/api/v1/farming/start"

        while True:
            res = self.make_request(url, self.headers, "")
            end = res.json().get("endTime")
            if end is None:
                countdown(3)
                continue
            break

        end_date = datetime.fromtimestamp(end / 1000)
        logger.info(f"{green}start farming successfully !")
        logger.info(f"{green}end farming : {white}{end_date}")
        return round(end / 1000)

    def get_friend(self):
        url = "https://user-domain.blum.codes/api/v1/friends/balance"

        res = self.make_request(url, self.headers)
        can_claim = res.json().get("canClaim", False)
        limit_invite = res.json().get("limitInvitation", 0)
        amount_claim = res.json().get("amountForClaim")
        logger.info(f"{white}limit invitation : {green}{limit_invite}")
        logger.info(f"{green}referral balance : {white}{amount_claim}")
        logger.info(f"{white}can claim referral : {green}{can_claim}")
        if can_claim:
            url_claim = "https://user-domain.blum.codes/api/v1/friends/claim"
            res = self.make_request(url_claim, self.headers, "")
            if res.json().get("claimBalance") is not None:
                logger.info(f"{green}success claim referral bonus !")
                return
            logger.info(f"{red}failed claim referral bonus !")
            return

    def checkin(self):
        url = "https://game-domain.blum.codes/api/v1/daily-reward?offset=-420"

        res = self.make_request(url, self.headers)
        if res.status_code == 404:
            logger.info(f"{yellow}already check in today !")
            return
        res = self.make_request(url, self.headers, "")
        if "ok" in res.text.lower():
            logger.info(f"{green}success check in today !")
            return

        logger.info(f"{red}failed check in today !")
        return

    def playgame(self):
        url_play = "https://game-domain.blum.codes/api/v1/game/play"
        url_claim = "https://game-domain.blum.codes/api/v1/game/claim"
        url_balance = "https://game-domain.blum.codes/api/v1/user/balance"

        while True:
            res = self.make_request(url_balance, self.headers)
            play = res.json().get("playPasses")
            if play is None:
                logger.info(f"{yellow}failed get game ticket !")
                break
            logger.info(f"{green}you have {white}{play}{green} game ticket")
            if play <= 0:
                return

            for i in range(min(play, 5)):
                if self.is_expired(self.access_token):
                    return True
                res = self.make_request(url_play, self.headers, "")
                game_id = res.json().get("gameId")
                if game_id is None:
                    message = res.json().get("message", "")
                    if message == "cannot start game":
                        logger.info(
                            f"{yellow}{message},will be tried again in the next round."
                        )
                        return False
                    logger.info(f"{yellow}{message}")
                    continue
                while True:
                    countdown(random.randint(30, 60))
                    point = random.randint(self.MIN_WIN, self.MAX_WIN)
                    data = json.dumps({"gameId": game_id, "points": point})
                    res = self.make_request(url_claim, self.headers, data)
                    if "OK" in res.text:
                        logger.info(
                            f"{green}success earn {white}{point}{green} from game !"
                        )
                        self.get_end_farming_time(only_show_balance=True)
                        break

                    message = res.json().get("message", "")
                    if message == "game session not finished":
                        continue

                    logger.info(f"{red}failed earn {white}{point}{red} from game !")
                    break

    def parse_init_data(self, data):
        return {k: v[0] for k, v in parse_qs(data).items()}

    def get_local_token(self, userid):
        if not os.path.exists("tokens.json"):
            open("tokens.json", "w").write(json.dumps({}))
        tokens = json.loads(open("tokens.json", "r").read())
        if str(userid) not in tokens.keys():
            return False

        return tokens[str(userid)]

    def save_local_token(self):
        tokens = json.loads(open("tokens.json", "r").read())
        tokens[str(self.userid)] = self.access_token
        open("tokens.json", "w").write(json.dumps(tokens, indent=4))

    def is_expired(self, token):
        if not token or isinstance(token, bool):
            return True
        header, payload, sign = token.split(".")
        payload = b64decode(payload + "==").decode()
        jload = json.loads(payload)
        now = round(datetime.now().timestamp()) + 300
        exp = jload["exp"]
        if now > exp:
            return True

        return False

    def save_failed_token(self, userid, data):
        file = "auth_failed.json"
        if not os.path.exists(file):
            open(file, "w").write(json.dumps({}))

        acc = json.loads(open(file, "r").read())
        if str(userid) in acc.keys():
            return

        acc[str(userid)] = data
        open(file, "w").write(json.dumps(acc, indent=4))

    def load_config(self):
        try:
            config = json.loads(open("config.json", "r").read())
            self.AUTOTASK = config["auto_complete_task"]
            self.JOINTRIBE = config["join_tribe"]
            self.AUTOGAME = config["auto_play_game"]
            self.DEFAULT_INTERVAL = config["interval"]
            self.MIN_WIN = config["game_point"]["low"]
            self.MAX_WIN = config["game_point"]["high"]
            self.report_url = config["report_url"]
            if self.MIN_WIN > self.MAX_WIN:
                logger.info(f"{yellow}high value must be higher than lower value")
                sys.exit()
        except json.decoder.JSONDecodeError:
            logger.info(f"{red}failed decode config.json")
            sys.exit()

    def print_ipinfo(self):
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/105.0.0.0 Safari/537.36"
            }
            url = "https://api.ip.sb/geoip"
            res = self.ses.get(url, headers=headers, timeout=3)
            if res.status_code != 200:
                logger.info(f"{red}failed fetch ipinfo !")
                return False

            res = res.json()
            city = res.get("city")
            country = res.get("country")
            region = res.get("region")
            ip = res.get("ip")
            logger.info(
                f"{green}ip: {ip} country : {white}{country} {green}region : {white}{region} {green}city : {white}{city}"
            )
        except Exception as e:
            logger.error(f"get ipinfo failed, error: {e}!")
        return True

    def make_request(self, url, headers, data=None):
        for _ in range(10):
            try:
                logfile = "http.log"
                if not os.path.exists(logfile):
                    open(logfile, "a")
                logsize = os.path.getsize(logfile)
                if (logsize / (1024 * 2)) > 1:
                    open(logfile, "w").write("")
                if data is None:
                    res = self.ses.get(url, headers=headers, timeout=30)
                elif data == "":
                    res = self.ses.post(url, headers=headers, timeout=30)
                elif isinstance(data, dict):
                    res = self.ses.post(url, headers=headers, json=data, timeout=30)
                else:
                    res = self.ses.post(url, headers=headers, data=data, timeout=30)

                open(logfile, "a", encoding="utf-8").write(res.text + "\n")

                if 'blum.codes' in url and res.status_code == 401:
                    self.renew_access_token()
                    time.sleep(2)
                    continue

                if 500 <= res.status_code < 600:
                    res.raise_for_status()

                if "<title>" in res.text:
                    logger.info(f"{red}failed fetch json response !")
                    time.sleep(2)
                    continue

                return res

            except requests.exceptions.HTTPError as e:
                logger.info(f"{red}HTTP error occurred: {str(e)}")
                time.sleep(2)

            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
                logger.info(f"{red}connection error/ connection timeout !")
                time.sleep(2)

            except requests.exceptions.ProxyError:
                logger.info(f"{red}bad proxy")
                return False

    def get_tribe(self):
        url = "https://tribe-domain.blum.codes/api/v1/tribe/my"
        res = self.make_request(url, headers=self.headers).json()
        chatname = res.get('chatname')
        if chatname:
            logger.info(f'already join tribe: {chatname}')
        return chatname

    def join_tribe(self):

        if self.get_tribe():
            return

        tribe_id = random.choice(["033d5e29-445a-400d-b360-bac04bd223aa", "b372af40-6e97-4782-b70d-4fc7ea435022",
                                  "38396b50-7b62-4e94-ac19-219247e9aa07"])
        url = f"https://tribe-domain.blum.codes/api/v1/tribe/{tribe_id}/join"
        res = self.make_request(url, headers=self.headers, data="")
        logger.info(f'join tribe resutl: {res.json()} ')

    def report_balance(self):
        try:
            balance = float(self.balance)
            report_data = {"user_id": self.userid, "balance": balance}
            ret = requests.post(self.report_url, json=report_data, timeout=3)
            logger.info(f'user: {self.userid} report ret: {ret.json()}')
        except Exception as e:
            logger.info(f"report balance failed, error: {e}")

    def get_access_token(self):
        access_token = self.get_local_token(self.userid)
        failed_fetch_token = False
        while True:
            if not access_token:
                access_token = self.renew_access_token()
                if not access_token:
                    self.save_failed_token(self.userid, self.init_data)
                    failed_fetch_token = True
                    break

            if self.is_expired(access_token):
                logger.error(f'access token: {access_token} is expired')
                access_token = ''
                continue
            break

        if failed_fetch_token:
            logger.error('fetch token failed')
            return ''

        return access_token

    def run(self):
        if not self.access_token:
            logger.error('access token is empty')
            return

        self.checkin()
        self.get_friend()

        status, end_farming_time = self.get_end_farming_time()
        if status:
            self.claim_farming()
            end_farming_time = self.start_farming()

        if isinstance(end_farming_time, str):
            end_farming_time = self.start_farming()

        if self.AUTOTASK:
            self.solve_task()

        if self.JOINTRIBE:
            self.join_tribe()

        if self.AUTOGAME:
            while True:
                token_expired = self.playgame()
                if token_expired:
                    self.renew_access_token()
                    continue
                break

        self.report_balance()
        countdown(self.DEFAULT_INTERVAL)
        return end_farming_time


def process_token(no, token, proxies, use_proxy):
    """
    Process a single token.

    Parameters:
        no (int): The account number (index).
        token (str): The token to be processed.
        proxies (list): List of proxies to use.
        use_proxy (bool): Flag to determine whether to use proxies.

    Returns:
        int or None: The end time returned by app.run(), or None if an exception occurs.
    """
    logger.info(f"{green}Account number - {white}{no + 1}")
    proxy = None
    if use_proxy:
        proxy = proxies[no % len(proxies)]

    try:
        app = BlumBot(token, proxy)
        app.load_config()
        end_time = app.run()
        return end_time
    except Exception as e:
        logger.exception(f"Account {no}, Token: {token}, Error: {e}")
        return None


def main():
    arg = argparse.ArgumentParser()
    arg.add_argument(
        "--marinkitagawa", action="store_true", help="no clear the terminal !"
    )
    arg.add_argument(
        "--data", help="Custom data input (default: data.txt)", default="data.txt"
    )
    arg.add_argument(
        "--proxy",
        help="custom proxy file input (default: proxies.txt)",
        default="proxies.txt",
    )

    args = arg.parse_args()
    if not args.marinkitagawa:
        os.system("cls" if os.name == "nt" else "clear")

    data_file = args.data
    proxy_file = args.proxy

    if not os.path.exists(args.data):
        logger.info(f"{red}{data_file} not found, please input valid file name !")
        sys.exit()

    datas = [i for i in open(data_file, "r").read().splitlines() if len(i) > 0]
    proxies = [i for i in open(proxy_file).read().splitlines() if len(i) > 0]
    use_proxy = len(proxies) > 0

    logger.info(f"{green}total account : {white}{len(datas)}")
    logger.info(f"{blue}use proxy : {white}{use_proxy}")

    if len(datas) <= 0:
        logger.error(f"{red}add data account in {data_file} first")
        sys.exit()

    while True:
        list_countdown = []

        with ThreadPoolExecutor(max_workers=15) as executor:
            # Submit all token processing tasks to the executor
            futures = {
                executor.submit(process_token, no, token, proxies, use_proxy): no
                for no, token in enumerate(datas)
            }

            # As each future completes, process the result
            for future in as_completed(futures):
                end_time = future.result()
                if end_time is not None:
                    list_countdown.append(end_time)

        if not list_countdown:
            logger.warning("All tasks failed or no valid end_time returned. Waiting for 1 second before retrying.")
            time.sleep(1)
            continue

        min_countdown = min(list_countdown)
        now = int(time.time())
        countdown_time = min_countdown - now

        if countdown_time <= 0:
            logger.info("Countdown has reached zero or is negative. Restarting the loop immediately.")
            continue

        countdown(countdown_time)  # Assume this is a predefined countdown function
        logger.info('~' * 50)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit()
