import networkx as nx
import matplotlib.pyplot as plt
import numpy as np
import math

G = nx.read_gpickle("ogbn-mag.gpickle")
node_mapping = dict(zip(sorted(G.nodes(), key=lambda k: -G.degree[k]), range(len(G.nodes()))))
G_new = nx.relabel_nodes(G, node_mapping)

CORRELATION_HEIGHT_OR_WIDTH = 1000
correlation_matrix = np.zeros([CORRELATION_HEIGHT_OR_WIDTH, CORRELATION_HEIGHT_OR_WIDTH])
for edge in G_new.edges():
    idx_i = int(math.floor(edge[0] / len(G.nodes()) * CORRELATION_HEIGHT_OR_WIDTH))
    idx_j = int(math.floor(edge[1] / len(G.nodes()) * CORRELATION_HEIGHT_OR_WIDTH))
    correlation_matrix[idx_i, idx_j] += 1
print(len(G_new.edges()))

with open("ogbn-mag-correlation-matrix.npy", 'wb') as fd:
    np.save(fd,correlation_matrix)
plt.imsave('correlation.png', correlation_matrix, cmap='hot')
