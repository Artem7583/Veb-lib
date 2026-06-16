const state = {
  auth: { token: localStorage.getItem("library_token") || "", user: { role: "guest", username: "guest", fullName: "Посетитель", patronId: null } },
  books: [], patrons: [], loans: [], requests: [], users: [], transactions: [], availableCopies: [], reports: {}, settings: {}, contact: {}, profile: null,
  chatThreads: [], activeChatThreadId: null, supportUnread: 0, bookCopies: [],
  meta: { categories: [], languages: [], stockStatuses: [] }, selectedBookId: null, selectedBookTitle: "", route: "home", lastSavedBookId: null,
  ui: { catalogPage: 1, copiesBookPage: 1, patronsPage: 1, requestsPage: 1, loansReaderPage: 1, returnPage: 1, historyPage: 1, usersPage: 1, logsPage: 1, analyticsTab: "reports", chatNew: false, copiesBookQuery: "", copiesStatusFilter: "" },
};
let chatRenderToken = 0;
const roleLabels = { guest: "Посетитель", reader: "Читатель", borrower: "Читатель", librarian: "Библиотекарь", manager: "Менеджер", admin: "Администратор" };
const stockLabels = { available: "Доступна", on_loan: "На руках", damaged: "Повреждена", lost: "Утеряна", written_off: "Списана", replaced: "Заменена", empty: "Нет экземпляров" };
const copyStatusClasses = {
  available: "copy-status--available",
  on_loan: "copy-status--loan",
  damaged: "copy-status--damaged",
  lost: "copy-status--lost",
  written_off: "copy-status--off",
  replaced: "copy-status--replaced",
};
const loanLabels = { active: "Активна", renewed: "Продлена", overdue: "Просрочена", returned: "Возвращена", lost: "Утеря" };
const requestLabels = { pending: "Ожидает", approved: "Одобрен", rejected: "Отклонен" };
const operationLabels = { acquisition: "Поступление", issue: "Выдача", return: "Возврат", renew: "Продление", lost: "Утеря", replacement: "Замена", write_off: "Списание", registration_request: "Регистрация" };
let isPageUnloading = false;

const SITE_PAGES = ["about", "services", "readers-info", "virtual", "events", "news", "partners", "faq", "roadmap"];
const INFO_PAGES = SITE_PAGES;
const PAGE_SIZE = { patrons: 10, requests: 6, loans: 10, return: 10, history: 8, users: 10, logs: 12, copiesBooks: 12 };
const FAVORITES_KEY = "library_favorite_book_ids";
const FAVORITES_CACHE_KEY = "library_favorite_book_cache";

const $ = (id) => document.getElementById(id);
let elements = {};

function bindElements() {
  elements = {
    currentRoleBadge: $("currentRoleBadge"), currentUserName: $("currentUserName"), authUserChip: $("authUserChip"), openAccountButton: $("openAccountButton"), logoutButton: $("logoutButton"),
    loginDialog: $("loginDialog"), registerDialog: $("registerDialog"), loginForm: $("loginForm"), registerForm: $("registerForm"),
    forgotPasswordDialog: $("forgotPasswordDialog"), forgotEmailForm: $("forgotEmailForm"),
    resetPasswordDialog: $("resetPasswordDialog"), resetPasswordForm: $("resetPasswordForm"),
    openForgotPasswordButton: $("openForgotPasswordButton"), closeForgotPasswordButton: $("closeForgotPasswordButton"),
    closeResetPasswordButton: $("closeResetPasswordButton"), topbarTagline: $("topbarTagline"),
    navTabs: $("navTabs"), statsGrid: $("statsGrid"), filtersForm: $("filtersForm"),
    bookForm: $("bookForm"), patronForm: $("patronForm"), issueForm: $("issueForm"), userForm: $("userForm"), settingsForm: $("settingsForm"), booksGrid: $("booksGrid"), resultsCount: $("resultsCount"),
    requestsList: $("requestsList"), requestsSummary: $("requestsSummary"), patronsTable: $("patronsTable"), loansTable: $("loansTable"), returnTable: $("returnTable"), historyList: $("historyList"), usersTable: $("usersTable"),
    reportsList: $("reportsList"), transactionsList: $("transactionsList"), copiesTable: $("copiesTable"), copiesSummary: $("copiesSummary"),
    copiesBookPicker: $("copiesBookPicker"), copiesBookSearch: $("copiesBookSearch"), copiesBookList: $("copiesBookList"), copiesBookPager: $("copiesBookPager"),
    copiesPanel: $("copiesPanel"), copiesBookHero: $("copiesBookHero"), copiesStatsRow: $("copiesStatsRow"), copiesBookCount: $("copiesBookCount"),
    copiesStepPick: $("copiesStepPick"), copiesStepManage: $("copiesStepManage"), copiesStatusFilter: $("copiesStatusFilter"),
    changeCopiesBookButton: $("changeCopiesBookButton"), copiesBackToListButton: $("copiesBackToListButton"), bookSort: $("bookSort"),
    bookDetailsDialog: $("bookDetailsDialog"), bookDetailsTitle: $("bookDetailsTitle"), bookDetailsSubtitle: $("bookDetailsSubtitle"), bookDetailsBody: $("bookDetailsBody"), bookDetailsCloseButton: $("bookDetailsCloseButton"),
    copyEditDialog: $("copyEditDialog"), copyEditForm: $("copyEditForm"), closeCopyEditButton: $("closeCopyEditButton"),
    addCopiesForm: $("addCopiesForm"), editSelectedBookButton: $("editSelectedBookButton"),
    passwordForm: $("passwordForm"), passwordDialog: $("passwordDialog"),
    chatThreadList: $("chatThreadList"), chatMessages: $("chatMessages"), chatThreadHead: $("chatThreadHead"),
    chatComposeForm: $("chatComposeForm"), chatNewThreadForm: $("chatNewThreadForm"),
    bookCardTemplate: $("bookCardTemplate"), coverPreview: $("coverPreview"), deleteCoverButton: $("deleteCoverButton"), notifyRoot: $("notifyRoot"), favoritesList: $("favoritesList"), profilePanel: $("profilePanel"),
    catalogPager: $("catalogPager"), catalogPerPage: $("catalogPerPage"), patronsPager: $("patronsPager"), requestsPager: $("requestsPager"), loansPager: $("loansPager"),
    returnPager: $("returnPager"), historyPager: $("historyPager"), usersPager: $("usersPager"), transactionsPager: $("transactionsPager"),
    confirmDialog: $("confirmDialog"), bookFormDialog: $("bookFormDialog"), userFormDialog: $("userFormDialog"), patronFormDialog: $("patronFormDialog"), addCopiesDialog: $("addCopiesDialog"),
    patronProfileDialog: $("patronProfileDialog"), patronProfileBody: $("patronProfileBody"), patronProfileTitle: $("patronProfileTitle"),
    openNewBookButton: $("openNewBookButton"), openNewUserButton: $("openNewUserButton"), openNewPatronButton: $("openNewPatronButton"), openAddCopiesButton: $("openAddCopiesButton"),
    exportCatalogBtn: $("exportCatalogBtn"), importCatalogInput: $("importCatalogInput"), catalogImportStatus: $("catalogImportStatus"),
    downloadCatalogTemplateBtn: $("downloadCatalogTemplateBtn"),
  };
}

function splitMultilineValue(text) {
  return String(text || "")
    .split(/\r?\n|,/)
    .map((part) => part.trim())
    .filter(Boolean);
}

function formatFooterBlock(label, value, fallbackHtml) {
  const lines = splitMultilineValue(value);
  if (!lines.length) return fallbackHtml || "";
  return `<span class="footer-label">${escapeHtml(label)}:</span><br>${lines.map((line) => escapeHtml(line)).join("<br>")}`;
}

function formatFooterLine(label, value) {
  const line = String(value || "").trim();
  if (!line) return "";
  return `<span class="footer-label">${escapeHtml(label)}:</span><br>${escapeHtml(line)}`;
}

function canonicalRole(role) { return role === "borrower" ? "reader" : role || "guest"; }
function authHeaders() { return state.auth.token ? { Authorization: `Bearer ${state.auth.token}` } : {}; }
function formToObject(form) { return Object.fromEntries(new FormData(form).entries()); }
function formatDate(value) { return value ? new Date(value).toLocaleDateString("ru-RU") : "-"; }
function formatMoney(value) { return `${Number(value || 0).toLocaleString("ru-RU", { maximumFractionDigits: 2 })} ₽`; }
function isStaff() { return ["librarian", "manager", "admin"].includes(state.auth.user.role); }
function isCatalogStaff() { return ["librarian", "admin"].includes(state.auth.user.role); }
function isOpsStaff() { return ["manager", "librarian", "admin"].includes(state.auth.user.role); }
function isManager() { return state.auth.user.role === "manager"; }

function pendingRequestCount() {
  const fromStats = state.stats?.pending_requests;
  if (typeof fromStats === "number") return fromStats;
  return (state.requests || []).filter((item) => item.status === "pending").length;
}

function escapeHtml(text) {
  const node = document.createElement("div");
  node.textContent = text == null ? "" : String(text);
  return node.innerHTML;
}

function readFavoriteCache() {
  try {
    const raw = JSON.parse(localStorage.getItem(FAVORITES_CACHE_KEY) || "{}");
    return raw && typeof raw === "object" ? raw : {};
  } catch {
    return {};
  }
}

function writeFavoriteCache(cache) {
  localStorage.setItem(FAVORITES_CACHE_KEY, JSON.stringify(cache));
}

function rememberFavoriteBook(book) {
  if (!book?.id) return;
  const cache = readFavoriteCache();
  cache[String(book.id)] = {
    id: Number(book.id),
    title: book.title || "",
    author: book.author || "",
  };
  writeFavoriteCache(cache);
}

function forgetFavoriteBook(id) {
  const cache = readFavoriteCache();
  delete cache[String(id)];
  writeFavoriteCache(cache);
}

function resolveFavoriteBook(id) {
  const fromState = state.books.find((b) => b.id === id);
  if (fromState) return fromState;
  const cached = readFavoriteCache()[String(id)];
  return cached || null;
}

function loadFavoriteIds() {
  try {
    const raw = JSON.parse(localStorage.getItem(FAVORITES_KEY) || "[]");
    if (!Array.isArray(raw)) return [];
    return [...new Set(raw.map((id) => Number(id)).filter((n) => Number.isFinite(n) && n > 0))];
  } catch {
    return [];
  }
}

function saveFavoriteIds(ids) {
  localStorage.setItem(FAVORITES_KEY, JSON.stringify(ids));
}

function refreshFavoritesUi() {
  renderFavorites();
  if (isReader() && ["cabinet", "account"].includes(state.route)) renderProfile();
}

function toggleFavoriteId(id, book) {
  const n = Number(id);
  const ids = loadFavoriteIds();
  const idx = ids.indexOf(n);
  if (idx >= 0) {
    ids.splice(idx, 1);
    saveFavoriteIds(ids);
    forgetFavoriteBook(n);
    showToast("Убрано из избранного");
  } else {
    ids.push(n);
    saveFavoriteIds(ids);
    rememberFavoriteBook(book || state.books.find((b) => b.id === n));
    showToast("Добавлено в избранное");
  }
  refreshFavoritesUi();
}

function removeFavoriteId(id) {
  const n = Number(id);
  saveFavoriteIds(loadFavoriteIds().filter((x) => x !== n));
  forgetFavoriteBook(n);
  showToast("Удалено из избранного");
  refreshFavoritesUi();
}

function renderFavorites() {
  const el = elements.favoritesList;
  if (!el) return;
  const ids = loadFavoriteIds();
  if (!ids.length) {
    el.innerHTML = '<div class="empty-state">Пока пусто. Отметьте книгу звёздочкой в каталоге.</div>';
    return;
  }
  ids.forEach((fid) => {
    const book = state.books.find((b) => b.id === fid);
    if (book) rememberFavoriteBook(book);
  });
  el.innerHTML = ids
    .map((fid) => {
      const book = resolveFavoriteBook(fid);
      if (!book) {
        return `<article class="favorites-item"><span>Книга #${fid} (нет в текущем каталоге)</span><button type="button" class="ghost-button table-button" data-remove-fav="${fid}">Убрать</button></article>`;
      }
      return `<article class="favorites-item"><span><strong>${escapeHtml(book.title)}</strong> — ${escapeHtml(book.author)}</span><button type="button" class="ghost-button table-button" data-remove-fav="${fid}">Убрать</button></article>`;
    })
    .join("");
  el.querySelectorAll("[data-remove-fav]").forEach((btn) => {
    btn.addEventListener("click", () => {
      removeFavoriteId(btn.getAttribute("data-remove-fav"));
      renderBooks();
    });
  });
}

function showToast(message, type = "success") {
  const root = elements.notifyRoot;
  if (!root) return;
  const item = document.createElement("div");
  item.className = `notify-item notify-item--${type === "error" ? "error" : type === "info" ? "info" : "success"}`;
  item.textContent = message;
  root.appendChild(item);
  const remove = () => item.remove();
  setTimeout(remove, 4200);
  item.addEventListener("click", remove);
}

let confirmPending = null;

function showConfirm({ title = "Подтверждение", message = "", okLabel = "Подтвердить", danger = false }) {
  const dlg = elements.confirmDialog;
  if (!dlg) return Promise.resolve(window.confirm(message));
  return new Promise((resolve) => {
    if (confirmPending) confirmPending(false);
    confirmPending = resolve;
    $("confirmTitle").textContent = title;
    $("confirmMessage").textContent = message;
    const okBtn = $("confirmOkBtn");
    okBtn.textContent = okLabel;
    okBtn.className = danger ? "danger-button" : "solid-button";
    dlg.showModal();
  });
}

function finishConfirm(result) {
  elements.confirmDialog?.close();
  if (confirmPending) {
    const fn = confirmPending;
    confirmPending = null;
    fn(result);
  }
}

async function api(url, options = {}) {
  const isFormData = options.body instanceof FormData;
  const response = await fetch(url, { ...options, headers: { ...(isFormData ? {} : { "Content-Type": "application/json" }), ...authHeaders(), ...(options.headers || {}) } });
  if (!response.ok) {
    let message = "Ошибка запроса";
    try { message = (await response.json()).message || message; } catch { message = response.statusText || message; }
    throw new Error(message);
  }
  return response.status === 204 ? null : response.json();
}

function setToken(token) { state.auth.token = token || ""; token ? localStorage.setItem("library_token", token) : localStorage.removeItem("library_token"); }
function setUser(user) {
  state.auth.user = { role: "guest", username: "guest", fullName: "Посетитель", patronId: null, ...(user || {}) };
  state.auth.user.role = canonicalRole(state.auth.user.role);
  elements.currentRoleBadge?.classList.add("hidden");
  elements.currentUserName.textContent = state.auth.user.fullName || state.auth.user.username || roleLabels[state.auth.user.role] || "Гость";
  elements.authUserChip?.classList.toggle("hidden", state.auth.user.role === "guest");
  if (elements.authUserChip) {
    elements.authUserChip.title = state.auth.user.role === "guest" ? "" : `${roleLabels[state.auth.user.role] || state.auth.user.role} — открыть профиль`;
  }
  elements.openAccountButton?.classList.toggle("hidden", state.auth.user.role !== "guest");
  elements.logoutButton?.classList.toggle("hidden", state.auth.user.role === "guest");
  document.body.dataset.role = state.auth.user.role;
  document.querySelectorAll(".guest-only").forEach((node) => node.classList.toggle("hidden", state.auth.user.role !== "guest"));
  document.querySelectorAll(".logged-in-nav").forEach((node) => node.classList.toggle("hidden", state.auth.user.role === "guest"));
  if (elements.topbarTagline) {
    const taglines = {
      guest: "Каталог и запись читателя",
      reader: "Личный кабинет и запросы",
      librarian: "Каталог · выдача · экземпляры",
      manager: "Выдача · запросы · отчёты",
      admin: "Управление системой",
    };
    elements.topbarTagline.textContent = taglines[state.auth.user.role] || taglines.guest;
  }
  syncRoleNavVisibility();
  applyRouteGuards();
}

