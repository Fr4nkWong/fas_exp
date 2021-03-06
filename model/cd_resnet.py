import torch
from torch import Tensor
import torch.nn as nn
from typing import Type, Any, Callable, Union, List, Optional

from .conv import CD_Conv2d
from .attention import Sim_AM


"""
DenseNet
"""
def transition_block(in_channels, out_channels):
    """control the number of channels"""
    blk = nn.Sequential(
            nn.BatchNorm2d(in_channels), 
            nn.ReLU(),
            nn.Conv2d(in_channels, out_channels, kernel_size=1),
            nn.AvgPool2d(kernel_size=2, stride=2))
    return blk


"""
ResNet18 + CDC +  SimAM + Multi-scale feature fusion
"""


def conv3x3(in_planes: int, out_planes: int, stride: int = 1, groups: int = 1, dilation: int = 1): # -> nn.Conv2d:
    """3x3 convolution with padding"""
    # return nn.Conv2d(in_planes, out_planes, kernel_size=3, stride=stride, padding=dilation, groups=groups, bias=False, dilation=dilation)
    return CD_Conv2d(in_channels=in_planes, out_channels=out_planes, kernel_size=3, stride=stride,
                    padding=dilation, groups=groups, bias=False, dilation=dilation) # [+]


def conv1x1(in_planes: int, out_planes: int, stride: int = 1) -> nn.Conv2d:
    """1x1 convolution"""
    return nn.Conv2d(in_planes, out_planes, kernel_size=1, stride=stride, bias=False)
    # return CD_Conv2d(in_channels=in_planes, out_channels=out_planes, kernel_size=1, stride=stride, bias=False) # [+]


class BasicBlock(nn.Module):
    """get BasicBlock which layers<50(18,34)"""
    expansion: int = 1

    def __init__(
        self,
        inplanes: int,
        planes: int,
        stride: int = 1,
        downsample: Optional[nn.Module] = None,
        groups: int = 1,
        base_width: int = 64,
        dilation: int = 1,
        norm_layer: Optional[Callable[..., nn.Module]] = None,
        att_mod=None
    ) -> None:
        """
        Args:
            inplanes: num of input channels
            planes: num of output channels
            stride: stride in conv
            downsample: designed downsample layer
            groups: 
            base_width:  
            dilation: padding in conv
            norm_layer: designed normalization layer
        """
        super(BasicBlock, self).__init__()
        if norm_layer is None:
            norm_layer = nn.BatchNorm2d
        if groups != 1 or base_width != 64:
            raise ValueError('BasicBlock only supports groups=1 and base_width=64')
        if dilation > 1:
            raise NotImplementedError("Dilation > 1 not supported in BasicBlock")
        # Both self.conv1 and self.downsample layers downsample the input when stride != 1
        self.conv1 = conv3x3(inplanes, planes, stride)
        self.bn1 = norm_layer(planes)
        self.relu = nn.ReLU(inplace=True)
        self.conv2 = conv3x3(planes, planes)
        self.bn2 = norm_layer(planes)
        self.downsample = downsample
        self.stride = stride
        if att_mod == 'SimAM': # [+]
            self.conv2 = nn.Sequential(
                self.conv2,
                Sim_AM(planes)
            )                                                                                   

    def forward(self, x: Tensor) -> Tensor:
        """
        Residual Connection
        """
        identity = x

        out = self.conv1(x)
        out = self.bn1(out)
        out = self.relu(out)

        out = self.conv2(out)
        out = self.bn2(out)

        if self.downsample is not None:
            identity = self.downsample(x)

        out += identity
        out = self.relu(out)

        return out


