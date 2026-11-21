// Пульт учителя. Обычный JavaScript без сборки: страница опрашивает сервер раз в 2 секунды.
"use strict";

const app = document.getElementById("app");
const lessonEl = document.getElementById("lesson");
const actionsEl = document.getElementById("actions");
const timerBox = document.getElementById("timerbox");
const navEl = document.getElementById("nav");
const modal = document.getElementById("modal");
const modalBody = document.getElementById("modal-body");
const trafficLightEl = document.getElementById("traffic-light");

let data = null;          // последний ответ /tapi/overview
let ai = null;            // последний ответ /tapi/ai: нейросеть, очередь, лента вопросов
let play = null;          // последний ответ /tapi/play: игры по сети класса
let teams = null;         // последний ответ /tapi/teams: команды проекта и идеи учеников
let menuOpen = false;     // меню «Ещё» в шапке
let lastKey = "";         // перерисовываем, только если что-то изменилось (иначе щелчки «съедаются»)
let lastRenderAt = 0;
const leftMatches = new Set();
let feedFilter = "";      // лента: только один ученик
let feedSearch = "";      // лента: поиск по тексту
const openDetails = new Set();   // какие раскрывашки открыты: пульт перерисовывается каждые 2 с, а они не должны закрываться

// раскрывашка, которая помнит, открыта ли она
function details(key, summary, ...body) {
  const d = h("details", { class: "keep" }, h("summary", {}, summary), ...body);
  d.open = openDetails.has(key);
  d.addEventListener("toggle", () => { if (d.open) openDetails.add(key); else openDetails.delete(key); });
  return d;
}
let editingGroup = null;  // id редактируемой группы (или "new")
const pick = { group: null, lesson: null };   // выбор перед началом занятия
let pollTimer = null;
let clockTimer = null;
let busy = false;
let refreshing = false;
let refreshQueued = false;
let wasOffline = false;
let audioCtx = null;
let lastAttention = 0;
let navKey = "";
let pollDraft = null;
const teacherTop = document.querySelector(".top");
if (teacherTop && typeof ResizeObserver !== "undefined") {
  new ResizeObserver(() => {
    document.documentElement.style.setProperty("--teacher-top-height", teacherTop.offsetHeight + "px");
  }).observe(teacherTop);
}

const store = {
  get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* без хранилища просто не запоминаем */ } },
};
const TABS = [["class", "🏫", "Класс"], ["project", "🚀", "Проекты"], ["ai", "🤖", "Нейросеть"], ["play", "🎮", "Игры"], ["groups", "👥", "Группы"], ["connect", "🔌", "Подключение"]];
let tab = TABS.some((t) => t[0] === store.get("kurs.tab")) ? store.get("kurs.tab") : "class";
function goTab(t) {
  if (data && data.course?.id === "games" && t === "ai") t = "class";
  tab = t;
  store.set("kurs.tab", t);
  menuOpen = false;
  renderTop();
  renderNav();
  render();
  window.scrollTo(0, 0);
}
document.addEventListener("click", (e) => { if (menuOpen && !e.target.closest(".menu-wrap")) { menuOpen = false; renderTop(); } });

// ---------- помощники ----------
const serverPort = () => location.port || (location.protocol === "https:" ? "443" : "80");

function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "value") el.value = v;
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat(Infinity)) {
    if (kid === null || kid === undefined || kid === false) continue;
    el.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  }
  return el;
}

async function api(method, path, body) {
  const opt = { method, headers: {}, credentials: "same-origin" };
  if (body !== undefined) {
    opt.headers["Content-Type"] = "application/json";
    opt.body = JSON.stringify(body);
  }
  const r = await fetch(path, opt);
  let j = {};
  try { j = await r.json(); } catch (e) { /* пустой ответ */ }
  if (!r.ok) {
    const err = new Error(j.error || ("Ошибка " + r.status));
    err.status = r.status;
    throw err;
  }
  return j;
}

async function downloadExport(url, fallbackName) {
  try {
    const r = await fetch(url, { credentials: "same-origin" });
    if (r.status === 401) { boot(); return; }
    if (!r.ok) {
      let msg = "Ошибка " + r.status;
      try {
        const j = await r.json();
        if (j && j.error) msg = j.error;
      } catch (e) { /* ответ не JSON */ }
      alert(msg);
      return;
    }
    const blob = await r.blob();
    let filename = fallbackName || "download";
    const cd = r.headers.get("Content-Disposition") || "";
    const mUtf8 = cd.match(/filename\*=UTF-8''([^;]+)/i);
    const mAscii = cd.match(/filename="?([^";]+)"?/i);
    if (mUtf8) filename = decodeURIComponent(mUtf8[1]);
    else if (mAscii) filename = mAscii[1];
    const blobUrl = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = blobUrl;
    a.download = filename;
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(blobUrl), 1000);
  } catch (e) {
    alert(e.message || "Не удалось скачать файл");
  }
}

async function act(path, body) {
  if (busy) return false;
  busy = true;
  try {
    await api("POST", "/tapi/" + path, body || {});
    await refresh();
    return true;
  } catch (e) {
    if (e.status === 401) { boot(); return false; }
    alert(e.message);
    return false;
  } finally {
    busy = false;
  }
}

const mmss = (sec) => String(Math.floor(sec / 60)).padStart(2, "0") + ":" + String(sec % 60).padStart(2, "0");
const ago = (ts, now) => {
  if (!ts) return "";
  const s = Math.round(now - ts);
  return s < 60 ? "только что" : Math.round(s / 60) + " мин назад";
};
const plural = (n, one, few, many) => (n % 10 === 1 && n % 100 !== 11 ? one : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20) ? few : many);

function openModal(...kids) {
  modalBody.replaceChildren(...kids.flat(Infinity).filter((x) => x));   // пустые части (null) не выводим
  modal.classList.remove("hidden");
}
function closeModal() { modal.classList.add("hidden"); }
modal.addEventListener("click", (e) => { if (e.target === modal) closeModal(); });
modal.querySelector(".modal-close").addEventListener("click", closeModal);
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeModal(); });

// короткий сигнал, когда появился новый запрос на вход или просьба о помощи
function beep() {
  if (store.get("kurs.sound") === "off") return;
  try {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx) return;
    if (!audioCtx) audioCtx = new AudioCtx();
    const playTone = () => {
      const o = audioCtx.createOscillator();
      const g = audioCtx.createGain();
      o.frequency.value = 880;
      g.gain.setValueAtTime(0.08, audioCtx.currentTime);
      g.gain.exponentialRampToValueAtTime(0.0001, audioCtx.currentTime + 0.25);
      o.connect(g).connect(audioCtx.destination);
      o.start();
      o.stop(audioCtx.currentTime + 0.25);
    };
    if (audioCtx.state === "suspended") {
      audioCtx.resume().then(playTone).catch(() => {});
    } else {
      playTone();
    }
  } catch (e) { /* звук недоступен */ }
}

// ---------- вход ----------
async function boot() {
  clearInterval(pollTimer);
  pollTimer = null;
  clearInterval(clockTimer);
  clockTimer = null;
  let who;
  try {
    who = await api("GET", "/tapi/whoami");
  } catch (e) {
    app.replaceChildren(h("p", { class: "err" }, e.message));
    return;
  }
  if (!who.has_password) return showPasswordForm(true);
  if (!who.logged_in) return showPasswordForm(false);
  await refresh();
  pollTimer = setInterval(refresh, 2000);
}

function showPasswordForm(setup) {
  clearInterval(clockTimer);
  clockTimer = null;
  lessonEl.textContent = "";
  actionsEl.replaceChildren();
  trafficLightEl?.replaceChildren();
  timerBox?.replaceChildren();
  navEl?.replaceChildren();
  navKey = "";
  lastKey = "";
  const pw = h("input", { id: "teacher-password", type: "password", required: true,
    autocomplete: setup ? "new-password" : "current-password" });
  const pw2 = setup ? h("input", { id: "teacher-password-repeat", type: "password", required: true, autocomplete: "new-password" }) : null;
  const err = h("div", { class: "err", role: "alert" });
  const go = async (e) => {
    e.preventDefault();
    err.textContent = "";
    if (setup && pw.value !== pw2.value) { err.textContent = "Пароли не совпадают"; return; }
    try {
      await api("POST", setup ? "/tapi/setup" : "/tapi/login", { password: pw.value });
      pw.blur();
      pw2?.blur();
      boot();
    } catch (ex) { err.textContent = ex.message; }
  };
  const resetBtn = !setup ? h("button", {
    type: "button",
    class: "link small",
    style: "margin-top:14px;background:none;border:none;color:var(--blue-ink);cursor:pointer;text-decoration:underline;display:inline-block;",
    onclick: async () => {
      if (confirm("Сбросить старый пароль и задать новый прямо сейчас?")) {
        try {
          await api("POST", "/tapi/reset_password");
          boot();
        } catch (ex) {
          err.textContent = ex.message;
        }
      }
    }
  }, "Забыли пароль? Нажмите для сброса") : null;
  app.replaceChildren(h("form", { class: "card center", onsubmit: go },
    h("h2", {}, setup ? "Первый запуск: придумайте пароль учителя" : "Вход для учителя"),
    setup ? h("p", { class: "muted" }, "Пароль нужен, чтобы пульт не открыл посторонний. Не короче 6 символов.") : null,
    h("label", { class: "field", for: pw.id }, h("span", {}, "Пароль"), pw),
    pw2 ? h("label", { class: "field", for: pw2.id }, h("span", {}, "Повторите пароль"), pw2) : null, err,
    h("button", { type: "submit", class: "big" }, setup ? "Сохранить пароль" : "Войти"),
    resetBtn));
  pw.focus();
}

// ---------- обновление ----------
function stateFingerprint() {
  const aiLog = (ai && Array.isArray(ai.log)) ? ai.log : [];
  const aiSummary = ai ? {
    today: ai.today,
    status: ai.status,
    config: ai.config,
    logLen: aiLog.length,
    logHead: aiLog.slice(0, 10).map((r) => [
      r.id, r.ts, r.status, r.ms, r.cached,
      r.flags ? r.flags.length : 0,
      r.question ? r.question.length : 0,
      r.answer ? r.answer.length : 0,
    ]),
    logTail: aiLog.length > 10 ? [aiLog[aiLog.length - 1].id, aiLog[aiLog.length - 1].ts, aiLog[aiLog.length - 1].status] : null,
  } : null;
  return JSON.stringify([data, aiSummary, play, teams, tab, feedFilter], (k, v) => (k === "now" || k === "seen" ? undefined : v));
}

async function refresh() {
  if (refreshing) {
    refreshQueued = true;
    return;
  }
  refreshing = true;
  try {
    const [d, a, p, t] = await Promise.all([
      api("GET", "/tapi/overview"),
      api("GET", "/tapi/ai" + (feedFilter ? "?student=" + encodeURIComponent(feedFilter) : "")),
      api("GET", "/tapi/play"),
      api("GET", "/tapi/teams"),
    ]);
    data = d;
    ai = a;
    play = p;
    teams = t;
    const recovered = wasOffline;
    wasOffline = false;
    if (feedFilter && !(data.students || []).some((s) => String(s.id) === String(feedFilter))) {
      feedFilter = "";
      refreshQueued = true;
    }
    if (data.course?.id === "games" && tab === "ai") {
      tab = "class";
      store.set("kurs.tab", "class");
    }
    const invites = play ? play.invites_in.length : 0;
    const attention = data.requests.length + data.help.length + (data.locks || []).length + invites + (data.course?.id !== "games" && ai && ai.status.last_error && aiUsed() ? 1 : 0);
    document.title = (attention ? `(${attention}) ` : "") + "Пульт учителя";
    if (attention > lastAttention) beep();
    lastAttention = attention;
    syncTeacherMatch();
    // не перерисовываем, пока учитель печатает, и если ничего не изменилось
    const typing = document.activeElement && ["TEXTAREA", "INPUT", "SELECT"].includes(document.activeElement.tagName) && !document.activeElement.closest(".play-host");
    const key = stateFingerprint();
    if (!recovered && key === lastKey && Date.now() - lastRenderAt < 30000) return;
    renderTop();
    renderNav();
    if (!typing && !app.querySelector('.module-poll[aria-busy="true"]')) {
      lastKey = key;
      render();
    } else if (typing && data.poll?.phase === "ideas") {
      const live = document.getElementById("poll-live-ideas");
      const options = document.getElementById("poll-options");
      if (live?.dataset.pollId === String(data.poll.id) && options) updatePollIdeas(live, data.poll, options);
    }
  } catch (e) {
    if (e.status === 401) { boot(); return; }
    wasOffline = true;
    lessonEl.textContent = "Нет связи с сервером";
  } finally {
    refreshing = false;
    if (refreshQueued) {
      refreshQueued = false;
      refresh();
    }
  }
}

