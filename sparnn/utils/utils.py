__author__ = 'zhenyang'

import numpy
import time
import os
import theano
import theano.tensor as TT
import logging
from theano.sandbox.rng_mrg import MRG_RandomStreams as RandomStreams

logger = logging.getLogger(__name__)


def quick_symbolic_variable(ndim, name, typ=theano.config.floatX):
    if ndim == 5:
        return TT.TensorType(dtype=typ, broadcastable=(False,) * 5)(name=name)
    elif ndim == 4:
        return TT.tensor4(name=name, dtype=typ)
    elif ndim == 3:
        return TT.tensor3(name=name, dtype=typ)
    elif ndim == 2:
        return TT.matrix(name=name, dtype=typ)
    elif ndim == 1:
        return TT.scalar(name=name, dtype=typ)
    else:
        assert False


def quick_init_gaussian(rng, dim_vec, name):
    ret = theano.shared(value=numpy.asarray(rng.normal(0, 0.1, dim_vec), dtype=theano.config.floatX), name=name)
    return ret


def quick_init_uniform(rng, dim_vec, name, scale=0.1):
    """
    Random weights drawn from a Uniform
    """
    assert 2 == len(dim_vec)
    ret = theano.shared(value=numpy.asarray(rng.uniform(-scale, scale, dim_vec), dtype=theano.config.floatX), name=name)
    return ret


def quick_init_ortho(rng, dim_vec, name, scale=1.0):
    """
    Random orthogonal weights, we take
    the right matrix in the SVD.

    Remember in SVD, u has the same # rows as W
    and v has the same # of cols as W. So we
    are ensuring that the rows are 
    orthogonal.
    """
    assert 2 == len(dim_vec)
    assert dim_vec[0] == dim_vec[1]
    W = rng.normal(0, 1.0, dim_vec)
    u, s, v = numpy.linalg.svd(W)
    ret = theano.shared(value=numpy.asarray(u * scale, dtype=theano.config.floatX), name=name)
    #print u, "\n\n", s, "\n\n", v, "\n"
    #print numpy.square(u).sum(), numpy.square(s).sum(), numpy.square(v).sum(), "\n"
    return ret


def quick_init_norm(rng, dim_vec, name, scale=0.1, ortho=False): #scale=0.01
    """
    Random weights drawn from a Gaussian
    """
    assert 2 == len(dim_vec)
    if dim_vec[0] == dim_vec[1] and ortho:
        ret = quick_init_ortho(rng, dim_vec, name, scale)
    else:
        ret = theano.shared(value=numpy.asarray(rng.normal(0, scale, dim_vec), dtype=theano.config.floatX), name=name)
    return ret


def get_fans(shape):
    fan_in = shape[0] if len(shape) == 2 else numpy.prod(shape[1:])
    fan_out = shape[1] if len(shape) == 2 else shape[0]
    return fan_in, fan_out


def quick_init_glorot_norm(rng, dim_vec, name):
    """
    Reference: Glorot & Bengio, AISTATS 2010
    """
    assert 2 == len(dim_vec)
    fan_in, fan_out = get_fans(dim_vec)
    s = numpy.sqrt(2. / (fan_in + fan_out))
    return quick_init_norm(rng, dim_vec, name, s)


def quick_init_glorot_uniform(rng, dim_vec, name):
    """
    Reference: Glorot & Bengio, AISTATS 2010
    """
    assert 2 == len(dim_vec)
    fan_in, fan_out = get_fans(dim_vec)
    s = numpy.sqrt(6. / (fan_in + fan_out))
    return quick_init_uniform(rng, dim_vec, name, s)


def quick_init_he_norm(rng, dim_vec, name):
    """
    Reference:  He et al., http://arxiv.org/abs/1502.01852
    """
    assert 2 == len(dim_vec)
    fan_in, fan_out = get_fans(dim_vec)
    s = numpy.sqrt(2. / fan_in)
    return quick_init_norm(rng, dim_vec, name, s)


def quick_init_he_uniform(rng, dim_vec, name):
    """
    Reference:  He et al., http://arxiv.org/abs/1502.01852
    """
    assert 2 == len(dim_vec)
    fan_in, fan_out = get_fans(dim_vec)
    s = numpy.sqrt(6. / fan_in)
    return quick_init_uniform(rng, dim_vec, name, s)


def quick_init_xavier(rng, dim_vec, name):
    #assert 4 == len(dim_vec)
    ret = theano.shared(
        value=numpy.asarray(
            rng.uniform(low=-1.0 / numpy.sqrt(dim_vec[1]), high=1.0 / numpy.sqrt(dim_vec[1]), size=dim_vec),
            dtype=theano.config.floatX), name=name)
    return ret


