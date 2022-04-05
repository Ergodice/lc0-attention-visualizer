import dash
import plotly.graph_objs as go
from plotly.subplots import make_subplots
from global_data import global_data

from svg_pieces import get_svg_board
from dash import dcc, html, Input, Output, State
from server import app

from utils import callback_triggered_by

import time


def heatmap_data(head):
    data = global_data.get_head_data(head)
    return data


def heatmap_figure():
    start = time.time()
    fig = make_figure()
    print('make fig:', time.time() - start)

    start = time.time()
    fig = add_heatmap_traces(fig)
    print('add traces:', time.time() - start)

    start = time.time()
    fig = add_layout(fig)
    print('add layout total:', time.time() - start)

    start = time.time()
    if not global_data.visualization_mode_is_64x64:
        fig = add_pieces(fig)
        print('add pieces:', time.time() - start)

    with open(f'sqr_{global_data.focused_square_ind}_fig_{global_data.running_counter}.txt', "w") as f:
        f.write(fig.__str__())
        global_data.running_counter += 1
    return fig


def heatmap():
    start = time.time()
    # We need to recalculate graph when grid size changes, other wise layout is a mess (Dash bug?). Use hidden Div's children to trigger callback for graph recalc.
    # Otherwise we can just recalculate figure part and frontend rendering will be much faster
    graph = html.Div(id='graph-container', children=[heatmap_graph()],
                     style={'height': '100%', 'width': '100%', "overflow": "auto"
                            })

    print('GRAPH CREATION:', time.time() - start)
    return graph


def heatmap_graph():
    fig = heatmap_figure()

    config = {
        'displaylogo': False,
        'modeBarButtonsToRemove': ['zoom', 'pan', 'select', 'zoomIn', 'zoomOut', 'autoScale', 'resetScale']}

    style = {'height': global_data.figure_container_height, 'width': '100%'}

    graph = dcc.Graph(figure=fig, id='graph', style=style,
                      responsive='auto',#True,  # True,
                      config=config
                      )

    # graph = html.Div(id='graph-container', children=[graph], style={'height': '100%', 'width': '100%', "overflow": "auto"
    #                                                           })
    # graph_component.children = [graph]

    global_data.cache_figure(fig)

    return graph


def make_figure():
    print('assumed key', global_data.subplot_rows, global_data.subplot_rows, global_data.visualization_mode_is_64x64)
    print('key', global_data.get_figure_cache_key())
    print('all keys', global_data.figure_cache.keys())
    fig = global_data.get_cached_figure()
    if fig is None:
        titles = [f"Head {i + 1}" for i in range(global_data.number_of_heads)]
        print('MAKING SUBPLOTS', 'rows:', global_data.subplot_rows, 'cols:', global_data.subplot_cols)
        print('NUMBER OF HEADS:', global_data.number_of_heads)
        fig = make_subplots(rows=global_data.subplot_rows, cols=global_data.subplot_cols, subplot_titles=titles,
                            horizontal_spacing=0.1 / global_data.subplot_cols,
                            vertical_spacing=0.25 / global_data.subplot_rows,
                            )
    return fig


def add_layout(fig):
    start = time.time()
    if global_data.check_if_figure_is_cached():
        print('Using existing layout')
        return fig

    layout = go.Layout(
        # title='Plot title goes here',
        margin={'t': 30, 'b': 0, 'r': 0, 'l': 0},
        plot_bgcolor='rgb(0,0,0)'
    )

    fig.update_layout(layout)
    # fig['layout'].update(layout)

    print('update layout:', time.time() - start)

    start = time.time()
    fig = update_axis(fig)
    print('update axis:', time.time() - start)
    # print(fig)
    return fig