const currentLesson = () => data.lessons.find((l) => l.lesson === data.state.lesson) || data.lessons[0];
function openSlides() {
  const lesson = data.state.running ? data.state.lesson : pick.lesson;
  const anchor = lesson ? "#l" + lesson + "-divider" : "";
  window.open("/presentation" + anchor, "_blank");
}
const currentGroup = () => data.groups.find((g) => g.id === data.state.group_id);

function renderTrafficLight() {
  if (!trafficLightEl || !data) return;
  const st = data.state;
  const online = (data.students || []).filter((x) => x.pc).length;
  const mainIp = (data.addresses && data.addresses[0]) || window.location.hostname || "localhost";
  const port = serverPort();
  const studentUrl = `${location.protocol}//${mainIp}:${port}`;

  let aiClass = "ok";
  let aiText = "🟢 ИИ готов";
  if (ai && ai.status) {
    if (ai.status.bridge && ai.status.bridge.active) {
      aiClass = "ok";
      aiText = `🟢 Мост ИИ: ${ai.status.bridge.models ? ai.status.bridge.models.split(',')[0].trim() : "Gemini"}`;
    } else if (ai.status.ok && ai.status.configured) {
      aiClass = "ok";
      aiText = `🟢 ИИ: ${ai.status.provider}`;
    } else if (ai.status.mode === "offline") {
      aiClass = "wait";
      aiText = "🟡 ИИ: Запасной режим";
    } else if (ai.status.mode === "pause") {
      aiClass = "wait";
      aiText = "⏸ ИИ: На паузе";
    } else {
      aiClass = "bad";
      aiText = "🔴 ИИ: Требует ключ";
    }
  }

  const chips = [
    h("span", { class: "traffic-chip ok", title: "Сервер курса активен на этом порту" }, "🟢 Порт " + port),
    h("button", {
      class: "traffic-chip ok",
      title: "Адрес для учеников (нажмите, чтобы скопировать)",
      onclick: () => {
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(studentUrl)
            .then(() => alert("Адрес для учеников скопирован в буфер:\n" + studentUrl))
            .catch(() => prompt("Скопируйте адрес для учеников:", studentUrl));
        } else {
          prompt("Скопируйте адрес для учеников:", studentUrl);
        }
      }
    }, `🟢 Сеть: ${studentUrl}`),
    data.course?.id === "chatbots" ? h("button", {
      class: "traffic-chip " + aiClass,
      title: "Статус нейросети (нажмите для перехода к настройкам и проверке связи)",
      onclick: () => goTab("ai")
    }, aiText) : null,
    h("button", {
      class: "traffic-chip " + (st.running ? "ok" : "wait"),
      title: "Статус класса (нажмите для перехода)",
      onclick: () => goTab("class")
    }, st.running ? `🟢 Класс: ${online} онлайн` : "⚪ Занятие не начато"),
  ];

  trafficLightEl.replaceChildren(...chips.filter(Boolean));
}

function renderTop() {
  const st = data.state;
  const l = currentLesson();
  const g = currentGroup();
  renderTrafficLight();
  if (st.running) {
    const online = data.students.filter((x) => x.pc).length;
    lessonEl.replaceChildren(h("span", { class: "live" }, st.paused ? "⏸ пауза" : "● идёт урок"),
      h("b", {}, `Занятие ${l.lesson}. ${l.title}`), h("small", {}, `${g ? g.name : "?"} · на уроке ${online} из ${data.students.length}`));
  } else lessonEl.replaceChildren(h("b", {}, "Занятие не идёт"), h("small", {}, "выберите группу и занятие на вкладке «Класс»"));
  timerBox.replaceChildren();
  if (st.running) {
    timerBox.append(st.timer_end
      ? h("span", { class: "row" }, h("span", { class: "timer", id: "timer" }, "⏱ " + mmss(Math.max(0, Math.round(st.timer_end - data.now)))),
          h("button", { class: "ghost small", title: "Добавить 5 минут", onclick: () => act("timer", { add: 5 }) }, "+5"),
          h("button", { class: "ghost small", title: "Убрать таймер", onclick: () => act("timer", { clear: true }) }, "✕"))
      : h("span", { class: "row" }, h("span", { class: "small sky" }, "⏱ таймер"),
          [5, 10, 15, 30].map((m) => h("button", { class: "ghost small", title: `Таймер на ${m} минут`, onclick: () => act("timer", { minutes: m, label: "Практика" }) }, m))));
  }
  const sound = store.get("kurs.sound") !== "off";
  const item = (icon, text, fn, hint) => h("button", { class: "menu-item", title: hint || "", onclick: () => { menuOpen = false; fn(); } }, h("span", { class: "mi" }, icon), text);
  const menu = h("div", { class: "menu" + (menuOpen ? "" : " hidden") },
    item("📽", "Слайды / Презентация", openSlides, "Открыть слайды к уроку для проектора"),
    st.running ? item("🖥", "Экран для проектора", () => window.open("/teacher/projector.html", "kurs-projector"), "Таймер и прогресс без имён") : null,
    item("🔄", "Перезапустить VS Code у всех", () => { if (confirm("Перезапустить VS Code у всех учеников? Их работа сохранится, вход останется.")) act("restart_clients"); }),
    item("⏻", "Закрыть VS Code у всех", () => { if (confirm("Закрыть VS Code у всех учеников? Их файлы сохранятся. Открыть снова — ярлыком «Курс».")) act("close_clients"); }),
    data.focus_all
      ? item("🔓", "Снять блокировку игр у всех", () => act("toggle_focus", { on: false }), "Разрешить игры и браузеры всем")
      : item("🛡️", "Заблокировать игры и браузеры у всех", () => {
          if (confirm("Включить режим урока у ВСЕХ учеников? Браузеры, Майнкрафт и игры будут принудительно закрыты.")) act("toggle_focus", { on: true });
        }, "Принудительно закрыть игры и браузеры на всех компьютерах"),
    data.block_sites_all
      ? item("🔓", "Разрешить ИИ и соцсети в браузере у всех", () => act("toggle_block_sites", { on: false }), "Разрешить ChatGPT, DeepSeek, Алису, ГигаЧат и VK")
      : item("🚫", "Запретить ИИ и VK в браузере у всех", () => {
          if (confirm("Закрывать вкладки с ChatGPT, DeepSeek, Алисой AI, ГигаЧатом, VK и др. на ВСЕХ компьютерах? Обычные сайты и VS Code продолжат работать.")) act("toggle_block_sites", { on: true });
        }, "Тихо закрывать ChatGPT, DeepSeek, Алису, ГигаЧат, VK и соцсети"),
    st.running ? item("⬇", "Скачать таблицу результатов", () => { downloadExport("/tapi/export.csv", "results.csv"); }) : null,
    item("↺", "Сбросить прогресс занятия у группы", () => {
      const lessonNum = st.running ? st.lesson : pick.lesson;
      const groupId = st.running ? data.state.group_id : pick.group;
      if (!lessonNum || !groupId) return alert("Сначала выберите группу и занятие");
      const l = data.lessons.find((x) => x.lesson === lessonNum);
      const g = data.groups.find((x) => x.id === groupId);
      const title = l ? l.title : `Занятие ${lessonNum}`;
      const groupName = g ? g.name : "выбранной группы";
      if (confirm(`Сбросить прогресс занятия ${lessonNum} («${title}») у ВСЕХ учеников группы «${groupName}»?\n\nВсе выполненные задания, попытки и подсказки этого урока будут очищены.`)) {
        act("reset_lesson_progress", { lesson: lessonNum, group_id: groupId });
      }
    }, "Очистить попытки и оценки по всем заданиям урока у группы"),
    data.course.id === "chatbots" ? item("📦", "Скачать проекты команд (ZIP)", () => { downloadExport("/tapi/export_projects.zip", "projects.zip"); }, "Все боты, код и команда.json") : null,
    data.course.id === "chatbots" ? item("📄", "Скачать проекты команд (JSON)", () => { downloadExport("/tapi/export_projects.json", "projects.json"); }, "Машиночитаемый JSON для парсинга") : null,
    item(sound ? "🔔" : "🔕", sound ? "Звук сигналов: включён" : "Звук сигналов: выключен", () => { store.set("kurs.sound", sound ? "off" : "on"); renderTop(); }),
    h("hr", {}),
    item("🚪", "Выйти из пульта", async () => { await api("POST", "/tapi/logout", {}); boot(); }));
  const parts = [];
  parts.push(h("button", { class: "ghost", title: "Открыть презентацию со слайдами к уроку", onclick: openSlides }, "📽 Слайды"));
  if (st.running) {
    parts.push(h("button", { class: st.paused ? "on" : "ghost", title: "Закрыть экраны учеников надписью «Смотрим на учителя»", onclick: () => act("pause", { paused: !st.paused }) }, st.paused ? "▶ Снять паузу" : "⏸ Пауза"));
    parts.push(h("button", { class: "danger", onclick: () => {
      if (!confirm("Завершить занятие? Работы учеников сохранятся здесь, а с компьютеров учеников сотрутся.")) return;
      const close = confirm("Закрыть VS Code на компьютерах учеников?\n\n«ОК» — закрыть, «Отмена» — оставить открытым.");
      act("end").then((ok) => { if (ok && close) act("close_clients"); });
    } }, "Завершить занятие"));
  }
  parts.push(h("span", { class: "menu-wrap" }, h("button", { class: "ghost", onclick: (e) => { e.stopPropagation(); menuOpen = !menuOpen; renderTop(); } }, "⋯ Ещё"), menu));
  actionsEl.replaceChildren(...parts);
  clearInterval(clockTimer);
  clockTimer = null;
  if (st.timer_end) {
    const offset = Date.now() / 1000 - data.now;
    clockTimer = setInterval(() => {
      const el = document.getElementById("timer");
      if (el) el.textContent = "⏱ " + mmss(Math.max(0, Math.round(st.timer_end + offset - Date.now() / 1000)));
    }, 1000);
  }
}

function renderNav() {
  const isGames = data.course?.id === "games";
  if (isGames && tab === "ai") {
    tab = "class";
    store.set("kurs.tab", "class");
  }
  const visibleTabs = isGames ? TABS.filter(([id]) => id !== "ai") : TABS;
  const att = data.requests.length + data.help.length + (data.locks || []).length;
  const badges = {
    class: att,
    ai: ai && ai.status.active_count ? ai.status.active_count : (ai && ai.status.last_error && aiUsed() ? "!" : (ai && ai.today ? ai.today : 0)),
    play: play ? play.invites_in.length : 0,
    // на занятии-проекте: сколько учеников ещё без команды
    project: teams && teams.team_lesson && teams.teams.length ? teams.free.length : 0,
  };
  const soft = { play: play && play.matches.length ? play.matches.length : 0 };
  const key = JSON.stringify([data.course?.id || "", tab, badges, soft]);
  if (key === navKey && navEl.childElementCount) return;
  navKey = key;
  const focused = navEl.contains(document.activeElement) ? document.activeElement.id : "";
  navEl.replaceChildren(...visibleTabs.map(([id, ic, title]) => h("button", { id: "nav-" + id, class: "tab" + (tab === id ? " on" : ""),
    "aria-current": tab === id ? "page" : null, onclick: () => goTab(id) },
    h("span", { class: "ic", "aria-hidden": "true" }, ic), title,
    badges[id] ? h("span", { class: "badge" }, badges[id]) : null,
    soft[id] ? h("span", { class: "badge soft", title: "Идут партии" }, soft[id]) : null)));
  if (focused) document.getElementById(focused)?.focus({ preventScroll: true });
}

function render() {
  if (data.course?.id === "games" && tab === "ai") {
    tab = "class";
    store.set("kurs.tab", "class");
  }
  const y = window.scrollY;
  const prevSide = app.querySelector(".side");
  const sideTop = prevSide ? prevSide.scrollTop : 0;
  const prevWrap = app.querySelector(".wrap");
  const wrapLeft = prevWrap ? prevWrap.scrollLeft : 0;
  const wrapTop = prevWrap ? prevWrap.scrollTop : 0;
  lastRenderAt = Date.now();
  const views = {
    class: () => (data.state.running ? renderLesson() : [...renderIdle(), data.poll ? modulePollCard() : null]),
    ai: () => aiTab(),
    play: () => playTab(),
    project: () => projectTab(),
    groups: () => [renderGroups()],
    connect: () => [connectCard(), h("section", { class: "card" }, h("h2", {}, "Адрес для учеников"), addresses())],
  };
  app.replaceChildren(...[].concat(views[tab]()).filter((x) => x));
  const nextSide = app.querySelector(".side");
  if (nextSide && sideTop) nextSide.scrollTop = sideTop;
  const nextWrap = app.querySelector(".wrap");
  if (nextWrap) {
    if (wrapLeft) nextWrap.scrollLeft = wrapLeft;
    if (wrapTop) nextWrap.scrollTop = wrapTop;
  }
  window.scrollTo(0, y);
}

