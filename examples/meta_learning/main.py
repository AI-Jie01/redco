from functools import partial
import fire
import jax.numpy as jnp
import optax
import numpy as np
import flax.linen as nn

from redco import Deployer, Trainer

from data_utils import get_torchmeta_dataset, sample_tasks
from maml_pipeline import maml_collate_fn, maml_loss_fn, maml_pred_fn


class CNN(nn.Module):
    """A simple CNN model."""
    n_classes: int = 1

    @nn.compact
    def __call__(self, x):
        x = nn.Conv(features=32, kernel_size=(3, 3))(x)
        x = nn.relu(x)
        x = nn.avg_pool(x, window_shape=(2, 2), strides=(2, 2))
        x = nn.Conv(features=64, kernel_size=(3, 3))(x)
        x = nn.relu(x)
        x = nn.avg_pool(x, window_shape=(2, 2), strides=(2, 2))
        x = x.reshape((x.shape[0], -1))  # flatten
        x = nn.Dense(features=256)(x)
        x = nn.relu(x)
        x = nn.Dense(features=self.n_classes)(x)
        return x


def inner_loss_fn(params, batch, model):
    logits = model.apply({'params': params}, batch['inputs'])
    return jnp.mean(optax.softmax_cross_entropy_with_integer_labels(
        logits=logits, labels=batch['labels']))


def inner_pred_fn(batch, params, model):
    return model.apply({'params': params}, batch['inputs']).argmax(axis=-1)


def eval_metric_fn(preds, examples):
    preds = np.array(preds)
    labels = np.array([example['test']['labels'] for example in examples])
    return {'acc': np.mean(preds == labels).item()}


def main(dataset_name='omniglot',
         n_ways=5,
         n_shots=5,
         n_test_shots=15,
         n_tasks_per_epoch=10000,
         n_epochs=1000,
         learning_rate=1e-3,
         per_device_batch_size=16,
         inner_learning_rate=0.1,
         inner_n_steps=1,
         train_key='train',
         val_key='test',
         jax_seed=42):
    tm_dataset = get_torchmeta_dataset(
        dataset_name=dataset_name,
        n_ways=n_ways,
        n_shots=n_shots,
        n_test_shots=n_test_shots)

    deployer = Deployer(jax_seed=jax_seed)

    model = CNN(n_classes=n_ways)
    dummy_example = sample_tasks(tm_dataset=tm_dataset['train'], n_tasks=1)[0]
    params = model.init(deployer.gen_rng(), np.array(
        dummy_example['train']['inputs']))['params']
    optimizer = optax.adam(learning_rate=learning_rate)

    collate_fn = partial(maml_collate_fn, train_key=train_key, val_key=val_key)

    loss_fn = partial(
        maml_loss_fn,
        inner_loss_fn=partial(inner_loss_fn, model=model),
        inner_learning_rate=inner_learning_rate,
        inner_n_steps=inner_n_steps)

    pred_fn = partial(
        maml_pred_fn,
        inner_loss_fn=partial(inner_loss_fn, model=model),
        inner_learning_rate=inner_learning_rate,
        inner_n_steps=inner_n_steps,
        inner_pred_fn=partial(inner_pred_fn, model=model))

    trainer = Trainer(
        deployer=deployer,
        collate_fn=collate_fn,
        apply_fn=model.apply,
        loss_fn=loss_fn,
        params=params,
        optimizer=optimizer)

    predictor = trainer.get_default_predictor(pred_fn=pred_fn)

    eval_examples = sample_tasks(
        tm_dataset=tm_dataset['val'], n_tasks=n_tasks_per_epoch)
    train_examples_fn = partial(
        sample_tasks, tm_dataset=tm_dataset['train'], n_tasks=n_tasks_per_epoch)
    trainer.fit(
        train_examples=train_examples_fn,
        per_device_batch_size=per_device_batch_size,
        n_epochs=n_epochs,
        eval_examples=eval_examples,
        eval_loss=True,
        eval_predictor=predictor,
        eval_metric_fn=eval_metric_fn)


if __name__ == '__main__':
    fire.Fire(main)