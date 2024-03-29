# Mamo

A big flappy cache that never forgets.

## Idea

Decorate functions with the mamo decorator to memoize computations, but only when
it is worth it.

## Architecture

Different modules

* persistence

We need to store computed values and be able to reload them.

Creating correspondence between old code and current code is the trickiest bit.

* API/wrappers

API to make the experience of using mamo a nice one.

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

## What would a mamo magic in IPython look like?

If we mamo a cell, how do we know its inputs? We need a function.
We could specify inputs and outputs by hand.

```
    %%mamo (inputs) -> outputs
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

## How do we reload values actually???

I guess the initial idea was to use memoization to avoid recomputation.
This means that code has to be executed though. And we will dynamically decide whether to
reexecute it or load stored values.

## Identity of values

PyTorch and hashing is a baaaad idea. Can instead rely on trying to figure out if we have a CID instead. (Do we know how the value was computed?)

## Do we want to check CID values for staleness every single time?

Not, not really. Only when we load them initially!

## What about returning constants/literal?

What if we memoize a look-up function that returns cached objects itself?
Or the same object is returned by multiple functions?
We could add a proxy? And connect it to the right CID?
Could use the latest/longest CID?

Could always wrap results in a wrapper?

```python
@mamo
def f():
    return x


result = f()
...
```

Create a view/copy?

I really am looking for a computational graph. Could I use TorchScript?
This would allow me to track how variables have been created ...

But we never store this identity in code later.

Once a value has been assigned to a variable, it loses its history and origin.

Maybe I should be explicit about its origin then?

```python
result = mamo(f, ..., "description?")
```
I kinda wanna store the call info with the variable. I could just use a subfield? but then 
I need to duplicate. So need a proxy and yadda yadda

```python
X = "Hello world"

def a():
    return X
    

def b():
    return X
    
Y = a()
Z = b()

