# 수학 태도 릴스

"수학을 잘하고 싶다면 태도부터 바꿔 보세요" 원고를 다듬고, 그 톤 그대로
세로형 릴스 영상(1080×1920, 39.2초)으로 만든 결과물입니다.

```
script/01-다듬은-원고.md   다듬은 글 + 원문에서 손본 부분 정리
script/02-릴스-대본.md     장면별 타임코드·자막·나레이션, 업로드 캡션/해시태그
render/make_reels.py       영상 렌더러 (Pillow로 프레임 생성 → ffmpeg 인코딩)
out/math-attitude-reels.mp4  완성 영상 (H.264 / yuv420p / 30fps)
out/cover.png              릴스 커버 이미지
```

## 다시 렌더링하기

```bash
sudo apt-get install -y ffmpeg fonts-nanum   # 나눔스퀘어라운드 필요
pip install pillow
python3 render/make_reels.py [출력경로]
```

문구나 길이를 바꾸려면 `render/make_reels.py`의 각 장면 함수(`s1_hook` ~ `s9_end`)와
맨 아래 `SCENES` 리스트(장면별 초)를 수정하면 됩니다.
