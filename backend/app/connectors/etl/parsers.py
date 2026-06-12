"""Shared ETL-script parsers used by every repository connector.

Turns a single script file into (metadata, raw_lineage), where raw_lineage is a list of
{"sources": [...], "targets": [...], "transformation_file": path} edges. References are
left as-written (e.g. 'shop.orders', 'project.dataset.table'); the lineage resolver maps
them to catalog assets across all connectors.
"""
from __future__ import annotations

import ast
import re
from typing import Dict, List, Tuple

import sqlglot


def extract_sql_lineage(sql: str, file_path: str) -> List[dict]:
    edges: List[dict] = []
    try:
        for stmt in sqlglot.parse(sql, error_level=sqlglot.ErrorLevel.IGNORE):
            if stmt is None:
                continue
            kind = type(stmt).__name__
            if kind in ("Insert", "Create", "Merge"):
                targets, sources = [], []
                if getattr(stmt, "this", None) is not None:
                    # target table name (strip alias/expressions)
                    for tbl in stmt.this.find_all(sqlglot.exp.Table) if hasattr(stmt.this, "find_all") else []:
                        targets.append(_qualified(tbl))
                    if not targets:
                        targets.append(str(stmt.this).split(" ")[0])
                # sources = all tables referenced minus the target
                all_tables = [_qualified(t) for t in stmt.find_all(sqlglot.exp.Table)]
                sources = [t for t in all_tables if t not in targets]
                if sources or targets:
                    edges.append({"sources": sources, "targets": targets,
                                  "transformation_file": file_path, "statement_type": kind})
    except Exception:  # noqa: BLE001
        pass
    return edges


def extract_column_lineage(sql: str, file_path: str) -> List[dict]:
    """Per-projection column lineage: target_column <- source_column(s)."""
    from sqlglot import exp
    edges: List[dict] = []
    try:
        statements = sqlglot.parse(sql, error_level=sqlglot.ErrorLevel.IGNORE)
    except Exception:  # noqa: BLE001
        return edges
    for stmt in statements:
        if stmt is None:
            continue
        select = stmt.find(exp.Select)
        if select is None:
            continue
        # resolve target table + explicit target columns
        target_table, target_cols = None, []
        this = getattr(stmt, "this", None)
        if isinstance(this, exp.Schema):
            target_table = this.this.name if this.this else None
            target_cols = [c.name for c in this.expressions if hasattr(c, "name")]
        elif isinstance(this, exp.Table):
            target_table = this.name
        elif this is not None:
            target_table = getattr(this, "name", None)
        if not target_table:
            continue
        # alias -> real table
        alias_map = {}
        for t in select.find_all(exp.Table):
            alias_map[t.alias_or_name] = t.name
        for i, proj in enumerate(select.expressions):
            if i < len(target_cols):
                out_col = target_cols[i]
            elif isinstance(proj, exp.Alias):
                out_col = proj.alias
            elif isinstance(proj, exp.Column):
                out_col = proj.name
            else:
                out_col = proj.alias_or_name or None
            if not out_col:
                continue
            for cn in proj.find_all(exp.Column):
                src_tbl = alias_map.get(cn.table, cn.table) or None
                # unqualified column in a single-source query -> attribute to that table
                if not src_tbl and len(alias_map) == 1:
                    src_tbl = next(iter(alias_map.values()))
                src_col = cn.name
                if not src_col:
                    continue
                edges.append({
                    "source_table": src_tbl, "source_column": src_col,
                    "target_table": target_table, "target_column": out_col,
                    "transformation_file": file_path})
    return edges


def _qualified(table: "sqlglot.exp.Table") -> str:
    parts = [p.name for p in (table.args.get("catalog"), table.args.get("db"), table.this) if p]
    return ".".join(parts) if parts else table.name


