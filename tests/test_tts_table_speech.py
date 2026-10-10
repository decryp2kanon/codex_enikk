import unittest
from test_tts_stream import stream


class TableSpeechTests(unittest.TestCase):
    def test_table_cells_without_delimiter_readings(self):
        raw = '| 항목 | 상태 |\n|---|---|\n| 병합 | 아직 안 했어. |'
        self.assertEqual(stream.notify.clean_text(raw), '항목, 상태\n\n병합, 아직 안 했어.')

    def test_literal_pipes_and_shell_commands_preserved(self):
        for raw in ['파이프 | 기호', '`cat file | sort`', 'cat file | sort']:
            self.assertEqual(stream.notify.clean_text(raw), raw)
        self.assertEqual(stream.notify.clean_text('| 명령 | `cat file | sort` |'),
                         '명령, `cat file | sort`')
        self.assertEqual(stream.notify.table_row_spoken(r'| 값 | a\|b |'), r'값, a\|b')

    def test_empty_cells_and_alignment(self):
        self.assertEqual(stream.notify.clean_text('| | 상태 |'), '상태')
        self.assertEqual(stream.notify.clean_text('| :--- | ---: |'), '')

    def test_stream_waits_for_complete_row(self):
        raw = '| 작업 | 아직 안 했어. |\n'
        self.assertEqual(list(stream.boundaries(raw[:-3])), [])
        self.assertEqual(list(stream.boundaries(raw)), [len(raw)])
        self.assertEqual(list(stream.boundaries(raw.rstrip(), final=True)), [len(raw.rstrip())])

    def test_split_delta_emits_each_row_once(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as root:
            jobs = []
            acc = stream.Accumulator(Path(root), 'fixture', jobs.append)
            state = acc.state('turn', 'item')
            state['phase'] = 'final_answer'
            for delta in ['| 작업 | 끝났어.', ' |\n|---|---|\n', '| 다음 | 기다려. |']:
                state['text'] += delta
                acc.emit(state)
            acc.emit(state, final=True)
            self.assertEqual([job['text'] for job in jobs], ['작업, 끝났어.', '다음, 기다려.'])

    def test_fenced_table_not_spoken(self):
        self.assertEqual(stream.notify.clean_text('```\n| 이름 | 값 |\n```'), '')
