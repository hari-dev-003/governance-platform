"""GitHub ETL connector — fetches ETL scripts and extracts lineage.

Uses sqlglot (always available) for SQL lineage and PyGithub (lazy) for repo access.
"""
from __future__ import annotations

import ast
import re
from typing import List, Optional

import sqlglot

from app.connectors.base import BaseConnector, ConnectionTestResult, DiscoveredAsset


class GitHubETLConnector(BaseConnector):
    def _github(self):
        from github import Github
        return Github(self.config["github_token"])

    async def test_connection(self) -> ConnectionTestResult:
        try:
            from github import Github  # noqa
        except ImportError:
            return ConnectionTestResult(success=False, message="PyGithub not installed")
        try:
            repo = self._github().get_repo(self.config["repo_name"])
            return ConnectionTestResult(success=True, message=f"Connected to {repo.full_name}",
                                        details={"default_branch": repo.default_branch})
        except Exception as e:  # noqa: BLE001
            return ConnectionTestResult(success=False, message=str(e))

    @staticmethod
    def extract_sql_lineage(sql: str, file_path: str) -> list:
        edges = []
        try:
            for stmt in sqlglot.parse(sql, error_level=sqlglot.ErrorLevel.IGNORE):
                if stmt is None:
                    continue
                kind = type(stmt).__name__
                if kind in ("Insert", "Create"):
                    targets = [str(stmt.this)] if getattr(stmt, "this", None) is not None else []
                    sources = [t.name for t in stmt.find_all(sqlglot.exp.Table)]
                    if sources or targets:
                        edges.append({"sources": sources, "targets": targets,
                                      "transformation_file": file_path, "statement_type": kind})
        except Exception:  # noqa: BLE001
            pass
        return edges

    @staticmethod
    def parse_airflow_dag(content: str, file_path: str) -> dict:
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
        return {"dag_file": file_path, "tasks": tasks, "dependencies": deps}

    async def discover(self) -> List[DiscoveredAsset]:
        g = self._github()
        repo = g.get_repo(self.config["repo_name"])
        branch = self.config.get("branch") or repo.default_branch
        contents = repo.get_contents(self.config.get("path", ""), ref=branch)
        files, assets = [], []
        while contents:
            fc = contents.pop(0)
            if fc.type == "dir":
                contents.extend(repo.get_contents(fc.path, ref=branch))
            elif fc.path.split(".")[-1].lower() in ("sql", "py"):
                files.append(fc)
        for f in files:
            ext = f.path.split(".")[-1].lower()
            try:
                raw = f.decoded_content.decode("utf-8", "ignore")
            except Exception:  # noqa: BLE001
                continue
            meta = {"file_path": f.path, "sha": f.sha, "html_url": f.html_url}
            lineage = []
            if ext == "sql":
                if "ref(" in raw or "source(" in raw:
                    meta["etl_type"] = "dbt_model"
                    meta["depends_on_refs"] = re.findall(r"ref\(['\"](\w+)['\"]\)", raw)
                else:
                    lineage = self.extract_sql_lineage(raw, f.path)
                    meta["etl_type"] = "sql_script"
            elif "from airflow" in raw or "DAG(" in raw:
                meta.update(self.parse_airflow_dag(raw, f.path))
                meta["etl_type"] = "airflow_dag"
            else:
                meta["etl_type"] = "python_script"
            assets.append(DiscoveredAsset(
                external_id=f"github://{self.config['repo_name']}/{f.path}",
                name=f.path.split("/")[-1], asset_type="etl_pipeline",
                parent_id=f"github://{self.config['repo_name']}", metadata=meta,
                raw_lineage=lineage or None))
        return assets

    async def get_asset_details(self, external_id: str) -> Optional[DiscoveredAsset]:
        return None
