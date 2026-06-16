# Library Web System

Веб-система библиотеки на **Flask + PostgreSQL + SPA (HTML/JS/CSS)**.

Учёт книг и экземпляров, выдача и возврат, запросы читателей, роли, журнал операций, импорт и экспорт каталога CSV.

**Демо:** http://147.78.65.84:3001  
**Репозиторий:** https://github.com/Artem7583/Veb-lib

---

## Тестовые аккаунты

Используйте для входа: **Личный кабинет** (кнопка в шапке) → email и пароль.

**Все роли демо-стенда:**

| Email | Пароль | Роль |
|-------|--------|------|
| `reader@example.com` | `reader123` | Читатель |
| `manager@example.com` | `manager123` | **Менеджер смены** |
| `librarian@example.com` | `librarian123` | Библиотекарь |
| `admin@example.com` | `admin123` | Администратор |

| Роль | Email | Пароль | Что проверить |
|------|-------|--------|----------------|
| **Читатель** | `reader@example.com` | `reader123` | Мой кабинет → Мои книги, Запросы, Профиль |
| **Менеджер смены** | `manager@example.com` | `manager123` | Работа → Запросы, Выдача; Отчёты (без каталога/экземпляров) |
| **Библиотекарь** | `librarian@example.com` | `librarian123` | Работа → Экземпляры, Читатели, Выдача; Отчёты |
| **Администратор** | `admin@example.com` | `admin123` | Админ → Пользователи, Настройки, Сообщения |

**Гость** (без входа): Главная, Каталог, регистрация нового читателя.

### Разграничение ролей

| Функция | Менеджер | Библиотекарь | Админ |
|---------|:--------:|:------------:|:-----:|
| Просмотр каталога | ✓ | ✓ | ✓ |
| Карточки книг, экземпляры, списание | — | ✓ | ✓ |
| Запросы читателей (одобрить/отклонить) | ✓ | ✓ | ✓ |
| Выдача, возврат, продление, утеря | ✓ | ✓ | ✓ |
| Читатели (реестр) | — | ✓ | ✓ |
| Отчёты и журнал | ✓ | ✓ | ✓ |
| Пользователи, настройки, CSV | — | — | ✓ |

> Аккаунты действуют на демо-стенде `147.78.65.84:3001`.  
> После локальной загрузки `sql/reset-demo-data.sql` — те же логины.  
> При старте приложения пароль менеджера синхронизируется автоматически (`ensure_demo_manager_user`).

---

## Возможности

| Раздел | Описание |
|--------|----------|
| Каталог | 25 демо-книг с обложками (Open Library), поиск, фильтры, карточки, пагинация |
| Экземпляры | Инв. номер, состояние, статус, замена, списание |
| Выдача | Выдача, возврат, продление, утеря |
| Читатели | Запросы → одобрение → выдача |
| Профиль | История, избранное, смена пароля |
| Поддержка | Сообщения читателя → admin |
| Админ | Пользователи, настройки, импорт/экспорт CSV |

Интерфейс собран из частей в `public/partials/`.

---

## Быстрый старт (Windows)

### Требования

Python 3.11+, PostgreSQL 14+

### Установка

```powershell
cd library-web-system
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### База данных

```sql
CREATE DATABASE library_system;
```

```powershell
copy .env.example .env
# отредактируйте DB_PASSWORD и AUTH_SECRET

