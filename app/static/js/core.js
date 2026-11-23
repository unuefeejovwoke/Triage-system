/* Shared code for every page: API calls, login session, layout, theme, and small helpers. */
"use strict";

/* ---------------------------------------------------------------- theme: light, dark, or system (applied before anything draws) */
const Theme = {
  media: window.matchMedia("(prefers-color-scheme: dark)"),
  get() { try { return localStorage.getItem("theme") || "dark"; } catch { return "dark"; } },
  resolved() { const t = this.get(); return t === "system" ? (this.media.matches ? "dark" : "light") : t; },
  apply() { document.documentElement.dataset.theme = this.resolved(); $$(".modes button").forEach((b) => b.classList.toggle("on", b.dataset.mode === this.get())); },
  set(t) { try { localStorage.setItem("theme", t); } catch {} this.apply(); },
};
document.documentElement.dataset.theme = Theme.resolved();
Theme.media.addEventListener?.("change", () => { if (Theme.get() === "system") Theme.apply(); });

/** Light / Dark / System switch. Call modeSwitch() to get its HTML, then bindModes(). */
function modeSwitch() {
  return `<div class="modes" role="radiogroup" aria-label="Colour mode">${[["light", "sun", "Light"], ["dark", "moon", "Dark"], ["system", "monitor", "System"]]
    .map(([m, i, l]) => `<button type="button" data-mode="${m}" role="radio" aria-label="${l} mode" title="${l}" class="${Theme.get() === m ? "on" : ""}">${icon(i, 14)}<span>${l}</span></button>`).join("")}</div>`;
}
function bindModes(root = document) { $$(".modes button", root).forEach((b) => (b.onclick = () => Theme.set(b.dataset.mode))); }

const TZ = "Africa/Lagos";
const LEVELS = {
  emergency: { label: "Emergency", rank: 1, cls: "em", icon: "siren", short: "Call 112 or go to the nearest emergency department now." },
  urgent:    { label: "Urgent",    rank: 2, cls: "ur", icon: "clock", short: "Go to a hospital or clinic today." },
  routine:   { label: "Routine",   rank: 3, cls: "ro", icon: "calendar", short: "Book a clinic appointment within the next few days." },
  self_care: { label: "Self-care", rank: 4, cls: "sc", icon: "home", short: "Safe to manage at home with care advice." },
};

/* ---------------------------------------------------------------- icons (16px, 1.75 stroke) */
const ICONS = {
  phone: '<path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1.9.4 1.8.7 2.7a2 2 0 0 1-.5 2.1L8 9.8a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.7.7a2 2 0 0 1 1.7 2z"/>',
  list: '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
  book: '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20V2H6.5A2.5 2.5 0 0 0 4 4.5v15z"/><path d="M8 7h8"/>',
  users: '<circle cx="9" cy="7" r="4"/><path d="M3 21v-2a4 4 0 0 1 4-4h4a4 4 0 0 1 4 4v2M16 3.1a4 4 0 0 1 0 7.8M21 21v-2a4 4 0 0 0-3-3.9"/>',
  shield: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/>',
  logout: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  check: '<path d="M20 6L9 17l-5-5"/>',
  x: '<path d="M18 6L6 18M6 6l12 12"/>',
  info: '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>',
  back: '<path d="M19 12H5M12 19l-7-7 7-7"/>',
  next: '<path d="M5 12h14M12 5l7 7-7 7"/>',
  chev: '<path d="M9 18l6-6-6-6"/>',
  alert: '<path d="M10.3 3.9L1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0zM12 9v4M12 17h.01"/>',
  siren: '<path d="M7 18v-6a5 5 0 1 1 10 0v6M5 21h14M12 3V1M4.2 5.2L3 4M19.8 5.2L21 4"/><path d="M5 18h14v3H5z"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  calendar: '<rect x="3" y="4" width="18" height="17" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>',
  home: '<path d="M3 10.5L12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/>',
  upload: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12"/>',
  key: '<circle cx="7.5" cy="15.5" r="4.5"/><path d="M21 2l-9.6 9.6M15.5 7.5l3 3L22 7l-3-3"/>',
  activity: '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
  monitor: '<rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  moon: '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21v-1a6 6 0 0 1 6-6h4a6 6 0 0 1 6 6v1"/>',
  edit: '<path d="M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/>',
  print: '<path d="M6 9V2h12v7M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/>',
  refresh: '<path d="M21 12a9 9 0 1 1-2.6-6.4L21 8M21 3v5h-5"/>',
  file: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/>',
  pulse: '<path d="M19 14c1.5-1.5 3-3.2 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.8 0-3 .5-4.5 2-1.5-1.5-2.7-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4 3 5.5l7 7z"/><path d="M3.5 12H8l1.5-3 3 6 1.5-3h6.5"/>',
};
const icon = (name, size = 16) => `<svg class="i" viewBox="0 0 24 24" style="width:${size}px;height:${size}px">${ICONS[name] || ""}</svg>`;
const levelIco = (lv, size = "") => lv ? `<span class="ico ${size} ${LEVELS[lv].cls}">${icon(LEVELS[lv].icon, size === "sm" ? 13 : 16)}</span>`
  : `<span class="ico ${size} mu">${icon("clock", size === "sm" ? 13 : 16)}</span>`;

