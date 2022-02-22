import async_mock
import asyncio
import unittest


class CallSequence:
    def __init__(self):
        self.calls = []

    async def a_then_b(self, name):
        await self.a(name)
        await self.b(name)

    @async_mock.async_mock_method
    async def a(self, name):
        self.calls.append((name, 'a'))

    @async_mock.async_mock_method
    async def b(self, name):
        self.calls.append((name, 'b'))

    def c(self, name):
        self.calls.append((name, 'c'))

    @async_mock.async_mock_method
    async def exception(self):
        raise NonError()


class NonError(Exception):
    pass


class AsyncMockMethodTest(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.get_event_loop()
        self.callseq = CallSequence()

    def assert_called_before(self, earlier, later):
        msg = f'{earlier} not before {later} in {self.callseq.calls}'
        self.assertLess(self.callseq.calls.index(earlier), self.callseq.calls.index(later), msg)

    def test_no_side_effect(self):
        self.loop.run_until_complete(self.callseq.a_then_b('x'))
        self.assertEqual(self.callseq.calls, [
            ('x', 'a'),
            ('x', 'b')
        ])

    def test_side_effect_func(self):
        self.callseq.a.side_effect = [lambda *_: self.callseq.c('y')]
        self.loop.run_until_complete(self.callseq.a_then_b('x'))
        self.assertEqual(self.callseq.calls, [
            ('x', 'a'),
            ('y', 'c'),
            ('x', 'b')
        ])

    def test_side_effect_coro(self):
        task_x = self.loop.create_task(self.callseq.a_then_b('x'))
        self.callseq.a.side_effect = [self.callseq.a_then_b('y')]
        self.loop.run_until_complete(task_x)
        self.assertEqual(self.callseq.calls, [
            ('x', 'a'),
            ('y', 'a'),
            ('y', 'b'),
            ('x', 'b')
        ])

    def test_side_effect_after_exception(self):
        self.callseq.exception.side_effect = [lambda _: self.callseq.c('y')]
        self.loop.run_until_complete(self.callseq.exception())
        self.assertEqual(self.callseq.calls, [
            ('y', 'c')
        ])
