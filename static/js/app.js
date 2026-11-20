/* ============================================================
   PyDocent — front-end SPA logic
   ============================================================ */
"use strict";

const XP_PER_LEVEL = 150;

const state = {
  lessons: [],            // summaries
  progress: { xp: 0, completed: [], lessons: {} },
  current: null,          // full current lesson
  currentChallenge: null, // the challenge section of current lesson
  hintIndex: 0,
  attempts: 0,
  lastRunHadOutput: false,
  pythonReady: true,
};

let editor = null;
let loadingLesson = false;
let navigating = false;
let working = false;
let saveQueue = Promise.resolve(true);

/* ---------- tiny helpers ---------- */
const $ = (sel) => document.querySelector(sel);
const el = (tag, cls, html) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (html != null) n.innerHTML = html;
  return n;
};
const escapeHtml = (s) =>
  s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

// Lightweight static Python syntax highlighter for example snippets.
// Linear single-pass scanner (no catastrophic regex); matches the editor's
// Dracula theme via .t-* classes. Safe for our controlled lesson code.
const PY_KEYWORDS = new Set(["def", "return", "for", "while", "if", "elif", "else",
  "in", "and", "or", "not", "is", "import", "from", "as", "with", "class", "lambda",
  "break", "continue", "pass", "True", "False", "None", "try", "except", "finally", "global"]);
const PY_BUILTINS = new Set(["print", "input", "range", "len", "int", "str", "float",
  "type", "list", "dict", "tuple", "set", "bool", "sum", "min", "max", "abs",
  "round", "sorted", "append", "enumerate", "zip", "map"]);

function highlightPython(src) {
  const esc = (c) => (c === "&" ? "&amp;" : c === "<" ? "&lt;" : c === ">" ? "&gt;" : c);
  const escStr = (s) => s.replace(/[&<>]/g, esc);
  let out = "", i = 0;
  const n = src.length;
  while (i < n) {
    const c = src[i];
    if (c === "#") {                       // comment to end of line
      let j = i; while (j < n && src[j] !== "\n") j++;
      out += `<span class="t-com">${escStr(src.slice(i, j))}</span>`; i = j; continue;
    }
    if (c === "'" || c === '"') {           // string literal
      let j = i + 1; while (j < n && src[j] !== c) j++;
      j = Math.min(j + 1, n);
      out += `<span class="t-str">${escStr(src.slice(i, j))}</span>`; i = j; continue;
    }
    const prev = src[i - 1] || "";
    if (/[0-9]/.test(c) && !/[A-Za-z0-9_]/.test(prev)) {  // number
      let j = i; while (j < n && /[0-9.]/.test(src[j])) j++;
      out += `<span class="t-num">${src.slice(i, j)}</span>`; i = j; continue;
    }
    if (/[A-Za-z_]/.test(c)) {              // identifier / keyword / builtin
      let j = i; while (j < n && /[A-Za-z0-9_]/.test(src[j])) j++;
      const word = src.slice(i, j);
      if (PY_KEYWORDS.has(word)) out += `<span class="t-kw">${word}</span>`;
      else if (PY_BUILTINS.has(word)) out += `<span class="t-fn">${word}</span>`;
      else out += word;
      i = j; continue;
    }
    out += esc(c); i++;
  }
  return out;
}