def parse_dbt(content: str, model_name: str, file_path: str) -> Tuple[dict, List[dict]]:
    refs = re.findall(r"ref\(\s*['\"](\w+)['\"]\s*\)", content)
    sources = re.findall(r"source\(\s*['\"](\w+)['\"]\s*,\s*['\"](\w+)['\"]\s*\)", content)
    src_names = refs + [f"{s[0]}.{s[1]}" for s in sources]
    meta = {"etl_type": "dbt_model", "model_name": model_name,
            "depends_on_refs": refs, "depends_on_sources": [f"{s[0]}.{s[1]}" for s in sources]}
    raw = [{"sources": src_names, "targets": [model_name], "transformation_file": file_path}] if src_names else []
    return meta, raw


def parse_airflow(content: str, file_path: str) -> Tuple[dict, List[dict]]:
    tasks, deps = [], []
    try:
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
                fn = ""
                if isinstance(node.value.func, ast.Attribute):
                    fn = node.value.func.attr
                elif isinstance(node.value.func, ast.Name):
                    fn = node.value.func.id
                if "Operator" in fn or "Task" in fn:
                    for tgt in node.targets:
                        if isinstance(tgt, ast.Name):
                            tasks.append(tgt.id)
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.RShift):
                deps.append({"from": ast.unparse(node.left), "to": ast.unparse(node.right)})
    except Exception:  # noqa: BLE001
        pass
    # also pull any embedded SQL strings for table-level lineage
    raw = []
    for m in re.findall(r'"""(.*?)"""|\'\'\'(.*?)\'\'\'', content, re.S):
        sql = m[0] or m[1]
        if re.search(r"\b(insert|create|select)\b", sql, re.I):
            raw.extend(extract_sql_lineage(sql, file_path))
    return {"etl_type": "airflow_dag", "tasks": tasks, "dependencies": deps}, raw


# ===========================================================================
# Static code analyzer for Spark / PySpark / pandas / Airflow-Python ETL.
# Tracks DataFrame variable provenance so each written dataset binds to the
# real source datasets it was derived from (table-level "inferred" lineage).
# Handles: JDBC reads/writes (.option("dbtable",...), .jdbc()), file I/O
# (.parquet/.csv/.json/.load/.save), pandas (read_parquet/to_parquet, ...),
# saveAsTable/insertInto, and read_*/write_*/save_* helper functions.
# ===========================================================================
_READ_ATTRS = {"parquet", "csv", "json", "orc", "text", "load", "table",
               "read_parquet", "read_csv", "read_json"}
_WRITE_ATTRS = {"to_parquet", "to_csv", "to_json", "saveastable", "insertinto"}


def _const_str(node):
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _root_name(node):
    while node is not None:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            node = node.value
        elif isinstance(node, ast.Call):
            node = node.func
        elif isinstance(node, ast.Subscript):
            node = node.value
        else:
            return None
    return None


def _string_datasets(expr) -> set:
    """All dataset string literals referenced in expr (tables, file paths)."""
    out = set()
    for n in ast.walk(expr):
        if not isinstance(n, ast.Call):
            continue
        f = n.func
        if isinstance(f, ast.Attribute):
            a = f.attr
            al = a.lower()
            if a == "option" and len(n.args) >= 2:
                if _const_str(n.args[0]) == "dbtable" and _const_str(n.args[1]):
                    out.add(_const_str(n.args[1]))
            elif a == "jdbc" and len(n.args) >= 2 and _const_str(n.args[1]):
                out.add(_const_str(n.args[1]))            # 2nd arg is the table
            elif a in _READ_ATTRS or al in _WRITE_ATTRS:
                for arg in n.args:
                    sv = _const_str(arg)
                    if sv:
                        out.add(sv)
                        break
        elif isinstance(f, ast.Name) and (f.id.startswith("read_") or f.id.startswith("write_") or f.id.startswith("save_")):
            for arg in n.args:
                sv = _const_str(arg)
                if sv:
                    out.add(sv)
                    break
    return out


def _is_write(expr) -> bool:
    for n in ast.walk(expr):
        if isinstance(n, ast.Attribute) and n.attr == "write":
            return True
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Attribute) and f.attr.lower() in _WRITE_ATTRS:
                return True
            if isinstance(f, ast.Name) and (f.id.startswith("write_") or f.id.startswith("save_")):
                return True
    return False


