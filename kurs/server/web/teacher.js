// Пульт учителя. Обычный JavaScript без сборки: страница опрашивает сервер раз в 2 секунды.
"use strict";

const app = document.getElementById("app");
const lessonEl = document.getElementById("lesson");
const actionsEl = document.getElementById("actions");
const timerBox = document.getElementById("timerbox");
const navEl = document.getElementById("nav");
const modal = document.getElementById("modal");
const modalBody = document.getElementById("modal-body");

let data = null;          // последний ответ /tapi/overview
let ai = null;            // последний ответ /tapi/ai: нейросеть, очередь, лента вопросов
let play = null;          // последний ответ /tapi/play: игры по сети класса
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
let lastAttention = 0;

const store = {
  get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* без хранилища просто не запоминаем */ } },
};
const TABS = [["class", "🏫", "Класс"], ["ai", "🤖", "Нейросеть"], ["play", "🎮", "Игры"], ["notebook", "📓", "Тетрадь"], ["groups", "👥", "Группы"], ["connect", "🔌", "Подключение"]];
let tab = TABS.some((t) => t[0] === store.get("kurs.tab")) ? store.get("kurs.tab") : "class";
function goTab(t) { tab = t; store.set("kurs.tab", t); menuOpen = false; renderTop(); renderNav(); render(); window.scrollTo(0, 0); }
document.addEventListener("click", (e) => { if (menuOpen && !e.target.closest(".menu-wrap")) { menuOpen = false; renderTop(); } });

// ---------- помощники ----------
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

async function act(path, body) {
  if (busy) return;
  busy = true;
  try {
    await api("POST", "/tapi/" + path, body || {});
    await refresh();
  } catch (e) {
    if (e.status === 401) return boot();
    alert(e.message);
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
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const o = ctx.createOscillator();
    const g = ctx.createGain();
    o.frequency.value = 880;
    g.gain.setValueAtTime(0.08, ctx.currentTime);
    g.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.25);
    o.connect(g).connect(ctx.destination);
    o.start();
    o.stop(ctx.currentTime + 0.25);
  } catch (e) { /* звук недоступен */ }
}

// ---------- вход ----------
async function boot() {
  clearInterval(pollTimer);
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
  lessonEl.textContent = "";
  actionsEl.replaceChildren();
  const pw = h("input", { type: "password", autocomplete: setup ? "new-password" : "current-password", placeholder: "Пароль" });
  const pw2 = setup ? h("input", { type: "password", autocomplete: "new-password", placeholder: "Пароль ещё раз" }) : null;
  const err = h("div", { class: "err" });
  const go = async (e) => {
    e.preventDefault();
    err.textContent = "";
    if (setup && pw.value !== pw2.value) { err.textContent = "Пароли не совпадают"; return; }
    try {
      await api("POST", setup ? "/tapi/setup" : "/tapi/login", { password: pw.value });
      boot();
    } catch (ex) { err.textContent = ex.message; }
  };
  app.replaceChildren(h("form", { class: "card center", onsubmit: go },
    h("h2", {}, setup ? "Первый запуск: придумайте пароль учителя" : "Вход для учителя"),
    setup ? h("p", { class: "muted" }, "Пароль нужен, чтобы пульт не открыл посторонний. Не короче 6 символов.") : null,
    pw, pw2, err,
    h("button", { type: "submit", class: "big" }, setup ? "Сохранить пароль" : "Войти")));
  pw.focus();
}

// ---------- обновление ----------
async function refresh() {
  try {
    data = await api("GET", "/tapi/overview");
    ai = await api("GET", "/tapi/ai" + (feedFilter ? "?student=" + feedFilter : ""));
    play = await api("GET", "/tapi/play");
  } catch (e) {
    if (e.status === 401) { boot(); return; }
    lessonEl.textContent = "Нет связи с сервером";
    return;
  }
  const invites = play ? play.invites_in.length : 0;
  const attention = data.requests.length + data.help.length + (data.locks || []).length + invites + (ai && ai.status.last_error && aiUsed() ? 1 : 0);
  document.title = (attention ? `(${attention}) ` : "") + "Пульт учителя";
  if (attention > lastAttention) beep();
  lastAttention = attention;
  syncTeacherMatch();
  // не перерисовываем, пока учитель печатает, и если ничего не изменилось
  const typing = document.activeElement && ["TEXTAREA", "INPUT", "SELECT"].includes(document.activeElement.tagName) && !document.activeElement.closest(".play-host");
  const key = JSON.stringify([data, ai, play, tab], (k, v) => (k === "now" || k === "seen" ? undefined : v));
  if (key === lastKey && Date.now() - lastRenderAt < 30000) return;
  lastKey = key;
  renderTop();
  renderNav();
  if (!typing) render();
}

