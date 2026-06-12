-- ============================================================================
-- Sample business database for Data Governance + lineage testing.
-- Source tables live in schema "shop"; ETL outputs in schema "analytics".
-- Run against a SEPARATE database (sample_shop):
--   docker exec -i <pg> psql -U user -c "CREATE DATABASE sample_shop;"
--   Get-Content sample_data.sql | docker exec -i <pg> psql -U user -d sample_shop
-- ============================================================================

DROP SCHEMA IF EXISTS shop CASCADE;
DROP SCHEMA IF EXISTS analytics CASCADE;
CREATE SCHEMA shop;
CREATE SCHEMA analytics;

-- ---- source tables (schema: shop) -----------------------------------------
CREATE TABLE shop.customers (
    id          SERIAL PRIMARY KEY,
    first_name  VARCHAR(80),
    last_name   VARCHAR(80),
    email       VARCHAR(160),
    phone       VARCHAR(40),
    ssn         VARCHAR(20),
    ip_address  VARCHAR(40),
    city        VARCHAR(80),
    country     VARCHAR(80),
    signup_date DATE
);
CREATE TABLE shop.products (
    id        SERIAL PRIMARY KEY,
    name      VARCHAR(120) NOT NULL,
    category  VARCHAR(80),
    price     NUMERIC(10,2)
);
CREATE TABLE shop.orders (
    id           SERIAL PRIMARY KEY,
    customer_id  INTEGER REFERENCES shop.customers(id),
    order_date   DATE,
    status       VARCHAR(30),
    total_amount NUMERIC(10,2)
);
CREATE TABLE shop.order_items (
    id          SERIAL PRIMARY KEY,
    order_id    INTEGER REFERENCES shop.orders(id),
    product_id  INTEGER REFERENCES shop.products(id),
    quantity    INTEGER,
    unit_price  NUMERIC(10,2)
);
CREATE TABLE shop.payments (
    id          SERIAL PRIMARY KEY,
    order_id    INTEGER REFERENCES shop.orders(id),
    card_number VARCHAR(32),
    amount      NUMERIC(10,2),
    paid_at     TIMESTAMP
);

-- ---- analytics target tables (ETL outputs, for column lineage) -------------
CREATE TABLE analytics.customer_revenue    (customer_id INT, country VARCHAR(80), revenue NUMERIC(12,2), order_count INT);
CREATE TABLE analytics.daily_sales         (order_date DATE, total_revenue NUMERIC(12,2), num_orders INT);
CREATE TABLE analytics.product_performance (product_id INT, name VARCHAR(120), category VARCHAR(80), units_sold INT, gross_sales NUMERIC(12,2));
CREATE TABLE analytics.payment_summary     (order_id INT, order_total NUMERIC(12,2), paid_total NUMERIC(12,2));
CREATE TABLE analytics.customer_360        (customer_id INT, email VARCHAR(160), country VARCHAR(80), orders INT, lifetime_value NUMERIC(12,2));

-- ============================ DATA ==========================================

INSERT INTO shop.customers (first_name, last_name, email, phone, ssn, ip_address, city, country, signup_date)
SELECT
  (ARRAY['John','Mary','David','Sarah','Michael','Priya','Wei','Aisha','Carlos','Emma'])[1+(g%10)],
  (ARRAY['Smith','Johnson','Lee','Patel','Garcia','Khan','Brown','Nguyen','Muller','Rossi'])[1+(g%10)],
  'user' || g || '@example.com',
  '415-555-' || lpad((1000+(g%9000))::text,4,'0'),
  lpad((100+(g%800))::text,3,'0') || '-' || lpad((10+(g%89))::text,2,'0') || '-' || lpad((1000+(g%9000))::text,4,'0'),
  '192.168.' || (g%255) || '.' || ((g*7)%255),
  (ARRAY['London','Mumbai','New York','Berlin','Toronto','Singapore','Dubai','Madrid','Sydney','Tokyo'])[1+(g%10)],
  (ARRAY['UK','India','USA','Germany','Canada','Singapore','UAE','Spain','Australia','Japan'])[1+(g%10)],
  DATE '2023-01-01' + (g%700)
FROM generate_series(1,200) AS g;
UPDATE shop.customers SET email = NULL WHERE id % 17 = 0;
UPDATE shop.customers SET email = 'dupe@example.com' WHERE id IN (3,33,63,93);

INSERT INTO shop.products (name, category, price)
SELECT 'Product ' || g, (ARRAY['Electronics','Books','Home','Toys','Apparel'])[1+(g%5)], round((10+(g%490))::numeric,2)
FROM generate_series(1,50) AS g;

INSERT INTO shop.orders (customer_id, order_date, status, total_amount)
SELECT 1+(g%200), DATE '2024-01-01' + (g%400),
       (ARRAY['paid','pending','shipped','cancelled','refunded'])[1+(g%5)], round((20+(g%980))::numeric,2)
FROM generate_series(1,600) AS g;
UPDATE shop.orders SET total_amount = -25.00 WHERE id % 23 = 0;
UPDATE shop.orders SET status = NULL WHERE id % 19 = 0;

INSERT INTO shop.order_items (order_id, product_id, quantity, unit_price)
SELECT 1+(g%600), 1+(g%50), 1+(g%5), round((10+(g%200))::numeric,2)
FROM generate_series(1,1500) AS g;

INSERT INTO shop.payments (order_id, card_number, amount, paid_at)
SELECT 1+(g%600), '4111111111111111', round((20+(g%980))::numeric,2),
       TIMESTAMP '2024-01-01 00:00:00' + (g%400) * INTERVAL '1 day'
FROM generate_series(1,400) AS g;

ANALYZE;

SELECT 'shop.customers' AS table, count(*) FROM shop.customers
UNION ALL SELECT 'shop.products', count(*) FROM shop.products
UNION ALL SELECT 'shop.orders', count(*) FROM shop.orders
UNION ALL SELECT 'shop.order_items', count(*) FROM shop.order_items
UNION ALL SELECT 'shop.payments', count(*) FROM shop.payments;
