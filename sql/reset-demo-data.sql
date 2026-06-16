SET client_encoding = 'UTF8';

BEGIN;

TRUNCATE TABLE book_requests RESTART IDENTITY CASCADE;
TRUNCATE TABLE book_transactions RESTART IDENTITY CASCADE;
TRUNCATE TABLE loans RESTART IDENTITY CASCADE;
TRUNCATE TABLE app_users RESTART IDENTITY CASCADE;
TRUNCATE TABLE patrons RESTART IDENTITY CASCADE;
TRUNCATE TABLE book_copies RESTART IDENTITY CASCADE;
TRUNCATE TABLE books RESTART IDENTITY CASCADE;
TRUNCATE TABLE categories RESTART IDENTITY CASCADE;

INSERT INTO categories (id, name, description) VALUES
(1, 'Учебная литература', 'Учебники, пособия и профессиональная литература для обучения.'),
(2, 'Художественная литература', 'Романы, повести, поэзия, драматургия.'),
(3, 'Научно-популярная литература', 'Научно-популярные и познавательные издания.');

INSERT INTO books (id, category_id, title, author, isbn, publish_year, language, publisher, shelf_code, description, replacement_cost) VALUES
(1, 1, 'Чистый код', 'Роберт Мартин', '978-5-496-00487-9', 2019, 'Русский', 'Питер', 'A-01', 'Практики написания понятного и поддерживаемого кода.', 1800),
(2, 1, 'Design Patterns', 'Erich Gamma', '978-0-201-63361-0', 1994, 'Английский', 'Addison-Wesley', 'A-04', 'Классика по шаблонам проектирования ПО.', 2500),
(3, 1, 'Python для детей', 'Джейсон Бриггс', '978-5-97060-782-4', 2016, 'Русский', 'ДМК Пресс', 'A-07', 'Введение в программирование на Python.', 1200),
(4, 2, 'Мастер и Маргарита', 'Михаил Булгаков', '978-5-389-01686-6', 2022, 'Русский', 'Азбука', 'B-12', 'Роман о добре и зле, Москве и мистике.', 900),
(5, 2, 'Евгений Онегин', 'Александр Пушкин', '978-5-17-123456-7', 2021, 'Русский', 'АСТ', 'B-01', 'Роман в стихах — основа школьной программы.', 650),
(6, 2, '1984', 'Джордж Оруэлл', '978-5-17-093899-7', 2020, 'Русский', 'АСТ', 'B-08', 'Антиутопия о тотальном контроле и свободе слова.', 750),
(7, 2, 'Преступление и наказание', 'Фёдор Достоевский', '978-5-389-123456-1', 2019, 'Русский', 'Азбука', 'B-05', 'Психологический роман о нравственном выборе.', 800),
(8, 3, 'Краткая история времени', 'Стивен Хокинг', '978-5-17-106101-3', 2020, 'Русский', 'АСТ', 'C-03', 'Популярное изложение космологии и физики.', 1400),
(9, 3, 'Sapiens. Краткая история человечества', 'Юваль Ной Харари', '978-5-17-103832-9', 2019, 'Русский', 'АСТ', 'C-06', 'От каменного века до современных технологий.', 1100),
(10, 3, 'Космос', 'Карл Саган', '978-5-389-098765-4', 2018, 'Русский', 'Азбука', 'C-02', 'Путешествие по Вселенной для широкого читателя.', 950),
(11, 3, 'Физика для будущих президентов', 'Ричард Мюллер', '978-5-496-01234-5', 2017, 'Русский', 'Питер', 'C-08', 'Энергия, климат и наука без формул.', 1300),
(12, 2, 'Гарри Поттер и философский камень', 'Джоан Роулинг', '978-5-389-045678-9', 2021, 'Русский', 'Махаон', 'B-15', 'Первая книга о юном волшебнике.', 850);

