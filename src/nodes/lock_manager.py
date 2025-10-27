from src.nodes.base_node import BaseNode
from src.utils.metrics import locks_acquired, locks_blocked
from aiohttp import web
import asyncio

# simple in-memory lock table (demo), replicated via Raft entries
lock_table = {}  # key -> {"mode":"X"/"S","holders":set(), "queue":[(mode, client_id)]}

class LockNode(BaseNode):
    def __init__(self):
        super().__init__()
        self.app.router.add_post("/lock/acquire", self.acquire)
        self.app.router.add_post("/lock/release", self.release)
        self.waiters = {}  # key -> asyncio.Condition

    async def apply(self, entry):
        t = entry["type"]
        if t=="LOCK_ACQUIRE":
            key = entry["key"]; mode = entry["mode"]; cid = entry["client_id"]
            st = lock_table.setdefault(key, {"mode":None,"holders":set(),"queue":[]})
            if st["mode"] in (None,"S") and mode=="S" and (st["mode"] is None or "X" not in st["holders"]):
                st["mode"]="S"; st["holders"].add(cid); locks_acquired.labels("S").inc()
            elif st["mode"] is None and mode=="X":
                st["mode"]="X"; st["holders"].add(cid); locks_acquired.labels("X").inc()
            else:
                st["queue"].append((mode,cid)); locks_blocked.labels(mode).inc()
        elif t=="LOCK_RELEASE":
            key = entry["key"]; cid = entry["client_id"]
            st = lock_table.get(key)
            if not st: return
            if cid in st["holders"]:
                st["holders"].remove(cid)
                if not st["holders"]:
                    st["mode"]=None
                    # wake queued
                    while st["queue"]:
                        mode, c = st["queue"][0]
                        # Deadlock check: if same client appears twice in queue for same key
                        queued_clients = [cid for _, cid in st["queue"]]
                        if len(queued_clients) != len(set(queued_clients)):
                            print(f"⚠️ Possible DEADLOCK detected on key '{key}' involving clients {queued_clients}", flush=True)
                        if mode=="S":
                            # drain all S at front
                            s_can = [(m,cc) for (m,cc) in st["queue"] if m=="S"]
                            for _ in range(len(s_can)):
                                st["queue"].remove(("S", s_can[_][1]))
                            st["mode"]="S"; st["holders"].update({cc for _,cc in s_can})
                        else: # X
                            st["queue"].pop(0); st["mode"]="X"; st["holders"].add(c)
                        break


    async def acquire(self, req):
        data = await req.json()
        entry = {"type":"LOCK_ACQUIRE","key":data["key"],"mode":data["mode"],"client_id":data["client_id"]}
        if self.raft.role != 2:
            # redirect to leader
            return web.json_response({"redirect": self.raft.leader_hint}, status=307)
        ok = await self.raft.replicate_and_commit(entry)
        return web.json_response({"ok": ok})

    async def release(self, req):
        data = await req.json()
        if self.raft.role != 2:
            return web.json_response({"redirect": self.raft.leader_hint}, status=307)
        ok = await self.raft.replicate_and_commit({"type":"LOCK_RELEASE","key":data["key"],"client_id":data["client_id"]})
        return web.json_response({"ok": ok})
