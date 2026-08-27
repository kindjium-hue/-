const pptxgen = require('pptxgenjs');

const DARK = '1E3D2B', GREEN = '2C5F2D', MOSS = '97BC62', LIGHT = 'F4F6F1',
      INK = '1F2B22', MUTED = '667A6B', AMBER = 'A9701A', WHITE = 'FFFFFF', LINE = 'DCE3D9';
const F = '맑은 고딕';
const W = 13.333, H = 7.5;

const p = new pptxgen();
p.layout = 'LAYOUT_WIDE';
p.author = '가천대학교부설평생교육원(메디컬)';
p.title = '2026년 1학기 보수교육 자율관리(자체점검) 결과';

const tx = (o) => Object.assign({ isTextBox: true, fontFace: F, color: INK, margin: 0 }, o);

// 슬라이드 공통 머리말 — 제목과 영역 배지
function head(s, title, badge) {
  if (badge) {
    s.addShape(p.ShapeType.ellipse, { x: 0.62, y: 0.6, w: 0.66, h: 0.66, fill: { color: GREEN } });
    s.addText(badge, tx({ x: 0.62, y: 0.6, w: 0.66, h: 0.66, align: 'center', valign: 'middle',
                          fontSize: 22, bold: true, color: WHITE }));
  }
  s.addText(title, tx({ x: badge ? 1.5 : 0.62, y: 0.64, w: 11.3, h: 0.6,
                        fontSize: 30, bold: true, color: DARK, valign: 'middle' }));
}

function bullets(items, o) {
  return items.map((t, i) => ({
    text: t,
    options: { bullet: { code: '2022' }, breakLine: i < items.length - 1,
               fontSize: o.fontSize || 14, color: o.color || INK, paraSpaceAfter: o.gap || 8 },
  }));
}

// 카드 한 장 (제목 + 불릿)
function card(s, o) {
  s.addShape(p.ShapeType.roundRect, { x: o.x, y: o.y, w: o.w, h: o.h, rectRadius: 0.08,
    fill: { color: o.fill }, line: { color: o.border || o.fill, width: 1 } });
  s.addText(o.title, tx({ x: o.x + 0.28, y: o.y + 0.22, w: o.w - 0.56, h: 0.34,
    fontSize: 15, bold: true, color: o.titleColor, valign: 'middle' }));
  s.addText(bullets(o.items, { fontSize: o.fontSize || 14, gap: o.gap || 9 }),
    tx({ x: o.x + 0.28, y: o.y + 0.68, w: o.w - 0.56, h: o.h - 0.92, valign: 'top' }));
}

/* 1 ─ 표지 */
{
  const s = p.addSlide();
  s.background = { color: DARK };
  s.addShape(p.ShapeType.ellipse, { x: 10.6, y: -1.5, w: 4.6, h: 4.6, fill: { color: GREEN } });
  s.addShape(p.ShapeType.ellipse, { x: 11.9, y: 4.9, w: 2.6, h: 2.6, fill: { color: '25543A' } });
  s.addText('2026년 1학기', tx({ x: 1.0, y: 2.05, w: 9, h: 0.45, fontSize: 18, color: MOSS, bold: true }));
  s.addText('보육교직원 보수교육기관\n자율관리(자체점검) 결과', tx({
    x: 1.0, y: 2.6, w: 9.4, h: 1.9, fontSize: 40, bold: true, color: WHITE, lineSpacing: 52 }));
  s.addText('가천대학교부설평생교육원(메디컬)', tx({
    x: 1.0, y: 4.85, w: 8, h: 0.4, fontSize: 17, color: MOSS }));
  s.addText('기본환경 · 교육운영 · 교육과정 · 기관운영 4개 영역 종합평가', tx({
    x: 1.0, y: 5.35, w: 9, h: 0.4, fontSize: 13, color: 'B9C9B4' }));
  s.addNotes('2026년 1학기 보수교육 운영 후 실시한 자체점검 결과를 4개 영역으로 나누어 보고드립니다.');
}

