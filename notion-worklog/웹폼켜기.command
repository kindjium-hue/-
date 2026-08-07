#!/bin/bash
# 맥에서 더블클릭하면 현장 업무 웹 폼을 켜 준다.
# 처음 한 번은 필요한 꾸러미를 내려받으므로 몇 분 걸릴 수 있다.

cd "$(dirname "$0")" || exit 1

echo "청명 현장 업무 웹 폼을 켭니다."
echo

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3이 없습니다."
  echo "터미널에서 'xcode-select --install' 을 한 번 실행하신 뒤 다시 시도해 주세요."
  echo
  read -n 1 -r -p "창을 닫으려면 아무 키나 누르세요..."
  exit 1
fi

PYTHON=".venv/bin/python"

# 처음 실행이거나 꾸러미가 빠졌으면 준비한다.
if [ ! -x "$PYTHON" ] || ! "$PYTHON" -c "import fastapi, uvicorn, httpx, jinja2, fitz, PIL" >/dev/null 2>&1; then
  echo "처음 실행이라 필요한 것을 준비합니다. 몇 분 걸릴 수 있습니다…"
  echo
  python3 -m venv .venv || { echo "준비 실패: 가상환경을 만들 수 없습니다."; read -n 1 -r -p "아무 키나…"; exit 1; }
  .venv/bin/python -m pip install --quiet --upgrade pip
  if ! .venv/bin/python -m pip install --quiet -r requirements.txt; then
    echo
    echo "준비 실패: 꾸러미를 내려받지 못했습니다. 인터넷 연결을 확인해 주세요."
    echo
    read -n 1 -r -p "창을 닫으려면 아무 키나 누르세요..."
    exit 1
  fi
  echo "준비가 끝났습니다."
  echo
fi

"$PYTHON" serve.py
status=$?

echo
if [ $status -ne 0 ]; then
  echo "서버를 켜지 못했습니다. 위 메시지를 확인해 주세요."
else
  echo "서버를 껐습니다."
fi
read -n 1 -r -p "창을 닫으려면 아무 키나 누르세요..."
