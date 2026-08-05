/* 폼 제출: 사진은 브라우저에서 미리 줄여 올린다(현장 데이터 절약 + 노션 용량 제한 대응). */

const MAX_EDGE = 2000;
const RESIZE_THRESHOLD = 1_200_000; // 이보다 작은 사진은 그대로 보낸다
const JPEG_QUALITY = 0.85;

document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("worklog-form");
  if (!form || !form.dataset.endpoint) return;

  bindFileLists(form);
  bindResultActions();
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    submitForm(form);
  });
});

/* ---------------------------------------------------------------- 파일 목록 */

function bindFileLists(form) {
  form.querySelectorAll('input[type="file"]').forEach((input) => {
    const list = form.querySelector(`.filelist[data-for="${input.name}"]`);
    if (!list) return;
    input.addEventListener("change", () => renderFileList(input, list));
  });
}

function renderFileList(input, list) {
  list.innerHTML = "";
  for (const file of input.files) {
    const item = document.createElement("li");

    if (file.type.startsWith("image/")) {
      const thumb = document.createElement("img");
      thumb.src = URL.createObjectURL(file);
      thumb.alt = "";
      thumb.addEventListener("load", () => URL.revokeObjectURL(thumb.src), { once: true });
      item.appendChild(thumb);
    }

    const name = document.createElement("span");
    name.className = "name";
    name.textContent = file.name;
    item.appendChild(name);

    const size = document.createElement("span");
    size.className = "size";
    size.textContent = formatSize(file.size);
    item.appendChild(size);

    list.appendChild(item);
  }
}

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)}KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)}MB`;
}

/* ------------------------------------------------------------------ 이미지 */

async function shrinkImage(file) {
  const isImage = file.type.startsWith("image/");
  const isHeic = /heic|heif/i.test(file.type) || /\.(heic|heif)$/i.test(file.name);
  if (!isImage && !isHeic) return file;
  if (file.type === "image/gif") return file;
  if (file.size <= RESIZE_THRESHOLD && !isHeic) return file;

  try {
    const source = await loadImage(file);
    const width = source.width || source.naturalWidth;
    const height = source.height || source.naturalHeight;
    const scale = Math.min(1, MAX_EDGE / Math.max(width, height));

    const canvas = document.createElement("canvas");
    canvas.width = Math.round(width * scale);
    canvas.height = Math.round(height * scale);
    canvas.getContext("2d").drawImage(source, 0, 0, canvas.width, canvas.height);
    if (source.close) source.close();

    const blob = await new Promise((resolve) =>
      canvas.toBlob(resolve, "image/jpeg", JPEG_QUALITY)
    );
    if (!blob || blob.size >= file.size) return file;

    const name = file.name.replace(/\.[^.]+$/, "") + ".jpg";
    return new File([blob], name, { type: "image/jpeg", lastModified: file.lastModified });
  } catch (error) {
    // 브라우저가 못 읽는 형식이면 원본을 그대로 서버에 맡긴다.
    return file;
  }
}

async function loadImage(file) {
  if (window.createImageBitmap) {
    try {
      return await createImageBitmap(file, { imageOrientation: "from-image" });
    } catch (error) {
      /* 구형 브라우저는 아래 경로로 */
    }
  }
  const url = URL.createObjectURL(file);
  try {
    return await new Promise((resolve, reject) => {
      const image = new Image();
      image.onload = () => resolve(image);
      image.onerror = () => reject(new Error("이미지를 읽을 수 없습니다."));
      image.src = url;
    });
  } finally {
    setTimeout(() => URL.revokeObjectURL(url), 10000);
  }
}

/* ------------------------------------------------------------------ 제출 */

async function submitForm(form) {
  const button = form.querySelector(".submit");
  const errorBox = form.querySelector(".error");
  const progress = form.querySelector(".progress");
  const bar = progress?.querySelector(".bar");
  const label = progress?.querySelector(".progress-label");

  const title = form.elements.title;
  if (title && !title.value.trim()) {
    showError(errorBox, "현장명을 입력해 주세요.");
    title.focus();
    return;
  }

  hide(errorBox);
  button.disabled = true;
  if (progress) {
    progress.hidden = false;
    if (bar) bar.style.width = "0%";
    if (label) label.textContent = "사진 준비 중…";
  }

  let payload;
  try {
    payload = await buildFormData(form);
  } catch (error) {
    button.disabled = false;
    if (progress) progress.hidden = true;
    showError(errorBox, error.message || "파일을 준비하지 못했습니다.");
    return;
  }

  if (label) label.textContent = "업로드 중…";

  try {
    const result = await send(form.dataset.endpoint, payload, (ratio) => {
      if (bar) bar.style.width = `${Math.round(ratio * 100)}%`;
      if (label && ratio >= 1) label.textContent = "노션에 저장 중…";
    });
    showResult(form, result);
  } catch (error) {
    button.disabled = false;
    if (progress) progress.hidden = true;
    showError(errorBox, error.message);
  }
}

async function buildFormData(form) {
  const data = new FormData();
  for (const element of form.elements) {
    if (!element.name || element.disabled) continue;
    if (element.type === "file") {
      // data-image 가 붙은 칸(사진)만 브라우저에서 미리 줄인다.
      const asImage = element.dataset.image !== undefined;
      for (const file of element.files) {
        data.append(element.name, asImage ? await shrinkImage(file) : file);
      }
    } else if (element.type !== "submit" && element.type !== "button") {
      data.append(element.name, element.value);
    }
  }
  return data;
}

function send(endpoint, data, onProgress) {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", endpoint);
    request.upload.addEventListener("progress", (event) => {
      if (event.lengthComputable) onProgress(event.loaded / event.total);
    });
    request.addEventListener("load", () => {
      let body = {};
      try {
        body = JSON.parse(request.responseText);
      } catch (error) {
        /* 그대로 진행 */
      }
      if (request.status >= 200 && request.status < 300) resolve(body);
      else reject(new Error(body.detail || `등록 실패 (HTTP ${request.status})`));
    });
    request.addEventListener("error", () =>
      reject(new Error("네트워크가 끊겼습니다. 신호를 확인하고 다시 시도해 주세요."))
    );
    request.addEventListener("timeout", () => reject(new Error("시간이 초과됐습니다.")));
    request.send(data);
  });
}

/* ------------------------------------------------------------------ 결과 */

function showResult(form, result) {
  const panel = document.querySelector(".result");
  if (!panel) {
    window.location.href = result.url || "/entries";
    return;
  }
  const message = panel.querySelector(".result-message");
  const link = panel.querySelector(".result-link");
  if (message && result.message) message.textContent = result.message;
  if (link && result.url) link.href = result.url;

  const warning = panel.querySelector(".result-warning");
  if (warning && result.warning) {
    warning.textContent = result.warning;
    warning.hidden = false;
  }

  const shareButton = panel.querySelector('[data-action="share"]');
  if (shareButton && navigator.share) shareButton.hidden = false;

  form.hidden = true;
  panel.hidden = false;
  panel.scrollIntoView({ behavior: "smooth", block: "start" });
}

function bindResultActions() {
  const panel = document.querySelector(".result");
  if (!panel) return;
  const link = panel.querySelector(".result-link");

  panel.querySelector('[data-action="copy"]')?.addEventListener("click", async (event) => {
    const button = event.currentTarget;
    try {
      await navigator.clipboard.writeText(link.href);
      button.textContent = "복사됨";
      setTimeout(() => (button.textContent = "링크 복사"), 1500);
    } catch (error) {
      window.prompt("아래 링크를 복사하세요", link.href);
    }
  });

  panel.querySelector('[data-action="share"]')?.addEventListener("click", () => {
    navigator.share({ title: document.title, url: link.href }).catch(() => {});
  });
}

/* ------------------------------------------------------------------ 잡동사니 */

function showError(box, message) {
  if (!box) {
    window.alert(message);
    return;
  }
  box.textContent = message;
  box.hidden = false;
  box.scrollIntoView({ behavior: "smooth", block: "center" });
}

function hide(element) {
  if (element) element.hidden = true;
}
