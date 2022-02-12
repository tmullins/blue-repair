from strictyaml import load, Map, Seq, Str


class Config:
    def __init__(self):
        schema = Map({'devices': Seq(Map({'name': Str(), 'address': Str()}))})
        with open('config.yaml') as f:
            self._config = load(f.read(), schema).data

    def get_devices(self):
        return self._config['devices']
