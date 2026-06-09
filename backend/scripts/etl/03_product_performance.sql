-- Product performance from line items (sources: order_items, products -> target: product_performance)
CREATE TABLE analytics.product_performance AS
SELECT p.id AS product_id, p.name, p.category,
       SUM(oi.quantity) AS units_sold, SUM(oi.quantity * oi.unit_price) AS gross_sales
FROM shop.order_items oi
JOIN shop.products p ON p.id = oi.product_id
GROUP BY p.id, p.name, p.category;
