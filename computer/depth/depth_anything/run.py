import sys
from os.path import abspath, dirname
sys.path.append(abspath(dirname(__file__)))

import argparse
import cv2
import numpy as np
import torch
import torch.nn.functional as F
from torchvision.transforms import Compose
from tqdm import tqdm

from .depth_anything.dpt import DepthAnything
from .depth_anything.util.transform import Resize, NormalizeImage, PrepareForNet

# NOTE: This is a slightly modified version of:
# https://github.com/LiheYoung/Depth-Anything/blob/main/run.py at commit 1d03336771fe09c5398ffdd211441e33941a97dc
# (or https://github.com/LiheYoung/Depth-Anything/blob/1d03336771fe09c5398ffdd211441e33941a97dc/run.py)
# to better work with the robot on M1 (but note this is from mid 2024, so you're probably better off starting anew)

################
# Instructions #
################
# Clone the Depth Anything repository (inside the 'depth' folder) and rename it to depth_anything.
# Replace run.py and dpt.py (inside a second depth_anything folder) with the provided files.
# The structure should look like this:
# depth
# ├── depth_anything
# │   ├── depth_anything
# │   │   ├── dpt.py
# │   └── run.py
# ├── calculate_depth_with_depth_anything.py
# Remember to install the requirements from the Depth Anything repository (requirements.txt)

###############
# Performance #
###############
# M1 Max 64 GB RAM: Average depth calculation time over 174 iterations: 0.099 seconds

#################
# Configuration #
#################
ENCODER='vits' # 'vits' | 'vitb' | 'vitl'

if torch.backends.mps.is_available():
    DEVICE = torch.device("mps")
elif torch.cuda.is_available():
    DEVICE = torch.device("cuda")
else:
    DEVICE = torch.device("cpu")
    
depth_anything = DepthAnything.from_pretrained('LiheYoung/depth_anything_{}14'.format(ENCODER)).to(DEVICE).eval()

total_params = sum(param.numel() for param in depth_anything.parameters())
print('Total parameters: {:.2f}M'.format(total_params / 1e6))

def get_depth(raw_image, grayscale=False):
    transform = Compose([
        Resize(
            width=518,
            height=518,
            resize_target=False,
            keep_aspect_ratio=True,
            ensure_multiple_of=14,
            resize_method='lower_bound',
            image_interpolation_method=cv2.INTER_CUBIC,
        ),
        NormalizeImage(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        PrepareForNet(),
    ])
    
    image = cv2.cvtColor(raw_image, cv2.COLOR_BGR2RGB) / 255.0
    
    h, w = image.shape[:2]
    
    image = transform({'image': image})['image']
    image = torch.from_numpy(image).unsqueeze(0).to(DEVICE)
    
    with torch.no_grad():
        depth = depth_anything(image)
    
    depth = F.interpolate(depth[None], (h, w), mode='bilinear', align_corners=False)[0, 0]
    depth = (depth - depth.min()) / (depth.max() - depth.min()) * 255.0
    
    depth = depth.cpu().numpy().astype(np.uint8)
    
    if grayscale:
        depth = np.repeat(depth[..., np.newaxis], 3, axis=-1)
    else:
        depth = cv2.applyColorMap(depth, cv2.COLORMAP_INFERNO)
    
    return depth
    