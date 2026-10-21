"""Supervised model worker. Native inference cannot wedge the server process."""

import asyncio
import multiprocessing
import time

from .config import Config


def _model_worker(connection, config):
    try:
        from .detector import MusicDetector

        detector = MusicDetector(config)
        connection.send(("ready", None))
        while True:
            window = connection.recv()
            connection.send(("result", detector.is_music(window)))
    except (EOFError, BrokenPipeError):
        pass
    except Exception as error:
        try:
            connection.send(("error", f"{type(error).__name__}: {error}"))
        except (EOFError, BrokenPipeError, OSError):
            pass
    finally:
        connection.close()


class ProcessDetector:
    def __init__(self, config: Config, worker=_model_worker):
        self.config, self.worker = config, worker
        self.process = None
        self.connection = None

    async def _receive(self, timeout, expected):
        deadline = time.monotonic() + timeout
        while True:
            if self.connection.poll():
                kind, value = self.connection.recv()
                if kind != expected:
                    raise RuntimeError(f"YAMNet worker error: {value}")
                return value
            if not self.process.is_alive():
                raise RuntimeError("YAMNet worker stopped unexpectedly")
            if time.monotonic() >= deadline:
                raise RuntimeError(f"YAMNet {expected} deadline exceeded; worker will restart")
            await asyncio.sleep(0.02)

    async def _start(self):
        context = multiprocessing.get_context("spawn")
        parent, child = context.Pipe()
        self.connection = parent
        self.process = context.Process(target=self.worker, args=(child, self.config), daemon=True)
        try:
            self.process.start()
            child.close()
            await self._receive(self.config.model_startup_timeout, "ready")
        except BaseException:
            child.close()
            await self.close()
            raise

    async def __aenter__(self):
        await self._start()
        return self

    async def classify(self, window) -> bool:
        try:
            if self.process is None or not self.process.is_alive():
                await self._start()
            async with asyncio.timeout(self.config.inference_timeout):
                await asyncio.to_thread(self.connection.send, window)
                return await self._receive(self.config.inference_timeout, "result")
        except asyncio.CancelledError:
            await self.close()
            raise
        except Exception as error:
            await self.close()
            if isinstance(error, TimeoutError):
                raise RuntimeError(
                    "YAMNet inference deadline exceeded; worker will restart"
                ) from error
            raise

    async def close(self):
        if self.process is not None and self.process.pid is not None:
            if self.process.is_alive():
                self.process.terminate()
            await asyncio.to_thread(self.process.join, 2)
            if self.process.is_alive():
                self.process.kill()
                await asyncio.to_thread(self.process.join, 1)
        if self.connection is not None:
            self.connection.close()

    async def __aexit__(self, *args):
        await self.close()