/* 2 ─ 점검 개요 */
{
  const s = p.addSlide();
  head(s, '점검 개요');
  const rows = [['점검 대상', '2026년 1학기 보육교직원 보수교육 전 과정'],
                ['점검 방법', '영역별 지표 자체점검 · 학습자 만족도 조사 · 강사 자체평가'],
                ['활용', '영역별 개선과제 도출 → 개선계획 수립 → 다음 학기 반영']];
  rows.forEach(([k, v], i) => {
    const y = 1.95 + i * 1.15;
    s.addText(k, tx({ x: 0.62, y, w: 1.35, h: 0.6, fontSize: 13, bold: true, color: GREEN, valign: 'middle' }));
    s.addText(v, tx({ x: 2.05, y, w: 4.3, h: 0.8, fontSize: 13, color: INK, valign: 'middle', lineSpacing: 19 }));
  });
  const areas = [['1', '기본환경', '시설 · 설비 · 학습 공간'], ['2', '교육운영', '요구도 · 학사 · 만족도'],
                 ['3', '교육과정', '교육내용 · 강사 · 교재'], ['4', '기관운영', '행정 · 기록 · 환류']];
  areas.forEach(([n, name, desc], i) => {
    const x = 6.9 + (i % 2) * 3.05, y = 1.8 + Math.floor(i / 2) * 2.1;
    s.addShape(p.ShapeType.roundRect, { x, y, w: 2.8, h: 1.9, rectRadius: 0.08,
      fill: { color: LIGHT }, line: { color: LINE, width: 1 } });
    s.addShape(p.ShapeType.ellipse, { x: x + 0.26, y: y + 0.38, w: 0.5, h: 0.5, fill: { color: GREEN } });
    s.addText(n, tx({ x: x + 0.26, y: y + 0.38, w: 0.5, h: 0.5, align: 'center', valign: 'middle',
      fontSize: 15, bold: true, color: WHITE }));
    s.addText(name, tx({ x: x + 0.9, y: y + 0.38, w: 1.8, h: 0.5, fontSize: 16, bold: true,
      color: DARK, valign: 'middle' }));
    s.addText(desc, tx({ x: x + 0.28, y: y + 1.18, w: 2.3, h: 0.4, fontSize: 12, color: MUTED }));
  });
  s.addText('점검 결과 4개 영역 모두 지표 충족도가 높게 나타났으며, 영역마다 보완할 과제를 함께 도출했습니다.',
    tx({ x: 0.62, y: 6.3, w: 12.1, h: 0.45, fontSize: 13, color: MUTED, valign: 'middle' }));
  s.addNotes('점검 대상과 방법을 먼저 말씀드리고, 오른쪽 네 영역 순서대로 결과를 보고합니다.');
}

