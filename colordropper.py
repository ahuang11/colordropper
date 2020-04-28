import os
from io import BytesIO
from urllib.request import urlopen

import numpy as np
import panel as pn
import xarray as xr
import holoviews as hv
import matplotlib.pyplot as plt
from holoviews.streams import Tap
from bokeh.models.tools import WheelZoomTool
from matplotlib.colors import LinearSegmentedColormap

pn.extension()
hv.extension('bokeh')
hv.renderer('bokeh').theme = 'caliber'

IMAGE_URL = ('https://img06.deviantart.net/2635/i/2010/170/c/f/'
             'night_and_day_wallpaper_by_seph_the_zeth.jpg')
IMAGE_EXT = os.path.splitext(IMAGE_URL)[1]

WHITE_SMOKE = '#f5f5f5'
DEFAULT_CMAP = 'RdBu_r'
NEW_LINE_INDENT = ',\n    '
HEXCODE = 'Hexcode'
RGB_1 = 'RGB (0 to 1)'
RGB_255 = 'RGB (0 to 255)'

STR_BOTH = 'stretch_both'
STR_WIDTH = 'stretch_width'
STR_HEIGHT = 'stretch_height'

EXAMPLE_CODE = """
```python
import xarray as xr
from matplotlib.colors import LinearSegmentedColormap

ds = xr.tutorial.open_dataset('air_temperature').isel(time=0)

colors = [{colors}]

cmap = LinearSegmentedColormap.from_list(
    'my_cmap', colors, N=len(colors))
ds['air'].plot(x='lon', y='lat', cmap=cmap)
```
""".strip()


def remove_white_borders(plot, element):
    p = plot.state
    p.border_fill_color = WHITE_SMOKE


def show_image(ds):
    shape = ds['R'].shape
    aspect = shape[1] / shape[0]

    wheel_zoom = WheelZoomTool(zoom_on_axis=False)

    image = (
        hv.RGB(ds, ['X', 'Y'], ['R', 'G', 'B'])
    ).opts(
        'RGB', default_tools=['pan', wheel_zoom, 'tap', 'reset'],
        active_tools=['tap', 'wheel_zoom'], xaxis=None, yaxis=None,
        aspect=aspect, responsive=True, hooks=[remove_white_borders],
    ).opts(toolbar='above')

    tap = hv.streams.Tap(source=image, x=shape[1], y=shape[0])
    tap.param.watch(tap_update, ['x', 'y'])
    return image


def read_data(input_obj, image_fmt, from_url):
    if from_url:
        content = urlopen(input_obj)
    else:
        content = BytesIO(input_obj)

    data = plt.imread(content, format=image_fmt)[::-1]
    pixelate_slider.end = int(max(data.shape) / 10)

    global base_ds
    base_ds = xr.Dataset({
        'R': (('Y', 'X'), data[..., 0]),
        'G': (('Y', 'X'), data[..., 1]),
        'B': (('Y', 'X'), data[..., 2]),
    })
    return base_ds


def process_input(event):
    input_obj = event.new
    from_url = isinstance(input_obj, str)

    if from_url:
        image_fmt = os.path.splitext(input_obj)[1]
    else:
        image_fmt = os.path.splitext(file_input.filename)[1]

    if image_fmt == '':
        image_fmt = None

    base_ds = read_data(input_obj, image_fmt, from_url)
    image_pane.object = show_image(base_ds)


def clamp(x):
    return int(max(0, min(x, 255)))


def rgb_to_hexcode(r, g, b, to_255=False):
    if to_255:
        r *= 255
        g *= 255
        b *= 255

    return '#{0:02x}{1:02x}{2:02x}'.format(
        clamp(r), clamp(g), clamp(b))


def hexcode_to_rgb(hexcode, norm=False):
    code = hexcode.lstrip('#')
    if norm:
        values = (round(int(code[i:i + 2], 16) / 255, 4) for i in (0, 2, 4))
    else:
        values = (int(code[i:i + 2], 16) for i in (0, 2, 4))
    return str(tuple(values))


def make_color_row(color):
    if embed_toggle.value and len(multi_select.options) > 0:
        value_str = f'<center>{color}</center>'
    else:
        value_str = ''

    if highlight_toggle.value:
        background = WHITE_SMOKE
    else:
        background = None

    swath = pn.Row(
        pn.pane.HTML(value_str, background=background, height=18,
                     sizing_mode=STR_WIDTH),
        background=color, margin=0, sizing_mode=STR_WIDTH
    )

    if divider_toggle.value:
        divider = pn.Spacer(
            width=1, margin=0,
            background=WHITE_SMOKE,
            sizing_mode=STR_HEIGHT
        )
        return pn.Row(swath, divider, margin=0)
    else:
        return swath


