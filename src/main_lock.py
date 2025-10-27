import asyncio
from src.nodes.lock_manager import LockNode
from src.utils.config import cfg  

async def main():
    print("Starting Raft Distributed Lock Node...", flush=True)
    node = LockNode()
    print(f"Node {cfg.NODE_ID} initialized, listening on port {cfg.HTTP_PORT}", flush=True)
    await node.start()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Fatal error: {e}", flush=True)