def stable_softmax(x):
    e_x = TT.exp(x - x.max(axis=1, keepdims=True))
    out = e_x / e_x.sum(axis=1, keepdims=True)
    return out


'''
    Quick_scan is an accelerated version of the official theano.scan
    The current scan implementation of Theano uses Cython and has an unsolved, enormous head-off in GPU. One direct
    solution is to unfold the computation if you know total time step in advance.
TODO!! Need further revision
'''


#def quick_scan(fn, sequences=None, outputs_info=None, n_steps=None, name=""):
#    if (type(n_steps) is int) or (type(n_steps) is numpy.ndarray):
#        output_list = []
#        current_state = []
#        assert outputs_info is not None
#        if type(outputs_info) is not list:
#            outputs_info = list(outputs_info)
#        if type(sequences) is list:
#            sequences = sequences[0]
#        for ele in outputs_info:
#            current_state.append(ele)
#            output_list.append([])
#        print current_state
#        print sequences
#        for i in range(n_steps):
#            if sequences is not None:
#                ret = fn(*([sequences[i], ] + current_state))
#            elif outputs_info is not None:
#                ret = fn(*current_state)
#            else:
#                assert False
#            current_state = list(ret)
#            for j in range(len(output_list)):
#                output_list[j].append(ret[j])

#        output = [TT.stack(*ele) for ele in output_list]
#        return output, None
#    else:
#        return theano.scan(fn=fn, sequences=sequences, outputs_info=outputs_info, n_steps=n_steps, name=name)


def quick_unroll_scan(fn, sequences, outputs_info, non_sequences, n_steps,
                go_backwards=False):
        """
        Helper function to unroll for loops. Can be used to unroll theano.scan.
        The parameter names are identical to theano.scan, please refer to here
        for more information.
        Note that this function does not support the truncate_gradient
        setting from theano.scan.
        Parameters
        ----------
        fn : function
            Function that defines calculations at each step.
        sequences : TensorVariable or list of TensorVariables
            List of TensorVariable with sequence data. The function iterates
            over the first dimension of each TensorVariable.
        outputs_info : list of TensorVariables
            List of tensors specifying the initial values for each recurrent
            value.
        non_sequences: list of TensorVariables
            List of theano.shared variables that are used in the step function.
        n_steps: int
            Number of steps to unroll.
        go_backwards: bool
            If true the recursion starts at sequences[-1] and iterates
            backwards.
        Returns
        -------
        List of TensorVariables. Each element in the list gives the recurrent
        values at each time step.
        """
        if not isinstance(sequences, (list, tuple)):
            sequences = [sequences]

        # When backwards reverse the recursion direction
        counter = range(n_steps)
        if go_backwards:
            counter = counter[::-1]

        output = []
        prev_vals = outputs_info
        for i in counter:
            step_input = [s[i] for s in sequences] + prev_vals + non_sequences
            out_ = fn(*step_input)
            # The returned values from step can be either a TensorVariable,
            # a list, or a tuple.  Below, we force it to always be a list.
            if isinstance(out_, TT.TensorVariable):
                out_ = [out_]
            if isinstance(out_, tuple):
                out_ = list(out_)
            output.append(out_)

            prev_vals = output[-1]

        # iterate over each scan output and convert it to same format as scan:
        # [[output11, output12,...output1n],
        # [output21, output22,...output2n],...]
        output_scan = []
        for i in range(len(output[0])):
            l = map(lambda x: x[i], output)
            output_scan.append(TT.stack(*l))

        return output_scan, None


'''
    Quick_zero, dim_vec must be a tuple!
'''


def quick_zero(dim_vec, name):
    ret = theano.shared(value=numpy.zeros(dim_vec).astype(theano.config.floatX), name=name)
    return ret


'''
Function:quick_theano_zero
Here TT.unbroadcast should be used to avoid autobroadcast

'''


def quick_theano_zero(dim_vec):
    ret = TT.unbroadcast(TT.alloc(numpy_floatX(0), *dim_vec), *range(len(dim_vec)))
    return ret