def initialize_example():
    base_ds = read_data(IMAGE_URL, IMAGE_EXT, True)
    image_pane.object = show_image(base_ds)


def update(options):
    options = [
        opt for opt in options
        if opt != '' and
        len(opt) == 7 and
        opt.startswith('#')
    ]
    num_options = len(options)

    multi_select.options = options
    text_input.value = ', '.join(options)

    if num_options == 0:
        options = [WHITE_SMOKE]

    color_row.objects = [make_color_row(opt) for opt in options]

    slider_update(None)


def pixelate_update(event):
    num_pixels = pixelate_slider.value
    # similar to ds.coarsen(x=10).mean() but parameterized
    coarse_ds = getattr(
        base_ds.coarsen(
            **{'X': num_pixels, 'Y': num_pixels}, boundary='pad'
        ), pixelate_group.value.lower()
    )().astype(int)
    image_pane.object = show_image(coarse_ds)


def slider_update(event):
    options = multi_select.options.copy()

    num_options = len(options)
    if num_slider.value < num_options:
        num_slider.value = num_options
    num_slider.start = num_options

    if num_options == 1:
        options *= 2

    if num_options > 0:
        num_colors = num_slider.value
        interp_cmap = LinearSegmentedColormap.from_list(
            'interp_cmap', options, num_colors)
        interp_colors = [rgb_to_hexcode(*interp_cmap(i)[:3], to_255=True)
                         for i in np.arange(interp_cmap.N)]
    else:
        interp_cmap = DEFAULT_CMAP
        interp_colors = options

    plot_pane.object = process_plot(interp_cmap)
    if output_group.value == HEXCODE:
        color_str = NEW_LINE_INDENT.join(f"'{opt}'" for opt in interp_colors)
    elif output_group.value == RGB_255:
        color_str = NEW_LINE_INDENT.join(hexcode_to_rgb(opt)
                                         for opt in interp_colors)
    elif output_group.value == RGB_1:
        color_str = NEW_LINE_INDENT.join(hexcode_to_rgb(opt, norm=True)
                                         for opt in interp_colors)

    color_str = '\n\t' + color_str + '\n'
    code_markdown.object = EXAMPLE_CODE.format(colors=color_str)


def tap_update(x=0, y=0):
    previous_selections.append(multi_select.options)
    ds = image_pane.object.data
    try:
        sel_ds = ds.isel(X=round(x.new), Y=round(y.new))
        hexcode = rgb_to_hexcode(sel_ds['R'], sel_ds['G'], sel_ds['B'])
        options = multi_select.options + [hexcode]
        update(options)
    except (AttributeError, IndexError) as e:
        print(e)


def remove_update(event):
    previous_selections.append(multi_select.options)
    options = [v for v in multi_select.options if v not in multi_select.value]
    update(options)


def undo_update(event):
    options = previous_selections.pop(-1)
    update(options)


def clear_update(event):
    previous_selections.append(multi_select.options)
    update([])


def toggle_update(event):
    update(multi_select.options)


def text_input_update(event):
    options = [color.strip() for color in event.new.split(',')]
    update(options)


def process_plot(cmap):
    return hv_plot.opts(cmap=cmap)

# Initialize top side widgets

horiz_spacer = pn.layout.HSpacer()

random_colors = [
    f'#{integer:06x}' for integer in
    np.random.randint(0, high=0xFFFFFF, size=9)
]
color_box = pn.GridBox(*[
    pn.pane.HTML(background=random_colors[i],
                 width=10, height=10, margin=1)
    for i in range(9)
], ncols=3, margin=(15, 0))

title_markdown = pn.pane.Markdown(
    '# <center>ColorDropper</center>\n', margin=(5, 15, 0, 15))
subtitle_markdown = pn.pane.Markdown(
    '### <center>(an online eyedropper tool)</center>', margin=(15, 0, 0, 0)
)
caption_markdown = pn.pane.Markdown(
    '<center>To use, paste an image url or click '
    'Choose File" to upload an image, then click on the image '
    'to get a hexcode for that clicked point!</center>\n<center>'
    '*<a href="https://github.com/ahuang11/colordropper">Source Code</a> | '
    '<a href="https://github.com/ahuang11/">Author\'s GitHub</a>*',
    sizing_mode=STR_WIDTH, margin=0
)

# Create top side layout

title_row = pn.Row(
    horiz_spacer,
    color_box,
    title_markdown,
    subtitle_markdown,
    horiz_spacer,
    sizing_mode=STR_WIDTH,
    margin=(5, 0, -15, 0))

top_layout = pn.WidgetBox(
    title_row,
    caption_markdown,
    sizing_mode=STR_WIDTH,
    margin=(5, 205)
)

# Initialize left side widgets

url_input = pn.widgets.TextInput(placeholder='Enter an image url here!',
                                 margin=(15, 10, 5, 10))
