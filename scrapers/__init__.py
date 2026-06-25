"""scrapers — Data acquisition modules for LNVE."""
from .google_maps import GoogleMapsScraper
from .yellow_pages import YellowPagesScraper

__all__ = ["GoogleMapsScraper", "YellowPagesScraper"]
