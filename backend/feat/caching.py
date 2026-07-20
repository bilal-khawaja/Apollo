import redis
from fastapi import Header, HTTPException, status
from typing import Optional

redis_client = redis.Redis(host='localhost', port=6379, db=0)

async def validate_idempotency(x_scan_id : Optional[str] = Header(None)):

    # Check if the X-Scan-ID header is present
    if not x_scan_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing X-Scan-ID header"
        )
    
    # Check if the request with the same X-Scan-ID has already been processed
    redis_key = f"idempotency:{x_scan_id}"

    # Use SETNX to set the key only if it does not already exist
    new_request = redis_client.setnx(redis_key, "processing")

    # If the key already exists, it means the request has been processed before and we should return a conflict response
    if not new_request:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Duplicate request detected"
        )

    redis_client.expire(redis_key, 300)  
