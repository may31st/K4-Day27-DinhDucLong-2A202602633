"""Exercise 5 — run with: uv run streamlit run app.py."""

from __future__ import annotations

import asyncio
import re
import uuid

import streamlit as st
from dotenv import load_dotenv
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command

from audit.replay import recent_threads
from common.db import db_path, replay_events
from exercises.exercise_4_audit import build_graph


def render_approval_card(payload: dict) -> dict | None:
    st.subheader(f"Approval requested — confidence {payload['confidence']:.0%}")
    st.caption(payload['confidence_reasoning'])
    st.markdown(payload['summary'])
    for comment in payload.get('comments', []):
        st.markdown(f"- **[{comment['severity']}]** `{comment['file']}:{comment.get('line') or '?'}` — {comment['body']}")
    with st.expander('Diff'):
        st.code(payload.get('diff_preview', ''), language='diff')
    feedback = st.text_input('Feedback (optional)', key=f"feedback_{st.session_state.thread_id}")
    columns = st.columns(3)
    for column, choice in zip(columns, ('approve', 'reject', 'edit')):
        if column.button(choice.title(), type='primary' if choice == 'approve' else 'secondary'):
            return {'choice': choice, 'feedback': feedback}
    st.caption('Edit records feedback and ends this review without posting a comment.')
    return None


def render_escalation_card(payload: dict) -> dict | None:
    st.subheader(f"Strong escalation — confidence {payload['confidence']:.0%}")
    st.caption(payload['confidence_reasoning'])
    if payload.get('risk_factors'):
        st.error('Risks: ' + ', '.join(payload['risk_factors']))
    st.markdown(payload['summary'])
    with st.form(f"escalation_{st.session_state.thread_id}"):
        answers = {question: st.text_input(question, key=f"answer_{st.session_state.thread_id}_{i}")
                   for i, question in enumerate(payload['questions'])}
        if st.form_submit_button('Submit answers'):
            if all(value.strip() for value in answers.values()):
                return answers
            st.warning('Please answer every question before submitting.')
    return None


async def run_graph(pr_url: str, thread_id: str, resume_value=None):
    async with AsyncSqliteSaver.from_conn_string(db_path()) as cp:
        await cp.setup()
        graph = build_graph(cp)
        cfg = {'configurable': {'thread_id': thread_id}}
        value = ({'pr_url': pr_url, 'thread_id': thread_id} if resume_value is None
                 else Command(resume=resume_value))
        return await graph.ainvoke(value, cfg)


async def load_session(thread_id: str):
    async with AsyncSqliteSaver.from_conn_string(db_path()) as cp:
        await cp.setup()
        graph = build_graph(cp)
        cfg = {'configurable': {'thread_id': thread_id}}
        snapshot = await graph.aget_state(cfg)
        if not snapshot.values:
            raise ValueError('Saved session not found')
        pending = [item for task in snapshot.tasks for item in task.interrupts]
        if pending:
            return dict(snapshot.values, __interrupt__=pending)
        if snapshot.next:
            return await graph.ainvoke(None, cfg)
        return snapshot.values


def remember_result(result):
    pending = result.get('__interrupt__')
    st.session_state.interrupt_payload = pending[0].value if pending else None
    st.session_state.final = None if pending else result


def open_session(thread_id):
    result = asyncio.run(load_session(thread_id))
    st.session_state.thread_id = thread_id
    st.session_state.pr_url = result['pr_url']
    st.query_params['thread'] = thread_id
    remember_result(result)


def mark_session_selection():
    st.session_state.open_selected_session = True


def main():
    load_dotenv()
    st.set_page_config(page_title='HITL PR Review', layout='wide')
    st.title('HITL PR Review Agent')
    for key, default in [('thread_id', None), ('pr_url', ''), ('interrupt_payload', None), ('final', None)]:
        st.session_state.setdefault(key, default)

    if not st.session_state.thread_id and st.query_params.get('thread'):
        try:
            open_session(st.query_params['thread'])
        except Exception as exc:
            st.error(f'Cannot restore session: {exc}')

    with st.sidebar:
        st.header('Recent sessions')
        try:
            rows = asyncio.run(recent_threads())
            if rows:
                table = [{key: row[key] for key in ('thread_id', 'pr_url', 'worst_risk', 'last_event')} for row in rows]
                selection = st.dataframe(table, hide_index=True, on_select=mark_session_selection,
                                         selection_mode='single-row', key='recent')
                selected = selection.selection.rows
                row = rows[selected[0] if selected else 0]
                clicked = st.button('Open session')
                changed = st.session_state.pop('open_selected_session', False)
                if clicked or (selected and changed):
                    open_session(row['thread_id'])
                    st.rerun()
            else:
                st.caption('No saved reviews yet.')
        except Exception as exc:
            st.error(f'Cannot load sessions: {exc}')

    with st.form('start'):
        pr_url = st.text_input('PR URL', value=st.session_state.pr_url,
                               placeholder='https://github.com/VinUni-AI20k/PR-Demo/pull/1')
        submitted = st.form_submit_button('Run review')

    if submitted:
        pr_url = pr_url.strip()
        if not re.fullmatch(r'https://github\.com/[^/\s]+/[^/\s]+/pull/[1-9]\d*/?', pr_url):
            st.error('Enter a GitHub pull request URL, for example https://github.com/owner/repo/pull/1')
        else:
            st.session_state.pr_url = pr_url
            st.session_state.thread_id = str(uuid.uuid4())
            st.session_state.interrupt_payload = None
            st.session_state.final = None
            st.query_params['thread'] = st.session_state.thread_id
            try:
                with st.spinner('Fetching PR + asking the LLM...'):
                    remember_result(asyncio.run(run_graph(pr_url, st.session_state.thread_id)))
                st.rerun()
            except Exception as exc:
                st.error(f'Review failed: {exc}')

    payload = st.session_state.interrupt_payload
    if payload is not None:
        answer = (render_approval_card(payload) if payload['kind'] == 'approval_request'
                  else render_escalation_card(payload))
        if answer is not None:
            try:
                with st.spinner('Resuming...'):
                    remember_result(asyncio.run(run_graph(st.session_state.pr_url,
                                    st.session_state.thread_id, resume_value=answer)))
                st.rerun()
            except Exception as exc:
                st.error(f'Cannot resume review: {exc}')

    final = st.session_state.final
    if final is not None:
        action = final.get('final_action', '?')
        if action in {'auto_committed', 'committed', 'committed_after_escalation'}:
            st.success(f'✓ {action} — comment posted to {st.session_state.pr_url}')
            st.link_button('View review on GitHub', st.session_state.pr_url)
        elif action == 'rejected':
            st.warning('Review closed — no comment posted')
        elif action == 'commit_failed':
            st.error('Could not post the review to GitHub. Check token permissions and connection.')
        else:
            st.info(f'final_action = {action}')
        if final.get('analysis'):
            st.metric('Confidence', f"{final['analysis'].confidence:.0%}")
            st.markdown(final['analysis'].summary)
        if final.get('posted_comment_body'):
            with st.expander('Posted review'):
                st.markdown(final['posted_comment_body'])

    if st.session_state.thread_id:
        thread = st.session_state.thread_id
        st.caption(f'thread_id = {thread} · replay: `uv run python -m audit.replay --thread {thread}`')
        with st.expander('Audit timeline'):
            try:
                st.dataframe(asyncio.run(replay_events(thread)), hide_index=True)
            except Exception as exc:
                st.error(f'Cannot read audit events: {exc}')


if __name__ == '__main__':
    main()
