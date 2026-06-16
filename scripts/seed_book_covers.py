# -*- coding: utf-8 -*-
"""Download or generate cover images for demo catalog books."""
from __future__ import annotations

import json
import struct
import urllib.error
import urllib.request
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COVERS_DIR = ROOT / "public" / "uploads" / "covers"
MANIFEST = ROOT / "data" / "catalog_books.json"

BOOKS = [
    {"id": 1, "isbn": "9785496004879", "title": "Чистый код", "author": "Роберт Мартин", "category_id": 1, "publish_year": 2019, "language": "Русский", "publisher": "Питер", "shelf_code": "A-01", "description": "Практики написания понятного и поддерживаемого кода.", "replacement_cost": 1800, "hue": 210},
    {"id": 2, "isbn": "9780201633610", "title": "Design Patterns", "author": "Erich Gamma", "category_id": 1, "publish_year": 1994, "language": "Английский", "publisher": "Addison-Wesley", "shelf_code": "A-04", "description": "Классика по шаблонам проектирования ПО.", "replacement_cost": 2500, "hue": 200},
    {"id": 3, "isbn": "9785970607824", "title": "Python для детей", "author": "Джейсон Бриггс", "category_id": 1, "publish_year": 2016, "language": "Русский", "publisher": "ДМК Пресс", "shelf_code": "A-07", "description": "Введение в программирование на Python.", "replacement_cost": 1200, "hue": 140},
    {"id": 4, "isbn": "9785389016866", "title": "Мастер и Маргарита", "author": "Михаил Булгаков", "category_id": 2, "publish_year": 2022, "language": "Русский", "publisher": "Азбука", "shelf_code": "B-12", "description": "Роман о добре и зле, Москве и мистике.", "replacement_cost": 900, "hue": 25},
    {"id": 5, "isbn": "9785171234567", "title": "Евгений Онегин", "author": "Александр Пушкин", "category_id": 2, "publish_year": 2021, "language": "Русский", "publisher": "АСТ", "shelf_code": "B-01", "description": "Роман в стихах — основа школьной программы.", "replacement_cost": 650, "hue": 35},
    {"id": 6, "isbn": "9785170938997", "title": "1984", "author": "Джордж Оруэлл", "category_id": 2, "publish_year": 2020, "language": "Русский", "publisher": "АСТ", "shelf_code": "B-08", "description": "Антиутопия о тотальном контроле и свободе слова.", "replacement_cost": 750, "hue": 0},
    {"id": 7, "isbn": "9785389123456", "title": "Преступление и наказание", "author": "Фёдор Достоевский", "category_id": 2, "publish_year": 2019, "language": "Русский", "publisher": "Азбука", "shelf_code": "B-05", "description": "Психологический роман о нравственном выборе.", "replacement_cost": 800, "hue": 15},
    {"id": 8, "isbn": "9785171061013", "title": "Краткая история времени", "author": "Стивен Хокинг", "category_id": 3, "publish_year": 2020, "language": "Русский", "publisher": "АСТ", "shelf_code": "C-03", "description": "Популярное изложение космологии и физики.", "replacement_cost": 1400, "hue": 260},
    {"id": 9, "isbn": "9785171038329", "title": "Sapiens", "author": "Юваль Ной Харари", "category_id": 3, "publish_year": 2019, "language": "Русский", "publisher": "АСТ", "shelf_code": "C-06", "description": "Краткая история человечества.", "replacement_cost": 1100, "hue": 45},
    {"id": 10, "isbn": "9785389098765", "title": "Космос", "author": "Карл Саган", "category_id": 3, "publish_year": 2018, "language": "Русский", "publisher": "Азбука", "shelf_code": "C-02", "description": "Путешествие по Вселенной.", "replacement_cost": 950, "hue": 240},
    {"id": 11, "isbn": "9785496012345", "title": "Физика для будущих президентов", "author": "Ричард Мюллер", "category_id": 3, "publish_year": 2017, "language": "Русский", "publisher": "Питер", "shelf_code": "C-08", "description": "Энергия, климат и наука без формул.", "replacement_cost": 1300, "hue": 190},
    {"id": 12, "isbn": "9785389045678", "title": "Гарри Поттер и философский камень", "author": "Джоан Роулинг", "category_id": 2, "publish_year": 2021, "language": "Русский", "publisher": "Махаон", "shelf_code": "B-15", "description": "Первая книга о юном волшебнике.", "replacement_cost": 850, "hue": 120},
    {"id": 13, "isbn": "9785040903456", "title": "Алгоритмы", "author": "Томас Кормен", "category_id": 1, "publish_year": 2019, "language": "Русский", "publisher": "Вильямс", "shelf_code": "A-09", "description": "Построение и анализ алгоритмов.", "replacement_cost": 3200, "hue": 220},
    {"id": 14, "isbn": "9785040901234", "title": "JavaScript. Подробное руководство", "author": "Дэвид Флэнаган", "category_id": 1, "publish_year": 2021, "language": "Русский", "publisher": "Вильямс", "shelf_code": "A-11", "description": "Справочник по языку JavaScript.", "replacement_cost": 2100, "hue": 55},
    {"id": 15, "isbn": "9785040905678", "title": "Грокаем алгоритмы", "author": "Адитья Бхаргава", "category_id": 1, "publish_year": 2020, "language": "Русский", "publisher": "Питер", "shelf_code": "A-12", "description": "Иллюстрированное введение в алгоритмы.", "replacement_cost": 1500, "hue": 170},
    {"id": 16, "isbn": "9785170878841", "title": "Война и мир", "author": "Лев Толстой", "category_id": 2, "publish_year": 2018, "language": "Русский", "publisher": "АСТ", "shelf_code": "B-02", "description": "Эпопея о России эпохи наполеоновских войн.", "replacement_cost": 1200, "hue": 30},
    {"id": 17, "isbn": "9785170887654", "title": "Анна Каренина", "author": "Лев Толстой", "category_id": 2, "publish_year": 2019, "language": "Русский", "publisher": "АСТ", "shelf_code": "B-03", "description": "Роман о любви, долге и обществе.", "replacement_cost": 900, "hue": 340},
    {"id": 18, "isbn": "9785389076543", "title": "Идиот", "author": "Фёдор Достоевский", "category_id": 2, "publish_year": 2020, "language": "Русский", "publisher": "Азбука", "shelf_code": "B-06", "description": "История князя Мышкина в Петербурге.", "replacement_cost": 780, "hue": 10},
    {"id": 19, "isbn": "9785170998876", "title": "Три товарища", "author": "Эрих Мария Ремарк", "category_id": 2, "publish_year": 2021, "language": "Русский", "publisher": "АСТ", "shelf_code": "B-09", "description": "Роман о дружбе и любви между мировыми войнами.", "replacement_cost": 820, "hue": 300},
    {"id": 20, "isbn": "9785171001123", "title": "Маленький принц", "author": "Антуан де Сент-Экзюпери", "category_id": 2, "publish_year": 2022, "language": "Русский", "publisher": "АСТ", "shelf_code": "B-10", "description": "Философская сказка для детей и взрослых.", "replacement_cost": 600, "hue": 50},
    {"id": 21, "isbn": "9785171012345", "title": "Краткая история почти всего", "author": "Билл Брайсон", "category_id": 3, "publish_year": 2019, "language": "Русский", "publisher": "АСТ", "shelf_code": "C-04", "description": "Увлекательный обзор науки.", "replacement_cost": 1050, "hue": 160},
    {"id": 22, "isbn": "9785389111222", "title": "Происхождение видов", "author": "Чарльз Дарвин", "category_id": 3, "publish_year": 2018, "language": "Русский", "publisher": "Азбука", "shelf_code": "C-05", "description": "Классика эволюционной биологии.", "replacement_cost": 980, "hue": 100},
    {"id": 23, "isbn": "9785171023456", "title": "Краткая история России", "author": "Борис Акунин", "category_id": 3, "publish_year": 2020, "language": "Русский", "publisher": "АСТ", "shelf_code": "C-07", "description": "Обзор ключевых событий российской истории.", "replacement_cost": 890, "hue": 20},
    {"id": 24, "isbn": "9785040909999", "title": "Искусство программирования", "author": "Дональд Кнут", "category_id": 1, "publish_year": 2017, "language": "Русский", "publisher": "Вильямс", "shelf_code": "A-15", "description": "Фундаментальный труд по алгоритмам и структурам данных.", "replacement_cost": 4500, "hue": 280},
    {"id": 25, "isbn": "9785389222333", "title": "Тёмные аллеи", "author": "Иван Бунин", "category_id": 2, "publish_year": 2021, "language": "Русский", "publisher": "Азбука", "shelf_code": "B-11", "description": "Сборник лирических рассказов.", "replacement_cost": 700, "hue": 330},
]


