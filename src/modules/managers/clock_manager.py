"""A singleton from which you can request clocks with an arbitrary speed

The clock manager itself is hardware independent, but it uses a hardware dependent clock solver to generate the
clocking tree.
"""

import re
from nmigen import *

from modules.xilinx.clock_solver import ClockSolver

clocks = {}


def generate_clock(requested_freq):
    """Returns a clock with the requested frequency

    Possible frequency definitions include: `1Mhz`, `1e6`, `0.1 Ghz`
    """
    requested_freq = _freq_to_int(requested_freq)

    if requested_freq not in clocks:
        clocks[requested_freq] = Signal()
    return clocks[requested_freq]


def module_clockdomain(module, requested_freq):
    requested_freq = _freq_to_int(requested_freq)
    domain_name = "f_{}_{}".format(requested_freq, hash(module))
    module.domains += [ClockDomain(domain_name)]
    return module.d[domain_name]


def manage_clocks(module, clk, f_in):
    """Instanciates the clocking resources (e.g. PLLs)

    This should be called exactly once from the top level after everything else
    """
    module.submodules.clock_solver = ClockSolver(clocks, clk, _freq_to_int(f_in))


def _freq_to_int(freq):
    try:
        return int(freq)
    except ValueError:
        match = re.match("([\d.]+) ?([gmk])(hz)?", freq.lower())
        if not match:
            raise ValueError("parameter {} could not be decoded as a frequency".format(freq))
        return int(float(match[1]) * ({"k": 1e3, "m": 1e6, "g": 1e9}[match[2]]))
