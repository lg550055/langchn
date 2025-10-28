import os
import json
from dotenv import load_dotenv
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

load_dotenv()
DB_ORL = os.getenv('DB_URL')
DB_NAME = 'stocks_db'
DB_COLL = 'fwdpe'

class MongoWrapper:
    def __init__(self):
        self.client = MongoClient(
            DB_ORL,
            server_api=ServerApi('1'),
            timeoutMS=5000,
            maxPoolSize=2
        )
        self.db = self.client[DB_NAME]
        self.coll = self.db[DB_COLL]

    def save_file_data_to_db(self, path: str, date: str) -> None:
        with open(path, 'r') as f:
            data = json.load(f)

        metadata = data.pop('metadata') if 'metadata' in data else ()

        document = {
            'date': date,
            'stocks': data,  # stock symbols and their data
            'metadata': metadata
        }

        # Upsert the document based on date (insert if new, replace if exists)
        self.coll.replace_one({'date': date}, document, upsert=True)
        # good practice: close connection
        self.client.close()
        print("-- Saved to db data for: ", date)
