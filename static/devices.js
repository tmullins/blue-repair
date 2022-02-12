function receive_message(event) {
    var devices = JSON.parse(event.data);
    var buttons = devices.map(make_button);
    document.body.replaceChildren(...buttons);
}

function make_button(device) {
    var button = document.createElement('button');
    button.className = device['state'];
    button.innerText = device['name'];
    button.addEventListener('click', function(event) {
        switch (device['state']) {
            case 'disconnected':
                var req = new XMLHttpRequest();
                req.open('POST', '/devices/connect');
                req.send(JSON.stringify({'address': device['address']}));
                break;
            case 'connected':
                var req = new XMLHttpRequest();
                req.open('POST', '/devices/disconnect');
                req.send(JSON.stringify({'address': device['address']}));
                break;
        }
    });
    return button;
}

document.addEventListener('DOMContentLoaded', function(event) {
    var socket = new WebSocket('ws://' + location.host + '/ws');
    socket.addEventListener('message', receive_message)
});
