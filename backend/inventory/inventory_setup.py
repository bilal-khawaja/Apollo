from fastapi import APIRouter, HTTPException, status, Depends, Body, UploadFile, File
from sqlmodel import select, Session
from database.models import User, Organizations, ProductCatalogue 
from database.setup import get_session
from accounts.auth.token import  get_current_user
from sqlmodel.ext.asyncio.session import AsyncSession
import pandas as pd
import io

router = APIRouter()

@router.post('/upload_product_catalogue')
async def upload_catalogue(
    file : UploadFile = File(...), 
    session : AsyncSession = Depends(get_session),
    current_user = Depends(get_current_user)
):

    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, 
                                    detail="Only Excel files are supported.")

    try:
        content = await file.read()
        vfile_clone = io.BytesIO(content)
        df = pd.read_excel(vfile_clone)
        df = df.where(pd.notnull(df), None)
        catalogue_items_dict = df.to_dict(orient='records') # records is a list of dictionaries, where each dictionary represents a row in the DataFrame

        product_count = 0

        catalogue_ojects = [ProductCatalogue(
            **{
                **item,
                "org_id": current_user.org_id,
                "sku_or_barcode": str(item["sku_or_barcode"]),
                "strength": str(item["strength"])
            }
        ) for item in catalogue_items_dict]

        session.add_all(catalogue_ojects)
        
        await session.commit()
        return {"message": f"Successfully uploaded {len(catalogue_ojects)} products."}

    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"An error occurred while processing the file: {str(e)}")    

