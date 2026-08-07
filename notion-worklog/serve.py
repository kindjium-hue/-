#!/usr/bin/env python3
"""웹 폼 서버를 켜고, 휴대폰에서 열 주소를 알려 준다.

`웹폼켜기.command`가 이 파일을 실행한다. 하는 일:
1. .env에 노션 토큰·DB ID가 있는지 확인
2. 빈 포트를 찾아 서버를 띄운다
3. 같은 와이파이에서 쓸 주소를 보여 주고, QR 코드도 그려 준다
4. cloudflared가 깔려 있으면 현장(LTE)용 https 주소까지 만들어 준다
"""

from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"

DEFAULT_PORT = 8000
PORT_TRIES = 12
TUNNEL_PATTERN = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
TUNNEL_WAIT_SECONDS = 25


def missing_settings(env: dict[str, str]) -> list[str]:
    """비어 있는 필수 설정 이름 목록."""
    return [
        key
        for key in ("NOTION_TOKEN", "NOTION_DATABASE_ID")
        if not (env.get(key) or "").strip()
    ]


def port_is_free(port: int, host: str = "0.0.0.0") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind((host, port))
        except OSError:
            return False
    return True


def pick_port(start: int = DEFAULT_PORT, tries: int = PORT_TRIES) -> int | None:
    """start부터 차례로 비어 있는 포트를 찾는다. 없으면 None."""
    for port in range(start, start + tries):
        if port_is_free(port):
            return port
    return None


def lan_ip() -> str | None:
    """같은 와이파이에서 접속할 때 쓸 내 IP."""
    for interface in ("en0", "en1"):  # 맥의 와이파이 · 유선
        try:
            found = subprocess.run(
                ["ipconfig", "getifaddr", interface],
                capture_output=True, text=True, timeout=5,
            ).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            found = ""
        if found:
            return found

    # 맥이 아니거나 위 방법이 안 되면 소켓으로 알아낸다 (실제로 보내지는 않는다)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("8.8.8.8", 80))
            return probe.getsockname()[0]
    except OSError:
        return None


def qr_lines(text: str) -> list[str]:
    """터미널에 그릴 QR 코드. qrcode 꾸러미가 없으면 빈 목록."""
    try:
        import qrcode
    except ModuleNotFoundError:
        return []
    code = qrcode.QRCode(border=1)
    code.add_data(text)
    code.make()
    matrix = code.get_matrix()
    # 위아래 두 줄을 한 줄로 합쳐 그려야 터미널에서 정사각형으로 보인다.
    blocks = {(True, True): "█", (True, False): "▀", (False, True): "▄", (False, False): " "}
    lines = []
    for row in range(0, len(matrix), 2):
        upper = matrix[row]
        lower = matrix[row + 1] if row + 1 < len(matrix) else [False] * len(upper)
        lines.append("".join(blocks[(bool(u), bool(l))] for u, l in zip(upper, lower)))
    return lines


def show(text: str, *, label: str) -> None:
    print(f"\n{label}\n  {text}")
    for line in qr_lines(text):
        print("  " + line)


def start_tunnel(port: int) -> tuple[subprocess.Popen | None, str | None]:
    """cloudflared가 있으면 현장용 https 주소를 만든다."""
    from shutil import which

    if not which("cloudflared"):
        return None, None

    print("\n현장(LTE)용 주소를 만들고 있습니다…")
    process = subprocess.Popen(
        ["cloudflared", "tunnel", "--url", f"http://localhost:{port}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    address: str | None = None
    deadline = time.monotonic() + TUNNEL_WAIT_SECONDS

    def watch() -> None:
        nonlocal address
        for line in process.stderr or []:
            found = TUNNEL_PATTERN.search(line)
            if found and not address:
                address = found.group(0)

    threading.Thread(target=watch, daemon=True).start()
    while address is None and time.monotonic() < deadline and process.poll() is None:
        time.sleep(0.4)
    return process, address


def main() -> int:
    sys.path.insert(0, str(BASE_DIR))
    import notion_lite as nl

    env = {**nl.read_env(ENV_PATH), **{k: v for k, v in os.environ.items() if v}}
    missing = missing_settings(env)
    if missing:
        print("노션 설정이 아직 없습니다: " + ", ".join(missing))
        print()
        print("`노션DB만들기.command`를 먼저 더블클릭해 주세요.")
        print("이미 만드셨다면 .env 파일에 아래 두 줄이 있는지 확인해 주세요.")
        print("  NOTION_TOKEN=ntn_...")
        print("  NOTION_DATABASE_ID=...")
        return 1

    port = pick_port()
    if port is None:
        print(f"{DEFAULT_PORT}번부터 {DEFAULT_PORT + PORT_TRIES - 1}번까지 모두 사용 중입니다.")
        print("이미 켜져 있는 것이 아닌지 확인해 주세요.")
        return 1

    show(f"http://localhost:{port}", label="이 맥에서 열기")
    address = lan_ip()
    if address:
        show(f"http://{address}:{port}", label="같은 와이파이의 휴대폰에서 열기 (QR을 카메라로 찍으세요)")

    tunnel, public = start_tunnel(port)
    if public:
        show(public, label="현장(LTE)에서 열기 — 이 주소를 직원에게 카톡으로 보내세요")
    elif tunnel is None:
        print("\n현장(LTE)용 주소는 cloudflared가 있어야 만들어집니다.")
        print("  터미널에서 한 번만: brew install cloudflared")

    print("\n" + "─" * 56)
    print("서버가 켜졌습니다. 이 창을 닫으면 서버도 꺼집니다.")
    print("멈추려면 control + C 를 누르세요.")
    print("─" * 56 + "\n")

    threading.Timer(1.5, lambda: webbrowser.open(f"http://localhost:{port}")).start()

    import uvicorn

    from app import app as worklog_app

    try:
        uvicorn.run(worklog_app, host="0.0.0.0", port=port, log_level="warning")
    except KeyboardInterrupt:
        pass
    finally:
        if tunnel and tunnel.poll() is None:
            tunnel.terminate()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
