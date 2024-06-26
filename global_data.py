import chess.engine
from constants import ROOT_DIR, CONTENT_HEIGHT, LEFT_PANE_WIDTH, EXPORT_FORMAT, EXPORT_SCALE
from time import sleep
# from test_array import activations_array

from copy import deepcopy

from board2planes import board2planes

import yaml

import os
from os.path import isdir, join
import sys

import numpy as np

sys.path.append(join(ROOT_DIR, "lczero-training", "tf"))
#import lczerotraining.tf.tfprocess as tfprocess

import importlib
tfprocess = importlib.import_module("lczero-training.tf.tfprocess")



SIMULATE_TF = False #TODO: Remove this option, deprecated
# turn off tensorflow importing and generate random data to speed up development
DEV_MODE = False
SIMULATED_LAYERS = 6
SIMULATED_HEADS = 64
FIXED_ROW = None  # 1 #None to disable
FIXED_COL = None  # 5 #None to disable
if DEV_MODE:
    class DummyModel:
        def __init__(self, layers, heads):
            self.layers = layers
            self.heads = heads

        def __call__(self, *args, **kwargs):
            data = [np.random.rand(1, self.heads, 64, 64) for i in range(self.layers)]
            return [None, None, None, data]

else:
    import tensorflow as tf
    from tensorflow.compat.v1 import ConfigProto
    from tensorflow.compat.v1 import InteractiveSession


