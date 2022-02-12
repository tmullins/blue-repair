import dbus_next


async def connect(bus, listener):
    client = BluezClient(bus, listener)
    await bus.call(destination='org.freedesktop.DBus',
                   path='/',
                   interface='org.freedesktop.DBus',
                   member='AddMatch',
                   signature='s',
                   body=["type='signal',sender='org.bluez',path_namespace='/'"])
    reply = await bus.call(destination='org.bluez',
                           path='/',
                           interface='org.freedesktop.DBus.ObjectManager',
                           member='GetManagedObjects')
    client._init_objects(reply[0])
    return client


class BluezClient:
    def __init__(self, bus, listener):
        self._bus = bus
        self._listener = listener
        self._adapter = None
        self._devices = {}
        self._handlers = {
            'org.freedesktop.DBus.ObjectManager': {
                'InterfacesAdded': self._interfaces_added,
                'InterfacesRemoved': self._interfaces_removed
            },
            'org.freedesktop.DBus.Properties': {
                'PropertiesChanged': self._properties_changed
            }
        }
        bus.add_message_handler(self._handle_message)
    
    def disconnect(self):
        self._bus.remove_message_handler(self._handle_message)

    def _init_objects(self, tree):
        for path, interfaces in tree.items():
            self._check_added_adapters(path, interfaces)
            self._check_added_devices(path, interfaces)

    def _handle_message(self, path, interface, member, body):
        try:
            handler = self._handlers[interface][member]
        except KeyError:
            return
        handler(path, body)

    def _interfaces_added(self, _, body):
        self._check_added_adapters(*body)
        self._check_added_devices(*body)

    def _check_added_adapters(self, path, interfaces):
        try:
            interfaces['org.bluez.Adapter1']
        except KeyError:
            return
        self._listener.add_adapter(Adapter(self._bus, path))

    def _check_added_devices(self, path, interfaces):
        try:
            interface = interfaces['org.bluez.Device1']
            address = interface['Address'].value
            connected = interface['Connected'].value
        except KeyError:
            return
        if path not in self._devices:
            self._devices[path] = address
            self._listener.add_device(address, Device(self._bus, path), connected)

    def _interfaces_removed(self, _, body):
        path, interfaces = body
        if 'org.bluez.Device1' in interfaces:
            try:
                address = self._devices[path]
            except KeyError:
                return
            del self._devices[path]
            self._listener.remove_device(address)

    def _properties_changed(self, path, body):
        interface, changed, invalidated = body
        if interface == 'org.bluez.Device1':
            try:
                address = self._devices[path]
                connected = changed['Connected'].value
            except KeyError:
                return
            self._listener.update_device(address, connected)


class _Listener:
    def __init__(self, listener, properties):
        self.listener = listener
        self.properties = properties


class Adapter:
    def __init__(self, bus, path):
        self._bus = bus
        self.path = path

    async def remove_device(self, device):
        await self._call(member='RemoveDevice',
                         signature='o',
                         body=[device.path])

    async def set_discovery_filter(self, filter={}):
        await self._call(member='SetDiscoveryFilter',
                         signature='a{sv}',
                         body=[filter])

    async def start_discovery(self):
        await self._call(member='StartDiscovery')

    async def stop_discovery(self):
        await self._call(member='StopDiscovery')

    async def _call(self, **kwargs):
        await self._bus.call(destination='org.bluez',
                             path=self.path,
                             interface='org.bluez.Adapter1',
                             **kwargs)


class Device:
    def __init__(self, bus, path):
        self._bus = bus
        self.path = path

    async def pair(self):
        await self._call(member='Pair')

    async def connect(self):
        await self._call(member='Connect')

    async def disconnect(self):
        await self._call(member='Disconnect')

    async def trust(self):
        await self._bus.call(destination='org.bluez',
                             path=self.path,
                             interface='org.freedesktop.DBus.Properties',
                             member='Set',
                             signature='ssv',
                             body=['org.bluez.Device1', 'Trusted', dbus_next.Variant('b', True)])

    async def _call(self, **kwargs):
        await self._bus.call(destination='org.bluez',
                             path=self.path,
                             interface='org.bluez.Device1',
                             **kwargs)
