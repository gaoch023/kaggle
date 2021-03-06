#!/usr/bin/python

'''
Data class in pylearn2 format
'''

import os
import numpy as np

from pylearn2.datasets.dense_design_matrix import DenseDesignMatrix, DefaultViewConverter
from pylearn2.datasets import preprocessing
import pylearn2.utils.serial as serial

DATA_DIR = '/home/nico/datasets/Kaggle/WhaleRedux/'


class ExtractGridPatchesWithY(preprocessing.ExtractGridPatches):
    """
    Converts a dataset of images into a dataset of patches extracted along a
    regular grid from each image.  The order of the images is
    preserved, and so are the targets.
    """
    def __init__(self, patch_shape, patch_stride):
        self.patch_shape = patch_shape
        self.patch_stride = patch_stride

    def apply(self, dataset, can_fit=False):
        X = dataset.get_topological_view()
        y = dataset.y
        num_topological_dimensions = len(X.shape) - 2
        if num_topological_dimensions != len(self.patch_shape):
            raise ValueError("ExtractGridPatches with "
                             + str(len(self.patch_shape))
                             + " topological dimensions called on"
                             + " dataset with " +
                             str(num_topological_dimensions) + ".")
        num_patches = X.shape[0]
        max_strides = [X.shape[0] - 1]
        for i in xrange(num_topological_dimensions):
            patch_width = self.patch_shape[i]
            data_width = X.shape[i + 1]
            last_valid_coord = data_width - patch_width
            if last_valid_coord < 0:
                raise ValueError('On topological dimension ' + str(i) +
                                 ', the data has width ' + str(data_width) +
                                 ' but the requested patch width is ' +
                                 str(patch_width))
            stride = self.patch_stride[i]
            if stride == 0:
                max_stride_this_axis = 0
            else:
                max_stride_this_axis = last_valid_coord / stride
            num_strides_this_axis = max_stride_this_axis + 1
            max_strides.append(max_stride_this_axis)
            num_patches *= num_strides_this_axis
        # batch size
        output_shape = [num_patches]
        # topological dimensions
        for dim in self.patch_shape:
            output_shape.append(dim)
        # number of channels
        output_shape.append(X.shape[-1])
        output = np.zeros(output_shape, dtype=X.dtype)
        channel_slice = slice(0, X.shape[-1])
        coords = [0] * (num_topological_dimensions + 1)
        keep_going = True
        i = 0
        while keep_going:
            args = [coords[0]]
            for j in xrange(num_topological_dimensions):
                coord = coords[j + 1] * self.patch_stride[j]
                args.append(slice(coord, coord + self.patch_shape[j]))
            args.append(channel_slice)
            patch = X[args]
            output[i, :] = patch
            i += 1
            # increment coordinates
            j = 0
            keep_going = False
            while not keep_going:
                if coords[-(j + 1)] < max_strides[-(j + 1)]:
                    coords[-(j + 1)] += 1
                    keep_going = True
                else:
                    coords[-(j + 1)] = 0
                    if j == num_topological_dimensions:
                        break
                    j = j + 1
        dataset.set_topological_view(output)
        dataset.y = np.repeat(y,num_patches/len(y),axis=0)

class WhaleRedux(DenseDesignMatrix):
    
    def __init__(self, which_set, which_data, start=None, stop=None, preprocessor=None):
        assert which_set in ['train','test']
        assert which_data in ['melspectrum','specfeat']
        
        X = np.load(os.path.join(DATA_DIR,which_set+'_'+which_data+'.npy'))
        X = np.cast['float32'](X)
        # X needs to be 1D, shape info is stored in view_converter
        X = np.reshape(X,(X.shape[0], np.prod(X.shape[1:])))
        
        if which_set == 'test':
            # dummy targets
            y = np.zeros((X.shape[0],2))
        else:
            y = np.load(os.path.join(DATA_DIR,'targets.npy'))
            
        if start is not None:
            assert start >= 0
            assert stop > start
            assert stop <= X.shape[0]
            X = X[start:stop, :]
            y = y[start:stop]
            assert X.shape[0] == y.shape[0]
            
        if which_data == 'melspectrum':
            # 2D data with 1 channel
            # do not change in case you extract patches, pylearn handles this!
            view_converter = DefaultViewConverter((67,40,1))
        elif which_data == 'specfeat':
            # 24 channels with 1D data
            # do not change in case you extract patches, pylearn handles this!
            view_converter = DefaultViewConverter((67,1,24))
            
        super(WhaleRedux,self).__init__(X=X, y=y, view_converter=view_converter)
        
        assert not np.any(np.isnan(self.X))
        
        if preprocessor:
            preprocessor.apply(self)


