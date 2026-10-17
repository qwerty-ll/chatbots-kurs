// Панель курса «Чат-боты на Python» для VS Code.
// Обычный JavaScript без сборки и без зависимостей. Логика:
//   вход ученика (выбор имени + подтверждение учителя) → задания, теория, шпаргалка, помощь;
//   проверка кода запускает kurs_check.py на этом компьютере; результаты уходят на сервер курса.
"use strict";
const vscode = require("vscode");
const cp = require("child_process");
const fs = require("fs");
const os = require("os");
const path = require("path");
const { call, ApiError } = require("./lib/http");
const F = require("./lib/files");
const { Guard, squash, isAiGenerated } = require("./lib/guard");

const POLL_MS = 3000;
const IDLE_POLL_MS = 5000;

/** @type {Kurs} */
let kurs;

function activate(context) {
  kurs = new Kurs(context);
  context.subscriptions.push(
    vscode.commands.registerCommand("kurs.openPanel", () => kurs.showPanel()),
    vscode.commands.registerCommand("kurs.run", (uri) => kurs.runFile(uri)),
    vscode.commands.registerCommand("kurs.check", (uri) => kurs.checkFile(uri)),
    vscode.workspace.onDidSaveTextDocument((doc) => kurs.onSave(doc)),
    vscode.window.onDidChangeActiveTextEditor((ed) => kurs.onEditor(ed)),
    vscode.workspace.onDidChangeTextDocument((e) => { kurs.diag.delete(e.document.uri); kurs.onChange(e); }),
    vscode.workspace.onDidOpenTextDocument((doc) => kurs.onOpen(doc)),
    { dispose: () => kurs.stop() }
  );
  kurs.start();
}

function deactivate() {
  if (kurs) kurs.stop();
}

