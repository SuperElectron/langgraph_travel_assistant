import os
import shutil
import sqlite3
import pandas as pd
import requests
import re
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma

class DataPreparer:
    def __init__(self,
                 verbose: bool = False,
                 db_path: str = "./database/travel2.sqlite",
                 db_path_backup: str = "./database/travel2.backup.sqlite",
                 db_url: str = "https://storage.googleapis.com/benchmarks-artifacts/travel-db/travel2.sqlite",
                 faq_url: str = "https://storage.googleapis.com/benchmarks-artifacts/travel-db/swiss_faq.md",
                 vector_store: str = "./database/chroma_langchain_db",
                 ):

        self.verbose = verbose
        self.db_path = db_path
        self.db_path_backup = db_path_backup

        self.db_url = db_url
        self.faq_url = faq_url
        self.vector_store = vector_store

    def log(self, message: str) -> None:
        """Helper method for logging if verbose is True."""
        if self.verbose:
            print(message)

    def download_databases(self, overwrite: bool = False) -> None:
        if overwrite or not os.path.exists(self.db_path):
            self.log("Trying to request and download database from URL...")
            response = requests.get(self.db_url)
            # Ensure the request was successful
            response.raise_for_status()
            with open(self.db_path, "wb") as f:
                f.write(response.content)
            self.log(f"DB saved to {self.db_path}")
            # Backup - we will use this to "reset" our DB in each section
            shutil.copy(self.db_path, self.db_path_backup)
            self.log(f"DB copied to {self.db_path_backup}")
        else:
            self.log(f"DB already exists at {self.db_path}. Skipping download...")

    def update_timestamps(self) -> None:
        conn = sqlite3.connect(self.db_path)
        self.log(f"DB connection established to {self.db_path}")
        cursor = conn.cursor()

        sql_query = """SELECT name FROM sqlite_master WHERE type='table';"""
        tables = pd.read_sql(sql_query, conn)["name"].to_list()

        table_dataframes = {}
        for table in tables:
            table_dataframes[table] = pd.read_sql_query(f"SELECT * FROM {table}", conn)

        latest_flight_time = pd.to_datetime(
            table_dataframes["flights"]["actual_departure"].replace("\\N", pd.NaT)
        ).max()

        current_time = pd.to_datetime("now").tz_localize(latest_flight_time.tz)

        time_diff = current_time - latest_flight_time

        table_dataframes["bookings"]["book_date"] = (
                pd.to_datetime(
                    table_dataframes["bookings"]["book_date"].replace("\\N", pd.NaT),
                    utc=True,
                )
                + time_diff
        )

        self.log(f"Bookings table, timestamps shifted by {time_diff} days")

        datetime_columns = [
            "scheduled_departure",
            "scheduled_arrival",
            "actual_departure",
            "actual_arrival",
        ]
        for column in datetime_columns:
            table_dataframes["flights"][column] = (
                    pd.to_datetime(
                        table_dataframes["flights"][column].replace("\\N", pd.NaT)
                    )
                    + time_diff
            )
        self.log(f"Flights table, timestamps shifted by {time_diff} days")

        for table_name, table_df in table_dataframes.items():
            table_df.to_sql(table_name, conn, if_exists="replace", index=False)

        self.log(f"All timestamp changes overwritten to DB: {self.db_path}")
        conn.commit()
        conn.close()

    def create_faq_documents(self) -> list[Document]:
        """Custom text splitter for the FAQ document."""
        response = requests.get(self.faq_url)
        response.raise_for_status()
        faq_text = response.text

        docs = [
            Document(page_content=txt.strip())
            for txt in re.split(r"(?=\n##)", faq_text)
        ]
        return docs

    def create_vectorstore(self, overwrite: bool = False) -> Chroma:
        embedding_model = OpenAIEmbeddings(model="text-embedding-3-small")
        collection_name = "faq_vectors"

        if os.path.exists(self.vector_store) and not overwrite:
            # Load the existing vector store
            vectorstore = Chroma(
                collection_name=collection_name,
                embedding_function=embedding_model,
                persist_directory=self.vector_store,
            )
            self.log("Existing vectorstore loaded successfully with type: VectorStore")
        else:
            # Create a new vector store from documents and persist it
            vectorstore = Chroma.from_documents(
                documents=self.create_faq_documents(),
                persist_directory=self.vector_store,
                embedding=embedding_model,
                collection_name=collection_name,
            )
            self.log("Vector database created from the documents successfully!")

        return vectorstore

    def start_retriever(self, overwrite: bool = False, k: int = 2):
        vectorstore = self.create_vectorstore(overwrite)
        retriever = vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": k})
        self.log(f"Retriever instantiated = 'similarity: {k}'")
        return retriever

    def prepare_all(self) -> None:

        self.download_databases(overwrite=True)
        self.update_timestamps()
        retriever = self.start_retriever(overwrite=False)
        self.log("All preparation steps completed successfully.")
