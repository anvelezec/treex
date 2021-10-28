from functools import partial
from typing import Union

import jax
import jax.numpy as jnp
import matplotlib.pyplot as plt
import numpy as np
import optax

import treex as tx

x = jnp.array([[0, 0], [0, 1], [1, 0], [1, 1]], dtype=jnp.float32)
y = jnp.array([0, 1, 1, 0], dtype=jnp.float32)[:, None]

# treex already defines tx.Linear but we can define our own
class Linear(tx.Module):
    w: Union[tx.Initializer, jnp.ndarray] = tx.Parameter.node()
    b: jnp.ndarray = tx.Parameter.node()

    def __init__(self, din, dout):
        self.w = tx.Initializer(lambda key: jax.random.uniform(key, shape=(din, dout)))
        self.b = jnp.zeros(shape=(dout,))

    def __call__(self, x):
        return jnp.dot(x, self.w) + self.b


class CustomMLP(tx.Module):
    def __init__(self, din, dhid, dout):

        self.l1 = Linear(din, dhid)
        self.l2 = Linear(dhid, dout)

    def __call__(self, x):
        x = self.l1(x)
        x = jax.nn.relu(x)
        x = self.l2(x)
        return x


model = CustomMLP(2, 16, 1).init(42)
optimizer = tx.Optimizer(optax.adam(0.01))
optimizer = optimizer.init(model.filter(tx.Parameter))


@jax.value_and_grad
def loss_fn(model, x, y):
    preds = model(x)
    loss = optax.sigmoid_binary_cross_entropy(preds, y).mean()
    return loss


@jax.jit
def train_step(model, x, y, optimizer: tx.Optimizer):
    loss, grads = loss_fn(model, x, y)

    # here model == params
    model = optimizer.update(grads, model)

    return loss, model, optimizer


for step in range(1000):
    loss, model, optimizer = train_step(model, x, y, optimizer)
    if step % 100 == 0:
        print(f"loss: {loss:.4f}")

model = model.eval()

preds = model(x)
preds = (preds > 0).astype(np.int32)

print(preds)

plt.scatter(x[:, 0], x[:, 1], c=preds.reshape(-1), label="data")
plt.show()
