import weaviate
import pandas as pd


with weaviate.connect_to_local() as client:
    coll = client.collections.get("Document")
    print("Number of Records :", len(coll) )

    res = coll.query.fetch_objects(limit=1, include_vector=True)
    o = res.objects[0]
    print("kaynak : ", o.properties["source"])
    print("Vector:", "default" in o.vector, "| Length:", len(o.vector.get("default", [])))

