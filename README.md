Tugas Individu 2 — Parallel and Distributed System
Institut Teknologi Kalimantan — 2025

Overview

Distributed Sync System adalah sistem terdistribusi berbasis Raft Consensus Algorithm yang terdiri dari tiga service utama:

1. Lock Node (Port 800x) → Distributed Lock Manager berbasis Raft.
2. Queue Node (Port 810x) → Distributed Queue dengan mekanisme acknowledgment (ACK).
3. Cache Node (Port 820x) → Distributed Cache dengan protokol MESI (Modified, Exclusive, Shared, Invalid) untuk menjaga konsistensi data antar node.

Ketiganya dikoordinasikan melalui leader election, replication, dan heartbeat untuk memastikan konsistensi & fault tolerance.

Architecture
           ┌──────────────────┐
           │  Client Request  │
           └────────┬─────────┘
                    │
         ┌──────────▼──────────┐
         │  Load Balancer /    │
         │  Manual Curl Tests  │
         └──────────┬──────────┘
      ┌─────────────┼──────────────────────┐
      │             │                      │
┌─────▼───────┐┌────▼───────┐┌─────────────▼───────┐
│ Lock Nodes  ││ Queue Nodes││ Cache Nodes         │
│ :8000–8002  ││ :8100–8102││ :8200–8202          │
│  Raft + Lock││ Raft + MQ  ││ Raft + MESI Cache   │
└──────────────┴─────────────┴──────────────────────┘


Semua node menggunakan RaftNode sebagai core modul untuk:
Election dan leader replication
Heartbeat broadcast
AppendEntries dan RequestVote
Commit log dan apply state machine

Build & Run
docker compose -f docker/docker-compose.yml up --build

Cek logs secara live:
docker compose -f docker/docker-compose.yml logs -f

Step-by-Step Demo
1Cek Health & Leader Lock Cluster
curl http://localhost:8000/health
curl http://localhost:8001/health
curl http://localhost:8002/health
role=2 → berarti node tersebut Leader

Test Acquire & Release Lock
Acquire Lock
$body = '{"key":"A","mode":"X","client_id":"client1"}'
Invoke-WebRequest -Uri "http://localhost:8002/lock/acquire" -Method POST -ContentType "application/json" -Body $body

Release Lock
$body = '{"key":"A","client_id":"client1"}'
Invoke-WebRequest -Uri "http://localhost:8002/lock/release" -Method POST -ContentType "application/json" -Body $body

Queue Cluster (Message Queue)
Cek siapa leader-nya:
curl http://localhost:8100/health
curl http://localhost:8101/health
curl http://localhost:8102/health

Enqueue (ke Leader Queue)
$body = '{"key":"user:42","value":"hello"}'
Invoke-WebRequest -Uri "http://localhost:8102/queue/enq" -Method POST -ContentType "application/json" -Body $body

Dequeue
Invoke-WebRequest -Uri "http://localhost:8102/queue/deq" -Method POST

Ack Message
$ack = '{"msg_id":"<MSG_ID_DARI_DEQ>"}'
Invoke-WebRequest -Uri "http://localhost:8102/queue/ack" -Method POST -ContentType "application/json" -Body $ack

Cache Cluster
Cek siapa leader:
curl http://localhost:8200/health
curl http://localhost:8201/health
curl http://localhost:8202/health

PUT Data
$body = @'
{"key":"user:42","val":{"name":"Arya","score":99}}
'@
Invoke-WebRequest -Uri "http://localhost:8201/cache/put" -Method POST -ContentType "application/json" -Body $body

GET Data
$body = @'
{"key":"user:42"}
'@
Invoke-WebRequest -Uri "http://localhost:8200/cache/get" -Method POST -ContentType "application/json" -Body $body

Metrics Monitoring
Prometheus-style metrics tersedia di setiap service:
# Lock Node
curl http://localhost:8002/metrics
# Queue Node
curl http://localhost:8102/metrics
# Cache Node
curl http://localhost:8200/metrics 

Contoh output:
raft_term 4
raft_role 2
queue_enq_total 5
queue_deq_total 4
cache_hits_total 2