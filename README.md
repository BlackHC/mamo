# Mamo
Your DNN-friendly persistent memoization library. Allows for stochasticity and non-determinism in memoized functions, with the goal of quick prototyping and experimentation without redundant computations.

## Getting started

```shell script
pip install mamo
```

## Design

By default, Mamo fingerprints the computational graph (as far as known to Mamo). Mamo only fingerprints data by hashing it when unavoidable.

Code changes drive data changes: especially, with high-dimensional data and many dependencies, it is highly likely that different calls return different data, so it makes sense to use this as default assumption.

Mamo assumes functions are pure and intentionally ignores stochasticity and non-determinism - otherwise, anything using a random number generator would constantly be marked as stale.

This has the advantage that Mamo can be used in a wide variety of use-cases, including those that are not deterministic, e.g. when we train DNNs or run code on GPUs.

What is important is that the results are congruent with the code: they can have been produced by running the code, and that we correctly mark data as stale when the code changes.

In the future, Mamo will support different fingerprints for the same value (i.e. running multiple trials).

## More details

Mamo has two important concepts that we need to distinguish:
value identities and fingerprints.

We need to identify objects that are the same semantically equivalent (via their call graph). For example, `evaluate(model_instance, dataset)` identifies the same object even if the model instance changes, or we update the dataset.

On the other hand, fingerprints are used to determine whether the value has changed. For example, if we change the code of `evaluate`, we want to mark the result as stale without having to re-run the entire computation graph.

## Assumptions

The biggest assumption for the current design is:

Values are unlikely to be the same when we rerun a function with the same arguments. This means that we can use hashing for checking inequality checks, and that different computational graphs imply unequal values.

Thus, Mamo does not implement perfect memoization but only a heuristic that does not try to actually match arguments fully, which allows for faster execution.
