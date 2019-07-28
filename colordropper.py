from io import BytesIO

import PIL
import requests
import numpy as np
import panel as pn
import xarray as xr
import holoviews as hv
from holoviews.streams import Tap
from bokeh.models import HoverTool, CustomJSHover

hv.extension('bokeh')
pn.extension()


EXAMPLE_CODE = """
```
import xarray as xr
import hvplot.xarray
from matplotlib.colors import LinearSegmentedColormap

da = xr.tutorial.open_dataset('air_temperature').isel(time=0)['air']
colors = {colors}

# matplotlib
cmap = LinearSegmentedColormap.from_list('custom_colormap', colors, N=len(colors))
da.plot(x='lon', y='lat', cmap=cmap)

# hvplot
da.hvplot('lon', 'lat').opts(cmap=cmap)
```
""".strip()


def process_image(content):
    image = PIL.Image.open(BytesIO(content))
    data = np.array(image)[::-1]
    shape = data.shape
    aspect = data.shape[1] / data.shape[0]

    global ds
    ds = xr.Dataset({
        'R': (('Y', 'X'), data[..., 0]),
        'G': (('Y', 'X'), data[..., 1]),
        'B': (('Y', 'X'), data[..., 2]),
    })

    image = (
        hv.Image(ds, ['X', 'Y'], ['R', 'G', 'B']) *
        hv.RGB(ds, ['X', 'Y'], ['R', 'G', 'B'])
    ).opts(
        'Image', default_tools=['pan', 'wheel_zoom', 'tap', 'reset'],
        active_tools=['tap', 'wheel_zoom'], xaxis='bare', yaxis='bare',
        aspect=aspect, alpha=0, responsive=True, cmap='RdBu_r',
    ).opts('RGB', default_tools=['pan', 'wheel_zoom', 'tap', 'reset'],
           responsive=True)

    tap = hv.streams.Tap(source=image, x=shape[1] / 2, y=shape[0] / 2)
    tap.param.watch(tap_update, ['x', 'y'])
    return image
    

def read_file(event):
    pane.object = process_image(event.new)


def clamp(x):
    return int(max(0, min(x, 255)))


def rgb_to_hexcode(r, g, b):
    return '#{0:02x}{1:02x}{2:02x}'.format(
        clamp(r), clamp(g), clamp(b))


def make_color_box(color):
    if value_toggle.value:
        value_str = f'<center>{color}</center>'
    else:
        value_str = ''

    if highlight_toggle.value:
        background = 'whitesmoke'
    else:
        background = None

    swath = pn.Row(
        pn.pane.HTML(value_str, background=background,
                     sizing_mode='stretch_width', height=18),
        background=color, margin=0, sizing_mode='stretch_width'
    )

    if divider_toggle.value:
        divider = pn.Spacer(
            width=1, margin=0,
            sizing_mode='stretch_height',
            background='whitesmoke'
        )
        return pn.Row(swath, divider, margin=0)
    else:
        return swath


def update(options):
    options = [opt for opt in options if opt != '']
    
    multi_select.options = options
    text_input.value = ', '.join(options)

    if len(options) == 0:
        options = ['whitesmoke']
    row.objects = [make_color_box(opt) for opt in options]

    markdown.object = EXAMPLE_CODE.format(colors=options)


def tap_update(x, y):
    previous_selections.append(multi_select.options)
    ds_sel = ds.isel(X=round(x.new), Y=round(y.new))
    hexcode = rgb_to_hexcode(ds_sel['R'], ds_sel['G'], ds_sel['B'])
    options = multi_select.options + [hexcode]
    update(options)


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


image_url = ('https://img06.deviantart.net/2635/i/2010/170/c/f/'
             'night_and_day_wallpaper_by_seph_the_zeth.jpg')
content = requests.get(image_url).content

previous_selections = []
multi_select = pn.widgets.MultiSelect(options=[], sizing_mode='stretch_both')
remove_button = pn.widgets.Button(name='Remove', button_type='warning')
undo_button = pn.widgets.Button(name='Undo', button_type='primary')
clear_button = pn.widgets.Button(name='Clear', button_type='danger')
divider_toggle = pn.widgets.Toggle(name='Show Divider')
value_toggle = pn.widgets.Toggle(name='Embed Values')
highlight_toggle = pn.widgets.Toggle(name='Highlight Text')
text_input = pn.widgets.TextInput()

file_input = pn.widgets.FileInput()
pane = pn.pane.HoloViews(process_image(content),
                         min_height=350, min_width=350,
                         sizing_mode='scale_both')
markdown = pn.pane.Markdown(EXAMPLE_CODE.format(colors=[]),
                            sizing_mode='scale_both',
                            margin=(5, 10))

remove_button.on_click(remove_update)
undo_button.on_click(undo_update)
clear_button.on_click(clear_update)

divider_toggle.param.watch(toggle_update, 'value')
value_toggle.param.watch(toggle_update, 'value')
highlight_toggle.param.watch(toggle_update, 'value')

text_input.param.watch(text_input_update, 'value')

file_input.param.watch(read_file, 'value')

buttons = pn.Column(remove_button, undo_button, clear_button)
toggles = pn.Column(divider_toggle, value_toggle, highlight_toggle)
widgetbox = pn.Row(multi_select, buttons, toggles)
row = pn.Row(make_color_box('whitesmoke'),
             sizing_mode='stretch_width', margin=(5, 10))
layout = pn.Column(file_input, widgetbox, row, text_input, pane, markdown,
                   sizing_mode='scale_both', max_width=1000,
                   min_height=350, min_width=350)

layout.servable(title='ColorDropper')
