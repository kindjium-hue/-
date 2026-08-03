#!/bin/bash
# 맥에서 더블클릭하면 노션에 '현장 업무' 데이터베이스를 만들어 준다.
# 별도 설치가 필요 없다 — 맥에 들어 있는 python3만 쓴다.

cd "$(dirname "$0")" || exit 1

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3이 없습니다."
  echo "터미널에서 'xcode-select --install' 을 한 번 실행하신 뒤 다시 시도해 주세요."
  echo
  read -n 1 -r -p "창을 닫으려면 아무 키나 누르세요..."
  exit 1
fi

python3 setup_db.py
status=$?

echo
if [ $status -ne 0 ]; then
  echo "끝내지 못했습니다. 위 메시지를 확인해 주세요."
fi
read -n 1 -r -p "창을 닫으려면 아무 키나 누르세요..."
