#!/usr/bin/python3
# @Мартин.
# ███████╗              ██╗  ██╗    ██╗  ██╗     ██████╗    ██╗  ██╗     ██╗    ██████╗
# ██╔════╝              ██║  ██║    ██║  ██║    ██╔════╝    ██║ ██╔╝    ███║    ╚════██╗
# ███████╗    █████╗    ███████║    ███████║    ██║         █████╔╝     ╚██║     █████╔╝
# ╚════██║    ╚════╝    ██╔══██║    ╚════██║    ██║         ██╔═██╗      ██║     ╚═══██╗
# ███████║              ██║  ██║         ██║    ╚██████╗    ██║  ██╗     ██║    ██████╔╝
# ╚══════╝              ╚═╝  ╚═╝         ╚═╝     ╚═════╝    ╚═╝  ╚═╝     ╚═╝    ╚═════╝

import threading
import time
from pynput import keyboard
import argparse
from lib.camptz import camPTZ  
from lib.version import VERSION
import sys

LOGO = "\033[1;32m" + r"""
                             .                                   
                          ,''`.         _                        
                     ,.,'''  '`--- ._,,'|                        
                   ,'                   /                        
              __.-'                    |                         
           ''                ___   ___ |                         
         ,'                  \(|\ /|)/ |                         
        ,'                 _     _     `._                       
       /     ,.......-\    `.      __     `-.                    
      /     ,' :  .:''`|    `:`.../:.`` ._   `._                 
  ,..,'  _/' .: :'     |     |      '.    \.    \                
 /      ,'  :'.:  / \  |     | / \   ':.  . \    \               
|      /  .: :' ,'  _)  ".._,;'  _)    :. :. \    |              
 |     | :'.:  /   |   .,   /   |       :  :  |   |              
 |     |:' :  /____|  /  \ /____|       :  :  |  ,'              
  |   /    '         /    \            :'   : |,/                
   \ |  '_          /______\              , : |                  
  _/ |  \'`--`.    _            ,_   ,-'''  :.|         __       
 /   |   \..   ` ./ `.   _,_  ,'  ``'  /'   :'|      _,''/       
/   /'. :   \.   _    [_]   `[_]  .__,,|   _....,--=/'  /:       
|   \_| :    `.-' `.    _.._     /     . ,'  :. ':/'  /'  `.     
`.   '`'`.         `. ,.'   ` .,'     :'/ ':..':.    |  .:' `.   
  \.      \          '               :' |    ''''      ''     `. 
    `''.   `|        ':     .      .:' ,|         .  ..':.      |
      /'   / '"-..._  :   .:'    _;:.,'  \.     .:'   :. ''.    |
     (._,.'        '`''''''''''''          \.._.:      ':  ':   /
                                             '`- ._    ,:__,,-' 
                                                    ``''"""+'\033[0m'+'\033[35m'+r'''
[Maptnh@S-H4CK13]      [Blood Cat PTZ '''+VERSION+r''']    [https://github.com/MartinxMax]'''+'\033[0m'

PAN_STEP = 0.25
TILT_STEP = 0.25
ZOOM_STEP = 0.25
SEND_INTERVAL = 0.12  

class PTZKeyboardController:
    def __init__(self, ptz_obj, token, ptz_path):
        self.ptz = ptz_obj
        self.token = token
        self.ptz_path = ptz_path

        self.pan_vel = 0.0
        self.tilt_vel = 0.0
        self.zoom_vel = 0.0

        self._lock = threading.Lock()
        self._running = False
        self._sender_thread = None

    def start(self):
        self._running = True
        self._sender_thread = threading.Thread(target=self._send_loop, daemon=True)
        self._sender_thread.start()

    def stop(self):
        self._running = False
        if self._sender_thread:
            self._sender_thread.join(timeout=1)

    def _send_loop(self):
        while self._running:
            with self._lock:
                pan = self.pan_vel
                tilt = self.tilt_vel
                zoom = self.zoom_vel
            try:
                self.ptz.move(pan, tilt, zoom, self.token, self.ptz_path)
            except Exception as e:
                print(f"[ptz] send error: {e}")
            time.sleep(SEND_INTERVAL)

        try:
            self.ptz.move(0.0, 0.0, 0.0, self.token, self.ptz_path)
        except Exception:
            pass

    def set_pan(self, v):
        with self._lock:
            self.pan_vel = v

    def set_tilt(self, v):
        with self._lock:
            self.tilt_vel = v

    def set_zoom(self, v):
        with self._lock:
            self.zoom_vel = v


def make_keyboard_listener(controller: PTZKeyboardController):
    pressed = set()

    def on_press(key):
        try:
            k = key.char
        except AttributeError:
            k = key

        if k in pressed:
            return
        pressed.add(k)

        if k == keyboard.Key.up:
            controller.set_tilt(TILT_STEP)
        elif k == keyboard.Key.down:
            controller.set_tilt(-TILT_STEP)
        elif k == keyboard.Key.left:
            controller.set_pan(-PAN_STEP)
        elif k == keyboard.Key.right:
            controller.set_pan(PAN_STEP)

        if isinstance(k, str):
            if k in ('+', '='):
                controller.set_zoom(ZOOM_STEP)
            elif k == '-':
                controller.set_zoom(-ZOOM_STEP)

    def on_release(key):
        try:
            k = key.char
        except AttributeError:
            k = key

        if k in pressed:
            pressed.remove(k)

        if k == keyboard.Key.up or k == keyboard.Key.down:
            controller.set_tilt(0.0)
        elif k == keyboard.Key.left or k == keyboard.Key.right:
            controller.set_pan(0.0)
        elif isinstance(k, str) and (k in ('+', '=', '-')):
            controller.set_zoom(0.0)

        if key == keyboard.Key.esc:
            return False

    return keyboard.Listener(on_press=on_press, on_release=on_release)


def main():
    print(LOGO)
    cam = camPTZ()

    parser = argparse.ArgumentParser(description='Blood Cat PTZ Camera Controller with ONVIF Scanner')
    parser.add_argument('--scan', default='', type=str, help='ONVIF port scan target IP')
    parser.add_argument('--ip', default='', type=str, help='Target IP')
    parser.add_argument('--port', default='', type=str, help='Target port')
    parser.add_argument('--username', default='', type=str, help='Username')
    parser.add_argument('--password', default='', type=str, help='Password')
    args = parser.parse_args()

    if args.scan:
        cam.scan_onvif(args.scan)
        sys.exit(0)

    if args.ip and args.port and args.username and args.password:
        token, path = cam.auth(args.ip, args.port, args.username, args.password)

        if token:
            print(f"[+] Authentication success [{token}]")

            controller = PTZKeyboardController(cam, token, path)
            controller.start()

            listener = make_keyboard_listener(controller)

            print("[+] PTZ keyboard control started. Arrow keys control pan/tilt, '+' '-' control zoom, Esc to exit.")

            try:
                listener.start()
                listener.join()
            except KeyboardInterrupt:
                pass
            finally:
                controller.stop()
                print("[-] Stopped.")
        else:
            print("[-] Authentication failed or host unreachable")
    else:
        print("[!] Missing parameters")


if __name__ == "__main__":
    main()

 