# Mamo
Your friendly neighborhood persistent memoization library.

## Getting started

```shell script
pip install mamo
```

## Design

Code changes drive data changes. Especially, with big data, it is highly likely that different calls return different data.

Mamo fingerprints data by hashing it when unavoidable and by fingerprinting the computational graph (as far as known to Mamo) otherwise.

As future extension, Mamo will support different fingerprints for the same value, but in common use-cases detecting code changes is more impactful.

It assumes functions are pure, which allows for ignoring stochasticity. Otherwise anything using a random number generator would constantly be marked as stale.

## More details

Mamo has concepts: value identity and fingerprints. Fingerprints are used to determine whether a stored computed value is stale:
If an argument value to the function that computes a value is different (different fingerprints) from the one that was used originally, we mark the value as stale.

Value identity is about when two values have the same identity. (If every value was unique, there would never be stale values.) This is only an important concept for computed values: the result of a function with the same arguments (argument identity) has the same value identity as the stored result for a previous call.

## Assumptions

The biggest assumption for the current design is:

Values are unlikely to ever be the same. 

This means that we can use hashing for checking equality checks, and that different computational graphs imply unequal values.

Thus, Mamo does not implement perfect memoization at the moment but only a heuristic that does not try to actually match arguments fully.
