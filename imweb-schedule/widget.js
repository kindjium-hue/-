/* 청명 일정 달력 — 아임웹 게시판에 쌓인 일정 글을 읽어 월간·주간 달력으로 보여 준다.
   글 제목 규칙:  날짜 시간 | 작업항목 | 현장명 | 담당자 | 장소 | 진행상태
   예) 2026-08-14 09:00 | 옥상방수, 누수탐지 | 카카오프렌즈 지곡점 | 송경훈 | 수원 권선구 | 예정 */

const DAY_NAMES = ["일", "월", "화", "수", "목", "금", "토"];
const STATES = ["예정", "진행중", "완료", "보류", "취소"];
const TITLE_HEAD = /(\d{4})-(\d{1,2})-(\d{1,2})(?:\s+(\d{1,2}):(\d{2}))?\s*\|/;
const SKIP_IMAGE = /icon|logo|blank|sprite|btn_|profile/i;
const MOBILE_MAX = 620;
const NARROW_MAX = 380;

const root = document.querySelector("[data-schedule-root]");
const pick = (name) => root.querySelector(`[data-${name}]`);

const setting = (name) => String(root.getAttribute(`data-${name}`) || "").trim();
const listOf = (name) => {
  const parts = setting(name).split(",");
  const out = [];
  for (let i = 0; i < parts.length; i += 1) {
    const value = parts[i].trim();
    if (value !== "") out.push(value);
  }
  return out;
};

const works = listOf("works");
const owners = listOf("owners");

let items = [];
let cursor = new Date();
let chosen = "";
let loading = false;
let boardOk = false;

/* ------------------------------------------------------------------ 날짜 */

