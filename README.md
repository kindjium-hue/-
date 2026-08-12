# 수학 태도 릴스

"수학을 잘하고 싶다면 태도부터 바꿔 보세요" 원고를 다듬고, 그 톤 그대로
세로형 릴스 영상(1080×1920, 41.5초)으로 만든 결과물입니다.

실제 학습지 사진 두 장(빼곡히 푼 것 / 거의 손대지 않은 것)을 대조 소재로 쓰고,
배경에는 바른 자세로 앉은 학생과 책상에 엎드린 학생을 손그림으로 그려 넣었습니다.

```
script/01-다듬은-원고.md   다듬은 글 + 원문에서 손본 부분 정리
script/02-릴스-대본.md     장면별 타임코드·자막·나레이션, 업로드 캡션/해시태그
assets/worksheet-a.jpg     성적이 오른 아이의 학습지 (풀이가 빼곡함)
assets/worksheet-b.jpg     제자리인 아이의 학습지 (여백과 낙서뿐)
assets/desk-original.jpg   두 장을 함께 찍은 원본 사진
render/draw_lib.py         손그림 학생 일러스트 · 학습지 카드 생성
render/make_reels.py       영상 렌더러 (Pillow로 프레임 생성 → ffmpeg 인코딩)
out/math-attitude-reels.mp4  완성 영상 (H.264 / yuv420p / 30fps)
out/cover.png              릴스 커버 이미지
```

사진을 다른 것으로 바꾸려면 `assets/worksheet-a.jpg` · `worksheet-b.jpg`를 교체하고,
잘리는 위치가 어긋나면 `assets/crop.json`으로 조정하면 됩니다(형식은 릴스 대본 문서 참고).
사진이 아예 없으면 렌더러가 학습지를 직접 그린 대체 카드로 돌아갑니다.

## 다시 렌더링하기

```bash
sudo apt-get install -y ffmpeg fonts-nanum   # 나눔스퀘어라운드 필요
pip install pillow
python3 render/make_reels.py [출력경로]
```

문구나 길이를 바꾸려면 `render/make_reels.py`의 각 장면 함수(`s1_hook` ~ `s9_end`)와
맨 아래 `SCENES` 리스트(장면별 초)를 수정하면 됩니다.

## 함께 들어 있는 도구

`notion-worklog/` — 현장 업무의 일정·진행상태·사진·견적서를 휴대폰 웹 폼으로 올려
노션 데이터베이스에 쌓는 작은 서버입니다. 작업항목을 고르고 고객명·평수만 넣으면
회사 견적서 양식 그대로 PDF도 만들어 줍니다. 설정 방법은 `notion-worklog/README.md` 참고.

`imweb-widget/` — 같은 견적서를 아임웹 페이지에서 뽑는 위젯(HTML/CSS/JS)입니다.
평수를 넣으면 견적서가 화면에 채워지고, 브라우저 인쇄로 PDF로 저장합니다.
붙여넣는 방법은 `imweb-widget/README.md` 참고.

`imweb-schedule/` — 아임웹 게시판에 일정 글을 올리면 달력에 자동으로 나타나는
위젯입니다. 월간·주간 보기, 날짜별 일정, 작업항목 중복 선택, 담당자·장소·진행사항,
BEFORE/AFTER 사진까지 게시판 글 하나로 관리합니다. `imweb-schedule/README.md` 참고.

`imweb-form/` — 아임웹 자체 일정(캘린더) 위젯을 쓸 때, 「상세 일정」에 붙여넣을
제목과 작업현황 표를 만들어 주는 폼입니다. `imweb-form/README.md` 참고.

`imweb-probe/` — 아임웹 캘린더가 어떤 주소로 무엇을 주고받는지 알아보는 임시 조사
도구입니다. 캘린더 내용을 읽거나 고치는 위젯을 만들기 전에 씁니다.

`imweb-calview/` — 아임웹 기본 캘린더의 일정 자료를 그대로 읽어, 같은 모양의 달력
(일·주·월)과 기간별 정리 표로 보여 주는 위젯입니다. `imweb-calview/README.md` 참고.
