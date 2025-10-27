import asyncio, aiohttp, time
from utils.config import cfg

class FailureDetector:
    def __init__(self, peers, interval=2, timeout=3):
        self.peers = peers
        self.interval = interval
        self.timeout = timeout
        self.status = {p: {"alive": False, "last_seen": 0.0} for p in peers}
        self.subscribers = []  # callback list untuk event node_down/up

    def subscribe(self, callback):
        self.subscribers.append(callback)

    async def _notify(self, peer, alive):
        for cb in self.subscribers:
            try:
                await cb(peer, alive)
            except Exception as e:
                print(f"[FD] callback error for {peer}: {e}")

    async def check_peer(self, session, peer):
        try:
            async with session.get(f"{peer}/healthz", timeout=self.timeout) as r:
                if r.status == 200:
                    self.status[peer]["alive"] = True
                    self.status[peer]["last_seen"] = time.time()
                    return
        except:
            pass
        self.status[peer]["alive"] = False

    async def run(self):    
        async with aiohttp.ClientSession() as s:
            while True:
                for p in self.peers:
                    old = self.status[p]["alive"]
                    await self.check_peer(s, p)
                    new = self.status[p]["alive"]
                    if old != new:
                        state = "UP" if new else "DOWN"
                        print(f"[FD] Peer {p} {state}")
                        await self._notify(p, new)
                await asyncio.sleep(self.interval)