// Minimal markdown: **bold**, `code`, and newlines.
function mdToHtml(text) {
  let t = escapeHtml(text);
  t = t.replace(/`([^`]+)`/g, "<code>$1</code>");
  t = t.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  t = t.replace(/\n/g, "<br>");
  return t;
}

/* ---------- Sound effects (synthesized — no audio files, fully offline) ----
   Uses the Web Audio API to generate short, pleasant blips and chimes. The
   AudioContext is created lazily on first interaction (browser autoplay rule).
*/
const sfx = {
  ctx: null,
  enabled: localStorage.getItem("tutor_sound") !== "off",
  _ensure() {
    if (!this.ctx) {
      try { this.ctx = new (window.AudioContext || window.webkitAudioContext)(); }
      catch (e) { this.ctx = null; }
    }
    if (this.ctx && this.ctx.state === "suspended") this.ctx.resume();
    return this.ctx;
  },
  _tone(freq, start, dur, type, gain) {
    const ctx = this.ctx;
    const osc = ctx.createOscillator();
    const g = ctx.createGain();
    osc.type = type || "sine";
    osc.frequency.value = freq;
    osc.connect(g); g.connect(ctx.destination);
    const t0 = ctx.currentTime + start;
    g.gain.setValueAtTime(0.0001, t0);
    g.gain.exponentialRampToValueAtTime(gain || 0.15, t0 + 0.015);
    g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
    osc.start(t0);
    osc.stop(t0 + dur + 0.03);
  },
  play(name) {
    if (!this.enabled) return;
    const ctx = this._ensure();
    if (!ctx) return;
    if (name === "run") {
      this._tone(520, 0, 0.07, "square", 0.06);
    } else if (name === "success") {
      [523.25, 659.25, 783.99].forEach((f, i) => this._tone(f, i * 0.09, 0.16, "sine", 0.16));
      this._tone(1046.5, 0.28, 0.22, "sine", 0.13);
    } else if (name === "level") {
      [392, 523.25, 659.25, 783.99, 1046.5].forEach((f, i) =>
        this._tone(f, i * 0.08, 0.2, "triangle", 0.15));
    } else if (name === "wrong") {
      this._tone(233, 0, 0.16, "sawtooth", 0.06);
      this._tone(196, 0.07, 0.2, "sawtooth", 0.05);
    } else if (name === "hint") {
      this._tone(880, 0, 0.06, "sine", 0.07);
    } else if (name === "nav") {
      this._tone(440, 0, 0.05, "sine", 0.05);
    }
  },
  toggle() {
    this.enabled = !this.enabled;
    localStorage.setItem("tutor_sound", this.enabled ? "on" : "off");
    if (this.enabled) this.play("hint");
    return this.enabled;
  },
};

/* ---------- API ----------
   Every request carries the per-launch token (injected by the server into
   the page). The server rejects state-changing requests without it, so a
   stale tab can't submit progress after the launcher restarts. */
const TUTOR_TOKEN = document.querySelector('meta[name="tutor-token"]').content;

async function api(path, opts) {
  opts = opts || {};
  const headers = Object.assign({ "X-Tutor-Token": TUTOR_TOKEN }, opts.headers || {});
  const res = await fetch(path, Object.assign({}, opts, { headers }));
  return res.json();
}



/* ---------- XP / level ---------- */
function levelFromXp(xp) { return Math.floor(xp / XP_PER_LEVEL) + 1; }

function renderXp(animate) {
  const xp = state.progress.xp || 0;
  const level = levelFromXp(xp);
  const into = xp % XP_PER_LEVEL;
  const pct = Math.round((into / XP_PER_LEVEL) * 100);
  $("#level-num").textContent = level;
  $("#xp-current").textContent = xp;
  $("#streak-num").textContent = (state.progress.completed || []).length;
  const fill = $("#xp-fill");
  if (!animate) fill.style.transition = "none";
  fill.style.width = pct + "%";
  if (!animate) requestAnimationFrame(() => (fill.style.transition = ""));
}

/* ---------- Sidebar ---------- */
function renderSidebar() {
  const list = $("#lesson-list");
  list.innerHTML = "";
  state.lessons.forEach((les) => {
    const done = (state.progress.completed || []).includes(les.id);
    const card = el("button", "lesson-card" + (done ? " done" : ""));
    card.type = "button";
    card.dataset.id = les.id;
    if (state.current && state.current.id === les.id) { card.classList.add("active"); card.setAttribute("aria-current", "page"); }
    card.innerHTML = `
      <span class="lc-emoji" aria-hidden="true">${les.emoji}</span>
      <div class="lc-text">
        <div class="lc-title">${escapeHtml(les.title)}</div>
        <div class="lc-meta">~${les.minutes} min · ${les.xp} XP</div>
      </div>
      <span class="lc-check" aria-hidden="true">✓</span>
      <span class="sr-only">${done ? "Completed" : "Not completed"}</span>`;
    card.addEventListener("click", () => openLesson(les.id));
    list.appendChild(card);
  });
}

/* ---------- Lesson rendering ---------- */
async function openLesson(id) {
  // Flush any pending autosave from the lesson we're leaving (state.current
  // still points at it here, so the payload is built for the right lesson).
  if (navigating || working) return;
  navigating = true;
  clearTimeout(autosaveTimer);
  if (state.current && state.currentChallenge && editor && !(await saveLessonWork())) {
    navigating = false;
    alert("Your work could not be saved. Please try again before changing lessons.");
    return;
  }
  let lesson;
  try { lesson = await api(`/api/lessons/${id}`); }
  catch (e) { navigating = false; alert("Could not load the lesson. Please try again."); return; }
  navigating = false;
  if (lesson.error) return;
  loadingLesson = true;
  state.current = lesson;
  state.currentChallenge = null;
  state.hintIndex = 0;
  state.attempts = 0;

  $("#welcome").classList.add("hidden");
  $("#lesson-view").classList.remove("hidden");
  $("#main").scrollTop = 0;

  $("#lesson-emoji").textContent = lesson.emoji || "📘";
  $("#lesson-title").textContent = lesson.title;
  $("#lesson-subtitle").textContent = lesson.subtitle || "";
  $("#lesson-xp-badge").textContent = `+${lesson.xp} XP`;

  renderSections(lesson);
  renderSidebar();
  setupNav(lesson.id);
  resetLab();

  // Restore this lesson's saved work (autosave) if the learner had some.
  if (lesson.saved && lesson.saved.code != null) {
    loadIntoEditor(lesson.saved.code);
    $("#stdin").value = lesson.saved.stdin || "";
    maybeToggleStdin();
  }
  loadingLesson = false;
  scheduleAutosave();
  $("#lesson-title").focus();
}

function renderSections(lesson) {
  const wrap = $("#sections");
  wrap.innerHTML = "";
  let firstRunnable = null;

  lesson.sections.forEach((sec) => {
    if (sec.type === "text") {
      wrap.appendChild(el("div", "sec sec-text", `<p>${mdToHtml(sec.content)}</p>`));
    } else if (sec.type === "example") {
      const node = el("div", "sec sec-example");
      node.innerHTML = `
        <div class="ex-label">${escapeHtml(sec.label || "Example")}</div>
        <div class="code-window">
          <div class="code-chrome">
            <span class="dot r"></span><span class="dot y"></span><span class="dot g"></span>
            <span class="code-lang">python</span>
          </div>
          <pre class="ex-code">${highlightPython(sec.code)}</pre>
        </div>
        <button class="ex-try">${/input\s*\(/.test(sec.code) ? "↓ Load in the lab" : "▶ Try this in the lab"}</button>`;
      node.querySelector(".ex-try").addEventListener("click", () => {
        if (!confirmReplace(sec.code)) return;
        loadIntoEditor(sec.code);
        if (/input\s*\(/.test(sec.code)) {
          $("#output").textContent = "Type your answer in Program input, then press Run.";
          $("#stdin").focus();
          $("#code-lab").scrollIntoView({ block: "start" });
        } else runCode();
      });
      if (firstRunnable === null) firstRunnable = sec.code;
      wrap.appendChild(node);
    } else if (sec.type === "challenge") {
      state.currentChallenge = sec;
      const node = el("div", "sec sec-challenge");
      node.innerHTML = `
        <span class="challenge-tag">🎯 Your Challenge</span>
        <p>${mdToHtml(sec.prompt)}</p>`;
      wrap.appendChild(node);
    } else if (sec.type === "extension") {
      const node = el("div", "sec sec-extension");
      node.innerHTML = `
        <span class="challenge-tag">🚀 ${escapeHtml(sec.title || "Extension")}</span>
        <p>${mdToHtml(sec.content)}</p>`;
      wrap.appendChild(node);
    }
  });

  // Pre-load the editor: challenge starter if present, else first example.
  if (state.currentChallenge) {
    loadIntoEditor(state.currentChallenge.starter || "");
    $("#challenge-bar").classList.remove("hidden");
  } else {
    loadIntoEditor(firstRunnable || "# Try some Python here!\n");
    $("#challenge-bar").classList.add("hidden");
  }
}

/* ---------- Code lab ---------- */
function ensureEditor() {
  if (editor) return;
  const cm = CodeMirror.fromTextArea($("#editor"), {
    mode: "python",
    theme: "dracula",
    lineNumbers: true,
    indentUnit: 4,
    tabSize: 4,
    indentWithTabs: false,
    screenReaderLabel: "Python code editor",
    extraKeys: {
      "Ctrl-Enter": runCode,
      Esc: () => $("#run-btn").focus(),
      Tab: () => ($("#stdin-wrap").classList.contains("hidden") ? $("#output") : $("#stdin")).focus(),
      "Shift-Tab": () => $("#run-btn").focus(),
    },
  });
  cm.getInputField().setAttribute("aria-describedby", "editor-help");
  const plain = $("#plain-editor");
  const toggle = $("#plain-mode");
  toggle.checked = localStorage.getItem("tutor_plain_editor") === "on";
  editor = {
    getValue: () => toggle.checked ? plain.value : cm.getValue(),
    setValue: (value) => { cm.setValue(value); plain.value = value; },
    clearHistory: () => cm.clearHistory(),
    setOption: (name, value) => { cm.setOption(name, value); if (name === "readOnly") plain.readOnly = !!value; },
  };
  function selectEditor() {
    const value = toggle.checked ? cm.getValue() : plain.value;
    if (toggle.checked) plain.value = value;
    else cm.setValue(value);
    plain.classList.toggle("hidden", !toggle.checked);
    cm.getWrapperElement().classList.toggle("hidden", toggle.checked);
    if (!toggle.checked) cm.refresh();
    localStorage.setItem("tutor_plain_editor", toggle.checked ? "on" : "off");
    maybeToggleStdin();
  }
  cm.on("change", () => { if (!toggle.checked) { maybeToggleStdin(); scheduleAutosave(); } });
  plain.addEventListener("input", () => { if (toggle.checked) { maybeToggleStdin(); scheduleAutosave(); } });
  plain.addEventListener("keydown", (event) => {
    if (event.ctrlKey && event.key === "Enter") { event.preventDefault(); runCode(); }
  });
  toggle.addEventListener("change", selectEditor);
  selectEditor();
}

function loadIntoEditor(code) {
  ensureEditor();
  editor.setValue(code);
  editor.clearHistory();
  maybeToggleStdin();
  scheduleAutosave();
}

function maybeToggleStdin() {
  const usesInput = /input\s*\(/.test(editor ? editor.getValue() : "");
  $("#stdin-wrap").classList.toggle("hidden", !usesInput);
}

/* ---------- Autosave (debounced) ----------
   While a lesson with a challenge is open, we quietly save the learner's
   code + input to the server a moment after they stop typing, so a crash
   or closed tab never loses their work. */
let autosaveTimer = null;

function scheduleAutosave() {
  if (loadingLesson || !state.current || !state.currentChallenge) return;
  clearTimeout(autosaveTimer);
  autosaveTimer = setTimeout(saveLessonWork, 1200);
}

async function saveLessonWork() {
  if (!state.current || !state.currentChallenge || !editor) return true;
  const payload = { lesson_id: state.current.id, code: editor.getValue(), stdin: $("#stdin").value };
  setSaveStatus("saving");
  saveQueue = saveQueue.catch(() => false).then(async () => { try {
    const res = await api("/api/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    setSaveStatus(res && res.state === "saved" ? "saved" : "error",
      res && res.message);
    return !!(res && res.state === "saved");
  } catch (e) {
    setSaveStatus("error", "Could not finish the request. Please try again.");
    return false;
  } });
  return saveQueue;
}

function confirmReplace(code) {
  return !editor || editor.getValue() === code || !editor.getValue().trim() ||
    (state.currentChallenge && editor.getValue() === (state.currentChallenge.starter || "")) ||
    confirm("Replace the code in the editor? Your current code will be overwritten.");
}

function setSaveStatus(status, message) {
  const s = $("#save-status");
  if (!s) return;
  s.textContent = status === "saving" ? "saving…"
    : status === "saved" ? "✓ saved" : "⚠ save failed";
  s.title = message || "";
  s.classList.toggle("error", status === "error");
}

function resetLab() {
  $("#output").innerHTML =
    '<span class="output-placeholder">▸ Click Run to see your code come alive.</span>';
  $("#run-status").textContent = "";
  $("#hint-box").classList.add("hidden");
  $("#hint-box").innerHTML = "";
  $("#solution-btn").classList.add("hidden");
  $("#hint-btn").disabled = false;
  $("#hint-btn").textContent = "💡 Hint";
  $("#stdin").value = "";
  const s = $("#save-status");
  if (s) { s.textContent = ""; s.classList.remove("error"); }
}

function executeInBrowser(code, stdin, check = null) {
  if (code.length > 100000 || stdin.length > 10000) {
    return Promise.resolve({error: "That code or input is too long."});
  }
  const frame = $("#execution-frame");
  const origin = new URL(frame.src).origin;
  const id = Array.from(crypto.getRandomValues(new Uint8Array(16)), n =>
    n.toString(16).padStart(2, "0")).join("");
  const stop = $("#stop-btn");
  stop.hidden = false;
  return new Promise(resolve => {
    function complete(result) {
      clearTimeout(timer);
      removeEventListener("message", receive);
      stop.onclick = null;
      stop.hidden = true;
      resolve(result);
    }
    function receive(event) {
      if (event.source !== frame.contentWindow || event.origin !== origin ||
          event.data?.id !== id) return;
      const result = event.data.result;
      if (typeof result?.error === "string") {
        complete({error: result.error.slice(0, 250)});
      } else if (typeof result?.stdout === "string" && typeof result?.stderr === "string") {
        const tests = Array.isArray(result.tests) ? result.tests.slice(0, 30)
          .filter(test => typeof test?.message === "string")
          .map(test => ({ok: test.ok === true, message: test.message.slice(0, 250)})) : [];
        complete({stdout: result.stdout.slice(0, 4100), stderr: result.stderr.slice(0, 4100),
          exit_code: result.exit_code, passed: result.passed === true, tests});
      } else {
        complete({error: "Python returned an unreadable result."});
      }
    }
    const timer = setTimeout(() => {
      frame.contentWindow.postMessage({id, stop: true}, origin);
      complete({error: "Python did not respond. Try again."});
    }, 38000);
    stop.onclick = () => frame.contentWindow.postMessage({id, stop: true}, origin);
    addEventListener("message", receive);
    frame.contentWindow.postMessage({id, code, stdin, check}, origin);
  });
}

async function runCode() {
  if (working || navigating) return;
  working = true;
  ensureEditor();
  const code = editor.getValue();
  const stdin = $("#stdin").value;
  const out = $("#output");
  const runBtn = $("#run-btn");
  const restoreFocus = document.activeElement === runBtn;

  sfx.play("run");
  runBtn.disabled = true;
  $("#run-status").textContent = "running…";
  out.innerHTML = '<span class="output-placeholder">running…</span>';

  let res;
  try {
    res = await executeInBrowser(code, stdin);
    if (res.error) res.stderr = res.error;
  } catch (e) {
    res = { stdout: "", stderr: "Could not finish the request. Please try again.", exit_code: -1 };
  }

  runBtn.disabled = false;
  if (restoreFocus) runBtn.focus();
  working = false;
  $("#run-status").textContent = "";

  const parts = [];
  if (res.stdout) parts.push(escapeHtml(res.stdout));
  if (res.stderr) parts.push(`<span class="err">${escapeHtml(res.stderr)}</span>`);
  state.lastRunHadOutput = !!(res.stdout && res.stdout.trim());

  if (parts.length === 0) {
    out.innerHTML = '<span class="output-placeholder">(no output — try adding a print())</span>';
  } else {
    out.innerHTML = parts.join("\n");
  }
  return res;
}

/* ---------- Browser challenge checking ---------- */
async function checkAnswer() {
  const ch = state.currentChallenge;
  if (!ch || !state.current || working || navigating) return;
  working = true;
  const checkBtn = $("#check-btn");
  const restoreFocus = document.activeElement === checkBtn;
  checkBtn.disabled = true;
  ensureEditor();
  editor.setOption("readOnly", true);
  $("#stdin").disabled = true;
  clearTimeout(autosaveTimer);
  if (!(await saveLessonWork())) { $("#run-status").textContent = "Could not save your work. Try again."; checkBtn.disabled = false; if (restoreFocus) checkBtn.focus(); editor.setOption("readOnly", false); $("#stdin").disabled = false; working = false; return; }
  $("#run-status").textContent = "checking…";

  let res;
  try {
    res = await executeInBrowser(editor.getValue(), $("#stdin").value, ch.check);
    if (res.passed) {
      const saved = await api("/api/complete", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({lesson_id: state.current.id}),
      });
      Object.assign(res, saved);
    }
  } catch (e) {
    res = { error: "Could not finish the request. Please try again." };
  }
  checkBtn.disabled = false;
  if (restoreFocus) checkBtn.focus();
  editor.setOption("readOnly", false);
  $("#stdin").disabled = false;
  working = false;
  state.attempts += 1;

  if (res.error) {
    sfx.play("wrong");
    $("#run-status").innerHTML = `<span class="err">${escapeHtml(res.error)}</span>`;
    return;
  }

  const parts = [];
  if (res.stdout) parts.push(escapeHtml(res.stdout));
  if (res.stderr) parts.push(`<span class="err">${escapeHtml(res.stderr)}</span>`);
  $("#output").innerHTML = parts.length ? parts.join("\n") : '<span class="output-placeholder">(no output)</span>';

  // Show the detailed pass/fail breakdown for every check.
  const box = $("#hint-box");
  box.innerHTML = "";
  box.classList.remove("hidden");
  (res.tests || []).forEach((t) => {
    box.appendChild(el("div", "check-line " + (t.ok ? "pass" : "fail"),
      (t.ok ? "✅ " : "✗ ") + escapeHtml(t.message)));
  });

  if (res.passed) {
    onChallengePass(res);
  } else {
    sfx.play("wrong");
    $("#run-status").innerHTML = '<span class="err">Not quite yet — fix the ✗ checks below!</span>';
    if (state.attempts >= 2) $("#solution-btn").classList.remove("hidden");
  }
}

function onChallengePass(res) {
  const xp = (res && res.xp_awarded) || 0;
  const prevLevel = levelFromXp(state.progress.xp || 0);
  if (res && res.progress) state.progress = res.progress;
  $("#run-status").innerHTML = '<span class="ok">✓ Correct! Nice work!</span>';
  renderXp(true);
  renderSidebar();

  if (xp > 0) {
    const newLevel = levelFromXp(state.progress.xp || 0);
    if (newLevel > prevLevel) {
      sfx.play("level");
      showToast(`🎉 Level ${newLevel}! +${xp} XP`);
    } else {
      sfx.play("success");
      showToast(`+${xp} XP earned!`);
    }
    fireConfetti();
  } else if (res && res.save_error) {
    // Passed, but the server couldn't persist the XP — say so honestly.
    $("#run-status").innerHTML = `<span class="err">${escapeHtml(res.save_error)}</span>`;
    sfx.play("wrong");
  } else {
    sfx.play("success");
    fireConfetti();
  }
}

/* ---------- Hints ---------- */
function showHint() {
  const ch = state.currentChallenge;
  if (!ch || !ch.hints || ch.hints.length === 0) return;
  sfx.play("hint");
  const box = $("#hint-box");
  box.classList.remove("hidden");
  if (state.hintIndex < ch.hints.length) {
    const line = el("div", "hint-line", `💡 ${mdToHtml(ch.hints[state.hintIndex])}`);
    box.appendChild(line);
    state.hintIndex += 1;
  }
  if (state.hintIndex >= ch.hints.length) {
    const hadFocus = document.activeElement === $("#hint-btn");
    $("#hint-btn").textContent = "💡 No more hints";
    $("#hint-btn").disabled = true;
    $("#solution-btn").classList.remove("hidden");
    if (hadFocus) $("#solution-btn").focus();
  }
}

function showSolution() {
  const ch = state.currentChallenge;
  if (!ch || !ch.solution) return;
  if (!confirmReplace(ch.solution)) return;
  loadIntoEditor(ch.solution);
  const box = $("#hint-box");
  box.classList.remove("hidden");
  box.appendChild(el("div", "hint-line",
    "✅ Here's one correct solution — read it, then hit <strong>Check my answer</strong>."));
}

/* ---------- Navigation ---------- */
function setupNav(id) {
  const idx = state.lessons.findIndex((l) => l.id === id);
  const prev = $("#prev-btn");
  const next = $("#next-btn");
  prev.disabled = idx <= 0;
  next.disabled = idx >= state.lessons.length - 1;
  next.textContent = idx >= state.lessons.length - 1 ? "🎉 All done!" : "Next lesson →";
  prev.onclick = () => idx > 0 && openLesson(state.lessons[idx - 1].id);
  next.onclick = () => idx < state.lessons.length - 1 && openLesson(state.lessons[idx + 1].id);
}

/* ---------- Toast + confetti ---------- */
let toastTimer = null;
function showToast(sub) {
  const t = $("#toast");
  $("#toast-sub").textContent = sub;
  t.classList.remove("hidden");
  requestAnimationFrame(() => t.classList.add("show"));
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    t.classList.remove("show");
    setTimeout(() => t.classList.add("hidden"), 500);
  }, 3200);
}

function fireConfetti() {
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const canvas = $("#confetti");
  const ctx = canvas.getContext("2d");
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;
  const colors = ["#00d4ff", "#7c3aed", "#22c55e", "#f59e0b", "#ec4899"];
  const pieces = Array.from({ length: 140 }, () => ({
    x: Math.random() * canvas.width,
    y: -20 - Math.random() * canvas.height * 0.3,
    r: 4 + Math.random() * 6,
    c: colors[(Math.random() * colors.length) | 0],
    vy: 2 + Math.random() * 4,
    vx: -2 + Math.random() * 4,
    rot: Math.random() * Math.PI,
    vr: -0.2 + Math.random() * 0.4,
  }));
  let frames = 0;
  function tick() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    pieces.forEach((p) => {
      p.x += p.vx; p.y += p.vy; p.rot += p.vr; p.vy += 0.05;
      ctx.save();
      ctx.translate(p.x, p.y);
      ctx.rotate(p.rot);
      ctx.fillStyle = p.c;
      ctx.fillRect(-p.r / 2, -p.r / 2, p.r, p.r * 0.6);
      ctx.restore();
    });
    frames += 1;
    if (frames < 160) requestAnimationFrame(tick);
    else ctx.clearRect(0, 0, canvas.width, canvas.height);
  }
  tick();
}

/* ---------- Reset ---------- */
async function resetProgress() {
  if (working || navigating) return;
  if (!confirm("Reset completed lessons and XP? Your saved code will be kept.")) return;
  clearTimeout(autosaveTimer);
  if (!(await saveLessonWork())) { alert("Could not save your work. Please try again."); return; }
  const result = await api("/api/progress/reset", {method: "POST"});
  if (!result.ok) { alert("Could not reset progress. Please try again."); return; }
  state.progress = await api("/api/progress");
  renderXp(true);
  renderSidebar();
}

async function eraseWork() {
  if (working || navigating) return;
  if (!confirm("Erase all saved code, input and progress for this copy? Close other tutor tabs first. Copies exported or backed up elsewhere are separate.")) return;
  working = true;
  clearTimeout(autosaveTimer);
  try {
    const result = await api("/api/progress/erase", {method: "POST"});
    if (!result.ok) throw new Error();
    location.reload();
  } catch {
    alert("Some saved work could not be erased. Please try again.");
    working = false;
  }
}

/* ---------- Sound toggle + Quit ---------- */
function renderSoundBtn() {
  const btn = $("#sound-btn");
  if (!btn) return;
  btn.textContent = sfx.enabled ? "🔊 Sound on" : "🔇 Sound off";
  btn.classList.toggle("muted", !sfx.enabled);
}

async function quitApp() {
  if (working || navigating) return;
  if (!confirm("Close PyDocent?")) return;
  clearTimeout(autosaveTimer);
  if (!(await saveLessonWork())) { alert("Your work could not be saved. Please try again before quitting."); return; }
  try {
    await api("/api/quit", { method: "POST" });
  } catch (e) { /* server is going down; ignore */ }
  $("#closed-overlay").classList.remove("hidden");
  $(".skip-link").classList.add("hidden");
  $("#app").inert = true;
  $("#closed-heading").focus();
}

/* ---------- Boot ---------- */
async function boot() {
  const data = await api("/api/lessons");
  state.lessons = data.lessons || [];
  state.progress = data.progress || { xp: 0, completed: [], lessons: {} };
  state.pythonReady = data.python_ready !== false;
  renderXp(false);
  renderSidebar();

  const resumeId = data.last_opened;
  if (state.lessons.some((lesson) => lesson.id === resumeId)) $("#start-btn").textContent = "▶ Continue learning";
  $("#start-btn").addEventListener("click", () => {
    if (state.lessons.length) openLesson(state.lessons.some((lesson) => lesson.id === resumeId) ? resumeId : state.lessons[0].id);
  });
  $("#run-btn").addEventListener("click", runCode);
  $("#check-btn").addEventListener("click", checkAnswer);
  $("#hint-btn").addEventListener("click", showHint);
  $("#solution-btn").addEventListener("click", showSolution);
  $("#reset-code").addEventListener("click", () => {
    if (state.currentChallenge && confirmReplace(state.currentChallenge.starter || "")) loadIntoEditor(state.currentChallenge.starter || "");
  });
  $("#stdin").addEventListener("input", scheduleAutosave);
  $("#erase-btn").addEventListener("click", eraseWork);
  $("#reset-btn").addEventListener("click", resetProgress);
  $("#sound-btn").addEventListener("click", () => { sfx.toggle(); renderSoundBtn(); });
  $("#quit-btn").addEventListener("click", quitApp);
  renderSoundBtn();

  if (!state.pythonReady) {
    $("#output").innerHTML =
      '<span class="err">⚠️ No Python interpreter was found to run code. ' +
      "If you're running the packaged app, install Python or use the bundled runtime.</span>";
  }
}

document.addEventListener("DOMContentLoaded", boot);
window.addEventListener("resize", () => {
  const c = $("#confetti");
  c.width = window.innerWidth; c.height = window.innerHeight;
});
