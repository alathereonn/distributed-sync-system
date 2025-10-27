import os
from pydantic import BaseModel

class Config(BaseModel):
    NODE_ID: str = os.getenv("NODE_ID","node-1")
    NODES: str = os.getenv("NODES","http://node1:8000,http://node2:8000,http://node3:8000")
    REDIS_URL: str = os.getenv("REDIS_URL","redis://redis:6379/0")
    HTTP_PORT: int = int(os.getenv("HTTP_PORT","8000"))
    SNAPSHOT_INTERVAL: int = int(os.getenv("SNAPSHOT_INTERVAL","500"))
    HEARTBEAT_MS: int = int(os.getenv("HEARTBEAT_MS","1000"))
    ELECTION_MS_MIN: int = int(os.getenv("ELECTION_MS_MIN","2000"))
    ELECTION_MS_MAX: int = int(os.getenv("ELECTION_MS_MAX","4000"))
    DATA_DIR: str = os.getenv("DATA_DIR","/data")
    CONSISTENT_HASH_VN: int = int(os.getenv("CONSISTENT_HASH_VN","64"))

cfg = Config()
