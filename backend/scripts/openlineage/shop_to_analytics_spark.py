"""
Spark ETL (your style: spark.read.format("jdbc").option(...)) — shop.* -> analytics.*

Self-contained: OpenLineage + Postgres JDBC are auto-fetched, and OpenLineage is wired to
your platform inside the SparkSession, so just run:

    source ~/sparkenv/bin/activate          # the venv with pyspark
    python shop_to_analytics_spark.py

Lineage (table + column) is emitted ONLY to your platform.
"""
import os

# --- Java 17 module access for Spark/OpenLineage (must be set BEFORE the JVM starts).
#     Harmless on Java 11. ---
os.environ.setdefault("JAVA_TOOL_OPTIONS",
    "--add-opens=java.base/java.lang=ALL-UNNAMED "
    "--add-opens=java.base/java.lang.invoke=ALL-UNNAMED "
    "--add-opens=java.base/java.io=ALL-UNNAMED "
    "--add-opens=java.base/java.net=ALL-UNNAMED "
    "--add-opens=java.base/java.nio=ALL-UNNAMED "
    "--add-opens=java.base/java.util=ALL-UNNAMED "
    "--add-opens=java.base/java.util.concurrent=ALL-UNNAMED "
    "--add-opens=java.base/sun.nio.ch=ALL-UNNAMED "
    "--add-opens=java.base/sun.security.action=ALL-UNNAMED "
    "--add-opens=java.base/java.security=ALL-UNNAMED")

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, sum as _sum, count, lit

# ---------------- config (env overrides; edit defaults if you like) ----------------
PLATFORM_API = os.environ.get("PLATFORM_API", "http://localhost:8000/api/v1")  # reachable from Spark's host
OL_API_KEY   = os.environ.get("OL_API_KEY", "my-secret-key")                   # = OPENLINEAGE_API_KEY in backend/.env
JDBC_URL     = os.environ.get("JDBC_URL", "jdbc:postgresql://localhost:5432/sample_shop")
DB_USER      = os.environ.get("DB_USER", "user")
DB_PASSWORD  = os.environ.get("DB_PASSWORD", "admin123")
# -----------------------------------------------------------------------------------

# 1. Spark session — JDBC driver + OpenLineage listener pointed at your platform
spark = (
    SparkSession.builder
    .appName("DatabaseETLJob")
    .config("spark.jars.packages",
            "io.openlineage:openlineage-spark_2.12:1.27.0,org.postgresql:postgresql:42.7.4")
    .config("spark.extraListeners", "io.openlineage.spark.agent.OpenLineageSparkListener")
    .config("spark.openlineage.transport.type", "http")
    .config("spark.openlineage.transport.url", PLATFORM_API)
    .config("spark.openlineage.transport.endpoint", "/lineage/openlineage")
    .config("spark.openlineage.transport.auth.type", "api_key")
    .config("spark.openlineage.transport.auth.apiKey", OL_API_KEY)
    .config("spark.openlineage.namespace", "postgres://localhost:5432")
    .getOrCreate()
)


def read_table(dbtable):
    return (spark.read.format("jdbc")
            .option("url", JDBC_URL)
            .option("dbtable", dbtable)
            .option("user", DB_USER)
            .option("password", DB_PASSWORD)
            .option("driver", "org.postgresql.Driver")
            .load())


def write_table(df, dbtable):
    (df.write.format("jdbc")
       .option("url", JDBC_URL)
       .option("dbtable", dbtable)
       .option("user", DB_USER)
       .option("password", DB_PASSWORD)
       .option("driver", "org.postgresql.Driver")
       .option("truncate", "true")
       .mode("overwrite")
       .save())


# 2. Read source tables
customers = read_table("shop.customers")
orders    = read_table("shop.orders")
products  = read_table("shop.products")
items     = read_table("shop.order_items")
payments  = read_table("shop.payments")

# 3. Transformations + 4. Write back (each write emits lineage for that output)

# analytics.customer_revenue  <- orders, customers
cust_orders = customers.join(orders, customers.id == orders.customer_id)
customer_revenue = (cust_orders.filter(col("status") == "paid")
                    .groupBy(customers.id.alias("customer_id"), customers.country)
                    .agg(_sum(orders.total_amount).alias("revenue"),
                         count(orders.id).alias("order_count")))
write_table(customer_revenue, "analytics.customer_revenue")

# analytics.daily_sales  <- orders
daily_sales = (orders.filter(col("status").isin("paid", "shipped"))
               .groupBy(orders.order_date)
               .agg(_sum(orders.total_amount).alias("total_revenue"),
                    count(lit(1)).alias("num_orders")))
write_table(daily_sales, "analytics.daily_sales")

# analytics.product_performance  <- order_items, products
items_products = items.join(products, items.product_id == products.id)
product_performance = (items_products
                       .groupBy(products.id.alias("product_id"), products.name, products.category)
                       .agg(_sum(items.quantity).alias("units_sold"),
                            _sum(items.quantity * items.unit_price).alias("gross_sales")))
write_table(product_performance, "analytics.product_performance")

# analytics.payment_summary  <- payments, orders
pay_orders = payments.join(orders, payments.order_id == orders.id)
payment_summary = (pay_orders
                   .groupBy(orders.id.alias("order_id"), orders.total_amount.alias("order_total"))
                   .agg(_sum(payments.amount).alias("paid_total")))
write_table(payment_summary, "analytics.payment_summary")

# analytics.customer_360  <- customers, orders
cust_orders_left = customers.join(orders, orders.customer_id == customers.id, "left")
customer_360 = (cust_orders_left
                .groupBy(customers.id.alias("customer_id"), customers.email, customers.country)
                .agg(count(orders.id).alias("orders"),
                     _sum(orders.total_amount).alias("lifetime_value")))
write_table(customer_360, "analytics.customer_360")

# 6. Stop
spark.stop()
