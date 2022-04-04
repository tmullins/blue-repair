import async_mock
import asyncio
import device_manager
import unittest
import unittest.mock


class DeviceManagerTest(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.get_event_loop()
        self.adapter_timeout = MockTimeout()
        self.scan_timeout = MockTimeout()
        self.here_address = '00:11:22:33:44:55'
        self.there_address = '66:77:88:99:AA:BB'
        self.nowhere_address = 'CC:DD:EE:FF:00:11'
        self.devman = device_manager.DeviceManager([
            {
                'name': 'Here',
                'address': self.here_address
            },
            {
                'name': 'There',
                'address': self.there_address
            },
            {
                'name': 'Nowhere',
                'address': self.nowhere_address
            }
        ], self.adapter_timeout, self.scan_timeout)
        self.adapter = MockAdapter()
        self.devman.add_adapter(self.adapter)
        self.here_device = MockDevice()
        self.devman.add_device(self.here_address, self.here_device, False)
        self.there_device = MockDevice()
        self.devman.add_device(self.there_address, self.there_device, True)

    def run_async(self, aw):
        self.loop.run_until_complete(aw)

    def create_task(self, coro):
        return self.loop.create_task(coro)

    def assert_devices(self, devices, here_state='disconnected', there_state='connected', nowhere_state='disconnected'):
        self.assertEqual(devices, [
            {
                'name': 'Here',
                'address': self.here_address,
                'state': here_state
            },
            {
                'name': 'There',
                'address': self.there_address,
                'state': there_state
            },
            {
                'name': 'Nowhere',
                'address': self.nowhere_address,
                'state': nowhere_state
            }
        ])

    def test_get_devices(self):
        self.assert_devices(self.devman.get_devices())

    def test_force_connect_non_existing(self):
        self.run_async(self.devman.connect(self.nowhere_address))
        self.assertEqual(self.adapter.calls, [
            ('set_discovery_filter', [{}]),
            ('start_discovery', []),
            ('stop_discovery', [])
        ])
        self.assertEqual(self.here_device.calls, [])
        self.assertEqual(self.there_device.calls, [])

    def test_connect_existing(self):
        self.adapter_timeout.wait_event.side_effect = [lambda *_: self.devman.remove_device(self.here_address)]
        self.run_async(self.devman.connect(self.here_address))
        self.assertEqual(self.adapter.calls, [
            ('remove_device', [self.here_device]),
            ('set_discovery_filter', [{}]),
            ('start_discovery', []),
            ('stop_discovery', [])
        ])
        self.assertEqual(self.here_device.calls, [])
        self.assertEqual(self.there_device.calls, [])

    def test_connect_appear_during_discovery(self):
        device = MockDevice()
        self.scan_timeout.wait_event.side_effect = [lambda *_: self.devman.add_device(self.nowhere_address, device, False)]
        self.run_async(self.devman.connect(self.nowhere_address))
        self.assertEqual(self.adapter.calls, [
            ('set_discovery_filter', [{}]),
            ('start_discovery', []),
            ('stop_discovery', [])
        ])
        self.assertEqual(self.here_device.calls, [])
        self.assertEqual(self.there_device.calls, [])
        self.assertEqual(device.calls, [
            'pair',
            'trust',
            'connect'
        ])

    def test_disconnect(self):
        self.run_async(self.devman.disconnect(self.there_address))
        self.assertEqual(self.here_device.calls, [])
        self.assertEqual(self.there_device.calls, ['disconnect'])
    
    def test_connect_during_connect(self):
        task = self.create_task(self.devman.connect(self.nowhere_address))
        self.adapter.start_discovery.side_effect = [self.devman.connect(self.nowhere_address)]
        self.run_async(task)
        self.assertEqual(self.adapter.calls, [
            ('set_discovery_filter', [{}]),
            ('start_discovery', []),
            ('stop_discovery', [])
        ])
    
    def test_disconnect_during_disconnect(self):
        task = self.create_task(self.devman.disconnect(self.there_address))
        self.there_device.disconnect.side_effect = [self.devman.disconnect(self.there_address)]
        self.run_async(task)
        self.assertEqual(self.there_device.calls, ['disconnect'])

    def test_connect_two_devices(self):
        self.devman.update_device(self.there_address, False)
        here_task = self.create_task(self.devman.connect(self.here_address))
        self.adapter.start_discovery.side_effect = [self.devman.connect(self.there_address)]
        self.run_async(here_task)
        self.assertIn(('remove_device', [self.here_device]), self.adapter.calls)
        self.assertIn(('remove_device', [self.there_device]), self.adapter.calls)
        self.assertIn(('set_discovery_filter', [{}]), self.adapter.calls)
        self.assertIn(('start_discovery', []), self.adapter.calls)
        self.assertIn(('stop_discovery', []), self.adapter.calls)
        self.assertEqual(len(self.adapter.calls), 5)

    def test_connect_already_discovered_sets_event(self):
        calls = 0
        def connect_and_check_event(instance, event):
            nonlocal calls
            calls += 1
            self.assertTrue(event.is_set())
        self.scan_timeout.wait_event.side_effect = [connect_and_check_event]
        self.run_async(self.devman.connect(self.here_address))
        self.assertEqual(calls, 1)

    def test_connect_discovery_sets_event(self):
        calls = 0
        def connect_and_check_event(instance, event):
            nonlocal calls
            calls += 1
            self.assertFalse(event.is_set())
            self.devman.add_device(self.nowhere_address, MockDevice(), False)
            self.assertTrue(event.is_set())
        self.scan_timeout.wait_event.side_effect = [connect_and_check_event]
        self.run_async(self.devman.connect(self.nowhere_address))
        self.assertEqual(calls, 1)

    def test_connect_lost_device_clears_event(self):
        calls = 0
        def connect_and_check_event(instance, event):
            nonlocal calls
            calls += 1
            self.assertFalse(event.is_set())
            raise asyncio.TimeoutError()
        self.scan_timeout.wait_event.side_effect = [connect_and_check_event]
        self.devman.remove_device(self.there_address)
        self.run_async(self.devman.connect(self.there_address))
        self.assertEqual(calls, 1)

    def test_subscribe(self):
        with self.devman.subscribe() as q:
            devices = q.get_nowait()
            self.assertTrue(q.empty())
            self.assert_devices(devices)

    def test_unsubscribe(self):
        q = self.devman.subscribe().queue
        q.get_nowait()
        self.devman.unsubscribe(q)
        self.devman.update_device(self.here_address, True)
        self.assertTrue(q.empty())

    def test_late_subscriber(self):
        self.devman.update_device(self.here_address, True)
        with self.devman.subscribe() as q:
            self.assert_devices(q.get_nowait(), here_state='connected')
            self.assertTrue(q.empty())

    def test_publish_connected_device(self):
        with self.devman.subscribe() as q:
            q.get_nowait()
            self.devman.update_device(self.here_address, True)
            self.assert_devices(q.get_nowait(), here_state='connected')
            self.assertTrue(q.empty())

    def test_publish_new_device_already_connected(self):
        with self.devman.subscribe() as q:
            q.get_nowait()
            self.devman.add_device(self.nowhere_address, MockDevice(), True)
            self.assert_devices(q.get_nowait(), nowhere_state='connected')
            self.assertTrue(q.empty())

    def test_publish_disconnected_device(self):
        with self.devman.subscribe() as q:
            q.get_nowait()
            self.devman.update_device(self.there_address, False)
            self.assert_devices(q.get_nowait(), there_state='disconnected')
            self.assertTrue(q.empty())

    def test_publish_lost_device_when_connected(self):
        with self.devman.subscribe() as q:
            q.get_nowait()
            self.devman.remove_device(self.there_address)
            self.assert_devices(q.get_nowait(), there_state='disconnected')
            self.assertTrue(q.empty())

    def test_publish_connecting_device(self):
        with self.devman.subscribe() as q:
            q.get_nowait()
            self.run_async(self.devman.connect(self.here_address))
            self.assert_devices(q.get_nowait(), here_state='connecting')
            self.assertTrue(q.empty())

    def test_publish_connecting_device_not_found(self):
        with self.devman.subscribe() as q:
            q.get_nowait()
            self.run_async(self.devman.connect(self.nowhere_address))
            self.assert_devices(q.get_nowait(), nowhere_state='connecting')
            self.assert_devices(q.get_nowait(), nowhere_state='disconnected')
            self.assertTrue(q.empty())

    def test_publish_disconnecting_device(self):
        with self.devman.subscribe() as q:
            q.get_nowait()
            self.run_async(self.devman.disconnect(self.there_address))
            self.assert_devices(q.get_nowait(), there_state='disconnecting')
            self.assertTrue(q.empty())


class MockAdapter:
    def __init__(self):
        self.calls = []

    async def remove_device(self, device):
        self.calls.append(('remove_device', [device]))

    async def set_discovery_filter(self, filter={}):
        self.calls.append(('set_discovery_filter', [filter]))

    @async_mock.async_mock_method
    async def start_discovery(self):
        self.calls.append(('start_discovery', []))

    async def stop_discovery(self):
        self.calls.append(('stop_discovery', []))


class MockDevice:
    def __init__(self):
        self.calls = []

    async def pair(self):
        self.calls.append('pair')

    async def connect(self):
        self.calls.append('connect')

    @async_mock.async_mock_method
    async def disconnect(self):
        self.calls.append('disconnect')

    async def trust(self):
        self.calls.append('trust')


class MockTimeout:
    @async_mock.async_mock_method
    async def wait_event(self, event):
        pass