# If X changes both Y and Z need to change.
# If either a or b changes, either Y or Z need to change.
```

I also need to track global variables in functions.. not just calls! That makes it slightly easier though \o/

This really would work well with TorchScript or anything else that allows me to track data dependencies. It really means that I cannot use regular variables/objects anymore because I need to keep track of these things.

Alternatively, I could try to enfore a "each call, different result object" policy. For Torch and NumPy, I might just get different views if necessary!!!

## How do I persist a WeakKeyDictionary and what does that even mean?

I am using a `WeakKeyDictionary` as not to waste resources at the moment.

That only makes sense in so far as I don't care about memory management just yet.

However, for persistence, I would want to base this on different decisions.

I probably want to use a two-layer system that keeps a LRU-cache in memory and second layer
that uses ZODB for persistence.

## The default Fibonacci test case already breaks my policy *lol*

Of course, returning ints and literals is a bad idea because it breaks the wrappers.

## My error handling sucks

Identities don't store the actual values, so it's impossible to debug.
I should probably at least store the creating context! (As strings?)

Or, I could resolve values with a WeakValueDictionary.

## Always wrap primitive types in constant numpy arrays?

Also, mamo assumes immutable data types essentially. We can also enforce this to a degree.

## How do I write tests for Mamo?

I need a range of simple unit tests and integration tests for different modules to be able to keep developing the library and be sure that it works as intended.

## How can I link/support custom hash functions

The issue is that I might not just want to use the type because of hierarchies and other messes.

I could use a package based system. So, look up by using `__class__.__module__`.

## How can I actually support value-types for using caching?

If I only fingerprint literals/builtin types, and then still store as part of the CID,
I'm fucking things up over different runs of the app as the hash will be salted.

So:
* [x] don't use hash() anywhere
* [x] use hashlib and reproducible fingerprints!
* [x] store primitive builtin types as values
* [x] don't use id because ValueFingerprintIdentity will still make it into the persistent cache!

Maybe, I should add a way to store named values in the persistent cache?

And support aliases? So I can store a computation and retrieve it using an alias?
(Ala tags?)

Also:
* [x] add support for tagging value cids!
* [ ] add an is_stale_call check for the computational graph

## All registries ought to be merged probably

There will be significant overlap if I allow generation of fingerprints using
actual data. It will need a cut-off similarly to persisted_cache etc.

Also, need tests for all the new features!!!

So:
* [x] add tests for numpy and torch support
* [x] add tests for tagging values

Tagging def needs more work and a bidirectional wrapper.

* [x] add a bimap
* [x] collect globals etc from function calls for better dependency checks?
* [x] what about constants?

## External names and fingerprints can clash in bad ways

If you use a value without registering it first and then register it later,
things will break. Do not do that.

TODO:
* [x] ensure that we cannot register a value after it is known already.

## Functions cannot be identified by fingerprint. Fingerprints are only for staleness.

If we use function fingerprints, there are no staleness checks possible because different versions of the same function will actually be different.

It's a bit weird that I want to look-up by identity and then retrieve the fingerprint.
We can change the persistent cache to return a Value, FunctionFingerprint pair.
And the same with the online cache. 

This can contain debugging information: this can be expanded to contain information about the call time and circumstances etc.

## Values that are loaded from the persisted cache might not be sufficiently proxy-wrapped.

Only newly computed values are result-wrapped. Cached values that are loaded into the online
cache through the persisted cache are not wrapped. This ought to be fixed...

* [x] loaded values also need to be result wrapped.

## What's next?

This should be sufficient to start working on reproducing BatchBALD's variance analysis and polishing the API and finding issues.

## Also, I need an IPython/Jupyter cell magic...

I would like it to capture stores and look at the bytecode to determine which globals to use as inputs. So essentially we create a fake function and register its inputs and outputs.

To perform any of this, we need to compile the cell to bytecode and then examine it.

This won't supported nested cell magics etc sadly though.

STOREs are much harder to track than LOADs because they don't pop the TOS.

I'll just track STORE_GLOBALs for now...

TODOs:
 
* [x] support an IPython cellmagic
* [x] add support for a StoredDict or something that allows for wrapping of items

## What's the problem with storing cell results in a dict?

We have custom code to wrap dict results which is not mirrored in PersistedCache.
This is a bug. Moreover, it would be nice to be able to return multiple results in general.

Resolution: support tuples as special type everywhere and apply all module extensions separately to each tuple item.

## Polish the API with some toy examples.

TODO:

* [x] support a separate path for externally cached files

## Better support for deep function signatures and staleness

* [x] support functions calling mamo-wrapped functions (duh!)
* [x] add a cache for shallow function signatures
* [f] walk the cache and detect staleness?
* [x] can we use named cells somehow? we can use a name with the cell magic (as an option)

We cannot detect staleness automatically because we cannot resolve functions easily potentially...

How do we force recomputation in case of staleness (or general recomputation)?
We could use a decorator or context manager.

As an API it might be neat to have a way to mark stale entries for recomputation via C&P in Jupyter.

We could mark staleness at least and then flag it up in later calls.

(So keep a dirty flag in the online version of any loaded value.)

## Do we want recompute by default or reuse by default?

In a Jupyter setting, we might be okay with recomputing a direct call by using stale data for indirect calls.
In a script setting, we might be okay with recomputing by default.

In general, we might be okay with recomputing by default only if it takes less than a certain time.
Which sounds like a sensible thing to have.

## New sprint

* [x] use pickle for get_estimated_size (given that we will usually pickle/serialize later anyway!!!)
* [x] ValueFingerprint plus general code.
* [x] add get_cached_value_identities.
* [x] Need FingerprintWValue that has custom hash
* [x] add call fingerprint that also fingerprints args etc so we can determine staleness
* [x] add tests for callfingerprint staleness
* [x] add support for forgetting cells as well

## Staleness/call fingerprints

Because we are using an object-aware database, only stale entries will cause duplications of fingerprints. Staleness becomes a "simple" check if these call fingerprints match or not.

Biggest issue:

I'm storing func pointers now, but they won't re-resolve on autoreload.
This can be fixed by not using CIDs but by using function ids to func objects.
As soon as the function is wrapped again within mamo, the association will be updated.

## Random observation

Depending on a global variable that depends on the same function does not result in staleness.
Because we cut cyclic dependencies (as we simulate one call stack instead of allowing for different ones.)

## Reflection on the state of Mamo

Coming back to this code after a somewhat longer break: it is difficult to understand what's going on with the call logic.

The semantics of everything here is a mess :(

## Revisiting the semantics and goals of Mamo

The big and main question is:

Do I need to recompute a value because something has changed?

We have a computational graph of values. The identity of leaves is value-based and we can use hashes/digests to test equality.

The identity of other nodes is based on the call graph. The result of a computation is based on the actual value and not the graph though.

Maybe we don't want to/need to always compute digests

With value digests, we can determine if we actually need to recompute a function.
With the call graph, we can determine if a node is stale.

I forgot that the cache is only storing inner nodes.

Philosophically, I'm confounding multiple things.

How do I look up cached results? Vs staleness?

Each arg can be a node in the comp graph. So the key is the actual node in the call graph.

### Insight

Memoization uses fingerprints. The staleness/the computational graph uses identities.

Both hierarchies need to be separate and independent from each other.

Looking at the latest version of the code this is not true still :-/

#### Globals are considered evil

I need to remove globals from fingerprints! They make sense for debugging (to determine why functions are not pure and what the original state was), but not for fingerprinting:

a = f1(); f1 changes global g
b = f2(a); f2 reads global g

If we cache a and b, b will be considered stale because f1) won't be executed and thus g will not be changed.
b's fingerprint will expect g to have the changed state though and thus b will be marked stale.

This means my fingerprint semantics was wrong. I must not take globals into account like that.
I can use global reads to check for purity and/or enforce ignoring specific global reads.
(Alternatively I could support stochastic functions as alternative to non-pure ones.)

## Revisiting Jupyter Cells

The big Q: what do we do with stale Jupyter code cells?
If we reexecute a cell, it will overwrite the globals, but not wrap them.
So this should be part of the cell function.

Also, we cannot necessarily reexecute all calls because we might not store all values.

## get_fignerprint_vid

I don't understand the structure of this. OnlineCache contains the cache. get_fingerprint_vid doesn't need to be a part of it.
And fingerprint_computable_value doesn't have to be a part of fingerprint_registry?

## Weak OnlineCache

Do we want to keep Vid -> Fingerprint without keeping the value?
We can get those from PersistedOnlineCache. No need to keep a second layer!
However, the problem being PersistedOnlineCache does not store external values!

We could get rid of most of MamoOnlineCache entirely if we stored VIDs and Fingerprints in ObjProxies :shrug:
(The only exception would be special-cased external objects.)
However, that removes the idea of MamoOnlineCache as an intermediate caching layer :-/

So one can separate:
A FingerprintFactory for ComputedValues and a registry that connects vids and values,
and an online cache on top of the persisted cache

# FingerprintDigest

FingerprintDigestValue might create cycles that keep objects alive.
We need to duplicate the values to break cycles.

Or we can create a WeakBimap?

## What do we store in PersistentCache vs OnlineCache?

OnlineCache holds a mapping from vid <-> wrapped values
PersistedCache just holds values. We can rewrap values that are being passed to PersistedCache to make sure that there are no shared references.

I think I need to separate external values and tags and move these out of OnlineCache.

* [x] store pickled values instead of pure values
* [x] get rid of FingerpringDigestValue for a bit
* [x] create a class that connects vids<->values and fingerprints weakly

## Metadata in PersistedStore

Vid -> CachedValue
Vid -> Fingerprint
Vid -> Metadata
