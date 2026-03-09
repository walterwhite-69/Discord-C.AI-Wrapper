import re
from curl_cffi.requests import AsyncSession



ANCHOR_URL = (
    "https://www.google.com/recaptcha/enterprise/anchor"
    "?ar=1&k=6LcKvP8pAAAAALsgIWumgGUZ-5BTiWIoA7H1FY1G"
    "&co=aHR0cHM6Ly9jaGFyYWN0ZXIuYWk6NDQz"
    "&hl=en&v=QvLuXwupqtKMva7GIh5eGl3U"
    "&size=invisible&anchor-ms=20000&execute-ms=30000&cb=ag27txpy827y"
)


BG_DATA = (
    "!q62grYxHRvVxjUIjSFNd0mlvrZ-iCgIHAAAB6FcAAAANnAkBySdqTJGFRK7SirleWAwPVhv9-XwP8ugG"
    "STJJgQ46-0IMBKN8HUnfPqm4sCefwxOOEURND35prc9DJYG0pbmg_jD18qC0c-lQzuPsOtUhHTtfv3--"
    "SVCcRvJWZ0V3cia65HGfUys0e1K-IZoArlxM9qZfUMXJKAFuWqZiBn-Qi8VnDqI2rRnAQcIB8Wra6xWz"
    "mFbRR2NZqF7lDPKZ0_SZBEc99_49j07ISW4X65sMHL139EARIOipdsj5js5JyM19a2TCZJtAu4XL1h0Z"
    "LfomM8KDHkcl_b0L-jW9cvAe2K2uQXKRPzruAvtjdhMdODzVWU5VawKhpmi2NCKAiCRUlJW5lToYkR_X"
    "-07AqFLY6qi4ZbJ_sSrD7fCNNYFKmLfAaxPwPmp5Dgei7KKvEQmeUEZwTQAS1p2gaBmt6SCOgId3QBfF"
    "_robIkJMcXFzj7R0G-s8rwGUSc8EQzT_DCe9SZsJyobu3Ps0-YK-W3MPWk6a69o618zPSIIQtSCor9w_"
    "oUYTLiptaBAEY03NWINhc1mmiYu2Yz5apkW_KbAp3HD3G0bhzcCIYZOGZxyJ44HdGsCJ-7ZFTcEAUST-"
    "aLbS-YN1AyuC7ClFO86CMICVDg6aIDyCJyIcaJXiN-bN5xQD_NixaXatJy9Mx1XEnU4Q7E_KISDJfKUh"
    "DktK5LMqBJa-x1EIOcY99E-eyry7crf3-Hax3Uj-e-euzRwLxn2VB1Uki8nqJQVYUgcjlVXQhj1X7tx4"
    "jzUb0yB1TPU9uMBtZLRvMCRKvFdnn77HgYs5bwOo2mRECiFButgigKXaaJup6NM4KRUevhaDtnD6aJ8Z"
    "WQZTXz_OJ74a_OvPK9eD1_5pTG2tUyYNSyz-alhvHdMt5_MAdI3op4ZmcvBQBV9VC2JLjphDuTW8eW_n"
    "uK9hN17zin6vjEL8YIm_MekB_dIUK3T1Nbyqmyzigy-Lg8tRL6jSinzdwOTc9hS5SCsPjMeiblc65aJC"
    "8AKmA5i80f-6Eg4BT305UeXKI3QwhI3ZJyyQAJTata41FoOXl3EF9Pyy8diYFK2G-CS8lxEpV7jcRYdu"
    "z4tEPeCpBxU4O_KtM2iv4STkwO4Z_-c-fMLlYu9H7jiFnk6Yh8XlPE__3q0FHIBFf15zVSZ3qroshYiH"
    "BMxM5BVQBOExbjoEdYKx4-m9c23K3suA2sCkxHytptG-6yhHJR3EyWwSRTY7OpX_yvhbFri0vgchw7U6"
    "ujyoXeCXS9N4oOoGYpS5OyFyRPLxJH7yjXOG2Play5HJ91LL6J6qg1iY8MIq9XQtiVZHadVpZVlz3iKc"
    "X4vXcQ3rv_qQwhntObGXPAGJWEel5OiJ1App7mWy961q3mPg9aDEp9VLKU5yDDw1xf6tOFMwg2Q-PNDa"
    "KXAyP_FOkxOjnu8dPhuKGut6cJr449BKDwbnA9BOomcVSztEzHGU6HPXXyNdZbfA6D12f5lWxX2B_pob"
    "w3a1gFLnO6mWaNRuK1zfzZcfGTYMATf6d7sj9RcKNS230XPHWGaMlLmNxsgXkEN7a9PwsSVwcKdHg_HU"
    "4vYdRX6vkEauOIwVPs4dS7yZXmtvbDaX1zOU4ZYWg0T42sT3nIIl9M2EeFS5Rqms_YzNp8J-YtRz1h5R"
    "htTTNcA5jX4N-xDEVx-vD36bZVzfoMSL2k85PKv7pQGLH-0a3DsR0pePCTBWNORK0g_RZCU_H898-nT1"
    "syGzNKWGoPCstWPRvpL9cnHRPM1ZKemRn0nPVm9Bgo0ksuUijgXc5yyrf5K49UU2J5JgFYpSp7aMGOUb"
    "1ibrj2sr-D63d61DtzFJ2mwrLm_KHBiN_ECpVhDsRvHe5iOx_APHtImevOUxghtkj-8RJruPgkTVaML2"
    "MEDOdL_UYaldeo-5ckZo3VHss7IpLArGOMTEd0bSH8tA8CL8RLQQeSokOMZ79Haxj8yE0EAVZ-k9-O72"
    "mmu5I0wH5IPgapNvExeX6O1l3mC4MqLhKPdOZOnTiEBlSrV4ZDH_9fhLUahe5ocZXvXqrud9QGNeTpZs"
    "SPeIYubeOC0sOsuqk10sWB7NP-lhifWeDob-IK1JWcgFTytVc99RkZTjUcdG9t8prPlKAagZIsDr1TiX"
    "3dy8sXKZ7d9EXQF5P_rHJ8xvmUtCWqbc3V5jL-qe8ANypwHsuva75Q6dtqoBR8vCE5xWgfwB0GzR3Xi_"
    "l7KDTsYAQIrDZVyY1UxdzWBwJCrvDrtrNsnt0S7BhBJ4ATCrW5VFPqXyXRiLxHCIv9zgo-NdBZQ4hEXX"
    "xMtbem3KgYUB1Rals1bbi8X8MsmselnHfY5LdOseyXWIR2QcrANSAypQUAhwVpsModw7HMdXgV9Uc-Hw"
    "CMWafOChhBr88tOowqVHttPtwYorYrzriXNRt9LkigESMy1bEDx79CJguitwjQ9IyIEu8quEQb_-7AEX"
    "rfDzl_FKgASnnZLrAfZMtgyyddIhBpgAvgR_c8a8Nuro-RGV0aNuunVg8NjL8binz9kgmZvOS38QaP5a"
    "nf2vgzJ9wC0ZKDg2Ad77dPjBCiCRtVe_dqm7FDA_cS97DkAwVfFawgce1wfWqsrjZvu4k6x3PAUH1UNz"
    "QUxVgOGUbqJsaFs3GZIMiI8O6-tZktz8i8oqpr0RjkfUhw_I2szHF3LM20_bFwhtINwg0rZxRTrg4il-"
    "_q7jDnVOTqQ7fdgHgiJHZw_OOB7JWoRW6ZlJmx3La8oV93fl1wMGNrpojSR0b6pc8SThsKCUgoY6zajW"
    "Wa3CesX1ZLUtE7Pfk9eDey3stIWf2acKolZ9fU-gspeACUCN20EhGT-HvBtNBGr_xWk1zVJBgNG29olX"
    "CpF26eXNKNCCovsILNDgH06vulDUG_vR5RrGe5LsXksIoTMYsCUitLz4HEehUOd9mWCmLCl00eGRCkwr"
    "9EB557lyr7mBK2KPgJkXhNmmPSbDy6hPaQ057zfAd5s_43UBCMtI-aAs5NN4TXHd6IlLwynwc1zsYOQ6"
    "z_HARlcMpCV9ac-8eOKsaepgjOAX4YHfg3NekrxA2ynrvwk9U-gCtpxMJ4f1cVx3jExNlIX5LxE46FYI"
    "hQ"
)



