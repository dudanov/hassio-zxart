"""Expose ZXArt Browser as a media source."""

from __future__ import annotations

from typing import Literal, Unpack, override

from homeassistant.components.media_player.const import MediaClass, MediaType
from homeassistant.components.media_source import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
    Unresolvable,
)
from homeassistant.core import HomeAssistant, callback
from zxart import Entity, Order, ZXArtClient
from zxart.common import CommonOptions
from zxart.models import MediaBase

from . import ZXArtConfigEntry
from .const import DOMAIN

type Media = Literal["tune", "image"]

_MAP_MIMETYPE = {
    "tune": "audio/mpeg",
    "image": "image/png",
}


async def async_get_media_source(hass: HomeAssistant) -> ZXArtMediaSource:
    """Set up ZXArt Browser media source."""

    # ZXArt supports only a single config entry
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    return ZXArtMediaSource(hass, entry)


class ZXArtMediaSource(MediaSource):
    """Provide ZXArt.ee resources as media sources."""

    name = "ZXArt Browser"
    urls: dict[str, str]

    def __init__(self, hass: HomeAssistant, entry: ZXArtConfigEntry) -> None:
        """Initialize ZXArtMediaSource."""

        super().__init__(DOMAIN)
        self.hass = hass
        self.entry = entry
        self.urls = {}

    @property
    def zxart(self) -> ZXArtClient:
        """Return the ZXArt API client."""

        return self.entry.runtime_data

    @override
    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve selected ZXArt station to a streaming URL."""

        media, _, id = item.identifier.partition("/")
        mimetype = _MAP_MIMETYPE[media]

        if url := self.urls.get(id):
            return PlayMedia(url, mimetype)

        raise Unresolvable("ZXArt tune is no available")

    @override
    async def async_browse_media(self, item: MediaSourceItem) -> BrowseMediaSource:
        """Return media."""

        if item.identifier:
            zxart = self.zxart
            children = [
                *await self._async_build_recent(zxart, item),
                *await self._async_build_rated(zxart, item),
                *await self._async_build_placed(zxart, item),
                *await self._async_build_commented(zxart, item),
                *await self._async_build_played(zxart, item),
            ]

        else:
            # Корневые элементы
            children = [
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier="tune",
                    media_class=MediaClass.DIRECTORY,
                    media_content_type=MediaType.MUSIC,
                    title="Tunes",
                    can_play=False,
                    can_expand=True,
                ),
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier="image",
                    media_class=MediaClass.DIRECTORY,
                    media_content_type=MediaType.IMAGE,
                    title="Images",
                    can_play=False,
                    can_expand=True,
                ),
            ]

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=None,
            media_class=MediaClass.DIRECTORY,
            media_content_type=MediaType.PLAYLIST,
            title=self.entry.title,
            can_play=False,
            can_expand=True,
            children_media_class=MediaClass.DIRECTORY,
            children=children,
        )

    @callback
    def _async_build_media[T: MediaBase](
        self,
        media_type: Media,
        media: list[T],
    ) -> list[BrowseMediaSource]:
        """Создает список источников медиа из списка мелодий."""

        items: list[BrowseMediaSource] = []
        mimetype = _MAP_MIMETYPE[media_type]

        if media_type == "tune":
            media_class, has_thumbnail = MediaClass.MUSIC, False
        else:
            media_class, has_thumbnail = MediaClass.IMAGE, True

        for x in media:
            if (url := x.media_url) is None:
                continue

            # Сохраняем ссылку на медиа для последующего резолвинга
            self.urls[id := str(x.id)] = url

            items.append(
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=f"{media_type}/{id}",
                    media_class=media_class,
                    media_content_type=mimetype,
                    title=x.title,
                    can_play=True,
                    can_expand=False,
                    thumbnail=url if has_thumbnail else None,
                )
            )

        return items

    async def _async_build_generic(
        self,
        zxart: ZXArtClient,
        item: MediaSourceItem,
        identifier: str,
        folder_name: str,
        **kwargs: Unpack[CommonOptions],
    ) -> list[BrowseMediaSource]:
        """Универсальный обработчик просмотра мелодий."""

        media_type, _, group = item.identifier.partition("/")

        # Отображаем наш идентификатор
        if group == identifier:
            if media_type == "tune":
                stations = await zxart.api(Entity.TUNE, **kwargs)
                return self._async_build_media(media_type, stations.result)

            if media_type == "image":
                stations = await zxart.api(Entity.IMAGE, **kwargs)
                return self._async_build_media(media_type, stations.result)

            return []

        # Отображаем корневой элемент
        if not group:
            if media_type == "tune":
                content_type = MediaType.MUSIC
            else:
                content_type = MediaType.IMAGE

            return [
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=f"{media_type}/{identifier}",
                    media_class=MediaClass.DIRECTORY,
                    media_content_type=content_type,
                    title=folder_name,
                    can_play=False,
                    can_expand=True,
                )
            ]

        # Отображаем другой элемент
        return []

    async def _async_build_rated(
        self,
        zxart: ZXArtClient,
        item: MediaSourceItem,
    ) -> list[BrowseMediaSource]:
        """Обработчик просмотра популярных мелодий."""

        return await self._async_build_generic(
            zxart=zxart,
            item=item,
            identifier="rated",
            folder_name="Top Rated",
            limit=250,
            order=Order.TOP_RATED,
        )

    async def _async_build_placed(
        self,
        zxart: ZXArtClient,
        item: MediaSourceItem,
    ) -> list[BrowseMediaSource]:
        """Обработчик просмотра популярных мелодий."""

        return await self._async_build_generic(
            zxart=zxart,
            item=item,
            identifier="placed",
            folder_name="Top Placed",
            limit=250,
            order=Order.TOP_PLACED,
        )

    async def _async_build_commented(
        self,
        zxart: ZXArtClient,
        item: MediaSourceItem,
    ) -> list[BrowseMediaSource]:
        """Обработчик просмотра популярных мелодий."""

        return await self._async_build_generic(
            zxart=zxart,
            item=item,
            identifier="commented",
            folder_name="Most Commented",
            limit=250,
            order=Order.MOST_COMMENTED,
        )

    async def _async_build_played(
        self,
        zxart: ZXArtClient,
        item: MediaSourceItem,
    ) -> list[BrowseMediaSource]:
        """Обработчик просмотра популярных мелодий."""

        return await self._async_build_generic(
            zxart=zxart,
            item=item,
            identifier="played",
            folder_name="Most Played",
            limit=250,
            order=Order.MOST_PLAYED,
        )

    async def _async_build_recent(
        self,
        zxart: ZXArtClient,
        item: MediaSourceItem,
    ) -> list[BrowseMediaSource]:
        """Обработчик просмотра популярных мелодий."""

        return await self._async_build_generic(
            zxart=zxart,
            item=item,
            identifier="recent",
            folder_name="Most Recent",
            limit=250,
            order=Order.MOST_RECENT,
        )
