// Интерфейс панели курса (внутри VS Code). Получает от расширения снимок состояния «view» и рисует его.
// Главная идея: ученик всегда видит одно понятное следующее действие.
"use strict";
(function () {
  const vscode = acquireVsCodeApi();
  const root = document.getElementById("root");
  const toastEl = document.getElementById("toast");
  const ui = Object.assign({ tab: "tasks", task: null, helpText: "", server: "", chatHistory: [], chatDraft: "", chatLoading: false,
    ideaDraft: {}, teamDraft: {}, planDraft: null }, vscode.getState() || {});
  let view = null;
  let toastTimer = null;
  let clockTimer = null;
  let lastKey = "";
  let lastCheckKey = "";
  let lastChatLength = 0;
  let voteDraft = null;
  let votePending = false;
  let voteError = "";
  let moduleIdea = { id: null, draft: null, pending: false, error: "" };
  let gamePlanDraft = null;
  const studioUi = { key: "", draft: null, target: "", source: "", pending: "", message: "", error: "", screen: "menu" };
  const askedSolution = new Set();
  const openDetails = new Set();
  const SUPPORT_TABS = ["help", "chat", "theory", "cheat"];

  function details(key, summary, ...body) {
    const d = h("details", {}, h("summary", {}, summary), ...body);
    d.open = openDetails.has(key);
    d.addEventListener("toggle", () => { if (d.open) openDetails.add(key); else openDetails.delete(key); });
    return d;
  }

  const send = (cmd, extra) => vscode.postMessage(Object.assign({ cmd }, extra || {}));
  const save = () => vscode.setState(ui);
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
    document.getElementById("course-content")?.focus({ preventScroll: true });
  }

  window.addEventListener("message", (e) => {
    const m = e.data;
    if (m.type === "view") {
      // перерисовываем только при настоящих изменениях: иначе опрос сервера «съедал» бы щелчки
      const key = JSON.stringify(m.view, (k, v) => (k === "now" || k === "local_offset" ? undefined : v));
      view = m.view;
      if (key !== lastKey) { lastKey = key; render(); }
      syncPlay();
    } else if (m.type === "voteResult") {
      votePending = false;
      voteError = m.error || "";
      if (!voteError) voteDraft = null;
      render();
      document.getElementById(voteError ? "module-vote-submit" : "module-vote-status")?.focus({ preventScroll: true });
    } else if (m.type === "moduleIdeaResult" && m.id === moduleIdea.id) {
      moduleIdea.pending = false;
      moduleIdea.error = m.error || "";
      if (!m.error) moduleIdea.draft = null;
      render();
      document.getElementById(m.error ? "module-idea-topic" : "module-vote-status")?.focus({ preventScroll: true });
    } else if (m.type === "gamePlanSaved") {
      if (gamePlanDraft?.key === m.key && gamePlanDraft.value === m.plan) gamePlanDraft = null;
      render();
    } else if (m.type === "studioResult") {
      if (studioUi.key !== m.key) return;
      studioUi.pending = "";
      studioUi.error = m.error || "";
      if (!m.error && m.cmd === "studioMenu") studioUi.draft = null;
      studioUi.message = m.error ? "" : ({
        studioMenu: "Меню сохранено и появится в терминале при следующем запуске.",
        studioSubmit: "Сборка отправлена учителю.",
        studioRunTemplate: "Шаблон открыт в терминале.",
      })[m.cmd];
      render();
      document.getElementById("studio-" + studioUi.target + "-feedback")?.focus({ preventScroll: true });
    } else if (m.type === "lobby") {
      lobby = m.lobby;
      lobbyError = m.error || "";
      if (ui.tab === "games" && !P.current()) render();
    } else if (m.type === "aiChatReply") {
      ui.chatLoading = false;
      ui.chatHistory = ui.chatHistory || [];
      const reply = typeof m.message === "object" && m.message ? (m.message.content || "") : String(m.message || "");
      ui.chatHistory.push({ role: "assistant", content: reply, ts: Date.now() });
      save();
      render();
    } else if (m.type === "aiChatError") {
      ui.chatLoading = false;
      ui.chatHistory = ui.chatHistory || [];
      ui.chatHistory.push({ role: "error", content: m.error || "Ошибка нейросети", ts: Date.now() });
      save();
      render();
    } else if (m.type === "toolGenerated") {
      ui.toolGenerating = false;
      toast(m.message || "Инструмент успешно создан!");
      save();
      render();
    } else if (m.type === "toolGenerateError") {
      ui.toolGenerating = false;
      toast("Ошибка: " + (m.error || "не удалось сгенерировать инструмент"));
      save();
      render();
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
    const active = document.activeElement;
    const focused = active && active.id;
    const caret = active && typeof active.selectionStart === "number" ? [active.selectionStart, active.selectionEnd] : null;
    const previousChat = document.getElementById("chat-box");
    const chatScroll = previousChat?.scrollTop || 0;
    root.replaceChildren(...screen().flat(Infinity).filter((x) => x));   // пустые части экрана (null) не выводим
    window.scrollTo(0, y);
    if (focused) {
      const el = document.getElementById(focused);
      if (el) {
        el.focus({ preventScroll: true });
        if (caret && el.setSelectionRange) try { el.setSelectionRange(caret[0], caret[1]); } catch (e) { /* не поле ввода */ }
      }
    }
    const currentChat = document.getElementById("chat-box");
    const chatLength = ui.chatHistory?.length || 0;
    if (currentChat) currentChat.scrollTop = !previousChat || chatLength !== lastChatLength ? currentChat.scrollHeight : chatScroll;
    lastChatLength = chatLength;
    clearInterval(clockTimer);
    if (view.state && view.state.timer_end) clockTimer = setInterval(tickTimer, 1000);
    // новый результат проверки — сразу показываем его
    const check = ui.task && view.checks && view.checks[ui.task];
    const checkKey = check ? ui.task + JSON.stringify(check) : "";
    if (checkKey && checkKey !== lastCheckKey) {
      const el = document.getElementById("check-result");
      if (el) el.scrollIntoView({ block: "start" });
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

  const statusOf = (id) => (view.state.results[id] || {}).status || null;
  const isOpen = (id) => view.state.open_tasks.includes(id);

  function nextTask(exclude = null) {
    return view.lesson.tasks.find((t) => t.id !== exclude && isOpen(t.id) && statusOf(t.id) !== "passed") || null;
  }

  function inside() {
    const st = view.state;
    const out = [];
    const tasks = view.lesson.tasks;
    const activeTask = tasks.find((task) => task.id === ui.task);
    const collectingIdeas = st.poll?.phase === "ideas";
    const menu = [["tasks", "Задания"]];
    if (view.lesson.teams) menu.push(["team", view.lesson.team_project ? "Студия" : "Команда"]);
    else if (view.lesson.project_idea) menu.push(["idea", "Проект"]);
    if (st.poll) menu.push(["vote", collectingIdeas || !st.poll.options.length ? "Идеи модуля" : "Голосование"]);
    menu.push(["help", "Помощь"]);
    const inSupport = SUPPORT_TABS.includes(ui.tab) || (ui.tab === "games" && playOn());
    if (!inSupport && !menu.some(([id]) => id === ui.tab)) ui.tab = "tasks";
    const progress = tasks.length ? ` · ${tasks.filter((task) => statusOf(task.id) === "passed").length}/${tasks.length} готово` : "";
    out.push(h("div", { class: "top" },
      h("div", { class: "top-row" },
        h("span", { class: "avatar" }, (view.me.name || "?")[0]),
        h("div", { class: "who" }, h("b", {}, view.me.name), h("span", {}, `Занятие ${st.lesson}${progress}`)),
        h("span", { class: "spacer" }),
        st.help_open ? h("span", { class: "pill small-text", title: "Учитель получил просьбу о помощи" }, "Жду учителя") : null,
        st.timer_end ? h("span", { class: "pill small-text", id: "timer", title: st.timer_label || "Таймер" }, timerText()) : null),
      h("nav", { class: "tabs", "aria-label": "Разделы курса" }, menu.map(([id, title]) => {
        const selected = id === ui.tab || (id === "help" && inSupport);
        return h("button", { id: "section-" + id, class: selected ? "on" : "", "aria-current": selected ? "page" : null,
          onclick: () => go({ tab: id, task: id === "tasks" && ui.tab === "tasks" ? null : activeTask?.id || null }) }, title);
      }))));
    const inv = st.play && st.play.invite;
    if (inv && ui.tab !== "games") out.push(h("div", { class: "page", style: "padding-bottom:0" }, inviteBanner(inv)));
    if (view.offline) out.push(h("div", { class: "banner" }, "Нет связи с сервером. Проверять код можно — результат отправится, когда связь вернётся."));
    const page = h("main", { class: "page" + (ui.tab === "tasks" && activeTask ? " has-bar" : ""), id: "course-content", tabindex: "-1" });
    const supportPage = inSupport && ui.tab !== "help";
    if (supportPage) page.append(h("button", { class: "link support-back", onclick: () => go({ tab: "help" }) }, "← Помощь"));
    if (ui.tab === "tasks") page.append(...(activeTask ? taskView(activeTask.id) : taskList()));
    if (ui.tab === "tasks" && !activeTask && ((collectingIdeas && !st.poll.idea) || (st.poll?.open && st.poll.choice === null))) {
      page.append(h("aside", { class: "card poll-callout" },
        h("h2", {}, collectingIdeas ? "Что ты хочешь разработать дальше?" : "Выбери тему следующего модуля"),
        h("button", { id: "open-module-poll", class: "secondary", onclick: () => {
          go({ tab: "vote" });
          document.getElementById("module-vote-status")?.focus({ preventScroll: true });
        } }, collectingIdeas ? "Предложить идею" : "Голосовать")));
    }
    if (ui.tab === "chat") page.append(...chatView());
    else if (ui.tab === "theory") page.append(...theory());
    else if (ui.tab === "cheat") page.append(...cheat());
    else if (ui.tab === "games") page.append(...games());
    else if (ui.tab === "idea") page.append(h("h1", {}, "💡 Мой проект"), ideaCard(false));
    else if (ui.tab === "team") page.append(...teamView());
    else if (ui.tab === "vote") page.append(collectingIdeas || !st.poll.options.length ? moduleIdeaView(st.poll) : voteView(st.poll));
    else if (ui.tab === "help") page.append(...help());
    out.push(page);
    if (ui.tab === "tasks" && activeTask) out.push(actionBar(activeTask.id));
    if (st.paused) out.push(h("div", { class: "pause" }, h("div", { class: "big-ic" }, "👀"), h("h1", {}, st.pause_text || "Пауза: смотрим на учителя"),
      h("p", {}, "Отпусти мышку и посмотри на экран учителя.")));
    if (st.locked) out.push(h("div", { class: "pause" }, h("div", { class: "big-ic" }, "🔒"), h("h1", {}, "Панель заблокирована"),
      h("p", {}, "В файл задания вставили готовый код. Подожди — учитель подойдёт и разблокирует."),
      st.help_open ? h("p", { class: "muted" }, "Учитель уже знает, что ты ждёшь.")
        : h("button", { onclick: () => send("help", { text: "Разблокируйте панель, пожалуйста" }) }, "🙋 Позвать учителя")));
    return out;
  }

  function moduleIdeaView(poll) {
    if (moduleIdea.id !== poll.id) moduleIdea = { id: poll.id, draft: null, pending: false, error: "" };
    const collecting = poll.phase === "ideas";
    const status = h("p", { id: "module-vote-status", role: "status", tabindex: "-1" },
      poll.idea ? "Твоя идея сохранена: " + poll.idea : collecting ? "Предложи одну тему." : "Сбор идей завершён.");
    const card = h("section", { class: "card module-vote" }, h("h1", {}, "Следующий модуль"), h("p", {}, poll.question), status);
    if (!collecting) return card;
    const value = moduleIdea.draft ?? poll.idea ?? "";
    const disabled = moduleIdea.pending || view.offline;
    const topic = h("input", { id: "module-idea-topic", type: "text", required: true, maxlength: "80", value, disabled,
      placeholder: "Например, игру с редактором уровней", "aria-describedby": "module-idea-hint" });
    const canSubmit = () => !disabled && Boolean(topic.value.trim()) && topic.value.trim() !== poll.idea;
    const button = h("button", { type: "submit", disabled: !canSubmit() },
      moduleIdea.pending ? "Сохраняю…" : poll.idea ? "Обновить идею" : "Отправить идею");
    topic.addEventListener("input", () => {
      moduleIdea.draft = topic.value;
      moduleIdea.error = "";
      document.getElementById("module-idea-error")?.remove();
      button.disabled = !canSubmit();
    });
    card.append(h("form", { "aria-busy": String(moduleIdea.pending), onsubmit: (e) => {
      e.preventDefault();
      if (!canSubmit()) return;
      moduleIdea.pending = true;
      moduleIdea.error = "";
      send("moduleIdea", { id: poll.id, topic: topic.value });
      render();
    } }, h("label", { for: topic.id }, "Что хочешь попробовать разработать?"), topic,
    h("small", { id: "module-idea-hint", class: "muted" }, "Идею можно изменить до начала голосования. Учитель увидит тему без твоего имени."),
    moduleIdea.error ? h("p", { id: "module-idea-error", class: "vote-error", role: "alert" }, moduleIdea.error) : null, button));
    return card;
  }

  function voteView(poll) {
    if (voteDraft?.id !== poll.id && !votePending) { voteDraft = null; voteError = ""; }
    const choice = voteDraft?.id === poll.id ? voteDraft.choice : poll.choice;
    const status = h("p", { id: "module-vote-status", role: "status", tabindex: "-1" },
      poll.choice === null ? (poll.open ? "Выбери одну тему." : "Ты не успел проголосовать.")
        : "Твой голос: " + poll.options[poll.choice] + ".");
    const card = h("section", { class: "card module-vote" }, h("h1", {}, "Следующий модуль"), status);
    if (!poll.open) {
      card.append(h("p", {}, poll.question), h("p", { class: "muted" }, "Голосование завершено."));
      return card;
    }
    const submit = h("button", { id: "module-vote-submit", type: "submit",
      disabled: votePending || view.offline || choice === null || choice === poll.choice },
      votePending ? "Сохраняю…" : poll.choice === null ? "Отдать голос" : "Изменить голос");
    const list = h("fieldset", { disabled: votePending || view.offline }, h("legend", {}, poll.question),
      poll.options.map((topic, i) => h("label", { class: "vote-choice" },
        h("input", { id: "module-choice-" + i, type: "radio", name: "module-choice", checked: choice === i,
          onchange: () => {
            voteDraft = { id: poll.id, choice: i };
            voteError = "";
            document.getElementById("module-vote-error")?.remove();
            submit.disabled = i === poll.choice;
          } }), h("span", {}, topic))));
    card.append(h("form", { "aria-busy": String(votePending), onsubmit: (e) => {
      e.preventDefault();
      if (submit.disabled || votePending) return;
      votePending = true;
      voteError = "";
      send("moduleVote", voteDraft);
      render();
    } }, list,
    h("p", { class: "muted small-text" }, "Голос можно изменить до завершения опроса."),
    voteError ? h("p", { id: "module-vote-error", class: "vote-error", role: "alert" }, voteError) : null, submit));
    return card;
  }

  function taskList() {
    const lesson = view.lesson;
    const tasks = lesson.tasks;
    const next = nextTask();
    const out = [h("header", { class: "lesson-heading" }, h("h1", {}, lesson.title))];
    if (!tasks.length) {
      out.push(h("section", { class: "card" }, h("h2", {}, "Пишем вместе с учителем"),
        h("p", {}, lesson.note || "Повтори пример учителя в файле для тренировки."),
        h("button", { onclick: () => send("openNotebook") }, "Открыть файл для тренировки")));
      if (lesson.steps.length) {
        out.push(h("section", { class: "card" }, details("lesson-plan", "План занятия",
          h("ol", {}, lesson.steps.map((step) => h("li", {}, step.title))))));
      }
      return out;
    }
    if (lesson.teams) out.push(teamBrief());
    if (!view.state.open_tasks.length) {
      out.push(h("div", { class: "card" }, h("p", {}, "Учитель ещё не открыл задания."),
        h("button", { class: "secondary", onclick: () => go({ tab: "theory" }) }, "Открыть учебник")));
    }
    if (lesson.teams) out.push(h("h2", { class: "task-list-heading" }, "Задания"));
    for (const task of tasks) {
      const status = statusOf(task.id);
      const open = isOpen(task.id) || Boolean(status);
      const suggested = !lesson.teams && next?.id === task.id;
      const label = status === "passed" ? "Готово" : status === "failed" ? "Исправить" : status === "started" ? "Начато"
        : !open ? "Закрыто" : suggested ? "Начни здесь" : "";
      const style = status === "passed" || status === "failed" ? status : suggested ? "next" : status || "";
      out.push(h("button", { id: "task-" + task.id, class: "task-card" + (suggested ? " next" : ""),
        disabled: !open, onclick: () => openTask(task) },
        h("span", { class: "num " + (status || (open ? "" : "locked")), "aria-hidden": "true" }, status === "passed" ? "✓" : task.num),
        h("span", { class: "t" }, h("b", {}, task.title), label ? h("small", { class: "task-state " + style }, label) : null),
        open ? h("span", { class: "task-arrow", "aria-hidden": "true" }, "→") : null));
    }
    if (lesson.project_idea && !lesson.teams) {
      out.push(h("section", { class: "card" }, h("h2", {}, "Мой проект"),
        h("p", {}, view.idea?.title || "Придумай, кому и чем может помочь твой бот."),
        h("button", { class: "secondary", onclick: () => go({ tab: "idea" }) }, view.idea ? "Посмотреть идею" : "Записать идею")));
    }
    return out;
  }

  function openTask(t) {
    go({ task: t.id, tab: "tasks" });
    if (view.files[t.id]) send("openFile", { task: t.id });
  }

  // ---------- проект: идея и команда
  function field(id, label, value, onInput, opts) {
    opts = opts || {};
    const el = h(opts.multi ? "textarea" : "input", { id, placeholder: opts.placeholder || "", maxlength: opts.max || null, rows: opts.multi ? 3 : null });
    el.value = value || "";
    el.addEventListener("input", () => { onInput(el.value); save(); });
    return h("label", { class: "field" }, h("b", {}, label), opts.hint ? h("small", { class: "muted" }, opts.hint) : null, el);
  }

  function ideaCard(compact) {
    const saved = view.idea || {};
    ui.ideaDraft = ui.ideaDraft || {};
    const val = (k) => (ui.ideaDraft[k] !== undefined ? ui.ideaDraft[k] : saved[k] || "");
    const dirty = ["title", "about", "tools"].some((k) => val(k) !== (saved[k] || ""));
    const set = (k) => (v) => { ui.ideaDraft[k] = v; };
    const body = [
      compact ? null : h("p", { class: "muted" }, "На следующем занятии вы соберёте бота-агента командой. Запиши идею — учитель увидит идеи всех, а команда выберет одну."),
      field("idea-title", "Кто твой бот", val("title"), set("title"), { placeholder: "Шеф Бонапетти — весёлый бот-кулинар", max: 80 }),
      field("idea-about", "Что он делает для человека", val("about"), set("about"), { multi: true, max: 400, placeholder: "Подбирает рецепт по продуктам, шутит про еду, подсказывает, как готовить." }),
      field("idea-tools", "Инструменты (2–3): что точно сделает программа", val("tools"), set("tools"), { multi: true, max: 400,
        placeholder: "find_recipe(product) — блюдо по продукту\nconvert(grams) — граммы в стаканы\ntip_of_day() — совет дня",
        hint: "Инструмент — то, что программа сделает точнее нейросети: посчитает, выберет случайно, найдёт в своём списке." }),
      h("div", { class: "row", style: "margin-top:8px" },
        h("button", { onclick: () => { send("ideaSave", { idea: { title: val("title"), about: val("about"), tools: val("tools") } }); ui.ideaDraft = {}; save(); } },
          saved.updated && !dirty ? "Сохранено ✓" : "💾 Сохранить идею"),
        dirty && saved.updated ? h("button", { class: "secondary small", onclick: () => { ui.ideaDraft = {}; save(); render(); } }, "Отменить правки") : null)];
    if (compact) return h("div", { class: "card" }, details("idea-mine", saved.title ? `💡 Моя идея: ${saved.title}` : "💡 Моя идея проекта", ...body));
    return h("div", { class: "card" }, ...body);
  }

  function teamTask() {
    return view.lesson.tasks.find((t) => t.id === view.lesson.team_task) || view.lesson.tasks[0] || null;
  }

  // в списке заданий: в какой ты команде и что делать дальше
  function teamBrief() {
    const d = view.team;
    if (!d) return null;
    if (!d.team) {
      return h("div", { class: "card", style: "border-left:4px solid var(--brand)" }, h("h2", {}, "Сначала вступи в команду"),
        h("p", { class: "muted small-text" }, d.teams.length ? (view.lesson.team_project ? "Выбери команду во вкладке «Студия»." : "Выбери команду на вкладке «Команда».") : "Учитель скоро создаст команды."),
        h("button", { onclick: () => go({ tab: "team" }) }, "Выбрать команду →"));
    }
    const t = d.team;
    if (view.lesson.team_project) {
      return h("div", { class: "card" }, h("h2", {}, t.name),
        h("p", { class: "muted small-text" }, t.members.map((m) => m.name).join(", ")),
        h("button", { onclick: () => go({ tab: "team" }) }, "Открыть студию"));
    }
    return h("div", { class: "card" },
      h("h2", {}, t.name + (t.bot_name ? ` · бот «${t.bot_name}»` : "")),
      h("p", { class: "muted small-text" }, t.members.map((m) => m.name).join(", ")),
      h("button", { onclick: () => go({ tab: "team" }) }, "Открыть команду"));
  }

  const TASK_MARK = { passed: ["✓ инструменты работают", "passed"], failed: ["✗ есть ошибки", "failed"], started: ["… пишет", "started"] };

  function teamView() {
    const d = view.team;
    const out = view.lesson.team_project && d?.team
      ? [] : [h("h1", {}, view.lesson.team_project ? "Студия разработки игры" : "👥 Команда")];
    if (!d) return out.concat(h("p", { class: "muted" }, "Загружаю команды…"));
    if (d.notice) {
      out.push(h("div", { class: "card fix" }, h("b", {}, d.notice),
        h("div", { style: "margin-top:6px" }, h("button", { class: "secondary small", onclick: () => send("teamNoticeOk") }, "Понятно"))));
    }
    if (!d.team) return out.concat(teamPicker(d));
    return out.concat(view.lesson.team_project ? gameTeam(d) : myTeam(d));
  }

  function gameTeam(d) {
    const team = d.team;
    const me = team.members.find((m) => m.me);
    const task = teamTask();
    const ready = task && (isOpen(task.id) || statusOf(task.id));
    const key = [view.state.class_id, team.id, me?.id].join("/");
    const plan = gamePlanDraft?.key === key ? gamePlanDraft.value : me?.plan ?? "";
    if (studioUi.key !== key) Object.assign(studioUi, { key, draft: null, target: "", source: "", pending: "", message: "", error: "", screen: "menu" });
    const studio = team.studio;
    if (!studio) return [h("p", { class: "muted" }, "Обновляю данные студии…")];
    return [
      h("section", { class: "studio-hero" }, h("p", { class: "studio-team-name" }, team.name),
        h("h1", {}, studio.menu.title),
        h("nav", { class: "studio-flow", "aria-label": "Шаги проекта" },
          [["studio-menu", "1. Меню"], ["studio-dev", "2. Код"], ["studio-release", "3. Сдача"]].map(([id, label]) =>
            h("button", { onclick: () => {
              const target = document.getElementById(id);
              target?.scrollIntoView({ block: "start" });
              target?.focus({ preventScroll: true });
            } }, label)))),
      h("section", { class: "card" }, h("div", { class: "row" }, h("h2", {}, "Роли команды"),
        h("span", { class: "spacer" }),
        d.cfg.open ? h("button", { class: "link small", onclick: () => send("teamLeave") }, "Выйти из команды") : null),
        h("p", {}, "Один участник пишет код, остальные настраивают меню, рисуют карту или проверяют игру."),
        h("form", { onsubmit: (e) => {
          e.preventDefault();
          send("teamPlan", { plan: gamePlanDraft?.key === key ? gamePlanDraft.value : plan, key });
        } }, field("game-team-plan", "Моя роль в проекте", plan, (value) => { gamePlanDraft = { key, value }; },
          { max: 200, placeholder: "Тестирую стены, ключ и выход" }),
        h("button", { type: "submit", class: "secondary", style: "margin-top:8px" }, "Сохранить роль")),
        h("ul", { class: "game-team-members" }, team.members.map((m) => h("li", {},
          h("b", {}, m.name + (m.me ? " (ты)" : "")), " · " + (m.plan || "роль пока не записана"),
          m.status === "passed" ? h("span", { class: "status passed" }, "Проверка пройдена") : null)))),
      studioMenuCard(studio),
      h("section", { id: "studio-dev", tabindex: "-1", class: "card studio-card" }, h("h2", {}, "Написать и проверить код"),
        h("p", {}, "Редактор дописывает ход игрока и сохраняет файл. У товарищей появится копия в папке «Команда»."),
        ready ? h("button", { onclick: () => openTask(task) }, view.files[task.id] ? "Открыть файл бродилки" : "Открыть задание")
          : h("p", { class: "muted" }, "Учитель ещё не открыл задание."),
        team.files.length ? h("ul", { class: "game-team-members" }, team.files.map((f) =>
          h("li", {}, h("button", { class: "secondary", onclick: () => send("openTeamFile", { name: f.name }) }, "Открыть копию · " + f.author))))
          : h("p", { class: "muted small-text" }, "Сохранённые копии появятся здесь."),
        details("studio-checks", "Что проверить перед показом",
          h("ul", {}, ["Пункт 2 показывает правила, пункт 3 закрывает программу.", "Стена и край карты останавливают игрока.",
            "Без ключа выход закрыт. С ключом можно победить.", "Покажите прохождение и расскажите, кто что сделал."].map((line) => h("li", {}, line))))),
      studioReleaseCard(studio, team.members, task),
    ];
  }

  function sendStudio(cmd, target, payload) {
    studioUi.pending = cmd;
    studioUi.target = target;
    studioUi.message = "";
    studioUi.error = "";
    send(cmd, { key: studioUi.key, ...payload });
    render();
  }

  function studioFeedback(target) {
    if (studioUi.target !== target) return null;
    const text = studioUi.pending ? "Подождите…" : studioUi.error || studioUi.message;
    return text ? h("p", { id: "studio-" + target + "-feedback", tabindex: "-1",
      class: studioUi.error ? "vote-error" : "studio-feedback", role: studioUi.error ? "alert" : "status" }, text) : null;
  }

  function menuPreview(menu) {
    const host = h("div", { class: "studio-preview", "aria-label": "Предпросмотр меню игры" });
    const draw = (values) => {
      const screen = studioUi.screen;
      const switchTo = (next) => {
        studioUi.screen = next;
        draw(values);
        host.querySelector("button")?.focus({ preventScroll: true });
      };
      host.replaceChildren(...[
        h("p", { class: "studio-preview-label" }, "Предпросмотр · терминал"),
        h("h3", {}, values.title || "Название игры"),
        screen === "menu" ? ["start", "rules", "exit"].map((key, i) => h("button", { type: "button", onclick: () => switchTo(key) },
          h("span", {}, String(i + 1)), values[key] || ["Играть", "Правила", "Выход"][i])) : [],
        screen === "start" ? h("div", {}, h("pre", { "aria-label": "Пример карты. Игрок в верхнем левом углу. Справа ключ и выход." }, "@...\n.##K\n...E"),
          h("p", {}, "В терминале используй w/a/s/d и Enter.")) : null,
        screen === "rules" ? h("p", {}, values.intro || "Здесь будут правила.") : null,
        screen === "exit" ? h("p", {}, "Игра завершена.") : null,
        screen !== "menu" ? h("button", { type: "button", onclick: () => switchTo("menu") }, "Вернуться к меню") : null
      ].flat().filter(Boolean));
    };
    draw(menu);
    return { host, draw };
  }

  function studioMenuCard(studio) {
    const draft = studioUi.draft;
    const values = { ...(draft?.values || studio.menu) };
    const preview = menuPreview(values);
    const changedByTeam = draft && draft.revision !== studio.revision;
    const disabled = Boolean(studioUi.pending) || view.offline;
    const saveButton = h("button", { type: "submit", disabled: disabled || !draft || changedByTeam || Object.values(values).some((item) => !item.trim()) },
      "Сохранить меню для команды");
    const resetButton = h("button", { type: "button", class: "link", disabled: !draft,
      onclick: () => { studioUi.draft = null; studioUi.error = ""; studioUi.message = ""; render(); } }, "Загрузить сохранённое меню");
    const fields = [
      ["title", "Название игры", 36], ["start", "1. Начать игру", 24], ["rules", "2. Показать правила", 24],
      ["exit", "3. Завершить игру", 24], ["intro", "Текст правил", 100],
    ].map(([key, label, max]) => field("studio-menu-" + key, label, values[key], (value) => {
      values[key] = value;
      studioUi.draft = { revision: draft?.revision ?? studio.revision, values: { ...values } };
      preview.draw(values);
      resetButton.disabled = false;
      saveButton.disabled = disabled || changedByTeam || Object.values(values).some((item) => !item.trim());
      const releaseButton = document.getElementById("studio-release-team");
      const templateButton = document.getElementById("studio-release-template");
      if (releaseButton) releaseButton.disabled = true;
      if (templateButton) templateButton.disabled = true;
      const releaseHint = document.getElementById("studio-release-hint");
      if (releaseHint) releaseHint.textContent = "Сначала сохрани правки меню.";
    }, { max }));
    return h("section", { id: "studio-menu", tabindex: "-1", class: "card studio-card" }, h("h2", {}, "Конструктор меню"),
      h("p", {}, "Подберите название и тексты. Кнопки в предпросмотре показывают, что увидит игрок. В Python пункты выбирают цифрами 1, 2 и 3."),
      h("div", { class: "studio-menu-grid" }, preview.host,
        h("form", { onsubmit: (e) => {
          e.preventDefault();
          if (!saveButton.disabled && studioUi.draft) {
            sendStudio("studioMenu", "menu", { revision: studioUi.draft.revision, menu: studioUi.draft.values });
          }
        } }, h("fieldset", { class: "studio-fields", disabled: Boolean(studioUi.pending) }, fields, saveButton, resetButton))),
      changedByTeam ? h("p", { class: "vote-error", role: "alert" }, "Товарищ изменил меню. Загрузите сохранённую версию, чтобы не затереть его правки.") : null,
      studioFeedback("menu"));
  }

  function studioReleaseCard(studio, members, task) {
    const release = studio.release;
    const sources = members.filter((member) => member.has_file || (member.me && task && view.files[task.id]));
    const source = sources.find((member) => String(member.id) === studioUi.source) || sources[0];
    const select = h("select", { id: "studio-source", onchange: (e) => { studioUi.source = e.target.value; } },
      sources.map((member) => h("option", { value: member.id, selected: member === source }, member.name + (member.me ? " (твой файл)" : ""))));
    const disabled = Boolean(studioUi.pending) || Boolean(studioUi.draft) || view.offline;
    const submit = (mode) => {
      if (release && !window.confirm("Заменить ранее сданную сборку?")) return;
      sendStudio("studioSubmit", "release", { revision: studio.revision, mode, source: Number(select.value),
        expected: release?.submitted ?? null });
    };
    return h("section", { id: "studio-release", tabindex: "-1", class: "card studio-card" }, h("h2", {}, "Сдать сборку"),
      release ? h("p", { class: "studio-release-status" }, "Сдано · " + (release.mode === "template" ? "Рабочий шаблон" : "Файл команды")
        + " · " + release.menu.title + " · отправил(а) " + release.submitted_by) : null,
      h("p", {}, "Учителю уйдёт копия игры и сохранённое меню. После новых правок можно пересдать."),
      h("p", { id: "studio-release-hint", class: "muted" }, studioUi.draft ? "Сначала сохрани правки меню."
        : !source ? "Файл команды появится после сохранения кода." : ""),
      source ? h("label", { class: "field", for: "studio-source" }, h("b", {}, "Чей файл отправить"), select) : null,
      h("button", { id: "studio-release-team", disabled: disabled || !source, onclick: () => submit("team") }, "Сдать файл команды"),
      h("div", { class: "studio-fallback" }, details("studio-fallback", "Если код ещё не готов",
        h("p", {}, "Можно сдать рабочий шаблон с вашим меню, а свой файл отправить позже."),
        h("div", { class: "row" },
          h("button", { class: "secondary", disabled: Boolean(studioUi.pending) || view.offline,
            onclick: () => sendStudio("studioRunTemplate", "run") }, "Запустить рабочий шаблон"),
          h("button", { id: "studio-release-template", class: "secondary", disabled, onclick: () => submit("template") }, "Сдать рабочий шаблон")),
        studioFeedback("run"))),
      studioFeedback("release"));
  }

  function teamPicker(d) {
    const cfg = d.cfg;
    const out = [h("p", {}, view.lesson.team_project ? "Выбери команду. Если товарищи ещё не подошли, начни с меню и теста шаблона."
      : `Выбери команду и нажми «Вступить». В команде минимум ${cfg.min} ${plural(cfg.min, "человек", "человека", "человек")}` +
      (cfg.max ? `, максимум ${cfg.max}.` : "."))];
    if (!cfg.open) out.push(h("div", { class: "card" }, "🔒 Запись в команды закрыта. Остался без команды — позови учителя."));
    if (!d.teams.length) out.push(h("div", { class: "card" }, h("p", {}, "Учитель ещё не создал команды.")));
    for (const t of d.teams) {
      const n = t.members.length;
      const need = Math.max(0, cfg.min - n);
      out.push(h("div", { class: "card team-card" },
        h("div", { class: "row" }, h("h2", { style: "margin:0" }, t.name), h("span", { class: "spacer" }),
          h("span", { class: "pill" }, `${n}${cfg.max ? " / " + cfg.max : ""} 👤`)),
        !view.lesson.team_project && (t.topic || t.bot_name) ? h("p", { class: "muted small-text" }, [t.bot_name ? `Бот «${t.bot_name}»` : "", t.topic].filter(Boolean).join(" · ")) : null,
        h("p", {}, n ? t.members.join(", ") : h("span", { class: "muted" }, "Пока никого — будь первым!")),
        need && n ? h("p", { class: "muted small-text" }, `Нужен ещё ${need} ${plural(need, "человек", "человека", "человек")}`) : null,
        t.banned ? h("p", { class: "muted small-text" }, "Учитель убрал тебя из этой команды.")
          : h("button", { disabled: !cfg.open || t.full, onclick: () => send("teamJoin", { team: t.id }) }, t.full ? "Мест нет" : "Вступить")));
    }
    if (!view.lesson.team_project) out.push(ideaCard(true));
    return out;
  }

  function myTeam(d) {
    const t = d.team;
    const cfg = d.cfg;
    const out = [];
    const me = t.members.find((m) => m.me) || {};
    const owners = {};
    for (const m of t.members) for (const x of m.tools || []) (owners[x] = owners[x] || []).push(m.name);
    const dups = new Set(Object.keys(owners).filter((x) => owners[x].length > 1));

    out.push(h("div", { class: "card" },
      h("div", { class: "row" }, h("h2", { style: "margin:0" }, t.name), h("span", { class: "spacer" }),
        cfg.open ? h("button", { class: "link small", onclick: () => send("teamLeave") }, "Выйти из команды") : null),
      h("div", { class: "row", style: "margin-top:6px" }, t.members.map((m) =>
        h("span", { class: "chip", title: m.online ? "на связи" : "не на связи" }, (m.online ? "🟢 " : "⚪ ") + m.name + (m.me ? " (ты)" : "")))),
      t.members.length < cfg.min ? h("p", { class: "muted small-text" }, `⚠ В команде должно быть минимум ${cfg.min}. Позовите кого-нибудь или попросите учителя.`) : null));

    // общая карточка бота: меняют все, сохраняется кнопкой
    const drafts = (ui.teamDraft = ui.teamDraft || {});
    const dkey = (k) => t.id + ":" + k;
    const val = (k) => (drafts[dkey(k)] !== undefined ? drafts[dkey(k)] : t[k] || "");
    const set = (k) => (v) => { drafts[dkey(k)] = v; };
    const dirty = ["topic", "bot_name", "persona"].some((k) => val(k) !== (t[k] || ""));
    out.push(h("div", { class: "card" }, h("h2", {}, "🤖 Наш бот"),
      !t.bot_name ? h("p", { class: "muted small-text" }, "Договоритесь, чью идею берёте, и впишите имя и характер бота. Печатает кто-то один.") : null,
      field("team-topic", "Тема проекта", val("topic"), set("topic"), { placeholder: "Бот-кулинар: рецепты по продуктам", max: 120 }),
      field("team-bot", "Имя бота", val("bot_name"), set("bot_name"), { placeholder: "Шеф Бонапетти", max: 40 }),
      field("team-persona", "Характер: как бот говорит", val("persona"), set("persona"), { multi: true, max: 400, placeholder: "Весёлый повар, отвечает коротко и с шутками про еду." }),
      h("div", { class: "row", style: "margin-top:8px" },
        // кнопка всегда активна: пока ученик печатает, панель не перерисовывается
        h("button", { onclick: () => {
          send("teamCard", { card: { topic: val("topic"), bot_name: val("bot_name"), persona: val("persona") } });
          for (const k of ["topic", "bot_name", "persona"]) delete drafts[dkey(k)];
          save();
        } }, "💾 Сохранить для всей команды"),
        dirty ? h("span", { class: "muted small-text" }, "есть несохранённые правки")
          : t.edited_by ? h("span", { class: "muted small-text" }, `✓ сохранено · последним менял(а): ${t.edited_by}`) : null)));

    // кто что делает: каждый пишет только свою строку
    const plan = ui.planDraft !== null && ui.planDraft !== undefined ? ui.planDraft : me.plan || "";
    const rows = t.members.map((m) => {
      const mark = TASK_MARK[m.status] || [m.tools && m.tools.length ? "файл сохранён" : "ещё нет файла", ""];
      return h("div", { class: "player", style: "align-items:flex-start" },
        h("div", { class: "grow" }, h("b", {}, m.name + (m.me ? " (ты)" : "")),
          h("div", { class: "small-text" }, m.me ? null : (m.plan || h("span", { class: "muted" }, "ещё не написал(а), что делает"))),
          m.tools && m.tools.length ? h("div", {}, m.tools.map((x) => h("span", { class: "chip" + (dups.has(x) ? " bad" : ""), title: dups.has(x) ? "Такое имя уже есть у товарища — переименуйте" : "" }, "🔧 " + x))) : null),
        h("span", { class: "status " + mark[1] }, mark[0]));
    });
    out.push(h("div", { class: "card" }, h("h2", {}, "📝 Кто что делает"),
      field("team-plan", "Мои инструменты (имена и что делают)", plan, (v) => { ui.planDraft = v; }, { max: 200, placeholder: "find_recipe — блюдо по продукту, tip_of_day — совет дня" }),
      h("div", { class: "row", style: "margin:6px 0 10px" },
        h("button", { class: "secondary small", onclick: () => { send("teamPlan", { plan: ui.planDraft !== null && ui.planDraft !== undefined ? ui.planDraft : me.plan || "" }); ui.planDraft = null; save(); } }, "Записать")),
      rows,
      dups.size ? h("p", { class: "muted small-text" }, `⚠ Одинаковые имена инструментов: ${[...dups].join(", ")}. Бот команды возьмёт только один — договоритесь и переименуйте.`) : null));

    // файлы
    const task = teamTask();
    out.push(h("div", { class: "card" }, h("h2", {}, "📂 Файлы команды"),
      h("div", { class: "steps" },
        h("div", { class: "step now" }, h("span", { class: "n" }, "1"), h("div", { class: "body" }, h("b", {}, "Мои_инструменты.py — пишешь только ты"),
          h("span", { class: "muted small-text" }, "Сохранил (Ctrl+S) — через несколько секунд файл у товарищей."),
          task ? h("div", { class: "row", style: "margin-top:4px;gap:6px" },
            h("button", { class: "small", onclick: () => openTask(task) }, view.files[task.id] ? "Открыть задание" : "Начать задание"),
            h("button", { class: "ghost small", disabled: ui.toolGenerating, onclick: () => { ui.toolGenerating = true; render(); send("generateFirstTool", { taskId: task.id }); } },
              ui.toolGenerating ? "⏳ ИИ пишет…" : "✨ 1-й инструмент от ИИ")) : null)),
        h("div", { class: "step now" }, h("span", { class: "n" }, "2"), h("div", { class: "body" }, h("b", {}, "Папка «Команда» — файлы товарищей"),
          h("span", { class: "muted small-text" }, "Их можно читать и запускать, но не менять."),
          t.files.length ? h("div", { class: "row", style: "margin-top:4px" }, t.files.map((f) =>
            h("button", { class: "secondary small", onclick: () => send("openTeamFile", { name: f.name }) }, "📄 " + f.author)))
            : h("div", { class: "muted small-text" }, "Пока никто из товарищей не сохранил свой файл."))),
        h("div", { class: "step now" }, h("span", { class: "n" }, "3"), h("div", { class: "body" }, h("b", {}, "Наш_бот.py — бот всей команды"),
          h("span", { class: "muted small-text" }, "Сам собирает инструменты всех. Ошибка у кого-то — его инструменты выключатся, остальные работают."),
          h("div", { style: "margin-top:4px" }, h("button", { class: "ok small", onclick: () => send("runTeamBot") }, "▶ Запустить бота команды")))))));

    out.push(h("div", { class: "card" }, details("team-rules", "🤝 Как не мешать друг другу",
      h("ol", {},
        h("li", {}, "Каждый пишет только свой файл Мои_инструменты.py. Чужие файлы — только для чтения."),
        h("li", {}, "Сначала запиши в «Кто что делает» имена своих инструментов: одинаковых имён в команде быть не должно."),
        h("li", {}, "Имя и характер бота — общие. Договоритесь, кто их печатает, и сохраните один раз."),
        h("li", {}, "Своё проверяй сам: ▶ свой файл — агент только с твоими инструментами, ✓ «Проверить» — всё ли работает."),
        h("li", {}, "Вместе проверяйте Наш_бот.py: задайте вопрос для инструмента товарища и найдите строку 🔧.")))));

    const ideas = t.members.filter((m) => m.idea && (m.idea.title || m.idea.about));
    if (ideas.length) {
      out.push(h("div", { class: "card" }, details("team-ideas", `💡 Идеи участников (${ideas.length})`,
        ideas.map((m) => h("div", { class: "hint" }, h("b", {}, `${m.name}: ${m.idea.title || ""}`),
          m.idea.about ? h("div", { class: "small-text" }, m.idea.about) : null,
          m.idea.tools ? h("div", { class: "small-text muted", style: "white-space:pre-wrap" }, "🔧 " + m.idea.tools) : null)))));
    }
    out.push(ideaCard(true));
    return out;
  }

  // ---------- задание
  function taskView(id) {
    const t = view.lesson.tasks.find((task) => task.id === id);
    const st = view.state.results[id] || { hints: 0, attempts: 0 };
    const check = view.checks[id];
    const passed = check ? check.ok : st.status === "passed";
    const out = [
      h("button", { class: "link support-back", onclick: () => go({ task: null }) }, "← Все задания"),
      h("h1", {}, t.title),
    ];
    if (check) out.push(...checkResult(t, check));
    else if (passed) out.push(passedCard());
    out.push(h("section", { class: "card task-description" }, h("h2", {}, "Что сделать"),
      h("div", { class: "statement", html: md(t.statement) }),
      t.dialog?.length ? details("example-" + id, "Пример диалога", chat(t.dialog))
        : t.example ? details("example-" + id, "Пример запуска", h("pre", {}, t.example)) : null));
    if (t.id === "team-01" || t.file === "Мои_инструменты.py") {
      out.push(h("section", { class: "card" }, details("team-ai-" + id, "Нужен пример инструмента?",
        h("p", {}, "ИИ добавит первый инструмент без параметров в твой файл. Второй, с параметром, напиши сам."),
        h("button", { class: "secondary", disabled: ui.toolGenerating, onclick: () => {
          ui.toolGenerating = true;
          render();
          send("generateFirstTool", { taskId: id });
        } }, ui.toolGenerating ? "ИИ готовит пример…" : "Создать первый инструмент с ИИ"))));
    }
    if (t.bonus && passed) out.push(h("section", { class: "card" }, details("bonus-" + id, "Дополнительное задание", h("p", {}, t.bonus))));
    if (st.status === "passed") out.push(...solutionBlock(t, st));
    const hints = t.hints_count ? hintsCard(t, st) : null;
    out.push(h("section", { class: "card task-support" },
      details("task-support-" + id, "Подсказки и помощь", hints,
        h("div", { class: "row" },
          h("button", { class: "secondary", onclick: () => go({ tab: "chat", task: id }) }, "Спросить ИИ"),
          h("button", { class: "secondary", onclick: () => go({ tab: "help" }) }, "Позвать учителя")))));
    if (view.files[id]) {
      out.push(h("div", { class: "task-settings" }, details("task-file-" + id, "Действия с файлом",
        h("div", { class: "row" },
          h("button", { class: "secondary", onclick: () => send("openFile", { task: id }) }, "Открыть файл слева"),
          h("button", { class: "link danger-text", onclick: () => send("reset", { task: id }) }, "Начать задание заново")))));
    }
    return out;
  }

  function chat(dialog, opts) {
    opts = opts || {};
    const game = view.lesson.course?.id === "games";
    return h("div", { class: "chat" }, dialog.map(([who, text], i) =>
      h("div", { class: "bubble " + (who === "you" ? "you" : "bot") + (opts.wrongLast && i === dialog.length - 1 && who !== "you" ? " wrong" : "") },
        h("span", { class: "who" }, who === "you" ? (game ? "Ввод" : "Человек") : (game ? "Программа" : "Бот")), text)));
  }

  function actionBar(id) {
    const exists = view.files[id];
    const busy = view.busy === id;
    const check = view.checks[id];
    const passed = !busy && (check ? check.ok : statusOf(id) === "passed");
    const next = passed ? nextTask(id) : null;
    const run = h("button", { id: "task-run", class: "secondary", disabled: busy, onclick: () => send("run", { task: id }), title: "F5" }, "Запустить");
    const submit = h("button", { id: "task-check", disabled: busy, onclick: () => send("check", { task: id }), title: "F6" },
      busy ? "Проверяю…" : check && !check.ok ? "Проверить ещё раз" : "Проверить");
    const tip = !exists ? "Файл откроется слева." : passed ? "Можно перейти дальше или ещё раз запустить программу."
      : check && !check.ok ? "Исправь код слева и проверь ещё раз." : "Пиши код слева. После запуска вводи ответы в консоли снизу.";
    return h("div", { class: "bar", role: "region", "aria-label": "Работа с заданием" },
      h("p", { class: "tip" }, tip),
      h("div", { class: "row" }, !exists
        ? h("button", { id: "task-create", onclick: () => send("createFile", { task: id }) }, "Создать файл")
        : [run, passed ? h("button", { onclick: () => next ? openTask(next) : go({ task: null }) },
          next ? "Следующее задание" : "Все задания") : submit]));
  }

  function passedCard() {
    return h("div", { class: "result ok", id: "check-result", role: "status" }, h("h2", {}, "Проверка пройдена"));
  }

  function checkResult(t, r) {
    if (r.ok) return [passedCard()];
    const out = [];
    const total = r.items.length;
    const good = r.items.filter((i) => i.ok).length;
    if (r.error && !total) {
      // программа даже не запустилась: пустой файл или Python не может её прочитать
      out.push(h("div", { class: "result bad", id: "check-result" }, h("h2", {}, "🧩 " + r.error.title), h("div", {}, r.summary)));
    } else {
      out.push(h("div", { class: "result bad", id: "check-result" },
        h("h2", {}, r.error ? "Программа остановилась с ошибкой" : "Проверка не пройдена"),
        h("div", {}, `Прошло ${good} из ${total} ${plural(total, "проверки", "проверок", "проверок")}`),
        h("div", { class: "meter" }, h("i", { style: `width:${Math.round((100 * good) / Math.max(1, total))}%` }))));
    }
    if (r.error) {
      const e = r.error;
      out.push(h("div", { class: "card fix" },
        h("h2", {}, "Что мешает программе"),
        e.code_line ? h("div", { class: "line" }, e.line ? h("small", {}, `строка ${e.line}`) : null, e.code_line.trim()) : null,
        h("div", {}, e.text),
        e.line ? h("p", { class: "muted small-text" }, "Эта строка подчёркнута красным в твоём файле.") : null,
        h("div", { style: "margin-top:8px" },
          h("button", { class: "secondary small", onclick: () => askAiAboutError(t, r) }, "Спросить ИИ об ошибке"))));
    }
    const failed = r.items.filter((i) => !i.ok);
    const failedTests = failed.filter((i) => i.kind === "test");
    // при ошибке, которая ломает все запуски, переписка ничего не добавит — показываем её только для неверных ответов
    const shown = (r.error ? [] : failedTests).slice(0, 2);
    for (const it of shown) {
      const want = (it.expect || []).join(" … ");
      out.push(h("div", { class: "card test" },
        h("div", { class: "q" }, (it.input && it.input.length) ? "Ввод: " + it.input.map((x) => `«${x}»`).join(" → ") : "Запуск без ввода"),
        it.mismatch ? (it.why ? h("p", {}, "💬 " + it.why) : null) : (it.message ? h("p", {}, it.message) : null),
        want ? h("div", { class: "chat" }, h("div", { class: "bubble want" }, h("span", { class: "who" }, "Ожидаемый результат"), want)) : null,
        it.dialog?.length ? details("test-output-" + t.id + "-" + failedTests.indexOf(it), "Посмотреть вывод программы",
          chat(it.dialog, { wrongLast: true })) : null));
    }
    const more = failedTests.length - shown.length;
    if (more > 0 && !r.error) out.push(h("p", { class: "muted" }, `И ещё ${more} ${plural(more, "проверка не прошла", "проверки не прошли", "проверок не прошли")} — сначала исправь эти.`));
    for (const it of failed.filter((i) => i.kind === "structure")) {
      out.push(h("div", { class: "card test" }, h("div", { class: "q" }, "В коде не хватает: " + it.title.replace(/^есть /, "")), h("p", {}, it.message)));
    }
    if (good) out.push(h("p", { class: "passed-list" }, `✓ ${good} ${plural(good, "проверка прошла", "проверки прошли", "проверок прошли")}.`));
    if (!r.ok && !r.error) {
      out.push(h("div", { class: "card", style: "background: var(--brand-soft); border-left: 3px solid var(--brand); margin-top: 10px;" },
        h("button", { class: "secondary small", onclick: () => askAiAboutError(t, r) }, "Спросить ИИ об ошибке")));
    }
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
    const box = h("div", { class: "task-hints" });
    for (let i = 1; i <= t.hints_count; i++) {
      if (hints[i - 1]) box.append(h("div", { class: "hint" }, h("b", {}, `${i}. `), hints[i - 1]));
      else if (i <= st.hints) box.append(h("button", { class: "secondary small", onclick: () => send("hint", { task: t.id, level: i }) }, `Показать подсказку ${i}`));
      else if (i === (st.hints || 0) + 1) {
        // сначала ученик пробует сам: подсказка N открывается после N проверок
        if ((st.attempts || 0) >= i) box.append(h("button", { class: "secondary", onclick: () => send("hint", { task: t.id, level: i }) }, `Открыть подсказку ${i} из ${t.hints_count}`));
        else box.append(h("div", { class: "locked" }, i === 1 ? "🔒 Сначала попробуй сам. Подсказка откроется после первой проверки."
          : `🔒 Подсказка ${i} откроется после ${i}-й проверки.`));
        break;
      }
    }
    return box;
  }

  // ---------- ИИ-помощник
  function formatAiMarkdown(text) {
    if (typeof text === "object" && text !== null) {
      text = text.content || "";
    }
    if (!text) return "";
    const codeBlocks = [];
    let s = String(text).replace(/```(?:[a-zA-Z0-9_-]+)?\n?([\s\S]*?)```/g, (_m, code) => {
      codeBlocks.push(code.trim());
      return `___CODE_BLOCK_${codeBlocks.length - 1}___`;
    });
    s = esc(s);
    s = s.replace(/`([^`]+)`/g, "<code>$1</code>");
    s = s.replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");
    s = s.replace(/\*([^*\n]+)\*/g, "<i>$1</i>");
    s = s.replace(/\n/g, "<br>");
    s = s.replace(/___CODE_BLOCK_(\d+)___/g, (_m, idx) => {
      return `<pre><code>${esc(codeBlocks[Number(idx)] || "")}</code></pre>`;
    });
    return s;
  }

  function sendAiMessage(text, taskId) {
    text = (text || "").trim();
    if (!text || ui.chatLoading || view.offline || view.state.ai?.mode === "pause") return;
    ui.chatHistory = ui.chatHistory || [];
    ui.chatHistory.push({ role: "user", content: text, ts: Date.now() });
    ui.chatLoading = true;
    ui.chatDraft = "";
    save();
    render();
    const msgsToSend = ui.chatHistory
      .filter((m) => m.role === "user" || m.role === "assistant")
      .slice(-10)
      .map((m) => ({
        role: m.role,
        content: typeof m.content === "object" && m.content ? (m.content.content || "") : String(m.content || "")
      }));

    send("aiChat", {
      messages: msgsToSend,
      taskId: taskId || ui.task || null
    });
  }

  function askAiAboutError(t, check) {
    go({ tab: "chat", task: t.id });
    let prompt = `Я решаю задание «${t.num}. ${t.title}».`;
    if (t.statement) {
      prompt += ` Условие: ${t.statement.replace(/\n+/g, " ")}.`;
    }
    prompt += ` При проверке возникла ошибка. `;
    if (check.error && check.error.text) {
      prompt += `Ошибка: ${check.error.text}`;
      if (check.error.code_line) prompt += ` в строке: ${check.error.code_line.trim()}`;
      prompt += `. Помоги понять, что не так в коде?`;
    } else if (check.items) {
      const bad = check.items.find((i) => !i.ok);
      if (bad) {
        if (bad.why) prompt += bad.why + ". ";
        if (bad.message) prompt += bad.message + ". ";
        if (bad.dialog && bad.dialog.length) {
          prompt += "Вывод программы отличается от ожидаемого. ";
        }
      }
      prompt += "Подскажи, где я ошибся, но не давай готовый код!";
    } else {
      prompt += "Программа не проходит проверку. В чём может быть причина?";
    }
    sendAiMessage(prompt, t.id);
  }

  function chatView() {
    const currentTask = view.lesson.tasks.find((t) => t.id === ui.task);
    const ai = view.state.ai;
    const history = ui.chatHistory || [];
    const disabled = ui.chatLoading || view.offline || ai?.mode === "pause";
    const out = [h("div", { class: "chat-head" }, h("h1", {}, "ИИ-помощник"),
      history.length && !ui.chatLoading ? h("button", { class: "link", onclick: () => {
        ui.chatHistory = [];
        ui.chatDraft = "";
        save();
        render();
      } }, "Очистить чат") : null)];
    out.push(currentTask ? h("div", { class: "card chat-context" },
      h("p", {}, h("b", {}, "Задание: "), currentTask.title),
      h("div", { class: "row" },
        h("button", { class: "link", onclick: () => go({ tab: "tasks" }) }, "Вернуться к заданию"),
        h("button", { class: "link", onclick: () => go({ tab: "chat", task: null }) }, "Спросить без задания")))
      : h("p", { class: "muted" }, "Спроси про Python или про ошибку в программе."));
    if (ai?.mode === "pause" || ai?.mode === "offline") {
      out.push(h("p", { class: "muted", role: "status" }, ai.mode === "pause"
        ? "Учитель поставил ответы ИИ на паузу. Можно открыть учебник или позвать учителя."
        : "Включён запасной режим. Ответы могут быть общими."));
    }
    const suggestions = currentTask ? ["С чего начать?", "Объясни условие простыми словами"]
      : ["Как работают input() и print()?", "Как понять ошибку Python?"];
    if (!history.length) {
      out.push(h("div", { class: "chat-chips" }, suggestions.map((question) => h("button", { class: "chat-chip", disabled,
        onclick: () => sendAiMessage(question, currentTask?.id) }, question))));
    }
    if (history.length || ui.chatLoading) {
      out.push(h("div", { class: "chat-msgs", id: "chat-box", role: "log", "aria-label": "Сообщения" },
        history.map((message) => {
          const content = typeof message.content === "object" && message.content ? message.content.content : message.content;
          if (message.role === "assistant") return h("div", { class: "chat-msg assistant", html: formatAiMarkdown(content) });
          if (message.role === "error") return h("div", { class: "chat-msg error" }, h("b", {}, "Ответ не получен. "), content);
          return h("div", { class: "chat-msg user" }, content);
        }),
        ui.chatLoading ? h("p", { class: "chat-typing" }, "Жду ответ…") : null));
    }
    const input = h("input", { id: "ai-question", type: "text", value: ui.chatDraft, disabled,
      placeholder: "Например, ошибка в цикле" });
    const button = h("button", { id: "ai-send", type: "submit", disabled: disabled || !input.value.trim() },
      ui.chatLoading ? "Отправлено" : "Отправить");
    input.addEventListener("input", () => {
      ui.chatDraft = input.value;
      button.disabled = disabled || !input.value.trim();
      save();
    });
    out.push(h("form", { class: "chat-form", onsubmit: (e) => {
      e.preventDefault();
      if (!button.disabled) sendAiMessage(input.value, currentTask?.id);
    } }, h("label", { for: input.id }, "Твой вопрос"),
    h("div", { class: "chat-input-row" }, input, button)));
    return out;
  }

  // ---------- учебник
  function theory() {
    const out = [h("h1", {}, "Учебник"), h("p", { class: "muted" }, "Короткие объяснения к уроку. Примеры перепечатай в свой файл руками — так запоминается лучше.")];
    if (!view.lesson.theory.length && !(view.lesson.stages || []).length) {
      out.push(h("div", { class: "card" }, "Для этого занятия учебника в панели пока нет. Смотри на экран учителя и загляни в «Шпаргалку»."));
    }
    out.push(h("div", { class: "card", style: "border-left: 4px solid var(--accent, #3b82f6); background: rgba(59, 130, 246, 0.08);" },
      h("h2", {}, "🧪 Поле тренировки и экспериментов"),
      h("p", {}, "Здесь можно свободно писать любой код, тестировать команды и нейросеть перед решением заданий. Внутри уже есть живые примеры и шпаргалка!"),
      h("div", { class: "row", style: "margin-top:8px" },
        h("button", { onclick: () => send("openNotebook") }, view.notebookExists ? "Открыть Тренировка.py" : "Создать поле тренировки"),
        view.notebookExists ? h("button", { class: "secondary", onclick: () => send("runNotebook") }, "▶ Запустить тренировку") : null)));
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
    const commonMistakes = [
      ["NameError: name 'ask' is not defined", "Забыл импортировать функцию. Напиши в самом верху файла: from ai import ask"],
      ["SyntaxError: expected ':'", "В конце строк с if, else, for, while, def обязательно должно стоять двоеточие :"],
      ["IndentationError: expected an indented block", "После if, for, def все строчки внутри должны быть сдвинуты на 4 пробела (клавиша Tab)"],
      ["ValueError: invalid literal for int()", "Ввели буквы вместо цифр. input() даёт текст, а int() переводит в число только цифры"],
      ["TypeError: can only concatenate str to str", "Нельзя склеивать текст и число: используй f-строку f\"Мне {age} лет\""],
      ["Ответ в консоли печатается как None", "Функция ничего не вернула, либо забыл написать print(ask(...))"],
    ];
    out.push(h("div", { class: "card" }, h("h2", {}, "💡 Подсказки и частые ошибки"),
      h("table", { class: "cheat" }, commonMistakes.map((r) => h("tr", {}, h("td", { style: "color:var(--bad, #f87171);font-weight:600;" }, r[0]), h("td", {}, r[1]))))));
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
    const goTo = (id, title) => h("button", { id: "section-" + id, class: "secondary", onclick: () => go({ tab: id }) }, title);
    out.push(h("div", { class: "help-links" }, goTo("chat", "Спросить ИИ"), goTo("theory", "Учебник"), goTo("cheat", "Шпаргалка")));
    if (view.state.help_open) {
      out.push(h("section", { class: "card" }, h("h2", { role: "status" }, "Учитель получил просьбу"),
        h("button", { class: "secondary", onclick: () => send("helpCancel") }, "Я уже разобрался")));
    } else {
      const txt = h("input", { id: "help-text", placeholder: "Например, не понимаю ошибку", value: ui.helpText });
      txt.addEventListener("input", () => { ui.helpText = txt.value; save(); });
      out.push(h("section", { class: "card" }, h("h2", {}, "Позвать учителя"),
        h("form", { class: "help-form", onsubmit: (e) => {
          e.preventDefault();
          send("help", { text: txt.value });
          ui.helpText = "";
          save();
          txt.value = "";
        } }, h("label", { for: txt.id }, "Что случилось? (необязательно)"), txt,
        h("button", { disabled: view.offline, type: "submit" }, "Позвать учителя"))));
    }
    const faq = [
      ["Где писать код и куда вводить ответы?", "В задании нажми «Создать файл». Код пиши слева. Нажми «Запустить» и вводи ответы в консоли снизу. Кнопка «Проверить» сама попробует несколько вариантов."],
      ["Что делать, если программа показывает ошибку?", "Нажми «Проверить». Панель покажет, что исправить. В задании есть «Подсказки и помощь», а в разделе «Действия с файлом» можно начать заново."],
      ["Почему буквы в коде странные?", "Проверь раскладку: команды Python пишутся английскими буквами. Текст в кавычках — любыми."],
    ];
    if (view.lesson.uses_ai) {
      faq.push(["Что делать, если программа с ИИ долго отвечает?", "Подожди ответа или позови учителя. Обычная автопроверка заданий работает с тестовыми ответами."],
        ["Где ключ от нейросети?", "Панель сама создаёт файл .env рядом с ai.py. Никому не показывай ключ."]);
    }
    out.push(h("section", { class: "card faq" }, h("h2", {}, "Как работать"),
      faq.map(([q, a], i) => details("faq" + i, q, h("p", {}, a)))));
    out.push(h("section", { class: "card" }, details("student-other", "Другие действия",
      h("div", { class: "row" },
        playOn() ? goTo("games", "Игры для перерыва") : null,
        view.lesson.tasks.length && !view.lesson.team_project ? h("button", { class: "link danger-text",
          onclick: () => send("resetLesson", { lesson: view.lesson.lesson }) }, "Начать занятие заново") : null,
        h("button", { class: "link", onclick: () => send("logout") }, "Выйти из курса")))));
    return out;
  }

  send("ready");
})();