/* 3 ─ 한눈에 보기 */
{
  const s = p.addSlide();
  head(s, '한눈에 보기');
  s.addText('강점', tx({ x: 0.62, y: 1.62, w: 3, h: 0.35, fontSize: 15, bold: true, color: GREEN }));
  [['현장 적용성', '사례·시나리오 기반 수업'], ['강사 전문성', '현직 경험을 갖춘 강사진'],
   ['개정 반영 속도', '변경 내용 즉시 교안 반영'], ['행정 지원', '전담 인력의 신속·친절한 안내']]
   .forEach(([t, d], i) => {
    const y = 2.15 + i * 1.08;
    s.addShape(p.ShapeType.roundRect, { x: 0.62, y, w: 5.6, h: 0.88, rectRadius: 0.06,
      fill: { color: LIGHT }, line: { color: LINE, width: 1 } });
    s.addText(t, tx({ x: 0.92, y: y + 0.14, w: 2.1, h: 0.6, fontSize: 14, bold: true, color: DARK, valign: 'middle' }));
    s.addText(d, tx({ x: 3.0, y: y + 0.14, w: 3.1, h: 0.6, fontSize: 12, color: MUTED, valign: 'middle' }));
  });
  s.addText('개선과제', tx({ x: 7.05, y: 1.62, w: 3, h: 0.35, fontSize: 15, bold: true, color: AMBER }));
  [['1영역', '협력형 학습 공간으로 강의실 재구성'], ['2영역', '요구도 반영 절차 문서화 · 이수 후 코칭'],
   ['3영역', '놀이 중심 · 아동권리 모듈 강화'], ['4영역', '상시 의견 수렴 · 환류 체계 구축']]
   .forEach(([t, d], i) => {
    const y = 2.15 + i * 1.08;
    s.addShape(p.ShapeType.roundRect, { x: 7.05, y, w: 5.68, h: 0.88, rectRadius: 0.06,
      fill: { color: 'FDF6EA' }, line: { color: 'F0E0C6', width: 1 } });
    s.addText(t, tx({ x: 7.35, y: y + 0.14, w: 0.95, h: 0.6, fontSize: 13, bold: true, color: AMBER, valign: 'middle' }));
    s.addText(d, tx({ x: 8.3, y: y + 0.14, w: 4.2, h: 0.6, fontSize: 12.5, color: INK, valign: 'middle' }));
  });
  s.addText('1학기 이수 인원 ○○명 · 만족도 평균 ○○점   (발표 전 실제 수치로 채워 주세요)',
    tx({ x: 0.62, y: 6.65, w: 12.1, h: 0.4, fontSize: 12, color: MUTED }));
  s.addNotes('왼쪽은 유지·강화할 강점, 오른쪽은 2학기에 실행할 개선과제입니다. 이수 인원과 만족도 수치는 실제 값으로 채워 발표하세요.');
}

/* 4 ─ 강점 */
{
  const s = p.addSlide();
  head(s, '강점 및 우수한 점');
  const items = [
    ['현장 적용 중심 교육과정', '보육실 상황을 재구성한 사례·시나리오 수업, 수업 말미에 현장 적용 계획 작성'],
    ['강사진의 현장 전문성', '어린이집 운영·보육 실무 경력을 갖춘 강사가 사례와 해결 과정을 함께 제시'],
    ['개정 사항의 신속한 반영', '표준보육과정·보육사업안내 개정 내용을 교안에 즉시 반영해 중점 지도'],
    ['실습 중심의 실용성', '현장에서 마주할 상황을 다루는 문제해결 실습으로 참여도 높음'],
    ['학습자 중심 교육환경', '최신 기자재를 갖춘 강의실, 넓은 무료 주차장으로 원거리 학습자 편의 확보'],
    ['점검·환류 체계 상시 운영', '과정 종료마다 만족도 조사와 강사 자체평가를 실시해 다음 과정에 반영'],
  ];
  items.forEach(([t, d], i) => {
    const x = 0.62 + (i % 2) * 6.15, y = 1.8 + Math.floor(i / 2) * 1.62;
    s.addShape(p.ShapeType.ellipse, { x, y: y + 0.06, w: 0.34, h: 0.34, fill: { color: MOSS } });
    s.addText(String(i + 1), tx({ x, y: y + 0.06, w: 0.34, h: 0.34, align: 'center', valign: 'middle',
      fontSize: 12, bold: true, color: DARK }));
    s.addText(t, tx({ x: x + 0.5, y, w: 5.3, h: 0.42, fontSize: 15, bold: true, color: DARK, valign: 'middle' }));
    s.addText(d, tx({ x: x + 0.5, y: y + 0.48, w: 5.4, h: 0.95, fontSize: 12.5, color: MUTED, lineSpacing: 18 }));
  });
  s.addNotes('강점은 여섯 가지로 정리했습니다. 특히 현장 적용성과 강사 전문성이 만족도에서 높게 평가되었습니다.');
}

