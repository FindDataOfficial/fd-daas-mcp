from __future__ import annotations

import scrapy


class RecordItem(scrapy.Item):
    """Generic observation record. Replace fields with the source's schema."""

    key = scrapy.Field()        # primary key / natural id
    value = scrapy.Field()      # payload (string/number/JSON)
    crawl_time = scrapy.Field()  # provenance: when crawled
    source = scrapy.Field()     # provenance: source URL / dataset id
