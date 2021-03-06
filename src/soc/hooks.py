from functools import reduce
from warnings import warn

from nmigen import *
from nmigen.hdl.ast import SignalSet
from soc.tracing_elaborate import ElaboratableSames

from cores.csr_bank import CsrBank, _Csr, ControlSignal, StatusSignal, EventReg
from soc.memorymap import MemoryMap


def csr_hook(platform, top_fragment: Fragment, sames: ElaboratableSames):
    already_done = []

    def inner(fragment):
        elaboratable = sames.get_elaboratable(fragment)
        if elaboratable:
            class_members = [(s, getattr(elaboratable, s)) for s in dir(elaboratable)]
            csr_signals = [(name, member) for name, member in class_members if isinstance(member, _Csr)]
            fragment_signals = reduce(lambda a, b: a | b, fragment.drivers.values(), SignalSet())
            csr_signals += [
                (signal.name, signal) for signal in fragment_signals
                if isinstance(signal, _Csr)
                   and signal.name != "$signal"
                   and not any(signal is cmp_signal for name, cmp_signal in csr_signals)
            ]
            for name, signal in csr_signals:
                if any(signal is done for done in already_done):
                    warn("adding a {} ({!r}; defined at {}) to two modules (one is {!r})".format(signal.__class__.__name__, name, signal.src_loc, elaboratable))
                already_done.append(signal)
            if csr_signals:
                m = Module()

                csr_bank = m.submodules.csr_bank = CsrBank()
                for name, signal in csr_signals:
                    if isinstance(signal, ControlSignal):
                        csr_bank.reg(name, signal)
                        signal._MustUse__used = True
                    elif isinstance(signal, StatusSignal):
                        csr_bank.reg(name, signal)
                        signal._MustUse__used = True
                    elif isinstance(signal, EventReg):
                        raise NotImplementedError()

                # the CSRs of an Elaboratable should live in its namespace and not in a sub namespace called csr_bank
                fragment.memorymap = csr_bank.memorymap
                platform.to_inject_subfragments.append((m, "ignore"))

        for subfragment, name in fragment.subfragments:
            inner(subfragment)
    inner(top_fragment)


def address_assignment_hook(platform, top_fragment: Fragment, sames: ElaboratableSames):
    def inner(fragment):
        module = sames.get_module(fragment)
        if hasattr(module, "peripheral"):  # we have the fragment of a marker module for a peripheral
            fragment.memorymap = module.peripheral.memorymap
            return

        # depth first recursion
        for sub_fragment, sub_name in fragment.subfragments:
            if sub_name != "ignore":
                inner(sub_fragment)

        # add everything to the own memorymap
        if not hasattr(fragment, "memorymap"):
            fragment.memorymap = MemoryMap()
        for sub_fragment, sub_name in fragment.subfragments:
            if sub_name != "ignore":
                assert hasattr(sub_fragment, "memorymap")
                fragment.memorymap.allocate_subrange(sub_fragment.memorymap, sub_name)
    inner(top_fragment)

    # prepare and finalize the memorymap
    top_memorymap: MemoryMap = top_fragment.memorymap
    top_memorymap.top = True

    assert platform.base_address is not None
    top_memorymap.place_at = platform.base_address

    print("memorymap:\n" + "\n".join(
        "    {}: {!r}".format(k, v) for k, v in top_memorymap.flatten().items()))
    platform.memorymap = top_memorymap


def peripherals_collect_hook(platform, top_fragment: Fragment, sames: ElaboratableSames):
    platform.peripherals = []

    def collect_peripherals(platform, fragment: Fragment, sames):
        module = sames.get_module(fragment)
        if module:
            if hasattr(module, "peripheral"):
                platform.peripherals.append(module.peripheral)
        for (f, name) in fragment.subfragments:
            collect_peripherals(platform, f, sames)

    collect_peripherals(platform, top_fragment, sames)

    ranges = [peripheral.range() for peripheral in platform.peripherals]

    def range_overlapping(x, y):
        if x.start == x.stop or y.start == y.stop:
            return False
        return ((x.start < y.stop and x.stop > y.start) or
                (x.stop > y.start and y.stop > x.start))

    for a in ranges:
        for b in ranges:
            if a is not b and range_overlapping(a, b):
                raise AssertionError("{!r} overlaps with {!r}".format(a, b))
