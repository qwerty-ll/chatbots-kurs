// Экран для проектора: таймер и сколько учеников сдали каждое открытое задание. Без имён.
"use strict";
const $ = (id) => document.getElementById(id);
let data = null;
let teams = null;
let offset = 0;

const fsBtn = $("fs");
function syncFsLabel() {
  if (fsBtn) fsBtn.textContent = document.fullscreenElement ? "Выйти из полного экрана" : "Во весь экран";
}
fsBtn.addEventListener("click", () => {
  const p = document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen();
  if (p && typeof p.catch === "function") p.catch(() => {});
});
document.addEventListener("fullscreenchange", syncFsLabel);
syncFsLabel();

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

function plural(n, one, few, many) {
  return n % 10 === 1 && n % 100 !== 11 ? one : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20) ? few : many;
}

function resetScreen(message) {
  data = null;
  teams = null;
  $("title").textContent = "Экран для проектора";
  $("sub").textContent = "";
  $("timer").textContent = "";
  const main = $("main");
  main.className = "tasks";
  main.replaceChildren(el("div", "empty", message));
}

async function refresh() {
  try {
    const r = await fetch("/tapi/overview", { credentials: "same-origin" });
    if (r.status === 401) {
      resetScreen("Войдите в пульт учителя в соседней вкладке.");
      return;
    }
    if (!r.ok) {
      resetScreen(`Ошибка сервера (${r.status}). Проверьте подключение.`);
      return;
    }
    const nextData = await r.json();
    let nextTeams = null;
    try {
      const tr = await fetch("/tapi/teams", { credentials: "same-origin" });
      if (tr.ok) nextTeams = await tr.json();
    } catch (e) { /* список команд необязателен */ }
    data = nextData;
    teams = nextTeams;
    offset = Date.now() / 1000 - (typeof data.now === "number" ? data.now : Date.now() / 1000);
  } catch (e) {
    if (!data) resetScreen("Нет связи с сервером.");
    return;
  }
  render();
}

function renderPoll(poll) {
  const nodes = [];
  const head = el("div", "section-head");
  head.append(el("h2", "", poll.question || "Голосование"));
  if (Array.isArray(poll.options) && poll.options.length) {
    const total = poll.total || 0;
    head.append(el("p", "", `Идёт голосование · голосов: ${total}`));
    nodes.push(head);
    const counts = Array.isArray(poll.counts) ? poll.counts : [];
    const maxBase = total || 1;
    poll.options.forEach((opt, i) => {
      const count = Number(counts[i] || 0);
      const row = el("div", "task");
      const bar = el("div", "track poll-bar");
      const fill = el("i");
      fill.style.width = `${Math.round((100 * count) / maxBase)}%`;
      bar.append(fill);
      row.append(el("div", "", opt), bar, el("div", "count", `${count}`));
      nodes.push(row);
    });
  } else {
    const ideas = Array.isArray(poll.ideas) ? poll.ideas : [];
    const total = ideas.reduce((n, item) => n + Number(item.count || 0), 0);
    head.append(el("p", "", `Идёт сбор идей · предложений: ${total}`));
    nodes.push(head);
    if (!ideas.length) {
      nodes.push(el("div", "empty", "Предлагайте темы в панели курса"));
    } else {
      const maxCount = Math.max(1, ...ideas.map((item) => Number(item.count || 0)));
      ideas.slice(0, 8).forEach((item) => {
        const count = Number(item.count || 0);
        const row = el("div", "task");
        const bar = el("div", "track poll-bar");
        const fill = el("i");
        fill.style.width = `${Math.round((100 * count) / maxCount)}%`;
        bar.append(fill);
        row.append(el("div", "", item.topic || ""), bar, el("div", "count", `${count}`));
        nodes.push(row);
      });
    }
  }
  return nodes;
}