class Bottleneck(nn.Module):
    # Bottleneck in torchvision places the stride for downsampling at 3x3 convolution(self.conv2)
    # while original implementation places the stride at the first 1x1 convolution(self.conv1)
    # according to "Deep residual learning for image recognition"https://arxiv.org/abs/1512.03385.
    # This variant is also known as ResNet V1.5 and improves accuracy according to
    # https://ngc.nvidia.com/catalog/model-scripts/nvidia:resnet_50_v1_5_for_pytorch.
    """get Bottleneck which layers>=50"""
    expansion: int = 4

    def __init__(
        self,
        inplanes: int,
        planes: int,
        stride: int = 1,
        downsample: Optional[nn.Module] = None,
        groups: int = 1,
        base_width: int = 64,
        dilation: int = 1,
        norm_layer: Optional[Callable[..., nn.Module]] = None
    ) -> None:
        super(Bottleneck, self).__init__()
        if norm_layer is None:
            norm_layer = nn.BatchNorm2d
        width = int(planes * (base_width / 64.)) * groups
        # Both self.conv2 and self.downsample layers downsample the input when stride != 1
        self.conv1 = conv1x1(inplanes, width)
        self.bn1 = norm_layer(width)
        self.conv2 = conv3x3(width, width, stride, groups, dilation)
        self.bn2 = norm_layer(width)
        self.conv3 = conv1x1(width, planes * self.expansion)
        self.bn3 = norm_layer(planes * self.expansion)
        self.relu = nn.ReLU(inplace=True)
        self.downsample = downsample
        self.stride = stride

    def forward(self, x: Tensor) -> Tensor:
        identity = x

        out = self.conv1(x)
        out = self.bn1(out)
        out = self.relu(out)

        out = self.conv2(out)
        out = self.bn2(out)
        out = self.relu(out)

        out = self.conv3(out)
        out = self.bn3(out)

        if self.downsample is not None:
            identity = self.downsample(x)

        out += identity
        out = self.relu(out)

        return out