# TODO If CUDNN is enabled use theano.sandbox.cuda.dnn.dnn_conv to achieve faster speed. But the current dnn_conv has some problems! So we use conv2d instead
def conv2d_same(input, filters, input_shape=(None, None, None, None), filter_shape=(None, None, None, None),
                padding=None):
    assert input.ndim == 4 and filters.ndim == 4
    assert (4 == len(input_shape)) and (4 == len(filter_shape))
    assert (1 == filter_shape[2] % 2) and (1 == filter_shape[3] % 2)
    if (tuple(input_shape[2:4]) == (1, 1) and tuple(filter_shape[2:4]) == (1, 1)) or (
                    tuple(filter_shape[2:4]) == (1, 1) and theano.config.device == "cpu"):
        return tensor4dot(input, filters)
    else:
        new_row_begin = filters.shape[2] / 2
        new_row_end = input.shape[2] + filters.shape[2] / 2
        new_col_begin = filters.shape[3] / 2
        new_col_end = input.shape[3] + filters.shape[3] / 2
        if padding is not None:
            assert 1 == padding.ndim
            padded_input = TT.ones((
                input.shape[0], input.shape[1], input.shape[2] + filters.shape[2] - 1,
                input.shape[3] + filters.shape[3] - 1)).astype(theano.config.floatX)
            padded_input = TT.set_subtensor(padded_input[:, :, new_row_begin:new_row_end, new_col_begin:new_col_end],
                                            numpy_floatX(0))
            padding = TT.shape_padleft(TT.shape_padright(padding, 2), 1)
            padded_input = padding * padded_input
        else:
            padded_input = TT.zeros((
                input.shape[0], input.shape[1], input.shape[2] + filters.shape[2] - 1,
                input.shape[3] + filters.shape[3] - 1)).astype(theano.config.floatX)
        padded_input = TT.inc_subtensor(padded_input[:, :, new_row_begin:new_row_end, new_col_begin:new_col_end], input)
        new_input_shape = [None, None, None, None]
        if input_shape[0] is not None:
            new_input_shape[0] = input_shape[0]
        if input_shape[1] is not None:
            new_input_shape[1] = input_shape[1]
        if input_shape[2] is not None and filter_shape[2] is not None:
            new_input_shape[2] = input_shape[2] + filter_shape[2] - 1
        if input_shape[3] is not None and filter_shape[3] is not None:
            new_input_shape[3] = input_shape[3] + filter_shape[3] - 1
        ret = TT.nnet.conv2d(input=padded_input, filters=filters, border_mode='valid',
                             input_shape=tuple(new_input_shape), filter_shape=filter_shape)

        return ret


def tensor4dot(input, filters):
    return TT.dot(filters.flatten(2), input.dimshuffle(0, 2, 1, 3)).dimshuffle(1, 0, 2, 3)


'''
Function: quick_activation
Input:
Prerequisite:
'''


def quick_activation(input, activation, *args):
    if "tanh" == activation:
        return TT.tanh(input)
    elif "sigmoid" == activation:
        return TT.nnet.sigmoid(input)
    elif "identity" == activation:
        return input
    elif "softmax" == activation:
        if 2 == input.ndim:
            ret = stable_softmax(input)
            return ret
        elif 3 == input.ndim:
            ret = stable_softmax(input.reshape((
                input.shape[0] * input.shape[1], input.shape[2]
            ))).reshape((
                input.shape[0], input.shape[1], input.shape[2]
            ))
            return ret
        elif 4 == input.ndim:
            ret = stable_softmax(input.dimshuffle(0, 2, 3, 1).reshape((
                input.shape[0] * input.shape[2] * input.shape[3], input.shape[1]
            ))).reshape((
                input.shape[0], input.shape[2], input.shape[3], input.shape[1]
            )).dimshuffle(0, 3, 1, 2)
            return ret
        elif 5 == input.ndim:
            ret = stable_softmax(input.dimshuffle(0, 1, 3, 4, 2).reshape((
                input.shape[0] * input.shape[1] * input.shape[3] * input.shape[4], input.shape[2]
            ))).reshape((
                input.shape[0], input.shape[1], input.shape[3], input.shape[4], input.shape[2]
            )).dimshuffle(0, 1, 4, 2, 3)
            return ret
        else:
            assert False
    elif activation == "relu":
        return TT.maximum(input, 0)
    else:
        # TODO Combine Logger and Assert
        assert False


def quick_sampling(input, sampling_func, rng=None, *args):
    if "argmax" == sampling_func:
        if 4 == input.ndim:
            ret = TT.argmax(input, axis=1, keepdims=True)
        elif 5 == input.ndim:
            ret = TT.argmax(input, axis=2, keepdims=True)
        else:
            assert False
    elif "multinomial" == sampling_func:
        # TODO Implement the multinomial sampling
        assert False
    else:
        assert False
    return ret


