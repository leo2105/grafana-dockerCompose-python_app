import pyds
import numpy as np

def add_line_to_display_meta(display_meta: pyds.NvDsDisplayMeta,
                             label: str,
                             color: tuple,
                             points: list,
                             x_limit: int=None,
                             y_limit: int=None) -> None:
    """Add a simple line to the display meta

    Args:
        display_meta (pyds.NvDsDisplayMeta): NvDsDisplayMeta of a frame
        label (str): Label to be added to the display
        color (tuple): Tuple with a rgba color. Ex.: (255,0,25,0.4) 
        points (list): List of lists (or tuples) with the point to create the line. Ex.: [[100,100],[700, 562]] 
        x_limit (int, optional): Maximum x-axis limit. Defaults to None.
        y_limit (int, optional): Maximum y-axis limit. Defaults to None.
    """
    for j in range(len(points) - 1):
        display_meta.num_lines += 1
        line_params = display_meta.line_params[display_meta.num_lines - 1]
        line_params.line_color.set(color[0], color[1], color[2], color[3])
        line_params.line_width = 8
        line_params.x1 = points[j][0]
        line_params.x2 = points[j+1][0]
        line_params.y1 = points[j][1]
        line_params.y2 = points[j+1][1]

    add_text_to_display_meta(display_meta, label, points[0][0], points[0][1], x_limit=x_limit, y_limit=y_limit)


def add_arrow_to_display_meta(display_meta: pyds.NvDsDisplayMeta,
                              label: str,
                              color: tuple,
                              arrow: list,
                              x_limit: int=None,
                              y_limit: int=None) -> None:
    """Add an arrow to the display meta

    Args:
        display_meta (pyds.NvDsDisplayMeta): NvDsDisplayMeta of a frame
        label (str): Label to be added to the display
        color (tuple): Tuple with a rgba color. Ex.: (255,0,25,0.4) 
        arrow (list): List of lists (or tuples) with the point to create the arrow. Ex.: [[100,100],[700, 562]] 
        x_limit (int, optional): Maximum x-axis limit. Defaults to None.
        y_limit (int, optional): Maximum y-axis limit. Defaults to None.
    """
    display_meta.num_arrows += 1

    arrow_params = display_meta.arrow_params[display_meta.num_arrows - 1]
    arrow_params.arrow_color.set(color[0], color[1], color[2], color[3])
    arrow_params.arrow_head = pyds.NvOSD_Arrow_Head_Direction.END_HEAD
    arrow_params.arrow_width = 8
    arrow_params.x1 = arrow[0][0]
    arrow_params.x2 = arrow[1][0]
    arrow_params.y1 = arrow[0][1]
    arrow_params.y2 = arrow[1][1]

    add_text_to_display_meta(display_meta, label, arrow[1][0], arrow[1][1], x_limit=x_limit, y_limit=y_limit)


def add_text_to_display_meta(display_meta: pyds.NvDsDisplayMeta,
                             label: str,
                             x_offset: int,
                             y_offset: int,
                             font_size: int = 20,
                             set_bg_clr: bool = 1,
                             text_color: tuple = (1.0, 1.0, 1.0, 1.0),
                             text_bg_clr: tuple = (0.0, 0.0, 0.0, 0.6),
                             x_limit: int=None,
                             y_limit: int=None) -> None:
    """Add a simple text to the display meta

    Args:
        display_meta (pyds.NvDsDisplayMeta): NvDsDisplayMeta of a frame
        label (str): Label to be added to the display
        x_offset (int): X-axis offset
        y_offset (int): Y-axis offset
        font_size (int, optional): Font size. Defaults to 20.
        set_bg_clr (bool, optional): True to use a background color. Defaults to 1.
        text_color (tuple, optional): RGBA color of the text. Defaults to (1.0, 1.0, 1.0, 1.0).
        text_bg_clr (tuple, optional): RGBA color of the background. Defaults to (0.0, 0.0, 0.0, 0.6).
        x_limit (int, optional): Maximum x-axis limit. Defaults to None.
        y_limit (int, optional): Maximum y-axis limit. Defaults to None.
    """
    display_meta.num_labels += 1
    text_params = display_meta.text_params[display_meta.num_labels - 1]

    if x_limit is not None:
        biggest_line = max(label.split("\n"))
        if x_offset > x_limit - (font_size * len(biggest_line)*0.8):
            x_offset = x_offset - (font_size * len(biggest_line)*0.8)
    if y_limit is not None:
        if y_offset > y_limit - (font_size * 2):
            y_offset = y_offset - (font_size * 2)

    text_params.display_text = label
    text_params.x_offset = int(x_offset)
    text_params.y_offset = int(y_offset)
    text_params.font_params.font_name = "Serif"
    text_params.font_params.font_size = font_size
    # set(red, green, blue, alpha)
    text_params.font_params.font_color.set(text_color[0], text_color[1], text_color[2], text_color[3])
    text_params.set_bg_clr = set_bg_clr
    # set(red, green, blue, alpha)
    text_params.text_bg_clr.set(text_bg_clr[0], text_bg_clr[1], text_bg_clr[2], text_bg_clr[3])


def get_random_rgba_color(alpha:float=0.4) -> tuple:
    """Create a random rgba color

    Args:
        alpha (float, optional): Alpha value. Defaults to 0.4.

    Returns:
        tuple: Tuple with a rgba color (r, g, b, a) 
    """
    color = np.random.rand(1,3)
    color = np.append(color, alpha)
    return tuple(color)
