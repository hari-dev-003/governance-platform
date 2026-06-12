-- ============================================================================
-- Single ETL pipeline: shop.* -> analytics.*  (parsed by sqlglot for lineage)
-- Put this file in a repo, connect it as an `etl_repo`/`github` source, Scan,
-- then Rebuild Lineage. Produces table + column lineage with no execution.
-- ============================================================================

INSERT INTO analytics.customer_revenue (customer_id, country, revenue, order_count)
SELECT c.id, c.country, SUM(o.total_amount), COUNT(o.id)
FROM shop.orders o
JOIN shop.customers c ON c.id = o.customer_id
WHERE o.status = 'paid'
GROUP BY c.id, c.country;

INSERT INTO analytics.daily_sales (order_date, total_revenue, num_orders)
SELECT order_date, SUM(total_amount), COUNT(*)
FROM shop.orders
WHERE status IN ('paid', 'shipped')
GROUP BY order_date;

INSERT INTO analytics.product_performance (product_id, name, category, units_sold, gross_sales)
SELECT p.id, p.name, p.category, SUM(oi.quantity), SUM(oi.quantity * oi.unit_price)
FROM shop.order_items oi
JOIN shop.products p ON p.id = oi.product_id
GROUP BY p.id, p.name, p.category;

INSERT INTO analytics.payment_summary (order_id, order_total, paid_total)
SELECT o.id, o.total_amount, SUM(pm.amount)
FROM shop.payments pm
JOIN shop.orders o ON o.id = pm.order_id
GROUP BY o.id, o.total_amount;

INSERT INTO analytics.customer_360 (customer_id, email, country, orders, lifetime_value)
SELECT c.id, c.email, c.country, COUNT(o.id), SUM(o.total_amount)
FROM shop.customers c
LEFT JOIN shop.orders o ON o.customer_id = c.id
GROUP BY c.id, c.email, c.country;