INSERT INTO book_copies (book_id, inventory_code, acquisition_date, price, condition_rating, aging_coefficient, status, notes, last_inventory_date) VALUES
(1, 'INV-1-001', '2023-01-10', 1800, 5, 0.30, 'available', 'Основной фонд', CURRENT_DATE),
(1, 'INV-1-002', '2023-06-15', 1800, 4, 0.42, 'available', 'Читальный зал', CURRENT_DATE),
(2, 'INV-2-001', '2022-09-12', 2500, 4, 0.55, 'available', 'Справочник', CURRENT_DATE),
(3, 'INV-3-001', '2024-02-01', 1200, 5, 0.18, 'available', 'Новое поступление', CURRENT_DATE),
(3, 'INV-3-002', '2024-02-01', 1200, 5, 0.18, 'on_loan', 'Выдана читателю', CURRENT_DATE),
(4, 'INV-4-001', '2023-11-16', 900, 5, 0.20, 'available', 'Абонемент', CURRENT_DATE),
(4, 'INV-4-002', '2022-08-01', 900, 4, 0.35, 'on_loan', 'Популярная книга', CURRENT_DATE),
(5, 'INV-5-001', '2021-05-20', 650, 4, 0.48, 'available', 'Классика', CURRENT_DATE),
(6, 'INV-6-001', '2023-03-12', 750, 5, 0.25, 'available', 'Фонд худлита', CURRENT_DATE),
(7, 'INV-7-001', '2020-01-15', 800, 3, 0.62, 'damaged', 'Требует ремонта корешка', CURRENT_DATE),
(8, 'INV-8-001', '2022-05-11', 1400, 4, 0.32, 'available', 'Научпоп', CURRENT_DATE),
(9, 'INV-9-001', '2023-09-01', 1100, 5, 0.22, 'available', 'Новинка', CURRENT_DATE),
(10, 'INV-10-001', '2022-12-01', 950, 4, 0.38, 'available', 'Космос', CURRENT_DATE),
(11, 'INV-11-001', '2021-07-14', 1300, 4, 0.45, 'available', 'Для старшеклассников', CURRENT_DATE),
(12, 'INV-12-001', '2024-01-16', 850, 5, 0.15, 'available', 'Детский абонемент', CURRENT_DATE),
(12, 'INV-12-002', '2024-01-16', 850, 5, 0.15, 'available', 'Детский абонемент', CURRENT_DATE);

INSERT INTO patrons (id, full_name, card_number, phone, email, address, membership_type, status, app_username) VALUES
(1, 'Анна Смирнова', 'RB-1001', '+7 999 111-22-33', 'anna@example.com', 'Красноярск', 'Студент', 'active', 'reader@example.com'),
(2, 'Илья Петров', 'RB-1002', '+7 999 222-33-44', 'ilya@example.com', 'Красноярск', 'Преподаватель', 'active', ''),
(3, 'Мария Иванова', 'RB-1003', '+7 999 333-44-55', 'maria@example.com', 'Красноярск', 'Общий', 'active', '');

INSERT INTO app_users (id, username, email, full_name, role, password_hash, patron_id, is_active) VALUES
(1, 'reader@example.com', 'reader@example.com', 'Анна Смирнова', 'reader', '5daa1c352c0994c3496cd56183b3a339:71e9626c44d2f126768c88e521a6b13e0bc074bb48cf58e051f55d8c954c24cbb0750d0cef2efc82deaa7610880310a6449f6edef8b7cd5900eb687ed44e4419', 1, TRUE),
(2, 'librarian@example.com', 'librarian@example.com', 'Старший библиотекарь', 'librarian', '1e9139a0c10e49cd388fe974e58e4475:31938acf0db37e7c4330f983ee34ac358e3473b500dd149cb755e1e56586a4b407e688e70e2ee33f2e49f10c9230f9b8ed00dfff9b3beaed05639e1efbbbb4a4', NULL, TRUE),
(3, 'admin@example.com', 'admin@example.com', 'Главный администратор', 'admin', 'e3f11da3794a033deb26b7257ba5cfdd:09ad8524024ed174e9f7b8bead4c3ad366af689786edc6ac098bf7c6d8030ccd5641cedba68ab3fa3f77a76b6d88b303d084ad4323da5c0f39d8053a98cbbc90', NULL, TRUE),
(4, 'manager@example.com', 'manager@example.com', 'Менеджер смены', 'manager', '48cd207b40a44ec0a35dccca4dc513d6:c05e8145d17cfffc829a14ddb1839a121224aad6ee8fdb98687e49435a7302bb0fca325f054ebe457e091c43c04ad751e4939cf818bfdd7c32dc9299f9ae13ca', NULL, TRUE);

INSERT INTO loans (copy_id, patron_id, issued_at, due_at, returned_at, status, renewal_count, issued_by, received_by, notes) VALUES
(5, 1, CURRENT_TIMESTAMP - INTERVAL '5 days', CURRENT_DATE + INTERVAL '9 days', NULL, 'active', 0, 'Старший библиотекарь', NULL, 'Учебная литература'),
(7, 1, CURRENT_TIMESTAMP - INTERVAL '12 days', CURRENT_DATE + INTERVAL '2 days', NULL, 'active', 0, 'Менеджер смены', NULL, 'Художественная литература');

INSERT INTO book_transactions (book_id, copy_id, patron_id, loan_id, operation_type, quantity, details, actor_name) VALUES
(1, 1, NULL, NULL, 'acquisition', 1, 'Поступление в фонд', 'Система'),
(3, 5, 1, 1, 'issue', 1, 'Выдача учебника', 'Старший библиотекарь'),
(4, 7, 1, 2, 'issue', 1, 'Выдача художественной литературы', 'Менеджер смены');

COMMIT;