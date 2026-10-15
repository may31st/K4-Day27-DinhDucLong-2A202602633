import os
import tempfile
import unittest
from pathlib import Path
from contextlib import ExitStack
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from exercises import exercise_4_audit as ex4
from test_lab import LLM, PR, URL, analysis


def button(app, label):
    return next(item for item in app.button if item.label == label)


class UITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.stack = ExitStack()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict(os.environ, {'HITL_DB_PATH': self.tmp.name + '/ui.db'}))
        self.stack.enter_context(patch.object(ex4, 'fetch_pr', return_value=PR))
        self.posted = []
        self.stack.enter_context(patch.object(ex4, 'post_review_comment', side_effect=lambda url, body: self.posted.append(body)))

    def start(self, score):
        self.stack.enter_context(patch.object(ex4, 'get_llm', return_value=LLM(analysis(score), analysis(.81, 'Refined'))))
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=30).run()
        self.assertEqual(len(app.exception), 0)
        app.text_input[0].set_value(URL)
        button(app, 'Run review').click().run()
        self.assertEqual(len(app.exception), 0)
        return app

    def test_approve_posts_once_and_saved_session_reopens(self):
        app = self.start(.65)
        self.assertEqual(self.posted, [])
        button(app, 'Approve').click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(self.posted), 1)
        self.assertEqual(len(app.success), 1)
        button(app, 'Open session').click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(self.posted), 1)
        self.assertEqual(len(app.success), 1)

    def test_reject_and_edit_do_not_post(self):
        for choice in ['Reject', 'Edit']:
            app = self.start(.65)
            button(app, choice).click().run()
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(self.posted, [])
            self.assertEqual(app.session_state['final']['final_action'], 'rejected')

    def test_reload_restores_pending_review_from_url(self):
        app = self.start(.65)
        restored = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=30)
        restored.query_params['thread'] = app.session_state['thread_id']
        restored.run()
        self.assertEqual(len(restored.exception), 0)
        self.assertEqual(self.posted, [])
        button(restored, 'Reject').click().run()
        self.assertEqual(len(restored.exception), 0)
        self.assertEqual(restored.session_state['final']['final_action'], 'rejected')

    def test_blank_escalation_answers_keep_waiting(self):
        app = self.start(.4)
        button(app, 'Submit answers').click().run()
        self.assertEqual(self.posted, [])
        self.assertIsNone(app.session_state['final'])
        self.assertGreaterEqual(len(app.warning), 1)

    def test_invalid_url_does_not_start_review(self):
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=30).run()
        app.text_input[0].set_value('https://example.org/not-a-pr')
        button(app, 'Run review').click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertIsNone(app.session_state['thread_id'])
        self.assertGreaterEqual(len(app.error), 1)

    def test_escalation_submits_question_answer_mapping(self):
        app = self.start(.4)
        question = next(item for item in app.text_input if item.label == 'Why does auth.py use MD5?')
        question.set_value('Legacy migration')
        button(app, 'Submit answers').click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(self.posted), 1)
        self.assertIn('Legacy migration', self.posted[0])
        self.assertEqual(app.session_state['final']['analysis'].summary, 'Refined')

    def test_auto_approve_shows_confidence_summary_and_link(self):
        app = self.start(.9)
        self.assertEqual(len(self.posted), 1)
        self.assertTrue(any('90%' in item.value for item in app.metric))
        self.assertTrue(any('Initial review' in item.value for item in app.markdown))
        self.assertTrue(any('GitHub' in item.label for item in app.get('link_button')))

    def test_post_failure_is_error_not_success(self):
        with patch.object(ex4, 'post_review_comment', side_effect=RuntimeError('offline')):
            app = self.start(.9)
        self.assertEqual(len(app.success), 0)
        self.assertGreaterEqual(len(app.error), 1)


if __name__ == '__main__':
    unittest.main()
