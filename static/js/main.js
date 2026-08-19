/* ============================================================
   main.js — Основные скрипты системы управления нагрузкой
   ============================================================ */


/* ── Показать/скрыть пароль ──────────────────────────────── */
function togglePassword(inputId, iconId) {
  const input = document.getElementById(inputId);
  const icon  = document.getElementById(iconId);
  if (!input) return;

  if (input.type === 'password') {
    input.type   = 'text';
    icon.className = 'bi bi-eye-slash';
  } else {
    input.type   = 'password';
    icon.className = 'bi bi-eye';
  }
}


/* ── Проверка совпадения паролей (профиль) ───────────────── */
function checkPasswordMatch(newId, confirmId, hintId) {
  const np   = document.getElementById(newId);
  const cp   = document.getElementById(confirmId);
  const hint = document.getElementById(hintId);
  if (!np || !cp || !hint) return;

  const okText  = hint.dataset.match    || '✓';
  const badText = hint.dataset.mismatch || '✗';
  cp.addEventListener('input', function () {
    if (cp.value.length === 0) {
      hint.style.display = 'none';
      return;
    }
    hint.style.display = 'block';
    if (np.value === cp.value) {
      hint.textContent = okText;
      hint.style.color = 'var(--clr-green)';
    } else {
      hint.textContent = badText;
      hint.style.color = 'var(--clr-red)';
    }
  });
}


/* ── Автозаполнение макс. нагрузки по должности ─────────── */
function initPositionWorkload(selectId, inputId, workloads) {
  const select = document.getElementById(selectId);
  const input  = document.getElementById(inputId);
  if (!select || !input) return;

  select.addEventListener('change', function () {
    const pos = this.value;
    if (workloads[pos]) {
      input.value = workloads[pos];
    }
  });
}


/* ── Подтверждение удаления ──────────────────────────────── */
function confirmDelete(message) {
  return confirm(message || (window.I18N && window.I18N.confirmDel) || 'Подтвердите удаление');
}


/* ── Автоматически скрыть flash-уведомления через 5 сек ─── */
function initAutoHideAlerts(timeout) {
  setTimeout(function () {
    document.querySelectorAll('.alert.fade.show').forEach(function (el) {
      const bsAlert = bootstrap.Alert.getOrCreateInstance(el);
      bsAlert.close();
    });
  }, timeout || 5000);
}


/* ── Инициализация при загрузке страницы ─────────────────── */
document.addEventListener('DOMContentLoaded', function () {

  // Автоскрытие уведомлений
  initAutoHideAlerts(5000);

  // Кнопка показа пароля на странице входа
  const loginPwd = document.getElementById('login-pwd');
  const loginEye = document.getElementById('login-eye');
  if (loginPwd && loginEye) {
    document.getElementById('login-eye-btn').addEventListener('click', function () {
      togglePassword('login-pwd', 'login-eye');
    });
  }

  // Проверка паролей на странице профиля
  checkPasswordMatch('new-pwd', 'confirm-pwd', 'match-hint');

  // Проверка паролей на форме нового пользователя
  checkPasswordMatch('new-password-input', 'confirm-password-input', 'password-match-hint');

  initBaseActionBindings();
  initUserFormActions();
  initSubjectCreditsForm();
  initTeacherFormWorkloads();
  initAiToolsPage();

});


/* ── Мобильный сайдбар ───────────────────────────────────── */
function toggleSidebar() {
  const sidebar = document.querySelector('.sidebar');
  const overlay = document.getElementById('sidebar-overlay');
  const icon    = document.getElementById('menu-icon');
  if (!sidebar) return;

  const isOpen = sidebar.classList.toggle('open');
  overlay.classList.toggle('active', isOpen);
  icon.className = isOpen ? 'bi bi-x' : 'bi bi-list';
}

function closeSidebar() {
  const sidebar = document.querySelector('.sidebar');
  const overlay = document.getElementById('sidebar-overlay');
  const icon    = document.getElementById('menu-icon');
  if (!sidebar) return;

  sidebar.classList.remove('open');
  overlay.classList.remove('active');
  if (icon) icon.className = 'bi bi-list';
}

