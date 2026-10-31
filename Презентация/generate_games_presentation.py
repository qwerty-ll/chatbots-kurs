#!/usr/bin/env python3
"""Генератор полной интерактивной презентации курса «Разработка консольных игр на Python» (8 занятий, 130+ слайдов).
Формат: 1920x1080 stage, адаптивное масштабирование, заметки докладчика (N), полноэкранный режим (F).
Каждое занятие включает:
- Разделитель с целями и таймингом
- Интерактивную разминку (вопрос в зал)
- Карточки целей урока
- Глубокие концептуальные слайды теории с аналогиями
- Разбор синтаксиса и кода построчно
- Таблицы частых ошибок с примерами и исправлением
- Интерактивные викторины для голосования класса (А, Б, В)
- Слайды 3 тренировочных задач из обучающей панели
- Полноформатную миссию сборки главной игры
- Полный образцовый код игры с подсветкой
- Задачу прокачки игры со звёздочкой 🌟
- Слайд рефлексии и подведения итогов
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
<title>Разработка консольных игр на Python · Полный курс (8 занятий)</title>
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
  td, th { border: 1px solid #D5DAF0; padding: .55em .8em; vertical-align: top; text-align: left; }
  th { font-weight: 700; }
  .notes { display: none; }
  #notes { position: fixed; left: 0; right: 0; bottom: 0; max-height: 42vh; overflow: auto; padding: 20px 30px;
            background: rgba(11,14,38,.96); color: #E8EBFF; font: 20px/1.5 'Nunito Sans', Arial, sans-serif; white-space: pre-wrap;
            border-top: 2px solid #2F43E8; display: none; z-index: 100; box-shadow: 0 -10px 40px rgba(0,0,0,0.5); }
  #notes b { color: #A9B5FF; }
  #hud { position: fixed; right: 18px; bottom: 14px; color: #9AA3E0; font: 16px 'Nunito Sans', Arial, sans-serif; z-index: 101;
          background: rgba(11,14,38,.75); padding: 6px 14px; border-radius: 12px; user-select: none; border: 1px solid #2F3876; }
  #hint { position: fixed; left: 50%; top: 16px; transform: translateX(-50%); color: #E8EBFF; font: 16px 'Nunito Sans', Arial, sans-serif;
           background: rgba(47,67,232,.95); padding: 10px 22px; border-radius: 14px; z-index: 102; transition: opacity .6s; font-weight: 600; box-shadow: 0 4px 20px rgba(47,67,232,0.4); }
  .code-box { background: #161A3C; color: #70E2FF; font-family: 'JetBrains Mono', monospace; font-size: 26px; line-height: 1.48; padding: 26px 30px; border-radius: 20px; border: 1px solid #2F3876; box-shadow: 0 8px 32px rgba(0,0,0,0.25); }
  .code-box .kw { color: #FF7BE5; font-weight: 600; }
  .code-box .fn { color: #5CE1E6; font-weight: 600; }
  .code-box .str { color: #FFDE59; }
  .code-box .num { color: #FF9B71; }
  .code-box .com { color: #7E8BBB; font-style: italic; }
  .code-box .op { color: #FFFFFF; font-weight: 600; }
  .code-box .hi { background: rgba(47,67,232,0.35); padding: 2px 6px; border-radius: 6px; }
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
<div id="hint">← → листать · F полный экран · N заметки спикера · Пробел / Клик — вперёд</div>
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

SLIDES = []
_INDEX = 1


def add_slide(slide_id: str, bg: str, content: str, notes: str = "", footer_text: str = "Разработка консольных игр на Python · 8 занятий") -> None:
    global _INDEX
    is_dark = bg.startswith("#1") or bg.startswith("#2")
    fg = "#FFFFFF" if is_dark else "#12163A"
    ft_color = "#9AA3E0" if is_dark else "#5A6284"
    html = f"""<div class="frame" data-id="{slide_id}"><div class="stage">
<section class="slide" id="{slide_id}" data-transition="fade" style="background:{bg};color:{fg};font-family:'Nunito Sans', Arial, sans-serif;padding:96px 128px 128px;display:flex;flex-direction:column;gap:32px;">
{content}
<p style="position:absolute;left:128px;bottom:48px;font-size:22px;color:{ft_color};font-weight:600;">{footer_text}</p>
<p style="position:absolute;right:128px;bottom:48px;font-size:22px;color:{ft_color};font-weight:700;">{_INDEX}</p>
</section></div>
<div class="notes">{notes}</div></div>"""
    SLIDES.append(html)
    _INDEX += 1


def header_light(tag: str, title: str) -> str:
    return f"""<div style="display:flex;flex-direction:column;gap:12px">
  <p style="font-size:24px;font-weight:700;letter-spacing:3px;text-transform:uppercase;color:#2F43E8">{tag}</p>
  <h2 style="font-family:'Rubik', Arial, sans-serif;font-size:54px;font-weight:700;line-height:1.15;color:#12163A">{title}</h2>
</div>"""


def header_dark(tag: str, title: str) -> str:
    return f"""<div style="display:flex;flex-direction:column;gap:12px">
  <p style="font-size:24px;font-weight:700;letter-spacing:3px;text-transform:uppercase;color:#A9B5FF">{tag}</p>
  <h2 style="font-family:'Rubik', Arial, sans-serif;font-size:54px;font-weight:700;line-height:1.15;color:#FFFFFF">{title}</h2>
</div>"""


def make_divider(slide_id: str, num: int, title: str, subtitle: str, train_tasks: str, game_title: str, bonus_title: str, notes: str) -> None:
    content = f"""
<div style="display:flex;gap:70px;align-items:center;height:100%">
  <div style="width:340px;display:flex;flex-direction:column;align-items:center;justify-content:center;border-right:3px solid #2F3876;padding-right:40px">
    <p style="font-size:30px;font-weight:700;letter-spacing:4px;color:#A9B5FF">ЗАНЯТИЕ</p>
    <p style="font-family:'Rubik', sans-serif;font-size:280px;font-weight:700;line-height:0.85;color:#FFFFFF">{num}</p>
  </div>
  <div style="flex:1;display:flex;flex-direction:column;gap:24px">
    <span style="font-size:26px;font-weight:700;letter-spacing:3px;text-transform:uppercase;color:#A9B5FF;background:#1B2050;padding:8px 18px;border-radius:12px;display:inline-block;width:fit-content">Курс разработки игр</span>
    <h1 style="font-family:'Rubik', sans-serif;font-size:68px;font-weight:700;color:#FFFFFF;line-height:1.1">{title}</h1>
    <p style="font-size:34px;color:#D5DAFF;line-height:1.35">{subtitle}</p>
    <div style="display:flex;flex-direction:column;gap:14px;margin-top:10px">
      <div style="background:#1B2050;border:1px solid #2F3876;padding:16px 24px;border-radius:16px;font-size:26px;color:#FFFFFF;display:flex;align-items:center;gap:16px">
        <span style="font-size:32px">🎯</span> <span><b>Тренировка:</b> {train_tasks}</span>
      </div>
      <div style="background:#2F43E8;padding:16px 24px;border-radius:16px;font-size:26px;color:#FFFFFF;display:flex;align-items:center;gap:16px;box-shadow:0 6px 24px rgba(47,67,232,0.4)">
        <span style="font-size:32px">🎮</span> <span><b>Сборка игры:</b> {game_title}</span>
      </div>
      <div style="background:#1B2050;border:1px solid #FFDE59;padding:16px 24px;border-radius:16px;font-size:26px;color:#FFDE59;display:flex;align-items:center;gap:16px">
        <span style="font-size:32px">🌟</span> <span><b>Прокачка игры:</b> {bonus_title}</span>
      </div>
    </div>
  </div>
</div>
"""
    add_slide(slide_id, "#12163A", content, notes)


def make_warmup(slide_id: str, num: int, question: str, scenario: str, options: list[str], prompt: str, notes: str) -> None:
    opts_html = "".join([f"""<div style="display:flex;gap:20px;align-items:center;background:#FFFFFF;border:1px solid #E1E4F0;border-radius:20px;padding:20px 28px;box-shadow:0 4px 16px rgba(18,22,58,.04)">
  <div style="width:48px;height:48px;border-radius:50%;background:#E4E8FF;display:flex;align-items:center;justify-content:center;font-weight:700;color:#2F43E8;font-size:24px">{chr(1040 + i)}</div>
  <p style="font-size:28px;color:#12163A;line-height:1.3">{opt}</p>
</div>""" for i, opt in enumerate(options)])
    content = f"""
{header_light(f"Разминка · Урок {num}", question)}
<div style="display:flex;gap:40px;align-items:stretch;margin-top:10px">
  <div style="flex:1;background:#2F43E8;border-radius:24px;padding:36px;color:#FFFFFF;display:flex;flex-direction:column;gap:20px;justify-content:center">
    <span style="font-size:64px">🤔</span>
    <h3 style="font-family:'Rubik', sans-serif;font-size:38px;font-weight:600">Игровая ситуация:</h3>
    <p style="font-size:28px;line-height:1.45;color:#E4E8FF">{scenario}</p>
    <div style="margin-top:10px;background:rgba(255,255,255,0.15);padding:14px 20px;border-radius:14px;font-size:24px">
      💡 <b>Вопрос залу:</b> {prompt}
    </div>
  </div>
  <div style="flex:1.2;display:flex;flex-direction:column;gap:16px;justify-content:center">
    {opts_html}
  </div>
</div>
"""
    add_slide(slide_id, "#F6F7FB", content, notes)


def make_learn(slide_id: str, num: int, items: list[tuple[str, str, str]], notes: str) -> None:
    cards = []
    for icon, title, desc in items:
        cards.append(f"""<div style="flex:1;background:#FFFFFF;border:1px solid #E1E4F0;border-radius:24px;padding:34px;box-shadow:0 6px 24px rgba(18,22,58,.06);display:flex;flex-direction:column;gap:18px">
  <div style="width:72px;height:72px;border-radius:20px;background:#2F43E8;display:flex;align-items:center;justify-content:center;font-size:36px;color:#FFFFFF">{icon}</div>
  <h3 style="font-family:'Rubik', sans-serif;font-size:34px;font-weight:600;color:#12163A;line-height:1.2">{title}</h3>
  <p style="font-size:26px;color:#4A5170;line-height:1.45">{desc}</p>
</div>""")
    cards_html = "\n".join(cards)
    content = f"""
{header_light(f"Цели занятия · Урок {num}", "Что мы освоим и соберём сегодня")}
<div style="display:flex;gap:30px;align-items:stretch;margin-top:16px">
  {cards_html}
</div>
"""
    add_slide(slide_id, "#F6F7FB", content, notes)


def make_code_explainer(slide_id: str, tag: str, title: str, code_html: str, explanations: list[tuple[str, str]], notes: str) -> None:
    exp_cards = []
    for marker, text in explanations:
        exp_cards.append(f"""<div style="display:flex;gap:20px;align-items:flex-start;background:#FFFFFF;border:1px solid #E1E4F0;border-radius:20px;padding:22px 26px;box-shadow:0 4px 16px rgba(18,22,58,.04)">
  <span style="background:#2F43E8;color:#FFFFFF;padding:4px 14px;border-radius:10px;font-weight:700;font-size:22px;white-space:nowrap">{marker}</span>
  <p style="font-size:26px;line-height:1.4;color:#12163A">{text}</p>
</div>""")
    exp_html = "\n".join(exp_cards)
    content = f"""
{header_light(tag, title)}
<div style="display:flex;gap:36px;align-items:flex-start;margin-top:10px">
  <div style="flex:1.15;display:flex;flex-direction:column;gap:14px">
    <div class="code-box">
{code_html}
    </div>
  </div>
  <div style="flex:1;display:flex;flex-direction:column;gap:16px">
    {exp_html}
  </div>
</div>
"""
    add_slide(slide_id, "#F6F7FB", content, notes)


def make_errors_table(slide_id: str, num: int, title: str, rows: list[tuple[str, str, str, str]], notes: str) -> None:
    tr_html = []
    for err, meaning, sample, fix in rows:
        tr_html.append(f"""<tr>
  <td style="font-family:'JetBrains Mono', monospace;font-weight:700;color:#D8283B;font-size:24px;background:#FFF0F2">{err}</td>
  <td style="font-size:24px;color:#12163A;background:#FFFFFF">{meaning}</td>
  <td style="font-family:'JetBrains Mono', monospace;font-size:22px;color:#941E2F;background:#FFF8F9">{sample}</td>
  <td style="font-family:'JetBrains Mono', monospace;font-size:22px;color:#1B7C3F;background:#F0FAF3;font-weight:600">{fix}</td>
</tr>""")
    tbody = "\n".join(tr_html)
    content = f"""
{header_light(f"Разбор граблей · Урок {num}", title)}
<div style="margin-top:10px;border-radius:20px;overflow:hidden;border:1px solid #D5DAF0;box-shadow:0 6px 24px rgba(18,22,58,.06)">
  <table>
    <thead>
      <tr style="background:#2F43E8;color:#FFFFFF;font-size:26px">
        <th style="width:20%;color:#FFFFFF">Ошибка</th>
        <th style="width:28%;color:#FFFFFF">Что означает</th>
        <th style="width:26%;color:#FFFFFF">Где ошиблись</th>
        <th style="width:26%;color:#FFFFFF">Как исправить</th>
      </tr>
    </thead>
    <tbody>
      {tbody}
    </tbody>
  </table>
</div>
"""
    add_slide(slide_id, "#F6F7FB", content, notes)


def make_quiz(slide_id: str, num: int, question: str, options: list[str], correct_idx: int, explanation: str, notes: str) -> None:
    cards = []
    letters = ["А", "Б", "В", "Г"]
    for i, opt in enumerate(options):
        is_cor = (i == correct_idx)
        border = "2px solid #2F43E8" if is_cor else "1px solid #E1E4F0"
        tag_bg = "#2F43E8" if is_cor else "#E4E8FF"
        tag_fg = "#FFFFFF" if is_cor else "#2F43E8"
        cards.append(f"""<div style="display:flex;gap:26px;align-items:center;background:#FFFFFF;border:{border};border-radius:22px;padding:22px 32px;box-shadow:0 4px 20px rgba(18,22,58,.05)">
  <div style="width:64px;height:64px;border-radius:50%;background:{tag_bg};color:{tag_fg};display:flex;align-items:center;justify-content:center;font-family:'Rubik', sans-serif;font-size:36px;font-weight:700">{letters[i]}</div>
  <p style="font-size:30px;color:#12163A;flex:1;line-height:1.3">{opt}</p>
</div>""")
    cards_html = "\n".join(cards)
    content = f"""
{header_light(f"Проверь себя · Урок {num}", question)}
<div style="display:flex;flex-direction:column;gap:18px;margin-top:14px">
  {cards_html}
</div>
<div style="margin-top:10px;background:#EBF2FF;border-left:6px solid #2F43E8;padding:16px 24px;border-radius:12px;font-size:24px;color:#12163A">
  💡 <b>Подсказка преподавателю:</b> {explanation}
</div>
"""
    add_slide(slide_id, "#F6F7FB", content, notes)


def make_train_tasks(slide_id: str, num: int, tasks: list[tuple[str, str, str, str]], notes: str) -> None:
    cards = []
    for code, title, goal, example in tasks:
        cards.append(f"""<div style="flex:1;background:#FFFFFF;border:1px solid #E1E4F0;border-radius:24px;padding:30px;box-shadow:0 6px 24px rgba(18,22,58,.06);display:flex;flex-direction:column;gap:16px">
  <div style="display:flex;align-items:center;justify-content:space-between">
    <span style="background:#2F43E8;color:#FFFFFF;padding:6px 14px;border-radius:10px;font-weight:700;font-size:22px">{code}</span>
    <span style="color:#7E8BBB;font-size:22px;font-weight:600">5–7 мин</span>
  </div>
  <h3 style="font-family:'Rubik', sans-serif;font-size:32px;font-weight:600;color:#12163A;line-height:1.2">{title}</h3>
  <p style="font-size:24px;color:#4A5170;line-height:1.4;flex:1">{goal}</p>
  <div style="background:#F0F3FF;border:1px solid #D5DAFF;padding:14px 18px;border-radius:14px;font-family:'JetBrains Mono', monospace;font-size:20px;color:#2F43E8">
    {example}
  </div>
</div>""")
    cards_html = "\n".join(cards)
    content = f"""
{header_light(f"Практика в панели · Урок {num}", "Блок тренировочных задач (Кирпичики игры)")}
<div style="display:flex;gap:28px;align-items:stretch;margin-top:14px">
  {cards_html}
</div>
"""
    add_slide(slide_id, "#F6F7FB", content, notes)


def make_mission(slide_id: str, num: int, title: str, desc: str, rules: list[str], time_min: int, notes: str) -> None:
    rules_html = "".join([f"""<div style="display:flex;gap:20px;align-items:flex-start">
  <div style="width:36px;height:36px;border-radius:10px;border:3px solid #7EE0A5;flex:none;margin-top:4px"></div>
  <p style="font-size:30px;line-height:1.35;color:#FFFFFF">{r}</p>
</div>""" for r in rules])
    content = f"""