/* 5~8 ─ 영역별 미흡 · 개선 */
const AREAS = [
  { n: '1', name: '기본환경',
    gap: ['모둠 토론·실습형 수업을 함께 운영하기에는 강의실이 협소',
          '수강 인원이 몰리는 시간대에는 실습 기자재와 좌석에 여유 부족'],
    plan: ['모둠 토론·개별 학습·휴식이 구분되는 협력형 학습 공간으로 재구성',
           '실습형 과목은 넓은 강의실에 우선 배정',
           '실습 기자재 학기별 점검·확충, 소방·안전·위생 정기 점검',
           '무료 주차장 안내 표지 보강으로 이용 편의 향상'],
    when: '2026년 2학기 중 추진',
    effect: '실습·토의형 수업을 안정적으로 운영할 수 있는 학습 공간을 확보합니다.',
    note: '강의실 환경은 만족도가 높은 편이지만, 실습형 수업이 늘면서 공간이 부족해졌습니다.' },
  { n: '2', name: '교육운영',
    gap: ['요구도 조사 결과가 과목·강사 편성에 반영되는 절차가 문서로 표준화되지 않음',
          '이수 후 현장 적용의 어려움을 상담할 사후 지원 창구 부재'],
    plan: ['수강신청 단계에서 요구도 조사 정례화, 반영 절차를 문서로 규정',
           '이수 후 3개월간 온라인 질의응답·개별 코칭 지원',
           '만족도 결과와 조치사항을 학기별 운영보고서로 정리해 강사진과 공유',
           '출결·이수 관리 기준을 재정비해 모집 안내문에 명시'],
    when: '2026년 2학기 중 추진',
    effect: '요구가 반영된 근거가 남고, 교육 효과가 현장까지 이어집니다.',
    note: '조사는 하고 있으나 반영 근거가 남지 않는 점, 교육이 끝난 뒤 지원이 끊기는 점이 핵심 과제입니다.' },
  { n: '4', name: '기관운영',
    gap: ['의견 수렴이 과정 종료 시점의 만족도 조사에 집중',
          '수집한 의견의 검토·반영 결과를 기록하고 회신하는 절차 미비',
          '강사진·행정 담당자의 역량 개발을 위한 정기 연수 부족'],
    plan: ['상시 의견 접수 → 검토·반영 → 결과 회신의 개선 체계 구축, 개선 이력 대장 관리',
           '학기별 강사 워크숍과 교수법 연수 지원',
           '행정 담당자 개인정보 보호·문서 관리 교육 실시',
           '교육 운영 서류의 작성·보존 기준 정비로 기록 신뢰성 확보'],
    when: '2026년 2학기 중 추진',
    effect: '의견이 반영되는 과정이 기록으로 남아 기관 운영의 신뢰도가 높아집니다.',
    note: '행정 안내에 대한 평가는 좋습니다. 의견이 반영된 결과를 남기고 알리는 절차를 갖추는 것이 과제입니다.' },
];

function areaSlide(a) {
  const s = p.addSlide();
  head(s, `${a.n}영역. ${a.name}`, a.n);
  card(s, { x: 0.62, y: 1.8, w: 5.6, h: 3.15, fill: 'F6F6F4', border: 'E2E4DE',
            title: '점검에서 확인된 미흡', titleColor: AMBER, items: a.gap, fontSize: 13.5, gap: 12 });
  card(s, { x: 7.05, y: 1.8, w: 5.68, h: 3.15, fill: LIGHT, border: LINE,
            title: '개선 계획', titleColor: GREEN, items: a.plan, fontSize: 13.5, gap: 10 });
  s.addShape(p.ShapeType.roundRect, { x: 0.62, y: 5.35, w: 12.11, h: 1.1, rectRadius: 0.08,
    fill: { color: DARK } });
  s.addText('기대 효과', tx({ x: 1.0, y: 5.62, w: 1.5, h: 0.55, fontSize: 13, bold: true,
    color: MOSS, valign: 'middle' }));
  s.addText(a.effect, tx({ x: 2.5, y: 5.62, w: 7.2, h: 0.55, fontSize: 14, color: WHITE, valign: 'middle' }));
  s.addShape(p.ShapeType.roundRect, { x: 10.0, y: 5.7, w: 2.35, h: 0.42, rectRadius: 0.1,
    fill: { color: GREEN } });
  s.addText(a.when, tx({ x: 10.0, y: 5.7, w: 2.35, h: 0.42, align: 'center', valign: 'middle',
    fontSize: 11.5, bold: true, color: WHITE }));
  s.addNotes(a.note);
}
areaSlide(AREAS[0]);
areaSlide(AREAS[1]);

