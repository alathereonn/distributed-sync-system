import aiohttp, asyncio, json
from src.utils.config import cfg
from src.utils.metrics import rpc_latency
from contextlib import asynccontextmanager
from time import perf_counter

@asynccontextmanager
async def _timed(op):
    t0 = perf_counter()
    try:
        yield
    finally:
        rpc_latency.labels(op).observe(perf_counter()-t0)

async def post_json(url, payload, op="rpc"):
    async with _timed(op):
        async with aiohttp.ClientSession() as s:
            async with s.post(url, json=payload, timeout=5) as r:
                r.raise_for_status()
                return await r.json()

def peers():
    return [u for u in cfg.NODES.split(",") if not u.endswith(f":{cfg.HTTP_PORT}") or not u.startswith(f"http://{cfg.NODE_ID}")]