<div style="display:flex;flex-direction:column;gap:24px;height:100%">
  <div style="display:flex;justify-content:space-between;align-items:center">
    <span style="background:#1B2050;color:#A9B5FF;padding:8px 20px;border-radius:12px;font-size:26px;font-weight:700;letter-spacing:3px;text-transform:uppercase">Главная Миссия · Урок {num}</span>
    <span style="background:#FFDE59;color:#12163A;padding:8px 22px;border-radius:12px;font-size:26px;font-weight:800">⏱ {time_min} минут</span>
  </div>
  <h1 style="font-family:'Rubik', sans-serif;font-size:74px;font-weight:700;color:#FFFFFF;line-height:1.1">{title}</h1>
  <p style="font-size:34px;color:#D5DAFF;line-height:1.4">{desc}</p>
  <div style="background:#1B2050;border:2px solid #2F3876;border-radius:24px;padding:36px;display:flex;flex-direction:column;gap:22px;margin-top:10px">
    <h3 style="font-family:'Rubik', sans-serif;font-size:34px;color:#7EE0A5">Чек-лист разработчика:</h3>
    {rules_html}
  </div>
</div>
"""
    add_slide(slide_id, "#12163A", content, notes)


def make_full_code(slide_id: str, num: int, title: str, filename: str, code_html: str, takeaways: list[str], notes: str) -> None:
    take_html = "".join([f"""<div style="background:#1B2050;border-left:5px solid #2F43E8;padding:16px 20px;border-radius:12px;color:#FFFFFF;font-size:24px;line-height:1.35">
  {t}
</div>""" for t in takeaways])
    content = f"""
<div style="display:flex;flex-direction:column;gap:18px">
  <div style="display:flex;justify-content:space-between;align-items:center">
    <span style="color:#A9B5FF;font-size:24px;font-weight:700;letter-spacing:3px;text-transform:uppercase">Эталонная сборка · Урок {num}</span>
    <span style="background:#2F3876;color:#70E2FF;padding:6px 16px;border-radius:10px;font-family:'JetBrains Mono', monospace;font-size:22px">файл: {filename}</span>
  </div>
  <h2 style="font-family:'Rubik', sans-serif;font-size:52px;font-weight:700;color:#FFFFFF">{title}</h2>
</div>
<div style="display:flex;gap:36px;align-items:flex-start;margin-top:8px">
  <div style="flex:1.25">
    <div class="code-box">
{code_html}
    </div>
  </div>
  <div style="flex:0.95;display:flex;flex-direction:column;gap:14px">
    <h3 style="font-family:'Rubik', sans-serif;font-size:32px;color:#A9B5FF">Ключевые приёмы:</h3>
    {take_html}
  </div>
</div>
"""
    add_slide(slide_id, "#12163A", content, notes)


def make_bonus(slide_id: str, num: int, title: str, challenge: str, preview: str, hints: list[str], notes: str) -> None:
    hints_html = "".join([f"""<li style="font-size:26px;color:#4A5170;line-height:1.45">{h}</li>""" for h in hints])
    content = f"""
{header_light(f"Прокачка игры со звёздочкой 🌟 · Урок {num}", title)}
<div style="display:flex;gap:40px;align-items:stretch;margin-top:14px">
  <div style="flex:1.1;background:#FFFFFF;border:2px solid #FFDE59;border-radius:24px;padding:36px;box-shadow:0 8px 30px rgba(255,222,89,0.15);display:flex;flex-direction:column;gap:20px">
    <div style="display:flex;align-items:center;gap:14px">
      <span style="font-size:48px">🌟</span>
      <h3 style="font-family:'Rubik', sans-serif;font-size:36px;color:#12163A">Бонусное задание:</h3>
    </div>
    <p style="font-size:28px;color:#12163A;line-height:1.45;font-weight:600">{challenge}</p>
    <div style="margin-top:8px">
      <h4 style="font-size:26px;color:#2F43E8;margin-bottom:10px">Как подойти к решению:</h4>
      <ul style="padding-left:26px;display:flex;flex-direction:column;gap:10px">
        {hints_html}
      </ul>
    </div>
  </div>
  <div style="flex:1;display:flex;flex-direction:column;gap:16px">
    <h3 style="font-family:'Rubik', sans-serif;font-size:32px;color:#12163A">Как выглядит в консоли:</h3>
    <div class="code-box" style="background:#0F132E;border:1px solid #FFDE59;flex:1">
{preview}
    </div>
  </div>
</div>
"""
    add_slide(slide_id, "#F6F7FB", content, notes)


def make_reflection(slide_id: str, num: int, questions: list[str], notes: str) -> None:
    q_cards = []
    for i, q in enumerate(questions):
        q_cards.append(f"""<div style="display:flex;gap:24px;align-items:center;background:#FFFFFF;border:1px solid #E1E4F0;border-radius:22px;padding:26px 32px;box-shadow:0 4px 18px rgba(18,22,58,.05)">
  <div style="width:58px;height:58px;border-radius:50%;background:#2F43E8;color:#FFFFFF;display:flex;align-items:center;justify-content:center;font-family:'Rubik', sans-serif;font-size:32px;font-weight:700">{i+1}</div>
  <p style="font-size:30px;color:#12163A;flex:1;line-height:1.35">{q}</p>
</div>""")
    cards_html = "\n".join(q_cards)
    content = f"""
{header_light(f"Рефлексия и финал · Урок {num}", "Подводим итоги занятия")}
<div style="display:flex;flex-direction:column;gap:18px;margin-top:16px">
  {cards_html}
</div>
<div style="margin-top:20px;background:#2F43E8;border-radius:20px;padding:22px 36px;color:#FFFFFF;font-size:28px;display:flex;align-items:center;gap:20px">
  <span style="font-size:42px">🎉</span>
  <span><b>Отличная работа!</b> Сохраните свой код, нажмите «Проверить» в панели и покажите игру соседу!</span>
</div>
"""
    add_slide(slide_id, "#F6F7FB", content, notes)


# =============================================================================
# ГЕНЕРАЦИЯ ВСЕХ 130+ СЛАЙДОВ
# =============================================================================

def build_all_slides():
    # -------------------------------------------------------------------------
    # БЛОК 0: ВВОДНЫЕ СЛАЙДЫ КУРСА (4 слайда)
    # -------------------------------------------------------------------------
    add_slide("cover", "#12163A", """
<p style="font-size:28px;font-weight:700;letter-spacing:4px;text-transform:uppercase;color:#A9B5FF">Программа дополнительного образования · 8 занятий</p>
<h1 style="font-family:'Rubik', Arial, sans-serif;font-size:112px;font-weight:700;line-height:1.05;color:#FFFFFF">Разработка консольных игр на Python</h1>
<p style="font-size:44px;line-height:1.3;color:#D5DAFF;max-width:1400px">От первых шагов в программировании до симуляций, 2D графики и Зала Славы</p>
<div style="flex:1"></div>
<div style="display:flex;gap:32px;align-items:center">
  <span style="font-size:28px;color:#A9B5FF;background:#1B2050;padding:12px 24px;border-radius:14px;border:1px solid #2F3876">🎮 8 готовых игр</span>
  <span style="font-size:28px;color:#A9B5FF;background:#1B2050;padding:12px 24px;border-radius:14px;border:1px solid #2F3876">🎯 24 задачи тренировки</span>
  <span style="font-size:28px;color:#FFDE59;background:#1B2050;padding:12px 24px;border-radius:14px;border:1px solid #FFDE59">🌟 8 прокачек со звёздочкой</span>
</div>
""", "Вступительный слайд. Приветствуем ребят, знакомимся, обозначаем амбициозную цель курса: к концу 8 урока каждый напишет 8 настоящих игр и презентует свой проект на хакатоне.")

    add_slide("course-plan", "#F6F7FB", """
<div style="display:flex;flex-direction:column;gap:14px">
  <p style="font-size:24px;font-weight:700;letter-spacing:3px;text-transform:uppercase;color:#2F43E8">Карта приключения</p>
  <h2 style="font-family:'Rubik', Arial, sans-serif;font-size:56px;font-weight:700;color:#12163A">Две части нашего курса</h2>
</div>
<div style="display:flex;gap:36px;align-items:stretch;flex:1;margin-top:10px">
  <div style="flex:1;background:#FFFFFF;border:2px solid #2F43E8;border-radius:24px;padding:34px;display:flex;flex-direction:column;gap:18px;box-shadow:0 8px 30px rgba(47,67,232,0.08)">
    <div style="display:flex;align-items:center;gap:14px">
      <span style="background:#2F43E8;color:#fff;font-size:22px;font-weight:700;padding:6px 16px;border-radius:12px">ЧАСТЬ 1</span>
      <h3 style="font-family:'Rubik', sans-serif;font-size:34px;font-weight:700;color:#12163A">Основы Python и Текстовые Игры</h3>
    </div>
    <p style="font-size:24px;color:#4A5170">Занятия 1–4 · Строим фундамент логики и механик</p>
    <div style="display:flex;flex-direction:column;gap:14px;font-size:24px;color:#12163A;flex:1">
      <p>🔹 <b>Урок 1:</b> Ввод-вывод, f-строки ➔ <b>«Квест в замке»</b></p>
      <p>🔹 <b>Урок 2:</b> Числа, random, if/else ➔ <b>«Взломщик сейфа»</b></p>
      <p>🔹 <b>Урок 3:</b> Циклы while, счетчики, HP ➔ <b>«RPG-Арена»</b></p>
      <p>🔹 <b>Урок 4:</b> Списки list, choice, in ➔ <b>«Турнир стихий: КНБ»</b></p>
    </div>
  </div>
  <div style="flex:1;background:#FFFFFF;border:2px solid #2F43E8;border-radius:24px;padding:34px;display:flex;flex-direction:column;gap:18px;box-shadow:0 8px 30px rgba(47,67,232,0.08)">
    <div style="display:flex;align-items:center;gap:14px">
      <span style="background:#2F43E8;color:#fff;font-size:22px;font-weight:700;padding:6px 16px;border-radius:12px">ЧАСТЬ 2</span>
      <h3 style="font-family:'Rubik', sans-serif;font-size:34px;font-weight:700;color:#12163A">Консольная Графика и Симуляции</h3>
    </div>
    <p style="font-size:24px;color:#4A5170">Занятия 5–8 · Анимация, двумерные координаты и жизнь</p>
    <div style="display:flex;flex-direction:column;gap:14px;font-size:24px;color:#12163A;flex:1">
      <p>🔹 <b>Урок 5:</b> time.sleep, анимация ➔ <b>«Турбо-трасса 2D»</b></p>
      <p>🔹 <b>Урок 6:</b> 2D сетка, координаты, WASD ➔ <b>«Лабиринт Подземелья»</b></p>
      <p>🔹 <b>Урок 7:</b> Клеточные автоматы Конвея ➔ <b>«Игра в жизнь»</b></p>
      <p>🔹 <b>Урок 8:</b> Файлы, меню ➔ <b>Финальный Хакатон и Рекорды</b></p>
    </div>
  </div>
</div>
""", "Разбираем роадмап курса: показываем ребятам, что обучение разбито на 2 логических этапа: от текста к графике и сложным алгоритмам.")

    add_slide("pedagogy", "#12163A", """
<div style="display:flex;flex-direction:column;gap:14px">
  <p style="font-size:24px;font-weight:700;letter-spacing:3px;text-transform:uppercase;color:#A9B5FF">Как устроен каждый наш урок</p>
  <h2 style="font-family:'Rubik', Arial, sans-serif;font-size:60px;font-weight:700;color:#FFFFFF">Принцип «Кирпичики ➔ Игра ➔ Прокачка»</h2>
</div>
<div style="display:flex;gap:32px;align-items:stretch;margin-top:24px">
  <div style="flex:1;background:#1B2050;border-radius:24px;padding:36px;display:flex;flex-direction:column;gap:18px;border:1px solid #2F3876">
    <span style="font-size:52px">🎯</span>
    <h3 style="font-family:'Rubik', sans-serif;font-size:36px;color:#FFFFFF">1. Тренировка</h3>
    <p style="font-size:26px;color:#D5DAFF;line-height:1.45">3 короткие задачи на 5–7 минут. Отрабатываем один изолированный инструмент языка (ввод, счетчик или сравнение).</p>
  </div>
  <div style="flex:1;background:#2F43E8;border-radius:24px;padding:36px;display:flex;flex-direction:column;gap:18px;box-shadow:0 8px 30px rgba(47,67,232,0.4)">
    <span style="font-size:52px">🎮</span>
    <h3 style="font-family:'Rubik', sans-serif;font-size:36px;color:#FFFFFF">2. Сборка игры</h3>
    <p style="font-size:26px;color:#FFFFFF;line-height:1.45">Соединяем решённые задачи воедино! Пишем полноценную сюжетную игру, которую можно сразу запустить и пройти.</p>
  </div>
  <div style="flex:1;background:#1B2050;border-radius:24px;padding:36px;display:flex;flex-direction:column;gap:18px;border:1px solid #FFDE59">
    <span style="font-size:52px">🌟</span>
    <h3 style="font-family:'Rubik', sans-serif;font-size:36px;color:#FFDE59">3. Прокачка</h3>
    <p style="font-size:26px;color:#D5DAFF;line-height:1.45">Бонусная задача со звёздочкой для тех, кто справился раньше. Добавляем супер-удары, ASCII-бары, препятствия и файлы.</p>
  </div>
</div>
""", "Важный педагогический слайд: снимаем страх перед большими программами. Мы не пишем 100 строк с чистого листа, а собираем игру как конструктор LEGO из маленьких решённых кирпичиков!")

    add_slide("rules", "#F6F7FB", """
<div style="display:flex;flex-direction:column;gap:14px">
  <p style="font-size:24px;font-weight:700;letter-spacing:3px;text-transform:uppercase;color:#2F43E8">Правила студии разработки</p>
  <h2 style="font-family:'Rubik', Arial, sans-serif;font-size:56px;font-weight:700;color:#12163A">Кодекс разработчика консольных игр</h2>
</div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:26px;margin-top:20px">
  <div style="background:#FFFFFF;border:1px solid #E1E4F0;border-radius:22px;padding:28px;display:flex;gap:20px;align-items:center;box-shadow:0 4px 18px rgba(18,22,58,.05)">
    <span style="font-size:48px">⌨️</span>
    <div><h3 style="font-size:30px;color:#12163A;font-family:'Rubik'">Кодим пальцами</h3><p style="font-size:24px;color:#4A5170">Не копипастим код вслепую — руки должны запомнить синтаксис!</p></div>
  </div>
  <div style="background:#FFFFFF;border:1px solid #E1E4F0;border-radius:22px;padding:28px;display:flex;gap:20px;align-items:center;box-shadow:0 4px 18px rgba(18,22,58,.05)">
    <span style="font-size:48px">🐞</span>
    <div><h3 style="font-size:30px;color:#12163A;font-family:'Rubik'">Ошибки — это подсказки</h3><p style="font-size:24px;color:#4A5170">Красный текст в консоли — это не приговор, а точный совет Python, где опечатка.</p></div>
  </div>
  <div style="background:#FFFFFF;border:1px solid #E1E4F0;border-radius:22px;padding:28px;display:flex;gap:20px;align-items:center;box-shadow:0 4px 18px rgba(18,22,58,.05)">
    <span style="font-size:48px">🤝</span>
    <div><h3 style="font-size:30px;color:#12163A;font-family:'Rubik'">Помогаем товарищу</h3><p style="font-size:24px;color:#4A5170">Решил раньше всех? Помоги соседу найти баг, но не нажимай клавиши за него!</p></div>
  </div>
  <div style="background:#FFFFFF;border:1px solid #E1E4F0;border-radius:22px;padding:28px;display:flex;gap:20px;align-items:center;box-shadow:0 4px 18px rgba(18,22,58,.05)">
    <span style="font-size:48px">🚀</span>
    <div><h3 style="font-size:30px;color:#12163A;font-family:'Rubik'">Тестируем сразу</h3><p style="font-size:24px;color:#4A5170">Написал 2 строчки — запусти! Проверь, как ведет себя игра.</p></div>
  </div>
</div>
""", "Договариваемся о правилах поведения на занятиях: кодинг своими руками, взаимопомощь и позитивное отношение к ошибкам компилятора.")

    # -------------------------------------------------------------------------
    # РАЗДЕЛИТЕЛЬ ЧАСТИ 1 (1 слайд)
    # -------------------------------------------------------------------------
    add_slide("part1-div", "#2F43E8", """
<div style="display:flex;flex-direction:column;gap:20px;justify-content:center;height:100%">
  <span style="font-size:30px;font-weight:700;letter-spacing:4px;text-transform:uppercase;color:#A9B5FF">Блок занятий 1–4</span>
  <h1 style="font-family:'Rubik', sans-serif;font-size:96px;font-weight:700;color:#FFFFFF;line-height:1.05">Часть 1: Основы Python и Текстовые Игры</h1>
  <p style="font-size:40px;color:#E4E8FF;max-width:1400px">Изучаем язык программирования с нуля: команды вывода, диалог с игроком, случайности, боевые циклы и инвентарь.</p>