function fillSelect(select, options, placeholder, mapper) {
  if (!select) return;
  const previous = select.value;
  select.innerHTML = `<option value="">${placeholder}</option>`;
  options.forEach((option) => { const item = mapper(option); select.insertAdjacentHTML("beforeend", `<option value="${item.value}">${item.label}</option>`); });
  if ([...select.options].some((option) => option.value === previous)) select.value = previous;
}

function buildPagerNumbers(current, pages) {
  if (pages <= 7) return Array.from({ length: pages }, (_, i) => i + 1);
  const set = new Set([1, pages, current, current - 1, current + 1]);
  return [...set].filter((p) => p >= 1 && p <= pages).sort((a, b) => a - b);
}

function renderPagerBar(container, opts) {
  const { page, pageSize, total, onPage, emptyText = "" } = opts;
  if (!container) return;
  if (!total) {
    container.innerHTML = emptyText ? `<div class="pager__meta muted">${emptyText}</div>` : "";
    container.dataset.pagerPage = "1";
    container.dataset.pagerPages = "1";
    return;
  }
  const pages = Math.max(1, Math.ceil(total / pageSize));
  const current = Math.min(Math.max(1, page), pages);
  if (current !== page) {
    onPage(current);
    return;
  }
  container.dataset.pagerPage = String(current);
  container.dataset.pagerPages = String(pages);
  container.dataset.pagerOnPage = container.dataset.pagerOnPage || String(Math.random());
  const nums = buildPagerNumbers(current, pages);
  let numsHtml = "";
  let prevNum = 0;
  nums.forEach((n) => {
    if (n - prevNum > 1) numsHtml += '<span class="pager__ellipsis">…</span>';
    numsHtml += `<button type="button" class="pager__num${n === current ? " is-active" : ""}" data-pager-go="${n}">${n}</button>`;
    prevNum = n;
  });
  container.innerHTML = `<div class="pager__row">
    <button type="button" class="ghost-button pager__btn" ${current <= 1 ? "disabled" : ""} data-pager-prev>Назад</button>
    <div class="pager__nums">${numsHtml}</div>
    <span class="pager__meta">Стр. ${current} из ${pages}</span>
    <button type="button" class="ghost-button pager__btn" ${current >= pages ? "disabled" : ""} data-pager-next>Вперёд</button>
  </div>`;
}

function bindPagerDelegation(container, getState, onPage) {
  if (!container || container.dataset.pagerBound) return;
  container.dataset.pagerBound = "1";
  container.addEventListener("click", (event) => {
    const target = event.target.closest("[data-pager-prev],[data-pager-next],[data-pager-go]");
    if (!target || !container.contains(target)) return;
    event.preventDefault();
    const { page, pages } = getState();
    if (target.hasAttribute("data-pager-prev") && page > 1) onPage(page - 1);
    else if (target.hasAttribute("data-pager-next") && page < pages) onPage(page + 1);
    else if (target.hasAttribute("data-pager-go")) onPage(Number(target.getAttribute("data-pager-go")));
  });
}

function rebuildIssueSelects() {
  const copyQ = ($("issueCopyFilter")?.value || "").trim().toLowerCase();
  const patronQ = ($("issuePatronFilter")?.value || "").trim().toLowerCase();
  const copies = state.availableCopies.filter((item) => {
    if (!copyQ) return true;
    const hay = `${item.title || ""} ${item.inventory_code || ""}`.toLowerCase();
    return hay.includes(copyQ);
  });
  const patrons = state.patrons.filter((item) => {
    if (!patronQ) return true;
    const hay = `${item.full_name || ""} ${item.card_number || ""}`.toLowerCase();
    return hay.includes(patronQ);
  });
  fillSelect($("issueCopySelect"), copies, "Выберите экземпляр", (item) => ({ value: item.id, label: `${item.title} • ${item.inventory_code}` }));
  fillSelect($("issuePatronSelect"), patrons, "Выберите читателя", (item) => ({ value: item.id, label: `${item.full_name} (${item.card_number})` }));
}

function renderStats(stats = {}) {
  document.querySelectorAll(".staff-only").forEach((node) => node.classList.toggle("hidden", !isStaff()));
  if (!isStaff()) { elements.statsGrid.innerHTML = ""; return; }
  const items = [
    ["Названий", stats.total_titles],
    ["Экземпляров", stats.total_copies],
    ["Доступно", stats.available_copies],
    ["Активных выдач", stats.active_loans],
    ["Просрочено", stats.overdue_loans],
    ["Читателей", stats.patrons_count],
  ];
  if (isOpsStaff()) items.push(["Запросов ожидает", stats.pending_requests ?? pendingRequestCount()]);
  elements.statsGrid.innerHTML = items.map(([label, value]) => `<div class="stat-chip"><span class="stat-chip__label">${label}</span><strong class="stat-chip__value">${value ?? 0}</strong></div>`).join("");
}

function sortedBooksList() {
  const books = [...state.books];
  const mode = elements.bookSort?.value || "alphaAsc";
  if (mode === "alphaDesc") return books.sort((a, b) => String(b.title).localeCompare(String(a.title), "ru"));
  if (mode === "yearDesc") return books.sort((a, b) => Number(b.publish_year || 0) - Number(a.publish_year || 0));
  if (mode === "yearAsc") return books.sort((a, b) => Number(a.publish_year || 0) - Number(b.publish_year || 0));
  return books.sort((a, b) => String(a.title).localeCompare(String(b.title), "ru"));
}

function openBookDetails(book) {
  if (!elements.bookDetailsDialog) return;
  elements.bookDetailsTitle.textContent = book.title;
  elements.bookDetailsSubtitle.textContent = `${book.author} • ${book.publish_year}`;
  const staffBlock = isStaff()
    ? `<p><strong>Экземпляров:</strong> ${book.total_copies} (свободно ${book.available_copies})</p><p><strong>Цена замены:</strong> ${formatMoney(book.replacement_cost)} • <strong>Итог:</strong> ${formatMoney(book.final_price)}</p><p><strong>Запросов:</strong> ${book.request_count || 0}</p>`
    : `<p><strong>Доступно для выдачи:</strong> ${book.available_copies > 0 ? "есть" : "нет"}</p>`;
  const readerBlock = state.auth.user.role === "reader"
    ? `<p><strong>Статус:</strong> ${stockLabels[book.stock_status] || book.stock_status}</p>`
    : "";
  elements.bookDetailsBody.innerHTML = `
    <p><strong>Категория:</strong> ${escapeHtml(book.category)}</p>
    <p><strong>ISBN:</strong> ${escapeHtml(book.isbn)}</p>
    <p><strong>Язык:</strong> ${escapeHtml(book.language)}</p>
    ${isStaff() ? `<p><strong>Полка:</strong> ${escapeHtml(book.shelf_code || "не указана")}</p>` : ""}
    <p><strong>Издатель:</strong> ${escapeHtml(book.publisher || "-")}</p>
    ${staffBlock}
    ${readerBlock}
    <p><strong>Описание:</strong> ${escapeHtml(book.description || "Нет описания.")}</p>
  `;
  elements.bookDetailsDialog.showModal();
}

function cloneBookCardFragment() {
  const tpl = elements.bookCardTemplate;
  if (!tpl?.content) return null;
  return tpl.content.cloneNode(true);
}

function renderBooks() {
  if (!elements.booksGrid) return;
  elements.booksGrid.innerHTML = "";
  const sorted = sortedBooksList();
  const total = sorted.length;
  const perPage = Math.max(1, Number(elements.catalogPerPage?.value || 12));
  const pages = Math.max(1, Math.ceil(total / perPage));
  if (state.ui.catalogPage > pages) state.ui.catalogPage = pages;
  const page = Math.max(1, state.ui.catalogPage);
  const slice = sorted.slice((page - 1) * perPage, page * perPage);

  elements.resultsCount.textContent = total ? `Найдено книг: ${total}` : "Книги не найдены.";
  if (!total) {
    elements.booksGrid.innerHTML = '<div class="empty-state">Книги не найдены.</div>';
    renderPagerBar(elements.catalogPager, { page: 1, pageSize: perPage, total: 0, onPage: () => {} });
    return;
  }

  const favoriteSet = new Set(loadFavoriteIds());
  slice.forEach((book) => {
    const fragment = cloneBookCardFragment();
    if (!fragment) return;
    const card = fragment.querySelector(".book-card");
    card.dataset.bookId = String(book.id);
    const cover = fragment.querySelector(".book-card__cover");
    cover.innerHTML = book.cover_image ? `<img src="${book.cover_image}" alt="" loading="lazy" />` : "Без обложки";
    fragment.querySelector(".book-card__category").textContent = book.category;
    fragment.querySelector(".book-card__status").textContent = stockLabels[book.stock_status] || book.stock_status;
    fragment.querySelector(".book-card__title").textContent = book.title;
    fragment.querySelector(".book-card__author").textContent = `${book.author} • ${book.publish_year}`;
    fragment.querySelector(".book-card__meta").textContent = isStaff()
      ? `ISBN ${book.isbn} • ${book.language} • Полка: ${book.shelf_code || "не указана"}`
      : `${book.language} • ${stockLabels[book.stock_status] || book.stock_status}`;
    fragment.querySelector(".book-card__footer").innerHTML = isStaff()
      ? `<span>Свободно ${book.available_copies}/${book.total_copies} • Запросов ${book.request_count || 0}</span><strong>${formatMoney(book.final_price)}</strong>`
      : `<span>${book.available_copies > 0 ? "Можно забронировать" : "Сейчас занята"}</span>`;
    card.addEventListener("click", (event) => {
      if (event.target.closest("button")) return;
      openBookDetails(book);
    });
    card.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        openBookDetails(book);
      }
    });
    fragment.querySelector('[data-action="request"]').addEventListener("click", (event) => requestBook(book, event.currentTarget));
    fragment.querySelector('[data-action="edit"]')?.addEventListener("click", () => openBookFormModal(book));
    fragment.querySelector('[data-action="delete"]')?.addEventListener("click", async () => {
      try {
        const ok = await showConfirm({ title: "Списать книгу", message: `Удалить «${book.title}» из каталога? Это действие необратимо.`, okLabel: "Списать", danger: true });
        if (!ok) return;
        await api(`/api/library/books/${book.id}`, { method: "DELETE" });
        showToast(`Книга «${book.title}» списана из каталога.`);
        await loadDashboard();
      } catch (error) {
        showError(error);
      }
    });
    if (!isCatalogStaff()) fragment.querySelectorAll(".librarian-only-inline").forEach((node) => node.remove());
    if (isStaff()) fragment.querySelector('[data-action="request"]').remove();
    if (state.auth.user.role === "guest") {
      const requestButton = fragment.querySelector('[data-action="request"]');
      if (requestButton) requestButton.textContent = "Забронировать";
    }
    if (state.auth.user.role === "reader") {
      const actions = fragment.querySelector(".book-card__actions");
      const fav = document.createElement("button");
      fav.type = "button";
      fav.className = "ghost-button";
      fav.setAttribute("aria-label", favoriteSet.has(book.id) ? "Убрать из избранного" : "В избранное");
      fav.textContent = favoriteSet.has(book.id) ? "\u2605" : "\u2606";
      fav.addEventListener("click", (e) => {
        e.stopPropagation();
        toggleFavoriteId(book.id, book);
        renderBooks();
      });
      actions.prepend(fav);
    }
    const requestBtn = fragment.querySelector('[data-action="request"]');
    if (requestBtn && book.available_copies <= 0) {
      requestBtn.classList.add("book-card__request--unavailable");
      requestBtn.setAttribute("aria-disabled", "true");
    }
    elements.booksGrid.appendChild(fragment);
  });
  renderPagerBar(elements.catalogPager, {
    page, pageSize: perPage, total,
    onPage: (p) => { state.ui.catalogPage = p; renderBooks(); },
  });
  if (state.lastSavedBookId) {
    const updatedCard = elements.booksGrid.querySelector(`[data-book-id="${state.lastSavedBookId}"]`);
    if (updatedCard) {
      updatedCard.classList.add("book-card--active");
      updatedCard.scrollIntoView({ behavior: "smooth", block: "center" });
    }
    state.lastSavedBookId = null;
  }
}

async function requestBook(book, button) {
  if (book.available_copies <= 0) {
    showToast("Сейчас все экземпляры заняты. Попробуйте позже.", "info");
    return;
  }
  if (state.auth.user.role === "guest") {
    showToast("Войдите в личный кабинет, чтобы забронировать книгу.", "info");
    state.route = "account";
    applyRouteGuards();
    return;
  }
  if (state.auth.user.role !== "reader") return;
  if (button) {
    button.disabled = true;
    button.textContent = "Отправляем...";
  }
  try {
    await api("/api/library/requests", { method: "POST", body: JSON.stringify({ bookId: book.id }) });
    showToast(`Заявка на бронь книги «${book.title}» отправлена библиотекарю.`);
    await loadDashboard();
  } catch (error) {
    if (button) {
      button.disabled = false;
      button.textContent = "Забронировать";
    }
    showError(error);
  }
}

function renderRequests() {
  const pending = pendingRequestCount();
  if (state.auth.user.role === "reader") {
    elements.requestsSummary.textContent = "Ваши запросы библиотекарю.";
  } else if (isOpsStaff()) {
    elements.requestsSummary.textContent = pending
      ? `Ожидают обработки: ${pending}. Одобрите выдачу или отклоните запрос.`
      : "Новых запросов нет. Здесь появятся бронирования читателей.";
  } else {
    elements.requestsSummary.textContent = "Управление запросами читателей.";
  }
  if (!state.requests.length) {
    elements.requestsList.innerHTML = '<div class="empty-state">Запросов пока нет.</div>';
    renderPagerBar(elements.requestsPager, { page: 1, pageSize: PAGE_SIZE.requests, total: 0, onPage: () => {}, emptyText: "" });
    updateStaffRequestBadges(pending);
    return;
  }
  const perPage = PAGE_SIZE.requests;
  const pages = Math.max(1, Math.ceil(state.requests.length / perPage));
  if (state.ui.requestsPage > pages) state.ui.requestsPage = pages;
  const page = Math.max(1, state.ui.requestsPage);
  const slice = state.requests.slice((page - 1) * perPage, page * perPage);
  elements.requestsList.innerHTML = slice.map((item) => `<article class="cart-item ${item.status === "rejected" ? "cart-item--rejected" : ""}"><div class="cart-item__cover">${item.cover_image ? `<img src="${item.cover_image}" alt="" />` : "Без обложки"}</div><div class="cart-item__body"><span class="pill ${item.status === "rejected" ? "pill--danger" : item.status === "approved" ? "pill--success" : "pill--soft"}">${requestLabels[item.status] || item.status}</span><h3>${escapeHtml(item.title)}</h3><p>${escapeHtml(item.author)}</p><div class="small-text">${escapeHtml(item.reader_name || "")} ${item.card_number ? `• билет ${escapeHtml(item.card_number)}` : ""} • ${formatDate(item.request_date)}</div>${item.status === "rejected" && item.notes ? `<div class="small-text request-reason">Причина: ${escapeHtml(item.notes)}</div>` : ""}</div><div class="cart-item__actions">${isOpsStaff() && item.status === "pending" ? `<button type="button" class="table-button" data-approve="${item.id}">Выдать</button><button type="button" class="table-button danger" data-reject="${item.id}">Отказать</button>` : ""}</div></article>`).join("");
  renderPagerBar(elements.requestsPager, {
    page, pageSize: perPage, total: state.requests.length,
    onPage: (p) => { state.ui.requestsPage = p; renderRequests(); },
  });
  updateStaffRequestBadges(pending);
}

function loanRowHtml(loan, options = {}) {
  const { showPatron = true, readerView = false } = options;
  const active = ["active", "renewed", "overdue"].includes(loan.status);
  let actions = "";
  if (isOpsStaff() && active) {
    actions = `<button type="button" class="table-button" data-loan-return="${loan.id}">Возврат</button><button type="button" class="table-button" data-loan-renew="${loan.id}">Продлить</button><button type="button" class="table-button danger" data-loan-lost="${loan.id}">Утеря</button>`;
  } else if (readerView && active) {
    actions = `<button type="button" class="table-button" data-reader-renew="${loan.id}">Продлить</button>`;
  }
  const patronCell = showPatron ? `<td data-label="Читатель">${escapeHtml(loan.patron_name)}</td>` : "";
  const issuedCell = readerView ? `<td data-label="Выдано">${formatDate(loan.issued_at)}</td>` : "";
  return `<tr>
    <td data-label="Книга">${escapeHtml(loan.title)}<div class="small-text">${escapeHtml(loan.inventory_code)}</div></td>
    ${patronCell}
    ${issuedCell}
    <td data-label="Срок">${formatDate(loan.due_at)}</td>
    <td data-label="Статус">${loanLabels[loan.status] || loan.status}</td>
    <td class="actions-cell" data-label="Действия">${actions}</td>
  </tr>`;
}

