import socket
import time
import re
import os
import configparser
from PyQt6.QtCore import QThread, pyqtSignal


# API keyiniz buradaki kodlarla bulunur, programın TS3 ile senkron çalışabilmesi için bunlara erişebilmesi gerekmektedir. 
# bu veriler hiçbir sunucuya gönderilmediği için sadece sizin localinizde barınır. 
def get_auto_ts3_api_key() -> str:
    """Auto-detect API Key from TS3's clientquery.ini config file across standard paths."""
    candidate_paths = [
        os.path.expandvars(r'%APPDATA%\TS3Client\clientquery.ini'),
        os.path.expandvars(r'%LOCALAPPDATA%\TS3Client\clientquery.ini'),
        r'C:\Program Files\TeamSpeak 3 Client\config\clientquery.ini',
        r'C:\Program Files (x86)\TeamSpeak 3 Client\config\clientquery.ini',
    ]

    # Search in APPDATA TS3Client subdirectories if any
    appdata_ts3 = os.path.expandvars(r'%APPDATA%\TS3Client')
    if os.path.isdir(appdata_ts3):
        for root, _, files in os.walk(appdata_ts3):
            for f in files:
                if f.lower() == 'clientquery.ini':
                    candidate_paths.append(os.path.join(root, f))

    for path in candidate_paths:
        if os.path.isfile(path):
            try:
                # 1. Try ConfigParser
                cfg = configparser.ConfigParser(strict=False)
                cfg.read(path, encoding='utf-8', errors='ignore')
                for sec in cfg.sections():
                    for k in cfg[sec]:
                        if k.lower() in ['api_key', 'apikey', 'key']:
                            val = cfg[sec][k].strip()
                            if val:
                                return val
            except Exception:
                pass

            try:
                # 2. Try raw line scan (in case INI section headers are missing or non-standard)
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        line_str = line.strip()
                        m = re.search(r'api_?key\s*=\s*(.+)', line_str, re.IGNORECASE)
                        if m:
                            key_val = m.group(1).strip()
                            if key_val:
                                return key_val
            except Exception as e:
                print(f"[TS3Client] Error reading {path}: {e}")

    return ""

def unescape_ts3(text: str) -> str:
    """Unescape TS3 ClientQuery response strings."""
    if not text:
        return ""
    replacements = [
        (r'\s', ' '),
        (r'\/', '/'),
        (r'\p', '|'),
        (r'\a', '\a'),
        (r'\b', '\b'),
        (r'\f', '\f'),
        (r'\n', '\n'),
        (r'\r', '\r'),
        (r'\t', '\t'),
        (r'\v', '\v'),
        (r'\\\\', '\\')
    ]
    res = text
    for old, new in replacements:
        res = res.replace(old, new)
    return res.strip()

def parse_ts3_item(item_str: str) -> dict:
    """Parse a single TS3 key=value space/newline-separated item."""
    data = {}
    tokens = re.split(r'\s+', item_str.strip())
    for token in tokens:
        if not token:
            continue
        if '=' in token:
            k, v = token.split('=', 1)
            data[k] = unescape_ts3(v)
        else:
            data[token] = True
    return data

def parse_ts3_list(line: str) -> list:
    """Parse TS3 pipe-separated (|) list response."""
    items = line.strip().split('|')
    return [parse_ts3_item(item) for item in items if item.strip()]

def check_is_whispering(item: dict) -> bool:
    """Check if TS3 item dictionary indicates whisper talking."""
    val_status = str(item.get("status", "0")).strip()
    if val_status == "0":
        return False
    val_recv = str(item.get("isreceivedwhisper", item.get("is_received_whisper", "0"))).strip()
    val_talk = str(item.get("client_flag_talking", "0")).strip()
    return val_status == "2" or val_recv in ["1", "true"] or val_talk == "2"


