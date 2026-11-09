"""MiniFASNet (V1, V2, V1SE, V2SE) — reimplementação da arquitetura do Silent-Face-Anti-Spoofing
(MiniVision, Apache 2.0) para carregar os pesos oficiais sem executar o código do repositório.
Os nomes dos atributos seguem o original para que o state_dict encaixe sem renomear chaves.
"""
import torch
from torch.nn import (AdaptiveAvgPool2d, BatchNorm1d, BatchNorm2d, Conv2d, Dropout, Linear, Module, PReLU,
                      ReLU, Sequential, Sigmoid)


class Flatten(Module):
    def forward(self, x):
        return x.view(x.size(0), -1)


class Conv_block(Module):
    def __init__(self, in_c, out_c, kernel=(1, 1), stride=(1, 1), padding=(0, 0), groups=1):
        super().__init__()
        self.conv = Conv2d(in_c, out_c, kernel_size=kernel, groups=groups, stride=stride, padding=padding, bias=False)
        self.bn = BatchNorm2d(out_c)
        self.prelu = PReLU(out_c)

    def forward(self, x):
        return self.prelu(self.bn(self.conv(x)))


class Linear_block(Module):
    def __init__(self, in_c, out_c, kernel=(1, 1), stride=(1, 1), padding=(0, 0), groups=1):
        super().__init__()
        self.conv = Conv2d(in_c, out_c, kernel_size=kernel, groups=groups, stride=stride, padding=padding, bias=False)
        self.bn = BatchNorm2d(out_c)

    def forward(self, x):
        return self.bn(self.conv(x))


