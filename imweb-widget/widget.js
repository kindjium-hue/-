/* 견적서 생성기 — 평수를 넣으면 회사 양식대로 견적서를 채운다.
   금액 계산은 파이썬 생성기(quote.py)와 같은 규칙을 쓴다. */

const PYEONG_TO_M2 = 3.3058;
const AMOUNT_STEP = 1000; // 조정한 금액은 1,000원 단위
const PRICE_UNIT = 10; // 조정한 단가는 10원 단위
const DIGITS = "영일이삼사오육칠팔구";
const SMALL_UNITS = ["", "십", "백", "천"];
const BIG_UNITS = ["", "만", "억", "조"];

const BRANDS = {
  roof: {
    name: "청명옥상방수",
    biz: "254-11-02805",
    addr: "경기 용인시 기흥구 동백죽전대로 205 B202호 D065",
    category: "방수미장 공사업",
    owner: "송경훈",
    phone: "010-4156-4043",
    project: ["옥상", "바닥 방수"],
    notes: [
      "* 공사명: 옥상 방수 공사",
      "* 공사일자: 협의(1-2일 소요)",
      "* 작업방법: 바탕면 정리 → 고압세척 → 프라이머 → 크랙보수 → 하도 작업 → 중도 작업 → 상도작업 → 검수",
      "* 보증기간: 작업구간에 한하여 2년 보증. (다른 부분에 의한 누수는 제외)",
    ],
    items: [
      { name: "바탕면작업", key: "roof-base", perArea: true },
      { name: "고압세척", key: "roof-wash", perArea: true },
      { name: "크랙보수", key: "roof-crack", perArea: true },
      { name: "하도 방수코트", key: "roof-coat1", perArea: true, balance: true },
      { name: "중도 방수코트", key: "roof-coat2", perArea: true, balance: true },
      { name: "상도 방수코트", key: "roof-coat3", perArea: true, balance: true },
      { name: "폐기물처리", key: "roof-waste", perArea: false },
      { name: "보양•청소", key: "roof-clean", perArea: false },
    ],
  },
  wall: {
    name: "청명종합설비",
    biz: "552-08-01511",
    addr: "권선구 서호동로26번길 19 3층 302-A1호",
    category: "방수미장 공사업",
    owner: "송경훈",
    phone: "010-4156-4043",
    project: ["외벽방수"],
    notes: [
      "* 공사명: 외벽 방수 공사",
      "* 공사일자: 협의(1-2일 소요)",
      "* 작업방법: 바탕면 정리 → 프라이머 → 크랙보수 → 표면방수제 → 구조 보강 작업",
      "* 보증기간: 작업구간에 한하여 2년 보증. (다른 부분에 의한 누수는 제외)",
    ],
    items: [
      { name: "크랙보수", key: "wall-crack", perArea: true, balance: true },
      { name: "표면 방수제 도포", key: "wall-coat", perArea: true, balance: true },
      { name: "스카이 차량", key: "wall-sky", perArea: false },
      { name: "보양•청소", key: "wall-clean", perArea: false },
      { name: "잡자재비용", key: "wall-etc", perArea: false },
    ],
  },
};

const root = document.querySelector("[data-quote-root]");

const pick = (name) => root.querySelector(`[data-${name}]`);
const gate = pick("gate");
const panel = pick("panel");
const pinInput = pick("pin-input");
const pinError = pick("pin-error");
const workSelect = pick("work");
const customerInput = pick("customer");
const areaInput = pick("area");
const finalInput = pick("final");
const matchInput = pick("match");
const dateInput = pick("date");
const areaHint = pick("area-hint");
const warnBox = pick("warn");
const formLink = pick("form-link");

const toNumber = (text) => {
  const cleaned = String(text || "").replace(/[^\d.]/g, "");
  const value = parseFloat(cleaned);
  return isFinite(value) ? value : 0;
};

const price = (key) => toNumber(root.getAttribute(`data-${key}`));

const won = (value) => Math.round(value).toLocaleString("ko-KR");

