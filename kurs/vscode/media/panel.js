// Интерфейс панели курса (внутри VS Code). Получает от расширения снимок состояния «view» и рисует его.
// Главная идея: ученик всегда видит одно понятное следующее действие.
"use strict";
(function () {
  const vscode = acquireVsCodeApi();
  const root = document.getElementById("root");
  const toastEl = document.getElementById("toast");
  const ui = Object.assign({ tab: "tasks", task: null, helpText: "", server: "", toured: {} }, vscode.getState() || {});
  let view = null;
  let toastTimer = null;
  let clockTimer = null;
  let lastKey = "";
  let lastCheckKey = "";
  const askedSolution = new Set();
  const openDetails = new Set();   // раскрытые блоки не закрываются, когда панель обновляется

  function details(key, summary, ...body) {
    const d = h("details", {}, h("summary", {}, summary), ...body);
    d.open = openDetails.has(key);
    d.addEventListener("toggle", () => { if (d.open) openDetails.add(key); else openDetails.delete(key); });
    return d;
  }

  const send = (cmd, extra) => vscode.postMessage(Object.assign({ cmd }, extra || {}));
  const save = () => vscode.setState(ui);
  const LEVELS = { 1: "Разминка", 2: "Посложнее", 3: "Задачи на подумать", 4: "Со звёздочкой" };

  function h(tag, attrs, ...kids) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === null || v === undefined || v === false) continue;
      if (k === "class") el.className = v;
      else if (k === "html") el.innerHTML = v;
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

  const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  // Мини-разметка учебника: **жирный**, `код`, пустая строка — новый абзац.
  const md = (s) => String(s || "").split(/\n{2,}/).map((p) =>
    "<p>" + esc(p).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/`([^`]+)`/g, "<code>$1</code>").replace(/\n/g, "<br>") + "</p>").join("");
  const stars = (n) => h("span", { class: "stars", title: `Сложность ${n} из 4` }, "★".repeat(n), h("span", { class: "off" }, "★".repeat(Math.max(0, 4 - n))));
  const plural = (n, one, few, many) => (n % 10 === 1 && n % 100 !== 11 ? one : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20) ? few : many);

  function toast(text) {
    toastEl.textContent = text;
    toastEl.classList.remove("hidden");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toastEl.classList.add("hidden"), 6000);
  }

  function go(patch) {
    Object.assign(ui, patch);
    save();
    render();
    window.scrollTo(0, 0);
  }

  window.addEventListener("message", (e) => {
    const m = e.data;
    if (m.type === "view") {
      // перерисовываем только при настоящих изменениях: иначе опрос сервера «съедал» бы щелчки
      const key = JSON.stringify(m.view, (k, v) => (k === "now" || k === "local_offset" ? undefined : v));
      view = m.view;
      if (key !== lastKey) { lastKey = key; render(); }
      syncPlay();
    } else if (m.type === "lobby") {
      lobby = m.lobby;
      lobbyError = m.error || "";
      if (ui.tab === "games" && !P.current()) render();
    } else if (m.type === "toast") toast(m.text);
    else if (m.type === "select") go({ tab: "tasks", task: m.task });
  });

  // ---------------------------------------------------------------- игры по сети класса
  const P = window.KursPlay;
  let lobby = null;
  let lobbyError = "";
  const leftMatches = new Set();   // партии, из которых ученик уже вышел (сервер узнает об этом через секунду)
  const playState = () => (view && view.state && view.state.play) || null;
  const playOn = () => { const p = playState(); return !!(p && (p.allowed || p.match)) || !!P.current(); };

  function startNet(m) {
    P.start({ mode: "net", game: m.game, matchId: m.id, url: `${view.playWs}?match=${encodeURIComponent(m.id)}`, auth: view.playAuth,
      names: m.names, onEnd: () => { leftMatches.add(m.id); send("playLeave"); render(); } });
  }

  // партия началась (приняли наш вызов или мы приняли чужой) — сразу открываем её
  function syncPlay() {
    const p = playState();
    if (!p || view.screen !== "in") return;
    const cur = P.current();
    if (p.match && !leftMatches.has(p.match.id) && (!cur || cur.matchId !== p.match.id)) {
      startNet(p.match);
      if (ui.tab !== "games") go({ tab: "games" }); else render();
    }
    if (!p.allowed && !p.match && cur && cur.mode === "cpu") { P.stop(); render(); }
  }

  // лобби обновляем, пока открыта вкладка игр
  setInterval(() => {
    const p = playState();
    if (view && view.screen === "in" && ui.tab === "games" && !P.current() && p && p.allowed) send("playLobby");
  }, 3000);

  function inviteBanner(inv) {
    return h("div", { class: "card invite" },
      h("b", {}, `${inv.name} зовёт тебя: ${(P.titles[inv.game] || inv.game)}`),
      h("div", { class: "row", style: "margin-top:8px" },
        h("button", { onclick: () => send("playAnswer", { id: inv.id, accept: true }) }, "Играть"),
        h("button", { class: "secondary", onclick: () => send("playAnswer", { id: inv.id, accept: false }) }, "Не сейчас")));
  }

  function games() {
    const p = playState();
    const out = [h("h1", {}, "🎮 Игры")];
    if (P.current()) { out.push(P.host); return out; }
    if (!p || !p.allowed) {
      out.push(h("div", { class: "card" }, h("div", { class: "big-ic" }, "🔒"), h("p", {}, (p && p.reason) || "Игры закрыты — их открывает учитель")));
      return out;
    }
    if (!lobby) {
      send("playLobby");
      out.push(h("p", { class: "muted" }, lobbyError || "Загружаю список игроков…"));
      return out;
    }
    for (const inv of lobby.invites_in) out.push(inviteBanner(inv));
    for (const inv of lobby.invites_out) {
      out.push(h("div", { class: "card" }, `Ждём ответа: ${inv.name} · ${P.titles[inv.game]} `,
        h("button", { class: "link", onclick: () => send("playCancel", { id: inv.id }) }, "Отменить")));
    }
    const card = h("div", { class: "card" }, h("h2", {}, "С кем сыграть"));
    if (!lobby.players.length) card.append(h("p", { class: "muted" }, "Сейчас свободных игроков нет. Сыграй пока с компьютером — ниже."));
    for (const pl of lobby.players) {
      card.append(h("div", { class: "player" },
        h("span", { class: "pname" }, pl.key === "t" ? "🎓 " : "", pl.name),
        pl.busy ? h("span", { class: "muted small-text" }, "играет") :
          h("span", { class: "row" }, lobby.games.map((g) => h("button", { class: "secondary small", title: "Вызвать: " + P.titles[g],
            onclick: () => send("playInvite", { to: pl.key, game: g }) }, P.titles[g].split(" ")[0])))));
    }
    out.push(card);
    out.push(h("div", { class: "card" }, h("h2", {}, "С компьютером"),
      h("div", { class: "row" }, lobby.games.map((g) => h("button", { class: "secondary",
        onclick: () => { P.start({ mode: "cpu", game: g, names: [view.me.name, "Компьютер"], onEnd: render }); render(); } }, P.titles[g])))));
    out.push(h("p", { class: "muted small-text" }, "Значки у имени — во что позвать: ♟️ шахматы, 🏒 аэрохоккей, 🚢 морской бой."));
    return out;
  }

  // ---------------------------------------------------------------- общий рендер
  function render() {
    if (!view) return;
    const y = window.scrollY;
    const focused = document.activeElement && document.activeElement.id;
    root.replaceChildren(...screen().flat(Infinity).filter((x) => x));   // пустые части экрана (null) не выводим
    window.scrollTo(0, y);
    if (focused) { const el = document.getElementById(focused); if (el) el.focus(); }
    clearInterval(clockTimer);
    if (view.state && view.state.timer_end) clockTimer = setInterval(tickTimer, 1000);
    // новый результат проверки — сразу показываем его
    const check = ui.task && view.checks && view.checks[ui.task];
    const checkKey = check ? ui.task + JSON.stringify(check) : "";
    if (checkKey && checkKey !== lastCheckKey) {
      const el = document.getElementById("check-result");
      if (el) el.scrollIntoView({ block: "start", behavior: "smooth" });
    }
    lastCheckKey = checkKey;
  }

  function screen() {
    switch (view.screen) {
      case "loading": return [hero("⏳", "Подключаемся…", "Секунду.", h("div", { class: "spinner" }))];
      case "noserver": return noServer();
      case "idle": return [hero("☕", "Занятие скоро начнётся", "Как только учитель начнёт урок, здесь появится список группы.", h("div", { class: "spinner" }))];
      case "pick": return pick();
      case "confirmHere": return [hero("👋", `Ты — ${view.here.name}?`, "За этим компьютером уже работает этот ученик.",
        h("div", { class: "row", style: "justify-content:center;margin-top:16px" },
          h("button", { class: "big", onclick: () => send("login", { student_id: view.here.student_id }) }, "Да, это я"),
          h("button", { class: "big secondary", onclick: () => send("notMe") }, "Нет, я другой")))];
      case "waiting": return [hero("✋", `${view.waitingName}, учитель сейчас подтвердит`, view.message,
        h("div", { class: "spinner" }), h("button", { class: "link", onclick: () => send("cancelWait") }, "Я нажал не на своё имя"))];
      case "denied": return [hero("🙅", "Вход не подтверждён", view.message,
        h("button", { class: "big", style: "margin-top:14px", onclick: () => send("backToPick") }, "Выбрать имя"))];
      case "ended": return [hero("👋", "До встречи!", view.message, h("p", {}, "Твоя работа сохранена у учителя."))];
      case "in": return inside();
      default: return [hero("ℹ️", "Курс", view.message)];
    }
  }

  function hero(icon, title, text, ...extra) {
    return h("div", { class: "hero" }, h("div", { class: "big-ic" }, icon), h("h1", {}, title), text ? h("p", {}, text) : null, extra);
  }

  function noServer() {
    const inp = h("input", { id: "server-input", placeholder: "Например: 192.168.1.10:8000", value: ui.server || view.server || "" });
    inp.addEventListener("input", () => { ui.server = inp.value; save(); });
    inp.addEventListener("keydown", (e) => { if (e.key === "Enter") send("setServer", { server: inp.value }); });
    return [hero("🔌", "Нет связи с сервером курса", view.message),
      h("div", { class: "page", style: "max-width:460px;padding-top:0" },
        h("div", { class: "card" }, h("b", {}, "Адрес сервера"), h("p", { class: "muted small-text" }, "Его скажет учитель."), inp,
          h("div", { class: "row", style: "margin-top:10px" },
            h("button", { onclick: () => send("setServer", { server: inp.value }) }, "Подключиться"),
            view.server ? h("button", { class: "secondary", onclick: () => send("retry") }, "Попробовать ещё раз") : null)))];
  }

  function pick() {
    const students = view.students || [];
    return [hero("👋", "Привет! Нажми на своё имя", "Учитель увидит и подтвердит, что это ты."),
      view.message ? h("div", { class: "page", style: "padding-bottom:0" }, h("div", { class: "card fix" }, view.message)) : null,
      h("div", { class: "names" }, students.map((s) =>
        h("button", { class: "name-card" + (s.pc ? " busy" : ""), onclick: () => send("login", { student_id: s.id }) },
          s.name, s.pc ? h("small", {}, "сейчас на " + s.pc) : null))),
      !students.length ? h("p", { class: "muted", style: "text-align:center" }, "В группе пока нет учеников. Позови учителя.") : null,
      h("p", { class: "muted small-text", style: "text-align:center" }, `Компьютер: ${view.pc}`)];
  }

  // ---------------------------------------------------------------- после входа
  function tickTimer() {
    const el = document.getElementById("timer");
    if (el && view.state) el.textContent = timerText();
  }

  function timerText() {
    const st = view.state;
    const left = Math.max(0, Math.round(st.timer_end + st.local_offset - Date.now() / 1000));
    return "⏱ " + String(Math.floor(left / 60)).padStart(2, "0") + ":" + String(left % 60).padStart(2, "0");
  }

  function aiPill(ai) {
    if (ai.mode === "pause") return "🤖 пауза";
    if (ai.mode === "offline") return "🤖 запасной режим";
    if (!ai.ok) return "🤖 недоступна";
    return ai.queue ? `🤖 очередь: ${ai.queue}` : "🤖 свободна";
  }

  function aiTitle(ai) {
    if (ai.mode === "pause") return "Учитель поставил нейросеть на паузу";
    if (ai.mode === "offline") return "Нейросеть отдыхает: отвечает запасной режим";
    if (!ai.ok) return "Нейросеть сейчас не отвечает. Попробуй через минуту.";
    return ai.queue ? `Сейчас к нейросети ${ai.queue} вопр. в очереди` : "Нейросеть свободна";
  }

  const statusOf = (id) => (view.state.results[id] || {}).status || null;
  const isOpen = (id) => view.state.open_tasks.includes(id);

  function nextTask() {
    return view.lesson.tasks.find((t) => isOpen(t.id) && statusOf(t.id) !== "passed") || null;
  }

  function inside() {
    const st = view.state;
    const out = [];
    const tasks = view.lesson.tasks;
    out.push(h("div", { class: "top" },
      h("div", { class: "top-row" },
        h("span", { class: "avatar" }, (view.me.name || "?")[0]),
        h("div", { class: "who" }, h("b", {}, view.me.name), h("span", {}, `Занятие ${st.lesson} · ${view.me.pc}`)),
        h("span", { class: "spacer" }),
        st.help_open ? h("span", { class: "pill", title: "Учитель знает, что тебе нужна помощь" }, "🙋 жду учителя") : null,
        view.lesson.uses_ai && st.ai ? h("span", { class: "pill", title: aiTitle(st.ai) }, aiPill(st.ai)) : null,
        st.timer_end ? h("span", { class: "pill", id: "timer", title: st.timer_label || "Таймер" }, timerText()) : null),
      h("div", { class: "dots", title: "Твой прогресс на уроке" }, tasks.map((t) => h("i", { class: statusOf(t.id) || "" })))));
    const tabs = [["tasks", "📋", "Задания"], ["theory", "📖", "Учебник"], ["cheat", "🔑", "Шпаргалка"], ["help", "🙋", "Помощь"]];
    if (playOn()) tabs.splice(3, 0, ["games", "🎮", "Игры"]);
    else if (ui.tab === "games") ui.tab = "tasks";
    out.push(h("div", { class: "tabs" }, tabs.map(([id, ic, title]) =>
      h("button", { class: ui.tab === id ? "on" : "", onclick: () => go({ tab: id, task: id === "tasks" ? null : ui.task }) }, h("span", { class: "ic" }, ic), title))));
    const inv = st.play && st.play.invite;
    if (inv && ui.tab !== "games") out.push(h("div", { class: "page", style: "padding-bottom:0" }, inviteBanner(inv)));
    if (view.offline) out.push(h("div", { class: "banner" }, "Нет связи с сервером. Проверять код можно — результат отправится, когда связь вернётся."));
    const page = h("div", { class: "page" });
    if (!ui.toured[view.me.name]) page.append(tour());
    if (ui.tab === "tasks") page.append(...(ui.task && tasks.some((t) => t.id === ui.task) ? taskView(ui.task) : taskList()));
    else if (ui.tab === "theory") page.append(...theory());
    else if (ui.tab === "cheat") page.append(...cheat());
    else if (ui.tab === "games") page.append(...games());
    else page.append(...help());
    out.push(page);
    if (ui.tab === "tasks" && ui.task) out.push(actionBar(ui.task));
    if (st.paused) out.push(h("div", { class: "pause" }, h("div", { class: "big-ic" }, "👀"), h("h1", {}, st.pause_text || "Пауза: смотрим на учителя"),
      h("p", {}, "Отпусти мышку и посмотри на экран учителя.")));
    if (st.locked) out.push(h("div", { class: "pause" }, h("div", { class: "big-ic" }, "🔒"), h("h1", {}, "Панель заблокирована"),
      h("p", {}, "В файл задания вставили готовый код. Подожди — учитель подойдёт и разблокирует."),
      st.help_open ? h("p", { class: "muted" }, "Учитель уже знает, что ты ждёшь.")
        : h("button", { onclick: () => send("help", { text: "Разблокируйте панель, пожалуйста" }) }, "🙋 Позвать учителя")));
    return out;
  }

  function tour() {
    const done = () => { ui.toured[view.me.name] = true; save(); render(); };
    return h("div", { class: "tour" },
      h("h2", {}, "Как тут всё устроено"),
      h("div", { class: "layout-pic" }, h("div", { class: "code" }, "Твой код"), h("div", { class: "panel" }, "Задание (здесь)"), h("div", { class: "term" }, "Программа работает тут")),
      h("div", { class: "tour-step" }, h("span", { class: "n" }, "1"), h("div", {}, h("b", {}, "Справа — задания."), " Выбери задание и прочитай, что должен уметь бот.")),
      h("div", { class: "tour-step" }, h("span", { class: "n" }, "2"), h("div", {}, h("b", {}, "Слева — твой файл."), " Там ты пишешь код. Он сохраняется сам.")),
      h("div", { class: "tour-step" }, h("span", { class: "n" }, "3"), h("div", {}, h("b", {}, "▶ Запустить"), " — программа заработает внизу. Отвечай ей там и жми Enter.")),
      h("div", { class: "tour-step" }, h("span", { class: "n" }, "4"), h("div", {}, h("b", {}, "✓ Проверить"), " — компьютер сам попробует разные ответы и скажет, всё ли верно.")),
      h("button", { class: "wide", onclick: done }, "Понятно, начнём!"));
  }

  // ---------- список заданий
  function taskList() {
    const tasks = view.lesson.tasks;
    const done = tasks.filter((t) => statusOf(t.id) === "passed").length;
    const next = nextTask();
    if (!tasks.length) {
      // занятие без заданий в панели: пишем код вместе с учителем
      return [h("h1", {}, view.lesson.title),
        h("div", { class: "card" }, h("h2", {}, "✍ Сегодня пишем код вместе с учителем"),
          h("p", {}, view.lesson.note || "Заданий в панели на этом занятии нет."),
          view.lesson.uses_ai ? h("p", { class: "muted" }, "Файл ai.py и ключ уже лежат в папке занятия: просто пиши from ai import ask.") : null,
          h("p", { class: "muted" }, "Застрял — вкладка «Помощь», кнопка «Позвать учителя».")),
        h("div", { class: "section-title" }, "План урока"),
        view.lesson.steps.map((s) => h("div", { class: "stage" }, h("span", { class: "n" }, s.n), h("span", {}, s.title)))];
    }
    const out = [h("h1", {}, view.lesson.title),
      h("p", { class: "muted" }, `Выполнено ${done} из ${tasks.length}. Главные — задания 1–6, остальные для тех, кто успевает.`)];
    if (next) {
      out.push(h("button", { class: "big wide", style: "margin:10px 0 4px", onclick: () => openTask(next) }, `Продолжить: задание ${next.num} →`));
    } else if (!view.state.open_tasks.length) {
      out.push(h("div", { class: "card" }, "⏳ Учитель ещё не открыл задания. Пока можно почитать «Учебник»."));
    }
    let level = 0;
    for (const t of tasks) {
      if (t.level !== level) { level = t.level; out.push(h("div", { class: "section-title" }, LEVELS[level] || "Задания")); }
      const st = statusOf(t.id);
      const open = isOpen(t.id) || !!st;
      const isNext = next && next.id === t.id;
      const [label, cls] = st === "passed" ? ["Готово ✓", "passed"] : st === "failed" ? ["Есть ошибки", "failed"]
        : st === "started" ? ["Начато", "started"] : !open ? ["Скоро", ""] : isNext ? ["Дальше", "next"] : ["Новое", ""];
      out.push(h("button", { class: "task-card" + (isNext ? " next" : ""), disabled: !open, onclick: () => openTask(t) },
        h("span", { class: "num " + (st || (open ? "" : "locked")) }, open ? (st === "passed" ? "✓" : t.num) : "🔒"),
        h("span", { class: "t" }, h("b", {}, `${t.num}. ${t.title}`), h("small", {}, open ? t.statement.split("\n")[0] : "Учитель откроет это задание позже")),
        h("span", { class: "row", style: "flex-direction:column;align-items:flex-end;gap:4px" }, h("span", { class: "status " + cls }, label), stars(t.level))));
    }
    return out;
  }

  function openTask(t) {
    go({ task: t.id, tab: "tasks" });
    if (view.files[t.id]) send("openFile", { task: t.id });
  }

  // ---------- задание
  function taskView(id) {
    const tasks = view.lesson.tasks;
    const t = tasks.find((x) => x.id === id);
    const idx = tasks.indexOf(t);
    const st = view.state.results[id] || { hints: 0, attempts: 0 };
    const check = view.checks[id];
    const passed = st.status === "passed";
    const out = [];
    out.push(h("div", { class: "crumbs" },
      h("button", { class: "link", onclick: () => go({ task: null }) }, "← Все задания"),
      h("span", { class: "muted small-text" }, `Задание ${idx + 1} из ${tasks.length}`)));
    out.push(h("h1", {}, `${t.num}. ${t.title} `, stars(t.level)));
    out.push(h("div", {}, t.topics.map((x) => h("span", { class: "chip" }, x))));

    // после проверки результат — сразу под заголовком: это главное, что ученик хочет увидеть
    if (check) out.push(...checkResult(t, check));
    else if (passed) out.push(passedCard(t));
    out.push(h("div", { class: "card" }, h("h2", {}, "Что должен уметь бот"), h("div", { class: "statement" }, t.statement)));
    if (t.dialog && t.dialog.length) {
      out.push(h("div", { class: "card" }, h("h2", {}, "Пример разговора с ботом"), chat(t.dialog)));
    }
    if (t.bonus && passed) out.push(h("div", { class: "card" }, h("b", {}, "⭐ Бонус: "), t.bonus));

    if (passed) out.push(...solutionBlock(t, st));
    if (!passed && !check && !(st.attempts > 0)) out.push(stepsCard(t, st));
    out.push(hintsCard(t, st));
    out.push(h("div", { class: "row", style: "margin-top:6px" },
      view.files[id] ? h("button", { class: "secondary small", onclick: () => send("reset", { task: id }) }, "↺ Начать заново") : null,
      h("button", { class: "secondary small", onclick: () => go({ tab: "help" }) }, "🙋 Позвать учителя")));
    return out;
  }

  function chat(dialog, opts) {
    opts = opts || {};
    return h("div", { class: "chat" }, dialog.map(([who, text], i) =>
      h("div", { class: "bubble " + (who === "you" ? "you" : "bot") + (opts.wrongLast && i === dialog.length - 1 && who !== "you" ? " wrong" : "") },
        h("span", { class: "who" }, who === "you" ? "Человек" : "Бот"), text)));
  }

  function stepsCard(t, st) {
    const exists = view.files[t.id];
    const tried = (st.attempts || 0) > 0;
    const s = (n, state, title, text) => h("div", { class: "step " + state }, h("span", { class: "n" }, state === "done" ? "✓" : n),
      h("div", { class: "body" }, h("b", {}, title), text ? h("span", { class: "muted small-text" }, text) : null));
    return h("div", { class: "card" }, h("h2", {}, "Как решать"), h("div", { class: "steps" },
      s(1, "done", "Прочитай, что должен уметь бот", null),
      s(2, exists ? "done" : "now", exists ? "Файл создан — пиши код слева" : "Создай файл для задания", exists ? "Код сохраняется сам." : "Кнопка внизу. Файл откроется слева."),
      s(3, exists ? (tried ? "done" : "now") : "later", "▶ Запусти и попробуй сам", "Программа заработает внизу экрана. Отвечай ей и жми Enter."),
      s(4, exists ? "now" : "later", "✓ Проверь", "Компьютер сам попробует разные ответы.")));
  }

  function actionBar(id) {
    const exists = view.files[id];
    const busy = view.busy === id;
    const st = view.state.results[id] || {};
    if (st.status === "passed") {
      const next = nextTask();
      return h("div", { class: "bar" }, h("div", { class: "row" },
        h("button", { class: "secondary", onclick: () => send("run", { task: id }) }, "▶ Запустить"),
        next ? h("button", { class: "ok big", onclick: () => openTask(next) }, `Дальше: задание ${next.num} →`)
          : h("button", { class: "ok big", onclick: () => go({ task: null }) }, "К списку заданий")));
    }
    if (!exists) {
      return h("div", { class: "bar" }, h("div", { class: "row" },
        h("button", { class: "big", onclick: () => send("createFile", { task: id }) }, "📄 Создать файл для задания")));
    }
    const check = view.checks[id];
    return h("div", { class: "bar" },
      h("div", { class: "tip" }, check && !check.ok ? "Исправь код слева и проверь ещё раз" : "Сначала попробуй сам ▶, потом проверь ✓"),
      h("div", { class: "row" },
        h("button", { class: "secondary big", onclick: () => send("run", { task: id }), title: "Клавиша F5" }, "▶ Запустить"),
        h("button", { class: "ok big", disabled: busy, onclick: () => send("check", { task: id }), title: "Клавиша F6" }, busy ? "Проверяю…" : "✓ Проверить")));
  }

  function passedCard(t) {
    return h("div", { class: "result ok", id: "check-result" }, h("div", { class: "big-ic" }, "🎉"), h("h2", {}, "Задание выполнено!"),
      h("p", {}, `Бот «${t.title}» работает как надо.`));
  }

  function checkResult(t, r) {
    if (r.ok) return [passedCard(t)];
    const out = [];
    const total = r.items.length;
    const good = r.items.filter((i) => i.ok).length;
    if (r.error && !total) {
      // программа даже не запустилась: пустой файл или Python не может её прочитать
      out.push(h("div", { class: "result bad", id: "check-result" }, h("h2", {}, "🧩 " + r.error.title), h("div", {}, r.summary)));
    } else {
      out.push(h("div", { class: "result bad", id: "check-result" },
        h("h2", {}, r.error ? "Программа остановилась с ошибкой" : good * 2 >= total ? "Почти! Нужно кое-что поправить" : "Пока не получилось — давай разберёмся"),
        h("div", {}, `Прошло ${good} из ${total} ${plural(total, "проверки", "проверок", "проверок")}`),
        h("div", { class: "meter" }, h("i", { style: `width:${Math.round((100 * good) / Math.max(1, total))}%` }))));
    }
    if (r.error) {
      const e = r.error;
      out.push(h("div", { class: "card fix" },
        h("h2", {}, "Что мешает программе"),
        e.code_line ? h("div", { class: "line" }, e.line ? h("small", {}, `строка ${e.line}`) : null, e.code_line.trim()) : null,
        h("div", {}, e.text),
        e.line ? h("p", { class: "muted small-text" }, "Эта строка подчёркнута красным в твоём файле.") : null));
    }
    const failed = r.items.filter((i) => !i.ok);
    const failedTests = failed.filter((i) => i.kind === "test");
    // при ошибке, которая ломает все запуски, переписка ничего не добавит — показываем её только для неверных ответов
    const shown = (r.error ? [] : failedTests).slice(0, 2);
    for (const it of shown) {
      const want = (it.expect || []).join(" … ");
      out.push(h("div", { class: "card test" },
        h("div", { class: "q" }, (it.input && it.input.length) ? `Когда человек отвечает ${it.input.map((x) => `«${x}»`).join(", потом ")}` : "Когда программа запускается"),
        it.mismatch ? (it.why ? h("p", {}, "💬 " + it.why) : null) : (it.message ? h("p", {}, it.message) : null),
        it.dialog && it.dialog.length ? [h("div", { class: "muted small-text", style: "margin-top:8px" }, "Вот как прошёл разговор с твоим ботом:"), chat(it.dialog, { wrongLast: true })] : null,
        want ? h("div", { class: "chat" }, h("div", { class: "bubble want" }, h("span", { class: "who" }, "А бот должен сказать"), want)) : null));
    }
    const more = failedTests.length - shown.length;
    if (more > 0 && !r.error) out.push(h("p", { class: "muted" }, `И ещё ${more} ${plural(more, "проверка не прошла", "проверки не прошли", "проверок не прошли")} — сначала исправь эти.`));
    for (const it of failed.filter((i) => i.kind === "structure")) {
      out.push(h("div", { class: "card test" }, h("div", { class: "q" }, "В коде не хватает: " + it.title.replace(/^есть /, "")), h("p", {}, it.message)));
    }
    if (good) out.push(h("p", { class: "passed-list" }, `✓ ${good} ${plural(good, "проверка прошла", "проверки прошли", "проверок прошли")}.`));
    return out;
  }

  function solutionBlock(t, st) {
    const sol = view.solutions[t.id];
    if (!sol) {
      if (!askedSolution.has(t.id)) { askedSolution.add(t.id); send("loadSolution", { task: t.id }); }
      return [];
    }
    return [
      h("div", { class: "card" },
        h("h2", {}, "Как тебе задание?"),
        h("div", { class: "row" }, [["легко", "😎"], ["нормально", "🙂"], ["сложно", "🤯"]].map(([x, ic]) =>
          h("button", { class: "secondary small" + (st.rating === x ? " sel" : ""), onclick: () => send("rate", { task: t.id, rating: x }) }, `${ic} ${x}`)))),
      h("div", { class: "card" },
        details("sol-" + t.id, "Посмотреть образец решения",
          h("p", { class: "muted small-text" }, "Решений бывает несколько — твоё тоже верное, раз проверка прошла."),
          h("pre", {}, sol.code),
          h("button", { class: "secondary small", onclick: () => send("compareSolution", { task: t.id }) }, "Сравнить с моим кодом")))];
  }

  function hintsCard(t, st) {
    const hints = view.hints[t.id] || [];
    const box = h("div", { class: "card" }, h("h2", {}, "💡 Подсказки"));
    for (let i = 1; i <= t.hints_count; i++) {
      if (hints[i - 1]) box.append(h("div", { class: "hint" }, h("b", {}, `${i}. `), hints[i - 1]));
      else if (i <= st.hints) box.append(h("button", { class: "secondary small", onclick: () => send("hint", { task: t.id, level: i }) }, `Показать подсказку ${i}`));
      else if (i === st.hints + 1) {
        // сначала ученик пробует сам: подсказка N открывается после N проверок
        if ((st.attempts || 0) >= i) box.append(h("button", { class: "secondary", onclick: () => send("hint", { task: t.id, level: i }) }, `Открыть подсказку ${i} из ${t.hints_count}`));
        else box.append(h("div", { class: "locked" }, i === 1 ? "🔒 Сначала попробуй сам. Подсказка откроется после первой проверки."
          : `🔒 Подсказка ${i} откроется после ${i}-й проверки.`));
        break;
      }
    }
    return box;
  }

  // ---------- учебник
  function theory() {
    const out = [h("h1", {}, "Учебник"), h("p", { class: "muted" }, "Короткие объяснения к уроку. Примеры перепечатай в свой файл руками — так запоминается лучше.")];
    if (!view.lesson.theory.length && !(view.lesson.stages || []).length) {
      out.push(h("div", { class: "card" }, "Для этого занятия учебника в панели пока нет. Смотри на экран учителя и загляни в «Шпаргалку»."));
    }
    const stages = view.lesson.stages || [];
    if (stages.length) {
      const ready = view.state.stage;
      out.push(h("div", { class: "card" }, h("h2", {}, "📓 Тетрадь урока"),
        h("p", {}, "Пиши код вместе с учителем. Когда учитель закончит этап, запусти свою тетрадь ▶ и проверь, что у тебя тоже работает."),
        stages.map((s) => h("div", { class: "stage" + (s.n <= ready ? " done" : "") }, h("span", { class: "n" }, s.n <= ready ? "✓" : s.n),
          h("span", {}, s.title), s.n <= ready ? h("span", { class: "muted small-text" }, " — учитель закончил") : null)),
        h("div", { class: "row", style: "margin-top:8px" },
          h("button", { onclick: () => send("openNotebook") }, view.notebookExists ? "Открыть тетрадь" : "Создать тетрадь урока"),
          view.notebookExists ? h("button", { class: "secondary", onclick: () => send("runNotebook") }, "▶ Запустить тетрадь") : null)));
    }
    for (const c of view.lesson.theory) {
      out.push(h("div", { class: "card theory" }, h("h2", {}, c.title), h("div", { html: md(c.text) }),
        c.code ? h("pre", {}, c.code) : null,
        c.try ? h("div", { class: "try" }, h("b", {}, "Попробуй сам: "), c.try) : null));
    }
    return out;
  }

  // ---------- шпаргалка
  function cheat() {
    const out = [h("h1", {}, "Шпаргалка")];
    out.push(h("div", { class: "card" }, h("h2", {}, "Главные кнопки"), h("table", { class: "cheat" },
      [["F5", "▶ запустить программу"], ["F6", "✓ проверить задание"], ["Ctrl+Z", "отменить, если что-то сломал"]].map((r) => h("tr", {}, h("td", {}, r[0]), h("td", {}, r[1]))))));
    for (const s of view.lesson.cheatsheet.sections || []) {
      out.push(h("div", { class: "card" }, h("h2", {}, s.title),
        h("table", { class: "cheat" }, s.rows.map((r) => h("tr", {}, h("td", {}, r[0]), h("td", {}, r[1]))))));
    }
    out.push(h("div", { class: "card" }, h("h2", {}, "Сокращения: набери и нажми Tab"),
      h("table", { class: "cheat" }, [["pr", "print(\"…\")"], ["inp", "answer = input(\"…\")"]].map((r) => h("tr", {}, h("td", {}, r[0]), h("td", {}, r[1]))))));
    return out;
  }

  // ---------- помощь
  function help() {
    const out = [h("h1", {}, "Помощь")];
    if (view.state.help_open) {
      out.push(h("div", { class: "result ok" }, h("div", { class: "big-ic" }, "🙋"), h("h2", {}, "Учитель знает, что тебе нужна помощь"),
        h("p", {}, "Пока ждёшь — попробуй подсказку к заданию."),
        h("button", { class: "secondary", onclick: () => send("helpCancel") }, "Я уже разобрался")));
    } else {
      const txt = h("input", { id: "help-text", placeholder: "Что случилось? (можно не писать)", value: ui.helpText });
      txt.addEventListener("input", () => { ui.helpText = txt.value; save(); });
      out.push(h("div", { class: "card" }, h("h2", {}, "Позвать учителя"), txt,
        h("button", { class: "big wide", style: "margin-top:10px", onclick: () => { send("help", { text: ui.helpText }); ui.helpText = ""; save(); } }, "🙋 Позвать учителя")));
    }
    const faq = [
      ["Программа не запускается, внизу красный текст", "Это ошибка. Под ней есть строчка 💡 с объяснением по-русски. Нажми ✓ Проверить — неправильная строка подчеркнётся красным."],
      ["Буквы в коде странные: шf, зкште", "Включена русская раскладка. Код (if, print, input) пишется английскими буквами. Текст в кавычках — любыми."],
      ["Программа ничего не делает", "Она ждёт ответа. Щёлкни в окно внизу, напиши ответ и нажми Enter."],
      ["Ничего не понимаю, всё сломалось", "В задании есть кнопка «↺ Начать заново». Или позови учителя — это нормально."],
      ["Где мой файл?", "Слева. Если закрыл — открой задание в списке, файл откроется сам."],
      ["Нейросеть долго думает или пишет «в очереди»", "В классе одна нейросеть на всех, вопросы идут по очереди. Подожди, не запускай программу много раз подряд. Очередь видно вверху: 🤖."],
      ["Нейросеть пишет «Не так часто» или «закончились»", "Между вопросами нужна пауза в несколько секунд, а в день — не больше лимита. Пока ждёшь — нажми ✓ Проверить: проверка нейросеть не тратит."],
      ["Где ключ от нейросети?", "В файле .env рядом с ai.py. Панель создала его сама. Никому не показывай!"],
    ];
    out.push(h("div", { class: "card faq" }, h("h2", {}, "Частые вопросы"),
      faq.map(([q, a], i) => details("faq" + i, q, h("p", {}, a)))));
    out.push(h("div", { class: "row" },
      h("button", { class: "secondary", onclick: () => { ui.toured[view.me.name] = false; go({ tab: "tasks", task: null }); } }, "Как тут всё устроено"),
      h("span", { class: "spacer" }),
      h("button", { class: "link", onclick: () => send("logout") }, "Выйти (за компьютер садится другой)")));
    return out;
  }

  send("ready");
})();
