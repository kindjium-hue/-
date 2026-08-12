/* 아임웹 캘린더 조사 도구 — 캘린더의 화면 구조와, 일정을 추가·수정할 때 오가는 통신을
   정리해 보여 준다. 값은 적지 않고 «항목 이름과 길이»만 적는다(개인정보·토큰 보호). */

const root = document.querySelector("[data-probe-root]");
const pick = (name) => root.querySelector(`[data-${name}]`);

const pad2 = (value) => `0${value}`.slice(-2);
const HIDE_KEY = /token|key|secret|sess|pass|auth|cookie|csrf/i;
const CAL_HINT = /calendar|schedule|event|cal_|sched/i;
const MAX_CALLS = 60;
const KEEP_KEY = "cheongmyeong_probe_log";

/** 저장·이동을 누르면 페이지가 새로 열려 기록이 사라진다. 그래서 남겨 둔다. */
const stored = () => {
  try {
    const text = localStorage.getItem(KEEP_KEY);
    const data = text ? JSON.parse(text) : [];
    return Array.isArray(data) ? data : [];
  } catch (error) {
    return [];
  }
};

const store = (rows) => {
  try {
    localStorage.setItem(KEEP_KEY, JSON.stringify(rows.slice(-MAX_CALLS)));
  } catch (error) {
    return;
  }
};

const forget = () => {
  try { localStorage.removeItem(KEEP_KEY); } catch (error) { return; }
};

const calls = stored();
let dom = [];

const filters = () => {
  const raw = String(root.getAttribute("data-filter") || "").split(",");
  const out = [];
  for (let i = 0; i < raw.length; i += 1) {
    const one = raw[i].trim().toLowerCase();
    if (one !== "") out.push(one);
  }
  return out;
};

const wanted = (url) => {
  const list = filters();
  if (list.length === 0) return true;
  const text = String(url || "").toLowerCase();
  for (let i = 0; i < list.length; i += 1) {
    if (text.indexOf(list[i]) >= 0) return true;
  }
  return false;
};

/** 주소에서 민감해 보이는 값만 가린다 */
const tidyUrl = (url) => {
  const text = String(url || "");
  const cut = text.indexOf("?");
  if (cut < 0) return text;
  const head = text.slice(0, cut);
  const parts = text.slice(cut + 1).split("&");
  const out = [];
  for (let i = 0; i < parts.length; i += 1) {
    const pair = parts[i].split("=");
    const key = pair[0];
    const val = pair.length > 1 ? pair.slice(1).join("=") : "";
    if (HIDE_KEY.test(key) || val.length > 40) out.push(`${key}=(가림:${val.length}자)`);
    else out.push(`${key}=${val}`);
  }
  return `${head}?${out.join("&")}`;
};

/** 보낸 내용의 «항목 이름»만 적는다 */
const shape = (body) => {
  if (body === null || body === undefined || body === "") return "(없음)";
  if (typeof body === "string") {
    const text = body.trim();
    if (text.charAt(0) === "{" || text.charAt(0) === "[") {
      try { return shape(JSON.parse(text)); } catch (error) { return `글자 ${text.length}자`; }
    }
    if (text.indexOf("=") > 0) {
      const parts = text.split("&");
      const keys = [];
      for (let i = 0; i < parts.length && keys.length < 30; i += 1) {
        const pair = parts[i].split("=");
        const value = pair.length > 1 ? pair.slice(1).join("=") : "";
        keys.push(`${pair[0]}(${value.length}자)`);
      }
      return `폼: ${keys.join(", ")}`;
    }
    return `글자 ${text.length}자`;
  }
  if (typeof FormData === "function" && body instanceof FormData) {
    const keys = [];
    body.forEach((value, key) => {
      if (keys.length < 30) keys.push(`${key}(${String(value).length}자)`);
    });
    return `폼데이터: ${keys.join(", ")}`;
  }
  if (typeof body === "object") {
    const keys = Object.keys(body);
    const out = [];
    for (let i = 0; i < keys.length && i < 30; i += 1) {
      const value = body[keys[i]];
      const kind = value === null ? "없음"
        : Array.isArray(value) ? `목록 ${value.length}개`
        : typeof value === "object" ? "묶음"
        : `${String(value).length}자`;
      out.push(`${keys[i]}(${kind})`);
    }
    return `묶음: ${out.join(", ")}`;
  }
  return String(typeof body);
};

