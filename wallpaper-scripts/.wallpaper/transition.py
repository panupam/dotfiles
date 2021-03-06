#!/usr/bin/python3
"""Script for smooth wallpaper transitions in Xfce4."""
import atexit
import os
import subprocess
from argparse import ArgumentDefaultsHelpFormatter, ArgumentParser
from multiprocessing.dummy import Pool  # use threads instead of processes
from random import choice
from signal import SIGTERM, signal
from time import sleep

from PIL import Image
from Xlib.display import Display

from styles import apply_style


class WallpaperTransition:
    """Class for performing wallpaper transition using Xfce."""

    TMP_FMT = "/tmp/{}_wall_{}.jpg"  # format for temp files for the transition
    THR_LIMIT = 8  # thread limit for per-monitor transitions

    def __init__(self, img_dir, timeout, duration, fps, backup_pic=None):
        """Initialize the instance.

        Args:
            img_dir (str): Path to the directory containing the wallpapers
            timeout (int): The wait between two transitions
            duration (int): The duration of a transition
            fps (int): The FPS for a transition
            backup_pic (str): Path to a picture that will be applied when this
                script crashes

        """
        self.img_dir = img_dir
        self.timeout = timeout
        self.duration = duration
        self.fps = fps
        self.backup_pic = backup_pic

        # Apply the backup picture on exit
        atexit.register(self.set_backup)
        # Gracefully exit after applying the backup picture on SIGTERM
        signal(SIGTERM, lambda s, f: exit())

    @staticmethod
    def get_monitors():
        """Get information on the connected monitors.

        Returns:
            dict: The keys are the monitor names (eg. "eDP1") and the values
                are tuples of the monitor's resolution

        """
        display = Display()
        root = display.screen().root
        root.create_gc()
        resources = root.xrandr_get_screen_resources()._data

        monitors = {}

        for crtc in resources["crtcs"]:
            monitor = display.xrandr_get_crtc_info(
                crtc, resources["config_timestamp"]
            )._data
            for output in monitor["outputs"]:  # is connected
                info = display.xrandr_get_output_info(
                    output, resources["config_timestamp"]
                )._data
                monitors[info["name"]] = (monitor["width"], monitor["height"])

        return monitors

    @staticmethod
    def get_wallpaper(monitor_id):
        """Get the path to the current wallpaper of the given monitor."""
        cmd = [
            "xfconf-query",
            "--channel",
            "xfce4-desktop",
            "--property",
            f"/backdrop/screen0/monitor{monitor_id}/workspace0/last-image",
        ]

        try:
            proc = subprocess.run(
                cmd, capture_output=True, check=True, text=True
            )
        except subprocess.CalledProcessError:
            return None
        else:
            return proc.stdout.strip()

    @staticmethod
    def set_wallpaper(monitor_id, img_path):
        """Set the current wallpaper for the given monitor."""
        cmd = [
            "xfconf-query",
            "--channel",
            "xfce4-desktop",
            "--property",
            f"/backdrop/screen0/monitor{monitor_id}/workspace0/last-image",
            "--set",
            img_path,
        ]
        subprocess.Popen(cmd)

    @staticmethod
    def get_wall_style(monitor_id):
        """Get the style of the current wallpaper of the given monitor."""
        cmd = [
            "xfconf-query",
            "--channel",
            "xfce4-desktop",
            "--property",
            f"/backdrop/screen0/monitor{monitor_id}/workspace0/image-style",
        ]

        try:
            proc = subprocess.run(
                cmd, capture_output=True, check=True, text=True
            )
        except subprocess.CalledProcessError:
            return None
        else:
            return int(proc.stdout)

    def _choose_transition(self, monitor_id, exclude=None):
        """Choose the wallpaper for a transition."""
        available = [
            item
            for item in os.listdir(self.img_dir)
            if os.path.isfile(os.path.join(self.img_dir, item))
            and item != os.path.basename(exclude)
        ]
        if not available:
            return None
        new_wallp = os.path.join(self.img_dir, choice(available))
        return new_wallp

    def bg_transition(self, monitor_id):
        """Perform a transition into a randomly chosen wallpaper."""
        current = self.get_wallpaper(monitor_id)
        if current is None:  # failed to get wallpaper
            return

        # Avoid transitioning into the same wallpaper
        new = self._choose_transition(monitor_id, exclude=current)
        if new is None:  # failed to get a new wallpaper
            return

        wall_style = self.get_wall_style(monitor_id)
        if wall_style is None:  # failed to get wallpaper style
            return

        bg = apply_style(
            Image.open(current), self.monitors[monitor_id], wall_style
        )
        fg = apply_style(
            Image.open(new), self.monitors[monitor_id], wall_style
        )

        total_imgs = int(self.duration * self.fps)
        wait = self.duration / self.fps

        for i in range(1, total_imgs + 1):
            Image.blend(bg, fg, i / total_imgs).save(
                self.TMP_FMT.format(monitor_id, i)
            )

        # FPS and duration is used for this
        for i in range(1, total_imgs + 1):
            sleep(wait)
            self.set_wallpaper(monitor_id, self.TMP_FMT.format(monitor_id, i))
        self.set_wallpaper(monitor_id, new)

        for i in range(1, total_imgs + 1):
            os.remove(self.TMP_FMT.format(monitor_id, i))

    def set_backup(self):
        """Set the backup image on all connected monitors."""
        if self.backup_pic is None:
            return

        # Connected monitors may have changed
        self.monitors = self.get_monitors()
        args = [(monitor_id, self.backup_pic) for monitor_id in self.monitors]
        with Pool(min(self.THR_LIMIT, len(self.monitors))) as pool:
            pool.starmap(self.set_wallpaper, args)

    def loop(self):
        """Loop and perform transitions."""
        while True:
            self.monitors = self.get_monitors()
            with Pool(min(self.THR_LIMIT, len(self.monitors))) as pool:
                pool.map(self.bg_transition, self.monitors.keys())
            sleep(self.timeout)


def main(args):
    """Run the main program.

    Arguments:
        args (`argparse.Namespace`): The object containing the commandline
            arguments

    """
    wt = WallpaperTransition(
        args.img_dir,
        args.timeout,
        args.duration,
        args.fps,
        backup_pic=args.backup,
    )
    wt.loop()


if __name__ == "__main__":
    parser = ArgumentParser(
        description="XFCE Wallpaper Transition",
        formatter_class=ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "img_dir",
        metavar="ImgDir",
        type=str,
        help="the directory of the backgrounds you want to loop through",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=600,
        help="idle period (in seconds) between transitions",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=1.0,
        help="duration of one transition (in seconds)",
    )
    parser.add_argument(
        "--fps", type=int, default=30, help="FPS for the transition"
    )
    parser.add_argument(
        "--backup",
        type=str,
        help="the backup picture to revert to, if the program crashes",
    )
    main(parser.parse_args())
