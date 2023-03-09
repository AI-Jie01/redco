import numpy as np
import jax
import jax.numpy as jnp
import flax.linen as nn
from flax.core.frozen_dict import unfreeze


class Actor(nn.Module):
    hidden_dim: int = 64
    n_layers: int = 2
    action_dim: int = None
    action_bound: float = None

    @nn.compact
    def __call__(self, states):
        x = states
        for _ in range(self.n_layers - 1):
            x = nn.Dense(features=self.hidden_dim)(x)
            x = nn.relu(x)

        x = nn.Dense(features=self.action_dim)(x)
        return nn.tanh(x) * self.action_bound


class Critic(nn.Module):
    hidden_dim: int = 64
    n_layers: int = 3

    @nn.compact
    def __call__(self, states, actions):
        x = jnp.concatenate([states, actions], axis=-1)

        for _ in range(self.n_layers - 1):
            x = nn.Dense(features=self.hidden_dim)(x)
            x = nn.relu(x)

        return nn.Dense(features=1)(x)


def collate_fn(examples):
    batch = {}
    for key in ['states', 'actions', 'td_targets']:
        if key in examples[0]:
            batch[key] = np.stack([example[key] for example in examples])

    return batch


def loss_fn(train_rng,
            state,
            params,
            batch,
            is_training,
            actor,
            critic,
            critic_loss_weight):
    critic_loss = jnp.mean(jnp.square(critic.apply(
        {'params': params['critic']},
        states=batch['states'],
        actions=batch['actions']
    )[:, 0] - batch['td_targets']))

    actions = actor.apply({'params': params['actor']}, batch['states'])
    q_values = critic.apply(
        {'params': jax.lax.stop_gradient(params['critic'])},
        states=batch['states'],
        actions=actions)

    actor_loss = -jnp.mean(q_values)

    return critic_loss * critic_loss_weight + actor_loss


def actor_pred_fn(pred_rng, batch, params, actor):
    return actor.apply({'params': params}, batch['states'])


def critic_pred_fn(pred_rng, batch, params, critic):
    return critic.apply(
        {'params': params}, states=batch['states'], actions=batch['actions']
    )[:, 0]
