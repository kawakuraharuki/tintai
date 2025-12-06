import logging
from playwright.sync_api import Page

logger = logging.getLogger(__name__)

def stealth_sync(page: Page):
    """
    Robust wrapper for playwright-stealth that handles different versions (1.x vs 2.x).
    """
    try:
        # Try 1.x style (function export)
        from playwright_stealth import stealth_sync as _stealth_sync
        _stealth_sync(page)
        return
    except ImportError:
        pass

    try:
        # Try 2.x style (Class based)
        from playwright_stealth import Stealth
        stealth = Stealth()
        if hasattr(stealth, "apply_stealth_sync"):
            stealth.apply_stealth_sync(page)
            return
    except ImportError:
        pass

    try:
        # Fallback for some versions where stealth is a module but aliased
        from playwright_stealth import stealth as _stealth_sync
        if callable(_stealth_sync):
            _stealth_sync(page)
            return
    except ImportError:
        pass
        
    logger.warning("Could not apply stealth_sync. playwright-stealth might not be installed correctly.")
