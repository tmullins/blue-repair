import asyncio
import bluez
import bus
import config
import device_manager
import json
import sanic


class Timeout:
    async def wait_event(self, event):
        await asyncio.wait_for(event.wait(), 20)


app = sanic.Sanic(__name__)

app.static('/', './static')
app.static('/', './static/index.html')

@app.before_server_start
async def start_dbus_client(app, loop):
    app.ctx.device_manager = device_manager.DeviceManager(config.Config().get_devices(), Timeout(), Timeout())
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