/* 7 ─ 3영역은 개선계획이 셋이라 별도 배치 */
{
  const s = p.addSlide();
  head(s, '3영역. 교육과정', '3');
  card(s, { x: 0.62, y: 1.8, w: 12.11, h: 1.8, fill: 'F6F6F4', border: 'E2E4DE',
    title: '점검에서 확인된 미흡', titleColor: AMBER, fontSize: 13.5, gap: 6,
    items: ['개정 교육과정의 반영이 일부 과목에 집중되고, 놀이 중심·문제해결을 다루는 토의·실습형 과목 비중이 낮음',
            '아동권리·아동학대 예방과 다문화·포용 교육 내용이 여러 과목에 분산되어 과목 간 연계성 부족'] });
  const plans = [
    ['개정 내용 전 과목 반영', '제4차 어린이집 표준보육과정, 2019 개정 누리과정, 매년 개정되는 보육사업안내의 변경 사항을 전 과목 교안에 공통 반영하고 중점 지도'],
    ['놀이 중심 보육 강화', '영유아가 스스로 놀이를 확장하도록 돕는 교사 역할을 실습으로 다루고, 열린 질문·사례 토의·실행계획 작성으로 이어지는 수업 설계 확대'],
    ['아동권리·다양성 심화', '아동권리 존중과 아동학대 예방(신고의무자 교육 포함)을 필수 모듈로 편성하고, 다문화·포용·인권 심화과정을 신설'],
  ];
  s.addText('개선 계획', tx({ x: 0.62, y: 3.82, w: 3, h: 0.32, fontSize: 15, bold: true, color: GREEN }));
  plans.forEach(([t, d], i) => {
    const x = 0.62 + i * 4.13;
    s.addShape(p.ShapeType.roundRect, { x, y: 4.28, w: 3.85, h: 2.4, rectRadius: 0.08,
      fill: { color: LIGHT }, line: { color: LINE, width: 1 } });
    s.addShape(p.ShapeType.ellipse, { x: x + 0.28, y: 4.55, w: 0.42, h: 0.42, fill: { color: GREEN } });
    s.addText(String(i + 1), tx({ x: x + 0.28, y: 4.55, w: 0.42, h: 0.42, align: 'center', valign: 'middle',
      fontSize: 13, bold: true, color: WHITE }));
    s.addText(t, tx({ x: x + 0.84, y: 4.55, w: 2.8, h: 0.42, fontSize: 14, bold: true, color: DARK, valign: 'middle' }));
    s.addText(d, tx({ x: x + 0.28, y: 5.16, w: 3.3, h: 1.35, fontSize: 12, color: MUTED, lineSpacing: 17 }));
  });
  
  s.addNotes('교육과정은 개선 계획을 세 갈래로 나눴습니다. 개정 내용 반영, 놀이 중심 수업 설계, 아동권리와 다양성 교육입니다.');
}
areaSlide(AREAS[2]);

