# -*- coding: utf-8 -*-
"""Build sql/reset-catalog-only.sql from data/catalog_books.json."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "catalog_books.json"
OUT = ROOT / "sql" / "reset-catalog-only.sql"


def esc(value: str) -> str:
    return value.replace("'", "''")


def main():
    books = json.loads(MANIFEST.read_text(encoding="utf-8"))
    book_rows = []
    copy_rows = []
    for book in books:
        book_rows.append(
            "("
            f"{book['id']}, {book['category_id']}, '{esc(book['title'])}', '{esc(book['author'])}', "
            f"'{esc(book['isbn'])}', {book['publish_year']}, '{esc(book['language'])}', "
            f"'{esc(book['publisher'])}', '{esc(book['shelf_code'])}', '{esc(book['description'])}', "
            f"{book['replacement_cost']}, '{esc(book['cover_image'])}'"
            ")"
        )
        copy_rows.append(
            f"({book['id']}, 'INV-{book['id']}-001', '2023-01-15', {book['replacement_cost']}, 5, 0.20, 'available', 'Основной фонд', CURRENT_DATE)"
        )
        if book["id"] in {3, 4, 12, 16}:
            status = "on_loan" if book["id"] in {3, 4} else "available"
            copy_rows.append(
                f"({book['id']}, 'INV-{book['id']}-002', '2023-06-01', {book['replacement_cost']}, 4, 0.35, '{status}', 'Дополнительный экземпляр', CURRENT_DATE)"
            )

    sql = f"""-- Сброс только каталога: книги, экземпляры, выдачи, запросы.
-- Пользователи, читатели, категории и настройки не затрагиваются.

SET client_encoding = 'UTF8';

BEGIN;

TRUNCATE TABLE book_requests RESTART IDENTITY CASCADE;
TRUNCATE TABLE book_transactions RESTART IDENTITY CASCADE;
TRUNCATE TABLE loans RESTART IDENTITY CASCADE;
TRUNCATE TABLE book_copies RESTART IDENTITY CASCADE;
TRUNCATE TABLE books RESTART IDENTITY CASCADE;

INSERT INTO books (id, category_id, title, author, isbn, publish_year, language, publisher, shelf_code, description, replacement_cost, cover_image) VALUES
{",\n".join(book_rows)};

INSERT INTO book_copies (book_id, inventory_code, acquisition_date, price, condition_rating, aging_coefficient, status, notes, last_inventory_date) VALUES
{",\n".join(copy_rows)};

SELECT setval(pg_get_serial_sequence('books', 'id'), (SELECT COALESCE(MAX(id), 1) FROM books));
SELECT setval(pg_get_serial_sequence('book_copies', 'id'), (SELECT COALESCE(MAX(id), 1) FROM book_copies));

COMMIT;
"""
    OUT.write_text(sql, encoding="utf-8")
    print(f"Wrote {OUT} with {len(books)} books")


if __name__ == "__main__":
    main()
