import requests
import base64
import os
import time
from datetime import datetime
from PIL import Image, ImageOps
import google.generativeai as genai
from io import BytesIO
import numpy as np
import cv2
from itertools import product
import warnings
from urllib3.exceptions import InsecureRequestWarning
from dotenv import load_dotenv
import random
import json

warnings.simplefilter('ignore', InsecureRequestWarning)

login_url = 'https://www.aeropres.in/chromeapi/dawn/v1/user/login/v2'
keepalive_url = 'https://www.aeropres.in/chromeapi/dawn/v1/userreward/keepalive?appid=undefined'
get_points_url = 'https://www.aeropres.in/api/atom/v1/userreferral/getpoint?appid=undefined'
get_puzzle_url = 'https://www.aeropres.in/chromeapi/dawn/v1/puzzle/get-puzzle'

headers = {
    'Content-Type': 'application/json',
    'Origin': 'chrome-extension://fpdkjdnhkakefebpekbdhillbhonfjjp',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36'
}

token = None
global_username = None
plus = '[\x1b[32m+\x1b[0m]'
mins = '[\x1b[31m-\x1b[0m]'
arah = '\x1b[33m»\x1b[0m'

load_dotenv()

EMAIL = os.getenv("EMAIL")
PASSWORD = os.getenv("PASSWORD")
PROXY = os.getenv("PROXY")

genai.configure(api_key="AIzaSyC9dfnNnd9uTuuxf9sgV_f48kYJ7uRQlZU")

def get_local_time():
    now = datetime.now()
    return now.strftime("%H:%M:%S %d-%m")

def get_random_proxy(proxy_file):
    with open(proxy_file, 'r') as f:
        proxies = [line.strip() for line in f.readlines()]
    return random.choice(proxies)

def parse_proxy_string(proxy_string):
    try:
        proxy_parts = proxy_string.split(':')
        if len(proxy_parts) == 2:
            return {
                'http': f'http://{proxy_string}',  
                'https': f'http://{proxy_string}'  
            }
        elif len(proxy_parts) == 4:
            user_pass = f'{proxy_parts[2]}:{proxy_parts[3]}@'
            proxy_ip = f'{proxy_parts[0]}:{proxy_parts[1]}'
            return {
                'http': f'http://{user_pass}{proxy_ip}',  
                'https': f'http://{user_pass}{proxy_ip}'  
            }
    except Exception as e:
        print(f"[{get_local_time()}] {mins} Format proxy tidak valid: {proxy_string}")
        return None

def get_working_proxy():
    if PROXY and PROXY.lower() != 'false':
        if os.path.exists(PROXY):
            proxies_tried = set()  
            while True:
                random_proxy = get_random_proxy(PROXY)
                if random_proxy in proxies_tried:
                    print(f"[{get_local_time()}] {mins} Semua proxy gagal. Menggunakan IP lokal.")
                    break
                proxies_tried.add(random_proxy)
                
                proxy = parse_proxy_string(random_proxy)
                if proxy and check_proxy(proxy):
                    print(f"[{get_local_time()}] {plus} Menggunakan proxy: {random_proxy}")
                    return proxy
                else:
                    print(f"[{get_local_time()}] {mins} Proxy gagal: {random_proxy}")
        else:
            proxy = parse_proxy_string(PROXY)
            if proxy and check_proxy(proxy):
                print(f"[{get_local_time()}] {plus} Menggunakan proxy: {PROXY}")
                return proxy
            else:
                print(f"[{get_local_time()}] {mins} Gagal menggunakan proxy: {PROXY}")

    print(f"[{get_local_time()}] {plus} Tidak ada proxy yang berfungsi, menggunakan IP lokal")
    return None

def check_proxy(proxy):
    test_url = 'http://example.com'
    try:
        print(f"[{get_local_time()}] {plus} Menguji proxy: {proxy}")
        response = requests.get(test_url, proxies=proxy, timeout=10)
        if response.status_code == 200:
            print(f"[{get_local_time()}] {plus} Proxy berfungsi: {proxy}")
            return True
    except Exception as e:
        print(f"[{get_local_time()}] {mins} Proxy gagal: {proxy} - {e}")
    return False

