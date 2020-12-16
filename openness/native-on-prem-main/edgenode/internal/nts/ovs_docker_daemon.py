#!/usr/bin/python3
# coding: utf-8
""" ovs docker daemon """
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2019-2020 Intel Corporation

import argparse
import logging
import subprocess
import signal
import sys
import re
import docker


_HOST_NS = "/var/run/docker/netns/default"
_HOST_NS_MNT = "/var/host_ns/mnt"
_LOG = None


def signal_handler():
    """ signal handling function """
    _LOG.info("Quiting")
    sys.exit(0)

def make_parser():
    """ make parser function """
    log_levels = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
    levels_str = "{0:s} or {1:s}".format(", ".join(log_levels[:-1]), log_levels[-1])

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "-v", "--verbosity", action="store", metavar="LEVEL", dest="verbosity", default="INFO",
        choices=log_levels,
        help="Application diagnostic output verbosity ({0:s})".format(levels_str))
    parser.add_argument(
        "-f", "--filter", action="store", metavar="NAME_FILTER", dest="name_filter",
        default="mec-app",
        help="Only add KNI interfaces to a POD which name starts with name_filter")
    parser.add_argument(
        "-p", "--log-path", action="store", metavar="LOG_PATH", dest="log_path",
        default="/var/log/ovs_daemon.log",
        help="Log file path")
    parser.add_argument(
        "-b", "--bridge", action="store", metavar="BRIDGE_NAME", dest="bridge_name",
        default="br0",
        help="OvS bridge name")
    parser.add_argument(
        "-e", "--enable", action="store", metavar="ENABLE", dest="enable",
        default="false",
        help="Enable script working")

    return parser

def setup_logger(options):
    """ setup logger function """
    log_fmt = "OVS DAEMON: [%(levelname)s] %(module)s(%(lineno)d): %(message)s"
    ts_fmt = "%Y-%m-%dT%H:%M:%S"

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(log_fmt, ts_fmt))
    root_logger = logging.getLogger('')
    root_logger.addHandler(handler)
    root_logger.setLevel(options.verbosity)
    return root_logger



def docker_connect():
    """ docker connect function """
    docker_cli = docker.from_env()
    try:
        docker_cli.ping()
    except docker.errors.APIError as err:
        _LOG.critical("Failed to connect to docker server\n {}".format(err))
        return None
    return docker_cli

def create_veth_pair_names(docker_name, name_filter):
    """ create veth pair names function """
    if docker_name.startswith(name_filter):
        offset = len(name_filter)
        return "ve1-"+docker_name[offset:offset+9], "ve2-"+docker_name[offset:offset+9]

    return "ve1-"+docker_name[:9], "ve2-"+docker_name[:9]


def run_command(command, expected_output):
    """ run command function """
    try:
        ret = subprocess.check_output(command).decode("utf-8")
    except subprocess.CalledProcessError as err:
        _LOG.error("\"{}\" failed[{}]: {}".format(' '.join(err.cmd), err.returncode, err.output))
        return False
    return expected_output in ret

def move_if(dst_ip_ns_path, if_name):
    """ move if function """
    command_prefix = ["ip",
                      "link",
                      "set",
                      if_name,
                      "netns"]

    move_to_host = command_prefix + [_HOST_NS]

    move_to_dst = ["nsenter",
                   "--mount=" + _HOST_NS_MNT,
                   "--net=" + _HOST_NS] + \
                    command_prefix + \
                    [dst_ip_ns_path]

    if not run_command(move_to_host, ""):
        _LOG.error("Failed to move {} to the default namespace".format(if_name))
        return False

    if not run_command(move_to_dst, ""):
        _LOG.error("Failed to move {} to {} namespace".format(if_name, dst_ip_ns_path))
        return False

    return True

def move_if_to_host(if_name, bridge_name):
    """ move if to host function """
    command_prefix = ["ip",
                      "link",
                      "set",
                      if_name,
                      "netns"]

    move_to_host = command_prefix + [_HOST_NS]

    add_to_ovs = ["nsenter",
                  "--mount=" + _HOST_NS_MNT,
                  "--net=" + _HOST_NS] + \
    ["/usr/local/bin/ovs-vsctl", "add-port", bridge_name, if_name]

    if not run_command(move_to_host, ""):
        _LOG.error("Failed to move {} to the default namespace".format(if_name))
        return False

    if not run_command(add_to_ovs, ""):
        _LOG.error("Failed to add interface to ovs")
        return False

    return True