// ---------- до занятия ----------
function renderIdle() {
  if (pick.group === null && data.groups.length) pick.group = data.state.group_id || data.groups[0].id;
  if (pick.lesson === null || !data.lessons.some((l) => l.lesson === pick.lesson)) {
    pick.lesson = (data.lessons.some((l) => l.lesson === data.state.lesson) ? data.state.lesson : null) || (data.lessons[0] && data.lessons[0].lesson);
  }

  const courseCard = h("div", { class: "course-switch", style: "margin-bottom:14px; padding:12px 14px; background:var(--card); border:1px solid var(--line); border-radius:10px;" },
    h("div", { class: "row", style: "gap:8px; align-items:center; margin-bottom:8px" },
      h("span", { style: "font-size:18px" }, "📚"),
      h("b", {}, "Программа курса:"),
      data.course ? h("span", { class: "pill" }, data.course.title) : null
    ),
    h("div", { class: "row", style: "gap:8px; flex-wrap:wrap" },
      (data.courses || []).map((c) =>
        h("button", {
          class: "choice" + ((data.course && data.course.id === c.id) ? " sel" : ""),
          style: "flex:1; min-width:min(100%, 240px); text-align:left;",
          onclick: () => { act("set_course", { course: c.id }); }
        },
        h("b", {}, (c.id === "games" ? "🎮 " : "🤖 ") + c.title),
        h("small", {}, c.subtitle))
      )
    )
  );

  const parts = (data.course && data.course.parts) || [];
  let lessonButtons = [];
  if (parts.length > 0) {
    for (const part of parts) {
      const partLessons = data.lessons.filter((l) => part.lessons.includes(l.lesson));
      if (!partLessons.length) continue;
      lessonButtons.push(
        h("div", { class: "section-title", style: "margin:10px 0 4px; font-weight:bold; color:var(--blue); font-size:12px; text-transform:uppercase; letter-spacing:0.5px;" },
          part.title
        )
      );
      for (const l of partLessons) {
        lessonButtons.push(
          h("button", { class: "choice" + (pick.lesson === l.lesson ? " sel" : ""), onclick: () => { pick.lesson = l.lesson; render(); } },
            `Занятие ${l.lesson}. ${l.title}`, h("small", {}, `${l.tasks.length} ${plural(l.tasks.length, "задание", "задания", "заданий")}`))
        );
      }
    }
  } else {
    lessonButtons = data.lessons.map((l) =>
      h("button", { class: "choice" + (pick.lesson === l.lesson ? " sel" : ""), onclick: () => { pick.lesson = l.lesson; render(); } },
        `Занятие ${l.lesson}. ${l.title}`, h("small", {}, `${l.tasks.length} ${plural(l.tasks.length, "задание", "задания", "заданий")}`))
    );
  }

  const wizard = h("section", { class: "card" },
    h("h2", {}, "Начать занятие"),
    courseCard,
    h("div", { class: "wizard" },
      h("div", {}, h("div", { class: "row" }, h("span", { class: "num" }, "1"), h("b", {}, "Группа")),
        data.groups.length ? data.groups.map((g) => h("button", { class: "choice" + (pick.group === g.id ? " sel" : ""), onclick: () => { pick.group = g.id; render(); } },
          g.name, h("small", {}, `${g.students.length} ${plural(g.students.length, "ученик", "ученика", "учеников")}`)))
          : h("p", { class: "muted" }, "Пока нет групп — добавьте ниже.")),
      h("div", {}, h("div", { class: "row" }, h("span", { class: "num" }, "2"), h("b", {}, "Занятие")),
        lessonButtons),
      h("div", {}, h("div", { class: "row" }, h("span", { class: "num" }, "3"), h("b", {}, "Начать")),
        h("p", { class: "muted" }, "После начала ученики увидят список группы. Каждый вход вы подтверждаете сами."),
        h("div", { class: "row", style: "gap:10px;margin-bottom:8px;flex-wrap:wrap;align-items:center;" },
          h("button", { class: "big", disabled: !pick.group || !pick.lesson, onclick: () => act("start", { group_id: pick.group, lesson: pick.lesson }) }, "▶ Начать занятие"),
          h("button", {
            class: "ghost small danger",
            disabled: !pick.group || !pick.lesson,
            title: "Очистить все результаты проверок и попытки выбранного занятия для этой группы",
            onclick: () => {
              const g = data.groups.find((x) => x.id === pick.group);
              const l = data.lessons.find((x) => x.lesson === pick.lesson);
              const gName = g ? g.name : "выбранной группы";
              const lTitle = l ? l.title : `Занятие ${pick.lesson}`;
              if (!confirm(`Сбросить прогресс занятия ${pick.lesson} («${lTitle}») у группы «${gName}»?\n\nВсе выполненные задания, попытки и подсказки учеников будут очищены.`)) return;
              act("reset_lesson_progress", { lesson: pick.lesson, group_id: pick.group });
            }
          }, "↺ Сбросить прогресс занятия у группы")),
        addresses())));
  const cards = [wizard,
    h("div", { class: "hint-cards" },
      h("button", { class: "hint-card", onclick: openSlides }, h("b", {}, "📽 Презентация"), h("small", {}, "открыть слайды к уроку для проектора")),
      h("button", { class: "hint-card", onclick: () => goTab("groups") }, h("b", {}, "👥 Группы"), h("small", {}, "добавить группу и учеников")),
      h("button", { class: "hint-card", onclick: () => goTab("connect") }, h("b", {}, "🔌 Подключение"), h("small", {}, "команда для компьютеров учеников")),
      data.course?.id !== "games" ? h("button", { class: "hint-card", onclick: () => goTab("ai") }, h("b", {}, "🤖 Нейросеть"), h("small", {}, "ключ GigaChat и проверка связи")) : null)];
  const last = data.state.last_class;
  const lastGroup = last && data.groups.find((g) => g.id === last.group_id);
  const lastLesson = last && (last.course && last.course !== data.course.id
    ? { lesson: last.lesson, title: last.lesson_title || data.courses.find((c) => c.id === last.course)?.title }
    : data.lessons.find((l) => l.lesson === last.lesson));
  if (lastGroup && lastLesson) {
    const n = (last.open_tasks || []).length;
    cards.unshift(h("section", { class: "card" }, h("h2", {}, "Продолжить прошлое занятие"),
      h("p", {}, `${lastGroup.name} · Занятие ${lastLesson.lesson}. ${lastLesson.title}`),
      h("p", { class: "muted" }, `Вернутся открытые задания (${n}). Решённые задания и файлы учеников сохранены — заново ничего делать не нужно.`),
      h("div", { class: "row", style: "gap:10px;flex-wrap:wrap;align-items:center;" },
        h("button", { class: "big", onclick: () => act("continue") }, "⏯ Продолжить занятие"),
        !last.course || last.course === data.course.id ? h("button", {
          class: "ghost small danger",
          title: "Сбросить результаты прошлого занятия",
          onclick: () => {
            if (!confirm(`Сбросить прогресс занятия ${lastLesson.lesson} («${lastLesson.title}») у группы «${lastGroup.name}»?\n\nВсе выполненные задания и попытки учеников будут очищены.`)) return;
            act("reset_lesson_progress", { lesson: lastLesson.lesson, group_id: lastGroup.id });
          }
        }, "↺ Сбросить прогресс этого занятия") : null)));
  }
  return cards;
}

function addresses() {
  const port = serverPort();
  if (!data.addresses.length) return h("p", { class: "muted" }, "Адрес в сети не найден: проверьте подключение.");
  return h("p", {}, "Адрес для учеников: ", data.addresses.map((a, i) => [i ? " " : "", h("span", { class: "addr" }, `${a}:${port}`)]));
}

function connectCard() {
  // команда для первого запуска на компьютере ученика: скачивает запуск курса с этого сервера
  const port = serverPort();
  const url = `${location.protocol}//${data.addresses[0] || "АДРЕС_УЧИТЕЛЯ"}:${port}`;
  const linux = `wget -T 10 -qO- ${url}/k | python3 - --shortcut`;
  const mac = `curl -sm 10 ${url}/k | python3 - --shortcut`;
  const win = `py -c "import urllib.request as u; exec(u.urlopen('${url}/k', timeout=10).read())" --shortcut`;
  return h("section", { class: "card" }, h("h2", {}, "Как подключить компьютер ученика (один раз на каждый компьютер)"), h("div", {},
    h("p", {}, "Откройте на компьютере ученика терминал и выполните команду. Linux:"),
    h("pre", { class: "code" }, linux),
    h("p", { class: "muted" }, "macOS:"), h("pre", { class: "code" }, mac),
    h("p", { class: "muted" }, "Windows:"), h("pre", { class: "code" }, win),
    h("p", { class: "muted" }, `Проверка связи: на компьютере ученика в браузере должен открываться ${url}. Не открывается — не тот адрес (другие адреса этого ПК: ${data.addresses.slice(1).join(", ") || "нет"}) или порт ${port} закрыт брандмауэром.`),
    h("p", { class: "muted" }, "Команда поставит панель курса в отдельный профиль VS Code (обычный VS Code не меняется), создаст папку «Курс» и ярлык «Курс» на рабочем столе. Дальше ученик открывает курс ярлыком.")));
}

function renderGroups() {
  const box = h("section", { class: "card" }, h("h2", {}, "Группы"));
  if (!data.groups.length && editingGroup === null) editingGroup = "new";
  for (const g of data.groups) {
    if (editingGroup === g.id) { box.append(groupForm(g)); continue; }
    box.append(h("div", { class: "list-item" },
      h("div", { class: "grow" }, h("b", {}, g.name), " ", h("span", { class: "muted" }, g.students.join(", ") || "нет учеников")),
      h("button", { class: "ghost small", onclick: () => { editingGroup = g.id; render(); } }, "Изменить"),
      h("button", { class: "ghost small", onclick: () => { if (confirm(`Удалить группу «${g.name}»? Результаты останутся в базе.`)) act("group/delete", { id: g.id }); } }, "Удалить")));
  }
  if (editingGroup === "new") box.append(groupForm(null));
  else box.append(h("button", { class: "ghost", style: "margin-top:8px", onclick: () => { editingGroup = "new"; render(); } }, "+ Новая группа"));
  return box;
}

function groupForm(g) {
  const name = h("input", { placeholder: "Название, например «Среда 16:00»", value: g ? g.name : "", style: "width:100%" });
  const names = h("textarea", { placeholder: "Имена учеников, по одному в строке.\nЛучше имя и первую букву фамилии: «Аня К.»" });
  names.value = g ? g.students.join("\n") : "";
  const save = async () => {
    if (busy) return;
    busy = true;
    try {
      await api("POST", "/tapi/group", { id: g ? g.id : null, name: name.value, names: names.value.split("\n") });
      editingGroup = null;
      await refresh();
    } catch (e) {
      if (e.status === 401) { boot(); return; }
      alert(e.message);
    } finally {
      busy = false;
    }
  };
  return h("div", { class: "card", style: "box-shadow:none;background:#FAFAFE" },
    h("h2", {}, g ? "Изменить группу" : "Новая группа"),
    name, h("div", { style: "height:8px" }), names,
    h("p", { class: "muted small" }, "Храним только имя. Полные фамилии не нужны."),
    h("div", { class: "row" }, h("button", { onclick: save }, "Сохранить"),
      data.groups.length ? h("button", { class: "ghost", onclick: () => { editingGroup = null; render(); } }, "Отмена") : null));
}

// ---------- во время занятия ----------
function renderLesson() {
  const st = data.state;
  const lesson = currentLesson();
  const out = [];
  if (st.paused) out.push(h("div", { class: "pause-banner" }, "⏸", h("span", {}, "У учеников пауза: панель закрыта экраном «Смотрим на учителя»."),
    h("span", { class: "spacer" }), h("button", { class: "ghost small", onclick: () => act("pause", { paused: false }) }, "Снять паузу")));
  out.push(h("div", { class: "grid" },
    h("div", { class: "side" }, attentionCard(), projectBrief(lesson), stepsCard(lesson), modulePollCard()),
    h("div", {}, tiles(), tableCard(lesson))));
  return out;
}

