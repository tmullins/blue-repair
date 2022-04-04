import asyncio


class DeviceManager:
    def __init__(self, devices, adapter_timeout, scan_timeout):
        self._adapter = None
        self._devices = {d['address']: Device(**d) for d in devices}
        self._adapter_timeout = adapter_timeout
        self._scan_timeout = scan_timeout
        self._discovering_clients = 0
        self._subscriber_queues = set()

    async def connect(self, address):
        device = self._devices[address]

        if device.state != 'disconnected':
            return
        self._publish_state(device, 'connecting')

        if device.discovered.is_set():
            await self._adapter.remove_device(device.dbus_proxy)
            await self._adapter_timeout.wait_event(device.lost)

        self._discovering_clients += 1
        if self._discovering_clients == 1:
            await self._adapter.set_discovery_filter({})
            await self._adapter.start_discovery()

        try:
            await self._scan_timeout.wait_event(device.discovered)
        except asyncio.TimeoutError:
            pass

        self._discovering_clients -= 1
        if self._discovering_clients == 0:
            await self._adapter.stop_discovery()

        if device.dbus_proxy:
            await device.dbus_proxy.pair()
            await device.dbus_proxy.trust()
            await device.dbus_proxy.connect()
        else:
            self._publish_state(device, 'disconnected')

    async def disconnect(self, address):
        device = self._devices[address]
        if device.state != 'connected':
            return
        self._publish_state(device, 'disconnecting')
        await device.dbus_proxy.disconnect()

    def get_devices(self):
        return [d.as_dict() for d in self._devices.values()]

    def subscribe(self):
        subscriber = Subscriber(self)
        self._subscriber_queues.add(subscriber.queue)
        subscriber.queue.put_nowait(self.get_devices())
        return subscriber

    def unsubscribe(self, queue):
        self._subscriber_queues.remove(queue)

    def add_adapter(self, dbus_proxy):
        self._adapter = dbus_proxy

    def add_device(self, address, dbus_proxy, connected):
        try:
            device = self._devices[address]
        except KeyError:
            return
        device.dbus_proxy = dbus_proxy
        device.discovered.set()
        device.lost.clear()
        if connected:
            self._publish_state(device, 'connected')

    def remove_device(self, address):
        try:
            device = self._devices[address]
        except KeyError:
            return
        self._publish_state(device, 'disconnected')
        device.discovered.clear()
        device.lost.set()
        device.dbus_proxy = None

    def update_device(self, address, connected):
        try:
            device = self._devices[address]
        except KeyError:
            return
        self._publish_state(device, 'connected' if connected else 'disconnected')

    def _publish_state(self, device, state):
        device.state = state
        devices = self.get_devices()
        for s in self._subscriber_queues:
            s.put_nowait(devices)


class Device:
    def __init__(self, name, address):
        self.name = name
        self.address = address
        self.state = 'disconnected'
        self.discovered = asyncio.Event()
        self.lost = asyncio.Event()
        self.lost.set()
        self.dbus_proxy = None

    def as_dict(self):
        return {'name': self.name, 'address': self.address, 'state': self.state}


class Subscriber:
    def __init__(self, device_manager):
        self.queue = asyncio.Queue()
        self._device_manager = device_manager

    def __enter__(self):
        return self.queue

    def __exit__(self, *exc_info):
        self._device_manager.unsubscribe(self.queue)
