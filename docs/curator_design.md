# Curator / Write Gate Design

## Goal

The curator reviews conversations and proposes memory updates.

The first version must not apply updates automatically. It only produces a
proposal that a human can inspect.

## Non-goals

- Do not save raw user messages directly into trusted memory.
- Do not turn jokes, dares, or one-off instructions into playbook rules.
- Do not rewrite or summarize the whole playbook.
- Do not let the conversational agent directly edit its own long-term rules.

## Candidate Signals

Memory update candidates should be limited to durable preferences or server
norms, such as:

- A user's preferred nickname or form of address.
- A topic someone explicitly wants the bot to avoid.
- Feedback that the bot is speaking too much or too formally.
- Stable server-specific norms, inside jokes, or tone preferences.
- Explicit requests like "remember this" or "don't do this again".

Normal conversation, jokes, roleplay, and adversarial instructions should
usually produce no proposal.

## Output Format

The curator should return one JSON object:

```json
{
  "action": "none",
  "target": null,
  "reason": "No durable memory update is needed.",
  "proposal": null
}
```

Allowed actions:

- `none`: no memory update.
- `append`: propose adding a new ID-based playbook item.
- `replace`: propose replacing one existing ID-based playbook item.

Allowed targets:

- `playbook`
- `persona`
- `server_context`

For `append`, `proposal` should be the exact new line to add, using the next
stable ID such as `P006`.

For `replace`, `proposal` should include the target ID and the full replacement
line.

## Apply Policy

The initial apply path is manual:

1. Curator proposes an update.
2. Human reviews the proposal.
3. Human updates memory with `scripts/update_memory_block.py`.
4. Human verifies with `scripts/show_agent_memory.py`.

Automatic writes are intentionally out of scope until the curator behavior is
trusted.
