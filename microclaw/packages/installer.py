import hashlib
import json
import pathlib
import shutil
import site
import sys
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from typing import Any
from urllib.parse import quote, urlparse, urlunparse

from loguru import logger

from .settings import ExtraPackagesSettings, PackageIndexSettings, PackageSettings


class PackageInstallError(Exception):
    pass


class PackageInstaller:
    manifest_file = "manifest.json"

    def __init__(self, settings: ExtraPackagesSettings):
        self._settings = settings
        self._packages_dir = pathlib.Path(
            settings.dir or pathlib.Path.home() / ".microclaw" / "packages",
        ).expanduser().resolve()

    def install_and_sync_path(self) -> None:
        if not self._settings.packages:
            return

        if self._is_up_to_date():
            logger.debug(f"Extra packages are up to date in {self._packages_dir}")
            self._add_to_sys_path()
            return

        logger.info("Installing extra packages...")

        if self._packages_dir.exists():
            shutil.rmtree(self._packages_dir)
        self._packages_dir.mkdir(parents=True, exist_ok=True)

        self._run_pip(self._build_args())
        self._write_manifest()
        self._add_to_sys_path()
        logger.info("Extra packages installed successfully.")

    def _is_up_to_date(self) -> bool:
        manifest_path = self._packages_dir / self.manifest_file
        if not manifest_path.exists():
            return False
        try:
            with manifest_path.open() as f:
                return json.load(f) == self._build_manifest()
        except (json.JSONDecodeError, OSError):
            return False

    def _build_manifest(self) -> dict[str, Any]:
        return {
            "packages": [
                {
                    "name": p.name,
                    "version": p.version,
                    "extras": p.extras,
                    "repository": p.repository,
                }
                for p in self._settings.packages
            ],
            "indexes": {
                name: {
                    "url": idx.url,
                    "priority": idx.priority,
                    "trusted": idx.trusted,
                    "credentials": (
                        hashlib.sha256(
                            f"{idx.credentials.username or ''}:{idx.credentials.password or ''}".encode(),
                        ).hexdigest()
                        if idx.credentials
                        else None
                    ),
                }
                for name, idx in self._settings.indexes.items()
            },
        }

    def _write_manifest(self) -> None:
        with (self._packages_dir / self.manifest_file).open("w") as f:
            json.dump(self._build_manifest(), f, indent=2)

    def _add_to_sys_path(self) -> None:
        path_str = str(self._packages_dir)
        if path_str not in sys.path:
            site.addsitedir(path_str)

    def _build_args(self) -> list[str]:
        args = ["install", "--target", str(self._packages_dir)]

        for index in self._settings.indexes.values():
            flag = "--index-url" if index.priority == "primary" else "--extra-index-url"
            args.extend([flag, self._build_index_url(index)])
            if index.trusted:
                host = _extract_host(index.url)
                if host:
                    args.extend(["--trusted-host", host])

        for pkg in self._settings.packages:
            args.append(_format_package(pkg))

        return args

    def _build_index_url(self, index: PackageIndexSettings) -> str:
        if index.credentials is None:
            return index.url
        user = index.credentials.username or ""
        passwd = index.credentials.password or ""
        if not user and not passwd:
            return index.url
        parsed = urlparse(index.url)
        netloc = f"{quote(user, safe='')}:{quote(passwd, safe='')}@{parsed.netloc}"
        return urlunparse(parsed._replace(netloc=netloc))

    def _run_pip(self, args: list[str]) -> None:
        from pip._internal.cli.main import main as pip_main

        stdout = StringIO()
        stderr = StringIO()
        code = 0

        try:
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = pip_main(args)
        except SystemExit as e:
            code = e.code if isinstance(e.code, int) else 1

        if code != 0:
            raise PackageInstallError(
                f"pip install failed with exit code {code}\n"
                f"stdout:\n{stdout.getvalue()}\n"
                f"stderr:\n{stderr.getvalue()}"
            )


def _format_package(pkg: PackageSettings) -> str:
    spec = pkg.name
    if pkg.extras:
        spec += f"[{','.join(pkg.extras)}]"
    if pkg.version:
        if not any(op in pkg.version for op in ("==", ">=", "<=", ">", "<", "~=", "!=")):
            spec += f"=={pkg.version}"
        else:
            spec += pkg.version
    return spec


def _extract_host(url: str) -> str | None:
    parsed = urlparse(url)
    return parsed.netloc.split(":")[0] if parsed.netloc else None
