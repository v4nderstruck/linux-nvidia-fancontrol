#!/usr/bin/python
import logging
import subprocess
import re
import time
from typing_extensions import Dict
import os

CONFIG_FILE = "/etc/fan_control.conf"

logger = logging.getLogger("fan_control")

regex_coretemp = re.compile(r"'GPUCoreTemp' \(.*\): (\d+).")
regex_fanspeed = re.compile(r"'GPUCurrentFanSpeed' \(.*\): (\d+).")

def read_config(path: str = CONFIG_FILE):
    """
    Config file format:
        # Comments
        temp_X fan_speed_X
        temp_Y fan_speed_Y
        ...
    """
    config = {}
    with open(path, "r") as f:
        try:
            for line in f:
                if line.startswith("#"):
                    continue
                temp, speed = line.strip().split()
                config[int(temp)] = int(speed)
        except ValueError:
            raise ValueError("Config file is not in the correct format")

    if not config:
        raise ValueError("Config file is empty")
    logger.debug(f"Parsed Config Dictionary: {config}")
    return config


def dict_to_ranges(temp_fan: Dict[int, int]):
    """
    Convert dict to list of tuples sorted by temperature
    [(temp1, fan_speed1), (temp2, fan_speed2), ...]
    """
    r = sorted(list(temp_fan.items()), key=lambda x: x[0])
    logger.debug(f"Converting dictionary to ranges: {r}")
    return r


def get_temp_fan_speed():
    """
    Uses nvidia-settings to get the current GPU temperature and fan speed. Returns a tuple of (temperature, fan_speed).
    """
    cmd = "nvidia-settings -q GPUCoreTemp -q GPUCurrentFanSpeed"
    cmd_output = subprocess.check_output(cmd, shell=True).decode("utf-8")
    logger.debug(cmd_output)
    match_temp = regex_coretemp.search(cmd_output)
    match_fan = regex_fanspeed.search(cmd_output)
    if not match_temp:
        raise ValueError("Could not parse temperature.")
    if not match_fan:
        raise ValueError("Could not parse fan speed.")
    return (int(match_temp.group(1)), int(match_fan.group(1)))


def compute_fan_speed(temp: int, temp_fan: list[tuple[int, int]]):
    """
    Given a temperature, compute the fan speed based on the parsed (soreted) temp_fan configuration. Will used the lower bound.
    """
    lower_fan = temp_fan[0][1] if temp >= temp_fan[0][0] else 0
    for t, fan in temp_fan:
        # first entry that is greater than temp
        if temp < t: 
            return lower_fan
        if temp >= t:
            lower_t = t
            lower_fan = fan
    logger.debug(f"Computed Fan Speed: {lower_fan}")
    return lower_fan

def set_fan_speed(current_fan: int, computed_fan:int):
    """
    Set the fan speed using nvidia-settings.
    """
    if abs(current_fan - computed_fan) > 5: 
        logger.info(f"Setting Fan Speed to {computed_fan}%")
        cmd = f"nvidia-settings -a GPUFanControlState=1 -a GPUTargetFanSpeed={computed_fan}"
        subprocess.check_output(cmd, shell=True)
    else:
        logger.info(f"Fan speed is already set to the correct value {current_fan}% ({computed_fan}%)")


if __name__ == "__main__":
    import sys

    config_file = sys.argv[1] if len(sys.argv) > 1 else CONFIG_FILE
    debug_level = sys.argv[2] if len(sys.argv) > 2 else "INFO"
    if debug_level == "DEBUG":
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
    logger.info(f"Opening config file: {config_file}")
    config = read_config(config_file)
    temp_fan = dict_to_ranges(config)

    while True:
        temp, fan = get_temp_fan_speed()
        logger.info(f"Current GPU Temperature is {temp}°C and Fan Speed is {fan}%")
        computed_fan = compute_fan_speed(temp, temp_fan)
        set_fan_speed(fan, computed_fan)
        time.sleep(30)