class ResNet(nn.Module):

    def __init__(
        self,
        block: Type[Union[BasicBlock, Bottleneck]],
        layers: List[int],
        num_classes: int = 1000,
        zero_init_residual: bool = False,
        groups: int = 1,
        width_per_group: int = 64,
        replace_stride_with_dilation: Optional[List[bool]] = None,
        norm_layer: Optional[Callable[..., nn.Module]] = None,
        in_mod=None,
        att_mod=None
    ) -> None:
        r"""
        Args:
            block: designed block uesd in resnet
            layers: 2D shapes (L, B). L is the number of layers. B is the number of blocks per layer. 
            num_classes: 
            zero_init_residual: 
            groups: 
            width_per_group: width of each group
            replace_stride_with_dilation: 
            norm_layer: normalization layer
        """
        super(ResNet, self).__init__()
        if norm_layer is None:
            norm_layer = nn.BatchNorm2d
        self._norm_layer = norm_layer

        self.inplanes = 64  # the original channel
        self.dilation = 1   # padding in conv
        if replace_stride_with_dilation is None:
            # each element in the tuple indicates if we should replace
            # the 2x2 stride with a dilated convolution instead
            replace_stride_with_dilation = [False, False, False]
        if len(replace_stride_with_dilation) != 3:
            raise ValueError("replace_stride_with_dilation should be None "
                             "or a 3-element tuple, got {}".format(replace_stride_with_dilation))
        self.groups = groups
        self.base_width = width_per_group
        # self.conv1 = nn.Conv2d(3, self.inplanes, kernel_size=7, stride=2, padding=3, bias=False)
        if in_mod == 'Depth': # [+]
            self.conv1 = CD_Conv2d(in_channels=1, out_channels=self.inplanes, kernel_size=7, stride=2, padding=3, bias=False)
        else:
            self.conv1 = CD_Conv2d(in_channels=3, out_channels=self.inplanes, kernel_size=7, stride=2, padding=3, bias=False)
        self.bn1 = norm_layer(self.inplanes)
        self.relu = nn.ReLU(inplace=True)
        self.maxpool = nn.MaxPool2d(kernel_size=3, stride=2, padding=1)
        # init residual blocks
        self.layer1 = self._make_layer(block, 64, layers[0], att_mod=att_mod)
        self.layer2 = self._make_layer(block, 128, layers[1], stride=2,
                                       dilate=replace_stride_with_dilation[0], att_mod=att_mod)
        self.layer3 = self._make_layer(block, 256, layers[2], stride=2,
                                       dilate=replace_stride_with_dilation[1], att_mod=att_mod)
        self.layer4 = self._make_layer(block, 512, layers[3], stride=2,
                                       dilate=replace_stride_with_dilation[2], att_mod=att_mod)
        self.avgpool = nn.AdaptiveAvgPool2d((1, 1))
        self.fc = nn.Linear(512 * block.expansion, num_classes)
        self.downsample_8x8 = nn.Upsample(size=(4, 4), mode='bilinear') # [+] {batchsize:32, wh:128} -> 8
        # [+] mulit-scale fusion
        # self.downsample1_7x7 = nn.Sequential(
        #     nn.Upsample(size=(7,7), mode='bilinear'),
        #     self._norm_layer(128 * block.expansion)
        # )
        # self.downsample2_7x7 = nn.Sequential(
        #     nn.Upsample(size=(7,7), mode='bilinear'),
        #     self._norm_layer(256 * block.expansion)
        # )
        # self.downsample3_7x7 = nn.Sequential(
        #     nn.Upsample(size=(7,7), mode='bilinear'),
        #     self._norm_layer(512 * block.expansion)
        # )
        # self.downsample4_7x7 = nn.Sequential(
        #     nn.Upsample(size=(7,7), mode='bilinear'),
            
        # )
        # init Conv & BN
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='relu')
            elif isinstance(m, (nn.BatchNorm2d, nn.GroupNorm)):
                nn.init.constant_(m.weight, 1)
                nn.init.constant_(m.bias, 0)

        # Zero-initialize the last BN in each residual branch,
        # so that the residual branch starts with zeros, and each residual block behaves like an identity.
        # This improves the model by 0.2~0.3% according to https://arxiv.org/abs/1706.02677
        if zero_init_residual:
            for m in self.modules():
                if isinstance(m, Bottleneck):
                    nn.init.constant_(m.bn3.weight, 0)  # type: ignore[arg-type]
                elif isinstance(m, BasicBlock):
                    nn.init.constant_(m.bn2.weight, 0)  # type: ignore[arg-type]

    def _make_layer(self, block: Type[Union[BasicBlock, Bottleneck]], planes: int, blocks: int,
                    stride: int = 1, dilate: bool = False, att_mod=None) -> nn.Sequential:
        r"""
        factory of making layer
        Args:
            block: designed block
            planes: channels of input
            blocks: num of blocks
            stride: stride in conv
            dilate: replace stride with dilation
        """
        norm_layer = self._norm_layer
        downsample = None
        previous_dilation = self.dilation
        if dilate:
            self.dilation *= stride
            stride = 1
        # expand dimension
        if stride != 1 or self.inplanes != planes * block.expansion:    
            downsample = nn.Sequential(
                conv1x1(self.inplanes, planes * block.expansion, stride),
                norm_layer(planes * block.expansion),
            )

        layers = []
        # adding blocks into layers
        layers.append(block(self.inplanes, planes, stride, downsample, self.groups,
                            self.base_width, previous_dilation, norm_layer, att_mod=att_mod))    # first block
        self.inplanes = planes * block.expansion
        for _ in range(1, blocks):
            layers.append(block(self.inplanes, planes, groups=self.groups,
                                base_width=self.base_width, dilation=self.dilation,
                                norm_layer=norm_layer, att_mod=att_mod))

        return nn.Sequential(*layers)

    def _forward_impl(self, x: Tensor) -> Tensor:
        # See note [TorchScript super()]
        x = self.conv1(x)
        x = self.bn1(x)
        x = self.relu(x)
        x = self.maxpool(x)

        x = self.layer1(x)  # (B,64,56,56) -> (B,64,56,56)
        # print('[backbone]\tlayer1: {}\t'.format(x.size()))
        x1 = self.downsample_8x8(x) # [+]
        x = self.layer2(x)  # (B,64,56,56) -> (B,128,28,28)
        # print('[backbone]\tlayer2: {}\t'.format(x.size()))
        x2 = self.downsample_8x8(x) # [+]
        x = self.layer3(x)  # (B,256,14,14) -> (B,512,14,14)
        # print('[backbone]\tlayer3: {}\t'.format(x.size()))
        x3 = self.downsample_8x8(x) # [+]
        x = self.layer4(x)  # (B,256,14,14) -> (B,512,7,7)
        # x = self._norm_layer(512)
        # print('[backbone]\tlayer4: {}\t'.format(x.size()))
        x = torch.cat([x1,x2,x3,x], dim=1) # [+]
        # x = self.avgpool(x)
        # x = torch.flatten(x, 1)
        # x = self.fc(x)

        return x

    def forward(self, x: Tensor) -> Tensor:
        return self._forward_impl(x)


