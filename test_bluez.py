import asyncio
import bluez
import dbus_next
import unittest
import unittest.mock


class BluezTest(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        self.bus = MockBus(self)
        self.listener = unittest.mock.Mock()
        self.client = self.loop.run_until_complete(bluez.connect(self.bus, self.listener))

    def send_interfaces_added(self, path, interfaces):
        self.bus.handler('/', 'org.freedesktop.DBus.ObjectManager', 'InterfacesAdded', [path, interfaces])

    def send_interfaces_removed(self, path, interfaces):
        self.bus.handler('/', 'org.freedesktop.DBus.ObjectManager', 'InterfacesRemoved', [path, interfaces])

    def send_properties_changed(self, path, interface, changed):
        self.bus.handler(path, 'org.freedesktop.DBus.Properties', 'PropertiesChanged', [interface, changed, []])

    def assert_adapter_added(self, path):
        for args, kwargs in self.listener.add_adapter.call_args_list:
            if args[0].path == path:
                return
        self.fail(f'Call add_adapter({path}) not found in {self.listener.add_adapter.call_args_list}')

    def assert_device_added(self, address, path, connected):
        for args, kwargs in self.listener.add_device.call_args_list:
            if args[0] == address and args[1].path == path and args[2] == connected:
                return
        self.fail(f'Call add_device({address}, {path}, {connected}) not found in {self.listener.add_device.call_args_list}')

    def test_connect_and_disconnect(self):
        self.bus.assert_call('add_message_handler', self.bus.handler)
        self.bus.assert_call('call', {
            'destination': 'org.freedesktop.DBus',
            'path': '/',
            'interface': 'org.freedesktop.DBus',
            'member': 'AddMatch',
            'signature': 's',
            'body': ["type='signal',sender='org.bluez',path_namespace='/'"]
        })
        self.bus.assert_call('call', {
            'destination': 'org.bluez',
            'path': '/',
            'interface': 'org.freedesktop.DBus.ObjectManager',
            'member': 'GetManagedObjects',
            'signature': '',
            'body': []
        })
        self.client.disconnect()
        self.bus.assert_call('remove_message_handler', self.bus.handler)

    def test_initial_adapter(self):
        self.assert_adapter_added('/ad')

    def test_add_adapter(self):
        self.send_interfaces_added('/apt', {
            'org.bluez.Adapter1': {}
        })
        self.assert_adapter_added('/apt')
    
    def test_initial_devices(self):
        self.assert_device_added('00:11:22:33:44:55', '/ad/dev1', False)
        self.assert_device_added('66:77:88:99:AA:BB', '/ad/dev2', True)

    def test_ignored_message(self):
        self.bus.handler('/', 'org.random', 'SomeOtherSignal', [])

    def test_add_interface(self):
        self.send_interfaces_added('/ad/dev3', {
            'org.bluez.Device1': {
                'Address': dbus_next.Variant('s', 'CC:DD:EE:FF:00:11'),
                'Connected': dbus_next.Variant('b', False)
            }
        })
        self.assert_device_added('CC:DD:EE:FF:00:11', '/ad/dev3', False)

    def test_remove_interface(self):
        self.send_interfaces_removed('/ad/dev1', ['org.bluez.Device1'])
        self.listener.remove_device.assert_called_once_with('00:11:22:33:44:55')

    def test_remove_ignored_interface(self):
        self.send_interfaces_removed('/ad/dev1', ['org.random.Interface'])
        self.listener.remove_device.assert_not_called()

    def test_change_property(self):
        self.send_properties_changed('/ad/dev1', 'org.bluez.Device1', {
            'Connected': dbus_next.Variant('b', True)
        })
        self.listener.update_device.assert_called_once_with('00:11:22:33:44:55', True)

    def test_change_ignored_property(self):
        self.send_properties_changed('/ad/dev1', 'org.bluez.Device1', {
            'Other': dbus_next.Variant('b', True)
        })
        self.listener.update_device.assert_not_called()

    def test_change_property_on_ignored_interface(self):
        self.send_properties_changed('/ad/dev1', 'org.random.Interface', {
            'Connected': dbus_next.Variant('b', True)
        })
        self.listener.update_device.assert_not_called()


class BluezAdapterTest(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        self.bus = MockBus(self)
        self.adapter = bluez.Adapter(self.bus, '/path')

    def test_remove_device(self):
        device = bluez.Device(self.bus, '/path/dev')
        self.loop.run_until_complete(self.adapter.remove_device(device))
        self.bus.assert_call('call', {
            'destination': 'org.bluez',
            'path': '/path',
            'interface': 'org.bluez.Adapter1',
            'member': 'RemoveDevice',
            'signature': 'o',
            'body': ['/path/dev']
        })
        
    def test_set_discovery_filter(self):
        self.loop.run_until_complete(self.adapter.set_discovery_filter({'key': 'value'}))
        self.bus.assert_call('call', {
            'destination': 'org.bluez',
            'path': '/path',
            'interface': 'org.bluez.Adapter1',
            'member': 'SetDiscoveryFilter',
            'signature': 'a{sv}',
            'body': [{'key': 'value'}]
        })
    
    def test_start_discovery(self):
        self.loop.run_until_complete(self.adapter.start_discovery())
        self.bus.assert_call('call', {
            'destination': 'org.bluez',
            'path': '/path',
            'interface': 'org.bluez.Adapter1',
            'member': 'StartDiscovery',
            'signature': '',
            'body': []
        })
    
    def test_stop_discovery(self):
        self.loop.run_until_complete(self.adapter.stop_discovery())
        self.bus.assert_call('call', {
            'destination': 'org.bluez',
            'path': '/path',
            'interface': 'org.bluez.Adapter1',
            'member': 'StopDiscovery',
            'signature': '',
            'body': []
        })


class BluezDeviceTest(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        self.bus = MockBus(self)
        self.adapter = bluez.Device(self.bus, '/path')
    
    def test_pair(self):
        self.loop.run_until_complete(self.adapter.pair())
        self.bus.assert_call('call', {
            'destination': 'org.bluez',
            'path': '/path',
            'interface': 'org.bluez.Device1',
            'member': 'Pair',
            'signature': '',
            'body': []
        })
    
    def test_connect(self):
        self.loop.run_until_complete(self.adapter.connect())
        self.bus.assert_call('call', {
            'destination': 'org.bluez',
            'path': '/path',
            'interface': 'org.bluez.Device1',
            'member': 'Connect',
            'signature': '',
            'body': []
        })
    
    def test_disconnect(self):
        self.loop.run_until_complete(self.adapter.disconnect())
        self.bus.assert_call('call', {
            'destination': 'org.bluez',
            'path': '/path',
            'interface': 'org.bluez.Device1',
            'member': 'Disconnect',
            'signature': '',
            'body': []
        })
    
    def test_trust(self):
        self.loop.run_until_complete(self.adapter.trust())
        self.bus.assert_call('call', {
            'destination': 'org.bluez',
            'path': '/path',
            'interface': 'org.freedesktop.DBus.Properties',
            'member': 'Set',
            'signature': 'ssv',
            'body': ['org.bluez.Device1', 'Trusted', dbus_next.Variant('b', True)]
        })


class MockBus:
    def __init__(self, test):
        self.test = test
        self.calls = []
        self.handler = None

    def add_message_handler(self, handler):
        self.calls.append(('add_message_handler', handler))
        self.handler = handler

    def remove_message_handler(self, handler):
        self.calls.append(('remove_message_handler', handler))

    async def call(self, destination, path, interface, member, signature='', body=[]):
        self.calls.append(('call', {
            'destination': destination,
            'path': path,
            'interface': interface,
            'member': member,
            'signature': signature,
            'body': body
        }))
        if member == 'GetManagedObjects':
            return [{
                '/ad': {
                    'org.bluez.Adapter1': {}
                },
                '/ad/dev1': {
                    'org.bluez.Device1': {
                        'Address': dbus_next.Variant('s', '00:11:22:33:44:55'),
                        'Connected': dbus_next.Variant('b', False)
                    }
                },
                '/ad/dev2': {
                    'org.bluez.Device1': {
                        'Address': dbus_next.Variant('s', '66:77:88:99:AA:BB'),
                        'Connected': dbus_next.Variant('b', True)
                    }
                },
            }]

    def assert_call(self, name, args):
        self.test.assertTrue(self.calls)
        self.test.assertEqual(self.calls.pop(0), (name, args))


class BluezRaceTest(unittest.TestCase):
    def test_connect_callback_race(self):
        loop = asyncio.new_event_loop()
        bus = MockRacingBus()
        listener = unittest.mock.Mock()
        loop.run_until_complete(bluez.connect(bus, listener))
        listener.add_device.assert_called_once()


class MockRacingBus:
    def __init__(self):
        self.handler = None

    def add_message_handler(self, handler):
        self.handler = handler

    async def call(self, destination, path, interface, member, signature='', body=[]):
        if member == 'GetManagedObjects':
            device = '/ad/dev1'
            interfaces = {
                'org.bluez.Device1': {
                    'Address': dbus_next.Variant('s', '00:11:22:33:44:55'),
                    'Connected': dbus_next.Variant('b', False)
                }
            }
            self.handler('/', 'org.freedesktop.DBus.ObjectManager', 'InterfacesAdded', [device, interfaces])
            return [{device: interfaces}]