/* ---------------------------------------------------------------- helpers */
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const levelPill = (lv) => (lv ? `<span class="lv ${lv}">${LEVELS[lv].label}</span>` : '<span class="pill">Open</span>');
const params = () => new URLSearchParams(location.search);
const sexLabel = (s) => ({ male: "Male", female: "Female", other: "Other", unknown: "Not stated" }[s] || s);

function fmtDate(iso, withTime = true) {
  if (!iso) return "—";
  const opts = { timeZone: TZ, day: "numeric", month: "short", year: "numeric" };
  if (withTime) Object.assign(opts, { hour: "2-digit", minute: "2-digit", hour12: false });
  return new Intl.DateTimeFormat("en-GB", opts).format(new Date(iso));
}
function fmtTime(iso) {
  return iso ? new Intl.DateTimeFormat("en-GB", { timeZone: TZ, hour: "2-digit", minute: "2-digit", hour12: false }).format(new Date(iso)) : "—";
}
function ago(iso) {
  const s = (Date.now() - new Date(iso)) / 1000;
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  if (s < 86400 * 7) return `${Math.floor(s / 86400)} d ago`;
  return fmtDate(iso, false);
}
function duration(a, b) {
  if (!a || !b) return "—";
  const s = Math.max(0, Math.round((new Date(b) - new Date(a)) / 1000));
  return `${Math.floor(s / 60)}m ${String(s % 60).padStart(2, "0")}s`;
}
/** Small trend line. values: numbers, oldest first. */
function sparkline(values, color = "var(--pri)") {
  const w = 84, h = 26, max = Math.max(1, ...values), n = Math.max(1, values.length - 1);
  const pts = values.map((v, i) => [(i / n) * w, h - 3 - (v / max) * (h - 6)]);
  const d = pts.map((p, i) => `${i ? "L" : "M"}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(" ");
  const id = "g" + Math.random().toString(36).slice(2, 8);
  return `<svg class="spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none"><defs><linearGradient id="${id}" x1="0" x2="0" y1="0" y2="1">
    <stop offset="0" stop-color="${color}" stop-opacity=".28"/><stop offset="1" stop-color="${color}" stop-opacity="0"/></linearGradient></defs>
    <path d="${d} L${w},${h} L0,${h} Z" fill="url(#${id})"/><path d="${d}" fill="none" stroke="${color}" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round"/></svg>`;
}

function toast(msg, isErr = false) {
  $$(".toast").forEach((t) => t.remove());
  const t = document.createElement("div");
  t.className = "toast" + (isErr ? " err" : "");
  t.innerHTML = icon(isErr ? "alert" : "check") + `<span>${esc(msg)}</span>`;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 4200);
}

function modal({ title, sub = "", body, actions = "", wide = false }) {
  const bg = document.createElement("div");
  bg.className = "modal-bg";
  bg.innerHTML = `<div class="modal ${wide ? "wide" : ""}" role="dialog" aria-modal="true">
      <header><div><h3>${esc(title)}</h3>${sub ? `<p>${esc(sub)}</p>` : ""}</div>
      <button class="x" data-close aria-label="Close">${icon("x")}</button></header>
      <div class="mb">${body}</div>${actions ? `<footer>${actions}</footer>` : ""}</div>`;
  const close = () => bg.remove();
  bg.addEventListener("click", (e) => { if (e.target === bg || e.target.closest("[data-close]")) close(); });
  document.addEventListener("keydown", function k(e) { if (e.key === "Escape") { close(); document.removeEventListener("keydown", k); } });
  document.body.appendChild(bg);
  const first = bg.querySelector("input:not([type=file]),select,textarea");
  if (first) first.focus();
  return { el: bg, close };
}

function apiError(detail) {
  if (!detail) return "Something went wrong.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((d) => {
    const field = (d.loc || []).filter((x) => x !== "body" && typeof x === "string").pop();
    const msg = (d.msg || "").replace(/^Value error, /, "");
    return field ? `${field.replace(/_/g, " ")}: ${msg}` : msg;
  }).join(" · ");
  if (detail.message) return detail.message;
  return JSON.stringify(detail);
}

/* ---------------------------------------------------------------- session and API */
const Session = {
  get token() { return sessionStorage.getItem("token"); },
  get user() { try { return JSON.parse(sessionStorage.getItem("user")); } catch { return null; } },
  save(token, user) { sessionStorage.setItem("token", token); sessionStorage.setItem("user", JSON.stringify(user)); },
  clear() { sessionStorage.removeItem("token"); sessionStorage.removeItem("user"); },
};

