SET client_encoding = 'UTF8';

ALTER TABLE app_users ADD COLUMN IF NOT EXISTS email VARCHAR(120) NOT NULL DEFAULT '';
UPDATE app_users SET email = username WHERE email = '';
CREATE UNIQUE INDEX IF NOT EXISTS app_users_email_unique ON app_users (LOWER(email));

DO $$
DECLARE constraint_name text;
BEGIN
  SELECT conname INTO constraint_name
  FROM pg_constraint
  WHERE conrelid = 'app_users'::regclass
    AND contype = 'c'
    AND pg_get_constraintdef(oid) LIKE '%role%';

  IF constraint_name IS NOT NULL THEN
    EXECUTE format('ALTER TABLE app_users DROP CONSTRAINT %I', constraint_name);
  END IF;
END $$;

ALTER TABLE app_users
  DROP CONSTRAINT IF EXISTS app_users_role_check;
UPDATE app_users SET role = 'reader' WHERE role = 'borrower';
UPDATE app_users SET role = 'librarian' WHERE role = 'manager';
UPDATE app_users SET role = 'reader', is_active = FALSE WHERE role = 'guest';

ALTER TABLE app_users
  ADD CONSTRAINT app_users_role_check
  CHECK (role IN ('reader', 'librarian', 'admin', 'borrower', 'manager'));

CREATE TABLE IF NOT EXISTS book_requests (
  id SERIAL PRIMARY KEY,
  user_id INT NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
  book_id INT NOT NULL REFERENCES books(id) ON DELETE CASCADE,
  request_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  status VARCHAR(20) NOT NULL CHECK (status IN ('pending', 'approved', 'rejected')),
  processed_at TIMESTAMP,
  processed_by VARCHAR(120),
  notes TEXT NOT NULL DEFAULT ''
);

CREATE UNIQUE INDEX IF NOT EXISTS book_requests_pending_unique
  ON book_requests (user_id, book_id)
  WHERE status = 'pending';

CREATE TABLE IF NOT EXISTS book_cart_items (
  id SERIAL PRIMARY KEY,
  patron_id INT NOT NULL REFERENCES patrons(id) ON DELETE CASCADE,
  book_id INT NOT NULL REFERENCES books(id) ON DELETE CASCADE,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (patron_id, book_id)
);

INSERT INTO book_requests (user_id, book_id, request_date, status)
SELECT au.id, ci.book_id, ci.created_at, 'pending'
FROM book_cart_items ci
JOIN app_users au ON au.patron_id = ci.patron_id
ON CONFLICT DO NOTHING;

DROP TABLE IF EXISTS book_cart_items;

CREATE TABLE IF NOT EXISTS system_settings (
  key VARCHAR(80) PRIMARY KEY,
  value TEXT NOT NULL DEFAULT '',
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO system_settings (key, value)
VALUES ('max_loan_days', '14'), ('fine_policy', '')
ON CONFLICT (key) DO NOTHING;

