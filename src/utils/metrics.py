from prometheus_client import Counter, Gauge, Histogram

locks_acquired = Counter("locks_acquired_total","total locks acquired",["mode"])
locks_blocked  = Counter("locks_blocked_total","total lock blocks",["mode"])
raft_term      = Gauge("raft_current_term","current raft term")
raft_role      = Gauge("raft_role","role: 0=follower,1=candidate,2=leader")
queue_enq      = Counter("queue_enqueued_total","enqueued messages")
queue_deq      = Counter("queue_dequeued_total","dequeued messages")
queue_lag      = Gauge("queue_lag","queue lag per shard",["shard"])
cache_hits     = Counter("cache_hits_total","cache hits")
cache_miss     = Counter("cache_miss_total","cache misses")
rpc_latency    = Histogram("rpc_latency_seconds","rpc latency",["op"])
