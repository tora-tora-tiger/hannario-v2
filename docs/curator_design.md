# Curator / Write Gate Design

## Goal

The curator reviews conversations and proposes memory updates.

The current bot intentionally allows Letta's conversational agent to use its
built-in memory behavior, including self-updates. Curator tooling is advisory:
it helps inspect logs, propose updates, and preview manual changes.

If memory drift becomes a problem, this design can become a stricter write gate
by making memory blocks read-only and routing durable updates through curator
approval.

## Non-goals

- Do not save raw user messages directly into trusted memory.
- Do not turn jokes, dares, or one-off instructions into playbook rules.
- Do not rewrite or summarize the whole playbook.
- Do not automatically apply curator proposals without human review.

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

The current dry-run script validates this shape with Pydantic before printing
JSON.

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

The current apply path is mixed:

- Letta's conversational agent may update its own memory during conversation.
- Curator scripts do not write memory.
- Human-reviewed manual updates use the scripts below.

The manual curator-assisted path is:

1. Curator proposes an update.
2. Human reviews the proposal.
3. Human updates memory with `scripts/update_memory_block.py`.
4. Human verifies with `scripts/show_agent_memory.py`.

Automatic curator writes are intentionally out of scope until the curator
behavior is trusted.

## Manual Memory Update Flow

1. Run the curator:

   ```sh
   uv run python scripts/curator_llm_dry_run.py "ユーザー: 今後はたろうって呼んで"
   ```

2. Review the returned JSON. Do not apply it blindly.

3. Preview the proposed append:

   ```sh
   uv run python scripts/preview_memory_apply.py "P006: ユーザーが希望した呼び方を尊重する。"
   ```

4. If accepted, copy the full previewed playbook and replace the `playbook`
   block manually:

   ```sh
   uv run python scripts/update_memory_block.py playbook "FULL PLAYBOOK TEXT"
   ```

5. Verify the memory:

   ```sh
   uv run python scripts/show_agent_memory.py
   ```

Never skip human review for curator proposals. Curator proposals are
suggestions, not trusted writes.

## Current Stub

`scripts/curator_dry_run.py` is a rule-based stub. It does not call an LLM and
does not write memory. It reads the current `playbook` block only to propose the
next stable ID.

The stub only checks for simple Japanese keywords such as "覚えて", "今後",
"呼んで", and "やめて". Treat its output as a CLI shape test, not a trusted
curator decision.

`scripts/curator_llm_dry_run.py` calls OpenAI directly with Structured Outputs
and validates the result with the same Pydantic schema. It reads
`OPENAI_API_KEY` from `.env.letta` and still does not write memory.

`scripts/eval_curator_llm.py` currently evaluates expected actions only.
Generated proposals still require human review before any memory update.

See [curator_examples.md](curator_examples.md) for expected behavior examples.