const pad = (value) => `0${value}`.slice(-2);
const keyOf = (date) => `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
const todayKey = () => keyOf(new Date());
const addDays = (date, count) => new Date(date.getFullYear(), date.getMonth(), date.getDate() + count);
const weekStart = (date) => addDays(date, -date.getDay());
const fromKey = (key) => {
  const parts = key.split("-");
  return new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]));
};
const longDate = (key) => {
  const date = fromKey(key);
  return `${date.getFullYear()}년 ${date.getMonth() + 1}월 ${date.getDate()}일 (${DAY_NAMES[date.getDay()]})`;
};

/* -------------------------------------------------------- 게시판 글 읽기 */

const workClass = (name) => {
  const at = works.indexOf(name);
  return at >= 0 && at < 6 ? `w${at}` : "w9";
};

/** 제목 한 줄을 일정으로 바꾼다. 규칙에 맞지 않으면 null */
const parseTitle = (text) => {
  const clean = String(text || "").replace(/\s+/g, " ").trim();
  const found = clean.match(TITLE_HEAD);
  if (!found) return null;

  const parts = clean.slice(found.index).split("|");
  const head = parts[0].trim().split(/\s+/);
  const day = head[0].split("-");
  const picked = [];
  const names = (parts[1] || "").split(/[,·+/]/);
  for (let i = 0; i < names.length; i += 1) {
    const name = names[i].trim();
    if (name !== "") picked.push(name);
  }
  const state = (parts[5] || "").trim();

  return {
    key: `${day[0]}-${pad(Number(day[1]))}-${pad(Number(day[2]))}`,
    time: head.length > 1 ? head[1] : "",
    works: picked,
    site: (parts[2] || "").trim(),
    owner: (parts[3] || "").trim(),
    place: (parts[4] || "").trim(),
    state: STATES.indexOf(state) >= 0 ? state : "",
    url: "",
    shots: null,
  };
};

/** 게시판 목록 HTML에서 일정 글을 골라낸다 */
const readList = (html, seen) => {
  const doc = new DOMParser().parseFromString(html, "text/html");
  const links = doc.querySelectorAll("a[href]");
  const found = [];
  for (let i = 0; i < links.length; i += 1) {
    const link = links[i];
    const item = parseTitle(link.textContent);
    if (!item) continue;
    const href = link.getAttribute("href") || "";
    if (href !== "" && seen[href] === true) continue;
    if (href !== "") seen[href] = true;
    item.url = href;
    found.push(item);
  }
  return { items: found, links: links.length };
};

const pageUrl = (base, page) => {
  if (page <= 1) return base;
  return base + (base.indexOf("?") >= 0 ? "&" : "?") + `page=${page}`;
};

const say = (text, bad) => {
  const box = pick("status");
  box.textContent = text;
  if (bad) box.setAttribute("data-bad", "yes");
  else box.removeAttribute("data-bad");
};

const load = () => {
  const base = setting("board");
  if (base === "") {
    say("게시판 주소가 비어 있습니다. 위젯 설정에서 일정 게시판 주소를 넣어 주세요.", true);
    return;
  }
  if (loading) return;
  loading = true;
  say("일정을 읽고 있습니다…");

  const pages = Math.max(1, Math.min(10, Number(setting("pages")) || 1));
  const seen = {};
  const gathered = [];
  let links = 0;
  let failed = "";

  const step = (page) => {
    if (page > pages) {
      loading = false;
      boardOk = failed === "";
      setWriteLink();
      items = gathered;
      items.sort((a, b) => (a.key + a.time < b.key + b.time ? -1 : 1));
      if (items.length > 0) {
        say(`게시판에서 일정 ${items.length}개를 읽었습니다.`);
      } else if (failed !== "") {
        say(`게시판을 읽지 못했습니다 (${failed}). 주소가 맞는지, 같은 사이트 안의 주소인지 확인해 주세요.`, true);
      } else {
        say(`게시판은 열렸지만(링크 ${links}개) 규칙에 맞는 일정 글이 없습니다. `
          + "글 제목이 «2026-08-14 09:00 | 옥상방수 | 현장명 | 담당자 | 장소 | 예정» 형태인지 확인해 주세요.", true);
      }
      draw();
      return;
    }
    fetch(pageUrl(base, page), { credentials: "same-origin" })
      .then((response) => {
        if (!response.ok) throw new Error(`${response.status}`);
        return response.text();
      })
      .then((html) => {
        const batch = readList(html, seen);
        links += batch.links;
        for (let i = 0; i < batch.items.length; i += 1) gathered.push(batch.items[i]);
        step(page + 1);
      })
      .catch((error) => {
        if (failed === "") failed = String(error.message || error);
        step(pages + 1);
      });
  };
  step(1);
};

/* -------------------------------------------------------------- 사진 읽기 */

const readShots = (html) => {
  const doc = new DOMParser().parseFromString(html, "text/html");
  const walker = doc.createTreeWalker(doc.body, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
  const shots = [];
  let tag = "사진";
  while (walker.nextNode()) {
    const node = walker.currentNode;
    if (node.nodeType === 3) {
      const text = node.nodeValue.toUpperCase();
      if (text.indexOf("BEFORE") >= 0) tag = "BEFORE";
      else if (text.indexOf("AFTER") >= 0) tag = "AFTER";
    } else if (node.tagName === "IMG") {
      const src = node.getAttribute("src") || "";
      const width = Number(node.getAttribute("width") || 0);
      if (src === "" || SKIP_IMAGE.test(src) || (width > 0 && width < 60)) continue;
      shots.push({ tag: tag, src: node.src || src });
    }
  }
  return shots;
};

const showShots = (item, box, button) => {
  button.textContent = "사진 불러오는 중…";
  fetch(item.url, { credentials: "same-origin" })
    .then((response) => response.text())
    .then((html) => {
      item.shots = readShots(html);
      button.textContent = item.shots.length > 0 ? "사진" : "사진 없음";
      paintShots(item, box);
    })
    .catch(() => {
      button.textContent = "사진을 읽지 못했습니다";
    });
};

const paintShots = (item, box) => {
  box.textContent = "";
  if (!item.shots) return;
  for (let i = 0; i < item.shots.length; i += 1) {
    const shot = item.shots[i];
    const wrap = document.createElement("div");
    wrap.className = "cs-shot";
    const image = document.createElement("img");
    image.setAttribute("src", shot.src);
    image.setAttribute("alt", `${item.site} ${shot.tag}`);
    image.setAttribute("loading", "lazy");
    const tag = document.createElement("span");
    tag.className = "cs-shot__tag";
    tag.textContent = shot.tag;
    wrap.appendChild(image);
    wrap.appendChild(tag);
    box.appendChild(wrap);
  }
};

/* ---------------------------------------------------------------- 그리기 */

const onKey = (key) => {
  const out = [];
  for (let i = 0; i < items.length; i += 1) if (items[i].key === key) out.push(items[i]);
  return out;
};

const chipText = (item) => {
  const head = item.time !== "" ? `${item.time} ` : "";
  const name = item.site !== "" ? item.site : (item.works[0] || "일정");
  return `${head}${name}`;
};

const chip = (item) => {
  const span = document.createElement("span");
  span.className = `cs-chip cs-chip--${workClass(item.works[0] || "")}`;
  span.textContent = chipText(item);
  return span;
};

const monthView = (box) => {
  const grid = document.createElement("div");
  grid.className = "cs-grid";
  for (let i = 0; i < 7; i += 1) {
    const head = document.createElement("div");
    head.className = "cs-head";
    if (i === 0) head.className += " cs-head--sun";
    if (i === 6) head.className += " cs-head--sat";
    head.textContent = DAY_NAMES[i];
    grid.appendChild(head);
  }

  const first = new Date(cursor.getFullYear(), cursor.getMonth(), 1);
  const start = weekStart(first);
  const today = todayKey();
  for (let i = 0; i < 42; i += 1) {
    const date = addDays(start, i);
    const key = keyOf(date);
    const cell = document.createElement("button");
    cell.className = "cs-cell";
    cell.setAttribute("type", "button");
    if (date.getMonth() !== cursor.getMonth()) cell.className += " cs-cell--pad";
    if (key === today) cell.className += " cs-cell--today";
    if (key === chosen) cell.className += " cs-cell--on";

    const num = document.createElement("span");
    num.className = "cs-cell__num";
    if (date.getDay() === 0) num.className += " cs-cell__num--sun";
    if (date.getDay() === 6) num.className += " cs-cell__num--sat";
    num.textContent = String(date.getDate());
    cell.appendChild(num);

    const day = onKey(key);
    const limit = day.length > 3 ? 2 : day.length;
    for (let n = 0; n < limit; n += 1) cell.appendChild(chip(day[n]));
    if (day.length > limit) {
      const more = document.createElement("span");
      more.className = "cs-more";
      more.textContent = `+${day.length - limit}건`;
      cell.appendChild(more);
    }
    cell.addEventListener("click", () => choose(key));
    grid.appendChild(cell);
  }
  box.appendChild(grid);
};

const weekView = (box) => {
  const wrap = document.createElement("div");
  wrap.className = "cs-week";
  const start = weekStart(cursor);
  const today = todayKey();
  for (let i = 0; i < 7; i += 1) {
    const date = addDays(start, i);
    const key = keyOf(date);
    const row = document.createElement("button");
    row.className = "cs-wrow";
    row.setAttribute("type", "button");
    if (key === today) row.className += " cs-wrow--today";
    if (key === chosen) row.className += " cs-wrow--on";

    const label = document.createElement("span");
    label.className = "cs-wrow__day";
    label.textContent = `${date.getMonth() + 1}/${date.getDate()}`;
    const small = document.createElement("small");
    small.textContent = DAY_NAMES[date.getDay()];
    label.appendChild(small);

    const body = document.createElement("span");
    body.className = "cs-wrow__body";
    const day = onKey(key);
    if (day.length === 0) {
      const none = document.createElement("span");
      none.className = "cs-wrow__empty";
      none.textContent = "일정 없음";
      body.appendChild(none);
    }
    for (let n = 0; n < day.length; n += 1) body.appendChild(chip(day[n]));

    row.appendChild(label);
    row.appendChild(body);
    row.addEventListener("click", () => choose(key));
    wrap.appendChild(row);
  }
  box.appendChild(wrap);
};

const kv = (name, value) => {
  const line = document.createElement("div");
  line.className = "cs-kv";
  const label = document.createElement("span");
  label.textContent = name;
  const text = document.createElement("b");
  text.textContent = value;
  line.appendChild(label);
  line.appendChild(text);
  return line;
};

const card = (item) => {
  const box = document.createElement("article");
  box.className = `cs-item cs-item--${workClass(item.works[0] || "")}`;

  const top = document.createElement("div");
  top.className = "cs-item__top";
  if (item.time !== "") {
    const time = document.createElement("span");
    time.className = "cs-item__time";
    time.textContent = item.time;
    top.appendChild(time);
  }
  if (item.site !== "") {
    const site = document.createElement("span");
    site.className = "cs-item__site";
    site.textContent = item.site;
    top.appendChild(site);
  }
  for (let i = 0; i < item.works.length; i += 1) {
    const badge = document.createElement("span");
    badge.className = `cs-badge cs-badge--${workClass(item.works[i])}`;
    badge.textContent = item.works[i];
    top.appendChild(badge);
  }
  if (item.state !== "") {
    const state = document.createElement("span");
    state.className = "cs-state";
    state.textContent = item.state;
    top.appendChild(state);
  }
  box.appendChild(top);

  if (item.owner !== "") box.appendChild(kv("담당", item.owner));
  if (item.place !== "") box.appendChild(kv("장소", item.place));

  const shots = document.createElement("div");
  shots.className = "cs-shots";

  const foot = document.createElement("div");
  foot.className = "cs-item__foot";
  if (item.url !== "") {
    const open = document.createElement("a");
    open.className = "cs-ghost";
    open.setAttribute("href", item.url);
    open.setAttribute("target", "_blank");
    open.setAttribute("rel", "noopener");
    open.textContent = "게시글 보기 · 진행사항 수정";
    foot.appendChild(open);

    const photos = document.createElement("button");
    photos.className = "cs-ghost";
    photos.setAttribute("type", "button");
    photos.textContent = "BEFORE / AFTER 사진 보기";
    photos.addEventListener("click", () => {
      if (item.shots) paintShots(item, shots);
      else showShots(item, shots, photos);
    });
    foot.appendChild(photos);
  }
  box.appendChild(foot);
  box.appendChild(shots);
  return box;
};

const dayView = () => {
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
    none.className = "cs-empty";
    none.textContent = "이 날은 등록된 일정이 없습니다.";
    list.appendChild(none);
    return;
  }
  for (let i = 0; i < day.length; i += 1) list.appendChild(card(day[i]));
};

const draw = () => {
  const box = pick("cal");
  box.textContent = "";
  if (root.getAttribute("data-view") === "week") {
    const start = weekStart(cursor);
    const end = addDays(start, 6);
    pick("period").textContent =
      `${start.getFullYear()}년 ${start.getMonth() + 1}월 ${start.getDate()}일 ~ ${end.getMonth() + 1}월 ${end.getDate()}일`;
    weekView(box);
  } else {
    pick("period").textContent = `${cursor.getFullYear()}년 ${cursor.getMonth() + 1}월`;
    monthView(box);
  }
  dayView();
};

const choose = (key) => {
  chosen = key;
  draw();
};

const move = (step) => {
  if (root.getAttribute("data-view") === "week") cursor = addDays(cursor, 7 * step);
  else cursor = new Date(cursor.getFullYear(), cursor.getMonth() + step, 1);
  draw();
};

const setView = (mode) => {
  root.setAttribute("data-view", mode);
  pick("view-month").setAttribute("aria-pressed", mode === "month" ? "true" : "false");
  pick("view-week").setAttribute("aria-pressed", mode === "week" ? "true" : "false");
  draw();
};

/* ------------------------------------------------------------ 등록 도우미 */

const chosenWorks = () => {
  const boxes = pick("new-works").querySelectorAll("input");
  const out = [];
  for (let i = 0; i < boxes.length; i += 1) {
    if (boxes[i].checked) out.push(boxes[i].getAttribute("data-work"));
  }
  return out;
};

const compose = () => {
  const date = pick("new-date").value;
  const time = pick("new-time").value;
  const picked = chosenWorks();
  const site = pick("new-site").value.trim();
  const owner = pick("new-owner").value;
  const place = pick("new-place").value.trim();
  const state = pick("new-status").value;
  const note = pick("new-note").value.trim();
  const dash = (text) => (text === "" ? "-" : text);

  pick("out-title").value = date === "" ? "날짜를 먼저 고르세요" :
    `${date}${time !== "" ? ` ${time}` : ""} | ${dash(picked.join(", "))} | ${dash(site)} | ${dash(owner)} | ${dash(place)} | ${state}`;

  pick("out-body").value = [
    "[일정]",
    `날짜: ${dash(date)}`,
    `시간: ${dash(time)}`,
    `작업항목: ${dash(picked.join(", "))}`,
    `현장: ${dash(site)}`,
    `담당자: ${dash(owner)}`,
    `장소: ${dash(place)}`,
    `진행상태: ${state}`,
    "",
    "[진행사항]",
    note !== "" ? note : "(작업이 진행될 때마다 이 아래에 날짜와 함께 적어 주세요)",
    "",
    "[BEFORE]",
    "(작업 전 사진을 이 아래에 올려 주세요)",
    "",
    "[AFTER]",
    "(작업 후 사진을 이 아래에 올려 주세요)",
  ].join("\n");
};

const told = (text) => {
  const box = pick("copied");
  box.textContent = text;
  box.hidden = false;
};

const copyFrom = (area, name) => {
  const text = area.value;
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(
      () => told(`${name}을 복사했습니다. 게시판 글쓰기에 붙여넣으세요.`),
      () => {
        area.select();
        told(`${name}을 선택해 두었습니다. Command + C 를 누르세요.`);
      }
    );
    return;
  }
  area.select();
  let ok = false;
  try { ok = document.execCommand("copy"); } catch (error) { ok = false; }
  told(ok ? `${name}을 복사했습니다.` : `${name}을 선택해 두었습니다. Command + C 를 누르세요.`);
};

const buildForm = () => {
  const box = pick("new-works");
  for (let i = 0; i < works.length; i += 1) {
    const label = document.createElement("label");
    label.className = "cs-check";
    const input = document.createElement("input");
    input.setAttribute("type", "checkbox");
    input.setAttribute("data-work", works[i]);
    input.addEventListener("change", compose);
    const text = document.createElement("span");
    text.textContent = works[i];
    label.appendChild(input);
    label.appendChild(text);
    box.appendChild(label);
  }

  const owner = pick("new-owner");
  for (let i = 0; i < owners.length; i += 1) {
    const option = document.createElement("option");
    option.setAttribute("value", owners[i]);
    option.textContent = owners[i];
    owner.appendChild(option);
  }
};

/** 게시판 주소가 맞는지에 따라 글쓰기 링크를 살리거나 잠근다 */
const setWriteLink = () => {
  const board = setting("board");
  const write = setting("write") !== "" ? setting("write") : board;
  const link = pick("write-link");
  const hint = pick("write-hint");

  if (write === "" || !boardOk) {
    link.removeAttribute("href");
    link.setAttribute("aria-disabled", "true");
    link.textContent = "③ 게시판 글쓰기 — 게시판 주소를 먼저 맞춰 주세요";
    hint.textContent = board === ""
      ? "위젯 코드의 data-board 에 일정 게시판 목록 주소(도메인 뒤 경로, 예: /schedule)를 넣어 주세요."
      : `지금 설정된 주소 «${write}» 를 열 수 없습니다. 아임웹에 게시판을 만들고 그 주소로 data-board 를 고쳐 주세요.`;
    return;
  }
  link.setAttribute("href", write);
  link.setAttribute("target", "_blank");
  link.setAttribute("rel", "noopener");
  link.removeAttribute("aria-disabled");
  link.textContent = "③ 게시판 글쓰기 열기 →";
  hint.textContent = `«${write}» 로 이동합니다. 글쓰기 주소가 따로 있으면 data-write 에 넣으세요.`;
};

/* ------------------------------------------------------------------ 폭·게이트 */

const applyWidth = () => {
  const width = root.offsetWidth || window.innerWidth || 0;
  if (width <= 0) return;
  if (width < MOBILE_MAX) root.classList.add("is-mobile");
  else root.classList.remove("is-mobile");
  if (width < NARROW_MAX) root.classList.add("is-narrow");
  else root.classList.remove("is-narrow");
};

const openPanel = () => {
  root.setAttribute("data-state", "open");
  pick("panel").hidden = false;
  pick("gate").hidden = true;
  applyWidth();
  draw();
  load();
};

const checkPin = () => {
  const wanted = setting("pin");
  const typed = String(pick("pin-input").value || "").trim();
  if (wanted === "" || typed === wanted) {
    pick("pin-error").hidden = true;
    openPanel();
    return;
  }
  pick("pin-error").hidden = false;
};

const setup = () => {
  if (!root) return;

  chosen = todayKey();
  pick("new-date").value = chosen;
  buildForm();
  compose();
  setWriteLink();

  pick("pin-submit").addEventListener("click", checkPin);
  pick("pin-input").addEventListener("keydown", (event) => {
    if (event.key === "Enter") checkPin();
  });

  pick("prev").addEventListener("click", () => move(-1));
  pick("next").addEventListener("click", () => move(1));
  pick("today").addEventListener("click", () => {
    cursor = new Date();
    chosen = todayKey();
    draw();
  });
  pick("reload").addEventListener("click", load);
  pick("view-month").addEventListener("click", () => setView("month"));
  pick("view-week").addEventListener("click", () => setView("week"));

  const watched = ["new-date", "new-time", "new-site", "new-owner", "new-place", "new-status", "new-note"];
  for (let i = 0; i < watched.length; i += 1) {
    pick(watched[i]).addEventListener("input", compose);
    pick(watched[i]).addEventListener("change", compose);
  }
  pick("copy-title").addEventListener("click", () => copyFrom(pick("out-title"), "제목"));
  pick("copy-body").addEventListener("click", () => copyFrom(pick("out-body"), "본문"));

  applyWidth();
  if (typeof ResizeObserver === "function") {
    const watcher = new ResizeObserver(() => applyWidth());
    watcher.observe(root);
  }
  window.addEventListener("resize", applyWidth);

  if (setting("pin") === "") openPanel();
};

setup();