const currentLesson = () => data.lessons.find((l) => l.lesson === data.state.lesson) || data.lessons[0];
const currentGroup = () => data.groups.find((g) => g.id === data.state.group_id);

function renderTop() {
  const st = data.state;
  const l = currentLesson();
  const g = currentGroup();
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
    st.running ? item("🖥", "Экран для проектора", () => window.open("/teacher/projector.html", "kurs-projector"), "Таймер и прогресс без имён") : null,
    item("🔄", "Перезапустить VS Code у всех", () => { if (confirm("Перезапустить VS Code у всех учеников? Их работа сохранится, вход останется.")) act("restart_clients"); }),
    item("⏻", "Закрыть VS Code у всех", () => { if (confirm("Закрыть VS Code у всех учеников? Их файлы сохранятся. Открыть снова — ярлыком «Курс».")) act("close_clients"); }),
    st.running ? item("⬇", "Скачать таблицу результатов", () => { location.href = "/tapi/export.csv"; }) : null,
    item(sound ? "🔔" : "🔕", sound ? "Звук сигналов: включён" : "Звук сигналов: выключен", () => { store.set("kurs.sound", sound ? "off" : "on"); renderTop(); }),
    h("hr", {}),
    item("🚪", "Выйти из пульта", async () => { await api("POST", "/tapi/logout", {}); boot(); }));
  const parts = [];
  if (st.running) {
    parts.push(h("button", { class: st.paused ? "on" : "ghost", title: "Закрыть экраны учеников надписью «Смотрим на учителя»", onclick: () => act("pause", { paused: !st.paused }) }, st.paused ? "▶ Снять паузу" : "⏸ Пауза"));
    parts.push(h("button", { class: "danger", onclick: () => {
      if (!confirm("Завершить занятие? Работы учеников сохранятся здесь, а с компьютеров учеников сотрутся.")) return;
      const close = confirm("Закрыть VS Code на компьютерах учеников?\n\n«ОК» — закрыть, «Отмена» — оставить открытым.");
      act("end").then(() => { if (close) act("close_clients"); });
    } }, "Завершить занятие"));
  }
  parts.push(h("span", { class: "menu-wrap" }, h("button", { class: "ghost", onclick: (e) => { e.stopPropagation(); menuOpen = !menuOpen; renderTop(); } }, "⋯ Ещё"), menu));
  actionsEl.replaceChildren(...parts);
  clearInterval(clockTimer);
  if (st.timer_end) {
    const offset = Date.now() / 1000 - data.now;
    clockTimer = setInterval(() => {
      const el = document.getElementById("timer");
      if (el) el.textContent = "⏱ " + mmss(Math.max(0, Math.round(st.timer_end + offset - Date.now() / 1000)));
    }, 1000);
  }
}

function renderNav() {
  const att = data.requests.length + data.help.length + (data.locks || []).length;
  const badges = {
    class: att,
    ai: ai && ai.status.queue.length ? ai.status.queue.length : (ai && ai.status.last_error && aiUsed() ? "!" : (ai && ai.today ? ai.today : 0)),
    play: play ? play.invites_in.length : 0,
  };
  const soft = { play: play && play.matches.length ? play.matches.length : 0 };
  navEl.replaceChildren(...TABS.map(([id, ic, title]) => h("button", { class: "tab" + (tab === id ? " on" : ""), onclick: () => goTab(id) },
    h("span", { class: "ic" }, ic), title,
    badges[id] ? h("span", { class: "badge" }, badges[id]) : null,
    soft[id] ? h("span", { class: "badge soft", title: "Идут партии" }, soft[id]) : null)));
}