def process_captcha(base64_data):
    def process_image_from_base64(base64_data):
        image_data = base64.b64decode(base64_data)
        image = Image.open(BytesIO(image_data))

        gray_image = ImageOps.grayscale(image)
        gray_np = np.array(gray_image)
        _, thresholded = cv2.threshold(gray_np, 50, 255, cv2.THRESH_BINARY_INV)
        processed_image = Image.fromarray(thresholded)

        processed_image_path = "processed_captcha.png"
        processed_image.save(processed_image_path)

        return processed_image_path

    def upload_to_gemini(path, mime_type="image/png"):
        file = genai.upload_file(path, mime_type=mime_type)
        return file

    def get_captcha_text_from_gemini(base64_data):
        try:
            processed_image_path = process_image_from_base64(base64_data)
            uploaded_file = upload_to_gemini(processed_image_path)

            generation_config = {
                "temperature": 1,
                "top_p": 0.95,
                "top_k": 64,
                "max_output_tokens": 8192,
                "response_mime_type": "text/plain",
            }

            model = genai.GenerativeModel(
                model_name="gemini-1.5-flash",
                generation_config=generation_config,
                system_instruction="Tolong ekstrak hanya karakter dari gambar CAPTCHA, tidak ada teks tambahan."
            )

            chat_session = model.start_chat(
                history=[
                    {
                        "role": "user",
                        "parts": [
                            uploaded_file,
                            "Ekstrak hanya karakternya, tidak ada teks tambahan seperti 'Karakter yang ditemukan adalah:'."
                        ],
                    },
                ]
            )

            response = chat_session.send_message("Ekstrak hanya karakter dari gambar.")
            return response.text.strip()

        except Exception as e:
            error_message = str(e)
            if "SAFETY" in error_message:
                print(f"Bypass Error, Retry...")
                return get_captcha_text_from_gemini(base64_data)
            else:
                raise e

    def remove_spaces(text):
        return text.replace(" ", "")

    captcha_text = get_captcha_text_from_gemini(base64_data)
    cleaned_captcha_text = remove_spaces(captcha_text)
    return cleaned_captcha_text

def animate_captcha_typing(captcha):
    typed = ""
    for char in captcha:
        typed += char
        print(f"Captcha  {arah} {typed}_", end="\r")
        time.sleep(0.4)
    print()

def get_puzzle():
    try:
        response = requests.get(get_puzzle_url, headers=headers, proxies=proxies, verify=False)

        if response.status_code == 201:
            try:
                puzzle_data = response.json()
            except ValueError:
                raise Exception(f"JSON tidak valid dalam respon puzzle. Status code: {response.status_code}, Respon: {response.text}")

            puzzle_id = puzzle_data.get('puzzle_id')
            if not puzzle_id:
                raise Exception(f"Puzzle ID tidak ditemukan dalam respon. Data respon: {puzzle_data}")

            get_puzzle_image_url = f"https://www.aeropres.in/chromeapi/dawn/v1/puzzle/get-puzzle-image?puzzle_id={puzzle_id}"
            image_response = requests.get(get_puzzle_image_url, headers=headers, proxies=proxies, verify=False)

            if image_response.status_code == 200:
                try:
                    image_data = image_response.json()
                except ValueError:
                    raise Exception(f"JSON tidak valid dalam respon gambar. Status code: {image_response.status_code}, Respon: {image_response.text}")

                if image_data.get('success'):
                    img_base64 = image_data['imgBase64']
                    cleaned_captcha_text = process_captcha(img_base64)
                    animate_captcha_typing(cleaned_captcha_text)
                    return puzzle_id, cleaned_captcha_text
                else:
                    raise Exception(f"Gagal mendapatkan gambar CAPTCHA. Data respon: {image_data}")
            else:
                raise Exception(f"Gagal mendapatkan gambar puzzle. Status code: {image_response.status_code}")
        else:
            raise Exception(f"Gagal mendapatkan puzzle ID. Status code: {response.status_code}")

    except Exception as e:
        print(f"[{get_local_time()}] {mins} Kesalahan mendapatkan CAPTCHA: {str(e)}")
        raise

def login(username, password, puzzle_id, captcha_answer):
    global token, global_username
    now = datetime.now().isoformat()
    login_data = {
        'username': username,
        'password': password,
        'logindata': {
            '_v': '1.0.7',
            'datetime': now
        },
        'puzzle_id': puzzle_id,
        'ans': captcha_answer
    }

    try:
        response = requests.post(login_url, json=login_data, headers=headers, proxies=proxies, verify=False)
        
        if response.status_code == 400:
            response_data = response.json()
            if response_data['message'] == "Incorrect answer. Try again!":
                print(f"Jawaban salah. Coba lagi!")
                print(f"Captcha  {arah} _", end="\r")
                puzzle_id, new_captcha_answer = get_puzzle()
                login(username, password, puzzle_id, new_captcha_answer)
                return

        response_data = response.json()
        token = response_data['data']['token']
        global_username = username
        print(f"\n[{get_local_time()}] {plus} Login   : Sukses")
        print(f"[{get_local_time()}] {plus} Nama    : {response_data['data']['firstname']}")
        print(f"[{get_local_time()}] {plus} Email   : {response_data['data']['email'][:5]}{'*' * (len(response_data['data']['email']) - 1)}{response_data['data']['email'][-10:]}")

        update_social_media_points()

        run_keep_alive_and_get_points()

    except Exception as e:
        print(f"\n[{get_local_time()}] {mins} Login      : Kesalahan {str(e)}")
        ask_credentials()