</div>
""", "Переход к Части 1 курса.")

    # -------------------------------------------------------------------------
    # УРОК 1: ВВОД, ВЫВОД И КВЕСТ В ЗАМКЕ (15 слайдов)
    # -------------------------------------------------------------------------
    make_divider("l1-divider", 1, "Ввод-вывод, f-строки и «Квест в замке»", "Осваиваем диалог программы с игроком и первое сюжетное ветвление", "«Привет, Игрок!», «Карточка героя», «Рюкзак»", "Игра «Квест в замке» (золото или дракон)", "🌟 Квест: Выбор оружия (меч или лук)", "Урок 1: объявляем тему, план и первую готовую игру.")
    
    make_warmup("l1-warm", 1, "Что делает игра при запуске?", "Вы нажимаете кнопку Play в любимой игре. Что происходит в первую секунду на экране?", ["Игра сразу бросает в бой без слов", "Игра выводит логотип, здоровается и ждёт действия игрока", "Игра закрывает окно и удаляется"], "Как программа понимает, что пользователь хочет начать?", "Разминка: активизируем ребят, обсуждаем, что любой игре нужен способ показать текст и получить ответ игрока.")
    
    make_learn("l1-learn", 1, [
        ("🖥", "Консоль и print()", "Узнаем, как выводить текст, сюжетные реплики и диалоги на экран терминала."),
        ("💬", "input() и переменные", "Научимся спрашивать имя игрока и сохранять его выбор в память компьютера."),
        ("⚔️", "f-строки и ветвление", "Подставим имя героя в сообщения и сделаем две двери в замке через if/else.")
    ], "Разбираем 3 ключевые цели первого занятия.")

    make_code_explainer("l1-print", "Команда вывода", "print() — как программа говорит с нами",
"""<span class="com"># Вывод простого текста</span>
<span class="fn">print</span>(<span class="str">"Добро пожаловать в Замок!"</span>)

<span class="com"># Пустая строка для красоты</span>
<span class="fn">print</span>()

<span class="com"># Несколько реплик подряд</span>
<span class="fn">print</span>(<span class="str">"Перед вами две тяжелые двери..."</span>)
<span class="fn">print</span>(<span class="str">"Куда вы пойдете?"</span>)""",
        [
            ("print(...)", "Главная команда языка Python для вывода информации на экран."),
            ("Кавычки \" \"", "Весь текст (строки) обязательно оборачивается в двойные или одинарные кавычки."),
            ("Скобки ( )", "В круглых скобках мы передаём то, что нужно напечатать.")
        ],
        "Подробно разбираем анатомию вызова функции print: скобки, кавычки и перенос строки."
    )

    make_code_explainer("l1-vars", "Память игры", "Переменные — коробочки с названиями",
"""<span class="com"># Записываем данные в переменные</span>
hero_name = <span class="str">"Артур"</span>
hero_hp = <span class="num">100</span>
hero_weapon = <span class="str">"Стальной меч"</span>

<span class="com"># Читаем данные из переменной</span>
<span class="fn">print</span>(hero_name)
<span class="fn">print</span>(hero_weapon)""",
        [
            ("Знак =", "Оператор присваивания! Он берёт значение справа и кладёт в переменную слева."),
            ("Имя переменной", "Пишется латиницей без пробелов, с маленькой буквы (например, hero_hp)."),
            ("Хранилище", "Переменная может хранить текст, число или результат выбора игрока.")
        ],
        "Объясняем концепцию переменных как подписанных коробок в оперативной памяти."
    )

    make_code_explainer("l1-input", "Слушаем игрока", "input() — ожидание ответа игрока",
"""<span class="com"># Спрашиваем имя и ждём нажатия Enter</span>
name = <span class="fn">input</span>(<span class="str">"Как зовут твоего героя? "</span>)

<span class="com"># Спрашиваем выбор пути</span>
door = <span class="fn">input</span>(<span class="str">"Какую дверь откроешь? (1 или 2): "</span>)

<span class="fn">print</span>(<span class="str">"Принято! Твой выбор сохранён."</span>)""",
        [
            ("input(...)", "Останавливает программу и ждёт, пока пользователь напечатает текст и нажмёт Enter."),
            ("Текст подсказки", "Внутри скобок пишем вопрос игроку — курсор встанет сразу после него."),
            ("Сохранение", "Обязательно сохраняем ответ в переменную: name = input(...)")
        ],
        "Показываем разницу между print и input: input умеет не только говорить, но и слушать!"
    )

    make_code_explainer("l1-fstr", "Магия Python", "f-строки — вставляем данные прямо в текст",
"""name = <span class="str">"Элиза"</span>
score = <span class="num">50</span>

<span class="com"># Старый сложный способ (легко ошибиться):</span>
<span class="com"># print("Привет, " + name + "! Очки: " + str(score))</span>

<span class="com"># Современный удобный способ через f-строку:</span>
<span class="fn">print</span>(<span class="str">f"Привет, {name}! У тебя {score} очков."</span>)
<span class="fn">print</span>(<span class="str">f"Рыцарь {name} входит в темный тронный зал."</span>)""",
        [
            ("Буква f перед кавычкой", "Обозначает форматную строку: Python знает, что внутри есть фигурные скобки."),
            ("Фигурные скобки { }", "Внутри скобок пишется имя переменной — Python сам подставит её значение!"),
            ("Читаемость", "Текст читается как обычное предложение, без плюсов и запятых.")
        ],
        "f-строки — фирменная фича Python 3.6+. Объясняем, почему это проще конкатенации строк через плюс."
    )

    make_errors_table("l1-errors", 1, "Типичные ошибки первого кода", [
        ("SyntaxError: EOL", "Забыли закрыть кавычку в строке", "print(\"Привет)", "print(\"Привет\")"),
        ("SyntaxError: unexpected EOF", "Забыли закрыть круглую скобку", "name = input(\"Имя: \"", "name = input(\"Имя: \")"),
        ("NameError: name 'x' is not defined", "Опечатка в имени переменной", "hero = \"Маг\"\nprint(haro)", "print(hero)"),
        ("SyntaxError: invalid syntax", "Забыли двоеточие в конце if", "if door == \"1\"", "if door == \"1\":")
    ], "Разбираем самые частые грабли первых 30 минут программирования.")

    make_quiz("l1-quiz", 1, "Что выведет этот код: print(f\"Герой {name}!\"), если name = \"Робин\"?", [
        "Герой {name}!",
        "Герой Робин!",
        "Герой {Робин}!"
    ], 1, "Правильный ответ Б: f-строка заменяет фигурные скобки {name} на значение переменной «Робин».", "Опрос класса: закрепляем понимание синтаксиса f-строк.")

    make_train_tasks("l1-tasks-train", 1, [
        ("g01-01", "Привет, Игрок!", "Спросить имя игрока через input() и вывести «Привет, <имя>!»", 'input("Имя: ") -> "Привет, Робин!"'),
        ("g01-02", "Карточка героя", "Спросить имя и класс (воин/маг) и напечатать статус-карточку героя", '"Герой: Линк | Класс: Воин"'),
        ("g01-03", "Рюкзак приключенца", "Спросить 2 предмета снаряжения и вывести инвентарь через запятую", '"В рюкзаке: Факел, Меч"')
    ], "Инструкция перед самостоятельной работой: 15 минут в обучающей панели на решение первых 3 мини-задач.")

    make_code_explainer("l1-choice", "Развилка сюжета", "if и else — выбор пути в игре",
"""door = <span class="fn">input</span>(<span class="str">"Выбери дверь (1 или 2): "</span>)

<span class="kw">if</span> door == <span class="str">"1"</span>:
    <span class="fn">print</span>(<span class="str">"Ты открываешь дверь 1 и находишь сундук с золотом!"</span>)
<span class="kw">else</span>:
    <span class="fn">print</span>(<span class="str">"Из темноты двери 2 появляется огнедышащий дракон!"</span>)""",
        [
            ("if условие :", "Если условие верно — выполняется блок под if. Обязательно двоеточие в конце!"),
            ("Двойное равно ==", "Проверка на равенство. Одно равно = записывает, а два == сравнивают!"),
            ("Отступ 4 пробела", "Табуляция показывает Python, какие команды относятся к выбранной ветке.")
        ],
        "Фундаментальный слайд: отступы в 4 пробела и ветвление if / else."
    )

    make_mission("l1-mission", 1, "Игра «Квест в замке»", "Соберите сюжетную текстовую мини-игру с ветвлением и карточкой персонажа", [
        "Спросить у игрока имя его рыцаря через input()",
        "Напечатать приветствие: Рыцарь <имя> подходит к двум дверям замка.",
        "Спросить номер двери: «Какую дверь открыть? (1 или 2): »",
        "Если выбрана дверь «1»: напечатать, что герой находит сундук золота",
        "Иначе (любой другой ввод): напечатать, что за дверью спит дракон"
    ], 15, "Основная миссия урока: сборка первой игры из решённых кирпичиков.")

    make_full_code("l1-full", 1, "Полный код игры «Квест в замке»", "castle_quest.py",
"""name = <span class="fn">input</span>(<span class="str">"Имя рыцаря: "</span>)
<span class="fn">print</span>(<span class="str">f"Рыцарь {name} подходит к двум дверям замка."</span>)

door = <span class="fn">input</span>(<span class="str">"Какую дверь открыть? (1 или 2): "</span>)

<span class="kw">if</span> door == <span class="str">"1"</span>:
    <span class="fn">print</span>(<span class="str">f"{name} открывает дверь 1 и находит сундук золота!"</span>)
<span class="kw">else</span>:
    <span class="fn">print</span>(<span class="str">f"{name} открывает дверь 2, а там спит голодный дракон!"</span>)""",
        [
            "Ввод имени с сохранением в переменную name",
            "Использование f-строки для погружения в атмосферу",
            "Сравнение строки door == '1'",
            "Два альтернативных исхода сюжета"
        ],
        "Разбор эталонного кода. Просим учеников сравнить со своим решением и нажать «Проверить»."
    )

    make_bonus("l1-bonus", 1, "Выбор оружия в замке", "Добавьте выбор оружия (меч или лук) и сделайте победу над драконом зависимой от экипировки!",
"""Имя рыцаря: Артур
Выбери оружие (меч/лук): меч
Какую дверь открыть? (1 или 2): 2
Дракон атакует! Но Артур с оружием
'меч' побеждает чудовище!""",
        [
            "Добавьте второй input() для выбора оружия: weapon = input('Оружие: ')",
            "В ветке else проверьте: if weapon == 'меч': победа, иначе дракон сильнее",
            "Используйте вложенное условие if или оператор and"
        ],
        "Задача для тех ребят, кто быстро справился с основной миссией."
    )

    make_reflection("l1-reflect", 1, [
        "Какая команда выводит текст на экран, а какая ждет ответа игрока?",
        "Чем отличается знак «=» от двойного знака «==»?",
        "Зачем в начале f-строки пишется маленькая английская буква f?"
    ], "Короткий опрос на закрепление материала перед перерывом.")

    # -------------------------------------------------------------------------
    # УРОК 2: ЧИСЛА, RANDOM И ВЗЛОМЩИК СЕЙФА (15 слайдов)
    # -------------------------------------------------------------------------
    make_divider("l2-divider", 2, "Числа, случайность и «Взломщик сейфа»", "Модуль random, преобразование типов int() и каскад условий elif", "«Бросок кубика», «Сравнение чисел», «Секретный пин-код»", "Игра «Взломщик сейфа» (подсказки «больше» и «меньше»)", "🌟 Взломщик: Ограничение в 3 попытки до тревоги", "Урок 2: переходим от чистого текста к математике и случайным величинам.")

    make_warmup("l2-warm", 2, "Как игры создают непредсказуемость?", "Почему в Minecraft каждый раз генерируется новый мир, а в RPG выпадает разный лут?", ["Программист вручную написал миллиард вариантов", "Компьютер бросает виртуальный кубик через модуль random", "Компьютер угадывает мысли игрока"], "Как называется элемент случайности в играх?", "Разминка о ГСЧ (генераторе случайных чисел) и его роли в геймдеве.")

    make_learn("l2-learn", 2, [
        ("🎲", "Модуль random", "Научимся генерировать случайные числа от 1 до 6 для бросков кубика и лута."),
        ("🔢", "Преобразование int()", "Поймём разницу между текстом \"42\" и настоящим числом 42."),
        ("🔐", "Сравнения и elif", "Соберем игру на угадывание тайного кода с подсказками больше/меньше.")
    ], "Три ключевые темы второго занятия.")

    make_code_explainer("l2-types", "Строки против Чисел", "Почему \"5\" + \"5\" равно \"55\", а не 10?",
"""<span class="com"># Текстовые строки (str):</span>
a = <span class="str">"5"</span>
b = <span class="str">"5"</span>
<span class="fn">print</span>(a + b)  <span class="com"># Напечатает "55" (склеивание текста!)</span>

