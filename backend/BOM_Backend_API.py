from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import io
import uvicorn

app = FastAPI(title="BOM Platform API")

# 配置 CORS，允许 React 前端跨域调用
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 开发阶段允许所有域
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 内存中缓存解析后的 BOM 数据，提升 Phase 1 的查询速度
global_bom_data = []


@app.post("/api/upload")
async def upload_bom(file: UploadFile = File(...)):
    """接收前端上传的 BOM 文件并解析"""
    global global_bom_data
    contents = await file.read()

    # 动态判断是 CSV 还是 Excel
    try:
        if file.filename.endswith('.csv'):
            df = pd.read_csv(io.BytesIO(contents))
        else:
            df = pd.read_excel(io.BytesIO(contents))

        # 填充空值，避免 JSON 序列化报错
        df = df.fillna("")

        # 转换为字典列表
        global_bom_data = df.to_dict(orient="records")
        return {"status": "success", "rows": len(global_bom_data), "data": global_bom_data}

    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/search")
async def search_drawings(category: str, component: str):
    """
    Phase 1: 模拟对接 SharePoint Graph API。
    实际开发时，这里将引入 msal 库获取 Token，并通过 httpx 发送请求到 Graph API。
    """
    # 模拟 Graph API 的检索耗时
    import asyncio
    await asyncio.sleep(0.5)

    # 根据型号模糊匹配一些测试的图纸数据
    mock_drawings = []
    if "02-" in component or "01-" in component:
        mock_drawings = [
            {"id": "doc1", "name": f"{component}A01_Assy.pdf", "version": "A01", "url": "#", "type": "PDF"},
            {"id": "doc2", "name": f"{component}B01_Part.pdf", "version": "B01", "url": "#", "type": "PDF"},
            {"id": "doc3", "name": f"{component}_Model.step", "version": "-", "url": "#", "type": "CAD"}
        ]
    elif component:
        mock_drawings = [
            {"id": "doc4", "name": f"{component}_Datasheet.pdf", "version": "1.0", "url": "#", "type": "PDF"}
        ]

    return {
        "status": "success",
        "category_mapped": f"Folder_ID_FOR_{category}",
        "results": mock_drawings
    }


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)