/** 받은 내용의 «구조»만 적는다 (값은 적지 않는다) */
const answerShape = (text) => {
  const raw = String(text || "").trim();
  if (raw === "") return "(빈 응답)";
  if (raw.charAt(0) !== "{" && raw.charAt(0) !== "[") return `글자 ${raw.length}자`;
  let data = null;
  try { data = JSON.parse(raw); } catch (error) { return `JSON 아님 (${raw.length}자)`; }

  const dig = (value, depth) => {
    if (Array.isArray(value)) {
      if (value.length === 0) return "목록 0개";
      return `목록 ${value.length}개 → ${dig(value[0], depth + 1)}`;
    }
    if (value !== null && typeof value === "object") {
      const keys = Object.keys(value);
      if (depth >= 3) return `묶음(${keys.length}칸)`;
      const out = [];
      for (let i = 0; i < keys.length && i < 24; i += 1) {
        const inner = value[keys[i]];
        if (Array.isArray(inner) || (inner !== null && typeof inner === "object")) {
          out.push(`${keys[i]}: ${dig(inner, depth + 1)}`);
        } else {
          out.push(keys[i]);
        }
      }
      return `{ ${out.join(", ")} }`;
    }
    return typeof value === "string" ? "글자" : String(typeof value);
  };
  return dig(data, 0);
};

const clock = () => {
  const now = new Date();
  return `${pad2(now.getHours())}:${pad2(now.getMinutes())}:${pad2(now.getSeconds())}`;
};

const remember = (row) => {
  row.at = clock();
  row.page = `${location.pathname}${location.search}`;
  calls.push(row);
  if (calls.length > MAX_CALLS) calls.shift();
  store(calls);
  report();
};

/** 응답이 늦게 온 것도 보관한다 */
const restore = () => {
  store(calls);
  report();
};

/* ------------------------------------------------------------ 통신 엿보기 */

const watchNetwork = () => {
  const realFetch = window.fetch;
  if (typeof realFetch === "function") {
    window.fetch = function (input, init) {
      const url = typeof input === "string" ? input : (input && input.url) || "";
      const options = init || {};
      const method = String(options.method || (input && input.method) || "GET").toUpperCase();
      const row = { method: method, url: tidyUrl(url), sent: shape(options.body), got: "…" };
      if (wanted(url)) remember(row);
      return realFetch.apply(this, arguments).then((response) => {
        if (!wanted(url)) return response;
        row.got = `${response.status}`;
        response.clone().text().then((text) => {
          row.got = `${response.status} · ${answerShape(text)}`;
          restore();
        }, () => { restore(); });
        return response;
      });
    };
  }

  const realOpen = XMLHttpRequest.prototype.open;
  const realSend = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function (method, url) {
    this.probeRow = { method: String(method || "").toUpperCase(), url: tidyUrl(url), raw: url };
    return realOpen.apply(this, arguments);
  };
  XMLHttpRequest.prototype.send = function (body) {
    const row = this.probeRow;
    if (row && wanted(row.raw)) {
      row.sent = shape(body);
      row.got = "…";
      remember(row);
      this.addEventListener("load", () => {
        let text = "";
        try {
          text = this.responseType === "" || this.responseType === "text" ? this.responseText : "";
        } catch (error) {
          text = "";
        }
        row.got = `${this.status} · ${text === "" ? "(글자 아님)" : answerShape(text)}`;
        restore();
      });
    }
    return realSend.apply(this, arguments);
  };
};

/* -------------------------------------------------------------- 화면 조사 */

const label = (el) => {
  const name = el.tagName.toLowerCase();
  const cls = String(el.getAttribute("class") || "").split(/\s+/).slice(0, 3).join(".");
  const id = el.getAttribute("id");
  return `${name}${id ? `#${id}` : ""}${cls !== "" ? `.${cls}` : ""}`;
};

