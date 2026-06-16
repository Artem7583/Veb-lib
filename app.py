import base64
import csv
import hashlib
import hmac
import io
import json
import os
import re
import time
import uuid
import random
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request, send_from_directory
from werkzeug.utils import secure_filename

import psycopg
from psycopg.rows import dict_row


load_dotenv()

APP_DIR = os.path.dirname(os.path.abspath(__file__))
PUBLIC_DIR = os.path.join(APP_DIR, "public")
COVERS_DIR = os.path.join(PUBLIC_DIR, "uploads", "covers")
HOME_IMAGES_DIR = os.path.join(PUBLIC_DIR, "img", "home")
DATA_DIR = os.path.join(APP_DIR, "data")
ALLOWED_COVER_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif"}
ALLOWED_HOME_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
HOME_BANNER_TITLES = {
    "banner-01.jpg": "Александр Пушкин",
    "banner-02.jpg": "Анна Ахматова",
    "banner-03.jpg": "Николай Гоголь",
}
CATALOG_CSV_HEADERS = [
    "title",
    "author",
    "isbn",
    "category",
    "language",
    "publish_year",
    "publisher",
    "shelf_code",
    "description",
    "replacement_cost",
    "cover_image",
    "initial_copies",
]

ROLE_PRIORITY = {
    "guest": 0,
    "reader": 1,
    "borrower": 1,
    "manager": 2,
    "librarian": 3,
    "admin": 4,
}

ROLE_ALIASES = {
    "borrower": "reader",
}

VALID_ACCOUNT_ROLES = {"reader", "librarian", "manager", "admin"}
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

ACTIVE_LOAN_STATUSES = ("active", "renewed", "overdue")

app = Flask(__name__, static_folder=PUBLIC_DIR, static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = 12 * 1024 * 1024


@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({"message": "Файл слишком большой. Загрузите изображение до 12 МБ."}), 413


# Обновленное подключение под стандарт psycopg v3 с сохранением возврата словарей (dict)
def get_connection():
    return psycopg.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "library_system"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "1"),
        row_factory=dict_row,  # Это заменяет psycopg2.extras.RealDictCursor
    )


def query_all(sql, params=None):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, params or [])
            return [dict(row) for row in cursor.fetchall()]


def query_one(sql, params=None):
    rows = query_all(sql, params)
    return rows[0] if rows else None


def execute(sql, params=None):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, params or [])
        connection.commit()


def ensure_upload_dirs():
    os.makedirs(COVERS_DIR, exist_ok=True)
    os.makedirs(HOME_IMAGES_DIR, exist_ok=True)


def list_home_banner_files():
    if not os.path.isdir(HOME_IMAGES_DIR):
        return []
    banners = []
    for name in sorted(os.listdir(HOME_IMAGES_DIR)):
        if name.lower().startswith("readme"):
            continue
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        if ext not in ALLOWED_HOME_IMAGE_EXTENSIONS:
            continue
        title = HOME_BANNER_TITLES.get(name.lower())
        if not title:
            title = name.rsplit(".", 1)[0].replace("-", " ").replace("_", " ").strip()
        banners.append({"url": f"/img/home/{name}", "name": name, "title": title})
    return banners


def normalize_catalog_row(raw_row):
    mapping = {
        "title": "title",
        "название": "title",
        "author": "author",
        "автор": "author",
        "isbn": "isbn",
        "category": "category",
        "категория": "category",
        "language": "language",
        "язык": "language",
        "publish_year": "publish_year",
        "year": "publish_year",
        "год": "publish_year",
        "publisher": "publisher",
        "издатель": "publisher",
        "shelf_code": "shelf_code",
        "полка": "shelf_code",
        "description": "description",
        "описание": "description",
        "replacement_cost": "replacement_cost",
        "цена_замены": "replacement_cost",
        "cover_image": "cover_image",
        "обложка": "cover_image",
        "initial_copies": "initial_copies",
        "экземпляров": "initial_copies",
        "copies": "initial_copies",
    }
    normalized = {}
    for key, value in raw_row.items():
        field = mapping.get(clean_text(key).lower())
        if field:
            value = clean_text(value)
            if field == "replacement_cost":
                value = value.replace(",", ".")
            normalized[field] = value
    return normalized


CATEGORY_ALIASES = {
    "программирование": "Учебная литература",
    "programming": "Учебная литература",
    "учебники": "Учебная литература",
    "классика": "Художественная литература",
    "classics": "Художественная литература",
    "наука": "Научно-популярная литература",
    "science": "Научно-популярная литература",
}


def resolve_category_id(cursor, category_name):
    name = clean_text(category_name)
    if name:
        name = CATEGORY_ALIASES.get(name.lower(), name)
        cursor.execute("SELECT id FROM categories WHERE LOWER(name) = LOWER(%s)", [name])
        row = cursor.fetchone()
        if row:
            return row["id"]
    fallback = query_one("SELECT id FROM categories ORDER BY id ASC LIMIT 1")
    if not fallback:
        raise ValueError("В системе нет категорий для импорта.")
    return fallback["id"]


def normalize_cover_path(value):
    path = clean_text(value)
    if not path:
        return ""
    if path.startswith("/"):
        return path
    return cover_url(secure_filename(os.path.basename(path)))


def build_catalog_csv_rows():
    rows = query_all(
        """
        SELECT
          b.title,
          b.author,
          b.isbn,
          c.name AS category,
          b.language,
          b.publish_year,
          b.publisher,
          b.shelf_code,
          b.description,
          b.replacement_cost,
          b.cover_image,
          COALESCE((
            SELECT COUNT(*)::int
            FROM book_copies bc
            WHERE bc.book_id = b.id AND bc.status IN ('available', 'on_loan', 'damaged')
          ), 0) AS initial_copies
        FROM books b
        JOIN categories c ON c.id = b.category_id
        WHERE NOT b.is_archived
        ORDER BY b.title ASC
        """
    )
    return rows


def catalog_csv_cell(key, value):
    if value is None:
        return ""
    if key == "publish_year":
        try:
            return str(int(value))
        except (TypeError, ValueError):
            return str(value)
    if key == "replacement_cost":
        try:
            number = float(value)
            text = f"{number:.2f}".rstrip("0").rstrip(".")
            return text.replace(".", ",")
        except (TypeError, ValueError):
            return str(value).replace(".", ",")
    text = str(value)
    return text.replace("\r\n", " ").replace("\n", " ").strip()