class SEModule(Module):
    def __init__(self, channels, reduction):
        super().__init__()
        self.avg_pool = AdaptiveAvgPool2d(1)
        self.fc1 = Conv2d(channels, channels // reduction, kernel_size=1, padding=0, bias=False)
        self.bn1 = BatchNorm2d(channels // reduction)
        self.relu = ReLU(inplace=True)
        self.fc2 = Conv2d(channels // reduction, channels, kernel_size=1, padding=0, bias=False)
        self.bn2 = BatchNorm2d(channels)
        self.sigmoid = Sigmoid()

    def forward(self, x):
        s = self.sigmoid(self.bn2(self.fc2(self.relu(self.bn1(self.fc1(self.avg_pool(x)))))))
        return x * s


class Depth_Wise(Module):
    def __init__(self, c1, c2, c3, residual=False, kernel=(3, 3), stride=(2, 2), padding=(1, 1), groups=1, se_reduct=None):
        super().__init__()
        self.conv = Conv_block(c1[0], c1[1], kernel=(1, 1), padding=(0, 0), stride=(1, 1))
        self.conv_dw = Conv_block(c2[0], c2[1], groups=c2[0], kernel=kernel, padding=padding, stride=stride)
        self.project = Linear_block(c3[0], c3[1], kernel=(1, 1), padding=(0, 0), stride=(1, 1))
        self.residual = residual
        if se_reduct is not None:
            self.se_module = SEModule(c3[1], se_reduct)

    def forward(self, x):
        out = self.project(self.conv_dw(self.conv(x)))
        if self.residual:
            if hasattr(self, "se_module"):
                out = self.se_module(out)
            return x + out
        return out


class Residual(Module):
    """Sequência de blocos residuais; com se=True o último bloco leva Squeeze-and-Excitation."""
    def __init__(self, c1, c2, c3, num_block, groups, kernel=(3, 3), stride=(1, 1), padding=(1, 1), se=False, se_reduct=4):
        super().__init__()
        blocks = []
        for i in range(num_block):
            last = se and i == num_block - 1
            blocks.append(Depth_Wise(c1[i], c2[i], c3[i], residual=True, kernel=kernel, padding=padding, stride=stride,
                                     groups=groups, se_reduct=se_reduct if last else None))
        self.model = Sequential(*blocks)

    def forward(self, x):
        return self.model(x)


class MiniFASNet(Module):
    def __init__(self, keep, embedding_size=128, conv6_kernel=(7, 7), drop_p=0.0, num_classes=3, img_channel=3, se=False):
        super().__init__()
        k = keep
        self.embedding_size = embedding_size
        self.conv1 = Conv_block(img_channel, k[0], kernel=(3, 3), stride=(2, 2), padding=(1, 1))
        self.conv2_dw = Conv_block(k[0], k[1], kernel=(3, 3), stride=(1, 1), padding=(1, 1), groups=k[1])
        self.conv_23 = Depth_Wise((k[1], k[2]), (k[2], k[3]), (k[3], k[4]), kernel=(3, 3), stride=(2, 2), padding=(1, 1), groups=k[3])
        self.conv_3 = Residual([(k[4], k[5]), (k[7], k[8]), (k[10], k[11]), (k[13], k[14])],
                               [(k[5], k[6]), (k[8], k[9]), (k[11], k[12]), (k[14], k[15])],
                               [(k[6], k[7]), (k[9], k[10]), (k[12], k[13]), (k[15], k[16])],
                               num_block=4, groups=k[4], se=se)
        self.conv_34 = Depth_Wise((k[16], k[17]), (k[17], k[18]), (k[18], k[19]), kernel=(3, 3), stride=(2, 2), padding=(1, 1), groups=k[19])
        self.conv_4 = Residual([(k[19], k[20]), (k[22], k[23]), (k[25], k[26]), (k[28], k[29]), (k[31], k[32]), (k[34], k[35])],
                               [(k[20], k[21]), (k[23], k[24]), (k[26], k[27]), (k[29], k[30]), (k[32], k[33]), (k[35], k[36])],
                               [(k[21], k[22]), (k[24], k[25]), (k[27], k[28]), (k[30], k[31]), (k[33], k[34]), (k[36], k[37])],
                               num_block=6, groups=k[19], se=se)
        self.conv_45 = Depth_Wise((k[37], k[38]), (k[38], k[39]), (k[39], k[40]), kernel=(3, 3), stride=(2, 2), padding=(1, 1), groups=k[40])
        self.conv_5 = Residual([(k[40], k[41]), (k[43], k[44])], [(k[41], k[42]), (k[44], k[45])], [(k[42], k[43]), (k[45], k[46])],
                               num_block=2, groups=k[40], se=se)
        self.conv_6_sep = Conv_block(k[46], k[47], kernel=(1, 1), stride=(1, 1), padding=(0, 0))
        self.conv_6_dw = Linear_block(k[47], k[48], groups=k[48], kernel=conv6_kernel, stride=(1, 1), padding=(0, 0))
        self.conv_6_flatten = Flatten()
        self.linear = Linear(512, embedding_size, bias=False)
        self.bn = BatchNorm1d(embedding_size)
        self.drop = Dropout(p=drop_p)
        self.prob = Linear(embedding_size, num_classes, bias=False)

    def forward(self, x):
        out = self.conv1(x)
        out = self.conv2_dw(out)
        out = self.conv_23(out)
        out = self.conv_3(out)
        out = self.conv_34(out)
        out = self.conv_4(out)
        out = self.conv_45(out)
        out = self.conv_5(out)
        out = self.conv_6_sep(out)
        out = self.conv_6_dw(out)
        out = self.conv_6_flatten(out)
        if self.embedding_size != 512:
            out = self.linear(out)
        out = self.bn(out)
        out = self.drop(out)
        return self.prob(out)


KEEP = {
    "1.8M": [32, 32, 103, 103, 64, 13, 13, 64, 26, 26, 64, 13, 13, 64, 52, 52, 64, 231, 231, 128,
             154, 154, 128, 52, 52, 128, 26, 26, 128, 52, 52, 128, 26, 26, 128, 26, 26, 128, 308, 308,
             128, 26, 26, 128, 26, 26, 128, 512, 512],
    "1.8M_": [32, 32, 103, 103, 64, 13, 13, 64, 13, 13, 64, 13, 13, 64, 13, 13, 64, 231, 231, 128, 231, 231, 128, 52,
              52, 128, 26, 26, 128, 77, 77, 128, 26, 26, 128, 26, 26, 128, 308, 308, 128, 26, 26, 128, 26, 26, 128, 512, 512],
}


def build(model_type: str, conv6_kernel=(5, 5)) -> MiniFASNet:
    keep = KEEP["1.8M"] if model_type in ("MiniFASNetV1", "MiniFASNetV1SE") else KEEP["1.8M_"]
    se = model_type.endswith("SE")
    num_classes = 4 if model_type == "MiniFASNetV2SE" else 3
    return MiniFASNet(keep, 128, conv6_kernel, drop_p=0.0, num_classes=num_classes, se=se)
