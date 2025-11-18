<!-- SPDX-License-Identifier: MIT -->
<!-- SPDX-FileCopyrightText: Copyright 2025 Sam Blenny -->
# IRC Display Bot

CircuitPython IRC bot to show status notifications on a small dedicated screen.


## Set Up Raspberry Pi OS with IRC Server

First you need to set up a Raspberry Pi with Raspberry Pi OS. I prefer to use
the Raspberry Pi OS Lite version and to enable the SSH server so I can access
it remotely, but it doesn't really matter. You do you. Any vaguely recent model
of Raspberry Pi should work fine as `ngircd` will run on a potato. I'm using a
Raspberry Pi 3 Model B.

Once you have the Raspberry Pi up and running, you'll need to install and
configure the `ircd` IRC server. Don't worry. It's easy to set up.


### Official Pi OS Install Method

1. Follow the Raspberry Pi Foundation Getting Started instructions at
   https://www.raspberrypi.com/documentation/computers/getting-started.html
   to prepare a bootable disk image for Raspberry Pi OS

2. Continue following the instructions to set up a user account and network
   connection.

3. Enable SSH remote terminal access:
   https://www.raspberrypi.com/documentation/computers/remote-access.html#ssh


### Old School CLI Pi OS Install Method

If like me you prefer to use macOS commandline tools (`dd ...`) rather than the
Raspberry Pi Imager app, you might find it useful to know that the macOS Finder
can expand xz archives. Just open the archive file in the Finder.

Verify the SHA256 hash:
```
shasum -a 256 ~/Downloads/2025-10-01-raspios-trixie-arm64-lite.img.xz
```

Check for the correct disk file number for your sd card (be careful!):
```
diskutil list
...
```

Unmount the drive for your SD card (e.g. assume you found it was /dev/disk5):
```
diskutil unmountDisk /dev/disk5
```

Flash the disk image with `dd` (DANGER! double check drive number!):
```
sudo dd if=2025-10-01-raspios-trixie-arm64-lite.img of=/dev/rdisk5 bs=1M; sync
```


### CLI Config Option: raspi-config

If you do things according to the official instructions you can just use the
GUI config stuff. But, if you prefer to use the Lite OS version and CLI tools,
You'll need to run `sudo raspi-config` to configure your Pi.

```
sudo raspi-config
```

In raspi-config:
- System Options > Wireless LAN > set wifi country, SSID, and password
- Interface Options > SSH > enable ssh
- Localisation Options > Locales > select your locale, but also select
  `en_US.UTF-8` to avoid trouble with software that assumes `en_US` is present
- Localisation Options > Timezone > set your timezone
- Advanced Options > Expand Filesystem
- Advanced Options > Logging > select Volatile (to reduce SD card wear)
- Advanced Options > WLAN Power Save > select No (improve wifi reliability)


### Router Configuration for Reserve IP Address

Running a local IRC server on your home network will work better if your
Raspberry Pi has an IP address that doesn't change. For typical home wifi
routers that assign IP addresses with DHCP, it's usually possible to log into
the router admin console and configure IP address assignments. For example, my
router's DHCP assigns my computer a 192.168.0.x IP address with the gateway
192.168.0.1 and the router admin console is at `http://192.168.0.1`.

CAUTION: If you're unfamiliar with configuring routers, tread carefully. It's
possible to get yourself into trouble. You might want to seek help from an
experienced friend.

Wifi routers usually have a feature for assigning a static IP address to a
connected device. The name of the feature and the means of enabling it may vary
by router brand and model. For example, my router has a page for Connected
Devices, and each device has an "EDIT" button. If you click EDIT, it gives you
several choices including an option to pick between "DHCP" and "Reserved IP".
For me, picking the "Reserved IP" option for a Raspberry Pi device causes the
router to always assign it the same IP.

You might need to know the MAC address of your Raspberry Pi's Wifi interface.
You can check that from a terminal on the Raspberry Pi with the command:
```
ip address
```


### Check Pi's IP Address

So far, the instructions have been for a Pi with a keyboard and HDMI display.
To log into the Pi remotely by SSH, or to connect to its IRC server (once you
set one up), you will need to know the Pi's IP address. To check the IP
address, do:

```
ip address
```

Look for something like `191.168.0.100`. Probably the fourth number will be
something other than `100`, but the first three might be the same.


### Add SSH Authorized Keys

It's easier to log in remotely by SSH if you generate a key pair on your normal
computer and install a copy of the public key from that pair on the Pi.

For example:

1. On macOS, generate a keypair (or skip the first bit to use existing keys)
   and print a copy of the public key (`.ssh/id_ed25519.pub`):

   ```
   ssh-keygen -C macbook -t ed25519
   cat ~/.ssh/id_ed25519.pub
   ```

   If you select the option to protect your private key with a password, which
   is a good idea to do, you might want to configure SSH to store that password
   in your macOS login keychain. You can do that by editing `~/.ssh/config` on
   the mac to add the following lines:

   ```
   Host *
     UseKeychain yes
   ```

   Once you do that, you will probably be prompted for the private key's
   password once, when you first try to use it. After that first time, the
   login keychain should unlock the private key for you automatically.