def catalog_csv_response(filename, rows=None):
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=CATALOG_CSV_HEADERS,
        delimiter=";",
        quoting=csv.QUOTE_MINIMAL,
        lineterminator="\r\n",
        extrasaction="ignore",
    )
    writer.writeheader()
    for row in rows or []:
        writer.writerow({key: catalog_csv_cell(key, row.get(key, "")) for key in CATALOG_CSV_HEADERS})
    payload = buffer.getvalue().encode("utf-8-sig")
    return Response(
        payload,
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def parse_catalog_csv_text(raw):
    sample = raw[:8192]
    delimiter = ";" if sample.count(";") >= sample.count(",") else ","
    reader = csv.DictReader(io.StringIO(raw), delimiter=delimiter)
    if not reader.fieldnames:
        raise ValueError("CSV пустой или без заголовков.")
    rows = list(reader)
    if not rows:
        raise ValueError("В файле нет строк для импорта.")
    return rows


def import_catalog_rows(rows, actor_name):
    created = 0
    updated = 0
    copies_added = 0
    errors = []
    with get_connection() as connection:
        with connection.cursor() as cursor:
            for index, raw_row in enumerate(rows, start=2):
                row = normalize_catalog_row(raw_row)
                title = row.get("title")
                author = row.get("author")
                isbn = row.get("isbn")
                if not title or not author or not isbn:
                    errors.append(f"Строка {index}: нужны title, author, isbn.")
                    continue
                try:
                    publish_year = int(row.get("publish_year") or 2000)
                except (TypeError, ValueError):
                    errors.append(f"Строка {index}: неверный publish_year.")
                    continue
                if publish_year < 1500 or publish_year > 2100:
                    errors.append(f"Строка {index}: год издания вне диапазона 1500–2100.")
                    continue
                try:
                    replacement_cost = float(row.get("replacement_cost") or 0)
                except (TypeError, ValueError):
                    replacement_cost = 0.0
                try:
                    initial_copies = max(0, int(row.get("initial_copies") or 0))
                except (TypeError, ValueError):
                    initial_copies = 0
                category_id = resolve_category_id(cursor, row.get("category"))
                cover_image = normalize_cover_path(row.get("cover_image"))
                language = row.get("language") or "Русский"
                publisher = row.get("publisher") or ""
                shelf_code = row.get("shelf_code") or ""
                description = row.get("description") or ""

                cursor.execute(
                    "SELECT id FROM books WHERE isbn = %s AND NOT is_archived",
                    [isbn],
                )
                existing = cursor.fetchone()
                if existing:
                    book_id = existing["id"]
                    cursor.execute(
                        """
                        UPDATE books
                        SET category_id = %s, title = %s, author = %s, publish_year = %s,
                            language = %s, publisher = %s, shelf_code = %s, description = %s,
                            replacement_cost = %s, cover_image = %s, updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                        """,
                        [
                            category_id,
                            title,
                            author,
                            publish_year,
                            language,
                            publisher,
                            shelf_code,
                            description,
                            replacement_cost,
                            cover_image,
                            book_id,
                        ],
                    )
                    updated += 1
                else:
                    cursor.execute(
                        """
                        INSERT INTO books (
                          category_id, title, author, isbn, publish_year, language,
                          publisher, shelf_code, description, replacement_cost, cover_image
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id, publish_year, replacement_cost
                        """,
                        [
                            category_id,
                            title,
                            author,
                            isbn,
                            publish_year,
                            language,
                            publisher,
                            shelf_code,
                            description,
                            replacement_cost,
                            cover_image,
                        ],
                    )
                    book = dict(cursor.fetchone())
                    book_id = book["id"]
                    created += 1
                    book_payload = {
                        "acquisitionDate": time.strftime("%Y-%m-%d"),
                        "conditionRating": 5,
                    }
                    for _ in range(initial_copies):
                        copy = create_copy(cursor, book, book_payload)
                        copies_added += 1
                        insert_transaction(
                            cursor,
                            {
                                "book_id": book_id,
                                "copy_id": copy["id"],
                                "operation_type": "acquisition",
                                "details": "Импорт каталога",
                                "actor_name": actor_name,
                            },
                        )
                    continue

                if initial_copies > 0:
                    cursor.execute(
                        "SELECT id, publish_year, replacement_cost FROM books WHERE id = %s",
                        [book_id],
                    )
                    book = dict(cursor.fetchone())
                    book_payload = {
                        "acquisitionDate": time.strftime("%Y-%m-%d"),
                        "conditionRating": 5,
                    }
                    for _ in range(initial_copies):
                        copy = create_copy(cursor, book, book_payload)
                        copies_added += 1
                        insert_transaction(
                            cursor,
                            {
                                "book_id": book_id,
                                "copy_id": copy["id"],
                                "operation_type": "acquisition",
                                "details": "Импорт каталога",
                                "actor_name": actor_name,
                            },
                        )
        connection.commit()
    return {"created": created, "updated": updated, "copiesAdded": copies_added, "errors": errors[:20]}


def cover_url(filename):
    return f"/uploads/covers/{filename}"


def cover_path_from_url(path):
    if not path or not path.startswith("/uploads/covers/"):
        return None
    filename = os.path.basename(path)
    full_path = os.path.abspath(os.path.join(COVERS_DIR, filename))
    covers_root = os.path.abspath(COVERS_DIR)
    if os.path.commonpath([covers_root, full_path]) != covers_root:
        return None
    return full_path


def delete_cover_file(path):
    full_path = cover_path_from_url(path)
    if full_path and os.path.exists(full_path):
        os.remove(full_path)


def save_cover_file(file_storage):
    ensure_upload_dirs()
    original_name = secure_filename(file_storage.filename or "")
    extension = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else ""
    if extension not in ALLOWED_COVER_EXTENSIONS:
        raise ValueError("Можно загружать только изображения JPG, PNG, WEBP или GIF.")

    filename = f"{uuid.uuid4().hex}.{extension}"
    file_storage.save(os.path.join(COVERS_DIR, filename))
    return cover_url(filename)


def base64url_encode(data):
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def base64url_decode(data):
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def create_token(user):
    role = normalize_role(user["role"])
    payload = {
        "sub": user["id"],
        "username": user["username"],
        "email": user.get("email", user["username"]),
        "role": role,
        "full_name": user["full_name"],
        "patron_id": user.get("patron_id"),
        "exp": int(time.time()) + 60 * 60 * 12,
    }
    encoded = base64url_encode(json.dumps(payload).encode("utf-8"))
    secret = os.getenv("AUTH_SECRET", "library-secret").encode("utf-8")
    signature = hmac.new(secret, encoded.encode("utf-8"), hashlib.sha256).digest()
    return f"{encoded}.{base64url_encode(signature)}"


def verify_token(token):
    if not token or "." not in token:
        return None

    encoded, received = token.split(".", 1)
    secret = os.getenv("AUTH_SECRET", "library-secret").encode("utf-8")
    expected = base64url_encode(hmac.new(secret, encoded.encode("utf-8"), hashlib.sha256).digest())

    if not hmac.compare_digest(received, expected):
        return None

    try:
        payload = json.loads(base64url_decode(encoded).decode("utf-8"))
    except Exception:
        return None

    if payload.get("exp", 0) < int(time.time()):
        return None

    return payload


def normalize_role(role):
    return ROLE_ALIASES.get(role, role or "guest")


def get_current_user():
    header = request.headers.get("Authorization", "")
    token = header[7:] if header.startswith("Bearer ") else None
    payload = verify_token(token)

    if not payload:
        return {
            "id": None,
            "username": "guest",
            "role": "guest",
            "email": "",
            "full_name": "Посетитель",
            "patron_id": None,
        }

    return {
        "id": payload.get("sub"),
        "username": payload.get("username"),
        "email": payload.get("email", payload.get("username")),
        "role": normalize_role(payload.get("role", "guest")),
        "full_name": payload.get("full_name", "Посетитель"),
        "patron_id": payload.get("patron_id"),
    }


def require_role(min_role):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            user = get_current_user()
            if ROLE_PRIORITY.get(normalize_role(user["role"]), -1) < ROLE_PRIORITY[normalize_role(min_role)]:
                return jsonify({"message": "Недостаточно прав для этой операции."}), 403
            return func(*args, **kwargs)

        return wrapper

    return decorator


def hash_password(password, salt):
    return hashlib.scrypt(password.encode("utf-8"), salt=salt.encode("utf-8"), n=16384, r=8, p=1).hex()


def verify_password(password, stored):
    if ":" not in stored:
        return False
    salt, digest = stored.split(":", 1)
    return hmac.compare_digest(hash_password(password, salt), digest)


def make_password_hash(password):
    salt = uuid.uuid4().hex
    return f"{salt}:{hash_password(password, salt)}"


def validate_email(email):
    return bool(EMAIL_RE.match((email or "").strip()))


def clean_text(value):
    return str(value or "").strip()


def require_fields(payload, fields):
    missing = [field for field in fields if not clean_text(payload.get(field))]
    if missing:
        return f"Заполните обязательные поля: {', '.join(missing)}."
    return None


def current_year():
    return time.localtime().tm_year


def compute_aging(publish_year, acquisition_date, condition_rating):
    acquisition_year = int(str(acquisition_date)[:4])
    age_by_edition = max(0, current_year() - int(publish_year))
    age_by_inventory = max(0, current_year() - acquisition_year)
    condition_wear = max(0, 5 - int(condition_rating))
    raw = age_by_edition / 25 + age_by_inventory / 20 + condition_wear * 0.08
    return round(min(1.5, raw), 2)


def bootstrap_user_payload(user):
    payload = {
        "username": user["username"],
        "email": user.get("email", user["username"]),
        "role": normalize_role(user["role"]),
        "fullName": user["full_name"],
        "patronId": user["patron_id"],
    }
    if user.get("patron_id"):
        patron = query_one(
            """
            SELECT card_number, phone, email, status, membership_type
            FROM patrons
            WHERE id = %s AND NOT is_archived
            """,
            [user["patron_id"]],
        )
        if patron:
            payload["cardNumber"] = patron["card_number"]
            payload["phone"] = patron["phone"] or ""
            payload["patronEmail"] = patron["email"] or ""
            payload["patronStatus"] = patron["status"]
            payload["membershipType"] = patron["membership_type"]
    return payload


def sanitize_book(book, role):
    if role in {"librarian", "manager", "admin"}:
        return book
    hidden = {
        "replacement_cost",
        "final_price",
        "request_count",
        "average_aging",
        "written_off_copies",
        "lost_copies",
        "damaged_copies",
        "on_loan_copies",
    }
    return {key: value for key, value in book.items() if key not in hidden}


def ensure_schema():
    execute("ALTER TABLE books ADD COLUMN IF NOT EXISTS last_copy_number INT NOT NULL DEFAULT 0")
    execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'app_users_role_check'
                  AND conrelid = 'app_users'::regclass
            ) THEN
                ALTER TABLE app_users DROP CONSTRAINT app_users_role_check;
            END IF;
            ALTER TABLE app_users
            ADD CONSTRAINT app_users_role_check
            CHECK (role IN ('reader', 'librarian', 'manager', 'admin', 'borrower'));
        EXCEPTION WHEN duplicate_object THEN
            NULL;
        END $$;
        """
    )
    execute(
        """
        CREATE TABLE IF NOT EXISTS support_messages (
            id SERIAL PRIMARY KEY,
            user_id INT REFERENCES app_users(id) ON DELETE SET NULL,
            sender_name VARCHAR(120) NOT NULL DEFAULT '',
            sender_email VARCHAR(200) NOT NULL DEFAULT '',
            subject VARCHAR(200) NOT NULL DEFAULT '',
            body TEXT NOT NULL DEFAULT '',
            status VARCHAR(20) NOT NULL DEFAULT 'open',
            admin_reply TEXT NOT NULL DEFAULT '',
            unread_for_admin BOOLEAN NOT NULL DEFAULT TRUE,
            unread_for_user BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    execute("ALTER TABLE support_messages ADD COLUMN IF NOT EXISTS unread_for_admin BOOLEAN NOT NULL DEFAULT TRUE")
    execute("ALTER TABLE support_messages ADD COLUMN IF NOT EXISTS unread_for_user BOOLEAN NOT NULL DEFAULT FALSE")
    execute(
        """
        CREATE TABLE IF NOT EXISTS support_chat_messages (
            id SERIAL PRIMARY KEY,
            thread_id INT NOT NULL REFERENCES support_messages(id) ON DELETE CASCADE,
            sender_user_id INT REFERENCES app_users(id) ON DELETE SET NULL,
            is_from_staff BOOLEAN NOT NULL DEFAULT FALSE,
            body TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    migrate_support_threads_to_chat()
    execute(
        """
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            id SERIAL PRIMARY KEY,
            user_id INT NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
            token_hash VARCHAR(128) NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            used_at TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    for key, value in (
        ("library_contact_email", "admin@example.com"),
        ("library_contact_phone", "+7 (391) 200-00-00"),
        ("library_demo_reset_links", "true"),
        ("library_work_hours", "Пн–Пт 9:00–20:00\nСб 10:00–18:00\nВс — выходной"),
        ("library_vk_url", "https://vk.com/"),
        ("library_max_url", "https://max.ru/"),
        ("library_site_name", "Библиотека"),
    ):
        execute(
            """
            INSERT INTO system_settings (key, value)
            VALUES (%s, %s)
            ON CONFLICT (key) DO NOTHING
            """,
            [key, value],
        )
    execute(
        """
        UPDATE books b
        SET last_copy_number = GREATEST(
            b.last_copy_number,
            COALESCE((
                SELECT MAX(
                    CASE
                        WHEN bc.inventory_code ~ '[0-9]+$'
                             AND length(substring(bc.inventory_code FROM '[0-9]+$')) <= 9
                        THEN CAST(substring(bc.inventory_code FROM '[0-9]+$') AS INT)
                        ELSE 0
                    END
                )
                FROM book_copies bc
                WHERE bc.book_id = b.id
            ), 0)
        )
        """
    )
    ensure_demo_manager_user()


MANAGER_DEMO_PASSWORD_HASH = (
    "48cd207b40a44ec0a35dccca4dc513d6:"
    "c05e8145d17cfffc829a14ddb1839a121224aad6ee8fdb98687e49435a7302bb0"
    "fca325f054ebe457e091c43c04ad751e4939cf818bfdd7c32dc9299f9ae13ca"
)


def ensure_demo_manager_user():
    execute(
        """
        UPDATE app_users
        SET role = 'manager',
            password_hash = %s,
            full_name = 'Менеджер смены',
            is_active = TRUE
        WHERE LOWER(email) = 'manager@example.com'
        """,
        [MANAGER_DEMO_PASSWORD_HASH],
    )
    execute(
        """
        INSERT INTO app_users (username, email, full_name, role, password_hash, is_active)
        SELECT 'manager@example.com', 'manager@example.com', 'Менеджер смены', 'manager', %s, TRUE
        WHERE NOT EXISTS (
            SELECT 1 FROM app_users WHERE LOWER(email) = 'manager@example.com'
        )
        """,
        [MANAGER_DEMO_PASSWORD_HASH],
    )


def build_book_filters(args):
    clauses = ["NOT b.is_archived"]
    params = []

    if args.get("search"):
        search = f"%{args['search']}%"
        clauses.append(
            """(b.title ILIKE %s OR b.author ILIKE %s OR b.isbn ILIKE %s 
               OR c.name ILIKE %s OR b.publisher ILIKE %s OR b.shelf_code ILIKE %s 
               OR EXISTS (SELECT 1 FROM book_copies bc WHERE bc.book_id = b.id AND bc.inventory_code ILIKE %s))"""
        )
        params.extend([search, search, search, search, search, search, search])

    if args.get("categoryId"):
        try:
            category_id = int(args["categoryId"])
        except (TypeError, ValueError):
            category_id = None
        if category_id:
            clauses.append("b.category_id = %s")
            params.append(category_id)

    if args.get("language"):
        clauses.append("b.language = %s")
        params.append(args["language"])

    if args.get("yearFrom"):
        try:
            year_from = int(args["yearFrom"])
        except (TypeError, ValueError):
            year_from = None
        if year_from:
            clauses.append("b.publish_year >= %s")
            params.append(year_from)

    if args.get("yearTo"):
        try:
            year_to = int(args["yearTo"])
        except (TypeError, ValueError):
            year_to = None
        if year_to:
            clauses.append("b.publish_year <= %s")
            params.append(year_to)

    if args.get("stockStatus"):
        clauses.append(
            """
            CASE
              WHEN COALESCE(cs.total_copies, 0) = 0 THEN 'empty'
              WHEN COALESCE(cs.available_copies, 0) > 0 THEN 'available'
              WHEN COALESCE(cs.on_loan_copies, 0) > 0 THEN 'on_loan'
              WHEN COALESCE(cs.damaged_copies, 0) > 0 THEN 'damaged'
              WHEN COALESCE(cs.lost_copies, 0) > 0 THEN 'lost'
              ELSE 'written_off'
            END = %s
            """
        )
        params.append(args["stockStatus"])

    return " WHERE " + " AND ".join(clauses), params


def get_stats():
    return query_one(
        """
        SELECT
          (SELECT COUNT(*)::int FROM books WHERE NOT is_archived) AS total_titles,
          (SELECT COUNT(*)::int FROM book_copies) AS total_copies,
          (SELECT COUNT(*)::int FROM book_copies WHERE status = 'available') AS available_copies,
          (SELECT COUNT(*)::int FROM loans WHERE status IN ('active', 'renewed', 'overdue')) AS active_loans,
          (SELECT COUNT(*)::int FROM loans WHERE status = 'overdue') AS overdue_loans,
          (SELECT COUNT(*)::int FROM book_copies WHERE status = 'written_off') AS written_off_copies,
          (SELECT ROUND(AVG(aging_coefficient)::numeric, 2) FROM book_copies) AS average_aging,
          (SELECT COUNT(*)::int FROM patrons WHERE NOT is_archived) AS patrons_count,
          (SELECT COUNT(*)::int FROM book_requests WHERE status = 'pending') AS pending_requests
        """
    )


def get_meta():
    categories = query_all("SELECT id, name FROM categories ORDER BY name ASC")
    languages = query_all("SELECT DISTINCT language FROM books WHERE NOT is_archived ORDER BY language ASC")
    return {
        "categories": categories,
        "languages": [row["language"] for row in languages],
        "stockStatuses": [
            {"value": "available", "label": "Доступна"},
            {"value": "on_loan", "label": "На руках"},
            {"value": "damaged", "label": "Требует ремонта"},
            {"value": "lost", "label": "Утеряна"},
            {"value": "written_off", "label": "Списана"},
            {"value": "empty", "label": "Нет экземпляров"},
        ],
    }


def get_books(filters):
    where_clause, params = build_book_filters(filters)
    return query_all(
        f"""
        WITH copy_summary AS (
          SELECT
            book_id,
            COUNT(*) FILTER (WHERE status IN ('available', 'on_loan', 'damaged'))::int AS total_copies,
            COUNT(*) FILTER (WHERE status = 'available')::int AS available_copies,
            COUNT(*) FILTER (WHERE status = 'on_loan')::int AS on_loan_copies,
            COUNT(*) FILTER (WHERE status = 'damaged')::int AS damaged_copies,
            COUNT(*) FILTER (WHERE status = 'written_off')::int AS written_off_copies,
            COUNT(*) FILTER (WHERE status = 'lost')::int AS lost_copies,
            ROUND(AVG(aging_coefficient)::numeric, 2) AS average_aging
          FROM book_copies
          GROUP BY book_id
        ),
        request_summary AS (
          SELECT
            book_id,
            COUNT(*) FILTER (WHERE status = 'pending')::int AS request_count
          FROM book_requests
          GROUP BY book_id
        )
        SELECT
          b.id,
          b.title,
          b.author,
          b.isbn,
          b.publish_year,
          b.language,
          b.publisher,
          b.shelf_code,
          b.description,
          b.replacement_cost,
          b.cover_image,
          c.id AS category_id,
          c.name AS category,
          COALESCE(cs.total_copies, 0) AS total_copies,
          COALESCE(cs.available_copies, 0) AS available_copies,
          COALESCE(cs.on_loan_copies, 0) AS on_loan_copies,
          COALESCE(cs.damaged_copies, 0) AS damaged_copies,
          COALESCE(cs.written_off_copies, 0) AS written_off_copies,
          COALESCE(cs.lost_copies, 0) AS lost_copies,
          COALESCE(req.request_count, 0) AS request_count,
          COALESCE(cs.average_aging, 0) AS average_aging,
          ROUND(
            (b.replacement_cost * GREATEST(0.15, 1 - LEAST(COALESCE(cs.average_aging, 0), 1)))::numeric,
            2
          ) AS final_price,
          CASE
            WHEN COALESCE(cs.total_copies, 0) = 0 THEN 'empty'
            WHEN COALESCE(cs.available_copies, 0) > 0 THEN 'available'
            WHEN COALESCE(cs.on_loan_copies, 0) > 0 THEN 'on_loan'
            WHEN COALESCE(cs.damaged_copies, 0) > 0 THEN 'damaged'
            WHEN COALESCE(cs.lost_copies, 0) > 0 THEN 'lost'
            ELSE 'written_off'
          END AS stock_status
        FROM books b
        JOIN categories c ON c.id = b.category_id
        LEFT JOIN copy_summary cs ON cs.book_id = b.id
        LEFT JOIN request_summary req ON req.book_id = b.id
        {where_clause}
        ORDER BY b.title ASC
        """,
        params,
    )


def get_copies(book_id):
    return query_all(
        """
        SELECT
          bc.id,
          bc.book_id,
          bc.inventory_code,
          bc.acquisition_date,
          bc.price,
          bc.condition_rating,
          bc.aging_coefficient,
          bc.status,
          bc.notes,
          bc.written_off_reason,
          b.title,
          p.full_name AS patron_name,
          l.id AS active_loan_id,
          l.due_at
        FROM book_copies bc
        JOIN books b ON b.id = bc.book_id
        LEFT JOIN loans l
          ON l.copy_id = bc.id
          AND l.status IN ('active', 'renewed', 'overdue')
        LEFT JOIN patrons p ON p.id = l.patron_id
        WHERE bc.book_id = %s
        ORDER BY bc.inventory_code ASC
        """,
        [book_id],
    )


def get_patrons():
    return query_all(
        """
        SELECT
          p.id,
          p.full_name,
          p.card_number,
          p.phone,
          p.email,
          p.address,
          p.membership_type,
          p.status,
          p.app_username,
          COUNT(l.id) FILTER (WHERE l.status IN ('active', 'renewed', 'overdue'))::int AS active_loans,
          COUNT(l.id) FILTER (WHERE l.status = 'overdue')::int AS overdue_loans
        FROM patrons p
        LEFT JOIN loans l ON l.patron_id = p.id
        WHERE NOT p.is_archived
        GROUP BY p.id
        ORDER BY p.full_name ASC
        """
    )


def get_reader_profile(patron_id, user_id=None):
    patron = query_one(
        """
        SELECT id, full_name, card_number, phone, email, membership_type, status, created_at
        FROM patrons
        WHERE id = %s AND NOT is_archived
        """,
        [patron_id],
    )
    if not patron:
        return None

    stats = query_one(
        """
        SELECT
          COUNT(*) FILTER (WHERE status = 'returned')::int AS books_read,
          COUNT(*) FILTER (WHERE status IN ('active', 'renewed', 'overdue'))::int AS books_on_hand,
          COUNT(*) FILTER (WHERE status = 'overdue')::int AS overdue_loans,
          COUNT(*)::int AS total_loans
        FROM loans
        WHERE patron_id = %s
        """,
        [patron_id],
    ) or {}

    req_stats = {"total": 0, "pending": 0}
    if user_id:
        req_stats = (
            query_one(
                """
                SELECT
                  COUNT(*)::int AS total,
                  COUNT(*) FILTER (WHERE status = 'pending')::int AS pending
                FROM book_requests
                WHERE user_id = %s
                """,
                [user_id],
            )
            or req_stats
        )

    recent_read = query_all(
        """
        SELECT b.title, b.author, l.returned_at, l.issued_at, l.status
        FROM loans l
        JOIN book_copies bc ON bc.id = l.copy_id
        JOIN books b ON b.id = bc.book_id
        WHERE l.patron_id = %s AND l.status IN ('returned', 'lost')
        ORDER BY COALESCE(l.returned_at, l.issued_at) DESC NULLS LAST
        LIMIT 8
        """,
        [patron_id],
    )

    active_loans = query_all(
        """
        SELECT b.title, b.author, l.due_at, l.issued_at, l.status
        FROM loans l
        JOIN book_copies bc ON bc.id = l.copy_id
        JOIN books b ON b.id = bc.book_id
        WHERE l.patron_id = %s AND l.status IN ('active', 'renewed', 'overdue')
        ORDER BY l.due_at ASC NULLS LAST
        LIMIT 6
        """,
        [patron_id],
    )

    created = patron.get("created_at")
    return {
        "patronId": patron_id,
        "fullName": patron["full_name"],
        "cardNumber": patron["card_number"],
        "phone": patron.get("phone") or "",
        "email": patron.get("email") or "",
        "membershipType": patron.get("membership_type") or "",
        "patronStatus": patron.get("status"),
        "memberSince": created.isoformat() if created else None,
        "booksRead": int(stats.get("books_read") or 0),
        "booksOnHand": int(stats.get("books_on_hand") or 0),
        "overdueLoans": int(stats.get("overdue_loans") or 0),
        "totalLoans": int(stats.get("total_loans") or 0),
        "requestsTotal": int(req_stats.get("total") or 0),
        "requestsPending": int(req_stats.get("pending") or 0),
        "recentRead": [
            {
                "title": row["title"],
                "author": row["author"],
                "returnedAt": row["returned_at"].isoformat() if row.get("returned_at") else None,
                "issuedAt": row["issued_at"].isoformat() if row.get("issued_at") else None,
                "status": row["status"],
            }
            for row in recent_read
        ],
        "activeLoans": [
            {
                "title": row["title"],
                "author": row["author"],
                "dueAt": row["due_at"].isoformat() if row.get("due_at") else None,
                "issuedAt": row["issued_at"].isoformat() if row.get("issued_at") else None,
                "status": row["status"],
            }
            for row in active_loans
        ],
    }


def refresh_overdues():
    execute(
        """
        UPDATE loans
        SET status = 'overdue'
        WHERE status IN ('active', 'renewed')
          AND due_at < CURRENT_DATE
        """
    )


def get_loans(user):
    refresh_overdues()
    sql = """
        SELECT
          l.id,
          l.copy_id,
          l.patron_id,
          l.issued_at,
          l.due_at,
          l.returned_at,
          l.status,
          l.renewal_count,
          l.notes,
          b.title,
          bc.inventory_code,
          p.full_name AS patron_name
        FROM loans l
        JOIN book_copies bc ON bc.id = l.copy_id
        JOIN books b ON b.id = bc.book_id
        JOIN patrons p ON p.id = l.patron_id
    """
    params = []
    if user["role"] == "reader" and user["patron_id"]:
        sql += " WHERE l.patron_id = %s "
        params.append(user["patron_id"])
    sql += """
        ORDER BY
          CASE WHEN l.status IN ('active', 'renewed', 'overdue') THEN 0 ELSE 1 END,
          l.issued_at DESC
        LIMIT 50
    """
    return query_all(sql, params)


def get_transactions(user):
    sql = """
        SELECT
          t.id,
          t.operation_type,
          t.operation_date,
          t.quantity,
          t.details,
          t.actor_name,
          b.title,
          bc.inventory_code,
          p.full_name AS patron_name
        FROM book_transactions t
        LEFT JOIN books b ON b.id = t.book_id
        LEFT JOIN book_copies bc ON bc.id = t.copy_id
        LEFT JOIN patrons p ON p.id = t.patron_id
    """
    params = []
    if user["role"] == "reader" and user["patron_id"]:
        sql += " WHERE t.patron_id = %s "
        params.append(user["patron_id"])
    sql += " ORDER BY t.operation_date DESC LIMIT 30 "
    return query_all(sql, params)


def get_available_copies():
    return query_all(
        """
        SELECT
          bc.id,
          bc.inventory_code,
          b.title,
          b.author
        FROM book_copies bc
        JOIN books b ON b.id = bc.book_id
        WHERE bc.status = 'available' AND NOT b.is_archived
        ORDER BY b.title ASC, bc.inventory_code ASC
        """
    )


def get_book_requests(user):
    sql = """
        SELECT
          br.id,
          br.user_id,
          br.book_id,
          br.status,
          br.request_date,
          br.processed_at,
          br.processed_by,
          br.notes,
          b.title,
          b.author,
          b.cover_image,
          au.full_name AS reader_name,
          au.email AS reader_email,
          p.card_number
        FROM book_requests br
        JOIN books b ON b.id = br.book_id
        JOIN app_users au ON au.id = br.user_id
        LEFT JOIN patrons p ON p.id = au.patron_id
    """
    params = []
    if normalize_role(user["role"]) == "reader":
        sql += " WHERE br.user_id = %s "
        params.append(user["id"])
    sql += """
        ORDER BY
          CASE br.status WHEN 'pending' THEN 0 WHEN 'approved' THEN 1 ELSE 2 END,
          br.request_date DESC
        LIMIT 100
    """
    return query_all(sql, params)


def get_users():
    return query_all(
        """
        SELECT
          au.id,
          au.username,
          au.email,
          au.full_name,
          au.role,
          au.is_active,
          au.created_at,
          au.patron_id,
          p.card_number
        FROM app_users au
        LEFT JOIN patrons p ON p.id = au.patron_id
        ORDER BY au.is_active ASC, au.created_at DESC
        """
    )


def get_reports():
    return {
        "popularBooks": query_all(
            """
            SELECT b.title, b.author, COUNT(l.id)::int AS loans_count
            FROM loans l
            JOIN book_copies bc ON bc.id = l.copy_id
            JOIN books b ON b.id = bc.book_id
            GROUP BY b.id
            ORDER BY loans_count DESC, b.title ASC
            LIMIT 10
            """
        ),
        "debtors": query_all(
            """
            SELECT p.full_name, p.email, p.card_number, COUNT(l.id)::int AS overdue_count
            FROM loans l
            JOIN patrons p ON p.id = l.patron_id
            WHERE l.status = 'overdue'
            GROUP BY p.id
            ORDER BY overdue_count DESC, p.full_name ASC
            LIMIT 20
            """
        ),
        "totals": get_stats(),
    }


def get_settings():
    rows = query_all("SELECT key, value FROM system_settings ORDER BY key ASC")
    return {row["key"]: row["value"] for row in rows}


def get_contact_info():
    settings = get_settings()
    return {
        "email": clean_text(settings.get("library_contact_email")),
        "phone": clean_text(settings.get("library_contact_phone")),
        "workHours": clean_text(settings.get("library_work_hours")),
        "vkUrl": clean_text(settings.get("library_vk_url")),
        "maxUrl": clean_text(settings.get("library_max_url")),
        "siteName": clean_text(settings.get("library_site_name")) or "Библиотека",
    }


def get_bootstrap(filters, user):
    role = normalize_role(user["role"])
    books = get_books(filters)
    if role not in {"librarian", "manager", "admin"}:
        books = [sanitize_book(book, role) for book in books]

    data = {
        "stats": get_stats() if role in {"librarian", "manager", "admin"} else {},
        "meta": get_meta(),
        "books": books,
        "user": bootstrap_user_payload(user),
        "patrons": [],
        "loans": [],
        "transactions": [],
        "availableCopies": [],
        "requests": [],
        "users": [],
        "reports": {},
        "settings": {},
        "contact": get_contact_info(),
    }

    if role == "reader":
        data["loans"] = get_loans(user)
        data["requests"] = get_book_requests(user)
        if user.get("patron_id"):
            data["profile"] = get_reader_profile(user["patron_id"], user.get("id"))

    if role in {"librarian", "manager", "admin"}:
        data["patrons"] = get_patrons()
        data["loans"] = get_loans(user)
        data["availableCopies"] = get_available_copies()
        data["requests"] = get_book_requests(user)
        data["reports"] = get_reports()
        data["transactions"] = get_transactions(user)

    if role == "admin":
        data["users"] = get_users()
        data["settings"] = get_settings()

    if role != "guest":
        data["supportUnread"] = get_support_unread_count(user)

    return data


def insert_transaction(cursor, payload):
    cursor.execute(
        """
        INSERT INTO book_transactions (
          book_id,
          copy_id,
          patron_id,
          loan_id,
          operation_type,
          quantity,
          details,
          actor_name
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        [
            payload.get("book_id"),
            payload.get("copy_id"),
            payload.get("patron_id"),
            payload.get("loan_id"),
            payload["operation_type"],
            payload.get("quantity", 1),
            payload.get("details", ""),
            payload.get("actor_name", "Система"),
        ],
    )


def create_copy(cursor, book, payload, manual_counter=None):
    import time

    if not book:
        raise ValueError("Неверные данные книги.")

    book_id = book.get("book_id") or book.get("id")
    if not book_id:
        raise ValueError("Неверные данные книги: отсутствует идентификатор книги.")

    # Проверка существования книги
    cursor.execute(
        "SELECT id, publish_year, replacement_cost FROM books WHERE id = %s",
        [book_id],
    )
    book_row = cursor.fetchone()
    if not book_row:
        raise ValueError(f"Книга с id {book_id} не найдена. Невозможно создать экземпляр.")
    book_row = dict(book_row)
    publish_year = book.get("publish_year", book_row["publish_year"])
    replacement_cost = book.get("replacement_cost", book_row["replacement_cost"])

    # Получаем следующий номер для этой книги
    if manual_counter is None:
        cursor.execute(
            "SELECT last_copy_number FROM books WHERE id = %s FOR UPDATE",
            [book_id],
        )
        row = cursor.fetchone()
        last_num = row["last_copy_number"] if row else 0
        next_num = last_num + 1
        cursor.execute(
            "UPDATE books SET last_copy_number = %s WHERE id = %s",
            [next_num, book_id],
        )
    else:
        next_num = manual_counter

    # Формируем инвентарный номер: INV-{book_id}-{номер от 1 до ...}
    inventory_code = f"INV-{book_id}-{next_num:06d}"

    acquisition_date = payload.get("acquisitionDate") or time.strftime("%Y-%m-%d")
    try:
        condition_rating = int(payload.get("conditionRating") or 5)
    except (TypeError, ValueError):
        condition_rating = 5
    try:
        price = float(payload.get("price") or replacement_cost or 0)
    except (TypeError, ValueError):
        price = float(replacement_cost or 0)

    aging = compute_aging(publish_year, acquisition_date, condition_rating)

    cursor.execute(
        """
        INSERT INTO book_copies (
            book_id, inventory_code, acquisition_date, price,
            condition_rating, aging_coefficient, status, notes, last_inventory_date
        )
        VALUES (%s, %s, %s, %s, %s, %s, 'available', %s, CURRENT_DATE)
        RETURNING id, inventory_code
        """,
        [book_id, inventory_code, acquisition_date, price, condition_rating, aging, payload.get("notes", "")]
    )
    return dict(cursor.fetchone())

@app.before_request
def prepare_app():
    if app.config.get("SCHEMA_READY"):
        return
    try:
        ensure_schema()
        app.config["SCHEMA_READY"] = True
    except Exception:
        pass


@app.get("/")
def index():
    return send_from_directory(PUBLIC_DIR, "index.html")


@app.get("/api/health")
def health():
    return jsonify({"ok": True})


@app.post("/api/auth/login")
def login():
    payload = request.get_json(force=True)
    username = clean_text(payload.get("username") or payload.get("email")).lower()
    password = payload.get("password", "")
    if not username or not password:
        return jsonify({"message": "Введите email и пароль."}), 400

    user = query_one(
        """
        SELECT id, username, email, full_name, role, password_hash, patron_id, is_active
        FROM app_users
        WHERE LOWER(username) = %s OR LOWER(email) = %s
        """,
        [username, username],
    )

    if user and not user["is_active"]:
        return jsonify({"message": "Аккаунт еще не подтвержден администратором. Дождитесь активации заявки."}), 403

    if not user:
        return jsonify({"message": "Пользователь с таким email не найден."}), 401

    if not verify_password(password, user["password_hash"]):
        return jsonify({"message": "Неверный пароль."}), 401

    token = create_token(user)
    return jsonify(
        {
            "token": token,
            "user": {
                "id": user["id"],
                "username": user["username"],
                "email": user.get("email", user["username"]),
                "role": normalize_role(user["role"]),
                "fullName": user["full_name"],
                "patronId": user["patron_id"],
            },
        }
    )


@app.post("/api/auth/register")
def register():
    payload = request.get_json(force=True)
    error = require_fields(payload, ["fullName", "email", "password"])
    if error:
        return jsonify({"message": error}), 400

    full_name = clean_text(payload.get("fullName"))
    email = clean_text(payload.get("email")).lower()
    password = payload.get("password", "")
    if not validate_email(email):
        return jsonify({"message": "Введите корректный email."}), 400
    if len(password) < 6:
        return jsonify({"message": "Пароль должен быть не короче 6 символов."}), 400

    existing = query_one("SELECT id FROM app_users WHERE LOWER(email) = %s OR LOWER(username) = %s", [email, email])
    if existing:
        return jsonify({"message": "Пользователь с таким email уже существует."}), 409

    with get_connection() as connection:
        with connection.cursor() as cursor:
            card_number = f"P-{int(time.time())}-{uuid.uuid4().hex[:4]}"
            cursor.execute(
                """
                INSERT INTO patrons (full_name, card_number, email, status, app_username)
                VALUES (%s, %s, %s, 'blocked', %s)
                RETURNING id
                """,
                [full_name, card_number, email, email],
            )
            patron = dict(cursor.fetchone())
            cursor.execute(
                """
                INSERT INTO app_users (username, email, full_name, role, password_hash, patron_id, is_active)
                VALUES (%s, %s, %s, 'reader', %s, %s, FALSE)
                RETURNING id
                """,
                [email, email, full_name, make_password_hash(password), patron["id"]],
            )
            user = dict(cursor.fetchone())
            insert_transaction(
                cursor,
                {
                    "patron_id": patron["id"],
                    "operation_type": "registration_request",
                    "details": f"Новая заявка на регистрацию: {full_name}",
                    "actor_name": full_name,
                },
            )
        connection.commit()

    return jsonify({"id": user["id"], "message": "Заявка на регистрацию отправлена администратору."}), 201


@app.get("/api/auth/me")
def me():
    return jsonify({"user": bootstrap_user_payload(get_current_user())})


@app.put("/api/auth/password")
def change_password():
    user = get_current_user()
    if user["role"] == "guest":
        return jsonify({"message": "Войдите в аккаунт."}), 401
    if normalize_role(user["role"]) != "reader":
        return jsonify({"message": "Смена пароля в профиле доступна только читателям. Сотрудникам пароль задаёт администратор во вкладке «Пользователи»."}), 403

    payload = request.get_json(force=True, silent=True) or {}
    current_password = payload.get("currentPassword") or ""
    new_password = payload.get("newPassword") or ""
    if len(new_password) < 6:
        return jsonify({"message": "Новый пароль должен быть не короче 6 символов."}), 400

    row = query_one(
        "SELECT id, password_hash FROM app_users WHERE id = %s",
        [user["id"]],
    )
    if not row or not verify_password(current_password, row["password_hash"]):
        return jsonify({"message": "Текущий пароль указан неверно."}), 400

    execute(
        "UPDATE app_users SET password_hash = %s WHERE id = %s",
        [make_password_hash(new_password), user["id"]],
    )
    return jsonify({"message": "Пароль обновлён."})


def hash_reset_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@app.get("/api/public/contact")
def public_contact():
    return jsonify(get_contact_info())


@app.get("/api/public/home-banners")
def public_home_banners():
    return jsonify(list_home_banner_files())


@app.get("/api/admin/catalog/template")
@require_role("admin")
def admin_catalog_template():
    sample = [
        {
            "title": "Пример книги",
            "author": "Иван Иванов",
            "isbn": "978-5-000000-00-0",
            "category": "Художественная литература",
            "language": "Русский",
            "publish_year": 2020,
            "publisher": "Пример",
            "shelf_code": "A-1",
            "description": "Краткое описание",
            "replacement_cost": 500,
            "cover_image": "/uploads/covers/example.jpg",
            "initial_copies": 2,
        }
    ]
    return catalog_csv_response("catalog_import_template.csv", sample)


@app.get("/api/admin/catalog/export")
@require_role("admin")
def admin_catalog_export():
    return catalog_csv_response("library-catalog.csv", build_catalog_csv_rows())


@app.post("/api/admin/catalog/import")
@require_role("admin")
def admin_catalog_import():
    uploaded = request.files.get("file")
    if not uploaded or not uploaded.filename:
        return jsonify({"message": "Выберите CSV-файл."}), 400
    try:
        raw = uploaded.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        return jsonify({"message": "Файл должен быть в кодировке UTF-8."}), 400
    try:
        rows = parse_catalog_csv_text(raw)
    except ValueError as error:
        return jsonify({"message": str(error)}), 400
    user = get_current_user()
    result = import_catalog_rows(rows, user["full_name"])
    if result["created"] == 0 and result["updated"] == 0 and result["errors"]:
        return jsonify({"message": result["errors"][0], "errors": result["errors"]}), 400
    return jsonify(result)


@app.post("/api/auth/forgot-password")
def forgot_password():
    payload = request.get_json(force=True, silent=True) or {}
    email = clean_text(payload.get("email")).lower()
    if not validate_email(email):
        return jsonify({"message": "Введите корректный email."}), 400

    response = {
        "message": "Если этот email зарегистрирован как читатель, дальнейшие инструкции будут доступны.",
    }
    user = query_one(
        """
        SELECT id, role, is_active
        FROM app_users
        WHERE LOWER(email) = %s OR LOWER(username) = %s
        """,
        [email, email],
    )
    if user and normalize_role(user["role"]) == "reader" and user["is_active"]:
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=2)
        execute(
            """
            INSERT INTO password_reset_tokens (user_id, token_hash, expires_at)
            VALUES (%s, %s, %s)
            """,
            [user["id"], hash_reset_token(token), expires_at],
        )
        settings = get_settings()
        if settings.get("library_demo_reset_links", "true").lower() in {"1", "true", "yes"}:
            base = request.url_root.rstrip("/")
            response["resetUrl"] = f"{base}/?reset={token}"
            response["demoNote"] = (
                "Учебный режим: ссылка показана на экране. В реальной библиотеке она приходит на email."
            )
        insert_support_from_public(
            sender_name="Восстановление пароля",
            sender_email=email,
            subject="Запрос ссылки для сброса пароля",
            body=f"Читатель запросил восстановление пароля для {email}.",
        )

    return jsonify(response)


@app.post("/api/auth/reset-password")
def reset_password_with_token():
    payload = request.get_json(force=True, silent=True) or {}
    token = clean_text(payload.get("token"))
    new_password = payload.get("newPassword") or ""
    if not token:
        return jsonify({"message": "Отсутствует код восстановления."}), 400
    if len(new_password) < 6:
        return jsonify({"message": "Пароль должен быть не короче 6 символов."}), 400

    row = query_one(
        """
        SELECT prt.id, prt.user_id, prt.used_at, prt.expires_at, au.role
        FROM password_reset_tokens prt
        JOIN app_users au ON au.id = prt.user_id
        WHERE prt.token_hash = %s
        ORDER BY prt.id DESC
        LIMIT 1
        """,
        [hash_reset_token(token)],
    )
    if not row:
        return jsonify({"message": "Ссылка недействительна или устарела."}), 400
    if row["used_at"]:
        return jsonify({"message": "Ссылка уже использована. Запросите новую."}), 400
    expires = row["expires_at"]
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > expires:
        return jsonify({"message": "Срок действия ссылки истёк. Запросите восстановление снова."}), 400
    if normalize_role(row["role"]) != "reader":
        return jsonify({"message": "Сброс пароля доступен только для читателей."}), 400

    execute(
        "UPDATE app_users SET password_hash = %s WHERE id = %s",
        [make_password_hash(new_password), row["user_id"]],
    )
    execute(
        "UPDATE password_reset_tokens SET used_at = CURRENT_TIMESTAMP WHERE id = %s",
        [row["id"]],
    )
    return jsonify({"message": "Пароль обновлён. Теперь можно войти."})


def is_staff_role(role):
    return normalize_role(role) in {"librarian", "manager", "admin"}


def migrate_support_threads_to_chat():
    threads = query_all(
        """
        SELECT id, user_id, body, admin_reply
        FROM support_messages
        ORDER BY id ASC
        """
    )
    for thread in threads:
        has_chat = query_one(
            "SELECT 1 AS ok FROM support_chat_messages WHERE thread_id = %s LIMIT 1",
            [thread["id"]],
        )
        if not has_chat and thread.get("body"):
            execute(
                """
                INSERT INTO support_chat_messages (thread_id, sender_user_id, is_from_staff, body)
                VALUES (%s, %s, FALSE, %s)
                """,
                [thread["id"], thread.get("user_id"), thread["body"]],
            )
        if thread.get("admin_reply"):
            has_staff = query_one(
                """
                SELECT 1 AS ok
                FROM support_chat_messages
                WHERE thread_id = %s AND is_from_staff = TRUE
                LIMIT 1
                """,
                [thread["id"]],
            )
            if not has_staff:
                execute(
                    """
                    INSERT INTO support_chat_messages (thread_id, sender_user_id, is_from_staff, body)
                    VALUES (%s, NULL, TRUE, %s)
                    """,
                    [thread["id"], thread["admin_reply"]],
                )


def get_support_unread_count(user):
    role = normalize_role(user["role"])
    if role == "guest":
        return 0
    if role == "admin":
        row = query_one(
            "SELECT COUNT(*)::int AS count FROM support_messages WHERE unread_for_admin = TRUE"
        )
        return int(row["count"] if row else 0)
    row = query_one(
        """
        SELECT COUNT(*)::int AS count
        FROM support_messages
        WHERE user_id = %s AND unread_for_user = TRUE
        """,
        [user["id"]],
    )
    return int(row["count"] if row else 0)


def can_access_support_thread(user, thread):
    role = normalize_role(user["role"])
    if role == "admin":
        return True
    if thread.get("user_id") and thread["user_id"] == user["id"]:
        return True
    return False


def serialize_chat_message(row):
    role = normalize_role(row.get("role") or "reader")
    sender_label = row.get("full_name") or "Пользователь"
    if row.get("is_from_staff"):
        sender_label = "Администратор"
    elif role in {"librarian", "manager"}:
        sender_label = row.get("full_name") or role_labels_display(role)
    return {
        "id": row["id"],
        "body": row["body"],
        "createdAt": row["created_at"].isoformat() if row.get("created_at") else None,
        "isFromStaff": bool(row.get("is_from_staff")),
        "senderName": sender_label,
        "senderRole": role,
    }


def role_labels_display(role):
    return {
        "reader": "Читатель",
        "librarian": "Библиотекарь",
        "manager": "Менеджер",
        "admin": "Администратор",
    }.get(role, role)


def get_support_threads_for_user(user):
    role = normalize_role(user["role"])
    if role == "admin":
        return query_all(
            """
            SELECT
              id,
              user_id,
              sender_name,
              sender_email,
              subject,
              status,
              unread_for_admin,
              unread_for_user,
              created_at
            FROM support_messages
            ORDER BY
              unread_for_admin DESC,
              created_at DESC
            LIMIT 200
            """
        )
    return query_all(
        """
        SELECT
          id,
          user_id,
          sender_name,
          sender_email,
          subject,
          status,
          unread_for_admin,
          unread_for_user,
          created_at
        FROM support_messages
        WHERE user_id = %s
        ORDER BY created_at DESC
        LIMIT 50
        """,
        [user["id"]],
    )


def get_support_thread_messages(thread_id):
    return query_all(
        """
        SELECT
          m.id,
          m.body,
          m.created_at,
          m.is_from_staff,
          m.sender_user_id,
          u.full_name,
          u.role
        FROM support_chat_messages m
        LEFT JOIN app_users u ON u.id = m.sender_user_id
        WHERE m.thread_id = %s
        ORDER BY m.created_at ASC, m.id ASC
        """,
        [thread_id],
    )


def insert_support_from_public(sender_name, sender_email, subject, body):
    return query_one(
        """
        INSERT INTO support_messages (user_id, sender_name, sender_email, subject, body)
        VALUES (NULL, %s, %s, %s, %s)
        RETURNING id
        """,
        [sender_name, sender_email, subject, body],
    )


@app.post("/api/support/public-message")
def create_public_support_message():
    payload = request.get_json(force=True, silent=True) or {}
    sender_name = clean_text(payload.get("fullName") or payload.get("senderName")) or "Посетитель"
    sender_email = clean_text(payload.get("email") or payload.get("senderEmail")).lower()
    subject = clean_text(payload.get("subject")) or "Обращение с сайта"
    body = clean_text(payload.get("body"))
    if not validate_email(sender_email):
        return jsonify({"message": "Укажите корректный email."}), 400
    if not body:
        return jsonify({"message": "Введите текст сообщения."}), 400
    if len(subject) > 200:
        return jsonify({"message": "Тема не длиннее 200 символов."}), 400

    message = insert_support_from_public(sender_name, sender_email, subject, body)
    thread_id = message["id"]
    execute(
        """
        INSERT INTO support_chat_messages (thread_id, sender_user_id, is_from_staff, body)
        VALUES (%s, NULL, FALSE, %s)
        """,
        [thread_id, body],
    )
    return jsonify(
        {
            "id": thread_id,
            "message": "Сообщение отправлено. Ответ появится в чате с администратором.",
        }
    ), 201


def create_support_thread_for_user(user, subject, body):
    sender_email = clean_text(user.get("email") or user.get("username"))
    thread = query_one(
        """
        INSERT INTO support_messages (
          user_id, sender_name, sender_email, subject, body,
          unread_for_admin, unread_for_user
        )
        VALUES (%s, %s, %s, %s, %s, TRUE, FALSE)
        RETURNING id, created_at
        """,
        [user["id"], user["full_name"], sender_email, subject, body],
    )
    execute(
        """
        INSERT INTO support_chat_messages (thread_id, sender_user_id, is_from_staff, body)
        VALUES (%s, %s, FALSE, %s)
        """,
        [thread["id"], user["id"], body],
    )
    return thread


@app.post("/api/support/messages")
def create_support_message():
    user = get_current_user()
    if user["role"] == "guest":
        return jsonify({"message": "Войдите в аккаунт, чтобы отправить сообщение."}), 401

    payload = request.get_json(force=True, silent=True) or {}
    subject = clean_text(payload.get("subject")) or "Обращение"
    body = clean_text(payload.get("body"))
    if not body:
        return jsonify({"message": "Введите текст сообщения."}), 400
    if len(subject) > 200:
        return jsonify({"message": "Тема не длиннее 200 символов."}), 400

    thread = create_support_thread_for_user(user, subject, body)
    return jsonify(
        {
            "id": thread["id"],
            "message": "Сообщение отправлено. Ответ — в разделе «Сообщения».",
        }
    ), 201


@app.get("/api/support/unread-count")
def support_unread_count():
    user = get_current_user()
    return jsonify({"count": get_support_unread_count(user)})


@app.get("/api/support/threads")
def support_threads_list():
    user = get_current_user()
    if user["role"] == "guest":
        return jsonify({"message": "Войдите в аккаунт."}), 401
    rows = get_support_threads_for_user(user)
    payload = []
    for row in rows:
        last = query_one(
            """
            SELECT body, created_at, is_from_staff
            FROM support_chat_messages
            WHERE thread_id = %s
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            [row["id"]],
        )
        unread = bool(row["unread_for_admin"]) if normalize_role(user["role"]) == "admin" else bool(row["unread_for_user"])
        payload.append(
            {
                "id": row["id"],
                "subject": row["subject"],
                "senderName": row["sender_name"],
                "senderEmail": row["sender_email"],
                "status": row["status"],
                "unread": unread,
                "createdAt": row["created_at"].isoformat() if row.get("created_at") else None,
                "preview": (last["body"][:120] if last and last.get("body") else ""),
            }
        )
    return jsonify(payload)


@app.get("/api/support/threads/<int:thread_id>")
def support_thread_detail(thread_id):
    user = get_current_user()
    if user["role"] == "guest":
        return jsonify({"message": "Войдите в аккаунт."}), 401
    thread = query_one(
        """
        SELECT id, user_id, sender_name, sender_email, subject, status, created_at
        FROM support_messages
        WHERE id = %s
        """,
        [thread_id],
    )
    if not thread or not can_access_support_thread(user, thread):
        return jsonify({"message": "Диалог не найден."}), 404

    role = normalize_role(user["role"])
    if role == "admin":
        execute(
            "UPDATE support_messages SET unread_for_admin = FALSE WHERE id = %s",
            [thread_id],
        )
    elif thread.get("user_id") == user["id"]:
        execute(
            "UPDATE support_messages SET unread_for_user = FALSE WHERE id = %s",
            [thread_id],
        )

    messages = get_support_thread_messages(thread_id)
    return jsonify(
        {
            "thread": {
                "id": thread["id"],
                "subject": thread["subject"],
                "senderName": thread["sender_name"],
                "status": thread["status"],
                "createdAt": thread["created_at"].isoformat() if thread.get("created_at") else None,
            },
            "messages": [serialize_chat_message(row) for row in messages],
        }
    )


@app.post("/api/support/threads")
def support_thread_create():
    user = get_current_user()
    if user["role"] == "guest":
        return jsonify({"message": "Войдите в аккаунт."}), 401
    payload = request.get_json(force=True, silent=True) or {}
    subject = clean_text(payload.get("subject")) or "Чат с администратором"
    body = clean_text(payload.get("body"))
    if not body:
        return jsonify({"message": "Введите сообщение."}), 400
    if len(subject) > 200:
        return jsonify({"message": "Тема не длиннее 200 символов."}), 400

    role = normalize_role(user["role"])
    if role != "admin":
        existing = query_one(
            """
            SELECT id FROM support_messages
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            [user["id"]],
        )
        if existing:
            thread_id = existing["id"]
            execute(
                """
                INSERT INTO support_chat_messages (thread_id, sender_user_id, is_from_staff, body)
                VALUES (%s, %s, FALSE, %s)
                """,
                [thread_id, user["id"], body],
            )
            execute(
                """
                UPDATE support_messages
                SET status = 'open', unread_for_admin = TRUE, unread_for_user = FALSE
                WHERE id = %s
                """,
                [thread_id],
            )
            return jsonify({"id": thread_id, "existing": True}), 200

    thread = create_support_thread_for_user(user, subject, body)
    return jsonify({"id": thread["id"]}), 201


@app.post("/api/support/threads/<int:thread_id>/messages")
def support_thread_post_message(thread_id):
    user = get_current_user()
    if user["role"] == "guest":
        return jsonify({"message": "Войдите в аккаунт."}), 401
    thread = query_one("SELECT id, user_id FROM support_messages WHERE id = %s", [thread_id])
    if not thread or not can_access_support_thread(user, thread):
        return jsonify({"message": "Диалог не найден."}), 404

    payload = request.get_json(force=True, silent=True) or {}
    body = clean_text(payload.get("body"))
    if not body:
        return jsonify({"message": "Введите текст сообщения."}), 400

    role = normalize_role(user["role"])
    from_staff = role == "admin"
    execute(
        """
        INSERT INTO support_chat_messages (thread_id, sender_user_id, is_from_staff, body)
        VALUES (%s, %s, %s, %s)
        """,
        [thread_id, user["id"], from_staff, body],
    )
    if from_staff:
        execute(
            """
            UPDATE support_messages
            SET status = 'answered', admin_reply = %s,
                unread_for_user = TRUE, unread_for_admin = FALSE
            WHERE id = %s
            """,
            [body, thread_id],
        )
    else:
        execute(
            """
            UPDATE support_messages
            SET status = 'open', body = %s,
                unread_for_admin = TRUE, unread_for_user = FALSE
            WHERE id = %s
            """,
            [body, thread_id],
        )
    return jsonify({"ok": True}), 201


@app.get("/api/admin/support-messages")
@require_role("admin")
def admin_support_messages():
    return support_threads_list()


@app.patch("/api/admin/support-messages/<int:message_id>")
@require_role("admin")
def admin_support_message_update(message_id):
    payload = request.get_json(force=True, silent=True) or {}
    status = clean_text(payload.get("status") or "open")
    if status not in {"open", "answered", "closed"}:
        return jsonify({"message": "Недопустимый статус."}), 400
    admin_reply = clean_text(payload.get("adminReply"))
    row = query_one("SELECT id FROM support_messages WHERE id = %s", [message_id])
    if not row:
        return jsonify({"message": "Диалог не найден."}), 404
    if admin_reply:
        user = get_current_user()
        execute(
            """
            INSERT INTO support_chat_messages (thread_id, sender_user_id, is_from_staff, body)
            VALUES (%s, %s, TRUE, %s)
            """,
            [message_id, user["id"], admin_reply],
        )
        execute(
            """
            UPDATE support_messages
            SET status = %s, admin_reply = %s, unread_for_user = TRUE, unread_for_admin = FALSE
            WHERE id = %s
            """,
            [status, admin_reply, message_id],
        )
    else:
        execute("UPDATE support_messages SET status = %s WHERE id = %s", [status, message_id])
    return jsonify({"ok": True})


@app.get("/api/library/bootstrap")
def bootstrap():
    return jsonify(get_bootstrap(request.args, get_current_user()))


@app.get("/api/library/books")
def books():
    user = get_current_user()
    role = normalize_role(user["role"])
    items = get_books(request.args)
    if role not in {"librarian", "manager", "admin"}:
        items = [sanitize_book(book, role) for book in items]
    return jsonify(items)


@app.get("/api/library/books/<int:book_id>/copies")
@require_role("librarian")
def book_copies(book_id):
    return jsonify(get_copies(book_id))


@app.get("/api/library/requests")
@require_role("manager")
def book_requests():
    user = get_current_user()
    return jsonify(get_book_requests(user))


@app.post("/api/library/requests")
@require_role("reader")
def create_book_request():
    user = get_current_user()
    payload = request.get_json(force=True)
    try:
        book_id = int(payload.get("bookId") or 0)
    except (TypeError, ValueError):
        book_id = 0
    book = query_one(
        """
        SELECT b.id, COUNT(bc.id) FILTER (WHERE bc.status = 'available')::int AS available_copies
        FROM books b
        LEFT JOIN book_copies bc ON bc.book_id = b.id
        WHERE b.id = %s AND NOT b.is_archived
        GROUP BY b.id
        """,
        [book_id],
    )
    if not book:
        return jsonify({"message": "Книга не найдена."}), 404
    if book["available_copies"] <= 0:
        return jsonify({"message": "Нет доступных экземпляров для бронирования."}), 400

    notes = clean_text(payload.get("notes"))
    existing_request = query_one(
        """
        SELECT id
        FROM book_requests
        WHERE user_id = %s AND book_id = %s AND status = 'pending'
        ORDER BY id DESC
        LIMIT 1
        """,
        [user["id"], book_id],
    )
    if existing_request:
        execute(
            """
            UPDATE book_requests
            SET request_date = CURRENT_TIMESTAMP, notes = %s
            WHERE id = %s
            """,
            [notes, existing_request["id"]],
        )
        request_row = {"id": existing_request["id"]}
    else:
        request_row = query_one(
            """
            INSERT INTO book_requests (user_id, book_id, status, notes)
            VALUES (%s, %s, 'pending', %s)
            RETURNING id
            """,
            [user["id"], book_id, notes],
        )
    return jsonify({"id": request_row["id"], "message": "Запрос на выдачу отправлен библиотекарю."}), 201


@app.post("/api/library/requests/<int:request_id>/reject")
@require_role("manager")
def reject_book_request(request_id):
    user = get_current_user()
    payload = request.get_json(silent=True) or {}
    execute(
        """
        UPDATE book_requests
        SET status = 'rejected', processed_at = CURRENT_TIMESTAMP, processed_by = %s, notes = %s
        WHERE id = %s AND status = 'pending'
        """,
        [user["full_name"], clean_text(payload.get("notes")) or "Отказано библиотекарем", request_id],
    )
    return ("", 204)


@app.post("/api/library/requests/<int:request_id>/approve")
@require_role("manager")
def approve_book_request(request_id):
    user = get_current_user()
    payload = request.get_json(silent=True) or {}
    due_at = clean_text(payload.get("dueAt")) or time.strftime("%Y-%m-%d", time.localtime(time.time() + 14 * 86400))
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT br.id, br.book_id, br.user_id, au.patron_id
                FROM book_requests br
                JOIN app_users au ON au.id = br.user_id
                WHERE br.id = %s AND br.status = 'pending'
                FOR UPDATE
                """,
                [request_id],
            )
            row = cursor.fetchone()
            if not row:
                return jsonify({"message": "Активный запрос не найден."}), 404
            request_row = dict(row)
            if not request_row["patron_id"]:
                return jsonify({"message": "У читателя нет читательского билета."}), 400

            cursor.execute(
                """
                SELECT id, book_id, inventory_code
                FROM book_copies
                WHERE book_id = %s AND status = 'available'
                ORDER BY acquisition_date ASC, id ASC
                LIMIT 1
                FOR UPDATE
                """,
                [request_row["book_id"]],
            )
            copy_row = cursor.fetchone()
            if not copy_row:
                return jsonify({"message": "Нет свободных экземпляров."}), 400
            copy = dict(copy_row)

            cursor.execute(
                """
                INSERT INTO loans (copy_id, patron_id, due_at, status, issued_by, notes)
                VALUES (%s, %s, %s, 'active', %s, %s)
                RETURNING id
                """,
                [copy["id"], request_row["patron_id"], due_at, user["full_name"], clean_text(payload.get("notes"))],
            )
            loan = dict(cursor.fetchone())
            cursor.execute("UPDATE book_copies SET status = 'on_loan' WHERE id = %s", [copy["id"]])
            cursor.execute(
                """
                UPDATE book_requests
                SET status = 'approved', processed_at = CURRENT_TIMESTAMP, processed_by = %s
                WHERE id = %s
                """,
                [user["full_name"], request_id],
            )
            insert_transaction(
                cursor,
                {
                    "book_id": copy["book_id"],
                    "copy_id": copy["id"],
                    "patron_id": request_row["patron_id"],
                    "loan_id": loan["id"],
                    "operation_type": "issue",
                    "details": f"Выдано по запросу #{request_id}: {copy['inventory_code']}",
                    "actor_name": user["full_name"],
                },
            )
        connection.commit()
    return ("", 204)


@app.post("/api/library/books")
@require_role("librarian")
def create_book():
    payload = request.get_json(force=True)
    user = get_current_user()
    error = require_fields(payload, ["categoryId", "title", "author", "isbn", "publishYear", "language"])
    if error:
        return jsonify({"message": error}), 400
    if int(payload["publishYear"]) < 1500 or int(payload["publishYear"]) > 2100:
        return jsonify({"message": "Год издания должен быть от 1500 до 2100."}), 400
    if float(payload.get("replacementCost") or 0) < 0 or int(payload.get("initialCopies") or 0) < 0:
        return jsonify({"message": "Цена и количество не могут быть отрицательными."}), 400

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO books (
                  category_id, title, author, isbn, publish_year, language,
                  publisher, shelf_code, description, replacement_cost, cover_image
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, publish_year, replacement_cost
                """,
                [
                    int(payload["categoryId"]),
                    payload["title"],
                    payload["author"],
                    payload["isbn"],
                    int(payload["publishYear"]),
                    payload["language"],
                    payload.get("publisher", ""),
                    payload.get("shelfCode", ""),
                    payload.get("description", ""),
                    float(payload.get("replacementCost") or 0),
                    payload.get("coverImage", ""),
                ],
            )
            book = dict(cursor.fetchone())
            count = int(payload.get("initialCopies") or 0)
            for _ in range(count):
                copy = create_copy(cursor, book, payload)
                insert_transaction(
                    cursor,
                    {
                        "book_id": book["id"],
                        "copy_id": copy["id"],
                        "operation_type": "acquisition",
                        "details": "Поступление нового экземпляра",
                        "actor_name": user["full_name"],
                    },
                )
        connection.commit()

    return jsonify({"id": book["id"]}), 201


@app.put("/api/library/books/<int:book_id>")
@require_role("librarian")
def update_book(book_id):
    payload = request.get_json(force=True)
    error = require_fields(payload, ["categoryId", "title", "author", "isbn", "publishYear", "language"])
    if error:
        return jsonify({"message": error}), 400
    if int(payload["publishYear"]) < 1500 or int(payload["publishYear"]) > 2100:
        return jsonify({"message": "Год издания должен быть от 1500 до 2100."}), 400
    if float(payload.get("replacementCost") or 0) < 0:
        return jsonify({"message": "Цена не может быть отрицательной."}), 400
    execute(
        """
        UPDATE books
        SET category_id = %s, title = %s, author = %s, isbn = %s, publish_year = %s,
            language = %s, publisher = %s, shelf_code = %s, description = %s,
            replacement_cost = %s, updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        [
            int(payload["categoryId"]),
            payload["title"],
            payload["author"],
            payload["isbn"],
            int(payload["publishYear"]),
            payload["language"],
            payload.get("publisher", ""),
            payload.get("shelfCode", ""),
            payload.get("description", ""),
            float(payload.get("replacementCost") or 0),
            book_id,
        ],
    )
    return jsonify({"ok": True, "id": book_id})


@app.post("/api/library/books/<int:book_id>/cover")
@require_role("librarian")
def upload_book_cover(book_id):
    uploaded_file = request.files.get("cover")
    if not uploaded_file or not uploaded_file.filename:
        return jsonify({"message": "Выберите файл обложки."}), 400

    book = query_one("SELECT id, cover_image FROM books WHERE id = %s AND NOT is_archived", [book_id])
    if not book:
        return jsonify({"message": "Книга не найдена."}), 404

    try:
        next_cover = save_cover_file(uploaded_file)
    except ValueError as error:
        return jsonify({"message": str(error)}), 400

    delete_cover_file(book.get("cover_image"))
    execute("UPDATE books SET cover_image = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s", [next_cover, book_id])
    return jsonify({"coverImage": next_cover})


@app.delete("/api/library/books/<int:book_id>/cover")
@require_role("librarian")
def delete_book_cover(book_id):
    book = query_one("SELECT id, cover_image FROM books WHERE id = %s AND NOT is_archived", [book_id])
    if not book:
        return jsonify({"message": "Книга не найдена."}), 404

    delete_cover_file(book.get("cover_image"))
    execute("UPDATE books SET cover_image = '', updated_at = CURRENT_TIMESTAMP WHERE id = %s", [book_id])
    return ("", 204)


@app.delete("/api/library/books/<int:book_id>")
@require_role("librarian")
def archive_book(book_id):
    book = query_one("SELECT cover_image FROM books WHERE id = %s", [book_id])
    if book:
        delete_cover_file(book.get("cover_image"))
    execute("UPDATE books SET is_archived = TRUE, cover_image = '', updated_at = CURRENT_TIMESTAMP WHERE id = %s", [book_id])
    return ("", 204)


@app.post("/api/library/books/<int:book_id>/copies")
@require_role("librarian")
def add_copies(book_id):
    payload = request.get_json(force=True)
    user = get_current_user()

    # Проверяем существование книги
    book = query_one("SELECT id, publish_year, replacement_cost FROM books WHERE id = %s", [book_id])
    if not book:
        return jsonify({"message": f"Книга с id={book_id} не найдена"}), 404

    try:
        count = int(payload.get("count") or 1)
        condition_rating = int(payload.get("conditionRating") or 5)
        price = float(payload.get("price") or 0)
    except (TypeError, ValueError):
        return jsonify({"message": "Проверьте количество, цену и состояние экземпляра."}), 400

    if count <= 0 or condition_rating < 1 or condition_rating > 5 or price < 0:
        return jsonify({"message": "Проверьте количество, цену и состояние экземпляра."}), 400

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT last_copy_number FROM books WHERE id = %s FOR UPDATE", [book_id])
            row = cursor.fetchone()
            if not row:
                return jsonify({"message": "Книга не найдена"}), 404
            start_num = row['last_copy_number'] + 1
            cursor.execute("UPDATE books SET last_copy_number = last_copy_number + %s WHERE id = %s", [count, book_id])

            for i in range(count):
                book_copy = book.copy()
                copy = create_copy(cursor, book_copy, payload, manual_counter=start_num + i)
                insert_transaction(
                    cursor,
                    {
                        "book_id": book_id,
                        "copy_id": copy["id"],
                        "operation_type": "acquisition",
                        "details": f"Добавлен экземпляр {copy['inventory_code']}",
                        "actor_name": user["full_name"],
                    },
                )
        connection.commit()
    return ("", 204)


@app.get("/api/library/patrons")
@require_role("manager")
def patrons():
    return jsonify(get_patrons())


@app.post("/api/library/patrons")
@require_role("admin")
def create_patron():
    payload = request.get_json(force=True)
    error = require_fields(payload, ["fullName", "cardNumber"])
    if error:
        return jsonify({"message": error}), 400
    status = payload.get("status", "active")
    if status not in {"active", "blocked"}:
        return jsonify({"message": "Недопустимый статус читателя."}), 400
    result = query_one(
        """
        INSERT INTO patrons (
          full_name, card_number, phone, email, address, membership_type, status, app_username
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        [
            clean_text(payload["fullName"]),
            clean_text(payload["cardNumber"]),
            payload.get("phone", ""),
            payload.get("email", ""),
            payload.get("address", ""),
            payload.get("membershipType", "Общий"),
            status,
            payload.get("appUsername", ""),
        ],
    )
    return jsonify(result), 201


@app.get("/api/library/patrons/<int:patron_id>/profile")
@require_role("manager")
def patron_profile(patron_id):
    profile = get_reader_profile(patron_id)
    if not profile:
        return jsonify({"message": "Читатель не найден."}), 404
    return jsonify(profile)


@app.put("/api/library/patrons/<int:patron_id>")
@require_role("admin")
def update_patron(patron_id):
    payload = request.get_json(force=True)
    error = require_fields(payload, ["fullName", "cardNumber"])
    if error:
        return jsonify({"message": error}), 400
    status = payload.get("status", "active")
    if status not in {"active", "blocked"}:
        return jsonify({"message": "Недопустимый статус читателя."}), 400
    execute(
        """
        UPDATE patrons
        SET full_name = %s, card_number = %s, phone = %s, email = %s,
            address = %s, membership_type = %s, status = %s, app_username = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        [
            clean_text(payload["fullName"]),
            clean_text(payload["cardNumber"]),
            payload.get("phone", ""),
            payload.get("email", ""),
            payload.get("address", ""),
            payload.get("membershipType", "Общий"),
            status,
            payload.get("appUsername", ""),
            patron_id,
        ],
    )
    return jsonify({"ok": True})


@app.delete("/api/library/patrons/<int:patron_id>")
@require_role("admin")
def archive_patron(patron_id):
    execute("UPDATE patrons SET is_archived = TRUE, updated_at = CURRENT_TIMESTAMP WHERE id = %s", [patron_id])
    return ("", 204)


@app.get("/api/admin/users")
@require_role("admin")
def admin_users():
    return jsonify(get_users())


@app.post("/api/admin/users")
@require_role("admin")
def admin_create_user():
    payload = request.get_json(force=True)
    error = require_fields(payload, ["fullName", "email", "password", "role"])
    if error:
        return jsonify({"message": error}), 400
    email = clean_text(payload.get("email")).lower()
    role = normalize_role(clean_text(payload.get("role")))
    if not validate_email(email):
        return jsonify({"message": "Введите корректный email."}), 400
    if role not in VALID_ACCOUNT_ROLES:
        return jsonify({"message": "Недопустимая роль пользователя."}), 400
    if len(payload.get("password", "")) < 6:
        return jsonify({"message": "Пароль должен быть не короче 6 символов."}), 400

    existing = query_one("SELECT id FROM app_users WHERE LOWER(email) = %s OR LOWER(username) = %s", [email, email])
    if existing:
        return jsonify({"message": "Пользователь с таким email уже существует."}), 409

    patron_id = None
    if role == "reader":
        patron = query_one(
            """
            INSERT INTO patrons (full_name, card_number, email, status, app_username)
            VALUES (%s, %s, %s, 'active', %s)
            RETURNING id
            """,
            [clean_text(payload.get("fullName")), f"P-{int(time.time())}-{uuid.uuid4().hex[:4]}", email, email],
        )
        patron_id = patron["id"]

    user = query_one(
        """
        INSERT INTO app_users (username, email, full_name, role, password_hash, patron_id, is_active)
        VALUES (%s, %s, %s, %s, %s, %s, TRUE)
        RETURNING id
        """,
        [email, email, clean_text(payload.get("fullName")), role, make_password_hash(payload["password"]), patron_id],
    )
    return jsonify(user), 201


@app.put("/api/admin/users/<int:user_id>")
@require_role("admin")
def admin_update_user(user_id):
    payload = request.get_json(force=True)
    role = normalize_role(clean_text(payload.get("role")))
    if role not in VALID_ACCOUNT_ROLES:
        return jsonify({"message": "Недопустимая роль пользователя."}), 400

    full_name = clean_text(payload.get("fullName"))
    email = clean_text(payload.get("email")).lower()
    if not full_name or not validate_email(email):
        return jsonify({"message": "Укажите ФИО и корректный email."}), 400

    is_active = bool(payload.get("isActive"))
    user = query_one("SELECT id, patron_id FROM app_users WHERE id = %s", [user_id])
    if not user:
        return jsonify({"message": "Пользователь не найден."}), 404

    patron_id = user.get("patron_id")
    if role == "reader" and not patron_id:
        patron = query_one(
            """
            INSERT INTO patrons (full_name, card_number, email, status, app_username)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
            """,
            [full_name, f"P-{int(time.time())}-{uuid.uuid4().hex[:4]}", email, "active" if is_active else "blocked", email],
        )
        patron_id = patron["id"]
    elif patron_id:
        execute(
            "UPDATE patrons SET full_name = %s, email = %s, app_username = %s, status = %s WHERE id = %s",
            [full_name, email, email, "active" if is_active else "blocked", patron_id],
        )

    params = [email, email, full_name, role, is_active, patron_id if role == "reader" else None]
    password_sql = ""
    new_password = payload.get("password") or ""
    if new_password:
        if len(new_password) < 6:
            return jsonify({"message": "Пароль должен быть не короче 6 символов."}), 400
        password_sql = ", password_hash = %s"
        params.append(make_password_hash(new_password))
    params.append(user_id)
    execute(
        f"""
        UPDATE app_users
        SET username = %s, email = %s, full_name = %s, role = %s, is_active = %s, patron_id = %s
        {password_sql}
        WHERE id = %s
        """,
        params,
    )
    return jsonify({"ok": True})


@app.delete("/api/admin/users/<int:user_id>")
@require_role("admin")
def admin_delete_user(user_id):
    current = get_current_user()
    if current["id"] == user_id:
        return jsonify({"message": "Нельзя удалить текущий аккаунт."}), 400
    execute("DELETE FROM app_users WHERE id = %s", [user_id])
    return ("", 204)


@app.post("/api/admin/users/<int:user_id>/activate")
@require_role("admin")
def admin_activate_user(user_id):
    execute("UPDATE app_users SET is_active = TRUE WHERE id = %s", [user_id])
    user = query_one("SELECT patron_id FROM app_users WHERE id = %s", [user_id])
    if user and user.get("patron_id"):
        execute("UPDATE patrons SET status = 'active' WHERE id = %s", [user["patron_id"]])
    return ("", 204)


@app.get("/api/admin/logs")
@require_role("admin")
def admin_logs():
    return jsonify(get_transactions({"role": "admin", "patron_id": None}))


@app.put("/api/admin/settings")
@require_role("admin")
def admin_settings():
    payload = request.get_json(force=True)
    with get_connection() as connection:
        with connection.cursor() as cursor:
            for key in (
                "max_loan_days",
                "fine_policy",
                "library_contact_email",
                "library_contact_phone",
                "library_demo_reset_links",
                "library_work_hours",
                "library_vk_url",
                "library_max_url",
                "library_site_name",
            ):
                if key in payload:
                    cursor.execute(
                        """
                        INSERT INTO system_settings (key, value)
                        VALUES (%s, %s)
                        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = CURRENT_TIMESTAMP
                        """,
                        [key, clean_text(payload.get(key))],
                    )
        connection.commit()
    return jsonify(get_settings())


@app.get("/api/library/loans")
@require_role("borrower")
def loans():
    return jsonify(get_loans(get_current_user()))


@app.post("/api/library/loans/issue")
@require_role("manager")
def issue_loan():
    payload = request.get_json(force=True)
    error = require_fields(payload, ["copyId", "patronId", "dueAt"])
    if error:
        return jsonify({"message": error}), 400
    user = get_current_user()
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, book_id, inventory_code, status FROM book_copies WHERE id = %s FOR UPDATE",
                [int(payload["copyId"])],
            )
            row = cursor.fetchone()
            if not row:
                return jsonify({"message": "Экземпляр не найден."}), 404
            copy = dict(row)
            if copy["status"] != "available":
                return jsonify({"message": "Экземпляр недоступен для выдачи."}), 400

            cursor.execute(
                """
                INSERT INTO loans (copy_id, patron_id, due_at, status, issued_by, notes)
                VALUES (%s, %s, %s, 'active', %s, %s)
                RETURNING id
                """,
                [int(payload["copyId"]), int(payload["patronId"]), payload["dueAt"], user["full_name"], payload.get("notes", "")],
            )
            loan = dict(cursor.fetchone())
            cursor.execute("UPDATE book_copies SET status = 'on_loan' WHERE id = %s", [int(payload["copyId"])])
            insert_transaction(
                cursor,
                {
                    "book_id": copy["book_id"],
                    "copy_id": copy["id"],
                    "patron_id": int(payload["patronId"]),
                    "loan_id": loan["id"],
                    "operation_type": "issue",
                    "details": f"Выдача экземпляра {copy['inventory_code']}",
                    "actor_name": user["full_name"],
                },
            )
        connection.commit()
    return ("", 204)


@app.post("/api/library/loans/<int:loan_id>/return")
@require_role("manager")
def return_loan(loan_id):
    payload = request.get_json(force=True) or {}
    user = get_current_user()
    next_status = payload.get("copyStatus", "available")
    if next_status not in {"available", "damaged"}:
        return jsonify({"message": "Статус после возврата: available или damaged."}), 400
    try:
        condition_rating = int(payload.get("conditionRating") or 5)
    except (TypeError, ValueError):
        return jsonify({"message": "Укажите корректное состояние экземпляра (1-5)."}), 400
    if condition_rating < 1 or condition_rating > 5:
        return jsonify({"message": "Состояние экземпляра должно быть от 1 до 5."}), 400

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT l.id, l.copy_id, l.patron_id, bc.book_id, bc.inventory_code, b.publish_year
                FROM loans l
                JOIN book_copies bc ON bc.id = l.copy_id
                JOIN books b ON b.id = bc.book_id
                WHERE l.id = %s AND l.status IN ('active', 'renewed', 'overdue')
                """,
                [loan_id],
            )
            row = cursor.fetchone()
            if not row:
                return jsonify({"message": "Активная выдача не найдена."}), 404
            loan = dict(row)
            cursor.execute(
                """
                UPDATE loans
                SET returned_at = CURRENT_TIMESTAMP, status = 'returned', received_by = %s
                WHERE id = %s
                """,
                [user["full_name"], loan_id],
            )
            cursor.execute(
                """
                UPDATE book_copies
                SET status = %s, condition_rating = %s, last_inventory_date = CURRENT_DATE
                WHERE id = %s
                """,
                [next_status, condition_rating, loan["copy_id"]],
            )
            aging = compute_aging(loan["publish_year"], time.strftime("%Y-%m-%d"), condition_rating)
            cursor.execute("UPDATE book_copies SET aging_coefficient = %s WHERE id = %s", [aging, loan["copy_id"]])
            insert_transaction(
                cursor,
                {
                    "book_id": loan["book_id"],
                    "copy_id": loan["copy_id"],
                    "patron_id": loan["patron_id"],
                    "loan_id": loan_id,
                    "operation_type": "return",
                    "details": f"Возврат экземпляра {loan['inventory_code']}",
                    "actor_name": user["full_name"],
                },
            )
        connection.commit()
    return ("", 204)


@app.post("/api/library/loans/<int:loan_id>/renew")
@require_role("manager")
def renew_loan(loan_id):
    user = get_current_user()
    payload = request.get_json(force=True) or {}
    error = require_fields(payload, ["dueAt"])
    if error:
        return jsonify({"message": error}), 400

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT l.id, l.copy_id, l.patron_id, bc.book_id
                FROM loans l
                JOIN book_copies bc ON bc.id = l.copy_id
                WHERE l.id = %s AND l.status IN ('active', 'renewed', 'overdue')
                """,
                [loan_id],
            )
            row = cursor.fetchone()
            if not row:
                return jsonify({"message": "Активная выдача не найдена."}), 404
            loan = dict(row)
            cursor.execute(
                """
                UPDATE loans
                SET due_at = %s, renewal_count = renewal_count + 1, status = 'renewed'
                WHERE id = %s
                """,
                [payload["dueAt"], loan_id],
            )
            insert_transaction(
                cursor,
                {
                    "book_id": loan["book_id"],
                    "copy_id": loan["copy_id"],
                    "patron_id": loan["patron_id"],
                    "loan_id": loan_id,
                    "operation_type": "renew",
                    "details": f"Продление срока до {payload['dueAt']}",
                    "actor_name": user["full_name"],
                },
            )
        connection.commit()
    return ("", 204)


