import torch
import torch.nn as nn
import torch.nn.functional as func


class Total_loss(nn.Module):
    def __init__(self, lamb=0.7):
        super(Total_loss, self).__init__()
        self.lamb = lamb
        self.criterion_cel = nn.CrossEntropyLoss()
        self.criterion_cmfl = CMFLoss()
    
    def forward(self, p, q, r, targets):
        """
        Args:
            p: probability of real in rgb branch
            q: probability of real in depth branch
            r: probability of real in joint branch
            targets: {0:fake, 1:real}
        """
        loss_r = self.criterion_cel(r, targets)
        loss_pq = self.criterion_cmfl(p,q,targets)+self.criterion_cmfl(q,p,targets)
        loss = (1-self.lamb)*loss_r + self.lamb*loss_pq
        return loss

class CMFLoss(nn.Module):
	"""
	Cross Modal Focal Loss
	Args:
		alpha
		gamma
		binary
		multiplier
		sg
	"""
	def __init__(self, alpha=1, gamma=2, binary=False, multiplier=2, sg=False):
		super(CMFLoss, self).__init__()
		self.alpha = alpha
		self.gamma = gamma
		self.binary = binary
		self.multiplier =multiplier
		self.sg=sg

	def forward(self, inputs_a,inputs_b, targets):

		bce_loss_a = func.binary_cross_entropy(inputs_a, targets, reduce=False)
		bce_loss_b = func.binary_cross_entropy(inputs_b, targets, reduce=False)

		pt_a = torch.exp(-bce_loss_a)
		pt_b = torch.exp(-bce_loss_b)

		eps = 0.000000001

		if self.sg:
			d_pt_a=pt_a.detach()
			d_pt_b=pt_b.detach()
			wt_a=((d_pt_b + eps)*(self.multiplier*pt_a*d_pt_b))/(pt_a + d_pt_b + eps)
			wt_b=((d_pt_a + eps)*(self.multiplier*d_pt_a*pt_b))/(d_pt_a + pt_b + eps)
		else:
			wt_a=((pt_b + eps)*(self.multiplier*pt_a*pt_b))/(pt_a + pt_b + eps)
			wt_b=((pt_a + eps)*(self.multiplier*pt_a*pt_b))/(pt_a + pt_b + eps)

		if self.binary:
			wt_a=wt_a * (1-targets)
			wt_b=wt_b * (1-targets)

		f_loss_a = self.alpha * (1-wt_a)**self.gamma * bce_loss_a
		f_loss_b = self.alpha * (1-wt_b)**self.gamma * bce_loss_b

		loss= 0.5*torch.mean(f_loss_a) + 0.5*torch.mean(f_loss_b) 
		
		return loss