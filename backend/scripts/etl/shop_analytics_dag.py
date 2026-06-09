"""Airflow DAG documenting the shop -> analytics ETL (parsed for lineage only)."""
from airflow import DAG
from airflow.providers.postgres.operators.postgres import PostgresOperator
from datetime import datetime

with DAG("shop_analytics", start_date=datetime(2024, 1, 1), schedule_interval="@daily") as dag:

    customer_revenue = PostgresOperator(
        task_id="build_customer_revenue",
        sql="""
            INSERT INTO analytics.customer_revenue (customer_id, country, revenue, order_count)
            SELECT c.id, c.country, SUM(o.total_amount), COUNT(o.id)
            FROM shop.orders o
            JOIN shop.customers c ON c.id = o.customer_id
            WHERE o.status = 'paid'
            GROUP BY c.id, c.country;
        """,
    )

    product_performance = PostgresOperator(
        task_id="build_product_performance",
        sql="""
            INSERT INTO analytics.product_performance (product_id, name, category, units_sold, gross_sales)
            SELECT p.id, p.name, p.category, SUM(oi.quantity), SUM(oi.quantity * oi.unit_price)
            FROM shop.order_items oi
            JOIN shop.products p ON p.id = oi.product_id
            GROUP BY p.id, p.name, p.category;
        """,
    )

    payment_summary = PostgresOperator(
        task_id="build_payment_summary",
        sql="""
            INSERT INTO analytics.payment_summary (order_id, order_total, paid_total)
            SELECT o.id, o.total_amount, SUM(pm.amount)
            FROM shop.payments pm
            JOIN shop.orders o ON o.id = pm.order_id
            GROUP BY o.id, o.total_amount;
        """,
    )

    [customer_revenue, product_performance] >> payment_summary
