const fs = require('fs');
const d = require('docx');
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, WidthType,
        AlignmentType, VerticalAlign, ShadingType, ShadingType: ST, BorderStyle, VerticalMergeType } = d;

const C = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const FONT = '맑은 고딕';
const W = [1870, 2313, 5456];          // 원본 표의 열 너비 비율 그대로
const TOTAL = W[0] + W[1] + W[2];

const border = { style: BorderStyle.SINGLE, size: 4, color: '000000' };
const BORDERS = { top: border, bottom: border, left: border, right: border };

function run(text, opt = {}) {
  return new TextRun({ text, font: FONT, size: opt.size || 19, bold: !!opt.bold });
}

// [미흡사항] · [개선계획] 처럼 앞머리 표지가 있으면 그 부분만 굵게
function bodyPara(text, opt = {}) {
  const m = text.match(/^(\[[^\]]+\]|○)\s*/);
  const children = m
    ? [run(m[0], { bold: true }), run(text.slice(m[0].length))]
    : [run(text)];
  return new Paragraph({
    children,
    spacing: { line: 300, after: opt.after === undefined ? 100 : opt.after },
    indent: m ? { left: 260, hanging: 260 } : undefined,
    alignment: AlignmentType.LEFT,   // 좁은 칸에서 양쪽정렬을 쓰면 글자 사이가 벌어져 보인다
  });
}

function cell(paras, opt = {}) {
  return new TableCell({
    width: { size: opt.width, type: WidthType.DXA },
    columnSpan: opt.span,
    verticalMerge: opt.merge,
    verticalAlign: opt.middle ? VerticalAlign.CENTER : VerticalAlign.TOP,
    shading: opt.shade ? { type: ShadingType.CLEAR, fill: opt.shade, color: 'auto' } : undefined,
    margins: { top: 90, bottom: 90, left: 110, right: 110 },
    children: paras,
  });
}

function label(text, opt = {}) {
  return cell([new Paragraph({
    children: [run(text, { bold: true })],
    alignment: opt.left ? AlignmentType.LEFT : AlignmentType.CENTER,
    spacing: { line: 280 },
  })], { width: opt.width, middle: true, shade: opt.shade, merge: opt.merge, span: opt.span });
}

function body(list, width, span) {
  return cell(list.map((t, i) => bodyPara(t, { after: i === list.length - 1 ? 0 : 100 })),
              { width, span });
}

// ── 기관명 표 ────────────────────────────────────────────────
const head = new Table({
  columnWidths: [3350, 6289],
  width: { size: 9639, type: WidthType.DXA },
  borders: BORDERS,
  rows: [new TableRow({ children: [
    label('기관명', { width: 3350, shade: 'F2F2F2' }),
    label('가천대학교부설평생교육원(메디컬)', { width: 6289 }),
  ]})],
});

// ── 종합평가 표 ──────────────────────────────────────────────
const rows = [];
rows.push(new TableRow({ tableHeader: true, children: [
  label('구분', { width: W[0], shade: 'F2F2F2' }),
  label('종합 평가', { width: W[1] + W[2], span: 2, shade: 'F2F2F2' }),
]}));
rows.push(new TableRow({ children: [
  label('강점 및\n우수한 점'.replace('\n', ' '), { width: W[0] }),
  body(C['강점'], W[1] + W[2], 2),
]}));

const areas = [['□ 1영역. 기본환경', '영역1'], ['□ 2영역. 교육운영', '영역2'],
               ['□ 3영역. 교육과정', '영역3'], ['□ 4영역. 기관운영', '영역4']];
areas.forEach(([name, key], i) => {
  rows.push(new TableRow({ children: [
    i === 0 ? label('미흡 및 개선점', { width: W[0], merge: VerticalMergeType.RESTART })
            : cell([new Paragraph('')], { width: W[0], merge: VerticalMergeType.CONTINUE }),
    label(name, { width: W[1], left: true }),
    body(C[key], W[2]),
  ]}));
});

rows.push(new TableRow({ children: [
  label('컨설팅', { width: W[0] }),
  label('□ 진행   ■ 미진행', { width: W[1], left: true }),
  body(C['컨설팅'], W[2]),
]}));
rows.push(new TableRow({ children: [
  label('결과활용 방안 및 차후 환류사항', { width: W[0] }),
  body(C['환류'], W[1] + W[2], 2),
]}));

const main = new Table({
  columnWidths: W, width: { size: TOTAL, type: WidthType.DXA }, borders: BORDERS, rows,
});

const doc = new Document({
  styles: { default: { document: { run: { font: FONT, size: 19 } } } },
  sections: [{
    properties: { page: { margin: { top: 1134, bottom: 1134, left: 1134, right: 1134 } } },
    children: [
      new Paragraph({ children: [run('2026년 보육교직원 보수교육기관 자율관리(자체점검) 종합평가', { bold: true, size: 24 })],
                      alignment: AlignmentType.CENTER, spacing: { after: 240 } }),
      head,
      new Paragraph({ children: [run('자율관리를 통해 발견된 기관의 강점 및 우수한 점과 미흡 및 개선사항을 기록해주세요.')],
                      spacing: { before: 160, after: 120 } }),
      main,
    ],
  }],
});

Packer.toBuffer(doc).then(b => { fs.writeFileSync(process.argv[3], b); console.log('작성 완료:', process.argv[3]); });