psql -U postgres -d library_system -f .\sql\schema.sql
psql -U postgres -d library_system -f .\sql\reset-demo-data.sql
```

### Демо-каталог с обложками (25 книг)

```powershell
.\.venv\Scripts\python.exe .\scripts\seed_book_covers.py
.\.venv\Scripts\python.exe .\scripts\build_catalog_sql.py
psql -U postgres -d library_system -f .\sql\reset-catalog-only.sql
```

Скрипт `seed_book_covers.py` скачивает обложки с Open Library или создаёт цветные JPEG-заглушки с названием книги. Файлы сохраняются в `public/uploads/covers/`.

### Запуск

```powershell
python app.py
```

Откройте http://localhost:3000 и войдите под `admin@example.com` / `admin123`.

### Автотест

```powershell
.\.venv\Scripts\python.exe .\smoke_test.py
```

Ожидается: `SMOKE TESTS PASSED`.

---

## Переменные окружения (`.env`)

```env
PORT=3000
DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=library_system
DB_USER=postgres
DB_PASSWORD=your_password
AUTH_SECRET=change-me-to-random-string
FLASK_DEBUG=true
```

---

## Импорт каталога CSV (admin)

**Админ → Настройки → Каталог книг (CSV для Excel)**

1. Скачать шаблон (`data/catalog_import_template.csv`).
2. Заполнить в Excel (UTF-8, разделитель **точка с запятой**): title, author, isbn, category, language, publish_year, cover_image и др.
3. Импортировать файл. Существующий ISBN обновляется, новый — создаётся с экземплярами.

Категории в системе: **Учебная литература**, **Художественная литература**, **Научно-популярная литература**.

---

## Структура проекта

```
app.py                 — backend, REST API
public/
  partials/            — header, main, footer, dialogs
  js/app.js            — логика интерфейса
  css/styles.css
  img/home/            — баннеры главной
  uploads/covers/      — обложки книг (book-01.jpg … book-25.jpg)
sql/
  schema.sql           — схема БД
  reset-demo-data.sql  — демо-данные и тестовые пользователи
  reset-catalog-only.sql — сброс только каталога (25 книг)
data/
  catalog_books.json   — манифест демо-каталога
  catalog_import_template.csv
scripts/
  seed_book_covers.py  — генерация обложек
  build_catalog_sql.py — сборка reset-catalog-only.sql
  reset_production_catalog.py — сброс каталога на сервере
  deploy_server.py
smoke_test.py          — автотест API
deploy-upgrade.sh
```

---

## Деплой

| Параметр | Значение |
|----------|----------|
| Сервер | 147.78.65.84:3001 |
| Каталог | `/root/library-web-system` |
| Процесс | PM2 `library-web-system` |

```powershell
$env:DEPLOY_PASSWORD = "ваш_пароль_ssh"
.\.venv\Scripts\python.exe .\scripts\deploy_server.py
```

Скрипт не перезаписывает `.env` на сервере. После деплоя обложек и SQL:

```powershell
.\.venv\Scripts\python.exe .\scripts\reset_production_catalog.py
```

---

## API (основное)

| Метод | Путь | Доступ |
|-------|------|--------|
| POST | `/api/auth/login` | все |
| GET | `/api/library/books` | все |
| POST | `/api/library/loans/issue` | manager+ |
| POST | `/api/library/requests` | reader |
| GET | `/api/library/requests` | manager+ |
| GET | `/api/admin/catalog/export` | admin |
| POST | `/api/admin/catalog/import` | admin |
| GET | `/api/health` | all |

---

## Частые проблемы

| Проблема | Решение |
|----------|---------|
| Неверный пароль на демо | Используйте таблицу аккаунтов выше; Ctrl+F5 |
| Нет вкладок на телефоне | Кнопка **«Разделы сайта»** в шапке |
| Пустой каталог локально | Выполните `sql/reset-demo-data.sql`, затем `reset-catalog-only.sql` |
| Обложки не отображаются | Запустите `scripts/seed_book_covers.py`, проверьте пути `/uploads/covers/*.jpg` |
| Ошибка импорта CSV | Кодировка UTF-8, разделитель `;`, уникальный ISBN |
| `ModuleNotFoundError` | Активируйте `.venv`, `pip install -r requirements.txt` |
| Сайт не открывается | Используйте **http://** (не https); проверьте PM2 на сервере |

---

## Лицензия и автор

Проект: [Artem7583/Veb-lib](https://github.com/Artem7583/Veb-lib)
