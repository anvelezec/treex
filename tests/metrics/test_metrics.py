import jax
import jax.numpy as jnp
import pytest

import treex as tx
from treex import metrics


class TestAccuracy:
    def test_list(self):

        N = 0

        @jax.jit
        def f(m, target, preds):
            nonlocal N
            N += 1
            m(target=target, preds=preds)
            return m

        metrics = tx.metrics.Metrics(
            [
                tx.metrics.Accuracy(num_classes=10),
                tx.metrics.Accuracy(num_classes=10),
            ]
        )
        target = jnp.array([0, 1, 2, 3, 4, 5, 6, 7, 8, 9])[None, None, None, :]
        preds = jnp.array([0, 1, 2, 3, 0, 5, 6, 7, 0, 9])[None, None, None, :]

        metrics = f(metrics, target, preds)
        assert N == 1
        assert metrics.compute() == {"accuracy": 0.8, "accuracy2": 0.8}

        metrics = f(metrics, target, preds)
        assert N == 1
        assert metrics.compute() == {"accuracy": 0.8, "accuracy2": 0.8}

    def test_dict(self):

        N = 0

        @jax.jit
        def f(m, target, preds):
            nonlocal N
            N += 1
            m(target=target, preds=preds)
            return m

        metrics = tx.metrics.Metrics(
            dict(
                a=tx.metrics.Accuracy(num_classes=10),
                b=tx.metrics.Accuracy(num_classes=10),
            )
        )
        target = jnp.array([0, 1, 2, 3, 4, 5, 6, 7, 8, 9])[None, None, None, :]
        preds = jnp.array([0, 1, 2, 3, 0, 5, 6, 7, 0, 9])[None, None, None, :]

        metrics = f(metrics, target, preds)
        assert N == 1
        assert metrics.compute() == {"a/accuracy": 0.8, "b/accuracy": 0.8}

        metrics = f(metrics, target, preds)
        assert N == 1
        assert metrics.compute() == {"a/accuracy": 0.8, "b/accuracy": 0.8}


class TestAuxMetrics:
    def test_basic(self):
        class MyModule(tx.Module):
            aux: jnp.ndarray = tx.MetricLog.node()
            some_value: jnp.ndarray = tx.node()

            def __init__(self) -> None:
                self.aux = jnp.array(1.0, jnp.float32)
                self.some_value = jnp.array(10.0, jnp.float32)

        N = 0

        @jax.jit
        def f(module: MyModule, aux_metrics: tx.metrics.AuxMetrics):
            nonlocal N
            N += 1
            metric_logs = module.filter(tx.MetricLog)
            aux_metrics(aux_metrics=metric_logs)
            return aux_metrics

        module = MyModule()

        metric_logs = module.filter(tx.MetricLog)
        metrics = tx.metrics.AuxMetrics(metric_logs)

        metrics = f(module, metrics)
        assert N == 1
        assert metrics.compute() == {"aux": 1.0}

        module.aux = jnp.array(0.0, jnp.float32)
        metrics = f(module, metrics)

        assert N == 1
        assert metrics.compute() == {"aux": 0.5}

    def test_named(self):
        class MyModule(tx.Module):
            aux: tx.Named[jnp.ndarray] = tx.MetricLog.node()
            some_value: jnp.ndarray = tx.node()

            def __init__(self) -> None:
                self.aux = tx.Named("my_metric", jnp.array(1.0, jnp.float32))
                self.some_value = jnp.array(10.0, jnp.float32)

        N = 0

        @jax.jit
        def f(module: MyModule, aux_metrics: tx.metrics.AuxMetrics):
            nonlocal N
            N += 1
            metric_logs = module.filter(tx.MetricLog)
            aux_metrics(aux_metrics=metric_logs)
            return aux_metrics

        module = MyModule()

        metric_logs = module.filter(tx.MetricLog)
        metrics = tx.metrics.AuxMetrics(metric_logs)

        metrics = f(module, metrics)
        assert N == 1
        assert metrics.compute() == {"my_metric": 1.0}

        module.aux.value = jnp.array(0.0, jnp.float32)
        metrics = f(module, metrics)

        assert N == 1
        assert metrics.compute() == {"my_metric": 0.5}