function updatePollIdeas(host, poll, options) {
  const key = JSON.stringify(poll.ideas);
  if (host.dataset.ideas === key) return;
  host.dataset.ideas = key;
  const total = poll.ideas.reduce((n, item) => n + item.count, 0);
  const list = h("ul", { class: "poll-results poll-ideas" }, poll.ideas.map(({ topic, count }) => {
    const add = h("button", { class: "ghost small", "aria-label": "Добавить в бюллетень: " + topic,
      onclick: () => {
        const current = options.value.split("\n").map((line) => line.trim()).filter(Boolean);
        if (!current.some((line) => line.toLowerCase() === topic.toLowerCase())) current.push(topic);
        pollDraft.options = options.value = current.join("\n");
        options.focus();
      } }, "Добавить");
    return h("li", {}, h("div", {}, h("b", {}, topic), h("small", { class: "muted" }, "Предложили: " + count)), add);
  }));
  host.querySelector("p").textContent = "Идёт сбор идей · предложений: " + total;
  host.lastElementChild.replaceChildren(poll.ideas.length ? list : h("p", { class: "muted" }, "Идеи учеников появятся здесь."));
}

function modulePollCard() {
  const poll = data.poll;
  const running = Boolean(data.state.running);
  const group = data.groups.find((g) => g.id === data.state.group_id);
  const card = h("section", { class: "card module-poll", "aria-labelledby": "module-poll-title" },
    h("h2", { id: "module-poll-title" }, "Голосование за следующий модуль"));
  if (poll?.options.length) {
    card.append(h("p", {}, h("b", {}, poll.question)),
      h("p", { class: "muted small" }, (group ? group.name + " · " : "") +
        (poll.open ? "Идёт голосование" : "Голосование завершено") + " · голосов: " + poll.total),
      h("ul", { class: "poll-results" }, poll.options.map((topic, i) =>
        h("li", {}, h("span", {}, topic), h("b", {}, poll.counts[i])))));
    if (poll.open) {
      card.append(h("button", { id: "poll-close", class: "ghost",
        onclick: (e) => submitPoll("poll/close", { id: poll.id }, card, e.currentTarget) },
        "Завершить голосование"));
      return card;
    }
  }
  const collecting = poll?.phase === "ideas";
  if (poll?.phase === "closed" && !poll.options.length) {
    card.append(h("p", { class: "muted" }, "Сбор идей завершён."));
  }
  if (collecting) {
    card.append(h("p", {}, h("b", {}, poll.question)));
  }
  if (!running) return card;
  const draftKey = [data.state.group_id, data.course.id, poll?.id, poll?.phase].join("/");
  if (pollDraft?.key !== draftKey) {
    pollDraft = { key: draftKey, question: "Что вы хотите попробовать разработать в следующем модуле?",
      options: collecting ? "" : "2D-игры на Pygame\nЧат-боты и ИИ-агенты\nВеб-приложения на Python\nАвтоматизация на Python" };
  }
  const question = h("input", { id: "poll-question", required: true, maxlength: "120", value: pollDraft.question,
    oninput: (e) => { pollDraft.question = e.target.value; } });
  const options = h("textarea", { id: "poll-options", required: true, rows: "4", "aria-describedby": "poll-options-hint" },
    pollDraft.options);
  options.addEventListener("input", (e) => { pollDraft.options = e.target.value; });
  const publish = h("button", { id: "poll-publish", type: "submit" }, "Открыть голосование");
  const ballot = h("form", { class: "poll-form", onsubmit: (e) => {
    e.preventDefault();
    const payload = { options: options.value.split("\n"), question: question.value, id: poll?.id };
    submitPoll(collecting ? "poll/publish" : "poll", payload, card, publish);
  } }, h("label", { for: options.id }, "Темы для голосования"), options,
    h("small", { id: "poll-options-hint", class: "muted" }, "От 2 до 8 тем, по одной на строку. Темы можно отредактировать и добавить свои."),
    publish);
  if (collecting) {
    const live = h("div", { id: "poll-live-ideas", "data-poll-id": poll.id },
      h("p", { id: "poll-ideas-status", class: "muted small", role: "status", tabindex: "-1" }), h("div"));
    updatePollIdeas(live, poll, options);
    card.append(live,
      ballot,
      h("button", { id: "poll-close", class: "ghost",
        onclick: (e) => submitPoll("poll/close", { id: poll.id }, card, e.currentTarget) }, "Завершить сбор идей"));
  } else {
    card.append(h("form", { class: "poll-form", onsubmit: (e) => {
      e.preventDefault();
      submitPoll("poll/collect", { question: question.value }, card, e.submitter || e.currentTarget.querySelector("button"));
    } }, h("label", { for: question.id }, "Вопрос ученикам"), question,
      h("button", { id: "poll-collect", type: "submit" }, "Начать сбор идей")),
      details("poll-ready-" + draftKey, "У меня уже есть список тем", ballot));
  }
  return card;
}

async function submitPoll(path, payload, card, button) {
  if (button.disabled || card.getAttribute("aria-busy") === "true") return;
  card.querySelector("[role=alert]")?.remove();
  button.disabled = true;
  card.setAttribute("aria-busy", "true");
  try {
    await api("POST", "/tapi/" + path, payload);
    card.removeAttribute("aria-busy");
    await refresh();
    const key = stateFingerprint();
    if (key !== lastKey) {
      lastKey = key;
      render();
    }
    const next = path === "poll/collect" ? "poll-ideas-status" : path === "poll/close" ? "poll-collect" : "poll-close";
    document.getElementById(next)?.focus({ preventScroll: true });
  } catch (e) {
    if (e.status === 401) return boot();
    card.append(h("p", { class: "poll-error", role: "alert" }, e.message));
    button.focus({ preventScroll: true });
  } finally {
    button.disabled = false;
    card.removeAttribute("aria-busy");
  }
}

// на занятиях с проектом: коротко про идеи и команды, подробно — на вкладке «Проекты»
function projectBrief(lesson) {
  if (!teams || !(lesson.project_idea || lesson.teams)) return null;
  const game = teams.team_project === "game";
  const text = lesson.teams
    ? (teams.teams.length ? `Команд: ${teams.teams.length} · без команды: ${teams.free.length}` +
        (game ? ` · сдали: ${teams.teams.filter((team) => team.studio?.release).length}` : "") +
        (teams.cfg.open ? " · запись открыта" : " · запись закрыта") : "Команд ещё нет — создайте их, ученики выберут сами.")
    : `Идей записано: ${teams.ideas.length} из ${data.students.length}. Ученики пишут их на вкладке «💡 Проект».`;
  return h("section", { class: "card" }, h("div", { class: "card-head" }, h("h2", {}, game ? "Студия разработки игры" : lesson.teams ? "👥 Команды" : "💡 Идеи проектов"),
    h("span", { class: "spacer" }), h("button", { class: "ghost small", onclick: () => goTab("project") }, game ? "Управлять командами" : "Открыть «Проекты»")),
    h("p", { class: "small" }, text));
}

function tiles() {
  const total = data.students.length;
  const online = data.students.filter((s) => s.pc).length;
  const open = data.state.open_tasks;
  const passedCells = data.students.reduce((n, s) => n + open.filter((id) => s.results[id] && s.results[id].status === "passed").length, 0);
  const pct = total && open.length ? Math.round((100 * passedCells) / (total * open.length)) : 0;
  const tile = (cls, v, l, extra) => h("div", { class: "tile " + cls }, h("div", { class: "v" }, v), h("div", { class: "l" }, l), extra);
  return h("div", { class: "tiles" },
    tile(online === total && total ? "good" : "", `${online} / ${total}`, "учеников на уроке"),
    tile(data.requests.length ? "alert" : "", data.requests.length, "ждут подтверждения входа"),
    tile(data.help.length ? "alert" : "", data.help.length, "зовут на помощь"),
    tile("", `${pct}%`, open.length ? "открытых заданий выполнено" : "задания ещё не открыты", h("div", { class: "bar" }, h("i", { style: `width:${pct}%` }))));
}

function attentionCard() {
  const locks = data.locks || [];
  const invites = play ? play.invites_in : [];
  const n = data.requests.length + data.help.length + locks.length + invites.length;
  const box = h("section", { class: "card" }, h("div", { class: "card-head" },
    h("h2", {}, "Требует внимания"), h("span", { class: "badge" + (n ? "" : " zero") }, n), h("span", { class: "spacer" }),
    data.requests.length > 1 ? h("button", { class: "ok small", onclick: () => act("approve_all") }, "Пустить всех") : null));
  const lockSwitch = h("label", { class: "check small", style: "margin-top:8px", title: "Вставил чужой код — панель ученика блокируется до вашего решения" },
    h("input", { type: "checkbox", checked: data.state.lock_on_paste ? true : null, onchange: (e) => act("lock_on_paste", { on: e.target.checked }) }),
    " блокировать панель при вставке чужого кода");
  const focusCount = (data.students || []).filter((s) => s.focus).length;
  const focusAll = Boolean(data.focus_all);
  const focusActive = focusAll || focusCount > 0;
  const focusControl = h("div", { style: "margin-top:10px;padding-top:8px;border-top:1px solid var(--line);display:flex;align-items:center;justify-content:space-between;gap:8px;" },
    h("span", { class: "small", style: "font-weight:600;color:var(--text);" },
      focusAll ? "🛡️ Блок игр: у всех" : (focusCount > 0 ? `🛡️ Блок игр: ${focusCount} уч.` : "🛡️ Блокировка игр и браузеров")
    ),
    h("button", {
      class: "ghost small" + (focusActive ? " danger" : ""),
      onclick: () => act("toggle_focus", { on: !focusActive })
    }, focusActive ? "Снять у всех" : "Вкл у всех")
  );
  const blockSitesCount = (data.students || []).filter((s) => s.block_sites).length;
  const blockSitesAll = Boolean(data.block_sites_all);
  const blockSitesActive = blockSitesAll || blockSitesCount > 0;
  const blockSitesControl = h("div", { style: "margin-top:8px;padding-top:8px;border-top:1px solid var(--line);display:flex;align-items:center;justify-content:space-between;gap:8px;" },
    h("span", { class: "small", style: "font-weight:600;color:var(--text);" },
      blockSitesAll ? "🚫 Блок ГПТ/Алиса/ГигаЧат/VK: у всех" : (blockSitesCount > 0 ? `🚫 Блок ГПТ/Алиса/ГигаЧат/VK: ${blockSitesCount} уч.` : "🚫 Блок ГПТ / Алиса / ГигаЧат / VK")
    ),
    h("button", {
      class: "ghost small" + (blockSitesActive ? " danger" : ""),
      onclick: () => act("toggle_block_sites", { on: !blockSitesActive })
    }, blockSitesActive ? "Снять у всех" : "Вкл у всех")
  );
  if (!n) { box.append(h("div", { class: "calm" }, h("b", {}, "Всё спокойно ✓"), "Новые запросы появятся здесь, а вкладка браузера покажет их число."), lockSwitch, focusControl, blockSitesControl); return box; }
  for (const inv of invites) {
    box.append(h("div", { class: "att" }, h("span", { class: "ic" }, "🎮"),
      h("div", { class: "txt" }, h("b", {}, inv.name), " зовёт вас сыграть", h("small", {}, KursPlay.titles[inv.game] || inv.game)),
      h("button", { class: "ok small", onclick: () => act("play/answer", { id: inv.id, accept: true }) }, "Играть"),
      h("button", { class: "ghost small", onclick: () => act("play/answer", { id: inv.id, accept: false }) }, "Нет")));
  }
  for (const x of locks) {
    box.append(h("div", { class: "att lock" }, h("span", { class: "ic" }, "🔒"),
      h("div", { class: "txt" }, h("b", {}, x.name), x.pc ? ` · ${x.pc}` : "",
        h("small", {}, `${x.kind === "outside_edit" ? "менял файл не в редакторе" : "вставил чужой код"}${x.file ? " · " + x.file : ""} · ${ago(x.ts, data.now)}`),
        h("div", { class: "row", style: "margin-top:6px" },
          h("button", { class: "ghost small", onclick: () => showStudent(x.student_id) }, "Посмотреть"),
          h("button", { class: "ok small", onclick: () => act("unlock", { student_id: x.student_id }) }, "Разблокировать")))));
  }
  for (const r of data.requests) {
    let text, sub;
    if (r.kind === "switch") { text = [h("b", {}, r.name), " садится за ", r.pc]; sub = `вместо ${r.prev}`; }
    else if (r.kind === "transfer") { text = [h("b", {}, r.name), " пересаживается"]; sub = `с ${r.other_pc} на ${r.pc}`; }
    else { text = [h("b", {}, r.name), " входит"]; sub = `компьютер ${r.pc}`; }
    box.append(h("div", { class: "att" }, h("span", { class: "ic" }, "🔑"), h("div", { class: "txt" }, text, h("small", {}, sub)),
      h("button", { class: "ok small", onclick: () => act("request", { id: r.id, approve: true }) }, "Пустить"),
      h("button", { class: "ghost small", onclick: () => act("request", { id: r.id, approve: false }) }, "Нет")));
  }
  for (const x of data.help) {
    box.append(h("div", { class: "att help" }, h("span", { class: "ic" }, "🙋"),
      h("div", { class: "txt" }, h("b", {}, x.name), ` · ${x.pc || ""}`,
        h("small", {}, (x.text ? `«${x.text}» · ` : "") + ago(x.created, data.now) + (x.status === "going" ? " · вы идёте" : ""))),
      x.status !== "going" ? h("button", { class: "ghost small", onclick: () => act("help", { id: x.id, going: true }) }, "Иду") : null,
      h("button", { class: "ok small", onclick: () => act("help", { id: x.id }) }, "Готово")));
  }
  box.append(lockSwitch, focusControl, blockSitesControl);
  return box;
}