def quick_aggregate_pooling(input, pooling_func, mask=None):
    assert input.ndim == 5
    assert mask.ndim == 2 if mask is not None else True
    if pooling_func == "max":
        if mask is None:
            return input.max(axis=0)
    elif pooling_func == "mean":
        if mask is None:
            return TT.cast(input.mean(axis=0), theano.config.floatX)
        else:
            return (input * TT.shape_padright(mask / mask.sum(axis=0), 3)).sum(axis=0)
    elif pooling_func == "L2":
        # TODO Add Lp Pooling proposed by Yann LeCun
        return None
    return None


def quick_cost(prediction, target, cost_func, mask=None, epsilon=10E-8):
    #assert prediction.ndim == target.ndim
    #assert (mask.ndim == 2 and prediction.ndim == 5) if mask is not None else True
    assert (mask.ndim == 2) if mask is not None else True
    if "SquaredLoss" == cost_func:
        if mask is None:
            return TT.sqr(prediction - target).sum()
        else:
            assert 5 == prediction.ndim
            return (TT.sqr((prediction - target)) * TT.shape_padright(mask, 3)).sum()

    elif "BinaryCrossEntropy" == cost_func:
        prediction = TT.clip(prediction, epsilon, 1.0 - epsilon)
        if mask is None:
            return TT.nnet.binary_crossentropy(prediction, target).sum()
        else:
            if 5 == prediction.ndim:
                #assert 5 == prediction.ndim
                return (TT.nnet.binary_crossentropy(prediction, target) * TT.shape_padright(mask, 3)).sum()
            elif 3 == prediction.ndim:
                return (TT.nnet.binary_crossentropy(prediction, target) * TT.shape_padright(mask, 1)).sum()
            else:
                assert False

    elif "CategoricalCrossEntropy" == cost_func:
        # TODO The function assumes the user inputs are a set of ints, not 1-N vector
        # TODO Need Some Future Tests, The algorithm runs correct for a simple (3,3,3,1,1) testcase
        target64 = TT.cast(target, "int64")
        prediction = TT.clip(prediction, epsilon, 1.0 - epsilon)
        if mask is None:
            if 5 == prediction.ndim:
                ret = TT.nnet.categorical_crossentropy(
                    prediction.dimshuffle(0, 1, 3, 4, 2).reshape((
                        prediction.shape[0] * prediction.shape[1] * prediction.shape[3] * prediction.shape[4],
                        prediction.shape[2])),
                    target64.dimshuffle(0, 1, 3, 4, 2).flatten(1)).sum()
            elif 4 == prediction.ndim:
                ret = TT.nnet.categorical_crossentropy(
                    prediction.dimshuffle(0, 2, 3, 1).reshape((
                        prediction.shape[0] * prediction.shape[2] * prediction.shape[3], prediction.shape[1])),
                    target64.dimshuffle(0, 2, 3, 1).flatten(1)).sum()
            elif 3 == prediction.ndim:
                ret = TT.nnet.categorical_crossentropy(
                    prediction.reshape((
                        prediction.shape[0] * prediction.shape[1], prediction.shape[2])),
                    target64.flatten(1)).sum()
            elif 2 == prediction.ndim:
                ret = TT.nnet.categorical_crossentropy(prediction, target64.flatten(1)).sum()
            else:
                assert False
            return ret
        else:
            if 5 == prediction.ndim:
                #assert 5 == prediction.ndim
                masked_pred = prediction + (TT.ones(1).astype('float32') - TT.shape_padright(mask, 3))
                ret = TT.nnet.categorical_crossentropy(
                    masked_pred.dimshuffle(0, 1, 3, 4, 2).reshape((
                        masked_pred.shape[0] * masked_pred.shape[1] * masked_pred.shape[3] * masked_pred.shape[4],
                        masked_pred.shape[2])),
                    target64.dimshuffle(0, 1, 3, 4, 2).flatten(1))
                ret = ret.reshape((masked_pred.shape[0], masked_pred.shape[1], masked_pred.shape[3], masked_pred.shape[4]))
                ret = ret * TT.shape_padright(mask, 2)
                ret = ret.sum()
            elif 3 == prediction.ndim:
                ret = TT.nnet.categorical_crossentropy(
                    prediction.reshape((
                        prediction.shape[0] * prediction.shape[1], prediction.shape[2])),
                    target64.flatten(1))
                ret = ret.reshape((prediction.shape[0], prediction.shape[1]))
                ret = ret * mask
                ret = ret.sum()
            else:
                assert False
            return ret

    elif "NegativeLogCosine" == cost_func:
        assert 5 == prediction.ndim
        if mask is None:
            ret = (0.5 * TT.log(TT.square(prediction.flatten(3)).sum(axis=2)) +
                   0.5 * TT.log(TT.square(target.flatten(3)).sum(axis=2)) -
                   TT.log((target.flatten(3) * prediction.flatten(3)).sum(axis=2))).sum()
            return ret
        else:
            # TODO Add mask
            assert False


