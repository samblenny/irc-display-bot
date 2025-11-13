# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: Copyright 2025 Sam Blenny
#
# See NOTES.md for documentation links and pinout info.
#
import board
from microcontroller import cpu
from micropython import const
import os
import wifi

from sb_CharDisplay import CharDisplay
from sb_IRCBot import IRCBot


# ---------------------------------------------------------------------------
# Options for settings.toml
# - `ILI9341_DISPLAY = 1` use 2.8" TFT display shield with ILI9341 chip
# - `WIFI_SSID = "your ssid"` set the SSID to use for your wifi
# - `WIFI_PASSWORD = "the password"` set password for your wifi
# - `IRC_SERVER = "<some IP address>"` set IP address for your IRC server
# - `IRC_NICK = "<nickname>"` set nickname to use for your IRC server
#
ILI9341_DISPLAY = False
if (val := os.getenv("ILI9341_DISPLAY")) is not None:
    ILI9341_DISPLAY = bool(val)
WIFI_SSID = None
if (val := os.getenv("WIFI_SSID")) is not None:
    WIFI_SSID = str(val)
WIFI_PASSWORD = None
if (val := os.getenv("WIFI_PASSWORD")) is not None:
    WIFI_PASSWORD = str(val)
IRC_SERVER = None
if (val := os.getenv("IRC_SERVER")) is not None:
    IRC_SERVER = str(val)
IRC_NICK = None
if (val := os.getenv("IRC_NICK")) is not None:
    IRC_NICK = str(val)
IRC_CHAN = None
if (val := os.getenv("IRC_CHAN")) is not None:
    IRC_CHAN = str(val)
# ---------------------------------------------------------------------------


def print_settings_banner():
    # Print startup banner showing if settings.toml is missing something
    heading = '# === IRC Dashboard Gadget Settings ==='
    m = 'missing'
    print()
    print(heading)
    print('# ILI9341_DISPLAY = %d' % ILI9341_DISPLAY)
    print('# WIFI_SSID: [%s]' % (m if WIFI_SSID is None else 'ok'))
    print('# WIFI_PASSWORD: [%s]' % (m if WIFI_PASSWORD is None else 'ok'))
    print('# IRC_SERVER: [%s]' % (m if IRC_SERVER is None else 'ok'))
    print('# IRC_NICK: [%s]' % (m if IRC_NICK is None else 'ok'))
    print('# IRC_CHAN: [%s]' % (m if IRC_CHAN is None else 'ok'))
    print('# ' + ('=' * (len(heading)-2)))


def wifi_connect(retries=5):
    # Try to connect to wifi
    if WIFI_SSID and WIFI_PASSWORD:
        for _ in range(retries):
            try:
                wifi.radio.connect(ssid=WIFI_SSID, password=WIFI_PASSWORD)
                ip = wifi.radio.ipv4_address
                return ip
            except ConnectionError as e:
                print(e)
    return False


def run():
    # This has the main program logic. Putting these things inside a function
    # helps force me to avoid spaghetti code. When lots of stuff lives in the
    # global namespace, it's too easy to write functions that unintentionally
    # reference global variables.

    print_settings_banner()
    cd = CharDisplay()

    # Reduce CPU frequency so the board runs cooler. The default ESP32-S3
    # default frequency is 240 MHz. To avoid messing up time.monotonic(), don't
    # attempt to set this below 80 MHz.
    if 'esp32s3' in board.board_id:
        cpu.frequency = 80_000_000

    # Wifi Up
    cd.show_msg("Connecting...")
    ip = wifi_connect()
    if ip:
        cd.show_msg('Connected as {}'.format(ip), hardwrap=False)
    else:
        cd.show_msg('Wifi Error Check Settings', hardwrap=False)

    # IRC Up
    # TODO: Handle Possible Connect Errors:
    # - 433 * tftbot :Nickname already in use
    print("Opening TCP connection to IRC server")
    irc = IRCBot(IRC_NICK, IRC_CHAN, IRC_SERVER, port=6667)
    ok = irc.connect()

    # Main loop
    while True:
        while (line := irc.recv_line()) is not None:
            (prefix, cmd, params) = line
            print(cmd, params)
            if cmd == '433':
                cd.show_msg('IRC: Nick in use')
            elif cmd == 'PING':
                irc.pong(params)
            elif cmd == 'JOIN':
                cd.show_msg('Joined %s' % params[1:])    # skip leading ':'
            elif cmd == 'PRIVMSG':
                # For messages, strip the channel then show the rest.
                # Typical params format is like: `#channel :blah blah blah`
                if (start := params.find(':')) > -1:
                    cd.show_msg(params[start+1:])


# ---
# Main entry point
# ---
run()