function renderLoans(target = elements.loansTable, activeOnly = false, pagerEl = null, pageKey = "loansReaderPage", pageSize = PAGE_SIZE.loans) {
  const allRows = state.loans.filter((loan) => !activeOnly || ["active", "renewed", "overdue"].includes(loan.status));
  const readerView = state.auth.user.role === "reader" && target === elements.loansTable;
  const showPatron = !readerView;
  const colSpan = readerView ? 5 : 5;
  if (pagerEl) {
    const pages = Math.max(1, Math.ceil(allRows.length / pageSize));
    if (state.ui[pageKey] > pages) state.ui[pageKey] = pages;
    const page = Math.max(1, state.ui[pageKey] || 1);
    const rows = allRows.slice((page - 1) * pageSize, page * pageSize);
    target.innerHTML = rows.length
      ? rows.map((loan) => loanRowHtml(loan, { showPatron, readerView })).join("")
      : `<tr><td colspan="${colSpan}" class="muted-cell">Нет записей.</td></tr>`;
    renderPagerBar(pagerEl, {
      page, pageSize, total: allRows.length,
      onPage: (p) => { state.ui[pageKey] = p; renderByRole(); },
      emptyText: allRows.length ? "" : "Нет записей.",
    });
    return;
  }
  target.innerHTML = allRows.length
    ? allRows.map((loan) => loanRowHtml(loan, { showPatron, readerView })).join("")
    : `<tr><td colspan="${colSpan}" class="muted-cell">Нет записей.</td></tr>`;
}

function findLoanById(loanId) {
  return state.loans.find((loan) => loan.id === loanId);
}

async function handleLoanAction(loanId, action) {
  const loan = findLoanById(loanId);
  if (!loan) throw new Error("Выдача не найдена. Обновите страницу.");
  if (action === "return") {
    const ok = await showConfirm({ title: "Возврат книги", message: `Принять возврат «${loan.title}» (${loan.inventory_code})?` });
    if (!ok) return;
    await api(`/api/library/loans/${loan.id}/return`, { method: "POST", body: JSON.stringify({ copyStatus: "available", conditionRating: 5 }) });
    showToast(`Возврат книги «${loan.title}» отмечен.`);
  } else if (action === "renew") {
    const dueAt = defaultDueDate();
    const ok = await showConfirm({ title: "Продление", message: `Продлить «${loan.title}» до ${formatDate(dueAt)}?` });
    if (!ok) return;
    await api(`/api/library/loans/${loan.id}/renew`, { method: "POST", body: JSON.stringify({ dueAt }) });
    showToast(`Срок возврата книги «${loan.title}» продлён до ${formatDate(dueAt)}.`);
  } else if (action === "lost") {
    const ok = await showConfirm({ title: "Утеря экземпляра", message: `Отметить «${loan.title}» как утерянную? Действие необратимо.`, okLabel: "Подтвердить утерю", danger: true });
    if (!ok) return;
    await api(`/api/library/loans/${loan.id}/lost`, { method: "POST", body: JSON.stringify({ notes: "Экземпляр утерян читателем" }) });
    showToast(`Книга «${loan.title}» отмечена как утерянная.`);
  } else if (action === "reader-renew") {
    const ok = await showConfirm({ title: "Продление", message: `Продлить срок возврата «${loan.title}»?` });
    if (!ok) return;
    const result = await api(`/api/library/loans/${loan.id}/renew-request`, { method: "POST", body: JSON.stringify({}) });
    showToast(result?.message || "Срок возврата продлён.");
  }
  await loadDashboard();
}

function bindTableActionDelegation() {
  const onLoanClick = async (event) => {
    const btn = event.target.closest("[data-loan-return], [data-loan-renew], [data-loan-lost], [data-reader-renew]");
    if (!btn) return;
    event.preventDefault();
    const loanId = Number(
      btn.getAttribute("data-loan-return")
      || btn.getAttribute("data-loan-renew")
      || btn.getAttribute("data-loan-lost")
      || btn.getAttribute("data-reader-renew"),
    );
    const action = btn.hasAttribute("data-loan-return")
      ? "return"
      : btn.hasAttribute("data-loan-renew")
        ? "renew"
        : btn.hasAttribute("data-loan-lost")
          ? "lost"
          : "reader-renew";
    try {
      await handleLoanAction(loanId, action);
    } catch (error) {
      showError(error);
    }
  };
  [elements.loansTable, elements.returnTable].forEach((table) => {
    if (!table || table.dataset.actionsBound) return;
    table.dataset.actionsBound = "1";
    table.addEventListener("click", onLoanClick);
  });

  if (elements.requestsList && !elements.requestsList.dataset.actionsBound) {
    elements.requestsList.dataset.actionsBound = "1";
    elements.requestsList.addEventListener("click", async (event) => {
      const approveBtn = event.target.closest("[data-approve]");
      const rejectBtn = event.target.closest("[data-reject]");
      if (!approveBtn && !rejectBtn) return;
      event.preventDefault();
      const id = Number((approveBtn || rejectBtn).getAttribute("data-approve") || (approveBtn || rejectBtn).getAttribute("data-reject"));
      const item = state.requests.find((r) => r.id === id);
      try {
        if (approveBtn) {
          const dueAt = defaultDueDate();
          await api(`/api/library/requests/${id}/approve`, { method: "POST", body: JSON.stringify({ dueAt }) });
          showToast(`Запрос на книгу «${item?.title || ""}» одобрен, выдача оформлена.`);
        } else {
          const ok = await showConfirm({ title: "Отклонить запрос", message: `Отклонить запрос на «${item?.title || "книгу"}»?` });
          if (!ok) return;
          await api(`/api/library/requests/${id}/reject`, { method: "POST", body: JSON.stringify({ notes: "Нет доступного экземпляра" }) });
          showToast(`Запрос отклонён.`, "error");
        }
        await loadDashboard();
      } catch (error) {
        showError(error);
      }
    });
  }
}

function renderHistory() {
  const returned = state.loans.filter((loan) => ["returned", "lost"].includes(loan.status));
  if (!returned.length) {
    elements.historyList.innerHTML = '<div class="empty-state">История пока пустая.</div>';
    renderPagerBar(elements.historyPager, { page: 1, pageSize: PAGE_SIZE.history, total: 0, onPage: () => {} });
    return;
  }
  const perPage = PAGE_SIZE.history;
  const pages = Math.max(1, Math.ceil(returned.length / perPage));
  if (state.ui.historyPage > pages) state.ui.historyPage = pages;
  const page = Math.max(1, state.ui.historyPage);
  const slice = returned.slice((page - 1) * perPage, page * perPage);
  elements.historyList.innerHTML = slice.map((loan) => `<article class="timeline-item"><div class="timeline-item__type">${loanLabels[loan.status]}</div><div class="timeline-item__title">${loan.title}</div><div class="timeline-item__meta">Выдано ${formatDate(loan.issued_at)} • возвращено ${formatDate(loan.returned_at)}</div></article>`).join("");
  renderPagerBar(elements.historyPager, {
    page, pageSize: perPage, total: returned.length,
    onPage: (p) => { state.ui.historyPage = p; renderHistory(); },
  });
}

function renderPatrons() {
  if (!state.patrons.length) {
    elements.patronsTable.innerHTML = '<tr><td colspan="6" class="muted-cell">Нет читателей.</td></tr>';
    renderPagerBar(elements.patronsPager, { page: 1, pageSize: PAGE_SIZE.patrons, total: 0, onPage: () => {} });
    return;
  }
  const perPage = PAGE_SIZE.patrons;
  const pages = Math.max(1, Math.ceil(state.patrons.length / perPage));
  if (state.ui.patronsPage > pages) state.ui.patronsPage = pages;
  const page = Math.max(1, state.ui.patronsPage);
  const slice = state.patrons.slice((page - 1) * perPage, page * perPage);
  const adminActions = (p) => (state.auth.user.role === "admin"
    ? `<button class="table-button" data-patron-edit="${p.id}">Изменить</button><button class="table-button danger" data-patron-delete="${p.id}">Удалить</button>`
    : "");
  elements.patronsTable.innerHTML = slice.map((p) => `<tr><td data-label="Читатель">${p.full_name}<div class="small-text">${p.email || p.phone || ""}</div></td><td data-label="Билет">${p.card_number}</td><td data-label="Статус">${p.status === "active" ? "Активный" : "Заблокирован"}</td><td data-label="На руках">${p.active_loans}</td><td data-label="Просрочено">${p.overdue_loans || 0}</td><td class="actions-cell" data-label="Действия"><button type="button" class="table-button" data-patron-profile="${p.id}">Профиль</button>${adminActions(p)}</td></tr>`).join("");
  slice.forEach((p) => {
    document.querySelector(`[data-patron-profile="${p.id}"]`)?.addEventListener("click", () => openPatronProfile(p.id));
    document.querySelector(`[data-patron-edit="${p.id}"]`)?.addEventListener("click", () => openPatronFormModal(p));
    document.querySelector(`[data-patron-delete="${p.id}"]`)?.addEventListener("click", async () => {
      const ok = await showConfirm({ title: "Удалить читателя", message: `Удалить ${p.full_name}?`, okLabel: "Удалить", danger: true });
      if (!ok) return;
      await api(`/api/library/patrons/${p.id}`, { method: "DELETE" });
      showToast(`Читатель ${p.full_name} удалён.`);
      await loadDashboard();
    });
  });
  renderPagerBar(elements.patronsPager, {
    page, pageSize: perPage, total: state.patrons.length,
    onPage: (p) => { state.ui.patronsPage = p; renderPatrons(); },
  });
}

function renderReports() {
  const popular = state.reports.popularBooks || [];
  const debtors = state.reports.debtors || [];
  elements.reportsList.innerHTML = `<article class="timeline-item"><div class="timeline-item__type">Популярные книги</div>${popular.map((b) => `<p>${escapeHtml(b.title)} — выдач: ${b.loans_count}</p>`).join("") || "<p>Нет данных.</p>"}</article><article class="timeline-item timeline-item--danger"><div class="timeline-item__type">Задолженности</div>${debtors.map((d) => `<p>${escapeHtml(d.full_name)} (${escapeHtml(d.card_number)}) — просрочек: ${d.overdue_count}</p>`).join("") || "<p>Нет должников.</p>"}</article>`;
}

function renderUsers() {
  if (!state.users.length) {
    elements.usersTable.innerHTML = '<tr><td colspan="5" class="muted-cell">Нет пользователей.</td></tr>';
    renderPagerBar(elements.usersPager, { page: 1, pageSize: PAGE_SIZE.users, total: 0, onPage: () => {} });
    return;
  }
  const perPage = PAGE_SIZE.users;
  const pages = Math.max(1, Math.ceil(state.users.length / perPage));
  if (state.ui.usersPage > pages) state.ui.usersPage = pages;
  const page = Math.max(1, state.ui.usersPage);
  const slice = state.users.slice((page - 1) * perPage, page * perPage);
  elements.usersTable.innerHTML = slice.map((u) => `<tr><td data-label="Пользователь">${u.full_name}<div class="small-text">${u.card_number || ""}</div></td><td data-label="Email">${u.email || u.username}</td><td data-label="Роль">${roleLabels[canonicalRole(u.role)]}</td><td data-label="Статус">${u.is_active ? "Активен" : "Ожидает подтверждения"}</td><td class="actions-cell" data-label="Действия"><button class="table-button" data-user-edit="${u.id}">Изменить</button>${!u.is_active ? `<button class="table-button" data-user-activate="${u.id}">Подтвердить</button>` : ""}<button class="table-button danger" data-user-delete="${u.id}">Удалить</button></td></tr>`).join("");
  slice.forEach((u) => {
    document.querySelector(`[data-user-edit="${u.id}"]`)?.addEventListener("click", () => openUserFormModal(u));
    document.querySelector(`[data-user-activate="${u.id}"]`)?.addEventListener("click", async () => {
      await api(`/api/admin/users/${u.id}/activate`, { method: "POST" });
      showToast(`Регистрация пользователя ${u.full_name} подтверждена.`);
      await loadDashboard();
    });
    document.querySelector(`[data-user-delete="${u.id}"]`)?.addEventListener("click", async () => {
      const ok = await showConfirm({ title: "Удалить пользователя", message: `Удалить ${u.full_name}?`, okLabel: "Удалить", danger: true });
      if (!ok) return;
      await api(`/api/admin/users/${u.id}`, { method: "DELETE" });
      showToast(`Пользователь ${u.full_name} удалён.`);
      await loadDashboard();
    });
  });
  renderPagerBar(elements.usersPager, {
    page, pageSize: perPage, total: state.users.length,
    onPage: (p) => { state.ui.usersPage = p; renderUsers(); },
  });
}

function copyRowActions(copy) {
  if (!isStaff()) return "";
  const canEdit = ["available", "damaged"].includes(copy.status);
  const canWriteOff = canEdit;
  const canReplace = ["available", "damaged", "lost"].includes(copy.status);
  return `<div class="actions-cell" data-label="Действия">
    ${canEdit ? `<button type="button" class="table-button" data-copy-edit="${copy.id}">Состояние</button>` : ""}
    ${canWriteOff ? `<button type="button" class="table-button danger" data-copy-writeoff="${copy.id}">Списать</button>` : ""}
    ${canReplace ? `<button type="button" class="table-button" data-copy-replace="${copy.id}">Заменить</button>` : ""}
  </div>`;
}

function openCopyEditDialog(copy) {
  if (!elements.copyEditDialog || !elements.copyEditForm) return;
  const form = elements.copyEditForm.elements;
  form.copyId.value = copy.id;
  form.conditionRating.value = copy.condition_rating ?? 5;
  form.status.value = ["available", "damaged"].includes(copy.status) ? copy.status : "available";
  form.acquisitionDate.value = (copy.acquisition_date || "").slice(0, 10);
  form.price.value = copy.price ?? "";
  form.notes.value = copy.notes || "";
  const metaEl = $("copyEditMeta");
  if (metaEl) {
    metaEl.innerHTML = `<div class="copy-edit-meta__code">Инв. № <strong>${escapeHtml(copy.inventory_code)}</strong></div><div class="small-text">Текущий статус: ${copyStatusPill(copy.status)}</div>`;
  }
  elements.copyEditDialog.showModal();
}

function bindCopyRowActions() {
  document.querySelectorAll("[data-copy-edit]").forEach((btn) => {
    btn.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      const id = Number(btn.getAttribute("data-copy-edit"));
      const copy = state.bookCopies.find((c) => c.id === id);
      if (!copy) return;
      openCopyEditDialog(copy);
    });
  });
  document.querySelectorAll("[data-copy-writeoff]").forEach((btn) => {
    btn.addEventListener("click", async (event) => {
      event.stopPropagation();
      try {
        const id = btn.getAttribute("data-copy-writeoff");
        const reason = "Списание по инвентаризации";
        const ok = await showConfirm({ title: "Списать экземпляр", message: "Списать этот экземпляр с полки?", okLabel: "Списать", danger: true });
        if (!ok) return;
        await api(`/api/library/copies/${id}/write-off`, { method: "POST", body: JSON.stringify({ reason }) });
        showToast("Экземпляр списан.");
        await reloadCopiesForSelectedBook();
        await loadDashboard();
      } catch (error) {
        showError(error);
      }
    });
  });
  document.querySelectorAll("[data-copy-replace]").forEach((btn) => {
    btn.addEventListener("click", async (event) => {
      event.stopPropagation();
      try {
        const id = btn.getAttribute("data-copy-replace");
        const ok = await showConfirm({ title: "Замена экземпляра", message: "Создать новый экземпляр взамен этого?" });
        if (!ok) return;
        await api(`/api/library/copies/${id}/replace`, { method: "POST", body: JSON.stringify({}) });
        showToast("Экземпляр заменён: старый помечен как заменённый, новый создан в этой же книге.");
        await reloadCopiesForSelectedBook();
        await loadDashboard();
      } catch (error) {
        showError(error);
      }
    });
  });
}

