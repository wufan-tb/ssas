import torch
from . cbam import CBAM
from torchvision.models.detection.backbone_utils import resnet_fpn_backbone

class Merge(torch.nn.Module):
    """upsample the features and concant them
    
    Args:
        torch (int): feaure channel number
    """
    def __init__(self, dim):
        super().__init__()
        self.upsample_2=torch.nn.Sequential(torch.nn.ConvTranspose2d(dim, dim, 4, 2, 1),torch.nn.LeakyReLU(0.2))
        self.upsample_4=torch.nn.Sequential(torch.nn.ConvTranspose2d(dim, dim, 4, 4, 0),torch.nn.LeakyReLU(0.2))
        self.upsample_8=torch.nn.Sequential(torch.nn.ConvTranspose2d(dim, dim, 4, 2, 1),
                                            torch.nn.ConvTranspose2d(dim, dim, 4, 4, 0),
                                            torch.nn.LeakyReLU(0.2))
        self.attn=CBAM(dim*4)
        
        for mm in self.children():
            for m in mm.children():
                if isinstance(m, torch.nn.Conv2d) or isinstance(m, torch.nn.ConvTranspose2d):
                    torch.nn.init.kaiming_uniform_(m.weight, a=1)
                    torch.nn.init.constant_(m.bias, 0)
                elif isinstance(m,torch.nn.LeakyReLU) or isinstance(m,torch.nn.Sigmoid):
                    m.inplace=True

    def forward(self, features):
        fea0=features['0']
        fea1=self.upsample_2(features['1'])
        fea2=self.upsample_4(features['2'])
        fea3=self.upsample_8(features['3'])
        feature=torch.cat([fea0,fea1,fea2,fea3],dim=1)
        feature=self.attn(feature)
        return feature

class Predictor(torch.nn.Module):
    """predict img label and anomaly mask

    Args:
        torch (int): feature channel number
    """
    def __init__(self, dim):
        super().__init__()
        self.upsample_4=torch.nn.Sequential(torch.nn.ConvTranspose2d(dim, dim//4, 4, 4, 0),torch.nn.LeakyReLU(0.2))
        self.mask_predict=torch.nn.Sequential(torch.nn.Conv2d(dim//4, 1, 1, 1, 0),torch.nn.Sigmoid())
        self.label_predict=torch.nn.Sequential(torch.nn.Flatten(1,-1),torch.nn.Linear(dim,dim//4),torch.nn.Linear(dim//4,1),torch.nn.Sigmoid())
        
        for mm in self.children():
            for m in mm.children():
                if isinstance(m, torch.nn.Conv2d) or isinstance(m, torch.nn.ConvTranspose2d):
                    torch.nn.init.kaiming_uniform_(m.weight, a=1)
                    torch.nn.init.constant_(m.bias, 0)
                elif isinstance(m,torch.nn.LeakyReLU) or isinstance(m,torch.nn.Sigmoid):
                    m.inplace=True
                
    def forward(self,x):
        *_,W=x.size()
        label=self.label_predict(torch.nn.AvgPool2d(W,1)(x))
        x=self.upsample_4(x)
        mask=self.mask_predict(x)
        return label,mask

class PAS(torch.nn.Module):
    """presude anomaly segementation

    Args:
        torch (None Args): None
    """
    def __init__(self):
        super(PAS, self).__init__()
        self.backbone=resnet_fpn_backbone('resnet50', True, trainable_layers=0)
        self.merge=Merge(dim=256)
        self.predictor=Predictor(dim=1024)
        
    def forward(self,x):
        multiscal_features=self.backbone(x)
        feature=self.merge(multiscal_features)
        pred_mask=self.predictor(feature)
        return pred_mask
        
if __name__=="__main__":
    net=PAS().to('cuda')
    x=torch.randn((10,3,256,256)).to('cuda')
    label,mask=net(x)
    print(label.shape,mask.shape)
    
    label_loss=torch.nn.BCELoss()
    mask_loss=torch.nn.L1Loss()
    
    label_target=torch.empty(10, 1).random_(2).to('cuda')
    mask_target=torch.empty(10,1,256,256).random_(2).to('cuda')
    
    print(label_loss(label,label_target),mask_loss(mask,mask_target))
    
    
    