def get_dataset(which_data, tot=False):
    train_path = DATA_DIR+'train_'+which_data+'_preprocessed.pkl'
    valid_path = DATA_DIR+'valid_'+which_data+'_preprocessed.pkl'
    tottrain_path = DATA_DIR+'tottrain_'+which_data+'_preprocessed.pkl'
    test_path = DATA_DIR+'test_'+which_data+'_preprocessed.pkl'
    
    if os.path.exists(train_path) and os.path.exists(valid_path) and os.path.exists(test_path):
        
        print 'loading preprocessed data'
        trainset = serial.load(train_path)
        validset = serial.load(valid_path)
        if tot:
            tottrainset = serial.load(tottrain_path)
        testset = serial.load(test_path)
    else:
        
        print 'loading raw data...'
        trainset = WhaleRedux(which_set='train', which_data=which_data, start=0, stop=40000)
        validset = WhaleRedux(which_set='train', which_data=which_data, start=40000, stop=47841)
        tottrainset = WhaleRedux(which_set='train', which_data=which_data)
        testset = WhaleRedux(which_set='test', which_data=which_data)
        
        print 'preprocessing data...'
        pipeline = preprocessing.Pipeline()
        
        if which_data == 'melspectrum':
            #pipeline.items.append(ExtractGridPatchesWithY(patch_shape=(16,16),patch_stride=(8,8)))
            pipeline.items.append(preprocessing.Standardize(global_mean=True, global_std=True))
            #pipeline.items.append(preprocessing.GlobalContrastNormalization(sqrt_bias=10., use_std=True))
            # ZCA = zero-phase component analysis
            # very similar to PCA, but preserves the look of the original image better
            pipeline.items.append(preprocessing.ZCA())
        else:
            #pipeline.items.append(ExtractGridPatchesWithY(patch_shape=(16,1),patch_stride=(8,1)))
            # global_mean/std=False voor per-feature standardization
            pipeline.items.append(preprocessing.Standardize(global_mean=False, global_std=False))
        
        trainset.apply_preprocessor(preprocessor=pipeline, can_fit=True)
        # this uses numpy format for storage instead of pickle, for memory reasons
        trainset.use_design_loc(DATA_DIR+'train_'+which_data+'_design.npy')
        # note the can_fit=False: no sharing between train and valid data
        validset.apply_preprocessor(preprocessor=pipeline, can_fit=False)
        validset.use_design_loc(DATA_DIR+'valid_'+which_data+'_design.npy')
        tottrainset.apply_preprocessor(preprocessor=pipeline, can_fit=True)
        tottrainset.use_design_loc(DATA_DIR+'tottrain_'+which_data+'_design.npy')
        # note the can_fit=False: no sharing between train and test data
        testset.apply_preprocessor(preprocessor=pipeline, can_fit=False)
        testset.use_design_loc(DATA_DIR+'test_'+which_data+'_design.npy')
        
        # this path can be used for visualizing weights after training is done
        trainset.yaml_src = '!pkl: "%s"' % train_path
        validset.yaml_src = '!pkl: "%s"' % valid_path
        tottrainset.yaml_src = '!pkl: "%s"' % tottrain_path
        testset.yaml_src = '!pkl: "%s"' % test_path
        
        print 'saving preprocessed data...'
        serial.save(DATA_DIR+'train_'+which_data+'_preprocessed.pkl', trainset)
        serial.save(DATA_DIR+'valid_'+which_data+'_preprocessed.pkl', validset)
        serial.save(DATA_DIR+'tottrain_'+which_data+'_preprocessed.pkl', tottrainset)
        serial.save(DATA_DIR+'test_'+which_data+'_preprocessed.pkl', testset)
        
    if tot:
        return tottrainset, validset, testset
    else:
        return trainset, validset, testset

if __name__ == '__main__':
    pass