@app.post("/api/library/loans/<int:loan_id>/renew-request")
@require_role("reader")
def renew_loan_request(loan_id):
    user = get_current_user()
    if not user.get("patron_id"):
        return jsonify({"message": "У читателя не привязан билет."}), 400

    settings = get_settings()
    try:
        max_days = int(settings.get("max_loan_days") or 14)
    except (TypeError, ValueError):
        max_days = 14

    loan = query_one(
        """
        SELECT l.id, l.due_at, l.status, b.title
        FROM loans l
        JOIN book_copies bc ON bc.id = l.copy_id
        JOIN books b ON b.id = bc.book_id
        WHERE l.id = %s AND l.patron_id = %s AND l.status IN ('active', 'renewed', 'overdue')
        """,
        [loan_id, user["patron_id"]],
    )
    if not loan:
        return jsonify({"message": "Активная выдача не найдена."}), 404

    due_at = time.strftime("%Y-%m-%d", time.localtime(time.time() + max_days * 86400))
    execute(
        """
        UPDATE loans
        SET due_at = %s, renewal_count = renewal_count + 1, status = 'renewed'
        WHERE id = %s
        """,
        [due_at, loan_id],
    )
    execute(
        """
        INSERT INTO book_transactions (loan_id, operation_type, details, actor_name)
        VALUES (%s, 'renew', %s, %s)
        """,
        [loan_id, f"Продление по запросу читателя до {due_at}", user["full_name"]],
    )
    return jsonify({"dueAt": due_at, "message": f"Срок возврата «{loan['title']}» продлён до {due_at}."})


