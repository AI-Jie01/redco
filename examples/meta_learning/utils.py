import os

import tqdm

from torchmeta.datasets import helpers
from torchmeta.utils.data import BatchMetaDataLoader

import numpy as np
import jax
import jax.numpy as jnp
import flax.linen as nn


class CNN(nn.Module):
    @nn.compact
    def __call__(self, x):
        x = jnp.transpose(x, (0, 2, 3, 1))

        x = nn.Conv(features=32, kernel_size=(3, 3))(x)
        x = nn.relu(x)
        x = nn.avg_pool(x, window_shape=(2, 2), strides=(2, 2))
        x = nn.Conv(features=64, kernel_size=(3, 3))(x)
        x = nn.relu(x)
        x = nn.avg_pool(x, window_shape=(2, 2), strides=(2, 2))
        x = x.reshape((x.shape[0], -1))  # flatten
        x = nn.Dense(features=256)(x)
        x = nn.relu(x)
        x = nn.Dense(features=5)(x)
        return x


def get_torchmeta_dataset(dataset_name, n_ways, n_shots, n_test_shots):
    dataset = {}
    for meta_split in ['train', 'val', 'test']:
        dataset[meta_split] = getattr(helpers, dataset_name)(
            "./data",
            ways=n_ways,
            shots=n_shots,
            test_shots=n_test_shots,
            meta_split=meta_split,
            download=True)

    return dataset


def sample_tasks(tm_dataset, n_tasks, epoch_idx=None, sample_batch_size=1000):
    task_loader = BatchMetaDataLoader(tm_dataset, batch_size=sample_batch_size)

    tasks = []
    for task_batch in tqdm.tqdm(
            task_loader, total=n_tasks, desc=f'Sampling {n_tasks} tasks'):
        for i in range(sample_batch_size):
            task = jax.tree_util.tree_map(
                lambda x: np.asarray(x)[i], task_batch)
            tasks.append({
                split: {'inputs': task[split][0], 'labels': task[split][1]}
                for split in task.keys()
            })

        if len(tasks) >= n_tasks:
            tasks = tasks[:n_tasks]
            break

    return tasks
