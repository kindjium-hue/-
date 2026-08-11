/* 견적서 생성기 — 평수를 넣으면 회사 양식대로 채운다. 계산 규칙은 quote.py와 같다.
   요약 보기에서 단가를 고칠 수 있고, 칸의 너비를 재서 모바일 배치로 바꾼다. */

const PYEONG_TO_M2 = 3.3058;
const AMOUNT_STEP = 1000; // 조정한 금액은 1,000원 단위
const PRICE_UNIT = 10; // 조정한 단가는 10원 단위
const DIGITS = "영일이삼사오육칠팔구";
const SMALL_UNITS = ["", "십", "백", "천"];
const BIG_UNITS = ["", "만", "억", "조"];

const MOBILE_MAX = 620; // 이보다 좁으면 모바일 배치
const NARROW_MAX = 360; // 아이폰 SE처럼 아주 좁으면 글자를 한 단계 더 줄인다
const SHEET_PX = 718; // 견적서 폭 190mm를 픽셀로 환산한 값
const FIT_STEPS = [95, 90, 85, 80, 75, 70, 65, 60, 55, 50, 45, 40];

const BRANDS = {
  roof: {
    name: "청명옥상방수",
    biz: "254-11-02805",
    addr: "경기 용인시 기흥구 동백죽전대로 205 B202호 D065",
    category: "방수미장 공사업",
    owner: "송경훈",
    phone: "010-4156-4043",
    project: ["옥상", "바닥 방수"],
    notes: "notes-roof",
    items: [
      { name: "바탕면작업", key: "roof-base", perArea: true },
      { name: "고압세척", key: "roof-wash", perArea: true },
      { name: "크랙보수", key: "roof-crack", perArea: true },
      { name: "하도 방수코트", key: "roof-coat1", perArea: true, balance: true },
      { name: "중도 방수코트", key: "roof-coat2", perArea: true, balance: true },
      { name: "상도 방수코트", key: "roof-coat3", perArea: true, balance: true },
      { name: "폐기물처리", key: "roof-waste" },
      { name: "보양•청소", key: "roof-clean" },
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
    notes: "notes-wall",
    items: [
      { name: "크랙보수", key: "wall-crack", perArea: true, balance: true },
      { name: "표면 방수제 도포", key: "wall-coat", perArea: true, balance: true },
      { name: "스카이 차량", key: "wall-sky" },
      { name: "보양•청소", key: "wall-clean" },
      { name: "잡자재비용", key: "wall-etc" },
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
const sheetWrap = pick("sheet-wrap");
const summaryTab = pick("view-summary");
const sheetTab = pick("view-sheet");

/* 요약 보기에서 고친 단가. 비어 있으면 설정 패널 값을 쓴다. */
const overrides = {};
const cardNodes = [];
let builtFor = "";
let totalNode = null;
let finalNode = null;

const toNumber = (text) => {
  const cleaned = String(text || "").replace(/[^\d.]/g, "");
  const value = parseFloat(cleaned);
  return isFinite(value) ? value : 0;
};

const price = (key) => toNumber(root.getAttribute(`data-${key}`));
const priceOf = (key) => (key in overrides ? overrides[key] : price(key));

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

/** 품목마다 평수·단가로 줄을 만든다 (단가 0인 품목도 목록에는 남긴다) */
const buildRows = (brand, area) => {
  const rows = [];
  for (let i = 0; i < brand.items.length; i += 1) {
    const spec = brand.items[i];
    const quantity = spec.perArea ? area : 1;
    const unit = priceOf(spec.key);
    rows.push({
      name: spec.name,
      key: spec.key,
      balance: spec.balance === true,
      quantity: quantity,
      unit: unit,
      amount: Math.round(quantity * unit),
    });
  }
  return rows;
};

/** 견적서에 실제로 올라가는 줄 (수량·단가가 있는 것만) */
const billable = (rows) => {
  const out = [];
  for (let i = 0; i < rows.length; i += 1) {
    if (rows[i].quantity > 0 && rows[i].unit > 0) out.push(rows[i]);
  }
  return out;
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

/** 특이사항은 HTML에 적어 둔 문구를 그대로 옮겨 담는다 */
const renderNotes = (key) => {
  const lines = pick(key).children;
  const boxes = [pick("sheet-notes"), pick("card-notes")];
  for (let box = 0; box < boxes.length; box += 1) {
    boxes[box].innerHTML = "";
    for (let i = 0; i < lines.length; i += 1) {
      boxes[box].appendChild(lines[i].cloneNode(true));
    }
  }
};

const listItem = (name, calc, className) => {
  const li = document.createElement("li");
  li.className = className ? `iw-listitem ${className}` : "iw-listitem";
  const title = document.createElement("span");
  title.className = "iw-listitem__name";
  title.textContent = name;
  const detail = document.createElement("span");
  detail.className = "iw-listitem__calc";
  detail.textContent = calc;
  const money = document.createElement("b");
  money.className = "iw-listitem__amount";
  li.appendChild(title);
  li.appendChild(detail);
  li.appendChild(money);
  return li;
};

const onPrice = (event) => {
  overrides[event.target.getAttribute("data-price-key")] = toNumber(event.target.value);
  render();
};

/** 요약 보기의 품목 목록을 만든다 (단가 칸이 들어간다) */
const buildCardList = (rows) => {
  const list = pick("card-rows");
  list.innerHTML = "";
  cardNodes.length = 0;

  for (let i = 0; i < rows.length; i += 1) {
    const row = rows[i];
    const li = listItem(row.name, "", "");
    const calc = li.children[1];
    calc.textContent = "";

    const input = document.createElement("input");
    input.className = "iw-price";
    input.setAttribute("type", "text");
    input.setAttribute("inputmode", "numeric");
    input.setAttribute("aria-label", `${row.name} 단가`);
    input.setAttribute("data-price-key", row.key);
    input.value = row.unit > 0 ? String(row.unit) : "";
    if (row.balance && matchInput.checked) input.setAttribute("disabled", "");
    input.addEventListener("input", onPrice);

    const unit = document.createElement("span");
    unit.className = "iw-listitem__unit";
    calc.appendChild(input);
    calc.appendChild(unit);
    list.appendChild(li);
    cardNodes.push({ input: input, unit: unit, amount: li.children[2] });
  }

  totalNode = listItem("합계", "부가세 별도", "iw-listitem--total");
  finalNode = listItem("최종 네고 금액", "부가세 별도", "iw-listitem--final");
  list.appendChild(totalNode);
  list.appendChild(finalNode);
};

/** 만들어 둔 목록에 숫자만 다시 써넣는다 (입력 중인 칸은 건드리지 않는다) */
const paintCards = (rows, subtotal, billed) => {
  for (let i = 0; i < cardNodes.length && i < rows.length; i += 1) {
    const node = cardNodes[i];
    const row = rows[i];
    const live = row.quantity > 0 && row.unit > 0;
    node.unit.textContent = row.quantity > 0 ? `원 × ${quantityText(row.quantity)}` : "원";
    node.amount.textContent = live ? `${won(row.amount)}원` : "-";
    if (node.input.getAttribute("disabled") !== null) {
      node.input.value = row.unit > 0 ? String(row.unit) : "";
    }
  }
  totalNode.children[2].textContent = subtotal > 0 ? `${won(subtotal)}원` : "-";
  finalNode.children[2].textContent = billed > 0 ? `${won(billed)}원` : "-";
};

const dateText = (value) => {
  const parts = String(value || "").split("-");
  if (parts.length !== 3) return "";
  return `${parts[0]} 년 ${Number(parts[1])} 월 ${Number(parts[2])}일`;
};

const renderCards = (rows, brand, subtotal, billed) => {
  const signature = `${workSelect.value}|${matchInput.checked ? 1 : 0}`;
  if (signature !== builtFor) {
    buildCardList(rows);
    builtFor = signature;
  }
  paintCards(rows, subtotal, billed);

  pick("card-won").textContent = billed > 0 ? `${won(billed)}원` : "-";
  pick("card-hangul").textContent = billed > 0 ? `일금 ${koreanAmount(billed)}원정` : "";
  pick("card-customer").textContent = customerInput.value.trim();
  pick("card-date").textContent = dateText(dateInput.value);
  pick("card-project").textContent = brand.project.join(" ");
  pick("card-company").textContent = brand.name;
  pick("card-biz").textContent = brand.biz;
  pick("card-owner").textContent = brand.owner;
  pick("card-phone").textContent = brand.phone;
};

const render = () => {
  const brand = BRANDS[workSelect.value] || BRANDS.roof;
  const area = toNumber(areaInput.value);
  const asked = toNumber(finalInput.value);

  areaHint.textContent = area > 0 ? `≈ ${(area * PYEONG_TO_M2).toFixed(1)}㎡` : "";

  const rows = buildRows(brand, area);
  const paid = billable(rows);
  let warning = "";
  if (matchInput.checked && asked > 0 && area > 0) {
    warning = matchToTotal(paid, asked);
  }
  warnBox.textContent = warning;
  warnBox.hidden = warning === "";

  let subtotal = 0;
  for (let i = 0; i < paid.length; i += 1) subtotal += paid[i].amount;
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
    subtotal > 0 ? `일금 ${koreanAmount(billed)}원정 ₩${won(billed)}` : "";
  pick("sheet-subtotal").textContent = subtotal > 0 ? won(subtotal) : "";
  pick("sheet-final").textContent = subtotal > 0 ? won(billed) : "";

  renderRows(paid, brand.project);
  renderNotes(brand.notes);
  renderCards(rows, brand, subtotal, billed);
};

const resetPrices = () => {
  const keys = Object.keys(overrides);
  for (let i = 0; i < keys.length; i += 1) delete overrides[keys[i]];
  builtFor = "";
  render();
};

/** 양식이 칸 안에 들어오도록 축소 비율 클래스를 하나 골라 붙인다 */
const setFit = (width) => {
  for (let i = 0; i < FIT_STEPS.length; i += 1) {
    sheetWrap.classList.remove(`iw-fit${FIT_STEPS[i]}`);
  }
  if (width <= 0 || width >= SHEET_PX) return;
  const percent = Math.floor(((width - 2) / SHEET_PX) * 20) * 5;
  sheetWrap.classList.add(`iw-fit${Math.max(40, Math.min(95, percent))}`);
};

/** 위젯이 놓인 칸의 너비로 모바일 여부를 정한다 */
const applyWidth = () => {
  const width = root.offsetWidth || window.innerWidth || 0;
  if (width <= 0) return;
  if (width < MOBILE_MAX) root.classList.add("is-mobile");
  else root.classList.remove("is-mobile");
  if (width < NARROW_MAX) root.classList.add("is-narrow");
  else root.classList.remove("is-narrow");
  setFit(width);
};

const setView = (mode) => {
  root.setAttribute("data-view", mode);
  summaryTab.setAttribute("aria-pressed", mode === "summary" ? "true" : "false");
  sheetTab.setAttribute("aria-pressed", mode === "sheet" ? "true" : "false");
  applyWidth();
};

const openPanel = () => {
  root.setAttribute("data-state", "open");
  panel.hidden = false;
  gate.hidden = true;
  render();
  applyWidth();
  setView(root.offsetWidth > 0 && root.offsetWidth < MOBILE_MAX ? "summary" : "sheet");
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

  summaryTab.addEventListener("click", () => setView("summary"));
  sheetTab.addEventListener("click", () => setView("sheet"));
  pick("reset").addEventListener("click", resetPrices);

  const watched = [workSelect, customerInput, areaInput, finalInput, matchInput, dateInput];
  for (let i = 0; i < watched.length; i += 1) {
    watched[i].addEventListener("input", render);
    watched[i].addEventListener("change", render);
  }

  applyWidth();
  if (typeof ResizeObserver === "function") {
    const watcher = new ResizeObserver(() => applyWidth());
    watcher.observe(root);
  }
  window.addEventListener("resize", applyWidth);

  if (String(root.getAttribute("data-pin") || "").trim() === "") openPanel();
};

setup();
