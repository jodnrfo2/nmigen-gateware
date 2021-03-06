from util.stream import StreamEndpoint


def write_to_stream(stream: StreamEndpoint, value):
    assert (yield stream.ready) == 1
    yield stream.payload.eq(value)
    yield stream.valid.eq(1)
    yield
    yield stream.valid.eq(0)
    yield


def read_from_stream(stream: StreamEndpoint, timeout=10):
    yield stream.ready.eq(1)
    for i in range(timeout):
        yield
        if (yield stream.valid):
            break
    yield stream.ready.eq(0)
    return (yield stream.payload)
