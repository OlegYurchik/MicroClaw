import asyncio
import logging
import os
import platform
import re

import facet

from .settings import CloudflareTunnelSettings


logger = logging.getLogger(__name__)


class CloudflareTunnelService(facet.AsyncioServiceMixin):
    def __init__(self, settings: CloudflareTunnelSettings, local_url: str, port: int):
        self._settings = settings
        self._local_url = local_url
        self._port = port
        self._process: asyncio.subprocess.Process | None = None
        self._public_url: str | None = None

    async def start(self):
        if not self._settings.enabled:
            logger.info("Cloudflare tunnel disabled, skipping startup")
            return

        self._ensure_binary()
        await self._start_process()
        logger.info("Cloudflare tunnel service started successfully")

    async def stop(self):
        if not self._settings.enabled:
            return

        await self._stop_process()
        logger.info("Cloudflare tunnel service stopped")

    async def get_public_url(self) -> str:
        if not self._settings.enabled:
            raise RuntimeError("Cloudflare tunnel is not enabled")

        if not self._public_url:
            raise RuntimeError("Tunnel URL not available. Ensure service is started.")

        return self._public_url

    async def _start_process(self):
        if self._process:
            logger.warning("Tunnel already running")
            return

        cmd = [
            self._binary_path,
            "tunnel",
            "--url",
            self._local_url,
            "--log",
            "info"
        ]

        logger.info(f"Starting Cloudflare tunnel to {self._local_url}: {' '.join(cmd)}")

        self._process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        self.add_task(self._read_logs())
        await self._wait_for_url()

        if not self._public_url:
            raise RuntimeError("Could not extract public URL from Cloudflare tunnel")

        logger.info(f"Cloudflare tunnel public URL: {self._public_url}")

    async def _stop_process(self):
        if not self._process:
            return

        logger.info("Stopping Cloudflare tunnel...")
        self._process.terminate()

        try:
            await asyncio.wait_for(self._process.wait(), timeout=5)
        except asyncio.TimeoutError:
            logger.warning("Force killing Cloudflare tunnel process")
            self._process.kill()

        self._process = None
        self._public_url = None
        logger.info("Cloudflare tunnel stopped")

    async def _wait_for_url(self, timeout: int = 30):
        for _ in range(timeout):
            if self._public_url:
                return
            await asyncio.sleep(1)

        raise RuntimeError("Timeout waiting for public URL extraction")

    async def _read_logs(self):
        if not self._process:
            return

        try:
            while not self._process.stderr.at_eof():
                line = await self._process.stderr.readline()
                if not line:
                    break

                log_line = line.decode().strip()
                if log_line:
                    self._process_log_line(log_line)

        except Exception as e:
            logger.error(f"Error reading tunnel logs: {e}")

    def _process_log_line(self, log_line: str):
        if ("Your quick Tunnel" in log_line or "https://" in log_line) and not self._public_url:
            logger.info(f"Cloudflare tunnel: {log_line}")
            try:
                url_match = re.search(r'https://[^\s]+', log_line)
                if url_match:
                    self._public_url = url_match.group(0)
            except Exception as e:
                logger.debug(f"Could not extract URL from log line: {e}")
        elif "error" in log_line.lower():
            logger.error(f"Cloudflare tunnel error: {log_line}")
        elif "warn" in log_line.lower():
            logger.warning(f"Cloudflare tunnel warning: {log_line}")
        else:
            logger.debug(f"Cloudflare tunnel: {log_line}")

    def _ensure_binary(self) -> None:
        if self._settings.path:
            if os.path.exists(self._settings.path):
                logger.info(f"Using cloudflared at {self._settings.path}")
                self._binary_path = self._settings.path
                return
            logger.warning(f"Specified cloudflared path not found: {self._settings.path}")
        
        self._use_bundled_binary()

    def _use_bundled_binary(self) -> None:
        system = platform.system().lower()
        machine = platform.machine().lower()

        arch_map = {
            "x86_64": "amd64",
            "amd64": "amd64",
            "aarch64": "arm64",
            "arm64": "arm64",
        }
        arch = arch_map.get(machine, "amd64")

        binary_name = f"cloudflared-{system}-{arch}-v{self._settings.version}"
        
        module_dir = os.path.dirname(os.path.abspath(__file__))
        bin_dir = os.path.join(module_dir, "bin")
        binary_path = os.path.join(bin_dir, binary_name)
        
        if os.path.exists(binary_path):
            self._binary_path = binary_path
            logger.info(f"Using bundled cloudflared binary: {self._binary_path}")
            return
        
        raise RuntimeError(
            f"Cloudflared binary not found. Expected: {binary_path}"
        )
