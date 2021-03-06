import math
from enum import Enum

from nmigen import *
from nmigen.hdl.ast import UserValue, MustUse

from util.bundle import Bundle


class Response(Enum):
    OKAY = 0b00
    EXOKAY = 0b01
    SLVERR = 0b10
    DECERR = 0b11


class BurstType(Enum):
    FIXED = 0b00
    INCR = 0b01
    WRAP = 0b10


class ProtectionType(UserValue):
    def __init__(self, privileged=False, secure=False, is_instruction=False):
        super().__init__()

        self.privileged = privileged
        self.secure = secure
        self.is_instruction = is_instruction

    def lower(self):
        return Signal(3, reset=int("".join(str(int(x)) for x in [self.privileged, not self.secure, self.is_instruction]), 2))


class AddressChannel(Bundle):
    def __init__(self, addr_bits, lite, id_bits, data_bytes, **kwargs):
        assert addr_bits % 8 == 0
        super().__init__(**kwargs)

        self.ready = Signal()
        self.valid = Signal()
        self.value = Signal(addr_bits)

        if not lite:
            self.id = Signal(id_bits)
            self.burst_type = Signal(BurstType)
            self.burst_len = Signal(range(16))  # in axi3 a burst can have a length of 16 as a hardcoded maximum
            self.beat_size_bytes = Signal(3, reset=int(math.log2(data_bytes)))  # this is 2**n encoded
            self.protection_type = Signal(ProtectionType().shape())