async function reloadCopiesForSelectedBook() {
  if (!state.selectedBookId) return;
  state.bookCopies = await api(`/api/library/books/${state.selectedBookId}/copies`);
  renderCopies();
}

function renderTransactions() {
  if (!state.transactions.length) {
    elements.transactionsList.innerHTML = '<div class="empty-state">Логи пока пустые.</div>';
    renderPagerBar(elements.transactionsPager, { page: 1, pageSize: PAGE_SIZE.logs, total: 0, onPage: () => {} });
    return;
  }
  const perPage = PAGE_SIZE.logs;
  const pages = Math.max(1, Math.ceil(state.transactions.length / perPage));
  if (state.ui.logsPage > pages) state.ui.logsPage = pages;
  const page = Math.max(1, state.ui.logsPage);
  const slice = state.transactions.slice((page - 1) * perPage, page * perPage);
  elements.transactionsList.innerHTML = slice.map((t) => `<article class="timeline-item"><div class="timeline-item__type">${operationLabels[t.operation_type] || t.operation_type}</div><div class="timeline-item__title">${t.title || "Операция"}</div><div class="timeline-item__meta">${formatDate(t.operation_date)} • ${t.actor_name || "Система"}</div><p>${t.details || ""}</p></article>`).join("");
  renderPagerBar(elements.transactionsPager, {
    page, pageSize: perPage, total: state.transactions.length,
    onPage: (p) => { state.ui.logsPage = p; renderTransactions(); },
  });
}

function copyStatusPill(status) {
  const label = stockLabels[status] || status;
  const cls = copyStatusClasses[status] || "copy-status--neutral";
  return `<span class="copy-status ${cls}">${escapeHtml(label)}</span>`;
}

function renderConditionStars(rating) {
  const n = Math.max(1, Math.min(5, Number(rating) || 5));
  const stars = Array.from({ length: 5 }, (_, index) => `<span class="copy-condition__star${index < n ? " is-filled" : ""}">★</span>`).join("");
  return `<span class="copy-condition" title="Состояние ${n} из 5">${stars}</span>`;
}

function copyNotesCell(copy) {
  if (copy.status === "on_loan" && copy.patron_name) {
    return `<span class="copy-loan-info">${escapeHtml(copy.patron_name)}</span><span class="small-text">вернуть до ${formatDate(copy.due_at)}</span>`;
  }
  const note = copy.notes || copy.written_off_reason;
  return note ? escapeHtml(note) : "—";
}

function filteredCopiesRows(copies = state.bookCopies) {
  const filter = state.ui.copiesStatusFilter || "";
  if (!filter) return copies;
  return copies.filter((copy) => copy.status === filter);
}

function renderCopiesBookHero(book) {
  if (!elements.copiesBookHero || !book) return;
  const initial = escapeHtml(String(book.title || "?").trim().charAt(0) || "?");
  const cover = book.cover_image
    ? `<img src="${book.cover_image}" alt="" loading="lazy" />`
    : `<span class="copies-book-hero__placeholder">${initial}</span>`;
  elements.copiesBookHero.innerHTML = `
    <div class="copies-book-hero__cover">${cover}</div>
    <div class="copies-book-hero__body">
      <div class="copies-book-hero__tags">
        <span class="pill pill--soft">${escapeHtml(book.category || "Без категории")}</span>
        <span class="pill pill--accent">${escapeHtml(stockLabels[book.stock_status] || book.stock_status || "—")}</span>
      </div>
      <h4 class="copies-book-hero__title">${escapeHtml(book.title)}</h4>
      <p class="copies-book-hero__meta">${escapeHtml(book.author)} • ${book.publish_year || "—"} • ISBN ${escapeHtml(book.isbn || "—")}</p>
      <p class="copies-book-hero__shelf">Полка <strong>${escapeHtml(book.shelf_code || "не указана")}</strong> • Замена ${formatMoney(book.replacement_cost)} • Язык ${escapeHtml(book.language || "—")}</p>
    </div>
  `;
}

function renderCopiesStats(copies) {
  if (!elements.copiesStatsRow) return;
  const counts = { available: 0, on_loan: 0, damaged: 0, lost: 0, written_off: 0, replaced: 0 };
  copies.forEach((copy) => {
    if (Object.prototype.hasOwnProperty.call(counts, copy.status)) counts[copy.status] += 1;
  });
  const items = [
    ["На полке", copies.length, ""],
    ["Свободно", counts.available, "copies-stat--ok"],
    ["На руках", counts.on_loan, "copies-stat--loan"],
    ["Повреждены", counts.damaged, "copies-stat--warn"],
    ["Утеряны / списаны", counts.lost + counts.written_off, "copies-stat--muted"],
  ];
  elements.copiesStatsRow.innerHTML = items.map(([label, value, cls]) => `<article class="copies-stat ${cls}"><span>${label}</span><strong>${value}</strong></article>`).join("");
}

function updateCopiesSteps(hasBook) {
  elements.copiesStepPick?.classList.toggle("copies-step--active", !hasBook);
  elements.copiesStepPick?.classList.toggle("copies-step--done", hasBook);
  if (elements.copiesStepPick) {
    elements.copiesStepPick.disabled = !hasBook;
    elements.copiesStepPick.title = hasBook ? "Вернуться к списку книг" : "";
  }
  elements.copiesStepManage?.classList.toggle("copies-step--active", hasBook);
  elements.copiesStepManage?.classList.toggle("copies-step--disabled", !hasBook);
  if (elements.copiesStepManage) elements.copiesStepManage.disabled = true;
}

function setCopiesToolbarVisibility(hasBook) {
  if (elements.changeCopiesBookButton) elements.changeCopiesBookButton.hidden = !hasBook;
  if (elements.refreshCopiesButton) elements.refreshCopiesButton.hidden = !hasBook;
  if (elements.editSelectedBookButton) elements.editSelectedBookButton.hidden = !hasBook;
}

function navigateToRoute(route) {
  if (route === "copies" && state.route === "copies" && state.selectedBookId) {
    clearSelectedBook();
    closeNavDropdowns();
    closeMobileNav();
    applyRouteGuards();
    showToast("Выберите другую книгу из списка.", "info");
    return;
  }
  state.route = route;
  closeNavDropdowns();
  closeMobileNav();
  applyRouteGuards();
}

function filteredCopiesBooks() {
  const q = (state.ui.copiesBookQuery || "").trim().toLowerCase();
  const books = [...state.books].sort((a, b) => String(a.title).localeCompare(String(b.title), "ru"));
  if (!q) return books;
  return books.filter((book) => {
    const hay = `${book.title || ""} ${book.author || ""} ${book.isbn || ""}`.toLowerCase();
    return hay.includes(q);
  });
}

function renderCopiesBookPicker() {
  if (!elements.copiesBookList) return;
  const books = filteredCopiesBooks();
  const perPage = PAGE_SIZE.copiesBooks;
  const total = books.length;
  const pages = Math.max(1, Math.ceil(total / perPage));
  if (state.ui.copiesBookPage > pages) state.ui.copiesBookPage = pages;
  const page = Math.max(1, state.ui.copiesBookPage);
  const slice = books.slice((page - 1) * perPage, page * perPage);

  if (elements.copiesBookCount) {
    elements.copiesBookCount.textContent = total
      ? `${total} ${total === 1 ? "книга" : total < 5 ? "книги" : "книг"}`
      : "0 книг";
  }

  if (!total) {
    const emptyText = state.ui.copiesBookQuery
      ? "По вашему запросу ничего не найдено. Попробуйте другое название, автора или ISBN."
      : "В каталоге пока нет книг. Добавьте издания в разделе «Каталог» или импортируйте CSV в настройках.";
    elements.copiesBookList.innerHTML = `<tr><td colspan="5"><div class="empty-state copies-empty">${emptyText}${state.ui.copiesBookQuery ? "" : '<div class="copies-empty__actions"><button type="button" class="solid-button" data-jump-route="catalog">Открыть каталог</button></div>'}</div></td></tr>`;
    elements.copiesBookList.querySelector("[data-jump-route]")?.addEventListener("click", () => {
      state.route = "catalog";
      applyRouteGuards();
    });
    renderPagerBar(elements.copiesBookPager, { page: 1, pageSize: perPage, total: 0, onPage: () => {} });
    return;
  }

  elements.copiesBookList.innerHTML = slice.map((book) => {
    const avail = Number(book.available_copies || 0);
    const totalCopies = Number(book.total_copies || 0);
    const stockClass = avail > 0 ? "copies-stock--ok" : totalCopies > 0 ? "copies-stock--busy" : "copies-stock--empty";
    return `<tr class="copies-book-row" data-book-row="${book.id}" tabindex="0" role="button" aria-label="Открыть экземпляры «${escapeHtml(book.title)}»">
      <td data-label="Название"><strong>${escapeHtml(book.title)}</strong><span class="small-text copies-book-row__cat">${escapeHtml(book.category || "")}</span></td>
      <td data-label="Автор">${escapeHtml(book.author)}</td>
      <td data-label="ISBN"><code class="copies-isbn">${escapeHtml(book.isbn || "—")}</code></td>
      <td data-label="На полке"><span class="copies-stock ${stockClass}">${totalCopies} <span class="small-text">(своб. ${avail})</span></span></td>
      <td class="actions-cell" data-label=""><button type="button" class="solid-button table-button" data-pick-book="${book.id}">Открыть</button></td>
    </tr>`;
  }).join("");

  slice.forEach((book) => {
    const open = () => selectBook(book.id, book.title).catch(showError);
    document.querySelector(`[data-pick-book="${book.id}"]`)?.addEventListener("click", (event) => {
      event.stopPropagation();
      open();
    });
    const row = document.querySelector(`[data-book-row="${book.id}"]`);
    row?.addEventListener("click", (event) => {
      if (event.target.closest("button")) return;
      open();
    });
    row?.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        open();
      }
    });
  });

  renderPagerBar(elements.copiesBookPager, {
    page, pageSize: perPage, total,
    onPage: (p) => { state.ui.copiesBookPage = p; renderCopiesBookPicker(); },
  });
}

function clearSelectedBook() {
  state.selectedBookId = null;
  state.selectedBookTitle = "";
  state.bookCopies = [];
  state.ui.copiesStatusFilter = "";
  if (elements.copiesStatusFilter) elements.copiesStatusFilter.value = "";
  renderCopies();
}

function renderCopies() {
  if (!elements.copiesTable) return;
  const hasBook = Boolean(state.selectedBookId);
  elements.copiesBookPicker?.classList.toggle("hidden", hasBook);
  elements.copiesPanel?.classList.toggle("hidden", !hasBook);
  setCopiesToolbarVisibility(hasBook);
  updateCopiesSteps(hasBook);

  if (!hasBook) {
    elements.copiesSummary.textContent = state.ui.copiesBookQuery
      ? "Выберите книгу из результатов поиска — откроется учёт экземпляров."
      : "Шаг 1: найдите издание в списке и нажмите «Открыть».";
    elements.copiesTable.innerHTML = "";
    if (elements.copiesBookHero) elements.copiesBookHero.innerHTML = "";
    if (elements.copiesStatsRow) elements.copiesStatsRow.innerHTML = "";
    if (elements.openAddCopiesButton) elements.openAddCopiesButton.disabled = true;
    if (elements.copiesBookSearch && elements.copiesBookSearch.value !== state.ui.copiesBookQuery) {
      elements.copiesBookSearch.value = state.ui.copiesBookQuery;
    }
    renderCopiesBookPicker();
    return;
  }

  const book = state.books.find((b) => b.id === state.selectedBookId);
  const copies = state.bookCopies || [];
  const visibleCopies = filteredCopiesRows(copies);
  renderCopiesBookHero(book);
  renderCopiesStats(copies);
  elements.copiesSummary.textContent = `Шаг 2: учёт экземпляров «${state.selectedBookTitle || book?.title || "Книга"}». Всего ${copies.length}, показано ${visibleCopies.length}.`;

  elements.copiesTable.innerHTML = visibleCopies.length
    ? visibleCopies.map((copy) => `<tr>
        <td data-label="Инв. №"><code class="copies-inv">${escapeHtml(copy.inventory_code)}</code></td>
        <td data-label="Статус">${copyStatusPill(copy.status)}</td>
        <td data-label="Состояние">${renderConditionStars(copy.condition_rating)}</td>
        <td data-label="Поступление">${formatDate(copy.acquisition_date)}</td>
        <td data-label="Читатель / примечание">${copyNotesCell(copy)}</td>
        <td>${copyRowActions(copy)}</td>
      </tr>`).join("")
    : `<tr><td colspan="6"><div class="empty-state copies-empty">${copies.length ? "Нет экземпляров с выбранным статусом." : "Экземпляров пока нет. Нажмите «Добавить экземпляры» — система выдаст инвентарные номера."}</div></td></tr>`;

  if (elements.addCopiesForm?.elements.bookId) {
    elements.addCopiesForm.elements.bookId.value = state.selectedBookId || "";
  }
  if (elements.openAddCopiesButton) elements.openAddCopiesButton.disabled = false;
  bindCopyRowActions();
}

function populateControls() {
  fillSelect($("categoryFilter"), state.meta.categories, "Все категории", (item) => ({ value: item.id, label: item.name }));
  fillSelect($("languageFilter"), state.meta.languages, "Все языки", (item) => ({ value: item, label: item }));
  fillSelect($("stockStatusFilter"), state.meta.stockStatuses, "Любой статус", (item) => ({ value: item.value, label: item.label }));
  fillSelect($("bookCategory"), state.meta.categories, "Выберите категорию", (item) => ({ value: item.id, label: item.name }));
  rebuildIssueSelects();
  if (elements.settingsForm) {
    const sf = elements.settingsForm.elements;
    sf.max_loan_days.value = state.settings.max_loan_days || 14;
    sf.fine_policy.value = state.settings.fine_policy || "";
    if (sf.library_contact_email) sf.library_contact_email.value = state.settings.library_contact_email || state.contact?.email || "";
    if (sf.library_contact_phone) sf.library_contact_phone.value = state.settings.library_contact_phone || state.contact?.phone || "";
    if (sf.library_site_name) sf.library_site_name.value = state.settings.library_site_name || state.contact?.siteName || "";
    if (sf.library_work_hours) sf.library_work_hours.value = state.settings.library_work_hours || state.contact?.workHours || "";
    if (sf.library_vk_url) sf.library_vk_url.value = state.settings.library_vk_url || state.contact?.vkUrl || "";
    if (sf.library_max_url) sf.library_max_url.value = state.settings.library_max_url || state.contact?.maxUrl || "";
    if (sf.library_demo_reset_links) {
      sf.library_demo_reset_links.checked = String(state.settings.library_demo_reset_links || "true").toLowerCase() !== "false";
    }
  }
  renderFooter();
  updateCatalogFilterSummary();
}

function openForgotPasswordDialog() {
  elements.loginDialog?.close();
  elements.forgotEmailForm?.reset();
  $("forgotEmailMessage")?.classList.add("hidden");
  elements.forgotPasswordDialog?.showModal();
}

function openResetPasswordDialog(token) {
  if (!elements.resetPasswordForm) return;
  elements.resetPasswordForm.reset();
  elements.resetPasswordForm.elements.token.value = token;
  $("resetPasswordMessage")?.classList.add("hidden");
  elements.resetPasswordDialog?.showModal();
}

function checkResetTokenInUrl() {
  const token = new URLSearchParams(window.location.search).get("reset");
  if (!token) return;
  openResetPasswordDialog(token);
  const url = new URL(window.location.href);
  url.searchParams.delete("reset");
  window.history.replaceState({}, "", url.pathname + url.search);
}

function isReader() {
  return state.auth.user.role === "reader";
}