def l1(x):
    """Computes the L1 norm of a tensor
    Parameters
    ----------
    x : Theano tensor
    Returns
    -------
    Theano scalar
        l1 norm (sum of absolute values of elements)
    """
    return TT.sum(abs(x))


def l2(x):
    """Computes the squared L2 norm of a tensor
    Parameters
    ----------
    x : Theano tensor
    Returns
    -------
    Theano scalar
        squared l2 norm (sum of squared values of elements)
    """
    return TT.sum(x**2)


def quick_penalty(tensor_or_tensors, penalty):
    """
    Computes the total cost for applying a specified penalty
    to a tensor or group of tensors.
    Parameters
    ----------
    tensor_or_tensors : Theano tensor or list of tensors
    penalty : 'l1' or 'l2'
    Returns
    -------
    Theano scalar
        a scalar expression for the total penalty cost
    """
    return sum(eval(penalty)(x) for x in tensor_or_tensors)


# TODO quick_conv2d and conv2d_same can be combined
def quick_conv2d(input, filters, border_mode, input_shape=(None, None, None, None),
                 filter_shape=(None, None, None, None), subsample=None):
    assert input.ndim == 4 and filters.ndim == 4
    assert (4 == len(input_shape)) and (4 == len(filter_shape))
    if subsample is not None:
        return TT.nnet.conv2d(input=input, filters=filters, border_mode=border_mode, input_shape=input_shape,
                              filter_shape=filter_shape, subsample=subsample)
    if (tuple(input_shape[2:3]) == (1, 1) and tuple(filter_shape[2:3]) == (1, 1)) or (
                    tuple(filter_shape[2:3]) == (1, 1) and theano.config.device == "cpu"):
        return tensor4dot(input, filters)
    else:
        return TT.nnet.conv2d(input=input, filters=filters, border_mode=border_mode, input_shape=input_shape,
                              filter_shape=filter_shape)


def quick_npy_rng(seed=10000):
    return numpy.random.RandomState(seed=seed)


#def quick_theano_rng(seed=1000):
#    return RandomStreams(seed=seed)
def quick_theano_rng(npy_rng):
    return RandomStreams(npy_rng.randint(1, 2147462579))


def quick_timed_log_eval(logger_func, s, func, *args):
    start = time.time()
    result = func(*args)
    end = time.time()
    logger_func(s + ": " + str(result) + " Time Spent: " + str(end - start))
    return result


def quick_logging_config(path, level=logging.DEBUG):
    print "All Logs will be saved to", os.path.abspath(path)
    logging.basicConfig(filename=path, level=level, format='%(levelname)s:%(message)s')


def quick_reshape_patch(img_tensor, patch_size):
    assert 5 == img_tensor.ndim
    ret = img_tensor.reshape((
        img_tensor.shape[0], img_tensor.shape[1], img_tensor.shape[3] / patch_size, patch_size,
        img_tensor.shape[4] / patch_size, patch_size)).dimshuffle(
        (0, 1, 3, 5, 2, 4)).reshape((img_tensor.shape[0], img_tensor.shape[1], patch_size * patch_size,
                                     img_tensor.shape[3] / patch_size, img_tensor.shape[4] / patch_size))
    return ret


def quick_reshape_patch_back(patch_tensor, patch_size):
    assert 5 == patch_tensor.ndim
    ret = patch_tensor.reshape((
        patch_tensor.shape[0], patch_tensor.shape[1], patch_size, patch_size
        , patch_tensor.shape[3], patch_tensor.shape[4])).dimshuffle((0, 1, 4, 2, 5, 3)).reshape(
        (patch_tensor.shape[0], patch_tensor.shape[1], 1,
         patch_tensor.shape[3] * patch_size, patch_tensor.shape[4] * patch_size))
    return ret


def numpy_floatX(input):
    if theano.config.floatX == 'float32':
        return numpy.float32(input)
    elif theano.config.floatX == 'float64':
        return numpy.float64(input)


def test():
    a = theano.shared(numpy.ones((3, 3, 3, 3)))
    b = theano.shared(numpy.ones((3, 3, 3, 3)))
    c = conv2d_same(a, b)
    f = theano.function([], c)
    print f()
