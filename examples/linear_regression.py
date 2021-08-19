import jax
import jax.numpy as jnp
import matplotlib.pyplot as plt
import numpy as np
import optax
import treex as tx

x = np.random.uniform(size=(500, 1))
y = 1.4 * x - 0.3 + np.random.normal(scale=0.1, size=(500, 1))


class Linear(tx.Module):
    w: tx.Parameter
    b: tx.Parameter

    def __init__(self, din, dout):
        self.w = tx.Initializer(lambda key: jax.random.uniform(key, shape=(din, dout)))
        self.b = jnp.zeros(shape=(dout,))

    def __call__(self, x):
        return jnp.dot(x, self.w) + self.b


model = Linear(1, 1).init(42)
optimizer = optax.adam(0.001)

opt_state = optimizer.init(model)


@jax.value_and_grad
def loss_fn(model, x, y):
    pred = model(x)
    return jnp.mean((pred - y) ** 2)


@jax.jit
def train_step(model, x, y, opt_state):
    loss, grads = loss_fn(model, x, y)
    updates, opt_state = optimizer.update(grads, opt_state, model)
    model = optax.apply_updates(model, updates)

    return loss, model, opt_state


for step in range(1000):
    loss, model, opt_state = train_step(model, x, y, opt_state)
    if step % 100 == 0:
        print(f"loss: {loss:.4f}")


X_test = np.linspace(x.min(), x.max(), 100)[:, None]
y_pred = model(X_test)

plt.scatter(x, y, c="k", label="data")
plt.plot(X_test, y_pred, c="b", linewidth=2, label="prediction")
plt.legend()
plt.show()