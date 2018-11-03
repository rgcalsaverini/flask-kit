class FakeOpen(object):
    def __init__(self, value=None):
        self.value = value

    def __enter__(self, *args):
        return self

    def __exit__(self, *args):
        return self

    def __call__(self, path, *args):
        self.path = path
        return self

    def read(self, *args):
        return self.value

    def write(self, value):
        self.value = value