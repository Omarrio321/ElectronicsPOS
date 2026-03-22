"""
server.py — Waitress + Zeroconf/mDNS production server for ElectroPOS
======================================================================
Binds to 0.0.0.0:<PORT> (default 5000) and announces
http://originalelectronics.local:<PORT> via mDNS so all LAN devices
can reach the app without editing their hosts file.

For public HTTPS access, run cloudflared alongside this server:
    cloudflared tunnel --url http://localhost:5000

Usage:
    python server.py                # HTTP, port 5000
    PORT=9000 python server.py      # custom port

Start shortcut:
    start_server.bat
"""

import os
import sys
import socket
import signal
import logging
import threading
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler

# Load .env BEFORE importing the app so DATABASE_URL / SECRET_KEY are set
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

from waitress import create_server as _waitress_create_server
from app import create_app
from config import config

# ── Logging ────────────────────────────────────────────────────────────────────
os.makedirs('logs', exist_ok=True)

_fmt = logging.Formatter('[%(asctime)s] %(levelname)-8s  %(message)s',
                         datefmt='%Y-%m-%d %H:%M:%S')

_fh = RotatingFileHandler('logs/server.log', maxBytes=5*1024*1024,
                          backupCount=3, encoding='utf-8')
_fh.setFormatter(_fmt)
_fh.setLevel(logging.INFO)

_ch = logging.StreamHandler(sys.stdout)
_ch.setFormatter(_fmt)
_ch.setLevel(logging.INFO)

logger = logging.getLogger('electropos.server')
logger.setLevel(logging.INFO)
logger.addHandler(_fh)
logger.addHandler(_ch)

# ── Global state (accessed by admin.py shutdown endpoint via __main__) ─────────
_server_instance   = None
_zc_instance       = None   # zeroconf.Zeroconf
_zc_info           = None   # zeroconf.ServiceInfo
shutdown_event     = threading.Event()


# ── Network helpers ────────────────────────────────────────────────────────────
def _score_interface(ip: str) -> int:
    """Score an interface IP — higher = more likely to be a real physical adapter.

    XAMPP, VirtualBox, and VMware virtual adapters get very low scores so they
    are never chosen over a real WiFi/Ethernet or hotspot interface.
    """
    parts = ip.split('.')
    if len(parts) != 4:
        return 0
    a, b, c, d = parts[0], parts[1], parts[2], parts[3]

    if a == '192' and b == '168':
        if c == '56':   return 5   # VirtualBox host-only
        if d == '1':    return 10  # virtual adapter host end (VMware etc.)
        return 100                 # real WiFi / Ethernet (highest priority)

    if a == '172':
        if b == '20' and c == '10':
            return 70              # iPhone/Android mobile hotspot
        if 16 <= int(b) <= 31:
            return 60              # other RFC-1918 /12 range
        return 30

    if a == '10':
        if b == '5':    return 5   # XAMPP virtual (skip)
        return 40                  # other 10.x.x.x (corporate VPN etc.)

    return 20


def _get_local_ip() -> str:
    """Auto-detect the real LAN IP at startup — fully dynamic, no hardcoding."""
    import subprocess
    routes = []
    try:
        flags = 0x08000000 if sys.platform == 'win32' else 0  # CREATE_NO_WINDOW
        result = subprocess.run(
            ['route', 'print', '0.0.0.0'],
            capture_output=True, text=True, timeout=5,
            creationflags=flags,
        )
        for line in result.stdout.splitlines():
            parts = line.split()
            if (len(parts) >= 5
                    and parts[0] == '0.0.0.0'
                    and parts[1] == '0.0.0.0'
                    and parts[2] not in ('0.0.0.0', 'Gateway')):
                try:
                    iface_ip = parts[3]
                    metric   = int(parts[4])
                    score    = _score_interface(iface_ip)
                    routes.append((score, metric, iface_ip))
                except (ValueError, IndexError):
                    pass
    except Exception:
        pass

    if routes:
        routes.sort(key=lambda r: (-r[0], r[1]))
        best_ip = routes[0][2]
        if best_ip and not best_ip.startswith('127.'):
            return best_ip

    # Fallback: outbound UDP trick (last resort)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        return s.getsockname()[0]
    except OSError:
        return '127.0.0.1'
    finally:
        s.close()


