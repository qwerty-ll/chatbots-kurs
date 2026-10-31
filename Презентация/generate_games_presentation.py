#!/usr/bin/env python3
"""Генератор интерактивной презентации курса «Разработка консольных игр на Python» (8 занятий).
Создаёт файл Презентация/games_presentation.html в едином визуальном стиле 1920x1080.
"""
from __future__ import annotations

import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_FILE = os.path.join(HERE, "games_presentation.html")

HTML_HEAD = """<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Разработка консольных игр на Python · 8 занятий</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Rubik:wght@400;500;600;700&display=swap">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Nunito+Sans:wght@400;600;700;800&display=swap">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&display=swap">
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  html, body { width: 100%; height: 100%; background: #0B0E26; overflow: hidden; font-family: 'Nunito Sans', Arial, sans-serif; }
  .frame { display: none; position: absolute; left: 0; top: 0; width: 1920px; height: 1080px; transform-origin: top left; }
  .frame.active { display: block; }
  .stage { position: relative; width: 1920px; height: 1080px; overflow: hidden; }
  .slide { position: relative; width: 1920px; height: 1080px; overflow: hidden; }
  table { border-collapse: collapse; width: 100%; }
  td, th { border: 1px solid #D5DAF0; padding: .45em .7em; vertical-align: top; text-align: left; background: #FFFFFF; }
  th { font-weight: 700; }
  .notes { display: none; }
  #notes { position: fixed; left: 0; right: 0; bottom: 0; max-height: 42vh; overflow: auto; padding: 16px 24px 20px;
            background: rgba(11,14,38,.96); color: #E8EBFF; font: 18px/1.5 'Nunito Sans', Arial, sans-serif; white-space: pre-wrap;
            border-top: 1px solid #2F3480; display: none; z-index: 10; }
  #notes b { color: #A9B5FF; }
  #hud { position: fixed; right: 14px; bottom: 10px; color: #9AA3E0; font: 14px 'Nunito Sans', Arial, sans-serif; z-index: 11;
          background: rgba(11,14,38,.6); padding: 4px 10px; border-radius: 10px; user-select: none; }
  #hint { position: fixed; left: 50%; top: 14px; transform: translateX(-50%); color: #E8EBFF; font: 15px 'Nunito Sans', Arial, sans-serif;
           background: rgba(47,67,232,.92); padding: 8px 16px; border-radius: 12px; z-index: 12; transition: opacity .6s; }
  .code-box { background: #161A3C; color: #70E2FF; font-family: 'JetBrains Mono', monospace; font-size: 26px; line-height: 1.45; padding: 24px 28px; border-radius: 18px; border: 1px solid #2F3876; }
  .code-box .kw { color: #FF7BE5; font-weight: 600; }
  .code-box .fn { color: #5CE1E6; font-weight: 600; }
  .code-box .str { color: #FFDE59; }
  .code-box .com { color: #7E8BBB; font-style: italic; }
  @page { size: 1920px 1080px; margin: 0; }
  @media print {
    html, body { width: 1920px; height: auto; overflow: visible; background: #fff; }
    .frame { display: block !important; position: relative !important; transform: none !important; page-break-after: always; break-after: page; }
    #notes, #hud, #hint { display: none !important; }
    * { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  }
</style>
</head>
<body>
"""

HTML_TAIL = """
<div id="notes"></div>
<div id="hud"></div>
<div id="hint">← → листать · F полный экран · N заметки докладчика · Cmd/Ctrl+P — сохранить как PDF</div>
<script>
(function () {
  var frames = Array.prototype.slice.call(document.querySelectorAll('.frame'));
  var notesBox = document.getElementById('notes'), hud = document.getElementById('hud'), hint = document.getElementById('hint');
  var cur = 0, showNotes = false;

  function fit() {
    var s = Math.min(window.innerWidth / 1920, window.innerHeight / 1080);
    var x = (window.innerWidth - 1920 * s) / 2, y = (window.innerHeight - 1080 * s) / 2;
    frames.forEach(function (f) { f.style.transform = 'translate(' + x + 'px,' + y + 'px) scale(' + s + ')'; });
  }
  function show(i) {
    cur = Math.max(0, Math.min(frames.length - 1, i));
    frames.forEach(function (f, k) { f.classList.toggle('active', k === cur); });
    hud.textContent = (cur + 1) + ' / ' + frames.length;
    var n = frames[cur].querySelector('.notes');
    notesBox.innerHTML = n ? n.innerHTML.replace(/\\n/g, '<br>') : '';
    history.replaceState(null, '', '#' + (cur + 1));
  }
  function toggleFull() {
    if (!document.fullscreenElement) document.documentElement.requestFullscreen && document.documentElement.requestFullscreen();
    else document.exitFullscreen && document.exitFullscreen();
  }
  document.addEventListener('keydown', function (e) {
    var k = e.key;
    if (k === 'ArrowRight' || k === 'PageDown' || k === ' ' || k === 'Enter') { show(cur + 1); e.preventDefault(); }
    else if (k === 'ArrowLeft' || k === 'PageUp' || k === 'Backspace') { show(cur - 1); e.preventDefault(); }
    else if (k === 'Home') show(0);
    else if (k === 'End') show(frames.length - 1);
    else if (k === 'f' || k === 'F' || k === 'а' || k === 'А') toggleFull();
    else if (k === 'n' || k === 'N' || k === 'т' || k === 'Т') { showNotes = !showNotes; notesBox.style.display = showNotes ? 'block' : 'none'; }
  });
  document.addEventListener('click', function (e) {
    if (e.target.closest('a')) return;
    show(e.clientX < window.innerWidth * 0.3 ? cur - 1 : cur + 1);
  });
  window.addEventListener('resize', fit);
  fit();
  var start = parseInt((location.hash || '').slice(1), 10);
  show(isNaN(start) ? 0 : start - 1);
  setTimeout(function () { hint.style.opacity = '0'; }, 5000);
})();
</script>
</body>
</html>
"""


