import ZODB
import persistent
import dataclasses


@dataclasses.dataclass
class Entry(persistent.Persistent):
    author: str
    num_refs: int


@dataclasses.dataclass
class BaseClass(persistent.Persistent):
    base_field: str


@dataclasses.dataclass
class ExtendedClass(BaseClass):
    extended_field: str


def test_zodb():
    connection = ZODB.connection(None)
    entry = Entry("Dumbo Dumbo", 10)
    root = connection.root
    root.entry = entry

    import transaction

    transaction.commit()
    print(root.entry)


def test_persistent_inheritance():
    db = ZODB.DB(None)
    connection = db.open()
    connection2 = db.open()
    instance = ExtendedClass("base", "extended")
    connection.root.instance = instance

    import transaction

    transaction.commit()

    connection3 = db.open()

    print(connection3.root.instance)
    print(connection2.root.instance)