const scan = () => {
  dom = [];
  const found = [];
  const all = document.querySelectorAll("div,section,table,ul,article");
  for (let i = 0; i < all.length; i += 1) {
    const el = all[i];
    if (root.contains(el)) continue;
    const mark = `${el.getAttribute("class") || ""} ${el.getAttribute("id") || ""}`;
    if (!CAL_HINT.test(mark)) continue;
    if (found.length >= 14) break;
    found.push(el);
    dom.push(`· ${label(el)} — 자식 ${el.children.length}개, 글자 ${el.textContent.trim().length}자`);
  }

  const names = [];
  for (let i = 0; i < found.length; i += 1) {
    const kids = found[i].querySelectorAll("*");
    for (let k = 0; k < kids.length && names.length < 30; k += 1) {
      const attrs = kids[k].attributes;
      for (let a = 0; a < attrs.length; a += 1) {
        const name = attrs[a].name;
        if (name.indexOf("data-") !== 0) continue;
        if (names.indexOf(name) < 0 && names.length < 30) names.push(name);
      }
    }
  }
  if (names.length > 0) dom.push(`· 쓰이는 data 이름: ${names.join(", ")}`);

  const texts = [];
  for (let i = 0; i < found.length && texts.length < 12; i += 1) {
    const kids = found[i].querySelectorAll("a,span,div,li,p,td");
    for (let k = 0; k < kids.length && texts.length < 12; k += 1) {
      if (kids[k].children.length > 0) continue;
      const text = kids[k].textContent.replace(/\s+/g, " ").trim();
      if (text.length < 2 || text.length > 60) continue;
      if (/^\d{1,2}$/.test(text)) continue;
      const line = `  - ${label(kids[k])} = ${text}`;
      if (texts.indexOf(line) < 0) texts.push(line);
    }
  }
  for (let i = 0; i < texts.length; i += 1) dom.push(texts[i]);
  report();
};

/* ---------------------------------------------------------------- 보고서 */

const build = () => {
  const out = [];
  out.push(`페이지: ${location.pathname}${location.search}`);
  out.push(`조사 시각: ${new Date().toLocaleString("ko-KR")}`);
  out.push("");
  out.push(`[화면 구조] 캘린더로 보이는 것 ${dom.length}줄`);
  if (dom.length === 0) out.push("· 캘린더로 보이는 요소를 찾지 못했습니다.");
  for (let i = 0; i < dom.length; i += 1) out.push(dom[i]);
  out.push("");
  out.push(`[통신 기록] ${calls.length}건 (값은 적지 않고 항목 이름만)`);
  if (calls.length === 0) out.push("· 아직 없습니다. 캘린더에서 일정을 추가·수정해 보세요.");
  let lastPage = "";
  for (let i = 0; i < calls.length; i += 1) {
    const row = calls[i];
    if (row.page && row.page !== lastPage) {
      out.push(`--- 페이지: ${row.page} ---`);
      lastPage = row.page;
    }
    out.push(`${i + 1}) ${row.at ? `[${row.at}] ` : ""}${row.method} ${row.url}`);
    out.push(`   보냄: ${row.sent}`);
    out.push(`   받음: ${row.got}`);
  }
  return out.join("\n");
};

const report = () => {
  pick("out").textContent = build();
  pick("count").textContent = `통신 기록 ${calls.length}건 · 캘린더로 보이는 요소 ${dom.length}줄`;
};

const selectOut = () => {
  const range = document.createRange();
  range.selectNodeContents(pick("out"));
  const selection = window.getSelection();
  selection.removeAllRanges();
  selection.addRange(range);
  pick("count").textContent = "결과를 선택해 두었습니다. Command + C 를 누르세요.";
};

const copyOut = () => {
  const text = build();
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(
      () => {
        pick("count").textContent = "결과를 복사했습니다. 그대로 붙여넣어 알려 주세요.";
      },
      () => { selectOut(); }
    );
    return;
  }
  selectOut();
};

const setup = () => {
  if (!root) return;
  watchNetwork();
  pick("scan").addEventListener("click", scan);
  pick("copy").addEventListener("click", copyOut);
  pick("clear").addEventListener("click", () => {
    calls.length = 0;
    forget();
    report();
  });
  scan();
  // 캘린더가 늦게 그려지는 경우가 많아 몇 번 더 살펴본다
  setTimeout(scan, 1500);
  setTimeout(scan, 4000);
};

setup();
