import asyncio
import logging
import aiohttp

logger = logging.getLogger(__name__)

async def _retry_get(session: aiohttp.ClientSession, url: str, **kwargs) -> aiohttp.ClientResponse:
    """
    Helper to retry GET requests on timeout or client error.
    Retries up to 2 times (total 3 attempts) with delays of 1s and 2s.
    Do not retry on HTTP 4xx responses.
    Note: The caller is responsible for raising or handling status errors on the final response,
    BUT since we need to inspect status codes to avoid retrying 4xx, we call raise_for_status() here
    to catch them, or we can just read response.status.
    """
    delays = [1, 2]
    attempts = 3
    
    for attempt in range(attempts):
        try:
            resp = await session.get(url, **kwargs)
            
            # If 4xx, do not retry, just return or let caller handle it.
            # We'll just return the response and let the caller do raise_for_status().
            # BUT wait, what if it's 5xx? We should retry 5xx!
            if 400 <= resp.status < 500:
                return resp
                
            if resp.status >= 500:
                resp.raise_for_status() # trigger ClientResponseError to retry
            
            return resp
            
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            if isinstance(e, aiohttp.ClientResponseError) and 400 <= e.status < 500:
                raise # do not retry 4xx
                
            if attempt < attempts - 1:
                logger.warning("Request to %s failed (%s), retrying in %ds...", url, e, delays[attempt])
                await asyncio.sleep(delays[attempt])
            else:
                raise