function stepsCard(lesson) {
  const open = new Set(data.state.open_tasks);
  const box = h("section", { class: "card" }, h("div", { class: "card-head" }, h("h2", {}, "Ход урока"), h("span", { class: "spacer" }),
    h("button", { class: "ghost small", onclick: () => act("open", { all: true, open: true }) }, "Открыть все задания"),
    h("button", { class: "ghost small", onclick: () => act("open", { all: true, open: false }) }, "Закрыть все")));
  box.append(h("div", { class: "steps" }, lesson.steps.map((s) => {
    const tasks = lesson.tasks.filter((t) => t.step === s.n);
    const isOpen = tasks.length && tasks.every((t) => open.has(t.id));
    return h("div", { class: "step" + (isOpen ? " open" : "") },
      h("span", { class: "n" }, `Шаг ${s.n}`), h("b", {}, s.title),
      h("span", { class: "tasks" }, tasks.length ? `${plural(tasks.length, "Задание", "Задания", "Задания")} ${tasks.map((t) => t.num).join(", ")}` : "без заданий"),
      tasks.length ? h("button", { class: "small" + (isOpen ? " ghost" : ""), onclick: () => act("open", { ids: tasks.map((t) => t.id), open: !isOpen }) }, isOpen ? "Закрыть" : "Открыть задания") : null);
  })));
  return box;
}

function tableCard(lesson) {
  const open = new Set(data.state.open_tasks);
  const head = h("tr", {}, h("th", { class: "name" }, "Ученик"),
    lesson.tasks.map((t) => h("th", { class: "task " + (open.has(t.id) ? "open" : "closed"), title: `${t.num}. ${t.title} — нажмите, чтобы ${open.has(t.id) ? "закрыть" : "открыть"}`,
      onclick: () => act("open", { ids: [t.id], open: !open.has(t.id) }) },
      h("span", { class: "num" }, t.num), h("span", { class: "lock" }, open.has(t.id) ? "открыто" : "🔒"))),
    h("th", {}, "Итог"));
  const body = h("tbody", {});
  for (const s of data.students) {
    const done = lesson.tasks.filter((t) => s.results[t.id] && s.results[t.id].status === "passed").length;
    const row = h("tr", {}, h("td", { class: "name" },
      h("span", { class: "dot" + (s.online ? " on" : ""), title: s.online ? "на связи" : "не на связи" }),
      h("span", { class: "name-link", onclick: () => showStudent(s.id) }, s.name),
      s.locked ? [" ", h("span", { class: "paste-flag", title: "Панель заблокирована за вставку чужого кода. Нажмите — разблокировать",
        onclick: () => { if (confirm(`Разблокировать панель: ${s.name}?`)) act("unlock", { student_id: s.id }); } }, "🔒")] : null,
      s.pastes ? [" ", h("span", { class: "paste-flag", title: `Пытался вставить готовый код: ${s.pastes} раз за занятие. Нажмите на имя — покажу что.`, onclick: () => showStudent(s.id) }, `⚠ ${s.pastes}`)] : null,
      " ", h("span", { class: "pc" }, s.pc || "не вошёл"),
      s.block_sites
        ? h("button", { class: "link small alert-btn", style: "background:#FFF3E0;color:#E65100;border:1px solid #FFCC80;border-radius:4px;padding:1px 5px;font-size:11px;font-weight:700;margin-left:4px;cursor:pointer;",
            title: `Блок ChatGPT, DeepSeek, Алисы, ГигаЧата и VK ВКЛЮЧЁН для ${s.name}. Нажмите, чтобы разрешить`,
            onclick: () => act("toggle_block_sites", { student_id: s.id, on: false }) }, "🚫 ИИ/ВК")
        : h("button", { class: "link small", style: "color:var(--muted);border:1px solid var(--line);border-radius:4px;padding:1px 5px;font-size:11px;margin-left:4px;cursor:pointer;",
            title: `Закрывать ChatGPT, DeepSeek, Алису, ГигаЧат и VK в браузере у ${s.name}`,
            onclick: () => act("toggle_block_sites", { student_id: s.id, on: true }) }, "🧠 ИИ/ВК"),
      s.focus
        ? h("button", { class: "link small alert-btn", style: "background:#FFEAEA;color:#D32F2F;border:1px solid #FFCDD2;border-radius:4px;padding:1px 5px;font-size:11px;font-weight:700;margin-left:4px;cursor:pointer;",
            title: `Блокировка игр и браузеров ВКЛЮЧЕНА для ${s.name}. Нажмите, чтобы отключить`,
            onclick: () => act("toggle_focus", { student_id: s.id, on: false }) }, "🛡️ Игры")
        : h("button", { class: "link small", style: "color:var(--muted);border:1px solid var(--line);border-radius:4px;padding:1px 5px;font-size:11px;margin-left:4px;cursor:pointer;",
            title: `Заблокировать игры и браузеры для ${s.name}`,
            onclick: () => act("toggle_focus", { student_id: s.id, on: true }) }, "🎮 Игры"),
      s.pc ? h("button", { class: "link small", title: "Перезапустить VS Code у этого ученика (работа сохранится, вход останется)",
        onclick: () => { if (confirm(`Перезапустить VS Code у ученика ${s.name} (${s.pc})? Работа сохранится, вход останется.`)) act("restart_student", { student_id: s.id }); } }, "🔄") : null,
      s.pc ? h("button", { class: "link small", title: "Завершить сеанс ученика", onclick: () => { if (confirm(`Завершить сеанс: ${s.name}?`)) act("kick", { student_id: s.id }); } }, "✕") : null));
    for (const t of lesson.tasks) {
      const r = s.results[t.id];
      if (!r) { row.append(h("td", {}, h("span", { class: "cell empty" }, "·"))); continue; }
      const sign = r.status === "passed" ? "✓" : r.status === "failed" ? "✗" : "…";
      row.append(h("td", {}, h("button", { class: "cell " + r.status, onclick: () => showResult(s, t), title: r.summary || "",
        "aria-label": s.name + ", задание " + t.num + ", " + (r.status === "passed" ? "выполнено" : r.status === "failed" ? "есть ошибки" : "начато") },
        sign, h("small", {}, `${r.attempts}×` + (r.hints ? ` 💡${r.hints}` : "")))));
    }
    row.append(h("td", {}, h("span", { class: "done-count" }, `${done}/${lesson.tasks.length}`)));
    body.append(row);
  }
  const foot = h("tr", {}, h("td", { class: "name" }, "Сдали"), lesson.tasks.map((t) =>
    h("td", {}, `${data.students.filter((s) => s.results[t.id] && s.results[t.id].status === "passed").length}`)), h("td", {}, ""));
  return h("section", { class: "card" }, h("div", { class: "card-head" }, h("h2", {}, "Прогресс класса"), h("span", { class: "spacer" }),
      h("button", { class: "ghost small danger", title: "Сбросить результаты всех заданий этого урока у всех учеников группы",
        onclick: async () => {
          if (!confirm(`Сбросить прогресс урока ${lesson.lesson} («${lesson.title}») у всех учеников группы?\n\nВсе выполненные задания, попытки и подсказки этого урока будут очищены.`)) return;
          await act("reset_lesson_progress", { lesson: lesson.lesson, group_id: data.state.group_id });
        } }, "↺ Сбросить прогресс урока"),
      h("button", { class: "ghost small", onclick: () => { downloadExport("/tapi/export.csv", "results.csv"); } }, "Скачать таблицу")),
    h("div", { class: "legend" },
      h("span", {}, h("i", { style: "background:var(--ok-bg)" }), "выполнено"),
      h("span", {}, h("i", { style: "background:var(--bad-bg)" }), "есть ошибки"),
      h("span", {}, h("i", { style: "background:var(--soft)" }), "начато"),
      h("span", {}, "3× — проверок, 💡2 — подсказок"),
      h("span", {}, "нажмите на клетку — увидите код")),
    h("div", { class: "wrap" }, h("table", { class: "res" }, h("thead", {}, head), body, h("tfoot", {}, foot))));
}

// ---------- вкладка «Нейросеть» ----------
function aiTab() {
  if (!ai) return [h("section", { class: "card" }, h("p", { class: "muted" }, "Загрузка…"))];
  return [h("div", { class: "grid" }, h("div", { class: "side" }, aiCard()), h("div", {}, aiFeed()))];
}

// ---------- вкладка «Игры» ----------
function syncTeacherMatch() {
  const m = play && play.match;
  const cur = KursPlay.current();
  if (m && !leftMatches.has(m.id) && (!cur || cur.matchId !== m.id)) {
    const wsProto = location.protocol === "https:" ? "wss://" : "ws://";
    KursPlay.start({ mode: "net", game: m.game, matchId: m.id, url: `${wsProto}${location.host}/ws/play?match=${encodeURIComponent(m.id)}`, auth: "",
      names: m.names, onEnd: () => { leftMatches.add(m.id); api("POST", "/tapi/play/leave", {}).catch(() => {}); lastKey = ""; refresh(); } });
    if (tab !== "play") goTab("play"); else render();
  }
}

