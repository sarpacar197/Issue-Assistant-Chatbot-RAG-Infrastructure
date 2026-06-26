import os
import weaviate
from weaviate.classes.config import Configure
from langchain_openai import AzureOpenAIEmbeddings
from dotenv import load_dotenv
from docx import Document

load_dotenv()

embedder = AzureOpenAIEmbeddings(
    azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
    azure_deployment=os.environ["AZURE_EMBEDDING_DEPLOYMENT"],
    api_version="VERSION",
    api_key=os.environ["AZURE_OPENAI_API_KEY"],
)



PATH = os.environ.get("DOCS_PATH", "./data/docs")
HOST = os.environ.get("WEAVIATE_HOST", "localhost")

def docx_read(path):
    doc = Document(path)
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())

with weaviate.connect_to_local(host=HOST, port=8080) as client:
    client.collections.delete("Document")
    if not client.collections.exists("Document"):
        client.collections.create("Document", vectorizer_config=Configure.Vectorizer.none())
    coll = client.collections.get("Document")

    files = [f for f in os.listdir(PATH) if f.endswith(".docx")][:10]
    with coll.batch.dynamic() as batch:
        for file in files:
            text = docx_read(os.path.join(PATH, file))
            if not text.strip():
                continue
            vec = embedder.embed_query(text)
            batch.add_object(properties={"text": text, "source": file}, vector=vec)
            print("Yüklendi:", file)
    print("Toplam kayıt:", len(coll))