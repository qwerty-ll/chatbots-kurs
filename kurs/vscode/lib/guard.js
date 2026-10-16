// «Пиши сам»: не даём вставлять в файлы заданий готовый код (из браузера, чата с нейросетью, подсказки, образца).
// Своё копировать можно: всё, что когда-либо было в своих файлах курса (даже если потом изменил или удалил),
// а также текст условия и примера диалога. Проверяем построчно: блокируем, только если во вставке
// набирается заметный кусок, которого у ученика никогда не было.
// Без зависимости от VS Code, чтобы это можно было проверять тестами.
"use strict";

const MIN_CHARS = 25;      // столько непробельных символов за одну вставку уже не «набрал руками»
const MIN_LINES = 3;       // или несколько строк сразу
const SHORT_LINE = 6;      // короткие строки (`else:`, `break`) не считаем — их и так все пишут одинаково
const KEEP_REMOVED = 50;   // сколько недавно удалённых кусков помнить (вырезал → вставил)

/** Текст без пробелов и переносов: так сравниваем, не обращая внимания на отступы. */
function squash(s) {
  return String(s || "").replace(/\s+/g, "");
}

/** Похоже ли это на вставку, а не на набор с клавиатуры (буква, автодополнение, перенос строки с отступом). */
function looksPasted(text) {
  const solid = squash(text);
  if (!solid) return false;
  const lines = String(text).split("\n").filter((l) => l.trim()).length;
  return solid.length >= MIN_CHARS || (lines >= MIN_LINES && solid.length >= 10);
}

class Guard {
  constructor() {
    this.snapshots = new Map();   // путь → текст документа до последнего изменения
    this.seen = new Set();        // все строки, которые когда-либо были в своих файлах (squash)
    this.removed = [];            // недавно удалённые куски (squash)
    this.allowed = [];            // разрешённые тексты: условие задания, пример диалога, заготовка (squash)
  }

  remember(text) {
    for (const line of String(text).split("\n")) {
      const s = squash(line);
      if (s.length >= SHORT_LINE) this.seen.add(s);
    }
  }

  /** Запомнить текущий текст документа: всё, что в нём есть, — своё. */
  snapshot(file, text) {
    this.snapshots.set(file, String(text));
    this.remember(text);
  }

  forget(file) {
    this.snapshots.delete(file);
  }

  /** Разрешить вставку этого текста (условие задания, заготовка, которую вставляет сама панель). */
  allow(text) {
    const s = squash(text);
    if (s) this.allowed.push(s);
  }

  /** Сколько во вставке чужого: непробельные символы строк, которых нет ни в своём, ни в разрешённом. */
  foreign(text, sources) {
    const whole = squash(text);
    const pools = this.removed.concat(this.allowed, sources.map(squash));
    if (pools.some((p) => p.includes(whole))) return { chars: 0, lines: 0 };
    let chars = 0;
    let lines = 0;
    for (const line of String(text).split("\n")) {
      const s = squash(line);
      if (s.length < SHORT_LINE || this.seen.has(s)) continue;
      if (pools.some((p) => p.includes(s))) continue;
      chars += s.length;
      lines += 1;
    }
    return { chars, lines };
  }

  /** Чужой ли это код (вставлять нельзя). */
  isForeign(text, sources) {
    if (!looksPasted(text)) return false;
    const f = this.foreign(text, sources);
    return f.chars >= MIN_CHARS || (f.lines >= MIN_LINES && f.chars >= 10);
  }

  /**
   * Разобрать изменение документа. changes — как в VS Code: {rangeOffset, rangeLength, text}, смещения — в старом тексте.
   * Возвращает {blocked: [вставки чужого кода], old: текст до изменения} и обновляет снимок.
   * sources — тексты своих файлов (другие файлы курса); снимок этого же файла учитывается сам.
   */
  inspect(file, newText, changes, sources) {
    const old = this.snapshots.has(file) ? this.snapshots.get(file) : null;
    const blocked = [];
    const blockedChanges = [];
    if (old !== null) {
      const own = [old].concat(sources || []);
      for (const c of changes) {
        if (c.text && this.isForeign(c.text, own)) {
          blocked.push(c.text);
          blockedChanges.push({
            rangeOffset: c.rangeOffset,
            rangeLength: c.rangeLength,
            text: c.text,
            originalText: old.substr(c.rangeOffset, c.rangeLength),
          });
        }
      }
      if (!blocked.length) {
        for (const c of changes) {
          const gone = squash(old.substr(c.rangeOffset, c.rangeLength));
          if (gone.length >= 10) {
            this.removed.push(gone);
            if (this.removed.length > KEEP_REMOVED) this.removed.shift();
          }
        }
      }
    }
    if (!blocked.length || old === null) this.snapshot(file, newText);
    return { blocked, blockedChanges, old };
  }
}

module.exports = { Guard, looksPasted, squash, MIN_CHARS };