class TS3ClientThread(QThread):
    connected_signal = pyqtSignal(bool, str)
    channel_updated_signal = pyqtSignal(str)
    users_updated_signal = pyqtSignal(list)
    message_received_signal = pyqtSignal(str, str)
    whisper_state_signal = pyqtSignal(bool)

    DEMO_CHANNEL = "Lobby (Demo)"
    DEMO_USERS = [
        {"clid": 1, "nickname": "J. Doe (gecmisolsun)", "is_talking": False, "is_whispering": False, "is_mic_muted": True, "is_output_muted": False, "is_channel_commander": True, "in_current_channel": True},
        {"clid": 2, "nickname": "A. Doe (gecmisolmasin)", "is_talking": True, "is_whispering": True, "is_mic_muted": False, "is_output_muted": True, "is_channel_commander": True, "in_current_channel": True},
        {"clid": 3, "nickname": "Dış Kanal > J. Doe (gecmisolsun)", "is_talking": True, "is_whispering": True, "is_mic_muted": False, "is_output_muted": False, "is_channel_commander": False, "in_current_channel": False}
    ]

    def __init__(self, config_manager):
        super().__init__()
        self.config = config_manager
        self.running = True
        self.socket = None
        self.current_cid = None
        self.current_channel_name = "Lobby"
        self.current_schandlerid = 1
        self.my_clid = None
        self.demo_msg_sent = False
        self._is_polling = False
        self.client_talk_states = {}
        self.last_channel_users_cache = []
        self.channel_names_cache = {}
        self.current_channel_client_nicks = {}

    def stop(self):
        self.running = False
        self.close_socket()

    def close_socket(self):
        if self.socket:
            try:
                self.socket.close()
            except Exception:
                pass
            self.socket = None

    def _register_events(self, sch_id=1):
        self._send_cmd(f"clientnotifyregister schandlerid={sch_id} event=any")
        self._send_cmd(f"clientnotifyregister schandlerid={sch_id} event=talkstatuschange")
        self._send_cmd(f"clientnotifyregister schandlerid={sch_id} event=channel")
        self._send_cmd(f"clientnotifyregister schandlerid={sch_id} event=textchannel")
        self._send_cmd(f"clientnotifyregister schandlerid={sch_id} event=textprivate")
        self._send_cmd(f"clientnotifyregister schandlerid={sch_id} event=textserver")

    def _find_and_select_active_schandler(self) -> bool:
        """Find an active server connection handler and select it via use schandlerid=N."""
        res = self._send_cmd("whoami")
        if "error id=1798" in res or "not authenticated" in res:
            return False

        if "cid=" in res:
            cid_match = re.search(r'cid=(\d+)', res)
            if cid_match and cid_match.group(1) != "0":
                return True

        # Query schandlerlist for active connections
        sch_res = self._send_cmd("schandlerlist")
        if sch_res:
            handlers = parse_ts3_list(sch_res)
            for h in handlers:
                sch_id = h.get("clschandlerid")
                if sch_id:
                    self._send_cmd(f"use schandlerid={sch_id}")
                    test_who = self._send_cmd("whoami")
                    if "cid=" in test_who:
                        cid_m = re.search(r'cid=(\d+)', test_who)
                        if cid_m and cid_m.group(1) != "0":
                            self.current_schandlerid = sch_id
                            self._register_events(sch_id)
                            return True
        return False

    def run(self):
        while self.running:
            demo_mode = self.config.get("demo_mode", False)
            if demo_mode:
                self.connected_signal.emit(True, "Demo Modu Aktif")
                self.channel_updated_signal.emit(self.DEMO_CHANNEL)
                self.users_updated_signal.emit(self.DEMO_USERS)
                self.whisper_state_signal.emit(True)
                if not self.demo_msg_sent:
                    self.message_received_signal.emit("J. Doe (gecmisolmasin) > Lobby", "Selamlar, oyun içi chat mesajı testi!")
                    self.demo_msg_sent = True
                time.sleep(1.0)
                continue
            else:
                self.demo_msg_sent = False

            host = self.config.get("host", "127.0.0.1")
            port = int(self.config.get("port", 25639))

            try:
                self.connected_signal.emit(False, "TS3 Bağlanıyor...")
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket.settimeout(0.5)
                self.socket.connect((host, port))

                # Read initial welcome header
                time.sleep(0.1)
                self._recv_all(timeout=0.3)

                # Get API Key (from config or auto-detect)
                api_key = self.config.get("api_key", "").strip()
                if not api_key:
                    api_key = get_auto_ts3_api_key()

                if api_key:
                    res = self._send_cmd(f"auth apikey={api_key}")
                    if "error id=0" not in res:
                        print(f"[TS3Client] Auth error: {res}")
                        self.connected_signal.emit(False, "API Key Hatalı!")
                        self.channel_updated_signal.emit("API Key Hatalı")
                        self.close_socket()
                        time.sleep(3.0)
                        continue

                # Select schandlerid
                use_res = self._send_cmd("use schandlerid=1")
                if "error id=1798" in use_res or "not authenticated" in use_res:
                    print("[TS3Client] Authentication required by TS3 ClientQuery!")
                    self.connected_signal.emit(False, "API Key Gerekli!")
                    self.channel_updated_signal.emit("API Key Gerekli")
                    self.close_socket()
                    time.sleep(3.0)
                    continue

                self._find_and_select_active_schandler()
                self._register_events(self.current_schandlerid)

                self.connected_signal.emit(True, "Aktif")

                last_poll = 0

                while self.running and not self.config.get("demo_mode", False):
                    now = time.time()
                    if now - last_poll >= 1.0:
                        self._poll_ts3_state()
                        last_poll = now

                    # Read incoming async lines
                    line = self._recv_all(timeout=0.2)
                    if line:
                        self._handle_raw_buffer(line)

            except Exception as e:
                print(f"[TS3Client] Connection exception: {e}")
                self.connected_signal.emit(False, f"TS3 Bağlantı Hatası: {e}")
                self.close_socket()
                time.sleep(2.0)

    def _handle_raw_buffer(self, buffer: str) -> str:
        """Extract and process all notify lines from raw socket buffer, returning remaining command responses."""
        cmd_lines = []
        for line in buffer.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("notify"):
                self._handle_notification(line)
            else:
                cmd_lines.append(line)
        return "\n".join(cmd_lines)

    def _recv_all(self, timeout=0.3) -> str:
        if not self.socket:
            return ""
        self.socket.settimeout(timeout)
        data = ""
        try:
            while True:
                chunk = self.socket.recv(4096).decode('utf-8', errors='ignore')
                if not chunk:
                    break
                data += chunk
                if len(chunk) < 4096:
                    break
        except Exception:
            pass
        return data

    def _send_cmd(self, cmd: str) -> str:
        if not self.socket:
            return ""
        try:
            self.socket.sendall((cmd + "\n").encode('utf-8'))
            response = ""
            start = time.time()
            while time.time() - start < 1.0:
                try:
                    self.socket.settimeout(0.3)
                    chunk = self.socket.recv(4096).decode('utf-8', errors='ignore')
                    if not chunk:
                        break
                    # Instantly process any notify lines inside chunk
                    cleaned_chunk = self._handle_raw_buffer(chunk)
                    response += cleaned_chunk
                    if "error id=" in response:
                        break
                except Exception:
                    break
            return response
        except Exception as e:
            print(f"[TS3Client] send_cmd error: {e}")
            return ""

    def _poll_ts3_state(self):
        """Poll current client status (whoami, channel name, client list with mic/headphone/whisper/channel commander flags)."""
        if self._is_polling:
            return
        self._is_polling = True
        try:
            whoami_res = self._send_cmd("whoami")
            if not whoami_res:
                return

            if "error id=1798" in whoami_res or "not authenticated" in whoami_res:
                self.connected_signal.emit(False, "API Key Gerekli!")
                self.channel_updated_signal.emit("API Key Girin")
                self.users_updated_signal.emit([])
                self.whisper_state_signal.emit(False)
                return

            cid_match = re.search(r'cid=(\d+)', whoami_res)
            clid_match = re.search(r'clid=(\d+)', whoami_res)

            if not cid_match or cid_match.group(1) == "0":
                if self._find_and_select_active_schandler():
                    whoami_res = self._send_cmd("whoami")
                    cid_match = re.search(r'cid=(\d+)', whoami_res)
                    clid_match = re.search(r'clid=(\d+)', whoami_res)

            if not cid_match or cid_match.group(1) == "0":
                self.channel_updated_signal.emit("Sunucuya Bağlı Değil")
                self.users_updated_signal.emit([])
                self.whisper_state_signal.emit(False)
                return

            cid = cid_match.group(1)
            self.my_clid = clid_match.group(1) if clid_match else None
            self.current_cid = cid

            # Get Channel Names dynamically from channellist and cache them
            chan_res = self._send_cmd("channellist")
            chan_name = "Kanal"
            if chan_res:
                chan_lines = [l.strip() for l in chan_res.splitlines() if "channel_name=" in l]
                if chan_lines:
                    channels = parse_ts3_list(chan_lines[0])
                    for ch in channels:
                        ch_cid = str(ch.get("cid", "")).strip()
                        ch_n = ch.get("channel_name", "Kanal")
                        self.channel_names_cache[ch_cid] = ch_n
                        if ch_cid == str(cid).strip():
                            chan_name = ch_n

            self.current_channel_name = chan_name
            self.channel_updated_signal.emit(chan_name)

            # Get Clients across all channels using -uid -voice -away
            client_res = self._send_cmd("clientlist -uid -voice -away")
            if not client_res:
                return

            client_lines = [l.strip() for l in client_res.splitlines() if "clid=" in l]
            if not client_lines:
                return

            clients_raw = parse_ts3_list(client_lines[0])
            channel_users = []
            new_channel_client_nicks = {}
            any_i_whispering = False

            for c in clients_raw:
                c_cid = str(c.get("cid", "")).strip()
                c_type = str(c.get("client_type", "0")).strip()
                if c_type == "1":
                    continue

                nick = c.get("client_nickname", "")
                if not nick:
                    continue

                clid_str = str(c.get("clid", "")).strip()
                live_talk = self.client_talk_states.get(clid_str, {})
                flag_talk = str(c.get("client_flag_talking", "0")).strip()

                is_talking = live_talk.get("is_talking", flag_talk in ["1", "2"])
                is_whispering = live_talk.get("is_whispering", check_is_whispering(c)) if is_talking else False

                if clid_str == str(self.my_clid).strip() and is_whispering:
                    any_i_whispering = True

                is_mic_muted = (str(c.get("client_input_muted", "0")).strip() == "1" or
                                str(c.get("client_input_hardware", "1")).strip() == "0")
                is_output_muted = (str(c.get("client_output_muted", "0")).strip() == "1" or
                                   str(c.get("client_output_hardware", "1")).strip() == "0")
                is_channel_commander = str(c.get("client_is_channel_commander", "0")).strip() == "1"

                # 1. Include users in current channel
                if c_cid == cid:
                    new_channel_client_nicks[clid_str] = nick
                    channel_users.append({
                        "clid": c.get("clid"),
                        "nickname": nick,
                        "is_talking": is_talking,
                        "is_whispering": is_whispering,
                        "is_mic_muted": is_mic_muted,
                        "is_output_muted": is_output_muted,
                        "is_channel_commander": is_channel_commander,
                        "in_current_channel": True
                    })
                # 2. Include users in OTHER channels who are actively whispering to us
                elif is_whispering:
                    channel_users.append({
                        "clid": c.get("clid"),
                        "nickname": f"{nick}",
                        "is_talking": True,
                        "is_whispering": True,
                        "is_mic_muted": False,
                        "is_output_muted": False,
                        "is_channel_commander": is_channel_commander,
                        "in_current_channel": False
                    })

            self.current_channel_client_nicks = new_channel_client_nicks
            self.last_channel_users_cache = channel_users
            self.whisper_state_signal.emit(any_i_whispering)
            if channel_users:
                self.users_updated_signal.emit(channel_users)
        finally:
            self._is_polling = False

    def _handle_notification(self, line: str):
        """Process real-time notify events from TS3 ClientQuery."""
        if line.startswith("notifytextmessage"):
            item = parse_ts3_item(line)
            sender = item.get("invokername", "TS3")
            msg = item.get("msg", "")
            targetmode = str(item.get("targetmode", "2")).strip()

            if targetmode == "1":
                scope = "ÖM"
            elif targetmode == "3":
                scope = "Sunucu"
            else:
                scope = self.current_channel_name if self.current_channel_name else "Kanal"

            sender_scope = f"{sender} > {scope}"

            if msg:
                print(f"[TS3Client] Chat message received: {sender_scope}: {msg}")
                self.message_received_signal.emit(sender_scope, msg)

        elif line.startswith("notifytalkstatuschange"):
            item = parse_ts3_item(line)
            status = str(item.get("status", "0")).strip()
            clid = str(item.get("clid", "")).strip()

            is_talking = status in ["1", "2"]
            is_whispering = check_is_whispering(item) if is_talking else False

            self.client_talk_states[clid] = {
                "is_talking": is_talking,
                "is_whispering": is_whispering
            }

            # Real-time instant update of cached user list
            if self.last_channel_users_cache:
                updated_users = []
                any_i_whisp = False
                found_in_cache = False

                for u in self.last_channel_users_cache:
                    u_clid = str(u.get("clid", "")).strip()
                    if u_clid == clid:
                        found_in_cache = True
                        # If user is in another channel and stopped whispering, omit them
                        if not u.get("in_current_channel", True) and not is_whispering:
                            continue
                        u_copy = dict(u)
                        u_copy["is_talking"] = is_talking
                        u_copy["is_whispering"] = is_whispering
                        updated_users.append(u_copy)
                    else:
                        updated_users.append(u)

                    current_whisp = (is_whispering if u_clid == clid else u.get("is_whispering", False))
                    if u_clid == str(self.my_clid).strip() and current_whisp:
                        any_i_whisp = True

                # If whispering user is from another channel and not in cache, poll state immediately
                if not found_in_cache and is_whispering:
                    if not self._is_polling:
                        self._poll_ts3_state()
                    return

                self.last_channel_users_cache = updated_users
                self.users_updated_signal.emit(updated_users)
                if clid == str(self.my_clid).strip():
                    self.whisper_state_signal.emit(any_i_whisp)

        elif line.startswith("notifyclientmoved"):
            item = parse_ts3_item(line)
            clid = str(item.get("clid", "")).strip()
            ctid = str(item.get("ctid", "")).strip()

            # If user was in our channel and moved to another channel
            if clid in self.current_channel_client_nicks and ctid != str(self.current_cid).strip():
                nick = self.current_channel_client_nicks.pop(clid, None)
                if nick:
                    target_chan = self.channel_names_cache.get(ctid, "Kanal")
                    move_msg = f"{nick} > {target_chan}"
                    print(f"[TS3Client] Client moved channel: {move_msg}")
                    self.message_received_signal.emit(move_msg, "")

            if not self._is_polling:
                self._poll_ts3_state()

        elif any(line.startswith(ev) for ev in [
            "notifycliententerview", "notifyclientleftview",
            "notifyclientpropertieschanged"
        ]):
            if not self._is_polling:
                self._poll_ts3_state()
