import asyncio
from src.nodes.queue_node import QueueNode

print("Starting Distributed Queue Node...", flush=True)

async def main():
    node = QueueNode()
    await node.start()

if __name__ == "__main__":
    asyncio.run(main())

