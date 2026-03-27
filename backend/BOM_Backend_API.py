from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import io
import uvicorn
import asyncio
from typing import Optional

app = FastAPI(title="BOM Platform API (Mock Version)")

# 配置 CORS，允许 React 前端跨域调用
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 开发阶段允许所有域
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 内存中缓存解析后的 BOM 数据
global_bom_data = []


@app.get("/")
async def root():
    """根目录欢迎测试页"""
    return {
        "message": "恭喜！BOM 平台后端已成功运行！",
        "docs_url": "访问 /docs 查看接口文档"
    }


@app.post("/api/upload")
async def upload_bom(file: UploadFile = File(...)):
    """接收前端上传的 BOM 文件并解析"""
    global global_bom_data
    contents = await file.read()

    try:
        if file.filename.endswith('.csv'):
            df = pd.read_csv(io.BytesIO(contents))
        else:
            df = pd.read_excel(io.BytesIO(contents), engine='openpyxl')

        df = df.fillna("")
        global_bom_data = df.to_dict(orient="records")
        return {"status": "success", "rows": len(global_bom_data), "data": global_bom_data}

    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/search")
async def search_drawings(category: str, component: str):
    """
    Phase 1: 完全使用 Mock 数据模拟 SharePoint 返回。
    """
    # 模拟网络延迟 0.6 秒，让前端 loading 动画更真实
    await asyncio.sleep(0.6)

    # 根据 Component 型号生成动态的 Mock 图纸数据
    mock_drawings = []

    # 如果是带有横杠的常规组件 (如 01-00128434)
    if component and "-" in component:
        mock_drawings = [
            {
                "id": f"doc_{component}_1",
                "name": f"{component}_Assembly_Drawing.pdf",
                "version": "A01",
                "url": "#",
                "type": "PDF",
                "date": "2023-10-15"
            },
            {
                "id": f"doc_{component}_2",
                "name": f"{component}_Part_Details.pdf",
                "version": "B02",
                "url": "#",
                "type": "PDF",
                "date": "2023-11-20"
            },
            {
                "id": f"doc_{component}_3",
                "name": f"{component}_3D_Model.step",
                "version": "Release",
                "url": "#",
                "type": "CAD",
                "date": "2023-12-01"
            }
        ]
    elif component:
        # 其他基础组件
        mock_drawings = [
            {
                "id": f"doc_{component}_4",
                "name": f"{component}_Datasheet.pdf",
                "version": "1.0",
                "url": "#",
                "type": "PDF",
                "date": "2024-01-10"
            }
        ]

    # 将解析到的 category 放在返回中以示验证
    return {
        "status": "success",
        "mock_category_folder": category,
        "results": mock_drawings
    }


if __name__ == "__main__":
    # 注意：确保你的文件名依然叫 BOM_Backend_API.py
    uvicorn.run("BOM_Backend_API:app", host="0.0.0.0", port=8000, reload=True)