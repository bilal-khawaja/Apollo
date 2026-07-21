import pandas as pd
import io
from fastapi import UploadFile, File, HTTPException, status
from fastapi.responses import StreamingResponse
from .webhooks_service import N8nEndpoints, get_n8n_url
import httpx


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


async def file_generation(data: list[dict], filename: str, timeout : float = 30.0 ):
        
        url = get_n8n_url(N8nEndpoints.FILE_GENERATION)
        
        # Calling webhooks service to generate the excel file
        async with httpx.AsyncClient() as client:
            try:

                response = await client.post(url, json=data, timeout=timeout)
                headers = {
                        'Content-Disposition': f'attachment; filename="{filename}.xlsx"'
                    }
                
                if response.status_code != 200:
                    raise HTTPException(status_code=response.status_code, detail="Failed to generate Excel file.")

                # Converting the response content to a BytesIO object for streaming
                buffer = io.BytesIO(response.content)

                return StreamingResponse(
                buffer,
                media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                headers=headers)

            except httpx.RequestError as e:
                raise HTTPException(status_code=500, detail=f"Error communicating with the file generation service: {str(e)}")