async function api(path, { method = "GET", body, form } = {}) {
  const headers = {};
  if (Session.token) headers.Authorization = `Bearer ${Session.token}`;
  let payload;
  if (form) payload = new URLSearchParams(form);
  else if (body !== undefined) { headers["Content-Type"] = "application/json"; payload = JSON.stringify(body); }
  const res = await fetch(path, { method, headers, body: payload });
  if (res.status === 401 && !path.startsWith("/auth/login")) {
    Session.clear();
    location.href = "/ui/login.html?expired=1";
    throw new Error("Session expired");
  }
  const data = res.status === 204 ? null : await res.json().catch(() => null);
  if (!res.ok) { const err = new Error(apiError(data?.detail)); err.status = res.status; err.detail = data?.detail; throw err; }
  return data;
}

/* ---------------------------------------------------------------- layout */
const NAV = [
  { href: "/ui/triage.html", label: "New consultation", icon: "phone", roles: ["nurse"] },
  { href: "/ui/consultations.html", label: "Consultations", icon: "list", roles: ["nurse", "admin"] },
  { href: "/ui/protocols.html", label: "Protocols", icon: "book", roles: ["nurse", "admin"] },
  { sep: true, roles: ["admin"] },
  { href: "/ui/users.html", label: "Users", icon: "users", roles: ["admin"] },
  { href: "/ui/audit.html", label: "Audit log", icon: "shield", roles: ["admin"] },
];

/** Builds the icon rail and top bar. Call at the start of every logged-in page. */
function layout({ crumb, roles = ["nurse", "admin"] }) {
  const user = Session.user;
  if (!Session.token || !user) { location.href = "/ui/login.html"; throw new Error("Not logged in"); }
  if (!roles.includes(user.role)) { location.href = home(user.role); throw new Error("Wrong role"); }
  const page = location.pathname;
  const initials = user.full_name.split(/\s+/).map((w) => w[0]).slice(0, 2).join("").toUpperCase();
  const nav = NAV.filter((n) => n.roles.includes(user.role)).map((n) => n.sep ? '<span class="sep"></span>'
    : `<a href="${n.href}" class="${page === n.href ? "on" : ""}" aria-label="${n.label}">${icon(n.icon, 17)}<span class="tip">${n.label}</span></a>`).join("");
  const shell = document.createElement("div");
  shell.className = "shell";
  shell.innerHTML = `
    <aside class="rail">
      <a class="brand" href="${home(user.role)}" aria-label="Home" style="width:34px;height:34px">T.</a>
      ${nav}

    </aside>
    <div class="main">
      <header class="top">
        <div class="crumb"><span class="ws"><i></i>Triage</span><span class="sl">/</span>${crumb}</div>
        <form class="search" id="gsearch"><input placeholder="Search consultations, e.g. C-000012" aria-label="Search">${icon("search", 15)}<kbd>/</kbd></form>
        <div class="tr"><span id="chips" style="display:flex;gap:8px"></span>${modeSwitch()}
          <div class="menu" id="menu"><button class="ib" style="border:0;background:none;width:auto;padding:0" aria-label="Account"><span class="avatar">${esc(initials)}</span></button>
            <div class="pop"><div class="who"><b>${esc(user.full_name)}</b><span>${user.role === "admin" ? "Administrator" : "Nurse"}</span></div>
              <button id="logout">${icon("logout")} Sign out</button></div></div>
        </div>
      </header>
      <main class="body" id="page"></main>
    </div>`;
  document.body.prepend(shell);
  $("#logout").onclick = () => { Session.clear(); location.href = "/ui/login.html"; };
  $("#menu > button").onclick = (e) => { e.stopPropagation(); $("#menu").classList.toggle("open"); };
  document.addEventListener("click", () => $("#menu")?.classList.remove("open"));
  bindModes(shell);
  $("#gsearch").onsubmit = (e) => { e.preventDefault(); const q = $("#gsearch input").value.trim(); location.href = `/ui/consultations.html${q ? "?q=" + encodeURIComponent(q) : ""}`; };
  document.addEventListener("keydown", (e) => {
    if (e.key === "/" && !["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName)) { e.preventDefault(); $("#gsearch input").focus(); }
  });
  return $("#page");
}

function home(role) { return role === "admin" ? "/ui/consultations.html" : "/ui/triage.html"; }

/* ---------------------------------------------------------------- idle sign-out (NDPA: protect unattended screens) */
const IDLE_MINUTES = 15;
(function idleWatch() {
  if (location.pathname.endsWith("/login.html")) return;
  let last = Date.now(), warned = false;
  const bump = () => { last = Date.now(); if (warned) { warned = false; $$(".toast").forEach((t) => t.remove()); } };
  ["mousemove", "keydown", "click", "scroll", "touchstart"].forEach((e) => document.addEventListener(e, bump, { passive: true }));
  setInterval(() => {
    if (!Session.token) return;
    const idle = (Date.now() - last) / 60000;
    if (idle >= IDLE_MINUTES) { Session.clear(); location.href = "/ui/login.html?idle=1"; }
    else if (idle >= IDLE_MINUTES - 1 && !warned) { warned = true; toast("You will be signed out in 1 minute because of inactivity. Move the mouse to stay signed in."); }
  }, 15000);
})();
