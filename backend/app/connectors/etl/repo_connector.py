"""ETL Repository connector - cross-connector lineage from a code repository.

Supports three repository sources (config 'repo_kind'):
  - "git"    : clone any Git URL (GitHub/GitLab/Bitbucket/self-hosted) via gitpython
  - "github" : GitHub REST API (no clone) - needs github_token + repo_name
  - "local"  : read scripts from a local folder path

Every .sql/.py file is parsed (sqlglot / dbt / Airflow) into source->target lineage,
which the lineage resolver maps to catalog assets from ANY connector.
"""
from __future__ import annotations

import os
import tempfile
from typing import List, Optional

from app.connectors.base import BaseConnector, ConnectionTestResult, DiscoveredAsset
from app.connectors.etl.parsers import analyze_file

_EXTS = (".sql", ".py")


class EtlRepoConnector(BaseConnector):
    def _kind(self) -> str:
        return self.config.get("repo_kind", "git")

    # ---- connectivity -------------------------------------------------
    async def test_connection(self) -> ConnectionTestResult:
        kind = self._kind()
        try:
            if kind == "local":
                path = self.config["local_path"]
                if not os.path.isdir(path):
                    return ConnectionTestResult(success=False, message=f"path not found: {path}")
                return ConnectionTestResult(success=True, message=f"Local repo OK: {path}")
            if kind == "github":
                from github import Github
                repo = Github(self.config["github_token"]).get_repo(self.config["repo_name"])
                return ConnectionTestResult(success=True, message=f"Connected to {repo.full_name}",
                                            details={"default_branch": repo.default_branch})
            # git
            from git import cmd
            url = self._git_url()
            cmd.Git().ls_remote(url)
            return ConnectionTestResult(success=True, message="Git repository reachable")
        except Exception as e:  # noqa: BLE001
            return ConnectionTestResult(success=False, message=str(e))

    def _git_url(self) -> str:
        url = self.config["git_url"]
        token = self.config.get("auth_token")
        if token and url.startswith("https://") and "@" not in url.split("//", 1)[1]:
            url = "https://" + token + "@" + url.split("//", 1)[1]
        return url

    # ---- discovery ----------------------------------------------------
    async def discover(self) -> List[DiscoveredAsset]:
        kind = self._kind()
        if kind == "github":
            return await self._discover_github()
        root, cleanup = self._materialize(kind)
        try:
            return self._scan_dir(root, repo_label=self.config.get("name_label", os.path.basename(root)))
        finally:
            if cleanup:
                import shutil
                shutil.rmtree(root, ignore_errors=True)

    def _materialize(self, kind: str):
        subpath = self.config.get("subpath", "").strip("/")
        if kind == "local":
            base = self.config["local_path"]
            return (os.path.join(base, subpath) if subpath else base), False
        # git clone (shallow)
        import git
        tmp = tempfile.mkdtemp(prefix="etlrepo_")
        git.Repo.clone_from(self._git_url(), tmp, depth=1,
                            branch=self.config.get("branch") or None)
        return (os.path.join(tmp, subpath) if subpath else tmp), True

    def _scan_dir(self, root: str, repo_label: str) -> List[DiscoveredAsset]:
        assets: List[DiscoveredAsset] = []
        for dirpath, _dirs, files in os.walk(root):
            if ".git" in dirpath.split(os.sep):
                continue
            for fn in files:
                if not fn.endswith(_EXTS):
                    continue
                full = os.path.join(dirpath, fn)
                rel = os.path.relpath(full, root).replace(os.sep, "/")
                try:
                    content = open(full, "r", encoding="utf-8", errors="ignore").read()
                except Exception:  # noqa: BLE001
                    continue
                meta, raw = analyze_file(rel, content)
                assets.append(DiscoveredAsset(
                    external_id=f"repo://{repo_label}/{rel}", name=fn,
                    asset_type="etl_pipeline", parent_id=f"repo://{repo_label}",
                    metadata=meta, raw_lineage=raw or None))
        return assets

    async def _discover_github(self) -> List[DiscoveredAsset]:
        from github import Github
        repo = Github(self.config["github_token"]).get_repo(self.config["repo_name"])
        branch = self.config.get("branch") or repo.default_branch
        stack = repo.get_contents(self.config.get("subpath", "") or self.config.get("path", ""), ref=branch)
        files, assets = [], []
        while stack:
            c = stack.pop(0)
            if c.type == "dir":
                stack.extend(repo.get_contents(c.path, ref=branch))
            elif c.path.endswith(_EXTS):
                files.append(c)
        for f in files:
            try:
                content = f.decoded_content.decode("utf-8", "ignore")
            except Exception:  # noqa: BLE001
                continue
            meta, raw = analyze_file(f.path, content)
            meta["html_url"] = f.html_url
            assets.append(DiscoveredAsset(
                external_id=f"repo://{self.config['repo_name']}/{f.path}", name=f.path.split("/")[-1],
                asset_type="etl_pipeline", parent_id=f"repo://{self.config['repo_name']}",
                metadata=meta, raw_lineage=raw or None))
        return assets

    async def get_asset_details(self, external_id: str) -> Optional[DiscoveredAsset]:
        return None