@app.post("/api/library/loans/<int:loan_id>/lost")
@require_role("manager")
def lost_loan(loan_id):
    user = get_current_user()
    payload = request.get_json(force=True) or {}
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT l.id, l.copy_id, l.patron_id, bc.book_id, bc.inventory_code
                FROM loans l
                JOIN book_copies bc ON bc.id = l.copy_id
                WHERE l.id = %s AND l.status IN ('active', 'renewed', 'overdue')
                """,
                [loan_id],
            )
            row = cursor.fetchone()
            if not row:
                return jsonify({"message": "Активная выдача не найдена."}), 404
            loan = dict(row)
            cursor.execute("UPDATE loans SET status = 'lost', returned_at = CURRENT_TIMESTAMP WHERE id = %s", [loan_id])
            cursor.execute("UPDATE book_copies SET status = 'lost' WHERE id = %s", [loan["copy_id"]])
            insert_transaction(
                cursor,
                {
                    "book_id": loan["book_id"],
                    "copy_id": loan["copy_id"],
                    "patron_id": loan["patron_id"],
                    "loan_id": loan_id,
                    "operation_type": "lost",
                    "details": payload.get("notes", f"Утеря экземпляра {loan['inventory_code']}"),
                    "actor_name": user["full_name"],
                },
            )
        connection.commit()
    return ("", 204)


@app.post("/api/library/copies/<int:copy_id>/write-off")
@require_role("librarian")
def write_off(copy_id):
    payload = request.get_json(force=True, silent=True) or {}
    user = get_current_user()
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, book_id, status FROM book_copies WHERE id = %s",
                [copy_id],
            )
            row = cursor.fetchone()
            if not row:
                return jsonify({"message": "Экземпляр не найден."}), 404
            copy = dict(row)
            if copy["status"] not in ("available", "damaged"):
                return jsonify(
                    {"message": "Списать можно только свободный или повреждённый экземпляр (не на выдаче)."}
                ), 400
            cursor.execute(
                """
                SELECT id FROM loans
                WHERE copy_id = %s AND status IN ('active', 'renewed', 'overdue')
                LIMIT 1
                """,
                [copy_id],
            )
            if cursor.fetchone():
                return jsonify({"message": "Нельзя списать экземпляр с активной выдачей. Сначала оформите возврат."}), 400
            cursor.execute(
                """
                UPDATE book_copies
                SET status = 'written_off', written_off_reason = %s, last_inventory_date = CURRENT_DATE
                WHERE id = %s
                """,
                [payload.get("reason", "Списание"), copy_id],
            )
            insert_transaction(
                cursor,
                {
                    "book_id": copy["book_id"],
                    "copy_id": copy_id,
                    "operation_type": "write_off",
                    "details": payload.get("reason", "Списание"),
                    "actor_name": user["full_name"],
                },
            )
        connection.commit()
    return ("", 204)


@app.post("/api/library/copies/<int:copy_id>/replace")
@require_role("librarian")
def replace_copy(copy_id):
    payload = request.get_json(force=True, silent=True) or {}
    user = get_current_user()

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT bc.id, bc.book_id, bc.status, b.publish_year, b.replacement_cost
                FROM book_copies bc
                JOIN books b ON b.id = bc.book_id
                WHERE bc.id = %s
                FOR UPDATE
            """, [copy_id])

            row = cursor.fetchone()
            if not row:
                return jsonify({"message": "Экземпляр не найден"}), 404

            original = dict(row)
            if original["status"] == "replaced":
                return jsonify({"message": "Этот экземпляр уже заменён. Повторная замена не требуется."}), 400
            if original["status"] not in {"available", "damaged", "lost", "written_off"}:
                return jsonify({"message": "Замена доступна только для доступного, повреждённого, утерянного или списанного экземпляра."}), 400
            cursor.execute(
                """
                SELECT id FROM loans
                WHERE copy_id = %s AND status IN ('active', 'renewed', 'overdue')
                LIMIT 1
                """,
                [copy_id],
            )
            if cursor.fetchone():
                return jsonify({"message": "Нельзя заменить экземпляр с активной выдачей. Сначала оформите возврат или утерю."}), 400

            book_for_copy = {
                "id": original["book_id"],
                "publish_year": original["publish_year"],
                "replacement_cost": original["replacement_cost"],
            }
            new_copy = create_copy(cursor, book_for_copy, payload)

            cursor.execute(
                "UPDATE book_copies SET status = 'replaced', replaced_by_copy_id = %s WHERE id = %s",
                [new_copy["id"], copy_id]
            )

            insert_transaction(
                cursor,
                {
                    "book_id": original["book_id"],
                    "copy_id": copy_id,
                    "operation_type": "replacement",
                    "details": f"Замена экземпляра на {new_copy['inventory_code']}",
                    "actor_name": user["full_name"],
                },
            )
        connection.commit()

    return ("", 204)