def frame(slide_id: str, bg: str, content: str, notes: str = "", footer_num: int = 1) -> str:
    color = "#FFFFFF" if bg.startswith("#1") or bg.startswith("#2") else "#12163A"
    ft_color = "#9AA3E0" if color == "#FFFFFF" else "#4A5170"
    return f"""<div class="frame" data-id="{slide_id}"><div class="stage">
<section class="slide" id="{slide_id}" data-transition="fade" style="background:{bg};color:{color};font-family:'Nunito Sans', Arial, sans-serif;padding:110px 128px 140px;display:flex;flex-direction:column;gap:36px;">
{content}
<p style="position:absolute;left:128px;bottom:54px;font-size:24px;color:{ft_color}">Разработка консольных игр на Python · 8 занятий</p>
<p style="position:absolute;right:128px;bottom:54px;font-size:24px;color:{ft_color}">{footer_num}</p>
</section></div>
<div class="notes">{notes}</div></div>"""


def card(title: str, text: str, icon_svg: str, bg: str = "#FFFFFF", fg: str = "#12163A") -> str:
    return f"""<div style="flex:1;display:flex;flex-direction:column;gap:16px;background:{bg};border:1px solid #E1E4F0;border-radius:24px;padding:34px;box-shadow:0 4px 24px rgba(18,22,58,.06);color:{fg};">
<div style="width:68px;height:68px;border-radius:50%;background:#2F43E8;display:flex;align-items:center;justify-content:center;color:#fff;">
{icon_svg}
</div>
<h3 style="font-family:'Rubik', Arial, sans-serif;font-size:36px;font-weight:600;line-height:1.2;">{title}</h3>
<p style="font-size:28px;line-height:1.4;opacity:0.9;">{text}</p>
</div>"""


def svg_icon(name: str) -> str:
    icons = {
        "game": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:38px;height:38px"><rect x="2" y="6" width="20" height="12" rx="4"/><line x1="6" y1="12" x2="10" y2="12"/><line x1="8" y1="10" x2="8" y2="14"/><circle cx="15" cy="11" r="1" fill="currentColor"/><circle cx="18" cy="13" r="1" fill="currentColor"/></svg>',
        "code": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:38px;height:38px"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>',
        "star": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:38px;height:38px"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>',
        "play": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:38px;height:38px"><polygon points="5 3 19 12 5 21 5 3"/></svg>',
        "cpu": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:38px;height:38px"><rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><line x1="9" y1="1" x2="9" y2="4"/><line x1="15" y1="1" x2="15" y2="4"/><line x1="9" y1="20" x2="9" y2="23"/><line x1="15" y1="20" x2="15" y2="23"/></svg>',
        "check": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:38px;height:38px"><polyline points="20 6 9 17 4 12"/></svg>'
    }
    return icons.get(name, icons["star"])


