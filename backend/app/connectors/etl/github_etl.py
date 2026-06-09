"""GitHub ETL connector (kept for back-compat) - delegates to the shared parsers.

New work should prefer the generic 'etl_repo' connector, which also supports cloning any
Git URL or reading a local folder. This connector uses the GitHub REST API.
"""
from __future__ import annotations

from typing import List, Optional

from app.connectors.base import BaseConnector, ConnectionTestResult, DiscoveredAsset
from app.connectors.etl.parsers import analyze_file


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

    async def discover(self) -> List[DiscoveredAsset]:
        g = self._github()
        repo = g.get_repo(self.config["repo_name"])
        branch = self.config.get("branch") or repo.default_branch
        stack = repo.get_contents(self.config.get("path", ""), ref=branch)
        files, assets = [], []
        while stack:
            c = stack.pop(0)
            if c.type == "dir":
                stack.extend(repo.get_contents(c.path, ref=branch))
            elif c.path.rsplit(".", 1)[-1].lower() in ("sql", "py"):
                files.append(c)
        for f in files:
            try:
                content = f.decoded_content.decode("utf-8", "ignore")
            except Exception:  # noqa: BLE001
                continue
            meta, raw = analyze_file(f.path, content)
            meta["html_url"] = f.html_url
            assets.append(DiscoveredAsset(
                external_id=f"repo://{self.config['repo_name']}/{f.path}",
                name=f.path.split("/")[-1], asset_type="etl_pipeline",
                parent_id=f"repo://{self.config['repo_name']}", metadata=meta, raw_lineage=raw or None))
        return assets

    async def get_asset_details(self, external_id: str) -> Optional[DiscoveredAsset]:
        return None