def update_axis(fig):
    if global_data.visualization_mode_is_64x64:
        tickvals = list(range(0, 64, 4))
        ticktext_x = [x + y for x, y in zip('ae' * 8, '1122334455667788')]
        ticktext_y = ticktext_x[::-1]
        showticklabels = True
        val_range = [-0.5, 63.5]
        ticks = 'outside'
    else:
        tickvals = list(range(8))  # [0, 1, 2, 3, 4, 5, 6, 7]
        ticktext_x = [letter for letter in 'abcdefgh']
        ticktext_y = [letter for letter in '12345678']
        showticklabels = True
        val_range = [-0.5, 7.5]
        ticks = ''

    fig.update_xaxes(title=None,
                     range=val_range,
                     # ticklen=50,
                     zeroline=False,
                     showgrid=False,
                     scaleanchor='y',
                     constrain='domain',
                     # constraintoward='right',
                     ticks=ticks,  # ticks,
                     ticktext=ticktext_x,
                     tickvals=tickvals,
                     showticklabels=showticklabels,
                     # mirror='ticks',
                     fixedrange=True
                     )
    fig.update_yaxes(title=None,
                     range=val_range,
                     zeroline=False,
                     showgrid=False,
                     scaleanchor='x',
                     constrain='domain',
                     constraintoward='top',
                     ticks=ticks,  # ticks,
                     ticktext=ticktext_y,
                     tickvals=tickvals,
                     showticklabels=showticklabels,
                     # mirror='allticks',
                     # side='top',
                     fixedrange=True
                     )
    return fig


def add_heatmap_trace(fig, row, col):
    # print('ADDING heatmap', row, col)
    head = (row - 1) * global_data.subplot_cols + (col - 1)
    data = heatmap_data(head)

    if data is None:
        return fig

    if global_data.visualization_mode_is_64x64:
        xgap, ygap = 0, 0
        hovertemplate = '<b>%{z}</b><extra></extra>'
    else:
        xgap, ygap = 2, 2
        hovertemplate = '<b>%{x}%{y}</b>: <b>%{z}</b><extra></extra>'

    trace = go.Heatmap(
        z=data,
        colorscale='Viridis',
        showscale=False,
        xgap=xgap,
        ygap=ygap,
        hovertemplate=hovertemplate
    )
    fig.add_trace(trace, row=row, col=col)
    return fig


def add_heatmap_traces(fig):
    print('adding traces, rows:', global_data.subplot_rows, 'cols:', global_data.subplot_cols)
    #adding traces is quick so we don't bother using cached values. Wipe old traces and add new.
    fig.data = []
    for row in range(global_data.subplot_rows):
        for col in range(global_data.subplot_cols):
            fig = add_heatmap_trace(fig, row + 1, col + 1)
    return fig


def add_pieces(fig):
    board_svg = get_svg_board(global_data.board, global_data.focused_square_ind, True)

    if global_data.check_if_figure_is_cached():
        print('USING CACHED')
        for img in fig.layout.images:
            img['source'] = board_svg
    else:
        fig.add_layout_image(
            dict(
                source=board_svg,
                xref="x",
                yref="y",
                x=3.5,
                y=3.5,
                sizex=8,
                sizey=8,
                xanchor='center',
                yanchor='middle',
                sizing="stretch",
            ),
            row='all',
            col='all',
            exclude_empty_subplots=True,
        )

    return fig

#a = """
# callback to update figure property of graph. In principle, this should be all we ever need to update (+graph height)
# Due to probable dash/plotly bug this is not enough if figure's subplot grid dimensions change as updating only figure will result in messed up layout
# To workaround this, we will update indicator component if grid dimension has changed, which in turn will trigger callback for full graph update
@app.callback([Output('graph', 'figure'),
               Output('recalculate-graph-indicator', 'children'),
               Output('graph', 'style')],
              [Input('graph', 'clickData'),
               Input('mode-selector', 'value'),
               Input('layer-selector', 'value'),
               Input('selected-model', 'children'),  # New model was selected
               Input('move-table', 'style_data_conditional'),  # New move was selected in move table
               Input('position-mode-changed-indicator', 'children'), # fen/pgn mode changed
               Input('fen-text', 'children')  # New fen was set
               ])