const SOCIAL_ICON_VK = `<svg class="social-icon" viewBox="0 0 48 48" width="36" height="36" aria-hidden="true"><rect width="48" height="48" rx="12" fill="#0077FF"/><path fill="#fff" d="M8 14h6.2c.5 3.8 1.6 6.6 3.4 8.4-2.2 1.6-4.6 3.4-6.6 5.8h7.8l3.2-4.6c2.4 2.2 4.8 4.8 6.4 8.2H32l-4.2-6.8c2.8-2.4 5.2-5.8 6.8-10.2H27l-2.8 5.6c-.8 1.6-1.8 3-3 4.2l-.2-9.8H8z"/></svg>`;
const SOCIAL_ICON_MAX = `<svg class="social-icon" viewBox="0 0 48 48" width="36" height="36" aria-hidden="true"><rect width="48" height="48" rx="12" fill="#7B5CFF"/><path fill="#fff" d="M14 30V18h5.4l4.2 7.4V18H29v12h-5.2l-4.4-7.6V30H14zm14.2 0 5.8-12L34 18h6.2l-3.4 6.8L40 30h-6l-3.4-6.6L27 30h-2.8z"/></svg>`;

function profileInitials(name) {
  const parts = String(name || "").trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0] || ""}${parts[parts.length - 1][0] || ""}`.toUpperCase();
}

function bindProfileQuickActions(root) {
  root?.querySelectorAll("[data-jump-route]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.route = btn.dataset.jumpRoute;
      applyRouteGuards();
    });
  });
}

function renderProfileBooksList(title, items, emptyText) {
  if (!items?.length) {
    return `<section class="profile-section"><h4 class="profile-section__title">${escapeHtml(title)}</h4><p class="small-text">${escapeHtml(emptyText)}</p></section>`;
  }
  const rows = items.map((item) => `
    <article class="profile-book-row">
      <div class="profile-book-row__title">${escapeHtml(item.title)}</div>
      <div class="profile-book-row__meta">${escapeHtml(item.author || "")}${item.dueAt ? ` • вернуть до ${formatDate(item.dueAt)}` : ""}${item.returnedAt ? ` • возвращено ${formatDate(item.returnedAt)}` : item.issuedAt && !item.returnedAt ? ` • выдано ${formatDate(item.issuedAt)}` : ""}</div>
    </article>
  `).join("");
  return `<section class="profile-section"><h4 class="profile-section__title">${escapeHtml(title)}</h4><div class="profile-book-list">${rows}</div></section>`;
}

function renderProfileStatsGrid(stats) {
  const cells = [
    ["Прочитано", stats.booksRead],
    ["На руках", stats.booksOnHand],
    ["Запросы", stats.requestsTotal],
    ["Избранное", stats.favoritesCount],
  ];
  return `<div class="profile-stats">${cells.map(([label, value]) => `
    <article class="profile-stat">
      <span class="profile-stat__value">${Number(value) || 0}</span>
      <span class="profile-stat__label">${escapeHtml(label)}</span>
    </article>
  `).join("")}</div>`;
}

function renderProfilePanelContent(profile, { staffView = false } = {}) {
  const user = state.auth.user;
  const patronStatus = profile.patronStatus === "blocked" ? "Заблокирован" : profile.patronStatus === "active" ? "Активный" : "—";
  const favoritesCount = staffView ? 0 : loadFavoriteIds().length;
  const stats = {
    booksRead: profile.booksRead ?? 0,
    booksOnHand: profile.booksOnHand ?? 0,
    requestsTotal: profile.requestsTotal ?? 0,
    favoritesCount,
  };
  const memberSince = profile.memberSince ? formatDate(profile.memberSince) : "—";
  const quickNav = staffView
    ? ""
    : `<div class="profile-quick">
        <button type="button" class="ghost-button" data-jump-route="my-books">Мои книги</button>
        <button type="button" class="ghost-button" data-jump-route="history">История</button>
        <button type="button" class="ghost-button" data-jump-route="requests">Запросы</button>
        <button type="button" class="ghost-button" data-jump-route="favorites">Избранное</button>
        <button type="button" class="ghost-button" data-jump-route="catalog">Каталог</button>
      </div>`;
  return `
    <div class="profile-hero">
      <div class="profile-avatar" aria-hidden="true">${escapeHtml(profileInitials(profile.fullName || user.fullName))}</div>
      <div class="profile-hero__main">
        <h4 class="profile-hero__name">${escapeHtml(profile.fullName || user.fullName || "—")}</h4>
        <p class="small-text profile-hero__sub">${escapeHtml(profile.email || user.email || user.username || "")}</p>
        ${staffView ? `<p class="small-text">Билет ${escapeHtml(profile.cardNumber || "—")} • ${escapeHtml(patronStatus)}</p>` : `<p class="small-text">Читатель с ${escapeHtml(memberSince)}</p>`}
      </div>
    </div>
    ${renderProfileStatsGrid(stats)}
    <dl class="profile-card profile-card--details">
      <div><dt>Читательский билет</dt><dd>${escapeHtml(profile.cardNumber || user.cardNumber || "—")}</dd></div>
      <div><dt>Статус</dt><dd>${escapeHtml(patronStatus)}</dd></div>
      <div><dt>Телефон</dt><dd>${escapeHtml(profile.phone || user.phone || "—")}</dd></div>
      <div><dt>Тип записи</dt><dd>${escapeHtml(profile.membershipType || user.membershipType || "—")}</dd></div>
      ${profile.overdueLoans > 0 ? `<div><dt>Просрочено</dt><dd class="profile-warn">${profile.overdueLoans}</dd></div>` : ""}
      ${profile.requestsPending > 0 ? `<div><dt>Ожидают ответа</dt><dd>${profile.requestsPending} запрос(ов)</dd></div>` : ""}
    </dl>
    ${renderProfileBooksList("Сейчас на руках", profile.activeLoans, "Нет активных выдач.")}
    ${renderProfileBooksList("Недавно прочитано", profile.recentRead, "История выдач пока пуста — как только вернёте книгу, она появится здесь.")}
    ${quickNav}
  `;
}

function renderProfile() {
  const el = elements.profilePanel;
  if (!el) return;
  const user = state.auth.user;
  const reader = isReader();
  const hintEl = $("profilePanelHint");
  if (user.role === "guest") {
    if (hintEl) hintEl.textContent = "Войдите через «Личный кабинет» в шапке.";
    el.innerHTML = '<div class="empty-state">Войдите в аккаунт, чтобы открыть профиль.</div>';
    return;
  }
  $("profileToolbar")?.classList.toggle("hidden", !reader);
  if (reader && state.profile) {
    if (hintEl) hintEl.textContent = "Краткая сводка по вашей учётной записи и выдачам.";
    el.innerHTML = renderProfilePanelContent(state.profile);
    bindProfileQuickActions(el);
    return;
  }
  if (hintEl) {
    hintEl.textContent = reader
      ? "Профиль читателя появится после привязки читательского билета."
      : "Учётная запись сотрудника библиотеки.";
  }
  const patronStatus = user.patronStatus === "blocked" ? "Заблокирован" : user.patronStatus === "active" ? "Активный" : "—";
  const readerFields = reader
    ? `
      <div><dt>Читательский билет</dt><dd>${escapeHtml(user.cardNumber || "не привязан")}</dd></div>
      <div><dt>Статус читателя</dt><dd>${escapeHtml(patronStatus)}</dd></div>
      <div><dt>Телефон</dt><dd>${escapeHtml(user.phone || "—")}</dd></div>`
    : "";
  const staffNote = !reader
    ? `<p class="small-text form-field-hint">Рабочие разделы: каталог, учёт копий, выдача, читатели${user.role === "admin" ? ", пользователи, обращения, настройки" : ""}. Профили читателей — во вкладке «Читатели».</p>`
    : "";
  el.innerHTML = `
    <div class="profile-hero">
      <div class="profile-avatar profile-avatar--staff" aria-hidden="true">${escapeHtml(profileInitials(user.fullName))}</div>
      <div class="profile-hero__main">
        <h4 class="profile-hero__name">${escapeHtml(user.fullName || "—")}</h4>
        <p class="small-text">${escapeHtml(roleLabels[user.role] || user.role)}</p>
      </div>
    </div>
    <dl class="profile-card">
      <div><dt>Email</dt><dd>${escapeHtml(user.email || user.username || "—")}</dd></div>
      ${readerFields}
    </dl>
    ${staffNote}
  `;
}

function openPasswordDialog() {
  if (!isReader()) {
    showToast("Смена пароля доступна читателям в личном кабинете.", "info");
    return;
  }
  elements.passwordForm?.reset();
  elements.passwordDialog?.showModal();
}

function openMessagesPage(forceNew = false) {
  const role = state.auth.user.role;
  if (role === "guest") {
    showToast("Войдите в аккаунт, чтобы открыть чат.", "info");
    state.route = "account";
    applyRouteGuards();
    return;
  }
  state.ui.chatNew = Boolean(forceNew);
  state.route = "messages";
  applyRouteGuards();
}

function openSupportDialog() {
  openMessagesPage(false);
}

function updateStaffRequestBadges(pending = pendingRequestCount()) {
  const n = Math.max(0, Number(pending) || 0);
  const label = n > 99 ? "99+" : String(n);
  const show = isOpsStaff() && n > 0;
  ["navStaffWorkBadge", "navStaffRequestsBadge"].forEach((id) => {
    const el = $(id);
    if (!el) return;
    el.textContent = label;
    el.classList.toggle("hidden", !show);
  });
}

function updateNavBadges(count) {
  const n = Math.max(0, Number(count) || 0);
  const label = n > 99 ? "99+" : String(n);
  const role = state.auth.user.role;
  const showOn = {
    admin: ["navAdminBadge", "navAdminMessagesBadge"],
    reader: ["navReaderCabinetBadge"],
    librarian: ["navStaffCabinetBadge"],
    manager: ["navStaffCabinetBadge"],
  }[role] || [];
  ["navAdminBadge", "navAdminMessagesBadge", "navReaderCabinetBadge", "navStaffCabinetBadge"].forEach((id) => {
    const el = $(id);
    if (!el) return;
    const show = showOn.includes(id) && n > 0;
    el.textContent = label;
    el.classList.toggle("hidden", !show);
  });
  updateStaffRequestBadges();
}

function setChatLayoutMode(isAdmin) {
  $("chatLayout")?.classList.toggle("chat-layout--solo", !isAdmin);
  elements.chatThreadList?.classList.toggle("hidden", !isAdmin);
}

async function refreshSupportUnread() {
  if (state.auth.user.role === "guest") {
    state.supportUnread = 0;
    updateNavBadges(0);
    return;
  }
  try {
    const data = await api("/api/support/unread-count");
    state.supportUnread = data.count || 0;
  } catch {
    state.supportUnread = state.chatThreads.filter((t) => t.unread).length;
  }
  updateNavBadges(state.supportUnread);
}

async function loadChatThreads() {
  state.chatThreads = await api("/api/support/threads");
  await refreshSupportUnread();
}

function renderChatThreadList() {
  const el = elements.chatThreadList;
  if (!el || state.auth.user.role !== "admin") return;
  if (!state.chatThreads.length) {
    el.innerHTML = '<p class="small-text chat-sidebar__empty">Диалогов пока нет</p>';
    return;
  }
  el.innerHTML = state.chatThreads.map((t) => `
    <button type="button" class="chat-thread${state.activeChatThreadId === t.id ? " is-active" : ""}${t.unread ? " chat-thread--unread" : ""}" data-chat-thread="${t.id}">
      <span class="chat-thread__title">${escapeHtml(t.subject)}</span>
      <span class="chat-thread__meta">${escapeHtml(t.senderName || "")}${t.unread ? '<span class="chat-thread__dot" aria-hidden="true"></span>' : ""}</span>
      <span class="chat-thread__preview">${escapeHtml(t.preview || "")}</span>
    </button>
  `).join("");
  el.querySelectorAll("[data-chat-thread]").forEach((btn) => {
    btn.addEventListener("click", () => {
      openChatThread(Number(btn.getAttribute("data-chat-thread"))).catch(showError);
    });
  });
}

function renderChatMessages(messages) {
  const el = elements.chatMessages;
  if (!el) return;
  if (!messages?.length) {
    el.innerHTML = '<div class="chat-empty">Сообщений пока нет</div>';
    return;
  }
  el.innerHTML = messages.map((m) => `
    <div class="chat-bubble${m.isFromStaff ? " chat-bubble--staff" : " chat-bubble--user"}">
      <div class="chat-bubble__meta">${escapeHtml(m.senderName)} • ${formatDate(m.createdAt)}</div>
      <div class="chat-bubble__text">${escapeHtml(m.body)}</div>
    </div>
  `).join("");
  el.scrollTop = el.scrollHeight;
}

function setChatPageHint(text) {
  const hint = $("chatPageHint");
  if (!hint) return;
  if (text) {
    hint.textContent = text;
    hint.classList.remove("hidden");
  } else {
    hint.textContent = "";
    hint.classList.add("hidden");
  }
}

function setAdminChatHead(title, sub) {
  const head = elements.chatThreadHead;
  if (!head) return;
  head.classList.remove("hidden");
  head.innerHTML = `
    <h4 class="chat-main__title">${escapeHtml(title)}</h4>
    ${sub ? `<p class="small-text">${escapeHtml(sub)}</p>` : ""}
  `;
}

function hideChatThreadHead() {
  elements.chatThreadHead?.classList.add("hidden");
  if (elements.chatThreadHead) elements.chatThreadHead.innerHTML = "";
}

async function openChatThread(threadId, { refreshList = true } = {}) {
  const isAdmin = state.auth.user.role === "admin";
  state.activeChatThreadId = threadId;
  const data = await api(`/api/support/threads/${threadId}`);
  const thread = data.thread;
  if (isAdmin) {
    setAdminChatHead(thread.subject, thread.senderName || "");
  } else {
    hideChatThreadHead();
  }
  renderChatMessages(data.messages);
  elements.chatNewThreadForm?.classList.add("hidden");
  elements.chatComposeForm?.classList.remove("hidden");
  state.ui.chatNew = false;
  if (isAdmin && refreshList) {
    await loadChatThreads();
    renderChatThreadList();
  }
  await refreshSupportUnread();
}

async function renderAdminChatPage(token) {
  setChatPageHint("Выберите диалог слева.");
  setChatLayoutMode(true);
  await loadChatThreads();
  if (token !== chatRenderToken) return;

  renderChatThreadList();
  if (!state.chatThreads.length) {
    state.activeChatThreadId = null;
    hideChatThreadHead();
    elements.chatMessages.innerHTML = '<div class="chat-empty">Пока нет обращений</div>';
    elements.chatComposeForm?.classList.add("hidden");
    elements.chatNewThreadForm?.classList.add("hidden");
    return;
  }

  const threadId = state.activeChatThreadId && state.chatThreads.some((t) => t.id === state.activeChatThreadId)
    ? state.activeChatThreadId
    : state.chatThreads[0].id;
  await openChatThread(threadId, { refreshList: false });
}

async function renderUserChatPage(token) {
  setChatPageHint("");
  setChatLayoutMode(false);
  hideChatThreadHead();
  await loadChatThreads();
  if (token !== chatRenderToken) return;

  const thread = state.chatThreads[0] || null;
  if (thread && !state.ui.chatNew) {
    await openChatThread(thread.id, { refreshList: false });
    if (token !== chatRenderToken) return;
    return;
  }

  state.activeChatThreadId = null;
  elements.chatMessages.innerHTML = '<div class="chat-empty">Напишите сообщение администратору</div>';
  elements.chatComposeForm?.classList.add("hidden");
  elements.chatNewThreadForm?.classList.remove("hidden");
}

async function renderChatPage() {
  const role = state.auth.user.role;
  if (role === "guest") return;
  const token = ++chatRenderToken;
  try {
    if (role === "admin") {
      await renderAdminChatPage(token);
    } else {
      await renderUserChatPage(token);
    }
  } catch (error) {
    if (token === chatRenderToken) showError(error);
  }
}

async function openPatronProfile(patronId) {
  try {
    const profile = await api(`/api/library/patrons/${patronId}/profile`);
    if (elements.patronProfileTitle) {
      elements.patronProfileTitle.textContent = profile.fullName || "Профиль читателя";
    }
    if (elements.patronProfileBody) {
      elements.patronProfileBody.innerHTML = renderProfilePanelContent(profile, { staffView: true });
    }
    elements.patronProfileDialog?.showModal();
  } catch (error) {
    showError(error);
  }
}

function initSpotlightImages() {
  document.querySelectorAll(".spotlight-card__img[data-fallback]").forEach((img) => {
    const fallback = img.getAttribute("data-fallback");
    if (!fallback) return;
    img.addEventListener("error", () => {
      if (img.dataset.fallbackUsed) return;
      img.dataset.fallbackUsed = "1";
      img.src = fallback;
    }, { once: false });
  });
}

function setAnalyticsTab(tab) {
  state.ui.analyticsTab = tab;
  document.querySelectorAll("[data-analytics-tab]").forEach((btn) => {
    btn.classList.toggle("is-active", btn.dataset.analyticsTab === tab);
  });
  $("analyticsReportsPane")?.classList.toggle("hidden", tab !== "reports");
  $("analyticsLogsPane")?.classList.toggle("hidden", tab !== "logs");
}

function syncRoleNavVisibility() {
  const role = state.auth.user.role;
  document.querySelectorAll(".admin-only-nav").forEach((el) => {
    el.classList.toggle("hidden", role !== "admin");
  });
  document.querySelectorAll(".staff-nav").forEach((el) => {
    el.classList.toggle("hidden", !isStaff());
  });
  document.querySelectorAll(".staff-only").forEach((el) => {
    el.classList.toggle("hidden", !isStaff());
  });
  document.querySelectorAll(".visitor-only").forEach((el) => {
    el.classList.toggle("hidden", isStaff());
  });
  document.querySelectorAll(".reader-only").forEach((el) => {
    el.classList.toggle("hidden", role !== "reader");
  });
  document.querySelectorAll(".logged-in-nav").forEach((el) => {
    el.classList.toggle("hidden", role === "guest");
  });
  document.querySelectorAll(".staff-cabinet-nav").forEach((el) => {
    el.classList.toggle("hidden", !["librarian", "manager"].includes(role));
  });
  document.querySelectorAll(".catalog-staff-only").forEach((el) => {
    el.classList.toggle("hidden", !isCatalogStaff());
  });
  updateNavBadges(state.supportUnread);
}

function setAccountTab(tab) {
  document.querySelectorAll("[data-account-tab]").forEach((btn) => {
    btn.classList.toggle("is-active", btn.dataset.accountTab === tab);
  });
  $("accountPaneLogin")?.classList.toggle("is-active", tab === "login");
  $("accountPaneRegister")?.classList.toggle("is-active", tab === "register");
}

function syncNavBackdrop() {
  const open = document.querySelector(".nav-dropdown.is-open");
  $("navBackdrop")?.classList.toggle("is-visible", Boolean(open));
}

function closeNavDropdowns(except) {
  document.querySelectorAll(".nav-dropdown.is-open").forEach((dd) => {
    if (except && dd === except) return;
    dd.classList.remove("is-open");
  });
  syncNavBackdrop();
}

function setFiltersDrawerOpen(open) {
  const drawer = $("filtersDrawer");
  const btn = $("toggleFiltersBtn");
  if (!drawer) return;
  drawer.classList.toggle("is-closed", !open);
  if (btn) btn.setAttribute("aria-expanded", open ? "true" : "false");
  if (open) {
    requestAnimationFrame(() => {
      drawer.scrollIntoView({ behavior: "smooth", block: "nearest" });
    });
  }
}

function updateCatalogFilterSummary() {
  const el = $("catalogFilterSummary");
  if (!el || !elements.filtersForm) return;
  if (state.auth.user.role === "guest") {
    el.textContent = "";
    return;
  }
  const parts = [];
  const f = elements.filtersForm.elements;
  const cat = f.categoryId?.selectedOptions?.[0];
  if (cat?.value) parts.push(cat.text);
  if (f.language?.value) parts.push(f.language.value);
  const stock = f.stockStatus?.selectedOptions?.[0];
  if (stock?.value) parts.push(stock.text);
  const sort = f.bookSort?.value;
  if (sort && sort !== "alphaAsc") {
    const sortLabels = { alphaDesc: "Я–А", yearDesc: "новые", yearAsc: "старые" };
    parts.push(sortLabels[sort] || sort);
  }
  if (f.yearFrom?.value || f.yearTo?.value) {
    parts.push(`год ${f.yearFrom?.value || "…"}–${f.yearTo?.value || "…"}`);
  }
  el.textContent = parts.length ? `Фильтры: ${parts.join(" · ")}` : "";
}

function bindNavDropdowns() {
  document.querySelectorAll(".nav-dropdown").forEach((dropdown) => {
    const trigger = dropdown.querySelector(".nav-tab--dropdown");
    if (!trigger || dropdown.dataset.dropdownBound) return;
    dropdown.dataset.dropdownBound = "1";
    trigger.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      const willOpen = !dropdown.classList.contains("is-open");
      closeNavDropdowns();
      if (willOpen) dropdown.classList.add("is-open");
      syncNavBackdrop();
    });
  });
  if (!document.body.dataset.navDropdownCloseBound) {
    document.body.dataset.navDropdownCloseBound = "1";
    $("navBackdrop")?.addEventListener("click", () => closeNavDropdowns());
    document.addEventListener("click", (event) => {
      if (event.target.closest(".nav-dropdown")) return;
      closeNavDropdowns();
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") closeNavDropdowns();
    });
  }
}

function renderFooter() {
  const c = state.contact || {};
  const s = state.settings || {};
  const siteName = (s.library_site_name || c.siteName || "Библиотека").trim() || "Библиотека";
  const phone = (s.library_contact_phone || c.phone || "").trim();
  const email = (s.library_contact_email || c.email || "").trim();
  const hours = (s.library_work_hours || c.workHours || "").trim();
  const vk = (s.library_vk_url || c.vkUrl || "").trim();
  const maxUrl = (s.library_max_url || c.maxUrl || "").trim();
  if ($("siteNameTitle")) $("siteNameTitle").textContent = siteName;
  if ($("footerSiteName")) $("footerSiteName").textContent = siteName;
  if ($("footerPhone")) $("footerPhone").innerHTML = formatFooterLine("Тел.", phone);
  if ($("footerEmail")) $("footerEmail").innerHTML = formatFooterLine("Email", email);
  if ($("footerHours")) {
    $("footerHours").innerHTML = formatFooterBlock("График работы", hours, "График работы уточняйте по телефону");
  }
  if ($("footerYear")) $("footerYear").textContent = `© ${new Date().getFullYear()} ${siteName}`;
  const social = $("footerSocialLinks");
  if (social) {
    const links = [];
    if (vk) {
      links.push(`<a href="${escapeHtml(vk)}" target="_blank" rel="noopener noreferrer" title="ВКонтакте" class="social-link social-link--vk">${SOCIAL_ICON_VK}<span>ВКонтакте</span></a>`);
    }
    if (maxUrl) {
      links.push(`<a href="${escapeHtml(maxUrl)}" target="_blank" rel="noopener noreferrer" title="MAX" class="social-link social-link--max">${SOCIAL_ICON_MAX}<span>MAX</span></a>`);
    }
    social.innerHTML = links.length ? links.join("") : '<span class="small-text">Ссылки на соцсети задаются в настройках администратора</span>';
  }
}

const MOBILE_NAV_GROUPS = [
  {
    title: "Основное",
    items: [
      { route: "home", label: "Главная" },
      { route: "catalog", label: "Каталог" },
    ],
  },
  {
    title: "О библиотеке",
    items: [
      { route: "readers-info", label: "Читателям" },
      { route: "news", label: "Новости" },
      { route: "about", label: "О нас" },
      { route: "faq", label: "Вопросы и ответы" },
    ],
  },
  {
    title: "Мой кабинет",
    roles: ["reader"],
    items: [
      { route: "cabinet", label: "Профиль" },
      { route: "my-books", label: "Мои книги" },
      { route: "requests", label: "Запросы" },
      { route: "history", label: "История" },
      { route: "favorites", label: "Избранное" },
      { route: "messages", label: "Сообщения" },
    ],
  },
  {
    title: "Работа",
    staff: true,
    items: [
      { route: "copies", label: "Экземпляры" },
      { route: "return", label: "Выдача и возврат" },
      { route: "patrons", label: "Читатели" },
      { route: "requests", label: "Запросы на выдачу" },
    ],
  },
  {
    title: "Отчёты",
    staff: true,
    items: [{ route: "analytics", label: "Отчёты и журнал" }],
  },
  {
    title: "Кабинет сотрудника",
    roles: ["librarian", "manager"],
    items: [
      { route: "cabinet", label: "Профиль" },
      { route: "messages", label: "Сообщения" },
    ],
  },
  {
    title: "Админ",
    roles: ["admin"],
    items: [
      { route: "users", label: "Пользователи" },
      { route: "messages", label: "Сообщения" },
      { route: "settings", label: "Настройки" },
      { route: "cabinet", label: "Профиль" },
    ],
  },
  {
    title: "Вход",
    roles: ["guest"],
    items: [{ route: "account", label: "Личный кабинет / регистрация" }],
  },
];

function getAllowedRoutes(role = state.auth.user.role) {
  const catalogStaffRoutes = ["home", "catalog", "copies", "requests", "return", "patrons", "analytics", "about", "faq"];
  const managerRoutes = ["home", "catalog", "requests", "return", "analytics", "about", "faq", "cabinet", "messages"];
  return {
    guest: ["home", "catalog", "account", ...SITE_PAGES],
    reader: ["home", "catalog", "cabinet", "requests", "my-books", "history", "favorites", "messages", ...SITE_PAGES],
    manager: managerRoutes,
    librarian: [...catalogStaffRoutes, "cabinet", "messages"],
    admin: [...catalogStaffRoutes, "users", "messages", "settings", "cabinet"],
  }[role] || ["home", "catalog"];
}

function closeMobileNav() {
  $("mobileNavDrawer")?.classList.remove("is-open");
  $("mobileNavDrawer")?.setAttribute("aria-hidden", "true");
  $("mobileNavToggle")?.setAttribute("aria-expanded", "false");
  $("navBackdrop")?.classList.remove("is-visible");
}

function openMobileNav() {
  renderMobileNav();
  $("mobileNavDrawer")?.classList.add("is-open");
  $("mobileNavDrawer")?.setAttribute("aria-hidden", "false");
  $("mobileNavToggle")?.setAttribute("aria-expanded", "true");
  $("navBackdrop")?.classList.add("is-visible");
}

function renderMobileNav() {
  const list = $("mobileNavList");
  if (!list) return;
  const role = state.auth.user.role;
  const allowed = new Set(getAllowedRoutes(role));
  const html = MOBILE_NAV_GROUPS.map((group) => {
    if (group.roles && !group.roles.includes(role)) return "";
    if (group.staff && !isStaff()) return "";
    const items = group.items.filter((item) => allowed.has(item.route));
    if (!items.length) return "";
    return `<div class="mobile-nav-group"><p class="mobile-nav-group__title">${escapeHtml(group.title)}</p>${items
      .map(
        (item) =>
          `<button type="button" class="mobile-nav-group__item${state.route === item.route ? " is-active" : ""}" data-mobile-route="${item.route}">${escapeHtml(item.label)}</button>`
      )
      .join("")}</div>`;
  }).join("");
  list.innerHTML = html || '<p class="small-text">Нет доступных разделов.</p>';
  list.querySelectorAll("[data-mobile-route]").forEach((btn) => {
    btn.addEventListener("click", () => {
      navigateToRoute(btn.getAttribute("data-mobile-route"));
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  });
}

function bindMobileNav() {
  if (document.body.dataset.mobileNavUiBound) return;
  document.body.dataset.mobileNavUiBound = "1";
  $("mobileNavToggle")?.addEventListener("click", () => {
    if ($("mobileNavDrawer")?.classList.contains("is-open")) closeMobileNav();
    else openMobileNav();
  });
  $("mobileNavClose")?.addEventListener("click", closeMobileNav);
  $("navBackdrop")?.addEventListener("click", () => {
    closeNavDropdowns();
    closeMobileNav();
  });
}

function applyRouteGuards() {
  const role = state.auth.user.role;
  const allowed = getAllowedRoutes(role);
  document.querySelectorAll("[data-nav-link][data-route]").forEach((tab) => {
    const route = tab.dataset.route;
    tab.classList.toggle("hidden", !allowed.includes(route));
    tab.classList.toggle("is-active", route === state.route);
  });
  if (role === "guest" && state.route === "cabinet") state.route = "account";
  if (role === "reader" && state.route === "account") state.route = "cabinet";
  if (!allowed.includes(state.route)) {
    state.route = ["guest", "reader"].includes(role) ? "home" : "catalog";
  }
  closeNavDropdowns();
  document.querySelectorAll("[data-page]").forEach((page) => page.classList.toggle("is-active", page.dataset.page === state.route));
  if (state.route === "analytics") setAnalyticsTab(state.ui.analyticsTab || "reports");
  if (state.route === "copies" && isCatalogStaff()) renderCopies();
  if (state.route === "favorites") renderFavorites();
  if (state.route === "requests") renderRequests();
  if (state.route === "my-books") renderLoans(elements.loansTable, false, elements.loansPager, "loansReaderPage", PAGE_SIZE.loans);
  if (state.route === "history") renderHistory();
  if (state.route === "messages" && state.auth.user.role !== "guest") {
    renderChatPage().catch(showError);
  }
  renderFooter();
  renderMobileNav();
}

function renderByRole() {
  renderStats(state.stats || {});
  renderBooks();
  renderCopies();
  renderRequests();
  renderLoans(elements.loansTable, false, elements.loansPager, "loansReaderPage", PAGE_SIZE.loans);
  renderLoans(elements.returnTable, true, elements.returnPager, "returnPage", PAGE_SIZE.return);
  renderHistory();
  renderPatrons();
  renderReports();
  renderUsers();
  renderTransactions();
  renderFavorites();
  renderProfile();
  syncRoleNavVisibility();
  applyRouteGuards();
  document.querySelectorAll(".admin-only").forEach((node) => node.classList.toggle("hidden", state.auth.user.role !== "admin"));
  document.querySelectorAll(".librarian-only").forEach((node) => node.classList.toggle("hidden", !isCatalogStaff()));
  document.querySelectorAll(".staff-ops-only").forEach((node) => node.classList.toggle("hidden", !isOpsStaff()));
  document.querySelectorAll(".guest-hidden").forEach((node) => node.classList.toggle("hidden", state.auth.user.role === "guest"));
  const staffHeroTitle = document.querySelector(".home-hero--staff .home-hero__title");
  const staffHeroLead = document.querySelector(".home-hero--staff .home-hero__lead");
  if (staffHeroTitle && staffHeroLead && isStaff()) {
    if (isManager()) {
      staffHeroTitle.textContent = "Выдача, возврат и запросы читателей";
      staffHeroLead.textContent = "Менеджер смены: обрабатывайте бронирования, оформляйте выдачу и возврат. Каталог — только просмотр.";
    } else {
      staffHeroTitle.textContent = "Работа с фондом и читателями";
      staffHeroLead.textContent = "Каталог, экземпляры, выдача и отчёты — в меню «Работа» и в разделах выше.";
    }
  }
}

function defaultDueDate() { return new Date(Date.now() + 14 * 86400000).toISOString().slice(0, 10); }
function updateBookCopiesFieldMode(isEdit) {
  document.querySelectorAll(".book-copy-fields-new").forEach((node) => node.classList.toggle("hidden", isEdit));
  $("bookEditCopiesHint")?.classList.toggle("hidden", !isEdit);
  const form = elements.bookForm;
  if (!form) return;
  ["initialCopies", "conditionRating", "acquisitionDate"].forEach((name) => {
    const field = form.elements[name];
    if (!field) return;
    field.disabled = isEdit;
    if (isEdit) field.removeAttribute("required");
    else if (name === "initialCopies") field.removeAttribute("required");
  });
}

function resetBookForm() {
  elements.bookForm?.reset();
  if (elements.bookForm) {
    elements.bookForm.elements.id.value = "";
    elements.bookForm.elements.language.value = "Русский";
    elements.bookForm.elements.conditionRating.value = 5;
    elements.bookForm.elements.acquisitionDate.value = new Date().toISOString().slice(0, 10);
    updateBookCopiesFieldMode(false);
    setCoverPreview("");
  }
}

function resetPatronForm() { elements.patronForm?.reset(); if (elements.patronForm) { elements.patronForm.elements.id.value = ""; elements.patronForm.elements.membershipType.value = "Общий"; elements.patronForm.elements.patronStatus.value = "active"; } }
function setCoverPreview(src) { if (!elements.coverPreview) return; elements.bookForm.elements.coverImage.value = src || ""; elements.deleteCoverButton.classList.toggle("hidden", !src || !elements.bookForm.elements.id.value); elements.coverPreview.innerHTML = src ? `<img src="${src}" alt="Обложка" />` : "Нет обложки"; }
function bookPayloadFromForm() {
  const payload = formToObject(elements.bookForm);
  delete payload.cover;
  if (payload.id) {
    delete payload.initialCopies;
    delete payload.conditionRating;
    delete payload.acquisitionDate;
  }
  return payload;
}
function patronPayloadFromForm() {
  const form = elements.patronForm.elements;
  return {
    id: form.id.value,
    fullName: form.fullName.value.trim(),
    cardNumber: form.cardNumber.value.trim(),
    membershipType: form.membershipType.value.trim() || "Общий",
    phone: form.phone.value.trim(),
    email: form.email.value.trim(),
    address: form.address.value.trim(),
    appUsername: form.appUsername.value.trim(),
    status: form.patronStatus.value === "blocked" ? "blocked" : "active"
  };
}

function fillBookFormFields(book) {
  const form = elements.bookForm.elements;
  form.id.value = book.id;
  form.title.value = book.title;
  form.author.value = book.author;
  form.isbn.value = book.isbn;
  form.categoryId.value = book.category_id;
  form.language.value = book.language;
  form.publishYear.value = book.publish_year;
  form.publisher.value = book.publisher || "";
  form.shelfCode.value = book.shelf_code || "";
  form.replacementCost.value = book.replacement_cost || "";
  form.description.value = book.description || "";
  updateBookCopiesFieldMode(true);
  setCoverPreview(book.cover_image || "");
}

function openBookFormModal(book = null) {
  resetBookForm();
  const titleEl = $("bookFormTitle");
  if (book) {
    fillBookFormFields(book);
    if (titleEl) titleEl.textContent = "Изменить карточку книги";
  } else if (titleEl) titleEl.textContent = "Новая книга";
  elements.bookFormDialog?.showModal();
}

function openPatronFormModal(patron = null) {
  resetPatronForm();
  const titleEl = $("patronFormTitle");
  if (patron) {
    const form = elements.patronForm.elements;
    form.id.value = patron.id;
    form.fullName.value = patron.full_name;
    form.cardNumber.value = patron.card_number;
    form.phone.value = patron.phone || "";
    form.email.value = patron.email || "";
    form.address.value = patron.address || "";
    form.membershipType.value = patron.membership_type || "Общий";
    form.appUsername.value = patron.app_username || "";
    form.patronStatus.value = patron.status === "blocked" ? "blocked" : "active";
    if (titleEl) titleEl.textContent = "Изменить читателя";
  } else if (titleEl) titleEl.textContent = "Новый читатель";
  elements.patronFormDialog?.showModal();
}

function openUserFormModal(user = null) {
  elements.userForm?.reset();
  const form = elements.userForm.elements;
  form.id.value = "";
  form.password.required = true;
  const titleEl = $("userFormTitle");
  if (user) {
    form.id.value = user.id;
    form.fullName.value = user.full_name;
    form.email.value = user.email || user.username;
    form.password.value = "";
    form.password.required = false;
    form.role.value = canonicalRole(user.role);
    form.isActive.value = String(Boolean(user.is_active));
    if (titleEl) titleEl.textContent = "Изменить пользователя";
  } else if (titleEl) titleEl.textContent = "Новый пользователь";
  elements.userFormDialog?.showModal();
}

function openAddCopiesModal() {
  if (!state.selectedBookId) {
    showToast("Сначала выберите книгу в списке.", "error");
    return;
  }
  const titleEl = $("addCopiesBookTitle");
  if (titleEl) titleEl.textContent = state.selectedBookTitle || `Книга #${state.selectedBookId}`;
  const form = elements.addCopiesForm?.elements;
  if (form) {
    form.bookId.value = state.selectedBookId;
    form.count.value = 1;
    form.conditionRating.value = 5;
    if (form.acquisitionDate) form.acquisitionDate.value = new Date().toISOString().slice(0, 10);
  }
  elements.addCopiesDialog?.showModal();
}

