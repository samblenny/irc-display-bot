# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: Copyright 2025 Sam Blenny
#
# See NOTES.md for documentation links and pinout info.
#
import atexit
import board
import displayio
from fourwire import FourWire
import terminalio

from adafruit_display_text import label
from adafruit_ili9341 import ILI9341


class CharDisplay:
    def __init__(self, width=16):
        # Try to initialize 2.8" TFT display shield with ILI9341 chip
        displayio.release_displays()
        spi = board.SPI()
        tft_cs = board.D10
        tft_dc = board.D9
        display_bus = FourWire(spi, command=tft_dc, chip_select=tft_cs)
        display = ILI9341(display_bus, width=320, height=240,
            rotation=180, auto_refresh=False)
        group = displayio.Group()
        display.root_group = group
        display.refresh()
        # System status textbox: scale=1, one line, very top of display
        status = label.Label(font=terminalio.FONT, scale=1, color=0x80ef00)
        status.anchor_point = (1, 0)
        status.anchored_position = (316, 4)
        status.line_spacing = 1.0  # default is 1.25
        group.append(status)
        # IRC topic textbox: scale=3, 6 lines, this is for IRC notifications
        topic = label.Label(font=terminalio.FONT, scale=3, color=0xefef00)
        topic.anchor_point = (0, 0)
        topic.anchored_position = (8, 16)
        topic.line_spacing = 1.0  # default is 1.25
        group.append(topic)
        # Set an atexit handler to release the display once code.py
        # ends. This is an aesthetic filter to prevent CircuitPython's
        # supervisor from hijacking the display to show its own stuff.
        def atexit_shutdown_display():
            try:
                status.text = 'OFFLINE'
                display.refresh()
                displayio.release_displays()
            except AttributeError:
                pass

        atexit.register(atexit_shutdown_display)
        self.display = display
        self.status = status
        self.topic = topic
        self.width = width

    def hard_wrap(self, text):
        w = self.width
        return '\n'.join([text[i:i+w] for i in range(0, len(text), w)])

    def word_wrap(self, text):
        # Format a string to fit on a narrow screen by word-wrapping at spaces
        w = self.width
        lines = []
        start = 0
        prev_space = 0
        for _ in range(len(text)):
            space = text.find(' ', start)
            if len(text) - start <= w:
                # All the remaining text fits in one line without breaking
                lines.append(text[start:])
                start = len(text)
                break
            elif space == -1 or space - start > w:
                # No space in the first width characters, so hard wrap
                lines.append(text[start:start+w])
                start += w
            else:
                # There's at least one space suitable for a line break
                for _ in range(len(text)):
                    next_space = text.find(' ', space + 1)
                    if next_space == -1:
                        break
                    elif next_space - start <= w + 1:
                        space = next_space
                    else:
                        break
                lines.append(text[start:space])
                start = space + 1
        if start < len(text):
            lines.append(text[start:])
        return '\n'.join(lines)

    def set_status(self, txt):
        # Show the message text the top status line
        print("status =", txt)
        self.status.text = txt
        self.display.refresh()

    def set_topic(self, txt, wrap=None):
        # Show the message text in the 6x16 character display IRC topic area
        print("topic =", txt)
        if wrap == 'hard':
            wrapped = self.hard_wrap(txt)
        elif wrap == 'word' or wrap is None:
            wrapped = self.word_wrap(txt)
        elif wrap == 'pre':
            wrapped = txt
        self.topic.text = wrapped
        self.display.refresh()
