SET client_encoding = 'UTF8';

-- 1. Список всех книг с количеством экземпляров
SELECT
  b.id,
  b.title,
  b.author,
  b.isbn,
  c.name AS category,
  COUNT(bc.id) AS total_copies
FROM books b
JOIN categories c ON c.id = b.category_id
LEFT JOIN book_copies bc ON bc.book_id = b.id
WHERE NOT b.is_archived
GROUP BY b.id, c.name
ORDER BY b.title;

-- 2. Все читатели
SELECT
  id,
  full_name,
  card_number,
  membership_type,
  status,
  app_username
FROM patrons
WHERE NOT is_archived
ORDER BY full_name;

-- 3. Активные выдачи
SELECT
  l.id,
  p.full_name AS patron,
  b.title,
  bc.inventory_code,
  l.issued_at,
  l.due_at,
  l.status
FROM loans l
JOIN patrons p ON p.id = l.patron_id
JOIN book_copies bc ON bc.id = l.copy_id
JOIN books b ON b.id = bc.book_id
WHERE l.status IN ('active', 'renewed', 'overdue')
ORDER BY l.due_at;

-- 4. Экземпляры, требующие списания или ремонта
SELECT
  bc.id,
  b.title,
  bc.inventory_code,
  bc.status,
  bc.condition_rating,
  bc.aging_coefficient
FROM book_copies bc
JOIN books b ON b.id = bc.book_id
WHERE bc.status IN ('damaged', 'written_off', 'lost')
ORDER BY bc.aging_coefficient DESC;

-- 5. Пользователи входа по ролям
SELECT
  username,
  full_name,
  role,
  is_active
FROM app_users
ORDER BY role, username;

-- 6. История операций
SELECT
  t.operation_date,
  t.operation_type,
  b.title,
  bc.inventory_code,
  p.full_name AS patron,
  t.actor_name,
  t.details
FROM book_transactions t
LEFT JOIN books b ON b.id = t.book_id
LEFT JOIN book_copies bc ON bc.id = t.copy_id
LEFT JOIN patrons p ON p.id = t.patron_id
ORDER BY t.operation_date DESC;
