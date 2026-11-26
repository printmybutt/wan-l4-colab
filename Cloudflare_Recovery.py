# Cloudflare recovery cell: only restarts this notebook's tunnel, never the model server.
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time
import urllib.request
import urllib.error

CF_SHA256 = '56f13335143ec0e22772963290683a84a04114a35ec64cbc794a4d39ff9bb8cf'
CF_BINARY_URL = 'https://github.com/cloudflare/cloudflared/releases/download/2026.11.2/cloudflared-linux-amd64'

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward credentials to a redirected host.

def probe_health(url, auth=None, timeout=5):
    headers = {'Accept': 'application/json', 'User-Agent': 'Wan-L4-healthcheck/2'}
    if auth:
        headers['Authorization'] = 'Basic ' + base64.b64encode(
            (auth[0] + ':' + auth[1]).encode()).decode()
    request = urllib.request.Request(url.rstrip('/') + '/health', headers=headers)
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=timeout) as response:
            code, body = response.status, response.read(4096)
            challenge = response.headers.get('WWW-Authenticate', '')
    except urllib.error.HTTPError as error:
        code, body = error.code, error.read(4096)
        challenge = error.headers.get('WWW-Authenticate', '')
    except (OSError, urllib.error.URLError) as error:
        return {'code': None, 'ok': False, 'app401': False,
                'detail': type(error).__name__ + ': ' + str(error)}
    try:
        data = json.loads(body)
    except (ValueError, UnicodeError):
        data = {}
    return {'code': code, 'ok': code == 200 and isinstance(data, dict) and data.get('ok') is True,
        'app401': code == 401 and 'Basic' in challenge and isinstance(data, dict)
                  and data.get('detail') == 'Authentication required',
        'detail': 'HTTP ' + str(code)}

def classify_probes(anonymous, authenticated):
    if anonymous['code'] is not None and 200 <= anonymous['code'] < 300:
        return 'unsafe', '匿名请求意外成功，不能公开该服务'
    if anonymous['app401'] and authenticated['ok']:
        return 'ready', '匿名 401 / 带密码 200，且健康响应内容正确'
    if anonymous['app401'] and authenticated['code'] == 401:
        return 'auth', '已到达应用，但带密码请求仍为 401：重跑第 9 节以同步服务密码与 WEB_AUTH'
    return 'retry', '匿名=' + anonymous['detail'] + '；带密码=' + authenticated['detail']

def stop_tunnel(proc):
    if proc is not None and proc.poll() is None:
        os.killpg(proc.pid, signal.SIGTERM)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()

def recover_tunnel(base, auth, old_tunnel=None, seconds_per_protocol=120):
    base = Path(base)
    if not auth or len(auth) != 2:
        raise RuntimeError('找不到 WEB_AUTH，请先运行第 9 节启动带密码服务')
    # Validate the origin before creating any public exposure.
    local_anonymous = probe_health('http://127.0.0.1:8000')
    local_authenticated = probe_health('http://127.0.0.1:8000', auth)
    status, detail = classify_probes(local_anonymous, local_authenticated)
    print('本地自检：', detail, flush=True)
    if status != 'ready':
        raise RuntimeError('本地服务未通过检查；先处理第 9 节。' + detail)
    binary = base / 'cloudflared'
    if not binary.exists() or hashlib.sha256(binary.read_bytes()).hexdigest() != CF_SHA256:
        temp = binary.with_suffix('.download')
        urllib.request.urlretrieve(CF_BINARY_URL, temp)
        if hashlib.sha256(temp.read_bytes()).hexdigest() != CF_SHA256:
            temp.unlink()
            raise RuntimeError('cloudflared SHA256 不匹配')
        temp.replace(binary)
    binary.chmod(0o700)
    if any((Path.home()/'.cloudflared'/name).exists() for name in ('config.yml', 'config.yaml')):
        raise RuntimeError('存在 cloudflared 配置，请在干净运行时处理，避免使用已有隧道配置')
    stop_tunnel(old_tunnel)
    last_detail = '没有获取到临时地址'
    # Preserve auto (QUIC with built-in fallback); HTTP/2 is a second diagnostic attempt.
    for protocol in ('auto', 'http2'):
        log_path = base / ('tunnel_' + protocol + '.log')
        print('启动 Cloudflare，协议=' + protocol + '；日志=' + str(log_path), flush=True)
        command = [str(binary), 'tunnel', '--no-autoupdate', '--protocol', protocol,
            '--url', 'http://127.0.0.1:8000']
        with log_path.open('w') as log:
            proc = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                    start_new_session=True)
        success = False
        url, previous_detail = None, None
        deadline = time.monotonic() + seconds_per_protocol
        try:
            while time.monotonic() < deadline:
                if proc.poll() is not None:
                    last_detail = 'cloudflared 已退出，exit=' + str(proc.returncode)
                    break
                log_text = log_path.read_text(errors='replace')
                match = re.search(r'https://[a-z0-9-]+\.trycloudflare\.com', log_text)
                if match:
                    url = match.group(0)
                    # A printed URL is not proof that the tunnel is connected.
                    anonymous = probe_health(url)
                    authenticated = probe_health(url, auth)
                    status, last_detail = classify_probes(anonymous, authenticated)
                    if status == 'ready':
                        success = True
                        print('公网自检通过：' + last_detail, flush=True)
                        return proc, url
                    if status in ('unsafe', 'auth'):
                        raise RuntimeError(last_detail)
                    if last_detail != previous_detail:
                        print('等待隧道/DNS就绪：' + last_detail, flush=True)
                        previous_detail = last_detail
                time.sleep(2)
            print('本次未就绪：' + last_detail, flush=True)
            # Keep full logs local; users can share the relevant error lines without credentials.
            print('请查看日志最后约 30 行：' + str(log_path), flush=True)
        finally:
            if not success:
                stop_tunnel(proc)
    raise RuntimeError('公网未就绪：' + last_detail +
        '。已停止失败隧道，本地服务和模型结果仍保留；查看 tunnel_http2.log / tunnel_auto.log。')

if globals().get('ENABLE_PUBLIC', False):
    # Clear stale URL even when recovery raises. Do not print WEB_AUTH.
    PUBLIC_URL = None
    _old_tunnel = globals().get('TUNNEL')
    TUNNEL = None
    TUNNEL, PUBLIC_URL = recover_tunnel(BASE, globals().get('WEB_AUTH'), _old_tunnel)
    print('页面地址：', PUBLIC_URL)
    print('用户名 owner；使用第 9 节设置的密码。')
else:
    print('公网隧道未启用。需要使用时设置 ENABLE_PUBLIC=True。')
