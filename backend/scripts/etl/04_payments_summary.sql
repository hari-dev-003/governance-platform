-- Payment reconciliation (sources: payments, orders -> target: payment_summary)
INSERT INTO analytics.payment_summary (order_id, order_total, paid_total)
SELECT o.id, o.total_amount, SUM(pm.amount)
FROM shop.orders o
JOIN shop.payments pm ON pm.order_id = o.id
GROUP BY o.id, o.total_amount;
