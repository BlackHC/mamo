# Dumbo

A big flappy cache that never forgets. (Dumb-o jell-o)

## Idea

Decorate functions with the dumbo decorator to memoize computations, but only when
it is worth it.

## Architecture

Different modules

* persistence

We need to store computed values and be able to reload them.

Creating correspondence between old code and current code is the trickiest bit.

* API/wrappers

API to make the experience of using dumbo a nice one.

* decision engine

We need to decide when to recompute and when to load from disk.

## TODOs

We can start with the API and the wrappers.

### What's the MVP?

We can memoize results, cache them and load them again.

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

## How do we find an identifier for a function that can be stored?

Fully qualified name + hash of code?

## Code dependency management

I had this idea of tracing the bytecode to determine code dependencies and invalidate cached entries on code changes.

This does not seem feasible. I could detect function calls but method calls for local variables would be too hard.

Maybe, it is sufficient to only look at function calls and enumerate all potential field names?

This is rather brittle though. Maybe only well-defined function calls?
And module calls?

## Lazy loading

Another idea which is more difficult to implement is lazy loading of data. But that would require dummy/proxy objects.
Just add a custom wrapper for cases when I want to use that feature!!!