def bring_if_up(docker_name, name_filter):
    """ bring if up function """
    ovs_if = create_veth_pair_names(docker_name, name_filter)
    bring_up = ["nsenter",
                "--mount=" + _HOST_NS_MNT,
                "--net=" + _HOST_NS] + \
    ["ip", "link", "set", ovs_if, "up"]

    if not run_command(bring_up, ""):
        _LOG.error("Failed to bring interface {} up".format(ovs_if))
        return False

    return True

def docker_create_if(docker_name, dst_ip_ns_path, bridge_name, name_filter):
    """ docker create if function """
    ovs_if, dst_if = create_veth_pair_names(docker_name, name_filter)
    create_veth_pair = ["ip",
                        "link",
                        "add",
                        ovs_if,
                        "type",
                        "veth",
                        "peer",
                        "name",
                        dst_if]

    if not run_command(create_veth_pair, ""):
        _LOG.error("Failed to create veth pair with names vethp1/2" + docker_name)
        return False

    # move to ovs host
    if not move_if_to_host(ovs_if, bridge_name):
        _LOG.error("Failed to move interface to host")
        run_command(["ip", "link", "delete", ovs_if], "")
        run_command(["ip", "link", "delete", dst_if], "")

        return False

    # move to docker dst
    if not move_if(dst_ip_ns_path, dst_if):
        _LOG.error("Failed to move interface to container " + docker_name)
        return False

    return True

def docker_delete_if(docker_name, bridge_name, name_filter):
    """ docker delete if function """
    ovs_if = create_veth_pair_names(docker_name, name_filter)
    remove_from_ovs = ["nsenter",
                       "--mount=" + _HOST_NS_MNT,
                       "--net=" + _HOST_NS] + \
    ["/usr/local/bin/ovs-vsctl", "del-port", bridge_name, ovs_if]

    if not run_command(remove_from_ovs, ""):
        _LOG.error("Failed to remove interface from ovs: " + ovs_if)
        return False

    return True

def filter_name(pod_name, name_filter):
    """ filter name """
    ret = pod_name.startswith(name_filter)
    if not ret:
        _LOG.debug("{} name doesn't start with {}, not processing.".format(pod_name, name_filter))
    return ret

def check_if_uuid(uuid_string):
    """ check if uuid function """
    regex = re.compile('^[a-f0-9]{8}-?[a-f0-9]{4}-?4[a-f0-9]{3}-?[89ab][a-f0-9]{3}-?[a-f0-9]{12}$',
                       re.I)
    return bool(regex.match(uuid_string))

def docker_poll(docker_cli, name_filter, bridge_name):
    """ docker poll function """
    events = docker_cli.events(decode=True)

    for event in events:

        try:
            if event['Type'] == 'container':

                if 'io.kubernetes.docker.type' in event['Actor']['Attributes']:
                    if event['Actor']['Attributes']['io.kubernetes.docker.type'] != 'container':
                        continue
                    sandbox_id = event['Actor']['Attributes']['io.kubernetes.sandbox.id']
                    pod_name = event['Actor']['Attributes']['io.kubernetes.pod.name']
                    if not filter_name(pod_name, "app"):
                        continue
                else:
                    sandbox_id = event['Actor']['ID']
                    pod_name = event['Actor']['Attributes']['name']

                    if not filter_name(pod_name, name_filter) and not check_if_uuid(pod_name):
                        continue


                sandbox = docker_cli.containers.get(sandbox_id)
                ip_ns_path = sandbox.attrs['NetworkSettings']['SandboxKey']

                if event['Action'] == 'start':
                    _LOG.info("New container found: " + str(pod_name))
                    if docker_create_if(pod_name, ip_ns_path, bridge_name, name_filter):
                        if bring_if_up(pod_name, name_filter):
                            _LOG.info("OVS interfaces are up")
                        _LOG.info("Interfaces added successfully")
                    else:
                        _LOG.info("Adding interfaces failed")
                        docker_delete_if(pod_name, bridge_name, name_filter)

                elif event['Action'] == 'die':
                    docker_delete_if(pod_name, bridge_name, name_filter)
                    _LOG.info("Container has been removed: " + str(pod_name))



        except RuntimeError as err:
            _LOG.critical("Docker events error {}".format(err))


def main(options):
    """ main """
    docker_cli = docker_connect()
    if not docker_cli:
        _LOG.info("Failed to connect do docker server")

    signal.signal(signal.SIGINT, signal_handler)


    _LOG.info("[Started]")
    _LOG.info("Waiting for containers events")
    docker_poll(docker_cli, options.name_filter, options.bridge_name)

if __name__ == '__main__':
    OPTIONS = make_parser().parse_args()
    _LOG = setup_logger(OPTIONS)
    if OPTIONS.enable.lower() != "true":
        _LOG.info("OVS disabled - shutting down")
        sys.exit()
    sys.exit(main(OPTIONS))
