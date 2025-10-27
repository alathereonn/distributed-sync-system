import asyncio, json, random, os
from aiohttp import web
from src.utils.config import cfg
from src.utils.metrics import raft_term, raft_role
from typing import List, Dict
from src.communication.message_passing import post_json

ROLE_FOLLOWER, ROLE_CANDIDATE, ROLE_LEADER = 0,1,2

class RaftNode:
    def __init__(self, apply_func):
        self.id = cfg.NODE_ID
        self.role = ROLE_FOLLOWER
        self.current_term = 0
        self.voted_for = None
        self.log: List[Dict] = []  # [{term, entry:{type, data}}]
        self.commit_index = -1
        self.last_applied = -1
        self.peers = [p for p in cfg.NODES.split(",") if not p.endswith(f":{cfg.HTTP_PORT}")]
        self.apply = apply_func
        self.leader_hint = None
        self.reset_election_timer()

    def reset_election_timer(self):
        self.election_due = asyncio.get_event_loop().time() + random.uniform(cfg.ELECTION_MS_MIN/1000, cfg.ELECTION_MS_MAX/1000)

    async def tick(self):
        while True:
            await asyncio.sleep(0.05)
            raft_term.set(self.current_term); raft_role.set(self.role)
            now = asyncio.get_event_loop().time()
            if self.role != ROLE_LEADER and now >= self.election_due:
                await self.start_election()

    async def start_election(self):
        self.role = ROLE_CANDIDATE
        print(f"Node {self.id} memulai election di term {self.current_term}", flush=True)
        self.current_term += 1
        self.voted_for = self.id
        votes = 1
        self.reset_election_timer()
        last_idx, last_term = len(self.log)-1, self.log[-1]["term"] if self.log else 0

        async def ask(peer):
            from src.communication.message_passing import post_json
            try:
                res = await post_json(f"{peer}/raft/request_vote", {
                    "term": self.current_term, "candidate_id": self.id,
                    "last_log_index": last_idx, "last_log_term": last_term
                }, op="request_vote")
                return res.get("vote_granted", False), res.get("term", self.current_term)
            except:
                return False, self.current_term

        rs = await asyncio.gather(*(ask(p) for p in self.peers), return_exceptions=True)
        for granted, term in rs:
            if term > self.current_term:
                self.current_term = term; self.role = ROLE_FOLLOWER; self.voted_for=None; return
            if granted: votes += 1

        if votes > (len(self.peers)+1)//2:
            self.role = ROLE_LEADER
            self.leader_hint = f"http://{cfg.NODE_ID}:{cfg.HTTP_PORT}"
            print(f"🏆 Node {self.id} elected as LEADER for term {self.current_term}!", flush=True)
            asyncio.create_task(self._heartbeat_loop())

    async def _heartbeat_loop(self):
        from src.communication.message_passing import post_json
        print(f"[{self.id}] Became LEADER at term {self.current_term}, starting heartbeat loop")
        while self.role == ROLE_LEADER:
            await asyncio.sleep(cfg.HEARTBEAT_MS / 1000)

            async def hb(peer):
                try:
                    await post_json(f"{peer}/raft/append_entries", {
                        "term": self.current_term,
                        "leader_id": self.id,
                        "prev_log_index": len(self.log) - 1,
                        "prev_log_term": self.log[-1]["term"] if self.log else 0,
                        "entries": [],
                        "leader_commit": self.commit_index
                    }, op="append_entries")
                    print(f"[{self.id}] Sent heartbeat to {peer}")
                except Exception as e:
                    print(f"[{self.id}] Failed to send heartbeat to {peer}: {e}")

            await asyncio.gather(*(hb(p) for p in self.peers), return_exceptions=True)

    async def replicate_and_commit(self, entry):
        # leader only
        self.log.append({"term": self.current_term, "entry": entry})
        idx = len(self.log)-1
        acks = 1

        async def push(peer):
            from src.communication.message_passing import post_json
            try:
                res = await post_json(f"{peer}/raft/append_entries", {
                    "term": self.current_term, "leader_id": self.id,
                    "prev_log_index": idx-1,
                    "prev_log_term": self.log[idx-1]["term"] if idx>0 else 0,
                    "entries": [self.log[idx]],
                    "leader_commit": self.commit_index
                }, op="append_entries")
                return res.get("success", False)
            except:
                return False

        rs = await asyncio.gather(*(push(p) for p in self.peers))
        acks += sum(1 for ok in rs if ok)
        if acks > (len(self.peers)+1)//2:
            self.commit_index = idx
            await self._apply_committed()
            return True
        return False

    async def _apply_committed(self):
        while self.last_applied < self.commit_index:
            self.last_applied += 1
            await self.apply(self.log[self.last_applied]["entry"])

# HTTP Handlers (mounted by base_node)
async def request_vote(req):
    node: RaftNode = req.app["raft"]
    data = await req.json()
    term = data["term"]
    if term > node.current_term:
        node.current_term = term; node.role = ROLE_FOLLOWER; node.voted_for=None
    vote = False
    up_to_date = True  # simplified
    if (node.voted_for in (None, data["candidate_id"])) and up_to_date and term >= node.current_term:
        node.voted_for = data["candidate_id"]; node.reset_election_timer(); vote=True
    return web.json_response({"term": node.current_term, "vote_granted": vote})

async def append_entries(req):
    node: RaftNode = req.app["raft"]
    data = await req.json()
    if data["term"] < node.current_term:
        return web.json_response({"success": False, "term": node.current_term})
    node.role = ROLE_FOLLOWER; node.reset_election_timer()
    # naive log match: accept directly (demo)
    if data["entries"]:
        node.log.extend(data["entries"])
    if data.get("leader_commit", -1) > node.commit_index:
        node.commit_index = data["leader_commit"]
        await node._apply_committed()
    node.leader_hint = f"http://{req.host}"
    return web.json_response({"success": True, "term": node.current_term})
