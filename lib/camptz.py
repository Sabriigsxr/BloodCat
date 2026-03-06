#!/usr/bin/python3
# @Мартин.
# ███████╗              ██╗  ██╗    ██╗  ██╗     ██████╗    ██╗  ██╗     ██╗    ██████╗
# ██╔════╝              ██║  ██║    ██║  ██║    ██╔════╝    ██║ ██╔╝    ███║    ╚════██╗
# ███████╗    █████╗    ███████║    ███████║    ██║         █████╔╝     ╚██║     █████╔╝
# ╚════██║    ╚════╝    ██╔══██║    ╚════██║    ██║         ██╔═██╗      ██║     ╚═══██╗
# ███████║              ██║  ██║         ██║    ╚██████╗    ██║  ██╗     ██║    ██████╔╝
# ╚══════╝              ╚═╝  ╚═╝         ╚═╝     ╚═════╝    ╚═╝  ╚═╝     ╚═╝    ╚═════╝
import requests
from requests.auth import HTTPDigestAuth
import xml.etree.ElementTree as ET
import time
import re
import warnings
from urllib.parse import urlparse
import concurrent.futures
import threading
warnings.filterwarnings("ignore")

class camPTZ():

    def __init__(self):
        self.__TIMEOUT = 6
        self.__HEADERS_SOAP = {
            "Content-Type": "application/soap+xml; charset=utf-8"
        }
        self.__discover = "/onvif/device_service"
        self.__auth_stat = False
        self.ONVIF = self.__load_onvif_ports()

    def __load_onvif_ports(self,file_path="TOP500_ONVIF_Port.txt"):
        ports = []

        with open(file_path, "r", encoding="utf-8") as f:
            data = f.read()
        for p in data.split(","):
            p = p.strip()
            if p.isdigit():
                ports.append(int(p))

        ports = sorted(set(ports))
        return ports

    def __check_onvif(self, ip, port, scheme, timeout=None):
        url = f"{scheme}://{ip}:{port}/onvif/device_service"
        SOAP = """<?xml version="1.0" encoding="UTF-8"?>
    <s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">
    <s:Body>
    <GetCapabilities xmlns="http://www.onvif.org/ver10/device/wsdl">
    <Category>All</Category>
    </GetCapabilities>
    </s:Body>
    </s:Envelope>
    """
        try:
            r = requests.post(
                url,
                data=SOAP,
                headers=self.__HEADERS_SOAP,
                timeout=(timeout or self.__TIMEOUT),
                verify=False
            )
            if r.status_code in (200, 401):
                text = (r.text or "").lower()
                if "onvif" in text or "ver10" in text or r.status_code == 401:
                    return True
        except requests.RequestException:
            pass
        return False


    def __check_onvif_wrapper(self, stop_event, ip, port, scheme):
    
        if stop_event.is_set():
            return False

        ok = self.__check_onvif(ip, port, scheme)

        if ok:
 
            stop_event.set()

        return ok


    def scan_onvif(self, ip, first_only=False, max_workers=16):
        targets = [(ip, port, scheme) for port in self.ONVIF for scheme in ("http", "https")]

        stop_event = threading.Event()
        results = []
        workers = min(max_workers, len(targets)) or 1

        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as exe:
      
            future_to_target = {
                exe.submit(self.__check_onvif_wrapper, stop_event, t_ip, t_port, t_scheme): (t_ip, t_port, t_scheme)
                for (t_ip, t_port, t_scheme) in targets
            }

            try:
                for fut in concurrent.futures.as_completed(future_to_target):
       
                    t_ip, t_port, t_scheme = future_to_target[fut]

                  
                    if stop_event.is_set() and first_only and results:
                        break

                    try:
                        ok = fut.result()
                    except Exception:
                        ok = False

                    if ok:
                        print(f"[+] ONVIF detected [{t_scheme}] [{t_ip}:{t_port}]")
                        results.append((t_scheme, t_ip, t_port))

                        if first_only:
 
                            for f in future_to_target:
                                if not f.done():
                                    f.cancel()
                            return results[0]
            except KeyboardInterrupt:
                stop_event.set()
                print("Scan aborted by user.")

        if not results:
            print("[-] No ONVIF found")
            if first_only:
                return False
            return []

        return results
    def __get_head(self, ip, port, path="/"):

        urls = [
            f"http://{ip}:{port}{path}",
            f"https://{ip}:{port}{path}"
        ]

        for url in urls:

            try:

                r = requests.head(url, timeout=3, verify=False)

                if r.status_code in [200, 401, 404]:

                    scheme = url.split("://")[0]

                    return scheme, r.status_code

            except:
                pass

        return None, None

    def get_profiles(self, media_xaddr, auth):

        soap = """<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">
<s:Body>
<trt:GetProfiles xmlns:trt="http://www.onvif.org/ver10/media/wsdl"/>
</s:Body>
</s:Envelope>"""

        try:

            r = requests.post(
                media_xaddr,
                data=soap,
                headers=self.__HEADERS_SOAP,
                auth=auth,
                timeout=self.__TIMEOUT,
                verify=False
            )

            tokens = re.findall(r'Profiles token="([^"]+)"', r.text)

            if not tokens:

                root = ET.fromstring(r.text.encode("utf-8"))

                for elem in root.iter():

                    tok = elem.get("token")

                    if tok:
                        tokens.append(tok)

            return tokens

        except:
            return []

    def auth(self, ip, port, username, password):

        scheme, status = self.__get_head(ip, port)

        if not scheme:
            return False

        self.__auth = HTTPDigestAuth(username, password)

        onvif_url = f"{scheme}://{ip}:{port}"

        soap = """<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">
<s:Body>
<tds:GetCapabilities xmlns:tds="http://www.onvif.org/ver10/device/wsdl">
<tds:Category>All</tds:Category>
</tds:GetCapabilities>
</s:Body>
</s:Envelope>"""

        try:

            r = requests.post(
                onvif_url + self.__discover,
                data=soap,
                headers=self.__HEADERS_SOAP,
                auth=self.__auth,
                timeout=self.__TIMEOUT,
                verify=False
            )

            if r.status_code == 401:
                return False

        except:
            return False

        try:

            root = ET.fromstring(r.text.encode("utf-8"))

            media_path = None
            ptz_path = None

            for elem in root.iter():

                tag = elem.tag.lower()

                if tag.endswith("xaddr"):

                    text = (elem.text or "").strip()

                    if text:

                        low = text.lower()

                        if "media" in low:
                            media_path = urlparse(text).path

                        if "ptz" in low:
                            ptz_path = urlparse(text).path

            if not media_path:
                return False

            tokens = self.get_profiles(
                onvif_url + media_path,
                self.__auth
            )

            if not tokens:
                return False

            token = tokens[0]

            if not ptz_path:
                return False

            self.__scheme = scheme
            self.__ip = ip
            self.__port = port
            self.__token = token
            self.__ptz_path = ptz_path

            self.__auth_stat = True

            return token, ptz_path

        except:
            return False

    def move(self, pan, tilt, zoom, token, ptz_path):

        if not self.__auth_stat:
            return False

        url = f"{self.__scheme}://{self.__ip}:{self.__port}{ptz_path}"

        soap = f"""<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">
<s:Body>
<tptz:ContinuousMove xmlns:tptz="http://www.onvif.org/ver20/ptz/wsdl">
<tptz:ProfileToken>{token}</tptz:ProfileToken>
<tptz:Velocity>
<tt:PanTilt x="{pan}" y="{tilt}" xmlns:tt="http://www.onvif.org/ver10/schema"/>
<tt:Zoom x="{zoom}" xmlns:tt="http://www.onvif.org/ver10/schema"/>
</tptz:Velocity>
</tptz:ContinuousMove>
</s:Body>
</s:Envelope>"""

        try:

            requests.post(
                url,
                data=soap,
                headers=self.__HEADERS_SOAP,
                auth=self.__auth,
                timeout=self.__TIMEOUT,
                verify=False
            )

        except:
            return False

        time.sleep(0.2)

        stop = f"""<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">
<s:Body>
<tptz:Stop xmlns:tptz="http://www.onvif.org/ver20/ptz/wsdl">
<tptz:ProfileToken>{token}</tptz:ProfileToken>
</tptz:Stop>
</s:Body>
</s:Envelope>"""

        try:

            requests.post(
                url,
                data=stop,
                headers=self.__HEADERS_SOAP,
                auth=self.__auth,
                timeout=self.__TIMEOUT,
                verify=False
            )

            return True

        except:
            return False