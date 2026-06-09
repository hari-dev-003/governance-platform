-- Aggregates paid orders per customer (sources: orders, customers -> target: customer_revenue)
CREATE TABLE analytics.customer_revenue AS
SELECT c.id AS customer_id, c.country, SUM(o.total_amount) AS revenue, COUNT(o.id) AS order_count
FROM shop.orders o
JOIN shop.customers c ON c.id = o.customer_id
WHERE o.status = 'paid'
GROUP BY c.id, c.country;
