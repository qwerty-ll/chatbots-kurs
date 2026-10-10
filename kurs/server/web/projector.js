// Экран для проектора: таймер и сколько учеников сдали каждое открытое задание. Без имён.
"use strict";
const $ = (id) => document.getElementById(id);
let data = null;
let offset = 0;

document.getElementById("fs").addEventListener("click", () => {
  if (document.fullscreenElement) document.exitFullscreen(); else document.documentElement.requestFullscreen();
});

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

async function refresh() {
  try {
    const r = await fetch("/tapi/overview", { credentials: "same-origin" });
    if (r.status === 401) { $("main").replaceChildren(el("div", "empty", "Войдите в пульт учителя в соседней вкладке.")); return; }
    data = await r.json();
    offset = Date.now() / 1000 - data.now;
  } catch (e) {
    return;
  }
  render();
}

function render() {
  const st = data.state;
  const lesson = data.lessons.find((l) => l.lesson === st.lesson) || data.lessons[0];
  $("title").textContent = st.running ? `Занятие ${lesson.lesson}. ${lesson.title}` : "Занятие скоро начнётся";
  const online = data.students.filter((s) => s.pc).length;
  $("sub").textContent = st.running ? `На уроке: ${online} из ${data.students.length}` : "";
  const main = $("main");
  if (st.paused) {
    const p = el("div", "pause");
    p.append(el("div", "ic", "👀"), el("h2", "", st.pause_text || "Смотрим на учителя"));
    main.className = "pause";
    main.replaceChildren(...p.childNodes);
    return;
  }
  main.className = "tasks";
  const open = lesson.tasks.filter((t) => st.open_tasks.includes(t.id));
  if (!st.running || !open.length) {
    main.replaceChildren(el("div", "empty", st.running ? "Скоро откроем задания" : ""));
    return;
  }
  const total = data.students.length || 1;
  main.replaceChildren(...open.map((t) => {
    const passed = data.students.filter((s) => s.results[t.id] && s.results[t.id].status === "passed").length;
    const row = el("div", "task");
    const bar = el("div", "track");
    const fill = el("i");
    fill.style.width = `${Math.round((100 * passed) / total)}%`;
    bar.append(fill);
    row.append(el("div", "", `${t.num}. ${t.title}`), bar, el("div", "count", `${passed} из ${data.students.length}`));
    return row;
  }));
}

function tick() {
  if (!data || !data.state.timer_end) { $("timer").textContent = ""; return; }
  const left = Math.max(0, Math.round(data.state.timer_end + offset - Date.now() / 1000));
  $("timer").textContent = String(Math.floor(left / 60)).padStart(2, "0") + ":" + String(left % 60).padStart(2, "0");
  const lbl = document.createElement("small");
  lbl.textContent = data.state.timer_label || "осталось";
  $("timer").append(lbl);
}

refresh();
setInterval(refresh, 3000);
setInterval(tick, 1000);
