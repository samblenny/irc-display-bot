# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: Copyright 2025 Sam Blenny
#
# See NOTES.md for documentation links and pinout info.
#
import re
import socketpool
import wifi


class IRCBot:
    def __init__(self, nick, chan, server, port=6667):
        self.rx_buf = bytearray(512)
        self.line_buf = bytearray(512)
        self.pool = socketpool.SocketPool(wifi.radio)
        self.sock = self.pool.socket()     # defaults to IP + TCP
        self.nick = nick
        self.chan = chan
        self.server = server
        self.port = port
        self._recv_line_iterator = None
        self.irc_re = re.compile(
            br'^((:\S+)\s+)?'      # optional prefix   (match group 2)
            br'(\S+)\s*'           # command or number (match group 3)
            br'(.*)'               # params            (match group 4)
        )

    def connect(self, timeout=30):
        self.sock.settimeout(timeout)
        try:
            self.sock.connect((self.server, self.port))
            self._recv_line_iterator = self._recv_line_gen()
            msg = (
                'NICK {0}\r\n'
                'USER {0} 0 * :{0}\r\n'
                'JOIN {1}\r\n'
                ).format(self.nick, self.chan)
            self.sock.sendall(msg.encode())
        except OSError as e:
            # Exceptions I've seen trigger this:
            # - OSError: [Errno 118] EHOSTUNREACH
            print('ERR connect: "%s", errno=%d', e, e.errno)
            return False
        return True

    def _recv_line_gen(self, timeout=1):
        # This generator wraps Socket.recv_into() to provide line buffering
        self.sock.settimeout(timeout)
        buf = self.rx_buf
        line = self.line_buf
        bufmv = memoryview(buf)
        linemv = memoryview(line)
        max_line = len(line)
        buf_start = 0
        line_end = 0
        while True:
            # Try to get some TCP bytes (maybe a full line, maybe less)
            try:
                size = self.sock.recv_into(buf)
            except OSError as e:
                # Exceptions I've seen trigger this:
                # - OSError: [Errno 116] ETIMEDOUT
                if e.errno == 116:
                    pass  # timeout is fine
                else:
                    print('ERR recv_into: "%s", errno=%d', e, e.errno)
                # ---
                yield None                    # no data yet -> yield nothing
                # ---
                continue
            # BEGIN full line parsing
            # Assume there may be multiple CRLF terminated lines in rx buffer
            # and that line buffer may already have some accumulated data...
            while (crlf := buf.find(b'\r\n', buf_start, size)) > -1:
                line_buf_space = max_line - line_end
                line_len = crlf - buf_start
                # Got a CRLF line ending
                if line_len < line_buf_space:
                    # Got newline and line will fit in the line buffer
                    line[line_end:line_end+line_len] = bufmv[buf_start:crlf]
                    line_end += line_len
                else:
                    # Got newline but line is too long, so truncate it
                    limit = min(0, max_line - line_end)
                    line[line_end:max_line] = bufmv[buf_start:buf_start+limit]
                    line_end = max_line
                # ---
                yield bytes(linemv[:line_end]).decode()       # Yield line
                # ---
                line_end = 0                       # Clear line buffer
                buf_start = crlf + 2               # Adjust rx buffer pointer
            if buf_start >= size:
                # RX buffer is empty, so start over with new packet
                buf_start = 0
                continue
            # END full line parsing
            # BEGIN partial line parsing
            line_buf_space = max_line - line_end
            part_len = size - buf_start
            if part_len < line_buf_space:
                # Partial line fits in line buffer -> copy it
                line[line_end:line_end+part_len] = bufmv[buf_start:size]
                line_end += part_len
            else:
                # Partial line is too long -> truncate it
                limit = min(0, max_line - line_end)
                line[line_end:max_line] = bufmv[buf_start:buf_start+limit]
                line_end += limit
            # Clear the RX buffer
            buf_start = 0
            # END partial line parsing

    def recv_line(self):
        # Return a line from the TCP stream buffer (includes auto-PONG)
        #
        # CAUTION!!! group(n) returns matches as strings, not type bytes.
        # If you want to use them as bytes, you'll need to do .encode().
        #
        it = self._recv_line_iterator
        if it and (line := next(it)):
            # Got a line, so parse it with regex match
            m = self.irc_re.match(line)
            prefix  = m.group(2)
            command = m.group(3)
            params  = m.group(4)
            return (prefix, command, params)
        return None

    def pong(self, params):
        # Send a PONG to keep the connection alive (params type is string)
        try:
            msg = 'PONG {}\r\n'.format(params)
            print(msg)
            self.sock.sendall(msg.encode())
        except OSError as e:
            print('ERR pong: "%s", errno=%d', e, e.errno)
