import pandas as pd
import io
from fastapi import UploadFile, File, HTTPException, status
from fastapi.responses import StreamingResponse

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


def file_generation(data: list[dict], filename: str, xl_name: str):

    # Utility function to generate an Excel file from a list of dictionaries.

    try:
        # converting dictionaries into a pandas DataFrame for easier manipulation and Excel writing
        df = pd.DataFrame(data)

        columns_to_drop = ["id", "org_id", "catalogue_id", "entry_date", "created_at", "updated_at", "location_id"]
        df = df.drop(columns=[col for col in columns_to_drop if col in df.columns], errors='ignore')

        # Create an in-memory buffer to hold the Excel file
        buffer = io.BytesIO()

        # Use pandas ExcelWriter to write the DataFrame to the buffer with openpyxl engine
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name=xl_name)
        
        # Reset the buffer's position to the beginning so it can be read from the start
        buffer.seek(0)

        # Prepare the response headers to indicate a file attachment with the specified filename
        headers = {
            'Content-Disposition': f'attachment; filename="{filename}.xlsx"'
        }

        # Return a StreamingResponse to send the Excel file back to the client
        return StreamingResponse(
        buffer,
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers=headers)

    except Exception as e:
        raise HTTPException(status_code=500, 
        detail=f"Failed to generate Excel file: {str(e)}")