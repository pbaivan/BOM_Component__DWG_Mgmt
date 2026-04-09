import sys
import os

with open("../../backend/BOM_Backend_API.py", "r", encoding="utf-8") as f:
    content = f.read()

split_str = '@app.get("/api/search")'
if split_str not in content:
    print("Cannot find split point!")
    sys.exit(1)

parts = content.split(split_str)
prefix = parts[0]

new_func = """@app.get("/api/search")
async def search_drawings(category: str, component: str):
    \"\"\"
    Search for component drawings across multiple SharePoint Folders via Microsoft Graph API.
    Replaces static FOLDER_ID with dynamic URL processing supporting multiple comma-separated URLs.
    \"\"\"
    import msal
    import httpx
    import urllib.parse
    import base64
    
    TENANT_ID = os.getenv("SHAREPOINT_TENANT_ID")
    CLIENT_ID = os.getenv("SHAREPOINT_CLIENT_ID")
    CLIENT_SECRET = os.getenv("SHAREPOINT_CLIENT_SECRET")
    
    # 支持多个 URL，逗号分隔
    TARGET_URL_STR = os.getenv("SHAREPOINT_TARGET_URL")
    
    if not all([TENANT_ID, CLIENT_ID, CLIENT_SECRET]):
        logger.error("SharePoint AD credentials not fully configured in .env")
        raise HTTPException(status_code=500, detail="SharePoint Graph API credentials not fully configured.")
        
    if not TARGET_URL_STR:
        logger.error("SHAREPOINT_TARGET_URL is not provided in .env")
        raise HTTPException(status_code=500, detail="No SharePoint Target URL provided in configuration.")
    
    if not component or len(component.strip()) < 2:
        return {
            "status": "success",
            "mock_category_folder": category,
            "sharepoint_path": ["SharePoint", "Drawings"],
            "results": []
        }
        
    component = component.strip()
    target_urls = [u.strip() for u in TARGET_URL_STR.split(",") if u.strip()]
    all_drawings = []
    
    try:
        # 1. 获取 App 级别的 Access Token
        authority = f"https://login.microsoftonline.com/{TENANT_ID}"
        app_msal = msal.ConfidentialClientApplication(
            CLIENT_ID, authority=authority, client_credential=CLIENT_SECRET
        )

        result = app_msal.acquire_token_silent(["https://graph.microsoft.com/.default"], account=None)
        if not result:
            result = await asyncio.to_thread(
                app_msal.acquire_token_for_client, scopes=["https://graph.microsoft.com/.default"]
            )

        if "access_token" not in result:
            logger.error(f"MSAL Token error: {result.get('error_description', result)}")
            raise HTTPException(status_code=500, detail="Failed to acquire Azure AD Access Token.")
            
        headers = {'Authorization': 'Bearer ' + result['access_token']}
        
        async with httpx.AsyncClient() as client:
            # 对于给定的每一个 URL，都去对应的图纸库搜一圈
            for url in target_urls:
                try:
                    # 将 URL 转换为 driveItem
                    b64_url = base64.urlsafe_b64encode(url.encode()).decode().rstrip('=')
                    encoded_url = 'u!' + b64_url
                    res = await client.get(f'https://graph.microsoft.com/v1.0/shares/{encoded_url}/driveItem', headers=headers)
                    
                    if res.status_code != 200:
                        logger.error(f"Cannot resolve URL {url}: {res.text}")
                        continue
                        
                    data = res.json()
                    drive_id = data.get('parentReference', {}).get('driveId')
                    folder_id = data.get('id')
                    
                    if not drive_id or not folder_id:
                        continue

                    # 尝试读取该目录下的 Category Mapping 子文件夹
                    category_id_map = {}
                    children_res = await client.get(f'https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{folder_id}/children', headers=headers)
                    if children_res.status_code == 200:
                        kids = children_res.json().get('value', [])
                        category_id_map = {c['name']: c['id'] for c in kids if 'folder' in c}
                
                    # 如果有对应的 category 文件夹，缩小查询范围，没有就在当前库根目录查
                    target_folder_id = category_id_map.get(category, folder_id)
                    
                    # Graph API Search
                    encoded_query = urllib.parse.quote(component)
                    search_url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{target_folder_id}/search(q='{encoded_query}')"
                    search_res = await client.get(search_url, headers=headers)
                    
                    if search_res.status_code == 200:
                        items = search_res.json().get("value", [])
                        for item in items:
                            if "folder" in item:
                                continue
                            
                            file_name = item.get("name", "")
                            
                            # 严格匹配文件名包含 component
                            if component.lower() not in file_name.lower():
                                continue
                            
                            # 提取正确的 download URL (微软常常要求对下载链接执行二次解析，这里先用原有的或者直开链接)
                            w_url = item.get("webUrl", "")
                            dn_url = item.get("@microsoft.graph.downloadUrl", w_url)
                            
                            # SharePoint bug fix: the direct download link MUST use the specific file download format
                            # If it doesn't have a download URL via @microsoft.graph, we force-replace the ?web=1 viewer parameter
                            if dn_url == w_url and "web=1" in dn_url:
                                dn_url = dn_url.replace("web=1", "download=1").replace("csf=1&", "")
                            
                            all_drawings.append({
                                "id": item.get("id"),
                                "name": file_name,
                                "version": "Live",
                                "type": "PDF" if file_name.lower().endswith(".pdf") else "Model",
                                "date": item.get("lastModifiedDateTime", "")[:10] if item.get("lastModifiedDateTime") else "Unknown",
                                "url": w_url, # online preview
                                "download_url": dn_url # direct download
                            })
                except Exception as iter_e:
                    logger.warning(f"Error processing URL {url}: {iter_e}")

            # Deduplicate by ID just in case
            unique_drawings = {d["id"]: d for d in all_drawings}.values()

            return {
                "status": "success",
                "mock_category_folder": category,
                "sharepoint_path": [
                    "SharePoint Targets", category, component
                ],
                "results": list(unique_drawings)
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("SharePoint search implementation error")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("BOM_Backend_API:app", host="0.0.0.0", port=8000, reload=True)
"""

with open("../../backend/BOM_Backend_API.py", "w", encoding="utf-8") as f:
    f.write(prefix + new_func)

print("Updated BOM_Backend_API with multiple URL support!")
