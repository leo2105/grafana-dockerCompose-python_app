################################################################################
# Copyright (c) 2019-2020, NVIDIA CORPORATION. All rights reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.  IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.
################################################################################

import gi
import sys
import ctypes
import platform
import time
from datetime import timezone, datetime
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib

def bus_call(bus: Gst.Bus, message: Gst.Message, loop: GLib.MainLoop) -> bool:
    """Handle message to the bus of a pipeline.

    Args:
        bus (Gst.Bus): Main pipeline's bus
        message (str): Message received from the bus
        loop (GLib.MainLoop): Main event loop of the application

    Returns:
        bool: Always True to keep the callback alive.
    """
    t = message.type
    if t == Gst.MessageType.EOS:
        sys.stdout.write("End-of-stream\n")
        #loop.quit()
    elif t==Gst.MessageType.WARNING:
        err, debug = message.parse_warning()
        #sys.stderr.write("Warning: %s: %s\n" % (err, debug))
    elif t == Gst.MessageType.ERROR:
        err, debug = message.parse_error()
        sys.stderr.write("Error: %s: %s\n" % (err, debug))
        #loop.quit()
    elif t in [Gst.MessageType.TAG]:
        pass
    else: # just report
        # sys.stderr.write(f"Warning: {message}}\n"
        now = datetime.now(timezone.utc).astimezone().isoformat()
        #sys.stderr.write('{} Warning: {} {}: {}\n'.format(now,
        #        Gst.MessageType.get_name(message.type), message.src.name,
        #        message.get_structure().to_string() ) )
    return True

def is_aarch64() -> bool:
    """Return true if plataform is ARM64.

    Returns:
        bool: True if plataform is ARM64
    """
    return platform.uname()[4] == 'aarch64'

sys.path.append('/opt/nvidia/deepstream/deepstream/lib')


def valid_color(color_tuple: tuple) -> bool:
    """Check if a given tuple has a valid rgba color.

    Args:
        color (tuple): Rgba color tuple. Ex.: (255,255,0,255)

    Returns:
        bool: True if the tuple is a valid rgba color
    """
    if type(color_tuple) is not tuple or len(color_tuple) != 4:
        return False
    
    for i in range(3):
        if int(color_tuple[i]) < 0 or int(color_tuple[i]) > 255:
            return False

    if color_tuple[3]: # if rgbA
        if color_tuple[3] < 0 or color_tuple[3] > 1:
            return False
    return True


def valid_line_length(length: int) -> bool:
    """Check if a given line length is valid.

    Args:
        length (int): Line length in pixels. Ex.: 10

    Returns:
        bool: True if the line length is valid
    """
    if type(length) is not int or length < 1:
            return False
    return True


class GetFps:
    """Handle FPS counting of a single stream in the main pipeline."""
    def __init__(self,stream_id: int) -> None:
        """
        Args:
            stream_id (int): Internal ID of the stream in the main pipeline
        """
        self.start_time=time.time()
        self.is_first=True
        self.frame_count=0
        self.stream_id=stream_id

    def get_fps(self) -> float:
        """Get the median framerate in frames per second (FPS) of the stream based on frame count since the last time it was update

        Returns:
            float: Framerate in frames per second (FPS) of the stream
        """
        end_time=time.time()
        deltat = end_time-self.start_time
        fps = float(self.frame_count)/deltat
        self.frame_count=0
        self.start_time=end_time

        return fps

    def increment_frame_count(self) -> None:
        """Increment frame count of the stream. Need to be called everytime there's a new buffer with valid frame."""
        if(self.is_first):
            self.start_time=time.time()
            self.is_first=False
        self.frame_count=self.frame_count+1