/* Закрывать сайдбар при нажатии Escape */
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') closeSidebar();
});
const AI_STORAGE_KEY   = 'ai_chat_messages';
const AI_OPEN_KEY      = 'ai_chat_open';
const AI_HISTORY_KEY   = 'ai_chat_history';

let aiHistory = [];

/* Сохранить состояние в sessionStorage */
function aiSaveState() {
  const box  = document.getElementById('ai-messages');
  if (!box) return;
  const msgs = Array.from(box.querySelectorAll('.ai-msg')).map(el => ({
    html: el.innerHTML,
    cls:  el.className,
  }));
  sessionStorage.setItem(AI_STORAGE_KEY, JSON.stringify(msgs));
  sessionStorage.setItem(AI_HISTORY_KEY, JSON.stringify(aiHistory));
  sessionStorage.setItem(AI_OPEN_KEY,    document.getElementById('ai-panel')?.classList.contains('open') ? '1' : '0');
}

/* Восстановить состояние из sessionStorage */
function aiRestoreState() {
  const panel = document.getElementById('ai-panel');
  const box   = document.getElementById('ai-messages');
  const sugg  = document.getElementById('ai-suggestions');
  if (!panel || !box) return;

  /* История переписки */
  try {
    const saved = sessionStorage.getItem(AI_HISTORY_KEY);
    if (saved) aiHistory = JSON.parse(saved);
  } catch(e) { aiHistory = []; }

  /* Сообщения */
  try {
    const saved = sessionStorage.getItem(AI_STORAGE_KEY);
    if (saved) {
      const msgs = JSON.parse(saved);
      if (msgs.length > 0) {
        box.innerHTML = '';
        msgs.forEach(m => {
          const div = document.createElement('div');
          div.className = m.cls.replace(' typing', ''); /* убираем класс typing */
          div.innerHTML  = m.html;
          box.appendChild(div);
        });
        /* Скрыть подсказки если уже был диалог */
        if (sugg && msgs.length > 1) sugg.style.display = 'none';
      }
    }
  } catch(e) {}

  /* Открыт ли чат */
  if (sessionStorage.getItem(AI_OPEN_KEY) === '1') {
    panel.classList.add('open');
    setTimeout(() => {
      scrollAI();
      document.getElementById('ai-input')?.focus();
    }, 50);
  }
}

function toggleAI() {
  const panel = document.getElementById('ai-panel');
  const isOpen = panel.classList.toggle('open');
  if (isOpen) {
    setTimeout(() => {
      scrollAI();
      document.getElementById('ai-input').focus();
    }, 50);
  }
  aiSaveState();
}

function autoResize(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 100) + 'px';
}

function handleAIKey(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendAIMessage();
  }
}

function initBaseActionBindings() {
  document.querySelectorAll('.js-toggle-sidebar').forEach((el) => {
    el.addEventListener('click', function () {
      toggleSidebar();
    });
  });

  document.querySelectorAll('[data-close-sidebar="1"]').forEach((el) => {
    el.addEventListener('click', function () {
      closeSidebar();
    });
  });

  document.querySelectorAll('.js-toggle-ai').forEach((el) => {
    el.addEventListener('click', function () {
      toggleAI();
    });
  });

  document.querySelectorAll('.js-ai-suggestion').forEach((el) => {
    el.addEventListener('click', function () {
      sendSuggestion(el.dataset.text || '');
    });
  });

  const aiInput = document.getElementById('ai-input');
  if (aiInput) {
    aiInput.addEventListener('keydown', handleAIKey);
    aiInput.addEventListener('input', function () {
      autoResize(aiInput);
    });
  }

  const aiSend = document.getElementById('ai-send');
  if (aiSend) {
    aiSend.addEventListener('click', sendAIMessage);
  }
}

function initUserFormActions() {
  document.querySelectorAll('.js-toggle-user-pwd').forEach((btn) => {
    btn.addEventListener('click', function () {
      togglePassword('pwd', 'eye-ico');
    });
  });
}

