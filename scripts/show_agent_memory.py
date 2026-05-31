import os

from dotenv import load_dotenv
from letta_client import Letta

from letta_settings import letta_base_url


def main() -> None:
    load_dotenv()

    agent_id = os.getenv("LETTA_AGENT_ID")
    if not agent_id:
        raise SystemExit("Missing LETTA_AGENT_ID. Add it to .env first.")

    client = Letta(base_url=letta_base_url())
    agent = client.agents.retrieve(agent_id, include_relationships="memory")

    print(f"agent_id={agent.id}")
    print(f"name={agent.name}")
    print()

    if agent.memory is None or not agent.memory.blocks:
        print("No memory blocks found.")
        return

    for block in agent.memory.blocks:
        print(f"## {block.label}")
        print(f"id={block.id}")
        print(block.value)
        print()


if __name__ == "__main__":
    main()
