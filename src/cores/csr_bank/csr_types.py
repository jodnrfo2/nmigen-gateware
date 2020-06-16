from nmigen import *
from nmigen import tracer
from nmigen._unused import MustUse
from nmigen.hdl.ast import UserValue

from soc.bus_slave import Response
from soc.memorymap import Address


class UncollectedCsrWarning(Warning):
    pass


class _Csr(MustUse):
    """a marker class to collect the registers easily"""
    _MustUse__warning = UncollectedCsrWarning
    address = None


class ControlSignal(UserValue, _Csr):
    """ Just a Signal. Indicator, that it is for controlling some parameter (i.e. can be written from the outside)
    Is mapped as a CSR in case the design is build with a SocPlatform.
    """

    def __init__(self, shape=None, *, address=None, read_strobe=None, write_strobe=None, name=None, src_loc_at=0, **kwargs):
        super().__init__(src_loc_at=-1)
        self._shape = shape
        self._kwargs = kwargs
        self.name = name or tracer.get_var_name(depth=2 + src_loc_at, default="$signal")

        self.address = Address.parse(address)
        self.write_strobe = write_strobe
        self.read_strobe = read_strobe

    def lower(self):
        return Signal(self._shape, name=self.name, **self._kwargs)


class StatusSignal(UserValue, _Csr):
    """ Just a Signal. Indicator, that it is for communicating the state to the outside world (i.e. can be read but not written from the outside)
        Is mapped as a CSR in case the design is build with a SocPlatform.
    """

    def __init__(self, shape=None, *, address=None, read_strobe=None, name=None, src_loc_at=0, **kwargs):
        super().__init__()
        self._shape = shape
        self._kwargs = kwargs
        self.name = name or tracer.get_var_name(depth=2 + src_loc_at, default="$signal")

        self.address = Address.parse(address)
        self.read_strobe = read_strobe

    def lower(self):
        return Signal(self._shape, name=self.name, **self._kwargs)


class EventReg(_Csr):  # TODO: bikeshed name
    """ A "magic" register, that doesnt have to be backed by a real register. Useful for implementing resets,
    fifo interfaces, ...
    The logic generated by the handle_read and handle_write hooks is part of the platform defined BusSlave and runs in its clockdomain.
    """

    def __init__(self, address=None):
        super().__init__()
        self.address = Address.parse(address)

        def handle_read(m, data, read_done):
            read_done(Response.OK)

        self.handle_read = handle_read

        def handle_write(m, data, write_done):
            write_done(Response.OK)

        self.handle_write = handle_write
