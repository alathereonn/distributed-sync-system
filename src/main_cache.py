import asyncio
from src.nodes.cache_node import CacheNode

print("Starting Distributed Cache Node...", flush=True)

async def main():
    node = CacheNode()
    print(f"Node {node.raft.id} listening on {node.app._state.get('cfg', None) or ''}", flush=True)
    await node.start()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Fatal error: {e}", flush=True)