def update_social_media_points():
    try:
        telegram_data = {"telegramid": "telegramid"}
        telegram_response = requests.post(
            'https://www.aeropres.in/chromeapi/dawn/v1/profile/update',
            json=telegram_data,
            headers={**headers, 'Authorization': f'Bearer {token}'},
            proxies=proxies,
            verify=False
        )
        if telegram_response.status_code == 200:
            print(f"[{get_local_time()}] {plus} Telegram Done")
        else:
            print(f"[{get_local_time()}] {mins} Gagal memperbarui poin Telegram")

        discord_data = {"discordid": "discordid"}
        discord_response = requests.post(
            'https://www.aeropres.in/chromeapi/dawn/v1/profile/update',
            json=discord_data,
            headers={**headers, 'Authorization': f'Bearer {token}'},
            proxies=proxies,
            verify=False
        )
        if discord_response.status_code == 200:
            print(f"[{get_local_time()}] {plus} Discord Done")
        else:
            print(f"[{get_local_time()}] {mins} Gagal memperbarui poin Discord")

        twitter_data = {"twitter_x_id": "twitter_x_id"}
        twitter_response = requests.post(
            'https://www.aeropres.in/chromeapi/dawn/v1/profile/update',
            json=twitter_data,
            headers={**headers, 'Authorization': f'Bearer {token}'},
            proxies=proxies,
            verify=False
        )
        if twitter_response.status_code == 200:
            print(f"[{get_local_time()}] {plus} Twitter Done")
        else:
            print(f"[{get_local_time()}] {mins} Gagal memperbarui poin Twitter")

    except Exception as e:
        print(f"[{get_local_time()}] {mins} Kesalahan memperbarui poin media sosial: {str(e)}")

def keep_alive():
    try:
        requests.post(keepalive_url, json={
            'username': global_username,
            'extensionid': 'fpdkjdnhkakefebpekbdhillbhonfjjp',
            'numberoftabs': 0,
            '_v': '1.0.9'
        }, headers={**headers, 'Authorization': f'Bearer {token}'}, proxies=proxies, verify=False)
    except Exception as e:
        print(f"[{get_local_time()}] {mins} Kesalahan KeepAlive: {str(e)}")

def get_points():
    try:
        response = requests.get(get_points_url, headers={**headers, 'Authorization': f'Bearer {token}'}, proxies=proxies, verify=False)
        response_data = response.json()['data']
        
        points_data = response_data['rewardPoint']
        referral_data = response_data['referralPoint']
        
        total_points = (
            points_data.get('points', 0) +
            points_data.get('registerpoints', 0) +
            points_data.get('signinpoints', 0) +
            points_data.get('twitter_x_id_points', 0) +
            points_data.get('discordid_points', 0) +
            points_data.get('telegramid_points', 0) +
            points_data.get('bonus_points', 0) +
            referral_data.get('commission', 0) 
        )
        
        print(f"[{get_local_time()}] {plus} Poin  : {total_points}")
        
    except Exception as e:
        print(f"[{get_local_time()}] {mins} Kesalahan poin: {str(e)}")

def ask_credentials():
    """
    Fungsi ini menangani proses login dengan mendapatkan CAPTCHA dan 
    menggunakan kredensial pengguna untuk login ke sistem.
    """
    try:
        print(f"\nEmail    {arah} {EMAIL[:5]}{'*' * (len(EMAIL) - 5)}{EMAIL[-10:]}")
        print(f"Password {arah} {PASSWORD[:2]}{'*' * (len(PASSWORD) - 2)}")
        
        print(f"Captcha  {arah} _", end="\r")
        puzzle_id, captcha_answer = get_puzzle()

        login(EMAIL, PASSWORD, puzzle_id, captcha_answer)
    except Exception as e:
        print(f"[{get_local_time()}] {mins} Kesalahan: {str(e)}")

def run_keep_alive_and_get_points():
    loop_counter = 0
    while True:
        loop_counter += 1
        keep_alive()
        time.sleep(5)
        get_points()
        time.sleep(5)

def get_ascii_art():

    return """\
    
    ______                     
    |  _  \   \x1b[33mADFMIDN - v1.2\x1b[0m               
    | | | |__ ___      ___ __  
    | | | / _` \ \ /\ / / '_ \ 
    | |/ / (_| |\ V  V /| | | |
    |___/ \__,_| \_/\_/ |_| |_|

    """

if __name__ == "__main__":
    print(get_ascii_art())
    proxies = get_working_proxy()
    ask_credentials()
