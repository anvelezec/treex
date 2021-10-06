import typing as tp
from dataclasses import dataclass
from inspect import istraceback, signature

import jax
import jax.numpy as jnp
import jax.tree_util
import numpy as np
import optax
import pytest

import treex as tx


class Linear(tx.Module):
    w: np.ndarray = tx.Parameter.node()
    b: np.ndarray = tx.Parameter.node()
    n: int = tx.State.node()

    def __init__(self, din, dout, name="linear"):

        self.din = din
        self.dout = dout
        self.w = np.random.uniform(size=(din, dout))
        self.b = np.random.uniform(size=(dout,))
        self.n = 1
        self.name = name


class MLP(tx.Module):
    linear1: Linear
    linear2: Linear

    def __init__(self, din, dmid, dout, name="mlp"):

        self.din = din
        self.dmid = dmid
        self.dout = dout
        self.name = name

        self.linear1 = Linear(din, dmid, name="linear1")
        self.linear2 = Linear(dmid, dout, name="linear2")


def _get_all_vars(cls):
    d = {}
    for c in reversed(cls.mro()):
        if hasattr(c, "__dict__"):
            d.update(vars(c))
    return d


class TestTreex:
    def test_vars_inheritance(self):
        class A:
            a = 1

        class B(A):
            b = 2

        v = _get_all_vars(B)

        v

    def test_flatten_nothing(self):
        x = [(1, 2), (3, tx.Nothing())]
        assert jax.tree_leaves(x) == [1, 2, 3]

        flat_with_nothing = jax.tree_flatten(x, lambda x: isinstance(x, tx.Nothing))[0]

        assert flat_with_nothing == [1, 2, 3, tx.Nothing()]

    def test_flatten(self):

        mlp = MLP(2, 3, 5)

        flat = jax.tree_leaves(mlp)

        assert len(flat) == 6

    def test_flatten_slice(self):

        mlp = MLP(2, 3, 5).filter(tx.State)

        flat = jax.tree_leaves(mlp)

        assert len(flat) == 2

    def test_flatten_slice_merging(self):

        mlp = MLP(2, 3, 5).filter(tx.State)

        flat = jax.tree_flatten(mlp, lambda x: isinstance(x, tx.Nothing))[0]

        assert len(flat) == 6

    def test_is_tree(self):

        mlp = MLP(2, 3, 5)

        @jax.jit
        def idfn(x):
            return x

        assert not isinstance(mlp.linear1.w, jnp.DeviceArray)
        assert not isinstance(mlp.linear1.b, jnp.DeviceArray)
        assert not isinstance(mlp.linear1.n, jnp.DeviceArray)

        assert not isinstance(mlp.linear2.w, jnp.DeviceArray)
        assert not isinstance(mlp.linear2.b, jnp.DeviceArray)
        assert not isinstance(mlp.linear1.n, jnp.DeviceArray)

        mlp = idfn(mlp)

        assert isinstance(mlp.linear1.w, jnp.DeviceArray)
        assert isinstance(mlp.linear1.b, jnp.DeviceArray)
        assert isinstance(mlp.linear1.n, jnp.DeviceArray)

        assert isinstance(mlp.linear2.w, jnp.DeviceArray)
        assert isinstance(mlp.linear2.b, jnp.DeviceArray)
        assert isinstance(mlp.linear2.n, jnp.DeviceArray)

    def test_filter(self):

        mlp = MLP(2, 3, 5)

        # params
        mlp_params = mlp.filter(tx.Parameter)

        assert not isinstance(mlp_params.linear1.w, tx.Nothing)
        assert not isinstance(mlp_params.linear1.b, tx.Nothing)
        assert isinstance(mlp_params.linear1.n, tx.Nothing)

        assert not isinstance(mlp_params.linear2.w, tx.Nothing)
        assert not isinstance(mlp_params.linear2.b, tx.Nothing)
        assert isinstance(mlp_params.linear2.n, tx.Nothing)

        # states
        mlp_states = mlp.filter(tx.State)

        assert isinstance(mlp_states.linear1.w, tx.Nothing)
        assert isinstance(mlp_states.linear1.b, tx.Nothing)
        assert not isinstance(mlp_states.linear1.n, tx.Nothing)

        assert isinstance(mlp_states.linear2.w, tx.Nothing)
        assert isinstance(mlp_states.linear2.b, tx.Nothing)
        assert not isinstance(mlp_states.linear2.n, tx.Nothing)

    def test_update(self):

        mlp = MLP(2, 3, 5)

        mlp_params = mlp.filter(tx.Parameter)
        mlp_states = mlp.filter(tx.State)

        mlp_next = mlp_params.merge(mlp_states)

        assert not isinstance(mlp_next.linear1.w, tx.Nothing)
        assert not isinstance(mlp_next.linear1.b, tx.Nothing)
        assert not isinstance(mlp_next.linear1.n, tx.Nothing)

        assert not isinstance(mlp_next.linear2.w, tx.Nothing)
        assert not isinstance(mlp_next.linear2.b, tx.Nothing)
        assert not isinstance(mlp_next.linear2.n, tx.Nothing)

    def test_update_initializers(self):
        x = np.random.uniform(size=(10, 2))

        m = tx.Linear(3)
        m2 = m.init(42, x)
        m = m.merge(m2)

        assert isinstance(m.kernel, jnp.ndarray)

    def test_update_inplace(self):

        mlp = MLP(2, 3, 5)

        mlp_params = mlp.filter(tx.Parameter)
        mlp_states = mlp.filter(tx.State)

        mlp_params.merge(mlp_states, inplace=True)

        assert not isinstance(mlp_params.linear1.w, tx.Nothing)
        assert not isinstance(mlp_params.linear1.b, tx.Nothing)
        assert not isinstance(mlp_params.linear1.n, tx.Nothing)

        assert not isinstance(mlp_params.linear2.w, tx.Nothing)
        assert not isinstance(mlp_params.linear2.b, tx.Nothing)
        assert not isinstance(mlp_params.linear2.n, tx.Nothing)

    def test_update_not_inplace(self):

        mlp = MLP(2, 3, 5)

        mlp_params = mlp.filter(tx.Parameter)
        mlp_states = mlp.filter(tx.State)

        mlp_params.merge(mlp_states)

        assert not isinstance(mlp_params.linear1.w, tx.Nothing)
        assert not isinstance(mlp_params.linear1.b, tx.Nothing)
        assert isinstance(mlp_params.linear1.n, tx.Nothing)

        assert not isinstance(mlp_params.linear2.w, tx.Nothing)
        assert not isinstance(mlp_params.linear2.b, tx.Nothing)
        assert isinstance(mlp_params.linear2.n, tx.Nothing)

    def test_list(self):
        class LinearList(tx.Module):
            params: tp.List[np.ndarray] = tx.Parameter.node()

            def __init__(self, din, dout, name="linear"):

                self.din = din
                self.dout = dout
                self.params = [
                    np.random.uniform(size=(din, dout)),
                    np.random.uniform(size=(dout,)),
                ]
                self.name = name

        linear = LinearList(2, 3, name="mlp")

        @jax.jit
        def idfn(x):
            return x

        assert not isinstance(linear.params[0], jnp.DeviceArray)
        assert not isinstance(linear.params[1], jnp.DeviceArray)

        linear = idfn(linear)

        assert isinstance(linear.params[0], jnp.DeviceArray)
        assert isinstance(linear.params[1], jnp.DeviceArray)

    def test_treelist(self):
        class MLP(tx.Module):
            linears: tp.List[Linear]

            def __init__(self, din, dmid, dout, name="mlp"):

                self.linears = [
                    Linear(din, dmid, name="linear1"),
                    Linear(dmid, dout, name="linear2"),
                ]

        mlp = MLP(2, 3, 5)

        @jax.jit
        def idfn(x):
            return x

        assert not isinstance(mlp.linears[0].w, jnp.DeviceArray)
        assert not isinstance(mlp.linears[0].b, jnp.DeviceArray)
        assert not isinstance(mlp.linears[0].n, jnp.DeviceArray)

        assert not isinstance(mlp.linears[1].w, jnp.DeviceArray)
        assert not isinstance(mlp.linears[1].b, jnp.DeviceArray)
        assert not isinstance(mlp.linears[1].n, jnp.DeviceArray)

        mlp = idfn(mlp)

        assert isinstance(mlp.linears[0].w, jnp.DeviceArray)
        assert isinstance(mlp.linears[0].b, jnp.DeviceArray)
        assert isinstance(mlp.linears[0].n, jnp.DeviceArray)

        assert isinstance(mlp.linears[1].w, jnp.DeviceArray)
        assert isinstance(mlp.linears[1].b, jnp.DeviceArray)
        assert isinstance(mlp.linears[1].n, jnp.DeviceArray)

    def test_idenpotent_init(self):
        n = 0

        class A(tx.Module):
            def setup(self):
                nonlocal n
                n = n + 1

        module = A()

        module = module.init(42, forward_method=None)
        module = module.init(42, forward_method=None)

        assert n == 1

    def test_initialized(self):
        class A(tx.Module):
            def setup(self):
                self.x = 420

        module = A()
        assert not module.initialized

        module = module.init(42, forward_method=None)

        assert module.x == 420
        assert module.initialized

    def test_initialized_inplace(self):
        class A(tx.Module):
            def setup(self):
                self.x = 420

        module = A()
        assert not module.initialized

        module.init(42, inplace=True, forward_method=None)

        assert module.x == 420
        assert module.initialized

    def test_train(self):

        mlp = MLP(2, 3, 5).init(42, forward_method=None)

        assert mlp.training
        assert mlp.linear1.training
        assert mlp.linear2.training

        mlp = mlp.eval()

        assert not mlp.training
        assert not mlp.linear1.training
        assert not mlp.linear2.training

        mlp = mlp.train()

        assert mlp.training
        assert mlp.linear1.training
        assert mlp.linear2.training

    def test_train_inplace(self):

        mlp = MLP(2, 3, 5).init(42, forward_method=None)

        assert mlp.training
        assert mlp.linear1.training
        assert mlp.linear2.training

        mlp.eval(inplace=True)

        assert not mlp.training
        assert not mlp.linear1.training
        assert not mlp.linear2.training

        mlp.train(inplace=True)

        assert mlp.training
        assert mlp.linear1.training
        assert mlp.linear2.training

    def test_multiple_initializers(self):
        class MLP(tx.Module):
            linear1: tx.Linear
            linear2: tx.Linear

            def __init__(self, din, dmid, dout, name="mlp"):

                self.linear1 = tx.Linear(din, dmid)
                self.linear2 = tx.Linear(dmid, dout)

        mlp = MLP(2, 3, 5).init(42, forward_method=None)

    def test_repr(self):
        class MyModule(tx.Module):
            a: tp.Dict[str, tp.List[MLP]]
            b: tp.List[tp.Union[tx.Initializer, jnp.ndarray]] = tx.Parameter.node()

            def __init__(self):

                self.a = {"mlps": [MLP(2, 3, 5), MLP(2, 3, 5)]}
                self.b = [
                    tx.Initializer(lambda key: jnp.zeros((10, 4))),
                    jnp.zeros((5, 13)),
                ]

        mlp = MyModule()  # .init(42)
        mlp = jax.tree_map(
            lambda x: jnp.asarray(x) if not isinstance(x, tx.Initializer) else x, mlp
        )
        mlp = mlp.filter(tx.Parameter)

        rep = repr(mlp)

        rep

    def test_tabulate(self):
        class MyModule(tx.Module):
            a: tp.Dict[str, tp.List[MLP]]
            b: tp.List[tp.Union[jnp.ndarray, tx.Initializer]] = tx.Parameter.node()

            def __init__(self):

                self.a = {"mlps": [MLP(256, 1024, 512), MLP(256, 1024, 512)]}
                self.b = [
                    tx.Initializer(lambda key: jnp.zeros((512, 256))),
                    jnp.zeros((512, 128)),
                ]

        mlp = MyModule()  # .init(42)
        mlp = jax.tree_map(
            lambda x: jnp.asarray(x) if not isinstance(x, tx.Initializer) else x, mlp
        )
        # mlp = mlp.filter(tx.Parameter)

        rep = mlp.tabulate()

        print(rep)

        assert '.a["mlps"]' in rep
        assert "b:" in rep

        print(mlp.a["mlps"][1].linear2)

    def test_tabulate_inputs(self):
        class MyModule(tx.Module):
            a: tp.Dict[str, tp.List[tx.MLP]]
            b: tp.List[tp.Union[jnp.ndarray]] = tx.Parameter.node()

            def __init__(self):

                self.a = {"mlps": [tx.MLP([256, 1024, 512]), tx.MLP([256, 1024, 512])]}
                self.b = [
                    jnp.zeros((512, 256)),
                    jnp.zeros((512, 128)),
                ]

            def __call__(self, x):

                y1 = self.a["mlps"][0](x)
                y2 = self.a["mlps"][1](x)

                return dict(y1=y1, y2=y2)

        x = np.random.uniform(size=(10, 256))
        mlp = MyModule().init(42, x)
        mlp = jax.tree_map(
            lambda x: jnp.asarray(x) if not isinstance(x, tx.Initializer) else x, mlp
        )
        # mlp = mlp.filter(tx.Parameter)

        rep = mlp.tabulate(inputs=tx.Inputs(x))

        print(rep)

        assert "(\x1b[32m10, 256\x1b[0m)" in rep
        assert "y1:" in rep
        assert "y2:" in rep

    def test_static_annotation(self):
        class Mod(tx.Module):
            a: tx.Linear
            b: tx.Linear = tx.static()

            def __init__(self):

                self.a = tx.Linear(4)
                self.b = tx.Linear(4)

        mod = Mod().init(42)

        assert len(jax.tree_leaves(mod)) == 2

        assert mod.a.initialized
        assert mod.a.kernel is not None
        assert mod.a.bias is not None

        assert not mod.b.initialized
        assert mod.b.kernel is None
        assert mod.b.bias is None

    def test_auto_annotations(self):
        class MLP(tx.Module):
            def __init__(self, din, dmid, dout, name="mlp"):

                self.din = din
                self.dmid = dmid
                self.dout = dout
                self.name = name

                self.linear1 = Linear(din, dmid, name="linear1")
                self.linear2 = Linear(dmid, dout, name="linear2")

        mlp = MLP(2, 3, 5).init(42)

        assert "linear1" in mlp.field_metadata

    def test_auto_annotations_inserted(self):
        class MLP(tx.Module):
            def __init__(self, din, dmid, dout, name="mlp"):

                self.din = din
                self.dmid = dmid
                self.dout = dout
                self.name = name

                self.linear1 = Linear(din, dmid, name="linear1")
                self.linear2 = Linear(dmid, dout, name="linear2")

        mlp = MLP(2, 3, 5).init(42)

        mlp.linear3 = Linear(7, 8, name="linear3").init(42)

        mlp.check_metadata_updates()  # find field

        assert "linear3" in mlp.field_metadata

    def test_auto_annotations_static(self):
        class MLP(tx.Module):
            linear2: Linear = tx.static()

            def __init__(self, din, dmid, dout, name="mlp"):

                self.din = din
                self.dmid = dmid
                self.dout = dout
                self.name = name

                self.linear1 = Linear(din, dmid, name="linear1")
                self.linear2 = Linear(dmid, dout, name="linear2")

        mlp = MLP(2, 3, 5).init(42)

        assert "linear1" in mlp.field_metadata
        assert not mlp.field_metadata["linear2"].node

    def test_annotations_missing_field_no_error(self):
        class MLP(tx.Module):
            linear3: Linear  # missing field

            def __init__(self, din, dmid, dout, name="mlp"):

                self.din = din
                self.dmid = dmid
                self.dout = dout
                self.name = name

                self.linear1 = Linear(din, dmid, name="linear1")
                self.linear2 = Linear(dmid, dout, name="linear2")

        mlp = MLP(2, 3, 5).init(42)

        assert "linear1" in mlp.field_metadata
        assert "linear2" in mlp.field_metadata

    def test_hashable(self):
        class M(tx.Module):
            a: tx.Hashable[np.ndarray]

            def __init__(self):

                self.a = tx.Hashable(np.ones((3, 4), dtype=np.float32))

        m = M().init(42)

        N = 0

        @jax.jit
        def f(x):
            nonlocal N
            N += 1
            return x

        m = f(m)
        assert N == 1

        m = f(m)
        assert N == 1

        m.a = tx.Hashable(np.zeros((3, 4), dtype=np.float32))

        m = f(m)
        assert N == 2

        m = f(m)
        assert N == 2

    def test_initializer(self):
        init = tx.Initializer(lambda k: jax.random.uniform(k, shape=[3, 5]))

        @jax.jit
        def f(x):
            return x

        init2 = f(init)

    def test_uninitialized_tabulate(self):
        class MyModule(tx.Module):
            a: tp.Union[np.ndarray, tx.Initializer] = tx.Parameter.node()

            def __init__(self):

                self.a = tx.Initializer(lambda k: jax.random.uniform(k, shape=[3, 5]))

        module = MyModule()

        print(module.tabulate())

    def test_treex_filter(self):

        tree = dict(a=1, b=Linear(3, 4))

        tree2 = tx.filter(tree, tx.Parameter)
        assert isinstance(tree2["a"], tx.Nothing)

        tree2 = tx.filter(tree, lambda field: isinstance(field.value, int))
        assert tree2["a"] == 1

    def test_module_map(self):
        class A(tx.Module):
            def __init__(self):

                self.a = 1

        module = A()

        def map_fn(x):
            x.a = 2

        module2 = tx.apply(map_fn, module)

        assert module.a == 1
        assert module2.a == 2

    def test_compact_init(self):
        class A(tx.Module):
            a: int = tx.Parameter.node()

            @tx.compact
            def __call__(self):
                a = self.get_field("a", lambda: 1)
                return a

        class B(tx.Module):
            a: A
            b: int = tx.Parameter.node()

            @tx.compact
            def __call__(self):
                b = self.get_field("b", lambda: 2)
                a = A()()

                return a + b

        module = B().init(42)

        assert module.b == 2
        assert module.a.a == 1
        assert jax.tree_leaves(module) == [1, 2]

    def test_compact_init_rng(self):
        class A(tx.Module):
            a: jnp.ndarray = tx.Parameter.node()

            @tx.compact
            def __call__(self):
                a = self.get_field(
                    "a", lambda: jax.random.uniform(tx.next_key(), [2, 4])
                )
                return a

        class B(tx.Module):
            a: A
            b: jnp.ndarray = tx.Parameter.node()

            @tx.compact
            def __call__(self):
                b = self.get_field("b", lambda: jax.random.uniform(tx.next_key(), [4]))
                a = A()()

                return a + b

        module = B().init(42)

        assert module.b.shape == (4,)
        assert module.a.a.shape == (2, 4)

    def test_reset_context_on_constructor(self):
        from treex import module as module_m

        class A(tx.Module):
            a: jnp.ndarray = tx.Parameter.node()

            def __init__(self) -> None:
                assert module_m._CONTEXT.initializing is False
                assert module_m._CONTEXT.key is None

            @tx.compact
            def __call__(self):
                if self.first_run:
                    assert module_m._CONTEXT.initializing is True
                    assert module_m._CONTEXT.key is not None

                a = self.get_field(
                    "a", lambda: jax.random.uniform(tx.next_key(), [2, 4])
                )
                return a

        class B(tx.Module):
            a: A
            b: jnp.ndarray = tx.Parameter.node()

            @tx.compact
            def __call__(self):
                b = self.get_field("b", lambda: jax.random.uniform(tx.next_key(), [4]))
                a = A()()

                return a + b

        module = B().init(42)

        assert module.b.shape == (4,)
        assert module.a.a.shape == (2, 4)
