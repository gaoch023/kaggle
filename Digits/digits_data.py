#!/usr/bin/python

import os
import numpy as np

from pylearn2.datasets.dense_design_matrix import DenseDesignMatrix
from pylearn2.datasets import preprocessing
import pylearn2.utils.serial as serial

from PIL import Image

DATA_DIR = '/home/nico/datasets/Kaggle/Digits/'

def initial_read():
    #create the training & test sets, skipping the header row with [1:]
    dataset = np.genfromtxt(open(DATA_DIR+'train.csv','r'), delimiter=',', dtype='f8')[1:]
    targets = [x[0] for x in dataset]
    train = [x[1:] for x in dataset]
    test = np.genfromtxt(open(DATA_DIR+'test.csv','r'), delimiter=',', dtype='f8')[1:]
    
    # transform
    train = np.reshape(np.array(train), (-1,28,28))
    test = np.reshape(np.array(test), (-1,28,28))
    targets = np.array(targets)
    
    # pickle
    np.save(DATA_DIR+'train', train)
    np.save(DATA_DIR+'test', test)
    np.save(DATA_DIR+'targets', targets)
    
class Digits(DenseDesignMatrix):
    
    def __init__(self, which_set, start=None, stop=None, preprocessor=None, axes=['c', 0, 1, 'b']):
        assert which_set in ['train','test']
        
        X = np.load(os.path.join(DATA_DIR,which_set+'.npy'))
        X = np.cast['float32'](X)
        
        if which_set == 'test':
            # dummy targets
            y = np.zeros((X.shape[0],10))
        else:
            y = np.load(os.path.join(DATA_DIR,'targets.npy'))
            one_hot = np.zeros((y.shape[0],10),dtype='float32')
            for i in xrange(y.shape[0]):
                one_hot[i,int(y[i])] = 1.
            y = one_hot
        
        def dimshuffle(b01c):
            default = ('b', 0, 1, 'c')
            return b01c.transpose(*[default.index(axis) for axis in axes])
        
        if start is not None:
            assert start >= 0
            assert stop > start
            assert stop <= X.shape[0]
            X = X[start:stop, :, :]
            y = y[start:stop]
            assert X.shape[0] == y.shape[0]
        
        topo_view = X
        m, r, c = topo_view.shape
        assert r == 28
        assert c == 28
        topo_view = topo_view.reshape(m,r,c,1)
        
        super(Digits,self).__init__(topo_view = dimshuffle(topo_view), y=y, axes=axes)
        
        assert not np.any(np.isnan(self.X))

def get_dataset(tot=False, preprocessor='normal'):
    if not os.path.exists(DATA_DIR+'train.npy') or \
        not os.path.exists(DATA_DIR+'test.npy') or \
        not os.path.exists(DATA_DIR+'targets.npy'):
        initial_read()
    
    train_path = DATA_DIR+'train_'+preprocessor+'_preprocessed.pkl'
    valid_path = DATA_DIR+'valid_'+preprocessor+'_preprocessed.pkl'
    tottrain_path = DATA_DIR+'tottrain_'+preprocessor+'_preprocessed.pkl'
    test_path = DATA_DIR+'test_'+preprocessor+'_preprocessed.pkl'
    
    if os.path.exists(train_path) and os.path.exists(valid_path) and os.path.exists(test_path):
        
        print 'loading preprocessed data'
        trainset = serial.load(train_path)
        validset = serial.load(valid_path)
        if tot:
            tottrainset = serial.load(tottrain_path)
        testset = serial.load(test_path)
    else:
        
        print 'loading raw data...'
        trainset = Digits(which_set='train', start=0, stop=34000)
        validset = Digits(which_set='train', start=34000, stop=42000)
        tottrainset = Digits(which_set='train')
        testset = Digits(which_set='test')
        
        print 'preprocessing data...'
        pipeline = preprocessing.Pipeline()
        pipeline.items.append(preprocessing.GlobalContrastNormalization(sqrt_bias=10., use_std=True))
        
        if preprocessor != 'nozca':
            # ZCA = zero-phase component analysis
            # very similar to PCA, but preserves the look of the original image better
            pipeline.items.append(preprocessing.ZCA())
        
        # note the can_fit=False's: no sharing between train and valid data
        trainset.apply_preprocessor(preprocessor=pipeline, can_fit=True)
        validset.apply_preprocessor(preprocessor=pipeline, can_fit=False)
        tottrainset.apply_preprocessor(preprocessor=pipeline, can_fit=True)
        testset.apply_preprocessor(preprocessor=pipeline, can_fit=False)
        
        if preprocessor == 'rotated':
            pass
        
        # this uses numpy format for storage instead of pickle, for memory reasons
        trainset.use_design_loc(DATA_DIR+'train_'+preprocessor+'_design.npy')
        validset.use_design_loc(DATA_DIR+'valid_'+preprocessor+'_design.npy')
        tottrainset.use_design_loc(DATA_DIR+'tottrain_'+preprocessor+'_design.npy')
        testset.use_design_loc(DATA_DIR+'test_'+preprocessor+'_design.npy')
        # this path can be used for visualizing weights after training is done
        trainset.yaml_src = '!pkl: "%s"' % train_path
        validset.yaml_src = '!pkl: "%s"' % valid_path
        tottrainset.yaml_src = '!pkl: "%s"' % tottrain_path
        testset.yaml_src = '!pkl: "%s"' % test_path
        
        print 'saving preprocessed data...'
        serial.save(train_path, trainset)
        serial.save(valid_path, validset)
        serial.save(tottrain_path, tottrainset)
        serial.save(test_path, testset)
        
    if tot:
        return tottrainset, validset, testset
    else:
        return trainset, validset, testset
    
if __name__ == '__main__':
    pass
