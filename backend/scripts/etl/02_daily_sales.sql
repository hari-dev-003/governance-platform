-- Daily sales rollup (source: orders -> target: daily_sales)
INSERT INTO analytics.daily_sales (order_date, total_revenue, num_orders)
SELECT order_date, SUM(total_amount), COUNT(*)
FROM shop.orders
WHERE status IN ('paid','shipped')
GROUP BY order_date;
