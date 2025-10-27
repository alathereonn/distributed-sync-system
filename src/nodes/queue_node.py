from src.nodes.base_node import BaseNode
from src.utils.metrics import queue_enq, queue_deq, queue_lag
from xxhash import xxh64
from aiohttp import web
import time, json, collections
from src.utils.config import cfg


class ConsistentHashRing:
    def __init__(self, nodes, vnodes=64):
        self.ring = []
        for n in nodes:
            for v in range(vnodes):
                h = xxh64(f"{n}-{v}").intdigest()
                self.ring.append((h,n))
        self.ring.sort()

    def shard(self, key):
        h = xxh64(key).intdigest()
        for k,n in self.ring:
            if h <= k: return n
        return self.ring[0][1]

queues = collections.defaultdict(list)            # shard -> list(payload)
inflight = {}                                     # msg_id -> (ts, shard)
VIS_TIMEOUT = 10

class QueueNode(BaseNode):
    def __init__(self):
        super().__init__()
        self.ring = ConsistentHashRing([p for p in self.raft.peers] + [f"http://{self.id}:{self.port}"])
        self.app.router.add_post("/queue/enq", self.enq)
        self.app.router.add_post("/queue/deq", self.deq)
        self.app.router.add_post("/queue/ack", self.ack)

    @property
    def id(self): return self.raft.id
    @property
    def port(self): from src.utils.config import cfg; return cfg.HTTP_PORT

    async def apply(self, entry):
        if entry["type"]=="QUEUE_ENQ":
            shard = entry["shard"]; payload = entry["payload"]
            queues[shard].append(payload); queue_enq.inc(); queue_lag.labels(shard).set(len(queues[shard]))
        elif entry["type"]=="QUEUE_ACK":
            msg_id = entry["msg_id"]; inflight.pop(msg_id, None); queue_deq.inc()

    async def enq(self, req):
        data = await req.json()
        shard = self.ring.shard(data["key"])
        if self.raft.role != 2:
            return web.json_response({"redirect": self.raft.leader_hint}, status=307)
        ok = await self.raft.replicate_and_commit({"type":"QUEUE_ENQ","shard": shard, "payload": data})
        return web.json_response({"ok":ok})

    async def deq(self, _):
        # scan shards (demo: local only)
        for shard, q in queues.items():
            if q:
                msg = q.pop(0); mid = f"{time.time_ns()}"
                inflight[mid] = (time.time(), shard)
                return web.json_response({"msg_id": mid, "payload": msg})
        # visibility timeout requeue (simplified)
        now = time.time()
        for mid,(ts,sh) in list(inflight.items()):
            if now - ts > VIS_TIMEOUT:
                # requeue (at-least-once)
                queues[sh].insert(0, {"redelivered": True, "msg_id": mid})
                inflight.pop(mid, None)
        return web.json_response({"empty": True})

    async def ack(self, req):
        data = await req.json()
        if self.raft.role != 2:
            return web.json_response({"redirect": self.raft.leader_hint}, status=307)
        ok = await self.raft.replicate_and_commit({"type":"QUEUE_ACK","msg_id": data["msg_id"]})
        return web.json_response({"ok": ok})