<span class="com"># Настоящие целые числа (int):</span>
x = <span class="fn">int</span>(a)
y = <span class="fn">int</span>(b)
<span class="fn">print</span>(x + y)  <span class="com"># Напечатает 10 (математическое сложение!)</span>""",
        [
            ("input() всегда дает текст", "Все, что игрок вводит с клавиатуры, Python считает строкой!"),
            ("Функция int(...)", "Превращает текст из цифр в целое число: guess = int(input(\"Код: \"))"),
            ("Опасность букв", "Если передать в int() буквы, например int(\"привет\"), программа вызовет ValueError.")
        ],
        "Критически важный слайд: объясняем типичную ловушку новичков со строками и числами."
    )

    make_code_explainer("l2-random", "Виртуальный кубик", "Подключаем модуль random",
"""<span class="kw">import</span> random

<span class="com"># Бросок шестигранного кубика (от 1 до 6 включительно)</span>
cube = random.<span class="fn">randint</span>(<span class="num">1</span>, <span class="num">6</span>)
<span class="fn">print</span>(<span class="str">f"На кубике выпало: {cube}"</span>)

<span class="com"># Генерация секретного кода от 1 до 100</span>
secret = random.<span class="fn">randint</span>(<span class="num">1</span>, <span class="num">100</span>)
<span class="fn">print</span>(<span class="str">"Секретный код сейфа загадан!"</span>)""",
        [
            ("import random", "Импортируем встроенный модуль генерации случайных чисел. Пишется в начале файла."),
            ("random.randint(a, b)", "Возвращает случайное целое число от a до b включительно."),
            ("Каждый запуск уникален", "При каждом новом запуске код будет генерировать новое число.")
        ],
        "Объясняем import библиотек и синтаксис функции randint."
    )

    make_code_explainer("l2-compare", "Язык сравнений", "Операторы сравнения в Python",
"""hp = <span class="num">75</span>
boss_hp = <span class="num">100</span>

<span class="fn">print</span>(hp == <span class="num">75</span>)   <span class="com"># True (равно)</span>
<span class="fn">print</span>(hp != boss_hp) <span class="com"># True (не равно)</span>
<span class="fn">print</span>(hp &gt; <span class="num">50</span>)    <span class="com"># True (больше)</span>
<span class="fn">print</span>(hp &lt; <span class="num">50</span>)    <span class="com"># False (меньше)</span>
<span class="fn">print</span>(hp &gt;= <span class="num">75</span>)   <span class="com"># True (больше либо равно)</span>""",
        [
            ("== (два знака)", "Проверка точного равенства: 5 == 5 -> True."),
            ("!= (восклицательный)", "Проверка неравенства: 5 != 3 -> True."),
            ("Логический ответ", "Результат любого сравнения — это всегда либо True (правда), либо False (ложь).")
        ],
        "Шесть базовых операторов сравнения, которые используются во всех игровых условиях."
    )

    make_code_explainer("l2-elif", "Три исхода ситуации", "Конструкция if / elif / else",
"""code = <span class="num">42</span>
guess = <span class="fn">int</span>(<span class="fn">input</span>(<span class="str">"Введи код: "</span>))

<span class="kw">if</span> guess == code:
    <span class="fn">print</span>(<span class="str">"Сейф открыт! Сокровища ваши!"</span>)
<span class="kw">elif</span> guess &lt; code:
    <span class="fn">print</span>(<span class="str">"Код больше! Подсказка грабителю..."</span>)
<span class="kw">else</span>:
    <span class="fn">print</span>(<span class="str">"Код меньше! Подсказка грабителю..."</span>)""",
        [
            ("if (первая проверка)", "Срабатывает, если игрок угадал код с первого раза."),
            ("elif (иначе если)", "Дополнительная проверка, если первое условие оказалось ложным."),
            ("else (во всех остальных случаях)", "Срабатывает автоматически, если ни if, ни elif не подошли.")
        ],
        "Разбираем каскадное ветвление elif. Подчёркиваем, что сработает только одна подходящая ветка."
    )

    make_errors_table("l2-errors", 2, "Ошибки работы с числами и условиями", [
        ("ValueError: invalid literal for int()", "Игрок ввёл слово вместо цифр", "int(\"привет\")", "Вводить только цифры 0-9"),
        ("TypeError: '<' not supported between str and int", "Забыли обернуть input() в int()", "\"10\" < 20", "int(input()) < 20"),
        ("SyntaxError: invalid syntax", "Написали один знак '=' в условии", "if code = 42:", "if code == 42:"),
        ("IndentationError: expected an indented block", "Забыли сделать отступ после двоеточия", "if x > 0:\nprint(x)", "if x > 0:\n    print(x)")
    ], "Разбираем TypeError и ValueError — главные ошибки при работе с числовым вводом.")

    make_quiz("l2-quiz", 2, "Что выведет код: print(type(input()))?", [
        "&lt;class 'int'&gt; (число)",
        "&lt;class 'str'&gt; (строку)",
        "&lt;class 'bool'&gt; (логический тип)"
    ], 1, "Правильный ответ Б: input() ВСЕГДА возвращает тип str (строка), даже если вы напечатали цифры 12345!", "Опрос класса: еще раз закрепляем, что input() всегда возвращает строку.")

    make_train_tasks("l2-tasks-train", 2, [
        ("g02-01", "Бросок кубика", "Импортировать random и сгенерировать бросок D6 кубика от 1 до 6", 'random.randint(1, 6) -> "Выпало: 4"'),
        ("g02-02", "Сравнение чисел", "Спросить число у игрока и вывести: Положительное / Отрицательное / Ноль", 'input() -> if > 0: ... elif < 0: ...'),
        ("g02-03", "Секретный пин-код", "Сравнить введённый пин-код с числом 777: «Доступ разрешён» или «Отказано»", 'if pin == 777: ... else: ...')
    ], "15 минут на решение 3 тренировочных задач в учебной панели.")

    make_mission("l2-mission", 2, "Игра «Взломщик сейфа»", "Соберите интерактивную игру по взлому цифрового сейфа с подсказками", [
        "Задать секретный код сейфа: code = 42 (или сгенерировать случайный)",
        "Спросить у игрока догадку с преобразованием в число: guess = int(input(\"Введи код: \"))",
        "Если guess == code: напечатать «Сейф открыт! Сокровища ваши!»",
        "Иначе если guess < code: напечатать «Код больше! Сигнализация тикает...»",
        "Иначе (если guess > code): напечатать «Код меньше! Сигнализация тикает...»"
    ], 15, "Основная миссия второго урока: сборка полноценной мини-игры.")

    make_full_code("l2-full", 2, "Полный код игры «Взломщик сейфа»", "safe_cracker.py",
"""code = <span class="num">42</span>
guess = <span class="fn">int</span>(<span class="fn">input</span>(<span class="str">"Введи код: "</span>))

<span class="kw">if</span> guess == code:
    <span class="fn">print</span>(<span class="str">"Сейф открыт! Сокровища ваши!"</span>)
<span class="kw">elif</span> guess &lt; code:
    <span class="fn">print</span>(<span class="str">"Код больше! Сигнализация тикает..."</span>)
<span class="kw">else</span>:
    <span class="fn">print</span>(<span class="str">"Код меньше! Сигнализация тикает..."</span>)""",
        [
            "Переменная code хранит числовое значение",
            "Обязательный int(input()) для корректного сравнения",
            "Каскад условий ==, <, > для трех возможных исходов",
            "Подсказка игроку для следующей попытки"
        ],
        "Разбираем эталонное решение задачи g02-04."
    )

    make_bonus("l2-bonus", 2, "Три попытки до тревоги 🚨", "Дайте игроку ровно 3 попытки угадать код без циклов — последовательными проверками!",
"""Попытка 1: 50
Код меньше!
Попытка 2: 30
Код больше!
Попытка 3: 7
Взлом успешен! Сокровища ваши!""",
        [
            "Заведите флаг успешного взлома: guessed = False",
            "Запрашивайте следующую попытку только если код ещё не найден: if not guessed:",
            "В самом конце: if not guessed: print('Сигнализация сработала!')"
        ],
        "Прокачка игры: пошаговый алгоритм трёх попыток через ветвления if / elif / else без циклов."
    )

    make_reflection("l2-reflect", 2, [
        "Зачем оборачивать input() в функцию int() при работе с числами?",
        "Какая функция из модуля random генерирует случайное целое число?",
        "Чем конструкция elif отличается от обычного повторного if?"
    ], "Подведение итогов занятия 2.")

    # -------------------------------------------------------------------------
    # УРОК 3: ЦИКЛЫ WHILE, HP И RPG-АРЕНА (15 слайдов)
    # -------------------------------------------------------------------------
    make_divider("l3-divider", 3, "Циклы while, счетчики и «RPG-Арена»", "Пошаговый игровой цикл, очки здоровья (HP), урон (-=) и лечение (+=)", "«Обратный отсчёт», «Сборщик монет», «Урон манекену»", "Игра «RPG-Арена: Битва с Драконом» (атака / лечение)", "🌟 Арена: Текстовая полоска здоровья [■■■■■□□□□□]", "Урок 3: осваиваем сердце игровой индустрии — Game Loop (Игровой цикл).")

    make_warmup("l3-warm", 3, "Почему игра не завершается после одного удара?", "В любой игре бой длится много раундов, пока босс или герой не потеряют все очки жизни. Как это устроено в коде?", ["Программист 100 раз скопировал одну строчку кода", "Код крутится в цикле, пока здоровье персонажей больше нуля", "Компьютер перезагружается после каждого раунда"], "Какое ключевое слово отвечает за повторение?", "Разминка о цикле while: объясняем необходимость повторения действий.")

    make_learn("l3-learn", 3, [
        ("🔄", "Цикл while", "Узнаем, как заставить программу повторять действия до выполнения условия."),
        ("❤️", "Очки HP и счетчики", "Научимся изменять здоровье и инвентарь с помощью hp -= 10 и hp += 5."),
        ("🐉", "RPG-Арена с боссом", "Напишем настоящий пошаговый бой героя против огнедышащего дракона.")
    ], "Цели третьего занятия.")

    make_code_explainer("l3-while", "Анатомия цикла", "while — делай, пока условие истинно",
"""count = <span class="num">3</span>

<span class="kw">while</span> count &gt; <span class="num">0</span>:
    <span class="fn">print</span>(<span class="str">f"До старта боя: {count}..."</span>)
    count -= <span class="num">1</span>  <span class="com"># Уменьшаем счетчик на 1</span>

<span class="fn">print</span>(<span class="str">"РАУНД НАЧАЛСЯ! В БОЙ!"</span>)""",
        [
            ("while условие :", "Проверяет условие перед каждым повторением. Если True — тело цикла выполняется."),
            ("Тело цикла (отступ)", "Все строки с отступом в 4 пробела будут повторяться."),
            ("Изменение переменной", "Обязательно меняем переменную внутри цикла, иначе он никогда не закончится!")
        ],
        "Подробный разбор механики цикла while и условия выхода."
    )

    make_code_explainer("l3-counters", "Игровая арифметика", "Операторы += и -= в действии",
"""hero_hp = <span class="num">100</span>
dragon_hp = <span class="num">150</span>

<span class="com"># Герой атакует:</span>
dragon_hp -= <span class="num">25</span>  <span class="com"># То же самое, что: dragon_hp = dragon_hp - 25</span>
<span class="fn">print</span>(<span class="str">f"Здоровье дракона: {dragon_hp}"</span>)

<span class="com"># Герой пьёт зелье исцеления:</span>
hero_hp += <span class="num">15</span>    <span class="com"># То же самое, что: hero_hp = hero_hp + 15</span>
<span class="fn">print</span>(<span class="str">f"Здоровье героя: {hero_hp}"</span>)""",
        [
            ("Снижение HP (-=)", "Быстрый способ отнять урон от переменной здоровья: hp -= damage."),
            ("Лечение (+=)", "Быстрый способ прибавить здоровье или собранные золотые монеты: coins += 1."),
            ("Компактность", "Код получается чистым, понятным и профессиональным.")
        ],
        "Операторы сокращенного присваивания += и -=."
    )

    make_code_explainer("l3-break", "Экстренный выход", "Оператор break — остановка битвы",
"""<span class="kw">while</span> <span class="kw">True</span>:
    action = <span class="fn">input</span>(<span class="str">"Твой приказ (атака / бегство): "</span>)
    <span class="kw">if</span> action == <span class="str">"бегство"</span>:
        <span class="fn">print</span>(<span class="str">"Герой трусливо сбегает с поля боя!"</span>)
        <span class="kw">break</span>  <span class="com"># Немедленно выходим из цикла!</span>
    <span class="fn">print</span>(<span class="str">"Удар нанесён!"</span>)

<span class="fn">print</span>(<span class="str">"Битва завершена."</span>)""",
        [
            ("while True:", "Бесконечный цикл — часто используется в игровых меню и циклах раундов."),
            ("break", "Мгновенно прерывает цикл и передаёт управление первой строке после него."),
            ("Контроль", "Позволяет выйти из игры при победе, поражении или выборе выхода в меню.")
        ],
        "Разбираем оператор break как инструмент контроля за бесконечным циклом."
    )

    make_errors_table("l3-errors", 3, "Ошибки в циклах и счетчиках", [
        ("Бесконечный цикл (зависание)", "Забыли изменить переменную счетчика внутри while", "while x > 0:\n    print(x)", "Добавить x -= 1 внутри цикла"),
        ("Цикл не запустился ни разу", "Начальное условие сразу было False", "x = 0\nwhile x > 5:", "Проверить стартовое значение x"),
        ("UnboundLocalError", "Использовали переменную до её создания", "hp -= 10", "Сначала объявить: hp = 100"),
        ("SyntaxError: 'break' outside loop", "Написали break вне тела цикла", "if hp <= 0:\n    break", "break можно писать ТОЛЬКО внутри цикла!")
    ], "Разбираем ловушку бесконечного цикла и комбинацию клавиш Ctrl+C для аварийной остановки.")

    make_quiz("l3-quiz", 3, "Сколько раз напечатается дракон при: hp = 6; while hp > 0: hp -= 2; print('Дракон')?", [
        "2 раза",
        "3 раза",
        "Бесконечно много раз"
    ], 1, "Правильный ответ Б: 3 раза! Сначала hp=4 (1 раз), потом hp=2 (2 раз), потом hp=0 (3 раз), затем 0 > 0 дает False и цикл завершается.", "Тест на понимание логики итераций цикла while.")

    make_train_tasks("l3-tasks-train", 3, [
        ("g03-01", "Обратный отсчёт", "Напечатать таймер от 3 до 1 через while и в конце вывести «В бой!»", '3 -> 2 -> 1 -> "В бой!"'),
        ("g03-02", "Сборщик монет", "В цикле спрашивать монеты, пока сумма не достигнет 10 золотых", 'coins += int(input()) -> "Собрано: 10!"'),
        ("g03-03", "Урон манекену", "У манекена 30 HP. Каждый раунд отнимать 10 HP, пока HP > 0", 'dummy_hp -= 10 -> "Манекен повержен!"')
    ], "15 минут на решение трех тренировочных задач в учебной панели.")

    make_mission("l3-mission", 3, "Игра «RPG-Арена: Битва с Драконом»", "Соберите пошаговый дуэльный симулятор героя против грозного босса", [
        "Задать здоровье: hero_hp = 20, dragon_hp = 30",
        "Запустить игровой цикл: while hero_hp > 0 and dragon_hp > 0:",
        "Спросить действие игрока: «Твой ход (атака/лечение): »",
        "Если «атака»: отнять у дракона 15 HP и напечатать лог урона",
        "Если «лечение»: прибавить герою 5 HP и напечатать лог исцеления",
        "Если дракон еще жив (dragon_hp > 0): дракон атакует в ответ на 10 HP!",
        "После цикла объявить победу героя или дракона"
    ], 20, "Основная миссия Урока 3: сборка пошагового файтинга с балансом здоровья.")

    make_full_code("l3-full", 3, "Полный код игры «RPG-Арена»", "dragon_arena.py",
"""hero_hp = <span class="num">20</span>
dragon_hp = <span class="num">30</span>

<span class="kw">while</span> hero_hp &gt; <span class="num">0</span> <span class="kw">and</span> dragon_hp &gt; <span class="num">0</span>:
    act = <span class="fn">input</span>(<span class="str">"Твой ход (атака/лечение): "</span>)
    <span class="kw">if</span> act == <span class="str">"атака"</span>:
        dragon_hp -= <span class="num">15</span>
        <span class="fn">print</span>(<span class="str">"Герой нанёс 15 урона дракону!"</span>)
    <span class="kw">elif</span> act == <span class="str">"лечение"</span>:
        hero_hp += <span class="num">5</span>
        <span class="fn">print</span>(<span class="str">"Герой выпил зелье и восстановил 5 HP!"</span>)
    
    <span class="kw">if</span> dragon_hp &gt; <span class="num">0</span>:
        hero_hp -= <span class="num">10</span>
        <span class="fn">print</span>(<span class="str">"Дракон дышит огнём и наносит 10 урона герою!"</span>)

<span class="kw">if</span> hero_hp &gt; <span class="num">0</span>:
    <span class="fn">print</span>(<span class="str">"Победа! Дракон повержен, королевство спасено!"</span>)
<span class="kw">else</span>:
    <span class="fn">print</span>(<span class="str">"Поражение! Герой пал в битве..."</span>)""",
        [
            "Условие цикла while hero_hp > 0 and dragon_hp > 0",
            "Выбор игроком тактики (удар или отхил)",
            "Ответный удар босса только если он еще не погиб",
            "Финальная проверка победителя после выхода из боя"
        ],
        "Разбираем образцовую архитектуру пошагового боя."
    )

    make_bonus("l3-bonus", 3, "Графическая шкала здоровья 📊", "Добавьте визуальный индикатор HP в консоли: [■■■■■□□□□□]!",
"""Раунд боя!
Герой:  [■■■■■■■■□□] 80 HP
Дракон: [■■■■□□□□□□] 40 HP
Твой ход (атака/лечение): """,
        [
            "Используйте умножение символов: bars = hero_hp // 10",
            "Сформируйте строку: \"■\" * bars + \"□\" * (10 - bars)",
            "Печатайте шкалу перед каждым вводом команды игрока"
        ],
        "Бонусная задача со звёздочкой: создание красивой консольной псевдографики."
    )

    make_reflection("l3-reflect", 3, [
        "Когда завершается цикл while hero_hp > 0 and dragon_hp > 0?",
        "Чем отличается hero_hp -= 15 от hero_hp = -15?",
        "Что делает оператор break внутри цикла?"
    ], "Рефлексия по итогам создания боевой RPG-системы.")

    # -------------------------------------------------------------------------
    # УРОК 4: СПИСКИ, RANDOM.CHOICE И ТУРНИР СТИХИЙ (15 слайдов)
    # -------------------------------------------------------------------------
    make_divider("l4-divider", 4, "Списки, случайный выбор и «Турнир стихий»", "Списки [...], индексы с 0, методы append() и len(), оператор in", "«Отряд героев», «Случайное событие», «Проверка заклинания»", "Игра «Турнир стихий: Камень-Ножницы-Бумага» против ИИ", "🌟 Турнир: Журнал раундов и статистика побед", "Урок 4: завершаем Часть 1 курса изучением коллекций и соревновательного ИИ.")

    make_warmup("l4-warm", 4, "Как хранить инвентарь или колоду карт?", "Представьте, что у персонажа в рюкзаке 20 разных предметов. Неужели придется создавать 20 отдельных переменных item1, item2, item3...?", ["Да, программисты вручную пишут 100 переменных", "Нет, в языках есть списки (массивы) для хранения коллекций", "Инвентарь невозможно запрограммировать в консоли"], "Как называется тип данных для списка предметов?", "Разминка о списках: демонстрируем неэффективность отдельных переменных и силу списков.")

    make_learn("l4-learn", 4, [
        ("📋", "Списки (list)", "Узнаем, как объединять предметы в квадратные скобки: ['меч', 'лук', 'щит']."),
        ("🎯", "Индексация с нуля", "Поймём, почему программисты всегда начинают счёт с 0, а не с 1."),
        ("🤖", "Случайный выбор ИИ", "Соберём соревновательную игру «Камень-Ножницы-Бумага» против компьютерного бота.")
    ], "Цели четвертого занятия.")

    make_code_explainer("l4-list", "Коллекции предметов", "Списки в квадратных скобках [ ]",
"""<span class="com"># Список оружия героя</span>
weapons = [<span class="str">"Меч"</span>, <span class="str">"Лук"</span>, <span class="str">"Посох"</span>]

<span class="com"># Список очков за раунды</span>
scores = [<span class="num">100</span>, <span class="num">250</span>, <span class="num">500</span>]

<span class="fn">print</span>(weapons)
<span class="fn">print</span>(<span class="str">f"Всего оружия в арсенале: {len(weapons)}"</span>)""",
        [
            ("Квадратные скобки [ ]", "Обозначают создание списка в Python. Элементы перечисляются через запятую."),
            ("Разнородные данные", "В списке можно хранить строки, числа и любые другие объекты."),
            ("Функция len(...)", "Возвращает длину списка (количество элементов внутри него).")
        ],
        "Введение в тип данных list: синтаксис скобок и функция len."
    )

    make_code_explainer("l4-indexing", "Счёт с нуля", "Индексы: почему первый элемент [0]?",
"""heroes = [<span class="str">"Рыцарь"</span>, <span class="str">"Маг"</span>, <span class="str">"Лучник"</span>]
<span class="com"># Индексы:    0         1        2</span>

<span class="fn">print</span>(heroes[<span class="num">0</span>])  <span class="com"># Напечатает "Рыцарь"</span>
<span class="fn">print</span>(heroes[<span class="num">1</span>])  <span class="com"># Напечатает "Маг"</span>
<span class="fn">print</span>(heroes[<span class="num">2</span>])  <span class="com"># Напечатает "Лучник"</span>

<span class="com"># Замена элемента:</span>
heroes[<span class="num">0</span>] = <span class="str">"Паладин"</span>
<span class="fn">print</span>(heroes[<span class="num">0</span>])  <span class="com"># Теперь там "Паладин"!</span>""",
        [
            ("Индекс [0]", "Первый элемент списка ВСЕГДА имеет индекс 0! Второй — индекс 1."),
            ("Квадратные скобки выбора", "heroes[0] означает «достать элемент под номером 0 из списка heroes»."),
            ("Мутабельность", "Списки можно менять на лету: заменять элементы, прокачивать оружие.")
        ],
        "Разбираем индексацию с нуля — классический концепт информатики."
    )

    make_code_explainer("l4-methods", "Методы списков", ".append() и оператор проверки in",
"""backpack = [<span class="str">"Факел"</span>, <span class="str">"Веревка"</span>]

<span class="com"># Добавляем найденный лут в конец списка</span>
backpack.<span class="fn">append</span>(<span class="str">"Зелье маны"</span>)
<span class="fn">print</span>(backpack)  <span class="com"># ['Факел', 'Веревка', 'Зелье маны']</span>

<span class="com"># Проверяем наличие предмета в рюкзаке</span>
<span class="kw">if</span> <span class="str">"Зелье маны"</span> <span class="kw">in</span> backpack:
    <span class="fn">print</span>(<span class="str">"У вас есть зелье для заклинания!"</span>)
<span class="kw">else</span>:
    <span class="fn">print</span>(<span class="str">"Зелья нет, магия заблокирована!"</span>)""",
        [
            (".append(item)", "Добавляет новый элемент в самый конец существующего списка."),
            ("Оператор in", "Проверяет, содержится ли элемент внутри списка. Возвращает True или False."),
            ("Инвентарь в играх", "Базовая механика для любого RPG инвентаря или колоды карт.")
        ],
        "Метод append и оператор in — фундамент работы с коллекциями."
    )

    make_code_explainer("l4-choice", "Ход противника", "random.choice — случайный выбор из списка",
"""<span class="kw">import</span> random

moves = [<span class="str">"камень"</span>, <span class="str">"ножницы"</span>, <span class="str">"бумага"</span>]

<span class="com"># Бот выбирает случайный жест из доступных</span>
bot_move = random.<span class="fn">choice</span>(moves)

<span class="fn">print</span>(<span class="str">f"ИИ выбрал: {bot_move}"</span>)""",
        [
            ("random.choice(items)", "Выбирает один случайный элемент из переданного списка."),
            ("Игровой ИИ", "Идеально подходит для выбора действия врага, генерации случайного лута или реплик NPC."),
            ("Честный рандом", "Каждый элемент списка имеет равные шансы быть выбранным.")
        ],
        "random.choice: простой способ вдохнуть непредсказуемость в поведение противника."
    )

    make_errors_table("l4-errors", 4, "Ошибки при работе со списками", [
        ("IndexError: list index out of range", "Попытка обратиться по несуществующему индексу", "items = [\"а\", \"б\"]\nprint(items[5])", "Использовать индекс от 0 до len(items)-1"),
        ("AttributeError: 'list' object has no attribute 'add'", "Перепутали имя метода добавления", "items.add(\"щит\")", "Использовать items.append(\"щит\")"),
        ("TypeError: 'list' object is not callable", "Поставили круглые скобки вместо квадратных", "items(0)", "Использовать квадратные: items[0]"),
        ("SyntaxError: invalid syntax", "Забыли запятую между элементами списка", "[\"лук\" \"стрелы\"]", "[\"лук\", \"стрелы\"]")
    ], "Разбираем главную ошибку IndexError: выход за границы массива.")

    make_quiz("l4-quiz", 4, "Что вернет len([\"меч\", \"лук\", \"щит\"][0])?", [
        "3 (длина списка)",
        "3 (длина слова 'меч')",
        "1 (первый элемент)"
    ], 1, "Правильный ответ Б: 3! Сначала берется элемент [0] — это строка 'меч', а длина слова 'меч' равна 3 буквам!", "Интересный вопрос на логику цепочки вызовов.")

    make_train_tasks("l4-tasks-train", 4, [
        ("g04-01", "Отряд героев", "Создать список героев, напечатать первого [0] и последнего [-1]", '["Воин", "Маг", "Лучник"]'),
        ("g04-02", "Случайное событие", "Случайный выбор из списка событий пути через random.choice()", '["Засада", "Сундук", "Таверна"]'),
        ("g04-03", "Проверка заклинания", "Проверить через оператор in, есть ли введенное заклинание в книге магии", 'if spell in spellbook: ...')
    ], "15 минут на решение трех тренировочных задач в учебной панели.")

    make_mission("l4-mission", 4, "Игра «Турнир стихий: КНБ»", "Соберите турнир против компьютерного соперника по правилам Камень-Ножницы-Бумага", [
        "Задать выбор противника: comp = \"ножницы\" (или random.choice)",
        "Спросить ход игрока: user = input(\"Твой ход (камень/ножницы/бумага): \")",
        "Если user == comp: напечатать «Ничья! Оба выбрали ножницы»",
        "Иначе если user == \"камень\": напечатать «Победа! Камень ломает ножницы»",
        "Иначе если user == \"бумага\": напечатать «Поражение! Ножницы режут бумагу»"
    ], 15, "Основная миссия четвертого урока: сборка турнирной дуэли.")

    make_full_code("l4-full", 4, "Полный код игры «Турнир стихий»", "element_battle.py",
"""comp = <span class="str">"ножницы"</span>
user = <span class="fn">input</span>(<span class="str">"Твой ход (камень/ножницы/бумага): "</span>)

<span class="kw">if</span> user == comp:
    <span class="fn">print</span>(<span class="str">"Ничья! Оба выбрали ножницы"</span>)
<span class="kw">elif</span> user == <span class="str">"камень"</span>:
    <span class="fn">print</span>(<span class="str">"Победа! Камень ломает ножницы"</span>)
<span class="kw">elif</span> user == <span class="str">"бумага"</span>:
    <span class="fn">print</span>(<span class="str">"Поражение! Ножницы режут бумагу"</span>)
<span class="kw">else</span>:
    <span class="fn">print</span>(<span class="str">"Неизвестный жест! Раунд отменён."</span>)""",
        [
            "Фиксация хода противника или выбор через random.choice",
            "Чтение выбора игрока через input()",
            "Полный перебор исходов игры Камень-Ножницы-Бумага",
            "Защита от некорректного ввода пользователя"
        ],
        "Разбираем логическую таблицу побед и поражений классической игры.")

    make_bonus("l4-bonus", 4, "Журнал раундов 📜", "Ведите историю всех раундов турнира и распечатайте финальный лог матча!",
"""Раунд 1: Игрок(камень) vs Бот(ножницы) -> Победа!
Раунд 2: Игрок(бумага) vs Бот(ножницы) -> Поражение!
Всего сыграно раундов: 2
История сохранена в списке history!""",
        [
            "Создайте пустой список до цикла: history = []",
            "После каждого раунда добавляйте результат: history.append(f'Раунд: {user} vs {comp}')",
            "В конце матча распечатайте весь список построчно"
        ],
        "Бонусная задача со звёздочкой: практическое применение метода append в цикле."
    )

    make_reflection("l4-reflect", 4, [
        "С какого числа начинается нумерация элементов в списках Python?",
        "Какая функция возвращает общее количество элементов в списке?",
        "Какой метод добавляет новый элемент в самый конец списка?"
    ], "Подводим итоги Части 1 курса: поздравляем ребят с освоением базы Python!")

    # -------------------------------------------------------------------------
    # РАЗДЕЛИТЕЛЬ ЧАСТИ 2 (1 слайд)
    # -------------------------------------------------------------------------
    add_slide("part2-div", "#2F43E8", """
<div style="display:flex;flex-direction:column;gap:20px;justify-content:center;height:100%">
  <span style="font-size:30px;font-weight:700;letter-spacing:4px;text-transform:uppercase;color:#A9B5FF">Блок занятий 5–8</span>
  <h1 style="font-family:'Rubik', sans-serif;font-size:92px;font-weight:700;color:#FFFFFF;line-height:1.05">Часть 2: Консольная Графика, Сетки и Симуляции</h1>
  <p style="font-size:40px;color:#E4E8FF;max-width:1400px">Переходим от статического текста к динамике: кадры анимации, тайминги time.sleep, двумерные координаты WASD, симуляция «Игра в жизнь» и сохранение рекордов в файл!</p>
</div>
""", "Переход к Части 2 курса.")

    # -------------------------------------------------------------------------
    # УРОК 5: КОНСОЛЬНАЯ АНИМАЦИЯ И ТУРБО-ТРАССА 2D (15 слайдов)
    # -------------------------------------------------------------------------
    make_divider("l5-divider", 5, "Консольная анимация и «Турбо-трасса 2D»", "Задержка time.sleep, покадровая отрисовка, умножение строк и руление", "«Бегущий спортсмен», «Индикатор загрузки», «Полоса трассы»", "Игра «Турбо-трасса 2D» (руление машиной 🏎 по 5 полосам)", "🌟 Турбо-трасса: Препятствия 🚧 и проверка аварий", "Урок 5: выходим в графическую динамику.")

    make_warmup("l5-warm", 5, "Что такое FPS и как создается иллюзия движения?", "Как на плоском экране статичные картинки превращаются в живой бег или гонку?", ["Экран сам по себе волшебный", "Глаз видит быструю смену неподвижных кадров (24–60 раз в секунду)", "Картинка физически растягивается внутри монитора"], "Как сделать паузу между кадрами в Python?", "Разминка об анимации: принцип мультфильма и покадровой перерисовки.")

    make_learn("l5-learn", 5, [
        ("⏱", "Модуль time и sleep()", "Научимся ставить программу на паузу: time.sleep(0.2) для плавной анимации."),
        ("🏎", "Умножение строк", "Освоим технику отрисовки дорожки: '.' * pos + '🏎' + '.' * (w - pos)."),
        ("🎮", "Управление клавишами", "Соберем игру с рулением гоночной машиной клавишами A (влево) и D (вправо).")
    ], "Цели пятого занятия.")

    make_code_explainer("l5-time", "Остановка времени", "time.sleep() — сердце любой анимации",
"""<span class="kw">import</span> time

<span class="fn">print</span>(<span class="str">"3..."</span>)
time.<span class="fn">sleep</span>(<span class="num">1.0</span>)  <span class="com"># Пауза ровно 1 секунду</span>

<span class="fn">print</span>(<span class="str">"2..."</span>)
time.<span class="fn">sleep</span>(<span class="num">1.0</span>)

<span class="fn">print</span>(<span class="str">"1..."</span>)
time.<span class="fn">sleep</span>(<span class="num">1.0</span>)

<span class="fn">print</span>(<span class="str">"СТАРТ ГОНКИ! 🏁"</span>)""",
        [
            ("import time", "Подключает стандартную библиотеку Python для работы со временем."),
            ("time.sleep(секунды)", "Приостанавливает выполнение программы на указанное дробное число секунд (например, 0.25)."),
            ("Кадровая частота", "Если делать паузу 0.1 секунды — получится 10 кадров в секунду.")
        ],
        "Разбираем вызов time.sleep и концепцию временных задержек."
    )

    make_code_explainer("l5-string-math", "Математика символов", "Умножение строк в Python",
"""<span class="com"># Умножаем символ на число:</span>
line = <span class="str">"="</span> * <span class="num">20</span>
<span class="fn">print</span>(line)  <span class="com"># Напечатает: ====================</span>

<span class="com"># Прогресс-бар загрузки:</span>
fill = <span class="str">"█"</span> * <span class="num">7</span>
empty = <span class="str">"░"</span> * <span class="num">3</span>
<span class="fn">print</span>(<span class="str">f"Загрузка: [{fill}{empty}] 70%"</span>)""",
        [
            ("Символ * N", "В Python строка, умноженная на целое число N, дублируется ровно N раз!"),
            ("Быстрая графика", "Не нужно писать циклы, чтобы нарисовать забор, рамку или полосу трассы."),
            ("Псевдографика", "Используем красивые символы Юникода (█, ░, ■, 🏎, ·) для создания UI.")
        ],
        "Умножение строк — мощный инструмент быстрой псевдографики."
    )

    make_code_explainer("l5-lane-render", "Формула трассы", "Позиция машинки на полосе дороги",
"""pos = <span class="num">2</span>  <span class="com"># Машинка на 3-й полосе (индекс 2 из 0,1,2,3,4)</span>
total_lanes = <span class="num">5</span>

<span class="com"># Левая часть обочины + Машина + Правая часть обочины:</span>
left_dots = <span class="str">"·"</span> * pos
right_dots = <span class="str">"·"</span> * (total_lanes - <span class="num">1</span> - pos)

track_line = left_dots + <span class="str">"🏎"</span> + right_dots
<span class="fn">print</span>(<span class="str">f"|{track_line}|"</span>)  <span class="com"># Напечатает: |··🏎··|</span>""",
        [
            ("Переменная pos", "Хранит текущий номер полосы машинки от 0 до 4."),
            ("Динамический расчет", "Количество точек слева равно pos. Количество справа равно 4 - pos."),
            ("Обочина дороги", "Символы | по краям создают ощущение настоящей трассы.")
        ],
        "Математическая формула отрисовки одномерной координаты объекта на полосе."
    )

    make_code_explainer("l5-controls", "Рулевое управление", "Обработка клавиш A и D с защитой границ",
"""pos = <span class="num">2</span>
cmd = <span class="fn">input</span>(<span class="str">"Руль (a - влево, d - вправо): "</span>)

<span class="kw">if</span> cmd == <span class="str">"a"</span> <span class="kw">and</span> pos &gt; <span class="num">0</span>:
    pos -= <span class="num">1</span>  <span class="com"># Сдвиг влево</span>
<span class="kw">elif</span> cmd == <span class="str">"d"</span> <span class="kw">and</span> pos &lt; <span class="num">4</span>:
    pos += <span class="num">1</span>  <span class="com"># Сдвиг вправо</span>

<span class="fn">print</span>(<span class="str">f"Новая полоса: {pos}"</span>)""",
        [
            ("and pos > 0", "Защита левой границы трассы! Не даёт машинке выехать за пределы полосы 0."),
            ("and pos < 4", "Защита правой границы трассы! Не даёт врезаться в правую стену полосы 4."),
            ("Реакция на команду", "Координата меняется на единицу за каждый ход игрока.")
        ],
        "Защита от вылета за границы трассы (clamping bounds)."
    )

    make_errors_table("l5-errors", 5, "Ошибки в анимации и управлении", [
        ("TypeError: can only concatenate str to str", "Забыли умножить строку, а прибавили число", "\"·\" + 3", "\"·\" * 3"),
        ("ValueError: negative dimensions", "Справа получилось отрицательное число точек", "\"·\" * (4 - 5)", "Проверять границы pos <= 4"),
        ("Зависание программы", "Передали слишком большое число в time.sleep", "time.sleep(100)", "Использовать 0.1 - 1.0"),
        ("Машинка уехала за экран", "Не поставили проверку границ pos > 0 and pos < 4", "pos -= 1 без проверки", "Добавить if pos > 0:")
    ], "Разбираем типичные баги отрисовки и отрицательных размеров строк.")

    make_quiz("l5-quiz", 5, "Что напечатает print(\"·\" * 3 + \"🏎\" + \"·\" * 1)?", [
        "·🏎···",
        "···🏎·",
        "····🏎"
    ], 1, "Правильный ответ Б: ровно 3 точки слева, затем машинка, затем 1 точка справа: ···🏎·", "Проверка навыка ментальной отрисовки формулы полосы.")

    make_train_tasks("l5-tasks-train", 5, [
        ("g05-01", "Бегущий спортсмен", "В цикле с задержкой time.sleep(0.1) печатать бег🏃 со смещением точек", '"·" * i + "🏃"'),
        ("g05-02", "Индикатор загрузки", "Отрисовать заполняющуюся шкалу [████░░░░] через умножение символов", '"█" * fill + "░" * empty'),
        ("g05-03", "Полоса трассы", "По заданной переменной pos=3 напечатать строку вида |···🏎·|", '"·" * pos + "🏎" + "·" * (4-pos)')
    ], "15 минут на решение трех тренировочных задач в учебной панели.")

    make_mission("l5-mission", 5, "Игра «Турбо-трасса 2D»", "Соберите динамичный симулятор гонки по 5 полосам с набором очков", [
        "Начальная полоса: pos = 2, очки: score = 0",
        "Запустить игровой цикл: while True:",
        "Спросить команду: cmd = input(\"Руль: \")",
        "Если cmd == \"стоп\": прервать цикл через break",
        "Если cmd == \"a\" and pos > 0: сдвиг влево pos -= 1",
        "Иначе если cmd == \"d\" and pos < 4: сдвиг вправо pos += 1",
        "Прибавить 10 очков (score += 10) и напечатать полосу трассы и счет"
    ], 20, "Основная миссия пятого урока: сборка гоночной консольной игры.")

    make_full_code("l5-full", 5, "Полный код игры «Турбо-трасса 2D»", "turbo_track.py",
"""pos = <span class="num">2</span>
score = <span class="num">0</span>

<span class="kw">while</span> <span class="kw">True</span>:
    cmd = <span class="fn">input</span>(<span class="str">"Руль (a - влево, d - вправо, стоп - выход): "</span>)
    <span class="kw">if</span> cmd == <span class="str">"стоп"</span>:
        <span class="kw">break</span>
    <span class="kw">if</span> cmd == <span class="str">"a"</span> <span class="kw">and</span> pos &gt; <span class="num">0</span>:
        pos -= <span class="num">1</span>
    <span class="kw">elif</span> cmd == <span class="str">"d"</span> <span class="kw">and</span> pos &lt; <span class="num">4</span>:
        pos += <span class="num">1</span>
    
    score += <span class="num">10</span>
    lane = <span class="str">"·"</span> * pos + <span class="str">"🏎"</span> + <span class="str">"·"</span> * (<span class="num">4</span> - pos)
    <span class="fn">print</span>(<span class="str">f"|{lane}| Счёт: {score}"</span>)

<span class="fn">print</span>(<span class="str">f"Гонка завершена! Финальный счёт: {score}"</span>)""",
        [
            "Управление машиной клавишами a и d",
            "Защита от вылета за левую и правую обочину",
            "Постоянное начисление очков за пройденную дистанцию",
            "Выход по кодовому слову «стоп»"
        ],
        "Разбираем эталонный код игры Турбо-трасса.")

    make_bonus("l5-bonus", 5, "Препятствия на дороге 🚧", "Сделайте случайное появление препятствий на трассе и проверку столкновения!",
"""|··🏎··| Счёт: 10
|·🚧···| Впереди препятствие на полосе 1!
Руль: d
|···🏎·| Увернулся! Счёт: 20
|···🚧·| АВАРИЯ! Столкновение с препятствием! Игра окончена.""",
        [
            "Используйте random.randint(0, 4) для генерации полосы препятствия",
            "Если pos == obstacle_pos: напечатать «АВАРИЯ!» и сделать break",
            "Игрок должен успевать перестраиваться на свободную полосу!"
        ],
        "Прокачка гонки до полноценной аркады на уклонение от аварий."
    )

    make_reflection("l5-reflect", 5, [
        "Зачем в анимации используется time.sleep?",
        "Как работает умножение строки на число в Python?",
        "Зачем нужны проверки pos > 0 и pos < 4 при рулении?"
    ], "Рефлексия по итогам 5 занятия.")

    # -------------------------------------------------------------------------
    # УРОК 6: 2D СЕТКА, КООРДИНАТЫ И ЛАБИРИНТ (15 слайдов)
    # -------------------------------------------------------------------------
    make_divider("l6-divider", 6, "2D сетка, координаты и «Лабиринт Подземелья»", "Координаты (X, Y), вложенные циклы for, управление WASD и выход", "«Печать сетки 3x3», «Игрок @ на сетке», «Перемещение WASD»", "Игра «Лабиринт Подземелья» (проведи героя к выходу)", "🌟 Подземелье: Сбор золотых сундуков на карте", "Урок 6: осваиваем двумерные игровые миры.")

    make_warmup("l6-warm", 6, "Как устроены карты в 2D играх?", "Вспомните шахматы, морской бой или карту Roguelike подземелий. Как компьютер знает, где находится персонаж?", ["Персонаж свободно летает в пустоте", "Мир поделён на клеточную сетку с координатами X и Y", "Компьютер рисует мир наугад"], "Сколько координат нужно для точки на плоскости?", "Разминка о системе 2D координат: от одномерной линии к плоскости.")

    make_learn("l6-learn", 6, [
        ("🗺", "Координаты (X, Y)", "Поймем, как ось X отвечает за горизонталь, а ось Y — за вертикаль."),
        ("🔄", "Вложенные циклы for", "Научимся сканировать и рисовать клетки поля строка за строкой."),
        ("🎮", "Классическое WASD", "Свяжем клавиши W, A, S, D с изменением координат игрока на карте.")
    ], "Цели шестого занятия.")

    make_code_explainer("l6-coords", "Карта плоскости", "Компьютерная система координат (X, Y)",
"""<span class="com"># Сетка размером 3x3:</span>
<span class="com">#       X=0   X=1   X=2</span>
<span class="com"># Y=0   (0,0) (1,0) (2,0)</span>
<span class="com"># Y=1   (0,1) (1,1) (2,1)</span>
<span class="com"># Y=2   (0,2) (1,2) (2,2)</span>

hero_x = <span class="num">0</span>  <span class="com"># Стартовая позиция</span>
hero_y = <span class="num">0</span>  <span class="com"># Верхний левый угол карты!</span>

<span class="fn">print</span>(<span class="str">f"Герой находится на клетке: ({hero_x}, {hero_y})"</span>)""",
        [
            ("Ось X (горизонталь)", "Идёт слева направо от 0 до ширины поля."),
            ("Ось Y (вертикаль)", "ВНИМАНИЕ! В компьютерной графике ось Y идёт СВЕРХУ ВНИЗ (0 — верхняя строка)!"),
            ("(0, 0) — верхний левый угол", "Стандарт во всей игровой индустрии и веб-разработке.")
        ],
        "Важное отличие экранных координат от школьной геометрии: Y направлен вниз!"
    )

    make_code_explainer("l6-nested-loops", "Художник сетки", "Вложенные циклы for для отрисовки поля",
"""width = <span class="num">3</span>
height = <span class="num">3</span>

<span class="kw">for</span> y <span class="kw">in</span> <span class="fn">range</span>(height):      <span class="com"># Идём по строкам сверху вниз</span>
    row = <span class="str">""</span>
    <span class="kw">for</span> x <span class="kw">in</span> <span class="fn">range</span>(width):   <span class="com"># Идём по клеткам слева направо</span>
        row += <span class="str">"· "</span>
    <span class="fn">print</span>(row)""",
        [
            ("Внешний цикл по Y", "Перебирает строки сверху вниз. Каждая итерация — это новая линия."),
            ("Внутренний цикл по X", "Собирает символы в текущей строке слева направо."),
            ("print(row)", "Печатает готовую сформированную строку и переводит курсор на новую строку.")
        ],
        "Разбираем работу двух вложенных циклов for."
    )

    make_code_explainer("l6-render", "Появление героя", "Условие: клетка героя или пустой пол?",
"""hero_x = <span class="num">1</span>
hero_y = <span class="num">1</span>

<span class="kw">for</span> y <span class="kw">in</span> <span class="fn">range</span>(<span class="num">3</span>):
    row = <span class="str">""</span>
    <span class="kw">for</span> x <span class="kw">in</span> <span class="fn">range</span>(<span class="num">3</span>):
        <span class="kw">if</span> x == hero_x <span class="kw">and</span> y == hero_y:
            row += <span class="str">"@ "</span>  <span class="com"># Символ героя!</span>
        <span class="kw">else</span>:
            row += <span class="str">"· "</span>  <span class="com"># Пустой пол подземелья</span>
    <span class="fn">print</span>(row)""",
        [
            ("Проверка x == hero_x and y == hero_y", "Только в одной уникальной клетке координаты совпадут с игроком!"),
            ("Символ @", "Классический символ героя в легендарных играх вроде Rogue и NetHack."),
            ("Остальные клетки", "Все остальные клетки отрисовываются точками как свободное пространство.")
        ],
        "Принцип отображения динамических игровых объектов поверх статичной карты."
    )

    make_code_explainer("l6-wasd", "Стандарт гейминга", "Логика управления клавишами WASD",
"""cmd = <span class="fn">input</span>(<span class="str">"Ход (w/a/s/d): "</span>)

<span class="kw">if</span> cmd == <span class="str">"w"</span>:
    y -= <span class="num">1</span>  <span class="com"># ВВЕРХ (уменьшаем Y!)</span>
<span class="kw">elif</span> cmd == <span class="str">"s"</span>:
    y += <span class="num">1</span>  <span class="com"># ВНИЗ (увеличиваем Y!)</span>
<span class="kw">elif</span> cmd == <span class="str">"a"</span>:
    x -= <span class="num">1</span>  <span class="com"># ВЛЕВО (уменьшаем X!)</span>
<span class="kw">elif</span> cmd == <span class="str">"d"</span>:
    x += <span class="num">1</span>  <span class="com"># ВПРАВО (увеличиваем X!)</span>""",
        [
            ("W (Вверх)", "Так как 0 наверху, движение вверх УМЕНЬШАЕТ Y: y -= 1."),
            ("S (Вниз)", "Движение вниз УВЕЛИЧИВАЕТ Y: y += 1."),
            ("A и D (Горизонталь)", "A уменьшает X (влево), D увеличивает X (вправо).")
        ],
        "Математическая привязка клавиш клавиатуры к изменению координатной сетки."
    )

    make_errors_table("l6-errors", 6, "Ошибки в координатах и 2D сетках", [
        ("Перепутали X и Y", "Движение влево меняет Y вместо X", "cmd == 'a': y -= 1", "cmd == 'a': x -= 1"),
        ("Инверсия верха и низа", "Считали, что вверх — это y += 1", "cmd == 'w': y += 1", "В экранных координатах вверх: y -= 1!"),
        ("Слипшиеся строки", "Забыли обнулять строку row = \"\" в начале цикла Y", "row накапливается", "row = \"\" внутри внешнего цикла"),
        ("Выход в бесконечность", "Забыли проверку границ сетки", "x = -1 или x = 10", "Проверять 0 <= x < width")
    ], "Разбираем типичные путаницы осей координат и отступов во вложенных циклах.")

    make_quiz("l6-quiz", 6, "Герой стоит в точке (1, 1). Игрок нажал клавишу 's'. Какими станут координаты?", [
        "(1, 0)",
        "(1, 2)",
        "(2, 1)"
    ], 1, "Правильный ответ Б: (1, 2)! Клавиша 's' означает движение вниз, то есть Y увеличивается на 1: y = 1 + 1 = 2.", "Тест на понимание экранных координат.")

    make_train_tasks("l6-tasks-train", 6, [
        ("g06-01", "Печать сетки 3x3", "Напечатать квадратное поле 3x3 из точек через вложенные циклы", 'for y in range(3): ...'),
        ("g06-02", "Игрок @ на сетке", "Отрисовать сетку 3x3, в которой на позиции (1, 1) нарисован @", 'if x==1 and y==1: "@" else "·"'),
        ("g06-03", "Перемещение WASD", "Спросить клавишу и изменить координаты x, y на единицу", 'cmd == "d" -> x += 1')
    ], "15 минут на решение трех тренировочных задач в учебной панели.")

    make_mission("l6-mission", 6, "Игра «Лабиринт Подземелья»", "Соберите игру-бродилку: проведите героя от старта (0,0) к выходу (2,2)!", [
        "Стартовая позиция героя: x = 0, y = 0",
        "Игровой цикл продолжается, пока герой не дойдет до выхода: while not (x == 2 and y == 2):",
        "Спросить у игрока направление хода: cmd = input(\"Куда идти: \")",
        "Обработать клавиши w (y-=1), s (y+=1), a (x-=1), d (x+=1)",
        "Напечатать текущие координаты героя: f\"Герой на позиции: ({x}, {y})\"",
        "После выхода из цикла напечатать: «Выход найден! Вы выбрались из подземелья!»"
    ], 20, "Основная миссия шестого урока: создание 2D приключения.")

    make_full_code("l6-full", 6, "Полный код игры «Лабиринт Подземелья»", "dungeon_maze.py",
"""x = <span class="num">0</span>
y = <span class="num">0</span>

<span class="kw">while</span> <span class="kw">not</span> (x == <span class="num">2</span> <span class="kw">and</span> y == <span class="num">2</span>):
    cmd = <span class="fn">input</span>(<span class="str">"Куда идти (w/a/s/d): "</span>)
    <span class="kw">if</span> cmd == <span class="str">"w"</span>:
        y -= <span class="num">1</span>
    <span class="kw">elif</span> cmd == <span class="str">"s"</span>:
        y += <span class="num">1</span>
    <span class="kw">elif</span> cmd == <span class="str">"a"</span>:
        x -= <span class="num">1</span>
    <span class="kw">elif</span> cmd == <span class="str">"d"</span>:
        x += <span class="num">1</span>
    <span class="fn">print</span>(<span class="str">f"Герой на позиции: ({x}, {y})"</span>)

<span class="fn">print</span>(<span class="str">"Выход найден! Вы выбрались из подземелья!"</span>)""",
        [
            "Хранение положения героя в переменных x и y",
            "Условие победы: совпадение обеих координат с выходом (2, 2)",
            "Обработка команд движения",
            "Логирование текущей позиции в консоль"
        ],
        "Разбираем эталонное решение игры Лабиринт Подземелья.")

    make_bonus("l6-bonus", 6, "Сбор сундуков с золотом 💰", "Разместите на клетке (1, 2) сундук сокровищ! При посещении клетки герой забирает 100 монет!",
"""Герой на позиции: (1, 1)
Куда идти: s
Герой на позиции: (1, 2)
ВАУ! Найден золотой сундук! +100 монет!
Куда идти: d
Герой на позиции: (2, 2)
Выход найден! Золото в кармане!""",
        [
            "Создайте координаты сундука: chest_x = 1, chest_y = 2",
            "Заведите флаг: chest_taken = False",
            "Если x == chest_x and y == chest_y and not chest_taken: начисляем золото и chest_taken = True!"
        ],
        "Прокачка подземелья: интерактивные объекты на карте."
    )

    make_reflection("l6-reflect", 6, [
        "В какую сторону света направлена ось Y в компьютерной графике?",
        "Какая клавиша уменьшает координату Y (y -= 1)?",
        "Как работает условие while not (x == 2 and y == 2)?"
    ], "Рефлексия по итогам создания 2D игры с картой.")

    # -------------------------------------------------------------------------
    # УРОК 7: ИГРА В ЖИЗНЬ ДЖОНА КОНВЕЯ (16 слайдов)
    # -------------------------------------------------------------------------
    make_divider("l7-divider", 7, "Симуляции и био-точки: «Игра в жизнь»", "Клеточный автомат Конвея, био-точки ● и ·, эволюция поколений", "«Закон жизни клетки», «Подсчёт био-точек», «Отрисовка колонии»", "Симулятор «Колония био-точек» (осциллятор-мигалка)", "🌟 Каталог био-организмов: Блок и Мигалка", "Урок 7: искусственная жизнь и клеточные автоматы.")

    make_warmup("l7-warm", 7, "Может ли игра играть сама в себя?", "Бывают ли игры без кнопок управления, где мир развивается по строгим законам природы сам по себе?", ["Нет, без игрока компьютер выключается", "Да! Это симуляторы и клеточные автоматы — мир живет по законам физики", "Игры могут работать только по нажатию мышки"], "Как называется самая известная математическая игра без игроков?", "Разминка о клеточных автоматах и концепции нулевого игрока (Zero-player game).")

    make_learn("l7-learn", 7, [
        ("🧬", "Джон Конвей (1970)", "Узнаем историю гениального математика, создавшего симуляцию жизни на шахматной доске."),
        ("⚫", "Био-точки ● и ·", "Определим живые клетки ● и пустое пространство · на двумерном поле."),
        ("🔄", "3 Закона Эволюции", "Запрограммируем правила выживания, рождения и смерти поколений клеток.")
    ], "Цели седьмого занятия.")

    add_slide("l7-history", "#F6F7FB", """
<div style="display:flex;flex-direction:column;gap:14px">
  <p style="font-size:24px;font-weight:700;letter-spacing:3px;text-transform:uppercase;color:#2F43E8">История науки</p>
  <h2 style="font-family:'Rubik', Arial, sans-serif;font-size:56px;font-weight:700;color:#12163A">Кто такой Джон Конвей и в чём его открытие?</h2>
</div>
<div style="display:flex;gap:36px;align-items:stretch;margin-top:16px">
  <div style="flex:1.1;background:#2F43E8;border-radius:24px;padding:36px;color:#FFFFFF;display:flex;flex-direction:column;gap:18px">
    <span style="font-size:60px">👨‍🔬</span>
    <h3 style="font-family:'Rubik', sans-serif;font-size:36px">Кембридж, 1970 год</h3>
    <p style="font-size:26px;line-height:1.45;color:#E4E8FF">Английский математик Джон Конвей хотел проверить: могут ли предельно простые правила породить сложное, непредсказуемое поведение живых существ?</p>
    <div style="background:rgba(255,255,255,0.15);padding:16px 20px;border-radius:14px;font-size:24px;margin-top:auto">
      ✨ <b>Результат:</b> Игра «Жизнь» стала легендой информатики и используется биологами по сей день!
    </div>
  </div>
  <div style="flex:1.2;background:#FFFFFF;border:1px solid #E1E4F0;border-radius:24px;padding:36px;box-shadow:0 6px 24px rgba(18,22,58,.06);display:flex;flex-direction:column;gap:18px">
    <h3 style="font-family:'Rubik', sans-serif;font-size:34px;color:#12163A">Принцип нулевого игрока:</h3>
    <p style="font-size:26px;color:#4A5170;line-height:1.45">В этой игре человеку не нужно нажимать кнопки геймпада. Игрок лишь задает начальное расположение био-точек, а дальше запускает часы эволюции и наблюдает за развитием цивилизации!</p>
    <div style="background:#F0F3FF;border:1px solid #D5DAFF;padding:16px 20px;border-radius:14px;font-size:24px;color:#2F43E8;font-weight:600">
      Био-точка жива: ● &nbsp;&nbsp;|&nbsp;&nbsp; Пустая среда: ·
    </div>
  </div>
</div>
""", "Исторический контекст: вдохновляем ребят историей великого математического открытия.")

    add_slide("l7-rules", "#F6F7FB", """
<div style="display:flex;flex-direction:column;gap:14px">
  <p style="font-size:24px;font-weight:700;letter-spacing:3px;text-transform:uppercase;color:#2F43E8">Моделирование жизни</p>
  <h2 style="font-family:'Rubik', Arial, sans-serif;font-size:56px;font-weight:700;color:#12163A">3 Закона Джона Конвея для био-точек</h2>
</div>
<div style="display:flex;gap:30px;align-items:stretch;margin-top:16px">
  <div style="flex:1;background:#FFFFFF;border:1px solid #D5DAF0;border-radius:24px;padding:34px;box-shadow:0 6px 24px rgba(18,22,58,.06);display:flex;flex-direction:column;gap:18px">
    <div style="width:68px;height:68px;border-radius:50%;background:#2F43E8;display:flex;align-items:center;justify-content:center;color:#fff;font-size:32px;font-weight:700">1</div>
    <h3 style="font-family:'Rubik', sans-serif;font-size:34px;color:#12163A">Выживание</h3>
    <p style="font-size:26px;color:#4A5170;line-height:1.4">Если у живой клетки <b>●</b> есть ровно <b>2 или 3</b> соседа, она остаётся жить в следующем поколении.</p>
    <div style="background:#F0FAF3;color:#1B7C3F;padding:12px;border-radius:12px;font-weight:700;font-size:22px">Жизнь продолжается</div>
  </div>
  <div style="flex:1;background:#2F43E8;border-radius:24px;padding:34px;color:#FFFFFF;box-shadow:0 8px 30px rgba(47,67,232,0.3);display:flex;flex-direction:column;gap:18px">
    <div style="width:68px;height:68px;border-radius:50%;background:#A9B5FF;display:flex;align-items:center;justify-content:center;color:#12163A;font-size:32px;font-weight:700">2</div>
    <h3 style="font-family:'Rubik', sans-serif;font-size:34px;color:#FFFFFF">Рождение</h3>
    <p style="font-size:26px;color:#E4E8FF;line-height:1.4">Если вокруг пустой клетки <b>·</b> собирается ровно <b>3</b> живые точки, в ней зарождается новая жизнь: <b>●</b>!</p>
    <div style="background:rgba(255,255,255,0.2);color:#FFFFFF;padding:12px;border-radius:12px;font-weight:700;font-size:22px">Зарождение колонии</div>
  </div>
  <div style="flex:1;background:#FFFFFF;border:1px solid #D5DAF0;border-radius:24px;padding:34px;box-shadow:0 6px 24px rgba(18,22,58,.06);display:flex;flex-direction:column;gap:18px">
    <div style="width:68px;height:68px;border-radius:50%;background:#D8283B;display:flex;align-items:center;justify-content:center;color:#fff;font-size:32px;font-weight:700">3</div>
    <h3 style="font-family:'Rubik', sans-serif;font-size:34px;color:#12163A">Гибель</h3>
    <p style="font-size:26px;color:#4A5170;line-height:1.4">Меньше 2 соседей — смерть от одиночества. Больше 3 соседей — гибель от перенаселения.</p>
    <div style="background:#FFF0F2;color:#D8283B;padding:12px;border-radius:12px;font-weight:700;font-size:22px">Клетка умирает</div>
  </div>
</div>
""", "Ключевые правила Конвея: объясняем доступным для школьников языком.")

    make_code_explainer("l7-logic", "Код биологии", "Как проверить статус клетки в Python",
"""cell = <span class="str">"●"</span>      <span class="com"># Текущее состояние (жива или мертва)</span>
neighbors = <span class="num">2</span>   <span class="com"># Сколько живых точек вокруг</span>

<span class="kw">if</span> cell == <span class="str">"●"</span> <span class="kw">and</span> (neighbors == <span class="num">2</span> <span class="kw">or</span> neighbors == <span class="num">3</span>):
    new_cell = <span class="str">"●"</span>  <span class="com"># Выжила!</span>
<span class="kw">elif</span> cell == <span class="str">"·"</span> <span class="kw">and</span> neighbors == <span class="num">3</span>:
    new_cell = <span class="str">"●"</span>  <span class="com"># Новорожденная клетка!</span>
<span class="kw">else</span>:
    new_cell = <span class="str">"·"</span>  <span class="com"># Погибла или осталась пустой</span>

<span class="fn">print</span>(<span class="str">f"Статус в новом поколении: {new_cell}"</span>)""",
        [
            ("cell == '●'", "Проверяем, жива ли клетка в текущем поколении."),
            ("neighbors == 2 or 3", "Условие стабильного выживания."),
            ("new_cell = '·'", "Во всех остальных случаях клетка погибает (одиночество или толпа).")
        ],
        "Перевод законов Конвея в чистый программный код на Python."
    )

    add_slide("l7-blinker", "#12163A", """
<div style="display:flex;flex-direction:column;gap:14px">
  <p style="font-size:24px;font-weight:700;letter-spacing:3px;text-transform:uppercase;color:#A9B5FF">Знаменитый осциллятор</p>
  <h2 style="font-family:'Rubik', Arial, sans-serif;font-size:56px;font-weight:700;color:#FFFFFF">Фигура «Мигалка» (Blinker): вечный двигатель</h2>
</div>
<div style="display:flex;gap:40px;align-items:center;margin-top:16px">
  <div style="flex:1;background:#1B2050;border:2px solid #2F3876;border-radius:24px;padding:36px;display:flex;flex-direction:column;gap:16px;text-align:center">
    <h3 style="font-family:'Rubik', sans-serif;font-size:36px;color:#A9B5FF">Поколение 1 (Горизонталь)</h3>
    <div style="font-family:'JetBrains Mono', monospace;font-size:54px;line-height:1.4;color:#70E2FF;background:#0F132E;padding:24px;border-radius:18px">
      · · ·<br>
      <span style="color:#FFDE59;font-weight:700">● ● ●</span><br>
      · · ·
    </div>
    <p style="font-size:24px;color:#D5DAFF">Три био-точки лежат в один ряд</p>
  </div>
  <div style="font-size:64px;color:#A9B5FF">➔</div>
  <div style="flex:1;background:#1B2050;border:2px solid #2F43E8;border-radius:24px;padding:36px;display:flex;flex-direction:column;gap:16px;text-align:center">
    <h3 style="font-family:'Rubik', sans-serif;font-size:36px;color:#FFFFFF">Поколение 2 (Вертикаль)</h3>
    <div style="font-family:'JetBrains Mono', monospace;font-size:54px;line-height:1.4;color:#70E2FF;background:#0F132E;padding:24px;border-radius:18px">
      · <span style="color:#FFDE59;font-weight:700">●</span> ·<br>
      · <span style="color:#FFDE59;font-weight:700">●</span> ·<br>
      · <span style="color:#FFDE59;font-weight:700">●</span> ·
    </div>
    <p style="font-size:24px;color:#D5DAFF">Точки повернулись на 90 градусов!</p>
  </div>
</div>
""", "Демонстрация Мигалки: почему горизонтальная линия из 3 точек на следующем шаге превращается в вертикальную.")

    make_errors_table("l7-errors", 7, "Ошибки при моделировании поколений", [
        ("Изменение сетки на лету", "Меняли клетки прямо во время проверки соседей", "grid[y][x] = new_cell", "Создавать отдельный список next_grid"),
        ("Ошиблись в числе соседей", "Считали саму клетку как своего соседа", "neighbors = 3 (включая себя)", "Считать только 8 окружающих клеток"),
        ("Перепутали символы", "Использовали русскую букву 'о' вместо точки '●'", "cell == 'о'", "Копировать точный символ ● и ·"),
        ("Зацикливание без шага", "Забыли ждать нажатия клавиши между поколениями", "print(gen1); print(gen2)", "Добавить input('Нажми Enter...')")
    ], "Разбираем главную архитектурную ошибку: изменение поля во время его сканирования.")

    make_quiz("l7-quiz", 7, "У пустой клетки · ровно 3 живых соседа ●. Что с ней произойдет?", [
        "Она останется пустой ·",
        "В ней родится живая био-точка ●",
        "Она взорвется"
    ], 1, "Правильный ответ Б: В ней родится новая био-точка ● по Второму Закону Джона Конвея!", "Тест на знание законов Конвея.")

    make_train_tasks("l7-tasks-train", 7, [
        ("g07-01", "Закон жизни клетки", "Написать проверку выживания клетки: при 2 или 3 соседях жива ●, иначе ·", 'if n == 2 or n == 3: "●"'),
        ("g07-02", "Счёт био-точек", "Посчитать количество символов ● в переданной строке через метод .count()", 'row.count("●") -> число'),
        ("g07-03", "Отрисовка колонии", "Распечатать матрицу из 3 строк био-точек построчно через цикл for", 'for row in grid: print(row)')
    ], "15 минут на решение трех тренировочных задач в учебной панели.")

    make_mission("l7-mission", 7, "Симулятор «Колония био-точек»", "Соберите пошаговый симулятор смены поколений знаменитого осциллятора-Мигалки", [
        "Задать 1-е поколение: gen1 = [\"· · ·\", \"● ● ●\", \"· · ·\"]",
        "Задать 2-е поколение: gen2 = [\"· ● ·\", \"· ● ·\", \"· ● ·\"]",
        "Напечатать заголовок «--- Поколение 1 ---» и вывести строки gen1",
        "Остановить программу до нажатия клавиши: input(\"Нажми Enter для шага симуляции: \")",
        "Напечатать заголовок «--- Поколение 2 ---» и вывести строки gen2",
        "Напечатать статус «Симуляция стабильна! Цикл повторяется.»"
    ], 20, "Основная миссия седьмого урока: сборка симулятора клеточного автомата.")

    make_full_code("l7-full", 7, "Полный код симулятора био-точек", "game_of_life_mini.py",
"""gen1 = [<span class="str">"· · ·"</span>, <span class="str">"● ● ●"</span>, <span class="str">"· · ·"</span>]
gen2 = [<span class="str">"· ● ·"</span>, <span class="str">"· ● ·"</span>, <span class="str">"· ● ·"</span>]

<span class="fn">print</span>(<span class="str">"--- Поколение 1 ---"</span>)
<span class="kw">for</span> r <span class="kw">in</span> gen1:
    <span class="fn">print</span>(r)

<span class="fn">input</span>(<span class="str">"Нажми Enter для шага симуляции: "</span>)

<span class="fn">print</span>(<span class="str">"--- Поколение 2 ---"</span>)
<span class="kw">for</span> r <span class="kw">in</span> gen2:
    <span class="fn">print</span>(r)

<span class="fn">print</span>(<span class="str">"Симуляция стабильна! Цикл повторяется."</span>)""",
        [
            "Моделирование поколений через списки строк",
            "Построчный вывод колонии через цикл for",
            "Интерактивная пауза через input() для изучения шага эволюции",
            "Демонстрация осциллятора 2-го периода"
        ],
        "Разбираем образцовый код симулятора Конвея.")

    make_bonus("l7-bonus", 7, "Каталог био-организмов 🦠", "Добавьте меню выбора фигуры: стабильный «Блок» (2x2) или осциллятор «Мигалка»!",
"""Выбери организм:
1 - Блок (неподвижная колония 2x2)
2 - Мигалка (осциллятор)
Твой выбор: 1
Поколение 1:      Поколение 2:
● ● ·            ● ● ·
● ● ·    ===>    ● ● ·
· · ·            · · ·
Блок абсолютно стабилен!""",
        [
            "Создайте списки для формы Блок: block = ['● ● ·', '● ● ·', '· · ·']",
            "Спросите пользователя через input(), какую форму запустить",
            "Покажите, что у Блока следующее поколение в точности равно предыдущему!"
        ],
        "Прокачка симулятора: знакомство со стабильными конфигурациями Конвея."
    )

    add_slide("l7-science", "#12163A", """
<div style="display:flex;flex-direction:column;gap:14px">
  <p style="font-size:24px;font-weight:700;letter-spacing:3px;text-transform:uppercase;color:#A9B5FF">Связь с реальным миром</p>
  <h2 style="font-family:'Rubik', Arial, sans-serif;font-size:56px;font-weight:700;color:#FFFFFF">Где применяются клеточные автоматы в науке?</h2>
</div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:26px;margin-top:20px">
  <div style="background:#1B2050;border:1px solid #2F3876;border-radius:22px;padding:30px;display:flex;gap:20px;align-items:center">
    <span style="font-size:54px">🦠</span>
    <div><h3 style="font-size:30px;color:#FFFFFF;font-family:'Rubik'">Эпидемиология</h3><p style="font-size:24px;color:#D5DAFF">Моделирование распространения вирусов и действия вакцин среди населения.</p></div>
  </div>
  <div style="background:#1B2050;border:1px solid #2F3876;border-radius:22px;padding:30px;display:flex;gap:20px;align-items:center">
    <span style="font-size:54px">🌲</span>
    <div><h3 style="font-size:30px;color:#FFFFFF;font-family:'Rubik'">Лесные пожары</h3><p style="font-size:24px;color:#D5DAFF">Расчет скорости распространения огня при разной силе ветра и плотности деревьев.</p></div>
  </div>
  <div style="background:#1B2050;border:1px solid #2F3876;border-radius:22px;padding:30px;display:flex;gap:20px;align-items:center">
    <span style="font-size:54px">🚗</span>
    <div><h3 style="font-size:30px;color:#FFFFFF;font-family:'Rubik'">Городские пробки</h3><p style="font-size:24px;color:#D5DAFF">Моделирование трафика машин на перекрестках для настройки умных светофоров.</p></div>
  </div>
  <div style="background:#1B2050;border:1px solid #2F3876;border-radius:22px;padding:30px;display:flex;gap:20px;align-items:center">
    <span style="font-size:54px">❄️</span>
    <div><h3 style="font-size:30px;color:#FFFFFF;font-family:'Rubik'">Физика кристаллов</h3><p style="font-size:24px;color:#D5DAFF">Рост снежинок и кристаллов льда из микроскопических молекул воды.</p></div>
  </div>
</div>
""", "Широкий научный кругозор: показываем, как сегодняшняя тема применяется в реальных суперкомпьютерах.")

    make_reflection("l7-reflect", 7, [
        "Сколько соседей нужно клетке ●, чтобы выжить в следующем поколении?",
        "При скольких соседях в пустой клетке · рождается новая жизнь?",
        "Почему фигура «Мигалка» называется осциллятором?"
    ], "Рефлексия по итогам создания симулятора клеточных автоматов.")

    # -------------------------------------------------------------------------
    # УРОК 8: ФИНАЛЬНЫЙ ХАКАТОН, МЕНЮ И РЕЛИЗ (16 слайдов)
    # -------------------------------------------------------------------------
    make_divider("l8-divider", 8, "Финальный хакатон: меню, рекорды и релиз", "Главное консольное меню, запись рекорда в файл, хакатон и защита проектов", "«Главное консольное меню», «Запись рекорда в records.txt»", "Финальная авторская игра с Залом Славы", "🌟 Заставка и фирменный ASCII-титул игры", "Урок 8: кульминация курса, финализация проектов и презентация.")

    make_warmup("l8-warm", 8, "Что отличает черновик от релизной игры?", "Вы написали отличную игровую механику. Чего не хватает, чтобы игру можно было с гордостью отправить другу или выложить в сеть?", ["Ничего, черновика достаточно", "Главного меню, сохранения рекордов и красивой заставки!", "Удалить весь код"], "Как сохранить лучший счет игрока навсегда?", "Разминка о полировке игр и файловой системе.")

    make_learn("l8-learn", 8, [
        ("📜", "Главное меню", "Соберем удобное меню запуска: 1 - Играть, 2 - Рекорды, 3 - Выход."),
        ("💾", "Файлы: with open()", "Научимся сохранять имена и очки победителей в файл records.txt на диске."),
        ("🏆", "Хакатон и Защита", "Доработаем любимую игру курса и покажем свой проект на большом экране!")
    ], "Цели финального занятия.")

    make_code_explainer("l8-menu", "Интерфейс игры", "Главное меню в цикле while True",
"""<span class="kw">while</span> <span class="kw">True</span>:
    <span class="fn">print</span>(<span class="str">"=== ГЛАВНОЕ МЕНЮ ==="</span>)
    <span class="fn">print</span>(<span class="str">"1. Начать игру"</span>)
    <span class="fn">print</span>(<span class="str">"2. Таблица рекордов"</span>)
    <span class="fn">print</span>(<span class="str">"3. Выход"</span>)
    
    choice = <span class="fn">input</span>(<span class="str">"Выбери пункт (1-3): "</span>)
    <span class="kw">if</span> choice == <span class="str">"1"</span>:
        <span class="fn">print</span>(<span class="str">"Запуск игры..."</span>)
    <span class="kw">elif</span> choice == <span class="str">"3"</span>:
        <span class="fn">print</span>(<span class="str">"До встречи!"</span>)
        <span class="kw">break</span>""",
        [
            ("Цикл меню", "После окончания игры игрок возвращается обратно в меню, а не вылетает из программы."),
            ("Проверка выбора", "Каждая цифра запускает соответствующую функцию или режим игры."),
            ("Пункт «Выход»", "Единственный способ корректно завершить программу через команду break.")
        ],
        "Архитектура консольного меню для любого программного продукта."
    )

    make_code_explainer("l8-files-write", "Вечная память", "Сохранение рекордов в файл через with open()",
"""player_name = <span class="str">"Алекс"</span>
score = <span class="num">250</span>

<span class="com"># Режим "a" (append) — дописывает новую запись в конец файла:</span>
<span class="kw">with</span> <span class="fn">open</span>(<span class="str">"records.txt"</span>, <span class="str">"a"</span>, encoding=<span class="str">"utf-8"</span>) <span class="kw">as</span> f:
    f.<span class="fn">write</span>(<span class="str">f"{player_name}: {score}\\n"</span>)

<span class="fn">print</span>(<span class="str">"Рекорд успешно сохранён на диск!"</span>)""",
        [
            ("with open(...) as f:", "Безопасный менеджер контекста! Сам закроет файл даже при ошибке в коде."),
            ("Режим 'a' (append)", "Не стирает старые рекорды, а добавляет новую строку в самый конец файла."),
            ("Символ переноса \\n", "Обязательно ставим в конце строки, чтобы следующий рекорд был на новой строчке.")
        ],
        "Работа с дисковыми файлами в Python через безопасный менеджер контекста with."
    )

    make_code_explainer("l8-files-read", "Зал Славы", "Чтение и показ таблицы рекордов",
"""<span class="kw">with</span> <span class="fn">open</span>(<span class="str">"records.txt"</span>, <span class="str">"r"</span>, encoding=<span class="str">"utf-8"</span>) <span class="kw">as</span> f:
    records_data = f.<span class="fn">read</span>()

<span class="fn">print</span>(<span class="str">"🏆 === ЗАЛ СЛАВЫ === 🏆"</span>)
<span class="fn">print</span>(records_data)
<span class="fn">print</span>(<span class="str">"======================="</span>)""",
        [
            ("Режим 'r' (read)", "Открывает существующий файл только для чтения данных."),
            ("f.read()", "Считывает весь текст файла в одну строковую переменную."),
            ("Вывод на экран", "Игроки могут увидеть все предыдущие победы и рекорды друзей.")
        ],
        "Чтение файла с диска и форматированный вывод Зала Славы."
    )

    make_code_explainer("l8-ascii", "Консольный стиль", "ASCII-арт заставки и рамки игры",
"""banner = <span class="str">\"\"\"
+-------------------------------+
|     🔥 PYTHON GAMES 2026 🔥   |
|   Финальный Релиз Проекта     |
+-------------------------------+
\"\"\"</span>

<span class="fn">print</span>(banner)
<span class="fn">print</span>(<span class="str">"Разработчик готов к презентации!"</span>)""",
        [
            ("Тройные кавычки \"\"\"", "Позволяют писать многострочный текст с любыми переносами строк и рамками."),
            ("Фирменный стиль", "Любая игра выглядит в 10 раз профессиональнее с красивым логотипом при старте."),
            ("Символы рамок", "Используйте символы +, -, |, ═, ║ для аккуратного оформления окон.")
        ],
        "ASCII-дизайн для консольных интерфейсов."
    )

    make_errors_table("l8-errors", 8, "Ошибки при работе с файлами и меню", [
        ("FileNotFoundError: [Errno 2]", "Файл records.txt еще не создан на диске", "open(\"records.txt\", \"r\")", "Сначала открыть в режиме 'a' или создать пустой"),
        ("Стерлись все прошлые рекорды", "Использовали режим 'w' вместо 'a'", "open(\"rec.txt\", \"w\")", "Режим 'w' перезаписывает! Для рекордов нужен 'a'"),
        ("Забыли кодировку encoding='utf-8'", "Русские буквы превратились в иероглифы", "open(\"rec.txt\", \"a\")", "Всегда писать: encoding=\"utf-8\""),
        ("Все записи склеились в одну строчку", "Забыли добавить символ \\n при записи", "f.write(f\"{name}: {score}\")", "f.write(f\"{name}: {score}\\n\")")
    ], "Разбираем главные грабли файлового ввода-вывода.")

    make_train_tasks("l8-tasks-train", 8, [
        ("g08-01", "Главное меню", "Вывести меню с пунктами 1, 2, 3 и обработать выбор игрока через if/elif", 'choice == "1" -> запуск'),
        ("g08-02", "Запись рекорда в файл", "Открыть файл records.txt в режиме 'a' и записать строку с именем и очками", 'with open("records.txt", "a") as f:'),
        ("g08-03", "Заставка игры", "Оформить красивую рамку с названием игры через тройные кавычки", 'print("+----------------+")')
    ], "15 минут на тренировочные задачи перед стартом хакатона.")

    add_slide("l8-hackathon", "#12163A", """
<div style="display:flex;flex-direction:column;gap:14px">
  <p style="font-size:24px;font-weight:700;letter-spacing:3px;text-transform:uppercase;color:#FFDE59">Творческий этап · 35 минут</p>
  <h2 style="font-family:'Rubik', Arial, sans-serif;font-size:64px;font-weight:700;color:#FFFFFF">Хакатон: прокачка и полировка игры</h2>
</div>
<div style="display:flex;gap:36px;align-items:stretch;margin-top:20px">
  <div style="flex:1;background:#1B2050;border:2px solid #2F43E8;border-radius:24px;padding:36px;display:flex;flex-direction:column;gap:20px">
    <span style="font-size:54px">💡</span>
    <h3 style="font-family:'Rubik', sans-serif;font-size:36px;color:#FFFFFF">Что можно сделать:</h3>
    <ul style="font-size:26px;color:#D5DAFF;line-height:1.5;padding-left:26px;display:flex;flex-direction:column;gap:12px">
      <li>Выбрать свою самую любимую игру из 8 уроков курса</li>
      <li>Добавить выбор уровней сложности (легкий / хардкор)</li>
      <li>Украсить игру крутыми ASCII-баннерами и эмодзи</li>
      <li>Подключить сохранение очков в Зал Славы records.txt</li>
      <li>Придумать неожиданные сюжетные повороты и пасхалки</li>
    </ul>
  </div>
  <div style="flex:1;background:#2F43E8;border-radius:24px;padding:36px;color:#FFFFFF;display:flex;flex-direction:column;gap:20px;box-shadow:0 8px 30px rgba(47,67,232,0.4)">
    <span style="font-size:54px">⏱</span>
    <h3 style="font-family:'Rubik', sans-serif;font-size:36px">Тайминг хакатона:</h3>
    <div style="font-size:28px;line-height:1.6;display:flex;flex-direction:column;gap:14px">
      <p>🔹 <b>00–25 мин:</b> Доработка механик и кода</p>
      <p>🔹 <b>25–35 мин:</b> Тестирование и подготовка к показу</p>
      <p>🔹 <b>Финал:</b> Выступление каждого разработчика!</p>
    </div>
    <div style="margin-top:auto;background:rgba(255,255,255,0.2);padding:14px 20px;border-radius:14px;font-size:24px">
      🚀 Преподаватель помогает каждому воплотить идеи!
    </div>
  </div>
</div>
""", "Старт хакатона: даем ребятам свободу творчества на 35 минут с поддержкой преподавателя.")

    add_slide("l8-criteria", "#F6F7FB", """
<div style="display:flex;flex-direction:column;gap:14px">
  <p style="font-size:24px;font-weight:700;letter-spacing:3px;text-transform:uppercase;color:#2F43E8">Оценка проектов</p>
  <h2 style="font-family:'Rubik', Arial, sans-serif;font-size:56px;font-weight:700;color:#12163A">4 Критерия классной игры</h2>
</div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:26px;margin-top:20px">
  <div style="background:#FFFFFF;border:1px solid #E1E4F0;border-radius:22px;padding:30px;display:flex;gap:20px;align-items:center;box-shadow:0 4px 18px rgba(18,22,58,.05)">
    <span style="font-size:54px">🎮</span>
    <div><h3 style="font-size:30px;color:#12163A;font-family:'Rubik'">Геймплей</h3><p style="font-size:24px;color:#4A5170">В игру интересно играть, есть победа, поражение и понятные правила.</p></div>
  </div>
  <div style="background:#FFFFFF;border:1px solid #E1E4F0;border-radius:22px;padding:30px;display:flex;gap:20px;align-items:center;box-shadow:0 4px 18px rgba(18,22,58,.05)">
    <span style="font-size:54px">🧼</span>
    <div><h3 style="font-size:30px;color:#12163A;font-family:'Rubik'">Чистота кода</h3><p style="font-size:24px;color:#4A5170">Понятные имена переменных, аккуратные отступы, нет лишнего кода.</p></div>
  </div>
  <div style="background:#FFFFFF;border:1px solid #E1E4F0;border-radius:22px;padding:30px;display:flex;gap:20px;align-items:center;box-shadow:0 4px 18px rgba(18,22,58,.05)">
    <span style="font-size:54px">🎨</span>
    <div><h3 style="font-size:30px;color:#12163A;font-family:'Rubik'">Атмосфера и дизайн</h3><p style="font-size:24px;color:#4A5170">ASCII-арт, сюжетные реплики, эмодзи, погружение игрока в мир.</p></div>
  </div>
  <div style="background:#FFFFFF;border:1px solid #E1E4F0;border-radius:22px;padding:30px;display:flex;gap:20px;align-items:center;box-shadow:0 4px 18px rgba(18,22,58,.05)">
    <span style="font-size:54px">💾</span>
    <div><h3 style="font-size:30px;color:#12163A;font-family:'Rubik'">Зал Славы</h3><p style="font-size:24px;color:#4A5170">Работающее сохранение лучших результатов игроков в файл на диске.</p></div>
  </div>
</div>
""", "Критерии оценки проектов для защиты.")

    add_slide("l8-defense", "#12163A", """
<div style="display:flex;flex-direction:column;gap:14px">
  <p style="font-size:24px;font-weight:700;letter-spacing:3px;text-transform:uppercase;color:#A9B5FF">Кульминация курса</p>
  <h2 style="font-family:'Rubik', Arial, sans-serif;font-size:64px;font-weight:700;color:#FFFFFF">Презентация и защита проектов 🎤</h2>
</div>
<div style="display:flex;gap:36px;align-items:stretch;margin-top:20px">
  <div style="flex:1.2;background:#1B2050;border:2px solid #2F3876;border-radius:24px;padding:36px;display:flex;flex-direction:column;gap:20px">
    <h3 style="font-family:'Rubik', sans-serif;font-size:34px;color:#FFDE59">План выступления (2–3 минуты на разработчика):</h3>
    <div style="font-size:26px;color:#FFFFFF;line-height:1.55;display:flex;flex-direction:column;gap:14px">
      <p>1️⃣ <b>Название и жанр:</b> как называется твоя игра и о чем её сюжет?</p>
      <p>2️⃣ <b>Демонстрация:</b> запусти игру на экране и покажи один раунд!</p>
      <p>3️⃣ <b>Гордость разработчика:</b> какая фича получилась круче всего?</p>
      <p>4️⃣ <b>Главный баг:</b> с какой ошибкой пришлось больше всего повоевать?</p>
    </div>
  </div>
  <div style="flex:0.8;background:#2F43E8;border-radius:24px;padding:36px;color:#FFFFFF;display:flex;flex-direction:column;gap:20px;justify-content:center;text-align:center">
    <span style="font-size:72px">👏</span>
    <h3 style="font-family:'Rubik', sans-serif;font-size:38px">Правило зрителей:</h3>
    <p style="font-size:26px;line-height:1.45;color:#E4E8FF">Поддерживаем каждого аплодисментами! Задаем добрые вопросы и пробуем пройти игры друг друга!</p>
  </div>
</div>
""", "Сценарий защиты проектов: каждый ученик получает минуту славы у доски.")

    add_slide("l8-future", "#F6F7FB", """
<div style="display:flex;flex-direction:column;gap:14px">
  <p style="font-size:24px;font-weight:700;letter-spacing:3px;text-transform:uppercase;color:#2F43E8">Твой путь в IT продолжается</p>
  <h2 style="font-family:'Rubik', Arial, sans-serif;font-size:56px;font-weight:700;color:#12163A">Куда двигаться дальше в разработке игр?</h2>
</div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:26px;margin-top:20px">
  <div style="background:#FFFFFF;border:1px solid #E1E4F0;border-radius:22px;padding:30px;display:flex;gap:20px;align-items:center;box-shadow:0 4px 18px rgba(18,22,58,.05)">
    <span style="font-size:54px">👾</span>
    <div><h3 style="font-size:30px;color:#12163A;font-family:'Rubik'">Библиотека Pygame</h3><p style="font-size:24px;color:#4A5170">Настоящие окна, спрайты, физика прыжков, музыка и поддержка геймпада.</p></div>
  </div>
  <div style="background:#FFFFFF;border:1px solid #E1E4F0;border-radius:22px;padding:30px;display:flex;gap:20px;align-items:center;box-shadow:0 4px 18px rgba(18,22,58,.05)">
    <span style="font-size:54px">🌐</span>
    <div><h3 style="font-size:30px;color:#12163A;font-family:'Rubik'">Игровые боты в Telegram</h3><p style="font-size:24px;color:#4A5170">Перенос ваших консольных квестов в чат-боты, в которые могут играть тысячи друзей.</p></div>
  </div>
  <div style="background:#FFFFFF;border:1px solid #E1E4F0;border-radius:22px;padding:30px;display:flex;gap:20px;align-items:center;box-shadow:0 4px 18px rgba(18,22,58,.05)">
    <span style="font-size:54px">🕹️</span>
    <div><h3 style="font-size:30px;color:#12163A;font-family:'Rubik'">Движок Godot Engine</h3><p style="font-size:24px;color:#4A5170">Популярный движок с языком GDScript, очень похожим на изученный вами Python!</p></div>
  </div>
  <div style="background:#FFFFFF;border:1px solid #E1E4F0;border-radius:22px;padding:30px;display:flex;gap:20px;align-items:center;box-shadow:0 4px 18px rgba(18,22,58,.05)">
    <span style="font-size:54px">🥇</span>
    <div><h3 style="font-size:30px;color:#12163A;font-family:'Rubik'">Олимпиадное программирование</h3><p style="font-size:24px;color:#4A5170">Алгоритмы, сортировки, поиск кратчайших путей и победы на турнирах.</p></div>
  </div>
</div>
""", "Мотивационный слайд о дальнейших горизонтах развития юных программистов.")

    make_reflection("l8-reflect", 8, [
        "Какой проект из 8 занятий тебе больше всего запомнился и почему?",
        "С какой программной ошибкой за курс было сложнее всего справиться?",
        "Какую игру ты хочешь разработать следующей?"
    ], "Финальная душевная рефлексия всего курса.")

    # -------------------------------------------------------------------------
    # ЗАКЛЮЧИТЕЛЬНЫЙ СЛАЙД (1 слайд)
    # -------------------------------------------------------------------------
    add_slide("final", "#12163A", """
<div style="display:flex;flex-direction:column;gap:36px;align-items:center;justify-content:center;height:100%;text-align:center">
  <span style="font-size:120px">🏆</span>
  <h1 style="font-family:'Rubik', sans-serif;font-size:104px;font-weight:700;color:#FFFFFF">Поздравляем выпускников курса!</h1>
  <p style="font-size:42px;color:#D5DAFF;max-width:1400px;line-height:1.35">Вы прошли огромный путь от самого первого print("Привет") до создания 2D симуляций, пошаговых битв и собственных релизов!</p>
  <div style="margin-top:20px;background:#2F43E8;padding:22px 56px;border-radius:22px;font-size:34px;color:#fff;font-weight:700;box-shadow:0 10px 40px rgba(47,67,232,0.5)">
    🎉 Вручение сертификатов разработчиков игр на Python! 🎉
  </div>
</div>
""", "Торжественный финал, аплодисменты группе, вручение дипломов.")


def generate():
    build_all_slides()
    content = HTML_HEAD + "\n".join(SLIDES) + HTML_TAIL
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Презентация создана: {OUT_FILE}")
    print(f"Всего слайдов: {len(SLIDES)}")
    print(f"Размер файла: {len(content)} байт ({len(content) // 1024} КБ)")


if __name__ == "__main__":
    generate()
