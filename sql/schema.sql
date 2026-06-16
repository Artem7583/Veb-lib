SET client_encoding = 'UTF8';

CREATE TABLE IF NOT EXISTS categories (
  id SERIAL PRIMARY KEY,
  name VARCHAR(120) NOT NULL UNIQUE,
  description TEXT
);

CREATE TABLE IF NOT EXISTS books (
  id SERIAL PRIMARY KEY,
  category_id INT NOT NULL REFERENCES categories(id) ON DELETE RESTRICT,
  title VARCHAR(255) NOT NULL,
  author VARCHAR(255) NOT NULL,
  isbn VARCHAR(32) NOT NULL UNIQUE,
  publish_year INT NOT NULL CHECK (publish_year BETWEEN 1500 AND 2100),
  language VARCHAR(60) NOT NULL,
  publisher VARCHAR(180) NOT NULL DEFAULT '',
  shelf_code VARCHAR(60) NOT NULL DEFAULT '',
  description TEXT NOT NULL DEFAULT '',
  replacement_cost NUMERIC(10, 2) NOT NULL DEFAULT 0,
  cover_image TEXT NOT NULL DEFAULT '',
  last_copy_number INT NOT NULL DEFAULT 0,
  is_archived BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE books ADD COLUMN IF NOT EXISTS cover_image TEXT NOT NULL DEFAULT '';
ALTER TABLE books ADD COLUMN IF NOT EXISTS last_copy_number INT NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS book_copies (
  id SERIAL PRIMARY KEY,
  book_id INT NOT NULL REFERENCES books(id) ON DELETE CASCADE,
  inventory_code VARCHAR(80) NOT NULL UNIQUE,
  acquisition_date DATE NOT NULL DEFAULT CURRENT_DATE,
  price NUMERIC(10, 2) NOT NULL DEFAULT 0,
  condition_rating INT NOT NULL CHECK (condition_rating BETWEEN 1 AND 5),
  aging_coefficient NUMERIC(4, 2) NOT NULL DEFAULT 0,
  status VARCHAR(30) NOT NULL CHECK (
    status IN ('available', 'on_loan', 'damaged', 'written_off', 'lost', 'replaced')
  ),
  notes TEXT NOT NULL DEFAULT '',
  replaced_by_copy_id INT REFERENCES book_copies(id) ON DELETE SET NULL,
  written_off_reason TEXT,
  last_inventory_date DATE NOT NULL DEFAULT CURRENT_DATE
);

CREATE TABLE IF NOT EXISTS patrons (
  id SERIAL PRIMARY KEY,
  full_name VARCHAR(255) NOT NULL,
  card_number VARCHAR(50) NOT NULL UNIQUE,
  phone VARCHAR(40) NOT NULL DEFAULT '',
  email VARCHAR(120) NOT NULL DEFAULT '',
  address TEXT NOT NULL DEFAULT '',
  membership_type VARCHAR(80) NOT NULL DEFAULT 'РћР±С‰РёР№',
  status VARCHAR(20) NOT NULL CHECK (status IN ('active', 'blocked')) DEFAULT 'active',
  app_username VARCHAR(60) NOT NULL DEFAULT '',
  is_archived BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS app_users (
  id SERIAL PRIMARY KEY,
  username VARCHAR(60) NOT NULL UNIQUE,
  email VARCHAR(120) NOT NULL DEFAULT '',
  full_name VARCHAR(255) NOT NULL,
  role VARCHAR(20) NOT NULL CHECK (role IN ('reader', 'librarian', 'admin', 'borrower', 'manager')),
  password_hash TEXT NOT NULL,
  patron_id INT REFERENCES patrons(id) ON DELETE SET NULL,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE app_users ADD COLUMN IF NOT EXISTS email VARCHAR(120) NOT NULL DEFAULT '';
UPDATE app_users SET email = username WHERE email = '';
CREATE UNIQUE INDEX IF NOT EXISTS app_users_email_unique ON app_users (LOWER(email));

CREATE TABLE IF NOT EXISTS loans (
  id SERIAL PRIMARY KEY,
  copy_id INT NOT NULL REFERENCES book_copies(id) ON DELETE RESTRICT,
  patron_id INT NOT NULL REFERENCES patrons(id) ON DELETE RESTRICT,
  issued_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  due_at DATE NOT NULL,
  returned_at TIMESTAMP,
  status VARCHAR(20) NOT NULL CHECK (
    status IN ('active', 'renewed', 'overdue', 'returned', 'lost')
  ),
  renewal_count INT NOT NULL DEFAULT 0,
  issued_by VARCHAR(120) NOT NULL DEFAULT 'РњРµРЅРµРґР¶РµСЂ',
  received_by VARCHAR(120),
  notes TEXT NOT NULL DEFAULT ''
);


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


CREATE TABLE IF NOT EXISTS book_transactions (
  id SERIAL PRIMARY KEY,
  book_id INT REFERENCES books(id) ON DELETE SET NULL,
  copy_id INT REFERENCES book_copies(id) ON DELETE SET NULL,
  patron_id INT REFERENCES patrons(id) ON DELETE SET NULL,
  loan_id INT REFERENCES loans(id) ON DELETE SET NULL,
  operation_type VARCHAR(40) NOT NULL,
  operation_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  quantity INT NOT NULL DEFAULT 1,
  details TEXT NOT NULL DEFAULT '',
  actor_name VARCHAR(120) NOT NULL DEFAULT 'РЎРёСЃС‚РµРјР°'
);

CREATE TABLE IF NOT EXISTS system_settings (
  key VARCHAR(80) PRIMARY KEY,
  value TEXT NOT NULL DEFAULT '',
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO system_settings (key, value)
VALUES
  ('max_loan_days', '14'),
  ('fine_policy', ''),
  ('library_contact_email', 'admin@example.com'),
  ('library_contact_phone', '')
ON CONFLICT (key) DO NOTHING;

CREATE TABLE IF NOT EXISTS password_reset_tokens (
  id SERIAL PRIMARY KEY,
  user_id INT NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
  token_hash VARCHAR(128) NOT NULL,
  expires_at TIMESTAMP NOT NULL,
  used_at TIMESTAMP,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS support_messages (
  id SERIAL PRIMARY KEY,
  user_id INT REFERENCES app_users(id) ON DELETE SET NULL,
  sender_name VARCHAR(120) NOT NULL DEFAULT '',
  sender_email VARCHAR(200) NOT NULL DEFAULT '',
  subject VARCHAR(200) NOT NULL DEFAULT '',
  body TEXT NOT NULL DEFAULT '',
  status VARCHAR(20) NOT NULL DEFAULT 'open',
  admin_reply TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);