def build_slides() -> str:
    frames = []
    idx = 1

    # =========================================================================
    # ТИТУЛЬНЫЙ СЛАЙД
    # =========================================================================
    frames.append(frame("cover", "#12163A", """
<p style="font-size:28px;font-weight:700;letter-spacing:4px;text-transform:uppercase;color:#A9B5FF">Программа дополнительного образования для школьников · 8 занятий</p>
<h1 style="font-family:'Rubik', Arial, sans-serif;font-size:120px;font-weight:700;line-height:1.02;color:#FFFFFF">Разработка консольных игр на Python</h1>
<p style="font-size:46px;line-height:1.3;color:#D5DAFF;width:1400px">От первых шагов в программировании до симуляций, 2D графики и рекордов</p>
<div style="flex:1"></div>
<div style="display:flex;gap:40px;align-items:center;">
  <span style="font-size:32px;color:#A9B5FF;background:#1B2050;padding:12px 24px;border-radius:14px">🎮 8 готовых игр</span>
  <span style="font-size:32px;color:#A9B5FF;background:#1B2050;padding:12px 24px;border-radius:14px">🎯 24 задачи тренировки</span>
  <span style="font-size:32px;color:#A9B5FF;background:#1B2050;padding:12px 24px;border-radius:14px">🌟 8 бонусных прокачек</span>
</div>
""", "Вступительное слово: приветствуем группу, объявляем запуск нового 8-урочного курса по созданию консольных игр.", idx))
    idx += 1

    # =========================================================================
    # ПЛАН КУРСА (2 ЧАСТИ)
    # =========================================================================
    frames.append(frame("course-structure", "#F6F7FB", """
<div style="display:flex;flex-direction:column;gap:14px">
  <p style="font-size:24px;font-weight:700;letter-spacing:3px;text-transform:uppercase;color:#2F43E8">Структура курса</p>
  <h2 style="font-family:'Rubik', Arial, sans-serif;font-size:60px;font-weight:700;color:#12163A">Две части нашего приключения</h2>
</div>
<div style="display:flex;gap:36px;align-items:stretch;flex:1">
  <div style="flex:1;background:#FFFFFF;border:2px solid #2F43E8;border-radius:24px;padding:36px;display:flex;flex-direction:column;gap:20px;box-shadow:0 8px 30px rgba(47,67,232,0.08)">
    <div style="display:flex;align-items:center;gap:14px">
      <span style="background:#2F43E8;color:#fff;font-size:24px;font-weight:700;padding:6px 16px;border-radius:12px">ЧАСТЬ 1</span>
      <h3 style="font-family:'Rubik', sans-serif;font-size:36px;font-weight:700;color:#12163A">Основы Python и Текстовые Игры</h3>
    </div>
    <p style="font-size:26px;color:#4A5170">Занятия 1–4 · Фундамент программирования</p>
    <div style="display:flex;flex-direction:column;gap:12px;font-size:26px;color:#12163A;flex:1">
      <p>🔹 <b>Урок 1:</b> Ввод-вывод, f-строки ➔ <b>Игра «Квест в замке»</b></p>
      <p>🔹 <b>Урок 2:</b> Числа, random, if/else ➔ <b>Игра «Взломщик сейфа»</b></p>
      <p>🔹 <b>Урок 3:</b> Циклы while, счетчики ➔ <b>Игра «RPG-Арена: Битва с Драконом»</b></p>
      <p>🔹 <b>Урок 4:</b> Списки list, random.choice ➔ <b>Игра «Турнир стихий: КНБ»</b></p>
    </div>
  </div>
  <div style="flex:1;background:#FFFFFF;border:2px solid #2F43E8;border-radius:24px;padding:36px;display:flex;flex-direction:column;gap:20px;box-shadow:0 8px 30px rgba(47,67,232,0.08)">
    <div style="display:flex;align-items:center;gap:14px">
      <span style="background:#2F43E8;color:#fff;font-size:24px;font-weight:700;padding:6px 16px;border-radius:12px">ЧАСТЬ 2</span>
      <h3 style="font-family:'Rubik', sans-serif;font-size:36px;font-weight:700;color:#12163A">Консольная Графика и Симуляции</h3>
    </div>
    <p style="font-size:26px;color:#4A5170">Занятия 5–8 · Анимация, сетки 2D и моделирование</p>
    <div style="display:flex;flex-direction:column;gap:12px;font-size:26px;color:#12163A;flex:1">
      <p>🔹 <b>Урок 5:</b> time.sleep, кадры ➔ <b>Игра «Турбо-трасса 2D»</b></p>
      <p>🔹 <b>Урок 6:</b> 2D сетка, координаты, WASD ➔ <b>Игра «Лабиринт Подземелья»</b></p>
      <p>🔹 <b>Урок 7:</b> Клеточные автоматы ➔ <b>«Игра в жизнь: Био-точки»</b></p>
      <p>🔹 <b>Урок 8:</b> Файлы, меню ➔ <b>Финальный Хакатон и Таблица Рекордов</b></p>
    </div>
  </div>
</div>
""", "Объясняем общее расписание: сначала осваиваем логику и текст, потом выходим в 2D графику и симуляцию.", idx))
    idx += 1

    # =========================================================================
    # ПРИНЦИП УРОКА: ТРЕНИРОВКА ➔ ИГРА ➔ ПРОКАЧКА
    # =========================================================================
    frames.append(frame("pedagogy", "#12163A", """
<div style="display:flex;flex-direction:column;gap:14px">
  <p style="font-size:24px;font-weight:700;letter-spacing:3px;text-transform:uppercase;color:#A9B5FF">Как устроен каждый урок</p>
  <h2 style="font-family:'Rubik', Arial, sans-serif;font-size:64px;font-weight:700;color:#FFFFFF">Принцип «Кирпичики ➔ Игра ➔ Прокачка»</h2>
</div>
<div style="display:flex;gap:32px;align-items:stretch;margin-top:20px">
  <div style="flex:1;background:#1B2050;border-radius:24px;padding:36px;display:flex;flex-direction:column;gap:18px">
    <span style="font-size:48px">🎯</span>
    <h3 style="font-family:'Rubik', sans-serif;font-size:38px;color:#FFFFFF">1. Тренировка</h3>
    <p style="font-size:28px;color:#D5DAFF;line-height:1.4">3 короткие задачи на 5–7 минут. Отрабатываем один конкретный кирпичик (ввод, счетчик, проверка или выбор).</p>
  </div>
  <div style="flex:1;background:#2F43E8;border-radius:24px;padding:36px;display:flex;flex-direction:column;gap:18px">
    <span style="font-size:48px">🎮</span>
    <h3 style="font-family:'Rubik', sans-serif;font-size:38px;color:#FFFFFF">2. Сборка игры</h3>
    <p style="font-size:28px;color:#FFFFFF;line-height:1.4">Соединяем решённые задачи воедино! Пишем сюжетную игру, которую можно сразу запустить и пройти.</p>
  </div>
  <div style="flex:1;background:#1B2050;border-radius:24px;padding:36px;display:flex;flex-direction:column;gap:18px">
    <span style="font-size:48px">🌟</span>
    <h3 style="font-family:'Rubik', sans-serif;font-size:38px;color:#FFFFFF">3. Прокачка</h3>
    <p style="font-size:28px;color:#D5DAFF;line-height:1.4">Бонусная задача со звёздочкой. Добавляем в игру супер-удары, шкалы здоровья, препятствия или файл рекордов.</p>
  </div>
</div>
""", "Подчёркиваем: ученики не сидят час над одной непонятной программой. Сначала они легко решают 3 мини-задачи, а потом игра собирается сама собой!", idx))
    idx += 1

    # =========================================================================
    # РАЗДЕЛИТЕЛЬ ЧАСТИ 1
    # =========================================================================
    frames.append(frame("part1-div", "#2F43E8", """
<div style="display:flex;flex-direction:column;gap:20px;justify-content:center;height:100%">
  <p style="font-size:32px;font-weight:700;letter-spacing:4px;text-transform:uppercase;color:#A9B5FF">Блок занятий 1–4</p>
  <h1 style="font-family:'Rubik', sans-serif;font-size:104px;font-weight:700;color:#FFFFFF;line-height:1.05">Часть 1: Основы Python и Текстовые Игры</h1>
  <p style="font-size:42px;color:#E4E8FF;width:1400px">Изучаем язык с самого нуля: команды вывода, ввод игрока, случайные события, циклы боя и списки героев.</p>
</div>
""", "Переход к Части 1.", idx))
    idx += 1

    # =========================================================================
    # УРОК 1: ВВОД, ВЫВОД И КВЕСТ
    # =========================================================================
    frames.append(frame("l1-divider", "#12163A", """
<div style="display:flex;gap:80px;align-items:center;height:100%">
  <div style="width:360px"><p style="font-size:32px;font-weight:700;letter-spacing:4px;color:#A9B5FF">УРОК</p><p style="font-family:'Rubik', sans-serif;font-size:300px;font-weight:700;line-height:0.9;color:#A9B5FF">1</p></div>
  <div style="flex:1;display:flex;flex-direction:column;gap:24px">
    <h2 style="font-family:'Rubik', sans-serif;font-size:72px;font-weight:700;color:#FFFFFF">Ввод-вывод и Игра «Квест в замке»</h2>
    <p style="font-size:34px;color:#D5DAFF">Команды print(), input() и магия f-строк</p>
    <div style="display:flex;flex-direction:column;gap:12px;margin-top:10px">
      <div style="background:#1B2050;padding:16px 24px;border-radius:14px;font-size:28px;color:#fff">🎯 Задачи: «Привет, Игрок!», «Карточка героя», «Рюкзак»</div>
      <div style="background:#2F43E8;padding:16px 24px;border-radius:14px;font-size:28px;color:#fff">🎮 Игра: «Квест в замке» (дверь 1 — золото, дверь 2 — дракон)</div>
      <div style="background:#1B2050;padding:16px 24px;border-radius:14px;font-size:28px;color:#fff">🌟 Прокачка: Выбор оружия (меч или лук)</div>
    </div>
  </div>
</div>
""", "Урок 1: объявляем тему первого занятия.", idx))
    idx += 1

    frames.append(frame("l1-theory", "#F6F7FB", """
<div style="display:flex;flex-direction:column;gap:14px">
  <p style="font-size:24px;font-weight:700;letter-spacing:3px;text-transform:uppercase;color:#2F43E8">Теория Урока 1</p>
  <h2 style="font-family:'Rubik', Arial, sans-serif;font-size:56px;font-weight:700;color:#12163A">Как программа общается с игроком</h2>
</div>
<div style="display:flex;gap:36px;align-items:stretch;margin-top:20px">
  <div style="flex:1;display:flex;flex-direction:column;gap:20px">
    <div style="background:#fff;border:1px solid #D5DAF0;border-radius:20px;padding:28px">
      <h3 style="font-size:32px;color:#2F43E8;margin-bottom:10px">1. Команда print()</h3>
      <p style="font-size:26px;color:#4A5170">Печатает текст на экран: <code>print("Вход в подземелье")</code></p>
    </div>
    <div style="background:#fff;border:1px solid #D5DAF0;border-radius:20px;padding:28px">
      <h3 style="font-size:32px;color:#2F43E8;margin-bottom:10px">2. Команда input()</h3>
      <p style="font-size:26px;color:#4A5170">Спрашивает игрока и ждёт Enter: <code>name = input("Имя: ")</code></p>
    </div>
    <div style="background:#fff;border:1px solid #D5DAF0;border-radius:20px;padding:28px">
      <h3 style="font-size:32px;color:#2F43E8;margin-bottom:10px">3. f-строки</h3>
      <p style="font-size:26px;color:#4A5170">Удобно подставляют переменные: <code>print(f"Привет, {name}!")</code></p>
    </div>
  </div>
  <div style="flex:1;display:flex;flex-direction:column;justify-content:center">
    <div class="code-box">
<span class="com"># Создаём карточку персонажа</span><br>
hero = <span class="fn">input</span>(<span class="str">"Имя героя: "</span>)<br>
cls = <span class="fn">input</span>(<span class="str">"Класс: "</span>)<br>
<br>
<span class="fn">print</span>(<span class="str">f"Герой: {hero} | Класс: {cls}"</span>)<br>
<br>
<span class="com"># Выбор пути</span><br>
door = <span class="fn">input</span>(<span class="str">"Какую дверь открыть? (1 или 2): "</span>)<br>
<span class="kw">if</span> door == <span class="str">"1"</span>:<br>
&nbsp;&nbsp;&nbsp;&nbsp;<span class="fn">print</span>(<span class="str">"В комнате сундук с золотом!"</span>)<br>
<span class="kw">else</span>:<br>
&nbsp;&nbsp;&nbsp;&nbsp;<span class="fn">print</span>(<span class="str">"В комнате спит дракон!"</span>)
    </div>
  </div>
</div>
""", "Разбираем синтаксис print, input и if/else.", idx))
    idx += 1

    # =========================================================================
    # УРОК 2: RANDOM И ВЗЛОМЩИК СЕЙФА
    # =========================================================================
    frames.append(frame("l2-divider", "#12163A", """
<div style="display:flex;gap:80px;align-items:center;height:100%">
  <div style="width:360px"><p style="font-size:32px;font-weight:700;letter-spacing:4px;color:#A9B5FF">УРОК</p><p style="font-family:'Rubik', sans-serif;font-size:300px;font-weight:700;line-height:0.9;color:#A9B5FF">2</p></div>
  <div style="flex:1;display:flex;flex-direction:column;gap:24px">
    <h2 style="font-family:'Rubik', sans-serif;font-size:72px;font-weight:700;color:#FFFFFF">Числа, случайность и «Взломщик сейфа»</h2>
    <p style="font-size:34px;color:#D5DAFF">int(), модуль random и сравнения &lt;, &gt;, ==</p>
    <div style="display:flex;flex-direction:column;gap:12px;margin-top:10px">
      <div style="background:#1B2050;padding:16px 24px;border-radius:14px;font-size:28px;color:#fff">🎯 Задачи: «Бросок кубика», «Сравнение чисел», «Секретный пин-код»</div>
      <div style="background:#2F43E8;padding:16px 24px;border-radius:14px;font-size:28px;color:#fff">🎮 Игра: «Взломщик сейфа» (подсказки «Код больше!» и «Код меньше!»)</div>
      <div style="background:#1B2050;padding:16px 24px;border-radius:14px;font-size:28px;color:#fff">🌟 Прокачка: 3 попытки до включения тревоги</div>
    </div>
  </div>
</div>
""", "Урок 2: модуль random и сравнение чисел.", idx))
    idx += 1

    # =========================================================================
    # УРОК 3: WHILE И RPG-АРЕНА
    # =========================================================================
    frames.append(frame("l3-divider", "#12163A", """
<div style="display:flex;gap:80px;align-items:center;height:100%">
  <div style="width:360px"><p style="font-size:32px;font-weight:700;letter-spacing:4px;color:#A9B5FF">УРОК</p><p style="font-family:'Rubik', sans-serif;font-size:300px;font-weight:700;line-height:0.9;color:#A9B5FF">3</p></div>
  <div style="flex:1;display:flex;flex-direction:column;gap:24px">
    <h2 style="font-family:'Rubik', sans-serif;font-size:72px;font-weight:700;color:#FFFFFF">Циклы while, счетчики и «RPG-Арена»</h2>
    <p style="font-size:34px;color:#D5DAFF">Пошаговый бой: очки здоровья (HP), урон (-=) и лечение (+=)</p>
    <div style="display:flex;flex-direction:column;gap:12px;margin-top:10px">
      <div style="background:#1B2050;padding:16px 24px;border-radius:14px;font-size:28px;color:#fff">🎯 Задачи: «Обратный отсчёт», «Сбор монет», «Урон манекену»</div>
      <div style="background:#2F43E8;padding:16px 24px;border-radius:14px;font-size:28px;color:#fff">🎮 Игра: «RPG-Арена: Битва с Драконом» (атака мечом / зелье лечения)</div>
      <div style="background:#1B2050;padding:16px 24px;border-radius:14px;font-size:28px;color:#fff">🌟 Прокачка: Графика полоски HP [■■■■■□□□□□]</div>
    </div>
  </div>
</div>
""", "Урок 3: пошаговый игровой цикл в while.", idx))
    idx += 1

    # =========================================================================
    # УРОК 4: СПИСКИ И ТУРНИР СТИХИЙ (КНБ)
    # =========================================================================
    frames.append(frame("l4-divider", "#12163A", """
<div style="display:flex;gap:80px;align-items:center;height:100%">
  <div style="width:360px"><p style="font-size:32px;font-weight:700;letter-spacing:4px;color:#A9B5FF">УРОК</p><p style="font-family:'Rubik', sans-serif;font-size:300px;font-weight:700;line-height:0.9;color:#A9B5FF">4</p></div>
  <div style="flex:1;display:flex;flex-direction:column;gap:24px">
    <h2 style="font-family:'Rubik', sans-serif;font-size:72px;font-weight:700;color:#FFFFFF">Списки и «Турнир стихий (КНБ)»</h2>
    <p style="font-size:34px;color:#D5DAFF">Списки [...], append(), выбор random.choice и оператор in</p>
    <div style="display:flex;flex-direction:column;gap:12px;margin-top:10px">
      <div style="background:#1B2050;padding:16px 24px;border-radius:14px;font-size:28px;color:#fff">🎯 Задачи: «Отряд героев», «Случайное событие», «Проверка заклинания»</div>
      <div style="background:#2F43E8;padding:16px 24px;border-radius:14px;font-size:28px;color:#fff">🎮 Игра: «Турнир стихий: Камень-Ножницы-Бумага» против ИИ</div>
      <div style="background:#1B2050;padding:16px 24px;border-radius:14px;font-size:28px;color:#fff">🌟 Прокачка: Ведение журнала раундов и статистики матча</div>
    </div>
  </div>
</div>
""", "Урок 4: списки и соревновательная игровая механика.", idx))
    idx += 1

    # =========================================================================
    # РАЗДЕЛИТЕЛЬ ЧАСТИ 2
    # =========================================================================
    frames.append(frame("part2-div", "#2F43E8", """
<div style="display:flex;flex-direction:column;gap:20px;justify-content:center;height:100%">
  <p style="font-size:32px;font-weight:700;letter-spacing:4px;text-transform:uppercase;color:#A9B5FF">Блок занятий 5–8</p>
  <h1 style="font-family:'Rubik', sans-serif;font-size:100px;font-weight:700;color:#FFFFFF;line-height:1.05">Часть 2: Консольная Графика, Сетки и Симуляции</h1>
  <p style="font-size:42px;color:#E4E8FF;width:1400px">Переходим от текста к динамике: кадры анимации, сетки 2D, движение WASD, симуляция «Игра в жизнь» и сохранение рекордов в файл!</p>
</div>
""", "Переход к Части 2 курса.", idx))
    idx += 1

    # =========================================================================
    # УРОК 5: ТУРБО-ТРАССА 2D
    # =========================================================================
    frames.append(frame("l5-divider", "#12163A", """
<div style="display:flex;gap:80px;align-items:center;height:100%">
  <div style="width:360px"><p style="font-size:32px;font-weight:700;letter-spacing:4px;color:#A9B5FF">УРОК</p><p style="font-family:'Rubik', sans-serif;font-size:300px;font-weight:700;line-height:0.9;color:#A9B5FF">5</p></div>
  <div style="flex:1;display:flex;flex-direction:column;gap:24px">
    <h2 style="font-family:'Rubik', sans-serif;font-size:72px;font-weight:700;color:#FFFFFF">Консольная анимация и «Турбо-трасса 2D»</h2>
    <p style="font-size:34px;color:#D5DAFF">Задержка time.sleep, покадровая отрисовка и границы дороги</p>
    <div style="display:flex;flex-direction:column;gap:12px;margin-top:10px">
      <div style="background:#1B2050;padding:16px 24px;border-radius:14px;font-size:28px;color:#fff">🎯 Задачи: «Бегущий спортсмен», «Индикатор загрузки», «Полоса трассы»</div>
      <div style="background:#2F43E8;padding:16px 24px;border-radius:14px;font-size:28px;color:#fff">🎮 Игра: «Турбо-трасса 2D» (руление машиной 🏎 по 5 полосам)</div>
      <div style="background:#1B2050;padding:16px 24px;border-radius:14px;font-size:28px;color:#fff">🌟 Прокачка: Препятствия 🚧 и проверка аварий</div>
    </div>
  </div>
</div>
""", "Урок 5: покадровая консольная анимация.", idx))
    idx += 1

    # =========================================================================
    # УРОК 6: 2D СЕТКА, КООРДИНАТЫ И ЛАБИРИНТ
    # =========================================================================
    frames.append(frame("l6-divider", "#12163A", """
<div style="display:flex;gap:80px;align-items:center;height:100%">
  <div style="width:360px"><p style="font-size:32px;font-weight:700;letter-spacing:4px;color:#A9B5FF">УРОК</p><p style="font-family:'Rubik', sans-serif;font-size:300px;font-weight:700;line-height:0.9;color:#A9B5FF">6</p></div>
  <div style="flex:1;display:flex;flex-direction:column;gap:24px">
    <h2 style="font-family:'Rubik', sans-serif;font-size:72px;font-weight:700;color:#FFFFFF">2D сетка, координаты и «Лабиринт Подземелья»</h2>
    <p style="font-size:34px;color:#D5DAFF">Координаты (X, Y), вложенные циклы for и управление WASD</p>
    <div style="display:flex;flex-direction:column;gap:12px;margin-top:10px">
      <div style="background:#1B2050;padding:16px 24px;border-radius:14px;font-size:28px;color:#fff">🎯 Задачи: «Печать сетки 3x3», «Игрок @ на сетке», «Перемещение WASD»</div>
      <div style="background:#2F43E8;padding:16px 24px;border-radius:14px;font-size:28px;color:#fff">🎮 Игра: «Лабиринт Подземелья» (проведи героя от (0,0) к выходу)</div>
      <div style="background:#1B2050;padding:16px 24px;border-radius:14px;font-size:28px;color:#fff">🌟 Прокачка: Сбор золотых сундуков на карте</div>
    </div>
  </div>
</div>
""", "Урок 6: координаты и 2D сетка.", idx))
    idx += 1

    # =========================================================================
    # УРОК 7: ИГРА В ЖИЗНЬ (СИМУЛЯЦИЯ ТОЧЕК)
    # =========================================================================
    frames.append(frame("l7-divider", "#12163A", """
<div style="display:flex;gap:80px;align-items:center;height:100%">
  <div style="width:360px"><p style="font-size:32px;font-weight:700;letter-spacing:4px;color:#A9B5FF">УРОК</p><p style="font-family:'Rubik', sans-serif;font-size:300px;font-weight:700;line-height:0.9;color:#A9B5FF">7</p></div>
  <div style="flex:1;display:flex;flex-direction:column;gap:24px">
    <h2 style="font-family:'Rubik', sans-serif;font-size:72px;font-weight:700;color:#FFFFFF">Симуляции и био-точки: «Игра в жизнь»</h2>
    <p style="font-size:34px;color:#D5DAFF">Клеточный автомат Джона Конвея, био-точки ● и ·, поколения</p>
    <div style="display:flex;flex-direction:column;gap:12px;margin-top:10px">
      <div style="background:#1B2050;padding:16px 24px;border-radius:14px;font-size:28px;color:#fff">🎯 Задачи: «Закон клетки», «Счёт био-точек», «Отрисовка колонии»</div>
      <div style="background:#2F43E8;padding:16px 24px;border-radius:14px;font-size:28px;color:#fff">🎮 Игра: Симулятор «Колония био-точек» (осциллятор-мигалка)</div>
      <div style="background:#1B2050;padding:16px 24px;border-radius:14px;font-size:28px;color:#fff">🌟 Прокачка: Каталог био-организмов (Блок и Мигалка)</div>
    </div>
  </div>
</div>
""", "Урок 7: симуляция клеточных автоматов.", idx))
    idx += 1

    frames.append(frame("l7-rules", "#F6F7FB", """
<div style="display:flex;flex-direction:column;gap:14px">
  <p style="font-size:24px;font-weight:700;letter-spacing:3px;text-transform:uppercase;color:#2F43E8">Моделирование жизни</p>
  <h2 style="font-family:'Rubik', Arial, sans-serif;font-size:56px;font-weight:700;color:#12163A">3 Закона Джона Конвея для био-точек</h2>
</div>
<div style="display:flex;gap:32px;align-items:stretch;margin-top:20px">
  <div style="flex:1;background:#fff;border-radius:24px;padding:36px;border:1px solid #D5DAF0;display:flex;flex-direction:column;gap:18px">
    <div style="width:64px;height:64px;border-radius:50%;background:#2F43E8;display:flex;align-items:center;justify-content:center;color:#fff;font-size:32px">1</div>
    <h3 style="font-family:'Rubik', sans-serif;font-size:36px;color:#12163A">Выживание</h3>
    <p style="font-size:28px;color:#4A5170;line-height:1.4">Если у живой клетки <b>●</b> есть <b>2 или 3</b> соседа, она остаётся жить в следующем поколении.</p>
  </div>
  <div style="flex:1;background:#2F43E8;border-radius:24px;padding:36px;display:flex;flex-direction:column;gap:18px;color:#fff">
    <div style="width:64px;height:64px;border-radius:50%;background:#A9B5FF;display:flex;align-items:center;justify-content:center;color:#12163A;font-size:32px">2</div>
    <h3 style="font-family:'Rubik', sans-serif;font-size:36px;color:#fff">Рождение</h3>
    <p style="font-size:28px;color:#E4E8FF;line-height:1.4">Если вокруг пустой клетки <b>·</b> ровно <b>3</b> живые точки, в ней зарождается новая жизнь: <b>●</b>!</p>
  </div>
  <div style="flex:1;background:#fff;border-radius:24px;padding:36px;border:1px solid #D5DAF0;display:flex;flex-direction:column;gap:18px">
    <div style="width:64px;height:64px;border-radius:50%;background:#2F43E8;display:flex;align-items:center;justify-content:center;color:#fff;font-size:32px">3</div>
    <h3 style="font-family:'Rubik', sans-serif;font-size:36px;color:#12163A">Гибель</h3>
    <p style="font-size:28px;color:#4A5170;line-height:1.4">Меньше 2 соседей — смерть от одиночества. Больше 3 соседей — гибель от перенаселения.</p>
  </div>
</div>
""", "Объясняем наглядно правила Конвея для детей: простые 3 правила рождают удивительные живые узоры!", idx))
    idx += 1

    # =========================================================================
    # УРОК 8: ФИНАЛЬНЫЙ ХАКАТОН
    # =========================================================================
    frames.append(frame("l8-divider", "#12163A", """
<div style="display:flex;gap:80px;align-items:center;height:100%">
  <div style="width:360px"><p style="font-size:32px;font-weight:700;letter-spacing:4px;color:#A9B5FF">УРОК</p><p style="font-family:'Rubik', sans-serif;font-size:300px;font-weight:700;line-height:0.9;color:#A9B5FF">8</p></div>
  <div style="flex:1;display:flex;flex-direction:column;gap:24px">
    <h2 style="font-family:'Rubik', sans-serif;font-size:72px;font-weight:700;color:#FFFFFF">Финальный хакатон: релиз и таблица рекордов</h2>
    <p style="font-size:34px;color:#D5DAFF">Главное меню, сохранение рекордов в файл и презентация игр</p>
    <div style="display:flex;flex-direction:column;gap:12px;margin-top:10px">
      <div style="background:#1B2050;padding:16px 24px;border-radius:14px;font-size:28px;color:#fff">🎯 Задачи: «Главное консольное меню», «Запись рекорда в records.txt»</div>
      <div style="background:#2F43E8;padding:16px 24px;border-radius:14px;font-size:28px;color:#fff">🎮 Финал: Создание собственной игры с Залом Славы (highscores.txt)</div>
      <div style="background:#1B2050;padding:16px 24px;border-radius:14px;font-size:28px;color:#fff">🌟 Прокачка: Фирменный ASCII-титул и рамка игры</div>
    </div>
  </div>
</div>
""", "Урок 8: кульминация курса, финализация проектов.", idx))
    idx += 1

    # =========================================================================
    # ФИНАЛ И НАГРАЖДЕНИЕ
    # =========================================================================
    frames.append(frame("final", "#12163A", """
<div style="display:flex;flex-direction:column;gap:36px;align-items:center;justify-content:center;height:100%;text-align:center">
  <span style="font-size:100px">🏆</span>
  <h1 style="font-family:'Rubik', sans-serif;font-size:110px;font-weight:700;color:#FFFFFF">Поздравляем разработчиков!</h1>
  <p style="font-size:42px;color:#D5DAFF;max-width:1400px">Вы прошли путь от первого print() до создания настоящих консольных 2D игр и симуляций на Python!</p>
  <div style="margin-top:20px;background:#2F43E8;padding:18px 48px;border-radius:20px;font-size:32px;color:#fff;font-weight:700">
    Защита проектов · Показ игр друг другу · Вручение дипломов 🎉
  </div>
</div>
""", "Финальное поздравление ребят и защита их игр.", idx))

    return "\n".join(frames)


def generate():
    content = HTML_HEAD + build_slides() + HTML_TAIL
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Презентация создана: {OUT_FILE} ({len(content)} байт)")


if __name__ == "__main__":
    generate()