# ── mDNS / Zeroconf ────────────────────────────────────────────────────────────
def _start_zeroconf(port: int) -> None:
    """Register originalelectronics.local on the LAN via mDNS."""
    global _zc_instance, _zc_info
    try:
        from zeroconf import ServiceInfo, Zeroconf

        local_ip = _get_local_ip()

        _zc_instance = Zeroconf()
        _zc_info = ServiceInfo(
            type_='_http._tcp.local.',
            name='OriginalElectronics._http._tcp.local.',
            addresses=[socket.inet_aton(local_ip)],
            port=port,
            properties={'path': '/'},
            server='originalelectronics.local.',
        )
        _zc_instance.register_service(_zc_info)
        logger.info(f'mDNS: originalelectronics.local -> http://{local_ip}:{port}  (LAN-wide)')
    except Exception as exc:
        logger.warning(f'mDNS registration skipped: {exc}')


def _stop_zeroconf() -> None:
    """Unregister mDNS service and close Zeroconf cleanly."""
    global _zc_instance, _zc_info
    if _zc_instance is None:
        return
    try:
        if _zc_info is not None:
            _zc_instance.unregister_service(_zc_info)
        _zc_instance.close()
        logger.info('mDNS: service unregistered.')
    except Exception as exc:
        logger.warning(f'mDNS cleanup error (non-fatal): {exc}')
    finally:
        _zc_instance = None
        _zc_info = None


# ── Public shutdown hook (called by admin.py via sys.modules["__main__"]) ──────
def request_shutdown() -> None:
    """Signal the shutdown monitor to stop Waitress gracefully."""
    shutdown_event.set()


# ── Shutdown monitor thread ────────────────────────────────────────────────────
def _shutdown_monitor() -> None:
    """Blocks on shutdown_event; when set, tears down mDNS then Waitress."""
    shutdown_event.wait()
    logger.info('Shutdown event received — unregistering mDNS…')
    _stop_zeroconf()
    logger.info('Closing Waitress…')
    if _server_instance is not None:
        try:
            _server_instance.close()
        except Exception:
            pass
    logger.info('Server stopped. Goodbye.')
    time.sleep(0.4)
    os._exit(0)


# ── OS signal handlers ─────────────────────────────────────────────────────────
def _handle_signal(signum, frame):
    name = {signal.SIGTERM: 'SIGTERM', signal.SIGINT: 'SIGINT'}.get(signum, str(signum))
    logger.info(f'Received {name} — requesting graceful shutdown…')
    shutdown_event.set()


signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT,  _handle_signal)


# ── Startup banner ─────────────────────────────────────────────────────────────
def _print_banner(local_ip: str, bind_host: str, bind_port: int) -> None:
    started = datetime.now().strftime('%Y-%m-%d  %H:%M:%S')
    w   = 72
    bar = '═' * w

    print(f'\n{bar}')
    print(f'  ElectroPOS — Production Server (Waitress + mDNS)')
    print(bar)
    print(f'  Server   : Waitress  |  8 threads')
    print(f'  Local    : http://127.0.0.1:{bind_port}')
    print(f'  Network  : http://{local_ip}:{bind_port}')
    print(f'  mDNS     : http://originalelectronics.local:{bind_port}')
    print(f'  Started  : {started}')
    print(bar)
    print('  For HTTPS on mobile: run  cloudflared tunnel --url http://localhost:5000')
    print('  Ctrl+C  or  Admin > Settings > Shutdown Server  to stop.')
    print(f'{bar}\n')


# ── Entry point ────────────────────────────────────────────────────────────────
def main() -> None:
    global _server_instance

    config_name = os.environ.get('FLASK_ENV', 'development')
    app = create_app(config[config_name])

    bind_host = os.environ.get('BIND_HOST', '0.0.0.0')
    bind_port = int(os.environ.get('PORT', 5000))
    local_ip  = _get_local_ip()

    _server_instance = _waitress_create_server(
        app,
        host=bind_host,
        port=bind_port,
        threads=8,
        channel_timeout=120,
        connection_limit=500,
        cleanup_interval=30,
        url_scheme='http',
    )

    _start_zeroconf(bind_port)

    threading.Thread(target=_shutdown_monitor, daemon=True,
                     name='shutdown-monitor').start()

    _print_banner(local_ip, bind_host, bind_port)
    logger.info(f'Listening on {bind_host}:{bind_port}  (config: {config_name})')

    try:
        _server_instance.run()
    except Exception as exc:
        logger.error(f'Server error: {exc}', exc_info=True)
        raise
    finally:
        logger.info('Waitress run() returned.')


if __name__ == '__main__':
    main()