/* 9 ─ 컨설팅 · 환류 */
{
  const s = p.addSlide();
  head(s, '컨설팅 및 결과 환류 계획');
  const steps = [['자체점검', '4개 영역 지표 점검\n만족도·강사 자체평가'],
                 ['개선계획 수립', '영역별 과제에\n담당자·추진 시기 지정'],
                 ['공유 · 반영', '강사 전체 회의 공유\n교안·수업 설계 반영'],
                 ['학기말 재점검', '이행 여부 확인 후\n다음 점검으로 연결']];
  steps.forEach(([t, d], i) => {
    const x = 0.62 + i * 3.15;
    s.addShape(p.ShapeType.roundRect, { x, y: 1.8, w: 2.75, h: 2.2, rectRadius: 0.08,
      fill: { color: i === 3 ? LIGHT : WHITE }, line: { color: i === 3 ? MOSS : LINE, width: i === 3 ? 2 : 1 } });
    s.addText(`0${i + 1}`, tx({ x: x + 0.28, y: 2.08, w: 1, h: 0.3, fontSize: 12, bold: true, color: MOSS }));
    s.addText(t, tx({ x: x + 0.28, y: 2.45, w: 2.2, h: 0.38, fontSize: 15, bold: true, color: DARK }));
    s.addText(d, tx({ x: x + 0.28, y: 2.92, w: 2.25, h: 0.85, fontSize: 12, color: MUTED, lineSpacing: 16 }));
    if (i < 3) s.addText('▶', tx({ x: x + 2.79, y: 2.75, w: 0.34, h: 0.3, fontSize: 12,
      color: MOSS, align: 'center' }));
  });
  s.addShape(p.ShapeType.roundRect, { x: 0.62, y: 4.4, w: 6.1, h: 2.0, rectRadius: 0.08,
    fill: { color: 'FDF6EA' }, line: { color: 'F0E0C6', width: 1 } });
  s.addText('컨설팅  □ 진행   ■ 미진행', tx({ x: 0.92, y: 4.68, w: 5.5, h: 0.35,
    fontSize: 14, bold: true, color: AMBER }));
  s.addText('1학기에는 자체점검을 중심으로 운영해 외부 컨설팅은 진행하지 않았습니다. 도출된 개선과제에 대해 2학기 중 관계 기관에 컨설팅을 신청해 자문을 받고 개선계획에 반영하겠습니다.',
    tx({ x: 0.92, y: 5.12, w: 5.5, h: 1.1, fontSize: 12, color: INK, lineSpacing: 17 }));
  s.addShape(p.ShapeType.roundRect, { x: 7.05, y: 4.4, w: 5.68, h: 2.0, rectRadius: 0.08,
    fill: { color: LIGHT }, line: { color: LINE, width: 1 } });
  s.addText('결과 활용', tx({ x: 7.35, y: 4.68, w: 5, h: 0.35, fontSize: 14, bold: true, color: GREEN }));
  s.addText(bullets(['만족도·요구도 조사 결과를 다음 학기 교육계획 수립의 기초 자료로 활용',
                     '보건복지부·한국보육진흥원 지침 개정 시 즉시 교육과정과 절차에 반영'],
                    { fontSize: 12, gap: 6 }),
    tx({ x: 7.35, y: 5.12, w: 5.1, h: 1.1 }));
  s.addNotes('점검이 한 번으로 끝나지 않도록 개선계획 수립부터 학기말 재점검까지 순환 구조로 운영하겠습니다.');
}

/* 10 ─ 마무리 */
{
  const s = p.addSlide();
  s.background = { color: DARK };
  s.addShape(p.ShapeType.ellipse, { x: -1.4, y: 5.1, w: 3.6, h: 3.6, fill: { color: '25543A' } });
  s.addText('현장에서 바로 쓰이는 보수교육', tx({
    x: 1.0, y: 2.25, w: 11, h: 0.9, fontSize: 34, bold: true, color: WHITE }));
  [['강점은 유지', '현장 적용성과 강사 전문성, 신속한 개정 반영'],
   ['과제는 실행', '4개 영역 개선과제를 2026년 2학기 중 추진'],
   ['점검은 순환', '학기말 재점검으로 다음 자체점검과 연결']].forEach(([t, d], i) => {
    const y = 3.75 + i * 0.98;
    s.addText(t, tx({ x: 1.0, y, w: 2.6, h: 0.45, fontSize: 17, bold: true, color: MOSS, valign: 'middle' }));
    s.addText(d, tx({ x: 3.7, y, w: 8.4, h: 0.45, fontSize: 15, color: 'D6E2D2', valign: 'middle' }));
  });
  s.addText('가천대학교부설평생교육원(메디컬)', tx({
    x: 1.0, y: 6.6, w: 8, h: 0.4, fontSize: 12, color: '8FA68C' }));
  s.addNotes('마무리 메시지입니다. 강점은 유지하고, 도출된 과제는 2학기에 실행하며, 점검이 순환되도록 하겠습니다.');
}

p.writeFile({ fileName: process.argv[2] }).then(f => console.log('작성 완료:', f));
