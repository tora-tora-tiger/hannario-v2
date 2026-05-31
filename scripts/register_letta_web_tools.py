import sys
from pathlib import Path

from dotenv import load_dotenv
from letta_client import Letta

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from curator_memory import require_agent_id
from letta_settings import letta_base_url
from letta_web_tools import LETTA_WEB_TOOL_SPECS, LettaWebToolSpec


def upsert_tool(client: Letta, spec: LettaWebToolSpec):
    return client.tools.upsert(
        source_code=spec.source_code,
        description=spec.description,
        tags=list(spec.tags),
        return_char_limit=spec.return_char_limit,
        default_requires_approval=spec.default_requires_approval,
    )


def attach_tool_if_needed(client: Letta, agent_id: str, tool_id: str, tool_name: str) -> None:
    attached_tools = client.agents.tools.list(agent_id)
    attached_tool_ids = {tool.id for tool in attached_tools}
    attached_tool_names = {tool.name for tool in attached_tools}

    if tool_id in attached_tool_ids or tool_name in attached_tool_names:
        print(f"already attached: {tool_name} ({tool_id})")
        return

    client.agents.tools.attach(agent_id, tool_id)
    print(f"attached: {tool_name} ({tool_id})")


def main() -> None:
    load_dotenv()
    client = Letta(base_url=letta_base_url())
    agent_id = require_agent_id()

    print(f"agent_id={agent_id}")
    for spec in LETTA_WEB_TOOL_SPECS:
        tool = upsert_tool(client, spec)
        print(f"upserted: {tool.name} ({tool.id})")
        if tool.id is None or tool.name is None:
            raise RuntimeError(f"Tool upsert returned incomplete tool: {tool!r}")
        attach_tool_if_needed(client, agent_id, tool.id, tool.name)


if __name__ == "__main__":
    main()
