from nmigen import *
from unittest import TestCase

from cores.ft601.ft601_stream_sink import FT601StreamSink
from util.sim import SimPlatform, TristateIo
from util.stream import StreamEndpoint


class Ft601FakeResource:
    reset = Signal()
    data = TristateIo(32)
    be = TristateIo(4)
    oe = Signal()
    read = Signal()
    write = Signal()
    siwu = Signal()
    rxf = Signal()
    txe = Signal()
    clk = Signal()


class TestFt601StreamSink(TestCase):
    def test_smoke(self):
        m = Module()

        platform = SimPlatform()
        platform.add_sim_clock("sync", 50e6)
        platform.add_sim_clock("ft601", 100e6)

        ft601 = Ft601FakeResource()
        counter_source = StreamEndpoint(32, is_sink=False, has_last=False)
        m.d.sync += counter_source.payload.eq(counter_source.payload + 1)
        m.d.comb += counter_source.valid.eq(1)
        m.submodules.dut = FT601StreamSink(ft601, counter_source)

        def testbench():
            read = []
            for i in range(3):
                yield ft601.txe.eq(1)
                written = 0
                began = False
                while True:
                    if not began:
                        if (yield ft601.write):
                            began = True
                    if began:
                        if (yield ft601.write):
                            written += 1
                            read.append((yield ft601.data.o))
                        else:
                            yield ft601.txe.eq(0)
                            break
                        if written == 2048:
                            yield ft601.txe.eq(0)
                            break
                    yield
                yield
                assert written == 2048
                for i in range(200):
                    yield
                    assert (yield ft601.write) == 0, "write was high in idle cycle {}".format(i)

            # validate the received data
            print(read)
            last = 0
            for v in read:
                assert v == last
                last += 1

        platform.sim(m, (testbench, "ft601"))