def update_heatmap_figure(click_data, mode, layer, *args):
    fig = dash.no_update
    trigger = callback_triggered_by()
    global_data.set_visualization_mode(mode)
    global_data.set_layer(layer)
    print('MODE', mode)
    if trigger == 'graph.clickData' and not click_data:
        return dash.no_update, dash.no_update, dash.no_update  # , dash.no_update, dash.no_update

    # if grid dimensions have change we need to trigger full graph component recalc (workaround for dash bug where
    # figure layout is messed up if only figure is updated)
    if global_data.grid_has_changed:
        print('GRID CHANGED')
        global_data.running_counter += 1
        global_data.grid_has_changed = False
        #Erase figure, update indicator with new value, hide graph until updated again
        return {}, global_data.running_counter, {'visibility': 'hidden'}

    if trigger == 'graph.clickData' and not global_data.visualization_mode_is_64x64:
        point = click_data['points'][0]
        x = point['x']
        y = point['y']
        square_ind = 8 * y + x
        if square_ind != global_data.focused_square_ind:
            global_data.focused_square_ind = square_ind
            fig = heatmap_figure()
            # container = dash.no_update

    if trigger == 'fen-text.children':
        fig = heatmap_figure()
        # container = dash.no_update

    if trigger in ('mode-selector.value', 'layer-selector.value', 'move-table.style_data_conditional', 'position-mode-changed-indicator.children'):
        #print('LAYER SELECTOR UPDATE')
        fig = heatmap_figure()
        # container = dash.no_update

    if trigger == 'selected-model.children':
        fig = heatmap_figure()  # dash.no_update#heatmap_figure()
        # container = heatmap_graph()

    return fig, dash.no_update, dash.no_update
#"""

@app.callback(Output('graph-container', 'children'),
              Input('recalculate-graph-indicator', 'children'))
def update_heatmap_graph(txt):
    if txt is not None:
        graph = heatmap_graph()
    else:
        graph = dash.no_update
    return graph

a = """ 
@app.callback(Output('graph-container', 'children'),
              [Input('graph', 'clickData'),
               Input('mode-selector', 'value'),
               Input('layer-selector', 'value'),
               Input('selected-model', 'children'),  # New model was selected
               Input('move-table', 'style_data_conditional'),  # New move was selected in move table
               Input('fen-text', 'children')  # New fen was set
               ])
def update_heatmaps(click_data, mode, layer, *args):
    graph = dash.no_update
    trigger = callback_triggered_by()
    global_data.set_visualization_mode(mode)
    global_data.set_layer(layer)
    print('MODE', mode)
    if trigger == 'graph.clickData' and not click_data:
        return dash.no_update#, dash.no_update, dash.no_update

    if trigger == 'graph.clickData' and not global_data.visualization_mode_is_64x64:
        point = click_data['points'][0]
        x = point['x']
        y = point['y']
        square_ind = 8 * y + x
        if square_ind != global_data.focused_square_ind:
            global_data.focused_square_ind = square_ind
            graph = heatmap_graph()

    if trigger == 'fen-text.children':
        graph = heatmap_graph()

    if trigger in ('mode-selector.value', 'layer-selector.value', 'move-table.style_data_conditional'):
        graph = heatmap_graph()

    if trigger == 'selected-model.children':
        graph = heatmap_graph()

    return graph
"""
a = """ 
@app.callback([Output('graph', 'figure'),
               Output('graph', 'style')],
              [Input('graph', 'clickData'),
               Input('mode-selector', 'value'),
               Input('layer-selector', 'value'),
               Input('model-selector', 'value'),
               Input('fen-text', 'children')
               ])
def update_heatmaps(click_data, mode, layer, model, *args):
    fig = dash.no_update
    trigger = callback_triggered_by()
    global_data.set_visualization_mode(mode)
    global_data.set_layer(layer)
    style = {'height': global_data.figure_container_height, 'width': '100%'}
    print('MODE', mode)
    if trigger == 'graph.clickData' and not click_data:
        return dash.no_update, dash.no_update

    if trigger == 'graph.clickData' and not global_data.visualization_mode_is_64x64:
        point = click_data['points'][0]
        x = point['x']
        y = point['y']
        square_ind = 8 * y + x
        if square_ind != global_data.focused_square_ind:
            global_data.focused_square_ind = square_ind
            fig = heatmap_figure()

    if trigger == 'fen-text.children':
        fig = heatmap_figure()

    if trigger in ('mode-selector.value', 'layer-selector.value'):
        fig = heatmap_figure()

    model_selector = False
    if trigger == 'model-selector.value':
        global_data.set_model(model)
        print(fig)
        print('--------------------------------------------------------------------------------------------')
        fig = heatmap_figure()
        model_selector = True
        #print(fig)
    if model_selector:
        prefix = 'selected'
    else:
        prefix = 'initial'
    with open(f'{prefix}_{global_data.tmp}_fig{global_data.subplot_rows}x{global_data.subplot_cols}.txt', "w") as f:
        f.write(fig.__str__())
    global_data.tmp += 1
    return fig, style

"""
