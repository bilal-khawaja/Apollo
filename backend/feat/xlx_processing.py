import pandas as pd
import io
from fastapi import UploadFile, File, HTTPException, status

async def file_processor(file: UploadFile, clean_headers: bool = True) -> list[dict]:
    """
    Utility function to handle the repetitive process of reading an uploaded 
    Excel file and preparing clean dictionary records.
    """
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Only valid Excel sheets (.xlsx, .xls) are supported.")
        
    try:
        content = await file.read()
        df = pd.read_excel(io.BytesIO(content))
        df = df.where(pd.notnull(df), None)
        
        if clean_headers:
            # Strip trailing spaces and lowercase everything to reduce human matching errors
            df.columns = [str(col).strip().lower() for col in df.columns]
            
        return df.to_dict(orient='records')
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to process Excel formatting: {str(e)}")