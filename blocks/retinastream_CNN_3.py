# I'll build a convolutional neural network to work on mnist

##################################################################
# Building the model
##################################################################
import pdb
import theano.tensor as T
import numpy as np

from blocks.bricks import Rectifier, Softmax, MLP
from extrabricks import SoftRectifier
from blocks.bricks.cost import SquaredError, MisclassificationRate
from blocks.bricks.conv import ConvolutionalLayer, ConvolutionalSequence, MaxPooling
from blocks.bricks.conv import ConvolutionalActivation, Flattener
from blocks.filter import VariableFilter
from blocks.initialization import IsotropicGaussian, Constant, Uniform
from blocks.roles import WEIGHT, FILTER, INPUT
from blocks.graph import ComputationGraph, apply_dropout
from blocks.bricks.cost import Cost
from blocks.bricks.base import application

from metrics import PearsonCorrelation, ExplainedVariance, MeanModelRates, PoissonLogLikelihood

batch_size = 256
filter_size = 11
num_filters = 1
initial_weight_std = .01
epochs = 5

x = T.tensor4('data')
y = T.fcol('rates')

# Convolutional Layers
#conv_layers = [
#        ConvolutionalLayer(Rectifier().apply, (filter_size,filter_size), num_filters, (2,2), name='l1')]

#convnet = ConvolutionalSequence(
#        conv_layers, num_channels=40, image_size=(32,32),
#        weights_init=IsotropicGaussian(initial_weight_std),
#        biases_init=Constant(0)
#        )

#convnet.initialize()

#output_dim = np.prod(convnet.get_dim('output'))
#print(output_dim)

# Fully connected layers
features = Flattener().apply(x)

mlp = MLP(
        activations=[SoftRectifier()],
        dims=[32*32*40, 1],
        weights_init=IsotropicGaussian(0.01),
        biases_init=Constant(0)
        )
mlp.initialize()

y_hat = mlp.apply(features)


# numerically stable softmax
cost = PoissonLogLikelihood().apply(y.flatten(), y_hat.flatten()) 
cost.name = 'nll'
mse         = T.mean(SquaredError().cost_matrix(y, y_hat))
mse.name    = 'mean_squared_error'
correlation = PearsonCorrelation().apply(y.flatten(), y_hat.flatten())
explain_var = ExplainedVariance().apply(y.flatten(), y_hat.flatten())
mean_y_hat  = MeanModelRates().apply(y_hat.flatten())
#error_rate = MisclassificationRate().apply(y.flatten(), y_hat)
#cost = MisclassificationRate().apply(y, y_hat)
#cost.name = 'error_rate'

cg = ComputationGraph(cost)

#pdb.set_trace()
weights = VariableFilter(roles=[FILTER, WEIGHT])(cg.variables)
l2_regularization = 0.005 * sum((W**2).sum() for W in weights)

cost_l2 = cost + l2_regularization
cost.name = 'cost_with_regularization'


##################################################################
# Training
##################################################################
from blocks.main_loop import MainLoop
from blocks.graph import ComputationGraph
from blocks.extensions import SimpleExtension, FinishAfter, Printing
from blocks.algorithms import GradientDescent, Scale, Momentum
from blocks.extensions.plot import Plot
from blocks.extensions.saveload import Checkpoint, LoadFromDump
from blocks.extensions.monitoring import DataStreamMonitoring, TrainingDataMonitoring
from blocks.model import Model
#from blocks import MainLoopDumpManager

#from fuel.datasets import MNIST
from fuel.streams import DataStream
from retinastream import RetinaStream
from fuel.schemes import SequentialScheme
from fuel.transformers import Flatten

import os
from os.path import expanduser
import h5py

#rng = np.random.RandomState(1)
seed = np.random.randint(100)

# LOAD DATA
machine_name = 'marr'
if machine_name == 'lenna':
    datadir = os.path.expanduser('~/experiments/data/012314b/')
elif machine_name == 'lane':
    datadir = '/Volumes/data/Lane/binary_white_noise/'
elif machine_name == 'marr':
    datadir = os.path.expanduser('~/deepretina/datasets/binary_white_noise/')
filename = 'retina_012314b.hdf5'
print 'Loading RetinaStream'

num_total_examples = 299850
num_train_examples = 239880 # for 80, 10, 10 split
num_val_examples   = 29985
training_stream    = RetinaStream(filename, datadir, cellidx=1, history=40, fraction=0.8, seed=seed,
        partition_label='train',
        iteration_scheme=SequentialScheme(num_train_examples, batch_size=batch_size))
validation_stream  = RetinaStream(filename, datadir, cellidx=1, history=40, fraction=0.8, seed=seed,
        partition_label='val',
        iteration_scheme=SequentialScheme(num_val_examples, batch_size=1024))

#algorithm = GradientDescent(cost=cost, params=cg.parameters,
#        step_rule=Scale(learning_rate=0.1))

model = Model(cost_l2)
algorithm = GradientDescent(
        cost=cost_l2,
        params=model.parameters,
        step_rule=Momentum(
            learning_rate=0.1,
            momentum=0.9)
        )

main_loop = MainLoop(
        model = model,
        data_stream = training_stream,
        algorithm = algorithm,
        extensions = [
            FinishAfter(after_n_epochs=epochs),
            TrainingDataMonitoring(
                [cost, correlation, explain_var, mean_y_hat, mse],
                prefix='train',
                after_epoch=True),
            DataStreamMonitoring(
                [cost, correlation, explain_var, mean_y_hat, mse],
                validation_stream,
                prefix='valid'),
            #Checkpoint('retinastream_model.pkl', after_epoch=True),
            #EarlyStoppingDump('/Users/jadz/Documents/Micelaneous/Coursework/Blocks/mnist-blocks/', 'valid_error_rate'),
            #MainLoopDumpManager(expanduser('~/deepretina/blocks/checkpoints'))
            Printing()
            ]
        )

main_loop.run()