class Kurs {
  constructor(context) {
    this.ctx = context;
    this.panel = null;
    this.status = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
    this.status.command = "kurs.openPanel";
    context.subscriptions.push(this.status);
    this.timer = null;
    this.uploadTimer = null;
    this.lastPyEditor = null;
    this.runner = null;
    this.diag = vscode.languages.createDiagnosticCollection("kurs");
    context.subscriptions.push(this.diag);
    this.runBtn = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 99);
    this.runBtn.text = "$(play) Запустить";
    this.runBtn.tooltip = "Запустить программу (F5)";
    this.runBtn.command = "kurs.run";
    this.checkBtn = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 98);
    this.checkBtn.text = "$(check) Проверить";
    this.checkBtn.tooltip = "Проверить задание (F6)";
    this.checkBtn.command = "kurs.check";
    context.subscriptions.push(this.runBtn, this.checkBtn);
    // то, что видит панель
    this.v = {
      screen: "loading", message: "", server: "", pc: "", students: [], here: null, me: null, lesson: null,
      state: null, offline: false, files: {}, checks: {}, hints: {}, solutions: {}, busy: null, waitingName: "",
    };
    this.token = null;
    this.request = null;   // {id, secret} — ждём подтверждения учителя
    this.tasks = {};       // id → задание с заготовкой (с сервера)
    this.pending = [];     // результаты, которые не удалось отправить без связи
    // «Пиши сам»: вставка чужого кода в файлы заданий откатывается
    this.restartSeen = {};     // номера команд «перезапустить VS Code» с пульта, которые мы уже видели
    this.guard = new Guard();
    if (!context.globalState.get("kurs.guardSince")) context.globalState.update("kurs.guardSince", Date.now());
    for (const doc of vscode.workspace.textDocuments) this.onOpen(doc);
  }

  // ---------------------------------------------------------------- настройки
  root() {
    const ws = vscode.workspace.workspaceFolders;
    return ws && ws.length ? ws[0].uri.fsPath : path.join(os.homedir(), "Курс");
  }
  config() {
    return F.readJson(path.join(this.root(), F.HIDDEN, "config.json"), {});
  }
  server() {
    const s = vscode.workspace.getConfiguration("kurs").get("server") || this.config().server || process.env.KURS_SERVER || "";
    return s.replace(/\/+$/, "");
  }
  pc() {
    return this.config().pc || os.hostname().split(".")[0];
  }
  python() {
    return vscode.workspace.getConfiguration("kurs").get("python") || this.config().python ||
      (process.platform === "win32" ? "python" : "python3");
  }
  checker() {
    return this.ctx.asAbsolutePath(path.join("bundled", "kurs_check.py"));
  }
  tokenKey() {
    return "kurs.token:" + this.server() + ":" + this.pc();
  }
  lessonNum() {
    return this.v.lesson ? this.v.lesson.lesson : (this.v.state ? this.v.state.lesson : 0);
  }
  workDir() {
    return F.lessonDir(this.root(), this.lessonNum());
  }
  taskById(id) {
    return this.v.lesson ? this.v.lesson.tasks.find((t) => t.id === id) : null;
  }
  taskFile(t) {
    return path.join(this.workDir(), t.file);
  }

  // ---------------------------------------------------------------- запуск
  start() {
    const cfgOpen = vscode.workspace.getConfiguration("kurs").get("autoOpen");
    if (cfgOpen && this.server()) {
      this.showPanel();
      this.simpleView();
    }
    this.updateStatus();
    this.boot();
  }

  stop() {
    clearTimeout(this.timer);
    clearTimeout(this.uploadTimer);
  }

  schedule(fn, ms) {
    clearTimeout(this.timer);
    this.timer = setTimeout(() => fn.call(this).catch((e) => console.error("kurs:", e)), ms);
  }

  async api(method, p, body) {
    return call(this.server(), method, p, body, this.token);
  }

  async boot() {
    this.v.server = this.server();
    this.v.pc = this.pc();
    if (!this.v.server) {
      this.setScreen("noserver", "Не задан адрес сервера курса.");
      return;
    }
    let hello;
    try {
      hello = await call(this.v.server, "GET", "/api/hello?pc=" + encodeURIComponent(this.v.pc));
    } catch (e) {
      this.setScreen("noserver", "Нет связи с сервером курса. Пробуем снова…");
      this.schedule(this.boot, IDLE_POLL_MS);
      return;
    }
    if (this.checkRestart(hello.restart) || this.checkClose(hello.close)) return;
    if (!hello.running) {
      this.setScreen("idle", "Занятие ещё не началось. Подожди учителя.");
      this.schedule(this.boot, IDLE_POLL_MS);
      return;
    }
    // сохранённый вход (например, после перезапуска VS Code)
    const saved = this.ctx.globalState.get(this.tokenKey());
    if (saved && saved.token) {
      this.token = saved.token;
      try {
        await this.api("GET", "/api/state");
        await this.enter(saved.student_id);
        return;
      } catch (e) {
        this.token = null;
        await this.ctx.globalState.update(this.tokenKey(), undefined);
      }
    }
    this.v.students = hello.students || [];
    this.v.here = hello.here || null;
    this.v.lessonTitle = hello.title;
    this.setScreen(this.v.here ? "confirmHere" : "pick", "");
    this.schedule(this.refreshRoster, IDLE_POLL_MS);
  }

  async refreshRoster() {
    if (!["pick", "confirmHere", "denied"].includes(this.v.screen)) return;
    try {
      const hello = await call(this.server(), "GET", "/api/hello?pc=" + encodeURIComponent(this.pc()));
      if (this.checkRestart(hello.restart) || this.checkClose(hello.close)) return;
      if (!hello.running) return this.boot();
      this.v.students = hello.students || [];
      this.v.here = hello.here || null;
      if (this.v.screen === "confirmHere" && !this.v.here) this.v.screen = "pick";
      this.render();
    } catch (e) { /* связь пропала: попробуем позже */ }
    this.schedule(this.refreshRoster, IDLE_POLL_MS);
  }

  async login(studentId) {
    try {
      const r = await call(this.server(), "POST", "/api/login", { pc: this.pc(), student_id: studentId });
      if (r.status === "approved") {
        this.token = r.token;
        await this.enter(studentId);
        return;
      }
      this.request = { id: r.request_id, secret: r.secret, student_id: studentId };
      this.v.waitingName = r.name;
      let msg = "Учитель скоро подтвердит вход.";
      if (r.kind === "transfer") msg = `Это имя сейчас на ${r.other_pc}. Учитель подтвердит, что это ты.`;
      if (r.kind === "switch") msg = "На этом компьютере уже работал другой ученик. Учитель подтвердит смену.";
      this.setScreen("waiting", msg);
      this.schedule(this.pollRequest, 1500);
    } catch (e) {
      this.setScreen("pick", e.message);
      this.schedule(this.refreshRoster, IDLE_POLL_MS);
    }
  }

  async pollRequest() {
    if (this.v.screen !== "waiting" || !this.request) return;
    try {
      const r = await call(this.server(), "GET", `/api/request?id=${this.request.id}&secret=${this.request.secret}`);
      if (r.status === "approved") {
        this.token = r.token;
        const sid = this.request.student_id;
        this.request = null;
        await this.enter(sid);
        return;
      }
      if (r.status === "denied" || r.status === "cancelled") {
        this.request = null;
        this.setScreen("denied", r.status === "denied" ? "Учитель не подтвердил вход. Выбери своё имя ещё раз или подними руку."
          : "Запрос отменён. Выбери имя ещё раз.");
        this.schedule(this.refreshRoster, IDLE_POLL_MS);
        return;
      }
    } catch (e) { /* ждём дальше */ }
    this.schedule(this.pollRequest, 2000);
  }

  /** Вход подтверждён: готовим папку, загружаем занятие, начинаем опрос. */
  async enter(studentId) {
    const root = this.root();
    const owner = F.readJson(path.join(root, F.HIDDEN, "owner.json"), null);
    if (owner && (owner.student_id !== studentId || owner.server !== this.server())) {
      await this.closeWorkEditors();
      F.wipeWork(root);   // работа прошлого ученика уже сохранена на сервере
    }
    F.writeFile(path.join(root, F.HIDDEN, "owner.json"), JSON.stringify({ student_id: studentId, server: this.server() }));
    await this.ctx.globalState.update(this.tokenKey(), { token: this.token, student_id: studentId });
    this.v.checks = {};
    this.v.hints = {};
    this.v.solutions = {};
    this.tasks = {};
    await this.pollState();
    try {
      const mine = await this.api("GET", "/api/files");
      F.restoreWork(root, mine.files);
      // работа, вернувшаяся с сервера, — своя
      for (const f of mine.files || []) {
        const full = path.join(root, F.WORK, ...String(f.path || "").split("/"));
        try { if (fs.readFileSync(full, "utf8") === f.content && this.isGuarded(full)) this.trust(full, f.content); } catch (err) { /* нет файла */ }
      }
    } catch (e) { /* не страшно */ }
    this.refreshFiles();
    this.render();
    this.simpleView();
    this.onEditor(vscode.window.activeTextEditor);
  }

  /** «Простой вид»: слева редактор, справа панель, без боковых панелей и лишних кнопок. */
  simpleView() {
    if (!vscode.workspace.getConfiguration("kurs").get("simpleView")) return;
    const hide = () => {
      for (const cmd of ["workbench.action.closeSidebar", "workbench.action.closeAuxiliaryBar"]) {
        vscode.commands.executeCommand(cmd).then(undefined, () => undefined);
      }
    };
    hide();
    setTimeout(hide, 2000);   // при запуске окно ещё достраивается и может открыть панели заново
  }

  /** Файлы занятия (например, ai.py) и .env с ключом класса — в папку занятия. */
  writeLessonFiles() {
    if (!this.v.lesson) return;
    const dir = this.workDir();
    for (const [name, content] of Object.entries(this.v.lesson.files || {})) {
      if (name.includes("/") || name.includes("\\") || name.startsWith(".")) continue;
      const file = path.join(dir, name);
      let old = null;
      try { old = fs.readFileSync(file, "utf8"); } catch (e) { /* файла ещё нет */ }
      if (old !== content) F.writeFile(file, content);   // ai.py — общий модуль класса, держим его свежим
    }
    if (this.v.lesson.uses_ai && this.token) {
      // ключ класса = токен сеанса: работает, только пока ученик вошёл
      F.writeFile(path.join(dir, ".env"),
        "# Настройки нейросети. Этот файл создала панель курса.\n" +
        "# API_KEY — твой ключ класса. Никому не показывай!\n" +
        `KURS_SERVER=${this.server()}\nAPI_KEY=${this.token}\n`);
    }
  }

  async pollState() {
    if (!this.token) return;
    try {
      const st = await this.api("GET", "/api/state");
      if (this.checkRestart(st.restart) || this.checkRestart(st.restart_me, "me") || this.checkClose(st.close)) return;
      st.local_offset = Date.now() / 1000 - st.now;
      this.applyLock(!!st.locked);
      const lessonChanged = !this.v.state || !this.v.lesson || this.v.state.class_id !== st.class_id || this.v.lesson.lesson !== st.lesson;
      this.v.state = st;
      this.v.me = { name: st.name, pc: st.pc };
      this.v.offline = false;
      if (lessonChanged) {
        this.v.lesson = await this.api("GET", "/api/lesson");
        this.writeLessonFiles();
        this.allowLessonTexts();
      }
      // подсказки и образцы, полученные раньше, восстанавливаем из ответов сервера при необходимости
      if (this.v.screen !== "in") this.v.screen = "in";
      await this.flushPending();
      this.refreshFiles();
      this.updateStatus();
      this.render();
    } catch (e) {
      if (e instanceof ApiError && (e.status === 410 || e.status === 401)) {
        await this.ended(e.message);
        return;
      }
      this.v.offline = true;
      this.render();
    }
    this.schedule(this.pollState, POLL_MS);
  }

  /** Сеанс закрыт: занятие кончилось, другой ученик вошёл, учитель завершил сеанс или ученик вышел. */
  async ended(reason) {
    this.token = null;
    await this.ctx.globalState.update(this.tokenKey(), undefined);
    await this.closeWorkEditors();
    try { F.wipeWork(this.root()); } catch (e) { console.error("kurs: wipe", e); }
    this.v.lesson = null;
    this.v.state = null;
    this.v.me = null;
    if (this.runner) this.runner.dispose();
    this.diag.clear();
    this.runBtn.hide();
    this.checkBtn.hide();
    this.showPanel();
    this.setScreen("ended", reason || "Сеанс закрыт.");
    this.updateStatus();
    this.schedule(this.boot, 8000);
  }

  async closeWorkEditors() {
    const root = this.root();
    const dirs = [path.join(root, F.WORK), path.join(root, F.SAMPLE)];
    try {
      for (const doc of vscode.workspace.textDocuments) {
        if (dirs.some((d) => F.isInside(doc.uri.fsPath, d)) && doc.isDirty) await doc.save();
      }
      const tabs = [];
      for (const group of vscode.window.tabGroups.all) {
        for (const tab of group.tabs) {
          const input = tab.input;
          const uris = [];
          if (input && input.uri) uris.push(input.uri);
          if (input && input.original) uris.push(input.original, input.modified);
          if (uris.some((u) => dirs.some((d) => F.isInside(u.fsPath, d)))) tabs.push(tab);
        }
      }
      if (tabs.length) await vscode.window.tabGroups.close(tabs, true);
    } catch (e) { console.error("kurs: close editors", e); }
  }

  // ---------------------------------------------------------------- перезапуск по команде учителя
  /** Учитель нажал «Перезапустить VS Code у всех» (kind "all") или только у этого ученика ("me"):
   *  номер команды вырос с тех пор, как окно открылось. */
  checkRestart(seq, kind = "all") {
    if (typeof seq !== "number") return false;
    const seen = this.restartSeen[kind];
    if (seen === undefined || seq <= seen) {
      this.restartSeen[kind] = seq;
      return false;
    }
    this.restartSeen[kind] = seq;
    this.restartNow().catch((e) => console.error("kurs: restart", e));
    return true;
  }

  /** Учитель нажал «Закрыть VS Code у всех»: сохраняем работу и закрываем окно курса. */
  checkClose(seq) {
    if (typeof seq !== "number") return false;
    const seen = this.restartSeen.close;
    this.restartSeen.close = seq;
    if (seen === undefined || seq <= seen) return false;
    this.closeNow().catch((e) => console.error("kurs: close", e));
    return true;
  }

  async closeNow() {
    this.toast("Учитель завершает работу — сохраняю твои файлы и закрываю VS Code…");
    clearTimeout(this.timer);
    for (const doc of vscode.workspace.textDocuments) {
      if (doc.isDirty && doc.uri.scheme === "file") await doc.save();
    }
    await this.upload();
    await vscode.commands.executeCommand("workbench.action.quit");
  }

  async restartNow() {
    this.toast("Учитель перезапускает VS Code — сохраняю твою работу…");
    for (const doc of vscode.workspace.textDocuments) {
      if (doc.isDirty && F.isInside(doc.uri.fsPath, path.join(this.root(), F.WORK))) await doc.save();
    }
    await this.upload();
    // обновить панель тем же запуском, что и ярлык «Курс» (если он есть на этом компьютере)
    const starter = path.join(os.homedir(), ".kurs", "kurs_start.py");
    if (fs.existsSync(starter)) {
      await new Promise((resolve) => cp.execFile(this.python(), [starter, "--no-open", "--server", this.server()],
        { timeout: 120000 }, () => resolve()));
    }
    await vscode.commands.executeCommand("workbench.action.reloadWindow");
  }

  // ---------------------------------------------------------------- блокировка за чужой код
  isLocked() {
    return !!(this.v.state && this.v.state.locked);
  }

  /** Заблокирован учителем (вставил чужой код): файлы курса только для чтения, пока учитель не разблокирует.
   *  Блокировка хранится на сервере, поэтому перезапуск VS Code её не снимает. */
  async applyLock(on) {
    if (on === this.lockApplied) return;
    this.lockApplied = on;
    try {
      const files = vscode.workspace.getConfiguration("files");
      const ro = Object.assign({}, files.get("readonlyInclude") || {});
      if (on) ro[F.WORK + "/**"] = true; else delete ro[F.WORK + "/**"];
      await files.update("readonlyInclude", Object.keys(ro).length ? ro : undefined, vscode.ConfigurationTarget.Workspace);
    } catch (e) { console.error("kurs: lock", e); }
  }

  // ---------------------------------------------------------------- «пиши сам»
  /** Файл, который ученик пишет сам: .py в Мои_работы, кроме общих модулей класса. */
  isGuarded(file) {
    const base = path.basename(file);
    return file.endsWith(".py") && base !== "ai.py" && base !== "agent.py" &&
      F.isInside(file, path.join(this.root(), F.WORK));
  }
  trustedAll() {
    return this.ctx.globalState.get("kurs.trusted") || {};
  }
  /** Запомнить версию файла, которую ученик написал в редакторе курса (или выдала сама панель). */
  trust(file, text) {
    const all = this.trustedAll();
    all[path.resolve(file)] = String(text);
    for (const k of Object.keys(all)) if (!fs.existsSync(k) && k !== path.resolve(file)) delete all[k];
    this.ctx.globalState.update("kurs.trusted", all);
  }
  /** Можно ли доверять тексту файла: он совпадает с версией из редактора курса. */
  isTrusted(file, text) {
    const t = this.trustedAll()[path.resolve(file)];
    if (t !== undefined) return t === text;
    // файлы, созданные до появления этой защиты, принимаем как есть
    let mtime = 0;
    try { mtime = fs.statSync(file).mtimeMs; } catch (e) { /* файла нет */ }
    return !text.trim() || mtime <= (this.ctx.globalState.get("kurs.guardSince") || 0);
  }
  /** Из панели можно копировать: учебник (теория с примерами кода), шпаргалку, условия и примеры диалога.
   *  Нельзя: подсказки и образцы решений — их перепечатывают сами. */
  allowLessonTexts() {
    const lesson = this.v.lesson || {};
    for (const c of lesson.theory || []) {
      this.guard.allow(c.text || "");
      this.guard.allow(c.code || "");
      this.guard.allow(c.try || "");
    }
    for (const s of (lesson.cheatsheet && lesson.cheatsheet.sections) || []) {
      for (const row of s.rows || []) for (const cell of row) this.guard.allow(cell);
    }
    for (const t of lesson.tasks || []) {
      this.guard.allow(t.statement || "");
      for (const d of t.dialog || []) this.guard.allow(d[1] || "");
      for (const test of t.tests || []) for (const e of test.expect || []) this.guard.allow(e);
    }
  }
  ownSources(except) {
    const out = [];
    for (const [k, v] of Object.entries(this.trustedAll())) if (k !== path.resolve(except)) out.push(v);
    return out;
  }

  async onOpen(doc) {
    const file = doc.uri.fsPath;
    if (doc.uri.scheme !== "file" || !this.isGuarded(file)) return;
    const text = doc.getText();
    if (this.isTrusted(file, text)) {
      this.trust(file, text);
      this.guard.snapshot(file, text);
      return;
    }
    // файл изменили в обход редактора курса — возвращаем версию ученика
    const back = this.trustedAll()[path.resolve(file)] || "";
    this.guard.snapshot(file, back);
    this.guard.allow(back);
    const edit = new vscode.WorkspaceEdit();
    edit.replace(doc.uri, new vscode.Range(0, 0, doc.lineCount, 0), back);
    await vscode.workspace.applyEdit(edit);
    this.blockedNotice("outside_edit", file, text);
  }

  async onChange(e) {
    const doc = e.document;
    const file = doc.uri.fsPath;
    if (doc.uri.scheme !== "file" || !e.contentChanges.length || !this.isGuarded(file)) return;
    const res = this.guard.inspect(file, doc.getText(), e.contentChanges, this.ownSources(file));
    if (!res.blocked.length) return;
    const edit = new vscode.WorkspaceEdit();
    if (res.blockedChanges && res.blockedChanges.length) {
      const sorted = res.blockedChanges.slice().sort((a, b) => b.rangeOffset - a.rangeOffset);
      for (const bc of sorted) {
        const startPos = doc.positionAt(bc.rangeOffset);
        const endPos = doc.positionAt(bc.rangeOffset + bc.text.length);
        edit.replace(doc.uri, new vscode.Range(startPos, endPos), bc.originalText);
      }
    } else {
      edit.replace(doc.uri, new vscode.Range(0, 0, doc.lineCount, 0), res.old);
    }
    await vscode.workspace.applyEdit(edit);
    const blockedText = res.blocked.join("\n");
    const isAi = isAiGenerated(blockedText);
    const kind = isAi ? "ai_paste_blocked" : "paste_blocked";
    this.blockedNotice(kind, file, blockedText);
  }

  /** Вставку взяли из подсказки или образца решения? */
  fromHintOrSample(text) {
    const s = squash(text);
    const pool = [];
    for (const list of Object.values(this.v.hints || {})) for (const x of list || []) if (x) pool.push(x);
    for (const sol of Object.values(this.v.solutions || {})) if (sol && sol.code) pool.push(sol.code);
    return s.length > 0 && pool.some((p) => squash(p).includes(s) || s.includes(squash(p)));
  }

  async blockedNotice(kind, file, text) {
    if (this.token) {
      try {
        const r = await this.api("POST", "/api/event", {
          kind,
          file: path.basename(file),
          chars: String(text).length,
          text: String(text).slice(0, 800)
        });
        if (r && r.locked) {
          const alertMsg = "Вставка готового кода из нейросети заблокирована! Панель заморожена — обратись к учителю.";
          vscode.window.showErrorMessage(alertMsg);
          this.toast(alertMsg);
          return this.pollState();
        }
      } catch (e) {
        /* оффлайн или ошибка сети */
      }
    }
    const msg = kind === "ai_paste_blocked"
      ? "Вставка готового кода из нейросети заблокирована! Панель заморожена — обратись к учителю."
      : kind === "outside_edit"
        ? "Файл меняли не в редакторе курса — вернул твою версию. Пиши код здесь."
        : this.fromHintOrSample(text)
          ? "Код из подсказки или образца вставлять нельзя — перепечатай его сам, так он лучше запомнится 🙂"
          : "Готовый код вставлять нельзя — напиши сам 🙂 Копировать можно свой код, примеры из «Учебника» и «Шпаргалки».";
    vscode.window.showWarningMessage(msg);
    this.toast(msg);
  }

  // ---------------------------------------------------------------- сохранение работы на сервере
  onSave(doc) {
    if (this.isGuarded(doc.uri.fsPath)) {
      this.trust(doc.uri.fsPath, doc.getText());
      this.guard.snapshot(doc.uri.fsPath, doc.getText());
    }
    if (!this.token) return;
    if (F.isInside(doc.uri.fsPath, path.join(this.root(), F.WORK))) {
      clearTimeout(this.uploadTimer);
      this.uploadTimer = setTimeout(() => this.upload(), 1500);
    }
  }

  async upload() {
    if (!this.token) return;
    const files = F.collectWork(this.root());
    if (!files.length) return;
    try { await this.api("POST", "/api/files", { files }); } catch (e) { /* без связи: отправим при следующем сохранении */ }
  }

  async flushPending() {
    while (this.pending.length) {
      const item = this.pending[0];
      const r = await this.api("POST", "/api/result", item);
      if (r.solution) this.v.solutions[item.task_id] = { code: r.solution, bonus: r.bonus };
      this.pending.shift();
    }
  }

  // ---------------------------------------------------------------- панель
  showPanel() {
    if (this.panel) {
      this.panel.reveal(vscode.ViewColumn.Two, true);
      return;
    }
    const media = vscode.Uri.joinPath(this.ctx.extensionUri, "media");
    this.panel = vscode.window.createWebviewPanel("kurs", "Курс", { viewColumn: vscode.ViewColumn.Two, preserveFocus: true },
      { enableScripts: true, retainContextWhenHidden: true, localResourceRoots: [media] });
    this.panel.iconPath = vscode.Uri.joinPath(media, "icon.svg");
    const w = this.panel.webview;
    const nonce = Array.from({ length: 24 }, () => Math.floor(Math.random() * 36).toString(36)).join("");
    const html = fs.readFileSync(path.join(this.ctx.extensionPath, "media", "panel.html"), "utf8")
      .replace(/{{csp}}/g, w.cspSource)
      .replace(/{{nonce}}/g, nonce)
      .replace("{{css}}", w.asWebviewUri(vscode.Uri.joinPath(media, "panel.css")).toString())
      .replace("{{js}}", w.asWebviewUri(vscode.Uri.joinPath(media, "panel.js")).toString())
      .replace("{{play}}", w.asWebviewUri(vscode.Uri.joinPath(media, "play.js")).toString())
      // игры по сети класса: панель подключается к серверу курса напрямую (WebSocket)
      .replace("{{connect}}", this.server() ? `${this.server()} ${this.server().replace(/^http/, "ws")}` : "'none'");
    w.html = html;
    w.onDidReceiveMessage((m) => this.onMessage(m).catch((e) => this.toast(e.message)));
    this.panel.onDidDispose(() => { this.panel = null; });
    this.render();
  }

  setScreen(screen, message) {
    this.v.screen = screen;
    this.v.message = message || "";
    this.render();
  }

  render() {
    // для игр по сети: адрес канала партии и ключ сеанса (панель входит в партию от имени ученика)
    this.v.playWs = this.server().replace(/^http/, "ws") + "/ws/play";
    this.v.playAuth = this.token || "";
    if (this.panel) this.panel.webview.postMessage({ type: "view", view: this.v });
  }

  toast(text) {
    if (this.panel) this.panel.webview.postMessage({ type: "toast", text });
    else vscode.window.showInformationMessage(text);
  }

  updateStatus() {
    if (this.v.me) this.status.text = `$(mortar-board) Курс: ${this.v.me.name}`;
    else this.status.text = "$(mortar-board) Курс";
    this.status.tooltip = "Открыть панель курса";
    this.status.show();
  }

  refreshFiles() {
    const files = {};
    if (this.v.lesson) for (const t of this.v.lesson.tasks) files[t.id] = fs.existsSync(this.taskFile(t));
    this.v.files = files;
    this.v.notebookExists = this.v.lesson ? fs.existsSync(this.notebookPath()) : false;
  }

  onEditor(ed) {
    if (ed && ed.document.languageId === "python") this.lastPyEditor = ed;
    const t = ed ? this.taskForPath(ed.document.uri.fsPath) : null;
    vscode.commands.executeCommand("setContext", "kurs.isTaskFile", !!t);
    // большие кнопки под кодом: ученику не нужно искать маленькие значки
    if (ed && ed.document.languageId === "python" && this.token) this.runBtn.show(); else this.runBtn.hide();
    if (t && this.token) this.checkBtn.show(); else this.checkBtn.hide();
  }

  /** Подчёркивает строку с ошибкой в редакторе и пишет объяснение по-русски. */
  markError(file, err) {
    const uri = vscode.Uri.file(file);
    if (!err || !err.line) { this.diag.delete(uri); return; }
    const line = Math.max(0, err.line - 1);
    const text = err.code_line || "";
    const start = text.length - text.trimStart().length;
    const range = new vscode.Range(line, start, line, Math.max(start + 1, text.length));
    const d = new vscode.Diagnostic(range, `${err.title}: ${err.text}`, vscode.DiagnosticSeverity.Error);
    d.source = "Курс";
    this.diag.set(uri, [d]);
  }

  taskForPath(file) {
    if (!this.v.lesson) return null;
    return this.v.lesson.tasks.find((t) => path.resolve(this.taskFile(t)) === path.resolve(file)) || null;
  }

  // ---------------------------------------------------------------- команды из панели
  async onMessage(m) {
    switch (m.cmd) {
      case "ready": return this.render();
      case "retry": return this.boot();
      case "setServer": return this.setServer(m.server);
      case "login": return this.login(m.student_id);
      case "notMe": this.v.here = null; return this.setScreen("pick", "");
      case "backToPick": return this.boot();
      case "cancelWait": this.request = null; return this.boot();
      case "createFile": return this.createFile(m.task);
      case "openFile": return this.openTaskFile(m.task);
      case "run": return this.runTask(m.task);
      case "check": return this.checkTask(m.task);
      case "hint": return this.hint(m.task, m.level);
      case "reset": return this.resetTask(m.task);
      case "rate": await this.api("POST", "/api/rating", { task_id: m.task, rating: m.rating }); return this.pollState();
      case "compareSolution": return this.compareSolution(m.task);
      case "loadSolution": return this.loadSolution(m.task);
      case "help": await this.api("POST", "/api/help", { text: m.text || "" }); return this.pollState();
      case "helpCancel": await this.api("POST", "/api/help", { cancel: true }); return this.pollState();
      case "openNotebook": return this.openNotebook();
      case "runNotebook": return this.runPath(this.notebookPath());
      case "logout": return this.logout();
      case "playLobby": return this.playLobby();
      case "playInvite": return this.playAct("invite", { to: m.to, game: m.game });
      case "playAnswer": return this.playAct("answer", { id: m.id, accept: m.accept });
      case "playCancel": return this.playAct("cancel", { id: m.id });
      case "playLeave": return this.playAct("leave", {});
      case "aiChat": return this.handleAiChat(m);
      default: return undefined;
    }
  }

  // ---------------------------------------------------------------- ИИ-наставник / чат помощи
  async handleAiChat(m) {
    if (!this.panel) return;
    try {
      const messages = Array.isArray(m.messages) ? m.messages : [];
      let currentCode = "";
      let taskTitle = "";
      if (m.taskId) {
        const t = this.taskById(m.taskId);
        if (t) {
          taskTitle = `${t.num}. ${t.title}`;
          const file = this.taskFile(t);
          if (fs.existsSync(file)) {
            currentCode = fs.readFileSync(file, "utf-8").slice(0, 3500);
          }
        }
      }
      const systemPrompt = "Ты — дружелюбный школьный ИИ-наставник по Python курса «Чат-боты». Твоя задача — помочь ученику самостоятельно разобраться и решить задачу. Объясняй простыми словами на понятных примерах для начинающих. Если ученик спрашивает, где ошибка — укажи на опечатку или неверную команду, но не пиши готовое решение задания целиком. Подсказывай наводящими вопросами и показывай короткие примеры из 1-2 строк.";

      const payloadMessages = [
        { role: "system", content: systemPrompt + (currentCode ? `\n\n[Текущий файл задания ${taskTitle}]:\n\`\`\`python\n${currentCode}\n\`\`\`` : "") },
        ...messages
      ];

      const res = await this.api("POST", "/api/ai/ask", {
        messages: payloadMessages,
        temperature: 0.7,
        max_tokens: 1200
      });

      const tid = res.ticket;
      if (!tid) throw new Error("Сервер не вернул номер тикета ИИ");

      for (let i = 0; i < 60; i++) {
        await new Promise((r) => setTimeout(r, 600));
        const ticket = await this.api("GET", `/api/ai/ticket?id=${tid}`);
        if (ticket.status === "done") {
          this.panel.webview.postMessage({ type: "aiChatReply", message: ticket.message });
          return;
        } else if (ticket.status === "error") {
          this.panel.webview.postMessage({ type: "aiChatError", error: ticket.error || "Ошибка нейросети" });
          return;
        }
      }
      this.panel.webview.postMessage({ type: "aiChatError", error: "Нейросеть отвечает дольше обычного. Попробуй ещё раз." });
    } catch (e) {
      this.panel.webview.postMessage({ type: "aiChatError", error: e.message });
    }
  }

  // ---------------------------------------------------------------- игры по сети класса
  async playLobby() {
    if (!this.token || !this.panel) return;
    try {
      const lobby = await this.api("GET", "/api/play");
      this.panel.webview.postMessage({ type: "lobby", lobby });
    } catch (e) {
      this.panel.webview.postMessage({ type: "lobby", lobby: null, error: e.message });
    }
  }

  async playAct(action, body) {
    try {
      await this.api("POST", "/api/play/" + action, body);
    } catch (e) {
      this.toast(e.message);
    }
    await this.pollState();
    await this.playLobby();
  }

  async setServer(server) {
    server = String(server || "").trim();
    if (!/^https?:\/\//.test(server)) server = "http://" + server;
    const file = path.join(this.root(), F.HIDDEN, "config.json");
    const cfg = F.readJson(file, {});
    cfg.server = server.replace(/\/+$/, "");
    F.writeFile(file, JSON.stringify(cfg, null, 2));
    return this.boot();
  }

  async getTask(id) {
    if (!this.tasks[id]) this.tasks[id] = await this.api("GET", "/api/task?id=" + encodeURIComponent(id));
    return this.tasks[id];
  }

  async createFile(id) {
    const t = await this.getTask(id);
    const file = this.taskFile(t);
    if (!fs.existsSync(file)) {
      F.writeFile(file, t.start);
      this.trust(file, t.start);
    }
    this.refreshFiles();
    this.render();
    await this.openPath(file);
    this.upload();
  }

  async openTaskFile(id) {
    const t = this.taskById(id);
    if (t) await this.openPath(this.taskFile(t));
  }

  async openPath(file) {
    const doc = await vscode.workspace.openTextDocument(vscode.Uri.file(file));
    const ed = await vscode.window.showTextDocument(doc, { viewColumn: vscode.ViewColumn.One, preview: false });
    this.lastPyEditor = ed;
    this.keepPanelRight();
    return ed;
  }

  /** Код всегда слева, панель курса справа: если панель оказалась в одной группе с кодом, переносим её. */
  keepPanelRight() {
    if (this.panel && this.panel.viewColumn === vscode.ViewColumn.One) {
      this.panel.reveal(vscode.ViewColumn.Two, true);
    }
  }

  async saveIfOpen(file) {
    const doc = vscode.workspace.textDocuments.find((d) => path.resolve(d.uri.fsPath) === path.resolve(file));
    if (doc && doc.isDirty) await doc.save();
  }

  async resetTask(id) {
    const t = await this.getTask(id);
    const ok = await vscode.window.showWarningMessage("Начать заново? Твой код в этом файле пропадёт.", { modal: true }, "Начать заново");
    if (ok !== "Начать заново") return;
    const file = this.taskFile(t);
    const doc = vscode.workspace.textDocuments.find((d) => path.resolve(d.uri.fsPath) === path.resolve(file));
    this.guard.allow(t.start);
    if (doc) {
      const ed = await vscode.window.showTextDocument(doc, vscode.ViewColumn.One);
      await ed.edit((b) => b.replace(new vscode.Range(0, 0, doc.lineCount, 0), t.start));
      await doc.save();
    } else {
      F.writeFile(file, t.start);
      this.trust(file, t.start);
      await this.openPath(file);
    }
  }

  // --- запуск
  async runTask(id) {
    const t = this.taskById(id);
    if (t) await this.runPath(this.taskFile(t));
  }

  async runFile(uri) {
    const file = uri && uri.fsPath ? uri.fsPath : vscode.window.activeTextEditor && vscode.window.activeTextEditor.document.uri.fsPath;
    if (!file) return;
    await this.runPath(file);
  }

  async runPath(file) {
    if (this.isLocked()) return this.toast("Панель заблокирована — подожди, пока учитель разблокирует.");
    if (!fs.existsSync(file)) return this.toast("Сначала создай файл задания.");
    await this.saveIfOpen(file);
    if (this.runner) this.runner.dispose();
    this.diag.delete(vscode.Uri.file(file));
    const pty = new RunPty(this.python(), this.checker(), file, (err) => this.markError(file, err));
    this.runner = vscode.window.createTerminal({ name: "▶ " + path.basename(file), pty, iconPath: new vscode.ThemeIcon("play") });
    pty.terminal = this.runner;
    this.runner.show(false);
  }

  // --- проверка
  async checkFile(uri) {
    const file = uri && uri.fsPath ? uri.fsPath : vscode.window.activeTextEditor && vscode.window.activeTextEditor.document.uri.fsPath;
    const t = file ? this.taskForPath(file) : null;
    if (!t) return this.toast("Этот файл не относится к заданию. Открой задание в панели курса.");
    this.showPanel();
    if (this.panel) this.panel.webview.postMessage({ type: "select", task: t.id });
    return this.checkTask(t.id);
  }

  async checkTask(id) {
    if (this.isLocked()) return this.toast("Панель заблокирована — подожди, пока учитель разблокирует.");
    const t = await this.getTask(id);
    const file = this.taskFile(t);
    if (!fs.existsSync(file)) return this.toast("Сначала нажми «Создать файл для задания».");
    await this.saveIfOpen(file);
    const disk = fs.readFileSync(file, "utf8");
    const open = vscode.workspace.textDocuments.find((d) => path.resolve(d.uri.fsPath) === path.resolve(file));
    if (open && !open.isDirty && open.getText() === disk) this.trust(file, disk);   // текст из редактора курса
    else if (!this.isTrusted(file, disk)) {
      if (this.token) this.api("POST", "/api/event", { kind: "outside_edit", file: path.basename(file), chars: disk.length, text: disk.slice(0, 400) }).catch(() => {});
      await this.openPath(file);   // откроется — и вернётся версия ученика
      return this.toast("Этот файл меняли не в редакторе курса. Проверка принимает только код, написанный здесь.");
    }
    const taskJson = path.join(this.root(), F.HIDDEN, "tasks", id + ".json");
    F.writeFile(taskJson, JSON.stringify(t));
    this.v.busy = id;
    this.render();
    let res;
    try {
      res = await this.execChecker(taskJson, file);
    } catch (e) {
      this.v.busy = null;
      this.render();
      return this.toast(e.message);
    }
    this.v.busy = null;
    this.v.checks[id] = res;
    this.markError(file, res.ok ? null : res.error);
    this.render();
    const code = fs.readFileSync(file, "utf8");
    const item = { task_id: id, ok: res.ok, summary: res.summary, code };
    try {
      const r = await this.api("POST", "/api/result", item);
      if (r.solution) this.v.solutions[id] = { code: r.solution, bonus: r.bonus };
    } catch (e) {
      if (e.network) this.pending.push(item);
    }
    this.upload();
    await this.pollState();
  }

  execChecker(taskJson, file) {
    return new Promise((resolve, reject) => {
      cp.execFile(this.python(), [this.checker(), taskJson, file, "--json"],
        { timeout: 120000, maxBuffer: 4 * 1024 * 1024, env: Object.assign({}, process.env, { PYTHONIOENCODING: "utf-8", PYTHONUTF8: "1" }) },
        (err, stdout, stderr) => {
          if (err && err.code === "ENOENT") {
            reject(new Error(`Не найден Python (команда «${this.python()}»). Позови учителя.`));
            return;
          }
          try {
            resolve(JSON.parse(stdout));
          } catch (e) {
            reject(new Error("Проверка не сработала: " + (stderr || String(err)).slice(0, 300)));
          }
        });
    });
  }

  async hint(id, level) {
    const r = await this.api("POST", "/api/hint", { task_id: id, level });
    const list = this.v.hints[id] || [];
    list[level - 1] = r.text;
    this.v.hints[id] = list;
    await this.pollState();
  }

  async loadSolution(id) {
    if (this.v.solutions[id]) return;
    const r = await this.api("GET", "/api/solution?id=" + encodeURIComponent(id));
    this.v.solutions[id] = { code: r.solution, bonus: r.bonus };
    this.render();
  }

  async compareSolution(id) {
    const t = this.taskById(id);
    const sol = this.v.solutions[id];
    if (!t || !sol) return;
    const sample = path.join(this.root(), F.SAMPLE, "Задание_" + t.file);
    F.writeFile(sample, sol.code);
    await vscode.commands.executeCommand("vscode.diff", vscode.Uri.file(sample), vscode.Uri.file(this.taskFile(t)),
      `Образец ↔ моё решение: ${t.title}`, { viewColumn: vscode.ViewColumn.One });
    this.keepPanelRight();
  }

  // --- поле тренировки (песочница)
  notebookPath() {
    const trainingFile = path.join(this.workDir(), "Тренировка.py");
    const legacyFile = path.join(this.workDir(), `Тетрадь_урока_${this.lessonNum()}.py`);
    if (fs.existsSync(trainingFile)) return trainingFile;
    if (fs.existsSync(legacyFile)) return legacyFile;
    return trainingFile;
  }

  async openNotebook() {
    const file = this.notebookPath();
    if (!fs.existsSync(file)) {
      const template = (this.v.lesson && (this.v.lesson.training_template || this.v.lesson.notebook_template)) || "";
      F.writeFile(file, template);
      this.trust(file, template);
    }
    this.refreshFiles();
    this.render();
    await this.openPath(file);
    this.upload();
  }

  async logout() {
    const ok = await vscode.window.showWarningMessage("Выйти? Файлы сохранятся у учителя и исчезнут с этого компьютера.", { modal: true }, "Выйти");
    if (ok !== "Выйти") return;
    await this.upload();
    try { await this.api("POST", "/api/logout", {}); } catch (e) { /* всё равно выходим */ }
    await this.ended("Ты вышел. Чтобы войти снова, выбери своё имя.");
  }
}

