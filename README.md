# Svent XFCE

Version 0.5.1 uses an independent XFCE layout with a full-width dark top panel,
searchable Whisker Applications menu, Firefox ESR, file manager, XFCE Terminal,
three miniature workspaces, IP, tray, audio, power and a HH:MM clock.
Super and Super+D open the searchable menu. Desktop icons are disabled.

`panel/profile.json` is the panel source. `panel/generate.py` generates its XML
at build time. No autostart rebuilds or restarts the panel.
`panel/apply.py` explicitly reloads panel properties; `--restore` restores its
previous properties. It does not change wallpaper or terminal settings.

IP polling uses milliseconds: 2000 means two seconds. Interface priority is
unchanged. Clicking the icon or address copies the current selected IP.
SVENT_INTERFACE optionally fixes an interface. Individual ip commands time out.

Wallpapers stay in `/usr/share/backgrounds/svent/`, supplied by svent-artwork.
The XFCE xinitrc prepares monitor properties before starting the desktop and
preserves readable custom backgrounds. It removes the old wallpaper wait loop.
Desktop Backgrounds opens native settings; choose the landscape or portrait
folder there. The explicit `svent-xfce-wallpaper` command calls core's selector.
No files from core, BSPWM or artwork are modified.

Normal terminals use styled XFCE Terminal. Catalog tools retain xterm, with
JetBrains Mono and Xresources styling. Logos remain pending in artwork.

Build on Linux with `dpkg-buildpackage -b -us -uc`. Install with XFCE logged out
so xfconfd cannot overwrite deployed XML. New settings take effect next login.
Validate rendering, wallpaper startup and pointer behavior in the target VM.
