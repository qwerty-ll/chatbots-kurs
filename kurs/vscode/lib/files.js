// Работа с папкой ученика. Без зависимости от VS Code, чтобы это можно было проверять тестами.
"use strict";
const fs = require("fs");
const path = require("path");

const WORK = "Мои_работы";
const SAMPLE = "Образец";
const HIDDEN = ".kurs";
const UPLOAD_EXT = new Set([".py", ".txt", ".json", ".md"]);
const MAX_FILE = 100 * 1024;
const MAX_FILES = 60;

function lessonDir(root, lesson) {
  return path.join(root, WORK, "Занятие_" + lesson);
}

function readJson(file, fallback) {
  try { return JSON.parse(fs.readFileSync(file, "utf8")); } catch (e) { return fallback; }
}

function writeFile(file, text) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, text, "utf8");
}

/** Все файлы работы ученика для резервной копии на сервере: [{path, content}], пути через «/» от Мои_работы. */
function collectWork(root) {
  const base = path.join(root, WORK);
  const out = [];
  const walk = (dir) => {
    let entries = [];
    try { entries = fs.readdirSync(dir, { withFileTypes: true }); } catch (e) { return; }
    for (const e of entries) {
      if (out.length >= MAX_FILES) return;
      if (e.name.startsWith(".") || e.name === "__pycache__" || e.name === "ai.py" || e.name === "agent.py") continue;   // .env с ключом и общие модули класса не копируем
      const full = path.join(dir, e.name);
      if (e.isDirectory()) walk(full);
      else if (UPLOAD_EXT.has(path.extname(e.name).toLowerCase())) {
        try {
          if (fs.statSync(full).size > MAX_FILE) continue;
          out.push({ path: path.relative(base, full).split(path.sep).join("/"), content: fs.readFileSync(full, "utf8") });
        } catch (err) { /* файл мог исчезнуть */ }
      }
    }
  };
  walk(base);
  return out;
}

/** Восстанавливает файлы с сервера, не затирая те, что уже есть. Возвращает число записанных файлов. */
function restoreWork(root, files) {
  const base = path.join(root, WORK);
  let n = 0;
  for (const f of files || []) {
    const rel = String(f.path || "");
    if (!rel || rel.split("/").includes("..") || path.isAbsolute(rel)) continue;
    const full = path.join(base, ...rel.split("/"));
    if (!full.startsWith(base + path.sep)) continue;
    if (fs.existsSync(full)) continue;
    writeFile(full, String(f.content || ""));
    n++;
  }
  return n;
}

/** Стирает работу ученика с компьютера (после конца занятия или смены ученика). */
function wipeWork(root) {
  for (const name of [WORK, SAMPLE]) {
    fs.rmSync(path.join(root, name), { recursive: true, force: true });
  }
  fs.rmSync(path.join(root, HIDDEN, "tasks"), { recursive: true, force: true });
  fs.rmSync(path.join(root, HIDDEN, "owner.json"), { force: true });
}

function isInside(file, dir) {
  const rel = path.relative(dir, file);
  return !!rel && !rel.startsWith("..") && !path.isAbsolute(rel);
}

module.exports = { WORK, SAMPLE, HIDDEN, lessonDir, readJson, writeFile, collectWork, restoreWork, wipeWork, isInside };
