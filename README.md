# Dumbo

A big flappy cache that never forgets.

## Idea

Decorate functions with the dumbo decorator to memoize computations, but only when
it is worth it.

## Considerations

### How do we decide whether to recompute something?

Especially, when methods can be stochastic or the data is big, we don't necessarily want to hash the contents. We might want to allow for controlled stochasticity.

So we want to be able to measure how long the first computation takes (and how big the resulting data is), and use that information to determine whether to cache the results.

For stochasticity, we could allow injecting different seeds and allow a certain number of samples to be created and cached.

We can use input/argument matchers to determine whether a cache entry matches a cached entry.

### How do we cache structured data?

If we use a WeakKeyDictionary to add cache attributes, we need to deal with structured data separately.

Ideally, we would like to find out when we access into cached data and resolve that.

An easier solution for starters is to create entries for important subcomponents of
structured data.

## What would a dumbo magic in IPython look like?

If we dumbo a cell, how do we know its inputs? We need a function.
We could specify inputs and outputs by hand.

```
    %%dumbo (inputs) -> outputs
```
