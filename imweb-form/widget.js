/* 청명 작업현황 작성 폼 — 아임웹 일정(캘린더)의 «상세 일정»에 붙여넣을
   제목과 상세 내용을 만들어 준다. 상세 내용은 편집기의 </> 버튼으로 넣는 표 형태 HTML이다. */

const root = document.querySelector("[data-form-root]");
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
const states = listOf("states");

const MOBILE_MAX = 560;
const CELL = "padding:7px 10px;border:1px solid #d8dee6";
const HEAD = `width:92px;background:#f2f5f9;font-weight:700;${CELL}`;
const LABEL = "margin:18px 0 6px;font-weight:700;font-size:15px";
const GHOST = "margin:0 0 14px;color:#98a1ad;font-size:14px";

/** 붙여넣을 HTML에 사람이 쓴 글자를 안전하게 넣는다 */
const safe = (text) =>
  String(text || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

const value = (name) => String(pick(name).value || "").trim();

const chosenWorks = () => {
  const boxes = pick("works-box").querySelectorAll("input");
  const out = [];
  for (let i = 0; i < boxes.length; i += 1) {
    if (boxes[i].checked) out.push(boxes[i].getAttribute("data-work"));
  }
  return out;
};

const lines = (text) => {
  const raw = String(text || "").split("\n");
  const out = [];
  for (let i = 0; i < raw.length; i += 1) {
    const line = raw[i].trim();
    if (line !== "") out.push(line);
  }
  return out;
};

const dateText = (date, time) => {
  if (date === "") return "";
  const parts = date.split("-");
  const day = `${parts[0]}년 ${Number(parts[1])}월 ${Number(parts[2])}일`;
  return time !== "" ? `${day} ${time}` : day;
};

/** 아임웹 일정에 넣을 표 형태 상세 내용 */
const buildHtml = (data) => {
  const rows = [];
  const row = (name, text) => {
    if (text === "") return;
    rows.push(`<tr><td style="${HEAD}">${name}</td><td style="${CELL}">${safe(text)}</td></tr>`);
  };
  row("작업항목", data.works.join(", "));
  row("일시", dateText(data.date, data.time));
  row("현장", data.site);
  row("장소", data.place);
  row("담당자", data.owner);
  row("연락처", data.phone);
  row("견적·금액", data.cost === "" ? "" : `${data.cost}원`);
  row("진행상태", data.state);

  const out = [];
  if (rows.length > 0) {
    out.push('<table style="width:100%;border-collapse:collapse;font-size:14px;line-height:1.7">');
    out.push(`<tbody>${rows.join("")}</tbody>`);
    out.push("</table>");
  }

  out.push(`<p style="${LABEL}">진행사항</p>`);
  if (data.note.length > 0) {
    const items = [];
    for (let i = 0; i < data.note.length; i += 1) items.push(`<li>${safe(data.note[i])}</li>`);
    out.push(`<ul style="margin:0 0 14px;padding-left:20px;font-size:14px;line-height:1.8">${items.join("")}</ul>`);
  } else {
    out.push(`<p style="${GHOST}">작업이 진행될 때마다 날짜와 함께 여기에 적어 주세요.</p>`);
  }

  if (data.extra !== "") {
    out.push(`<p style="${LABEL}">특이사항</p>`);
    out.push(`<p style="margin:0 0 14px;font-size:14px;line-height:1.8">${safe(data.extra)}</p>`);
  }

  out.push(`<p style="${LABEL}">BEFORE</p>`);
  out.push(`<p style="${GHOST}">작업 전 사진을 이 자리에 넣어 주세요.</p>`);
  out.push(`<p style="${LABEL}">AFTER</p>`);
  out.push(`<p style="${GHOST}">작업 후 사진을 이 자리에 넣어 주세요.</p>`);
  return out.join("\n");
};

/** HTML 붙여넣기가 안 되는 편집기를 위한 글자만 버전 */
const buildText = (data) => {
  const out = [];
  const row = (name, text) => {
    if (text !== "") out.push(`${name}: ${text}`);
  };
  row("작업항목", data.works.join(", "));
  row("일시", dateText(data.date, data.time));
  row("현장", data.site);
  row("장소", data.place);
  row("담당자", data.owner);
  row("연락처", data.phone);
  row("견적·금액", data.cost === "" ? "" : `${data.cost}원`);
  row("진행상태", data.state);

  out.push("");
  out.push("[진행사항]");
  if (data.note.length > 0) {
    for (let i = 0; i < data.note.length; i += 1) out.push(`- ${data.note[i]}`);
  } else {
    out.push("(작업이 진행될 때마다 날짜와 함께 적어 주세요)");
  }
  if (data.extra !== "") {
    out.push("");
    out.push("[특이사항]");
    out.push(data.extra);
  }
  out.push("");
  out.push("[BEFORE]");
  out.push("(작업 전 사진)");
  out.push("");
  out.push("[AFTER]");
  out.push("(작업 후 사진)");
  return out.join("\n");
};

/** 달력 칸에 보일 제목 */
const buildTitle = (data) => {
  if (pick("machine").checked) {
    const dash = (text) => (text === "" ? "-" : text);
    if (data.date === "") return "작업일을 먼저 고르세요";
    return `${data.date}${data.time !== "" ? ` ${data.time}` : ""} | ${dash(data.works.join(", "))}`
      + ` | ${dash(data.site)} | ${dash(data.owner)} | ${dash(data.place)} | ${data.state}`;
  }
  const head = [];
  if (data.time !== "") head.push(data.time);
  if (data.site !== "") head.push(data.site);
  if (head.length === 0) head.push("작업");
  const tail = [];
  if (data.works.length > 0) tail.push(data.works.join("·"));
  if (data.owner !== "") tail.push(data.owner);
  const state = data.state !== "" && data.state !== "예정" ? ` [${data.state}]` : "";
  return `${head.join(" ")}${tail.length > 0 ? ` · ${tail.join(" · ")}` : ""}${state}`;
};

const compose = () => {
  const data = {
    date: value("date"),
    time: value("time"),
    works: chosenWorks(),
    site: value("site"),
    place: value("place"),
    owner: value("owner"),
    state: value("state"),
    phone: value("phone"),
    cost: value("cost"),
    note: lines(pick("note").value),
    extra: value("extra"),
  };
  const html = buildHtml(data);
  pick("out-title").value = buildTitle(data);
  pick("out-html").value = html;
  pick("out-text").value = buildText(data);
  pick("preview").innerHTML = html;
};

const said = (text) => {
  const box = pick("said");
  box.textContent = text;
  box.hidden = false;
};

const copyFrom = (area, name) => {
  const text = area.value;
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(
      () => said(`${name}을 복사했습니다.`),
      () => {
        area.select();
        said(`${name}을 선택해 두었습니다. Command + C 를 누르세요.`);
      }
    );
    return;
  }
  area.select();
  let ok = false;
  try { ok = document.execCommand("copy"); } catch (error) { ok = false; }
  said(ok ? `${name}을 복사했습니다.` : `${name}을 선택해 두었습니다. Command + C 를 누르세요.`);
};

