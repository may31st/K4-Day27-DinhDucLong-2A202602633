"""Live integration demo: Exercise 1 analyzer + Exercise 4 HITL/audit nodes.

Run from the repository root with:
    uv run python -X utf8 -m evidence.run_human_approval_demo

Uses real GitHub and LLM calls and unchanged confidence thresholds. Stops
before routing if the LLM does not return a human-approval score. Does not
publish: open the printed Streamlit URL and click Approve to resume.
"""

import asyncio
import json
import time
import uuid
from pathlib import Path

from dotenv import load_dotenv
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph

from common.db import db_path
from common.schemas import AuditEntry, ReviewState, risk_level_for
from exercises import exercise_1_confidence as exercise1
from exercises import exercise_4_audit as exercise4


async def analyze(state):
    started = time.monotonic()
    result = await asyncio.to_thread(exercise1.node_analyze, state)
    analysis = result['analysis']
    await exercise4.audit(state, AuditEntry(
        agent_id=exercise4.AGENT_ID, action='analyze',
        confidence=analysis.confidence, risk_level=risk_level_for(analysis.confidence),
        decision='pending', reason='Live Exercise 1 analyzer: ' + analysis.confidence_reasoning,
        execution_time_ms=int((time.monotonic() - started) * 1000),
    ))
    return result


async def main():
    load_dotenv('.env', override=True)
    thread = str(uuid.uuid4())
    builder = StateGraph(ReviewState)
    for name in ('fetch_pr', 'route', 'auto_approve', 'human_approval', 'escalate', 'synthesize', 'commit'):
        builder.add_node(name, getattr(exercise4, 'node_' + name))
    builder.add_node('analyze', analyze)
    for source, target in [(START, 'fetch_pr'), ('fetch_pr', 'analyze'), ('analyze', 'route'),
                           ('human_approval', 'commit'), ('escalate', 'synthesize'),
                           ('synthesize', 'commit'), ('commit', END), ('auto_approve', END)]:
        builder.add_edge(source, target)
    builder.add_conditional_edges('route', lambda state: state['decision'], {
        name: name for name in ('auto_approve', 'human_approval', 'escalate')
    })
    config = {'configurable': {'thread_id': thread}}
    async with AsyncSqliteSaver.from_conn_string(db_path()) as checkpoint:
        graph = builder.compile(checkpointer=checkpoint)
        result = await graph.ainvoke({
            'pr_url': 'https://github.com/VinUni-AI20k/PR-Demo/pull/1', 'thread_id': thread,
        }, config, interrupt_before=['route'])
        decision = exercise1.node_route(result)['decision']
        if decision != 'human_approval':
            print(f'Not a human-approval score: {result["analysis"].confidence}; no comment posted.')
            return
        result = await graph.ainvoke(None, config)
        payload = result['__interrupt__'][0].value
        assert payload['kind'] == 'approval_request'
        Path('evidence/pr1-human-pending.json').write_text(json.dumps({
            'thread_id': thread, 'analyzer': 'exercise_1_confidence.node_analyze',
            'confidence': result['analysis'].confidence, 'payload': payload,
        }, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'HUMAN_APPROVAL_READY http://127.0.0.1:8501/?thread={thread}')


if __name__ == '__main__':
    asyncio.run(main())
