# -*- coding: utf-8 -*-
"""원본 HWP의 표 서식을 그대로 두고 셀 본문 문단만 content.py의 원고로 교체한다.

원본 파일을 열어 BodyText/Section0 레코드를 파싱한 뒤, CELLS에 지정한
셀(LIST_HEADER 레코드 번호)의 문단을 새로 만들어 넣고, OLE 복합 문서를
다시 써서 저장한다. 나머지 스트림(DocInfo·FileHeader 등)은 원본 그대로다.
"""
import struct, zlib, sys, os, olefile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from content import CELLS
import cfb

# 사용법: python3 rewrite_hwp.py <원본.hwp> <결과.hwp>
SRC, DST = sys.argv[1], sys.argv[2]

PARA_HEADER, PARA_TEXT, PARA_CHAR_SHAPE, PARA_LINE_SEG, CTRL_HEADER, LIST_HEADER = 66, 67, 68, 69, 71, 72
INLINE = {1, 2, 3, 11, 12, 14, 15, 16, 17, 18, 21, 22, 23}  # 16바이트를 차지하는 확장 제어문자


def parse(data):
    recs, i = [], 0
    while i < len(data):
        h = struct.unpack('<I', data[i:i + 4])[0]
        tag, lvl, size = h & 0x3FF, (h >> 10) & 0x3FF, (h >> 20) & 0xFFF
        i += 4
        if size == 0xFFF:
            size = struct.unpack('<I', data[i:i + 4])[0]
            i += 4
        recs.append([tag, lvl, data[i:i + size]])
        i += size
    return recs


def serialize(recs):
    out = bytearray()
    for tag, lvl, p in recs:
        if len(p) >= 0xFFF:
            out += struct.pack('<II', (tag & 0x3FF) | (lvl << 10) | (0xFFF << 20), len(p))
        else:
            out += struct.pack('<I', (tag & 0x3FF) | (lvl << 10) | (len(p) << 20))
        out += p
    return bytes(out)


def leading_ctrl(text_bytes):
    """문단 맨 앞에 붙은 확장 제어문자(단 정의 등) 바이트를 그대로 돌려준다."""
    n, j = len(text_bytes), 0
    while j + 2 <= n:
        ch = struct.unpack('<H', text_bytes[j:j + 2])[0]
        if ch in INLINE:
            j += 16
        else:
            break
    return text_bytes[:j]


def cell_range(recs, li):
    """LIST_HEADER 다음부터 그 셀에 속한 레코드 구간의 끝 인덱스를 찾는다."""
    lvl = recs[li][1]
    j = li + 1
    while j < len(recs):
        tag, l, _ = recs[j]
        if l < lvl or (l == lvl and tag in (LIST_HEADER, CTRL_HEADER)):
            break
        j += 1
    return j


def main():
    ole = olefile.OleFileIO(SRC)
    streams = {'/'.join(p): ole.openstream('/'.join(p)).read() for p in ole.listdir()}
    section = zlib.decompress(streams['BodyText/Section0'], -15)
    recs = parse(section)

    inst = 0x40000000  # 새 문단에 부여할 인스턴스 ID 시작값
    new_recs = list(recs)

    for li in sorted(CELLS, reverse=True):   # 뒤에서부터 교체해야 인덱스가 밀리지 않는다
        assert recs[li][0] == LIST_HEADER, li
        end = cell_range(recs, li)
        body = recs[li + 1:end]
        plvl = body[0][1]

        # 템플릿: 셀의 첫 문단과 그 하위 레코드
        thead = body[0][2]
        ttext = body[1][2]
        tshape = body[2][2]
        tseg = body[3][2]
        extra = []                            # 첫 문단에 딸린 컨트롤 레코드
        for tag, lvl, p in body[4:]:
            if lvl <= plvl:
                break
            extra.append([tag, lvl, p])
        prefix = leading_ctrl(ttext)
        shape_id = struct.unpack('<II', tshape[:8])[1]

        texts = CELLS[li]
        built = []
        for k, t in enumerate(texts):
            raw = (prefix if k == 0 else b'') + (t + '\r').encode('utf-16le')  # 문단 끝 문자 포함
            nchars = len(raw) // 2
            last = (k == len(texts) - 1)
            mask = struct.unpack('<I', thead[4:8])[0] if (k == 0 and prefix) else 0
            h = bytearray(thead)
            h[0:4] = struct.pack('<I', nchars | (0x80000000 if last else 0))
            h[4:8] = struct.pack('<I', mask)
            h[12:14] = struct.pack('<H', 1)   # 글자모양 개수
            h[14:16] = struct.pack('<H', 0)   # 영역 태그 개수
            h[16:18] = struct.pack('<H', 0)   # 줄 정보 없음 → 한글이 다시 계산
            h[18:22] = struct.pack('<I', inst); inst += 1
            built.append([PARA_HEADER, plvl, bytes(h)])
            built.append([PARA_TEXT, plvl + 1, raw])
            built.append([PARA_CHAR_SHAPE, plvl + 1, struct.pack('<II', 0, shape_id)])
            if k == 0:
                built.extend(extra)

        lh = bytearray(recs[li][2])
        lh[0:4] = struct.pack('<I', len(texts))
        new_recs[li] = [LIST_HEADER, recs[li][1], bytes(lh)]
        new_recs[li + 1:end] = built

    # 저장된 줄 배치 정보를 모두 지운다. 남겨 두면 표 높이가 바뀔 때
    # 한글이 옛 좌표대로 그려 글자가 겹쳐 보인다.
    stripped = []
    for tag, lvl, p in new_recs:
        if tag == PARA_LINE_SEG:
            continue
        if tag == PARA_HEADER:
            p = bytearray(p)
            p[16:18] = struct.pack('<H', 0)
            p = bytes(p)
        stripped.append([tag, lvl, p])
    new_recs = stripped

    out_section = serialize(new_recs)
    streams['BodyText/Section0'] = zlib.compress(out_section, 9)[2:-4]

    # 미리보기 텍스트 갱신
    prv = []
    for tag, lvl, p in new_recs:
        if tag == PARA_TEXT:
            chars, j = [], 0
            while j + 2 <= len(p):
                ch = struct.unpack('<H', p[j:j + 2])[0]
                if ch in INLINE:
                    j += 16
                elif ch < 32:
                    j += 2
                else:
                    chars.append(chr(ch)); j += 2
            if chars:
                prv.append(''.join(chars))
    streams['PrvText'] = ('\r\n'.join(prv)[:1000]).encode('utf-16le')

    root = cfb.Entry('Root Entry', 5, clsid=b'\x00' * 16)
    node = {'': root}
    for path in ['\x05HwpSummaryInformation', 'BodyText/Section0', 'DocInfo',
                 'DocOptions/_LinkDoc', 'FileHeader', 'PrvImage', 'PrvText',
                 'Scripts/DefaultJScript', 'Scripts/JScriptVersion']:
        parts = path.split('/')
        parent = root
        for d in parts[:-1]:
            if d not in node:
                st = cfb.Entry(d, 1)
                parent.children.append(st)
                node[d] = st
            parent = node[d]
        parent.children.append(cfb.Entry(parts[-1], 2, streams[path]))
    cfb.write(root, DST)
    print('작성 완료:', DST, '섹션 크기', len(out_section), '압축', len(streams['BodyText/Section0']))


main()