const fillOptions = (box, values) => {
  for (let i = 0; i < values.length; i += 1) {
    const option = document.createElement("option");
    option.setAttribute("value", values[i]);
    option.textContent = values[i];
    box.appendChild(option);
  }
};

const today = () => {
  const now = new Date();
  const month = `0${now.getMonth() + 1}`.slice(-2);
  const day = `0${now.getDate()}`.slice(-2);
  return `${now.getFullYear()}-${month}-${day}`;
};

const applyWidth = () => {
  const width = root.offsetWidth || window.innerWidth || 0;
  if (width <= 0) return;
  if (width < MOBILE_MAX) root.classList.add("is-mobile");
  else root.classList.remove("is-mobile");
};

const setup = () => {
  if (!root) return;

  const box = pick("works-box");
  for (let i = 0; i < works.length; i += 1) {
    const label = document.createElement("label");
    label.className = "cw-check";
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
  fillOptions(pick("owner"), owners);
  fillOptions(pick("state"), states);
  pick("date").value = today();

  const watched = ["date", "time", "site", "place", "owner", "state", "phone", "cost", "note", "extra", "machine"];
  for (let i = 0; i < watched.length; i += 1) {
    pick(watched[i]).addEventListener("input", compose);
    pick(watched[i]).addEventListener("change", compose);
  }

  pick("copy-title").addEventListener("click", () => copyFrom(pick("out-title"), "제목"));
  pick("copy-html").addEventListener("click", () => copyFrom(pick("out-html"), "HTML"));
  pick("copy-text").addEventListener("click", () => copyFrom(pick("out-text"), "글자"));

  const calendar = setting("calendar");
  if (calendar !== "") {
    const link = pick("calendar-link");
    link.setAttribute("href", calendar);
    link.setAttribute("target", "_blank");
    link.setAttribute("rel", "noopener");
    link.hidden = false;
  }

  compose();
  applyWidth();
  if (typeof ResizeObserver === "function") {
    const watcher = new ResizeObserver(() => applyWidth());
    watcher.observe(root);
  }
  window.addEventListener("resize", applyWidth);
};

setup();