def _iter_stmts(node):
    for body_attr in ("body", "orelse", "finalbody"):
        for child in getattr(node, body_attr, []) or []:
            yield child
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.For, ast.While,
                                  ast.If, ast.With, ast.Try)):
                yield from _iter_stmts(child)


def extract_spark_lineage(content: str, file_path: str) -> list:
    edges = []
    try:
        tree = ast.parse(content)
    except Exception:  # noqa: BLE001
        return edges
    var_src: dict = {}

    def emit_write(expr):
        targets = _string_datasets(expr)
        srcs = set()
        for n in ast.walk(expr):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and                     (n.func.id.startswith("write_") or n.func.id.startswith("save_")):
                for a in n.args:
                    if isinstance(a, ast.Name) and a.id in var_src:
                        srcs |= var_src[a.id]
        rn = _root_name(expr)
        if rn and rn in var_src:
            srcs |= var_src[rn]
        for t in targets:
            real = sorted(x for x in srcs if x != t)
            if real:
                edges.append({"sources": real, "targets": [t], "transformation_file": file_path})

    for stmt in _iter_stmts(tree):
        if isinstance(stmt, ast.Assign):
            rhs = stmt.value
            if _is_write(rhs):
                emit_write(rhs)
                continue
            ds = _string_datasets(rhs)
            refs = set()
            for n in ast.walk(rhs):
                if isinstance(n, ast.Name) and n.id in var_src:
                    refs |= var_src[n.id]
            srcs = ds | refs
            for t in stmt.targets:
                if isinstance(t, ast.Name):
                    var_src[t.id] = srcs
        elif isinstance(stmt, ast.Expr) and _is_write(stmt.value):
            emit_write(stmt.value)
    return edges


def analyze_file(file_path: str, content: str) -> Tuple[Dict, List[dict]]:
    """Return (metadata, raw_lineage) for one ETL script file."""
    ext = file_path.rsplit(".", 1)[-1].lower()
    meta: Dict = {"file_path": file_path}
    raw: List[dict] = []
    if ext == "sql":
        if "ref(" in content or "source(" in content:
            model = file_path.rsplit("/", 1)[-1].replace(".sql", "")
            m, raw = parse_dbt(content, model, file_path)
            meta.update(m)
        else:
            meta["etl_type"] = "sql_script"
            raw = extract_sql_lineage(content, file_path)
            meta["column_lineage_edges"] = extract_column_lineage(content, file_path)
    elif ext == "py":
        if "from airflow" in content or "DAG(" in content:
            m, raw = parse_airflow(content, file_path)
            meta.update(m)
        else:
            meta["etl_type"] = "python_script"
            # pull embedded SQL strings (e.g. Spark .sql("..."))
            for m in re.findall(r'"""(.*?)"""|\'\'\'(.*?)\'\'\'|"(.*?)"', content, re.S):
                sql = next((x for x in m if x), "")
                if re.search(r"\b(insert into|create table|merge into)\b", sql, re.I):
                    raw.extend(extract_sql_lineage(sql, file_path))
        # static Spark/pandas/file-IO code analysis (DataFrame API, parquet, JDBC)
        spark_edges = extract_spark_lineage(content, file_path)
        if spark_edges:
            raw = (raw or []) + spark_edges
            if meta.get("etl_type") == "python_script":
                meta["etl_type"] = "spark_job"
    else:
        meta["etl_type"] = "unknown"
    if "column_lineage_edges" not in meta:
        # derive column lineage from any embedded SQL we already pulled
        col_edges = []
        if ext == "py":
            import re as _re
            for m in _re.findall(r'"""(.*?)"""|\'\'\'(.*?)\'\'\'', content, _re.S):
                sqltxt = m[0] or m[1]
                if _re.search(r"\b(insert|create|merge)\b", sqltxt, _re.I):
                    col_edges.extend(extract_column_lineage(sqltxt, file_path))
        meta["column_lineage_edges"] = col_edges
    meta["lineage_edges"] = raw          # persisted so rebuild can re-resolve later
    return meta, raw