function playTab() {
  if (!play) return [h("section", { class: "card" }, h("p", { class: "muted" }, "Загрузка…"))];
  const cfg = play.config;
  const titles = KursPlay.titles;
  const cur = KursPlay.current();
  const seg = (m, label, hint) => h("button", { class: "seg" + (cfg.mode === m ? " on" : ""), title: hint, onclick: () => act("play/config", { mode: m }) }, label);
  const access = h("section", { class: "card" }, h("h2", {}, "Доступ к играм"),
    h("p", { class: "muted small" }, "Шахматы, аэрохоккей и морской бой в панели ученика — друг с другом, с вами или с компьютером. Время урока не тратится; на паузе игры закрыты у всех."),
    h("div", { class: "segs" }, seg("off", "Закрыты", "Вкладки «Игры» у учеников нет"), seg("all", "Открыты всем"),
      seg("done", "Решившим задания", "Кто решил все открытые сейчас задания")),
    h("div", { class: "row", style: "margin-top:10px" }, Object.entries(titles).map(([id, title]) =>
      h("label", { class: "check" }, h("input", { type: "checkbox", checked: cfg.games.includes(id) ? true : null,
        onchange: (e) => act("play/config", { games: e.target.checked ? cfg.games.concat(id) : cfg.games.filter((x) => x !== id) }) }), title))),
    h("label", { class: "check" }, h("input", { type: "checkbox", checked: cfg.teacher ? true : null, onchange: (e) => act("play/config", { teacher: e.target.checked }) }),
      "принимать вызовы от учеников"),
    play.matches.length ? h("button", { class: "danger small", style: "margin-top:6px", onclick: () => { if (confirm("Остановить все партии?")) act("play/stop_all"); } }, "■ Остановить все партии") : null);
  const people = h("section", { class: "card" }, h("h2", {}, "Ученики"),
    h("p", { class: "muted small" }, cfg.mode === "all" ? "Игры открыты всем." : "Можно открыть игры отдельным ученикам — кнопкой справа от имени."));
  if (!play.students.length) people.append(h("p", { class: "muted" }, "Занятие не идёт — список появится после начала."));
  const busy = new Set(play.matches.flatMap((m) => m.names));
  for (const st of play.students) {
    people.append(h("div", { class: "list-item" },
      h("span", { class: "dot" + (st.online ? " on" : "") }),
      h("span", { class: "grow" }, st.name, busy.has(st.name) ? h("span", { class: "chip" }, "играет") : null),
      h("span", { class: "chip" + (st.allowed ? " ok" : "") }, st.allowed ? "можно играть" : "закрыто"),
      cfg.mode !== "all" ? h("button", { class: "ghost small", onclick: () => act("play/config", { allow: { student_id: st.id, on: !st.manual } }) },
        st.manual ? "Закрыть" : "Открыть") : null));
  }
  const right = [];
  if (cur) {
    right.push(h("section", { class: "card" }, h("h2", {}, "Ваша партия"), KursPlay.host));
  } else {
    const lobbyCard = h("section", { class: "card" }, h("h2", {}, "Сыграть самому"));
    for (const inv of play.invites_in) {
      lobbyCard.append(h("div", { class: "att" }, h("span", { class: "ic" }, "🎮"), h("div", { class: "txt" }, h("b", {}, inv.name), " зовёт вас: ", titles[inv.game]),
        h("button", { class: "ok small", onclick: () => act("play/answer", { id: inv.id, accept: true }) }, "Играть"),
        h("button", { class: "ghost small", onclick: () => act("play/answer", { id: inv.id, accept: false }) }, "Нет")));
    }
    for (const inv of play.invites_out) {
      lobbyCard.append(h("p", {}, `Ждём ответа: ${inv.name} · ${titles[inv.game]} `,
        h("button", { class: "link small", onclick: () => act("play/cancel", { id: inv.id }) }, "Отменить")));
    }
    const free = play.players.filter((x) => x.key !== "t");
    if (!free.length) lobbyCard.append(h("p", { class: "muted" }, "Пока никто из учеников не может играть: откройте доступ слева."));
    for (const pl of free) {
      lobbyCard.append(h("div", { class: "list-item" }, h("span", { class: "grow" }, h("b", {}, pl.name)),
        pl.busy ? h("span", { class: "chip" }, "играет") : cfg.games.map((g) =>
          h("button", { class: "ghost small", title: "Вызвать: " + titles[g], onclick: () => act("play/invite", { to: pl.key, game: g }) }, titles[g]))));
    }
    lobbyCard.append(h("div", { class: "row", style: "margin-top:10px" }, h("span", { class: "muted small" }, "С компьютером:"),
      Object.keys(titles).map((g) => h("button", { class: "ghost small", onclick: () => {
        KursPlay.start({ mode: "cpu", game: g, names: ["Учитель", "Компьютер"], onEnd: () => { lastKey = ""; render(); } });
        render();
      } }, titles[g]))));
    right.push(lobbyCard);
  }
  const live = h("section", { class: "card" }, h("h2", {}, "Идут партии"));
  if (!play.matches.length) live.append(h("p", { class: "muted" }, "Сейчас никто не играет."));
  for (const m of play.matches) {
    live.append(h("div", { class: "list-item" },
      h("span", { class: "grow" }, titles[m.game], " · ", h("b", {}, m.names.join(" — ")),
        h("small", { class: "muted" }, ` · ${mmss(Math.max(0, Math.round(data.now - m.created)))}` + (m.game === "chess" ? ` · ходов: ${m.moves}` : ""))),
      h("button", { class: "ghost small", onclick: () => { if (confirm("Остановить эту партию?")) act("play/end", { match: m.id }); } }, "Остановить")));
  }
  right.push(live);
  return [h("div", { class: "grid" }, h("div", { class: "side" }, access, people), h("div", {}, right))];
}

// ---------- вкладка «Проекты»: команды и идеи учеников ----------
function projectTab() {
  if (!teams) return [h("section", { class: "card" }, h("p", { class: "muted" }, "Загрузка…"))];
  if (!teams.group) return [h("section", { class: "card" }, h("h2", {}, "🚀 Проекты"),
    h("p", { class: "muted" }, "Начните занятие с группой — здесь появятся идеи учеников и команды для проекта."))];
  const cfg = teams.cfg;
  const game = teams.team_project === "game";
  const releases = teams.teams.map((team) => team.studio?.release).filter(Boolean);
  const inTeams = teams.teams.reduce((n, t) => n + t.members.length, 0);
  const small = teams.teams.filter((t) => t.members.length < cfg.min);
  const num = (key, label, hint) => h("label", { class: "field" }, h("span", {}, label),
    h("input", { type: "number", min: "0", max: "50", value: cfg[key], style: "width:90px",
      onchange: (e) => act("teams/config", { [key]: Number(e.target.value || 0) }) }), hint ? h("small", { class: "muted" }, hint) : null);
  const count = h("input", { type: "number", min: "1", max: "30", value: teams.teams.length ? 1
    : game ? Math.min(30, Math.max(1, Math.ceil(teams.free.length / 3))) : 7, style: "width:90px" });
  const names = h("textarea", { placeholder: "Названия по одному в строке (можно не писать — будет «Команда 1», «Команда 2»…)", rows: "3", style: "min-height:64px;margin-top:6px" });
  const create = () => act("teams/create", { count: Number(count.value || 0), names: names.value.split("\n").map((x) => x.trim()).filter(Boolean) });
  const seg = (open, label, hint) => h("button", { class: "seg" + (!!cfg.open === open ? " on" : ""), title: hint, onclick: () => act("teams/config", { open }) }, label);

  const exportCard = game ? h("section", { class: "card" }, h("h2", {}, "Сборки и черновики"),
    h("p", { class: "muted small" }, "Архив содержит сданные версии с меню и текущие черновики команд."),
    h("button", { class: "ghost", disabled: !releases.length && !teams.teams.some((t) => t.members.some((m) => m.has_file)),
      onclick: () => { downloadExport("/tapi/export_games.zip", "games.zip"); } }, "Скачать игры (ZIP)"))
    : data.course.id === "chatbots" ? h("section", { class: "card", style: "border-left:4px solid var(--ok, #10b981)" },
    h("h2", {}, "💾 Экспорт проектов"),
    h("p", { class: "muted small" }, "Выгрузить карточки команд, код участников и файл Наш_бот.py:"),
    h("div", { class: "row", style: "gap:8px;margin-top:8px" },
      h("button", { class: "ok small", onclick: () => { downloadExport("/tapi/export_projects.zip", "projects.zip"); } }, "📦 Скачать все (ZIP)"),
      h("button", { class: "ghost small", onclick: () => { downloadExport("/tapi/export_projects.json", "projects.json"); } }, "📄 Данные (JSON)"))) : null;

  const manage = h("section", { class: "card" }, h("h2", {}, "👥 Команды"),
    game ? h("p", { class: "muted small" }, "Обычно в команде 2–3 ученика. Работу можно начать одному. Сдача доступна и с рабочим шаблоном, это будет видно в карточке.")
      : !teams.team_lesson ? h("p", { class: "muted small" }, "Ученики выбирают команду на финальном занятии. Создать команды можно заранее.") : null,
    h("div", { class: "row", style: "align-items:flex-end;gap:10px" },
      h("label", { class: "field" }, h("span", {}, teams.teams.length ? "Добавить команд" : "Сколько команд"), count),
      h("button", { onclick: create }, teams.teams.length ? "+ Добавить" : "Создать команды")),
    names,
    h("div", { class: "segs", style: "margin-top:10px" }, seg(true, "Запись открыта", "Ученики сами вступают и выходят"),
      seg(false, "Запись закрыта", "Состав меняете только вы")),
    h("div", { class: "row", style: "gap:16px;margin-top:6px" },
      num("min", "Минимум в команде"), num("max", "Максимум", "0 — без ограничения")),
    h("p", { class: "small", style: "margin-top:8px" }, `В командах ${inTeams} из ${inTeams + teams.free.length}` +
      (teams.free.length ? ` · без команды: ${teams.free.length}` : " · все распределены ✓") +
      (small.length && teams.teams.length ? ` · мало участников: ${small.map((t) => t.name).join(", ")}` : "")),
    teams.teams.length ? h("button", { class: "danger small", style: "margin-top:6px", onclick: () => {
      if (confirm("Удалить все команды? Ученики останутся без команд, их файлы сохранятся.")) act("teams/delete", { all: true });
    } }, "Удалить все команды") : null);

  const assignSelect = (sid, current, label) => {
    const sel = h("select", { class: "small", onchange: (e) => { if (e.target.value !== "") act("teams/assign", { student_id: sid, team_id: Number(e.target.value) }); } },
      h("option", { value: "" }, label),
      teams.teams.filter((t) => t.id !== current).map((t) => h("option", { value: t.id }, `→ ${t.name} (${t.members.length})`)),
      current ? h("option", { value: "0" }, "→ без команды") : null);
    return sel;
  };

  const free = h("section", { class: "card" }, h("h2", {}, `Без команды (${teams.free.length})`));
  if (!teams.free.length) free.append(h("p", { class: "muted" }, "Все ученики в командах."));
  for (const st of teams.free) {
    free.append(h("div", { class: "list-item" }, h("span", { class: "dot" + (st.online ? " on" : "") }),
      h("button", { class: "grow link name-link", onclick: () => showStudent(st.id) }, st.name),
      teams.teams.length ? assignSelect(st.id, null, "в команду…") : null));
  }

  const ideasCard = h("section", { class: "card" }, h("h2", {}, `💡 Идеи учеников (${teams.ideas.length})`));
  const ideasLessonHint = data.course?.id === "games" ? "на Занятии 8" : "на Занятии 5";
  if (!teams.ideas.length) ideasCard.append(h("p", { class: "muted" }, `Идей пока нет. Ученики записывают их во вкладке «💡 Проект» ${ideasLessonHint}.`));
  for (const x of teams.ideas) {
    ideasCard.append(h("div", { class: "list-item", style: "align-items:flex-start;flex-direction:column;gap:2px" },
      h("div", {}, h("b", {}, x.name), x.team ? h("span", { class: "chip" }, x.team) : null, " ", h("span", {}, x.title || "")),
      x.about ? h("div", { class: "small" }, x.about) : null,
      x.tools ? h("div", { class: "small muted", style: "white-space:pre-wrap" }, "🔧 " + x.tools) : null));
  }

  const mark = { passed: [game ? "✓ проверка пройдена" : "✓ инструменты работают", "ok"], failed: ["✗ ошибки", "bad"], started: ["… пишет", ""] };
  const grid = h("div", { class: "team-grid" });
  if (!teams.teams.length) grid.append(h("section", { class: "card" }, h("p", { class: "muted" }, "Команд пока нет: создайте их слева. Ученики сами выберут команду в панели.")));
  for (const t of teams.teams) {
    const owners = {};
    for (const m of t.members) for (const x of m.tools) (owners[x] = owners[x] || []).push(m.name);
    const card = h("section", { class: "card team" },
      h("div", { class: "card-head" },
        h("h2", {}, h("button", { class: "link name-link", "aria-label": "Переименовать команду «" + t.name + "»",
          onclick: () => { const n = prompt("Название команды", t.name); if (n) act("teams/rename", { team_id: t.id, name: n }); } }, t.name)),
        h("span", { class: "badge" + (!game && t.members.length < cfg.min ? "" : " zero") }, t.members.length),
        h("span", { class: "spacer" }),
        h("button", { class: "ghost small", "aria-label": "Удалить команду «" + t.name + "»", onclick: () => { if (confirm(`Удалить команду «${t.name}»? Её участники останутся без команды.`)) act("teams/delete", { team_id: t.id }); } }, "✕")),
      !game && (t.bot_name || t.topic) ? h("p", { class: "small" }, [t.bot_name ? `🤖 ${t.bot_name}` : "", t.topic].filter(Boolean).join(" · ")) : null,
      !game && t.persona ? h("p", { class: "small muted" }, "🎭 " + t.persona) : null,
      game && t.studio ? h("div", { class: "teacher-studio-build" }, h("b", {}, t.studio.menu.title),
        h("p", { class: "small" }, t.studio.release
          ? `Сдано · ${t.studio.release.mode === "template" ? "Рабочий шаблон" : "Файл команды"} · ${t.studio.release.menu.title}`
          : t.studio.revision ? "Меню сохранено · сборка ожидается" : "Сборка ожидается"),
        t.studio.release ? h("p", { class: "small muted" }, "Отправил(а) " + t.studio.release.submitted_by +
          (t.studio.release.author ? " · файл " + t.studio.release.author : "")) : null,
        h("div", { class: "row", style: "margin-top:8px;gap:6px;" },
          h("button", { class: "ghost small", onclick: () => showStudioCode(t) }, "Код команды"),
          t.studio.release ? h("button", {
            class: "ghost small danger",
            onclick: () => {
              if (confirm(`Сбросить сдачу команды «${t.name}»? Команда сможет доработать и сдать игру заново.`)) {
                act("teams/clear_release", { team_id: t.id });
              }
            }
          }, "Сбросить сдачу") : null)) : null,
      !game && t.members.length < cfg.min ? h("p", { class: "small", style: "color:var(--bad)" }, `Мало участников: нужно минимум ${cfg.min}`) : null);
    if (!t.members.length) card.append(h("p", { class: "muted small" }, "Пока никого."));
    for (const m of t.members) {
      const st = mark[m.status] || [m.card_title || m.has_file ? "файл сохранён" : "нет файла", ""];
      card.append(h("div", { class: "member" },
        h("div", { class: "row" },
          h("span", { class: "dot" + (m.online ? " on" : "") }),
          h("button", { class: "link name-link", onclick: () => showStudent(m.id) }, m.name),
          h("span", { class: "chip " + st[1] }, st[0]),
          h("span", { class: "actions" }, assignSelect(m.id, t.id, "перевести…"),
            h("button", { class: "ghost small", title: "Убрать из команды: сам вернуться не сможет", onclick: () => { if (confirm(`Убрать ${m.name} из команды «${t.name}»? Вернуться в неё сам ученик не сможет — только вы его переведёте.`)) act("teams/kick", { student_id: m.id }); } }, "Выгнать"))),
        m.plan ? h("div", { class: "small muted" }, "📝 " + m.plan) : null,
        m.card_title ? h("div", { class: "small" }, "Карточка: " + m.card_title) : null,
        !game && m.tools.length ? h("div", {}, m.tools.map((x) => h("span", { class: "chip" + (owners[x].length > 1 ? " bad" : ""), title: owners[x].length > 1 ? "Такое же имя у товарища" : "" }, "🔧 " + x))) : null));
    }
    if (t.banned.length) {
      card.append(h("p", { class: "small muted" }, "Выгнаны: ", t.banned.map((b, i) => [i ? ", " : "", b.name, " ",
        h("button", { class: "link small", onclick: () => act("teams/assign", { student_id: b.id, team_id: t.id }) }, "вернуть")])));
    }
    grid.append(card);
  }
  return [game ? h("section", { class: "teacher-studio-summary" }, h("h2", {}, "Студия · Командная бродилка"),
    h("p", {}, `Команд: ${teams.teams.length} · сдали: ${releases.length} · на шаблоне: ${releases.filter((r) => r.mode === "template").length}`)) : null,
    h("div", { class: "grid" }, h("div", { class: "side" }, manage, free, exportCard, game ? null : ideasCard), h("div", {}, grid))];
}

