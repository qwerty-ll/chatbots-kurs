// Небольшой HTTP-клиент для сервера курса. Без зависимостей: только модули Node.
"use strict";
const http = require("http");
const https = require("https");

/**
 * Запрос к серверу курса. Возвращает {status, data}. При обрыве связи бросает ошибку с полем network = true.
 */
function request(base, method, path, body, token, timeoutMs) {
  return new Promise((resolve, reject) => {
    let url;
    try {
      url = new URL(path, base);
    } catch (e) {
      const err = new Error("Неверный адрес сервера: " + base);
      err.network = true;
      reject(err);
      return;
    }
    const payload = body === undefined ? null : Buffer.from(JSON.stringify(body), "utf8");
    const headers = { Accept: "application/json" };
    if (payload) {
      headers["Content-Type"] = "application/json";
      headers["Content-Length"] = String(payload.length);
    }
    if (token) headers["X-Kurs-Token"] = token;
    const lib = url.protocol === "https:" ? https : http;
    const req = lib.request(url, { method, headers, timeout: timeoutMs || 6000 }, (res) => {
      const chunks = [];
      res.on("data", (c) => chunks.push(c));
      res.on("end", () => {
        const text = Buffer.concat(chunks).toString("utf8");
        let data = {};
        try { data = text ? JSON.parse(text) : {}; } catch (e) { data = { error: text.slice(0, 200) }; }
        resolve({ status: res.statusCode, data });
      });
    });
    req.on("timeout", () => req.destroy(new Error("timeout")));
    req.on("error", (e) => {
      const err = new Error("Нет связи с сервером");
      err.network = true;
      err.cause = e;
      reject(err);
    });
    if (payload) req.write(payload);
    req.end();
  });
}

/** Ошибка API с HTTP-статусом и понятным текстом от сервера. */
class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

async function call(base, method, path, body, token) {
  const r = await request(base, method, path, body, token);
  if (r.status >= 400) throw new ApiError(r.status, (r.data && r.data.error) || "Ошибка " + r.status);
  return r.data;
}

module.exports = { request, call, ApiError };
