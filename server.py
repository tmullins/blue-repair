import asyncio
import bluez
import bus
import config
import device_manager
import json
import sanic


class ScanTimeout:
    async def wait_event(self, event):
        await asyncio.wait_for(event.wait(), 20)


app = sanic.Sanic(__name__)

app.static('/', './static')
app.static('/', './static/index.html')

# TODO:
#  - If connected, buttom prompts to turn off controller
#  - 2 queues for messages from device_manager:
#    - existing "device state" queue, push new state on every change, everyone subscribes
#    - new "message" queue, push message on errors, subscribe on connect/disconnect query even if already in progress
#    - how does second queue get associated with websocket?
#  - add tests for exceptions thrown by every call, make sure state is not an "in progress" state after

# FIXME bug: if device exists disconnected, remove device needs to wait for removal to propagate before moving on to scan

@app.before_server_start
async def start_dbus_client(app, loop):
    app.ctx.device_manager = device_manager.DeviceManager(config.Config().get_devices(), ScanTimeout())
    app.ctx.bus = bus.Bus()
    await app.ctx.bus.connect()
    app.ctx.bluez_client = await bluez.connect(app.ctx.bus, app.ctx.device_manager)

@app.after_server_stop
async def stop_dbus_client(app, loop):
    app.ctx.bluez_client.disconnect()
    app.ctx.bus.disconnect()

@app.get("/devices")
async def devices(request):
    return sanic.response.json(app.ctx.device_manager.get_devices())

@app.post("/devices/connect")
async def devices_connect(request):
    app.add_task(app.ctx.device_manager.connect(request.json['address']))
    return sanic.response.empty()

@app.post("/devices/disconnect")
async def devices_disconnect(request):
    app.add_task(app.ctx.device_manager.disconnect(request.json['address']))
    return sanic.response.empty()

@app.websocket("/ws")
async def websocket(request, ws):
    with app.ctx.device_manager.subscribe() as queue:
        while True:
            devices = await queue.get()
            await ws.send(json.dumps(devices))