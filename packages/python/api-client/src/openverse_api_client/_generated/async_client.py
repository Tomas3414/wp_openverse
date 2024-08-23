"""
Fully typed Openverse API client.

This file is generated from a template. Do not edit it by hand!

See https://docs.openverse.org/packages/python/api-client/index.html#development-and-implementation-details
"""

from typing_extensions import cast, Self, overload
import typing_extensions as typing
import httpx

from openverse_api_client._generated.models import (
    OAuth2KeyInfo,
    OAuth2Token,
    OAuth2Application,
    Source,
    AudioWaveform,
    Audio,
    Image,
    PaginatedImageList,
    PaginatedAudioList,
)
from openverse_api_client._generated import routes
from openverse_api_client._auth import OpenverseAuth
from openverse_api_client._response import Response, Request


EXPIRY_THRESHOLD = 30


class AsyncOpenverseClient:
    base_url: str = "https://api.openverse.org"
    auth: OpenverseAuth | None = None
    client: httpx.AsyncClient
    endpoints = routes.ENDPOINTS

    _is_shared_client: bool

    def __init__(
        self,
        base_url: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        httpx_client: httpx.AsyncClient | None = None,
    ):
        self.base_url = base_url if base_url else self.base_url
        if self.base_url[-1] == "/":
            self.base_url = self.base_url[:-1]

        if httpx_client is None:
            self.client = httpx.AsyncClient()
            self._is_shared_client = False
        else:
            self.client = httpx_client
            self._is_shared_client = True

        if client_id or client_secret:
            if not client_id and client_secret:
                raise ValueError(
                    "`client_id` and `client_secret` are both required when either is defined"
                )

            self.auth = OpenverseAuth(
                client=self,
                client_id=typing.cast(str, client_id),
                client_secret=typing.cast(str, client_secret),
            )

    def unauthed(self) -> Self:
        return cast(
            Self,
            AsyncOpenverseClient(
                base_url=self.base_url,
                httpx_client=self.client,
            ),
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type=None, exc_value=None, traceback=None) -> None:
        await self.client.__aexit__(exc_type, exc_value, traceback)

    async def close(self):
        await self.client.aclose()

    async def _base_request(
        self,
        *,
        method: str,
        path: str,
        **kwargs,
    ) -> httpx.Response:
        return await self.client.request(
            method=method,
            url=f"{self.base_url}{path}",
            **kwargs,
        )

    async def _request(
        self,
        *,
        method: str,
        path: str,
        **kwargs,
    ) -> httpx.Response:
        kwargs.setdefault("auth", self.auth)
        return await self._base_request(
            method=method,
            path=path,
            **kwargs,
        )

    @overload
    async def __call__(
        self,
        route: type[routes.v1_audio_search] | routes.v1_audio_search,
        headers: dict[str, str] | httpx.Headers | None = None,
    ) -> Response[PaginatedAudioList]: ...

    @overload
    async def __call__(
        self,
        route: type[routes.v1_audio] | routes.v1_audio,
        headers: dict[str, str] | httpx.Headers | None = None,
    ) -> Response[Audio]: ...

    @overload
    async def __call__(
        self,
        route: type[routes.v1_audio_related] | routes.v1_audio_related,
        headers: dict[str, str] | httpx.Headers | None = None,
    ) -> Response[PaginatedAudioList]: ...

    @overload
    async def __call__(
        self,
        route: type[routes.v1_audio_thumb] | routes.v1_audio_thumb,
        headers: dict[str, str] | httpx.Headers | None = None,
    ) -> Response[bytes]: ...

    @overload
    async def __call__(
        self,
        route: type[routes.v1_audio_waveform] | routes.v1_audio_waveform,
        headers: dict[str, str] | httpx.Headers | None = None,
    ) -> Response[AudioWaveform]: ...

    @overload
    async def __call__(
        self,
        route: type[routes.v1_audio_stats] | routes.v1_audio_stats,
        headers: dict[str, str] | httpx.Headers | None = None,
    ) -> Response[list[Source]]: ...

    @overload
    async def __call__(
        self,
        route: type[routes.v1_auth_tokens_register] | routes.v1_auth_tokens_register,
        headers: dict[str, str] | httpx.Headers | None = None,
    ) -> Response[OAuth2Application]: ...

    @overload
    async def __call__(
        self,
        route: type[routes.v1_auth_tokens_token] | routes.v1_auth_tokens_token,
        headers: dict[str, str] | httpx.Headers | None = None,
    ) -> Response[OAuth2Token]: ...

    @overload
    async def __call__(
        self,
        route: type[routes.v1_image_search] | routes.v1_image_search,
        headers: dict[str, str] | httpx.Headers | None = None,
    ) -> Response[PaginatedImageList]: ...

    @overload
    async def __call__(
        self,
        route: type[routes.v1_image] | routes.v1_image,
        headers: dict[str, str] | httpx.Headers | None = None,
    ) -> Response[Image]: ...

    @overload
    async def __call__(
        self,
        route: type[routes.v1_image_related] | routes.v1_image_related,
        headers: dict[str, str] | httpx.Headers | None = None,
    ) -> Response[Image]: ...

    @overload
    async def __call__(
        self,
        route: type[routes.v1_image_thumb] | routes.v1_image_thumb,
        headers: dict[str, str] | httpx.Headers | None = None,
    ) -> Response[bytes]: ...

    @overload
    async def __call__(
        self,
        route: type[routes.v1_image_stats] | routes.v1_image_stats,
        headers: dict[str, str] | httpx.Headers | None = None,
    ) -> Response[list[Source]]: ...

    @overload
    async def __call__(
        self,
        route: type[routes.v1_rate_limit] | routes.v1_rate_limit,
        headers: dict[str, str] | httpx.Headers | None = None,
    ) -> Response[OAuth2KeyInfo]: ...

    async def __call__(
        self,
        route: type[routes.Route] | routes.Route,
        headers: dict[str, str] | httpx.Headers | None = None,
    ):
        if not isinstance(route, routes.Route):
            # Allow passing a raw Route class without instantiating it for paramless requests
            # Also allow it to raise a type error in case the route has required parameters
            route = route()

        path = route.path

        if route.path_params:
            path = path.format(**route.path_params)

        req_kwargs = {
            "params": route.query_params,
            "headers": headers,
        }

        if route.content_type == "application/json":
            req_kwargs["json"] = route.body
        else:
            req_kwargs["data"] = route.body

        response = await self._request(method=route.method, path=path, **req_kwargs)

        await response.aread()
        if route.json_response:
            content = response.json()
        else:
            content = response.content

        return Response(
            body=content,
            status_code=response.status_code,
            headers=response.headers,
            request=Request(
                headers=response.request.headers,
                content=response.request.content,
                url=str(response.request.url),
                method=response.request.method,
            ),
        )
