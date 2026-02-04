import requests
from base64 import b64encode
from random import choice, random
from asyncio import sleep as asleep
from urllib.parse import quote

from cloudscraper import create_scraper
from urllib3 import disable_warnings

from ... import LOGGER, shortener_dict
from ...core.config_manager import Config

# --- VERCEL CONFIG ---
VERCEL_DOMAIN = "https://token-system-dcbots.vercel.app"
# ---------------------

async def short_url(longurl, attempt=0):
    if not shortener_dict and not Config.PROTECTED_API:
        return longurl
    if attempt >= 4:
        return longurl

    cget = create_scraper().request
    disable_warnings()
    
    try:
        # STEP 1: വെർസെൽ വെരിഫിക്കേഷൻ ലെയർ
        unique_uid = None
        hint = None
        
        # Wzv3-ൽ സാധാരണ ടോക്കൺ format: start=TOKEN
        # നാം വെർസെല്ലിലേക്ക് ഇത് അയക്കുന്നു
        if VERCEL_DOMAIN and "start=" in longurl:
            try:
                # ലിങ്കിൽ നിന്ന് ടോക്കൺ മാത്രം എടുക്കുന്നു
                original_token = longurl.split("start=")[-1]
                # User ID നിലവിൽ അറിയില്ലെങ്കിൽ 'wzv3_user' എന്ന് നൽകാം
                user_id = "wzv3_user" 

                v_res = requests.get(
                    f"{VERCEL_DOMAIN}/api/verify/create",
                    params={"uid": user_id, "token": original_token},
                    timeout=10
                ).json()
                
                unique_uid = v_res.get('unique_uid')
                hint = v_res.get('connection_hint')
                # ഇപ്പോൾ നാം ഷോർട്ട് ചെയ്യാൻ പോകുന്നത് വെർസെൽ ലിങ്കാണ്
                longurl = v_res.get('verify_link')

            except Exception as ve:
                LOGGER.error(f"Vercel Registration Error: {ve}")

        # --- നിങ്ങളുടെ ഒറിജിനൽ ഷോർട്ടനർ ലോജിക് (മാറ്റമില്ലാതെ) ---
        if Config.PROTECTED_API:
            res = cget("GET", Config.PROTECTED_API, params={"url": longurl}).json()
            if res.get("status") == "success":
                return res["url"]
            raise Exception(f"Protected API Error: {res}")

        _shortener, _shortener_api = choice(list(shortener_dict.items()))
        
        shorted_url = None
        if "shorte.st" in _shortener:
            headers = {"public-api-token": _shortener_api}
            data = {"urlToShorten": quote(longurl)}
            shorted_url = cget(
                "PUT", "https://api.shorte.st/v1/data/url", headers=headers, data=data
            ).json().get("shortenedUrl")
        elif "linkvertise" in _shortener:
            url = quote(b64encode(longurl.encode("utf-8")))
            linkvertise = [
                f"https://link-to.net/{_shortener_api}/{random() * 1000}/dynamic?r={url}",
                f"https://up-to-down.net/{_shortener_api}/{random() * 1000}/dynamic?r={url}",
                f"https://direct-link.net/{_shortener_api}/{random() * 1000}/dynamic?r={url}",
                f"https://file-link.net/{_shortener_api}/{random() * 1000}/dynamic?r={url}",
            ]
            shorted_url = choice(linkvertise)
        elif "bitly.com" in _shortener:
            headers = {"Authorization": f"Bearer {_shortener_api}"}
            shorted_url = cget(
                "POST",
                "https://api-ssl.bit.ly/v4/shorten",
                json={"long_url": longurl},
                headers=headers,
            ).json().get("link")
        elif "ouo.io" in _shortener:
            shorted_url = cget(
                "GET", f"http://ouo.io/api/{_shortener_api}?s={longurl}", verify=False
            ).text
        elif "cutt.ly" in _shortener:
            shorted_url = cget(
                "GET",
                f"http://cutt.ly/api/api.php?key={_shortener_api}&short={longurl}",
            ).json().get("url", {}).get("shortLink")
        else:
            res = cget(
                "GET",
                f"https://{_shortener}/api?api={_shortener_api}&url={quote(longurl)}",
            ).json()
            shorted_url = res.get("shortenedUrl")
            if not shorted_url:
                shrtco_res = cget(
                    "GET", f"https://api.shrtco.de/v2/shorten?url={quote(longurl)}"
                ).json()
                shrtco_link = shrtco_res["result"]["full_short_link"]
                res = cget(
                    "GET",
                    f"https://{_shortener}/api?api={_shortener_api}&url={shrtco_link}",
                ).json()
                shorted_url = res.get("shortenedUrl")
        
        if not shorted_url:
            shorted_url = longurl

        # STEP 2: ജിപി ലിങ്കിനെ വെർസെൽ സ്റ്റാർട്ട് ലിങ്ക് ആക്കി മാറ്റുന്നു
        if VERCEL_DOMAIN and unique_uid and hint:
            try:
                final_res = requests.get(
                    f"{VERCEL_DOMAIN}/api/start/create",
                    params={"uid": unique_uid, "hint": hint, "url": shorted_url},
                    timeout=10
                ).json()
                return final_res.get('start_link', shorted_url)
            except Exception as fe:
                LOGGER.error(f"Vercel Final Link Error: {fe}")
                return shorted_url
        
        return shorted_url

    except Exception as e:
        LOGGER.error(e)
        await asleep(0.8)
        attempt += 1
        return await short_url(longurl, attempt)
