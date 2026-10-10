// Игры по сети класса: шахматы, морской бой, аэрохоккей — в панели ученика и на пульте учителя.
// Правила считают сами игроки, сервер только пересылает ходы (WebSocket /ws/play).
// Можно играть и с компьютером — тогда сеть не нужна.
"use strict";
(function () {
  const TITLES = { chess: "♟️ Шахматы", hockey: "🏒 Аэрохоккей", battleship: "🚢 Морской бой" };
  const REACTIONS = ["👍", "😮", "🤝", "😅"];

  function el(tag, attrs, ...kids) {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === null || v === undefined || v === false) continue;
      if (k === "class") e.className = v;
      else if (k === "style") e.setAttribute("style", v);
      else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
      else e.setAttribute(k, v === true ? "" : v);
    }
    for (const kid of kids.flat(Infinity)) if (kid !== null && kid !== undefined && kid !== false) e.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
    return e;
  }
  const rnd = (n) => Math.floor(Math.random() * n);

  // оформление игр — одно и то же в панели ученика и на пульте
  const CSS = `
.play-host { display: flex; flex-direction: column; gap: 8px; }
.play-head { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; font-weight: 600; }
.play-vs { color: #6B7280; font-weight: 500; }
.play-bubble { font-size: 22px; min-width: 1em; }
.play-status { font-weight: 600; margin: 4px 0; }
.play-game { display: flex; flex-direction: column; align-items: center; gap: 6px; }
.play-row { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.play-row .spacer { flex: 1; }
.play-done { background: #E8F5EE; color: #1F6B45; border-radius: 10px; padding: 10px 12px; font-weight: 600; }
.play-done.hidden { display: none; }
.play-help { font-size: 12px; color: #6B7280; margin: 0; text-align: center; }
.chess { display: grid; grid-template-columns: repeat(8, 40px); border-radius: 8px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,.15); }
.chess .sq { width: 40px; height: 40px; border: 0; padding: 0; margin: 0; font-size: 30px; line-height: 40px; cursor: pointer; position: relative; border-radius: 0;
  font-family: "DejaVu Sans", "Segoe UI Symbol", "Noto Sans Symbols2", "Apple Symbols", serif; font-variant-emoji: text; }
.chess .sq:hover { filter: brightness(1.05); }
.chess .light { background: #E9EEE2; } .chess .dark { background: #7FA37A; }
.chess .last { box-shadow: inset 0 0 0 40px rgba(63,179,127,.35); }
.chess .sel { box-shadow: inset 0 0 0 3px #1F6B45; }
.chess .dot::after { content: ""; position: absolute; left: 15px; top: 15px; width: 10px; height: 10px; border-radius: 50%; background: rgba(0,0,0,.28); }
.chess .hit { box-shadow: inset 0 0 0 3px rgba(229,72,77,.8); }
.chess .check { background: #F2A7A9; }
.chess .pw { color: #FFFFFF; -webkit-text-stroke: 0.8px #374151; text-shadow: 0 1px 2px rgba(0,0,0,.35); } .chess .pb { color: #111827; }
.play-host button { border-radius: 8px; }
.play-host button.secondary { background: #FFFFFF; color: #1F2937; border: 1.5px solid #D1D5DB; }
.play-host button.secondary:hover { background: #F3F4F6; }
.bs-wrap { display: flex; flex-wrap: wrap; gap: 14px; justify-content: center; }
.bs-title { font-size: 12px; color: #6B7280; margin-bottom: 4px; text-align: center; }
.bs { display: grid; gap: 1px; background: #CBD5E1; border: 1px solid #CBD5E1; }
.bs.enemy { grid-template-columns: repeat(10, 24px); } .bs.mine { grid-template-columns: repeat(10, 14px); }
.bs > * { width: 24px; height: 24px; border: 0; padding: 0; margin: 0; background: #F4F7FA; border-radius: 0; }
.bs.mine > * { width: 14px; height: 14px; }
.bs.enemy > button:not([disabled]) { cursor: crosshair; } .bs.enemy > button:not([disabled]):hover { background: #DDE7F0; }
.bs .ship { background: #64748B; } .bs .miss { background: #E2E8F0; } .bs .miss::after { content: "·"; color: #64748B; }
.bs .hit { background: #E5484D; } .bs .sunk { background: #7F1D1D; }
.hockey { border-radius: 12px; touch-action: none; cursor: none; max-width: 100%; }
`;
  if (document.head && !document.getElementById("kurs-play-css")) {
    const st = document.createElement("style");
    st.id = "kurs-play-css";
    st.textContent = CSS;
    document.head.appendChild(st);
  }

  // =====================================================================  ШАХМАТЫ
  const Chess = (function () {
    const N = { n: [-17, -15, -10, -6, 6, 10, 15, 17] };
    const isW = (p) => p && p === p.toUpperCase();
    const colorOf = (p) => (p ? (isW(p) ? "w" : "b") : null);
    const rc = (i) => [i >> 3, i & 7];
    const at = (r, c) => (r >= 0 && r < 8 && c >= 0 && c < 8 ? r * 8 + c : -1);
    const VAL = { p: 100, n: 300, b: 320, r: 500, q: 900, k: 0 };

    function start() {
      const back = "rnbqkbnr";
      const b = new Array(64).fill("");
      for (let c = 0; c < 8; c++) { b[c] = back[c]; b[8 + c] = "p"; b[48 + c] = "P"; b[56 + c] = back[c].toUpperCase(); }
      return { b, turn: "w", castle: { K: true, Q: true, k: true, q: true }, ep: -1 };
    }

    function attacked(b, sq, by) {
      const [r, c] = rc(sq);
      const P = by === "w" ? "P" : "p";
      const dir = by === "w" ? 1 : -1;   // белая пешка бьёт вверх: стоит ниже клетки
      for (const dc of [-1, 1]) { const i = at(r + dir, c + dc); if (i >= 0 && b[i] === P) return true; }
      const pc = (x) => (by === "w" ? x.toUpperCase() : x);
      for (const [dr, dc] of [[-2, -1], [-2, 1], [-1, -2], [-1, 2], [1, -2], [1, 2], [2, -1], [2, 1]]) {
        const i = at(r + dr, c + dc); if (i >= 0 && b[i] === pc("n")) return true;
      }
      for (const [dr, dc] of [[-1, -1], [-1, 0], [-1, 1], [0, -1], [0, 1], [1, -1], [1, 0], [1, 1]]) {
        const i = at(r + dr, c + dc); if (i >= 0 && b[i] === pc("k")) return true;
      }
      const ray = (dirs, kinds) => {
        for (const [dr, dc] of dirs) {
          let rr = r + dr, cc = c + dc;
          while (at(rr, cc) >= 0) {
            const p = b[at(rr, cc)];
            if (p) { if (colorOf(p) === by && kinds.includes(p.toLowerCase())) return true; break; }
            rr += dr; cc += dc;
          }
        }
        return false;
      };
      return ray([[-1, 0], [1, 0], [0, -1], [0, 1]], "rq") || ray([[-1, -1], [-1, 1], [1, -1], [1, 1]], "bq");
    }

    function pseudo(s) {
      const out = [];
      const me = s.turn;
      const them = me === "w" ? "b" : "w";
      for (let i = 0; i < 64; i++) {
        const p = s.b[i];
        if (!p || colorOf(p) !== me) continue;
        const [r, c] = rc(i);
        const t = p.toLowerCase();
        const add = (to, extra) => out.push(Object.assign({ from: i, to }, extra || {}));
        if (t === "p") {
          const d = me === "w" ? -1 : 1;
          const last = me === "w" ? 0 : 7;
          const one = at(r + d, c);
          if (one >= 0 && !s.b[one]) {
            add(one, r + d === last ? { promo: "q" } : null);
            const startRow = me === "w" ? 6 : 1;
            const two = at(r + 2 * d, c);
            if (r === startRow && !s.b[two]) add(two, { double: true });
          }
          for (const dc of [-1, 1]) {
            const x = at(r + d, c + dc);
            if (x < 0) continue;
            if (s.b[x] && colorOf(s.b[x]) === them) add(x, r + d === last ? { promo: "q" } : null);
            else if (x === s.ep) add(x, { ep: true });
          }
        } else if (t === "n" || t === "k") {
          const steps = t === "n" ? [[-2, -1], [-2, 1], [-1, -2], [-1, 2], [1, -2], [1, 2], [2, -1], [2, 1]]
            : [[-1, -1], [-1, 0], [-1, 1], [0, -1], [0, 1], [1, -1], [1, 0], [1, 1]];
          for (const [dr, dc] of steps) {
            const x = at(r + dr, c + dc);
            if (x >= 0 && colorOf(s.b[x]) !== me) add(x);
          }
          if (t === "k") {
            const row = me === "w" ? 7 : 0;
            const K = me === "w" ? "K" : "k", Q = me === "w" ? "Q" : "q";
            if (i === at(row, 4) && !attacked(s.b, i, them)) {
              if (s.castle[K] && !s.b[at(row, 5)] && !s.b[at(row, 6)] && !attacked(s.b, at(row, 5), them) && !attacked(s.b, at(row, 6), them))
                add(at(row, 6), { castle: "k" });
              if (s.castle[Q] && !s.b[at(row, 3)] && !s.b[at(row, 2)] && !s.b[at(row, 1)] && !attacked(s.b, at(row, 3), them) && !attacked(s.b, at(row, 2), them))
                add(at(row, 2), { castle: "q" });
            }
          }
        } else {
          const dirs = t === "r" ? [[-1, 0], [1, 0], [0, -1], [0, 1]] : t === "b" ? [[-1, -1], [-1, 1], [1, -1], [1, 1]]
            : [[-1, 0], [1, 0], [0, -1], [0, 1], [-1, -1], [-1, 1], [1, -1], [1, 1]];
          for (const [dr, dc] of dirs) {
            let rr = r + dr, cc = c + dc;
            while (at(rr, cc) >= 0) {
              const x = at(rr, cc);
              if (!s.b[x]) add(x);
              else { if (colorOf(s.b[x]) !== me) add(x); break; }
              rr += dr; cc += dc;
            }
          }
        }
      }
      return out;
    }

    function apply(s, m) {
      const b = s.b.slice();
      const p = b[m.from];
      const castle = Object.assign({}, s.castle);
      b[m.to] = m.promo ? (s.turn === "w" ? m.promo.toUpperCase() : m.promo) : p;
      b[m.from] = "";
      if (m.ep) b[m.to + (s.turn === "w" ? 8 : -8)] = "";
      if (m.castle) {
        const row = s.turn === "w" ? 7 : 0;
        if (m.castle === "k") { b[at(row, 5)] = b[at(row, 7)]; b[at(row, 7)] = ""; }
        else { b[at(row, 3)] = b[at(row, 0)]; b[at(row, 0)] = ""; }
      }
      if (p.toLowerCase() === "k") { if (s.turn === "w") castle.K = castle.Q = false; else castle.k = castle.q = false; }
      for (const [sq, key] of [[63, "K"], [56, "Q"], [7, "k"], [0, "q"]]) if (m.from === sq || m.to === sq) castle[key] = false;
      return { b, turn: s.turn === "w" ? "b" : "w", castle, ep: m.double ? (m.from + m.to) / 2 : -1 };
    }

    function kingSq(b, color) { return b.indexOf(color === "w" ? "K" : "k"); }
    function inCheck(s) { return attacked(s.b, kingSq(s.b, s.turn), s.turn === "w" ? "b" : "w"); }
    function legal(s) {
      return pseudo(s).filter((m) => { const n = apply(s, m); return !attacked(n.b, kingSq(n.b, s.turn), n.turn); });
    }
    function status(s) {
      const moves = legal(s);
      const pieces = s.b.filter((p) => p);
      if (!moves.length) return inCheck(s) ? "mate" : "stalemate";
      if (pieces.length === 2) return "draw";
      return inCheck(s) ? "check" : "";
    }

    // компьютер: перебор на 2 хода вперёд по ценности фигур, с долей случайности — его можно обыграть
    function evaluate(s) {
      let v = 0;
      for (let i = 0; i < 64; i++) {
        const p = s.b[i];
        if (!p) continue;
        const [r, c] = rc(i);
        const center = 6 - Math.abs(3.5 - r) - Math.abs(3.5 - c);
        const val = VAL[p.toLowerCase()] + (p.toLowerCase() === "p" || p.toLowerCase() === "n" ? center * 4 : 0);
        v += isW(p) ? val : -val;
      }
      return v;
    }
    function search(s, depth, alpha, beta) {
      const moves = legal(s);
      if (!moves.length) return inCheck(s) ? (s.turn === "w" ? -99999 : 99999) : 0;
      if (!depth) return evaluate(s);
      const max = s.turn === "w";
      let best = max ? -Infinity : Infinity;
      for (const m of moves) {
        const v = search(apply(s, m), depth - 1, alpha, beta);
        if (max) { best = Math.max(best, v); alpha = Math.max(alpha, v); } else { best = Math.min(best, v); beta = Math.min(beta, v); }
        if (beta <= alpha) break;
      }
      return best;
    }
    function bestMove(s) {
      const moves = legal(s);
      let best = null, bestV = Infinity;
      for (const m of moves) {
        const v = search(apply(s, m), 2, -Infinity, Infinity) + Math.random() * 40;
        if (v < bestV) { bestV = v; best = m; }
      }
      return best;
    }

    // одинаковые «сплошные» фигуры для обеих сторон, цвет — через оформление (так белые лучше видны на доске)
    const GLYPH = { K: "♚", Q: "♛", R: "♜", B: "♝", N: "♞", P: "♟", k: "♚", q: "♛", r: "♜", b: "♝", n: "♞", p: "♟" };

    function game(ctx) {
      let s = start();
      const mine = ctx.you === 0 ? "w" : "b";
      let sel = -1, last = null, over = false;
      const board = el("div", { class: "chess" });
      const info = el("div", { class: "play-status" });
      const box = el("div", { class: "play-game" }, info, board);

      function draw() {
        const st = status(s);
        const targets = sel >= 0 ? legal(s).filter((m) => m.from === sel).map((m) => m.to) : [];
        const cells = [];
        for (let k = 0; k < 64; k++) {
          const i = mine === "w" ? k : 63 - k;
          const [r, c] = rc(i);
          const p = s.b[i];
          const cls = ["sq", (r + c) % 2 ? "dark" : "light"];
          if (i === sel) cls.push("sel");
          if (last && (i === last.from || i === last.to)) cls.push("last");
          if (targets.includes(i)) cls.push(p ? "hit" : "dot");
          if ((st === "check" || st === "mate") && p === (s.turn === "w" ? "K" : "k")) cls.push("check");
          cells.push(el("button", { class: cls.join(" "), onclick: () => click(i) }, p ? el("span", { class: isW(p) ? "pw" : "pb" }, GLYPH[p]) : ""));
        }
        board.replaceChildren(...cells);
        const yourTurn = s.turn === mine;
        if (st === "mate") { over = true; info.textContent = yourTurn ? "Мат. Победил соперник" : "Мат! Ты победил 🎉"; }
        else if (st === "stalemate" || st === "draw") { over = true; info.textContent = "Ничья"; }
        else info.textContent = (yourTurn ? "Твой ход" : "Ход соперника") + (st === "check" ? " · Шах!" : "") + ` · ты играешь ${mine === "w" ? "белыми" : "чёрными"}`;
        if (over) ctx.finished(info.textContent);
      }
      function play(m, send) {
        s = apply(s, m);
        last = m;
        sel = -1;
        if (send) ctx.send({ type: "move", from: m.from, to: m.to, promo: m.promo || null });
        draw();
      }
      function click(i) {
        if (over || s.turn !== mine) return;
        if (sel >= 0) {
          const m = legal(s).find((x) => x.from === sel && x.to === i);
          if (m) return play(m, true);
        }
        sel = s.b[i] && colorOf(s.b[i]) === mine ? i : -1;
        draw();
      }
      function onMessage(msg) {
        if (msg.type !== "move") return;
        const m = legal(s).find((x) => x.from === msg.from && x.to === msg.to);
        if (m) play(m, false);
      }
      draw();
      return { box, onMessage, stop() {}, ai: { reply(msg, answer) {        // компьютер играет чёрными
        if (msg.type !== "move" || over) return;
        setTimeout(() => { const m = bestMove(s); if (m) answer({ type: "move", from: m.from, to: m.to, promo: m.promo || null }); }, 350);
      } } };
    }
    return { game, start, legal, apply, status };
  })();

  // =====================================================================  МОРСКОЙ БОЙ
  const Battleship = (function () {
    const FLEET = [4, 3, 3, 2, 2, 2, 1, 1, 1, 1];
    function place() {
      for (;;) {
        const g = Array.from({ length: 10 }, () => new Array(10).fill(-1));
        let ok = true;
        FLEET.forEach((len, id) => {
          if (!ok) return;
          for (let tries = 0; tries < 300; tries++) {
            const h = Math.random() < 0.5;
            const x = rnd(h ? 11 - len : 10), y = rnd(h ? 10 : 11 - len);
            const cells = Array.from({ length: len }, (_, k) => (h ? [x + k, y] : [x, y + k]));
            const free = cells.every(([cx, cy]) => {
              for (let dx = -1; dx <= 1; dx++) for (let dy = -1; dy <= 1; dy++) {
                const nx = cx + dx, ny = cy + dy;
                if (nx >= 0 && ny >= 0 && nx < 10 && ny < 10 && g[ny][nx] >= 0) return false;
              }
              return true;
            });
            if (free) { cells.forEach(([cx, cy]) => { g[cy][cx] = id; }); return; }
          }
          ok = false;
        });
        if (ok) return g;
      }
    }
    // ответ на выстрел по своему полю: попал ли, потоплен ли корабль, все ли потоплены
    function answer(fleet, hits, x, y) {
      const id = fleet[y][x];
      hits[y][x] = true;
      if (id < 0) return { x, y, hit: false };
      const cells = [];
      for (let yy = 0; yy < 10; yy++) for (let xx = 0; xx < 10; xx++) if (fleet[yy][xx] === id) cells.push([xx, yy]);
      const sunk = cells.every(([cx, cy]) => hits[cy][cx]);
      let all = true;
      for (let yy = 0; yy < 10; yy++) for (let xx = 0; xx < 10; xx++) if (fleet[yy][xx] >= 0 && !hits[yy][xx]) all = false;
      return { x, y, hit: true, sunk: sunk ? cells : null, win: all };
    }

    function game(ctx) {
      const saved = ctx.store.get("fleet");
      let fleet = saved || place();
      const myHits = Array.from({ length: 10 }, () => new Array(10).fill(false));     // куда стрелял соперник
      const enemy = Array.from({ length: 10 }, () => new Array(10).fill(""));         // что я знаю о поле соперника: miss/hit/sunk
      let phase = saved ? "wait" : "place";
      const ready = [false, false];
      let turn = 0, over = false, pending = false;
      const info = el("div", { class: "play-status" });
      const mineEl = el("div", { class: "bs mine" });
      const enemyEl = el("div", { class: "bs enemy" });
      const controls = el("div", { class: "row play-row" });
      const box = el("div", { class: "play-game" }, info, el("div", { class: "bs-wrap" },
        el("div", {}, el("div", { class: "bs-title" }, "Поле соперника — стреляй сюда"), enemyEl),
        el("div", {}, el("div", { class: "bs-title" }, "Твой флот"), mineEl)), controls,
        el("p", { class: "play-help" }, "Попал — стреляешь ещё раз. Потопил корабль — клетки вокруг отмечаются сами."));

      function draw() {
        mineEl.replaceChildren(...Array.from({ length: 100 }, (_, k) => {
          const x = k % 10, y = (k / 10) | 0;
          const ship = fleet[y][x] >= 0, shot = myHits[y][x];
          return el("i", { class: (ship ? "ship " : "") + (shot ? (ship ? "hit" : "miss") : "") });
        }));
        enemyEl.replaceChildren(...Array.from({ length: 100 }, (_, k) => {
          const x = k % 10, y = (k / 10) | 0;
          const v = enemy[y][x];
          return el("button", { class: v, disabled: v || phase !== "play" || turn !== ctx.you || over || pending ? true : null, onclick: () => shoot(x, y) });
        }));
        controls.replaceChildren();
        if (phase === "place") {
          info.textContent = "Расставь флот: «Перемешать», пока не понравится, потом «Готов»";
          controls.append(el("button", { class: "secondary small", onclick: () => { fleet = place(); draw(); } }, "🔀 Перемешать"),
            el("button", { class: "small", onclick: readyUp }, "✓ Готов"));
        } else if (phase === "wait") info.textContent = "Ждём, пока соперник расставит флот…";
        else if (!over) info.textContent = turn === ctx.you ? "Твой выстрел — нажми на клетку поля соперника" : "Стреляет соперник…";
      }
      function readyUp() {
        ctx.store.set("fleet", fleet);
        phase = "wait";
        ready[ctx.you] = true;
        ctx.send({ type: "ready" });
        maybeStart();
      }
      function maybeStart() { if (ready[0] && ready[1] && phase !== "place") phase = "play"; draw(); }
      function shoot(x, y) {
        if (phase !== "play" || turn !== ctx.you || over || pending || enemy[y][x]) return;
        pending = true;
        ctx.send({ type: "shot", x, y });
        draw();
      }
      function mark(r) {   // результат моего выстрела
        pending = false;
        enemy[r.y][r.x] = r.hit ? "hit" : "miss";
        if (r.sunk) {
          for (const [x, y] of r.sunk) enemy[y][x] = "sunk";
          for (const [x, y] of r.sunk) for (let dx = -1; dx <= 1; dx++) for (let dy = -1; dy <= 1; dy++) {
            const nx = x + dx, ny = y + dy;
            if (nx >= 0 && ny >= 0 && nx < 10 && ny < 10 && !enemy[ny][nx]) enemy[ny][nx] = "miss";
          }
        }
        if (!r.hit) turn = 1 - ctx.you;
        if (r.win) { over = true; info.textContent = "Весь флот соперника потоплен! Ты победил 🎉"; ctx.finished(info.textContent); }
      }
      function onMessage(msg, replay) {
        if (msg.type === "ready") { ready[msg.by] = true; maybeStart(); return; }
        if (msg.type === "shot" && msg.by !== ctx.you) {
          const r = answer(fleet, myHits, msg.x, msg.y);
          if (!replay) ctx.send(Object.assign({ type: "result" }, r));
          if (!r.hit) turn = ctx.you;
          if (r.win) { over = true; info.textContent = "Твой флот потоплен. Победил соперник"; ctx.finished(info.textContent); }
          draw();
          return;
        }
        if (msg.type === "result" && msg.by !== ctx.you) { mark(msg); draw(); }
      }
      draw();
      // компьютер: расставляет флот сам, стреляет «охотой» — после попадания добивает соседние клетки
      const cpu = { fleet: place(), hits: Array.from({ length: 10 }, () => new Array(10).fill(false)), tried: new Set(), targets: [] };
      function cpuShot(answerFn) {
        let x, y;
        while (cpu.targets.length) { [x, y] = cpu.targets.shift(); if (!cpu.tried.has(x + "," + y)) break; x = undefined; }
        if (x === undefined) do { x = rnd(10); y = rnd(10); } while (cpu.tried.has(x + "," + y));
        cpu.tried.add(x + "," + y);
        cpu.last = [x, y];
        answerFn({ type: "shot", x, y });
      }
      return { box, onMessage, stop() {}, ai: { reply(msg, answerFn) {
        if (msg.type === "ready") { answerFn({ type: "ready" }); return; }
        if (msg.type === "shot") {
          const r = answer(cpu.fleet, cpu.hits, msg.x, msg.y);
          setTimeout(() => {
            answerFn(Object.assign({ type: "result" }, r));
            if (!r.hit && !r.win) setTimeout(() => cpuShot(answerFn), 500);
          }, 250);
          return;
        }
        if (msg.type === "result") {
          if (msg.hit && !msg.sunk) for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
            const nx = msg.x + dx, ny = msg.y + dy;
            if (nx >= 0 && ny >= 0 && nx < 10 && ny < 10) cpu.targets.push([nx, ny]);
          }
          if (msg.sunk) {
            cpu.targets = [];
            for (const [x, y] of msg.sunk) for (let dx = -1; dx <= 1; dx++) for (let dy = -1; dy <= 1; dy++) cpu.tried.add((x + dx) + "," + (y + dy));
          }
          if (msg.hit && !msg.win) setTimeout(() => cpuShot(answerFn), 500);
        }
      } } };
    }
    return { game, place, answer };
  })();

  // =====================================================================  АЭРОХОККЕЙ
  const Hockey = (function () {
    const W = 1, H = 1.5, PR = 0.065, KR = 0.035, GOAL = 0.36, WIN = 7, MAXV = 0.045;
    function game(ctx) {
      const host = ctx.you === 0;          // у первого игрока считается физика, второй присылает свою клюшку
      const SCALE = 260;
      const canvas = el("canvas", { width: W * SCALE, height: H * SCALE, class: "hockey" });
      const info = el("div", { class: "play-status" });
      const box = el("div", { class: "play-game" }, info, canvas, el("p", { class: "play-help" }, "Води мышкой по своей половине (внизу). Забей 7 голов!"));
      const g = canvas.getContext("2d");
      let me = { x: 0.5, y: H - 0.2, vx: 0, vy: 0 }, foe = { x: 0.5, y: 0.2, vx: 0, vy: 0 };
      let puck = { x: 0.5, y: H / 2, vx: 0, vy: 0 };
      let score = [0, 0], over = false, target = { x: 0.5, y: H - 0.2 }, frame = 0, raf = null, lastSent = 0;

      function toWorld(e) {
        const r = canvas.getBoundingClientRect();
        return { x: ((e.clientX - r.left) / r.width) * W, y: ((e.clientY - r.top) / r.height) * H };
      }
      canvas.addEventListener("pointermove", (e) => { target = toWorld(e); });
      canvas.addEventListener("pointerdown", (e) => { target = toWorld(e); });
      const keys = {};
      const kd = (e) => { if (e.key.startsWith("Arrow")) { keys[e.key] = e.type === "keydown"; e.preventDefault(); } };
      window.addEventListener("keydown", kd);
      window.addEventListener("keyup", kd);

      function movePaddle(p, t, minY, maxY) {
        const k = 0.012;
        if (keys.ArrowLeft) t.x -= k * 3; if (keys.ArrowRight) t.x += k * 3; if (keys.ArrowUp) t.y -= k * 3; if (keys.ArrowDown) t.y += k * 3;
        t.x = Math.max(PR, Math.min(W - PR, t.x)); t.y = Math.max(minY, Math.min(maxY, t.y));
        const nx = p.x + Math.max(-0.05, Math.min(0.05, t.x - p.x));
        const ny = p.y + Math.max(-0.05, Math.min(0.05, t.y - p.y));
        p.vx = nx - p.x; p.vy = ny - p.y; p.x = nx; p.y = ny;
      }
      function collide(p) {
        const dx = puck.x - p.x, dy = puck.y - p.y, d = Math.hypot(dx, dy);
        if (d < PR + KR && d > 0) {
          const nx = dx / d, ny = dy / d;
          puck.x = p.x + nx * (PR + KR); puck.y = p.y + ny * (PR + KR);
          const rel = (puck.vx - p.vx) * nx + (puck.vy - p.vy) * ny;
          if (rel < 0) { puck.vx -= 1.9 * rel * nx; puck.vy -= 1.9 * rel * ny; }
          puck.vx += p.vx * 0.6; puck.vy += p.vy * 0.6;
        }
      }
      function physics() {
        puck.x += puck.vx; puck.y += puck.vy;
        puck.vx *= 0.994; puck.vy *= 0.994;
        const v = Math.hypot(puck.vx, puck.vy);
        if (v > MAXV) { puck.vx *= MAXV / v; puck.vy *= MAXV / v; }
        if (puck.x < KR) { puck.x = KR; puck.vx = Math.abs(puck.vx); }
        if (puck.x > W - KR) { puck.x = W - KR; puck.vx = -Math.abs(puck.vx); }
        const inGoal = Math.abs(puck.x - W / 2) < GOAL / 2;
        if (puck.y < KR && !inGoal) { puck.y = KR; puck.vy = Math.abs(puck.vy); }
        if (puck.y > H - KR && !inGoal) { puck.y = H - KR; puck.vy = -Math.abs(puck.vy); }
        collide(me); collide(foe);
        if (puck.y < -KR) goal(0);          // забил хозяин физики (его ворота внизу, чужие — вверху)
        else if (puck.y > H + KR) goal(1);
      }
      function goal(who) {
        score[who]++;
        puck = { x: 0.5, y: who === 0 ? H / 2 - 0.15 : H / 2 + 0.15, vx: 0, vy: 0 };
        if (score[who] >= WIN) {
          over = true;
          const text = (who === 0 ? ctx.names[0] : ctx.names[1]) + " победил со счётом " + Math.max(...score) + ":" + Math.min(...score);
          ctx.send({ type: "over", text });
          ctx.finished(text);
        }
      }
      function cpu() {   // компьютер: держится между шайбой и своими воротами, атакует на своей половине
        const t = { x: puck.x, y: puck.y < H / 2 ? puck.y - 0.05 : 0.18 };
        foe.vx = Math.max(-0.018, Math.min(0.018, t.x - foe.x));
        foe.vy = Math.max(-0.018, Math.min(0.018, t.y - foe.y));
        foe.x = Math.max(PR, Math.min(W - PR, foe.x + foe.vx));
        foe.y = Math.max(PR, Math.min(H / 2 - PR, foe.y + foe.vy));
      }
      const mirror = (p) => ({ x: W - p.x, y: H - p.y });
      function draw() {
        const S = SCALE;
        g.fillStyle = "#16202E"; g.fillRect(0, 0, W * S, H * S);
        g.strokeStyle = "rgba(255,255,255,.25)"; g.lineWidth = 2;
        g.beginPath(); g.moveTo(0, (H / 2) * S); g.lineTo(W * S, (H / 2) * S); g.stroke();
        g.beginPath(); g.arc((W / 2) * S, (H / 2) * S, 0.15 * S, 0, Math.PI * 2); g.stroke();
        g.fillStyle = "#E5484D"; g.fillRect(((W - GOAL) / 2) * S, 0, GOAL * S, 5);
        g.fillStyle = "#3FB37F"; g.fillRect(((W - GOAL) / 2) * S, H * S - 5, GOAL * S, 5);
        const circle = (p, r, col) => { g.fillStyle = col; g.beginPath(); g.arc(p.x * S, p.y * S, r * S, 0, Math.PI * 2); g.fill(); };
        circle(foe, PR, "#E5484D"); circle(me, PR, "#3FB37F"); circle(puck, KR, "#F1F1F1");
        const mine = host ? score[0] : score[1], theirs = host ? score[1] : score[0];
        info.textContent = over ? info.textContent : `Ты ${mine} : ${theirs} ${ctx.names[1 - ctx.you]}`;
      }
      function loop() {
        if (over) { draw(); return; }
        frame++;
        movePaddle(me, target, H / 2 + PR, H - PR);
        if (host) {
          if (ctx.cpu) cpu();
          physics();
          if (frame % 2 === 0) ctx.send({ type: "st", pk: [puck.x, puck.y], hp: [me.x, me.y], sc: score });
        } else if (frame % 2 === 0) ctx.send({ type: "pd", p: [me.x, me.y] });
        draw();
        raf = requestAnimationFrame(loop);
      }
      function onMessage(msg) {
        if (msg.type === "pd" && host) { const m = mirror({ x: msg.p[0], y: msg.p[1] }); foe.vx = m.x - foe.x; foe.vy = m.y - foe.y; foe.x = m.x; foe.y = m.y; }
        if (msg.type === "st" && !host) {
          puck = Object.assign(mirror({ x: msg.pk[0], y: msg.pk[1] }), { vx: 0, vy: 0 });
          const f = mirror({ x: msg.hp[0], y: msg.hp[1] }); foe.x = f.x; foe.y = f.y;
          score = msg.sc;
        }
        if (msg.type === "over") { over = true; info.textContent = msg.text; ctx.finished(msg.text); }
      }
      raf = requestAnimationFrame(loop);
      return { box, onMessage, stop() { over = true; cancelAnimationFrame(raf); window.removeEventListener("keydown", kd); window.removeEventListener("keyup", kd); },
        ai: { reply() {} } };
    }
    return { game };
  })();

  const GAMES = { chess: Chess.game, battleship: Battleship.game, hockey: Hockey.game };

  // =====================================================================  партия: сеть или компьютер
  const host = el("div", { class: "play-host" });
  let cur = null;

  function frame(opts, names) {
    const nameA = el("b", {}, names[0]), nameB = el("b", {}, names[1]);
    const bubble = el("span", { class: "play-bubble" });
    const head = el("div", { class: "play-head" }, el("span", {}, TITLES[opts.game]), el("span", { class: "play-vs" }, nameA, " — ", nameB), bubble);
    const gameBox = el("div", {});
    const done = el("div", { class: "play-done hidden" });
    const foot = el("div", { class: "row play-row" },
      opts.mode === "net" ? REACTIONS.map((r) => el("button", { class: "secondary small", onclick: () => cur && cur.send({ type: "react", e: r }) }, r)) : null,
      el("span", { class: "spacer" }),
      el("button", { class: "secondary small", onclick: () => {
        if (!cur) return;
        if (!cur.ended) {
          if (!confirm(opts.mode === "net" ? "Сдаться и выйти из партии?" : "Закончить игру?")) return;
          cur.send({ type: "resign" });
        }
        finish();
      } }, "Выйти"));
    host.replaceChildren(head, gameBox, done, foot);
    return { gameBox, bubble, done };
  }

  function finish() {
    if (!cur) return;
    const c = cur;
    c.close();
    cur = null;
    host.replaceChildren();
    if (c.opts.onEnd) c.opts.onEnd();
  }

  function start(opts) {
    stop();
    const names = opts.names || ["Ты", "Компьютер"];
    const ui = frame(opts, names);
    const store = {
      get: (k) => { try { return JSON.parse(localStorage.getItem(`kurs.play.${opts.matchId || "cpu"}.${k}`)); } catch (e) { return null; } },
      set: (k, v) => { try { localStorage.setItem(`kurs.play.${opts.matchId || "cpu"}.${k}`, JSON.stringify(v)); } catch (e) { /* без хранилища */ } },
    };
    if (opts.mode === "cpu") store.set("fleet", null);
    const c = { opts, ui, ended: false, game: null, ws: null, timer: null };
    const finished = (text) => { if (!c.ended) { c.ended = true; ui.done.textContent = text + " · «Выйти» — к списку игроков"; ui.done.classList.remove("hidden"); } };
    const make = (you, sendFn, isCpu) => {
      if (c.game) c.game.stop();
      c.game = GAMES[opts.game]({ you, names, send: sendFn, finished, store, cpu: isCpu });
      ui.gameBox.replaceChildren(c.game.box);
    };
    if (opts.mode === "cpu") {
      // компьютер отвечает от имени второго игрока
      const toPlayer = (msg) => { msg.by = 1; if (c.game) c.game.onMessage(msg); };
      c.send = (msg) => { msg.by = 0; if (c.game && c.game.ai) c.game.ai.reply(msg, toPlayer); };
      make(0, (m) => c.send(m), true);
      c.close = () => { if (c.game) c.game.stop(); };
    } else {
      let tries = 0;
      const connect = () => {
        const ws = new WebSocket(opts.url);
        c.ws = ws;
        ws.onopen = () => { tries = 0; ws.send(JSON.stringify({ auth: opts.auth || "" })); };
        ws.onmessage = (e) => {
          let msg;
          try { msg = JSON.parse(e.data); } catch (err) { return; }
          if (msg.type === "hello") {
            make(msg.you, (m) => c.send(m), false);
            for (const m of msg.log) c.game.onMessage(m, true);
            if (msg.over) finished(msg.over);
          } else if (msg.type === "stopped") { finished(msg.reason || "Партия окончена"); c.dead = true; ws.close(); }
          else if (msg.type === "resign") finished("Соперник сдался — победа за тобой 🎉");
          else if (msg.type === "gone") ui.bubble.textContent = "соперник отключился…";
          else if (msg.type === "joined") ui.bubble.textContent = "";
          else if (msg.type === "react") { ui.bubble.textContent = msg.e; setTimeout(() => { if (ui.bubble.textContent === msg.e) ui.bubble.textContent = ""; }, 2500); }
          else if (c.game) c.game.onMessage(msg, false);
        };
        ws.onclose = () => { if (!c.dead && cur === c && tries++ < 20) setTimeout(connect, 1500); };
      };
      c.send = (msg) => { if (c.ws && c.ws.readyState === 1) c.ws.send(JSON.stringify(msg)); };
      c.timer = setInterval(() => c.send({ type: "ping" }), 15000);
      c.close = () => { c.dead = true; clearInterval(c.timer); if (c.game) c.game.stop(); if (c.ws) c.ws.close(); };
      connect();
    }
    cur = c;
  }

  function stop() {
    if (cur) { cur.close(); cur = null; }
    host.replaceChildren();
  }

  window.KursPlay = {
    host, titles: TITLES, start, stop,
    current: () => (cur ? { game: cur.opts.game, matchId: cur.opts.matchId || null, mode: cur.opts.mode } : null),
    _test: { Chess, Battleship },
  };
})();
