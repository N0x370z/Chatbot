import asyncio
import logging

import aiohttp

logger = logging.getLogger(__name__)


async def _retry_get(session: aiohttp.ClientSession, url: str, **kwargs) -> aiohttp.ClientResponse:
    """GET with automatic retry on transient errors (timeout / 5xx).

    - 4xx responses are returned immediately without retrying.
    - 5xx responses trigger up to 2 retries with 1s / 2s back-off.
    - The caller is responsible for calling raise_for_status() on the final response.
    """
    delays = [1, 2]
    attempts = 3

    for attempt in range(attempts):
        try:
            resp = await session.get(url, **kwargs)

            if 400 <= resp.status < 500:
                return resp

            if resp.status >= 500:
                await resp.release()
                if attempt < attempts - 1:
                    logger.warning(
                        "Request to %s returned HTTP %d, retrying in %ds...",
                        url, resp.status, delays[attempt],
                    )
                    await asyncio.sleep(delays[attempt])
                    continue
                resp.raise_for_status()

            return resp

        except (TimeoutError, aiohttp.ClientError) as e:
            if isinstance(e, aiohttp.ClientResponseError) and 400 <= e.status < 500:
                raise

            if attempt < attempts - 1:
                logger.warning(
                    "Request to %s failed (%s), retrying in %ds...",
                    url, e, delays[attempt],
                )
                await asyncio.sleep(delays[attempt])
            else:
                raise
