# the 1x hdmi plugin module
# see: https://wiki.apertus.org/index.php/Beta_HDMI_Plugin_Module

from nmigen.build import Resource, Subsignal, Pins, PinsN, DiffPairs, Attrs


def connect(platform, plugin_connector_name, hdmi_num=0):
    platform.add_resources([
        Resource("hdmi", hdmi_num,
                 # high speed serial lanes
                 Subsignal("clock", DiffPairs("lvds3_p", "lvds3_n", dir='o', conn=(plugin_connector_name, 0)), Attrs(IOSTANDARD="LVDS_25")),
                 Subsignal("data", DiffPairs("lvds2_p lvds1_p lvds0_p", "lvds2_n lvds1_n lvds0_n", dir='o', conn=(plugin_connector_name, 0)), Attrs(IOSTANDARD="LVDS_25")),

                 # i2c to read edid data from the monitor
                 Subsignal("sda", Pins("lvds5_n", dir='io', conn=(plugin_connector_name, 0)), Attrs(IOSTANDARD="LVCMOS25")),
                 Subsignal("scl", Pins("lvds5_p", dir='io', conn=(plugin_connector_name, 0)), Attrs(IOSTANDARD="LVCMOS25")),

                 # hdmi plugin-module specific signals
                 Subsignal("output_enable", PinsN("gpio6", dir='o', conn=(plugin_connector_name, 0)), Attrs(IOSTANDARD="LVCMOS33")),
                 Subsignal("eq", Pins("gpio1 gpio4", dir='o', conn=(plugin_connector_name, 0)), Attrs(IOSTANDARD="LVCMOS33")),
                 Subsignal("dcc_enable", Pins("gpio5", dir='o', conn=(plugin_connector_name, 0)), Attrs(IOSTANDARD="LVCMOS33")),
                 Subsignal("vcc_enable", Pins("gpio7", dir='o', conn=(plugin_connector_name, 0)), Attrs(IOSTANDARD="LVCMOS33")),
                 Subsignal("ddet", Pins("gpio3", dir='o', conn=(plugin_connector_name, 0)), Attrs(IOSTANDARD="LVCMOS33")),
                 Subsignal("ihp", Pins("gpio2", dir='o', conn=(plugin_connector_name, 0)), Attrs(IOSTANDARD="LVCMOS33")),
        )
    ])