function renderTeams(teamsData) {
  const list = Array.isArray(teamsData.teams) ? teamsData.teams : [];
  const game = teamsData.team_project === "game";
  const head = el("div", "section-head");
  head.append(el("h2", "", game ? "Студия разработки игры" : "Командный проект"));
  const released = game ? list.filter((t) => t.studio && t.studio.release).length : 0;
  const readyBots = !game ? list.filter((t) => Array.isArray(t.members) && t.members.length > 0 && t.members.every((m) => m.status === "passed")).length : 0;
  const summaryParts = [`Команд: ${list.length}`];
  if (game) summaryParts.push(`сдали: ${released}`);
  else if (list.length) summaryParts.push(`готовы: ${readyBots}`);
  if (Array.isArray(teamsData.free) && teamsData.free.length) {
    summaryParts.push(`без команды: ${teamsData.free.length}`);
  }
  head.append(el("p", "", summaryParts.join(" · ")));

  if (!list.length) {
    return [head, el("div", "empty", "Команды скоро появятся")];
  }

  const grid = el("div", "teams-grid");
  for (const t of list) {
    const members = Array.isArray(t.members) ? t.members : [];
    let isReady = false;
    let statusText = "";
    let metaText = `${members.length} ${plural(members.length, "участник", "участника", "участников")}`;

    if (game) {
      const studio = t.studio || {};
      if (studio.release) {
        isReady = true;
        statusText = studio.release.mode === "template" ? "✓ Сдано (шаблон)" : "✓ Сдано";
      } else if (studio.revision) {
        statusText = "Меню сохранено · ждём сборку";
      } else {
        statusText = "В работе";
      }
      if (studio.menu && studio.menu.title) {
        metaText = `${studio.menu.title} · ${metaText}`;
      }
    } else {
      const passed = members.filter((m) => m.status === "passed").length;
      isReady = members.length > 0 && passed === members.length;
      statusText = isReady ? "✓ Инструменты готовы" : members.length ? `Готово: ${passed} из ${members.length}` : "Ждёт участников";
      if (t.bot_name) metaText = `🤖 ${t.bot_name} · ${metaText}`;
    }

    const card = el("div", "team-card" + (isReady ? " ready" : ""));
    card.append(
      el("div", "team-name", t.name || "Команда"),
      el("div", "team-meta", metaText),
      el("div", "team-status " + (isReady ? "ok" : "wait"), statusText)
    );
    grid.append(card);
  }
  return [head, grid];
}

function render() {
  if (!data || !data.state) {
    resetScreen("Нет данных от сервера.");
    return;
  }
  const st = data.state;
  const lessons = Array.isArray(data.lessons) ? data.lessons : [];
  const lesson = lessons.find((l) => l.lesson === st.lesson) || lessons[0] || null;
  const students = Array.isArray(data.students) ? data.students : [];
  $("title").textContent = st.running
    ? (lesson ? `Занятие ${lesson.lesson}. ${lesson.title}` : `Занятие ${st.lesson || ""}`)
    : "Занятие скоро начнётся";
  const online = students.filter((s) => s.pc).length;
  $("sub").textContent = st.running ? `На уроке: ${online} из ${students.length}` : "";
  const main = $("main");
  if (st.paused) {
    const p = el("div", "pause");
    p.append(el("div", "ic", "👀"), el("h2", "", st.pause_text || "Смотрим на учителя"));
    main.className = "pause";
    main.replaceChildren(...p.childNodes);
    return;
  }
  main.className = "tasks";
  const openIds = Array.isArray(st.open_tasks) ? st.open_tasks : [];
  const tasks = lesson && Array.isArray(lesson.tasks) ? lesson.tasks : [];
  const open = tasks.filter((t) => openIds.includes(t.id));

  if (st.running && open.length) {
    const total = students.length || 1;
    main.replaceChildren(...open.map((t) => {
      const passed = students.filter((s) => s.results && s.results[t.id] && s.results[t.id].status === "passed").length;
      const row = el("div", "task");
      const bar = el("div", "track");
      const fill = el("i");
      fill.style.width = `${Math.round((100 * passed) / total)}%`;
      bar.append(fill);
      row.append(el("div", "", `${t.num}. ${t.title}`), bar, el("div", "count", `${passed} из ${students.length}`));
      return row;
    }));
    return;
  }

  if (data.poll && data.poll.open) {
    main.replaceChildren(...renderPoll(data.poll));
    return;
  }

  if (st.running && teams && (teams.team_lesson || (lesson && lesson.teams))) {
    main.replaceChildren(...renderTeams(teams));
    return;
  }

  main.replaceChildren(el("div", "empty", st.running ? "Скоро откроем задания" : ""));
}

function tick() {
  if (!data || !data.state || !data.state.timer_end) {
    $("timer").textContent = "";
    return;
  }
  const left = Math.max(0, Math.round(data.state.timer_end + offset - Date.now() / 1000));
  $("timer").textContent = String(Math.floor(left / 60)).padStart(2, "0") + ":" + String(left % 60).padStart(2, "0");
  const lbl = document.createElement("small");
  lbl.textContent = data.state.timer_label || "осталось";
  $("timer").append(lbl);
}

refresh();
setInterval(refresh, 3000);
setInterval(tick, 1000);