2. On macOS, log into your Pi by SSH using password authentication using the
   IP address and username for your Pi. For example:

   ```
   ssh pi@192.168.0.100
   ```

3. Once you're in a Pi terminal using SSH, create a `.ssh` directory on the PI,
   then edit `.ssh/authorized_keys` and paste in your public key(s):

   ```
   mkdir -p ~/.ssh
   chmod 700 ~/.ssh
   nano ~/.ssh/authorized_keys
   # paste your mac's public key, then exit and save the file
   ```

4. On macOS, start a new Terminal window and try connecting to the Pi by SSH
   using your SSH keypair:

   ```
   ssh pi@192.168.0.100
   ```

   This may ask you for the password to unlock your private key the first time
   out. But, after that, assuming you set up `UseKeychain yes`, the key should
   unlock automatically.

5. [Optional] to make it even easier, you can add a line to your `/etc/hosts`
   file on the mac (e.g. `192.168.0.100  pi3b`), then you could do something
   like `ssh pi@pi3b`. CAUTION: Tread carefully with `sudo nano /etc/hosts` as
   editing mistakes there can cause trouble.


### Set Up Pi with IRC Server (motd, ngircd, etc)

This all assumes you're logged into the Pi over SSH or at its keyboard. Some of
these steps are optional aesthetic tweaks to modify default behaviors that I
personally find irritating. Maybe you don't care. In that case, feel free to
skip those steps.

1. Get updates and install useful packages including irssi and ngircd. When you
   install ngircd, you will have a working IRC server with default settings,
   bound to all your IP addresses (localhost and wifi):

   ```
   sudo apt update
   sudo apt upgrade
   sudo apt install figlet tio screen git vim irssi ngircd
   ```

2. (Optional) Replace annoying default SSH and ngircd motd login messages with
   a figlet hostname banner

   ```
   figlet -f small $(hostname) | sudo tee /etc/motd
   sudo sed -i 's/^uname/#uname/' /etc/update-motd.d/10-uname
   figlet -f small "Welcome to $(hostname)" | sudo tee /etc/ngircd/ngircd.motd
   sudo systemctl restart ngircd
   ```

3. (Optional) Configure the ngircd server to have a persistent `#sensors`
   channel, to have an operator user, and to disable some unnecessary default
   features.

   I've found these changes to be convenient when working on bots and bringing
   up a new sensor network installation with irc-display-bot,
   [serial-sensor-hub](https://github.com/samblenny/serial-sensor-hub), and a
   regular `irssi` chat window. Without the config changes, channel op status
   can get weird depending on which clients connect and disconnect in what
   order. The options stuff is just to make the protocol less chatty so my
   terminal doesn't fill up with useless log messages while working on bots.

   First, begin editing the ngircd config file with:

   ```
   sudo nano /etc/ngircd/ngircd.conf
   ```

   Scroll down to the end of the file, paste this stuff at the bottom, edit the
   operator name and password to whatever you like, then save the file and exit
   nano:

   ```
   [Channel]
   Name = #sensors
   Modes = nt

   [Operator]
   Name = admin
   Password = notMyRealPassword

   [Options]
   DNS = no
   Ident = no
   MorePrivacy = yes
   ScrubCTCP = yes
   ```

   Check that you didn't make any typos by running:

   ```
   ngircd --configtest
   ```

   If configtest didn't complain about anything, then restart ngircd:

   ```
   sudo systemctl restart ngircd
   ```

4. (Optional) Make systemd services to turn off the activity and power LEDs

   You can turn off the Raspberry Pi LEDs by echoing "none" into
   `/sys/class/leds/ACT/trigger` and `/sys/class/leds/PWR/trigger`, but the
   effect doesn't persist across a reboot. To make the change permanent, you
   can make a simple systemd service to run a shell command at boot. I like
   this so I don't get distracted by things blinking at me in my peripheral
   vision. Maybe you like the blinkenlights though. Your choice.

   First, create a new systemd service file:
   ```
   sudo nano /etc/systemd/system/disable-leds.service
   ```

   Paste this stuff into the file, then save it:
   ```
   [Unit]
   Description=Disable ACT LED
   After=network.target

   [Service]
   Type=oneshot
   ExecStart=/bin/sh -c 'echo none > /sys/class/leds/ACT/trigger; \
                         echo none > /sys/class/leds/PWR/trigger'

   [Install]
   WantedBy=multi-user.target
   ```

   Finally, enable the new service:
   ```
   sudo systemctl enable disable-leds.service
   ```
