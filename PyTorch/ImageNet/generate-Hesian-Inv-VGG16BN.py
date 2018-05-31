"""
This code generate Hessian inverse for VGG16 BN version
"""

import torch
from hessian_utils import generate_hessian, generate_hessian_inv_Woodbury
from models.vgg_layer_input import vgg16_bn

import os
from datetime import datetime
from numpy.linalg import inv, pinv, LinAlgError
import numpy as np

import torch.backends.cudnn as cudnn
import torchvision.datasets as datasets
import torchvision.transforms as transforms

# Detect whether there is GPU.
use_cuda = torch.cuda.is_available()
# -------------------------------- User Config ----------------------------------------------
# If you meet the error of "Tensor in different GPUs", please set the following line
# in both this .py and hessian_utils.py to force them to share the same GPU.
# os.environ["CUDA_VISIBLE_DEVICES"] = "0"
# Parameters and path to specify
hessian_batch_size = 2
hessian_inv_save_root = './VGG16/hessian_inv'
if not os.path.exists(hessian_inv_save_root):
    os.makedirs(hessian_inv_save_root)
hessian_save_root = './VGG16/hessian'
if not os.path.exists(hessian_save_root):
    os.makedirs(hessian_save_root)
traindir = '/home/shangyu/imagenet-train' # Set you imagenet train data path here
pretrain_model_path = './VGG16/vgg16_bn-6c64b313.pth'
use_Woodbury = True
# -------------------------------- User Config ----------------------------------------------
# Load pretrain model
pretrain = torch.load(pretrain_model_path)
net = vgg16_bn()
net.load_state_dict(pretrain)

# Layer name of VGG16BN
layer_name_list = [
    'features.0',
    'features.3',
    'features.7',
    'features.10',
    'features.14',
    'features.17',
    'features.20',
    'features.24',
    'features.27',
    'features.30',
    'features.34',
    'features.37',
    'features.40',
    'classifier.0',
    'classifier.3',
    'classifier.6'
]
# In my test, prunning in these layer will cause nan if hessian is generated by normal method,
# I specifically set these layer to use Woodbury here. 
use_Woodbury_list = [
    'features.34',
    'features.37',
    'features.40',
    'classifier.0',
    'classifier.3',
    'classifier.6'
]

# Generate Hessian

print('==> Preparing data..')
normalize = transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])

trainDataset = datasets.ImageFolder(traindir, transforms.Compose([
		transforms.RandomResizedCrop(224),
		transforms.RandomHorizontalFlip(),
		transforms.ToTensor(),
		normalize,
	]))

hessian_loader = torch.utils.data.DataLoader(trainDataset, batch_size = hessian_batch_size, shuffle=True)
print ('[%s] Finish process data' % datetime.now())

if use_cuda:
    net.cuda()
    net = torch.nn.DataParallel(net, device_ids=range(torch.cuda.device_count()))
    cudnn.benchmark = True

for layer_name in layer_name_list:
    print ('[%s] %s' %(datetime.now(), layer_name))
    if layer_name in use_Woodbury_list:
        use_Woodbury = True
    else:
        use_Woodbury = False
    print ('[%s] %s. Method: %s' %(datetime.now(), layer_name, 'Woodbury' if use_Woodbury else 'Normal'))
    # Generate Hessian
    if layer_name.startswith('features'):
        if use_Woodbury:
            hessian_inv = generate_hessian_inv_Woodbury(net = net, trainloader = hessian_loader, \
                        layer_name = layer_name, layer_type = 'C', \
                        n_batch_used = 100, 
                        batch_size = hessian_batch_size, stride_factor = 5)
        else:
            hessian = generate_hessian(net = net, trainloader = hessian_loader, \
                        layer_name = layer_name, layer_type = 'C', \
                        n_batch_used = 100, 
                        batch_size = hessian_batch_size, stride_factor = 5)
    elif layer_name.startswith('classifier'):
        if use_Woodbury:
            hessian_inv = generate_hessian_inv_Woodbury(net = net, trainloader = hessian_loader, \
                        layer_name = layer_name, layer_type = 'F', \
                        n_batch_used = 100, 
                        batch_size = hessian_batch_size)
        else:
            hessian = generate_hessian(net = net, trainloader = hessian_loader, \
                        layer_name = layer_name, layer_type = 'F', \
                        n_batch_used = 100, 
                        batch_size = hessian_batch_size)
    if not use_Woodbury:
        np.save('%s/%s.npy' %(hessian_save_root, layer_name), hessian)
        # Inverse Hessian
        try:
            hessian_inv = inv(hessian)
        except LinAlgError:
            print LinAlgError
            hessian_inv = pinv(hessian)
    # Save hessian inverse 
    np.save('%s/%s.npy' %(hessian_inv_save_root, layer_name), hessian_inv)