file_input = pn.widgets.FileInput(accept='image/*')

pixelate_group = pn.widgets.RadioButtonGroup(
    options=['Mean', 'Min', 'Max'], margin=(15, 10, 5, 10))

pixelate_slider = pn.widgets.IntSlider(
    name='Number of pixels to aggregate', start=1, end=100, step=1,
    sizing_mode=STR_WIDTH)
pixelate_slider.callback_policy = 'throttled'

text_input = pn.widgets.TextInput(
    placeholder='Click on image above to see values or add '
                'comma separated hexcodes here!', margin=(10, 10, 0, 10))

divider_toggle = pn.widgets.Toggle(name='Show Divider',
                                   sizing_mode=STR_WIDTH)
embed_toggle = pn.widgets.Toggle(name='Embed Values', value=True,
                                 sizing_mode=STR_WIDTH)
highlight_toggle = pn.widgets.Toggle(name='Highlight Text',
                                     sizing_mode=STR_WIDTH)

previous_selections = []
multi_select = pn.widgets.MultiSelect(options=[], sizing_mode=STR_BOTH)
remove_button = pn.widgets.Button(name='Remove', button_type='warning',
                                  width=280)
undo_button = pn.widgets.Button(name='Undo', button_type='primary',
                                width=280)
clear_button = pn.widgets.Button(name='Clear', button_type='danger',
                                 width=280)
image_pane = pn.pane.HoloViews(
    sizing_mode='scale_both', align='center',
    max_height=250, margin=(0, 3))

initialize_example()

# Link left side objects

url_input.param.watch(process_input, 'value')
file_input.param.watch(process_input, 'value')

pixelate_group.param.watch(pixelate_update, 'value')
pixelate_slider.param.watch(pixelate_update, 'value')

text_input.param.watch(text_input_update, 'value')
divider_toggle.param.watch(toggle_update, 'value')
embed_toggle.param.watch(toggle_update, 'value')
highlight_toggle.param.watch(toggle_update, 'value')

remove_button.on_click(remove_update)
undo_button.on_click(undo_update)
clear_button.on_click(clear_update)

# Create left side layout

slider_row = pn.Row(pixelate_group, pixelate_slider,
                    sizing_mode=STR_WIDTH, margin=(0, 6))
color_row = pn.Row(make_color_row(WHITE_SMOKE), margin=(0, 11, 10, 11),
                   sizing_mode=STR_WIDTH)
toggles_row = pn.Row(divider_toggle, embed_toggle, highlight_toggle,
                     sizing_mode=STR_WIDTH)
buttons_col = pn.Column(remove_button, undo_button, clear_button)
select_row = pn.Row(multi_select, buttons_col, sizing_mode=STR_WIDTH,
                    margin=(0, 0, 10, 0))

left_layout = pn.WidgetBox(
    url_input,
    file_input,
    image_pane,
    slider_row,
    text_input,
    color_row,
    toggles_row,
    select_row,
    sizing_mode=STR_BOTH
)

# Create right side widgets

output_group = pn.widgets.RadioButtonGroup(
    options=[HEXCODE, RGB_255, RGB_1], margin=(15, 10, 5, 10))
num_slider = pn.widgets.IntSlider(
    name='Number of colors', start=2, end=255, step=1, value=1,
    margin=(10, 15))
data = np.load('tmp_ds.npy')[::-1]
plot_da = xr.DataArray(data, name='tmp', dims=('y', 'x'))
hv_plot = hv.Image(plot_da, ['x', 'y'], ['tmp']).opts(
    responsive=True, toolbar=None, colorbar=True, default_tools=[],
    colorbar_opts={'background_fill_color': WHITE_SMOKE}, cmap=DEFAULT_CMAP,
    xaxis=None, yaxis=None, hooks=[remove_white_borders], aspect='equal')
plot_pane = pn.pane.HoloViews(
    min_height=300, max_height=500, object=hv_plot, sizing_mode='scale_both',
    align='center', margin=(0, 3))
code_markdown = pn.pane.Markdown(
    EXAMPLE_CODE.format(colors=''),
    sizing_mode=STR_WIDTH, margin=(0, 15, 0, 15))

# Link right side objects

output_group.param.watch(toggle_update, 'value')
num_slider.param.watch(slider_update, 'value')

# Create right side layout

right_layout = pn.WidgetBox(
    output_group,
    num_slider,
    plot_pane,
    code_markdown,
    sizing_mode=STR_BOTH
)

# Create bottom side layout

bottom_layout = pn.Row(
    left_layout,
    right_layout,
    sizing_mode=STR_WIDTH,
    margin=(0, 200)
)

# Create dashboard

layout = pn.Column(
    top_layout,
    bottom_layout,
    sizing_mode=STR_BOTH,
    margin=0
)
layout.servable(title='ColorDropper')