async function uploadCover(bookId) { const file = elements.bookForm.elements.cover.files[0]; if (!file) return; if (!file.type.startsWith("image/")) throw new Error("Выберите изображение обложки."); const formData = new FormData(); formData.append("cover", file); await api(`/api/library/books/${bookId}/cover`, { method: "POST", body: formData }); }
async function selectBook(bookId, title = "") {
  state.selectedBookId = bookId;
  state.selectedBookTitle = title;
  state.ui.copiesStatusFilter = "";
  if (elements.copiesStatusFilter) elements.copiesStatusFilter.value = "";
  state.bookCopies = await api(`/api/library/books/${bookId}/copies`);
  state.route = "copies";
  renderCopies();
  applyRouteGuards();
  showToast(`Открыт учёт экземпляров «${title || "книги"}».`, "info");
}

async function loadDashboard() {
  const skipKeys = new Set(["bookSort"]);
  const params = new URLSearchParams();
  new FormData(elements.filtersForm).forEach((value, key) => {
    if (skipKeys.has(key)) return;
    if (String(value).trim()) params.append(key, value);
  });
  const data = await api(`/api/library/bootstrap?${params.toString()}`);
  Object.assign(state, {
    books: data.books || [], patrons: data.patrons || [], loans: data.loans || [], requests: data.requests || [],
    users: data.users || [], transactions: data.transactions || [], availableCopies: data.availableCopies || [],
    reports: data.reports || {}, settings: data.settings || {}, contact: data.contact || {},
    meta: data.meta || state.meta, stats: data.stats || {}, profile: data.profile || null,
    supportUnread: data.supportUnread ?? 0,
  });
  setUser(data.user || state.auth.user);
  updateNavBadges(state.supportUnread);
  populateControls();
  renderByRole();
}

