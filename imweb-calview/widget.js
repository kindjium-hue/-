/* 청명 일정 달력 (아임웹 캘린더 형식) — 아임웹 기본 캘린더가 쓰는 자료를 그대로 읽어
   같은 모양의 달력으로 보여 주고, 기간별 표로도 정리한다.

   자료 출처:  POST /ajax/calendar_data.cm   보냄 board_code, start, end
               받음 [{ id, title, start, end, className }]
   board_code 는 아임웹 캘린더가 스스로 보내는 요청에서 얻거나, 페이지 안에서 찾는다. */

const DATA_URL = "/ajax/calendar_data.cm";
const DAY_NAMES = ["일", "월", "화", "수", "목", "금", "토"];
const MOBILE_MAX = 640;
const NARROW_MAX = 400;
const CELL_MAX = 4;

const root = document.querySelector("[data-calview-root]");
const pick = (name) => root.querySelector(`[data-${name}]`);
const setting = (name) => String(root.getAttribute(`data-${name}`) || "").trim();

const works = (() => {
  const parts = setting("works").split(",");
  const out = [];
  for (let i = 0; i < parts.length; i += 1) {
    const one = parts[i].trim();
    if (one !== "") out.push(one);
  }
  return out;
})();

const store = {};
let boardCode = setting("board-code");
let cursor = new Date();
let chosen = "";
let span = "month";
let loading = false;
let ready = false;
let selfCall = false;

/* ------------------------------------------------------------------ 날짜 */

