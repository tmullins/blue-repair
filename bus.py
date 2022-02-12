import dbus_next


class Bus:
    def __init__(self):
        self._bus = dbus_next.aio.MessageBus(bus_type=dbus_next.BusType.SYSTEM)
        self._handlers = set()

    async def connect(self):
        await self._bus.connect()
        self._bus.add_message_handler(self._handle_message)
    
    def disconnect(self):
        self._bus.remove_message_handler(self._handle_message)
        self._bus.disconnect()

    def add_message_handler(self, handler):
        self._handlers.add(handler)

    def remove_message_handler(self, handler):
        self._handlers.remove(handler)

    async def call(self, **kwargs):
        msg = dbus_next.Message(**kwargs)
        reply = await self._bus.call(msg)
        if reply.error_name:
            raise RuntimeError(f'{reply.error_name}: {reply.body[0]}')
        return reply.body

    def _handle_message(self, msg):
        for handler in self._handlers:
            handler(msg.path, msg.interface, msg.member, msg.body)