async function refreshAuth() { try { const result = await api("/api/auth/me"); setUser(result.user); } catch { setToken(""); setUser(null); } }
async function login(credentials) { const result = await api("/api/auth/login", { method: "POST", body: JSON.stringify(credentials) }); setToken(result.token); setUser(result.user); }
function showError(error) {
  if (isPageUnloading) return;
  if (error?.name === "AbortError" || error?.message === "Failed to fetch") return;
  showToast(error.message || "Ошибка", "error");
}

function bindForm(el, event, handler) {
  if (el) el.addEventListener(event, handler);
}

function setupPagerDelegations() {
  bindPagerDelegation(elements.catalogPager, () => {
    const perPage = Math.max(1, Number(elements.catalogPerPage?.value || 12));
    const pages = Math.max(1, Math.ceil(state.books.length / perPage));
    return { page: Math.min(Math.max(1, state.ui.catalogPage), pages), pages };
  }, (page) => {
    state.ui.catalogPage = page;
    renderBooks();
  });
  bindPagerDelegation(elements.requestsPager, () => {
    const pages = Math.max(1, Math.ceil((state.requests?.length || 0) / PAGE_SIZE.requests));
    return { page: Math.min(Math.max(1, state.ui.requestsPage), pages), pages };
  }, (page) => {
    state.ui.requestsPage = page;
    renderRequests();
  });
  bindPagerDelegation(elements.loansPager, () => {
    const total = state.loans.length;
    const pages = Math.max(1, Math.ceil(total / PAGE_SIZE.loans));
    return { page: Math.min(Math.max(1, state.ui.loansReaderPage), pages), pages };
  }, (page) => {
    state.ui.loansReaderPage = page;
    renderLoans(elements.loansTable, false, elements.loansPager, "loansReaderPage", PAGE_SIZE.loans);
  });
  bindPagerDelegation(elements.returnPager, () => {
    const total = state.loans.filter((loan) => ["active", "renewed", "overdue"].includes(loan.status)).length;
    const pages = Math.max(1, Math.ceil(total / PAGE_SIZE.return));
    return { page: Math.min(Math.max(1, state.ui.returnPage), pages), pages };
  }, (page) => {
    state.ui.returnPage = page;
    renderLoans(elements.returnTable, true, elements.returnPager, "returnPage", PAGE_SIZE.return);
  });
  bindPagerDelegation(elements.historyPager, () => {
    const total = state.loans.filter((loan) => ["returned", "lost"].includes(loan.status)).length;
    const pages = Math.max(1, Math.ceil(total / PAGE_SIZE.history));
    return { page: Math.min(Math.max(1, state.ui.historyPage), pages), pages };
  }, (page) => {
    state.ui.historyPage = page;
    renderHistory();
  });
  bindPagerDelegation(elements.patronsPager, () => {
    const pages = Math.max(1, Math.ceil((state.patrons?.length || 0) / PAGE_SIZE.patrons));
    return { page: Math.min(Math.max(1, state.ui.patronsPage), pages), pages };
  }, (page) => {
    state.ui.patronsPage = page;
    renderPatrons();
  });
  bindPagerDelegation(elements.usersPager, () => {
    const pages = Math.max(1, Math.ceil((state.users?.length || 0) / PAGE_SIZE.users));
    return { page: Math.min(Math.max(1, state.ui.usersPage), pages), pages };
  }, (page) => {
    state.ui.usersPage = page;
    renderUsers();
  });
  bindPagerDelegation(elements.transactionsPager, () => {
    const pages = Math.max(1, Math.ceil((state.transactions?.length || 0) / PAGE_SIZE.logs));
    return { page: Math.min(Math.max(1, state.ui.logsPage), pages), pages };
  }, (page) => {
    state.ui.logsPage = page;
    renderTransactions();
  });
}

