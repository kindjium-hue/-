# -*- coding: utf-8 -*-
"""최소 기능의 CFB(복합 문서) 라이터. HWP 5.0 컨테이너 재작성용."""
import struct

FREESECT, ENDOFCHAIN, FATSECT, DIFSECT = 0xFFFFFFFF, 0xFFFFFFFE, 0xFFFFFFFD, 0xFFFFFFFC
SEC, MINISEC, CUTOFF = 512, 64, 4096


class Entry:
    def __init__(self, name, kind, data=b'', clsid=b'\x00' * 16):
        self.name, self.kind, self.data, self.clsid = name, kind, data, clsid
        self.children = []
        self.id = -1
        self.left = self.right = self.child = 0xFFFFFFFF
        self.start = ENDOFCHAIN
        self.size = 0


def _key(e):
    return (len(e.name), e.name.upper())


def _bst(nodes):
    """정렬된 노드 목록으로 균형 이진 탐색 트리를 만들고 루트를 돌려준다."""
    if not nodes:
        return 0xFFFFFFFF
    mid = len(nodes) // 2
    node = nodes[mid]
    node.left = _bst(nodes[:mid])
    node.right = _bst(nodes[mid + 1:])
    return node.id


def _chain(fat, sectors, first_free):
    """섹터 번호를 이어 붙여 FAT 체인을 만든다."""
    for a, b in zip(sectors, sectors[1:]):
        fat[a] = b
    if sectors:
        fat[sectors[-1]] = ENDOFCHAIN
        return sectors[0]
    return ENDOFCHAIN


def write(root, path):
    # 1) 디렉터리 엔트리 번호 부여 (루트 0번, 이후 깊이 우선)
    entries = []

    def number(e):
        e.id = len(entries)
        entries.append(e)
        for c in e.children:
            number(c)

    number(root)
    for e in entries:
        kids = sorted(e.children, key=_key)
        for k in kids:
            k.left = k.right = 0xFFFFFFFF
        e.child = _bst(kids)

    # 2) 미니 스트림(4096바이트 미만)과 일반 스트림 분리
    mini, minifat = bytearray(), []
    normal = []
    for e in entries:
        if e.kind != 2:
            continue
        e.size = len(e.data)
        if e.size < CUTOFF:
            e.start = len(mini) // MINISEC
            n = -(-e.size // MINISEC) or 1
            mini += e.data + b'\x00' * (n * MINISEC - e.size)
            minifat.append((e, n))
        else:
            normal.append(e)

    root.size = len(mini)

    # 3) 미니 FAT 체인
    mf = [FREESECT] * (len(mini) // MINISEC)
    for e, n in minifat:
        s = e.start
        for k in range(n - 1):
            mf[s + k] = s + k + 1
        mf[s + n - 1] = ENDOFCHAIN
    minifat_bytes = b''.join(struct.pack('<I', v) for v in mf)

    # 4) 디렉터리 스트림
    def dir_entry(e):
        if e.kind == 1:            # 스토리지는 시작 섹터/크기를 쓰지 않는다
            e.start, e.size = 0, 0
        nm = e.name.encode('utf-16le') + b'\x00\x00'
        b = nm + b'\x00' * (64 - len(nm))
        b += struct.pack('<H', len(nm))
        b += struct.pack('<BB', e.kind, 1)  # 1 = black
        b += struct.pack('<III', e.left, e.right, e.child)
        b += e.clsid + struct.pack('<I', 0)
        b += b'\x00' * 16  # 생성/수정 시각
        b += struct.pack('<IIi', e.start if e.start != ENDOFCHAIN else ENDOFCHAIN,
                         e.size & 0xFFFFFFFF, 0)
        assert len(b) == 128, len(b)
        return b

    # 5) 섹터 배치: [일반 스트림들][미니 스트림 컨테이너][미니FAT][디렉터리][FAT]
    blocks = []          # (이름, 바이트) 순서대로 섹터 할당
    for e in normal:
        blocks.append(('stream', e, e.data))
    mini_block = ('mini', None, bytes(mini))
    blocks.append(mini_block)
    minifat_block = ('minifat', None, minifat_bytes)
    blocks.append(minifat_block)

    nsec = lambda d: -(-len(d) // SEC)

    data_sectors = sum(nsec(b[2]) for b in blocks)
    dir_sectors = 0
    fat_sectors = 0
    while True:
        dir_bytes = b''.join(dir_entry(e) for e in entries)
        dir_sectors = nsec(dir_bytes) or 1
        total = data_sectors + dir_sectors + fat_sectors
        need = -(-total // (SEC // 4)) or 1
        if need == fat_sectors:
            break
        fat_sectors = need

    fat = [FREESECT] * (data_sectors + dir_sectors + fat_sectors)
    cur = 0
    assigned = {}
    for kind, e, d in blocks:
        n = nsec(d)
        secs = list(range(cur, cur + n))
        cur += n
        assigned[id(d)] = _chain(fat, secs, 0)
        if kind == 'stream':
            e.start = assigned[id(d)]

    dir_secs = list(range(cur, cur + dir_sectors)); cur += dir_sectors
    dir_start = _chain(fat, dir_secs, 0)
    fat_secs = list(range(cur, cur + fat_sectors)); cur += fat_sectors
    for s in fat_secs:
        fat[s] = FATSECT

    root.start = assigned[id(mini_block[2])]
    minifat_start = assigned[id(minifat_block[2])] if minifat_bytes else ENDOFCHAIN

    # 디렉터리 엔트리는 start/size가 확정된 뒤 다시 만든다
    dir_bytes = b''.join(dir_entry(e) for e in entries)
    dir_bytes += b'\x00' * (dir_sectors * SEC - len(dir_bytes))

    fat_bytes = b''.join(struct.pack('<I', v) for v in fat)
    fat_bytes += b'\xFF' * (fat_sectors * SEC - len(fat_bytes))

    assert fat_sectors <= 109, 'DIFAT 섹터가 필요할 만큼 큰 파일'

    header = b'\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1' + b'\x00' * 16
    header += struct.pack('<HHH', 0x003E, 0x0003, 0xFFFE)
    header += struct.pack('<HH', 9, 6)
    header += b'\x00' * 6
    header += struct.pack('<I', 0)               # 디렉터리 섹터 수(v3은 0)
    header += struct.pack('<I', fat_sectors)
    header += struct.pack('<I', dir_start)
    header += struct.pack('<I', 0)               # 트랜잭션 서명
    header += struct.pack('<I', CUTOFF)
    header += struct.pack('<I', minifat_start)
    header += struct.pack('<I', nsec(minifat_bytes) if minifat_bytes else 0)
    header += struct.pack('<I', ENDOFCHAIN)      # 첫 DIFAT 섹터
    header += struct.pack('<I', 0)               # DIFAT 섹터 수
    difat = [fat_secs[i] if i < len(fat_secs) else FREESECT for i in range(109)]
    header += b''.join(struct.pack('<I', v) for v in difat)
    assert len(header) == SEC, len(header)

    body = bytearray()
    for kind, e, d in blocks:
        body += d + b'\x00' * (nsec(d) * SEC - len(d))
    body += dir_bytes + fat_bytes

    with open(path, 'wb') as fp:
        fp.write(header + bytes(body))