/** 1200000 → '일백이십만' (견적서 표기 방식) */
const koreanAmount = (value) => {
  let left = Math.round(value);
  if (left === 0) return "영";
  const groups = [];
  while (left > 0) {
    groups.push(left % 10000);
    left = Math.floor(left / 10000);
  }
  let text = "";
  for (let index = groups.length - 1; index >= 0; index -= 1) {
    const group = groups[index];
    if (group === 0) continue;
    let chunk = "";
    for (let pos = 3; pos >= 0; pos -= 1) {
      const digit = Math.floor(group / Math.pow(10, pos)) % 10;
      if (digit > 0) chunk += DIGITS[digit] + SMALL_UNITS[pos];
    }
    text += chunk + BIG_UNITS[index];
  }
  return text;
};

/** 평수와 단가로 견적 줄을 만든다 */
const buildRows = (brand, area) => {
  const rows = [];
  for (let i = 0; i < brand.items.length; i += 1) {
    const spec = brand.items[i];
    const quantity = spec.perArea ? area : 1;
    const unit = price(spec.key);
    if (quantity <= 0 || unit <= 0) continue;
    rows.push({
      name: spec.name,
      balance: spec.balance === true,
      quantity: quantity,
      unit: unit,
      amount: Math.round(quantity * unit),
    });
  }
  return rows;
};

/** 최종 금액에 맞춰 조정 대상의 단가를 원래 비율대로 다시 나눈다 */
const matchToTotal = (rows, target) => {
  const picked = [];
  let fixed = 0;
  for (let i = 0; i < rows.length; i += 1) {
    if (rows[i].balance) picked.push(rows[i]);
    else fixed += rows[i].amount;
  }
  if (picked.length === 0) return "조정할 품목이 없습니다.";

  const room = target - fixed;
  if (room <= 0) {
    return `최종 금액이 조정하지 않는 항목 합계(${won(fixed)}원)보다 작습니다.`;
  }

  let weightSum = 0;
  let biggest = 0;
  for (let i = 0; i < picked.length; i += 1) {
    weightSum += picked[i].unit;
    if (picked[i].unit > picked[biggest].unit) biggest = i;
  }
  if (weightSum <= 0) return "조정할 품목의 단가가 0입니다.";

  let others = 0;
  for (let i = 0; i < picked.length; i += 1) {
    if (i === biggest) continue;
    const share = (room * picked[i].unit) / weightSum;
    picked[i].amount = Math.round(share / AMOUNT_STEP) * AMOUNT_STEP;
    others += picked[i].amount;
  }
  // 반올림 잔액은 비중이 가장 큰 품목(중도)이 흡수해 합계를 정확히 맞춘다
  picked[biggest].amount = room - others;

  for (let i = 0; i < picked.length; i += 1) {
    const perUnit = picked[i].amount / picked[i].quantity;
    picked[i].unit = Math.round(perUnit / PRICE_UNIT) * PRICE_UNIT;
  }
  return "";
};

const quantityText = (value) =>
  Number.isInteger(value) ? String(value) : String(Math.round(value * 100) / 100);

const cell = (text, className) => {
  const td = document.createElement("td");
  td.className = className;
  td.textContent = text;
  return td;
};

const renderRows = (rows, projectLines) => {
  const body = pick("sheet-rows");
  body.innerHTML = "";
  if (rows.length === 0) return;

  for (let i = 0; i < rows.length; i += 1) {
    const row = rows[i];
    const tr = document.createElement("tr");
    tr.className = "iw-item";
    if (i === 0) {
      const project = document.createElement("td");
      project.className = "iw-project";
      project.setAttribute("rowspan", String(rows.length));
      for (let line = 0; line < projectLines.length; line += 1) {
        const span = document.createElement("span");
        span.textContent = projectLines[line];
        project.appendChild(span);
      }
      tr.appendChild(project);
    }
    tr.appendChild(cell(row.name, "iw-td iw-name"));
    tr.appendChild(cell(quantityText(row.quantity), "iw-td"));
    tr.appendChild(cell(won(row.unit), "iw-td iw-td--num"));
    tr.appendChild(cell(won(row.amount), "iw-td iw-td--num"));
    tr.appendChild(cell("", "iw-td"));
    body.appendChild(tr);
  }

  const blank = document.createElement("tr");
  blank.className = "iw-blank";
  for (let i = 0; i < 5; i += 1) blank.appendChild(cell("", "iw-td"));
  body.appendChild(blank);
};

