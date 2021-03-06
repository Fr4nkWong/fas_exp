import math

import torch
import torch.nn as nn

# from .SqueezeNet import RGB_net, Depth_net
# from .MobileNet import RGB_net, Depth_net
# from .ResNet import RGB_net, Depth_net
# from .DenseNet import RGB_net, Depth_net
# from .Res2Net import RGB_net, Depth_net
from .cd_resnet import RGB_net, Depth_net


class RGBD_model(nn.Module):
    """
    RGB-D Architecture
    """
    def __init__(self, device):
        """
        Args:
            device
        """
        super(RGBD_model, self).__init__()
        self.rgb_net = RGB_net().to(device)
        self.depth_net = Depth_net().to(device)
        self.classifier = nn.Sequential(
            # nn.Sigmoid(),
            nn.Linear(1920,1), # diy by backbone
            nn.Sigmoid()
        )

    def forward(self, x_rgb, x_d):
        """"
        Args:
            x_rgb: rgb-image. [B,3,W,W]
            x_d: d-image. [B,3,W,W]
        Returns:
            p: prob of live in rgb
            q: prob of live in depth
            r: prob of live. the final score.
        """
        x_d = x_d[:,0:1,:,:]
        # print('[RGBD-backbone]\tx_rgb: {}\tx_d: {}'.format(x_rgb.size(), x_d.size()))
        gap_rgb, p = self.rgb_net(x_rgb)
        # print('[RGB-head]\tgap_rgb: {}\tp: {}'.format(gap_rgb.size(), p.size()))
        
        gap_d, q = self.depth_net(x_d)
        # print('[D-head]\tgap_d: {}\tq: {}'.format(gap_d.size(), q.size()))

        gap = torch.cat([gap_rgb,gap_d], dim=1)
        r = self.classifier(gap)
        # print('[RGBD-head]\t gap: {}\t r: {}'.format(gap.size(), r.size()))
        # print('[RGBD-head]\t p:\t',output[2].squeeze(1))
        # print('[RGBD-head]\t q:\t',output[3].squeeze(1))
        # print('[RGBD-head]\t r:\t',output[1].squeeze(1))
        return gap, r, p, q