def _resnet(
    arch: str,
    block: Type[Union[BasicBlock, Bottleneck]],
    layers: List[int],
    pretrained: bool,
    progress: bool,
    **kwargs: Any
) -> ResNet:
    r"""
    factory of making resnet
    Args:
        arch: type of resnet
        block: designed block uesd in resnet
        layers: 2D shapes (L, B). L is the number of layers. B is the number of blocks per layer. 
    """
    model = ResNet(block, layers, **kwargs)
    return model



def resnet18(pretrained: bool = False, progress: bool = True, **kwargs: Any) -> ResNet:
    r"""ResNet-18 model from
    `"Deep Residual Learning for Image Recognition" <https://arxiv.org/pdf/1512.03385.pdf>`_.

    Args:
        pretrained (bool): If True, returns a model pre-trained on ImageNet
        progress (bool): If True, displays a progress bar of the download to stderr
    """
    return _resnet('resnet18', BasicBlock, [2, 2, 2, 2], pretrained, progress,
                   **kwargs)




def resnet34(pretrained: bool = False, progress: bool = True, **kwargs: Any) -> ResNet:
    r"""ResNet-34 model from
    `"Deep Residual Learning for Image Recognition" <https://arxiv.org/pdf/1512.03385.pdf>`_.

    Args:
        pretrained (bool): If True, returns a model pre-trained on ImageNet
        progress (bool): If True, displays a progress bar of the download to stderr
    """
    return _resnet('resnet34', BasicBlock, [3, 4, 6, 3], pretrained, progress,
                   **kwargs)




def resnet50(pretrained: bool = False, progress: bool = True, **kwargs: Any) -> ResNet:
    r"""ResNet-50 model from
    `"Deep Residual Learning for Image Recognition" <https://arxiv.org/pdf/1512.03385.pdf>`_.

    Args:
        pretrained (bool): If True, returns a model pre-trained on ImageNet
        progress (bool): If True, displays a progress bar of the download to stderr
    """
    return _resnet('resnet50', Bottleneck, [3, 4, 6, 3], pretrained, progress,
                   **kwargs)



import torch.nn.functional as func


class RGB_net(nn.Module):
    def __init__(self):
        super(RGB_net, self).__init__()
        self.net = resnet18(
            att_mod='SimAM'
        )
        # features_rgb = list(net.children())
        # self.net = nn.Sequential(*features_rgb[0:8])
        self.gavg_pool = nn.AdaptiveAvgPool2d(1)
        self.classifier = nn.Sequential(
            nn.Linear(960,1),
            nn.Sigmoid()
        )

    def forward(self, x):
        """
        Args:
            x: rgb-image. (B,3,224,224)
        """
        y = self.net(x)
        # print('[RGB-backbone]\ty_rgb: {}'.format(y.size()))
        gap = self.gavg_pool(y).squeeze()
        gap = func.sigmoid(gap)
        # print('[RGB-backbone]\ty_rgb: {}\tgap_rgb: {}'.format(y.size(), gap.size()))
        p = self.classifier(gap)
        return gap, p


class Depth_net(nn.Module):
    def __init__(self):
        super(Depth_net, self).__init__()
        self.net = resnet18(
            in_mod='Depth',
            att_mod='SimAM'
        )
        # features_d = list(net.children())
        # temp_layer = list(features_d[0].children())
        # temp_layer = temp_layer[0]
        # mean_weight = np.mean(temp_layer.weight.data.detach().numpy(),axis=1)
        # new_weight = np.zeros((64,1,7,7))
        # for i in range(1):
        #     new_weight[:,i,:,:]=mean_weight
        # features_d[0]=nn.Conv2d(1, 64, kernel_size=(7, 7), stride=(2, 2), padding=(3, 3), bias=False)
        # features_d[0].weight.data = torch.Tensor(new_weight)
        # self.net = nn.Sequential(*features_d[0:8])
        self.gavg_pool = nn.AdaptiveAvgPool2d(1)
        self.classifier = nn.Sequential(
            nn.Linear(960,1),
            nn.Sigmoid()
        )
    
    def forward(self, x):
        """
        Args:
            x: d-image. (B,1,128,128)
        """
        y = self.net(x)
        # print('[D-backbone]\ty_d: {}'.format(y.size()))
        gap = self.gavg_pool(y).squeeze()
        gap = func.sigmoid(gap)
        #print('[D-backbone]\ty_d: {}\tgap_d: {}'.format(y.size(), gap.size()))
        q = self.classifier(gap)
        return gap, q