@app.put("/api/library/copies/<int:copy_id>")
@require_role("librarian")
def update_copy(copy_id):
    payload = request.get_json(force=True, silent=True) or {}
    user = get_current_user()

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT bc.id, bc.book_id, bc.status, bc.acquisition_date, bc.price,
                       bc.condition_rating, b.publish_year
                FROM book_copies bc
                JOIN books b ON b.id = bc.book_id
                WHERE bc.id = %s
                """,
                [copy_id],
            )
            row = cursor.fetchone()
            if not row:
                return jsonify({"message": "Экземпляр не найден."}), 404
            copy = dict(row)

            if copy["status"] in {"written_off", "replaced", "lost"}:
                return jsonify({"message": "Нельзя редактировать списанный, заменённый или утерянный экземпляр."}), 400

            if copy["status"] == "on_loan":
                return jsonify({"message": "Экземпляр на выдаче. Сначала оформите возврат, затем измените данные."}), 400

            try:
                condition_rating = int(payload.get("conditionRating", payload.get("condition_rating", 5)))
            except (TypeError, ValueError):
                return jsonify({"message": "Состояние должно быть числом от 1 до 5."}), 400
            if condition_rating < 1 or condition_rating > 5:
                return jsonify({"message": "Состояние должно быть от 1 до 5."}), 400

            next_status = payload.get("status") or copy["status"]
            if next_status not in {"available", "damaged"}:
                return jsonify({"message": "Допустимые статусы: «Доступен» или «Повреждён»."}), 400

            acquisition_date = clean_text(payload.get("acquisitionDate")) or None
            if not acquisition_date and copy.get("acquisition_date"):
                acquisition_date = str(copy["acquisition_date"])[:10]
            notes = clean_text(payload.get("notes"))
            try:
                price = float(payload.get("price")) if payload.get("price") not in (None, "") else None
            except (TypeError, ValueError):
                return jsonify({"message": "Укажите корректную цену экземпляра."}), 400

            updates = [
                "condition_rating = %s",
                "status = %s",
                "notes = %s",
                "acquisition_date = %s",
                "last_inventory_date = CURRENT_DATE",
            ]
            params = [condition_rating, next_status, notes, acquisition_date]
            if price is not None:
                updates.append("price = %s")
                params.append(price)

            aging = compute_aging(copy["publish_year"], acquisition_date, condition_rating)
            updates.append("aging_coefficient = %s")
            params.append(aging)
            params.append(copy_id)

            cursor.execute(
                f"UPDATE book_copies SET {', '.join(updates)} WHERE id = %s",
                params,
            )
            insert_transaction(
                cursor,
                {
                    "book_id": copy["book_id"],
                    "copy_id": copy_id,
                    "operation_type": "acquisition",
                    "details": f"Обновлены данные экземпляра (состояние {condition_rating}/5)",
                    "actor_name": user["full_name"],
                },
            )
        connection.commit()
    return ("", 204)


@app.put("/api/library/copies/<int:copy_id>/comment")
@require_role("librarian")
def update_copy_comment(copy_id):
    payload = request.get_json(force=True, silent=True) or {}
    notes = clean_text(payload.get("notes"))
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM book_copies WHERE id = %s", [copy_id])
            if not cursor.fetchone():
                return jsonify({"message": "Экземпляр не найден."}), 404
            cursor.execute(
                """
                UPDATE book_copies
                SET notes = %s, last_inventory_date = CURRENT_DATE
                WHERE id = %s
                """,
                [notes, copy_id],
            )
        connection.commit()
    return ("", 204)

@app.get("/api/library/transactions")
@require_role("borrower")
def transactions():
    return jsonify(get_transactions(get_current_user()))


@app.get("/<path:path>")
def static_proxy(path):
    return send_from_directory(PUBLIC_DIR, path)


if __name__ == "__main__":
    ensure_schema()
    ensure_upload_dirs()
    debug = os.getenv("FLASK_DEBUG", "false").lower() in ("1", "true", "yes")
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "3000")), debug=debug)