const pad = (value) => `0${value}`.slice(-2);
const keyOf = (date) => `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
const todayKey = () => keyOf(new Date());
const fromKey = (key) => {
  const p = key.split("-");
  return new Date(Number(p[0]), Number(p[1]) - 1, Number(p[2]));
};
const addDays = (date, n) => new Date(date.getFullYear(), date.getMonth(), date.getDate() + n);
const weekStart = (date) => addDays(date, -date.getDay());
const longDate = (key) => {
  const d = fromKey(key);
  return `${d.getFullYear()}년 ${d.getMonth() + 1}월 ${d.getDate()}일 (${DAY_NAMES[d.getDay()]})`;
};
const shortDate = (key) => {
  const d = fromKey(key);
  return `${d.getMonth() + 1}/${d.getDate()} (${DAY_NAMES[d.getDay()]})`;
};

const datePart = (text) => {
  const found = String(text || "").match(/(\d{4})-(\d{1,2})-(\d{1,2})/);
  if (!found) return "";
  return `${found[1]}-${pad(Number(found[2]))}-${pad(Number(found[3]))}`;
};
const timePart = (text) => {
  const found = String(text || "").match(/(\d{1,2}):(\d{2})/);
  return found ? `${pad(Number(found[1]))}:${found[2]}` : "";
};

/* -------------------------------------------------------------- 일정 자료 */

const colorClass = (name) => {
  const text = String(name || "");
  const found = text.match(/(\d+)/);
  if (found) return `c${Number(found[1]) % 6}`;
  if (text === "") return "c9";
  let sum = 0;
  for (let i = 0; i < text.length; i += 1) sum += text.charCodeAt(i);
  return `c${sum % 6}`;
};

const tagsIn = (title) => {
  const out = [];
  for (let i = 0; i < works.length; i += 1) {
    if (String(title || "").indexOf(works[i]) >= 0) out.push(works[i]);
  }
  return out;
};

/** 아임웹이 준 한 줄을 우리 형식으로 */
const toItem = (row) => {
  const start = datePart(row.start);
  if (start === "") return null;
  let last = datePart(row.end) || start;
  const time = timePart(row.start);
  // 종일 일정의 끝날짜는 «다음 날»로 오는 관례가 있어 하루 당긴다
  if (last > start && timePart(row.end) === "" && time === "") last = keyOf(addDays(fromKey(last), -1));
  if (last < start) last = start;
  return {
    id: String(row.id || `${start}-${row.title}`),
    title: String(row.title || "").trim(),
    start: start,
    last: last,
    time: time,
    color: colorClass(row.className),
    tags: tagsIn(row.title),
  };
};

const keep = (rows) => {
  let added = 0;
  for (let i = 0; i < rows.length; i += 1) {
    const item = toItem(rows[i]);
    if (!item) continue;
    if (!store[item.id]) added += 1;
    store[item.id] = item;
  }
  return added;
};

const asRows = (data) => {
  if (Array.isArray(data)) return data;
  if (data && typeof data === "object") {
    const keys = ["data", "list", "value", "events", "result"];
    for (let i = 0; i < keys.length; i += 1) {
      if (Array.isArray(data[keys[i]])) return data[keys[i]];
    }
  }
  return [];
};

const onKey = (key) => {
  const out = [];
  const ids = Object.keys(store);
  for (let i = 0; i < ids.length; i += 1) {
    const item = store[ids[i]];
    if (item.start <= key && key <= item.last) out.push(item);
  }
  out.sort((a, b) => (a.time + a.title < b.time + b.title ? -1 : 1));
  return out;
};

const between = (from, to) => {
  const out = [];
  const ids = Object.keys(store);
  for (let i = 0; i < ids.length; i += 1) {
    const item = store[ids[i]];
    if (item.last >= from && item.start <= to) out.push(item);
  }
  out.sort((a, b) => (a.start + a.time < b.start + b.time ? -1 : 1));
  return out;
};

/* ---------------------------------------------------------- 아임웹에 물어보기 */

const say = (text, bad) => {
  const box = pick("status");
  box.textContent = text;
  if (bad) box.setAttribute("data-bad", "yes");
  else box.removeAttribute("data-bad");
};

const findBoardCode = () => {
  if (boardCode !== "") return boardCode;
  const html = document.documentElement.innerHTML;
  const found = html.match(/board_code["'\s:=]{1,8}["']?([A-Za-z0-9_-]{8,40})/);
  if (found) boardCode = found[1];
  return boardCode;
};

const ask = (from, to) => {
  const code = findBoardCode();
  if (code === "") {
    say("아임웹 캘린더를 찾지 못했습니다. 이 위젯을 캘린더와 같은 페이지에 두거나, "
      + "board_code 를 설정에 넣어 주세요.", true);
    return;
  }
  if (loading) return;
  loading = true;
  if (!ready) say("아임웹 캘린더에서 일정을 받아오고 있습니다…");

  const body = `board_code=${encodeURIComponent(code)}&start=${from}&end=${to}`;
  selfCall = true;
  const asking = fetch(DATA_URL, {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
      "X-Requested-With": "XMLHttpRequest",
    },
    body: body,
  });
  selfCall = false;
  asking
    .then((response) => {
      if (!response.ok) throw new Error(`${response.status}`);
      return response.json();
    })
    .then((data) => {
      loading = false;
      ready = true;
      keep(asRows(data));
      say(`아임웹 캘린더에서 일정 ${Object.keys(store).length}건을 읽었습니다.`);
      draw();
    })
    .catch((error) => {
      loading = false;
      if (Object.keys(store).length > 0) {
        say(`일정 ${Object.keys(store).length}건을 화면에서 읽었습니다. `
          + `(직접 조회는 실패: ${error.message || error})`);
      } else {
        say(`일정을 받아오지 못했습니다 (${error.message || error}). 캘린더와 같은 페이지인지 `
          + "확인해 주세요.", true);
      }
      draw();
    });
};

/** 아임웹 캘린더가 스스로 부르는 요청을 엿봐 board_code 와 일정을 함께 얻는다 */
const listen = () => {
  const realOpen = XMLHttpRequest.prototype.open;
  const realSend = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function (method, url) {
    this.calviewUrl = String(url || "");
    return realOpen.apply(this, arguments);
  };
  XMLHttpRequest.prototype.send = function (body) {
    if (String(this.calviewUrl || "").indexOf("calendar_data") >= 0) {
      const sent = typeof body === "string" ? body : "";
      const found = sent.match(/board_code=([^&]+)/);
      if (found && boardCode === "") boardCode = decodeURIComponent(found[1]);
      this.addEventListener("load", () => {
        let data = null;
        try { data = JSON.parse(this.responseText); } catch (error) { data = null; }
        if (!data) return;
        if (keep(asRows(data)) > 0 || !ready) {
          ready = true;
          say(`아임웹 캘린더에서 일정 ${Object.keys(store).length}건을 읽었습니다.`);
          draw();
        }
      });
    }
    return realSend.apply(this, arguments);
  };

  const realFetch = window.fetch;
  if (typeof realFetch !== "function") return;
  window.fetch = function (input, init) {
    const url = typeof input === "string" ? input : (input && input.url) || "";
    const mine = String(url).indexOf("calendar_data") >= 0;
    const options = init || {};
    if (mine && typeof options.body === "string" && boardCode === "") {
      const found = options.body.match(/board_code=([^&]+)/);
      if (found) boardCode = decodeURIComponent(found[1]);
    }
    const skip = selfCall;
    return realFetch.apply(this, arguments).then((response) => {
      if (!mine || skip) return response;
      response.clone().json().then((data) => {
        if (keep(asRows(data)) > 0) {
          ready = true;
          say(`아임웹 캘린더에서 일정 ${Object.keys(store).length}건을 읽었습니다.`);
          draw();
        }
      }, () => {});
      return response;
    });
  };
};

/* ---------------------------------------------------------------- 그리기 */

const openUrl = (key) => {
  const base = setting("calendar") !== "" ? setting("calendar") : location.pathname;
  return `${base}?d=${key}&view_type=month`;
};

const chip = (item) => {
  const el = document.createElement("span");
  el.className = `cv-chip cv-chip--${item.color}`;
  el.textContent = item.time !== "" ? `${item.time} ${item.title}` : item.title;
  return el;
};

const cellFor = (date, monthOf) => {
  const key = keyOf(date);
  const cell = document.createElement("button");
  cell.className = "cv-cell";
  cell.setAttribute("type", "button");
  if (monthOf !== null && date.getMonth() !== monthOf) cell.className += " cv-cell--pad";
  if (key === todayKey()) cell.className += " cv-cell--today";
  if (key === chosen) cell.className += " cv-cell--on";

  const num = document.createElement("span");
  num.className = "cv-num";
  if (date.getDay() === 0) num.className += " cv-num--sun";
  if (date.getDay() === 6) num.className += " cv-num--sat";
  num.textContent = String(date.getDate());
  cell.appendChild(num);

  const day = onKey(key);
  const limit = day.length > CELL_MAX ? CELL_MAX - 1 : day.length;
  for (let i = 0; i < limit; i += 1) cell.appendChild(chip(day[i]));
  if (day.length > limit) {
    const more = document.createElement("span");
    more.className = "cv-more";
    more.textContent = `+${day.length - limit}건 더`;
    cell.appendChild(more);
  }
  cell.addEventListener("click", () => {
    chosen = key;
    draw();
  });
  return cell;
};

const headRow = (grid, days, dates) => {
  for (let i = 0; i < days; i += 1) {
    const at = dates ? dates[i].getDay() : i;
    const head = document.createElement("div");
    head.className = "cv-head";
    if (at === 0) head.className += " cv-head--sun";
    if (at === 6) head.className += " cv-head--sat";
    head.textContent = dates
      ? `${dates[i].getMonth() + 1}/${dates[i].getDate()} ${DAY_NAMES[at]}`
      : DAY_NAMES[i];
    grid.appendChild(head);
  }
};

const drawGrid = () => {
  const box = pick("cal");
  box.textContent = "";
  const view = root.getAttribute("data-view");
  const grid = document.createElement("div");

  if (view === "day") {
    grid.className = "cv-grid cv-grid--day";
    headRow(grid, 1, [cursor]);
    grid.appendChild(cellFor(cursor, null));
  } else if (view === "week") {
    grid.className = "cv-grid cv-grid--week";
    const start = weekStart(cursor);
    const dates = [];
    for (let i = 0; i < 7; i += 1) dates.push(addDays(start, i));
    headRow(grid, 7, dates);
    for (let i = 0; i < 7; i += 1) grid.appendChild(cellFor(dates[i], null));
  } else {
    grid.className = "cv-grid";
    headRow(grid, 7, null);
    const first = new Date(cursor.getFullYear(), cursor.getMonth(), 1);
    const start = weekStart(first);
    for (let i = 0; i < 42; i += 1) grid.appendChild(cellFor(addDays(start, i), cursor.getMonth()));
  }
  box.appendChild(grid);
};

const period = () => {
  const view = root.getAttribute("data-view");
  if (view === "day") return longDate(keyOf(cursor));
  if (view === "week") {
    const start = weekStart(cursor);
    const end = addDays(start, 6);
    return `${start.getFullYear()}년 ${start.getMonth() + 1}월 ${start.getDate()}일 ~ ${end.getMonth() + 1}월 ${end.getDate()}일`;
  }
  return `${cursor.getFullYear()}년 ${cursor.getMonth() + 1}월`;
};

const itemCard = (item) => {
  const box = document.createElement("article");
  box.className = `cv-item cv-item--${item.color}`;

  const when = document.createElement("span");
  when.className = "cv-item__when";
  when.textContent = item.start === item.last
    ? (item.time !== "" ? item.time : "종일")
    : `${shortDate(item.start)} ~ ${shortDate(item.last)}`;
  box.appendChild(when);

  const name = document.createElement("span");
  name.className = "cv-item__name";
  name.textContent = item.title !== "" ? item.title : "(제목 없음)";
  box.appendChild(name);

  for (let i = 0; i < item.tags.length; i += 1) {
    const badge = document.createElement("span");
    badge.className = `cv-badge cv-badge--${colorClass(item.tags[i])}`;
    badge.textContent = item.tags[i];
    box.appendChild(badge);
  }

  const open = document.createElement("a");
  open.className = "cv-open";
  open.setAttribute("href", openUrl(item.start));
  open.setAttribute("target", "_blank");
  open.setAttribute("rel", "noopener");
  open.textContent = "열기";
  box.appendChild(open);
  return box;
};

const drawDay = () => {
  const list = pick("day-list");
  list.textContent = "";
  if (chosen === "") {
    pick("day-title").textContent = "날짜를 누르면 그날 일정이 보입니다";
    return;
  }
  const day = onKey(chosen);
  pick("day-title").textContent = `${longDate(chosen)} · ${day.length}건`;
  if (day.length === 0) {
    const none = document.createElement("p");
    none.className = "cv-empty";
    none.textContent = "이 날은 등록된 일정이 없습니다.";
    list.appendChild(none);
    return;
  }
  for (let i = 0; i < day.length; i += 1) list.appendChild(itemCard(day[i]));
};

/* ------------------------------------------------------------- 정리 표 */

const spanRange = () => {
  const now = new Date();
  if (span === "year") {
    return [keyOf(new Date(now.getFullYear(), 0, 1)), keyOf(new Date(now.getFullYear(), 11, 31))];
  }
  if (span === "quarter") {
    const from = new Date(cursor.getFullYear(), cursor.getMonth() - 1, 1);
    const to = new Date(cursor.getFullYear(), cursor.getMonth() + 2, 0);
    return [keyOf(from), keyOf(to)];
  }
  const from = new Date(cursor.getFullYear(), cursor.getMonth(), 1);
  const to = new Date(cursor.getFullYear(), cursor.getMonth() + 1, 0);
  return [keyOf(from), keyOf(to)];
};

const filtered = () => {
  const bounds = spanRange();
  const query = String(pick("search").value || "").trim();
  const tag = pick("pick").value;
  const rows = between(bounds[0], bounds[1]);
  const out = [];
  for (let i = 0; i < rows.length; i += 1) {
    const item = rows[i];
    if (query !== "" && item.title.indexOf(query) < 0) continue;
    if (tag !== "" && item.tags.indexOf(tag) < 0) continue;
    out.push(item);
  }
  return out;
};

const drawSheet = () => {
  const rows = filtered();
  const body = pick("rows");
  body.textContent = "";

  const counts = {};
  for (let i = 0; i < rows.length; i += 1) {
    const tags = rows[i].tags;
    for (let t = 0; t < tags.length; t += 1) counts[tags[t]] = (counts[tags[t]] || 0) + 1;
  }
  const parts = [];
  const names = Object.keys(counts);
  for (let i = 0; i < names.length; i += 1) parts.push(`${names[i]} ${counts[names[i]]}`);
  const bounds = spanRange();
  pick("sum").textContent = `${bounds[0]} ~ ${bounds[1]} · 모두 ${rows.length}건`
    + (parts.length > 0 ? ` · ${parts.join(" · ")}` : "");

  if (rows.length === 0) {
    const tr = document.createElement("tr");
    const td = document.createElement("td");
    td.className = "cv-td";
    td.setAttribute("colspan", "4");
    td.textContent = "해당하는 일정이 없습니다.";
    tr.appendChild(td);
    body.appendChild(tr);
    return;
  }

  for (let i = 0; i < rows.length; i += 1) {
    const item = rows[i];
    const tr = document.createElement("tr");
    const date = document.createElement("td");
    date.className = "cv-td cv-td--date";
    date.textContent = item.start === item.last
      ? `${item.start}${item.time !== "" ? ` ${item.time}` : ""}`
      : `${item.start} ~ ${item.last}`;
    const name = document.createElement("td");
    name.className = "cv-td cv-td--name";
    name.textContent = item.title;
    const tags = document.createElement("td");
    tags.className = "cv-td";
    tags.textContent = item.tags.join(", ");
    const go = document.createElement("td");
    go.className = "cv-td";
    const link = document.createElement("a");
    link.className = "cv-open";
    link.setAttribute("href", openUrl(item.start));
    link.setAttribute("target", "_blank");
    link.setAttribute("rel", "noopener");
    link.textContent = "열기";
    go.appendChild(link);
    tr.appendChild(date);
    tr.appendChild(name);
    tr.appendChild(tags);
    tr.appendChild(go);
    body.appendChild(tr);
  }
};

const copySheet = () => {
  const rows = filtered();
  const lines = ["날짜\t일정\t작업항목"];
  for (let i = 0; i < rows.length; i += 1) {
    const item = rows[i];
    const when = item.start === item.last
      ? `${item.start}${item.time !== "" ? ` ${item.time}` : ""}`
      : `${item.start} ~ ${item.last}`;
    lines.push(`${when}\t${item.title}\t${item.tags.join(", ")}`);
  }
  const text = lines.join("\n");
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(
      () => { pick("sum").textContent = `표 ${rows.length}줄을 복사했습니다. 엑셀에 붙여넣으세요.`; },
      () => { pick("sum").textContent = "복사가 막혔습니다. 표를 직접 선택해 복사해 주세요."; }
    );
    return;
  }
  pick("sum").textContent = "이 브라우저에서는 복사가 안 됩니다. 표를 직접 선택해 주세요.";
};

/* -------------------------------------------------------------- 움직임 */

const draw = () => {
  pick("period").textContent = period();
  drawGrid();
  drawDay();
  drawSheet();
};

const need = () => {
  const view = root.getAttribute("data-view");
  let from = "";
  let to = "";
  if (view === "day") {
    from = keyOf(addDays(cursor, -1));
    to = keyOf(addDays(cursor, 1));
  } else if (view === "week") {
    from = keyOf(weekStart(cursor));
    to = keyOf(addDays(weekStart(cursor), 6));
  } else {
    const first = new Date(cursor.getFullYear(), cursor.getMonth(), 1);
    from = keyOf(weekStart(first));
    to = keyOf(addDays(weekStart(first), 41));
  }
  const bounds = spanRange();
  if (bounds[0] < from) from = bounds[0];
  if (bounds[1] > to) to = bounds[1];
  ask(from, to);
};

const setView = (mode) => {
  root.setAttribute("data-view", mode);
  pick("view-day").setAttribute("aria-pressed", mode === "day" ? "true" : "false");
  pick("view-week").setAttribute("aria-pressed", mode === "week" ? "true" : "false");
  pick("view-month").setAttribute("aria-pressed", mode === "month" ? "true" : "false");
  draw();
  need();
};

const setSpan = (mode) => {
  span = mode;
  pick("span-month").setAttribute("aria-pressed", mode === "month" ? "true" : "false");
  pick("span-quarter").setAttribute("aria-pressed", mode === "quarter" ? "true" : "false");
  pick("span-year").setAttribute("aria-pressed", mode === "year" ? "true" : "false");
  drawSheet();
  need();
};

const move = (step) => {
  const view = root.getAttribute("data-view");
  if (view === "day") cursor = addDays(cursor, step);
  else if (view === "week") cursor = addDays(cursor, 7 * step);
  else cursor = new Date(cursor.getFullYear(), cursor.getMonth() + step, 1);
  draw();
  need();
};

const applyWidth = () => {
  const width = root.offsetWidth || window.innerWidth || 0;
  if (width <= 0) return;
  if (width < MOBILE_MAX) root.classList.add("is-mobile");
  else root.classList.remove("is-mobile");
  if (width < NARROW_MAX) root.classList.add("is-narrow");
  else root.classList.remove("is-narrow");
};

const setup = () => {
  if (!root) return;
  listen();

  const box = pick("pick");
  const all = document.createElement("option");
  all.setAttribute("value", "");
  all.textContent = "작업항목 전체";
  box.appendChild(all);
  for (let i = 0; i < works.length; i += 1) {
    const option = document.createElement("option");
    option.setAttribute("value", works[i]);
    option.textContent = works[i];
    box.appendChild(option);
  }

  chosen = todayKey();
  pick("prev").addEventListener("click", () => move(-1));
  pick("next").addEventListener("click", () => move(1));
  pick("today").addEventListener("click", () => {
    cursor = new Date();
    chosen = todayKey();
    draw();
    need();
  });
  pick("view-day").addEventListener("click", () => setView("day"));
  pick("view-week").addEventListener("click", () => setView("week"));
  pick("view-month").addEventListener("click", () => setView("month"));
  pick("span-month").addEventListener("click", () => setSpan("month"));
  pick("span-quarter").addEventListener("click", () => setSpan("quarter"));
  pick("span-year").addEventListener("click", () => setSpan("year"));
  pick("search").addEventListener("input", drawSheet);
  pick("pick").addEventListener("change", drawSheet);
  pick("copy").addEventListener("click", copySheet);

  draw();
  applyWidth();
  if (typeof ResizeObserver === "function") {
    const watcher = new ResizeObserver(() => applyWidth());
    watcher.observe(root);
  }
  window.addEventListener("resize", applyWidth);

  // 아임웹 캘린더가 먼저 자료를 받아오도록 조금 기다린 뒤 직접도 물어본다
  setTimeout(need, 1200);
};

setup();
