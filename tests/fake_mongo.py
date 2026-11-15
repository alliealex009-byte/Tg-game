"""Tiny in-memory stand-in for the parts of pymongo that app/mongo.py uses, so storage logic can be tested offline.
Supports: find_one, update_one ($set/$inc/$setOnInsert, upsert), insert_one, find().sort().limit(), count_documents, aggregate($group/$sum)."""
import copy
import itertools

_ids = itertools.count(1)


def _match(doc, flt):
    for k, cond in flt.items():
        v = doc.get(k)
        if isinstance(cond, dict):
            for op, x in cond.items():
                ok = {"$gte": lambda: v is not None and v >= x, "$lte": lambda: v is not None and v <= x,
                      "$gt": lambda: v is not None and v > x, "$lt": lambda: v is not None and v < x,
                      "$ne": lambda: v != x}[op]()
                if not ok:
                    return False
        elif v != cond:
            return False
    return True


class Result:
    def __init__(self, matched=0, upserted=None):
        self.matched_count, self.upserted_id = matched, upserted


class Cursor:
    def __init__(self, docs):
        self.docs = docs

    def sort(self, spec):
        for key, direction in reversed(spec):
            self.docs.sort(key=lambda d: d.get(key, 0), reverse=direction < 0)
        return self

    def limit(self, n):
        self.docs = self.docs[:n]
        return self

    def __iter__(self):
        return iter(copy.deepcopy(self.docs))


class Collection:
    def __init__(self):
        self.docs = []

    def create_index(self, *a, **k):
        pass

    def find_one(self, flt=None):
        for d in self.docs:
            if _match(d, flt or {}):
                return copy.deepcopy(d)
        return None

    def find(self, flt=None):
        return Cursor([d for d in self.docs if _match(d, flt or {})])

    def insert_one(self, doc):
        doc = copy.deepcopy(doc)
        doc.setdefault("_id", next(_ids))
        self.docs.append(doc)

    def update_one(self, flt, upd, upsert=False):
        for d in self.docs:
            if _match(d, flt):
                for k, v in upd.get("$set", {}).items():
                    d[k] = v
                for k, v in upd.get("$inc", {}).items():
                    d[k] = d.get(k, 0) + v
                return Result(1)
        if upsert:
            doc = {k: v for k, v in flt.items() if not isinstance(v, dict)}
            doc.update(upd.get("$setOnInsert", {}))
            doc.update(upd.get("$set", {}))
            self.docs.append(doc)
            return Result(0, doc["_id"])
        return Result(0)

    def count_documents(self, flt):
        return len([d for d in self.docs if _match(d, flt)])

    def aggregate(self, pipeline):
        g = pipeline[0]["$group"]
        field = g["s"]["$sum"].lstrip("$")
        return [{"_id": None, "s": sum(d.get(field, 0) for d in self.docs)}] if self.docs else []


class FakeDatabase(dict):
    def __missing__(self, k):
        self[k] = Collection()
        return self[k]


class FakeClient(dict):
    def __missing__(self, k):
        self[k] = FakeDatabase()
        return self[k]
