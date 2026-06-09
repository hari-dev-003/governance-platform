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
    else:
        meta["etl_type"] = "unknown"
    meta["lineage_edges"] = raw          # persisted so rebuild can re-resolve later
    return meta, raw
