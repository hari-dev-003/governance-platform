"""Python ETL building analytics.customer_360 (parsed for lineage only)."""
import psycopg2

BUILD_SQL = """
    CREATE TABLE analytics.customer_360 AS
    SELECT c.id AS customer_id, c.email, c.country,
           COUNT(o.id) AS orders, SUM(o.total_amount) AS lifetime_value
    FROM shop.customers c
    LEFT JOIN shop.orders o ON o.customer_id = c.id
    GROUP BY c.id, c.email, c.country;
"""

def run():
    conn = psycopg2.connect(dbname="sample_shop")
    with conn.cursor() as cur:
        cur.execute(BUILD_SQL)
    conn.commit()

if __name__ == "__main__":
    run()