function render() {
  const y = window.scrollY;
  lastRenderAt = Date.now();
  const views = {
    class: () => (data.state.running ? renderLesson() : renderIdle()),
    ai: () => aiTab(),
    play: () => playTab(),
    notebook: () => [data.state.running ? stagesCard(currentLesson()) : h("section", { class: "card" }, h("p", { class: "muted" }, "Тетрадь урока доступна во время занятия."))],
    groups: () => [renderGroups()],
    connect: () => [connectCard(), h("section", { class: "card" }, h("h2", {}, "Адрес для учеников"), addresses())],
  };
  app.replaceChildren(...[].concat(views[tab]()).filter((x) => x));
  window.scrollTo(0, y);
}

// ---------- до занятия ----------
function renderIdle() {
  if (pick.group === null && data.groups.length) pick.group = data.state.group_id || data.groups[0].id;
  if (pick.lesson === null) pick.lesson = data.state.lesson || (data.lessons[0] && data.lessons[0].lesson);
  const wizard = h("section", { class: "card" }, h("h2", {}, "Начать занятие"), h("div", { class: "wizard" },
    h("div", {}, h("div", { class: "row" }, h("span", { class: "num" }, "1"), h("b", {}, "Группа")),
      data.groups.length ? data.groups.map((g) => h("button", { class: "choice" + (pick.group === g.id ? " sel" : ""), onclick: () => { pick.group = g.id; render(); } },
        g.name, h("small", {}, `${g.students.length} ${plural(g.students.length, "ученик", "ученика", "учеников")}`)))
        : h("p", { class: "muted" }, "Пока нет групп — добавьте ниже.")),
    h("div", {}, h("div", { class: "row" }, h("span", { class: "num" }, "2"), h("b", {}, "Занятие")),
      data.lessons.map((l) => h("button", { class: "choice" + (pick.lesson === l.lesson ? " sel" : ""), onclick: () => { pick.lesson = l.lesson; render(); } },
        `Занятие ${l.lesson}. ${l.title}`, h("small", {}, `${l.tasks.length} ${plural(l.tasks.length, "задание", "задания", "заданий")}`)))),
    h("div", {}, h("div", { class: "row" }, h("span", { class: "num" }, "3"), h("b", {}, "Начать")),
      h("p", { class: "muted" }, "После начала ученики увидят список группы. Каждый вход вы подтверждаете сами."),
      h("button", { class: "big", disabled: !pick.group || !pick.lesson, onclick: () => act("start", { group_id: pick.group, lesson: pick.lesson }) }, "▶ Начать занятие"),
      addresses())));
  const cards = [wizard,
    h("div", { class: "hint-cards" },
      h("button", { class: "hint-card", onclick: () => goTab("groups") }, h("b", {}, "👥 Группы"), h("small", {}, "добавить группу и учеников")),
      h("button", { class: "hint-card", onclick: () => goTab("connect") }, h("b", {}, "🔌 Подключение"), h("small", {}, "команда для компьютеров учеников")),
      h("button", { class: "hint-card", onclick: () => goTab("ai") }, h("b", {}, "🤖 Нейросеть"), h("small", {}, "ключ GigaChat и проверка связи")))];
  const last = data.state.last_class;
  const lastGroup = last && data.groups.find((g) => g.id === last.group_id);
  const lastLesson = last && data.lessons.find((l) => l.lesson === last.lesson);
  if (lastGroup && lastLesson) {
    const n = (last.open_tasks || []).length;
    cards.unshift(h("section", { class: "card" }, h("h2", {}, "Продолжить прошлое занятие"),
      h("p", {}, `${lastGroup.name} · Занятие ${lastLesson.lesson}. ${lastLesson.title}`),
      h("p", { class: "muted" }, `Вернутся открытые задания (${n}) и этап тетради. Решённые задания и файлы учеников сохранены — заново ничего делать не нужно.`),
      h("button", { class: "big", onclick: () => act("continue") }, "⏯ Продолжить занятие")));
  }
  return cards;
}

