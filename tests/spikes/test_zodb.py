import ZODB
import persistent
import dataclasses

@dataclasses.dataclass
class Entry(persistent.Persistent):
    author: str
    num_refs: int

def test_zodb():
    connection = ZODB.connection(None)
    entry = Entry("Dumbo Dumbo", 10)
    root = connection.root
    root.entry = entry

    import transaction

    transaction.commit()
    print(root.entry)