async function showStudioCode(team) {
  openModal(h("h2", {}, `Код команды «${team.name}»`), h("p", { class: "muted" }, "Загрузка…"));
  try {
    const d = await api("GET", "/tapi/teams/studio_code?team_id=" + encodeURIComponent(team.id));
    const release = d.release || team.studio?.release || null;
    const menuData = d.studio_menu || d.menu || release?.menu || team.studio?.menu || null;
    const codeText = typeof d.code === "string" ? d.code : (typeof d.content === "string" ? d.content : "");
    const files = Array.isArray(d.files) ? d.files : [];
    const metaParts = [];
    if (release) {
      metaParts.push(release.mode === "template" ? "Рабочий шаблон" : "Файл команды");
      if (release.submitted_by) metaParts.push("отправил(а): " + release.submitted_by);
      if (release.author) metaParts.push("файл: " + release.author);
    } else if (d.mode || d.author || d.filename) {
      if (d.mode) metaParts.push(d.mode === "template" ? "Рабочий шаблон" : "Файл команды");
      if (d.author) metaParts.push("автор: " + d.author);
      if (d.filename) metaParts.push("файл: " + d.filename);
    } else {
      metaParts.push("Сдача ещё не оформлена");
    }
    openModal(
      h("h2", {}, `Код команды «${d.team_name || team.name}»`),
      h("div", { class: "row", style: "margin-bottom:10px;gap:8px;" },
        h("span", { class: "kv" }, metaParts.join(" · ")),
        h("span", { class: "spacer" }),
        release ? h("button", {
          class: "ghost small danger",
          onclick: async () => {
            if (!confirm(`Сбросить сдачу команды «${team.name}»? Команда сможет доработать и сдать игру заново.`)) return;
            const ok = await act("teams/clear_release", { team_id: team.id });
            if (ok) closeModal();
          }
        }, "Сбросить сдачу") : null),
      menuData ? [
        h("h3", { style: "margin:10px 0 4px;" }, "studio_menu.json"),
        h("pre", { class: "code" }, typeof menuData === "string" ? menuData : JSON.stringify(menuData, null, 2))
      ] : null,
      codeText ? [
        h("h3", { style: "margin:12px 0 4px;" }, d.filename || "Код игры"),
        h("pre", { class: "code" }, codeText)
      ] : files.length ? files.map((f) => [
        h("h3", { style: "margin:12px 0 4px;" }, f.path || f.name || "Файл"),
        h("pre", { class: "code" }, f.content || "")
      ]) : h("p", { class: "muted", style: "margin-top:12px;" }, "Сохранённого кода команды пока нет.")
    );
  } catch (e) {
    if (e.status === 401) { closeModal(); boot(); return; }
    openModal(h("h2", {}, `Код команды «${team.name}»`), h("p", { class: "err" }, e.message));
  }
}

// ---------- нейросеть ----------
function aiUsed() {
  return ai && (currentLesson().uses_ai || ai.log.length > 0 || (ai.status.active_count || 0) > 0 || (ai.status.queue && ai.status.queue.length > 0));
}

function aiCard() {
  const st = ai.status;
  const isBridge = st.bridge && st.bridge.active;
  const providerName = isBridge ? "🌉 Мост к ноутбуку" : (st.provider === "gigachat" ? "GigaChat" : "OpenAI-совместимый сервис");
  let state, cls;
  if (!st.configured) { state = "Не настроена: откройте «Настройки» и введите ключ"; cls = "bad"; }
  else if (st.mode === "pause") { state = "На паузе: ученики не могут спрашивать"; cls = "wait"; }
  else if (st.mode === "offline") { state = "Запасной режим: отвечает заготовка"; cls = "wait"; }
  else if (!st.ok) { state = "Ошибка: " + st.last_error; cls = "bad"; }
  else if (isBridge) { state = `Мост активен (${st.bridge.models || "Gemini 3 Flash"})` + (st.avg_seconds ? ` · ответ за ~${st.avg_seconds} с` : ""); cls = "ok"; }
  else { state = "Работает" + (st.avg_seconds ? ` · ответ за ~${st.avg_seconds} с` : ""); cls = "ok"; }
  const mode = (m, label) => h("button", { class: "small" + (st.mode === m ? "" : " ghost"), onclick: () => act("ai/mode", { mode: m }) }, label);
  const activeCount = st.active_count || 0;
  return h("section", { class: "card" },
    h("div", { class: "card-head" }, h("h2", {}, "🤖 Нейросеть"), h("span", { class: "muted small" }, providerName), h("span", { class: "spacer" }),
      h("button", { class: "ghost small", onclick: aiSettings }, "Настройки")),
    h("div", { class: "ai-state " + cls }, state),
    h("div", { class: "row", style: "margin:10px 0" }, mode("live", "Работает"), mode("offline", "Запасной режим"), mode("pause", "Пауза"),
      h("button", { class: "ghost small", onclick: aiTest }, "Проверить связь")),
    h("div", { class: "small" },
      activeCount > 0
        ? h("div", {}, "Сейчас обрабатывается: ", h("b", {}, `${activeCount} ${plural(activeCount, "запрос", "запроса", "запросов")}`))
        : h("div", { class: "muted" }, "Сейчас активных запросов нет"),
      h("div", { class: "muted", style: "margin-top:6px" }, `Сегодня вопросов: ${ai.today}.`)));
}

async function aiTest() {
  openModal(h("h2", {}, "Проверка связи с нейросетью"), h("p", { class: "muted" }, "Отправляю короткий вопрос…"));
  try {
    const r = await api("POST", "/tapi/ai/test", {});
    openModal(h("h2", {}, r.ok ? "✓ Нейросеть отвечает" : "✗ Нейросеть не отвечает"),
      r.ok ? h("p", {}, `Ответ: «${r.answer}» за ${r.seconds} с.`) : h("p", { class: "err" }, r.error),
      !r.ok ? h("p", { class: "muted small" }, "Проверьте ключ и сертификат в «Настройках». Пока можно включить «Запасной режим» — урок не остановится.") : null);
  } catch (e) { openModal(h("h2", {}, "Ошибка"), h("p", { class: "err" }, e.message)); }
}

function aiSettings() {
  const c = ai.config;
  const field = (label, input, hint) => h("label", { class: "field" }, h("span", {}, label), input, hint ? h("small", { class: "muted" }, hint) : null);
  const inp = (key, type) => h("input", { type: type || "text", value: c[key] == null ? "" : c[key], "data-k": key });
  const num = (key) => h("input", { type: "number", min: "0", value: c[key], "data-k": key, "data-num": "1" });
  const chk = (key) => { const e = h("input", { type: "checkbox", "data-k": key, "data-bool": "1" }); e.checked = !!c[key]; return e; };
  const provider = h("select", { "data-k": "provider" }, h("option", { value: "gigachat" }, "GigaChat (Сбер)"), h("option", { value: "openai" }, "OpenAI-совместимый сервис (в т.ч. Ollama)"));
  provider.value = c.provider;
  const scope = h("select", { "data-k": "gigachat_scope" }, ["GIGACHAT_API_PERS", "GIGACHAT_API_B2B", "GIGACHAT_API_CORP"].map((x) => h("option", { value: x }, x)));
  scope.value = c.gigachat_scope;
  const gKey = h("input", { type: "password", autocomplete: "off", "data-k": "gigachat_key", placeholder: c.has_gigachat_key ? "ключ задан ✓ — оставьте пустым, чтобы не менять" : "вставьте «Ключ авторизации»" });
  const oKey = h("input", { type: "password", autocomplete: "off", "data-k": "openai_key", placeholder: c.has_openai_key ? "ключ задан ✓" : "ключ сервиса" });
  const giga = h("div", {}, h("h3", {}, "GigaChat"),
    field("Ключ авторизации", gKey, "Личный кабинет GigaChat API → «Ключ авторизации». Хранится только на этом компьютере, в браузер не возвращается."),
    field("Версия API (scope)", scope, "Для физлиц — GIGACHAT_API_PERS."),
    field("Модель", inp("gigachat_model"), "GigaChat — самая быстрая; GigaChat-Pro / GigaChat-Max — умнее, но медленнее."),
    field("Сертификат «Russian Trusted Root CA»", inp("ca_file"), "Путь к файлу .cer/.crt, если система его не знает. Без него GigaChat может не подключиться."),
    h("label", { class: "check" }, chk("verify_ssl"), " проверять сертификат (выключать только для проверки)"));
  const openai = h("div", {}, h("h3", {}, "OpenAI-совместимый сервис"),
    field("Адрес", inp("openai_base_url"), "Например http://localhost:11434/v1 для Ollama."), field("Ключ", oKey), field("Модели через запятую", inp("openai_models")));
  const limits = h("div", {}, h("h3", {}, "Ограничения для класса"),
    h("div", { class: "cols3" },
      field("Длина ответа (токены)", num("max_tokens"), "Короче ответ — быстрее генерация."),
      field("Пауза между вопросами, с", num("min_interval")),
      field("Вопросов в день на ученика", num("daily_limit")),
      field("Длина вопроса, символов", num("max_prompt_chars")),
      field("Помнить строгие ответы, мин", num("cache_minutes"), "Одинаковый вопрос с temperature ≤ 0.3 — сразу из памяти.")),
    h("label", { class: "check" }, chk("short_hint"), " просить нейросеть отвечать коротко"),
    h("label", { class: "check" }, chk("no_code"), " не писать ученикам готовый код (задания решают сами)"));
  const box = h("div", { class: "settings" }, field("Поставщик", provider), giga, openai, limits);
  const sync = () => { giga.classList.toggle("hidden", provider.value !== "gigachat"); openai.classList.toggle("hidden", provider.value !== "openai"); };
  provider.addEventListener("change", sync);
  sync();
  const save = async () => {
    if (busy) return;
    busy = true;
    const patch = {};
    box.querySelectorAll("[data-k]").forEach((e) => {
      const k = e.getAttribute("data-k");
      if (e.getAttribute("data-bool")) patch[k] = e.checked;
      else if (e.getAttribute("data-num")) patch[k] = Number(e.value || 0);
      else patch[k] = e.value;
    });
    try {
      await api("POST", "/tapi/ai/config", patch);
      closeModal();
      await refresh();
      aiTest();
    } catch (e) {
      if (e.status === 401) { closeModal(); boot(); return; }
      alert(e.message);
    } finally {
      busy = false;
    }
  };
  openModal(h("h2", {}, "Настройки нейросети"), box, h("div", { class: "row", style: "margin-top:14px" },
    h("button", { onclick: save }, "Сохранить и проверить связь"), h("button", { class: "ghost", onclick: closeModal }, "Отмена")));
}