function initSubjectCreditsForm() {
  const inp = document.getElementById('subject-credits');
  const hint = document.getElementById('credits-hours-hint');
  if (!inp || !hint) return;

  const hp = parseInt(inp.dataset.hoursPerCredit || '15', 10);
  const tpl = (hint.closest('.hint-box') && hint.closest('.hint-box').dataset.hoursHint) || '';
  const refresh = function () {
    const c = parseFloat(String(inp.value).replace(',', '.')) || 0;
    const h = Math.round(c * hp * 10) / 10;
    if (tpl) {
      hint.textContent = tpl.replace('__HP__', hp).replace('__H__', h);
    } else {
      hint.textContent = '≈ ' + h + ' ак. ч.';
    }
  };

  document.querySelectorAll('.js-credit-preset').forEach((btn) => {
    btn.addEventListener('click', function () {
      inp.value = btn.dataset.credit || '0';
      refresh();
    });
  });

  inp.addEventListener('input', refresh);
  refresh();
}

function initTeacherFormWorkloads() {
  const select = document.getElementById('position-select');
  const input = document.getElementById('max-workload');
  const rateSel = document.getElementById('rate-select');
  const warn = document.getElementById('position-supervisor-warning');
  if (!select || !input) return;

  let workloads = {};
  let supervisorOnly = [];
  try { workloads = JSON.parse(select.dataset.positionWorkloads || '{}'); }
  catch (e) { workloads = {}; }
  try { supervisorOnly = JSON.parse(select.dataset.supervisorOnly || '[]'); }
  catch (e) { supervisorOnly = []; }

  function recalc() {
    const pos = select.value;
    const rate = parseFloat((rateSel && rateSel.value || '1').replace(',', '.')) || 1;
    if (workloads[pos] !== undefined) {
      input.value = Math.round(workloads[pos] * rate * 100) / 100;
    }
    if (warn) {
      warn.style.display = supervisorOnly.indexOf(pos) >= 0 ? 'block' : 'none';
    }
  }

  select.addEventListener('change', recalc);
  if (rateSel) rateSel.addEventListener('change', recalc);
}

function sendSuggestion(text) {
  const sugg = document.getElementById('ai-suggestions');
  if (sugg) sugg.style.display = 'none';
  document.getElementById('ai-input').value = text;
  sendAIMessage();
}

function scrollAI() {
  const box = document.getElementById('ai-messages');
  if (box) box.scrollTop = box.scrollHeight;
}

function addMsg(text, role) {
  const box = document.getElementById('ai-messages');
  const div = document.createElement('div');
  div.className = 'ai-msg ' + role;
  div.innerHTML = text.replace(/\n/g, '<br>');
  box.appendChild(div);
  scrollAI();
  return div;
}

async function sendAIMessage() {
  const input = document.getElementById('ai-input');
  const btn   = document.getElementById('ai-send');
  const text  = input.value.trim();
  if (!text) return;

  addMsg(text, 'user');
  aiHistory.push({ role: 'user', content: text });
  input.value = '';
  input.style.height = 'auto';
  btn.disabled = true;

  const I = window.I18N || {};
  const typing = addMsg(I.aiThinking || '...', 'bot typing');

  try {
    const csrfMeta = document.querySelector('meta[name="csrf-token"]');
    const csrfToken = csrfMeta ? csrfMeta.getAttribute('content') : '';
    const resp = await fetch('/ai/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken,
      },
      body: JSON.stringify({ message: text, history: aiHistory.slice(-10) })
    });
    const data  = await resp.json();
    const reply = data.reply || data.error || (I.aiError || 'Error');
    typing.remove();
    addMsg(reply, 'bot');
    aiHistory.push({ role: 'assistant', content: reply });
  } catch (e) {
    typing.remove();
    addMsg(I.aiError || '⚠️ Error', 'bot');
  } finally {
    btn.disabled = false;
    input.focus();
  }

  aiSaveState();
}

