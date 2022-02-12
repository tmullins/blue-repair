# BlueRepair

BlueRepair is a simple web interface for pairing to known bluetooth devices. It
provides one button to forget, scan for, and then pair to a device. It's most
useful for devices that are repeatedly used with multiple hosts but can only
remember one, such as a game controller used with a console and a PC.

BlueRepair was developed on a Raspberry Pi, but should work on any device with
dbus and bluetoothd. Python 3.7 or later is recommended.

## Install Dependencies

    pip3 install dbus_next sanic

## Configure

The web interface needs to be pre-populated with a set of known devices. These
can be discovered the first time using the desktop bluetooth UI or using
`bluetoothctl scan on`.

Example `config.yaml`:

    devices:
      - name: A device
        address: 00:11:22:33:44:55
      - name: Another device
        address: 66:77:88:99:AA:FF 

## Run the Server

By default, this will run on port 8000:

    sanic -H 0.0.0.0 server.app