const renderNotes = (lines) => {
  const box = pick("sheet-notes");
  box.innerHTML = "";
  for (let i = 0; i < lines.length; i += 1) {
    const span = document.createElement("span");
    span.textContent = lines[i];
    box.appendChild(span);
  }
};

const dateText = (value) => {
  const parts = String(value || "").split("-");
  if (parts.length !== 3) return "";
  return `${parts[0]} 년 ${Number(parts[1])} 월 ${Number(parts[2])}일`;
};

const render = () => {
  const brand = BRANDS[workSelect.value] || BRANDS.roof;
  const area = toNumber(areaInput.value);
  const asked = toNumber(finalInput.value);

  areaHint.textContent = area > 0 ? `≈ ${(area * PYEONG_TO_M2).toFixed(1)}㎡` : "";

  const rows = buildRows(brand, area);
  let warning = "";
  if (matchInput.checked && asked > 0 && area > 0) {
    warning = matchToTotal(rows, asked);
  }
  warnBox.textContent = warning;
  warnBox.hidden = warning === "";

  let subtotal = 0;
  for (let i = 0; i < rows.length; i += 1) subtotal += rows[i].amount;
  const billed = asked > 0 ? asked : subtotal;

  pick("sheet-date").textContent = dateText(dateInput.value);
  const customer = customerInput.value.trim();
  pick("sheet-customer").textContent = customer ? `${customer} 귀중` : "";
  pick("sheet-biz").textContent = brand.biz;
  pick("sheet-company").textContent = brand.name;
  pick("sheet-addr").textContent = brand.addr;
  pick("sheet-category").textContent = brand.category;
  pick("sheet-owner").textContent = brand.owner;
  pick("sheet-phone").textContent = brand.phone;
  pick("sheet-hangul").textContent =
    area > 0 ? `일금 ${koreanAmount(billed)}원정 ₩${won(billed)}` : "";
  pick("sheet-subtotal").textContent = area > 0 ? won(subtotal) : "";
  pick("sheet-final").textContent = area > 0 ? won(billed) : "";

  renderRows(rows, brand.project);
  renderNotes(brand.notes);
};

const openPanel = () => {
  root.setAttribute("data-state", "open");
  panel.hidden = false;
  gate.hidden = true;
  render();
};

const checkPin = () => {
  const wanted = String(root.getAttribute("data-pin") || "").trim();
  const typed = String(pinInput.value || "").trim();
  if (wanted === "" || typed === wanted) {
    pinError.hidden = true;
    openPanel();
    return;
  }
  pinError.hidden = false;
};

const today = () => {
  const now = new Date();
  const month = `0${now.getMonth() + 1}`.slice(-2);
  const day = `0${now.getDate()}`.slice(-2);
  return `${now.getFullYear()}-${month}-${day}`;
};

const setup = () => {
  if (!root) return;

  dateInput.value = today();

  const formUrl = String(root.getAttribute("data-form-url") || "").trim();
  if (formUrl.indexOf("http") === 0) {
    formLink.setAttribute("href", formUrl);
    formLink.hidden = false;
  }

  pick("pin-submit").addEventListener("click", checkPin);
  pinInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") checkPin();
  });

  const watched = [workSelect, customerInput, areaInput, finalInput, matchInput, dateInput];
  for (let i = 0; i < watched.length; i += 1) {
    watched[i].addEventListener("input", render);
    watched[i].addEventListener("change", render);
  }

  if (String(root.getAttribute("data-pin") || "").trim() === "") openPanel();
};

setup();
