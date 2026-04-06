import sys

with open(r'C:\Users\hongji.huang\OneDrive - PBA Systems Pte. Ltd\Desktop\BOM_Component__DWG_Mgmt\backend\BOM_Backend_API.py', 'r', encoding='utf-8') as f:
    content = f.read()

helper = '''
def _delete_save_record(record_id: str) -> None:
    normalized_record_id = _normalize_record_id(record_id)
    with _get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM bom_saved_records WHERE record_id = %s", (normalized_record_id,))
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="record_id not found.")
        conn.commit()
'''

endpoint = '''
@app.delete("/api/save/record/{record_id}")
async def delete_save_record(record_id: str):
    try:
        await asyncio.to_thread(_delete_save_record, record_id)
        return {
            "status": "success",
            "message": "BOM record and all associated tables have been permanently deleted.",
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to delete the BOM record.")
        raise HTTPException(status_code=500, detail="Failed to delete the BOM record.")
'''

if '_delete_save_record' not in content:
    content = content.replace('def _list_save_records', helper + '\n\ndef _list_save_records')
if '/api/save/record/{record_id}' not in content:
    content = content.replace('@app.get("/api/save/list")', endpoint + '\n@app.get("/api/save/list")')
    
with open(r'C:\Users\hongji.huang\OneDrive - PBA Systems Pte. Ltd\Desktop\BOM_Component__DWG_Mgmt\backend\BOM_Backend_API.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Patch applied successfully.")