/**
 * Терминал запуска программы ученика. В нём видно только то, что выводит программа, и то, что вводит ученик:
 * без длинных служебных команд. Ошибки объясняет kurs_check.py --run.
 */
class RunPty {
  constructor(python, checker, file, onError) {
    this.python = python;
    this.checker = checker;
    this.file = file;
    this.onError = onError;
    this.errFile = path.join(os.tmpdir(), `kurs-run-${process.pid}-${Date.now()}.json`);
    this.writeEmitter = new vscode.EventEmitter();
    this.closeEmitter = new vscode.EventEmitter();
    this.onDidWrite = this.writeEmitter.event;
    this.onDidClose = this.closeEmitter.event;
    this.line = "";
    this.proc = null;
  }

  write(text) {
    this.writeEmitter.fire(String(text).replace(/\r?\n/g, "\r\n"));
  }

  open() {
    this.write(`\x1b[1;34m▶ Запуск ${path.basename(this.file)}\x1b[0m\n`);
    this.proc = cp.spawn(this.python, ["-u", this.checker, "--run", this.file], {
      cwd: path.dirname(this.file),
      env: Object.assign({}, process.env, { PYTHONIOENCODING: "utf-8", PYTHONUTF8: "1", PYTHONUNBUFFERED: "1", KURS_ERROR_FILE: this.errFile }),
    });
    this.proc.stdout.setEncoding("utf8");
    this.proc.stderr.setEncoding("utf8");
    this.proc.stdout.on("data", (d) => this.write(d));
    this.proc.stderr.on("data", (d) => this.write(`\x1b[31m${d}\x1b[0m`));
    this.proc.on("error", (e) => {
      this.write(`\nНе получилось запустить Python (${this.python}): ${e.message}\nПозови учителя.\n`);
      this.proc = null;
    });
    this.proc.on("close", (code) => {
      if (!this.proc) return;
      this.proc = null;
      this.write(code === 0 ? "\n\x1b[2m— программа завершилась —\x1b[0m\n" : "\n\x1b[2m— программа остановилась —\x1b[0m\n");
      const err = F.readJson(this.errFile, null);
      fs.rmSync(this.errFile, { force: true });
      if (err && this.onError) this.onError(err);
    });
  }

  handleInput(data) {
    if (!this.proc) return;
    for (const ch of data) {
      if (ch === "\r") {
        this.write("\n");
        this.proc.stdin.write(this.line + "\n");
        this.line = "";
      } else if (ch === "\x7f" || ch === "\b") {
        if (this.line.length) {
          this.line = Array.from(this.line).slice(0, -1).join("");
          this.writeEmitter.fire("\b \b");
        }
      } else if (ch === "\x03") {
        this.write("^C\n");
        this.proc.kill("SIGINT");
      } else if (ch >= " ") {
        this.line += ch;
        this.writeEmitter.fire(ch);
      }
    }
  }

  close() {
    if (this.proc) this.proc.kill();
    this.proc = null;
  }
}

module.exports = { activate, deactivate };
