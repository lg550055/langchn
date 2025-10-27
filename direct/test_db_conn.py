import os
import json
from dotenv import load_dotenv
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

load_dotenv()
DB_ORL = os.getenv('DB_URL')

client = MongoClient(
    DB_ORL,
    server_api=ServerApi('1'),
    timeoutMS=5000,
    maxPoolSize=2
)

# ping to confirm a successful connection
try:
    client.admin.command('ping')
    print("Pinged your deployment. You successfully connected to MongoDB!")
except Exception as e:
    print(e)

# Create a db, if not exists -need to perform a write operation, e.g insert doc into collection
db = client['stocks_db']
coll = db['fwdpe']  # or: db.create_collection('fwdpe')
# unique index on 'date' for efficient upserts and queries
coll.create_index('date', unique=True)

# Process all JSON files in the current directory
path = './archive/'
for filename in os.listdir(path):
    if filename.startswith('2025'):
        print("-- processing: ", filename)
        full_path = path + filename
        with open(full_path, 'r') as f:
            data = json.load(f)

        metadata = {}
        if 'metadata' in data:
            date = data['metadata']['date']
            # Separate metadata and stocks
            metadata = data.pop('metadata')
        else:
            date = filename.split('.')[0]
            print("---- date from filename:", date,"-end")
                
        document = {
            'date': date,
            'stocks': data,  # stock symbols and their data
            'metadata': metadata
        }
        
        # Upsert the document based on date (insert if new, replace if exists)
        coll.replace_one({'date': date}, document, upsert=True)

print("-- Stored all dated json file data in db")

db_names = client.list_database_names()
print("-- db names: ", db_names)

# Close connection; optional, but good practice
client.close()