def _parse_between(source: str, start: str, end: str) -> str:

    try:
        left  = source.index(start) + len(start)
        right = source.index(end, left)
        return source[left:right]
    except ValueError:
        return ""


def _extract_url_param(url: str, param: str) -> str:

    match = re.search(rf"[?&]{re.escape(param)}=([^&]+)", url)
    return match.group(1) if match else ""




async def solve_recaptcha(anchor_url: str = ANCHOR_URL) -> str:















    recaptcha_type = _parse_between(anchor_url, "recaptcha/", "/")

    if recaptcha_type not in ("enterprise", "api2"):
        raise RuntimeError(f"Unknown reCAPTCHA type: '{recaptcha_type}'")

    key = _extract_url_param(anchor_url, "k")
    co  = _extract_url_param(anchor_url, "co")
    v   = _extract_url_param(anchor_url, "v")

    if not all([key, co, v]):
        raise RuntimeError(f"Failed to parse URL params — key={key!r} co={co!r} v={v!r}")


    get_headers = {
        "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/83.0.4103.116 Safari/537.36",
        "Pragma":          "no-cache",
        "Accept":          "*/*",
        "Accept-Language": "en-US,en;q=0.8",
    }



    async with AsyncSession(impersonate="chrome124") as session:
        get_resp = await session.get(
            anchor_url,
            headers=get_headers,
            allow_redirects=True,
            timeout=15,
        )
        get_resp.raise_for_status()
        anchor_html = get_resp.text



    c_token = _parse_between(anchor_html, 'id="recaptcha-token" value="', '"')
    if not c_token:
        raise RuntimeError("Could not parse recaptcha-token from anchor page HTML.")


    post_url = f"https://www.google.com/recaptcha/{recaptcha_type}/reload?k={key}"


    post_body = (
        f"v={v}"
        f"&reason=q"
        f"&c={c_token}"
        f"&k={key}"
        f"&co={co}"
        f"&hl=en"
        f"&size=invisible"
        f"&chr=%5B89%2C64%2C27%5D"
        f"&vh=14544019692"
        f"&bg={BG_DATA}"
    )

    post_headers = {
        "Host":             "www.google.com",
        "User-Agent":       "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:147.0) "
                            "Gecko/20100101 Firefox/147.0",
        "Accept":           "*/*",
        "Accept-Language":  "en-US,en;q=0.9",
        "Accept-Encoding":  "gzip, deflate, br, zstd",
        "Origin":           "https://www.google.com",
        "Alt-Used":         "www.google.com",
        "Connection":       "keep-alive",
        "Referer":          anchor_url,
        "Sec-Fetch-Dest":   "empty",
        "Sec-Fetch-Mode":   "cors",
        "Content-Type":     "application/x-www-form-urlencoded",
    }

    async with AsyncSession(impersonate="chrome124") as session:
        post_resp = await session.post(
            post_url,
            data=post_body.encode(),
            headers=post_headers,
            allow_redirects=True,
            timeout=15,
        )
        post_resp.raise_for_status()
        post_source = post_resp.text



    solution = _parse_between(post_source, '"rresp","', '"')
    if not solution:
        raise RuntimeError(
            f"Could not parse rresp from reload response.\n"
            f"Response snippet: {post_source[:300]}"
        )

    return solution




if __name__ == "__main__":
    import asyncio

    async def _test():
        print("Solving reCAPTCHA v3...")
        token = await solve_recaptcha()
        print(f"\n✅ Solution token:\n{token}")

    asyncio.run(_test())
