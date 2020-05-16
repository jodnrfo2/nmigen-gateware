import subprocess
import tempfile
from shlex import quote
from base64 import b64encode

from nmigen.build.run import BuildProducts

from soc.zynq.to_raw_bitstream import bit2bin


def run_on_camera(cmd, host="10.42.0.1", user="operator", password="axiom", sudo=True, sshpass=True):
    if sudo:
        cmd = "echo {} | sudo -S bash -c {}".format(password, quote(cmd))
    ssh_cmd = "ssh {}@{} {}".format(user, host, quote(cmd))
    if sshpass:
        ssh_cmd = "sshpass -p{} {}".format(password, ssh_cmd)
    print("\nexecuting: ", ssh_cmd)
    return subprocess.check_output(ssh_cmd, shell=True)


def copy_to_camera(source, destination, host="10.42.0.1", user="operator", password="axiom", sshpass=True):
    scp_cmd = "scp {} {}".format(quote(source), quote("{}@{}:{}".format(user, host, destination)))
    if sshpass:
        scp_cmd = "sshpass -p{} {}".format(password, scp_cmd)
    print("\nexecuting: ", scp_cmd)
    return subprocess.check_output(scp_cmd, shell=True)


def self_extracting_blob(data, path):
    return "base64 -d > {} <<EOF\n{}\nEOF\n\n".format(quote(path), b64encode(data).decode("ASCII"))


def program_bitstream_ssh(platform, build_products: BuildProducts, name, **kwargs):
    fatfile = ""

    bitstream_name = "{}.bit".format(name)
    bin_bitstream = bit2bin(build_products.get(bitstream_name), flip_data=True)
    fatfile += self_extracting_blob(bin_bitstream, "/usr/lib/firmware/{}.bin".format(name))

    init_script = "\n# init script:\n"
    init_script += "echo {}.bin > /sys/class/fpga_manager/fpga0/firmware\n".format(name)
    init_script += platform.init_script
    fatfile += init_script

    # TODO: register map

    fatfile_name = "build/{}.fatbitstream.sh".format(name)
    with open(fatfile_name, "w") as f:
        f.write(fatfile)
    copy_to_camera(fatfile_name, "/home/operator/{}.fatbitstream.sh".format(name), **kwargs)
    run_on_camera("bash /home/operator/{}.fatbitstream.sh".format(name), **kwargs)