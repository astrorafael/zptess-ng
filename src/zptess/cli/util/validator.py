import re
import argparse

from ...lib import SERIAL_PORT_PREFIX, TEST_SERIAL_PORT, TEST_BAUD
from ...lib import TEST_IP, TEST_TCP_PORT, TEST_UDP_PORT


def valid_ip_address(ip: str):
    """Validate an IPv4 address returning True or False"""
    return [
        0 <= int(x) < 256 for x in re.split(r"\.", re.match(r"^\d+\.\d+\.\d+\.\d+$", ip).group(0))
    ].count(True) == 4


def vendpoint(
    value,
    default_ip: str = TEST_IP,
    default_tcp_port: int = TEST_TCP_PORT,
    default_udp_port: int = TEST_UDP_PORT,
    default_serial_port: str = TEST_SERIAL_PORT,
    default_baud: int = TEST_BAUD,
) -> str:
    """
    Utility to convert command line values to serial or tcp endpoints
    tcp
    tcp::<port>
    tcp:<ip>
    tcp:<ip>:<port>
    udp
    udp::<port>
    udp:<ip>
    udp:<ip>:<port>
    serial
    serial::<baud>
    serial:<serial_port>
    serial:<serial_port>:<baud>

    """
    parts = [elem.strip() for elem in value.split(":")]
    length = len(parts)
    if length < 1 or length > 3:
        raise argparse.ArgumentTypeError("Invalid endpoint format {0}".format(value))
    proto = parts[0]
    if proto == "tcp":
        if length == 1:
            ip = str(default_ip)
            port = str(default_tcp_port)
        elif length == 2:
            ip = parts[1]
            port = str(default_tcp_port)
        elif valid_ip_address(parts[1]):
            ip = parts[1]
            port = parts[2]
        else:
            ip = str(default_ip)
            port = parts[2]
        result = proto + ":" + ip + ":" + port
    elif proto == "serial":
        if length == 1:
            serial = SERIAL_PORT_PREFIX + str(default_serial_port)
            baud = str(default_baud)
        elif length == 2:
            serial = SERIAL_PORT_PREFIX + str(parts[1])
            baud = str(default_baud)
        elif parts[1] != "":
            serial = SERIAL_PORT_PREFIX + str(parts[1])
            baud = parts[2]
        else:
            serial = SERIAL_PORT_PREFIX + str(default_serial_port)
            baud = parts[2]
        result = proto + ":" + serial + ":" + baud
    elif proto == "udp":
        if length == 1:
            ip = str(default_ip)
            port = str(default_udp_port)
        elif length == 2:
            ip = parts[1]
            port = str(default_udp_port)
        elif valid_ip_address(parts[1]):
            ip = parts[1]
            port = parts[2]
        else:
            ip = str(default_ip)
            port = parts[2]
        result = proto + ":" + ip + ":" + port
    else:
        raise argparse.ArgumentTypeError("Invalid endpoint prefix {0}".format(parts[0]))
    return result