def png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", crc)


def solid_png(path: Path, rgb: tuple[int, int, int], width: int = 240, height: int = 360) -> None:
    raw = b""
    row = bytes([0, rgb[0], rgb[1], rgb[2]]) * width
    for _ in range(height):
        raw += row
    compressed = zlib.compress(raw, 9)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n" + png_chunk(b"IHDR", ihdr) + png_chunk(b"IDAT", compressed) + png_chunk(b"IEND", b"")
    path.write_bytes(png)


def hue_to_rgb(hue: int) -> tuple[int, int, int]:
    h = (hue % 360) / 60.0
    x = int(255 * (1 - abs(h % 2 - 1)))
    if h < 1:
        return 255, x, 0
    if h < 2:
        return x, 255, 0
    if h < 3:
        return 0, 255, x
    if h < 4:
        return 0, x, 255
    if h < 5:
        return x, 0, 255
    return 255, 0, x


def download_cover(isbn: str, dest: Path) -> bool:
    digits = "".join(ch for ch in isbn if ch.isdigit())
    url = f"https://covers.openlibrary.org/b/isbn/{digits}-M.jpg"
    req = urllib.request.Request(url, headers={"User-Agent": "library-web-system/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = resp.read()
        if len(data) < 1200:
            return False
        dest.write_bytes(data)
        return True
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def main():
    COVERS_DIR.mkdir(parents=True, exist_ok=True)
    manifest = []
    for book in BOOKS:
        # Важно: мы гарантируем, что файл действительно является PNG,
        # поэтому используем расширение .png (иначе браузер может не отрисовать
        # "jpg" с PNG-данными).
        filename = f"book-{book['id']:02d}.png"
        path = COVERS_DIR / filename
        solid_png(path, hue_to_rgb(book["hue"]))
        manifest.append({**book, "cover_image": f"/uploads/covers/{filename}"})
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Prepared {len(manifest)} covers in {COVERS_DIR}")


if __name__ == "__main__":
    main()
