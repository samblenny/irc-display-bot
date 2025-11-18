# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: Copyright 2025 Sam Blenny
#
# See NOTES.md for documentation links and pinout info.
#
import board
from microcontroller import cpu
from micropython import const
import os
import time
import wifi

from sb_chardisplay import CharDisplay
from sb_ircbot import IRCBot


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


def wifi_connect():
    # Try to connect to wifi
    if WIFI_SSID and WIFI_PASSWORD:
        try:
            wifi.radio.connect(ssid=WIFI_SSID, password=WIFI_PASSWORD)
            ip = wifi.radio.ipv4_address
            return ip
        except ConnectionError as e:
            print(e)
    return None


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

    # Wrap the radio stuff in a big retry loop
    RETRY_S = const(5)
    RETRY_S_MAX = const(180)
    while True:

        # Wifi Up
        wifi_retry = RETRY_S
        while True:
            cd.show_msg("WiFi Connect...")
            wifi.radio.enabled = True
            ip = wifi_connect()
            if ip:
                cd.show_msg('WiFi IP is %s' % ip)
                break
            else:
                # Wifi problem: sleep for a bit then try again
                cd.show_msg('Wifi Down')
                wifi.radio.enabled = False
                time.sleep(wifi_retry)
                wifi_retry = min(RETRY_S_MAX, wifi_retry * 2)
                continue

        # IRC Up
        irc_retry = RETRY_S
        cd.show_msg("IRC Connect...")
        radio = wifi.radio
        with IRCBot(IRC_NICK, IRC_CHAN, IRC_SERVER, port=6667) as irc:
            while radio.connected and not irc.connected:
                # If initial connect failed, retry with exponential backoff
                time.sleep(irc_retry)
                irc_retry = min(RETRY_S_MAX, irc_retry * 2)
                irc.connect()

            irc.register()

            # Main IRC bot loop
            irc_retry = RETRY_S
            while radio.connected and irc.connected:
                line = irc.recv_line()
                if line is None:
                    time.sleep(0.001)
                    continue
                (prefix, cmd, params) = line
                print(cmd, params)
                if cmd == '433':
                    # - 433 * <nick> :Nickname already in use
                    cd.show_msg('IRC: Nick in use')
                    irc.registered = False
                    time.sleep(irc_retry)
                    irc_retry = min(RETRY_S_MAX, irc_retry * 2)
                    irc.register()
                elif cmd == 'PING':
                    irc.pong(params)
                elif cmd == 'JOIN':
                    my_nick = ':%s!' % IRC_NICK
                    if prefix and prefix.find(my_nick) == 0:
                        # Only notify when I join. Ignore other users.
                        # This trims the leading ':' off the channel name
                        cd.show_msg('Joined %s' % params[1:])
                elif cmd == '332':
                    # Channel topic notification for JOIN
                    # Typical cmd+params format: `332 tftbot #sensors :!pre /`
                    nickchan = '%s %s :' % (IRC_NICK, IRC_CHAN)
                    pre = '!pre '
                    if not params.startswith(nickchan):
                        continue
                    text = params[len(nickchan):]
                    if text.startswith(pre):
                        # bot mode for displaying preformatted text with
                        # dynamically slectable line delimeters: first char of
                        # first word after the `!pre` is the delimeter that
                        # gets replaced with line breaks
                        text = text[len(pre):]
                        if len(text) >= 1:
                            delim = text[0]
                            text = text[1:].replace(delim, '\n')
                            cd.show_msg(text, wrap='pre')
                    else:
                        # Default to hard wrapping lines
                        cd.show_msg(text, wrap='hard')
                elif cmd == 'TOPIC':
                    # Channel topic notifiction after JOIN
                    # Typical cmd+param format: `TOPIC #sensors :!pre /...`
                    chan = '%s :' % IRC_CHAN
                    pre = '!pre '
                    if not params.startswith(chan):
                        continue
                    text = params[len(chan):]
                    if text.startswith(pre):
                        # bot mode for displaying preformatted text with
                        # dynamically slectable line delimeters: first char of
                        # first word after the `!pre` is the delimeter that
                        # gets replaced with line breaks
                        text = text[len(pre):]
                        if len(text) >= 1:
                            delim = text[0]
                            text = text[1:].replace(delim, '\n')
                            cd.show_msg(text, wrap='pre')
                    else:
                        # Default to hard wrapping lines
                        cd.show_msg(text, wrap='hard')

# ---
# Main entry point
# ---
run()