function aiFeed() {
  const time = (ts) => new Date(ts * 1000).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
  const sel = h("select", { onchange: (e) => { feedFilter = e.target.value; refresh(); } },
    h("option", { value: "" }, "Все ученики"), data.students.map((s) => h("option", { value: s.id }, s.name)));
  sel.value = feedFilter;

  const countEl = h("span", { class: "muted small" });
  const listEl = h("div", { class: "ai-feed-list" });
  const clearBtn = h("button", {
    class: "ghost small" + (feedFilter || feedSearch ? "" : " hidden"),
    onclick: () => {
      const hadFilter = Boolean(feedFilter);
      feedFilter = "";
      feedSearch = "";
      searchInput.value = "";
      sel.value = "";
      if (hadFilter) refresh();
      else renderList();
    }
  }, "Сбросить фильтр");

  function renderList() {
    const log = ai.log || [];
    const term = feedSearch.toLowerCase().trim();
    const filtered = log.filter((r) => {
      if (term) {
        const match = (r.name && r.name.toLowerCase().includes(term)) ||
                      (r.pc && r.pc.toLowerCase().includes(term)) ||
                      (r.question && r.question.toLowerCase().includes(term)) ||
                      (r.answer && r.answer.toLowerCase().includes(term)) ||
                      (r.system && r.system.toLowerCase().includes(term));
        if (!match) return false;
      }
      return true;
    });

    countEl.textContent = `сегодня: ${ai.today}` + (filtered.length !== log.length ? ` · найдено: ${filtered.length}` : "");
    clearBtn.classList.toggle("hidden", !(feedFilter || feedSearch));

    if (!log.length) {
      listEl.replaceChildren(h("p", { class: "muted" }, "Вопросов пока нет. Здесь появится всё, что ученики отправляют нейросети, и её ответы."));
      return;
    }
    if (!filtered.length) {
      listEl.replaceChildren(h("p", { class: "muted" }, "По вашему поисковому запросу ничего не найдено."));
      return;
    }

    listEl.replaceChildren(...filtered.slice(0, 150).map((r) => h("div", { class: "feed-item" + (r.flags.length ? " flagged" : ""), style: "border-top:1px solid var(--line);padding:12px 0;" },
      h("div", { class: "feed-meta", style: "display:flex;flex-wrap:wrap;align-items:center;gap:6px;font-size:13px;color:var(--muted);" },
        h("b", { class: "name-link", style: "cursor:pointer;color:var(--blue);", onclick: () => showStudent(r.student_id) }, "👤 " + r.name),
        h("span", { style: "font-weight:600;color:var(--text);" }, `· 🖥 ${r.pc || "ПК"}`),
        h("span", {}, `· ⏰ ${time(r.ts)}`),
        r.ms ? h("span", { class: "chip" }, `⚡ ${(r.ms / 1000).toFixed(1)} с`) : null,
        r.cached ? h("span", { class: "chip" }, "из памяти") : null,
        r.status !== "done" ? h("span", { class: "chip bad" }, "ошибка") : null,
        r.flags.map((f) => h("span", { class: "chip bad" }, "⚠ " + f))
      ),
      r.system ? h("div", { class: "feed-role", style: "margin:4px 0 2px;font-size:13px;color:var(--blue-ink);" }, "🎭 Роль: " + r.system) : null,
      h("div", { style: "margin:6px 0 2px;" },
        h("div", { class: "feed-q", style: "font-weight:600;white-space:pre-wrap;color:var(--text);line-height:1.4;" }, "💬 " + r.question)
      ),
      h("div", { class: "feed-a", style: "white-space:pre-wrap;background:#F4F6FC;border:1px solid #E4E8F4;border-radius:8px;padding:8px 12px;margin-top:6px;line-height:1.45;font-size:13.5px;color:#1E234D;" },
        (r.status === "done" ? "🤖 " : "❌ ") + (r.answer || "(пустой ответ)")
      )
    )));
  }

  const searchInput = h("input", {
    type: "search",
    placeholder: "🔍 Поиск по вопросу или ПК…",
    value: feedSearch,
    style: "padding:5px 10px;border:1px solid var(--line);border-radius:8px;font-size:13px;width:220px;",
    oninput: (e) => { feedSearch = e.target.value; renderList(); }
  });

  renderList();

  const box = h("section", { class: "card" },
    h("div", { class: "card-head", style: "display:flex;align-items:center;gap:10px;flex-wrap:wrap;" },
      h("h2", {}, "Что спрашивают у нейросети"),
      countEl,
      h("span", { class: "spacer" }),
      searchInput,
      sel,
      clearBtn,
      h("button", { class: "ghost small", onclick: () => { if (confirm("Очистить всю ленту вопросов?")) act("ai/clear"); } }, "Очистить")
    ),
    listEl,
    h("p", { class: "muted small", style: "margin-top:12px;" }, "Лента хранится 30 дней на этом компьютере, потом удаляется сама.")
  );
  return box;
}

async function showResult(s, t) {
  try {
    const d = await api("GET", "/tapi/student?id=" + s.id);
    const r = d.results.find((x) => x.task_id === t.id) || {};
    const task = await api("GET", "/tapi/task?id=" + encodeURIComponent(t.id));
    openModal(
      h("h2", {}, `${s.name} · задание ${t.num}. ${t.title}`),
      h("p", { class: "kv" }, `${{ passed: "✓ выполнено", failed: "✗ есть ошибки", started: "начато" }[r.status] || "—"} · проверок: ${r.attempts || 0} · подсказок: ${r.hints || 0}` + (r.rating ? ` · ученик оценил: ${r.rating}` : "")),
      r.summary ? h("p", {}, "Последняя проверка: " + r.summary) : null,
      h("div", { class: "cols" },
        h("div", {}, h("h2", {}, "Код ученика"), h("pre", { class: "code" }, r.code || "— пока нет —")),
        h("div", {}, h("h2", {}, "Эталон"), h("pre", { class: "code" }, task.solution))),
      h("h2", {}, "Подсказки ученику"), h("ol", {}, task.hints.map((x, i) => h("li", { style: i < (r.hints || 0) ? "" : "color:var(--muted)" }, x + (i < (r.hints || 0) ? " (открыта)" : "")))));
  } catch (e) { alert(e.message); }
}

async function showStudent(id) {
  try {
    const d = await api("GET", "/tapi/student?id=" + id);
    const when = (ts) => new Date(ts * 1000).toLocaleString("ru-RU", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
    const locked = (data.locks || []).some((x) => x.student_id === id);
    const stud = data.students.find((x) => x.id === id) || {};
    const isFocus = !!stud.focus;
    const isBlockSites = !!stud.block_sites;
    openModal(h("h2", {}, d.name),
      h("div", { style: "display:flex;gap:8px;align-items:center;margin:6px 0 10px;flex-wrap:wrap;" },
        locked ? h("button", { class: "ok small", onclick: async () => { await act("unlock", { student_id: id }); closeModal(); } }, "🔓 Разблокировать панель") : null,
        h("button", {
          class: isBlockSites ? "ghost small danger" : "ok small",
          title: isBlockSites ? "Разрешить ChatGPT, DeepSeek, Алису, ГигаЧат и VK в браузере" : "Закрывать ChatGPT, DeepSeek, Алису, ГигаЧат и VK в браузере",
          onclick: async () => {
            await act("toggle_block_sites", { student_id: id, on: !isBlockSites });
            closeModal();
          }
        }, isBlockSites ? "🔓 Разрешить ИИ и VK" : "🚫 Запретить ИИ и VK"),
        h("button", {
          class: isFocus ? "ghost small danger" : "ok small",
          title: isFocus ? "Снять блокировку игр и браузера" : "Включить блокировку игр и браузера",
          onclick: async () => {
            await act("toggle_focus", { student_id: id, on: !isFocus });
            closeModal();
          }
        }, isFocus ? "🔓 Снять блокировку игр и браузера" : "🛡️ Заблокировать игры и браузер"),
        data.state.running ? h("button", {
          class: "ghost small danger",
          title: "Сбросить результаты текущего урока только для этого ученика",
          onclick: async () => {
            if (!confirm(`Сбросить прогресс урока ${data.state.lesson} («${currentLesson().title}») у ученика ${d.name}?\n\nВсе результаты проверок, попытки и подсказки этого урока будут очищены.`)) return;
            await act("reset_lesson_progress", { lesson: data.state.lesson, student_id: id });
            closeModal();
          }
        }, "↺ Сбросить прогресс урока ученика") : null
      ),
      d.ai_queries && d.ai_queries.length ? [
        h("h3", { style: "margin-top:14px;display:flex;align-items:center;gap:8px;" }, "🤖 Запросы к нейросети", h("span", { class: "chip" }, d.ai_queries.length)),
        h("p", { class: "muted small" }, "Что ученик отправлял ИИ и какие ответы получал:"),
        h("div", { style: "max-height:360px;overflow-y:auto;display:flex;flex-direction:column;gap:10px;margin:8px 0 16px;padding-right:4px;" },
          d.ai_queries.map((q) => h("div", { class: "feed-item" + (q.flags && q.flags.length ? " flagged" : ""),
                                              style: "border:1px solid var(--line);border-radius:10px;padding:10px 12px;background:#fff;" },
            h("div", { class: "feed-meta", style: "display:flex;flex-wrap:wrap;gap:6px;align-items:center;" },
              h("span", { style: "font-weight:700;" }, `🖥 ${q.pc || "ПК"}`),
              h("span", {}, `· ⏰ ${when(q.ts)}`),
              q.ms ? h("span", { class: "chip" }, `⚡ ${(q.ms / 1000).toFixed(1)} с`) : null,
              q.cached ? h("span", { class: "chip" }, "из памяти") : null,
              q.status !== "done" ? h("span", { class: "chip bad" }, "ошибка") : null,
              (q.flags || []).map((f) => h("span", { class: "chip bad" }, "⚠ " + f))
            ),
            q.system ? h("div", { class: "feed-role", style: "margin-top:4px;font-size:13px;color:var(--blue-ink);" }, "🎭 Роль: " + q.system) : null,
            h("div", { class: "feed-q", style: "margin:6px 0 4px;font-weight:600;" }, "💬 " + q.question),
            h("div", { class: "feed-a", style: "background:#F4F6FC;border:1px solid #E4E8F4;border-radius:8px;padding:8px 10px;margin-top:4px;font-size:13px;" },
              (q.status === "done" ? "🤖 " : "❌ ") + (q.answer || "(нет ответа)"))
          ))
        )
      ] : (data.course?.id !== "games" ? h("p", { class: "muted", style: "margin:10px 0;" }, "🤖 Запросов к нейросети от этого ученика пока нет.") : null),
      d.pastes && d.pastes.length ? [h("h3", {}, "⚠ Попытки вставить готовый код"),
        h("p", { class: "muted" }, "Панель не пустила этот текст в файл задания. Хороший повод подойти и спросить, откуда он."),
        d.pastes.map((p) => [h("p", { class: "kv" }, `${when(p.ts)} · ${p.file || ""} · ${p.kind === "ai_paste_blocked" ? "⚠ вставка из ИИ (панель заблокирована)" : p.kind === "outside_edit" ? "файл меняли не в редакторе курса" : "обычная вставка"}`),
          h("pre", { class: "code" }, p.text || "")])] : null,
      h("p", { class: "kv" }, "Файлы с компьютера ученика (сохраняются при каждом сохранении и проверке)."),
      d.files.length ? d.files.map((f) => [h("p", { class: "kv" }, f.path), h("pre", { class: "code" }, f.content)])
        : h("p", { class: "muted" }, "Файлов пока нет."));
  } catch (e) { alert(e.message); }
}

boot();