function addresses() {
  const port = location.port || "80";
  if (!data.addresses.length) return h("p", { class: "muted" }, "Адрес в сети не найден: проверьте подключение.");
  return h("p", {}, "Адрес для учеников: ", data.addresses.map((a, i) => [i ? " " : "", h("span", { class: "addr" }, `${a}:${port}`)]));
}

function connectCard() {
  // команда для первого запуска на компьютере ученика: скачивает запуск курса с этого сервера
  const port = location.port || "80";
  const url = `http://${data.addresses[0] || "АДРЕС_УЧИТЕЛЯ"}:${port}`;
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
    try {
      await api("POST", "/tapi/group", { id: g ? g.id : null, name: name.value, names: names.value.split("\n") });
      editingGroup = null;
      await refresh();
    } catch (e) { alert(e.message); }
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
    h("div", { class: "side" }, attentionCard(), stepsCard(lesson)),
    h("div", {}, tiles(), tableCard(lesson))));
  return out;
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
  if (!n) { box.append(h("div", { class: "calm" }, h("b", {}, "Всё спокойно ✓"), "Новые запросы появятся здесь, а вкладка браузера покажет их число."), lockSwitch); return box; }
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
  box.append(lockSwitch);
  return box;
}

function stagesCard(lesson) {
  const st = data.state;
  const box = h("section", { class: "card" }, h("h2", {}, "📓 Тетрадь урока"));
  if (!lesson.stages.length) { box.append(h("p", { class: "muted" }, "У этого занятия нет этапов.")); return box; }
  box.append(h("p", { class: "muted small" }, "Печатайте код этапа на проекторе, ученики пишут за вами. Закончили — «Этап готов»: ученики увидят, что пора запустить и проверить свою тетрадь. Готовый код ученикам не выдаётся."));
  for (const s of lesson.stages) {
    const ready = s.n <= st.stage;
    box.append(h("div", { class: "stage" + (ready ? " done" : "") }, h("span", { class: "n" }, ready ? "✓" : s.n),
      h("span", { class: "t" }, s.title),
      h("button", { class: "link small", title: "Код этапа для вас — показать на проекторе", onclick: () => showStage(s) }, "Код"),
      !ready && s.n === st.stage + 1 ? h("button", { class: "small", onclick: () => act("stage", { stage: s.n }) }, "Этап готов") : null));
  }
  if (st.stage > 0) box.append(h("button", { class: "link small", onclick: () => act("stage", { stage: st.stage - 1 }) }, "↶ Отменить последний этап"));
  return box;
}