async function findTeacher() {
  const credEl = document.getElementById('subj-credits');
  const box    = document.getElementById('teacher-result');
  if (!credEl || !box) return;
  const credits = String(credEl.value).replace(',', '.');
  if (!credits || Number(credits) <= 0) return;

  const I = window.I18N || {};
  box.style.display = 'block';
  box.innerHTML = '<div class="text-muted small"><i class="bi bi-cpu me-1"></i>' + (I.aiAnalyzing || '...') + '</div>';

  const resp = await fetch('/ai/find-teacher?credits=' + encodeURIComponent(credits));
  const data = await resp.json();

  if (!data.results || data.results.length === 0) {
    box.innerHTML = '<div class="alert alert-warning">' + (I.aiNoMatch || '—') + '</div>';
    return;
  }

  let html = '<div class="row g-2">';
  data.results.forEach((r, i) => {
    const medal = ['🥇', '🥈', '🥉'][i] || '';
    const border = i === 0 ? 'var(--clr-accent)' : 'var(--clr-border)';
    html += `
      <div class="col-md-4">
        <div class="card" style="border-color:${border}">
          <div class="card-body p-3">
            <div class="fw-semibold small">${medal} ${r.teacher}</div>
            <div class="text-muted ai-tools-subtitle">${r.position}</div>
            <div class="ai-tools-meta">
              ${I.aiFree || ''} <span class="hours-chip">${r.free}</span>
              ${I.aiAfter || ''} <span class="hours-chip">${r.new_pct}%</span>
            </div>
            <div class="ai-tools-score">${I.aiScore || ''} ${r.score}/100</div>
          </div>
        </div>
      </div>`;
  });
  html += '</div>';
  box.innerHTML = html;
}

async function predictHours() {
  const positionEl = document.getElementById('pred-position');
  const credEl     = document.getElementById('pred-credits');
  const box        = document.getElementById('predict-result');
  if (!positionEl || !credEl || !box) return;
  const position = positionEl.value;
  const credits  = String(credEl.value).replace(',', '.');
  if (!credits || Number(credits) <= 0) return;

  const I = window.I18N || {};
  box.style.display = 'block';
  box.innerHTML = '<div class="text-muted small"><i class="bi bi-cpu me-1"></i>' + (I.aiCalculating || '...') + '</div>';

  const resp = await fetch(`/ai/predict?position=${encodeURIComponent(position)}&credits=${encodeURIComponent(credits)}`);
  const data = await resp.json();

  box.innerHTML = `
    <div class="d-flex gap-3 align-items-center flex-wrap">
      <div class="stat-card accent ai-tools-card">
        <div class="ai-tools-value text-info">${data.lecture}</div>
        <div class="ai-tools-subtitle">${I.aiLecture || 'Lecture'}</div>
      </div>
      <div class="stat-card accent2 ai-tools-card">
        <div class="ai-tools-value ai-tools-violet">${data.practice}</div>
        <div class="ai-tools-subtitle">${I.aiPractice || 'Practice'}</div>
      </div>
      <div class="stat-card green ai-tools-card">
        <div class="ai-tools-value text-success">${data.lab}</div>
        <div class="ai-tools-subtitle">${I.aiLab || 'Lab'}</div>
      </div>
      <div class="text-muted ai-tools-meta">
        <i class="bi bi-info-circle me-1"></i>
        ${I.aiBasedOn || ''} <strong class="text-light">${position}</strong>
      </div>
    </div>`;
}

function initAiToolsPage() {
  const btnFind = document.getElementById('btn-find-teacher');
  const btnPredict = document.getElementById('btn-predict-hours');
  if (btnFind) btnFind.addEventListener('click', findTeacher);
  if (btnPredict) btnPredict.addEventListener('click', predictHours);
}

/* Инициализация виджета при загрузке страницы */
document.addEventListener('DOMContentLoaded', function () {
  aiRestoreState();
});

/* Сохранить перед уходом со страницы */
window.addEventListener('beforeunload', function () {
  aiSaveState();
});