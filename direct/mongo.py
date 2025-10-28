import os
from dotenv import load_dotenv
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

load_dotenv()
DB_ORL = os.getenv('DB_URL')
DB_NAME = 'stocks_db'
DB_COLL = 'fwdpe'

class Mongo:
    def __init__(self):
        self.client = MongoClient(
            DB_ORL,
            server_api=ServerApi('1'),
            timeoutMS=5000,
            maxPoolSize=2
        )
        self.db = self.client[DB_NAME]
        self.coll = self.db[DB_COLL]
