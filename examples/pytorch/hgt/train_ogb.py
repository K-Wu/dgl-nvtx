#!/usr/bin/env python
# coding: utf-8

# In[1]:


import scipy.io
import urllib.request
import dgl
import math
import numpy as np
from model import *
import argparse
import nvtx

from ogb.nodeproppred import NodePropPredDataset
import numpy as np

dataset = NodePropPredDataset(name='ogbn-mag')

torch.manual_seed(0)
# data_url = 'https://data.dgl.ai/dataset/ACM.mat'
# data_file_path = r'D:\external-repos\dgl\examples\pytorch\hgt\ACM.mat'

# urllib.request.urlretrieve(data_url, data_file_path)
# data = scipy.io.loadmat(data_file_path)


parser = argparse.ArgumentParser(description='Training GNN on ogbn-products benchmark')

parser.add_argument('--n_epoch', type=int, default=200)
parser.add_argument('--n_hid', type=int, default=256)
parser.add_argument('--n_inp', type=int, default=256)
parser.add_argument('--clip', type=int, default=1.0)
parser.add_argument('--max_lr', type=float, default=1e-3)
parser.add_argument('--multi_stream', type=bool, default=False)

args = parser.parse_args()


def get_n_params(model):
    pp = 0
    for p in list(model.parameters()):
        nn = 1
        for s in list(p.size()):
            nn = nn * s
        pp += nn
    return pp


def train(model, G):
    best_val_acc = torch.tensor(0)
    best_test_acc = torch.tensor(0)
    train_step = torch.tensor(0)
    for epoch in np.arange(args.n_epoch) + 1:
        model.train()
        logits = model(G, 'paper')
        # The loss is computed only for labeled nodes.
        loss = F.cross_entropy(logits[train_idx], labels[train_idx].to(device))
        optimizer.zero_grad()
        with nvtx.annotate("backward", color="purple"):
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), args.clip)
        with nvtx.annotate("optimizer.step", color="purple"):
            optimizer.step()
        train_step += 1
        scheduler.step(train_step)
        if epoch % 5 == 0:
            model.eval()
            logits = model(G, 'paper')
            pred = logits.argmax(1).cpu()
            train_acc = (pred[train_idx] == labels[train_idx]).float().mean()
            val_acc = (pred[val_idx] == labels[val_idx]).float().mean()
            test_acc = (pred[test_idx] == labels[test_idx]).float().mean()
            if best_val_acc < val_acc:
                best_val_acc = val_acc
                best_test_acc = test_acc
            print(
                'Epoch: %d LR: %.5f Loss %.4f, Train Acc %.4f, Val Acc %.4f (Best %.4f), Test Acc %.4f (Best %.4f)' % (
                    epoch,
                    optimizer.param_groups[0]['lr'],
                    loss.item(),
                    train_acc.item(),
                    val_acc.item(),
                    best_val_acc.item(),
                    test_acc.item(),
                    best_test_acc.item(),
                ))


device = torch.device("cuda:0")

G = dgl.heterograph({
    ('paper', 'written-by', 'author'): tuple(map(lambda x: x.flatten(), list(
        map(np.array, zip(dataset.graph['edge_index_dict'][('author', 'writes', 'paper')][[1, 0]]))))),
    ('author', 'writing', 'paper'): tuple(map(lambda x: x.flatten(), list(
        map(np.array, zip(dataset.graph['edge_index_dict'][('author', 'writes', 'paper')]))))),
    ('paper', 'citing', 'paper'): tuple(map(lambda x: x.flatten(), list(
        map(np.array, zip(dataset.graph['edge_index_dict'][('paper', 'cites', 'paper')]))))),
    ('paper', 'cited', 'paper'): tuple(map(lambda x: x.flatten(), list(
        map(np.array, zip(dataset.graph['edge_index_dict'][('paper', 'cites', 'paper')][[1, 0]]))))),
    ('paper', 'is-about', 'subject'): tuple(map(lambda x: x.flatten(), list(
        map(np.array, zip(dataset.graph['edge_index_dict'][('paper', 'has_topic', 'field_of_study')]))))),
    ('subject', 'has', 'paper'): tuple(map(lambda x: x.flatten(), list(
        map(np.array, zip(dataset.graph['edge_index_dict'][('paper', 'has_topic', 'field_of_study')][[1, 0]]))))),
})
print(G)

# pvc = data['PvsC'].tocsr()
# p_selected = pvc.tocoo()
# generate labels
# labels = pvc.indices
# labels = torch.tensor(labels).long()

# generate train/val/test split
# pid = p_selected.row

labels = dataset.labels['paper'].flatten()
pid = np.arange(len(labels))
labels = torch.tensor(labels).long()

