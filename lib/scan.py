#!/usr/bin/python3
# @Мартин.
# ███████╗              ██╗  ██╗    ██╗  ██╗     ██████╗    ██╗  ██╗     ██╗    ██████╗
# ██╔════╝              ██║  ██║    ██║  ██║    ██╔════╝    ██║ ██╔╝    ███║    ╚════██╗
# ███████╗    █████╗    ███████║    ███████║    ██║         █████╔╝     ╚██║     █████╔╝
# ╚════██║    ╚════╝    ██╔══██║    ╚════██║    ██║         ██╔═██╗      ██║     ╚═══██╗
# ███████║              ██║  ██║         ██║    ╚██████╗    ██║  ██╗     ██║    ██████╔╝
# ╚══════╝              ╚═╝  ╚═╝         ╚═╝     ╚═════╝    ╚═╝  ╚═╝     ╚═╝    ╚═════╝

import requests
import socket
import struct
import time
import os
import threading
import concurrent.futures
from lib.camlib import * 
log = LogCat()
requests.packages.urllib3.disable_warnings()

class scan:

    def __init__(self):

        self.TIMEOUT = 4

        self.ONVIF_PORTS = self.load_ports("./TOP500_ONVIF_Port.txt")
        self.RTSP_PORTS = self.load_ports("./TOP1000_RTSP_Port.txt")
        self.RTMP_PORTS = self.load_ports("./TOP10_RTMP_Port.txt")
        
        self.soap_headers = {
            "Content-Type": "application/soap+xml; charset=utf-8"
        }

    def load_ports(self,file):

        ports = []

        with open(file,"r") as f:
            data = f.read()

        for p in data.split(","):

            p = p.strip()

            if p.isdigit():
                ports.append(int(p))

        return list(set(ports))

 
    def check_onvif(self,ip,port):

        soap = """<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">
<s:Body>
<GetCapabilities xmlns="http://www.onvif.org/ver10/device/wsdl">
<Category>All</Category>
</GetCapabilities>
</s:Body>
</s:Envelope>
"""

        for scheme in ["http","https"]:

            url = f"{scheme}://{ip}:{port}/onvif/device_service"

            try:

                r = requests.post(
                    url,
                    data=soap,
                    headers=self.soap_headers,
                    timeout=self.TIMEOUT,
                    verify=False
                )

                text = (r.text or "").lower()

                if "onvif" in text or "ver10" in text or r.status_code == 401:
                    log.success(f"[\033[31mONVIF\033[0m] {ip}:{port}")
                    return True

            except:
                pass

        return False

 
    def check_rtsp(self,ip,port):

        try:

            s = socket.socket()
            s.settimeout(self.TIMEOUT)
            s.connect((ip,port))

            req = f"OPTIONS rtsp://{ip}:{port}/ RTSP/1.0\r\nCSeq: 1\r\n\r\n"

            s.send(req.encode())

            data = s.recv(1024).decode(errors="ignore")

            if "RTSP/1.0" in data:
                log.success(f"[\033[31mRTSP\033[0m] {ip}:{port}")
                return True

        except:
            pass

        finally:
            try:
                s.close()
            except:
                pass

        return False

 
    def check_rtmp(self,ip,port):
        try:
            s = socket.socket()
            s.settimeout(self.TIMEOUT)
            s.connect((ip,port))

            c0 = b"\x03"

            c1 = struct.pack(">I",int(time.time())) + b"\x00\x00\x00\x00" + os.urandom(1528)

            s.send(c0 + c1)

            data = s.recv(1537)

            if data and data[0] == 3:
                log.success(f"[\033[31mRTMP\033[0m] {ip}:{port}")
                return True

        except:
            pass

        finally:
            try:
                s.close()
            except:
                pass

        return False
 

    def run(self, ip, type_='all'):
   
        log.info("Enabling scanning module...")
        tasks = {}

        result = {
            "onvif_port": [],
            "rtsp_port": [],
            "rtmp_port": []
        }

        with concurrent.futures.ThreadPoolExecutor(max_workers=120) as exe:

            if type_ in ('all', 'onvif'):
                for port in self.ONVIF_PORTS:
                    future = exe.submit(self.check_onvif, ip, port)
                    tasks[future] = ("onvif", port)

            if type_ in ('all', 'rtsp'):
                for port in self.RTSP_PORTS:
                    future = exe.submit(self.check_rtsp, ip, port)
                    tasks[future] = ("rtsp", port)

            if type_ in ('all', 'rtmp'):
                for port in self.RTMP_PORTS:
                    future = exe.submit(self.check_rtmp, ip, port)
                    tasks[future] = ("rtmp", port)

            for future in concurrent.futures.as_completed(tasks):

                proto, port = tasks[future]

                try:
                    ok = future.result()
                except:
                    ok = False

                if ok:

                    if proto == "onvif":
                        result["onvif_port"].append(port)

                    elif proto == "rtsp":
                        result["rtsp_port"].append(port)

                    elif proto == "rtmp":
                        result["rtmp_port"].append(port)

        log.info("Scan complete...")
        if type_ == "all":
            return result

        if type_ == "onvif":
            return {"onvif_port": result["onvif_port"]}

        if type_ == "rtsp":
            return {"rtsp_port": result["rtsp_port"]}

        if type_ == "rtmp":
            return {"rtmp_port": result["rtmp_port"]}