function bindEvents() {
  let debounceTimer;
  if (!elements.filtersForm || !elements.navTabs) {
    console.error("Критические элементы интерфейса не найдены.");
    return;
  }
  setupPagerDelegations();
  bindMobileNav();
  elements.filtersForm.addEventListener("submit", (event) => {
    event.preventDefault();
    state.ui.catalogPage = 1;
    loadDashboard().catch(showError);
  });
  elements.filtersForm.addEventListener("input", (event) => {
    if (event.target.name === "search") {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => { state.ui.catalogPage = 1; loadDashboard().catch(showError); }, 280);
    }
  });
  elements.filtersForm.addEventListener("change", (event) => {
    updateCatalogFilterSummary();
    if (event.target?.name === "bookSort") {
      state.ui.catalogPage = 1;
      renderBooks();
    }
  });
  elements.bookSort?.addEventListener("change", () => {
    state.ui.catalogPage = 1;
    updateCatalogFilterSummary();
    renderBooks();
  });
  elements.catalogPerPage?.addEventListener("change", () => { state.ui.catalogPage = 1; renderBooks(); });
  $("toggleFiltersBtn")?.addEventListener("click", () => {
    const drawer = $("filtersDrawer");
    setFiltersDrawerOpen(drawer?.classList.contains("is-closed"));
  });
  $("applyFiltersBtn")?.addEventListener("click", () => {
    state.ui.catalogPage = 1;
    updateCatalogFilterSummary();
    loadDashboard().catch(showError);
    setFiltersDrawerOpen(false);
  });
  $("resetFilters")?.addEventListener("click", () => {
    const search = elements.filtersForm.elements.search?.value || "";
    elements.filtersForm.reset();
    if (elements.filtersForm.elements.search) elements.filtersForm.elements.search.value = search;
    state.ui.catalogPage = 1;
    updateCatalogFilterSummary();
    showToast("Фильтры сброшены.");
    loadDashboard().catch(showError);
  });
  $("issueCopyFilter")?.addEventListener("input", rebuildIssueSelects);
  $("issuePatronFilter")?.addEventListener("input", rebuildIssueSelects);
  $("refreshCopiesButton")?.addEventListener("click", () => reloadCopiesForSelectedBook().catch(showError));
  document.querySelectorAll("[data-nav-link]").forEach((el) => {
    el.addEventListener("click", (event) => {
      const route = el.dataset.route;
      if (!route) return;
      if (el.tagName === "A") event.preventDefault();
      navigateToRoute(route);
    });
  });
  document.body.addEventListener("click", (event) => {
    const jump = event.target.closest("[data-jump-route]");
    if (!jump) return;
    event.preventDefault();
    navigateToRoute(jump.dataset.jumpRoute);
  });
  $("homeLoginBtn")?.addEventListener("click", () => {
    state.route = "account";
    applyRouteGuards();
  });
  $("confirmOkBtn")?.addEventListener("click", () => finishConfirm(true));
  $("confirmCancelBtn")?.addEventListener("click", () => finishConfirm(false));
  elements.confirmDialog?.addEventListener("cancel", (event) => {
    event.preventDefault();
    finishConfirm(false);
  });
  document.querySelectorAll("[data-analytics-tab]").forEach((btn) => {
    btn.addEventListener("click", () => setAnalyticsTab(btn.dataset.analyticsTab));
  });
  elements.openNewBookButton?.addEventListener("click", () => openBookFormModal());
  elements.openNewUserButton?.addEventListener("click", () => openUserFormModal());
  elements.openNewPatronButton?.addEventListener("click", () => openPatronFormModal());
  elements.openAddCopiesButton?.addEventListener("click", () => openAddCopiesModal());
  elements.changeCopiesBookButton?.addEventListener("click", () => clearSelectedBook());
  elements.copiesBackToListButton?.addEventListener("click", () => clearSelectedBook());
  elements.copiesStepPick?.addEventListener("click", () => {
    if (state.selectedBookId) clearSelectedBook();
  });
  elements.copiesBookSearch?.addEventListener("input", () => {
    state.ui.copiesBookQuery = elements.copiesBookSearch.value || "";
    state.ui.copiesBookPage = 1;
    renderCopiesBookPicker();
  });
  elements.copiesStatusFilter?.addEventListener("change", () => {
    state.ui.copiesStatusFilter = elements.copiesStatusFilter.value || "";
    renderCopies();
  });
  $("closeBookFormButton")?.addEventListener("click", () => elements.bookFormDialog?.close());
  $("closeUserFormButton")?.addEventListener("click", () => elements.userFormDialog?.close());
  $("closePatronFormButton")?.addEventListener("click", () => elements.patronFormDialog?.close());
  $("closeAddCopiesButton")?.addEventListener("click", () => elements.addCopiesDialog?.close());
  elements.openAccountButton?.addEventListener("click", () => {
    state.route = "account";
    applyRouteGuards();
  });
  elements.authUserChip?.addEventListener("click", () => {
    if (state.auth.user.role === "guest") return;
    state.route = "cabinet";
    applyRouteGuards();
  });
  $("closePatronProfileButton")?.addEventListener("click", () => elements.patronProfileDialog?.close());
  bindNavDropdowns();
  document.querySelectorAll("[data-account-tab]").forEach((btn) => {
    btn.addEventListener("click", () => setAccountTab(btn.dataset.accountTab));
  });
  $("accountForgotBtn")?.addEventListener("click", () => openForgotPasswordDialog());
  bindForm($("accountLoginForm"), "submit", async (event) => {
    event.preventDefault();
    const message = $("accountLoginMessage");
    message?.classList.add("hidden");
    try {
      await login(formToObject($("accountLoginForm")));
      $("accountLoginForm")?.reset();
      showToast(`Вы вошли как ${state.auth.user.fullName || roleLabels[state.auth.user.role]}.`);
      state.route = state.auth.user.role === "reader" ? "cabinet" : "catalog";
      await loadDashboard();
    } catch (error) {
      if (message) {
        message.textContent = error.message || "Не удалось войти.";
        message.classList.remove("hidden");
      } else {
        showError(error);
      }
    }
  });
  bindForm($("accountRegisterForm"), "submit", async (event) => {
    event.preventDefault();
    const message = $("accountRegisterMessage");
    const submitButton = $("accountRegisterSubmit");
    message?.classList.add("hidden");
    submitButton.disabled = true;
    submitButton.textContent = "Отправляем...";
    try {
      await api("/api/auth/register", { method: "POST", body: JSON.stringify(formToObject($("accountRegisterForm"))) });
      $("accountRegisterForm")?.reset();
      if (message) {
        message.className = "form-message form-message--success";
        message.textContent = "Заявка отправлена. После подтверждения администратором войдите во вкладке «Вход».";
        message.classList.remove("hidden");
      }
      setAccountTab("login");
      showToast("Заявка на регистрацию отправлена.");
    } catch (error) {
      if (message) {
        message.className = "form-message";
        message.textContent = error.message || "Не удалось отправить заявку.";
        message.classList.remove("hidden");
      } else {
        showError(error);
      }
    } finally {
      submitButton.disabled = false;
      submitButton.textContent = "Отправить заявку";
    }
  });
  elements.openForgotPasswordButton?.addEventListener("click", () => openForgotPasswordDialog());
  elements.closeForgotPasswordButton?.addEventListener("click", () => elements.forgotPasswordDialog?.close());
  elements.closeResetPasswordButton?.addEventListener("click", () => elements.resetPasswordDialog?.close());
  bindForm(elements.forgotEmailForm, "submit", async (event) => {
    event.preventDefault();
    const msg = $("forgotEmailMessage");
    try {
      const payload = formToObject(elements.forgotEmailForm);
      const result = await api("/api/auth/forgot-password", { method: "POST", body: JSON.stringify({ email: payload.email }) });
      if (msg) {
        msg.className = "form-message form-message--success";
        if (result.resetUrl) {
          msg.innerHTML = `${escapeHtml(result.message || "")} ${escapeHtml(result.demoNote || "")} <a href="${escapeHtml(result.resetUrl)}">Перейти к смене пароля</a>`;
        } else {
          msg.textContent = [result.message, result.demoNote].filter(Boolean).join(" ");
        }
        msg.classList.remove("hidden");
      }
      showToast(result.resetUrl ? "Ссылка для сброса готова." : "Запрос принят.");
    } catch (error) {
      if (msg) {
        msg.className = "form-message";
        msg.textContent = error.message;
        msg.classList.remove("hidden");
      } else {
        showError(error);
      }
    }
  });
  bindForm(elements.resetPasswordForm, "submit", async (event) => {
    event.preventDefault();
    const msg = $("resetPasswordMessage");
    try {
      const payload = formToObject(elements.resetPasswordForm);
      if (payload.newPassword !== payload.newPasswordConfirm) throw new Error("Пароли не совпадают.");
      const result = await api("/api/auth/reset-password", {
        method: "POST",
        body: JSON.stringify({ token: payload.token, newPassword: payload.newPassword }),
      });
      elements.resetPasswordDialog?.close();
      showToast(result.message || "Пароль обновлён. Войдите с новым паролем.");
      elements.loginDialog?.showModal();
    } catch (error) {
      if (msg) {
        msg.className = "form-message";
        msg.textContent = error.message;
        msg.classList.remove("hidden");
      } else {
        showError(error);
      }
    }
  });
  $("closeLoginButton").addEventListener("click", () => elements.loginDialog.close());
  $("closeRegisterButton").addEventListener("click", () => {
    elements.registerDialog.close();
    elements.registerForm.reset();
  });
  elements.loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const message = $("loginMessage");
    message?.classList.add("hidden");
    try {
      await login(formToObject(elements.loginForm));
      elements.loginDialog.close();
      elements.loginForm.reset();
      if (isStaff()) state.route = "catalog";
      else if (state.auth.user.role === "reader") state.route = "home";
      showToast(`Вы вошли как ${state.auth.user.fullName || roleLabels[state.auth.user.role]}.`);
      await loadDashboard();
    } catch (error) {
      if (message) {
        message.textContent = error.message || "Не удалось войти.";
        message.classList.remove("hidden");
      } else {
        showError(error);
      }
    }
  });
  elements.registerForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const message = $("registerMessage");
    const submitButton = $("registerSubmitButton");
    message?.classList.add("hidden");
    submitButton.disabled = true;
    submitButton.textContent = "Отправляем...";
    try {
      await api("/api/auth/register", { method: "POST", body: JSON.stringify(formToObject(elements.registerForm)) });
      elements.registerForm.reset();
      if (message) {
        message.textContent = "Заявка отправлена. Администратор подтвердит аккаунт во вкладке «Пользователи», после этого вы сможете войти.";
        message.classList.remove("hidden");
      }
      submitButton.textContent = "Заявка отправлена";
    } catch (error) {
      if (message) {
        message.textContent = error.message || "Не удалось отправить заявку.";
        message.classList.remove("hidden");
      } else {
        showError(error);
      }
      submitButton.disabled = false;
      submitButton.textContent = "Отправить заявку";
    }
  });
  document.querySelectorAll("[data-toggle-password]").forEach((button) => {
    button.addEventListener("click", () => {
      const input = button.closest(".password-field")?.querySelector("input");
      if (!input) return;
      const isHidden = input.type === "password";
      input.type = isHidden ? "text" : "password";
      button.textContent = isHidden ? "Скрыть" : "Показать";
    });
  });
  elements.bookDetailsCloseButton?.addEventListener("click", () => elements.bookDetailsDialog?.close());
  elements.closeCopyEditButton?.addEventListener("click", () => elements.copyEditDialog?.close());
  bindForm(elements.copyEditForm, "submit", async (event) => {
    event.preventDefault();
    try {
      const payload = formToObject(elements.copyEditForm);
      await api(`/api/library/copies/${payload.copyId}`, {
        method: "PUT",
        body: JSON.stringify({
          conditionRating: Number(payload.conditionRating),
          status: payload.status,
          acquisitionDate: payload.acquisitionDate,
          price: payload.price || null,
          notes: payload.notes || "",
        }),
      });
      elements.copyEditDialog?.close();
      showToast("Данные экземпляра сохранены.");
      await reloadCopiesForSelectedBook();
    } catch (error) {
      showError(error);
    }
  });
  bindForm(elements.addCopiesForm, "submit", async (event) => {
    event.preventDefault();
    try {
      const payload = formToObject(elements.addCopiesForm);
      const bookId = payload.bookId || state.selectedBookId;
      if (!bookId) throw new Error("Сначала выберите книгу в каталоге.");
      const count = Number(payload.count);
      if (!Number.isFinite(count) || count < 1) throw new Error("Укажите, сколько экземпляров добавить.");
      const ok = await showConfirm({ title: "Добавить экземпляры", message: `Добавить ${count} экземпляр(ов) к этой книге?` });
      if (!ok) return;
      await api(`/api/library/books/${bookId}/copies`, {
        method: "POST",
        body: JSON.stringify({
          count: Number(payload.count),
          conditionRating: Number(payload.conditionRating),
          acquisitionDate: payload.acquisitionDate,
        }),
      });
      showToast(`Добавлено экземпляров: ${count}.`);
      elements.addCopiesDialog?.close();
      elements.addCopiesForm.elements.count.value = 1;
      await reloadCopiesForSelectedBook();
      await loadDashboard();
    } catch (error) {
      showError(error);
    }
  });
  elements.logoutButton.addEventListener("click", async () => { setToken(""); setUser(null); showToast("Вы вышли из аккаунта."); await loadDashboard(); });
  bindForm(elements.bookForm, "submit", async (event) => {
    event.preventDefault();
    try {
      const payload = bookPayloadFromForm();
      const isEdit = Boolean(payload.id);
      if (isEdit && !payload.id) throw new Error("Не удалось определить книгу для сохранения. Откройте карточку снова.");
      const method = isEdit ? "PUT" : "POST";
      const url = isEdit ? `/api/library/books/${payload.id}` : "/api/library/books";
      const targetCopies = Math.max(0, Number(payload.initialCopies || 0));
      const savedRoute = state.route;
      const result = await api(url, { method, body: JSON.stringify(payload) });
      const bookId = result?.id || payload.id;

      await uploadCover(bookId);
      state.lastSavedBookId = String(bookId);
      state.route = isEdit ? savedRoute : "copies";
      if (!isEdit && targetCopies > 0) {
        await selectBook(Number(bookId), payload.title);
      }
      showToast(
        isEdit
          ? `Книга «${payload.title}» сохранена. Экземпляры — в разделе «Работа → Экземпляры».`
          : `Книга «${payload.title}» добавлена${targetCopies ? ` (${targetCopies} экз.)` : ""}.`
      );
      resetBookForm();
      elements.bookFormDialog?.close();
      await loadDashboard();
    } catch (error) {
      showError(error);
    }
  });
  $("resetBookForm")?.addEventListener("click", () => { resetBookForm(); showToast("Форма книги очищена."); });
  elements.deleteCoverButton?.addEventListener("click", async () => {
    try {
      const id = elements.bookForm?.elements.id.value;
      if (!id) return;
      const ok = await showConfirm({ title: "Удалить обложку", message: "Удалить обложку этой книги?" });
      if (!ok) return;
      await api(`/api/library/books/${id}/cover`, { method: "DELETE" });
      setCoverPreview("");
      showToast("Обложка книги удалена.");
      await loadDashboard();
    } catch (error) {
      showError(error);
    }
  });
  elements.bookForm?.elements.cover?.addEventListener("change", () => { const file = elements.bookForm.elements.cover.files[0]; if (file) { elements.coverPreview.innerHTML = `<img src="${URL.createObjectURL(file)}" alt="Новая обложка" />`; showToast("Новая обложка выбрана. Нажмите «Сохранить», чтобы загрузить ее."); } });
  bindForm(elements.patronForm, "submit", async (event) => {
    event.preventDefault();
    try {
      const payload = patronPayloadFromForm();
      const isEdit = Boolean(payload.id);
      await api(isEdit ? `/api/library/patrons/${payload.id}` : "/api/library/patrons", { method: isEdit ? "PUT" : "POST", body: JSON.stringify(payload) });
      showToast(isEdit ? `Читатель ${payload.fullName} сохранён.` : `Читатель ${payload.fullName} добавлен.`);
      resetPatronForm();
      elements.patronFormDialog?.close();
      await loadDashboard();
    } catch (error) {
      showError(error);
    }
  });
  bindForm(elements.issueForm, "submit", async (event) => { event.preventDefault(); try { const payload = formToObject(elements.issueForm); await api("/api/library/loans/issue", { method: "POST", body: JSON.stringify(payload) }); showToast("Выдача книги оформлена."); elements.issueForm.reset(); elements.issueForm.elements.dueAt.value = defaultDueDate(); await loadDashboard(); } catch (error) { showError(error); } });
  bindForm(elements.userForm, "submit", async (event) => {
    event.preventDefault();
    try {
      const payload = formToObject(elements.userForm);
      const isEdit = Boolean(payload.id);
      payload.isActive = payload.isActive === "true";
      if (!isEdit && (!payload.password || payload.password.length < 6)) {
        throw new Error("Для нового пользователя укажите пароль (не короче 6 символов).");
      }
      if (isEdit && !payload.password) delete payload.password;
      const method = isEdit ? "PUT" : "POST";
      const url = isEdit ? `/api/admin/users/${payload.id}` : "/api/admin/users";
      await api(url, { method, body: JSON.stringify(payload) });
      showToast(isEdit ? `Пользователь ${payload.fullName} сохранён.` : `Пользователь ${payload.fullName} создан.`);
      elements.userForm.reset();
      elements.userForm.elements.password.required = true;
      elements.userFormDialog?.close();
      await loadDashboard();
    } catch (error) {
      showError(error);
    }
  });
  bindForm(elements.settingsForm, "submit", async (event) => {
    event.preventDefault();
    try {
      const payload = formToObject(elements.settingsForm);
      const demoBox = elements.settingsForm.elements.library_demo_reset_links;
      if (demoBox) payload.library_demo_reset_links = demoBox.checked ? "true" : "false";
      state.settings = await api("/api/admin/settings", { method: "PUT", body: JSON.stringify(payload) });
      showToast("Настройки системы сохранены.");
      await loadDashboard();
    } catch (error) {
      showError(error);
    }
  });
  bindForm(elements.passwordForm, "submit", async (event) => {
    event.preventDefault();
    try {
      const payload = formToObject(elements.passwordForm);
      if (payload.newPassword !== payload.newPasswordConfirm) throw new Error("Новые пароли не совпадают.");
      await api("/api/auth/password", {
        method: "PUT",
        body: JSON.stringify({
          currentPassword: payload.currentPassword,
          newPassword: payload.newPassword,
        }),
      });
      elements.passwordForm.reset();
      elements.passwordDialog?.close();
      showToast("Пароль успешно изменён.");
    } catch (error) {
      showError(error);
    }
  });
  bindForm(elements.chatComposeForm, "submit", async (event) => {
    event.preventDefault();
    if (!state.activeChatThreadId) return;
    try {
      const payload = formToObject(elements.chatComposeForm);
      await api(`/api/support/threads/${state.activeChatThreadId}/messages`, {
        method: "POST",
        body: JSON.stringify({ body: payload.body }),
      });
      elements.chatComposeForm.reset();
      await openChatThread(state.activeChatThreadId);
      showToast("Сообщение отправлено.");
    } catch (error) {
      showError(error);
    }
  });
  bindForm(elements.chatNewThreadForm, "submit", async (event) => {
    event.preventDefault();
    try {
      const payload = formToObject(elements.chatNewThreadForm);
      const created = await api("/api/support/threads", {
        method: "POST",
        body: JSON.stringify({ subject: payload.subject, body: payload.body }),
      });
      state.ui.chatNew = false;
      elements.chatNewThreadForm.reset();
      state.activeChatThreadId = created.id;
      state.chatThreads = await api("/api/support/threads");
      await renderChatPage();
      showToast("Сообщение отправлено.");
    } catch (error) {
      showError(error);
    }
  });
  $("openPasswordDialogBtn")?.addEventListener("click", openPasswordDialog);
  $("closePasswordDialogBtn")?.addEventListener("click", () => elements.passwordDialog?.close());
  $("footerSupportBtn")?.addEventListener("click", () => openMessagesPage(false));
  elements.editSelectedBookButton?.addEventListener("click", () => {
    const book = state.books.find((b) => b.id === state.selectedBookId);
    if (!book) {
      showToast("Сначала выберите книгу в списке.", "error");
      return;
    }
    openBookFormModal(book);
  });
  elements.exportCatalogBtn?.addEventListener("click", () => exportCatalogCsv().catch(showError));
  elements.downloadCatalogTemplateBtn?.addEventListener("click", () => downloadCatalogTemplate().catch(showError));
  elements.importCatalogInput?.addEventListener("change", (event) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (file) importCatalogCsv(file).catch(showError);
  });
}

async function downloadCatalogTemplate() {
  const response = await fetch("/api/admin/catalog/template", { headers: authHeaders() });
  if (!response.ok) throw new Error("Не удалось скачать шаблон.");
  const blob = await response.blob();
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = "catalog_import_template.csv";
  link.click();
  URL.revokeObjectURL(link.href);
}

async function exportCatalogCsv() {
  const response = await fetch("/api/admin/catalog/export", { headers: authHeaders() });
  if (!response.ok) throw new Error("Не удалось выгрузить каталог.");
  const blob = await response.blob();
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `library-catalog-${new Date().toISOString().slice(0, 10)}.csv`;
  link.click();
  URL.revokeObjectURL(link.href);
  showToast("Каталог выгружен в CSV.");
}

async function importCatalogCsv(file) {
  const statusEl = elements.catalogImportStatus;
  if (!file) return;
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch("/api/admin/catalog/import", {
    method: "POST",
    headers: authHeaders(),
    body: formData,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.message || "Импорт не выполнен.");
  if (statusEl) {
    statusEl.textContent = `Импорт: создано ${payload.created || 0}, обновлено ${payload.updated || 0}, экземпляров ${payload.copiesAdded || 0}.`;
  }
  showToast("Каталог импортирован.");
  await loadDashboard();
}

async function init() {
  if (window.__layoutReady) await window.__layoutReady;
  bindElements();
  window.addEventListener("beforeunload", () => {
    isPageUnloading = true;
  });
  resetBookForm();
  resetPatronForm();
  if (elements.issueForm?.elements.dueAt) elements.issueForm.elements.dueAt.value = defaultDueDate();
  bindEvents();
  bindTableActionDelegation();
  initSpotlightImages();
  checkResetTokenInUrl();
  await refreshAuth();
  await loadDashboard();
}
init().catch(showError);
