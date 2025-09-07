import aiohttp


class _HttpClient:
    """A robust, shared HTTP client for downloading files and making API calls."""
    def __init__(
        self, timeout_connect: float = 5.0, timeout_read: float = 20.0, limit: int = 100
    ) -> None:
        self._timeout_connect = timeout_connect
        self._timeout_read = timeout_read
        self._limit = limit
        self._session: aiohttp.ClientSession | None = None

    async def session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(
                total=None, connect=self._timeout_connect, sock_read=self._timeout_read
            )
            connector = aiohttp.TCPConnector(
                limit=self._limit, ssl=False, ttl_dns_cache=60
            )
            self._session = aiohttp.ClientSession(
                timeout=timeout, connector=connector, trust_env=True
            )
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()


# A single, shared instance to be used across the application
http_client = _HttpClient()