class DataChannel(Bundle):
    def __init__(self, data_bits, read, lite, id_bits, **kwargs):
        assert data_bits % 8 == 0
        super().__init__(**kwargs)

        self.ready = Signal()
        self.valid = Signal()
        self.value = Signal(data_bits)
        if read:
            self.resp = Signal(Response)
        else:
            byte_strobe_len = int(data_bits // 8)
            self.byte_strobe = Signal(byte_strobe_len, reset=-1)

        if not lite:
            self.last = Signal()
            self.id = Signal(id_bits)


class WriteResponseChannel(Bundle):
    def __init__(self, lite, id_bits, **kwargs):
        super().__init__(**kwargs)

        self.ready = Signal()
        self.valid = Signal()
        self.resp = Signal(Response)

        if not lite:
            self.id = Signal(id_bits)


class AxiEndpoint(Bundle, MustUse):
    @staticmethod
    def like(model, master=None, lite=None, name="axi", **kwargs):
        """
        Create an AxiInterface shaped like a given model.
        :param name: the name of the resulting axi port
        :type model: AxiEndpoint
        :param model: the model after which the axi port should be created
        :type master: bool
        :param master: overrides the master property of the model
        :param lite: overrides the lite property of the model. Only works for creating an AXI lite inteface from an AXI full interface.
        :return:
        """
        if lite is not None:
            assert model.is_master or lite, "cant make up id_bits out of thin air"

        return AxiEndpoint(
            addr_bits=model.addr_bits,
            data_bits=model.data_bits,
            lite=lite if lite is not None else model.is_lite,
            id_bits=None if (lite is not None and lite) else model.id_bits,
            master=master if master is not None else model.is_master,
            name=name,
            **kwargs
        )

    def __init__(self, *, addr_bits, data_bits, master, lite, id_bits=None, **kwargs):
        """
        Constructs a Record holding all the signals for axi (lite)

        :param addr_bits: the number of bits the address signal has.
        :param data_bits: the number of bits the
        :param lite: whether to construct an AXI lite or full bus.
        :param id_bits: the number of bits for the id signal of full axi. do not specify if :param lite is True.
        :param master: whether the record represents a master or a slave
        """
        super().__init__(**kwargs)

        if id_bits:
            assert not lite, "there is no id tracking with axi lite"
        if lite:
            assert id_bits is None
        if not master:
            self._MustUse__silence = True

        # metadata
        self.is_master = master
        if master:
            self.num_slaves = 0
        self.addr_bits = addr_bits
        self.data_bits = data_bits
        self.data_bytes = data_bits // 8
        assert math.log2(self.data_bytes) == int(math.log2(self.data_bytes))
        self.is_lite = lite
        self.id_bits = id_bits

        # signals
        lite_args = {"lite": lite, "id_bits": id_bits}
        self.read_address = AddressChannel(addr_bits, data_bytes=self.data_bytes, **lite_args)
        self.read_data = DataChannel(data_bits, read=True, **lite_args)

        self.write_address = AddressChannel(addr_bits, data_bytes=self.data_bytes, **lite_args)
        self.write_data = DataChannel(data_bits, read=False, **lite_args)
        self.write_response = WriteResponseChannel(**lite_args)

    def connect_slave(self, slave):
        """
        Connects an AXI slave to this AXI master. Can only be used a single time since every other case requires some kind
        of AXI inteconnect.

        usage example:
        >>> m.d.comb += master.connect_slave(slave)

        :type slave: AxiEndpoint
        :param slave: the slave to connect.
        :returns the list of
        """
        assert self.is_master
        master = self
        assert not slave.is_master
        assert master.is_lite == slave.is_lite
        full = not master.is_lite
        assert self.num_slaves == 0, "Only one Slave can be added to an AXI master without an interconnect"

        stmts = []

        stmts += [slave.read_address.value.eq(master.read_address.value)]
        stmts += [slave.read_address.valid.eq(master.read_address.valid)]
        if full:
            stmts += [slave.read_address.id.eq(master.read_address.id)]
            stmts += [slave.read_address.burst_type.eq(master.read_address.burst_type)]
            stmts += [slave.read_address.burst_len.eq(master.read_address.burst_len)]
            stmts += [slave.read_address.beat_size_bytes.eq(master.read_address.beat_size_bytes)]
            stmts += [slave.read_address.protection_type.eq(master.read_address.protection_type)]
        stmts += [master.read_address.ready.eq(slave.read_address.ready)]

        stmts += [master.read_data.value.eq(slave.read_data.value)]
        stmts += [master.read_data.valid.eq(slave.read_data.valid)]
        stmts += [master.read_data.resp.eq(slave.read_data.resp)]
        if full:
            stmts += [master.read_data.id.eq(slave.read_data.id)]
            stmts += [master.read_data.last.eq(slave.read_data.last)]
        stmts += [slave.read_data.ready.eq(master.read_data.ready)]

        stmts += [slave.write_address.value.eq(master.write_address.value)]
        stmts += [slave.write_address.valid.eq(master.write_address.valid)]
        if full:
            stmts += [slave.write_address.id.eq(master.write_address.id)]
            stmts += [slave.write_address.burst_type.eq(master.write_address.burst_type)]
            stmts += [slave.write_address.burst_len.eq(master.write_address.burst_len)]
            stmts += [slave.write_address.beat_size_bytes.eq(master.write_address.beat_size_bytes)]
            stmts += [slave.write_address.protection_type.eq(master.write_address.protection_type)]
        stmts += [master.write_address.ready.eq(slave.write_address.ready)]

        stmts += [slave.write_data.value.eq(master.write_data.value)]
        stmts += [slave.write_data.valid.eq(master.write_data.valid)]
        stmts += [slave.write_data.byte_strobe.eq(master.write_data.byte_strobe)]
        if full:
            stmts += [slave.write_data.id.eq(master.write_data.id)]
            stmts += [slave.write_data.last.eq(master.write_data.last)]
        stmts += [master.write_data.ready.eq(slave.write_data.ready)]

        stmts += [master.write_response.resp.eq(slave.write_response.resp)]
        stmts += [master.write_response.valid.eq(slave.write_response.valid)]
        if full:
            stmts += [master.write_response.id.eq(slave.write_response.id)]
        stmts += [slave.write_response.ready.eq(master.write_response.ready)]

        self._MustUse__used = True
        self.num_slaves += 1
        return stmts
