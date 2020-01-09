from dataclasses import dataclass
from typing import Optional, Set

from dumbo.internal.fingerprints import Fingerprint
from dumbo.internal.identities import ValueIdentity, ComputedValueIdentity
from dumbo.internal.providers import ValueProvider


@dataclass
class ValueProviderMediator(ValueProvider):
    result_provider: ValueProvider
    external_value_provider: ValueProvider

    def identify_value(self, value) -> ValueIdentity:
        return self.external_value_provider.identify_value(value) or self.result_provider.identify_value(value)

    def fingerprint_value(self, value) -> Fingerprint:
        return self.external_value_provider.fingerprint_value(value) or self.result_provider.fingerprint_value(value)

    def resolve_value(self, vid: ValueIdentity):
        if isinstance(vid, ComputedValueIdentity):
            return self.result_provider.resolve_value(vid)
        return self.external_value_provider.resolve_value(vid)

    def resolve_fingerprint(self, vid: ValueIdentity):
        if isinstance(vid, ComputedValueIdentity):
            return self.result_provider.resolve_fingerprint(vid)
        return self.external_value_provider.resolve_fingerprint(vid)

    def register(self, vid: ValueIdentity, value: object, fingerprint: Optional[Fingerprint]):
        if value is not None:
            existing_vid = self.identify_value(value)
            if existing_vid is not None and existing_vid != vid:
                raise AttributeError(
                    f"{vid} has same value as {existing_vid}!"
                    'We follow an "each computation, different result" policy.'
                    "This makes tracking possible."
                )

        # Vids are compartmentalized by value registry and thus we don't need any
        # additional error checking here.

        if isinstance(vid, ComputedValueIdentity):
            return self.result_provider.register(vid, value, fingerprint)
        else:
            return self.external_value_provider.register(vid, value, fingerprint)

    def invalidate(self, value: object):
        if self.external_value_provider.has_value(value):
            self.external_value_provider.invalidate(value)
        elif self.result_provider.has_value(value):
            self.result_provider.invalidate(value)

    def has_vid(self, vid: ValueIdentity):
        return self.external_value_provider.has_vid(vid) or self.result_provider.has_vid(vid)

    def has_value(self, value):
        return self.external_value_provider.has_value(value) or self.external_value_provider.has_value(value)

    def get_vids(self) -> Set[ValueIdentity]:
        vids = set()
        vids.update(self.external_value_provider.get_vids())
        vids.update(self.result_provider.get_vids())
        return vids