shuffle = np.random.permutation(pid)
train_idx = torch.tensor(shuffle[0:800 * 60]).long()
val_idx = torch.tensor(shuffle[800 * 60:900 * 60]).long()
test_idx = torch.tensor(shuffle[900 * 60:]).long()

node_dict = {}
edge_dict = {}
for ntype in G.ntypes:
    node_dict[ntype] = len(node_dict)
for etype in G.etypes:
    edge_dict[etype] = len(edge_dict)
    G.edges[etype].data['id'] = torch.ones(G.number_of_edges(etype), dtype=torch.long) * edge_dict[etype]

#     Random initialize input feature
for ntype in G.ntypes:
    emb = nn.Parameter(torch.Tensor(G.number_of_nodes(ntype), 256), requires_grad=False)
    nn.init.xavier_uniform_(emb)
    G.nodes[ntype].data['inp'] = emb

G = G.to(device)
# TODO: faulty. This does not involve author affliated with institution, and involve artificial reverse edges,
# import numpy
# #with open("writing_coo_1.npy",'wb') as fd:
# numpy.save("writing_coo_1.npy",numpy.array([srcs_or_dsts.tolist() for srcs_or_dsts in G.edges(etype='writing')],dtype=numpy.int32))
# #with open("cited_coo_1.npy",'wb') as fd:
# numpy.save("cited_coo_1.npy",numpy.array([srcs_or_dsts.tolist() for srcs_or_dsts in G.edges(etype='cited')],dtype=numpy.int32))
# #with open("citing_coo_1.npy",'wb') as fd:
# numpy.save("citing_coo_1.npy",numpy.array([srcs_or_dsts.tolist() for srcs_or_dsts in G.edges(etype='citing')],dtype=numpy.int32))
# #with open("is-about_coo_1.npy",'wb') as fd:
# numpy.save("is-about_coo_1.npy",numpy.array([srcs_or_dsts.tolist() for srcs_or_dsts in G.edges(etype='is-about')],dtype=numpy.int32))
# #with open("written-by_coo_1.npy",'wb') as fd:
# numpy.save("written-by_coo_1.npy",numpy.array([srcs_or_dsts.tolist() for srcs_or_dsts in G.edges(etype='written-by')],dtype=numpy.int32))
# #with open("has_coo_1.npy",'wb') as fd:
# numpy.save("has_coo_1.npy",numpy.array([srcs_or_dsts.tolist() for srcs_or_dsts in G.edges(etype='has')],dtype=numpy.int32))
#
# exit()

if args.multi_stream:
    print("multi-stream enabled!")
    model = HGTMultiStream(G,
                           node_dict, edge_dict,
                           n_inp=args.n_inp,
                           n_hid=args.n_hid,
                           n_out=labels.max().item() + 1,
                           n_layers=2,
                           n_heads=4,
                           use_norm=True).to(device)
else:
    print("multi-stream disabled!")
    model = HGT(G,
                node_dict, edge_dict,
                n_inp=args.n_inp,
                n_hid=args.n_hid,
                n_out=labels.max().item() + 1,
                n_layers=2,
                n_heads=4,
                use_norm=True).to(device)
optimizer = torch.optim.AdamW(model.parameters())
scheduler = torch.optim.lr_scheduler.OneCycleLR(optimizer, total_steps=args.n_epoch, max_lr=args.max_lr)
print('Training HGT with #param: %d' % (get_n_params(model)))
train(model, G)

model = HeteroRGCN(G,
                   in_size=args.n_inp,
                   hidden_size=args.n_hid,
                   out_size=labels.max().item() + 1).to(device)
optimizer = torch.optim.AdamW(model.parameters())
scheduler = torch.optim.lr_scheduler.OneCycleLR(optimizer, total_steps=args.n_epoch, max_lr=args.max_lr)
print('Training RGCN with #param: %d' % (get_n_params(model)))
train(model, G)

if args.multi_stream:
    print("multi-stream enabled!")
    model = HGTMultiStream(G,
                           node_dict, edge_dict,
                           n_inp=args.n_inp,
                           n_hid=args.n_hid,
                           n_out=labels.max().item() + 1,
                           n_layers=0,
                           n_heads=4).to(device)
else:
    print("multi-stream disabled!")
    model = HGT(G,
                node_dict, edge_dict,
                n_inp=args.n_inp,
                n_hid=args.n_hid,
                n_out=labels.max().item() + 1,
                n_layers=0,
                n_heads=4).to(device)
optimizer = torch.optim.AdamW(model.parameters())
scheduler = torch.optim.lr_scheduler.OneCycleLR(optimizer, total_steps=args.n_epoch, max_lr=args.max_lr)
print('Training MLP with #param: %d' % (get_n_params(model)))
train(model, G)
