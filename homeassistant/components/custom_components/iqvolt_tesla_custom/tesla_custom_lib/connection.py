#  SPDX-License-Identifier: Apache-2.0
"""Python Package for controlling Tesla API.

For more details about this api, please refer to the documentation at
https://github.com/zabuldon/teslajsonpy
"""
from json import JSONDecodeError
import logging
from typing import Optional

from bs4 import BeautifulSoup
import httpx
import orjson
from tesla_custom_lib.const import *
from tesla_custom_lib.exceptions import TeslaException
from yarl import URL

_LOGGER = logging.getLogger(__name__)


class Connection:
    """Connection to Tesla Motors API."""

    def __init__(
        self,
        websession: Optional[httpx.AsyncClient] = None,
        wrapper_api_key: str = None,
        base_url: str = None,
        polling_policy: str = None,
    ) -> None:
        """Initialize connection object."""
        self.wrapper_api_key: str = wrapper_api_key
        self.base_url: str = base_url
        self.websession = websession
        polling_policy = polling_policy or "linear"
        self.head = {}

    async def get(self, command):
        """Get data from API."""
        return await self.post(command, "get", None)

    async def post(self, command, method="post", data=None, url=""):
        """Post data to API."""
        self.head = {"Authorization": self.wrapper_api_key}
        if not url:
            url = f"/api/1/{command.lower()}"
        return await self.__open(url, method=method, headers=self.head, data=data)

    async def __open(
        self,
        url: str,
        method: str = "get",
        headers=None,
        cookies=None,
        data=None,
        baseurl: str = "",
    ) -> None:
        """Open url."""
        headers = headers or {}
        cookies = cookies or {}
        if not baseurl:
            baseurl = self.base_url
        url: URL = URL(baseurl).join(URL(url))
        debug = _LOGGER.isEnabledFor(logging.DEBUG)
        if debug:
            _LOGGER.debug("%s: %s %s", method, url, data)

        try:
            if data:
                resp: httpx.Response = await getattr(self.websession, method)(
                    str(url), json=data, headers=headers, cookies=cookies
                )
            else:
                resp: httpx.Response = await getattr(self.websession, method)(
                    str(url), headers=headers, cookies=cookies
                )
            if debug:
                _LOGGER.debug("%s: %s", resp.status_code, resp.text)
            if resp.status_code > 299:
                if resp.status_code == 401:
                    if data and data.get("error") == "invalid_token":
                        raise TeslaException("invalid_token", resp.status_code)
                elif resp.status_code == 408:
                    raise TeslaException("vehicle_unavailable", resp.status_code)
                raise TeslaException("TeslaException", resp.status_code)
            data = orjson.loads(resp.content)  # pylint: disable=no-member
            if data.get("error"):
                # known errors:
                #     'vehicle unavailable: {:error=>"vehicle unavailable:"}',
                #     "upstream_timeout", "vehicle is curently in service"
                if debug:
                    _LOGGER.debug(
                        "Raising exception for : %s",
                        f'{data.get("error")}:{data.get("error_description")}',
                    )
                raise TeslaException(
                    f'{data.get("error")}:{data.get("error_description")}'
                )
        except httpx.HTTPStatusError as exception_:
            raise TeslaException(exception_.request.url) from exception_
        except JSONDecodeError as exception_:
            raise TeslaException("Error decoding response into json") from exception_
        return data

    async def close(self) -> None:
        """Close connection."""
        await self.websession.aclose()
        _LOGGER.debug("Connection closed")


def get_inputs(soup: BeautifulSoup, searchfield=None) -> dict[str, str]:
    """Parse soup for form with searchfield."""
    searchfield = searchfield or {"id": "form"}
    data = {}
    form = soup.find("form", searchfield)
    if not form:
        form = soup.find("form")
    if form:
        for field in form.find_all("input"):
            try:
                data[field["name"]] = ""
                if field["type"] and field["type"] == "hidden":
                    data[field["name"]] = field["value"]
            except BaseException:  # pylint: disable=broad-except
                pass
    return data
