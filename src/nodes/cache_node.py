from src.nodes.base_node import BaseNode
from src.utils.metrics import cache_hits, cache_miss
from aiohttp import web
from collections import OrderedDict

class LRU(OrderedDict):
    def __init__(self, cap=1024): super().__init__(); self.cap=cap
    def get_(self,k):
        if k in self: v=self.pop(k); self[k]=v; return v
        return None
    def put(self,k,v):
        if k in self: self.pop(k)
        elif len(self)>=self.cap: self.popitem(last=False)
        self[k]=v

cache = LRU(256)
states = {} 

class CacheNode(BaseNode):
    def __init__(self):
        super().__init__()
        self.app.router.add_post("/cache/get", self.getv)
        self.app.router.add_post("/cache/put", self.putv)

    async def apply(self, entry):
        t = entry["type"]
        if t=="CACHE_UPD":
            key, val = entry["key"], entry["val"]
            cache.put(key, val); states[key]="M"
        elif t=="CACHE_INV":
            key = entry["key"]; states[key]="I"; 
            if key in cache: del cache[key]

    async def getv(self, req):
        data = await req.json()
        v = cache.get_(data["key"])
        if v is None:
            cache_miss.inc(); return web.json_response({"hit": False})
        cache_hits.inc(); return web.json_response({"hit": True, "val": v, "state": states.get(data["key"],"S")})

    async def putv(self, req):
        data = await req.json()
        if self.raft.role != 2:
            return web.json_response({"redirect": self.raft.leader_hint}, status=307)
        # write: invalidate others then update
        ok1 = await self.raft.replicate_and_commit({"type":"CACHE_INV","key": data["key"]})
        ok2 = await self.raft.replicate_and_commit({"type":"CACHE_UPD","key": data["key"], "val": data["val"]})
        return web.json_response({"ok": ok1 and ok2})
