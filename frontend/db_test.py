import psycopg
import os
from dotenv import load_dotenv

load_dotenv(r'C:\Users\hongji.huang\OneDrive - PBA Systems Pte. Ltd\Desktop\BOM_Component__DWG_Mgmt\backend\.env')

conn = psycopg.connect(os.getenv('BOM_DATABASE_URL'))
cur = conn.cursor()

def check_fk():
    cur.execute("SELECT tc.table_name, kcu.column_name, ccu.table_name AS foreign_table_name, ccu.column_name AS foreign_column_name, rc.delete_rule FROM information_schema.table_constraints AS tc JOIN information_schema.key_column_usage AS kcu ON tc.constraint_name = kcu.constraint_name JOIN information_schema.constraint_column_usage AS ccu ON ccu.constraint_name = tc.constraint_name JOIN information_schema.referential_constraints AS rc ON rc.constraint_name = tc.constraint_name WHERE constraint_type = 'FOREIGN KEY';")
    return cur.fetchall()

print('Foreign Keys and Delete Rules:', check_fk())

cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public';")
print('Tables:', cur.fetchall())
