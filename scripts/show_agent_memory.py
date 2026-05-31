from dotenv import load_dotenv
from letta_client import Letta

from curator_memory import require_agent_id
from letta_settings import letta_base_url


def main() -> None:
    load_dotenv()

    client = Letta(base_url=letta_base_url())
    agent = client.agents.retrieve(require_agent_id(), include_relationships="memory")

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