# class to hold data, state and configurations
# Dash is stateless and in general it is very bad idea to store data in global variables on server side
# However, this application is ment to be run by single user on local machine, so it is safe to store data and state
# information on global object
class GlobalData:
    def __init__(self):
        import os
        if not DEV_MODE:
            # import tensorflow as tf
            os.environ["CUDA_VISIBLE_DEVICES"] = "0"

            # from tensorflow.compat.v1 import ConfigProto
            # from tensorflow.compat.v1 import InteractiveSession
            # import chess
            # import matplotlib.patheffects as path_effects

            #config = ConfigProto()
            #config.gpu_options.allow_growth = True
            #session = InteractiveSession(config=config)
            #tf.keras.backend.clear_session()

        self.tmp = 0
        self.export_format = EXPORT_FORMAT
        self.export_scale = EXPORT_SCALE
        self.fen = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'  # '2kr3r/ppp2b2/2n4p/4p3/Q2Pq1pP/2P1N3/PP3PP1/R1B1KB1R w KQ - 3 18'#'6n1/1p1k4/3p4/pNp5/P1P4p/7P/1P4KP/r7 w - - 2 121'#
        self.board = chess.Board(fen=self.fen)
        self.focused_square_ind = 0
        self.active_move_table_cell = None  # tuple (row_ind, col_id), e.g. (12, 'White')

        self.activations = None  # activations_array
        self.visualization_mode = 'ROW'
        self.visualization_mode_is_64x64 = False
        self.subplot_mode = 'big' #'fit'  # big'#'fit'#, 'big'
        self.subplot_cols = 0
        self.subplot_rows = 0
        self.number_of_heads = 0
        self.selected_head = None
        self.show_all_heads = True

        self.show_colorscale = False
        self.colorscale_mode = 'mode1'

        self.figure_container_height = '100%'  # '100%'

        self.running_counter = 0  # used to pass new values to hidden indicator elements which will trigger follow-up callback
        self.grid_has_changed = False

        # self.has_subplot_grid_changed = True
        # self.figure_layout_images = None #store layout and only recalculate when subplot grid has changed
        # self.figure_layout_annotations = None
        # self.need_update_axis = True

        self.screen_w = 0
        self.screen_h = 0
        self.figure_w = 0
        self.figure_h = 0
        self.heatmap_w = 0
        self.heatmap_h = 0
        self.heatmap_fig_w = 0
        self.heatmap_fig_h = 0
        self.heatmap_gap = 0
        self.colorscale_x_offset = 0

        self.heatmap_horizontal_gap = 0.275

        self.figure_cache = {}

        self.update_grid_shape()

        self.pgn_data = []  # list of boards in pgn
        self.move_table_boards = {}  # dict of boards in pgn, key is (move_table.row_ind, move_table.column_id)

        if not SIMULATE_TF:
            self.selected_layer = None
        else:
            self.selected_layer = 0

        self.nr_of_layers_in_body = -1
        self.has_attention_policy = False

        self.model_paths = []
        self.model_names = []
        self.model_yamls = {} #key = model path, value = yaml of that model
        self.model_cache = {}
        self.find_models2()
        self.model_path = None#self.model_paths[0]  # '/home/jusufe/PycharmProjects/lc0-attention-visualizer/T12_saved_model_1M'
        self.model = None
        self.tfp = None #TensorflowProcess
        if not SIMULATE_TF:
            self.load_model()
        self.activations_data = None

        if self.model is not None or SIMULATE_TF:
            self.update_activations_data()

        if self.selected_layer is not None:
            self.set_layer(self.selected_layer)

        self.move_table_active_cell = None

        self.force_update_graph = False

    def set_subplot_mode(self, fit_to_page):
        if fit_to_page == [True]:
            self.subplot_mode = 'fit'
        else:
            self.subplot_mode = 'big'
        self.update_grid_shape()

    def set_screen_size(self, w, h):
        self.screen_w = w
        self.screen_h = h

        self.figure_w = w*LEFT_PANE_WIDTH/100
        self.figure_h = h*CONTENT_HEIGHT/100
        print('GRAPH AREA', self.figure_w, self.figure_h)

    def set_heatmap_size(self, size):
        if size != '1':
            #print('-----------------------HEATMAP SIZE', size)
            # w, h = size
            # print('TYETETETETEU', global_data.screen_w)
            # global_data.set_screen_size(w, h)
            #print('>>>>>: HEATMAP WIDTH', size[0])
            #print('>>>>>: HEATMAP HEIGHT', size[1])
            #print('>>>>>: FIG WIDTH', size[2])
            #print('>>>>>: FIG HEIGHT', size[3])
            #print('>>>>>: HEATMAP GAP', size[4])

            self.heatmap_w = float(size[0])
            self.heatmap_h = float(size[1])
            self.heatmap_fig_w = float(size[2])
            self.heatmap_fig_h = float(size[3])
            self.heatmap_gap = round(float(size[4]), 2)

            self.colorscale_x_offset = float(size[5])/self.heatmap_fig_w

            if size[6] == 1:
                self.force_update_graph = True
            else:
                self.force_update_graph = False


            #if self.heatmap_gap < 30:
            #    self.heatmap_horizontal_gap += 0.025

            #    self.heatmap_horizontal_gap = min(0.25, self.heatmap_horizontal_gap)
            #if self.heatmap_gap < 200:
            #    self.heatmap_horizontal_gap += -0.025
            #    self.heatmap_horizontal_gap = max(0.1, self.heatmap_horizontal_gap)

    def set_colorscale_mode(self, mode, colorscale_mode, colorscale_mode_64x64, show):
        if mode == '64x64':
            self.colorscale_mode = colorscale_mode_64x64
        else:
            self.colorscale_mode = colorscale_mode
        #print('SHOW value', show)
        self.show_colorscale = show == [True]

    def cache_figure(self, fig):
        if not self.check_if_figure_is_cached() and fig != {}:
            key = self.get_figure_cache_key()
            cached_fig = deepcopy(fig)
            cached_fig.update_layout({'coloraxis1': None}, overwrite=True)
            #print('CACHING FIGURE:')
            self.figure_cache[key] = cached_fig

    def get_cached_figure(self):
        if self.check_if_figure_is_cached():
            key = self.get_figure_cache_key()
            fig = deepcopy(self.figure_cache[key])
        else:
            fig = None
        return fig

    def check_if_figure_is_cached(self):
        key = self.get_figure_cache_key()
        return key in self.figure_cache

    def get_figure_cache_key(self):
        return (self.subplot_rows, self.subplot_cols, self.visualization_mode_is_64x64,
                self.selected_head if not self.show_all_heads else -1, self.show_colorscale, self.colorscale_mode,
                self.board.turn)
        #return (self.subplot_rows, self.subplot_cols, self.visualization_mode_is_64x64, self.selected_head if not self.show_all_heads else -1, self.heatmap_horizontal_gap, self.heatmap_fig_h, self.heatmap_fig_w)
        #return (self.subplot_rows, self.subplot_cols, self.visualization_mode_is_64x64, self.show_all_heads)

    def get_side_to_move(self):
        return ['Black', 'White'][self.board.turn]

    def load_model(self):
        if self.model_path in self.model_cache:
            self.model, self.tfp = self.model_cache[self.model_path]

        elif self.model_path is not None:
            #net = '/home/jusufe/Projects/lc0/BT1024-3142c-swa-186000.pb.gz'
            #yaml_path = '/home/jusufe/Downloads/cfg.yaml'
            if not DEV_MODE:
                net = self.model_path
                yaml_path = self.model_yamls[self.model_path]
                with open(yaml_path) as f:
                    cfg = f.read()
                cfg = yaml.safe_load(cfg)

                if 'dropout_rate' in cfg['model']:
                    print('Setting dropout_rate to 0.0')
                    cfg['model']['dropout_rate'] = 0.0

                tfp = tfprocess.TFProcess(cfg)
                tfp.init_net()
                tfp.replace_weights(net, ignore_errors=False)
                self.model = tfp.model
                self.tfp = tfp
            else:
                self.model = DummyModel(SIMULATED_LAYERS, SIMULATED_HEADS)
                self.tfp = None

        else:
            self.model = None
            self.tfp = None

    def find_models(self):
        root = ROOT_DIR
        models_root_folder = os.path.join(root, 'models')
        model_folders = [f for f in os.listdir(models_root_folder) if isdir(join(models_root_folder, f))]
        model_paths = [os.path.relpath(join(models_root_folder, f)) for f in os.listdir(models_root_folder) if
                       isdir(join(models_root_folder, f))]
        self.model_names = model_folders
        self.model_paths = model_paths

        #print('MODELS:')
        #print(self.model_names)
        #print(self.model_paths)

    def find_models2(self):
        import os
        from os.path import isdir, join
        root = ROOT_DIR
        models_root_folder = os.path.join(root, 'models')
        model_folders = [f for f in os.listdir(models_root_folder) if isdir(join(models_root_folder, f))]
        model_paths = [os.path.relpath(join(models_root_folder, f)) for f in os.listdir(models_root_folder) if
                       isdir(join(models_root_folder, f))]

        models = []
        paths = []
        yamls = []
        for path in model_paths:
            yaml_files = [file for file in os.listdir(path) if file.endswith(".yaml")]
            if len(yaml_files) != 1:
                continue
            model_files = [file for file in os.listdir(path) if file.endswith(".pb.gz")]
            if len(model_files) == 0:
                continue

            models += model_files
            paths += [os.path.relpath(join(path, f)) for f in model_files]
            yaml_file = os.path.relpath(join(path, yaml_files[0]))
            yamls += [yaml_file]*len(model_files)

        self.model_yamls = {path: yaml_file for path, yaml_file in zip(paths, yamls)}
        self.model_names = models
        self.model_paths = paths#model_paths


    def update_activations_data(self):

        if self.model is not None and self.selected_layer is None:
            self.selected_layer = 0

        if not SIMULATE_TF:
            if self.selected_layer is not None and self.model is not None and self.selected_layer != 'Smolgen':
                if not DEV_MODE:
                    inputs = board2planes(self.board)
                    inputs = tf.reshape(tf.convert_to_tensor(inputs, dtype=tf.float32), [-1, 112, 8, 8])
                else:
                    inputs = None

                outputs = self.model(inputs)

                print(outputs.keys())
                self.activations_data = outputs["attn_wts"]
                cat = outputs.get("value_q_cat")
                print("q cat and err", outputs.get("value_q").numpy() , outputs.get("value_q_err").numpy() )
                print("winner", outputs.get("value_winner").numpy())
                if cat is not None:
                    # convert to numpy array then print
                    cat = tf.squeeze(cat, axis=0).numpy()
                    n_buckets = cat.shape[-1]
                    indices = np.arange(n_buckets) / n_buckets * 2 - 1
                    cat = np.stack([indices, cat], axis=1)
                    print("cat: ", np.array_repr(cat))
                else:
                    print("cat not found")

                print("keys: ", outputs.keys())

                #smolgen = self.tfp.smol_weight_gen_dense.get_weights()[0].reshape((256, 64, 64))
                #print('Smolgen')
                #print(type(smolgen))
                #print(smolgen.shape)
                #print(type(smolgen[0]))
                #print(smolgen[0].shape)
                #_, _, _, self.activations_data = self.model(inputs)
            elif self.selected_layer == 'Smolgen' and self.tfp is not None and self.tfp.use_smolgen:
                weights = self.tfp.smol_weight_gen_dense.get_weights()[0]
                self.activations_data = weights.reshape((weights.shape[0], 64, 64))
                print('TYPEEEEE', type(self.activations_data))

        else:
            layers = SIMULATED_LAYERS
            heads = SIMULATED_HEADS
            self.activations_data = [np.random.rand(1, heads, 64, 64) for i in range(layers)]

        if self.model is not None:

            if self.model_path not in self.model_cache:
                self.model_cache[self.model_path] = [self.model, self.tfp]

            self.update_layers_in_body_count()

        #TODO: figure out better way to determine if we have policy attention weights
        #TODO: What happens if policy vis is selected and user switches to model without policy layer? Take care of this case.
        if self.activations_data is not None and self.activations_data[-2].shape == (1, 8, 24):
            self.has_attention_policy = True
        else:
            self.has_attention_policy = False
        # self.update_selected_activation_data()
        # self.activations = self.activations_data[self.selected_layer]

    def update_grid_shape(self):
        # TODO: add client side callback triggered by Interval component to save window or precise container dimensions to Div
        # TODO: Trigger server side figure update callback when dimensions are recorded and store in global_data
        # TODO: If needed, recalculate subplot rows and cols and container scaler based on the changed dimension

        def calc_cols(heads, rows):
            if heads % rows == 0:
                cols = int(heads / rows)
            else:
                cols = int(1 + heads / rows)
            return cols

        if FIXED_ROW and FIXED_COL:
            self.subplot_cols = FIXED_COL
            self.subplot_rows = FIXED_ROW
            return None

        heads = self.number_of_heads
        if self.subplot_mode == 'fit':
            max_rows_in_screen = 4
            if heads <= 4:
                rows = 1
            elif heads <= 8:
                rows = 2
            else:
                rows = heads // 8 + int(heads % 8 != 0)

        elif self.subplot_mode == 'big':
            #print(heads)

            max_rows_in_screen = 2
            rows = heads // 4 + int(heads % 4 != 0)
            #print(rows)

        if rows > max_rows_in_screen:
            container_height = f'{int((rows / max_rows_in_screen) * 100)}%'
        else:
            container_height = '100%'

        if rows != 0:
            cols = calc_cols(heads, rows)
        else:
            cols = 0

        if self.subplot_rows != rows or self.subplot_cols != cols:
            self.grid_has_changed = True

        self.subplot_cols = cols
        self.subplot_rows = rows

        if self.show_all_heads:
            self.figure_container_height = container_height
        else:
            self.figure_container_height = '100%'

    def update_selected_activation_data(self):
        # import numpy as np
        # self.activations = activations_array + np.random.rand(8, 64, 64)
        if self.activations_data is not None:
            if self.selected_layer not in ('Policy', 'Smolgen'):
                if not DEV_MODE:
                    activations = tf.squeeze(self.activations_data[self.selected_layer], axis=0).numpy()
                    #self.activations = activations[:, ::-1, :] #Flip along y-axis
                else:
                    activations = np.squeeze(self.activations_data[self.selected_layer], axis=0)
            elif self.selected_layer == 'Policy':
                print('RAW POLICY SHAPE', self.activations_data[-1].shape)
                activations = self.activations_data[-1].numpy()
                #print('POLICY SHAPE', activations.shape)

                #print('RAW POLICY SHAPE', self.activations_data[-1].shape)
                #activations = np.squeeze(self.activations_data[-1].numpy(), axis=0) #shape 64,64
                #promo = np.squeeze(self.activations_data[-2].numpy(), axis=0) #shape 8,24
                #print('promo shape:', promo.shape)
                #if self.board.turn:
                #    pad_shape = (48, 8)
                #else:
                #    pad_shape = (8, 48)
                #promo_padded = np.pad(promo, (pad_shape, (0, 0)), mode='constant', constant_values=None) #shape 64,24
                #self.activations = np.expand_dims(np.concatenate((activations, promo_padded), axis=1), axis=0)#shape 1,64,88
                #print('POLICY SHAPE', self.activations.shape)
            elif self.selected_layer == 'Smolgen':
                activations = self.tfp.smol_weight_gen_dense.get_weights()[0].reshape((256, 64, 64))

            self.activations = activations[:, ::-1, :]  # Flip along y-axis

    def set_visualization_mode(self, mode):
        self.visualization_mode = mode
        self.visualization_mode_is_64x64 = mode == '64x64'

    def set_layer(self, layer):
        self.selected_layer = layer
        self.update_selected_activation_data()
        if layer not in ('Policy', 'Smolgen'):
            self.number_of_heads = self.activations_data[self.selected_layer].shape[1]
        elif layer == 'Policy':
            self.number_of_heads = 1
        elif layer == 'Smolgen':
            self.number_of_heads = self.activations.shape[0]
            self.set_head(0)
        self.update_grid_shape()

    def set_head(self, head):
        self.selected_head = head

    def set_model(self, model):
        if model != self.model_path:
            self.model_path = model
            self.load_model()
            self.update_activations_data()
            self.update_selected_activation_data()
            self.number_of_heads = self.activations_data[self.selected_layer].shape[1]
            if self.selected_head is None:
                self.selected_head = 0
            else:
                self.selected_head = min(self.selected_head, self.number_of_heads - 1)
            self.update_grid_shape()
        if SIMULATE_TF:
            sleep(2)

    def update_layers_in_body_count(self):
        # TODO: figure out robust way to separate attention layers in body from the rest. UPDATE: Use yaml
        heads = self.activations_data[0].shape[1]
        for ind, layer in enumerate(self.activations_data):
            if layer.shape[1] != heads or len(layer.shape) != 4:
                ind = ind - 1
                break
        self.nr_of_layers_in_body = ind + 1
        if self.selected_layer not in ('Policy', 'Smolgen'):
            self.selected_layer = min(self.selected_layer, self.nr_of_layers_in_body - 1)

    def get_head_data(self, head):

        if self.activations.shape[0] <= head:
            return None

        if self.visualization_mode == '64x64':
            # print('64x64 selection')
            data = self.activations[head, :, :]

        elif self.visualization_mode == 'ROW':
            # print('ROW selection')
            if self.board.turn or self.selected_layer == 'Smolgen': #White turn to move
                row = 63 - self.focused_square_ind
                data = self.activations[head, row, :].reshape((8, 8))
            else:
                #row = self.focused_square_ind
                multiples = self.focused_square_ind // 8
                remainder = self.focused_square_ind % 8

                a = 7 - remainder
                b = multiples * 8
                row = a + b
                data = self.activations[head, row, :].reshape((8, 8))[::-1, :]
        else:
            # print('COL selection')
            if self.board.turn or self.selected_layer == 'Smolgen': #White turn to move
                col = self.focused_square_ind
                data = self.activations[head, :, col].reshape((8, 8))[::-1, ::-1]
            else:
                focused = 63 - self.focused_square_ind
                multiples = focused // 8
                remainder = focused % 8
                a = 7 - remainder
                b = multiples * 8
                col = a + b
                #print('COL!!!!!!!!!!!!!!!!!', col, a, b, focused, self.focused_square_ind)
                data = self.activations[head, :, col].reshape((8, 8))[:, ::-1]
        return data

    def set_fen(self, fen):
        self.board.set_fen(fen)
        self.fen = fen
        self.update_activations_data()
        self.update_selected_activation_data()

    def set_board(self, board):
        self.board = deepcopy(board)
        self.update_activations_data()
        self.update_selected_activation_data()


global_data = GlobalData()
print('global data created')
