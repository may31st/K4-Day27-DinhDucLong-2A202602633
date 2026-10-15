import asyncio
import os
import tempfile
import unittest
from contextlib import ExitStack
from unittest.mock import patch

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command

from common.db import replay_events, write_audit_event
from common.github import PullRequest
from common.schemas import PRAnalysis, AuditEntry
from audit import replay
from exercises import exercise_1_confidence as ex1
from exercises import exercise_2_hitl as ex2
from exercises import exercise_3_escalation as ex3
from exercises import exercise_4_audit as ex4


URL = 'https://github.com/example/lab/pull/1'
PR = PullRequest(URL, 'example', 'lab', 1, 'Login', 'author', 'main',
                 'login', 'abcdef123', '+ password = md5(password)', ['auth.py'])


def analysis(confidence, summary='Initial review'):
    return PRAnalysis(summary=summary, confidence=confidence,
                      confidence_reasoning='Missing deployment context',
                      risk_factors=['Weak password hash'],
                      escalation_questions=['Why does auth.py use MD5?'])


class LLM:
    def __init__(self, *outputs):
        self.outputs = iter(outputs)
        self.messages = []

    def with_structured_output(self, schema):
        assert schema is PRAnalysis
        return self

    def invoke(self, messages):
        self.messages.append(messages)
        return next(self.outputs)

    async def ainvoke(self, messages):
        return self.invoke(messages)


class RoutingTests(unittest.TestCase):
    def test_exercise_one_routes_boundary_scores(self):
        for score, action in [(0, 'pending_escalation'), (.579, 'pending_escalation'),
                              (.58, 'pending_human_approval'), (.729, 'pending_human_approval'),
                              (.73, 'auto_approved'), (1, 'auto_approved')]:
            with self.subTest(score=score), patch.object(ex1, 'fetch_pr', return_value=PR), \
                    patch.object(ex1, 'get_llm', return_value=LLM(analysis(score))):
                result = ex1.build_graph().invoke({'pr_url': URL})
                self.assertEqual(result['final_action'], action)

    def test_approval_pauses_then_posts_only_on_approve(self):
        for choice, action in [('approve', 'committed'), ('reject', 'rejected'), ('edit', 'rejected')]:
            posted = []
            with self.subTest(choice=choice), patch.object(ex2, 'fetch_pr', return_value=PR), \
                    patch.object(ex2, 'get_llm', return_value=LLM(analysis(.65))), \
                    patch.object(ex2, 'post_review_comment', side_effect=lambda url, body: posted.append(body)):
                graph = ex2.build_graph()
                cfg = {'configurable': {'thread_id': choice}}
                paused = graph.invoke({'pr_url': URL}, cfg)
                self.assertEqual(paused['__interrupt__'][0].value['kind'], 'approval_request')
                self.assertEqual(posted, [])
                final = graph.invoke(Command(resume={'choice': choice, 'feedback': 'Reviewed'}), cfg)
                self.assertEqual(final['final_action'], action)
                self.assertEqual(len(posted), int(choice == 'approve'))

    def test_escalation_synthesizes_original_review_and_answers(self):
        llm = LLM(analysis(.4), analysis(.8, 'Refined review'))
        posted = []
        with patch.object(ex3, 'fetch_pr', return_value=PR), \
                patch.object(ex3, 'get_llm', return_value=llm), \
                patch.object(ex3, 'post_review_comment', side_effect=lambda url, body: posted.append(body)):
            graph = ex3.build_graph()
            cfg = {'configurable': {'thread_id': 'escalation'}}
            paused = graph.invoke({'pr_url': URL}, cfg)
            self.assertEqual(paused['__interrupt__'][0].value['questions'], ['Why does auth.py use MD5?'])
            final = graph.invoke(Command(resume={'Why does auth.py use MD5?': 'Legacy migration'}), cfg)
            self.assertEqual(final['final_action'], 'committed_after_escalation')
            self.assertIn('Refined review', posted[0])
            prompt = str(llm.messages[-1])
            for value in ['Initial review', 'Legacy migration', PR.diff]:
                self.assertIn(value, prompt)


class AuditTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {'HITL_DB_PATH': self.tmp.name + '/audit.db', 'GITHUB_USER': 'reviewer'})
        self.env.start()

    async def asyncTearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    async def test_durable_resume_does_not_refetch_or_post_twice(self):
        posted = []
        with patch.object(ex4, 'fetch_pr', return_value=PR), \
                patch.object(ex4, 'get_llm', return_value=LLM(analysis(.65))), \
                patch.object(ex4, 'post_review_comment', side_effect=lambda url, body: posted.append(body)):
            cfg = {'configurable': {'thread_id': 'durable'}}
            async with AsyncSqliteSaver.from_conn_string(os.environ['HITL_DB_PATH']) as cp:
                result = await ex4.build_graph(cp).ainvoke({'pr_url': URL, 'thread_id': 'durable'}, cfg)
                self.assertIn('__interrupt__', result)
            self.assertEqual(posted, [])
            async with AsyncSqliteSaver.from_conn_string(os.environ['HITL_DB_PATH']) as cp:
                final = await ex4.build_graph(cp).ainvoke(Command(resume={'choice': 'approve', 'feedback': 'OK'}), cfg)
            self.assertEqual(final['final_action'], 'committed')
            self.assertEqual(len(posted), 1)
        events = await replay_events('durable')
        self.assertEqual([e['action'] for e in events], ['fetch_pr', 'analyze', 'route', 'human_approval', 'human_approval', 'human_approval', 'commit'])
        self.assertEqual(events[-2]['reviewer_id'], 'reviewer')
        self.assertEqual(events[-2]['decision'], 'approve')
        self.assertTrue(all(e['reviewer_id'] is None for e in events if e['action'] not in {'human_approval', 'escalate'}))
        self.assertTrue(all(e['execution_time_ms'] >= 0 for e in events))

    async def test_recent_sessions_report_highest_risk_not_alphabetical_max(self):
        for risk in ['high', 'low', 'med']:
            await write_audit_event(thread_id='risk-test', pr_url=URL, entry=AuditEntry(
                agent_id='test', action='route', confidence=.5, risk_level=risk,
                decision='pending', execution_time_ms=0))
        rows = await replay.recent_threads()
        self.assertEqual(rows[0]['worst_risk'], 'high')
        self.assertEqual(rows[0]['events'], 3)

    async def test_cli_existing_thread_resumes_without_new_fetch(self):
        cfg = {'configurable': {'thread_id': 'cli-resume'}}
        with patch.object(ex4, 'fetch_pr', return_value=PR), \
                patch.object(ex4, 'get_llm', return_value=LLM(analysis(.65))):
            async with AsyncSqliteSaver.from_conn_string(os.environ['HITL_DB_PATH']) as cp:
                await ex4.build_graph(cp).ainvoke({'pr_url': URL, 'thread_id': 'cli-resume'}, cfg)
        with patch.object(ex4, 'fetch_pr', side_effect=AssertionError('Refetched saved PR')), \
                patch.object(ex4, 'handle_interrupt', return_value={'choice': 'reject'}):
            result = await ex4.run(URL, 'cli-resume')
            self.assertEqual(result['final_action'], 'rejected')
            completed = await ex4.run(URL, 'cli-resume')
            self.assertEqual(completed['final_action'], 'rejected')

    async def test_audit_all_branches_and_post_failure(self):
        for score, fail, choice, expected in [(.9, False, None, 'auto_committed'),
                                             (.9, True, None, 'commit_failed'),
                                             (.65, False, 'reject', 'rejected'),
                                             (.65, False, 'edit', 'rejected'),
                                             (.4, False, None, 'committed_after_escalation')]:
            thread = str((score, fail, choice))
            with ExitStack() as stack:
                stack.enter_context(patch.object(ex4, 'fetch_pr', return_value=PR))
                stack.enter_context(patch.object(ex4, 'get_llm', return_value=LLM(analysis(score), analysis(.81, 'Refined'))))
                stack.enter_context(patch.object(ex4, 'post_review_comment', side_effect=RuntimeError('offline') if fail else None))
                async with AsyncSqliteSaver.from_conn_string(os.environ['HITL_DB_PATH']) as cp:
                    graph = ex4.build_graph(cp)
                    cfg = {'configurable': {'thread_id': thread}}
                    result = await graph.ainvoke({'pr_url': URL, 'thread_id': thread}, cfg)
                    if '__interrupt__' in result:
                        answer = {'choice': choice, 'feedback': 'Revise'} if choice else {'Why MD5?': 'Legacy'}
                        result = await graph.ainvoke(Command(resume=answer), cfg)
                    self.assertEqual(result['final_action'], expected)
            events = await replay_events(thread)
            self.assertGreaterEqual(len(events), 4)
            if score == .4:
                synth = next(e for e in events if e['action'] == 'synthesize')
                self.assertEqual(synth['confidence'], .81)
                self.assertEqual(synth['risk_level'], 'low')


if __name__ == '__main__':
    unittest.main()