async function showStage(s) {
  try {
    const r = await api("GET", "/tapi/stage_code?n=" + s.n);
    openModal(h("h2", {}, `Этап ${s.n}. ${s.title}`), h("p", { class: "muted small" }, "Только для вас: код тетради до этого этапа. Крупный шрифт — удобно показывать на проекторе."),
      h("pre", { class: "code huge" }, r.code));
  } catch (e) { alert(e.message); }
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
      s.pc ? h("button", { class: "link small", title: "Перезапустить VS Code у этого ученика (работа сохранится, вход останется)",
        onclick: () => { if (confirm(`Перезапустить VS Code у ученика ${s.name} (${s.pc})? Работа сохранится, вход останется.`)) act("restart_student", { student_id: s.id }); } }, "🔄") : null,
      s.pc ? h("button", { class: "link small", title: "Завершить сеанс ученика", onclick: () => { if (confirm(`Завершить сеанс: ${s.name}?`)) act("kick", { student_id: s.id }); } }, "✕") : null));
    for (const t of lesson.tasks) {
      const r = s.results[t.id];
      if (!r) { row.append(h("td", {}, h("span", { class: "cell empty" }, "·"))); continue; }
      const sign = r.status === "passed" ? "✓" : r.status === "failed" ? "✗" : "…";
      row.append(h("td", {}, h("span", { class: "cell " + r.status, onclick: () => showResult(s, t), title: r.summary || "" },
        sign, h("small", {}, `${r.attempts}×` + (r.hints ? ` 💡${r.hints}` : "")))));
    }
    row.append(h("td", {}, h("span", { class: "done-count" }, `${done}/${lesson.tasks.length}`)));
    body.append(row);
  }
  const foot = h("tr", {}, h("td", { class: "name" }, "Сдали"), lesson.tasks.map((t) =>
    h("td", {}, `${data.students.filter((s) => s.results[t.id] && s.results[t.id].status === "passed").length}`)), h("td", {}, ""));
  return h("section", { class: "card" }, h("div", { class: "card-head" }, h("h2", {}, "Прогресс класса"), h("span", { class: "spacer" }),
      h("a", { href: "/tapi/export.csv" }, h("button", { class: "ghost small" }, "Скачать таблицу"))),
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
    KursPlay.start({ mode: "net", game: m.game, matchId: m.id, url: `ws://${location.host}/ws/play?match=${encodeURIComponent(m.id)}`, auth: "",
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

// ---------- нейросеть ----------
function aiUsed() {
  return ai && (currentLesson().uses_ai || ai.log.length > 0 || ai.status.queue.length > 0);
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
  const waitSec = st.avg_seconds ? Math.round(st.avg_seconds * (st.queue.length + (st.working ? 1 : 0))) : null;
  return h("section", { class: "card" },
    h("div", { class: "card-head" }, h("h2", {}, "🤖 Нейросеть"), h("span", { class: "muted small" }, providerName), h("span", { class: "spacer" }),
      h("button", { class: "ghost small", onclick: aiSettings }, "Настройки")),
    h("div", { class: "ai-state " + cls }, state),
    h("div", { class: "row", style: "margin:10px 0" }, mode("live", "Работает"), mode("offline", "Запасной режим"), mode("pause", "Пауза"),
      h("button", { class: "ghost small", onclick: aiTest }, "Проверить связь")),
    h("div", { class: "small" },
      st.working ? h("div", {}, "Сейчас отвечает: ", h("b", {}, st.working.name)) : h("div", { class: "muted" }, "Сейчас никто не ждёт ответа"),
      st.queue.length ? h("div", {}, `В очереди ${st.queue.length}: `, st.queue.map((q) => h("span", { class: "chip" }, q.name)),
        waitSec ? h("span", { class: "muted" }, ` · последний дождётся примерно через ${waitSec} с`) : null) : null,
      h("div", { class: "muted", style: "margin-top:6px" }, `Сегодня вопросов: ${ai.today}. Нейросеть отвечает по одному вопросу за раз, у ученика в очереди не больше одного вопроса.`)));
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
      field("Длина ответа (токены)", num("max_tokens"), "Короче ответ — быстрее очередь."),
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
    } catch (e) { alert(e.message); }
  };
  openModal(h("h2", {}, "Настройки нейросети"), box, h("div", { class: "row", style: "margin-top:14px" },
    h("button", { onclick: save }, "Сохранить и проверить связь"), h("button", { class: "ghost", onclick: closeModal }, "Отмена")));
}

function aiFeed() {
  const time = (ts) => new Date(ts * 1000).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
  const sel = h("select", { onchange: (e) => { feedFilter = e.target.value; refresh(); } },
    h("option", { value: "" }, "Все ученики"), data.students.map((s) => h("option", { value: s.id }, s.name)));
  sel.value = feedFilter;

  const searchInput = h("input", {
    type: "search",
    placeholder: "🔍 Поиск по вопросу или ПК…",
    value: feedSearch,
    style: "padding:5px 10px;border:1px solid var(--line);border-radius:8px;font-size:13px;width:220px;",
    oninput: (e) => { feedSearch = e.target.value; render(); }
  });

  const clearBtn = (feedFilter || feedSearch)
    ? h("button", { class: "ghost small", onclick: () => { feedFilter = ""; feedSearch = ""; refresh(); } }, "Сбросить фильтр")
    : null;

  const term = feedSearch.toLowerCase().trim();
  const filtered = (ai.log || []).filter((r) => {
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

  const box = h("section", { class: "card" },
    h("div", { class: "card-head", style: "display:flex;align-items:center;gap:10px;flex-wrap:wrap;" },
      h("h2", {}, "Что спрашивают у нейросети"),
      h("span", { class: "muted small" }, `сегодня: ${ai.today}` + (filtered.length !== ai.log.length ? ` · найдено: ${filtered.length}` : "")),
      h("span", { class: "spacer" }),
      searchInput,
      sel,
      clearBtn,
      h("button", { class: "ghost small", onclick: () => { if (confirm("Очистить всю ленту вопросов?")) act("ai/clear"); } }, "Очистить")
    )
  );

  if (!ai.log.length) {
    box.append(h("p", { class: "muted" }, "Вопросов пока нет. Здесь появится всё, что ученики отправляют нейросети, и её ответы."));
  } else if (!filtered.length) {
    box.append(h("p", { class: "muted" }, "По вашему поисковому запросу ничего не найдено."));
  }

  for (const r of filtered.slice(0, 150)) {
    box.append(h("div", { class: "feed-item" + (r.flags.length ? " flagged" : ""), style: "border-top:1px solid var(--line);padding:12px 0;" },
      h("div", { class: "feed-meta", style: "display:flex;flex-wrap:wrap;align-items:center;gap:6px;font-size:13px;color:var(--muted);" },
        h("b", { class: "name-link", style: "cursor:pointer;color:var(--blue);", onclick: () => showStudent(r.student_id) }, "👤 " + r.name),
        h("span", { style: "font-weight:600;color:var(--ink);" }, `· 🖥 ${r.pc || "ПК"}`),
        h("span", {}, `· ⏰ ${time(r.ts)}`),
        r.ms ? h("span", { class: "chip" }, `⚡ ${(r.ms / 1000).toFixed(1)} с`) : null,
        r.cached ? h("span", { class: "chip" }, "из памяти") : null,
        r.status !== "done" ? h("span", { class: "chip bad" }, "ошибка") : null,
        r.flags.map((f) => h("span", { class: "chip bad" }, "⚠ " + f))
      ),
      r.system ? h("div", { class: "feed-role", style: "margin:4px 0 2px;font-size:13px;color:var(--blue-ink);" }, "🎭 Роль: " + r.system) : null,
      h("div", { style: "margin:6px 0 2px;" },
        h("div", { class: "feed-q", style: "font-weight:600;white-space:pre-wrap;color:var(--ink);line-height:1.4;" }, "💬 " + r.question)
      ),
      h("div", { class: "feed-a", style: "white-space:pre-wrap;background:#F4F6FC;border:1px solid #E4E8F4;border-radius:8px;padding:8px 12px;margin-top:6px;line-height:1.45;font-size:13.5px;color:#1E234D;" },
        (r.status === "done" ? "🤖 " : "❌ ") + (r.answer || "(пустой ответ)")
      )
    ));
  }
  box.append(h("p", { class: "muted small", style: "margin-top:12px;" }, "Лента хранится 30 дней на этом компьютере, потом удаляется сама."));
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
    openModal(h("h2", {}, d.name),
      locked ? h("p", {}, h("button", { class: "ok small", onclick: async () => { await act("unlock", { student_id: id }); closeModal(); } }, "🔓 Разблокировать панель")) : null,
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
      ] : h("p", { class: "muted", style: "margin:10px 0;" }, "🤖 Запросов к нейросети от этого ученика пока нет."),
      d.pastes && d.pastes.length ? [h("h3", {}, "⚠ Попытки вставить готовый код"),
        h("p", { class: "muted" }, "Панель не пустила этот текст в файл задания. Хороший повод подойти и спросить, откуда он."),
        d.pastes.map((p) => [h("p", { class: "kv" }, `${when(p.ts)} · ${p.file || ""} · ${p.kind === "outside_edit" ? "файл меняли не в редакторе курса" : "вставка"}`),
          h("pre", { class: "code" }, p.text || "")])] : null,
      h("p", { class: "kv" }, "Файлы с компьютера ученика (сохраняются при каждом сохранении и проверке)."),
      d.files.length ? d.files.map((f) => [h("p", { class: "kv" }, f.path), h("pre", { class: "code" }, f.content)])
        : h("p", { class: "muted" }, "Файлов пока нет."));
  } catch (e) { alert(e.message); }
}

boot();
