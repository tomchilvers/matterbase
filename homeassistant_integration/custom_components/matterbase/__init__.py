"""A sidebar connector for the independent Matterbase server. No entities or devices."""
from pathlib import Path
from homeassistant.components.frontend import async_remove_panel
from homeassistant.components.http import StaticPathConfig
from homeassistant.components.panel_custom import async_register_panel

DOMAIN = "matterbase"


async def async_setup_entry(hass, entry):
    state = hass.data.setdefault(DOMAIN, {})
    if not state.get("static_registered"):
        await hass.http.async_register_static_paths([
            StaticPathConfig("/matterbase-integration/panel.js", str(Path(__file__).parent / "web/panel.js"), False)
        ])
        state["static_registered"] = True
    await async_register_panel(
        hass, frontend_url_path=DOMAIN, webcomponent_name="matterbase-panel",
        sidebar_title="Matterbase", sidebar_icon="mdi:qrcode-scan",
        module_url="/matterbase-integration/panel.js?v=1.0.0",
        config={"url": entry.data["url"]}, require_admin=True,
    )
    return True


async def async_unload_entry(hass, entry):
    async_remove_panel(hass, DOMAIN)
    return True
